"""Creating soldiers, squads, vehicles, the player, and populating a battlefield."""
from __future__ import annotations

import math
import random
from collections import Counter

import numpy as np
import tcod

from . import tiles as T
from .ai import Order, Squad, assign_positions
from .constants import ALLIES, AXIS, SIDES, other_side
from .data.items import ITEMS, ammo_id
from .data.nations import NATIONS, equip_sources, nco_rank, officer_rank, ordinal, random_name, unit_designation
from .data.roles import PLAYER_ROLE_WEIGHTS, ROLES, build_kit, squad_template
from .data.vehicles import VEHICLES
from .entities import Actor, Item, Vehicle

TRAITS = {
    "crack_shot": "Crack shot", "shaky": "Shaky hands", "brave": "Brave", "coward": "Faint-hearted",
    "lucky": "Lucky", "veteran": "Veteran", "green": "Green recruit", "strong": "Strong back",
    "brawler": "Brawler", "camouflaged": "Fieldcraft", "tough": "Tough as nails",
}

VEH_CLASSES = {
    "tank": ("tank", "ltank"), "td": ("td", "spg"), "atgun": ("atgun",), "aagun": ("aagun",),
    "ht": ("halftrack",), "truck": ("truck",), "car": ("car",), "armcar": ("armcar",),
    "fieldgun": ("fieldgun",), "tankette": ("tankette",), "lc": ("lc",),
}


def pick_vehicle(rng, nation, year, cls, include_zero=False) -> str | None:
    vtypes = VEH_CLASSES.get(cls, (cls,))
    srcs = equip_sources(nation, year) + [nation]
    for src in srcs:
        pool = [v for v in VEHICLES.values() if v.vtype in vtypes and src in v.nations
                and v.years[0] <= year < v.years[1] and (v.freq > 0 or include_zero)]
        if pool:
            return rng.choices(pool, [max(1, v.freq) for v in pool])[0].id
    return None


# ====================================================================== soldiers

def default_grade(rng, nation: str, role: str) -> int:
    """The rank a man in this job usually held (with the casualties' reshuffling)."""
    from .data import ranks as R
    if role in COMMAND_ROLES:
        return COMMAND_ROLES[role]
    if role == "officer":
        return rng.choice((R.LT2, R.LT2, R.LT))
    if role == "surgeon":
        return rng.choice((R.CAPTAIN, R.CAPTAIN, R.MAJOR))
    if role == "squad_leader":
        base = nco_rank(nation)
        return max(R.CORPORAL, base - (1 if rng.random() < 0.25 else 0))
    from .data.roles import ROLE_GRADES, SERVICE_ROLES
    if role in ("fighter_pilot", "bomber_pilot") and nation in ("usa", "japan", "ussr"):
        return rng.choice((R.LT2, R.LT2, R.LT))       # (their pilots were nearly all officers)
    if role in SERVICE_ROLES["air"] + SERVICE_ROLES["navy"]:
        lo, hi = ROLE_GRADES[role]
        return rng.choice([lo, lo, lo + (1 if hi > lo else 0), min(hi, lo + 2)])
    if role == "platoon_sergeant":
        return rng.choice((R.STAFF_SGT, R.PLATOON_SGT))
    if role == "first_sergeant":
        return R.FIRST_SGT
    if role == "sergeant_major":
        return R.SGT_MAJOR
    if role in ("lmg_gunner", "hmg_gunner"):
        return rng.choice((R.PFC, R.PFC, R.CORPORAL))
    if role in ("radioman", "medic", "mortarman", "sniper", "engineer", "flamethrower"):
        return rng.choice((R.PRIVATE, R.PFC, R.PFC, R.CORPORAL))
    if role == "tank_crew":
        return rng.choice((R.PRIVATE, R.PFC, R.CORPORAL))
    return rng.choice((R.PRIVATE, R.PRIVATE, R.PRIVATE, R.PFC, R.PFC, R.CORPORAL))


# senior roles the player can start in, and the grade that goes with each
COMMAND_ROLES = {"company_commander": 10, "battalion_commander": 12, "regiment_commander": 13,
                 "brigade_commander": 14, "division_commander": 15, "corps_commander": 16,
                 "army_commander": 17, "army_group_commander": 18}


def make_soldier(game, nation: str, role: str, rank: int | None = None, para=False) -> Actor:
    rng = game.rng
    doc = NATIONS[nation]["doctrine"]
    if rank is None:
        rank = default_grade(rng, nation, role)
    a = Actor(nation, role, rank, random_name(rng, nation))
    a.skill = max(1.0, min(10.0, rng.gauss(doc["training"], 1.4)))
    a.bravery = max(5.0, min(100.0, rng.gauss(50, 18)))
    a.morale = doc["morale"] + rng.uniform(-10, 10)
    if rng.random() < 0.18:
        a.traits.add("veteran")
        a.skill = min(10, a.skill + 1.5)
        a.morale += 8
    elif rng.random() < 0.18:
        a.traits.add("green")
        a.skill = max(1, a.skill - 1.5)
        a.morale -= 6
    if role == "sniper":
        a.skill = min(10, a.skill + 2)
        a.traits.add("camouflaged")
    from .data.roles import PACIFIC_THEATRES
    pac = game.theatre.get("id") in PACIFIC_THEATRES or \
        (game.map is not None and game.map.climate in ("tropical", "volcanic"))
    kit = build_kit(rng, nation, game.year, role, para=para, winter=game.map is not None and game.map.climate == "winter",
                    pacific=pac)
    apply_kit(a, kit, game.year)
    from .skills import roll
    roll(rng, a)                       # his skills: a roll round his training, with his job's floors under it
    from .flavor import stamp
    for it in a.inv:
        stamp(game, it, a)             # his rifle's serial, his tags, the letter from home
    return a


def rig_for(nation: str, year: float, role: str, weapon_id: str | None) -> str | None:
    from .data.items import RIGS
    table = None
    for src in [nation] + equip_sources(nation, year):
        if src in RIGS:
            table = RIGS[src]
            break
    if role == "medic":
        return "medic_bags"
    if role == "tank_crew":
        return "crew_belt"
    if table is None:
        table = {"rifle": "bandolier", "smg": "su_smg", "lmg": "lmg_belt", "carbine": "su_smg", "mg": "lmg_belt"}
    t = ITEMS[weapon_id] if weapon_id else None
    cat = t.cat if t is not None else "rifle"
    cls = {"smg": "smg", "assault": "smg", "lmg": "lmg", "hmg": "mg", "carbine": "carbine",
           "pistol": "carbine", "at_launcher": "carbine", "at_disposable": "rifle", "mortar": "carbine",
           "flamer": "carbine", "at_rifle": "carbine"}.get(cat, "rifle")
    if t is not None and t.get("magtype"):
        from .inventory import item_size
        size = item_size(ITEMS[t.magtype])
        if size == (2, 2):
            cls = "mg" if cat in ("hmg", "lmg") and t.feed == "belt" else ("lmg" if cat == "lmg" else "smg")
        elif size == (1, 2) and cls == "rifle":
            cls = "smg"
    rid = table.get(cls, table.get("rifle"))
    # make sure the magazines actually fit the webbing
    if t is not None and t.get("magtype"):
        from .inventory import item_size
        mw, mh = item_size(ITEMS[t.magtype])
        spec = ITEMS[rid].grids if rid in ITEMS else ()
        if not any((gw >= mw and gh >= mh) or (gw >= mh and gh >= mw) for gw, gh, _, allow in spec if not allow):
            rid = {(1, 2): "su_smg", (2, 2): "lmg_belt", (1, 1): "bandolier"}.get((mw, mh), "lmg_belt")
    return rid


