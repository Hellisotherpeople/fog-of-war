"""Behind the wire: guarding prisoners, and the other kind of camp.

Two duties share one routine.  A prisoner-of-war camp is a working camp: roll calls, work parties,
a ration that is never quite enough, and men who will try the wire.  A German concentration camp is
the same routine with the fear turned up: selections, kapos, punishments, and work that is meant to
kill as much as to produce.

The player is a guard, not the commandant.  The choices are the ones a guard actually had: how hard
to drive a party, whether to look away from a beating, whether to sign a man off as unfit, whether to
share a cigarette.  The outcomes are deliberately mixed - every choice buys something and costs
something, and the two camps do not feel the same to stand in.

Historical shape only: Stalag rations and Arbeitskommandos, KZ Appell, Blockälteste and Selection.
Nothing here is numbered from a single camp.
"""
from __future__ import annotations

import math

from . import tiles as T

POW_TILES = ("bunk", "wire", "gate", "lookout_post", "table", "sacks", "water_trough")


def _t(game, key):
    return T.ID.get(key)


def build(game, kind="pow"):
    """A compound in the rear: wire on a rectangle, a gate, huts, a tower, and a road out."""
    from . import mapgen
    m = game.map
    rng = game.rng
    p = game.player
    cx, cy = p.x, p.y
    for _ in range(200):
        cx, cy = rng.randint(30, m.w - 30), rng.randint(25, m.h - 25)
        if all(m.in_bounds(cx + dx, cy + dy) and m.walk[cx + dx, cy + dy]
               for dx in range(-14, 15, 3) for dy in range(-11, 12, 3)):
            break
    w, h = 26, 18
    x0, y0 = cx - w // 2, cy - h // 2
    x1, y1 = x0 + w, y0 + h
    ground = int(m.t[cx, cy])
    for x in range(x0 - 2, x1 + 2):
        for y in range(y0 - 2, y1 + 2):
            if m.in_bounds(x, y) and T.WALK[m.t[x, y]]:
                m.t[x, y] = ground
    # the wire, the gate and the tower
    for x in range(x0, x1 + 1):
        m.t[x, y0] = _t(game, "wire") if x != cx else _t(game, "gate")
        m.t[x, y1] = _t(game, "wire")
    for y in range(y0, y1 + 1):
        m.t[x0, y] = _t(game, "wire")
        m.t[x1, y] = _t(game, "wire")
    m.t[x1 - 2, y0] = _t(game, "lookout_post")
    m.t[x0 + 2, y0] = _t(game, "table")
    for hx, hy in ((x0 + 5, y0 + 4), (x0 + 5, y1 - 5), (x1 - 7, y0 + 4), (x1 - 7, y1 - 5)):
        for dx in range(3):
            for dy in range(2):
                if m.in_bounds(hx + dx, hy + dy):
                    m.t[hx + dx, hy + dy] = _t(game, "floor_wood")
        for dx in range(1, 3):
            if m.in_bounds(hx + dx, hy + 1):
                m.t[hx + dx, hy + 1] = _t(game, "bunk")
    m.t[x0 + 2, y1 - 3] = _t(game, "sacks")
    m.t[cx, y1 - 2] = _t(game, "water_trough")
    m.t[cx, y0 + 2] = _t(game, "table")
    # the road out, and a work site beyond it
    for y in range(y0 - 12, y0):
        if m.in_bounds(cx, y) and T.WALK[m.t[cx, y]]:
            m.t[cx, y] = _t(game, "road")
    m.refresh()
    game.map.refresh()
    game.__dict__["camp"] = dict(kind=kind, x=cx, y=cy, rect=(x0, y0, w, h), prisoners=0, dead=0,
                                 labour=0.0, next=game.turn + 60, log=[])
    game.player.x, game.player.y = cx, y0 - 2
    from .spawn import place
    place(game, p, cx, y0 - 2, 4)
    game.player_fov()


