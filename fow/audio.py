"""Synthesised, positional sound.

Every sound is generated with numpy at startup (no audio assets).  Game events
are queued by Game.emit_sound() into game.audio_events; each frame Audio.update()
turns them into voices with distance attenuation, stereo panning, muffling for
distant sounds / deafness / being inside a tank, and small time offsets so a
batch of turns plays out as a firefight rather than one bang.

SDL3 mixes every bound audio stream, so a pool of streams is the mixer.
"""
from __future__ import annotations

import math
import random
import time

import numpy as np

SR = 44100


# ====================================================================== synthesis helpers

def _t(dur):
    return np.arange(int(SR * dur), dtype=np.float32) / SR


def _noise(n, rng):
    return rng.standard_normal(n).astype(np.float32)


def _filter(x, lo=None, hi=None):
    """Band-limit with an FFT mask (smooth roll-off)."""
    n = len(x)
    if n == 0:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    mask = np.ones_like(f)
    if hi is not None:
        mask *= 1 / (1 + (f / hi) ** 4)
    if lo is not None:
        mask *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X * mask, n).astype(np.float32)


def _env(n, attack=0.001, decay=0.1):
    t = np.arange(n, dtype=np.float32) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def _pad(x, dur):
    n = int(SR * dur)
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros(n - len(x), np.float32)])


def _reverb(x, taps=((0.07, 0.35), (0.16, 0.22), (0.31, 0.14), (0.55, 0.08)), rng=None):
    extra = int(SR * (taps[-1][0] + 0.1))
    out = np.concatenate([x, np.zeros(extra, np.float32)])
    for delay, gain in taps:
        d = int(SR * delay)
        out[d:d + len(x)] += _filter(x, hi=2500) * gain
    return out


def _norm(x, peak=0.9):
    m = np.max(np.abs(x)) if len(x) else 0
    return (x / m * peak).astype(np.float32) if m > 0 else x


def _shot(rng, crack=1.0, body_hi=2200, body_decay=0.06, boom_hz=90, boom=0.6, dur=0.5):
    n = int(SR * dur)
    x = np.zeros(n, np.float32)
    c = _filter(_noise(int(SR * 0.004), rng), lo=2500) * crack
    x[:len(c)] += c * _env(len(c), 0.0002, 0.002)
    b = _filter(_noise(n, rng), hi=body_hi) * _env(n, 0.0005, body_decay)
    x += b * 1.2
    t = _t(dur)
    x += np.sin(2 * np.pi * boom_hz * t * (1 - t * 0.5)) * _env(n, 0.001, body_decay * 2.2) * boom
    return x


# ====================================================================== the sound bank

