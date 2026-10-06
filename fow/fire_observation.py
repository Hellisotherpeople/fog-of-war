"""Counter-battery intelligence needs an observer or an established survey network."""
from __future__ import annotations

from .constants import other_side
from .intelligence import distance, radio_link


def locate(game, battery, mission):
    if mission.get("fired", 0) <= 0 or battery.pos is None:
        return None
    side = other_side(battery.side)
    guns = [v for v in game.vehicles if v.ai.get("battery") == battery.id and v.active]
    sq = next((q for q in game.squads if q.id == battery.squad_id), None)
    targets = guns + ([a for a in sq.members if a.active] if sq else [])
    for a in game.actors:
        if a.side != side or not a.active or a.downed or not radio_link(game, a):
            continue
        seen = [e for e in a.visible if e in targets] if a.vis_turn >= game.turn - 10 else []
        if seen:
            e = seen[0]
            return dict(side=side, x=e.x, y=e.y, observed=game.turn, due=game.turn + 90,
                        source="forward observer", observers=[a.id], error=8.,
                        mortar=battery.kind == "mortar", battery=battery.id)
    # Sound ranging requires separated, occupied, surveyed posts, several rounds,
    # and communication. A single listener supplies a bearing, not a grid square.
    posts = []
    for rec in game.map.gen_positions:
        if rec.get("kind") != "observation" or rec.get("side") != side or rec.get("destroyed"):
            continue
        observer = next((a for a in game.actors if a.side == side and a.active and not a.downed
                         and distance(a.pos, (rec["x"], rec["y"])) <= 3 and radio_link(game, a)), None)
        if observer:
            posts.append((rec, observer))
    pair = next(((r, a, s, b) for r, a in posts for s, b in posts if a is not b and
                 distance((r["x"], r["y"]), (s["x"], s["y"])) >= 20), None)
    if pair is None or mission["fired"] < 6:
        return None
    r, a, s, b = pair
    # Thunder, competing gunfire and wind make this harder; never improve the fix.
    error = 18 + min(30, game.noise / 3)
    x = max(0, min(game.map.w - 1, round(battery.pos[0] + game.rng.gauss(0, error))))
    y = max(0, min(game.map.h - 1, round(battery.pos[1] + game.rng.gauss(0, error))))
    return dict(side=side, x=x, y=y, observed=game.turn, due=game.turn + 600,
                source="surveyed sound-ranging posts", observers=[a.id, b.id], error=error,
                mortar=battery.kind == "mortar", battery=battery.id)


def delivered(game, report):
    if not isinstance(report, dict) or "observers" not in report:
        return False                 # old saves' automatic retaliation has no supporting report
    return all(any(a.id == aid and a.side == report["side"] and radio_link(game, a)
                   for a in game.actors) for aid in report["observers"])
