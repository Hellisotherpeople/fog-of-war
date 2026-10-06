"""Workshop destinations, replacement kit and appointments at higher headquarters."""
from __future__ import annotations

from .intelligence import distance, headquarters, map_report


def destination(game, kinds):
    p = game.player
    local = [r for r in game.map.gen_positions if r.get("kind") in kinds and r.get("side") == p.side
             and not r.get("destroyed")]
    if local:
        rec = min(local, key=lambda r: distance((r["x"], r["y"]), p.pos))
        return dict(sector=(game.sector.x, game.sector.y), point=(rec["x"], rec["y"]), kind=rec["kind"])
    choices = []
    for s in game.strategic.sectors():
        r = map_report(game, s)
        if r and r["control"] == p.side and any(k in kinds and side == p.side and ok
                                                for k, side, ok in r["installations"]):
            choices.append(s)
    s = min(choices, key=lambda s: distance((s.x, s.y), (game.sector.x, game.sector.y)), default=None)
    if s:
        return dict(sector=(s.x, s.y), point=None, kind=kinds[0])
    return None


def entry(game):
    ticket = game.player.ai.get("service_order")
    if not ticket or game.__dict__.get("domain", "land") != "land":
        return None
    dest = destination(game, ("hq",) if ticket["kind"] == "conference" else ("motor_pool", "factory"))
    ticket["destination"] = dest
    point = None
    label = "higher headquarters" if ticket["kind"] == "conference" else "repair workshop"
    if dest:
        if dest["sector"] != (game.sector.x, game.sector.y):
            from .base import _next_edge
            from .orders import exit_point
            edge = _next_edge(game, dest["sector"])
            if edge:
                point = (*exit_point(game, edge), f"Route to {label} at {game.strategic.at(*dest['sector']).name}")
        else:
            point = (*dest["point"], label)
    text = ticket["text"] + (" Destination marked in your orders." if dest else
                             " No workshop location is on your sheet; obtain a situation map at HQ.")
    return dict(key="service", who=ticket["who"], how=ticket["how"], text=text,
                issued=ticket["issued"], due=None, reward="return to duty with serviceable equipment" if
                ticket["kind"] == "repair" else "fresh operations orders and the headquarters situation map",
                penalty="the equipment remains unserviceable" if ticket["kind"] == "repair" else
                "headquarters awaits your report", urgent=False, point=point, authority=ticket["authority"])


def plan(ps):
    g, p = ps.game, ps.game.player
    order = entry(g)
    if order is None or order["point"] is None:
        return "consult the orders book for a service destination", ps.cmd_orders_book
    ticket = p.ai["service_order"]
    dest, pt = ticket["destination"], order["point"]
    arrival = 2 if dest["sector"] != (g.sector.x, g.sector.y) else 4
    if p.vehicle is not None and distance(p.pos, pt[:2]) > arrival:
        return f"drive toward {pt[2]}", lambda: drive_step(ps, pt[:2])
    if dest["sector"] != (g.sector.x, g.sector.y):
        from .base import _next_edge
        edge = _next_edge(g, dest["sector"])
        return pt[2].lower(), lambda: ps._travel_chosen(edge) if distance(p.pos, pt[:2]) <= 2 else \
            ps.start_travel(pt[0], pt[1], then=lambda: ps._travel_chosen(edge), stop_short=1)
    if distance(p.pos, pt[:2]) > 4:
        return f"proceed to the {pt[2]}", lambda: ps.start_travel(pt[0], pt[1], stop_short=3)
    if ticket["kind"] == "conference":
        return "report for the command conference", lambda: conference(ps)
    return "wait while the fitters work; any key stops", lambda: ps.begin_wait("time", 600)


def conference(ps):
    g, p = ps.game, ps.game.player
    ticket = p.ai.get("service_order")
    if not ticket or ticket["kind"] != "conference" or not headquarters(g):
        return
    rec = headquarters(g)
    officer = next((a for a in g.actors if a.side == p.side and a.active and a.rank > p.rank
                    and distance(a.pos, p.pos) <= 10), None)
    if officer is None:
        # This is the previously off-map commander at his appointed headquarters.
        from .spawn import make_soldier
        cells = [(x, y) for x in range(rec["x"] - 3, rec["x"] + 4) for y in range(rec["y"] - 3, rec["y"] + 4)
                 if g.map.in_bounds(x, y) and g.map.walk[x, y] and (x, y) not in g.soldier_at
                 and (x, y) not in g.vehicle_at]
        if not cells:
            g.msg("The command post is crowded. Make room by the map table.", "info")
            return
        officer = make_soldier(g, p.nation, "officer")
        officer.rank = ticket["authority"]
        officer.name = ticket["who"]
        officer.x, officer.y = cells[0]
        g.actors.append(officer)
        g.soldier_at[officer.pos] = officer
        from .ai import Squad, Order
        sq = Squad(p.side, p.nation, "staff", "Higher headquarters")
        sq.members, sq.leader = [officer], officer
        officer.squad = sq
        sq.order = Order("hold", target=officer.pos)
        g.squads.append(sq)
    from .intelligence import copy_map
    copy_map(g)
    from .recognition import consider
    consider(g)
    from .intent import profile
    g.msg(f"{officer.rank_short} {officer.last_name} goes over the map with you: '{profile(p.nation)[0]}. "
          "Organize your subordinate commands, replenish your stores, and consolidate your assigned ground.'", "info")
    p.ai.pop("service_order", None)
    p.ai["last_conference"] = g.turn
    # The new briefing becomes a received order, with the actual officer's authority.
    ob = min(g.map.objectives, key=lambda ob: distance(ob.pos, p.pos), default=None)
    if ob:
        g.field_order = dict(text=f"Consolidate {ob.name}; organize reserves and supply.",
                            point=ob.pos, sector=(g.sector.x, g.sector.y), reason="Orders received at the command conference.",
                            edge=None, issued=g.turn, authority=officer.rank, who=officer.full_name)
    ps.act(6000)


