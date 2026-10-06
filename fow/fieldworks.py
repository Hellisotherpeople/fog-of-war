"""Engineer works: men carry stores to a site and spend real working time there."""
from __future__ import annotations

from . import tiles as T
from .intelligence import distance

# name, resulting tile, man-seconds, material crates, requires engineer, installation kind
WORKS = {
    "foxhole": ("Foxhole", "foxhole", 7200, 0, False, None),
    "trench": ("Slit trench", "trench", 14400, 1, False, None),
    "sandbags": ("Sandbag breastwork", "sandbags", 1800, 2, False, None),
    "wire": ("Wire obstacle", "wire", 1200, 2, True, None),
    "gun_pit": ("Gun emplacement", "gun_pit", 21600, 2, True, None),
    "bunker": ("Concrete fighting position", "tobruk", 172800, 24, True, "fortress"),
    "hedgehog": ("Steel tank obstacle", "hedgehog", 7200, 8, True, None),
    "teeth": ("Concrete tank obstacle", "teeth", 43200, 12, True, None),
    "atditch": ("Anti-tank ditch", "atditch", 86400, 2, True, None),
    "camo_net": ("Camouflage shelter", "camo_net", 900, 1, False, None),
    "road": ("Road repair / surfacing", "road", 14400, 3, True, None),
    "bridge": ("Bridge span (one bay)", "bridge", 86400, 16, True, None),
    "wall": ("Masonry cover", "low_wall", 14400, 6, True, None),
    "hq": ("Field command post", "radio_set", 43200, 12, True, "hq"),
    "observation": ("Surveyed observation post", "lookout_post", 21600, 6, True, "observation"),
    "depot": ("Forward supply point", "ammo_stack", 43200, 10, True, "depot"),
    "aid": ("Field aid station", "redcross", 43200, 10, True, "aid"),
    "motor_pool": ("Field repair workshop", "machinery", 172800, 30, True, "motor_pool"),
    "airfield": ("Landing strip works", "runway", 691200, 80, True, "airfield"),
    "rail_yard": ("Railhead repair works", "rail", 345600, 50, True, "rail_yard"),
    "factory": ("Workshop reconstruction", "machinery", 691200, 100, True, "factory"),
    "food_depot": ("Food store and distribution point", "crates", 86400, 20, True, "food_depot"),
    "power_station": ("Generator station", "machinery", 345600, 60, True, "power_station"),
    "shelter": ("Civilian shelter", "bed", 172800, 25, True, "shelter"),
    "well": ("Water point", "well", 172800, 20, True, "well"),
}


def projects(game):
    return game.map.__dict__.setdefault("works", [])


def engineer(a):
    return a.role in ("engineer", "seabee", "mechanic", "motor_sergeant")


def tools(a):
    return a.has_tool("shovel") or a.has_tool("repair")


def source(game, side, point):
    sources = [(r["x"], r["y"]) for r in getattr(game.map, "gen_positions", [])
               if r.get("kind") in ("depot", "motor_pool", "factory", "rail_yard")
               and r.get("side") == side and not r.get("destroyed")]
    sources += [(v.x, v.y) for v in game.vehicles if v.active and v.side == side and v.ai.get("material_cargo", 0) > 0]
    return min(sources, key=lambda pos: distance(pos, point), default=None)


def footprint(kind, x, y):
    tile = WORKS[kind][1]
    if kind == "airfield":
        return [(xx, yy, "runway") for xx in range(x - 2, x + 3) for yy in range(y - 12, y + 13)]
    if kind == "rail_yard":
        return [(x, yy, "rail") for yy in range(y - 6, y + 7)]
    if WORKS[kind][5] and kind not in ("bunker", "observation", "well"):
        return [(xx, yy, tile if (xx, yy) == (x, y) else "camo_net")
                for xx in range(x - 2, x + 3) for yy in range(y - 2, y + 3)]
    return [(x, y, tile)]


