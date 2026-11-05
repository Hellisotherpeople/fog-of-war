"""Autopilot is the trade, not just the rifle: medics go to the wounded, fitters go to the broken tank."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_home_"))
os.environ["FOW_DEBUG"] = "1"

from test_smoke import Game  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import jobs, maintenance, succession, vdamage  # noqa: E402
from fow.entities import Item  # noqa: E402


def _quiet(g):
    for a in list(g.actors):
        if a.side != g.player.side and a.alive:
            a.body.dead = True
            g.kill(a, None)
    g.support.next_sortie = {k: 10 ** 9 for k in g.support.next_sortie}
    g.seen_enemies = lambda within=35: False


def test_medic_goes_to_the_wounded_and_puts_the_job_on_the_card():
    g = Game("bocage44", "usa", "medic", seed=3, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    for _ in range(6):
        p.add_item(Item("bandage"))
    hurt = next(a for a in g.actors if a.side == p.side and a is not p and a.alive and a.vehicle is None)
    hurt.body.damage(g.rng, "l_leg", 22)
    hurt.body.hp["l_leg"] = 0
    from fow.spawn import place
    place(g, hurt, p.x + 6, p.y, 1)
    d0 = max(abs(hurt.x - p.x), abs(hurt.y - p.y))
    succession.set_autopilot(g, True)
    for _ in range(400):
        g.world_turn()
        if p.carrying is not None or max(abs(hurt.x - p.x), abs(hurt.y - p.y)) <= 2:
            break
    card = g.__dict__.get("player_job") or {}
    d1 = max(abs(hurt.x - p.x), abs(hurt.y - p.y)) if p.carrying is None else 0
    assert card.get("kind") in ("triage", "treat", "evac", "sweep"), card
    assert d1 < d0 or p.carrying is hurt
    for _ in range(60):
        g.world_turn()
        if p.carrying is hurt:
            break
    assert p.carrying is hurt or (g.__dict__.get("player_job") or {}).get("kind") == "evac"
    assert hurt.body.bleed_rate() < 1.0                  # (the wound is dressed)


def test_damaged_tank_drives_to_the_motor_pool_and_stops():
    g = Game("bocage44", "usa", "rifleman", seed=4, setup={"battlefield": "standard"})
    v = next(v for v in g.vehicles if v.side == g.player.side and not v.dead and v.vt.vtype == "tank")
    v.ai.pop("to_repair", None)
    v.player_crewed = False
    v.parts["gun"] = vdamage.OUT
    pool = (min(g.map.w - 3, v.x + 30), min(g.map.h - 3, v.y + 2))
    g.map.gen_positions.append(dict(kind="motor_pool", side=v.side, x=pool[0], y=pool[1],
                                    rect=(pool[0] - 3, pool[1] - 3, 7, 7)))
    maintenance._seek_repair(g, v)
    assert v.ai.get("to_repair") == pool
    assert v.squad.order.kind == "move" and v.squad.order.target == pool
    v.x, v.y = pool
    maintenance._seek_repair(g, v)
    assert v.squad.order.kind == "hold"


def test_motor_sergeant_walks_to_the_broken_track():
    g = Game("bocage44", "usa", "motor_sergeant", seed=5, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    v = next(v for v in g.vehicles if v.side == p.side and not v.dead)
    v.parts["tracks"] = vdamage.OUT
    g.lift_vehicle(v)
    v.x, v.y = p.x + 5, p.y
    g.place_vehicle(v)
    c = jobs._fitter(g, p, ())
    assert c
    assert (g.__dict__.get("player_job") or {}).get("kind") == "fix"


def test_job_card_never_runs_past_the_panel():
    import tcod
    from fow.constants import SCREEN_H, SCREEN_W, VIEW_W
    from fow.render import draw_panel
    g = Game("bocage44", "usa", "medic", seed=7, setup={"battlefield": "standard"})
    g.__dict__["autopilot"] = True
    jobs.card(g, "triage", "Carrying a badly wounded man of the platoon's second section back to the "
                           "battalion aid post through the orchard")
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    draw_panel(con, g)
    for row in range(SCREEN_H):
        assert chr(con.ch[SCREEN_W - 1, row]) == " ", row
        assert chr(con.ch[VIEW_W, row]) in " │", row


def test_autopilot_eats_drinks_and_rests():
    g = Game("bocage44", "usa", "rifleman", seed=8, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    p.add_item(Item("ration"))
    p.add_item(Item("canteen"))
    p.ai["needs"] = dict(hunger=90., thirst=90., infection=0.)
    c = jobs._survival(g, p, [], 999)
    assert c and g.__dict__["player_job"]["kind"] == "drink"
    c = jobs._survival(g, p, [], 999)
    assert c and g.__dict__["player_job"]["kind"] == "eat"
    g.is_night = lambda: False
    g.map.pos_cover[p.x, p.y] = 0
    for i in list(p.inv):
        if i.t.tool == "blanket":
            p.remove_item(i)
    p.fatigue = 95
    f0 = p.fatigue
    c = jobs._survival(g, p, [], 999)
    assert c and g.__dict__["player_job"]["kind"] == "rest" and p.fatigue < f0


def test_autopilot_tops_up_from_a_stack():
    from fow import tiles as T
    g = Game("bocage44", "usa", "rifleman", seed=9, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    w = p.weapon
    for i in p.inv:
        if i.t.kind in ("mag", "ammo", "clip"):
            i.loaded = 0
            i.count = 0
    g.sector = g.sector_for(p)
    g.map.t[p.x + 1, p.y] = T.ID["ammo_stack"]
    c = jobs._survival(g, p, [], 999)
    assert c and (g.__dict__.get("player_job") or {}).get("kind") == "ammo"


def test_autopilot_reports_for_orders_when_idle():
    g = Game("bocage44", "usa", "rifleman", seed=10, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    g.player_orders = None
    g.duty.tasks.clear()
    succession.set_autopilot(g, True)
    sup = p.squad.leader
    sup.rank = max(sup.rank, p.rank + 3)
    c = jobs.act(g, p, [], p.squad, "hold", 999)
    card = g.__dict__.get("player_job") or {}
    assert card.get("kind") in ("report", "march", "fight", "orders")
    assert c or card.get("kind")


def test_taking_back_control_clears_the_card():
    g = Game("bocage44", "usa", "medic", seed=6, setup={"battlefield": "standard"})
    succession.set_autopilot(g, True)
    jobs.card(g, "triage", "Going to a casualty")
    succession.set_autopilot(g, False)
    assert g.__dict__.get("player_job") is None