def drive_step(ps, point):
    """Enter follows the marked workshop route one driving action at a time."""
    g, p = ps.game, ps.game.player
    v = p.vehicle
    from .crew import can
    if not v.mobile or not can(v, "drive")[0]:
        g.msg("Take the driving or command station to follow the workshop route. If immobilized, wait for fitters.", "info")
        return
    brain = g.brains[p.side]
    mp = brain.vehicle_map(*point, v.vt.crush, v.vt.vtype in ("car", "truck", "armcar"), wide=v.size[1] >= 2)
    if mp is None:
        g.msg("No vehicle route to that workshop is known. Follow the marked direction and look for a road.", "info")
        return
    choices = [(mp[v.x + dx, v.y + dy], dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               if (dx or dy) and g.map.in_bounds(v.x + dx, v.y + dy) and mp[v.x + dx, v.y + dy] < mp[v.x, v.y]]
    if choices:
        _, dx, dy = min(choices)
        ps.drive(dx, dy)
    else:
        g.msg("The workshop route is blocked here. Maneuver onto a clear approach.", "info")


def tick(game):
    p = game.player
    if game.__dict__.get("domain", "land") != "land" or not p.alive:
        return
    from .maintenance import repairs, quiet
    v = p.vehicle
    ticket = p.ai.get("service_order")
    if ticket and ticket["kind"] == "repair":
        vehicle = next((o for o in game.vehicles if o.id == ticket.get("vehicle")), None)
        if vehicle is None or vehicle.dead or not repairs(vehicle) and vehicle.hp >= vehicle.vt.hp:
            p.ai.pop("service_order", None)
            ticket = None
    if v is not None and not ticket and (repairs(v) or v.hp < v.vt.hp):
        p.ai["service_order"] = dict(kind="repair", vehicle=v.id, issued=game.turn, authority=p.rank,
            who="your crew's damage report", how="inspection", text="Take the vehicle to the motor pool for "
            + ("hull repairs and component service." if v.hp < v.vt.hp else "component repairs or replacement."))
    if v is not None and quiet(game, v) and repairs(v):
        from .maintenance import fitters_near, call_truck
        if not fitters_near(game, v) and game.sector.control == p.side and game.turn - v.ai.get("fitters_requested", -9999) > 600:
            from .intelligence import radio_link
            # A nearby friendly unit can notice a disabled vehicle even with its radio out.
            witness = any(a.active and not a.downed and a.side == p.side and distance(a.pos, v.pos) <= 8
                          for a in game.actors if a is not p)
            if radio_link(game, p) or witness:
                v.ai["fitters_requested"] = game.turn
                call_truck(game, p.side, v.pos, why="damaged vehicle reported")
    if not p.ai.get("service_order") and p.rank >= 12 and p.rank < 18 and game.turn >= 1800 and \
            game.turn - p.ai.get("last_conference", -21600) >= 21600 and game.turn - p.fired_turn > 300:
        from .recognition import channel
        dest = destination(game, ("hq",))
        if channel(game) and dest:
            f = game.command.billet
            sup = f.parent if f else None
            grade = max(p.rank + 1, 14)
            who = sup.commander_label() if sup and sup.commander_grade() > p.rank else "the senior operations commander"
            p.ai["service_order"] = dict(kind="conference", issued=game.turn, authority=grade,
                who=who, how=channel(game), text="Report to higher headquarters for an operations conference.")
            game.msg(f"Orders from {who}: report to headquarters for a conference. The route is in T.", "radio")
    # Personal radios and other damaged kit are serviced at a staffed supply/workshop post.
    for a in game.actors:
        if not a.active or a.downed or a.suppression > 10 or game.turn - a.fired_turn < 120:
            continue
        staff = next((b for b in game.near(a.x, a.y, 4, a.side) if b is not a and b.active and not b.downed
                      and b.role in ("armourer", "motor_sergeant", "mechanic", "quartermaster")), None)
        if staff is None:
            continue
        damaged = next((it for it in a.inv if it.condition < .7 and it.t.kind in ("tool", "gun", "armor")), None)
        if damaged is None:
            continue
        from .sustain import take
        if take(game.sector, a.side, "parts", .1):
            damaged.condition = min(1., damaged.condition + .05)
            if a is p and damaged.condition >= .7:
                game.msg(f"{staff.rank_short} {staff.last_name} returns your {damaged.t.name}, serviceable again.", "good")
