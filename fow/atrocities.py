"""The ugly ledger: prisoners, civilians, reprisals, and the camp.

The war was not clean and the game says so, in the game's voice and without a lecture.  What counts
as an atrocity depends a little on who is looking: an SS field unit's book expects a reprisal and
celebrates it; a line regiment shrugs; a Soviet or German staff wants it written down.  The player
is judged by the men who saw it, and by what his own unit is taught to expect.

Nothing here changes the wound model.  It records the thing, gives the men who saw it a reaction,
and leaves a line in the record for the debrief and the after-action report.
"""
from __future__ import annotations

KINDS = {
    "prisoner_shot": ("shot a prisoner", 1),
    "civilian_killed": ("a civilian killed", 1),
    "town_shelled": ("shelled a town", 1),
    "reprisal": ("a reprisal", 2),
    "camp_death": ("a prisoner dead in the camp", 1),
    "camp_selection": ("men sent away from the ramp", 2),
}


def _ss(game):
    return getattr(game.player, "service", "") == "ss"


def _state(game):
    return game.__dict__.setdefault("atrocities", dict(counts={}, last={}, lines=[]))


def note(game, kind, where=None, detail="", by="you"):
    """Record it.  Rate-limited per kind so a bombardment doesn't write a hundred lines."""
    if kind not in KINDS:
        return
    st = _state(game)
    t = game.turn
    if t - st["last"].get(kind, -9999) < 45 and kind != "reprisal":
        st["counts"][kind] = st["counts"].get(kind, 0) + 1
        return
    st["last"][kind] = t
    st["counts"][kind] = st["counts"].get(kind, 0) + 1
    word = KINDS[kind][0]
    line = f"{word.capitalize()}" + (f" at {where}" if where else "") + (f": {detail}" if detail else "") + "."
    st["lines"].append((game.turn, line))
    ss = _ss(game)
    if kind in ("prisoner_shot", "reprisal") and ss:
        game.msg(f"{line} The SS book expects no less.", "info")
        game.command.merit += 2
    elif kind in ("civilian_killed", "town_shelled"):
        game.msg(f"{line} Nobody in the section looks surprised.", "info")
    elif kind == "camp_selection":
        game.msg(f"{line}.", "info")
    else:
        game.msg(line, "info")


def prisoner_shot(game, victim, witness=None):
    note(game, "prisoner_shot", detail=f"{game.name_of(victim)} had his hands up")
    if witness is not None and witness.active and game.rng.random() < 0.5:
        witness.morale = max(0.0, witness.morale - 1)


def civilian_killed(game, victim, killer=None):
    note(game, "civilian_killed", detail=f"{game.name_of(victim)}")


def town_shelled(game, x, y):
    m = game.map
    if not (m.in_bounds(x, y) and m.tile(x, y).floor):
        return
    note(game, "town_shelled", where=game.sector.name)


def camp_selection(game, where="the ramp", count=1):
    note(game, "camp_selection", where=where, detail=f"{count} taken off the strength")


def camp_death(game, count=1):
    note(game, "camp_death", detail=f"{count} on the strength this week")


def summary(game):
    st = game.__dict__.get("atrocities") or {}
    out = []
    for k, n in (st.get("counts") or {}).items():
        if n:
            out.append(f"{n} x {KINDS[k][0]}")
    return out
