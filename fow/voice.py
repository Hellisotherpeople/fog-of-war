"""Soldiers' voices.

Speech bubbles and radio traffic are spoken aloud, in each army's own language,
by the platform's speech synthesiser (macOS `say`, or espeak-ng / espeak on
Linux).  Lines are rendered on a background thread, cached on disk, then treated
like every other battlefield sound: strained and echoing when shouted, placed in
stereo, muffled by distance and deafness, or squeezed through a radio set with
static and a squelch.  With no synthesiser, soldiers still shout - in
formant-synthesised gibberish that has the rhythm of the line.

Romanised Russian, Japanese and Chinese are turned back into native script so the
synthesiser pronounces them properly.
"""
from __future__ import annotations

import hashlib
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import unicodedata
import wave

import numpy as np

SR = 44100
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".fogofwar", "voices")

LOCALE = {"usa": "en_US", "uk": "en_GB", "canada": "en_US", "australia": "en_AU", "newzealand": "en_GB",
          "india": "en_IN", "ussr": "ru_RU", "france": "fr_FR", "poland": "pl_PL", "china": "zh_CN",
          "germany": "de_DE", "italy": "it_IT", "japan": "ja_JP", "finland": "fi_FI", "hungary": "hu_HU",
          "romania": "ro_RO"}
FEMALE_VOICES = {"Samantha", "Kathy", "Karen", "Moira", "Tessa", "Veena", "Tara", "Anna", "Milena", "Kyoko",
                 "Alice", "Amélie", "Amelie", "Zosia", "Satu", "Tünde", "Ioana", "Tingting", "Meijia", "Sinji",
                 "Flo", "Sandy", "Shelley", "Grandma", "Paulina", "Monica", "Marie", "Sara", "Nora", "Ellen",
                 "Yuna", "Zuzana", "Mariska", "Laura", "Carmit", "Damayanti", "Lekha", "Joana", "Luciana",
                 "Melina", "Lesya", "Linh", "Kanya", "Yelda", "Mónica", "Paola", "Federica", "Emma", "Serena",
                 "Kate", "Fiona", "Victoria", "Allison", "Ava", "Susan", "Zoe"}
NOVELTY = {"Albert", "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Wobble", "Good News", "Jester",
           "Organ", "Superstar", "Trinoids", "Whisper", "Zarvox", "Junior", "Deranged", "Hysterical", "Pipe Organ",
           "Princess"}
# a man's voice from a female-only language: drop the pitch into a baritone
MALE_PBAS = 22


# ====================================================================== native script

_RU = [("shch", "щ"), ("zh", "ж"), ("kh", "х"), ("tch", "ч"), ("ch", "ч"), ("sh", "ш"), ("tz", "ц"), ("ts", "ц"),
       ("yo", "ё"), ("yu", "ю"), ("ya", "я"), ("ye", "е"), ("a", "а"), ("b", "б"),
       ("v", "в"), ("w", "в"), ("g", "г"), ("d", "д"), ("e", "е"), ("z", "з"), ("i", "и"), ("j", "й"), ("k", "к"),
       ("l", "л"), ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("r", "р"), ("s", "с"), ("t", "т"), ("u", "у"),
       ("f", "ф"), ("h", "х"), ("c", "к"), ("q", "к"), ("x", "кс"), ("'", "ь")]
_RU_VOWELS = set("aeiouy")


def ru_cyrillic(text: str) -> str:
    """Latin-transliterated Russian back to Cyrillic ('Za Rodinu!' -> 'За Родину!')."""
    out = []
    i = 0
    low = text.lower()
    while i < len(text):
        ch = low[i]
        if ch == "y":
            nxt = low[i + 1] if i + 1 < len(low) else ""
            prev = low[i - 1] if i > 0 else ""
            if nxt in ("o", "u", "a", "e"):
                pass                    # handled as yo/yu/ya/ye below
            elif prev in _RU_VOWELS:
                out.append(_case("й", text[i]))
                i += 1
                continue
            elif prev.isalpha():
                out.append(_case("ы", text[i]))
                i += 1
                continue
            else:
                out.append(_case("й", text[i]))
                i += 1
                continue
        for lat, cyr in _RU:
            if low.startswith(lat, i):
                out.append(_case(cyr, text[i]))
                i += len(lat)
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _case(cyr, orig):
    return cyr[0].upper() + cyr[1:] if orig.isupper() else cyr


