"""Every item has a drawing for the look-it-over box, and every drawing fits it.

    python tests/test_item_art.py
"""
from __future__ import annotations

import os
import sys

from test_smoke import Game  # noqa: F401  (isolated saves and headless SDL before the game is imported)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import check_art  # noqa: E402


def test_every_item_has_a_valid_drawing():
    assert check_art.main([]) == 0


def test_look_it_over_shows_the_drawing_first():
    from fow.data.items import ITEMS
    from fow.itemart import load
    from test_smoke import FakeApp
    from fow.play import PlayState
    from fow.entities import Item
    g = Game("bocage44", "usa", seed=1, setup={"battlefield": "standard", "seamless": False})
    ps = PlayState(FakeApp(), g)
    for tid in ("m1_garand", "zippo", "stahlhelm"):
        lines = ps.examine_lines(Item(tid))
        art = load()[tid]
        assert [l.strip() for l, _ in lines[:len(art)]] == [r.strip() for r in art]
        assert ITEMS[tid].desc.split()[0] in lines[len(art) + 1][0]


def test_a_look_at_the_world_shows_the_thing_itself():
    """Looking at a tile (x, hover) draws what's there: the gun a man holds, the kit on the ground."""
    from test_smoke import FakeApp
    from fow.play import PlayState
    from fow.entities import Item
    from fow.itemart import load
    g = Game("bocage44", "usa", seed=1, setup={"battlefield": "standard", "seamless": False})
    ps = PlayState(FakeApp(), g)
    p = g.player
    m = g.map
    # the rifle in his hands: looking at yourself shows your own weapon
    w = p.weapon
    if w is not None:
        art = ps._look_art(p.x, p.y, True, 0)
        assert art and art[0][0].strip() in [r.strip() for r in load()[w.t.id]]
    # a rifle lying in the grass
    m.add_item(p.x + 1, p.y, Item("m1_garand"))
    art = ps._look_art(p.x + 1, p.y, True, 1)
    assert art, "a rifle on the ground should draw"
    assert art[0][0].strip() in [r.strip() for r in load()["m1_garand"]]
    # a dead man's slung gun shows, dimmed, when you look at the body
    from fow.entities import make_corpse
    victims = [a for a in g.actors if a is not p and a.weapon is not None]
    if not victims:               # give someone a rifle so the body has one to sling
        from fow.ai import Soldier
        v = g.actors[1]
        v.weapon = Item("m1_garand")
        v.invent.hands = v.weapon
        victims = [v]
    body = make_corpse(victims[0])
    m.add_item(p.x - 1, p.y, body)
    art = ps._look_art(p.x - 1, p.y, True, 1)
    assert art, "a body with a slung rifle should draw its rifle"


if __name__ == "__main__":
    test_every_item_has_a_valid_drawing()
    test_look_it_over_shows_the_drawing_first()
    test_a_look_at_the_world_shows_the_thing_itself()
    print("ok")
