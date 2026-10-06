"""Information, labor and authority must physically support the result."""
from __future__ import annotations

import pickle
from collections import Counter
from copy import deepcopy
from unittest.mock import patch

from test_smoke import Game, FakeApp
from fow.ai import Squad, Order
from fow.entities import Item, Vehicle
from fow.spawn import make_soldier
from fow import fieldworks as W, intelligence as I, recognition as R, intent, service
from fow.sustain import stores
from fow.command import Formation
from fow.play import PlayState


def scene():
    g = Game("bocage44", "usa", role="regiment_commander", seed=25,
             setup={"battlefield": "standard"})
    g.turn = 1000
    p = g.player
    p.x, p.y, p.rank = 10, 10, 13
    p.vehicle = None
    p.fired_turn = -9999
    g.actors, g.vehicles, g.squads = [p], [], []
    g.soldier_at, g.vehicle_at = {p.pos: p}, {}
    g._arr_turn = -1
    g.map.fill(1, 1, 65, 55, "grass")
    g.map.refresh()
    g.map.gen_positions = []
    g.sector.installations = []
    g.map.mines.clear()
    g.map.works = []
    g.command.billet = None
    g.command.billet_squad = None
    g.command.personnel = dict(claims=[], credited=0., spent=0., last_promotion=0,
                               pending=None, awards=[], last_review=g.turn)
    g.command.attached.clear()
    g.command.pending.clear()
    g.mission, g.field_order = None, None
    for b in g.brains.values():
        b.contacts.clear()
    player_sq = Squad(p.side, p.nation, "hq", "Command group")
    player_sq.members, player_sq.leader, player_sq.player_led = [p], p, True
    p.squad = player_sq
    g.squads.append(player_sq)
    g.command.billet_squad = player_sq
    return g


def soldier(g, x=14, y=10, nation="usa", role="engineer", rank=3):
    a = make_soldier(g, nation, role)
    a.x, a.y, a.rank = x, y, rank
    a.fired_turn, a.moved_turn = -9999, -9999
    g.actors.append(a)
    g.soldier_at[a.pos] = a
    g._arr_turn = -1
    sq = Squad(a.side, nation, "engineer" if role == "engineer" else "rifle")
    sq.members, sq.leader, a.squad = [a], a, sq
    sq.initial = 1
    sq.morale = 80
    sq.order = Order("hold", target=a.pos)
    g.squads.append(sq)
    return a


def radio(a):
    a.invent.slots["pack"] = Item("backpack")
    item = Item("radio")
    assert a.add_item(item) is not None
    return item


def unradio(a):
    for i in list(a.inv):
        if i.t.tool in ("radio", "handradio"):
            a.remove_item(i)


def move(g, a, pos):
    g.soldier_at.pop(a.pos, None)
    a.x, a.y = pos
    g.soldier_at[a.pos] = a
    g._arr_turn = -1


def test_500_unwitnessed_kills_teach_skill_but_never_promote():
    g = scene()
    p = g.player
    p.rank = 2
    enemy = make_soldier(g, "germany", "rifleman")
    enemy.x, enemy.y = 16, 10
    before = p.skills["marksmanship"]
    for _ in range(500):
        g.command.on_kill(g, enemy)
    g.turn += 86400 * 10
    assert not g.command.consider_promotion(g)
    assert p.rank == 2 and p.skills["marksmanship"] > before
    assert R.state(g)["credited"] == 0 and not R.state(g)["claims"]


def test_witness_must_get_report_out_and_dead_witness_loses_unsent_evidence():
    g = scene()
    witness = soldier(g, 22, 10, role="rifleman")
    unradio(g.player)
    unradio(witness)
    assert R.claim(g, "kills", 1, "observed action", (20, 10))
    R.process(g)
    claim = R.state(g)["claims"][0]
    assert claim["reported"] is None
    radio(witness)
    R.process(g)
    assert claim["reported"] == g.turn and not R.state(g)["credited"]
    witness.body.dead = True
    g.turn = claim["due"]
    R.process(g)
    assert R.state(g)["credited"] == 1  # the statement had already been transmitted
    witness.body.dead = False
    unradio(witness)
    R.claim(g, "kills", 2, "later action", (20, 10))
    witness.body.dead = True
    g.turn += 3600
    R.process(g)
    assert R.state(g)["credited"] == 1