_KANA = {
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ", "sha": "しゃ", "shu": "しゅ", "sho": "しょ", "cha": "ちゃ",
    "chu": "ちゅ", "cho": "ちょ", "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ", "hya": "ひゃ", "hyu": "ひゅ",
    "hyo": "ひょ", "mya": "みゃ", "myu": "みゅ", "myo": "みょ", "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ", "ja": "じゃ", "ju": "じゅ", "jo": "じょ", "bya": "びゃ",
    "byu": "びゅ", "byo": "びょ", "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ", "shi": "し", "chi": "ち",
    "tsu": "つ", "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ", "sa": "さ", "su": "す", "se": "せ",
    "so": "そ", "ta": "た", "te": "て", "to": "と", "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "fu": "ふ", "he": "へ", "ho": "ほ", "ma": "ま", "mi": "み", "mu": "む", "me": "め",
    "mo": "も", "ya": "や", "yu": "ゆ", "yo": "よ", "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wo": "を", "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご", "za": "ざ", "ji": "じ",
    "zu": "ず", "ze": "ぜ", "zo": "ぞ", "da": "だ", "de": "で", "do": "ど", "ba": "ば", "bi": "び", "bu": "ぶ",
    "be": "べ", "bo": "ぼ", "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ", "a": "あ", "i": "い",
    "u": "う", "e": "え", "o": "お",
}
_LONG = {"ā": "aa", "ī": "ii", "ū": "uu", "ē": "ei", "ō": "ou", "â": "aa", "ô": "ou", "û": "uu"}


def ja_kana(text: str) -> str:
    """Hepburn romaji to hiragana ('Tennōheika banzai!' -> 'てんのうへいか ばんざい!')."""
    s = "".join(_LONG.get(c, c) for c in text.lower()).replace("-", "")
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if not c.isalpha():
            out.append({"'": "", "!": "！", "?": "？", ",": "、", ".": "。"}.get(c, c))
            i += 1
            continue
        # doubled consonant: small tsu
        if i + 1 < len(s) and c == s[i + 1] and c not in "aeioun":
            out.append("っ")
            i += 1
            continue
        if c == "n" and (i + 1 >= len(s) or s[i + 1] not in "aeiouy"):
            out.append("ん")
            i += 1
            continue
        for L in (3, 2, 1):
            chunk = s[i:i + L]
            if chunk in _KANA:
                out.append(_KANA[chunk])
                i += L
                break
        else:
            i += 1                       # a stray letter (an exclamation's trailing 'h'): unspoken
    return "".join(out)


ZH = {"Chōng a!": "冲啊！", "Shā!": "杀！", "Shǒuliúdàn!": "手榴弹！", "Wèishēngbīng!": "卫生兵！",
      "Jiù mìng!": "救命！", "Huàn dànjiā!": "换弹夹！", "Rìběn guǐzi!": "日本鬼子！", "Chèntuì!": "撤退！",
      "Bié kāi qiāng!": "别开枪！", "Tǎnkè!": "坦克！", "Jūjī shǒu!": "狙击手！", "Jīqiāng!": "机枪！",
      "Āiyō!": "哎哟！", "Aaa!": "啊！", "Shì!": "是！", "Míngbai!": "明白！", "Zūnmìng!": "遵命！",
      "Tīng wǒ zhǐhuī!": "听我指挥！", "Gēn wǒ lái!": "跟我来！", "Kāi huǒ!": "开火！", "Dǎ!": "打！",
      "Bèi fāxiàn le, kāi huǒ!": "被发现了，开火！", "Cóng cèyì bāochāo!": "从侧翼包抄！", "Rào guòqù!": "绕过去！",
      "Dōu bǔjǐ hǎo le ma? Zǒu!": "都补给好了吗？走！", "Tǐng zhù!": "挺住！", "Méi shì de.": "没事的。",
      "Wǒ lái le!": "我来了！", "Pàobīng zhīyuán!": "炮兵支援！", "Dànyào!": "弹药！", "Shì! Mǎshàng qù!": "是！马上去！",
      "Xiànzài nǐ zuì zīshēn. Zhège bān guī nǐ le.": "现在你最资深。这个班归你了。",
      "Páizhǎng xīshēng le!": "排长牺牲了！", "Liánzhǎng xīshēng le!": "连长牺牲了！", "Shǒu zhù! Duǒ hǎo!": "守住！躲好！",
      "Wā zhànhào!": "挖战壕！", "Qiánjìn! Kuài!": "前进！快！", "Zhǐ néng huánjī!": "只能还击！",
      "Zìyóu kāi huǒ!": "自由开火！", "Pā xià! Méi mìnglìng bù xǔ kāi qiāng!": "趴下！没命令不许开枪！",
      "Huǒlì yāzhì!": "火力压制！", "Jíhé!": "集合！", "Shàng chē!": "上车！", "Xià chē!": "下车！",
      "Qù lǐng dànyào!": "去领弹药！", "Huìbào!": "汇报！", "Forward!": "前进！", "Enemy!": "敌人！"}