class Bank:
    def __init__(self, seed=7):
        rng = np.random.default_rng(seed)
        self.rng = rng
        self.s: dict[str, list[np.ndarray]] = {}
        add = self._add
        for v in range(3):
            add("rifle", _reverb(_shot(rng, 1.0, 2400, 0.05, 95, 0.7)))
            add("pistol", _reverb(_shot(rng, 0.8, 3200, 0.03, 140, 0.35, 0.35)))
            add("shotgun", _reverb(_shot(rng, 0.9, 1800, 0.08, 80, 0.9)))
            add("atrifle", _reverb(_shot(rng, 1.0, 1500, 0.1, 60, 1.0, 0.8)))
            add("cannon", _reverb(self._explosion(rng, 0.9, crack=True)))
            add("expl_small", _reverb(self._explosion(rng, 0.6)))
            add("expl_med", _reverb(self._explosion(rng, 1.2)))
            add("expl_big", _reverb(self._explosion(rng, 2.2), taps=((0.12, 0.4), (0.3, 0.3), (0.6, 0.2), (1.0, 0.1))))
        add("mortar", self._mortar(rng))
        add("rocket", self._rocket(rng))
        add("whistle", self._shell_whistle(rng))
        add("siren", self._siren())
        add("ricochet", self._ricochet(rng))
        add("ricochet", self._ricochet(rng, 2600))
        add("whizz", self._whizz(rng))
        add("whizz", self._whizz(rng, 1.3))
        add("ping", self._ping())
        add("clang", self._clang(rng))
        add("click", self._click(rng))
        add("reload", self._reload(rng))
        add("thud", self._thud(rng))
        add("engine", self._engine(rng, 38))
        add("truck", self._engine(rng, 70, tracks=False))
        add("aircraft", self._aircraft(rng))
        add("flamer", self._flamer(rng))
        add("glass", self._glass(rng))
        add("whistle_officer", self._officer_whistle())
        add("radio", self._radio(rng))
        add("step", self._step(rng))
        add("splash", self._splash(rng))
        add("crash", _reverb(self._explosion(rng, 0.5) * 0.7))
        add("pop", self._pop(rng))
        add("hiss", self._hiss(rng))
        add("ui", self._ui_click())
        add("rustle", self._rustle(rng))
        # far / muffled versions for anything loud
        for k in list(self.s):
            if k in ("rifle", "pistol", "shotgun", "atrifle", "cannon", "expl_small", "expl_med", "expl_big",
                     "mortar", "engine", "truck", "aircraft", "flamer", "rocket"):
                self.s[k + "_far"] = [_norm(_reverb(_filter(x, hi=650), taps=((0.2, 0.4), (0.45, 0.25), (0.8, 0.15))), 0.6)
                                      for x in self.s[k]]
        # loops
        self.loops = {"battle": self._battle_loop(rng), "wind": self._wind_loop(rng), "rain": self._rain_loop(rng),
                      "tinnitus": self._tinnitus()}
        self._bursts: dict = {}

    def _add(self, k, x):
        self.s.setdefault(k, []).append(_norm(x))

    def get(self, k):
        v = self.s.get(k)
        if not v:
            return None
        return v[random.randrange(len(v))]

    def burst(self, kind, rps, n):
        """A burst of automatic fire at the weapon's real cyclic rate."""
        key = (kind, int(rps), int(n))
        b = self._bursts.get(key)
        if b is not None:
            return b
        base = self.s["rifle" if kind == "mg" else "pistol"]
        interval = 1.0 / max(1.0, rps)
        L = int(SR * (interval * n + 0.9))
        out = np.zeros(L, np.float32)
        for i in range(n):
            s = base[i % len(base)]
            start = int(SR * (i * interval + random.uniform(0, interval * 0.1)))
            seg = s[: min(len(s), L - start)] * (0.8 + 0.2 * random.random())
            out[start:start + len(seg)] += seg
        b = _norm(out, 0.95)
        self._bursts[key] = b
        self._bursts[key + ("far",)] = _norm(_filter(b, hi=650), 0.6)
        return b

    def burst_far(self, kind, rps, n):
        self.burst(kind, rps, n)
        return self._bursts[(kind, int(rps), int(n), "far")]

    # ---- individual sounds
    def _explosion(self, rng, size, crack=False):
        dur = 0.8 + size * 0.8
        n = int(SR * dur)
        brown = np.cumsum(_noise(n, rng))
        brown -= np.linspace(0, brown[-1], n)
        brown = _filter(brown / (np.max(np.abs(brown)) + 1e-6), hi=180 + 120 / size)
        x = brown * _env(n, 0.004, 0.25 * size + 0.1) * 1.6
        x += _filter(_noise(n, rng), hi=1400) * _env(n, 0.001, 0.08 + 0.05 * size) * 0.9
        # debris patter
        for _ in range(int(8 * size)):
            p = int(rng.uniform(0.15, dur * 0.8) * SR)
            k = int(SR * 0.01)
            if p + k < n:
                x[p:p + k] += _filter(_noise(k, rng), lo=800, hi=3000) * 0.08
        if crack:
            c = _filter(_noise(int(SR * 0.006), rng), lo=1800)
            x[:len(c)] += c * 1.5
        return x

    def _mortar(self, rng):
        n = int(SR * 0.4)
        t = _t(0.4)
        x = np.sin(2 * np.pi * 120 * t) * _env(n, 0.002, 0.08)
        x += _filter(_noise(n, rng), hi=600) * _env(n, 0.001, 0.05) * 0.8
        return _reverb(x)

    def _rocket(self, rng):
        n = int(SR * 0.9)
        t = _t(0.9)
        x = _filter(_noise(n, rng), lo=400, hi=3500) * np.minimum(1, t * 8) * np.exp(-t * 2.5)
        return x

    def _shell_whistle(self, rng):
        dur = 1.3
        t = _t(dur)
        f = 1700 - 1150 * (t / dur) ** 1.4
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = np.sin(ph + 0.3 * np.sin(2 * np.pi * 7 * t)) * (0.25 + 0.75 * (t / dur) ** 2)
        x += _filter(_noise(len(t), rng), lo=500, hi=2000) * 0.15 * (t / dur)
        return x

    def _siren(self):
        dur = 3.0
        t = _t(dur)
        f = 420 + 520 * (t / dur) ** 0.8
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)) * np.minimum(1, t * 2)
        return x

    def _ricochet(self, rng, f0=3400):
        dur = 0.45
        t = _t(dur)
        f = f0 - (f0 * 0.6) * t / dur
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = np.sin(ph) * np.exp(-t * 6)
        x[: int(SR * 0.003)] += _noise(int(SR * 0.003), rng) * 0.8
        return x

    def _whizz(self, rng, speed=1.0):
        n = int(SR * 0.12 / speed)
        x = _filter(_noise(n, rng), lo=2500) * _env(n, 0.005, 0.03)
        x[: int(SR * 0.002)] += 1.0
        return x

    def _ping(self):
        t = _t(0.7)
        return (np.sin(2 * np.pi * 3850 * t) + 0.6 * np.sin(2 * np.pi * 5230 * t) +
                0.3 * np.sin(2 * np.pi * 7100 * t)) * np.exp(-t * 7)

    def _clang(self, rng):
        t = _t(0.8)
        x = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((310, 1), (820, 0.7), (1370, 0.5), (2230, 0.3)))
        x = x * np.exp(-t * 5)
        x[: int(SR * 0.01)] += _noise(int(SR * 0.01), rng) * 2
        return _reverb(x)

    def _click(self, rng):
        n = int(SR * 0.05)
        x = np.zeros(n, np.float32)
        k = int(SR * 0.004)
        x[:k] = _filter(_noise(k, rng), lo=2000) * np.linspace(1, 0, k)
        return x

    def _reload(self, rng):
        n = int(SR * 0.6)
        x = np.zeros(n, np.float32)
        for at in (0.0, 0.28, 0.4):
            p = int(SR * at)
            k = int(SR * 0.012)
            x[p:p + k] += _filter(_noise(k, rng), lo=1200, hi=6000) * np.linspace(1, 0, k)
        return x

    def _thud(self, rng):
        t = _t(0.3)
        return np.sin(2 * np.pi * 70 * t) * np.exp(-t * 18) + _filter(_noise(len(t), rng), hi=400) * np.exp(-t * 25) * 0.5

    def _engine(self, rng, hz, tracks=True):
        dur = 2.0
        t = _t(dur)
        x = np.zeros(len(t), np.float32)
        for k, a in ((1, 1.0), (2, 0.6), (3, 0.35), (5, 0.2)):
            x += np.sin(2 * np.pi * hz * k * t + 0.5 * np.sin(2 * np.pi * 3 * t)) * a
        x = x * (0.7 + 0.3 * np.sin(2 * np.pi * 6 * t)) * 0.4
        x += _filter(_noise(len(t), rng), hi=300) * 0.6
        if tracks:
            for i in range(int(dur * 9)):
                p = int(SR * (i / 9 + rng.uniform(0, 0.02)))
                k = int(SR * 0.015)
                if p + k < len(x):
                    x[p:p + k] += _filter(_noise(k, rng), lo=700, hi=4000) * 0.35
        fade = np.minimum(1, np.minimum(t * 4, (dur - t) * 4))
        return x * fade

    def _aircraft(self, rng):
        dur = 4.0
        t = _t(dur)
        f = 110 * (1.08 - 0.16 * t / dur)                       # doppler drop
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = sum(np.sin(ph * k) / k for k in range(1, 8))
        env = np.exp(-((t - dur * 0.45) ** 2) / (2 * (dur * 0.22) ** 2))
        x = x * env + _filter(_noise(len(t), rng), hi=900) * env * 0.4
        return x

    def _flamer(self, rng):
        dur = 1.2
        t = _t(dur)
        x = _filter(_noise(len(t), rng), hi=1200) * np.minimum(1, t * 10) * np.minimum(1, (dur - t) * 5)
        for _ in range(30):
            p = int(rng.uniform(0, dur - 0.02) * SR)
            k = int(SR * 0.004)
            x[p:p + k] += _noise(k, rng) * 0.6
        return x

    def _glass(self, rng):
        dur = 0.6
        x = np.zeros(int(SR * dur), np.float32)
        for _ in range(14):
            p = int(rng.uniform(0, dur * 0.7) * SR)
            t = _t(0.08)
            f = rng.uniform(3000, 7000)
            seg = np.sin(2 * np.pi * f * t) * np.exp(-t * 60)
            x[p:p + len(seg)] += seg[: max(0, len(x) - p)] * rng.uniform(0.3, 1)
        return x

    def _officer_whistle(self):
        t = _t(0.7)
        f = 3000 + 180 * np.sign(np.sin(2 * np.pi * 22 * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        return np.sin(ph) * np.minimum(1, np.minimum(t * 30, (0.7 - t) * 10))

    def _radio(self, rng):
        t = _t(0.6)
        x = _filter(_noise(len(t), rng), lo=400, hi=2800) * 0.5 * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 9 * t)))
        x[: int(SR * 0.08)] += np.sin(2 * np.pi * 1000 * t[: int(SR * 0.08)]) * 0.6
        return x

    def _step(self, rng):
        n = int(SR * 0.08)
        return _filter(_noise(n, rng), hi=500) * _env(n, 0.002, 0.02)

    def _splash(self, rng):
        n = int(SR * 0.5)
        x = _filter(_noise(n, rng), lo=300, hi=3000) * _env(n, 0.003, 0.12)
        return x

    def _pop(self, rng):
        n = int(SR * 0.2)
        return _filter(_noise(n, rng), hi=1500) * _env(n, 0.001, 0.03)

    def _hiss(self, rng):
        n = int(SR * 1.5)
        return _filter(_noise(n, rng), lo=2000) * _env(n, 0.05, 0.8) * 0.5

    def _ui_click(self):
        t = _t(0.04)
        return np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 120)

    def _rustle(self, rng):
        n = int(SR * 0.25)
        return _filter(_noise(n, rng), lo=1500, hi=6000) * _env(n, 0.03, 0.08) * 0.5

    def _battle_loop(self, rng):
        dur = 8.0
        n = int(SR * dur)
        brown = np.cumsum(_noise(n, rng))
        brown -= np.linspace(0, brown[-1], n)
        x = _filter(brown / (np.max(np.abs(brown)) + 1e-6), hi=120) * 0.5
        for _ in range(7):
            b = _filter(self._explosion(rng, rng.uniform(0.8, 2.0)), hi=250) * rng.uniform(0.2, 0.5)
            p = int(rng.uniform(0, dur - 2.5) * SR)
            x[p:p + len(b)] += b[: n - p]
        for _ in range(5):
            b = _filter(self.s["rifle"][0], hi=500) * rng.uniform(0.05, 0.12)
            for k in range(rng.integers(3, 10)):
                p = int((rng.uniform(0, dur - 1) + k * 0.1) * SR)
                x[p:p + len(b)] += b[: n - p]
        return _norm(x, 0.5)

    def _wind_loop(self, rng):
        dur = 6.0
        t = _t(dur)
        x = _filter(_noise(len(t), rng), lo=150, hi=900) * (0.6 + 0.4 * np.sin(2 * np.pi * t / dur * 2))
        return _norm(x, 0.4)

    def _rain_loop(self, rng):
        dur = 4.0
        n = int(SR * dur)
        x = _filter(_noise(n, rng), lo=1500, hi=9000) * 0.3
        for _ in range(400):
            p = rng.integers(0, n - 200)
            x[p:p + 200] += _filter(_noise(200, rng), lo=2000) * np.exp(-np.arange(200) / 30) * 0.3
        return _norm(x, 0.35)

    def _tinnitus(self):
        t = _t(2.0)
        return (np.sin(2 * np.pi * 4600 * t) * 0.5).astype(np.float32)


