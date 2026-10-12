"""Mission outcomes describe physical results, not crossing generation-cell boundaries."""
from __future__ import annotations

import math


def entity(game, eid, vehicles=False):
    local = game.vehicles if vehicles else game.actors
    found = next((a for a in local if a.id == eid), None)
    landscape = game.__dict__.get("landscape")
    if found is None and landscape is not None:
        found = (landscape.vehicles if vehicles else landscape.actors).get(eid)
    return found


def world_pos(game, actor):
    landscape = game.__dict__.get("landscape")
    if landscape is not None and landscape.frame is game.map:
        if actor.__dict__.get("_stream_dormant"):
            return actor.pos
        return landscape.world_pos(*actor.pos)
    return game.sector.x * game.map_w + actor.x, game.sector.y * game.map_h + actor.y


def prepare(game, ms):
    p = game.player
    ms.setdefault("roster", [a.id for a in (p.squad.members if p.squad else [p]) if a.alive])
    ms.setdefault("start_world", world_pos(game, p))
    ms.setdefault("observations", {})
    ms.setdefault("confirmed_targets", [])
    if ms["kind"] in ("hold", "rearguard"):
        ms.setdefault("hold_required", max(1, ms["until"] - ms.get("start", game.turn)))
        ms.setdefault("held_seconds", 0)
        ms.setdefault("hold_checked", game.turn)
    if ms["kind"] == "take":
        from .scenarios import mission_objectives
        ms.setdefault("capture_required", any(o.owner != p.side for o in mission_objectives(game)))
        if ms.get("sid") == "armour":
            ms.setdefault("armour_targets", [v.id for v in game.vehicles if v.side != p.side and not v.dead
                                             and v.vt.vtype in ("tank", "td", "armcar")])
    if ms["kind"] == "raid":
        rec = ms.get("rec")
        if rec:
            x, y, w, h = rec["rect"]
            ms.setdefault("gun_targets", [v.id for v in game.vehicles if not v.dead and v.side != p.side
                                           and v.vt.static and x <= v.x < x+w and y <= v.y < y+h])


def rally_destination(game, ms):
    """Brief a fixed, generated friendly post; never move it farther away when the player arrives."""
    from .service import scene_map, resolve, post_destination
    if ms.get("rally_destination"):
        return resolve(game, ms["rally_destination"])
    if ms.get("rally_unavailable"):
        return None
    start = ms.get("_start_sector", game.sector)
    side = game.player.side
    sectors = [s for s in game.strategic.sectors() if s.playable and s.control == side and s is not start]
    sectors.sort(key=lambda s: abs(s.x-start.x) + abs(s.y-start.y))
    for sec in sectors:
        if not any(ok and sd == side and kind in ("hq", "aid", "depot") for kind, sd, ok in sec.installations):
            continue
        m = scene_map(game, sec)
        recs = [r for r in m.gen_positions if r.get("side") == side and not r.get("destroyed")
                and r.get("kind") in ("hq", "aid", "depot")]
        if not recs:
            continue
        rec = min(recs, key=lambda r: (r["kind"] != "hq", r["kind"] != "aid"))
        dest = post_destination(game, sec, rec, framed=m is game.map)
        dest.setdefault("world", (sec.x * game.map_w + rec["x"], sec.y * game.map_h + rec["y"]))
        dest["label"] = f"friendly lines: {rec['kind'].replace('_', ' ')} rally post"
        ms["rally_destination"] = dest
        from .base import _next_edge
        ms["home"] = _next_edge(game, dest["sector"]) or ms.get("home")
        return resolve(game, dest)
    ms["rally_unavailable"] = True
    return None


def rally_point(game, ms):
    from .contacts import route
    dest = rally_destination(game, ms)
    if dest and math.dist(world_pos(game, game.player), dest["world"]) <= 20:
        staff = [a for a in game.actors if a.id not in ms.get("roster", [game.player.id])
                 and a.active and not a.downed and a.side == game.player.side and not a.ai.get("civilian")
                 and math.dist(world_pos(game, a), dest["world"]) <= 16]
        if staff:
            who = min(staff, key=lambda a: math.dist(a.pos, game.player.pos))
            return *who.pos, f"Report at the rally post to {game.name_of(who)}"
    return route(game, dest) if dest else None


