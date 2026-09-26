"""What's lying around.

Every stretch of ground a war has passed over is littered: helmets, rifles thrown down
by men who ran or were carried off, bandoliers, ration tins, letters.  Houses still hold
what their people left when they fled - food, a coat, a bottle, a hunting gun under the
floor.  Behind the lines there are dumps: crates of ammunition, medical stores, rations
stacked under a tarpaulin with a bored sentry or none at all.

Made once, when a sector is first seen; after that it's only what the war leaves.
"""
from __future__ import annotations

from . import tiles as T
from .constants import SIDES
from .data.items import ITEMS
from .entities import Item

# what's in people's houses, barns and churches
HOUSE = [("ration", 5), ("canteen", 3), ("cigarettes", 3), ("flask", 2), ("letter", 1), ("photo", 1),
         ("bible", 1), ("rosary", 1), ("cards", 1), ("harmonica", 0.5), ("watch", 1), ("map", 1.2),
         ("compass", 0.5), ("bandage", 2), ("shovel", 0.8), ("wirecutters", 0.5), ("binoculars", 0.3),
         ("sulfa", 0.7), ("morphine", 0.2), ("soft_cap", 0.5)]
BARN = [("shovel", 3), ("wirecutters", 1.5), ("wire_spool", 1), ("sandbags", 2), ("canteen", 1), ("ration", 2),
        ("cigarettes", 1)]
CHURCH = [("bible", 3), ("rosary", 3), ("bandage", 3), ("medkit", 0.6), ("morphine", 0.6), ("letter", 1)]
WINTER = [("winter_coat", 3), ("snow_smock", 1)]
STYLE_TABLE = {"house": HOUSE, "farmhouse": HOUSE, "townhouse": HOUSE, "izba": HOUSE, "desert_house": HOUSE,
               "hut": HOUSE, "barn": BARN, "shed": BARN, "church": CHURCH}
# a dump behind the lines
DUMP = [("ammo_crate", 5), ("ration", 4), ("bandage", 3), ("medkit", 1), ("canteen", 2), ("plasma", 0.8),
        ("sandbags", 2), ("wire_spool", 1), ("grenade", 3), ("mag", 4), ("ammo", 4), ("morphine", 1)]
# what a fight leaves behind
LITTER = [("helmet", 4), ("gun", 3), ("mag", 5), ("ammo", 4), ("grenade", 2), ("bandage", 3), ("canteen", 2),
          ("ration", 3), ("shovel", 1.5), ("letter", 1), ("photo", 1), ("cigarettes", 1.5), ("container", 1),
          ("melee", 0.6), ("tool", 0.8)]


def _w(rng, table):
    return rng.choices([t for t, _ in table], [w for _, w in table])[0]


def _pool(nation, year, kind, cats=None):
    from .data.nations import equip_sources
    srcs = equip_sources(nation, year)
    out = []
    for t in ITEMS.values():
        if t.kind != kind:
            continue
        if cats and t.get("cat") not in cats:
            continue
        nats = t.get("nations") or ()
        if nats and not any(s in nats for s in srcs):
            continue
        y0, y1 = t.get("years", (1900, 1950))
        if not (y0 <= year < y1):
            continue
        out.append(t)
    return out