def valid_site(game, kind, point):
    if kind not in WORKS:
        return False, "Unknown engineering work."
    for x, y, tile in footprint(kind, *point):
        if not game.map.in_bounds(x, y):
            return False, "The works would extend beyond this map."
        old = game.map.tile(x, y)
        if kind == "bridge":
            if not old.water and old.key not in ("bridge", "rubble", "crater"):
                return False, "Place a bridge bay across water or a damaged crossing."
        elif old.water or not old.walk or old.floor or old.key in ("foxhole", "trench", "tobruk"):
            return False, "The site needs open, dry ground or cleared rubble."
        if (x, y) in game.vehicle_at or (x, y) in game.map.mines:
            return False, "Clear the site of vehicles and mines first."
        if kind in ("foxhole", "trench", "gun_pit", "atditch") and not old.dig:
            return False, "This ground cannot be dug with field tools."
    return True, ""


def assign(game, sq, kind, point, automatic=False):
    ok, why = valid_site(game, kind, point)
    if not ok:
        return False, why
    skilled = WORKS[kind][4]
    if not any(a.active and not a.downed and tools(a) and (not skilled or engineer(a)) for a in sq.members):
        return False, "This work needs engineers with tools." if skilled else "No fit men with entrenching tools."
    if any(p["status"] not in ("complete", "cancelled") and
           (p["squad"] == sq.id or distance(p["point"], point) < 5) for p in projects(game)):
        return False, "A work party or site is already committed."
    depot = source(game, sq.side, point)
    if WORKS[kind][3] and depot is None:
        return False, "No material supply point. Bring a supply truck or establish a route to a depot."
    project = dict(id=len(projects(game)) + 1, kind=kind, point=tuple(point), squad=sq.id,
                   side=sq.side, work=0., status="collecting stores" if WORKS[kind][3] else "working",
                   source=depot, materials=0., carried=0., automatic=automatic, created=game.turn,
                   previous=sq.order)
    projects(game).append(project)
    sq.rep["construction"] = project["id"]
    sq.rep.pop("intent", None)
    from .ai import Order
    game.command.apply(game, sq, Order("defend", target=point, radius=5, issued=game.turn,
                                      src="ai" if automatic else "player"))
    return True, f"{WORKS[kind][0]} assigned; {WORKS[kind][3]} material crates, {WORKS[kind][2] // 3600} man-hours."


def cancel(game, sq):
    for p in projects(game):
        if p["squad"] == sq.id and p["status"] not in ("complete", "cancelled"):
            p["status"] = "cancelled"
            sq.order = p["previous"]
            sq.positions = {}
    sq.rep.pop("construction", None)