def test_promotion_requires_vacancy_service_review_and_delivery():
    g = scene()
    p = g.player
    p.rank = 2
    ledger = R.state(g)
    ledger["credited"] = 100
    radio(p)
    assert not R.consider(g) and ledger["pending"] is None
    g.turn = 86400
    assert not R.consider(g) and ledger["pending"]
    unradio(p)
    g.turn += 3600
    assert not R.consider(g) and p.rank == 2
    radio(p)
    assert R.consider(g) and p.rank == 3
    ledger["credited"] += 1000
    g.turn += 86400 * 30
    assert not R.consider(g)  # no higher billet is vacant


def test_order_delivery_rechecks_rank_and_working_radio():
    g = scene()
    a = soldier(g, 45, 30)
    radio(g.player)
    set_ = radio(a)
    payload = dict(mission="seize", freedom="bounded", risk="normal", target=(25, 25))
    sent, _ = g.command.issue(g, [a.squad], "mission", payload, say=False,
                            forced_channel=dict(kind="radio", delay=10))
    assert sent and "intent" not in a.squad.rep
    set_.condition = 0
    g.turn += 10
    g.command.update(g)
    assert "intent" not in a.squad.rep
    set_.condition = 1
    sent, _ = g.command.issue(g, [a.squad], "mission", payload, say=False,
                            forced_channel=dict(kind="radio", delay=10))
    g.command.pending[-1].pop("garbled", None)
    a.rank = g.player.rank
    g.turn += 10
    g.command.update(g)
    assert "intent" not in a.squad.rep


def test_appointments_and_reassignment_change_real_chain_without_changing_rank():
    g = scene()
    a, b = soldier(g), soldier(g, 18, 10, rank=8)
    f = Formation(900, a.side, a.nation, "platoon", "Test platoon")
    f.squads, f.commander = [a.squad], a
    a.squad.formation = f
    root = g.command.bases[g.player.side]
    f.parent = root
    root.children.append(f)
    assert intent.administer(g, a.squad, "appointment", dict(actor=b.id, formation=f.id))
    assert f.commander is b and b.rank == 8 and f.acting
    assert intent.administer(g, b.squad, "reassign", dict(formation=f.id))
    assert b.squad in f.squads and b.squad.formation is f
    b.rank = g.player.rank
    assert not intent.administer(g, a.squad, "appointment", dict(actor=b.id, formation=f.id))


def test_standing_mission_consolidates_and_stops_at_loss_limit():
    g = scene()
    a = soldier(g)
    payload = dict(mission="seize", freedom="bounded", risk="normal", target=a.pos)
    assert intent.administer(g, a.squad, "mission", payload)
    with patch('fow.intent.low_on_ammo', return_value=False):
        intent.update(g, a.squad)
        assert a.squad.order.kind == "dig" and a.squad.rep["intent"]["completed"]
        a.squad.rep["intent"]["strength"] = 10
        g.turn += 15
        intent.update(g, a.squad)
        assert a.squad.order.kind == "defend" and a.squad.rep["intent"]["halted"]
    g.command.deliver(g, a.squad, dict(kind="hold", order=Order("hold"), channel="voice"), quiet=True)
    assert "intent" not in a.squad.rep


def test_reports_are_delayed_frozen_and_symmetric():
    for nation, enemy in (("usa", "germany"), ("germany", "usa")):
        g = scene()
        a = soldier(g, 20, 20, nation=nation, role="radioman")
        b = soldier(g, 30, 20, nation=enemy)
        radio(a)
        I.observe(g, a, b)
        assert b.id not in g.brains[a.side].contacts
        old = b.pos
        move(g, b, (40, 20))
        g.turn += 15
        I.tick(g)
        c = g.brains[a.side].contacts[b.id]
        assert (c.x, c.y) == old and c.turn == g.turn - 15
        unradio(a)
        g.turn += 20
        I.observe(g, a, b)
        assert (c.x, c.y) == old


def test_carried_map_stays_stale_until_hq_copy_and_survives_save():
    g = scene()
    s = g.sector
    before = deepcopy(I.map_report(g, s))
    assert before
    s.control = "axis"
    s.units["axis"]["tank"] += 40
    g.turn += 600
    view = I.map_sector(g, s)
    assert view.control == before["control"] and view.units == before["units"]
    latest = deepcopy(before)
    latest["control"], latest["turn"] = "axis", g.turn
    g.strategic.situation_reports[g.player.side][(s.x, s.y)] = latest
    from fow.ui import OvermapState
    OvermapState(FakeApp(), g)
    assert I.map_report(g, s)["control"] == before["control"]
    g.map.gen_positions = [dict(kind="hq", side=g.player.side, x=10, y=10)]
    OvermapState(FakeApp(), g)
    assert I.map_report(g, s)["control"] == "axis"
    loaded = pickle.loads(pickle.dumps(g))
    assert I.map_report(loaded, loaded.sector) == latest


