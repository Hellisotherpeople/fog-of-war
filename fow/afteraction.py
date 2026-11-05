"""What led to it: the last minute, from what the soldier knew.

The game already knows the facts of a death - the round, the wound, the man who fired - but a
sentence with the cause in it tells a player nothing about the decision that put him there.  This
keeps a short, cheap record of the player's own state each second (stance, cover, movement, rounds,
suppression, wounds, what he could see) and turns it, at the end, into a plain timeline.

Facts and inference are kept apart.  A line is a fact when the game saw it happen to him; it is
inference when it comes from the trace (a dropped cover value, a rise in suppression) and not from
a visible man.  The unseen shooter's exact position is never printed - only that fire came from
somewhere he had not looked.
"""
from __future__ import annotations

KEEP = 150                       # seconds of trace
MAX_LINES = 10


def sample(game):
    """One second of the player's state.  Called from the world turn; cheap on purpose."""
    p = game.player
    if p is None or not p.alive:
        return
    b = p.body
    m = game.map
    if m is None or not m.in_bounds(p.x, p.y):
        return
    seen = 0
    for e in getattr(p, "visible", ()) or ():
        if getattr(e, "vt", None) is None and getattr(e, "alive", True):
            seen += 1
    aid = None
    from .medical import aid_posts
    posts = aid_posts(game, p.side) or ()
    if posts:
        aid = min(max(abs(r[0] - p.x), abs(r[1] - p.y)) for r in posts)
    tr = game.__dict__.setdefault("trace", [])
    tr.append(dict(
        t=game.turn, x=p.x, y=p.y, stance=p.stance, cover=int(m.pos_cover[p.x, p.y]),
        sup=int(p.suppression), bleed=round(b.bleed_rate(), 2), wounds=len(b.wounds),
        mag=(p.weapon.loaded if p.weapon is not None and p.weapon.t.kind == "gun" else -1),
        seen=seen, aid=aid, held=(p.weapon.t.id if p.weapon is not None else None),
        treating=bool(p.ai.get("treating", 0) > game.turn),
        moving=p.moved_turn >= game.turn - 1))
    if len(tr) > KEEP:
        del tr[:-KEEP]


def _turn_word(d):
    return "just before" if d < 3 else f"{d}s before"


def report(game, killer=None):
    """The timeline, newest last.  [] when there is no trace (a save from before this existed)."""
    tr = list(game.__dict__.get("trace") or ())
    if not tr:
        return []
    end = tr[-1]["t"]
    start = max(tr[0]["t"], end - 75)
    tr = [s for s in tr if s["t"] >= start]
    out = []
    prev = None
    for s in tr:
        ago = end - s["t"]
        if prev is None:
            if s["seen"]:
                out.append((ago, f"You had {s['seen']} of the enemy in sight.", "fact"))
            prev = s
            continue
        # stood up in the open
        if prev["stance"] == 2 and s["stance"] < 2 and s["seen"] and s["cover"] < 45:
            out.append((ago, "You got up in the open with the enemy in sight.", "fact"))
        # began a reload with a part-empty magazine, close in
        elif s["mag"] == 0 and prev["mag"] > 0 and s["seen"]:
            out.append((ago, "The magazine ran dry and you began to reload.", "fact"))
        # walked out of cover
        elif (s["x"], s["y"]) != (prev["x"], prev["y"]) and prev["cover"] >= 45 and s["cover"] < 30:
            out.append((ago, "You left cover for open ground.", "fact"))
        # rounds arriving
        if s["sup"] > prev["sup"] + 20:
            who = "The enemy had you in view." if s["seen"] else "Rounds came in from somewhere you had not seen."
            out.append((ago, who, "fact" if s["seen"] else "infer"))
        if s["wounds"] > prev["wounds"]:
            out.append((ago, "You were hit.", "fact"))
        if s["bleed"] > prev["bleed"] + 0.2 and prev["bleed"] <= 0.9:
            part = "It bled badly."
            out.append((ago, part, "fact"))
        if s["treating"] and not prev["treating"]:
            out.append((ago, "You stopped to put a dressing on.", "fact"))
        if s["aid"] is not None and (prev["aid"] is None or s["aid"] < prev["aid"] - 8):
            out.append((ago, f"The nearest aid post was {s['aid']} yards off.", "fact"))
        prev = s
    # coalesce repeats, keep the end of the story, then the start
    lines = []
    seen_at = set()
    for ago, text, kind in reversed(out):
        if text in seen_at:
            continue
        seen_at.add(text)
        lines.append((ago, text, kind))
        if len(lines) >= MAX_LINES:
            break
    lines.reverse()
    tail = []
    if killer is not None:
        if getattr(killer, "vt", None) is not None:
            tail.append((0, f"A {killer.vt.name} was firing at you.", "fact"))
        elif getattr(killer, "visible", False) or killer in (getattr(game.player, "visible", ()) or ()):
            tail.append((0, "He was in your sight when he fired.", "fact"))
        else:
            tail.append((0, "He was not in your sight when he fired.", "infer"))
    final = (end, "You died of your wounds.", "fact")
    result = [(a, t, k) for a, t, k in lines] + tail + [final]
    game.death_advice = _advice(result, game)
    return result


_ADVICE = (
    ("got up in the open", "Stand up to move, not to think: reload and dress crouched or flat."),
    ("ran dry", "Change magazines in cover before the pouches are empty."),
    ("left cover", "Cross open ground in bounds, with a man watching for you."),
    ("Rounds came in", "Rounds coming in: get flat and crawl to the nearest cover. Look for the flash."),
    ("hurt badly", "A dressing on early is worth ten on later."),
    ("bled badly", "Bad bleeding: pressure dressing now; a tourniquet if it is a limb."),
    ("put a dressing on", "Treat in cover. The enemy shoots the man kneeling in the open."),
    ("aid post was", "Find the aid post before the shooting starts."),
)


def _advice(lines, game):
    out = []
    text = " ".join(t for _a, t, _k in lines)
    for needle, tip in _ADVICE:
        if needle.lower() in text.lower() and tip not in out:
            out.append(tip)
        if len(out) >= 3:
            break
    if not out:
        out.append("Get flat early and crawl to cover; standing up in the open is what most deaths have in common.")
    return out


REMARKS = (
    "The quartermaster will want the rifle back.",
    "His name goes in the company roll, in ink, and stays there.",
    "There is a letter to write. It will be someone else's job.",
    "He was not the first this morning and will not be the last tonight.",
    "The platoon fills the gap and carries on. There is nothing else to do.",
    "A shellhole is a grave until the burying party comes.",
)


def remark(game):
    return REMARKS[game.turn % len(REMARKS)]


def render(con, x, y, width, lines):
    """Draw the timeline; returns the row after it."""
    from . import textfit
    wcol = max(1, width - 12)
    for ago, text, kind in lines:
        if y > 26:
            break
        stamp = _turn_word(ago)[:11]
        col = (200, 190, 160) if kind == "fact" else (175, 175, 160)
        stamp = textfit.fit(stamp, 11)
        for i, w in enumerate(textfit.wrap(text, wcol)):
            con.print(x, y, (stamp if i == 0 else ""), fg=(150, 145, 125))
            con.print(x + 12, y, textfit.fit(w, wcol), fg=col)
            y += 1
    return y


def _wrap(text, width):
    import textwrap
    return textwrap.wrap(text, max(10, width)) or [""]