# ====================================================================== the player

GUN_SOUND = {"pistol": "pistol", "smg": "smg", "assault": "smg", "rifle": "rifle", "carbine": "rifle",
             "sniper": "rifle", "lmg": "mg", "hmg": "mg", "at_rifle": "atrifle", "shotgun": "shotgun"}
ROF = {"mg42": 20, "mg42_tripod": 20, "mg34": 14, "mg34_tripod": 14, "bar": 9, "bren": 8, "m1919": 8,
       "vickers": 8, "maxim1910": 10, "maxim_m32": 10, "dp28": 10, "type92": 7, "type96": 9, "type99_lmg": 13,
       "type11": 8, "breda30": 7, "breda37": 7, "fm2429": 8, "wz28": 9, "ckm_wz30": 9, "zb26": 9,
       "lahti_saloranta": 8, "solothurn31m": 11, "schwarzlose": 7, "type24_maxim": 10, "ppsh": 15,
       "ppd40": 14, "pps43": 11, "mp40": 9, "mp38": 9, "sten": 9, "thompson_m1a1": 12, "thompson_1928": 13,
       "m3_grease": 7, "owen": 11, "suomi": 14, "mab38": 10, "kiraly": 12, "orita": 10, "type100": 8,
       "mas38": 10, "stg44": 9, "fg42": 12, "c96": 14, "m2hb": 9, "besa": 10, "dt": 10, "dshk": 10,
       "breda38": 8, "type91": 8, "type97_tmg": 9, "reibel": 12, "ckm_wz30_t": 9, "schwarzlose_t": 7,
       "zb53_t": 9, "besa_hvy": 7}


