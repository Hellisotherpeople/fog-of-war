"""Logistics: supply lines, quartermasters, and the trade in captured matériel and papers.

Supply.  Every side's sectors are fed from its depots and its rear.  A sector cut off
from both is a pocket: it gets no replacements, its men go hungry and fight worse,
its ammunition points run dry.

The quartermaster.  At a depot (or the supply sergeant at a company ammunition point)
you can turn in what you've picked up and draw what you're allowed.  Nobody sold army
kit, but everybody traded: captured weapons and equipment go to salvage and
intelligence and earn you requisition credit; rear-echelon troops pay good money -
cigarettes, mostly - for a Luger, a Walther, a katana or an Iron Cross.  What you can
draw depends on your rank and on how well the depot is supplied.

Intelligence.  Enemy soldiers carry papers: a private his paybook, an NCO his
notebook, an officer his orders, a captain a marked map, a major the operation orders.
Brought to an intelligence officer (at a command post) or the quartermaster, they're
worth credit and merit in proportion - and the information is real: enemy positions
on this field, enemy strength in the sectors around, the next attack coming.
"""
from __future__ import annotations

from .data.items import ITEMS

# base requisition value of things
CAT_VALUE = {"rifle": 20, "carbine": 20, "sniper": 45, "smg": 40, "assault": 60, "lmg": 70, "hmg": 90,
             "pistol": 25, "shotgun": 25, "at_rifle": 50, "at_launcher": 60, "at_disposable": 25, "flamer": 70,
             "mortar": 60}
TOOL_VALUE = {"binoculars": 30, "radio": 50, "handradio": 40, "watch": 15, "compass": 10, "map": 15,
              "flaregun": 12, "wirecutters": 8, "shovel": 4, "canteen": 3, "cigarettes": 8, "ration": 4,
              "whistle": 2, "orders": 0}
SOUVENIRS = {"p08": 90, "p38": 70, "katana": 120, "nambu14": 60, "c96": 60, "dadao": 40, "szabla": 40,
             "stahlhelm": 12, "type90": 15, "peaked_cap": 25, "fs_knife": 15}
CIG_CREDIT = 10                    # a pack of cigarettes goes as far as this much credit

# intelligence documents: (item id, level, credit, merit)
DOCS = {"paybook": (1, 4, 0.3), "notebook": (2, 12, 1.0), "field_orders": (3, 35, 2.5), "marked_map": (4, 70, 4.0),
        "op_orders": (5, 160, 8.0)}


def doc_for(grade: int) -> str:
    if grade >= 11:
        return "op_orders"
    if grade >= 10:
        return "marked_map"
    if grade >= 8:
        return "field_orders"
    if grade >= 3:
        return "notebook"
    return "paybook"


def base_value(t) -> int:
    """What a thing is worth to the army, before anyone haggles."""
    base = 0
    if t.kind == "gun":
        base = CAT_VALUE.get(t.cat, 20)
    elif t.kind == "melee":
        base = 10
    elif t.kind == "grenade":
        base = 3
    elif t.kind in ("mag", "clip"):
        base = 2
    elif t.kind == "ammo":
        base = 1
    elif t.kind == "medical":
        base = {"kit": 15, "plasma": 10, "morphine": 5, "bandage": 1, "sulfa": 1, "tourniquet": 2}.get(t.med, 2)
    elif t.kind == "armor":
        base = 5
    elif t.kind == "tool":
        base = TOOL_VALUE.get(t.tool, 3)
    elif t.kind == "container":
        base = 6
    elif t.kind == "explosive":
        base = 10
    return base


