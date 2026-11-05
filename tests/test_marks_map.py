"""Grease-pencil marks and the battlefield map sheet: what is written, where it comes back, and who reads it."""
from __future__ import annotations

import os
import tempfile

import tcod
import tcod.event as E

from test_smoke import FakeApp
from fow import marks as MK
from fow.constants import SCREEN_H, SCREEN_W
from fow.game import Game
from fow.play import Key, PlayState
from fow.mapui import MapState


def make():
    g = Game("bocage44", "usa", role="squad_leader", seed=2, setup={"battlefield": "standard"})
    g.map.explored[:] = True
    return g


def text_of(state):
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    state.render(con)
    return "\n".join("".join(chr(c) for c in con.ch[:, y]) for y in range(SCREEN_H))


def test_marks_round_trip_and_are_capped():
    g = make()
    p = g.player
    MK.place(g, p.x + 2, p.y, "danger", p)
    found = MK.at(g, p.x + 2, p.y)
    assert found and found[0]["kind"] == "danger"
    assert MK.clear_at(g, p.x + 2, p.y) == 1
    assert not MK.at(g, p.x + 2, p.y)
    for i in range(MK.MAX + 12):
        MK.place(g, (p.x + i * 7) % g.map.w, (p.y + i * 11) % g.map.h, "cover", p)
    assert len(g.map_marks) <= MK.MAX
    assert len(g.map_marks) > MK.MAX - 6


def test_same_kind_nearby_is_one_mark():
    g = make()
    p = g.player
    MK.place(g, p.x, p.y, "rally", p)
    MK.place(g, p.x + 1, p.y, "rally", p)
    assert len(g.map_marks) == 1
    assert MK.at(g, p.x + 1, p.y)


def test_unexplored_ground_cannot_be_marked():
    g = make()
    p = g.player
    g.map.explored[:] = False
    assert MK.place(g, p.x, p.y, "danger", p) is None


def test_marks_survive_save_and_load():
    g = make()
    p = g.player
    MK.place(g, p.x + 3, p.y, "casualty", p)
    d = tempfile.mkdtemp(prefix="fow_marks_")
    path = os.path.join(d, "s.pkl")
    g.save(path)
    g2 = Game.load(path)
    assert MK.at(g2, p.x + 3, p.y)
    assert MK.nearest(g2, p.x, p.y, "casualty", 20) is not None


def test_map_screen_marks_and_clears_and_walks():
    g = make()
    app = FakeApp()
    ps = PlayState(app, g)
    app.push(ps)
    ps.cmd_map()
    st = app.states[-1]
    assert isinstance(st, MapState)
    assert "BATTLEFIELD MAP" in text_of(st)
    st.on_key(Key(char="2"))
    assert any(m["kind"] == "rally" for m in g.map_marks)
    st.on_key(Key(char="0"))
    assert not g.map_marks
    st.on_key(Key(char="1"))
    before = (st.cx, st.cy)
    st.on_key(Key(sym=E.KeySym.RIGHT))
    assert (st.cx, st.cy) != before
    before_states = len(app.states)
    st.on_key(Key(char="f"))
    assert len(app.states) < before_states or "radio" in st.note
    if app.states and app.states[-1] is st:
        st.on_key(Key(sym=E.KeySym.ESCAPE))
    assert app.states == [ps]


def test_enemy_seen_is_remembered_then_fades():
    from types import SimpleNamespace
    g = make()
    p = g.player
    enemy = SimpleNamespace(id=99999, side="germany", alive=True, vehicle=None, role_name="rifleman",
                            x=p.x + 6, y=p.y)
    p.visible = [enemy]
    MK.remember_enemies(g)
    assert MK.sightings(g)
    g.turn += MK.REMEMBER + 1
    assert not MK.sightings(g)


def test_rally_order_writes_a_marker_and_sets_the_order():
    g = make()
    app = FakeApp()
    ps = PlayState(app, g)
    app.push(ps)
    p = g.player
    sq = p.squad
    assert sq is not None
    ps._order_rally((p.x + 6, p.y))
    assert sq.order.kind == "rally" and sq.order.target == (p.x + 6, p.y)
    assert any(m["kind"] == "rally" for m in g.map_marks)


def test_order_menu_offers_the_nearest_rally_marker():
    g = make()
    app = FakeApp()
    ps = PlayState(app, g)
    app.push(ps)
    p = g.player
    sq = p.squad
    MK.place(g, p.x - 8, p.y, "rally", p)
    ps.cmd_orders()
    vals = [o[1] for o in ps.popups[-1].options]
    assert ("rally_at", (p.x - 8, p.y)) in vals
    ps._order(("rally_at", (p.x - 8, p.y)))
    assert sq.order.kind == "rally" and sq.order.target == (p.x - 8, p.y)


def test_rally_order_puts_the_section_into_retreat():
    from fow import ai
    g = make()
    app = FakeApp()
    ps = PlayState(app, g)
    app.push(ps)
    p = g.player
    sq = p.squad
    ps._order_rally((p.x - 12, p.y))
    sq.arrived = False
    ai.squad_update(g, sq)
    assert sq.state in ("retreat", "hold")


def test_rally_bounds_by_halves():
    from fow import ai
    from fow.ai import Order
    g = make()
    app = FakeApp()
    ps = PlayState(app, g)
    app.push(ps)
    p = g.player
    sq = p.squad
    sq.order = Order("rally", target=(p.x - 10, p.y), issued=g.turn)
    act = [a for a in sq.members if a.active and a is not p]
    assert len(act) >= 2
    one = act[0]
    two = next(a for a in act if a.id % 2 != one.id % 2)
    one_pos, two_pos = (one.x, one.y), (two.x, two.y)
    ai.retreat_act(g, one, [])
    ai.retreat_act(g, two, [])
    # one team moves on the first bound, the other holds as overwatch
    assert (one.x, one.y) != one_pos
    assert (two.x, two.y) == two_pos


def test_run_through_rally_places_men_on_the_mark():
    from fow import ai
    g = make()
    p = g.player
    sq = p.squad
    mk = MK.place(g, p.x - 12, p.y, "rally", p)
    sq.state = "retreat"
    sq.order.kind = "hold"
    ai.rally(g, sq)
    assert sq.__dict__.get("rally", {}).get("at") is not None
    x, y = sq.rally["at"]
    assert max(abs(x - (p.x - 12)), abs(y - p.y)) <= 1
