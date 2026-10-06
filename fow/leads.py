"""Briefing leads are remembered places, not tracking beacons on hidden people."""
from __future__ import annotations


def remember(game, ms, x, y, label, radius=0, key=None):
    # A coarse map square, fixed when the information is received.
    if radius:
        step = max(2, radius)
        x, y = round(x / step) * step, round(y / step) * step
    x = max(1, min(game.map.w - 2, int(x)))
    y = max(1, min(game.map.h - 2, int(y)))
    lead = dict(x=x, y=y, label=label, radius=radius, at=game.turn, key=key)
    ms.setdefault("leads", []).append(lead)
    return lead


def initialize(game, ms):
    """Also migrates older briefings once; no repeated sampling of hidden targets."""
    if "leads" in ms:
        return
    ms["leads"] = []
    task = ms.get("task")
    if task in ("rescue_airman", "eliminate"):
        aid = ms.get("airman" if task == "rescue_airman" else "mark")
        a = next((a for a in game.actors if a.id == aid), None)
        if a:
            # The original holding position is the last report, even if he has since moved.
            pt = a.squad.order.target if a.squad and a.squad.order.target else a.pos
            remember(game, ms, *pt, "Airman's last reported area" if task == "rescue_airman" else
                     "Target's last reported area", 16)
    elif task == "photograph":
        for r in getattr(game.map, "gen_positions", []):
            if r.get("side") != game.player.side and r.get("rect"):
                remember(game, ms, r["x"], r["y"], "Reconnaissance: " + r.get("name", r["kind"]),
                         key=f"{r['kind']}@{r['x']},{r['y']}")
    elif task == "wireless":
        # A recommended starting area, not a magical safe radio site.
        buildings = getattr(game.map, "buildings", [])
        if buildings:
            x, y, w, h, _ = min(buildings, key=lambda b: abs(b[0] - game.player.x) + abs(b[1] - game.player.y))
            remember(game, ms, x + w // 2, y + h // 2, "Suggested wireless area; scout it and relocate after sending", 12)
        else:
            remember(game, ms, *game.player.pos, "Find concealment here for the wireless; relocate after sending", 12)


def current(game, ms):
    initialize(game, ms)
    leads = ms.get("leads", [])
    if ms.get("task") == "photograph":
        leads = [r for r in leads if r.get("key") not in ms.get("shot", [])]
    if not leads:
        return None
    return min(leads, key=lambda r: abs(r["x"] - game.player.x) + abs(r["y"] - game.player.y))


def point(game, ms):
    lead = current(game, ms)
    if lead is None:
        return None
    label = lead["label"]
    if lead["radius"]:
        label += f" (search within ~{round(lead['radius'] * 2.2)} yards)"
    return lead["x"], lead["y"], label