def act(game, a, visible):
    sq = a.squad
    if sq is None or not sq.rep.get("construction") or visible or a.suppression > 20:
        return None
    p = next((p for p in projects(game) if p["id"] == sq.rep["construction"]), None)
    if p is None or p["status"] in ("complete", "cancelled"):
        return None
    _, tile, required, materials, skilled, install = WORKS[p["kind"]]
    if not tools(a) or skilled and not engineer(a) or a.vehicle is not None:
        return None
    if game.turn - sq.last_contact < 60 or game.map.fire[a.x, a.y]:
        return None
    if a.stamina < 15 or a.__dict__.get("fatigue", 0) > 85:
        p["status"] = "work party resting"
        a.stamina = min(100, a.stamina + 3)
        return 1000
    from .ai import path_step
    from .sustain import take
    cargo = a.ai.get("works_cargo")
    goal = p["point"]
    if p["materials"] < materials and cargo is None:
        goal = source(game, a.side, p["point"])
        if goal is None:
            p["status"] = "waiting for a supply point"
            return 100
        if distance(a.pos, goal) <= 3:
            amount = min(2., materials - p["materials"] - p["carried"])
            if amount <= 0:
                return 100
            truck = next((v for v in game.vehicles if v.active and v.side == a.side
                          and (v.x, v.y) == goal and v.ai.get("material_cargo", 0) >= amount), None)
            if truck:
                truck.ai["material_cargo"] -= amount
            elif not take(game.sector, a.side, "materials", amount):
                p["status"] = "waiting for material stores"
                return 100
            a.ai["works_cargo"] = dict(project=p["id"], amount=amount)
            p["carried"] += amount
            return 500
    if distance(a.pos, goal) > (2 if cargo else 1):
        return path_step(game, a, *goal) or 100
    if cargo:
        if cargo["project"] == p["id"]:
            p["materials"] += cargo["amount"]
            p["carried"] = max(0., p["carried"] - cargo["amount"])
        a.ai.pop("works_cargo", None)
        return 500
    if p["materials"] < materials:
        return 100
    ok, why = valid_site(game, p["kind"], p["point"])
    if not ok:
        p["status"] = why
        return 100
    p["status"] = "working"
    from .skills import level, use
    # Work is paid in the same action clock as movement and combat.
    labor = 10 * (.65 + level(a, "construction") * .07)
    p["work"] += labor
    use(game, a, "construction", .15)
    a.stamina = max(0, a.stamina - .5)
    if p["work"] >= required:
        cells = footprint(p["kind"], *p["point"])
        # Do not seal someone inside a wall or overwrite a vehicle that drove onto the site.
        if any(not T.WALK[T.ID[t]] and ((x, y) in game.soldier_at or (x, y) in game.vehicle_at)
               for x, y, t in cells):
            p["status"] = "clear the site for completion"
            return 100
        for x, y, t in cells:
            game.map.set(x, y, t)
        game.map.refresh()
        game.terrain_dirty = True
        p["status"] = "complete"
        sq.rep.pop("construction", None)
        sq.order = p["previous"]
        sq.positions = {}
        if install:
            x, y = p["point"]
            rect = (min(c[0] for c in cells), min(c[1] for c in cells),
                    max(c[0] for c in cells) - min(c[0] for c in cells) + 1,
                    max(c[1] for c in cells) - min(c[1] for c in cells) + 1)
            rec = dict(kind=install, side=p["side"], x=x, y=y, rect=rect, built=True,
                       work_id=p["id"], critical_tile=tile)
            game.map.gen_positions.append(rec)
            record = [install, p["side"], True]
            rec["installation"] = record
            game.sector.installations.append(record)
            if install == "fortress":
                game.sector.fort = min(3, game.sector.fort + 1)
        if a.side == game.player.side and (game.can_see(*p["point"]) or game.command._can_report(game, sq)):
            game.msg(f"{sq.short or sq.name}: {WORKS[p['kind']][0]} ready.", "good")
    return 1000


def tick(game):
    # Carriers killed en route lose their load. It never appears at the building site.
    for p in projects(game):
        p["carried"] = sum(a.ai["works_cargo"]["amount"] for a in game.actors if a.active and
                           a.ai.get("works_cargo", {}).get("project") == p["id"])
    for rec in getattr(game.map, "gen_positions", []):
        if rec.get("built") and not rec.get("destroyed") and \
                game.map.t[rec["x"], rec["y"]] != T.ID[rec["critical_tile"]]:
            rec["destroyed"] = True
            match = rec.get("installation")
            if match:
                match[2] = False
    if game.turn % 120:
        return
    from .intent import staff_support
    staff_support(game)
    # Staff support follows a commander who has stopped, with the same rule for either army.
    from .data.ranks import LT_COL
    from .command import contact_point
    for side in ("allies", "axis"):
        officers = [a for a in game.actors if a.side == side and a.active and not a.downed and a.rank >= LT_COL
                    and game.turn - max(a.moved_turn, a.vehicle.moved_turn if a.vehicle else -999) > 180]
        if not officers:
            continue
        chief = max(officers, key=lambda a: a.rank)
        if any(r.get("kind") == "hq" and r.get("side") == side and not r.get("destroyed")
               and distance((r["x"], r["y"]), chief.pos) < 40 for r in game.map.gen_positions):
            continue
        workers = [q for q in game.squads if q.side == side and not q.gone and not q.player_led
                   and q.order.src != "player" and not q.rep.get("construction")
                   and game.turn - q.last_contact > 120 and contact_point(q)
                   and distance(contact_point(q), chief.pos) < 35
                   and any(engineer(a) and tools(a) for a in q.members)]
        if not workers:
            continue
        for dx, dy in ((6, 4), (-6, 4), (6, -4), (-6, -4)):
            ok, _ = assign(game, workers[0], "hq", (chief.x + dx, chief.y + dy), automatic=True)
            if ok:
                break