def _zh_extra():
    from .data.phrases import ZH_EXTRA
    from .data.banter import ZH_BANTER
    ZH.update(ZH_EXTRA)
    ZH.update(ZH_BANTER)


def native(text: str, locale: str) -> str | None:
    """The line as the synthesiser should read it, or None if it can't be said in this language."""
    lg = locale[:2]
    if lg == "ru":
        return ru_cyrillic(text)
    if lg == "ja":
        return ja_kana(text)
    if lg == "zh":
        if "给他包扎！" not in ZH.values():
            _zh_extra()
        return ZH.get(text.strip())
    return text


# ====================================================================== synthesisers

class Synth:
    name = "none"

    def voices(self, locale):
        return [], []

    def render(self, voice, text, rate, pbas, path) -> bool:
        return False


class MacSay(Synth):
    name = "say"

    def __init__(self):
        self.table = {}
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
        except Exception:
            out = ""
        for line in out.splitlines():
            m = re.match(r"^(.+?)\s+([a-z]{2,3}_[A-Z0-9]{2,3})\s+#", line)
            if not m:
                continue
            name, loc = m.group(1).strip(), m.group(2)
            base = name.split(" (")[0]
            if base in NOVELTY:
                continue
            self.table.setdefault(loc, []).append(name)

    def voices(self, locale):
        cands = self.table.get(locale) or []
        if not cands:
            lg = locale[:2]
            for loc, names in self.table.items():
                if loc.startswith(lg):
                    cands = cands + names
        male = [n for n in cands if n.split(" (")[0] not in FEMALE_VOICES]
        female = [n for n in cands if n.split(" (")[0] in FEMALE_VOICES]
        # the plainer voices first; the Eloquence family reads like a person at a distance
        order = {"Reed": 0, "Daniel": 0, "Thomas": 0, "Rishi": 0, "Eddy": 1, "Fred": 1, "Jacques": 1,
                 "Aman": 1, "Ralph": 2, "Rocko": 2, "Grandpa": 5}
        male.sort(key=lambda n: order.get(n.split(" (")[0], 3))
        return male, female

    def render(self, voice, text, rate, pbas, path) -> bool:
        body = (f"[[pbas {pbas}]] " if pbas else "") + text
        try:
            r = subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", path, "--file-format=WAVE",
                                "--data-format=LEI16@22050", body], capture_output=True, timeout=20)
            return r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 1000
        except Exception:
            return False


class Espeak(Synth):
    name = "espeak"

    def __init__(self, exe):
        self.exe = exe

    def voices(self, locale):
        lg = locale[:2]
        return [f"{lg}+m3", f"{lg}+m1"], [f"{lg}+f2"]

    def render(self, voice, text, rate, pbas, path) -> bool:
        pitch = 35 if pbas else 50
        try:
            r = subprocess.run([self.exe, "-v", voice, "-s", str(int(rate * 0.8)), "-p", str(pitch), "-w", path, text],
                               capture_output=True, timeout=20)
            return r.returncode == 0 and os.path.exists(path)
        except Exception:
            return False


def find_synth() -> Synth:
    if shutil.which("say"):
        s = MacSay()
        if s.table:
            return s
    for exe in ("espeak-ng", "espeak"):
        p = shutil.which(exe)
        if p:
            return Espeak(p)
    return Synth()


# ====================================================================== sound processing

def _load_wav(path):
    with wave.open(path) as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        sw = w.getsampwidth()
        ch = w.getnchannels()
    if sw == 2:
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    elif sw == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128.0
    else:
        x = np.frombuffer(raw, np.int32).astype(np.float32) / 2 ** 31
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def _resample(x, sr_in, sr_out, pitch=1.0):
    """Resample (and shift pitch by playing faster or slower)."""
    if len(x) == 0:
        return x
    ratio = sr_in * pitch / sr_out
    n = int(len(x) / ratio)
    idx = np.arange(n, dtype=np.float64) * ratio
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def _trim(x, thresh=0.01):
    nz = np.where(np.abs(x) > thresh)[0]
    if len(nz) == 0:
        return x[:0]
    return x[max(0, nz[0] - 200): nz[-1] + 800]


def _band(x, lo=None, hi=None):
    from .audio import _filter
    return _filter(x, lo, hi)


