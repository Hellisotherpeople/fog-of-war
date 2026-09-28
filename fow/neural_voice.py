"""Natural voices: Piper, a small neural speech synthesiser that runs locally on the CPU.

The system synthesiser (macOS `say`, espeak) is instant and always there, and sounds like it.
Piper sounds like people.  It needs the `piper-tts` package (pip install -r requirements-voices.txt)
and one voice model per language, which the game downloads the first time a battle needs it
(60-80 MB each, into ~/.fogofwar/piper) - and until then, and for languages Piper has no man's
voice for (Japanese, Chinese), the system voice carries on.

Several of the models hold many speakers - 904 American, 109 British and Irish (with their regional
accents), 236 German, 125 French - so every soldier gets a voice of his own.  They're sorted into men
and women by measuring each speaker's pitch the first time the model's used.
"""
from __future__ import annotations

import json
import os
import threading
import wave

import numpy as np

DIR = os.path.join(os.path.expanduser("~"), ".fogofwar", "piper")
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

# per locale: the men's model (the first found or downloaded is used) and a women's model
MODELS = {
    # (men, women).  The many-speaker English models give every man his own voice; elsewhere a few single
    # voices (the many-speaker German and French models mumble through short commands, so they're not used)
    "en_US": (["en_US-libritts_r-medium"], ["en_US-lessac-medium"]),
    "en_GB": (["en_GB-vctk-medium"], ["en_GB-jenny_dioco-medium"]),
    "en_AU": (["en_GB-vctk-medium"], ["en_GB-jenny_dioco-medium"]),
    "en_IN": (["en_GB-vctk-medium"], ["en_GB-jenny_dioco-medium"]),
    "de_DE": (["de_DE-thorsten-medium", "de_DE-karlsson-low", "de_DE-pavoque-low"], ["de_DE-kerstin-low"]),
    "fr_FR": (["fr_FR-tom-medium", "fr_FR-gilles-low"], ["fr_FR-siwis-medium"]),
    "ru_RU": (["ru_RU-dmitri-medium", "ru_RU-denis-medium", "ru_RU-ruslan-medium"], ["ru_RU-irina-medium"]),
    "it_IT": (["it_IT-riccardo-x_low"], ["it_IT-paola-medium"]),
    "pl_PL": (["pl_PL-darkman-medium"], ["pl_PL-gosia-medium"]),
    "fi_FI": (["fi_FI-harri-medium"], []),
    "hu_HU": (["hu_HU-imre-medium"], ["hu_HU-anna-medium"]),
    "ro_RO": (["ro_RO-mihai-medium"], []),
}
MAX_VARIANTS = 12            # distinct voices per army from a many-speaker model


def available() -> bool:
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def _path(key):
    return os.path.join(DIR, key + ".onnx")


def have(key) -> bool:
    return os.path.exists(_path(key)) and os.path.exists(_path(key) + ".json")


def _url(key, ext):
    code, name, quality = key.split("-")
    return f"{BASE}/{code[:2]}/{code}/{name}/{quality}/{key}{ext}"


class Downloader:
    """Fetches voice models in the background, one at a time."""

    def __init__(self):
        self.queue = []
        self.active = None
        self.failed = set()
        self.done = []
        self.lock = threading.Lock()
        self.thread = None
        self.running = False        # (set and cleared under the lock: a thread on its way out doesn't count)

    def want(self, key):
        with self.lock:
            if have(key) or key in self.queue or key == self.active or key in self.failed:
                return
            self.queue.append(key)
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()

    def _run(self):
        import urllib.request
        while True:
            with self.lock:
                if not self.queue:
                    self.active = None
                    self.running = False
                    return
                key = self.active = self.queue.pop(0)
            os.makedirs(DIR, exist_ok=True)
            ok = True
            for ext in (".onnx.json", ".onnx"):
                dest = _path(key) + (".json" if ext == ".onnx.json" else "")
                if os.path.exists(dest):
                    continue
                tmp = dest + ".part"
                try:
                    with urllib.request.urlopen(_url(key, ext), timeout=60) as r, open(tmp, "wb") as f:
                        while True:
                            b = r.read(1 << 16)
                            if not b:
                                break
                            f.write(b)
                    os.replace(tmp, dest)
                except Exception:
                    ok = False
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                    break
            with self.lock:
                if ok:
                    self.done.append(key)
                else:
                    self.failed.add(key)


