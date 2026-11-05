"""Difficulty, run codes and runs, storeys, queues, events, packs, reports, advanced settings."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_big_"))
os.environ["FOW_DEBUG"] = "1"

from test_smoke import Game  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import difficulty, floors, orders, packs, reportcard, runcode, runs  # noqa: E402
from fow.ai import Order  # noqa: E402


def _stalingrad(seed=90):
    return Game("stalingrad42", "ussr", "rifleman", seed=seed, setup={"battlefield": "standard"})


def test_difficulty_scales_the_enemy_and_your_bleeding():
    g = Game("bocage44", "usa", "rifleman", seed=91, setup={"difficulty": "realistic"})
    q = difficulty.get(g, "enemy_skill")
    p = g.player
    assert q > 1.0 and p.body.__dict__["_diff_bleed"] > 1.0
    from fow.spawn import make_soldier
    enemy = make_soldier(g, "germany", "rifleman")
    assert enemy.side != p.side
    g2 = Game("bocage44", "usa", "rifleman", seed=91, setup={"difficulty": "recruit"})
    e2 = make_soldier(g2, "germany", "rifleman")
    assert difficulty.get(g2, "enemy_skill") < 1.0


def test_a_run_code_round_trips():
    code = runcode.make(12345, "bocage44", "usa", "rifleman", dict(scenario="front", difficulty="veteran"))
    d = runcode.parse(code)
    assert d["seed"] == 12345 and d["theatre"] == "bocage44" and d["nation"] == "usa"
    assert runcode.parse(code.lower()) == d
    bad = code.replace("FOW-", "FOW-2", 1)
    assert runcode.parse(bad) is None
    assert runcode.parse("FOW-NOPE") is None


def test_runs_index_and_latest(tmp_path):
    from fow import game as G
    old = G.SAVE_DIR
    try:
        G.SAVE_DIR = str(tmp_path)
        runs.SAVE_DIR = str(tmp_path)
        runs.INDEX = os.path.join(str(tmp_path), "runs.json")
        g = Game("bocage44", "usa", "rifleman", seed=92)
        g.run_id = runs.new_id()
        path = g.save()
        assert os.path.exists(path)
        runs.note(g.run_id, g, name="Test Run")
        assert runs.latest_alive() == g.run_id
        g2 = G.Game.load(path)
        assert g2.player is not None
        runs.forget(g.run_id)
        assert runs.latest_alive() is None
    finally:
        G.SAVE_DIR = old
        runs.SAVE_DIR = old
        runs.INDEX = os.path.join(old, "runs.json")


def test_storeys_are_separate_and_a_hole_drops_you():
    g = _stalingrad()
    m = g.map
    b = next(b for b in m.buildings if m.storeys.get(tuple(b[:4]), 1) >= 3)
    rect = b[:4]
    arr = floors.plan(m, rect, 1)
    assert arr is not None
    assert any(int(v) for row in arr for v in row)
    p = g.player
    g.pop_actor_at(p, 0)
    p.z = 1
    spot = floors._upper_spot(g, rect, 1, g.rng)
    p.x, p.y = spot
    g.set_actor_at(p)
    floors.hole(g, p.x, p.y, 1)
    floors.fall(g, p)
    assert p.z == 0 and g.actor_at(p.x, p.y, 0) is p
    assert (p.x, p.y, 1) not in g.soldier_at_z


def test_queued_orders_are_kept_and_honoured():
    g = Game("bocage44", "usa", "squad_leader", seed=93)
    sq = g.player.squad
    sq.player_led = True
    orders.queue_order(sq, "move", (sq.leader.x + 5, sq.leader.y))
    assert sq.rep["queue"]
    sq.last_contact = -999
    assert orders.next_queued(g, sq)
    assert sq.order.kind == "move" and not sq.rep["queue"]


def test_promotion_need_is_cheap_at_the_bottom_and_credit_moves_it():
    g = Game("bocage44", "usa", "rifleman", seed=94)
    from fow.data import ranks as R
    assert g.command.promotion_need(R.PRIVATE) <= 5
    s = __import__("fow.recognition", fromlist=["state"]).state(g)
    s["credited"] = 100.0
    from fow import career
    career.consider(g)
    assert s.get("pending") is not None


def test_fieldworks_scrape_and_loophole():
    g = Game("bocage44", "usa", "rifleman", seed=95)
    p = g.player
    from fow.entities import Item
    if p.add_item(Item("shovel")) is None:
        bp = Item("backpack")
        p.invent.slots["pack"] = bp
        bp.where = "pack"
        assert p.add_item(Item("shovel")) is not None
    c = __import__("fow.actions", fromlist=["dig"]).dig(g, p, "scrape")
    if c is None:                     # (not every tile is diggable: find one that is, in reach)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            from fow import actions as A
            if A.move(g, p, dx, dy):
                c = A.dig(g, p, "scrape")
                if c is not None:
                    break
    assert c is not None


def test_pack_items_missions_and_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(packs, "SHIPPED", tmp_path)
    monkeypatch.setattr(packs, "USER", tmp_path)
    import json
    (tmp_path / "q.json").write_text(json.dumps({
        "name": "Q",
        "items": {"pack_pistol": {"name": "Pack pistol", "kind": "gun", "cal": "9mm", "mag": 8, "dmg": 22}},
        "missions": {"pack_mission": {"name": "Pack mission", "w": 1, "desc": "A test."}},
        "roles": {"pack_role": {"name": "Pack role", "desc": "A test role."}},
    }), encoding="utf-8")
    errs = packs.load_all(force=True)
    assert not errs
    from fow.data.items import ITEMS
    from fow.scenarios import SCENARIOS
    from fow.data.roles import ROLES
    assert ITEMS["pack_pistol"].name == "Pack pistol"
    assert "pack_mission" in SCENARIOS and "pack_role" in ROLES
    ITEMS.pop("pack_pistol")
    SCENARIOS.pop("pack_mission")
    ROLES.pop("pack_role")


def test_report_card_lines_and_export(tmp_path, monkeypatch):
    import fow.reportcard as rc
    monkeypatch.setattr(rc, "REPORTS", str(tmp_path))
    g = Game("bocage44", "usa", "rifleman", seed=96)
    assert any("Time on the ground" in t for t, _ in reportcard.lines(g))
    from fow import marks as MK
    g.map.explored[:] = True
    MK.place(g, g.player.x + 1, g.player.y, "danger")
    assert any("Pencilled on the map" in t for t, _ in reportcard.lines(g))
    path = reportcard.export(g)
    assert path and os.path.exists(path)


def test_unlocked_settings_expose_advanced_rows():
    from types import SimpleNamespace
    from fow.ui import OptionsState
    app = SimpleNamespace(settings={"unlocked": False, "difficulty": "veteran"}, show_numbers=False,
                          audio=None, gfx=None)
    st = OptionsState(app)
    keys = [it[1] for it in st.items]
    assert "unlocked" in keys and "god_mode" not in keys
    app.settings["unlocked"] = True
    st._build()
    keys = [it[1] for it in st.items]
    assert "god_mode" in keys and "reality_radius" in keys
