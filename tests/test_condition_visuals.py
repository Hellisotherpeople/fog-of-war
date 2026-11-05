"""Condition shows in the picture, and a blast does not turn good kit to scrap."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import equipment, icons  # noqa: E402
from fow.entities import Item  # noqa: E402


def test_item_picture_changes_with_condition():
    icons.ENABLED = True
    it = Item("m1_garand")
    it.condition = 1.0
    pristine = icons.paint(icons.item_key(it), 80, 30).copy()
    it.condition = 0.4
    key = icons.item_key(it)
    assert "#" in key and key.startswith("gun:")
    worn = icons.paint(key, 80, 30)
    assert worn.shape == pristine.shape
    assert (worn != pristine).any()


def test_orientation_keeps_the_wear_mark():
    icons.ENABLED = True
    it = Item("m1_garand")
    it.condition = 0.4
    key = icons.item_key(it)
    turned = icons.oriented(key, 4, 2)
    assert turned.endswith("#" + key.rsplit("#", 1)[1])
    assert icons.paint(turned, 20, 40) is not None


def test_sound_kit_survives_a_close_blast():
    class G:
        class rng:
            @staticmethod
            def random():
                return 0.5
    for tid, power in (("m1_garand", 300), ("bandage", 120), ("helmet_m1", 120)):
        it = Item(tid)
        equipment.damage(G(), it, power * 0.65, 0, 0)
        assert it.condition > 0.4 and it.functional, tid
