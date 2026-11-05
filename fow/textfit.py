"""Hard width limits for hand-drawn text.

Anything printed outside a Popup lays out its own rows, so it must prove it fits.  These helpers wrap
(or, where wrapping would spoil a label, truncate with an ellipsis) and never return a row wider than
asked.  One column of slack is not left to chance: a long attribution, a long quote, a translated
line or a player's name all go through here.
"""
from __future__ import annotations

import textwrap


def wrap(text: str, width: int) -> list[str]:
    width = max(1, width)
    return textwrap.wrap(str(text), width) or [""]


def fit(text: str, width: int, ellipsis: str = "…") -> str:
    width = max(1, width)
    s = str(text)
    if len(s) <= width:
        return s
    if width <= len(ellipsis):
        return s[:width]
    return s[:width - len(ellipsis)].rstrip() + ellipsis


def clip(text: str, width: int, max_rows: int, ellipsis: str = "…") -> list[str]:
    """Wrapped rows, capped, with the last row fitted so it does not run over."""
    rows = wrap(text, width)
    if len(rows) <= max_rows:
        return rows
    rows = rows[:max(1, max_rows)]
    if width > len(ellipsis):
        rows[-1] = fit(rows[-1], width - len(ellipsis)) + ellipsis
    else:
        rows[-1] = fit(rows[-1], width, ellipsis)
    return rows


def draw(con, x: int, y: int, width: int, rows: list[tuple[str, tuple]], max_rows: int | None = None):
    """Print (text, colour) rows through wrap; returns the row after the block."""
    left = max_rows
    for text, col in rows:
        for line in wrap(text, width):
            if left is not None and left <= 0:
                return y
            con.print(x, y, line, fg=col)
            y += 1
            if left is not None:
                left -= 1
    return y