def quiet(game, radius=30):
    p = game.player
    return not any(a.side != p.side and a.active and not a.downed and not a.ai.get("civilian")
                   and math.hypot(a.x-p.x, a.y-p.y) < radius for a in game.actors)


def receiver(game, ms):
    """Arrival means reaching the assigned functioning post and its living people."""
    from .intelligence import distance
    from .senses import los_clear
    from .service import destination_available
    dest = rally_destination(game, ms)
    if dest is None:
        return None
    if distance(world_pos(game, game.player), dest["world"]) > 14:
        return None
    if not destination_available(game, dest, (dest["kind"],)):
        if not ms.get("rally_lost"):
            ms["rally_lost"] = True
            game.msg("The briefed rally post has fallen or been destroyed. The mission cannot be reported here.", "warn")
        return None
    if not quiet(game):
        return None
    p = game.player
    return next((a for a in game.actors if a.id not in ms.get("roster", [p.id]) and a.side == p.side
                 and a.active and not a.downed and not a.ai.get("civilian")
                 and distance(a.pos, p.pos) <= 4 and los_clear(game, *p.pos, *a.pos)), None)


def team_at_rally(game, ms):
    """Missing/unloaded men are missing, never silently counted as rescued or dead."""
    dest = rally_destination(game, ms)
    arrived, dead, missing = [], [], []
    for eid in ms.get("roster", [game.player.id]):
        a = entity(game, eid)
        if a is not None and not a.alive:
            dead.append(eid)
        elif a is not None and dest and math.dist(world_pos(game, a), dest["world"]) <= 18:
            arrived.append(eid)
        else:
            missing.append(eid)
    return arrived, dead, missing


def observe(game, ms):
    """A patrol reports distinct enemy positions it actually sees, not the army's global contact list."""
    from .senses import player_can_see_actor
    seen = ms.setdefault("observations", {})
    for a in game.actors:
        if a.side == game.player.side or not a.active or a.ai.get("civilian") or not game.map.in_bounds(*a.pos):
            continue
        if not player_can_see_actor(game, a):
            continue
        key = a.squad.id if a.squad is not None else a.id
        if key not in seen:
            pos = world_pos(game, a)
            if all(math.dist(pos, c["world"]) >= 10 for c in seen.values()):
                seen[key] = dict(world=pos, turn=game.turn)
    return len(seen)


def on_kill(game, victim):
    ms = game.__dict__.get("mission") or {}
    if ms.get("kind") != "sniper" or ms.get("stage") != "hunt":
        return
    if victim.side == game.player.side or getattr(victim, "rank", -1) < 2 and getattr(victim, "role", "") not in (
            "lmg_gunner", "hmg_gunner", "sniper"):
        return
    if victim.ai.get("civilian") or victim.ai.get("incapacitated_before_fatal_hit"):
        return
    targets = ms.setdefault("confirmed_targets", [])
    if victim.id not in targets:
        targets.append(victim.id)


def holding(game, ms, objectives):
    p = game.player
    close = any(math.dist(world_pos(game, p), getattr(o, "_world_pos",
                (game.sector.x*game.map_w+o.x, game.sector.y*game.map_h+o.y))) <= o.radius + 30 for o in objectives)
    held = bool(objectives) and all(o.owner == p.side for o in objectives) and close
    elapsed = max(0, game.turn - ms.get("hold_checked", game.turn))
    # Count observed intervals on station; being elsewhere or losing the ground breaks the hold.
    if held and ms.get("was_holding"):
        ms["held_seconds"] += elapsed
    elif not held:
        ms["held_seconds"] = 0
    ms.update(hold_checked=game.turn, was_holding=held)
    return held and ms["held_seconds"] >= ms["hold_required"]


def clear_of_target(game, ms, distance=60):
    # Old saves lack the anchor. Start observing displacement now rather than inventing a past escape.
    origin = ms.setdefault("withdraw_world", world_pos(game, game.player))
    return math.dist(world_pos(game, game.player), origin) >= distance and quiet(game)


def complete(game, ms, text, merit=6):
    """Completion records service. Decorations still require the existing witnessed-deeds review."""
    if ms.get("stage") == "done":
        return
    ms.update(stage="done", outcome=text, completed=game.turn)
    game.msg(text, "good")
    game.command.merit += merit
    game.duty.rep = min(100., game.duty.rep + merit)
    game.command.__dict__.setdefault("record", []).append(f"{game.datetime_str()}: {text}")
    game.update_orders(force=True)