def test_engineers_collect_real_materials_then_work_and_survive_save():
    g = scene()
    a = soldier(g, 20, 20)
    g.map.gen_positions = [dict(kind="depot", side=a.side, x=20, y=20)]
    st = stores(g.sector, a.side)
    st["materials"] = 2
    ok, reason = W.assign(g, a.squad, "sandbags", (26, 20))
    assert ok, reason
    W.act(g, a, [])
    p = W.projects(g)[0]
    assert st["materials"] == 0 and p["materials"] == 0 and a.ai["works_cargo"]["amount"] == 2
    move(g, a, (25, 20))
    W.act(g, a, [])
    assert p["materials"] == 2 and p["work"] == 0
    a.suppression = 50
    assert W.act(g, a, []) is None and p["work"] == 0
    a.suppression = 0
    g = pickle.loads(pickle.dumps(g))
    a = next(a for a in g.actors if a.role == "engineer")
    for _ in range(300):
        W.act(g, a, [])
        g.turn += 10
    assert W.projects(g)[0]["status"] == "complete"
    assert g.map.tile(26, 20).key == "sandbags" and g.map.cover_dir[:, 25, 20].max() > 0


def test_missing_engineers_missing_stores_and_dead_carriers_do_not_build():
    g = scene()
    a = soldier(g, 20, 20, role="rifleman")
    assert not W.assign(g, a.squad, "hq", (30, 20))[0]
    a.role = "engineer"
    a.add_item(Item("shovel"))
    assert not W.assign(g, a.squad, "hq", (30, 20))[0]
    g.map.gen_positions = [dict(kind="depot", side=a.side, x=20, y=20)]
    stores(g.sector, a.side)["materials"] = 0
    assert W.assign(g, a.squad, "sandbags", (30, 20))[0]
    W.act(g, a, [])
    assert W.projects(g)[0]["work"] == 0
    stores(g.sector, a.side)["materials"] = 2
    W.act(g, a, [])
    a.body.dead = True
    W.tick(g)
    assert W.projects(g)[0]["carried"] == 0 and W.projects(g)[0]["materials"] == 0


def test_completed_headquarters_works_until_destroyed():
    g = scene()
    a = soldier(g, 29, 20)
    g.map.gen_positions = [dict(kind="depot", side=a.side, x=20, y=20)]
    assert W.assign(g, a.squad, "hq", (30, 20))[0]
    project = W.projects(g)[0]
    project["materials"] = 12
    project["work"] = W.WORKS["hq"][2] - 1
    W.act(g, a, [])
    assert project["status"] == "complete"
    move(g, g.player, (30, 22))
    assert I.headquarters(g)
    g.map.set(30, 20, "rubble", refresh=True)
    W.tick(g)
    assert not I.headquarters(g)
    assert not any(i[0] == "hq" and i[2] for i in g.sector.installations if i[1] == a.side and i[0] == "hq")


def test_counterbattery_needs_observer_and_keeps_old_coordinates():
    from fow.fire_observation import locate, delivered
    from types import SimpleNamespace
    g = scene()
    gun = Vehicle("t34_76", "allies", "usa", 30, 20)
    gun.ai["battery"] = 999
    g.vehicles.append(gun)
    battery = SimpleNamespace(id=999, side="allies", kind="gun", pos=gun.pos, squad_id=None)
    assert locate(g, battery, dict(fired=20)) is None
    observer = soldier(g, 40, 20, nation="germany", role="radioman")
    radio(observer)
    observer.visible, observer.vis_turn = [gun], g.turn
    report = locate(g, battery, dict(fired=6))
    assert report and report["due"] >= g.turn + 90
    gun.x += 10
    assert report["x"] == 30 and delivered(g, report)
    unradio(observer)
    assert not delivered(g, report)
    assert not delivered(g, (g.turn, "axis", 30, 20))


def test_sound_ranging_needs_two_staffed_posts_and_repeated_fire():
    from fow.fire_observation import locate
    from types import SimpleNamespace
    g = scene()
    battery = SimpleNamespace(id=999, side="allies", kind="gun", pos=(40, 25), squad_id=None)
    a = soldier(g, 10, 30, nation="germany", role="radioman")
    b = soldier(g, 35, 30, nation="germany", role="radioman")
    radio(a); radio(b)
    g.map.gen_positions = [dict(kind="observation", side="axis", x=a.x, y=a.y)]
    assert locate(g, battery, dict(fired=20)) is None
    g.map.gen_positions.append(dict(kind="observation", side="axis", x=b.x, y=b.y))
    assert locate(g, battery, dict(fired=1)) is None
    report = locate(g, battery, dict(fired=8))
    assert report["due"] >= g.turn + 600 and len(report["observers"]) == 2


