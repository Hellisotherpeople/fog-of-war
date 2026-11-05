"""High-contrast rendering: lift the text, crush the ground.

Applied to the finished console like the colour-blind pass, so it covers every panel, menu and diagram
without each of them knowing about it.  Backgrounds go near-black, text toward white - useful in sunlight,
on a bad panel, or for low vision.
"""
from __future__ import annotations

import numpy as np


def apply(con) -> None:
    fg = con.rgb["fg"]
    bg = con.rgb["bg"]
    f = fg.astype(np.float32)
    g = f.mean(axis=2, keepdims=True)
    f = f * 0.20 + 255 * 0.80 * np.sqrt(g / 255.0)
    con.rgb["fg"][:] = np.clip(f, 0, 255).astype(np.uint8)
    con.rgb["bg"][:] = (bg.astype(np.float32) * 0.25).astype(np.uint8)
