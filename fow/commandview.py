"""The trace: what every unit under your hand has been told to do, and where it will happen.

F8 lays a grease-pencil trace over the ground.  Each unit's ordered area is shaded, its line of
advance is drawn, and the ground its fire covers is hatched.  Overlapping areas get darker: where
three units' sectors cross, you are strong; where none does, there is a gap.  A leader looks at the
trace before he looks at the enemy.

It is a reading of orders, not omniscience: units appear where they were last heard of, and a unit
you cannot reach is drawn faint and marked with a question.  The enemy is not on it.
"""
from __future__ import annotations

from .cmdui import command_units, _state_color
from .constants import UI_DIM, VIEW_H, VIEW_W

HATCH = ("·", "░", "▒", "▓")
COL = {0: (90, 105, 80), 1: (140, 180, 120), 2: (215, 195, 110), 3: (240, 150, 95), 4: (240, 105, 85)}
FIRE_KINDS = ("watch", "defend", "hold", "ambush", "suppress", "attack", "assault", "flank", "probe",
              "infiltration", "stoss", "schwerpunkt", "motti", "bite_and_hold", "recon_by_fire")


def draw(con, ps):
    g = ps.game
    cam = ps.cam
    cmd = g.command
    chain, others = command_units(g)
    units = chain + others
    heat = {}
    labels = []
    for sq in units:
        k = cmd.known_of(g, sq)
        if k is None:
            continue
        stale = g.turn - k["turn"] > 15
        col = _state_color(sq, stale) if sq in chain else (150, 170, 200)
        o = sq.order
        anchor = (k["x"], k["y"])
        tgt = o.target if o.src == "player" and o.target is not None else anchor
        if sq.player_led and o.kind == "follow":
            tgt = (g.player.x, g.player.y)
        # the ordered area
        r = max(2, int(o.radius))
        if o.kind in ("move", "attack", "assault", "flank", "probe", "suppress", "ambush", "dig",
                      "defend", "hold", "follow", "resupply"):
            _area(heat, tgt, r, cam, 2 if o.kind in ("defend", "hold", "ambush", "suppress") else 1)
        # its line
        _line(con, cam, anchor, tgt, col, stale)
        # what its fire covers: a cone toward the enemy side of its order
        if o.kind in FIRE_KINDS:
            _cone(heat, anchor, tgt, cam, col)
        labels.append((tgt, anchor, sq, o, col, stale))
    # the heat first, under the pencil
    for (x, y), n in heat.items():
        if not cam.on_screen(x, y):
            continue
        sx, sy = cam.to_screen(x, y)
        if not (0 <= sx < VIEW_W and 0 <= sy < VIEW_H):
            continue
        con.print(sx, sy, HATCH[min(3, n // 2)], fg=COL[min(4, n)])
    # then units, areas and names
    for tgt, anchor, sq, o, col, stale in labels:
        if cam.on_screen(*tgt):
            _ring(con, cam, tgt, max(2, int(o.radius)), col)
            tx, ty = cam.to_text(*tgt)
            name = (sq.short or sq.name)[:5]
            tail = "?" if stale else ""
            con.print(tx, ty, f"[{name}{tail}]", fg=(18, 18, 14), bg=col)
        if cam.on_screen(*anchor):
            ax, ay = cam.to_text(*anchor)
            con.print(ax, ay, _sym(o), fg=col)
    if not units:
        con.print(2, 2, "No units under your hand.", fg=UI_DIM)


def _sym(o):
    from .cmdui import ORDER_SYM
    return ORDER_SYM.get(o.drill or o.kind, "+")


def _area(heat, c, r, cam, weight):
    x0, y0 = c
    for x in range(x0 - r, x0 + r + 1):
        for y in range(y0 - r, y0 + r + 1):
            if (x - x0) ** 2 + (y - y0) ** 2 > r * r:
                continue
            heat[(x, y)] = heat.get((x, y), 0) + weight


def _ring(con, cam, c, r, col):
    """A dotted circle, on the cells the map console can show."""
    import math
    for i in range(0, 32):
        a = 2 * math.pi * i / 32
        x, y = int(round(c[0] + math.cos(a) * r)), int(round(c[1] + math.sin(a) * r))
        if cam.on_screen(x, y):
            sx, sy = cam.to_screen(x, y)
            con.print(sx, sy, "·", fg=col)


def _line(con, cam, a, b, col, stale):
    import math
    d = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    for i in range(1, d, 2):
        x = int(round(a[0] + (b[0] - a[0]) * i / d))
        y = int(round(a[1] + (b[1] - a[1]) * i / d))
        if cam.on_screen(x, y):
            sx, sy = cam.to_screen(x, y)
            con.print(sx, sy, "·" if stale else "‑", fg=(col[0] // 2 + 40, col[1] // 2 + 40, col[2] // 2 + 40))


def _cone(heat, anchor, tgt, cam, col):
    """Roughly where the unit's fire falls: from where it is, through what it was told to hold or take."""
    import math
    dx, dy = tgt[0] - anchor[0], tgt[1] - anchor[1]
    if dx == dy == 0:
        return
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    reach = 14
    for step in range(1, reach + 1):
        cx, cy = anchor[0] + ux * step, anchor[1] + uy * step
        spread = 0.35 + step * 0.16
        for side in (-1, 0, 1):
            x = int(round(cx - uy * spread * side))
            y = int(round(cy + ux * spread * side))
            heat[(x, y)] = heat.get((x, y), 0) + 1


def legend(con):
    con.print(2, VIEW_H - 1, " TRACE  ·  ordered area   ░ fire   [unit] last word   ? no word ", fg=(230, 220, 180),
              bg=(30, 28, 20))
