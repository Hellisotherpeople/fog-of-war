"""Grease-pencil marks on the map: a rally point, a danger, cover worth having, a cache, a casualty.

A mark is the player's own memory made visible.  It belongs to the ground, not to the sheet: it is kept
in world coordinates and comes back to the map when that ground does, through walking, streaming or a
save.  The section can see the pencil marks when it matters - a routed squad falls back on a rally
point and a medic works through marked casualties - and nothing about them is magic: only ground you
have actually seen can be marked.
"""
from __future__ import annotations

MAX = 80
MERGE = 2                        # the same kind within two tiles is one mark, moved and re-dated

KINDS = {
    "danger": ("!", "danger", (255, 110, 90)),
    "rally": ("⚑", "rally point", (150, 220, 140)),
    "cover": ("○", "firing position", (170, 195, 255)),
    "cache": ("▣", "cache", (235, 210, 120)),
    "casualty": ("+", "casualty", (240, 160, 160)),
}
ORDER = tuple(KINDS)
KEY = {"1": "danger", "2": "rally", "3": "cover", "4": "cache", "5": "casualty"}
LINE = "  ".join(f"{n} {KINDS[k][0]} {KINDS[k][1]}" for n, k in KEY.items())


def world_of(game, x, y):
    land = game.__dict__.get("landscape")
    if land is not None and getattr(land, "frame", None) is game.map:
        return land.world_pos(x, y)
    w, h = game.map_w, game.map_h
    s = game.sector
    return s.x * w + x, s.y * h + y


def local_of(game, wx, wy):
    land = game.__dict__.get("landscape")
    if land is not None and getattr(land, "frame", None) is game.map:
        ox, oy = land.origin
        return wx - ox, wy - oy
    w, h = game.map_w, game.map_h
    s = game.sector
    return wx - s.x * w, wy - s.y * h


def _marks(game):
    return game.__dict__.setdefault("map_marks", [])


def at(game, x, y):
    """Marks on this tile, nearest first (they are yours, so there are only ever yours)."""
    out = []
    for mk in _marks(game):
        lx, ly = local_of(game, mk["wx"], mk["wy"])
        if lx == x and ly == y:
            out.append(mk)
    return out


def near(game, x, y, radius=1):
    out = []
    for mk in _marks(game):
        lx, ly = local_of(game, mk["wx"], mk["wy"])
        if max(abs(lx - x), abs(ly - y)) <= radius:
            out.append(mk)
    return out


def place(game, x, y, kind, by=None):
    """Mark this tile.  Returns the mark, or None when there is nothing to write on."""
    m = game.map
    p = game.player
    if kind not in KINDS or not m.in_bounds(x, y) or not m.explored[x, y]:
        return None
    wx, wy = world_of(game, x, y)
    for mk in _marks(game):
        if mk["kind"] == kind and max(abs(mk["wx"] - wx), abs(mk["wy"] - wy)) <= MERGE:
            mk["wx"], mk["wy"] = wx, wy
            mk["turn"] = game.turn
            mk["by"] = (by or p).id
            return mk
    mk = dict(wx=wx, wy=wy, kind=kind, side=(by or p).side, by=(by or p).id, turn=game.turn)
    marks = _marks(game)
    marks.append(mk)
    if len(marks) > MAX:
        del marks[:len(marks) - MAX]
    return mk


def clear_at(game, x, y, radius=1):
    go = {(mk["wx"], mk["wy"]) for mk in near(game, x, y, radius)}
    if not go:
        return 0
    marks = _marks(game)
    before = len(marks)
    marks[:] = [mk for mk in marks if (mk["wx"], mk["wy"]) not in go]
    return before - len(marks)


def on_map(game, side=None):
    """(local x, local y, mark) for marks on the map in hand."""
    m = game.map
    out = []
    for mk in _marks(game):
        if side is not None and mk.get("side") != side:
            continue
        x, y = local_of(game, mk["wx"], mk["wy"])
        if m.in_bounds(x, y):
            out.append((x, y, mk))
    return out