def apply_kit(a: Actor, kit: dict, year: float = 1943.0):
    from .ammo import give_ammo
    from .data.items import PACKS
    from .inventory import stack_max
    inv = a.invent
    if kit.get("helmet"):
        inv.slots["head"] = Item(kit["helmet"])
        inv.slots["head"].where = "head"
    rid = rig_for(a.nation, year, a.role, kit.get("wield"))
    if rid:
        inv.slots["rig"] = Item(rid)
        inv.slots["rig"].where = "rig"
    items = list(kit["items"])
    wt = ITEMS[kit["wield"]] if kit.get("wield") else None
    if wt is not None and wt.cat == "at_launcher" and inv.slots["pack"] is None:
        inv.slots["pack"] = Item("sack")            # a rocket bag
        inv.slots["pack"].where = "pack"
    # radios ride in the pack slot, so they come first
    items.sort(key=lambda e: 0 if ITEMS[e[0]].tool == "radio" else 1 if ITEMS[e[0]].kind == "armor" else 2)
    guns = []
    if kit.get("wield"):
        w = Item(kit["wield"])
        a.wield(w)
        if w.t.kind == "gun":
            guns.append(w)
    if kit.get("sling"):
        sg = Item(kit["sling"])
        a.add_item(sg)
        if sg.t.kind == "gun":
            guns.append(sg)
    # other weapons in the kit first, so ammunition can be matched to them
    for iid, n in items:
        t = ITEMS[iid]
        if t.kind == "gun":
            for _ in range(n):
                g = Item(iid)
                if a.add_item(g) is not None:
                    guns.append(g)
    # the things a man keeps on him come first - tags round his neck, the letter in his breast pocket - so a
    # full set of pouches never leaves them behind
    items = sorted(items, key=lambda it_n: ITEMS[it_n[0]].tool not in ("dogtags", "letter", "photo"))
    for iid, n in items:
        t = ITEMS[iid]
        if t.kind == "gun":
            continue
        if iid == "backpack":
            if inv.slots["pack"] is None:
                inv.slots["pack"] = Item(PACKS.get(a.nation, "backpack"))
                inv.slots["pack"].where = "pack"
            continue
        if t.kind == "ammo":
            gun = next((g for g in guns if g.t.cal == t.cal), None)
            if gun is not None:
                give_ammo(a, gun, n)
            else:
                a.add_item(Item(iid, n))
            continue
        if t.kind == "armor" and t.slot == "body":
            if inv.slots["body"] is None:
                inv.slots["body"] = Item(iid)
                inv.slots["body"].where = "body"
                continue
        mx = stack_max(t)
        if t.kind in ("medical", "grenade", "clip") or mx > 1:
            left = n
            while left > 0:
                k = min(left, max(1, mx))
                a.add_item(Item(iid, k))
                left -= k
        else:
            for _ in range(n):
                a.add_item(Item(iid))


# ====================================================================== placement

