#!/usr/bin/env python3
"""Check content packs without starting the game.  Exit 1 on any error.

    python tools/packcheck.py assets/packs
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", os.path.join(os.path.dirname(__file__), ".packcheck-home"))

from fow import packs  # noqa: E402


def main(paths):
    bad = 0
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(sorted(os.path.join(p, n) for n in os.listdir(p) if n.endswith(".json")))
        elif os.path.isfile(p) and p.endswith(".json"):
            files.append(p)
    if not files:
        print("no .json packs found")
        return 1
    for path in files:
        before = len(packs.ERRORS)
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError) as e:
            print(f"BAD  {path}: {e}")
            bad += 1
            continue
        packs.apply(data, os.path.basename(path))
        errs = packs.ERRORS[before:]
        if errs:
            bad += 1
            for e in errs:
                print(f"BAD  {path}: {e}")
        else:
            counts = {k: len(data.get(k) or {}) for k in ("theatres", "items", "vehicles", "roles", "missions",
                                                          "quotes", "phrases")}
            print("OK   " + path + "  " + ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