def in_sector(game, sx, sy):
    w, h = game.map_w, game.map_h
    return [mk for mk in _marks(game)
            if sx * w <= mk["wx"] < (sx + 1) * w and sy * h <= mk["wy"] < (sy + 1) * h]


def nearest(game, x, y, kind=None, radius=90, side=None):
    """The nearest mark of a kind, in local map coordinates, within a radius of tiles."""
    m = game.map
    best = None
    for mk in _marks(game):
        if kind is not None and mk["kind"] != kind:
            continue
        if side is not None and mk.get("side") != side:
            continue
        lx, ly = local_of(game, mk["wx"], mk["wy"])
        if not m.in_bounds(lx, ly):
            continue
        d = max(abs(lx - x), abs(ly - y))
        if d <= radius and (best is None or d < best[0]):
            best = (d, lx, ly, mk)
    return best


def color(mk, turn):
    """Old pencil fades: a mark from yesterday is still there, but not trusted the way a fresh one is."""
    base = KINDS[mk["kind"]][2]
    age = max(0, turn - mk.get("turn", turn))
    if age > 86400:
        f = 0.45
    elif age > 7200:
        f = max(0.55, 1.0 - (age - 7200) / 40000)
    else:
        f = 1.0
    return tuple(int(c * f) for c in base)


def age_words(turns):
    if turns < 10:
        return "a moment ago"
    if turns < 90:
        return f"{turns} seconds ago"
    if turns < 5400:
        return f"{max(1, turns // 60)} minutes ago"
    if turns < 86400:
        return f"{turns // 3600} hours ago"
    return f"{turns // 86400} days ago"


def look_lines(game, x, y):
    out = []
    for mk in at(game, x, y):
        glyph, name, _col = KINDS[mk["kind"]]
        age = age_words(max(0, game.turn - mk.get("turn", game.turn)))
        out.append((f"{glyph} You marked this as a {name} {age}.", color(mk, game.turn)))
    return out


REMEMBER = 600                    # ten minutes: where the enemy was, and no longer


def remember_enemies(game):
    """What you have seen of the enemy stays on the sheet a while after he's gone to ground."""
    p = game.player
    seen = game.__dict__.setdefault("enemy_seen", {})
    for a in getattr(p, "visible", ()) or ():
        if a.side == p.side or not a.alive or a.vehicle is not None or a.ai.get("civilian"):
            continue
        wx, wy = world_of(game, a.x, a.y)
        seen[a.id] = dict(wx=wx, wy=wy, turn=game.turn, kind=a.role_name if hasattr(a, "role_name") else "soldier")
    dead = [i for i, s in seen.items() if game.turn - s["turn"] > REMEMBER]
    for i in dead:
        del seen[i]
    if len(seen) > 60:
        for i in sorted(seen, key=lambda i: seen[i]["turn"])[:len(seen) - 60]:
            del seen[i]


def sightings(game):
    """(local x, local y, record, colour) for enemies seen recently."""
    m = game.map
    out = []
    for rec in game.__dict__.get("enemy_seen", {}).values():
        age = game.turn - rec["turn"]
        if age > REMEMBER:
            continue
        x, y = local_of(game, rec["wx"], rec["wy"])
        if not m.in_bounds(x, y) or not m.explored[x, y]:
            continue
        f = max(0.35, 1 - age / REMEMBER)
        out.append((x, y, rec, (int(255 * f), int(95 * f + 20), int(75 * f + 20))))
    return out


def announce(game, x, y, kind, by=None):
    mk = place(game, x, y, kind, by)
    if mk is None:
        game.msg("There's nothing there to mark - you haven't seen it.", "info")
        return None
    _, name, _ = KINDS[kind]
    game.msg(f"You write a {name} on your map.", "info")
    return mk


def note(game, x, y):
    """A plain description for the tile's line in the look and map panels."""
    kinds = [KINDS[mk["kind"]][1] for mk in at(game, x, y)]
    return ", ".join(dict.fromkeys(kinds)) if kinds else None
