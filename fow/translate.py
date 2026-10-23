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

ACTIVE_SIDE = None          # the player's side while the option is on (the App sets it each frame); None: it's off

_CACHE: dict = {}
_TEMPLATES: dict = {}
_INDEX: dict = {}
_FIELD = re.compile(r"\{(\w+)\}")


def active_for(actor) -> bool:
    return ACTIVE_SIDE is not None and actor.side == ACTIVE_SIDE and lang(actor.nation) != "en"


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
        return en, en, True
    if not any(c.isalpha() for c in text):
        return text, voice, False          # a hum ("♪ ...") or a pause has no English: read aloud it'd be "symbol"
    if voice is not None:
        # the caller wrote the line in English and had a native line (or silence) for the voice: say the English
        return text, text, True
    # a line in none of his army's tables is the game's own English (an order the player gives, a tank
    # commander's fire order): his voice reads it as English too
    from .game import is_native
    if not text.strip(".!? ") or is_native(actor.nation, text):
        return text, None, False
    return text, None, True


def in_english(actor) -> bool:
    """Does he say an English-only line out loud: an English speaker, or your side with the option on."""
    return lang(actor.nation) == "en" or active_for(actor)