def value(it, player_nation: str) -> int:
    """What the quartermaster will give you for it."""
    t = it.t
    if it.tid in DOCS:
        return 0                                        # papers go to intelligence
    nats = t.get("nations") or ()
    own = not nats or player_nation in nats
    base = base_value(t)
    if t.kind == "ammo":
        base = max(1, it.count // 20)
    if not own:
        base = int(base * 1.5)                          # enemy matériel: salvage and intelligence
        base = max(base, SOUVENIRS.get(it.tid, 0))      # and the rear echelon's appetite for souvenirs
    else:
        base = int(base * 0.3)                          # turning in surplus of our own
    return max(0, base) * max(1, it.count if t.kind in ("medical", "grenade", "tool") else 1)


def souvenir(it, player_nation) -> bool:
    nats = it.t.get("nations") or ()
    return it.tid in SOUVENIRS and bool(nats) and player_nation not in nats


def rank_ok(player, t) -> tuple[bool, str]:
    """Are you allowed to draw this?"""
    g = player.rank
    role = player.role
    if t.kind == "gun":
        c = t.cat
        if c in ("lmg", "hmg") and role not in ("lmg_gunner", "hmg_gunner", "lmg_assistant", "hmg_assistant") and g < 3:
            return False, "a gunner's job"
        if c in ("at_launcher", "at_rifle", "flamer", "mortar") and role not in ("at_soldier", "flamethrower",
                                                                                 "mortarman", "engineer") and g < 3:
            return False, "specialists only"
        if c in ("smg", "assault") and g < 2 and role not in ("smg_gunner", "tank_crew"):
            return False, "NCOs first"
        if c == "sniper" and role != "sniper" and g < 8:
            return False, "snipers only"
    if t.kind == "tool":
        if t.tool in ("radio",) and role not in ("radioman",) and g < 8 and not player.ai.get("hq_equipment"):
            return False, "officers and signallers"
        if t.tool == "binoculars" and g < 3 and not player.ai.get("hq_equipment"):
            return False, "NCOs and officers"
    return True, ""


def stock(game, side):
    """What the depot holds, and the price multiplier for how well it's supplied."""
    from .data.nations import equip_sources
    from .sustain import stores, category
    nation = game.player_nation
    supply = sector_supply(game, side)
    srcs = equip_sources(nation, game.year)
    out = []
    for t in ITEMS.values():
        if stores(game.sector, side)[category(t)] < 1:
            continue
        if t.freq <= 0 and t.kind == "gun":
            continue
        if t.kind not in ("gun", "grenade", "medical", "tool", "mag", "clip", "ammo", "explosive", "melee", "armor",
                          "container"):
            continue
        if t.kind in ("tool",) and t.tool in ("orders", "letter", "photo", "rosary", "dogtags", "lucky_coin", "cards",
                                              "bible", "harmonica", "ammo_crate", "pack"):
            continue
        if t.kind == "armor" and t.slot != "head" and t.id not in ("winter_coat", "snow_smock", "rain_cape"):
            continue
        nats = t.get("nations") or ()
        if nats and not any(s in nats for s in srcs):
            continue
        y0, y1 = t.get("years", (1900, 1950))
        if not (y0 <= game.year < y1):
            continue
        if t.kind in ("ammo",) and not t.cal:
            continue
        out.append(t)
    mult = 1.0 if supply >= 0.7 else 1.6 if supply >= 0.35 else 3.0
    if supply < 0.15:
        out = [t for t in out if t.kind in ("ammo", "clip", "mag", "medical")]
    return out, mult, supply


def price(t, mult) -> int:
    base = base_value(t)
    if t.kind in ("mag", "clip"):
        base = 3
    elif t.kind == "ammo":
        base = 2
    elif t.kind == "grenade":
        base = 4
    return max(1, int(round(base * mult)))


def sector_supply(game, side) -> float:
    st = game.strategic
    sup = getattr(st, "supply", None) or {}
    return sup.get((side, game.sector.x, game.sector.y), 1.0)


# ====================================================================== intelligence

def turn_in_papers(game, player, it):
    """An intelligence officer reads what you brought.  Returns (credit, merit, what it told us)."""
    level, credit, merit = DOCS[it.tid]
    info = []
    data = it.data or {}
    rng = game.rng
    enemy = data.get("side")
    if level >= 1:
        info.append(f"identifies {data.get('unit', 'an enemy unit')}")
    h = game.__dict__.get("hierarchy")
    if h is not None and level >= 2:
        n = h.learn_enemy(game, unit_text=data.get("unit"), everything=level >= 4)
        if n:
            info.append("names their commanders" + (" all the way up" if level >= 4 else ""))
    if level >= 2 and enemy:
        from .brain import Contact
        positions = data.get("positions", [])
        for aid, x, y in positions:
            game.brains[player.side].contacts[aid] = Contact(aid, x, y, data.get("written", game.turn), "inf")
        info.append(f"{len(positions)} positions in the written report; they may have moved")
    if level >= 4 and data.get("reports"):
        from copy import deepcopy
        reports = deepcopy(data["reports"])
        for report in reports.values():
            report["source"] = "captured map"
            report["enemy_known"] = True
        from .intelligence import merge_map
        merge_map(player, reports)
        info.append("dated enemy dispositions copied to your map")
    return credit, merit, info


def _reveal_local(game, side, enemy, radius, near=None) -> int:
    brain = game.brains[side]
    n = 0
    px, py = near if near else (game.player.x, game.player.y)
    for a in game.actors:
        if a.side != enemy or not a.alive or a.state != "ok":
            continue
        if max(abs(a.x - px), abs(a.y - py)) > radius:
            continue
        brain.report(a, game.turn)
        n += 1
    for v in game.vehicles:
        if v.side == enemy and not v.dead and max(abs(v.x - px), abs(v.y - py)) <= radius:
            brain.report(v, game.turn)
            n += 1
    return n


def _enemy_plan(game, side) -> str | None:
    """The operation orders: where they'll attack next."""
    st = game.strategic
    enemy = "axis" if side == "allies" else "allies"
    best = None
    from .strategic import power
    for s in st.sectors():
        if s.control != enemy:
            continue
        for n in st.neighbors(s):
            if n.control == side:
                p = power(s.units[enemy])
                if best is None or p > best[0]:
                    best = (p, s, n)
    if best is None:
        return None
    _, s, n = best
    warned = getattr(st, "warned", None)
    if warned is None:
        st.warned = warned = {}
    warned[(side, n.x, n.y)] = st.ticks + 6        # the defenders dig in: forewarned
    n.fort = min(3, n.fort + 1)
    return f"reveals the next attack: from {s.name} on {n.name}. {n.name} is warned and digs in."
