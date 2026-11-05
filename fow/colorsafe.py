"""A colour-blind-safe pass over the interface text.

Green and red carry a lot of meaning here - compatible ammunition, wound states, the going, unit
status.  This shifts the two hues that collide most toward blue and amber, keeping the same light and
dark so the panel still reads.  It is a post-pass, so it changes what is drawn and nothing in the
simulation.
"""
from __future__ import annotations

import numpy as np


def apply(con):
    try:
        fg = con.fg
    except AttributeError:
        return
    if fg is None:
        return
    a = np.array(fg, copy=True)
    if a.ndim < 3 or a.shape[2] < 3:
        return
    r = a[:, :, 0].astype(np.int16)
    g = a[:, :, 1].astype(np.int16)
    b = a[:, :, 2].astype(np.int16)
    green = (g > r + 8) & (g > b + 8)
    red = (r > g + 20) & (r > b + 20)
    # green -> a strong blue, keeping brightness
    lum = np.clip((r + g + b) // 3, 0, 255).astype(np.uint8)
    a[green, 0] = (lum[green] * 0.45).astype(np.uint8)
    a[green, 1] = (lum[green] * 0.72).astype(np.uint8)
    a[green, 2] = np.clip(lum[green].astype(np.int16) + 70, 0, 255).astype(np.uint8)
    # red/orange -> amber
    a[red, 0] = np.clip(r[red].astype(np.int16) + 15, 0, 255).astype(np.uint8)
    a[red, 1] = (b[red] * 0.2 + g[red] * 0.55 + 55).astype(np.uint8)
    a[red, 2] = (b[red] * 0.2).astype(np.uint8)
    try:
        con.fg[:] = a
    except Exception:
        pass
