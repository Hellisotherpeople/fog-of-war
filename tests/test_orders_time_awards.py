"""Regressions for authority, shared simulation time, and persistent illustrated citations.

    python tests/test_orders_time_awards.py
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from test_smoke import FakeApp, Game  # isolated saves and dummy SDL, before importing the interface
import tcod
import tcod.event as E

from fow import orders
from fow.ai import Order
from fow.play import PlayState, Key
from fow.constants import SCREEN_W, SCREEN_H


def scene(scenario="front", realtime=False):
    g = Game("bocage44", "usa", seed=5, role="rifleman",
             setup={"battlefield": "standard", "scenario": scenario})
    app = FakeApp()
    app.settings.update(autosave=False, fast_quiet=False, realtime=realtime, realtime_pace="normal")
    ps = PlayState(app, g)
    app.states = [ps]
    return g, ps, app


def superior(g, rank=3):
    from fow.spawn import make_soldier
    a = make_soldier(g, g.player.nation, "rifleman")
    a.rank = rank
    a.x, a.y = g.player.x + 1, g.player.y
    g.actors.append(a)
    return a


def test_briefing_governs_arrow_enter_and_stale_focus():
    g, ps, app = scene("raid")
    g.player.squad.order = Order("attack", target=(2, 2), issued=10)
    g.duty.give(g, "come", superior(g), (2, 2))
    t = g.duty.task
    g.order_focus = f"duty:{t['uid']}"  # an old saved selection must not bypass authority
    b = orders.book(g)
    assert b[0]["key"] == "mission" and b[0]["governing"]
    assert orders.active(g)["key"] == "mission"
    assert not orders.focus(g, f"duty:{t['uid']}")
    rec = g.mission["rec"]["rect"]
    target = (rec[0] + rec[2] // 2, rec[1] + rec[3] // 2)
    assert g.order_pointer()[:2] == target
    with patch.object(ps, "start_travel") as travel:
        ps.cmd_do_order()
        assert travel.call_args.args[:2] == target
    g.update_orders(force=True)
    assert g.mission["text"] in g.player_orders


def test_deferred_duties_pause_without_punishment_and_resume():
    g, _, _ = scene("raid")
    recipient = superior(g)
    recipient.x += 20
    g.duty.give(g, "runner", superior(g), recipient.id)
    task = g.duty.task
    original = task["deadline"] - g.turn
    rep, strikes = g.duty.rep, g.duty.strikes
    for _ in range(3):
        g.turn += original + 10
        g.duty._check_task(g, task)
    assert task in g.duty._tasks() and task["deadline"] - g.turn == original
    assert (g.duty.rep, g.duty.strikes) == (rep, strikes) and not task["nagged"]
    g.mission["stage"] = "done"
    recipient.body.dead = True
    assert not orders.deferred(g, f"duty:{task['uid']}")
    g.duty._check_task(g, task)
    assert task not in g.duty._tasks()  # the now missing recipient cancels it without a strike
    assert g.duty.strikes == strikes


def test_new_equal_authority_can_redirect_but_older_or_lower_cannot():
    g, _, _ = scene("patrol")
    sup = superior(g, 10)
    g.duty.give(g, "scout", sup, (12, 12), leg="out")  # same instant as briefing: no replacement
    assert orders.governing(g)["key"] == "mission"
    g.duty.task = None
    g.turn += 5
    g.duty.give(g, "scout", sup, (12, 12), leg="out")
    task = g.duty.task
    sup.rank = 0  # issuer's later demotion does not rewrite an already received order
    assert orders.governing(g)["key"] == f"duty:{task['uid']}"
    g.turn += 1
    g.duty.give(g, "come", superior(g, 3), (2, 2))
    assert orders.active(g)["key"] == f"duty:{task['uid']}"
    assert orders.deferred(g, "mission")
    g.duty._drop(task)
    assert orders.governing(g)["key"] == "mission"


def test_local_orders_support_the_mission_and_lose_focus_when_it_changes():
    g, _, _ = scene("assault")
    sq = g.player.squad
    sq.player_led = False
    sq.leader = superior(g)
    sq.order = Order("attack", obj=0)
    g.map.objectives[0].owner = "axis"
    assert orders.focus(g, "squad")
    assert orders.governing(g)["key"] == "mission" and orders.active(g)["key"] == "squad"
    sq.order = Order("retreat", target=(2, 2), issued=50)
    assert orders.active(g)["key"] == "mission" and orders.deferred(g, "squad")


def test_mission_stages_route_home_without_randomness_or_desertion():
    g, ps, _ = scene("patrol")
    assert g.order_pointer() is None  # observing the enemy has no invented attack objective
    assert "no single destination" in ps.order_hint()
    g.mission.update(stage="return", text="Return with the report.")
    sq = g.player.squad
    sq.player_led = False
    sq.leader = superior(g)
    sq.order = Order("attack", obj=0)
    state = g.rng.getstate()
    targets = [g.order_pointer() for _ in range(6)]
    assert all(t == targets[0] for t in targets) and state == g.rng.getstate()
    edge = g.mission["home"]
    assert orders.authorized_departure(g, edge)
    with patch.object(g, "travel", return_value=True) as travel:
        ps.prompt_travel(edge)
        travel.assert_called_once_with(edge)
    assert g.stats["desertions"] == 0


def test_hq_recall_is_explicit_and_requires_sufficient_authority():
    g, _, _ = scene("rearguard")
    g.turn += 301
    assert not orders.recall(g, 10, "company", "The line has collapsed.")
    assert g.mission["stage"] == "hold"
    assert orders.recall(g, 12, "battalion", "The line has collapsed.")
    assert g.mission["stage"] == "cancelled" and orders.governing(g)["key"] == "field"
    assert "collapsed" in orders.governing(g)["reason"]
    assert orders.authorized_departure(g, g.field_order["edge"])


def test_orders_screen_explains_the_deferred_order():
    from fow.ui import OrdersState
    g, ps, app = scene("raid")
    g.duty.give(g, "come", superior(g), (2, 2))
    ui = OrdersState(app, ps)
    ui.sel = next(i for i, o in enumerate(ui.orders) if o["key"].startswith("duty:"))
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    ui.render(con)
    text = "\n".join("".join(map(chr, row)) for row in con.ch.T)
    assert "Deferred" in text and "priority" in text and "paused" in text


def test_enter_walk_stops_when_the_mission_changes():
    g, ps, _ = scene("raid")
    p = g.player
    g.mission["rec"]["rect"] = (p.x + 6, p.y, 2, 2)
    for x in range(p.x, p.x + 10):
        g.map.set(x, p.y, "grass")
        g.map.set(x, p.y + 1, "grass")
    g.map.refresh()
    ps.cmd_do_order()
    assert ps.travel_path and ps._following_order is not None
    before = p.pos
    g.mission.update(stage="exfil", text="The target is gone. Get back to our lines.")
    ps._travel_step(100.)
    assert not ps.travel_path and p.pos == before
    assert "current instruction" in list(g.messages)[-1].text


def test_scout_return_arrow_and_enter_both_point_to_the_issuer():
    g, ps, _ = scene()
    sup = superior(g)
    sup.x += 8
    g.duty.give(g, "scout", sup, (g.player.x + 15, g.player.y), leg="back")
    assert g.order_pointer()[:2] == sup.pos
    assert "Report back" in orders.active(g)["text"]
    with patch.object(ps, "start_travel") as travel:
        ps.cmd_do_order()
        assert travel.call_args.args[:2] == sup.pos


def test_realtime_runs_idle_but_action_spam_cannot_buy_extra_moves():
    g, ps, app = scene(realtime=True)
    p = g.player
    p.moves = 100
    start = g.turn
    ps.act(200)
    assert g.turn == start and p.moves == -100
    debt, position = p.moves, p.pos
    for _ in range(10):
        ps.on_key(Key(char="h"))
        ps.on_key(Key(char="."))
        ps.on_click(4, 4, 1)
    assert p.pos == position and p.moves == debt and g.turn == start
    ps._rt_last = 100.
    assert not ps._realtime_tick(100.5)
    assert ps._realtime_tick(101.)
    assert g.turn == start + 1 and p.moves > debt
    for tick in range(102, 108):
        ps._realtime_tick(float(tick))
    assert g.turn == start + 7
    assert 0 < p.moves <= max(100, p.speed())  # no stockpile of idle action points
    assert not ps._fast_quiet()


def test_realtime_pauses_menus_focus_and_does_not_catch_up():
    g, ps, app = scene(realtime=True)
    start = g.turn
    ps._rt_last = 100.
    app.states.append(object())
    assert not ps._realtime_tick(103.)
    app.states.pop()
    assert not ps._realtime_tick(103.01)
    app.focused = False
    assert not ps._realtime_tick(110.)
    app.focused = True
    assert not ps._realtime_tick(110.01)
    assert not ps._realtime_tick(1000.)  # suspended process/window: no catch-up damage
    assert g.turn == start
    assert ps._realtime_tick(1001.) and g.turn == start + 1


def test_realtime_wait_and_turn_based_mode_still_charge_time():
    g, ps, app = scene(realtime=True)
    g.player.moves = 100
    ps.act(200)
    start = g.turn
    ps.cmd_realtime()
    assert not app.settings["realtime"] and g.turn > start and g.player.moves > 0
    start = g.turn
    ps.act(200)
    assert g.turn > start
    ps.cmd_realtime()
    start = g.turn
    ps.begin_wait("event", 3)
    with patch.object(ps, "_wait_stop", return_value=None):
        for _ in range(10):
            ps._wait_tick()
            if not ps.auto_wait:
                break
    assert g.turn >= start + 3


def test_realtime_is_independent_of_effect_animation():
    g, ps, _ = scene(realtime=True)
    ps.anim = 4
    ps.anim_next = 10**20
    ps._rt_last = 100.
    with patch("fow.play.time.monotonic", return_value=101.):
        start = g.turn
        ps.tick()
        assert g.turn == start + 1


def test_air_and_naval_realtime_advance_one_second_and_charge_existing_costs():
    from fow.skyseaui import SkySeaState
    for service, role, scenario in (("air", "fighter_pilot", "air:sweep"),
                                    ("navy", "ship_captain", "sea:surface")):
        g = Game("guadalcanal42", "usa", role=role, seed=4,
                 setup=dict(battlefield="standard", service=service, scenario=scenario))
        app = FakeApp()
        app.settings.update(realtime=True, realtime_pace="normal", autosave=False)
        ps = PlayState(app, g)
        ui = SkySeaState(app, g, ps)
        ui.aboard = g.__dict__.get("domain") == "aboard"
        app.states = [ps, ui]
        ss = g.skysea
        ss.station = "pilot" if service == "air" else "bridge"
        start = ss.t
        ui._rt_last = 100.
        assert ui._realtime_tick(101.) and ss.t == start + 1
        ui.on_key(Key(sym=E.KeySym.RIGHT))
        assert ui._rt_action_until == ss.t + (1 if service == "air" else 10)
        unit = ss.player_plane or ss.player_ship
        direction = unit.hdg if service == "air" else unit.order_hdg
        ui.on_key(Key(sym=E.KeySym.RIGHT))
        assert (unit.hdg if service == "air" else unit.order_hdg) == direction
        until = ui._rt_action_until
        ui.on_key(Key(sym=E.KeySym.F6))
        assert not app.settings["realtime"] and ss.t == until


def test_citations_survive_battle_reset_saves_and_second_awards():
    from fow.awards import records
    g, _, _ = scene()
    cmd = g.command
    from fow.recognition import state
    state(g)["credited"] = 8  # witness reports already accepted by headquarters
    cmd.battle.update(kills=5, objectives=1, wounds=2)
    name = cmd._battle_awards(g, posthumous=True)
    entry = records(cmd, g.player.nation)[0]
    assert name == entry["name"] and entry["posthumous"]
    assert "5 enemies defeated" in entry["evidence"] and "2 wounds" in entry["evidence"]
    assert not cmd.battle["kills"] and g.sector.name in entry["why"]
    cmd._award(g, entry["level"], "for rescuing the patrol")
    assert records(cmd, g.player.nation)[-1]["repeat"]
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "save.pkl")
        g.save(path)
        loaded = Game.load(path)
        assert records(loaded.command, loaded.player.nation) == records(cmd, g.player.nation)


def test_post_screen_illustrates_all_awards_and_legacy_citations_are_honest():
    from fow import icons
    from fow.awards import records, icon_key
    from fow.data.ranks import MEDALS
    from fow.ui import GameOverState
    g, _, app = scene()
    for level in range(5):
        g.command._award(g, level, "for completing the operation", posthumous=level == 4)
    for nation, names in MEDALS.items():
        for level in range(len(names)):
            graphic = icons.paint(f"award|{nation}|{level}|1", 96, 120)
            assert graphic is not None and graphic[..., 3].max() > 0
    ui = GameOverState(app, g)
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    ui.render(con)
    assert "CITATIONS" in "".join(map(chr, con.ch.T.flatten()))
    ui.on_key(Key(sym=E.KeySym.RIGHT))
    assert ui.award_page == 1
    ui.render(con)
    assert "POSTHUMOUS" in "".join(map(chr, con.ch.T.flatten()))
    del g.command.award_records
    entries = records(g.command, g.player.nation)
    assert len(entries) == 5 and all("unavailable" in e["why"] for e in entries)
    assert icons.paint(icon_key(entries[0]), 96, 120) is not None


if __name__ == "__main__":
    tests = [fn for name, fn in list(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests:
        test()
        print("ok   ", test.__name__, flush=True)
    print(f"{len(tests)} tests passed", flush=True)