class Audio:
    VOICES = 26

    def __init__(self, settings):
        import tcod.sdl.audio as A
        self.settings = settings
        self.enabled = bool(settings.get("sound", True))
        self.device = A.get_default_playback().open(format=np.float32, channels=2, frequency=SR)
        self.voices = [self.device.new_stream(format=np.float32, channels=2, frequency=SR) for _ in range(self.VOICES)]
        self.loop_streams = {k: self.device.new_stream(format=np.float32, channels=2, frequency=SR)
                             for k in ("battle", "wind", "rain", "tinnitus")}
        self.bank = Bank()
        self.recent = []            # timestamps of recent gunfire (intensity)
        self.last_engine = 0.0
        self.last_update = time.time()
        self.scheduled = []         # (play_at, stereo array) not yet queued
        self.voice_bank = None
        self.voice_wait = []        # voice lines still being rendered: (give_up_at, event)
        self.voice_until = []       # when the voices now playing finish
        self._warmed = set()
        self.apply_volume()

    # ---------------------------------------------------------------- control
    def apply_volume(self):
        v = float(self.settings.get("volume", 0.8)) if self.enabled else 0.0
        for s in self.voices:
            s.gain = v
        for s in self.loop_streams.values():
            s.gain = v

    def set_enabled(self, on):
        self.enabled = on
        if not on:
            for s in self.voices + list(self.loop_streams.values()):
                try:
                    s.flush()
                    s.clear() if hasattr(s, "clear") else None
                except Exception:
                    pass
            self.scheduled = []
        self.apply_volume()

    def busy(self):
        return bool(self.scheduled)

    def voices_on(self):
        return self.enabled and bool(self.settings.get("voices", True))

    def _bank(self):
        if self.voice_bank is None:
            from .voice import VoiceBank
            self.voice_bank = VoiceBank()
        return self.voice_bank

    def close(self):
        try:
            for s in self.voices + list(self.loop_streams.values()):
                s.close()
            self.device.close()
        except Exception:
            pass

    # ---------------------------------------------------------------- playback
    def _free_voice(self):
        best = None
        for s in self.voices:
            q = s.queued_samples
            if q == 0:
                return s
            if best is None or q < best[0]:
                best = (q, s)
        return None

    WEAPONS = {"gunfire", "cannon", "explosion", "mortar", "rocket", "shell", "whizz", "ricochet", "penetration",
               "flamer", "thud", "splash", "aircraft"}

    def mix(self, cat):
        """A channel of the mixer (see the Options screen)."""
        from .settings import DEFAULTS
        key = f"vol_{cat}"
        try:
            return max(0.0, min(1.5, float(self.settings.get(key, DEFAULTS.get(key, 1.0)))))
        except (TypeError, ValueError):
            return 1.0

    def play(self, mono, gain_l, gain_r, delay=0.0, cat="effects"):
        if not self.enabled or mono is None:
            return
        m = self.mix(cat)
        if m <= 0.001:
            return
        gain_l *= m
        gain_r *= m
        at = time.time() + delay
        stereo = np.empty((len(mono), 2), np.float32)
        stereo[:, 0] = mono * gain_l
        stereo[:, 1] = mono * gain_r
        self.scheduled.append((at, stereo))

    def _pump(self):
        now = time.time()
        keep = []
        for at, st in sorted(self.scheduled, key=lambda e: e[0]):
            if at <= now + 0.01:
                v = self._free_voice()
                if v is None:
                    continue       # drop: too much going on
                v.queue_audio(st)
            else:
                keep.append((at, st))
        self.scheduled = keep

    def ui(self, name="ui"):
        s = self.bank.get(name)
        if s is not None:
            self.play(s, 0.35, 0.35, cat="ui")

    # ---------------------------------------------------------------- game integration
    def update(self, game):
        if not self.enabled:
            return
        self._pump()
        if game is None:
            self._loops(None, 0.0)
            return
        events = getattr(game, "audio_events", None)
        p = game.player
        if events and p is not None:
            game.audio_events = []
            voices = [e for e in events if e[0] == "voice"]
            others = [e for e in events if e[0] != "voice"]
            if others:
                self._events(game, p, others)
            if voices and self.voices_on():
                self._voice_events(game, p, voices)
        if p is not None and self.voices_on():
            self._warm(game)
            self._retry_voices(game, p)
        self._pump()
        self._loops(game, self._intensity())

    def _intensity(self):
        now = time.time()
        self.recent = [t for t in self.recent if now - t < 20]
        return min(1.0, len(self.recent) / 40.0)

    def _events(self, game, p, events):
        lx, ly = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        deaf = p.body.deaf > 0 or not p.body.conscious
        inside = p.vehicle is not None
        vol_scale = 0.18 if deaf else (0.6 if inside else 1.0)
        turns = [e[6] for e in events]
        t0 = min(turns)
        span = max(turns) - t0
        spacing = min(0.14, 0.9 / (span + 1))
        cands = []
        for kind, weapon, x, y, loud, power, turn, extra in events:
            d = math.hypot(x - lx, y - ly)
            level = loud - 20 * math.log10(max(1.0, d))
            amp = 10 ** ((level - 70) / 20.0) * vol_scale
            if amp < 0.012:
                continue
            far = d > 28 or deaf or inside
            pan = max(-1.0, min(1.0, (x - lx) / max(6.0, d)))
            gl = math.cos((pan + 1) * math.pi / 4)
            gr = math.sin((pan + 1) * math.pi / 4)
            delay = (turn - t0) * spacing + random.uniform(0, 0.05) + min(0.3, d / 340.0 * 2)
            cands.append((amp, kind, weapon, power, far, gl, gr, delay, d, extra))
        cands.sort(key=lambda c: -c[0])
        engine_played = False
        for amp, kind, weapon, power, far, gl, gr, delay, d, extra in cands[:20]:
            amp = min(1.1, amp)
            snd = self._pick(kind, weapon, power, far, extra)
            if snd is None:
                continue
            if kind in ("engine",):
                if engine_played or time.time() - self.last_engine < 1.6:
                    continue
                engine_played = True
                self.last_engine = time.time()
            if kind in ("gunfire", "explosion", "cannon"):
                self.recent.append(time.time())
            self.play(snd, gl * amp, gr * amp, delay, cat="weapons" if kind in self.WEAPONS else "effects")

    # ---------------------------------------------------------------- voices
    def _warm(self, game):
        """Render the armies' stock lines in the background, before anyone needs them."""
        key = (id(game), getattr(game.sector, "name", ""))
        if key in self._warmed:
            return
        self._warmed.add(key)
        bank = self._bank()
        from .data import ranks as R
        from .data.nations import NATIONS
        from .data.phrases import all_lines
        nations = {game.player_nation} | {a.nation for a in game.actors[:200]}
        order = ("contact", "attack", "grenade", "medic", "pain", "reload", "mg", "tank", "sniper", "retreat",
                 "surrender")
        for nat in sorted(nations, key=lambda n: n != game.player_nation):
            sh = NATIONS[nat]["shouts"]
            lines = [x for k in order for x in sh.get(k, [])]
            lines += [x.replace("{rank}", "") for x in R.ACK.get(nat, [])] + all_lines(nat)
            pain = set(sh.get("pain", []))
            for spk in bank.voice_set(nat):
                for ln in lines:
                    bank.request(spk, ln, "scream" if ln in pain else "shout", warm=True)

    def _voice_events(self, game, p, events):
        # a long wait can produce dozens: only the last few lines matter
        for ev in events[-6:]:
            self.voice_wait.append((time.time() + (2.5 if ev[7].get("style") == "radio" else 1.2), ev))
        self._retry_voices(game, p)

    def _retry_voices(self, game, p):
        if not self.voice_wait:
            return
        now = time.time()
        bank = self._bank()
        keep = []
        lx, ly = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        deaf = p.body.deaf > 0 or not p.body.conscious
        self.voice_until = [t for t in self.voice_until if t > now]
        for give_up, ev in self.voice_wait:
            kind, weapon, x, y, loud, power, turn, info = ev
            own = info.get("own")
            style = info.get("style", "shout")
            d = 0.0 if (own or style == "radio") else math.hypot(x - lx, y - ly)
            level = loud - 20 * math.log10(max(1.0, d))
            amp = 10 ** ((level - 70) / 20.0) * (0.25 if deaf else 1.0)
            if own:
                amp = 0.45 * (0.3 if deaf else 1.0)
            elif style == "radio":
                amp = 0.4 * (0.35 if deaf else 1.0)
            if amp < 0.015:
                continue                  # too far to hear a word
            spk = bank.speaker(info["nation"], info["sid"], info.get("female", False), info.get("role", ""))
            clip = bank.request(spk, info["text"], style)
            if clip is None:
                if now < give_up:
                    keep.append((give_up, ev))
                continue
            if len(self.voice_until) >= 3 and not own:
                continue                  # everyone shouting at once: you catch the nearest
            if d > 22 or deaf or p.vehicle is not None:
                clip = _filter(clip, hi=1100 if not deaf else 500)
            if own or style == "radio":
                gl = gr = 0.707
            else:
                pan = max(-1.0, min(1.0, (x - lx) / max(6.0, d)))
                gl = math.cos((pan + 1) * math.pi / 4)
                gr = math.sin((pan + 1) * math.pi / 4)
            amp = min(0.9, amp * 1.6)
            self.play(clip, gl * amp, gr * amp, min(0.25, d / 340.0 * 2), cat="voices")
            self.voice_until.append(now + len(clip) / SR)
        self.voice_wait = keep

    def _pick(self, kind, weapon, power, far, extra):
        b = self.bank
        suffix = "_far" if far else ""
        if kind == "gunfire":
            from .data.items import ITEMS
            t = ITEMS.get(weapon) if weapon else None
            cat = GUN_SOUND.get(t.cat, "rifle") if t is not None else "rifle"
            if cat in ("mg", "smg"):
                n = int(extra or (t.burst if t is not None else 5))
                if n > 1:
                    rps = ROF.get(weapon, 10 if cat == "mg" else 10)
                    return b.burst_far(cat, rps, n) if far else b.burst(cat, rps, n)
                cat = "rifle" if cat == "mg" else "pistol"
            snd = b.get(cat + suffix)
            return snd if snd is not None else b.get(cat)
        if kind in ("explosion", "crash"):
            if kind == "crash":
                return b.get("expl_small" + suffix)
            if power >= 400:
                return b.get("expl_big" + suffix)
            if power >= 130:
                return b.get("expl_med" + suffix)
            return b.get("expl_small" + suffix)
        if kind == "cannon":
            return b.get("cannon" + suffix)
        simple = {"mortar": "mortar" + suffix, "rocket": "rocket" + suffix, "flamer": "flamer" + suffix,
                  "ping": "ping", "click": "click", "reload": "reload", "glass": "glass",
                  "ricochet": "ricochet", "penetration": "clang", "whistle": "whistle_officer",
                  "footsteps": "step", "engine": ("engine" if extra != "wheels" else "truck") + suffix,
                  "flare": "pop", "smoke": "hiss", "whizz": "whizz", "shell": "whistle", "siren": "siren",
                  "aircraft": "aircraft" + suffix, "thud": "thud", "splash": "splash", "radio": "radio",
                  "ramp": "clang", "wire": "click", "door": "click"}
        name = simple.get(kind)
        return b.get(name) if name else None

    def _loops(self, game, intensity):
        amb = self.settings.get("ambience", True) and game is not None
        want = {"battle": 0.0, "wind": 0.0, "rain": 0.0, "tinnitus": 0.0}
        if amb:
            # the distant war: a murmur when it's quiet, a roar when it isn't - and louder with a battle next door
            near = 0.0
            st = getattr(game, "strategic", None)
            if st is not None and getattr(st, "attacks", None) and getattr(game, "sector", None) is not None:
                try:
                    near = 0.15 * len(st.attacks_near(game.sector))
                except Exception:
                    near = 0.0
            want["battle"] = 0.05 + 0.3 * intensity + min(0.2, near)
            if game.weather in ("rain", "snow"):
                want["rain"] = 0.3 if game.weather == "rain" else 0.08
            want["wind"] = 0.08 + (0.15 if game.weather in ("snow", "sandstorm") else 0.0)
            amb_mix = self.mix("ambience")
            for k in ("battle", "wind", "rain"):
                want[k] *= amb_mix
            p = game.player
            if p is not None and p.body.deaf > 0:
                want["tinnitus"] = min(0.5, p.body.deaf / 60.0) * self.mix("effects")
                want["battle"] *= 0.3
                want["wind"] *= 0.3
                want["rain"] *= 0.3
        # the loops go out a quarter of a second at a time, so a change (the mixer, the weather, a blast
        # that leaves your ears ringing) is heard at once rather than when the whole loop has played
        pos = self.__dict__.setdefault("loop_pos", {})
        chunk = SR // 4
        for k, stream in self.loop_streams.items():
            g = want[k]
            if g <= 0.001:
                continue
            while stream.queued_samples < chunk:
                loop = self.bank.loops[k]
                i = pos.get(k, 0) % len(loop)
                piece = loop[i:i + chunk]
                if len(piece) < chunk:
                    piece = np.concatenate([piece, loop[:chunk - len(piece)]])
                pos[k] = (i + chunk) % len(loop)
                st = np.empty((len(piece), 2), np.float32)
                st[:, 0] = piece * g
                st[:, 1] = piece * g * (0.9 if k == "wind" else 1.0)
                stream.queue_audio(st)