def process(x, style, rng):
    """Shape a clean synthesised line into a shout, a mutter, a scream or a radio voice."""
    if len(x) == 0:
        return x
    x = x / max(1e-4, float(np.max(np.abs(x))))
    if style == "radio":
        x = _band(x, 380, 2600)
        x = np.tanh(x * 5.0) * 0.6
        hiss = rng.standard_normal(len(x)).astype(np.float32) * 0.05
        x = x + _band(hiss, 800, 5000)
        # key-up squelch and the carrier dropping at the end
        sq_n = int(SR * 0.09)
        sq = _band(rng.standard_normal(sq_n).astype(np.float32), 1000, 6000) * 0.35 * np.linspace(1, 0, sq_n)
        tail_n = int(SR * 0.16)
        tail = _band(rng.standard_normal(tail_n).astype(np.float32), 700, 5000) * 0.3 * np.linspace(1, 0, tail_n) ** 2
        click = np.zeros(int(SR * 0.004), np.float32)
        click[0] = 0.8
        x = np.concatenate([click, sq * 0.6, x, tail]).astype(np.float32)
        return x * 0.8
    if style in ("shout", "scream"):
        x = _band(x, 170, 6000)
        drive = 2.2 if style == "shout" else 3.5
        x = np.tanh(x * drive) / np.tanh(drive)
        # the flat slap of a shout off walls and ground
        d = int(SR * 0.055)
        out = np.zeros(len(x) + d * 3, np.float32)
        out[:len(x)] += x
        out[d:d + len(x)] += _band(x, 200, 2500) * 0.22
        out[d * 3:d * 3 + len(x)] += _band(x, 200, 1600) * 0.09
        return out * 0.85
    # talking: a little room, nothing more
    return _band(x, 120, 7000) * 0.7


def babble(text, rng, pitch=1.0, female=False):
    """No synthesiser: formant-synthesised shouting with the rhythm of the line."""
    vowels = [c for c in unicodedata.normalize("NFKD", text.lower()) if c in "aeiouy"]
    n = max(1, min(14, len(vowels)))
    f0 = (185.0 if female else 118.0) * pitch
    formants = {"a": (800, 1250), "e": (500, 1900), "i": (320, 2300), "o": (520, 950), "u": (350, 800),
                "y": (330, 2000)}
    out = []
    for k in range(n):
        v = vowels[k] if k < len(vowels) else "a"
        dur = rng.uniform(0.09, 0.16) * (1.8 if k == n - 1 else 1.0)
        m = int(SR * dur)
        t = np.arange(m) / SR
        f = f0 * (1.15 - 0.25 * k / n) * (1 + 0.02 * np.sin(2 * np.pi * 5 * t))
        ph = np.cumsum(2 * np.pi * f / SR)
        glott = (np.mod(ph, 2 * np.pi) / np.pi - 1.0).astype(np.float32)
        f1, f2 = formants[v]
        s = _band(glott, f1 * 0.6, f1 * 1.5) + 0.5 * _band(glott, f2 * 0.7, f2 * 1.3)
        env = np.minimum(1, t / 0.015) * np.minimum(1, (dur - t) / 0.03)
        cons = _band(rng.standard_normal(int(SR * 0.025)).astype(np.float32), 2500, 7000) * 0.3
        out += [cons, (s * env).astype(np.float32)]
    return np.concatenate(out).astype(np.float32)


# ====================================================================== the voice bank

class Speaker:
    __slots__ = ("voice", "pbas", "pitch", "female", "locale")

    def __init__(self, voice, pbas, pitch, female, locale):
        self.voice = voice
        self.pbas = pbas
        self.pitch = pitch
        self.female = female
        self.locale = locale


