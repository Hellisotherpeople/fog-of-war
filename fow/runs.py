"""The runs on this machine: named saves, and the little record the menu shows of each.

One file per run in the save folder, and an index beside them.  The index is written after each save and
is only a convenience - a run whose index line is missing is still a save, and can be read.  Ironman runs
keep one file and no backup to fall back on.
"""
from __future__ import annotations

import json
import os
import re
import time

from .game import SAVE_DIR

INDEX = os.path.join(SAVE_DIR, "runs.json")
NAME_RE = re.compile(r"^save-([A-Za-z0-9]{4,24})\.pkl$")


def slot_path(run_id: str) -> str:
    return os.path.join(SAVE_DIR, f"save-{run_id}.pkl")


def new_id() -> str:
    seed = f"{time.time_ns()}"
    import hashlib
    return hashlib.sha1(seed.encode()).hexdigest()[:10]


def _read() -> dict:
    try:
        with open(INDEX, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        tmp = INDEX + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, INDEX)
    except OSError:
        pass


def note(run_id: str, game, **extra) -> None:
    """Record what the menu may say about a run.  Cheap: a dict and a small file."""
    if not run_id:
        return
    p = game.player
    data = _read()
    rec = dict(data.get(run_id) or {})
    rec.update(dict(
        name=(p.name if p is not None else rec.get("name", "Someone")),
        rank=(p.rank_short if p is not None else rec.get("rank", "")),
        role=(p.role_name if p is not None else rec.get("role", "")),
        theatre=game.theatre.get("battle") or game.theatre.get("name"),
        year=game.theatre.get("date", [0])[0],
        minutes=int(game.clock // 60),
        alive=bool(p is not None and p.alive),
        dead=bool(game.game_over and p is not None and not p.alive),
        code=getattr(game, "run_code", None) or rec.get("code"),
        ironman=bool(getattr(game, "ironman", False) or rec.get("ironman")),
        difficulty=str((game.__dict__.get("difficulty") or {}).get("kind", "")),
        updated=time.time(),
    ))
    rec.update(extra)
    data[run_id] = rec
    _write(data)


def listing() -> list[dict]:
    """Runs that still have a file, newest first."""
    data = _read()
    out = []
    seen = set()
    for run_id, rec in data.items():
        path = slot_path(run_id)
        if not os.path.exists(path):
            continue
        rec = dict(rec)
        rec["id"] = run_id
        rec["exists"] = True
        seen.add(run_id)
        out.append(rec)
    # a save with no index line (hand-copied, or the index lost) is still somebody's war
    try:
        names = os.listdir(SAVE_DIR)
    except OSError:
        names = []
    for name in names:
        m = NAME_RE.match(name)
        if not m or m.group(1) in seen:
            continue
        rid = m.group(1)
        try:
            stamp = os.path.getmtime(os.path.join(SAVE_DIR, name))
        except OSError:
            stamp = 0
        out.append(dict(id=rid, name="Unnamed run", rank="", role="", theatre="", year=0, minutes=0,
                        alive=True, dead=False, ironman=False, difficulty="", updated=stamp, exists=True))
    out.sort(key=lambda r: r.get("updated", 0), reverse=True)
    return out


def forget(run_id: str) -> None:
    data = _read()
    data.pop(run_id, None)
    _write(data)
    for suffix in ("", ".bak", ".tmp"):
        try:
            os.remove(slot_path(run_id) + suffix)
        except OSError:
            pass


def latest_alive() -> str | None:
    for r in listing():
        if r.get("alive") and not r.get("dead"):
            return r["id"]
    return None


def describe(r: dict) -> str:
    bits = [f"{r.get('rank', '')} {r.get('name', 'Someone')}".strip(), (r.get("role") or "").lower()]
    if r.get("theatre"):
        bits.append(f"{r['theatre']}, {r.get('year', '')}")
    mins = int(r.get("minutes") or 0)
    if mins:
        bits.append(f"{mins // 60}h {mins % 60:02d}m")
    if r.get("dead"):
        bits.append("dead")
    elif r.get("ironman"):
        bits.append("ironman")
    return " - ".join(b for b in bits if b)