def _f0(x, sr) -> float:
    """The median pitch (Hz) of a stretch of speech, by autocorrelation over voiced frames."""
    n = int(sr * 0.04)
    lo, hi = int(sr / 350), int(sr / 70)
    out = []
    for i in range(0, len(x) - n, n // 2):
        fr = x[i:i + n] - x[i:i + n].mean()
        e = float(np.dot(fr, fr))
        if e < 1e-3:
            continue
        ac = np.correlate(fr, fr, "full")[n - 1:]
        seg = ac[lo:hi]
        if len(seg) == 0:
            continue
        k = int(np.argmax(seg))
        if seg[k] > 0.4 * ac[0]:
            out.append(sr / (lo + k))
    return float(np.median(out)) if out else 0.0


class Piper:
    """The engine: loads each model once, renders a line to a WAV file."""
    name = "piper"

    def __init__(self):
        self.models = {}
        self.lock = threading.Lock()
        self.dl = Downloader()
        self.genders = self._load_genders()

    # ---------------------------------------------------------------- which voices
    def _load_genders(self):
        try:
            with open(os.path.join(DIR, "speakers.json")) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_genders(self):
        try:
            os.makedirs(DIR, exist_ok=True)
            with open(os.path.join(DIR, "speakers.json"), "w") as f:
                json.dump(self.genders, f)
        except Exception:
            pass

    def model_for(self, locale, female=False, fetch=True):
        """The first of this locale's men's (or women's) models that's here; the missing ones are fetched, in
        order, in the background."""
        men, women = MODELS.get(locale, ([], []))
        pool = women if female else men
        if fetch:
            for key in pool:
                if not have(key):
                    self.dl.want(key)
        return next((k for k in pool if have(k)), None)

    def voices(self, locale, female=False):
        """Voice ids for this locale ('piper:model' or 'piper:model:speaker'), [] until one is ready."""
        if self.model_for(locale, female) is None:
            return []
        men, women = MODELS.get(locale, ([], []))
        out = []
        for key in (women if female else men):
            if not have(key):
                continue
            n = self._num_speakers(key)
            if n <= 1:
                out.append(f"piper:{key}")
                continue
            picks = self.genders.get(key)
            if picks is None:
                picks = self._sort_speakers(key, n)
            chosen = picks.get("f" if female else "m") or picks.get("m") or [0]
            out += [f"piper:{key}:{s}" for s in chosen[:MAX_VARIANTS]]
        return out

    def _num_speakers(self, key):
        try:
            with open(_path(key) + ".json") as f:
                return int(json.load(f).get("num_speakers", 1))
        except Exception:
            return 1

    def _sort_speakers(self, key, n):
        """Men and women among a many-speaker model's voices, by pitch (done once; remembered)."""
        rng = np.random.default_rng(7)
        ids = sorted(rng.choice(n, size=min(n, 48), replace=False).tolist())
        m, f = [], []
        for sid in ids:
            x, sr = self._synth(key, "Hold that line and keep your heads down.", sid, 1.0, 0.667, 0.8)
            if x is None:
                continue
            hz = _f0(x, sr)
            if 70 < hz < 150:
                m.append(sid)
            elif hz > 175:
                f.append(sid)
        picks = {"m": m, "f": f}
        self.genders[key] = picks
        self._save_genders()
        return picks

    # ---------------------------------------------------------------- rendering
    def _voice(self, key):
        v = self.models.get(key)
        if v is None:
            from piper import PiperVoice
            v = self.models[key] = PiperVoice.load(_path(key), config_path=_path(key) + ".json")
        return v

    def _synth(self, key, text, speaker, length, noise, noise_w):
        from piper.config import SynthesisConfig
        with self.lock:
            voice = self._voice(key)
            cfg = SynthesisConfig(speaker_id=speaker, length_scale=length, noise_scale=noise, noise_w_scale=noise_w)
            chunks = list(voice.synthesize(text, syn_config=cfg))
        if not chunks:
            return None, 0
        sr = chunks[0].sample_rate
        x = np.concatenate([c.audio_float_array for c in chunks]).astype(np.float32)
        return x, sr

    def render(self, voice, text, rate, pbas, path) -> bool:
        parts = voice.split(":")
        key = parts[1]
        speaker = int(parts[2]) if len(parts) > 2 else None
        # the system synth's words-a-minute, as Piper's pace; shouting and screaming come out livelier
        length = max(0.7, min(1.25, 185.0 / max(120, rate)))
        lively = rate >= 225
        try:
            x, sr = self._synth(key, text, speaker, length, 0.8 if lively else 0.667, 0.95 if lively else 0.8)
        except Exception:
            return False
        if x is None or len(x) == 0:
            return False
        pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        return os.path.getsize(path) > 1000


def status(locales) -> list[str]:
    """For the Options screen: what's downloaded, what isn't."""
    out = []
    for loc in locales:
        men, _w = MODELS.get(loc, ([], []))
        got = next((k for k in men if have(k)), None)
        out.append(f"{loc}: {got or ('not downloaded' if men else 'no neural voice (system voice)')}")
    return out


def size_mb(key) -> int:
    return 80 if any(s in key for s in ("libritts", "vctk", "mls")) else 63
