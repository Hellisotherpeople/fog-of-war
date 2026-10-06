"""Equipment belongs at depots, firing positions, shelters, wrecks and inhabited buildings.

Stocks are made once on first visiting a sector. Fighting then leaves its own casualties,
dropped equipment, scattered stores and burned supplies.
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
         ("sulfa", 0.7), ("morphine", 0.2), ("soft_cap", 0.5), ("local_drink", 1.5), ("pocket_watch", 0.4),
         ("crucifix", 0.6), ("shaving_kit", 0.5), ("housewife", 0.4), ("wedding_ring", 0.15)]
# what the people of each country left in their houses (by the sector's language)
LOCAL_DRINK = {"fr": "wine", "it": "wine", "be": "wine", "ru": "vodka", "uk": "vodka", "pl": "vodka", "de": "schnapps",
               "ja": "sake", "fi": "vodka", "gr": "wine"}
LOCAL_NATION = {"fr": "france", "be": "france", "nl": "france", "it": "italy", "ru": "ussr", "uk": "ussr",
                "pl": "poland", "de": "germany", "ja": "japan", "fi": "finland", "zh": "china", "gr": "italy"}
BARN = [("shovel", 3), ("wirecutters", 1.5), ("wire_spool", 1), ("sandbags", 2), ("canteen", 1), ("ration", 2),
        ("cigarettes", 1)]
CHURCH = [("bible", 3), ("rosary", 3), ("bandage", 3), ("medkit", 0.6), ("morphine", 0.6), ("letter", 1)]
WINTER = [("winter_coat", 3), ("snow_smock", 1)]
STYLE_TABLE = {"house": HOUSE, "farmhouse": HOUSE, "townhouse": HOUSE, "izba": HOUSE, "desert_house": HOUSE,
               "hut": HOUSE, "barn": BARN, "shed": BARN, "church": CHURCH,
               "chateau": HOUSE, "station": HOUSE, "bungalow": HOUSE, "white_house": HOUSE, "lighthouse": HOUSE,
               "windmill": BARN, "post_mill": BARN, "kiln": BARN, "elevator": BARN, "keep": BARN, "tower": BARN,
               "chapel": CHURCH, "white_church": CHURCH, "shrine": CHURCH, "temple": CHURCH, "pagoda": CHURCH,
               "marabout": CHURCH}
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
        n = sum(rng.random() < civil_left for _ in range(2 + min(5, len(cells) // 25)))
        # People leave possessions by beds, tables and storage, not evenly over every floor.
        anchors = [xy for xy in cells if any(m.in_bounds(xy[0] + dx, xy[1] + dy) and
                   T.DEFS[int(m.t[xy[0] + dx, xy[1] + dy])].key in ("bed", "table", "crates", "stove")
                   for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)))]
        cells = anchors[:3] or rng.sample(cells, min(2, len(cells)))
        if rng.random() < 0.06 and style in ("house", "farmhouse", "izba", "townhouse"):
            # something hidden under the floorboards
            nat = rng.choice(nations)
            for what in ("gun", "ammo"):
                it = military_item(game, nat, what, rng)
                if it is not None:
                    m.add_item(*rng.choice(cells), it)
                    placed += 1
        lang = getattr(s, "lang", None)
        for _ in range(n):
            tid = _w(rng, WINTER if winter and rng.random() < 0.2 else table)
            if tid == "local_drink":
                tid = LOCAL_DRINK.get(lang, "flask")
            it = military_item(game, nations[0], tid, rng) if tid in ITEMS else None
            if it is not None:
                from .flavor import stamp
                stamp(game, it, nation=LOCAL_NATION.get(lang))     # (their letters, their photographs)
                m.add_item(*rng.choice(cells), it)
                placed += 1
    # Equipment follows the military geography. Quiet sectors have no random battlefield litter.
    from .spawn import pick_nation
    records = list(getattr(m, "gen_positions", []) or [])
    for rec in records:
        kind = rec.get("kind")
        side = rec.get("side") or s.control
        if side not in SIDES or rec.get("destroyed"):
            continue
        nat = pick_nation(game, side)
        sup = st.supply_of(side, s)
        if kind == "depot":
            placed += stock_site(game, rec, nat, "Armoury racks", ("gun", "mag", "ammo", "grenade"), int(45 + 55 * sup))
            placed += stock_site(game, rec, nat, "Depot stores", tuple(x[0] for x in DUMP), int(30 + 35 * sup))
        elif kind in ("hq", "airfield", "harbour", "motor_pool"):
            table = ("gun", "mag", "ammo", "helmet", "container") if kind == "hq" else \
                    ("ammo_crate", "ammo", "ration", "bandage", "spanner", "wirecutters")
            placed += stock_site(game, rec, nat, "Reserve arms" if kind == "hq" else "Service stores", table, int(16 + 18 * sup))
        elif kind in ("artillery", "aa", "bunker", "mg_nest", "trench", "foxhole"):
            if rng.random() < (.95 if kind in ("artillery", "aa", "bunker") else .55):
                abandoned = fought and rng.random() < .45
                placed += stock_site(game, rec, nat, "Abandoned firing position" if abandoned else "Ready ammunition",
                                     ("ammo", "mag", "ammo_crate", "bandage", "ration") + (("gun", "helmet") if abandoned else ()),
                                     rng.randint(4, 10), worn=abandoned)
    # Small reserve caches: tucked into actual shelters, behind firing positions or in barns.
    shelters = [r for r in records if r.get("kind") in ("bunker", "trench", "foxhole")]
    shelters += [dict(x=x + w // 2, y=y + h // 2, rect=(x, y, w, h))
                 for x, y, w, h, style in getattr(m, "buildings", []) if style in ("barn", "shed", "farmhouse")]
    rng.shuffle(shelters)
    side = s.control
    if side in SIDES:
        nat = pick_nation(game, side)
        for rec in shelters[:rng.randint(1, 3)]:
            placed += stock_site(game, rec, nat, "Sheltered reserve cache", ("ammo", "mag", "ration", "bandage", "grenade"),
                                 rng.randint(8, 15), worn=fought and rng.random() < .4)
    # Remnants of a withdrawal collect by shell holes and wrecks, not arbitrary grass tiles.
    if fought:
        anchors = [(v.x, v.y) for v in game.vehicles if v.dead or v.abandoned]
        scarred = [(int(x), int(y)) for x, y in zip(*((m.t == T.ID["crater"]) | (m.t == T.ID["crater_big"])).nonzero())]
        anchors += rng.sample(scarred, min(5, len(scarred)))
        for x, y in anchors[:8]:
            rec = dict(x=x, y=y)
            placed += stock_site(game, rec, rng.choice(nations), "Abandoned kit", tuple(x[0] for x in LITTER),
                                 rng.randint(2, 5), worn=True)
    return placed


def stock_site(game, rec, nation, name, table, count, worn=False):
    """One finite, coherent stash. Stores are stacked at a few accessible spots inside the site."""
    m, rng = game.map, game.rng
    x, y = rec["x"], rec["y"]
    rect = rec.get("rect", (x - 3, y - 3, 7, 7))
    cells = [xy for xy in _floor_cells(m, *rect) if xy not in game.vehicle_at]
    if not cells:
        return 0
    # Prefer walls, crates, sandbags and other cover; keep the doorways/aisles clear.
    cells.sort(key=lambda xy: (not any(m.in_bounds(xy[0] + dx, xy[1] + dy) and
                    (not m.walk[xy[0] + dx, xy[1] + dy] or m.pos_cover[xy[0] + dx, xy[1] + dy] >= 30)
                    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))), abs(xy[0] - x) + abs(xy[1] - y)))
    anchors = cells[:max(1, min(6, count // 12 + 1))]
    # A rack holds one weapon pattern and matching ammunition, not an arbitrary calibre soup.
    gun = military_item(game, nation, "gun", rng)
    placed = 0
    for i in range(count):
        what = rng.choice(table)
        if gun is not None and what in ("gun", "ammo", "mag"):
            if what == "gun":
                it = Item(gun.tid, full=False)
            elif what == "mag" and gun.t.get("magtype"):
                it = Item(gun.t.magtype)
            else:
                aid = f"ammo_{gun.t.cal}"
                it = Item(aid, rng.randint(20, 50)) if aid in ITEMS else None
        else:
            it = military_item(game, nation, what, rng)
        if it is None:
            continue
        if worn:
            it.condition = rng.uniform(.35, .85)
        xy = anchors[i % len(anchors)]
        m.add_item(*xy, it)
        placed += 1
    if placed:
        m.__dict__.setdefault("loot_sites", []).append(dict(name=name, points=anchors, side=rec.get("side"), count=placed))
        if name in ("Armoury racks", "Reserve arms", "Sheltered reserve cache"):
            key = "supply_cache" if name == "Sheltered reserve cache" else "arms_rack"
            for x, y in anchors:
                if T.COVER[m.t[x, y]] < 20 and not T.DOOR[m.t[x, y]]:
                    m.set(x, y, key)
            m.refresh()
    return placed
