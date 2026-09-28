"""Lore: the longer story of each item, shown when you examine it (play.examine).

The entries live in lore_guns.py (weapons), lore_kit.py (grenades, charges, blades, medical supplies) and
lore_gear.py (radios, helmets, webbing, a soldier's things).  Items without an entry show their description.
"""
from __future__ import annotations

from importlib import import_module

LORE: dict[str, str] = {}
for _m in ("lore_guns", "lore_kit", "lore_gear"):
    try:
        LORE.update(import_module(f"{__package__}.{_m}").LORE)
    except ImportError:
        pass
