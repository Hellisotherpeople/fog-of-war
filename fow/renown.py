"""Your name, while it lasts.

Men become known in a battle, and the other side learns the names of the ones who cost them.  This keeps
what the player has done in this run: the kills that mattered, the ground taken, men carried out, citations.
The section starts to talk about him and gives him a name; the enemy's observers list him, then his stretch
of line, then send a sniper or a patrol after him; prisoners who have heard the name look at him differently.

It is all local to the run.  A new game is a new world, with a new nobody.
"""
from __future__ import annotations

THRESHOLDS = ((6, "noticed"), (14, "named"), (28, "hunted"), (50, "feared"), (85, "legend"))
WORDS = {
    "noticed": "The section has started to talk about you.",
    "named": "The section has a name for you now: {nick}.",
    "hunted": "The enemy know the name. There's a sniper working your stretch of line.",
    "feared": "Enemy patrols give your section's front a wider berth. They've been told about you.",
    "legend": "The company tells your story to replacements. Half of it is true.",
}
NAMES = {
    "usa": ["the Ghost", "Doc", "the Deacon", "Lucky", "the Farmer", "Two-Gun", "the Professor", "Pop"],
    "uk": ["the Ghost", "the Sergeant", "Lucky", "the Miner", "the Padre", "Smiler"],
    "germany": ["der Geist", "der Alte", "der Jäger", "der Feuerwehr"],
    "ussr": ["the Ghost", "the Hunter", "the Teacher"],
    "japan": ["the Shadow", "the Hunter"],
    "italy": ["il Fantasma", "il Vecchio"],
}
FEATS = {
    "kill": 1, "close": 2, "vehicle": 3, "objective": 3, "rescue": 3, "capture": 2, "medal": 8,
    "wound": 1, "hold": 2,
}


def state(game) -> dict:
    st = game.__dict__.get("renown")
    if st is None:
        st = game.__dict__["renown"] = dict(score=0, stage="", nick=None, feats=[], kills=0, close=0,
                                            vehicles=0, rescued=0, objectives=0)
    return st


def stage(game) -> str:
    s = state(game)["score"]
    out = ""
    for n, word in THRESHOLDS:
        if s >= n:
            out = word
    return out


def threat(game, a) -> float:
    """How much the enemy wants this man above another."""
    if not getattr(a, "is_player", False):
        return 1.0
    s = state(game)["score"]
    if s >= 50:
        return 2.2
    if s >= 28:
        return 1.8
    if s >= 14:
        return 1.4
    if s >= 6:
        return 1.15
    return 1.0


def known(game) -> bool:
    return state(game)["score"] >= 14


def event(game, kind: str, n: int = 1, text: str | None = None) -> None:
    """Something that makes a man's name.  Only the first few of each count."""
    p = game.player
    if p is None or not p.alive:
        return
    st = state(game)
    st["feats"].append((game.turn, kind, text))
    st["feats"] = st["feats"][-40:]
    before = stage(game)
    weight = FEATS.get(kind, 1)
    if kind == "kill":
        st["kills"] += 1
        if st["kills"] > 25:
            weight = 0
    elif kind == "close":
        st["close"] += 1
    elif kind == "vehicle":
        st["vehicles"] += 1
    elif kind == "rescue":
        st["rescued"] += 1
    elif kind == "objective":
        st["objectives"] += 1
    st["score"] += weight * n
    for threshold, word in THRESHOLDS:
        if before != word and st["score"] >= threshold and st.get("stage") != word:
            st["stage"] = word
            if word == "named":
                st["nick"] = game.rng.choice(NAMES.get(p.nation, NAMES["usa"]))
            game.msg(WORDS[word].format(nick=st.get("nick") or "the new man"), "good")
            from . import diary
            diary.entry(game, "name", WORDS[word].format(nick=st.get("nick") or "the new man"))
            break


def title(game) -> str | None:
    st = state(game)
    if not st.get("nick") or st["score"] < 14:
        return None
    return st["nick"]


def prisoner_worth(game) -> float:
    """A prisoner who has heard of the player is a little more forthcoming, or more frightened."""
    return 0.12 if known(game) else 0.0