def military_item(game, nation, what, rng):
    """One piece of a nation's kit of the given sort."""
    yr = game.year
    if what == "gun":
        pool = _pool(nation, yr, "gun", ("rifle", "rifle", "carbine", "smg", "pistol", "lmg"))
        pool = [t for t in pool if t.freq > 0] or pool
        if not pool:
            return None
        t = rng.choices(pool, [max(1, t.freq) for t in pool])[0]
        it = Item(t.id, full=False)
        # dropped half-empty, if not empty
        if it.mag_item is not None:
            it.mag_item.loaded = rng.randint(0, it.mag_item.t.mag)
            it.loaded = it.mag_item.loaded
        elif t.cat not in ("at_disposable",):
            it.loaded = rng.randint(0, t.mag)
        return it
    if what in ("mag", "ammo"):
        guns = _pool(nation, yr, "gun", ("rifle", "carbine", "smg", "lmg", "pistol"))
        if not guns:
            return None
        g = rng.choices(guns, [max(1, t.freq) for t in guns])[0]
        if what == "mag" and g.get("magtype") and g.magtype in ITEMS:
            m = Item(g.magtype, full=False)
            m.loaded = rng.randint(max(1, m.t.mag // 3), m.t.mag)
            return m
        aid = f"ammo_{g.cal}"
        if aid in ITEMS:
            return Item(aid, rng.randint(8, 40))
        return None
    if what == "helmet":
        from .data.items import HELMETS
        hid = HELMETS.get(nation)
        return Item(hid) if hid in ITEMS else None
    if what == "grenade":
        pool = [t for t in _pool(nation, yr, "grenade") if t.id != "molotov"]
        return Item(rng.choice(pool).id) if pool else None
    if what == "container":
        from .data.items import PACKS, RIGS
        rigs = RIGS.get(nation) or RIGS.get("uk")
        cid = PACKS.get(nation) if rng.random() < 0.5 else rng.choice([rigs["rifle"], rigs["smg"]])
        return Item(cid) if cid in ITEMS else None
    if what == "melee":
        pool = _pool(nation, yr, "melee")
        return Item(rng.choice(pool).id) if pool else None
    if what == "tool":
        return Item(rng.choice(["binoculars", "compass", "map", "watch", "wirecutters", "flaregun", "whistle"]))
    if what in ITEMS:
        t = ITEMS[what]
        n = 1
        if t.kind == "medical" and t.med == "bandage":
            n = rng.randint(1, 4)
        elif t.tool == "cigarettes":
            n = rng.randint(1, 3)
        return Item(what, n)
    return None


def _floor_cells(m, x0, y0, bw, bh):
    out = []
    for x in range(x0 + 1, x0 + bw - 1):
        for y in range(y0 + 1, y0 + bh - 1):
            if m.in_bounds(x, y) and m.walk[x, y] and m.water[x, y] < 2:
                out.append((x, y))
    return out


def scatter(game):
    """Fill a freshly made sector with the stuff of life and war."""
    rng = game.rng
    m = game.map
    s = game.sector
    st = game.strategic
    winter = game.theatre.get("climate") == "winter" or game.month() in (12, 1, 2)
    nations = []
    for side in SIDES:
        try:
            from .spawn import pick_nation
            nations.append(pick_nation(game, side))
        except Exception:
            pass
    nations = nations or [game.player_nation]
    fought = st.is_front(s, "allies") or st.is_front(s, "axis") or s.last_fight >= 0 or \
        any(o.last_fight >= 0 for o in st.neighbors(s))
    civil_left = 0.55 if fought else 0.85           # how much the people left behind (and nobody's taken)
    placed = 0
    # houses, barns, churches
    for (x0, y0, bw, bh, style) in list(getattr(m, "buildings", []) or []):
        table = STYLE_TABLE.get(style)
        if table is None:
            continue
        cells = _floor_cells(m, x0, y0, bw, bh)
        if not cells:
            continue
        n = sum(rng.random() < civil_left for _ in range(2 + len(cells) // 9))
        if rng.random() < 0.06 and style in ("house", "farmhouse", "izba", "townhouse"):
            # something hidden under the floorboards
            nat = rng.choice(nations)
            for what in ("gun", "ammo"):
                it = military_item(game, nat, what, rng)
                if it is not None:
                    m.add_item(*rng.choice(cells), it)
                    placed += 1
        for _ in range(n):
            tid = _w(rng, WINTER if winter and rng.random() < 0.2 else table)
            it = military_item(game, nations[0], tid, rng) if tid in ITEMS else None
            if it is not None:
                m.add_item(*rng.choice(cells), it)
                placed += 1
    # battlefield litter
    if fought:
        n = rng.randint(45, 80)
    else:
        n = rng.randint(12, 24)
    for _ in range(n):
        x, y = rng.randrange(2, m.w - 2), rng.randrange(2, m.h - 2)
        if not m.walk[x, y] or m.water[x, y] >= 2 or (x, y) in game.vehicle_at:
            continue
        nat = rng.choice(nations)
        it = military_item(game, nat, _w(rng, LITTER), rng)
        if it is not None:
            m.add_item(x, y, it)
            placed += 1
            # things come in twos and threes where a man fell or a position was
            if rng.random() < 0.5:
                x2, y2 = x + rng.randint(-1, 1), y + rng.randint(-1, 1)
                if m.in_bounds(x2, y2) and m.walk[x2, y2] and (x2, y2) not in game.vehicle_at:
                    it2 = military_item(game, nat, _w(rng, LITTER), rng)
                    if it2 is not None:
                        m.add_item(x2, y2, it2)
                        placed += 1
    # supply dumps behind the lines
    for side in SIDES:
        if s.control != side:
            continue
        depot = bool(s.installs(side, "depot"))
        rear = st._front_distance(s, side) >= 2
        if not (depot or (rear and rng.random() < 0.3) or rng.random() < 0.08):
            continue
        sup = st.supply_of(side, s)
        nat = nations[SIDES.index(side)] if len(nations) > SIDES.index(side) else nations[0]
        for _ in range(1 + (2 if depot else 0)):
            cx, cy = rng.randrange(8, m.w - 8), rng.randrange(8, m.h - 8)
            k = int(rng.randint(8, 18) * (0.4 + sup))
            for _ in range(k):
                x, y = cx + rng.randint(-2, 2), cy + rng.randint(-2, 2)
                if not (m.in_bounds(x, y) and m.walk[x, y]) or m.water[x, y] >= 1 or (x, y) in game.vehicle_at:
                    continue
                it = military_item(game, nat, _w(rng, DUMP), rng)
                if it is not None:
                    m.add_item(x, y, it)
                    placed += 1
    return placed