def populate(game, n):
    """Prisoners in the compound, guards at the gate and the tower."""
    from .spawn import make_soldier, place
    c = game.__dict__.get("camp")
    if c is None:
        return
    side = game.player.side
    enemy = game.side_nation("axis" if side == "allies" else "allies")
    x0, y0, w, h = c["rect"]
    x1 = x0 + w
    y1 = y0 + h
    rng = game.rng
    for i in range(n):
        a = make_soldier(game, enemy, "rifleman", rank=1)
        a.ai["camp_prisoner"] = True
        a.ai["camp_role"] = "labour"
        a.role = "prisoner"
        a.weapon = None
        x, y = rng.randint(x0 + 2, x0 + w - 2), rng.randint(y0 + 2, y0 + h - 2)
        if place(game, a, x, y, 3):
            c["prisoners"] += 1
    guard_n = max(3, n // 4)
    for i in range(guard_n):
        a = make_soldier(game, game.player.nation, "rifleman", rank=1)
        a.ai["camp_guard"] = True
        a.role = "guard"
        place(game, a, rng.choice((x0 + 2, x1 - 2)), rng.randint(y0 + 2, y1 - 2), 3)
    c["next"] = game.turn + 90


def _say(game, text, kind="info"):
    if game.player.side:
        game.msg(text, kind)
    c = game.__dict__.get("camp")
    if c is not None:
        c["log"].append(text)


def _word(c):
    return "KZ" if c.get("kind") == "camp" else "camp"


def roll_call(game):
    c = game.__dict__["camp"]
    alive = sum(1 for a in game.actors if a.alive and a.ai.get("camp_prisoner"))
    c["prisoners"] = alive
    missing = max(0, c.get("expected", alive) - alive)
    c["expected"] = alive
    _say(game, f"Appell. {alive} on parade." + (f" {missing} missing." if missing else ""), "info")
    if missing:
        _say(game, "The commandant wants the wire checked and the roll corrected.", "warn")


def event(game):
    """A choice a guard actually faced.  Two or three options, each with a cost."""
    from .render import Popup
    c = game.__dict__.get("camp")
    ps = game.__dict__.get("_play")
    if c is None or ps is None:
        return
    k = c["kind"]
    p = game.player
    if k == "camp":
        opts = [("Drive the work party hard", "hard", (240, 180, 110), True),
                ("Let the weak fall out", "soft", (200, 220, 170), True),
                ("Sign off the sick for the ramp", "select", (230, 160, 150), True)]
        lines = [("Arbeitskommando forms up. The kapo waits for your word.", (200, 195, 170)),
                 (f"Prisoners: {c['prisoners']}. Dead: {c['dead']}.", (170, 170, 150))]
        title = "The camp"
    else:
        opts = [("Work party out to the road", "work", (220, 210, 160), True),
                ("Keep them in: an inspection", "inspect", (200, 200, 220), True),
                ("Open the Red Cross parcels", "parcels", (200, 230, 190), True)]
        lines = [("Stalag routine. The wire is quiet; the men watch you.", (200, 195, 170))]
        title = "Prison camp"
    ps.open_popup(Popup(title, opts, ps._screen_anchor(), width=66, lines=lines),
                  lambda v: resolve(game, v), cancel=lambda: None)


def resolve(game, v):
    c = game.__dict__.get("camp")
    from .sustain import stores
    s = stores(game.sector, game.player.side)
    if v == "hard":
        c["labour"] += 6
        s["materials"] = s.get("materials", 0) + 4
        if game.rng.random() < 0.45:
            c["dead"] += 1
            from . import atrocities
            atrocities.camp_death(game)
        _say(game, "The party shifts earth until dark. One man is carried back.", "info")
        game.duty.rep += 0.2
    elif v == "soft":
        c["labour"] += 3
        _say(game, "You let the weak fall out. The kapo mutters; the men notice.", "good")
        game.player.morale = min(100, game.player.morale + 2)
    elif v == "select":
        c["dead"] += 1
        from . import atrocities
        atrocities.camp_selection(game, "the ramp")
        _say(game, "A lorry takes the sick away. Nobody is sure to where.", "info")
    elif v == "work":
        c["labour"] += 4
        s["materials"] = s.get("materials", 0) + 2
        _say(game, "The party works the road. Two men slip out of the gate and are counted back at dusk.", "info")
    elif v == "inspect":
        _say(game, "You walk the huts. The men stand at their bunks and stare past you.", "info")
    elif v == "parcels":
        s["food"] = s.get("food", 0) + 3
        _say(game, "Parcels opened. The smell of coffee and tobacco crosses the compound.", "good")
    game.__dict__.get("camp", {})["next"] = game.turn + 240


def person_act(game, a):
    """Prisoners mill about inside the wire; guards keep their post.  Neither fights."""
    c = game.__dict__.get("camp")
    if c is None:
        return 100
    if a.ai.get("camp_guard"):
        post = a.ai.get("camp_post")
        if post is None:
            x0, y0, w, h = c["rect"]
            a.ai["camp_post"] = post = (x0 + 2 if a.id % 2 else x0 + w - 2, y0 + 2 + (a.id % (h - 4)))
        if max(abs(a.x - post[0]), abs(a.y - post[1])) > 1:
            from .ai import path_step
            return path_step(game, a, post[0], post[1]) or 100
        return 100
    if a.ai.get("camp_prisoner"):
        if game.turn % 11 == a.id % 11:
            x0, y0, w, h = c["rect"]
            from .ai import path_step
            tx = x0 + 3 + (a.id * 7 + game.turn) % max(1, w - 6)
            ty = y0 + 3 + (a.id * 3) % max(1, h - 6)
            return path_step(game, a, tx, ty) or 100
        return 100
    return 100


def tick(game):
    c = game.__dict__.get("camp")
    if c is None or not game.__dict__.get("_play"):
        return
    if game.turn < c.get("next", 0):
        return
    if game.turn % 60:
        return
    if game.turn % 300 == 0:
        roll_call(game)
    event(game)
    c["next"] = game.turn + 240
