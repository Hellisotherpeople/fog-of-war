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


if __name__ == "__main__":
    test_every_item_has_a_valid_drawing()
    test_look_it_over_shows_the_drawing_first()
    print("ok")
