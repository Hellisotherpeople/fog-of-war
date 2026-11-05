"""Your side speaks English (Options): your own army's words shown and spoken in English, in its own voices.

Old war films did it - the Germans in a German film speak German, and in an English one they speak English
with a German accent, while the enemy stays foreign.  With the option on, every line a man on your side says
passes through Actor.say, which swaps the native line for its English (data/translations.py, or the English
line of the same phrase when a line has no translation of its own), and marks it to be spoken in English by
the speaker's own voice (voice.py: the accent comes from the voice reading English as its language would).
The enemy keeps his language: you still have to know what "Handgranate!" means.
"""
from __future__ import annotations

import re

from .data.phrases import lang

ACTIVE_SIDE = None          # the player's side (the App sets it each frame)
ACTIVE_MODE = "own"         # all: every foreign line, own: your side and languages you know, off: nobody
PLAYER = None               # the player, for language knowledge (the App sets it each frame)
_LUCK: dict = {}
_UNDERSTOOD: dict = {}
LANGUAGE_ROLES = {"agent": 4.5, "intel": 4.0, "partisan": 2.0, "officer": 1.0, "squad_leader": 0.5}
LANGUAGE_UNITS = {"soe": 3.0, "oss": 3.0, "jedburgh": 4.0, "lrdg": 2.5, "razvedka": 3.0,
                  "brandenburg": 4.0, "chindits": 1.5, "raiders": 1.0, "cichociemni": 3.0}

_CACHE: dict = {}
_TEMPLATES: dict = {}
_INDEX: dict = {}
_FIELD = re.compile(r"\{(\w+)\}")


def understands(nation) -> bool:
    """Does the player get this language: training, role, or the ear of a man who has been about."""
    p = PLAYER
    if p is None or lang(nation) == "en":
        return False
    from .skills import level
    skill = level(p, "languages")
    key = (id(p), nation, int(skill * 2))
    if key in _UNDERSTOOD:
        return _UNDERSTOOD[key]
    import random
    skill += LANGUAGE_ROLES.get(p.role, 0.0) + LANGUAGE_UNITS.get(p.__dict__.get("unit_type") or "", 0.0)
    luck = _LUCK.setdefault((id(p), nation), random.random())
    ok = skill / 9.0 > luck and skill >= 2.0
    _UNDERSTOOD[key] = ok
    return ok


def active_for(actor) -> bool:
    if ACTIVE_MODE == "off" or lang(actor.nation) == "en":
        return False
    if ACTIVE_MODE == "all":
        return True
    if ACTIVE_SIDE is not None and actor.side == ACTIVE_SIDE:
        return True
    return ACTIVE_MODE == "own" and understands(actor.nation)


def translating(nation, side) -> bool:
    if ACTIVE_MODE == "off" or lang(nation) == "en":
        return False
    if ACTIVE_MODE == "all":
        return True
    if ACTIVE_SIDE is not None and side == ACTIVE_SIDE:
        return True
    return ACTIVE_MODE == "own" and understands(nation)


def _tables(lg):
    """native line -> English line, for one language: the translations, then the English of the same phrase."""
    idx = _INDEX.get(lg)
    if idx is not None:
        return idx
    idx = {}
    from .data import ranks as R
    from .data.chatter import C
    from .data.nations import NATIONS
    from .data.phrases import P
    # (the phrase tables are parallel: the n-th German line of a phrase says what the n-th English one does)
    for table in (P, C):
        for key, by_lang in table.items():
            en = by_lang.get("en") or []
            for i, line in enumerate(by_lang.get(lg) or []):
                if en:
                    idx.setdefault(line, en[i % len(en)])
    us = NATIONS["usa"]["shouts"]
    for n, d in NATIONS.items():
        if lang(n) != lg:
            continue
        for key, lines in d["shouts"].items():
            en = us.get(key) or []
            for i, line in enumerate(lines):
                if en:
                    idx.setdefault(line, en[i % len(en)])
        for src, en in ((R.ACK.get(n, []), R.ACK.get("usa", [])), (R.REFUSE.get(n, []), R.REFUSE.get("usa", []))):
            for i, line in enumerate(src):
                if en:
                    idx.setdefault(line, en[i % len(en)])
    try:
        from .data.banter import BANTER
        en = BANTER.get("en") or []
        for i, pair in enumerate(BANTER.get(lg) or []):
            if en:
                for a, b in zip(pair, en[i % len(en)]):
                    idx.setdefault(a, b)
    except ImportError:
        pass
    try:
        from .data.translations import EN
        idx.update(EN.get(lg, {}))                  # a real translation beats the English of the same phrase
    except ImportError:
        pass
    _INDEX[lg] = idx
    return idx


