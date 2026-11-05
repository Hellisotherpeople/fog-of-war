"""Content packs: theatres, quotes and extra lines, loaded from JSON.

A pack is a folder under `assets/packs/` (shipped) or `~/.fogofwar/packs/` (yours), one or more `.json`
files.  Each file may add:

    {"name": "...", "author": "...", "version": 1,
     "theatres": {id: {...}},          # a full theatre record, as in data/theatres.py
     "quotes": [[tags, quote, attribution, bio], ...],
     "phrases": {key: {lang: [lines]}}} # extra speech lines

Nothing is replaced: theatre ids already present are skipped, quotes are appended, phrase lines are merged.
A malformed pack is reported and the rest still loads; nothing here touches a save.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "assets" / "packs"
USER = Path(os.environ.get("FOW_HOME") or (Path.home() / ".fogofwar")) / "packs"
LOADED = [False]
ERRORS: list[str] = []
REQUIRED_THEATRE = ("name", "battle", "date", "climate", "sides")


def _files() -> list[Path]:
    out = []
    for root in (SHIPPED, USER):
        if not root.is_dir():
            continue
        out.extend(sorted(root.glob("*.json")))
    return out


def apply(data: dict, where: str) -> None:
    from .data.theatres import THEATRES
    from . import quotes as _q
    from .data.phrases import P
    if not isinstance(data, dict):
        ERRORS.append(f"{where}: not an object")
        return
    for iid, rec in (data.get("items") or {}).items():
        if not isinstance(rec, dict) or "name" not in rec or "kind" not in rec:
            ERRORS.append(f"{where}: item {iid} needs name and kind")
            continue
        from .data.items import ITEMS
        from .data.defs import ItemType
        if iid in ITEMS:
            continue
        kw = {k: v for k, v in rec.items() if k != "name"}
        if "nations" in kw:
            kw["nations"] = tuple(kw["nations"])
        if "years" in kw:
            kw["years"] = tuple(kw["years"])
        try:
            ITEMS[iid] = ItemType(iid, str(rec["name"]), **kw)
            from .data.items import _register_mags
            _register_mags({iid})                  # (its magazines and clips, as the shipped guns get)
        except TypeError as e:
            ITEMS.pop(iid, None)
            ERRORS.append(f"{where}: item {iid}: {e}")
    for vid, rec in (data.get("vehicles") or {}).items():
        if not isinstance(rec, dict) or "name" not in rec:
            ERRORS.append(f"{where}: vehicle {vid} needs a name")
            continue
        from .data.vehicles import VEHICLES
        from .data.defs import VehicleType
        if vid in VEHICLES:
            continue
        kw = {k: v for k, v in rec.items() if k != "name"}
        kw["nations"] = tuple(kw.get("nations", ()))
        kw["years"] = tuple(kw.get("years", (1900, 1950)))
        try:
            VEHICLES[vid] = VehicleType(vid, str(rec["name"]), **kw)
        except TypeError as e:
            ERRORS.append(f"{where}: vehicle {vid}: {e}")
    for rid, rec in (data.get("roles") or {}).items():
        if not isinstance(rec, dict) or "name" not in rec:
            ERRORS.append(f"{where}: role {rid} needs a name")
            continue
        from .data.roles import ROLES
        if rid in ROLES:
            continue
        ROLES[rid] = dict(rec)
    for sid, rec in (data.get("missions") or {}).items():
        if not isinstance(rec, dict) or "name" not in rec:
            ERRORS.append(f"{where}: mission {sid} needs a name")
            continue
        from .scenarios import SCENARIOS
        if sid in SCENARIOS:
            continue
        SCENARIOS[sid] = dict(rec, pack=True)
    for tid, th in (data.get("theatres") or {}).items():
        if not isinstance(th, dict) or any(k not in th for k in REQUIRED_THEATRE):
            ERRORS.append(f"{where}: theatre {tid} missing one of {', '.join(REQUIRED_THEATRE)}")
            continue
        if tid in THEATRES:
            continue
        THEATRES[tid] = dict(th, id=tid, pack=data.get("name", "pack"))
    for row in data.get("quotes") or []:
        if isinstance(row, (list, tuple)) and len(row) >= 4:
            _q.Q.append((tuple(row[0]), str(row[1]), str(row[2]), str(row[3])))
        else:
            ERRORS.append(f"{where}: bad quote row")
    for key, table in (data.get("phrases") or {}).items():
        if not isinstance(table, dict):
            continue
        P.setdefault(key, {})
        for lg, lines in table.items():
            P[key].setdefault(lg, [])
            P[key][lg] += [str(x) for x in lines]


DISABLED = Path(os.environ.get("FOW_HOME") or (Path.home() / ".fogofwar")) / "packs_disabled.json"


def disabled() -> set:
    try:
        data = json.loads(DISABLED.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else [])
    except (OSError, ValueError):
        return set()


def set_disabled(names) -> None:
    try:
        DISABLED.parent.mkdir(parents=True, exist_ok=True)
        DISABLED.write_text(json.dumps(sorted(set(names))), encoding="utf-8")
    except OSError:
        pass


def load_all(force=False) -> list[str]:
    """Load every pack once.  Returns the errors (also kept in ERRORS)."""
    if LOADED[0] and not force:
        return ERRORS
    LOADED[0] = True
    off = disabled()
    for path in _files():
        if path.name in off or path.stem in off:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            ERRORS.append(f"{path.name}: {e}")
            continue
        apply(data, path.name)
    return ERRORS


def theatre_ids() -> list[str]:
    return [p.stem for p in _files()]
