"""ASCII drawings of the kit, shown at the top of the box when you look an item over (play.examine_lines).

The drawings live in assets/art/*.txt, not in the code: a line `%% id [id ...]` starts a drawing shared by those
item ids, and the drawing runs to the next such line.  tools/check_art.py lists and validates them.
"""
from __future__ import annotations

import os

ART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "art")
MAX_W, MAX_H = 56, 10      # inside the 58-wide look-it-over box
_art: dict[str, tuple[str, ...]] | None = None


def parse(text: str) -> dict[str, tuple[str, ...]]:
    art, ids, rows = {}, None, []

    def close():
        while rows and not rows[-1].strip():
            rows.pop()
        while rows and not rows[0].strip():
            rows.pop(0)
        for i in ids or ():
            art[i] = tuple(rows)
    for line in text.splitlines():
        if line.startswith("%%"):
            close()
            ids, rows = line[2:].split(), []
        elif ids is not None:
            rows.append(line.rstrip())
    close()
    return art


def load() -> dict[str, tuple[str, ...]]:
    global _art
    if _art is None:
        _art = {}
        names = sorted(os.listdir(ART_DIR)) if os.path.isdir(ART_DIR) else []
        for name in names:
            if name.endswith(".txt"):
                with open(os.path.join(ART_DIR, name), encoding="utf-8") as f:
                    _art.update(parse(f.read()))
    return _art


def art_lines(t, width: int) -> list[tuple[str, tuple]]:
    """The drawing of item type t, centred in `width` columns, in the item's own colour lifted to be legible."""
    rows = load().get(t.id)
    if not rows:
        return []
    pad = " " * max(0, (width - max(len(r) for r in rows)) // 2)
    col = tuple(min(255, int(c * 0.6 + 100)) for c in t.color)
    return [(pad + r, col) for r in rows] + [("", None)]
