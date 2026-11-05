"""The enemy commander's mind, section memory, the diary, trade orders and the rear."""
from __future__ import annotations

import os
import sys
import tempfile
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_home_"))
os.environ["FOW_DEBUG"] = "1"

from test_smoke import Game, FakeApp  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import bonds, diary, jobs, opponent, rear_cycle, trade, vdamage  # noqa: E402
from fow import tiles as T  # noqa: E402
from fow.entities import Item  # noqa: E402
from fow.play import PlayState  # noqa: E402


def _quiet(g):
    for a in list(g.actors):
        if a.side != g.player.side and a.alive:
            a.body.dead = True
            g.kill(a, None)
    g.seen_enemies = lambda within=35: False


def test_commander_school_and_a_probe():
    g = Game("bocage44", "germany", "rifleman", seed=31, setup={"battlefield": "standard"})
    st = opponent.state(g, g.player.side)
    assert 0 <= st["push"] <= 1 and st["word"]
    assert 1.0 <= opponent.counter_need(g, g.player.side) <= 1.6
    from fow.ai import Order
    sq = next(q for q in g.squads if q.side == g.player.side and q.members and not q.player_led)
    sq.order = Order("hold", target=sq.anchor(), radius=4, issued=g.turn)
    sq.last_contact = g.turn - 500
    g.turn += 1000
    opponent.probe(g, g.player.side, [sq])
    assert sq.rep.get("probe") and sq.order.kind in ("move", "hold", "defend")
    first = st["probes"]
    opponent.probe(g, g.player.side, [sq])
    assert st["probes"] == first                      # cooldown


