"""Warming up in the background: spend RAM at start so the game doesn't spend time later.

Everything expensive here is deterministic - sprite atlases at the sizes the zoom can reach, fonts,
the fixed phrase tables - so building it before the player needs it costs time once, on an idle
thread, and saves a hitch every time the view zooms or a menu paints.

Two levels: "startup" warms the sizes a normal game actually uses; "everything" fills the whole zoom
range and every painted picture it can name, which can take hundreds of megabytes.  The player asked
for the choice; off is still the default on a small machine.
"""
from __future__ import annotations

import threading

_bank = None
_done = threading.Event()
_lock = threading.Lock()


def cached_bank():
    from .sprites import SpriteBank
    global _bank
    with _lock:
        if _bank is None:
            _bank = SpriteBank()
    return _bank


def ready():
    return _done.is_set()


def start(settings):
    mode = settings.get("preload", "off")
    if mode not in ("startup", "everything"):
        return None
    th = threading.Thread(target=_warm, args=(mode,), name="fow-preload", daemon=True)
    th.start()
    return th


def _warm(mode):
    try:
        import numpy as np                       # noqa: F401  (the bank and painters need it)
        from . import fonts, sprites
        from .data.nations import NATIONS
        from .data.phrases import all_lines
        bank = cached_bank()
        sizes = (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 32) if mode == "everything" \
            else (10, 12, 14, 18, 22)
        for s in sizes:
            try:
                bank.build(s)
            except Exception:
                pass
        for cw, ch in ((8, 16), (10, 20), (12, 24), (14, 28)):
            try:
                fonts.make_tileset("ttf", cw, ch)
            except Exception:
                break
        for n in NATIONS:
            try:
                all_lines(n)
            except Exception:
                pass
        if mode == "everything":
            _pictures(fonts)
    finally:
        _done.set()


def _pictures(fonts):
    """Paint every picture the interface can name, at a size big enough to be scaled down sensibly."""
    from . import icons
    keys = []
    from .data.items import ITEMS
    for key in ITEMS:
        keys.append(f"item:{key}")
    keys += ["unit:rifle|1", "unit:mg|1", "unit:tank|1", "doll|head:1:torso:1:l_arm:1:r_arm:1:l_leg:1:r_leg:1"]
    for k in keys:
        try:
            icons.paint(k, 32, 32)
        except Exception:
            pass