class VoiceBank:
    """Renders lines in the background; hands back processed clips once they're ready."""

    MAX_CLIPS = 260
    MAX_READY = 600
    WORKERS = 3

    def __init__(self):
        self.synth = find_synth()
        self.jobs: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = 0
        self.ready: dict = {}          # render key -> mono float32 at SR (clean, unprocessed)
        self.failed: set = set()
        self.queued: set = set()
        self.clips: dict = {}          # (render key, pitch, style) -> processed clip
        self.lock = threading.Lock()
        self.rng = np.random.default_rng(11)
        self._pools = {}
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.threads = [threading.Thread(target=self._work, daemon=True) for _ in range(self.WORKERS)]
        for t in self.threads:
            t.start()

    @property
    def available(self):
        return self.synth.name != "none"

    # ---------------------------------------------------------------- speakers
    def speaker(self, nation, sid, female=False, role=""):
        loc = LOCALE.get(nation, "en_US")
        pool = self._pools.get(loc)
        if pool is None:
            male, fem = self.synth.voices(loc)
            pool = self._pools[loc] = (male, fem)
        male, fem = pool
        h = int(hashlib.md5(str(sid).encode()).hexdigest()[:8], 16)
        pitch = 0.93 + (h % 1000) / 1000 * 0.15
        if female:
            if fem:
                return Speaker(fem[h % min(2, len(fem))], 0, pitch, True, loc)
            if male:
                return Speaker(male[0], 70, pitch, True, loc)
        else:
            if role == "volkssturm":
                old = [v for v in male if v.startswith("Grandpa")]
                if old:
                    return Speaker(old[0], 0, pitch * 0.97, False, loc)
            usable = [v for v in male if not v.startswith("Grandpa")] or male
            if usable:
                return Speaker(usable[h % min(2, len(usable))], 0, pitch, False, loc)
            if fem:
                return Speaker(fem[0], MALE_PBAS + h % 6, pitch, False, loc)
        return Speaker(None, 0, pitch, female, loc)

    def voice_set(self, nation):
        """One speaker for each distinct voice this army's men can have (for warming the cache)."""
        loc = LOCALE.get(nation, "en_US")
        seen = {}
        for sid in range(40):
            for fem in (False,):
                s = self.speaker(nation, sid, fem)
                seen.setdefault((s.voice, s.pbas), s)
        return list(seen.values())

    # ---------------------------------------------------------------- rendering
    def _key(self, spk, text, rate):
        return hashlib.sha1(f"{self.synth.name}|{spk.voice}|{spk.pbas}|{rate}|{text}".encode()).hexdigest()[:20]

    def request(self, spk, line, style="shout", warm=False):
        """Ask for a line.  Returns a processed clip if it's ready, else queues it and returns None."""
        if spk.voice is None:
            key = ("babble", line, round(spk.pitch, 2), spk.female)
            clip = self.clips.get(key)
            if clip is None:
                rng = np.random.default_rng(abs(hash(key)) % (2 ** 32))
                clip = process(babble(line, rng, spk.pitch, spk.female), style, rng)
                self._store(key, clip)
            return clip
        text = native(line, spk.locale)
        if not text:
            return None
        rate = {"shout": 225, "scream": 240, "radio": 205, "talk": 185}.get(style, 210)
        rk = self._key(spk, text, rate)
        ck = (rk, round(spk.pitch, 2), style)
        clip = self.clips.get(ck)
        if clip is not None:
            return clip
        with self.lock:
            raw = self.ready.get(rk)
            if raw is None:
                if rk not in self.queued and rk not in self.failed:
                    self.queued.add(rk)
                    self._seq += 1
                    self.jobs.put((1 if warm else 0, self._seq, (rk, spk.voice, text, rate, spk.pbas)))
                return None
        x, sr = raw
        clip = process(_resample(x, sr, SR, spk.pitch), style, self.rng)
        self._store(ck, clip)
        return clip

    def warm(self, spk, lines, style="shout"):
        for ln in lines:
            self.request(spk, ln, style, warm=True)

    def pending(self):
        return self.jobs.qsize()

    def _store(self, key, clip):
        if len(self.clips) > self.MAX_CLIPS:
            for k in list(self.clips)[: self.MAX_CLIPS // 4]:
                del self.clips[k]
        self.clips[key] = clip

    def _work(self):
        while True:
            _, _, (rk, voice, text, rate, pbas) = self.jobs.get()
            path = os.path.join(CACHE_DIR, rk + ".wav")
            ok = os.path.exists(path) and os.path.getsize(path) > 1000
            if not ok:
                fd, tmp = tempfile.mkstemp(suffix=".wav", dir=CACHE_DIR)
                os.close(fd)
                ok = self.synth.render(voice, text, rate, pbas, tmp)
                if ok:
                    os.replace(tmp, path)
                else:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
            raw = None
            if ok:
                try:
                    x, sr = _load_wav(path)
                    x = _trim(x)
                    raw = (x, sr) if len(x) else None
                except Exception:
                    raw = None
            with self.lock:
                self.queued.discard(rk)
                if raw is not None:
                    if len(self.ready) > self.MAX_READY:
                        for k in list(self.ready)[: self.MAX_READY // 4]:
                            del self.ready[k]       # still on disk: comes back on the next request
                    self.ready[rk] = raw
                else:
                    self.failed.add(rk)
