"""More of the war: the added arms, SS formations, historical sites, tableaux and the drill.

    python -m pytest tests/test_content_expansion.py
"""
from __future__ import annotations

import os
import sys

from test_smoke import Game, FakeApp  # noqa: F401  (isolated saves and headless SDL first)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import icons  # noqa: E402
from fow.data.items import ITEMS  # noqa: E402
from fow.data.notable import NOTABLE  # noqa: E402
from fow.play import PlayState  # noqa: E402


def test_late_war_arms_exist_and_draw():
    for tid in ("avt40", "dt29", "mp41r", "stg45", "type2_smg", "mas40", "f4u" if "f4u" in ITEMS else "m1917_enfield"):
        assert tid in ITEMS
        from fow.entities import Item
        assert icons.item_key(Item(tid))


def test_ss_formations_are_their_own_service():
    for k in ("de_lssah", "de_hj", "de_dasreich", "de_char"):
        assert NOTABLE[k]["service"] == "ss"
    g = Game("bocage44", "germany", "rifleman", seed=1,
             setup={"battlefield": "standard", "scenario": "front", "service": "army", "unit": "notable:de_hj"})
    assert g.player.service == "ss"
    assert "Hitlerjugend" in g.player.unit


def test_historical_sites_and_tableaux_build():
    from fow import landmarks, tableaux
    from fow.data.history import SITES
    from fow.mapgen import Gen
    gen = Gen(dict(seed=4, w=90, h=70, biome="farmland", climate="summer", theatre="bocage44", lang="fr"))
    site = SITES["bocage44"][0]
    assert landmarks.historical(gen, site)
    assert any(r.get("kind") == "history" and r.get("note") for r in gen.positions)
    assert any(name == site["name"] for name, *_ in gen.poi)
    from fow import tiles as T
    assert any(m == T.ID["marker"] for m in gen.m.t.ravel())
    gen2 = Gen(dict(seed=5, w=90, h=70, biome="factory", climate="summer", theatre="kursk43", lang="ru"))
    tableaux.place(gen2)
    assert gen2.poi or gen2.m.__dict__.get("parked")


def test_drill_runs_its_lessons():
    from fow.entities import Item
    g = Game("bocage44", "usa", "rifleman", seed=7,
             setup={"battlefield": "standard", "scenario": "drill", "drill": "basic", "service": "army"})
    ps = PlayState(FakeApp(), g)
    p, d = g.player, g.drill
    assert len([a for a in g.actors if a.ai.get("drill_target")]) == 3
    p.x, p.y = d.marker
    d.update(ps)
    ps.mode = "look"
    d.update(ps)
    p.stance = 1
    d.update(ps)
    p.weapon = Item("m1_garand")
    d.update(ps)
    g.stats["drill_shots"] = 3
    d.update(ps)
    g.stats["drill_reloads"] = 1
    d.update(ps)
    assert p.body.wounds
    g.stats["drill_bandages"] = 1
    d.update(ps)
    ps.inv_screen = object()
    d.update(ps)
    ps.inv_screen = None
    g.drill_map = True
    d.update(ps)
    g.stats["drill_shots"] = 8
    d.update(ps)
    assert d.done and ps.popups


def test_drill_role_trial_has_its_own_lesson():
    g = Game("bocage44", "usa", "medic", seed=8,
             setup={"battlefield": "standard", "scenario": "drill", "drill": "role", "service": "army"})
    assert any("instructor" in text for text, _ in g.drill.steps)