def test_a_section_remembers_and_a_replacement_is_green():
    g = Game("bocage44", "usa", "rifleman", seed=32, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    sq = p.squad
    dead = next(m for m in sq.members if m is not p and m.alive)
    bonds.remember(g, sq, dead)
    assert sq.rep["memory"]["lost"] and sq.rep["memory"]["graves"]
    from fow.spawn import make_soldier
    a = make_soldier(g, p.nation, "rifleman")
    before = a.skill
    bonds.new_man(g, a, sq)
    assert a.ai.get("new_to_section") and a.skill < before
    bonds.settle(g, a)
    assert a.ai.get("new_to_section") is None and a.id not in sq.rep["memory"]["new"]


def test_replacements_join_the_squad():
    g = Game("bocage44", "usa", "rifleman", seed=33, setup={"battlefield": "standard"})
    _quiet(g)
    sq = g.player.squad
    n0 = len(sq.members)
    n = bonds.replacements(g, sq, 2)
    assert n >= 1 and len(sq.members) > n0


def test_diary_records_and_copies_out():
    g = Game("bocage44", "usa", "rifleman", seed=34, setup={"battlefield": "standard"})
    diary.start(g)
    diary.entry(g, "note", "A quiet hour. Someone is singing.")
    diary.photo(g, "for the book")
    assert any(e["kind"] == "photo" for e in g.__dict__["diary"])
    path = diary.export(g)
    assert path and os.path.exists(path)
    assert "quiet hour" in open(path, encoding="utf-8").read()


def test_camera_takes_a_photo():
    g = Game("bocage44", "usa", "rifleman", seed=35, setup={"battlefield": "standard"})
    _quiet(g)
    fa = FakeApp()
    ps = PlayState(fa, g)
    cam = Item("camera")
    g.player.add_item(cam)
    before = len(g.__dict__.get("diary", []))
    ps._personal_use(cam)
    assert len(g.__dict__.get("diary", [])) == before + 1
    assert cam.uses == cam.t.uses - 1


def _aid(g, p):
    g.map.gen_positions.append(dict(kind="aid", side=p.side, x=p.x + 10, y=p.y,
                                    rect=(p.x + 8, p.y - 2, 4, 5)))


def test_a_medic_is_sent_to_carry_a_stable_casualty():
    g = Game("bocage44", "usa", "medic", seed=36, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    _aid(g, p)
    hurt = next(a for a in g.actors if a.side == p.side and a is not p and a.alive and a.vehicle is None)
    hurt.body.damage(g.rng, "l_leg", 10, "cut")
    hurt.body.hp["l_leg"] = 0
    hurt.body.wounds[0].bleed = 0.1
    hurt.x, hurt.y = p.x + 2, p.y
    td = trade.find(g, "medic", p.squad.leader)
    assert td and td[0] == "evac" and td[1] == hurt.id


def test_the_sergeant_gives_the_medics_trade_as_an_order():
    g = Game("bocage44", "usa", "medic", seed=44, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    _aid(g, p)
    hurt = next(a for a in g.actors if a.side == p.side and a is not p and a.alive and a.vehicle is None)
    hurt.body.damage(g.rng, "l_leg", 10, "cut")
    hurt.body.hp["l_leg"] = 0
    hurt.body.wounds[0].bleed = 0.1
    hurt.x, hurt.y = p.x + 2, p.y
    sup = p.squad.leader
    td = trade.find(g, "medic", sup)
    assert td and td[0] == "evac"
    g.duty.give(g, td[0], sup, td[1], **td[2])
    assert g.duty.task and g.duty.task["kind"] == "evac"


def test_an_engineer_is_sent_to_the_wire():
    g = Game("bocage44", "usa", "engineer", seed=37, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    p.invent.slots["pack"] = Item("backpack")
    assert p.invent.add(Item("wirecutters"), prefer="pack")
    g.map.t[p.x + 2, p.y] = T.ID["wire"]
    td = trade.find(g, "engineer", p.squad.leader)
    assert td and td[0] == "wire"
    g.map.t[p.x + 2, p.y] = T.ID["grass"]
    g.map.t[p.x + 1, p.y] = T.ID["grass"]
    assert trade.check(g, dict(kind="wire", target=(p.x + 2, p.y), issued=g.turn, by=1))


def test_a_fitter_is_sent_to_a_broken_vehicle():
    g = Game("bocage44", "usa", "motor_sergeant", seed=38, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    v = next(v for v in g.vehicles if v.side == p.side and not v.dead)
    v.parts["tracks"] = vdamage.OUT
    g.lift_vehicle(v)
    v.x, v.y = p.x + 4, p.y
    g.place_vehicle(v)
    td = trade.find(g, "motor_sergeant", p.squad.leader if p.squad else None)
    assert td and td[0] == "recover" and td[2].get("vid") == v.id


def test_trade_credit_is_kept():
    g = Game("bocage44", "usa", "medic", seed=39, setup={"battlefield": "standard"})
    m0 = g.command.merit
    trade.credit(g, "evac")
    assert g.command.merit > m0 and trade.summary(g)


def test_the_kitchen_feeds_the_line():
    g = Game("bocage44", "usa", "rifleman", seed=40, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    cook = next((a for a in g.actors if a.side == p.side and a.role == "cook"), None)
    if cook is None:
        from fow.spawn import make_soldier, place
        cook = make_soldier(g, p.nation, "cook")
        cook.side = p.side
        place(g, cook, p.x + 1, p.y, 1)
    g.map.gen_positions.append(dict(kind="depot", side=p.side, x=cook.x, y=cook.y,
                                    rect=(cook.x - 2, cook.y - 2, 5, 5)))
    p.ai["needs"] = dict(hunger=90., thirst=90., infection=0.)
    g.sector = g.sector_for(p)
    from fow.sustain import stores
    stores(g.sector, p.side)["food"] = 10
    rear_cycle.feed(g)
    assert p.ai["needs"]["hunger"] < 90 and p.ai["needs"]["thirst"] < 90


def test_a_fought_out_section_is_relieved():
    from fow.ai import Order
    g = Game("bocage44", "usa", "rifleman", seed=41, setup={"battlefield": "standard"})
    _quiet(g)
    p = g.player
    fought = next(q for q in g.squads if q.side == p.side and q.members and not q.player_led)
    fresh = next(q for q in g.squads if q.side == p.side and q.members and q is not fought and not q.player_led)
    fought.order = Order("defend", target=fought.anchor(), radius=4, issued=g.turn)
    fresh.order = Order("hold", target=fresh.anchor(), radius=4, issued=g.turn)
    fought.last_contact = g.turn - 1200
    fought.initial = 12
    for m in fought.members[2:]:
        m.body.dead = True
        g.kill(m, None)
    fresh.last_contact = g.turn - 500
    fresh.morale = 80
    fresh.initial = 12
    fresh_x, fresh_y = fresh.anchor()
    g.lift_vehicle  # no-op
    # bring the fresh section close
    for m in fresh.members:
        m.x, m.y = fought.anchor()[0] + 4, fought.anchor()[1]
    rear_cycle.rotate(g)
    assert fought.rep.get("relieved") and fresh.rep.get("relieved")


def test_drill_lane_lays_out_the_trade_kit():
    from fow.drill import Drill
    g = Game("bocage44", "usa", "engineer", seed=42, setup={"battlefield": "standard"})
    d = Drill(g, "role", (g.player.x + 4, g.player.y))
    stages = d.__dict__["role_stage"]
    assert stages
    play = types.SimpleNamespace(game=g)
    n = next(iter(stages))
    d._stage(play, n)
    assert g.player.has_tool("wirecutters") or g.player.find(lambda i: i.t.kind == "explosive")


def test_autopilot_narration_says_why():
    g = Game("bocage44", "usa", "medic", seed=43, setup={"battlefield": "standard"})
    g.__dict__["_prefs"] = {"autopilot_narrate": True}
    jobs.card(g, "triage", "Going to a casualty", (1, 1))
    assert " - he " in list(g.messages)[-1].text