def test_radio_repairs_need_nearby_fitter_spares_and_work_hull_needs_workshop():
    from fow import maintenance as M, vdamage
    g = scene()
    v = Vehicle("t34_76", "allies", "usa", 30, 20)
    v.parts["radio"] = vdamage.OUT
    v.ai["maint"] = {"radio": M.JOBS["radio"][1]}
    v.hp -= 10
    hp = v.hp
    g.vehicles = [v]
    M._repair(g, v)
    assert v.parts["radio"] == 0
    truck = Vehicle("gmc", "allies", "usa", 32, 20)
    truck.ai.update(fitters=True, parts_cargo=0)
    g.vehicles.append(truck)
    M._repair(g, v)
    assert v.parts["radio"] == 0
    truck.ai["parts_cargo"] = 1
    M._repair(g, v)
    assert v.parts["radio"] == 2 and truck.ai["parts_cargo"] == 0 and v.hp == hp
    g.map.gen_positions = [dict(kind="motor_pool", side=v.side, x=v.x, y=v.y, rect=(25, 15, 10, 10))]
    M._repair(g, v)
    assert v.hp > hp


def test_service_ticket_routes_and_conference_delivers_new_orders():
    g = scene()
    g.map.gen_positions = [dict(kind="hq", side=g.player.side, x=12, y=12)]
    g.player.ai["service_order"] = dict(kind="conference", issued=g.turn, authority=15,
                                       who="General Test", how="radio", text="Report to headquarters.")
    app = FakeApp()
    ps = PlayState(app, g)
    app.states = [ps]
    from fow.orders import active, navigation
    assert active(g)["key"] == "service" and navigation(g)[:2] == (12, 12)
    with patch.object(ps, 'act'):
        service.conference(ps)
    assert "service_order" not in g.player.ai
    assert any(a.rank == 15 for a in g.actors)
    assert g.field_order["authority"] == 15


def test_command_popups_and_both_map_views_render():
    import tcod
    from fow.constants import SCREEN_W, SCREEN_H
    from fow.cmdui import unit_menu
    from fow.command_work_ui import guidance, appointment, construction, staff
    from fow.ui import OvermapState
    g = scene()
    a = soldier(g)
    app = FakeApp()
    ps = PlayState(app, g)
    app.states = [ps]
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    for fn in (guidance, appointment, construction):
        ps.popups.clear()
        fn(ps, [a.squad])
        ps.render(con)
        assert ps.popups
    ps.popups.clear()
    unit_menu(ps, [a.squad], "Engineers")
    ps.render(con)
    staff(ps)
    ps.render(con)
    sheet = OvermapState(app, g)
    sheet.render(con)
    sheet.compact = True
    sheet.render(con)


def test_staff_party_moves_into_contact_without_spawning_or_overriding_orders():
    g = scene()
    a = soldier(g, 20, 10, role="radioman", rank=8)
    a.squad.kind = "hq"
    a.squad.last_contact = -999
    before = len(g.actors)
    intent.staff_support(g)
    assert a.squad.order.src == "staff" and a.squad.order.target == g.player.pos
    assert len(g.actors) == before
    a.squad.order = Order("hold", target=(20, 10), src="player")
    intent.staff_support(g)
    assert a.squad.order.target == (20, 10) and a.squad.order.src == "player"


def test_general_staff_cannot_transmit_without_a_radio_or_hq():
    g = scene()
    unradio(g.player)
    key = (g.sector.x, g.sector.y)
    g.ops.divs = {1: dict(name="Test regiment", sectors={key}, order="hold", target=None, status="holding")}
    g.command.strategic_orders.clear()
    note = g.ops.order(g, 1, "hold")
    assert "radio" in note and not g.command.strategic_orders
    radio(g.player)
    g.ops.order(g, 1, "hold")
    assert len(g.command.strategic_orders) == 1


def test_cancelling_works_restores_order_and_exhausted_workers_rest():
    g = scene()
    a = soldier(g, 26, 20)
    a.squad.last_contact = -999
    prior = a.squad.order
    assert W.assign(g, a.squad, "foxhole", (27, 20))[0]
    p = W.projects(g)[-1]
    a.stamina = 0
    assert W.act(g, a, []) == 1000 and p["work"] == 0
    assert a.stamina > 0
    W.cancel(g, a.squad)
    assert p["status"] == "cancelled" and a.squad.order is prior