def _templates(lg):
    """The lines with blanks in them ({name}, {rank}, {part}), as patterns to recognise them filled in."""
    t = _TEMPLATES.get(lg)
    if t is None:
        t = []
        for src, dst in _tables(lg).items():
            if "{" in src:
                pat = re.escape(src)
                names = _FIELD.findall(src)
                for nm in dict.fromkeys(names):
                    pat = pat.replace(re.escape("{" + nm + "}"), f"(?P<{nm}>.+?)", 1)
                    pat = pat.replace(re.escape("{" + nm + "}"), f"(?P={nm})")
                try:
                    t.append((re.compile(pat + r"\Z"), dst))
                except re.error:
                    pass
        _TEMPLATES[lg] = t
    return t


def _part(lg, word):
    try:
        from .data.translations import PART_EN
        hit = PART_EN.get(lg, {}).get(word)
        if hit:
            return hit
    except ImportError:
        pass
    from .data.chatter import PART
    for pid, w in PART.get(lg, {}).items():
        if w == word:
            return PART["en"].get(pid, word)
    return word


def _noun(lg, word):
    """A thing in a trade ('Zigaretten') as the English say it ('smokes')."""
    from .data.chatter import NOUN
    for key, w in NOUN.get(lg, {}).items():
        if w == word:
            return NOUN["en"].get(key, word)
    return word


def english(nation, text):
    """The English for a line in this army's language, or None if it isn't one of theirs."""
    lg = lang(nation)
    if lg == "en" or not text:
        return None
    key = (lg, text)
    if key in _CACHE:
        return _CACHE[key]
    out = _tables(lg).get(text)
    if out is None:
        for pat, dst in _templates(lg):
            m = pat.match(text)
            if m:
                vals = {k: (_part(lg, v) if k == "part" else _noun(lg, v) if k in ("give", "want") else v)
                        for k, v in m.groupdict().items()}
                try:
                    out = dst.format(**{k: vals.get(k, "") for k in _FIELD.findall(dst)})
                except (KeyError, IndexError, ValueError):
                    out = None
                break
    if len(_CACHE) > 4000:
        _CACHE.clear()
    _CACHE[key] = out
    return out


# lines written straight into the code rather than the phrase tables
EXTRA = {"de": {"Mir ist so kalt...": "I'm so cold...", "Wasser...": "Water...", "Ja, ja...": "Yeah, yeah...",
                "Nein!": "No!"},
         "ru": {"Kholodno...": "So cold..."},
         "ja": {"Bakayarō!": "You bastards!"}}


def line(actor, text, voice):
    """What a man on your side says with the option on: (shown, spoken, in English?)."""
    en = english(actor.nation, text) or EXTRA.get(lang(actor.nation), {}).get(text)
    if en is not None:
        # shown beside the original, spoken in English by his own voice
        return f"{text} / {en}", en, True
    if not any(c.isalpha() for c in text):
        return text, voice, False          # a hum ("♪ ...") or a pause has no English: read aloud it'd be "symbol"
    from .game import is_native
    if is_native(actor.nation, text):
        return text, voice or text, False    # a native line with no translation: leave it in his language
    if voice is not None:
        # the caller wrote the line in English and had a native line (or silence) for the voice: say the English
        return text, text, True
    if not text.strip(".!? "):
        return text, None, False
    return text, None, True


def in_english(actor) -> bool:
    """Does he say an English-only line out loud: an English speaker, or your side with the option on."""
    return lang(actor.nation) == "en" or active_for(actor)
