"""Quality is read off the gun, and captured maps are worth something.

    python -m pytest tests/test_quality_and_maps.py
"""
from __future__ import annotations

import os
import sys

from test_smoke import Game, FakeApp  # noqa: F401  (isolated saves and headless SDL first)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import quality  # noqa: E402
from fow import tasks  # noqa: E402
from fow.ai import switch_weapon  # noqa: E402
from fow.data.items import ITEMS  # noqa: E402
from fow.entities import Item  # noqa: E402
from fow.intelligence import study  # noqa: E402
from fow.play import PlayState  # noqa: E402


def test_quality_orders_the_arsenal_sensibly():
    assert quality.tier(ITEMS["mg42"]) > quality.tier(ITEMS["m1903"])
    assert quality.tier(ITEMS["m1903"]) > quality.tier(ITEMS["m1911"])
    assert quality.better(ITEMS["mg42"], ITEMS["m1903"]) == 1
    assert quality.better(ITEMS["m1903"], ITEMS["mg42"]) == -1
    assert quality.better(ITEMS["m1911"], ITEMS["m1911"]) == 0
    assert "Exceptional" in quality.words(ITEMS["mg42"]) or "Fine" in quality.words(ITEMS["mg42"])
    assert quality.words(ITEMS["m1_garand"]).endswith(".")


def test_ai_takes_the_better_gun():
    g = Game("bocage44", "usa", seed=2, setup={"battlefield": "standard", "seamless": False})
    a = next(a for a in g.actors if a.side == g.player.side and not a.is_player and a.weapon is not None)
    a.add_item(Item("m1903"))
    for i in (x for x in list(a.inv) if x.t.kind == "gun"):
        i.loaded = i.t.mag
    switch_weapon(g, a)
    assert a.weapon.tid == "m1903"                  # better than his issue SMG
    assert tasks._wanted("weapons", Item("m1903"), a) is False    # already has one
    assert tasks._wanted("weapons", Item("m1911"), a) is False    # worse
    assert tasks._wanted("weapons", Item("mg42"), a) is True      # much better, and loaded
    a.weapon = None
    assert tasks._wanted("weapons", Item("m1911"), a) is True


def test_captured_map_marks_their_defences():
    g = Game("bocage44", "usa", seed=3, setup={"battlefield": "standard", "seamless": False})
    p = g.player
    enemy = "axis"
    it = Item("marked_map")
    it.data = {"side": enemy, "unit": "a German company", "written": g.turn, "positions": []}
    rec = next((r for r in g.map.gen_positions if r.get("side") == enemy), None)
    if rec is not None:
        it.data["positions"] = [(9991, rec["x"], rec["y"])]
    learned = study(g, p, it)
    assert learned and any("defence" in w or "positions" in w for w in learned)
    assert p.ai["map_intel"], "the defensive layout should leave pencil notes on the map"
    assert it.data.get("studied") == g.turn
    assert learned == study(g, p, it) or "already" in study(g, p, it)[0]


def test_captured_map_is_a_map_and_shows_in_the_look_box():
    from fow import icons
    it = Item("marked_map")
    assert it.t.tool == "map"
    assert icons.item_key(Item("m1_garand"))
    ps = PlayState(FakeApp(), Game("bocage44", "usa", seed=4, setup={"battlefield": "standard",
                                                                    "seamless": False}))
    it = Item("m1_garand")
    lines = ps.examine_lines(it)
    assert any("carry" in l[0].lower() or "Serviceable" in l[0] or "Well made" in l[0] for l in lines)
    assert not any(l[0].startswith("  ") and len(l[0]) > 40 for l in lines)  # no ASCII art rows