def reachable(game):
    """Where a man can walk to from an edge of the map (through doors): a place outside it is a sealed pocket - a
    room with no door, the gap between two bunkers - and nobody should be put there.  None where it doesn't
    apply (aboard, or no way in from any edge)."""
    m = game.map
    if game.__dict__.get("domain", "land") != "land":
        return None
    key = (id(m), m.__dict__.get("walk_version", m.version))
    c = m.__dict__.get("_reach")
    if c is not None and c[0] == key:
        return c[1]
    walk = m.walk
    cost = np.where(walk, 1, 0).astype(np.int32)
    dist = tcod.path.maxarray(walk.shape, dtype=np.int32)
    edge = np.zeros(walk.shape, bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    dist[edge & walk] = 0
    tcod.path.dijkstra2d(dist, cost, 2, 3, out=dist)
    mask = dist < np.iinfo(np.int32).max
    if mask.sum() < walk.sum() * 0.3:
        mask = None                                # (an island, a sealed map: don't second-guess it)
    m._reach = (key, mask)
    return mask


def free_tile_near(game, x, y, radius=6, avoid_water=True, rng=None):
    m = game.map
    rng = rng or game.rng
    best = None
    reach = reachable(game)
    for r in range(0, radius + 1):
        cands = []
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                xx, yy = x + dx, y + dy
                if not m.in_bounds(xx, yy):
                    continue
                if not m.walk[xx, yy] or T.DOOR[m.t[xx, yy]] == 1:
                    continue
                if (xx, yy) in game.soldier_at or (xx, yy) in game.vehicle_at:
                    continue
                if avoid_water and m.water[xx, yy] >= 2:
                    continue
                if (xx, yy) in m.mines:
                    continue
                if reach is not None and not reach[xx, yy]:
                    continue
                cands.append((xx, yy))
        if cands:
            return rng.choice(cands)
    return best


def place(game, a, x, y, radius=6, avoid_water=True) -> bool:
    p = free_tile_near(game, x, y, radius, avoid_water)
    if p is None:
        p = free_tile_near(game, x, y, radius * 4, avoid_water)
    if p is None:
        return False
    a.x, a.y = p
    game.add_actor(a)
    return True


def edge_band_point(game, edge, rng, depth=(2, 12), lateral=None):
    m = game.map
    lat = lateral if lateral is not None else rng.uniform(0.08, 0.92)
    d = rng.randint(*depth)
    if edge == "N":
        return int(lat * (m.w - 1)), d
    if edge == "S":
        return int(lat * (m.w - 1)), m.h - 1 - d
    if edge == "W":
        return d, int(lat * (m.h - 1))
    return m.w - 1 - d, int(lat * (m.h - 1))


def facing_from_edge(edge) -> int:
    # vehicles face away from their own edge
    return {"N": 6, "S": 2, "W": 0, "E": 4}.get(edge, 0)


# ====================================================================== squads

def give_papers(a, game=None):
    """A paybook for everyone; NCOs a notebook; officers their orders, maps, the plan."""
    from .logistics import doc_for
    if a.is_player or a.role in ("quartermaster",):
        return
    it = Item(doc_for(a.rank))
    it.data = {"side": a.side, "nation": a.nation, "unit": a.unit, "grade": a.rank}
    if game is not None:
        it.data["written"] = game.turn
        it.data["pos"] = a.pos
        it.data["positions"] = [(b.id, b.x, b.y) for b in game.actors if b.side == a.side and b.active
                                and abs(b.x - a.x) + abs(b.y - a.y) <= (80 if a.rank >= 8 else 25)]
        if a.rank >= 10:
            from .intelligence import _snapshot
            it.data["reports"] = {(s.x, s.y): _snapshot(game.strategic, s, a.side, game.turn)
                                  for s in game.strategic.neighbors(game.sector) + [game.sector]}
    a.add_item(it, "pockets")


def apply_special(game, a, sid, unit_text=None):
    """Make a man one of a special unit: its weapons, kit, training, doctrine and name."""
    from .data.special import SPECIAL
    d = SPECIAL[sid]
    rng = game.rng
    a.unit_type = sid
    if d.get("service"):
        a.service = d["service"]
    for t in d.get("traits", []):
        a.traits.add(t)
    a.skill = max(1.0, min(10.0, a.skill + d.get("skill", 0)))
    a.morale = max(10.0, min(100.0, a.morale + d.get("morale", 0)))
    from .skills import UNIT_SKILLS, roll
    if a.__dict__.get("skills") is None:
        roll(rng, a)
    for k, floor in UNIT_SKILLS.get(sid, {}).items():
        a.skills[k] = round(min(10.0, max(a.skills.get(k, 0), floor + rng.gauss(0, 0.7))), 1)
    if "female" in d.get("flags", []):
        a.female = True
        if a.nation == "ussr":
            first = rng.choice(["Lyudmila", "Natalya", "Yevdokiya", "Marina", "Nadezhda", "Olga", "Irina", "Raisa",
                                "Klavdiya", "Roza", "Tatyana", "Mariya", "Yekaterina", "Polina"])
            last = a.name.split()[-1]
            if last.endswith(("ov", "ev", "in", "yn")):
                last += "a"
            elif last.endswith("iy"):
                last = last[:-2] + "aya"
            a.name = f"{first} {last}"
    guns = [w for w in d.get("weapons", []) if w in ITEMS]
    if guns and a.role not in ("agent", "medic", "radioman", "officer", "hmg_gunner", "hmg_assistant", "mortarman",
                               "at_soldier", "flamethrower") and rng.random() < 0.8:
        wid = rng.choice(guns)
        if a.weapon is None or a.weapon.tid != wid:
            old = a.weapon
            if old is not None and old.t.kind == "gun":
                a.remove_item(old)                    # handed in: the unit has its own
            w = Item(wid)
            a.add_item(w)
            a.wield(w)
            try:
                from .ammo import give_loads
                give_loads(a, w, 4)
            except Exception:
                pass
    for tid, n in d.get("kit", {}).items():
        if tid in ITEMS:
            a.add_item(Item(tid, n))
    if unit_text is None:
        k = rng.randint(1, d.get("k_max", 30))
        unit_text = d["unit"].format(c=rng.randint(1, 9), k=k, ko=ordinal(k), n=rng.choice(["A Squadron",
                                                                                        "B Squadron", "C Squadron"]))
    a.unit = unit_text


def maybe_special_squad(game, sq):
    """Now and then, a squad is something out of the ordinary."""
    from .data.special import SPECIAL, eligible
    rng = game.rng
    th = game.theatre
    tid = th.get("id", "")
    for sid, d in SPECIAL.items():
        w = d.get("ai", 0)
        if w <= 0 or not eligible(sid, sq.nation, game.year, tid):
            continue
        if sid == "waffen_ss" and any("SS" in x for x in th.get("divisions", {}).get(sq.nation, [])):
            w *= 6                                   # SS divisions fought here
        if sid in ("penal", "nkvd") and sq.kind not in ("rifle", "assault"):
            continue
        if rng.random() < w:
            k = rng.randint(1, d.get("k_max", 30))
            text = d["unit"].format(c=rng.randint(1, 9), k=k, ko=ordinal(k), n=rng.choice(["A Squadron", "B Squadron"]))
            for m in sq.members:
                apply_special(game, m, sid, text)
            sq.name = d["name"]
            sq.special = sid
            return sid
    return None


def make_squad(game, side, nation, kind, x, y, order=None, para=False, spread=3,
               place_members=True, name=None) -> Squad:
    rng = game.rng
    sq = Squad(side, nation, kind, name or f"{kind} squad")
    sq.order = order or Order("hold", target=(x, y))
    if kind == "volkssturm" and nation != "germany":
        kind = "rifle"
    roles = squad_template(rng, nation, game.year, kind)
    for role in roles:
        a = make_soldier(game, nation, role, para=para)
        a.squad = sq
        sq.members.append(a)
        if place_members:
            place(game, a, x + rng.randint(-spread, spread), y + rng.randint(-spread, spread), 6)
    if kind == "engineer" and nation == "usa" and game.year >= 1942 and game.theatre_id in (
            "guadalcanal42", "tarawa43", "saipan44", "iwojima45", "okinawa45"):
        for man in sq.members:
            if man.role == "engineer":
                man.role = "seabee"
                man.service = "navy"
                man.skills["construction"] = max(6., man.skills.get("construction", 0))
        sq.name = "Naval construction detachment"
    leaders = [m for m in sq.members if m.role in ("squad_leader", "officer")]
    sq.leader = leaders[0] if leaders else (max(sq.members, key=lambda m: m.rank) if sq.members else None)
    sq.initial = len(sq.members)
    unit = unit_designation(rng, nation, game.theatre.get("divisions", {}).get(nation))
    for m in sq.members:
        m.unit = unit
        give_papers(m, game)
    if kind in ("rifle", "assault", "mg", "sniper", "engineer") and not getattr(game, "first_battle_setup", False):
        maybe_special_squad(game, sq)
    game.squads.append(sq)
    return sq


def make_vehicle_squad(game, side, nation, cls, x, y, n=1, order=None, edge=None) -> Squad | None:
    rng = game.rng
    vid = pick_vehicle(rng, nation, game.year, cls)
    if vid is None:
        return None
    sq = Squad(side, nation, "tank" if cls in ("tank", "td") else cls, f"{VEHICLES[vid].name} section")
    sq.order = order or Order("hold", target=(x, y))
    face = facing_from_edge(edge) if edge else rng.randint(0, 7)
    for i in range(n):
        if i > 0 and rng.random() < 0.3:
            vid2 = pick_vehicle(rng, nation, game.year, cls) or vid
        else:
            vid2 = vid
        p, f = spot_and_facing(game, x + rng.randint(-5, 5), y + rng.randint(-5, 5), VEHICLES[vid2], facing=face)
        if p is None:
            continue
        v = Vehicle(vid2, side, nation, p[0], p[1], f)
        v.squad = sq
        sq.vehicles.append(v)
        game.add_vehicle(v)
    if not sq.vehicles:
        return None
    sq.initial = 4 * len(sq.vehicles)
    game.squads.append(sq)
    return sq


def vehicle_spot(game, x, y, vt, radius=10, facing=0):
    """Somewhere near (x, y) with room for the whole vehicle.  Returns the pivot tile, or None."""
    from .footprint import offsets, vehicle_size
    m = game.map
    L, W = vehicle_size(vt)
    water_ok = vt.water in ("water", "amphib")

    def fits(px, py, f):
        for dx, dy in offsets(L, W, f):
            xx, yy = px + dx, py + dy
            if not m.in_bounds(xx, yy):
                return False
            if (xx, yy) in game.vehicle_at or (xx, yy) in game.soldier_at:
                return False
            if vt.water == "water":
                if m.water[xx, yy] < 2:
                    return False
            elif not m.walk[xx, yy] or T.FLOOR[m.t[xx, yy]] or T.DOOR[m.t[xx, yy]]:
                return False
            elif m.water[xx, yy] >= 2 and not water_ok:
                return False
        return True

    for rad in (radius, radius * 2 + 4):
        for r in range(rad + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    if fits(x + dx, y + dy, facing):
                        return (x + dx, y + dy)
        # no room that way round: try the other headings
        for f in ((facing + 2) % 8, (facing + 4) % 8, (facing + 6) % 8):
            for r in range(rad + 1):
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        if max(abs(dx), abs(dy)) == r and fits(x + dx, y + dy, f):
                            vehicle_spot.last_facing = f
                            return (x + dx, y + dy)
    return None


vehicle_spot.last_facing = None


def spot_and_facing(game, x, y, vt, radius=10, facing=0):
    vehicle_spot.last_facing = None
    p = vehicle_spot(game, x, y, vt, radius, facing)
    f = vehicle_spot.last_facing if vehicle_spot.last_facing is not None else facing
    return p, f


INF_KIND = {"inf": "rifle", "mg": "mg", "mortar": "mortar", "at": "at", "hq": "hq",
            "sniper": "sniper", "eng": "engineer"}


def squad_kind_for(game, side, nation, unit):
    rng = game.rng
    k = INF_KIND.get(unit, "rifle")
    if k == "rifle":
        if nation == "germany" and "volkssturm" in game.theatre.get("special", ()) and rng.random() < 0.35:
            return "volkssturm"
        if nation in ("ussr", "germany") and game.year > 1942.5 and rng.random() < 0.15:
            return "assault"
    return k


# ====================================================================== populating a sector

LOCAL_CAP_INF = 13
LOCAL_CAP_VEH = 7


def split_local(units: Counter, cap_inf=LOCAL_CAP_INF, scale=1.0):
    """Split a sector's forces into what's on the map now and what arrives later
    (a bigger battlefield takes more at once)."""
    cap_inf = int(round(cap_inf * scale))
    cap_veh = int(round(LOCAL_CAP_VEH * scale))
    inf_keys = ["inf", "mg", "mortar", "at", "hq", "sniper", "eng"]
    veh_keys = ["tank", "td", "atgun", "ht"]
    now = Counter()
    later = Counter()
    n_inf = 0
    for k in inf_keys:
        for _ in range(units.get(k, 0)):
            if n_inf < cap_inf:
                now[k] += 1
                n_inf += 1
            else:
                later[k] += 1
    n_veh = 0
    for k in veh_keys:
        for _ in range(units.get(k, 0)):
            if n_veh < cap_veh:
                now[k] += 1
                n_veh += 1
            else:
                later[k] += 1
    return now, later


def pick_nation(game, side):
    weights = game.theatre["sides"][side]
    if side == game.player_side and game.player_nation:
        if game.rng.random() < 0.85:
            return game.player_nation
    return game.rng.choices([n for n, _ in weights], [w for _, w in weights])[0]


def populate(game, sector, att_side, att_edge):
    """Fill the freshly generated or loaded map with the sector's forces."""
    rng = game.rng
    m = game.map
    positions = getattr(m, "gen_positions", []) or []
    def_side = other_side(att_side) if att_side else None
    special = game.theatre.get("special", set())
    for side in SIDES:
        units = sector.units[side]
        if sum(units.values()) == 0:
            continue
        is_att = side == att_side
        now, later = split_local(units, cap_inf=13 if is_att or att_side is None else 9,
                                 scale=game.__dict__.get("troop_scale", 1.0))
        edge = game.home_edge(side)
        paradrop = (f"paradrop_{side}" in special) and game.first_battle and not is_att or \
                   (f"paradrop_{side}" in special and game.first_battle)
        landing = is_att and "landing" in special and sector.biome == "beach" and game.first_battle
        # attackers: the first wave is on the map, the rest trickle in
        wave_now = now
        if is_att and not paradrop:
            wave_now = Counter()
            for k, n in now.items():
                first = max(1, int(round(n * 0.55))) if n else 0
                wave_now[k] = first
                later[k] += n - first
        spawn_units(game, side, wave_now, edge, is_att, positions, paradrop, landing)
        if later:
            game.schedule_wave(side, later, edge, delay=rng.randint(120, 300), landing=landing)
    # installation assets (on a sector we've been to before: the people and vehicles, not the stores again)
    fresh = not getattr(m, "loaded", False)
    for rec in positions:
        if rec.get("spots") is not None and rec.get("side"):
            spawn_installation(game, rec, things=fresh)
    ensure_aid_posts(game)
    from .floors import place_upstairs
    place_upstairs(game)                  # the defenders' snipers in the church towers
    _short_of_ammunition(game)            # what the roads behind didn't bring up
    # each side's company ammunition point, behind its own line
    if sector.biome != "sea":
        for side in SIDES:
            if sum(sector.units[side].values()) == 0:
                continue
            edge = game.home_edge(side)
            if edge is None:
                continue
            if "landing" in special and side == att_side and sector.biome == "beach" and game.first_battle:
                continue           # it comes ashore later, if at all
            if logistics_supply(game, side) < 0.15:
                continue            # cut off: the ammunition point is empty
            for k in range(rng.choice((1, 1, 2))):
                x, y = edge_band_point(game, edge, rng, depth=(3, 9))
                pt = free_tile_near(game, x, y, 8)
                if pt is not None:
                    if fresh:
                        m.add_item(pt[0], pt[1], Item("ammo_crate"))    # (crates are saved with the map)
                    if k == 0:
                        rear_staff(game, side, pick_nation(game, side), pt[0], pt[1], "quartermaster",
                                   "company supply")
    # preparatory bombardment on the defenders
    if att_side and not any(s.startswith("paradrop") for s in special) and game.first_battle:
        lvl = game.theatre["arty"].get(att_side, 0.5)
        if rng.random() < lvl:
            for o in m.objectives:
                if rng.random() < 0.6:
                    game.support.barrage(att_side, o.x, o.y, 8, int(20 * lvl) + 6,
                                         delay=rng.randint(5, 90))


def spawn_units(game, side, units: Counter, edge, is_att, positions, paradrop=False, landing=False, wave=False):
    rng = game.rng
    m = game.map
    objs = m.objectives
    nation_cache = pick_nation(game, side)
    squads = []
    # infantry
    for unit, n in units.items():
        if unit in ("tank", "td", "atgun", "ht"):
            continue
        for _ in range(n):
            nat = nation_cache if rng.random() < 0.85 else pick_nation(game, side)
            kind = squad_kind_for(game, side, nat, unit)
            if paradrop:
                x, y = rng.randint(10, m.w - 10), rng.randint(10, m.h - 10)
                sq = make_squad(game, side, nat, kind, x, y, para=True, place_members=False)
                for a in sq.members:
                    paradrop_place(game, a, x, y)
                sq.order = Order("move", target=(x, y), issued=game.turn)
            elif landing:
                sq = make_squad(game, side, nat, kind, 0, 0, place_members=False)
                embark_landing(game, sq, edge)
            elif is_att or (wave and edge is not None):
                # attackers - and reinforcements for either side - march in from their own edge
                x, y = edge_band_point(game, edge, rng)
                sq = make_squad(game, side, nat, kind, x, y)
                if not is_att:
                    objs = game.map.objectives
                    if objs:
                        oi = min(range(len(objs)), key=lambda i: (objs[i].x - x) ** 2 + (objs[i].y - y) ** 2)
                        sq.order = Order("defend", obj=oi, radius=objs[oi].radius, issued=game.turn)
                        sq.arrived = False
            else:
                sq = make_squad(game, side, nat, kind, 0, 0, place_members=False)
                defend_place(game, sq, positions)
            squads.append(sq)
    # vehicles
    for unit, n in units.items():
        if unit not in ("tank", "td", "atgun", "ht"):
            continue
        nat = nation_cache
        for _ in range(n):
            if unit == "atgun":
                if is_att:
                    # towed guns come up behind the assault
                    x, y = edge_band_point(game, edge, rng, depth=(2, 6))
                    make_vehicle_squad(game, side, nat, "atgun", x, y, 1, Order("hold", target=(x, y)), edge=edge)
                    continue
                spot = at_gun_spot(game, side)
                sq = make_vehicle_squad(game, side, nat, "atgun", spot[0], spot[1], 1,
                                        Order("hold", target=spot), edge=game.home_edge(other_side(side)))
                if sq:
                    for v in sq.vehicles:
                        v.facing = facing_toward_edge(game.home_edge(other_side(side)))
                continue
            if unit == "ht":
                x, y = edge_band_point(game, edge, rng) if is_att else near_objective_point(game, side)
                sq = make_vehicle_squad(game, side, nat, "ht", x, y, 1, edge=edge)
                if sq is None:
                    # no half-tracks in this army this year: the infantry who'd have ridden in one walk
                    inf = make_squad(game, side, nat, "rifle", x, y)
                    squads.append(inf)
                    continue
                inf = make_squad(game, side, nat, "rifle", x, y, place_members=False)
                v = sq.vehicles[0]
                for a in inf.members:
                    if len(v.passengers) < v.vt.seats:
                        a.vehicle = v
                        a.x, a.y = v.x, v.y
                        v.passengers.append(a)
                        game.actors.append(a)
                    else:
                        place(game, a, x, y)
                inf.vehicles = []
                v.squad = inf
                inf.vehicles.append(v)
                game.squads.remove(sq)
                squads.append(inf)
                continue
            if landing:
                game.schedule_wave(side, Counter({unit: 1}), edge, delay=rng.randint(240, 600), landing=False)
                continue       # armour lands with a later wave
            x, y = edge_band_point(game, edge, rng, depth=(3, 14)) if is_att else near_objective_point(game, side)
            sq = make_vehicle_squad(game, side, nat, unit, x, y, 1, edge=edge)
            if sq is None and unit == "td":
                # no tank destroyers in this army this year: what did the job was a tank
                sq = make_vehicle_squad(game, side, nat, "tank", x, y, 1, edge=edge)
            if sq:
                squads.append(sq)
    return squads


def facing_toward_edge(edge) -> int:
    return {"N": 2, "S": 6, "W": 4, "E": 0}.get(edge, 0)


def near_objective_point(game, side):
    rng = game.rng
    objs = game.map.objectives
    if objs:
        o = rng.choice(objs)
        return o.x + rng.randint(-8, 8), o.y + rng.randint(-8, 8)
    return game.map.w // 2, game.map.h // 2


def at_gun_spot(game, side):
    rng = game.rng
    m = game.map
    enemy_edge = game.home_edge(other_side(side))
    objs = m.objectives
    o = rng.choice(objs) if objs else None
    cx, cy = (o.x, o.y) if o else (m.w // 2, m.h // 2)
    # a little in front of the objective, toward the enemy
    off = {"N": (0, -6), "S": (0, 6), "W": (-6, 0), "E": (6, 0)}.get(enemy_edge, (0, 0))
    return cx + off[0] + rng.randint(-8, 8), cy + off[1] + rng.randint(-5, 5)


def defend_place(game, sq, positions):
    """Put a defending squad into positions around an objective."""
    rng = game.rng
    m = game.map
    objs = m.objectives
    # choose an objective (spread defenders)
    counts = Counter(s.order.obj for s in game.squads if s.side == sq.side and s.order.kind == "defend")
    if objs:
        oi = min(range(len(objs)), key=lambda i: counts.get(i, 0) + rng.random() * 0.8)
        o = objs[oi]
        sq.order = Order("defend", obj=oi, radius=o.radius, issued=game.turn)
        if o.owner is None:
            o.owner = sq.side                 # (a ground someone else holds has to be taken, not walked onto)
        cx, cy = o.x, o.y
    else:
        cx, cy = m.w // 2, m.h // 2
        sq.order = Order("hold", target=(cx, cy))
    # MG teams and some squads prefer prepared positions
    prepared = [p for p in positions if p.get("kind") in ("bunker", "mg_nest", "trench", "foxhole")
                and not p.get("taken")]
    want_prepared = sq.kind in ("mg", "rifle", "volkssturm", "at") and prepared and rng.random() < 0.75
    if want_prepared:
        pref = [p for p in prepared if (sq.kind == "mg") == (p["kind"] in ("bunker", "mg_nest"))] or prepared
        p = min(pref, key=lambda p: math.hypot(p["x"] - cx, p["y"] - cy) + rng.random() * 30)
        p["taken"] = True
        cx, cy = p["x"], p["y"]
        tiles = p.get("tiles")
        if p["kind"] == "bunker" and p.get("rect"):
            x0, y0, bw, bh = p["rect"]
            inner = [(x, y) for x in range(x0 + 1, x0 + bw - 1) for y in range(y0 + 1, y0 + bh - 1)
                     if m.walk[x, y] and (x, y) not in game.soldier_at and (x, y) not in game.vehicle_at
                     and m.water[x, y] < 2]
            rng.shuffle(inner)
            for a, (x, y) in zip(sq.members, inner):
                a.x, a.y = x, y
                game.add_actor(a)
                a.stance = 1
        elif tiles:
            spots = [t for t in tiles if (t[0], t[1]) not in game.soldier_at and m.walk[t[0], t[1]]
                     and (t[0], t[1]) not in game.vehicle_at
                     and m.water[t[0], t[1]] < 2 and (t[0], t[1]) not in m.mines]
            step = max(1, len(spots) // max(1, len(sq.members)))
            chosen = spots[::step]
            rng.shuffle(chosen)
            for a, (x, y) in zip(sq.members, chosen):
                a.x, a.y = x, y
                game.add_actor(a)
                a.stance = 1
        sq.arrived = True
    # anyone not yet placed: use assigned positions around the objective
    unplaced = [a for a in sq.members if (a.x, a.y) == (0, 0) or game.soldier_at.get((a.x, a.y)) is not a]
    if unplaced:
        sq.arrived = True
        tmp_leader = unplaced[0]
        tmp_leader.x, tmp_leader.y = cx, cy
        assign_positions(game, sq)
        for a in unplaced:
            p = sq.positions.get(a.id)
            if p and p not in game.soldier_at and p not in game.vehicle_at:
                a.x, a.y = p
                game.add_actor(a)
            else:
                place(game, a, cx, cy, 8)
            a.stance = 1 if m.pos_cover[a.x, a.y] > 30 else 0
    if sq.leader is None and sq.members:
        sq.leader = sq.members[0]


def paradrop_place(game, a, x, y):
    rng = game.rng
    m = game.map
    px = int(x + rng.gauss(0, 14))
    py = int(y + rng.gauss(0, 14))
    px = max(1, min(m.w - 2, px))
    py = max(1, min(m.h - 2, py))
    tid = m.t[px, py]
    d = T.DEFS[int(tid)]
    fate = None
    if d.key.startswith("tree") or d.key in ("pine", "olive", "palm"):
        fate = "tree"
    elif d.water >= 2:
        fate = "water"
    elif d.key.startswith("wall") or d.key in ("cliff", "machinery"):
        fate = "hard"
    if fate in ("tree", "hard") or not m.walk[px, py]:
        p = free_tile_near(game, px, py, 5, avoid_water=False)
        if p is None:
            p = free_tile_near(game, px, py, 20)
        if p is None:
            return
        px, py = p
    if (px, py) in game.soldier_at:
        p = free_tile_near(game, px, py, 5, avoid_water=False)
        if p is None:
            return
        px, py = p
    a.x, a.y = px, py
    game.add_actor(a)
    a.stance = 2
    if fate == "tree":
        a.entangled = rng.randint(8, 25)
        a.ai["drop_fate"] = "tree"
    elif fate == "hard":
        a.body.damage(rng, rng.choice(("l_leg", "r_leg")), rng.uniform(15, 50), "blunt")
        a.ai["drop_fate"] = "hard"
    elif fate == "water":
        a.ai["drop_fate"] = "water"
    # heavy weapons came down in separate containers; some are simply lost
    if rng.random() < 0.15 and a.weapon is not None and a.weapon.t.weight > 5:
        lost = a.weapon
        a.remove_item(lost)
        a.weapon = None
        a.ai["lost_weapon"] = lost.t.name


def embark_landing(game, sq, edge):
    """Put an attacking squad into a landing craft offshore."""
    rng = game.rng
    m = game.map
    vid = "lcvp"
    face = facing_from_edge(edge)
    for tries in range(40):
        x, y = edge_band_point(game, edge, rng, depth=(1, 8))
        if m.water[x, y] >= 2 and (x, y) not in game.vehicle_at:
            spot = vehicle_spot(game, x, y, VEHICLES[vid], 3, face)
            if spot is not None:
                x, y = spot
                break
    else:
        # no sea: just land them on the edge
        for a in sq.members:
            place(game, a, *edge_band_point(game, edge, rng))
        return
    v = Vehicle(vid, sq.side, sq.nation, x, y, facing_from_edge(edge))
    v.squad = sq
    sq.vehicles.append(v)
    game.add_vehicle(v)
    for a in sq.members:
        a.vehicle = v
        a.x, a.y = v.x, v.y
        v.passengers.append(a)
        game.actors.append(a)
    sq.order = Order("attack", obj=None, target=None)


def spawn_installation(game, rec, things=True):
    """The guns, vehicles and people of an installation - and, the first time, its stores (`things`)."""
    rng = game.rng
    side = rec["side"]
    if not things:
        from .base import intact
        if not intact(game, rec):
            return                            # taken or destroyed since we were last here
    nat = pick_nation(game, side)
    m = game.map
    guns_placed = False
    if rec.get("kind") == "artillery" and game.support is not None:
        # the batteries that are here on the war map, gun for gun (fires.py)
        try:
            guns_placed = bool(game.support.fires.place_guns(game, rec))
        except Exception:
            import os
            if os.environ.get("FOW_DEBUG"):
                raise
    for spot in rec.get("spots", []):
        kind, x, y = spot
        if kind == "howitzer" and guns_placed:
            continue
        if kind in ("howitzer", "aagun", "atgun"):
            cls = {"howitzer": "fieldgun", "aagun": "aagun", "atgun": "atgun"}[kind]
            vid = pick_vehicle(rng, nat, game.year, cls, include_zero=True)
            if vid is None:
                continue
            p, f = spot_and_facing(game, x, y, VEHICLES[vid], 3, facing_toward_edge(game.home_edge(other_side(side))))
            if p is None:
                continue
            v = Vehicle(vid, side, nat, p[0], p[1], f)
            sq = Squad(side, nat, "atgun", f"{VEHICLES[vid].name} crew")
            sq.no_count = True
            sq.order = Order("hold", target=p)
            v.squad = sq
            sq.vehicles.append(v)
            game.squads.append(sq)
            game.add_vehicle(v)
            if kind == "howitzer":
                v.ai["battery"] = True
        elif kind in ("truck", "car", "ambulance", "tank_parked"):
            cls = {"truck": "truck", "car": "car", "ambulance": "truck", "tank_parked": "tank"}[kind]
            vid = "ambulance" if kind == "ambulance" else pick_vehicle(rng, nat, game.year, cls)
            if vid is None:
                continue
            p, f = spot_and_facing(game, x, y, VEHICLES[vid], 3, rng.randint(0, 7))
            if p is None:
                continue
            v = Vehicle(vid, side, nat, p[0], p[1], f)
            if kind == "tank_parked" and rng.random() < 0.5:
                v.engine = False       # under repair
            v.crew = 0 if kind in ("truck", "car", "ambulance") else v.crew
            v.abandoned = v.crew == 0
            game.add_vehicle(v)
        elif kind == "crate":
            if things:
                m.add_item(x, y, Item("ammo_crate"))
        elif kind == "medkit" and things:
            m.add_item(x, y, Item("medkit"))
            m.add_item(x, y, Item("bandage", 6))
            m.add_item(x, y, Item("morphine", 3))
            m.add_item(x, y, Item("plasma", 2))
        elif kind == "guards":
            sq = make_squad(game, side, nat, "rifle", x, y)
            sq.no_count = True
            sq.order = Order("defend", target=(x, y), radius=8)
            sq.arrived = True
        elif kind == "aidstaff":
            aid_staff(game, side, nat, x, y)
        elif kind == "qm":
            rear_staff(game, side, nat, x, y, "quartermaster", "supply depot")
        elif kind == "intel":
            rear_staff(game, side, nat, x, y, "intel", "intelligence")
    if not rec.get("no_staff"):
        from .base import spawn_staff
        spawn_staff(game, rec)


def rear_staff(game, side, nat, x, y, role, name):
    """A quartermaster at a depot, a supply sergeant at an ammunition point, an intelligence officer at HQ."""
    sq = Squad(side, nat, "rear", name)
    sq.no_count = True
    sq.order = Order("hold", target=(x, y), radius=3)
    sq.arrived = True
    a = make_soldier(game, nat, role, rank={"quartermaster": 4, "intel": 9}.get(role, 3))
    a.squad = sq
    sq.members.append(a)
    place(game, a, x, y, 3)
    sq.leader = a
    sq.initial = 1
    game.squads.append(sq)
    return a


def aid_staff(game, side, nat, x, y):
    """A surgeon and his orderlies."""
    sq = Squad(side, nat, "aid", "aid station")
    sq.no_count = True
    sq.order = Order("hold", target=(x, y), radius=6)
    sq.arrived = True
    for role in ("surgeon", "medic", "medic"):
        a = make_soldier(game, nat, role, rank=11 if role == "surgeon" else None)
        a.squad = sq
        sq.members.append(a)
        place(game, a, x, y, 4)
    sq.leader = sq.members[0]
    sq.initial = len(sq.members)
    game.squads.append(sq)
    return sq


def logistics_supply(game, side) -> float:
    from .logistics import sector_supply
    return sector_supply(game, side)


def ensure_aid_posts(game):
    """Every side on the field has somewhere to take its wounded: an aid station, or a battalion aid post."""
    from . import tiles as T
    m = game.map
    recs = getattr(m, "gen_positions", None)
    if recs is None:
        m.gen_positions = recs = []
    for side in SIDES:
        if not any(a.side == side for a in game.actors):
            continue
        if any(r.get("kind") == "aid" and r.get("side") == side for r in recs):
            continue
        edge = game.home_edge(side)
        if edge is None:
            continue
        x, y = edge_band_point(game, edge, game.rng, depth=(5, 11))
        # coming in from the sea: the aid post is on the first dry ground, not in the surf
        ix, iy = {"N": (0, 1), "S": (0, -1), "W": (1, 0), "E": (-1, 0)}[edge]
        dry = 0
        for _ in range(max(m.w, m.h)):
            if not m.in_bounds(x, y):
                break
            dry = dry + 1 if (m.water[x, y] == 0 and m.walk[x, y] and
                              T.DEFS[int(m.t[x, y])].key not in ("pier", "bridge")) else 0
            if dry >= 5:
                break
            x, y = x + ix, y + iy
        x, y = max(1, min(m.w - 2, x)), max(1, min(m.h - 2, y))
        pt = free_tile_near(game, x, y, 10)
        if pt is None or m.water[pt[0], pt[1]] or T.DEFS[int(m.t[pt])].key in ("pier", "bridge"):
            continue
        x, y = pt
        rect = (max(1, x - 4), max(1, y - 3), 9, 7)
        # a few stretchers and a red cross on the ground
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = x + dx, y + dy + 2
            if m.in_bounds(xx, yy) and m.walk[xx, yy] and not T.WATER[m.t[xx, yy]]:
                m.t[xx, yy] = T.ID["redcross"]
        for k in range(-2, 3, 2):
            xx, yy = x + k, y - 1
            if m.in_bounds(xx, yy) and m.walk[xx, yy] and (xx, yy) not in game.soldier_at and not m.water[xx, yy]:
                m.t[xx, yy] = T.ID["bed"]
        m.refresh()
        rec = dict(kind="aid", side=side, x=x, y=y, rect=rect, name="the battalion aid post",
                   spots=[("aidstaff", x, y)], no_staff=True)      # (the doctor and his orderlies: no chaplain)
        recs.append(rec)
        spawn_installation(game, rec)


# ====================================================================== player

def _edge_distance(game, pt, edge):
    if pt is None or edge is None:
        return 0
    m = game.map
    return {"N": pt[1], "S": m.h - 1 - pt[1], "W": pt[0], "E": m.w - 1 - pt[0]}.get(edge, 0)


def create_player(game, nation: str, role: str | None = None) -> tuple[Actor, list[str]]:
    """Create the player's soldier, insert them into a squad, return (actor, briefing lines)."""
    rng = game.rng
    side = NATIONS[nation]["side"]
    if role is None:
        roles = list(PLAYER_ROLE_WEIGHTS)
        role = rng.choices(roles, [PLAYER_ROLE_WEIGHTS[r] for r in roles])[0]
    notes = []
    # tank crew only where there are tanks to crew
    my_tanks = [sq for sq in game.squads if sq.side == side and sq.vehicles and
                any(v.vt.vtype in ("tank", "td", "ltank", "spg") and v.active for v in sq.vehicles)]
    my_tanks = [sq for sq in my_tanks if getattr(sq, "nation", None) == nation] or my_tanks
    assigned = game.__dict__.get("_starting_vehicle")
    if assigned is not None and game.setup.get("vehicle"):
        my_tanks = [assigned.squad]
    if role == "tank_crew" and not my_tanks:
        role = "rifleman"
    my_guns = [v for v in game.vehicles if v.side == side and v.ai.get("battery") and v.active and v.squad is not None]
    my_guns = [v for v in my_guns if v.nation == nation] or my_guns
    if role == "artilleryman" and not my_guns:
        role = "rifleman"
    special = game.theatre.get("special", set())
    para = f"paradrop_{side}" in special and game.first_battle
    p = make_soldier(game, nation, role, para=para)
    p.is_player = True
    # traits
    pool = list(TRAITS)
    for t in rng.sample(pool, rng.choice((0, 1, 1, 2))):
        if t in ("veteran", "green") and ("veteran" in p.traits or "green" in p.traits):
            continue
        p.traits.add(t)
    if "tough" in p.traits:
        for k in p.body.max:
            p.body.max[k] = int(p.body.max[k] * 1.15)
            p.body.hp[k] = p.body.max[k]
    if "strong" in p.traits:
        pass
    if "brave" in p.traits:
        p.morale += 15
    p.unit = unit_designation(rng, nation, game.theatre.get("divisions", {}).get(nation))
    # -- find a squad
    want = {"lmg_gunner": "rifle", "lmg_assistant": "rifle", "rifleman": "rifle", "smg_gunner": "rifle",
            "squad_leader": "rifle", "at_soldier": "at", "medic": "rifle", "radioman": "hq",
            "officer": "hq", "sniper": "sniper", "engineer": "engineer", "mortarman": "mortar",
            "hmg_gunner": "mg", "hmg_assistant": "mg", "flamethrower": "engineer",
            "volkssturm": "volkssturm", "surgeon": "aid", "platoon_sergeant": "rifle", "first_sergeant": "hq",
            "sergeant_major": "hq"}.get(role, "hq" if role in COMMAND_ROLES else "rifle")
    mine = [sq for sq in game.squads if sq.side == side and sq.members]
    ours = [sq for sq in mine if getattr(sq, "nation", None) == nation]
    mine = ours or mine                              # (a US soldier in a US section, not a British one)
    placed = False
    if role == "artilleryman":
        # a number on a gun: the layer, who sets the sights and pulls the lanyard
        v = rng.choice(my_guns)
        sq = v.squad
        p.vehicle = v
        v.crew_actors.append(p)
        v.player_crewed = True
        v.player_station = "gunner"
        game.actors.append(p)
        p.squad = sq
        sq.members.append(p)
        p.x, p.y = v.x, v.y
        placed = True
        name = sq.name.split(", gun")[0]
        notes.append(f"You're the layer on a {v.vt.name} of {name}. When a fire mission comes down, your orders say "
                     f"where: Enter lays the gun and fires it. (e: seats and getting out)")
    elif role == "tank_crew":
        sq = rng.choice(my_tanks)
        v = assigned if assigned is not None and game.setup.get("vehicle") else rng.choice([v for v in sq.vehicles if v.active])
        p.vehicle = v
        v.crew_actors.append(p)
        v.player_crewed = True
        from .crew import stations
        from .vdamage import hatch_user
        # the commander's seat - or, in a two-man tank, the gunner's, who commands as well
        v.player_station = "commander" if "commander" in stations(v.vt) else hatch_user(v) or stations(v.vt)[0]
        game.actors.append(p)
        p.squad = sq
        sq.members.append(p)
        sq.leader = p
        sq.player_led = True
        p.x, p.y = v.x, v.y
        placed = True
        notes.append(f"You command a {v.vt.name}. Your crew drive and fight it on your word. "
                     f"(e to change seats)")
    else:
        cands = [sq for sq in mine if sq.kind == want] or [sq for sq in mine if sq.kind == "rifle"] or mine
        if role in COMMAND_ROLES:
            cands = [sq for sq in mine if sq.kind == "hq"]
            if cands and COMMAND_ROLES[role] >= 12:
                # senior commanders keep their headquarters back from the line
                e = game.home_edge(side)
                cands.sort(key=lambda s2: _edge_distance(game, s2.anchor(), e))
                cands = cands[:1]
        sq = rng.choice(cands) if cands else None
        if sq is None and role in COMMAND_ROLES:
            e = game.home_edge(side)
            x, y = edge_band_point(game, e, rng, depth=(4, 14)) if e else (game.map.w // 2, game.map.h // 2)
            sq = make_squad(game, side, nation, "hq", x, y)
        if sq is None:
            from .spawn import make_squad as _ms
            e = game.home_edge(side)
            x, y = edge_band_point(game, e, rng)
            sq = make_squad(game, side, nation, want, x, y)
        # take the place of a matching member
        same = [m for m in sq.members if m.role == role] or \
            ([m for m in sq.members if m.role == "officer"] if role in COMMAND_ROLES else []) or \
            [m for m in sq.members if m.role == "rifleman"]
        if same:
            old = same[0]
            p.x, p.y = old.x, old.y
            game.remove_actor(old)
            if old.vehicle is not None:
                v = old.vehicle
                if old in v.passengers:
                    v.passengers.remove(old)
                p.vehicle = v
                p.x, p.y = v.x, v.y
                v.passengers.append(p)
                game.actors.append(p)
            else:
                game.add_actor(p)
            sq.members[sq.members.index(old)] = p
            if sq.leader is old:
                sq.leader = p
        else:
            anc = sq.anchor() or (game.map.w // 2, game.map.h // 2)
            if sq.members and sq.members[0].vehicle is not None:
                v = sq.members[0].vehicle
                p.vehicle = v
                p.x, p.y = v.x, v.y
                v.passengers.append(p)
                game.actors.append(p)
            else:
                place(game, p, anc[0], anc[1])
            sq.members.append(p)
        p.squad = sq
        placed = True
        for m in sq.members:
            m.unit = p.unit
        if role in ("squad_leader", "officer", "platoon_sergeant", "first_sergeant", "sergeant_major") or \
                role in COMMAND_ROLES:
            sq.leader = p
            sq.player_led = True
            sq.order = Order("follow", issued=game.turn, src="player")
        if role in COMMAND_ROLES and COMMAND_ROLES[role] >= 14:
            # a general travels with staff: an aide, a runner, the guard
            anc = (p.x, p.y)
            for r2, g2 in (("officer", 10), ("rifleman", 2), ("rifleman", 1)):
                a2 = make_soldier(game, nation, r2, rank=g2)
                a2.squad = sq
                a2.unit = p.unit
                sq.members.append(a2)
                place(game, a2, anc[0], anc[1], 3)
            notes.append("Your staff is with you: an aide, a runner and a guard. The radio keeps you "
                         "in touch with the front.")
    # nationality of squad-mates follows the player
    # -- unfair starts
    roll = rng.random()
    b = p.body
    if roll < 0.08 and p.vehicle is None:
        part = rng.choice(("l_arm", "r_arm", "l_leg", "torso"))
        b.damage(rng, part, rng.uniform(10, 28), "fragment")
        notes.append(f"You were hit before it even started. Your {part.replace('l_', 'left ').replace('r_', 'right ')} is bleeding.")
    elif roll < 0.13 and p.vehicle is None and not para:
        # straggler: separated from the squad
        e = game.home_edge(side)
        x, y = edge_band_point(game, e, rng, depth=(10, 40))
        game.remove_actor(p)
        place(game, p, x, y, 10)
        notes.append("You got separated from your squad in the confusion. You're on your own.")
    elif roll < 0.17:
        game.support.barrage(other_side(side), p.x, p.y, 5, 16, delay=rng.randint(4, 12))
        notes.append("Somebody on the other side has your position zeroed.")
    elif roll < 0.20 and p.vehicle is None:
        if p.weapon is not None and p.weapon.t.kind == "gun":
            p.weapon.jammed = True
            notes.append(f"Your {p.weapon.t.name} is fouled with sand and mud. It's jammed.")
    # paradrop fate
    fate = p.ai.get("drop_fate")
    if para and p.vehicle is None:
        game.remove_actor(p)
        x, y = rng.randint(10, game.map.w - 10), rng.randint(10, game.map.h - 10)
        paradrop_place(game, p, x, y)
        fate = p.ai.get("drop_fate")
        notes.append("The pilot panicked in the flak. You jumped too low, too fast, miles off the drop zone.")
        if fate == "tree":
            notes.append("Your canopy is snagged in a tree. You're dangling, cutting at your risers.")
        elif fate == "water":
            notes.append("You landed in flooded fields. The water is over your head and your kit is heavy.")
        elif fate == "hard":
            notes.append("You hit something hard on landing. Your leg is agony.")
        if p.ai.get("lost_weapon"):
            notes.append(f"Your {p.ai['lost_weapon']} was torn away in the jump.")
    orders = Item("orders")
    orders.data = {"text": ""}
    p.add_item(orders, "pockets")
    p.morale = max(30, p.morale)
    game.player = p
    return p, notes


def _short_of_ammunition(game):
    """A sector whose supply roads are cut or long: the men in it have fewer rounds and grenades than they should,
    in proportion (the war map's supply: Strategic.supply_of)."""
    from .logistics import sector_supply
    rng = game.rng
    p = game.player
    for side in SIDES:
        sup = sector_supply(game, side)
        if sup >= 0.5:
            continue
        short = min(0.8, (0.5 - sup) * 1.6)
        for a in game.actors:
            if a.side != side or a.is_player or not a.alive:
                continue
            for it in list(a.inv):
                if it is a.weapon:
                    continue
                if it.t.kind in ("mag", "clip", "grenade") and rng.random() < short:
                    a.remove_item(it)
                elif it.t.kind == "ammo" and it.count > 1:
                    it.count = max(1, int(it.count * (1 - short)))
        if p is not None and side == p.side:
            game.msg("Ammunition is short here: the roads behind have been cut or are too long. Men are counting "
                     "their rounds.", "warn")
