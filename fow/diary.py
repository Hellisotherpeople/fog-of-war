"""The little book in the pocket.

A soldier writes down what he can't say.  The diary keeps the run: the first shot, the ground taken, the men
lost beside him, the citations, the promises made to the dying, the camps and the bad mornings.  It starts
with which battle and who he was, and it ends on the death screen, where it is the only continuous account
of the short life just played.

Entries are the game's own voice and the run's real record, not a scoreboard.  Photographs are taken with a
camera and described as the man would describe them: the light, the ground, the faces he can see.
"""
from __future__ import annotations

import os
import textwrap


def _book(game) -> list:
    return game.__dict__.setdefault("diary", [])


def entry(game, kind: str, text: str) -> None:
    """Add a line, with the date and place."""
    if game.map is None:
        return
    try:
        stamp = game.now().strftime("%d %b %H:%M")
    except Exception:
        stamp = "the field"
    sec = game.sector.name if game.sector is not None else "the field"
    _book(game).append(dict(kind=kind, at=game.turn, stamp=stamp, where=sec, text=text))
    if len(_book(game)) > 300:
        del _book(game)[0]


def start(game) -> None:
    p = game.player
    _book(game).clear()
    entry(game, "start", f"{game.theatre['battle']}. I am {p.rank_full} {p.name}, {p.role_name.lower()}, "
                         f"{game.side_nation(p.side)} army. I don't know how long this lasts. I'll write it down.")


def photo(game, why="") -> str:
    """A photograph: what is in front of the man, as he would remember it."""
    p = game.player
    from .weather import description
    m = game.map
    near = [a for a in game.actors if a.alive and a is not p and a.side == p.side and
            max(abs(a.x - p.x), abs(a.y - p.y)) <= 4 and a.vehicle is None]
    faces = [a.last_name for a in near[:3]]
    ground = m.tile(p.x, p.y).name if m.in_bounds(p.x, p.y) else "the ground"
    light = "in the dark" if game.is_night() else "in daylight"
    bits = [f"Photograph {light}, {description(game).lower()}", f"the {ground}"]
    if faces:
        bits.append("faces: " + ", ".join(faces))
    if why:
        bits.append(why)
    text = "; ".join(bits) + "."
    entry(game, "photo", text)
    return text


def won(game, name: str) -> None:
    entry(game, "award", f"{name}.")


def lost(game, a) -> None:
    from .people import call_name
    entry(game, "loss", f"{a.rank_short} {call_name(a)} was killed beside me. {a.last_name}'s people are in "
                        f"{a.life['town'] if a.__dict__.get('life') else 'some town I never saw'}.")


def promise(game, text: str) -> None:
    entry(game, "promise", text)


def export(game) -> str | None:
    """Write the diary out beside the saves at the end; a run leaves something behind."""
    p = game.player
    home = os.environ.get("FOW_HOME") or os.path.expanduser("~/.fogofwar")
    try:
        d = os.path.join(home, "diaries")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, game.now().strftime("%Y%m%d-%H%M") + f"-{p.last_name.lower()}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"FOG OF WAR - the diary of {p.rank_full} {p.name}\n")
            f.write(f"{game.theatre['name']}: {game.theatre['battle']}\n\n")
            for e in _book(game):
                f.write(f"{e['stamp']} - {e['where']}\n{textwrap.fill(e['text'], 88)}\n\n")
        return path
    except OSError:
        return None
