"""The after-action report: a fight condensed to a page, and the runs before it.

The point is not a score.  It is a record a clerk could file: the ground, what was asked, what was done,
who it cost, what was written down, and what the next man can learn from it.  It exports beside the diary.
"""
from __future__ import annotations

import os
import time

from .game import SAVE_DIR

REPORTS = os.path.join(SAVE_DIR, "reports")


def _minutes(game) -> int:
    return int(game.clock // 60)


def _team_count(game):
    """Who was on the ground at the start, by side, from the initial strength if we have it."""
    st = getattr(game, "initial_strength", None) or {}
    return st


def lines(game) -> list[tuple[str, str]]:
    p = game.player
    st = game.stats
    out = [(f"{game.theatre.get('name', '')}: {game.theatre.get('battle', '')}", "dim"),
           (f"{game.start_dt:%d %B %Y}, {game.start_dt:%H:%M}", "dim")]
    mins = _minutes(game)
    out.append((f"Time on the ground: {mins // 60}h {mins % 60:02d}m", ""))
    out.append(("", ""))
    out.append((f"Asked to: {game.scenario.replace('_', ' ')}. {((game.mission or {}).get('text') or '')}".strip(),
                ""))
    out.append((f"Done: {st['objectives']} objective(s) taken with the section; "
                f"{len(game.sector_log)} sector(s) fought over.", ""))
    out.append(("", ""))
    out.append((f"The cost, by your hand: {st['kills']} enemy killed, {st['vehicles_killed']} vehicle(s) "
                f"destroyed, {st['wounds']} times wounded.", ""))
    try:
        from . import bonds
        mem = (p.squad.rep.get("memory") or {}) if p is not None and p.squad is not None else {}
        lost = list(mem.get("lost") or [])
        if lost:
            out.append(("The section lost: " + ", ".join(lost[:8]) + (f" and {len(lost) - 8} more"
                                                                       if len(lost) > 8 else "") + ".", ""))
    except Exception:
        pass
    from . import renown, trade, diary
    if renown.title(game):
        out.append((f"The section called you {renown.title(game)}.", ""))
    tr = trade.summary(game)
    if tr:
        out.append(("Trade: " + ", ".join(tr) + ".", ""))
    if game.__dict__.get("diary"):
        out.append(("", ""))
        out.append(("From the diary:", "dim"))
        for e in list(game.diary)[-4:]:
            out.append((f"{e.get('stamp', '')} - {e.get('text', '')}", ""))
    out.append(("", ""))
    out.append((("Killed" if p is not None and not p.alive else "Survived") +
                (f" - {game.death_text}" if game.death_text else "."), "dim"))
    return out


def export(game) -> str | None:
    try:
        os.makedirs(REPORTS, exist_ok=True)
        p = game.player
        name = (p.name if p is not None else "soldier").replace(" ", "_")
        path = os.path.join(REPORTS, f"{time.strftime('%Y%m%d-%H%M%S')}-{name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# After action: {game.theatre.get('battle', '')}\n\n")
            for text, _tone in lines(game):
                f.write(text + "\n")
            f.write("\n---\n")
            if getattr(game, "run_code", None):
                f.write(f"Run code: `{game.run_code}`\n")
        return path
    except OSError:
        return None


def history(n=6) -> list[str]:
    from . import runs
    out = []
    for r in runs.listing()[:n]:
        if not r.get("dead") and not r.get("alive"):
            continue
        out.append(runs.describe(r))
    return out


def compare(game) -> list[str]:
    """Your last few runs beside this one, plainly."""
    from . import runs
    mine = _minutes(game)
    rows = [f"This one: {mine // 60}h {mine % 60:02d}m, {game.stats['kills']} killed, "
            f"{game.stats['objectives']} objective(s)."]
    others = [r for r in runs.listing() if r.get("id") != getattr(game, "run_id", None)][:5]
    if not others:
        rows.append("No earlier runs on this machine.")
    for r in others:
        m = int(r.get("minutes") or 0)
        rows.append(f"{runs.describe(r)} - {m // 60}h {m % 60:02d}m")
    return rows
