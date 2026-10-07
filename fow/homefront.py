"""Inhabited country behind either army: work, hospitals, shelters and displaced people."""
from __future__ import annotations

import math
import random

from . import tiles as T

FACILITIES = {
    "factory": ("engineering works", "spares_store", "parts"),
    "food_depot": ("food warehouse", "food_store", "food"),
    "hospital": ("civilian hospital", "medical_store", "medical"),
    "power_station": ("electrical substation", "transformer", "power"),
    "rail_yard": ("railway goods yard", "crates", "transport"),
}


def prepare(strategic, sector):
    """Original distance from the fighting controls initial damage, on BOTH sides.

    Keep it once generated: capturing a town must not conjure ruins or new people.
    """
    if hasattr(sector, "homefront") or not sector.playable or sector.control is None:
        return
    lateral, depth = strategic._axes(sector.x, sector.y)
    distance = abs(depth - strategic._formula_boundary(lateral))
    rng = random.Random(sector.seed + 4187)
    sector.homefront = dict(depth=distance, prosperity=min(1., distance / 16),
                            damage=max(.02, .7 * math.exp(-distance / 3)),
                            goodwill=0, casualties=0, evacuated=0)
    if distance < 4 or sector.biome == "beach":
        return
    if sector.biome in ("city_ruins", "factory"):
        sector.biome = "town"
    if distance > 8 and rng.random() < .4 and sector.biome not in ("jungle", "desert", "volcanic"):
        sector.biome = "town" if rng.random() < .5 else "village"
    count = 1 + int(distance >= 9) + int(distance >= 16)
    kinds = list(FACILITIES)
    rng.shuffle(kinds)
    for kind in kinds[:count]:
        sector.installations.append([kind, sector.control, True])


def build(gen, kind, side):
    """A protected, accessible works/clinic and its actual stores; no decorative targets."""
    name, tile, _resource = FACILITIES[kind]
    w, h = (24, 16) if kind != "hospital" else (22, 18)
    pos = None
    for _ in range(180):
        x, y = gen.rng.randint(4, gen.w - w - 4), gen.rng.randint(4, gen.h - h - 4)
        if gen.area_free(x - 1, y - 1, x + w + 1, y + h + 1) and \
                not T.WATER[gen.m.t[x:x + w, y:y + h]].any():
            pos = x, y
            break
    if pos is not None:
        x, y = pos
        gen.m.t[x:x + w, y:y + h] = T.ID["dirt"]
        style = "house" if kind == "hospital" else "factory"
        gen.building(x + 2, y + 2, w - 4, h - 4, style, ruin=0, door_side="S", rooms=False)
        bx, by, bw, bh = x + 2, y + 2, w - 4, h - 4
    else:
        # Dense towns have no empty industrial plots: adapt an existing street building.
        # Keep its walls and doors, and never overwrite another installation or a road.
        def available(b):
            bx, by, bw, bh, style = b
            if style not in ("house", "townhouse", "farmhouse", "izba", "barn", "shed") or bw < 8 or bh < 8:
                return False
            for rec in gen.positions:
                if rec.get("rect"):
                    rx, ry, rw, rh = rec["rect"]
                    if bx < rx + rw and bx + bw > rx and by < ry + rh and by + bh > ry:
                        return False
            return not T.WATER[gen.m.t[bx:bx + bw, by:by + bh]].any()
        candidates = [b for b in gen.m.buildings if available(b)]
        if not candidates:
            return None
        bx, by, bw, bh, _style = gen.rng.choice(candidates)
        x, y, w, h = bx, by, bw, bh
        gen.m.t[bx + 1:bx + bw - 1, by + 1:by + bh - 1] = T.ID["floor_concrete"]
    targets = []
    for xx in range(bx + 2, bx + bw - 2, 3):
        gen.m.t[xx, by + 2] = T.ID[tile]
        targets.append((xx, by + 2))
        if kind == "hospital":
            for yy in range(by + 4, by + bh - 2, 3):
                gen.m.t[xx, yy] = T.ID["hospital_bed"]
    if kind == "rail_yard" and pos is not None:
        gen.m.t[x:x + w, y + h - 1] = T.ID["rail"]
    if kind != "hospital" and pos is not None:
        gen.m.t[x + w // 2 - 2, y + h - 2] = T.ID["checkpoint"]
    rec = dict(kind=kind, side=side, x=bx + bw // 2, y=by + bh - 2, rect=(x, y, w, h),
               name="the " + name, homefront=True, targets=targets, target_tile=T.ID[tile],
               spots=[("aidstaff" if kind == "hospital" else "guards", bx + bw // 2, by + bh - 2)],
               no_staff=True)
    gen.positions.append(rec)
    gen.poi.append((rec["name"], rec["x"], rec["y"], 10))
    gen.protected[x:x + w, y:y + h] = True
    return rec


def dress(gen):
    """Markets and shelters belong in residential buildings, with exits kept open."""
    for x, y, w, h, style in gen.m.buildings:
        if any(r.get("homefront") and r["rect"][0] <= x < r["rect"][0] + r["rect"][2] and
               r["rect"][1] <= y < r["rect"][1] + r["rect"][3] for r in gen.positions):
            continue
        if style not in ("house", "townhouse", "farmhouse", "izba", "hut", "desert_house") or w < 6 or h < 6:
            continue
        if gen.rng.random() < .25:
            gen.m.t[x + 2, y + 2] = T.ID["market_stall"]
        if gen.rng.random() < .2:
            gen.m.t[x + 2:x + 4, y + h - 4:y + h - 2] = T.ID["shelter_floor"]


def populate(game):
    from .entities import Actor, Item
    from .data.nations import random_name
    from .spawn import place
    from .loot import LOCAL_NATION
    s, m = game.sector, game.map
    prepare(game.strategic, s)
    hf = s.__dict__.get("homefront")
    if hf is None:
        return
    residents = s.__dict__.get("civilians")
    if residents is None:
        residents = s.civilians = []
        homes = [(x + w // 2, y + h // 2) for x, y, w, h, style in m.buildings
                 if style in ("house", "townhouse", "farmhouse", "izba", "hut", "desert_house", "church")]
        nation = LOCAL_NATION.get(getattr(s, "lang", ""), game.side_nation(s.control))
        rng = random.Random(s.seed + 578)
        count = min(len(homes) * 2, 4 + int(hf["prosperity"] * 22))
        for _ in range(count):
            home = rng.choice(homes)
            a = Actor(nation, "civilian", 0, random_name(rng, nation), *home)
            a.side = s.control                     # an affiliation, never a combat target
            a.ai.update(civilian=True, home=home, occupation=rng.choice(("resident", "railway worker", "shopkeeper",
                                                                        "farm worker", "nurse")))
            a.invent.slots["body"] = Item("civvies")
            if place(game, a, *home, radius=7):
                residents.append(a)
    else:
        for a in residents:
            if a.alive and a.state != "evacuated":
                place(game, a, a.x, a.y, radius=7)
    if not getattr(m, "loaded", False):
        for rec in getattr(m, "gen_positions", []):
            if rec.get("kind") not in FACILITIES:
                continue
            goods = {"hospital": ("bandage", "splint", "antiseptic", "plasma"),
                     "factory": ("tool_roll", "spare_parts", "gun_oil"),
                     "food_depot": ("ration", "water_tin", "blanket"),
                     "power_station": ("tool_roll", "spare_parts"),
                     "rail_yard": ("fuel_can", "spare_parts", "ration")}[rec["kind"]]
            for i, tid in enumerate(goods):
                m.add_item(rec["x"] + i % 3, rec["y"], Item(tid))


def act(game, a):
    """Civilians seek cover from either army, help wounded neighbours, and can be escorted."""
    from .actions import move
    if a.downed:
        return 100
    if (game.turn + a.id) % 5:
        return 100
    threats = [o for o in game.near(a.x, a.y, 18) if not o.ai.get("civilian") and o.fired_turn >= game.turn - 12]
    danger = bool(threats) or a.suppression > 8 or game.map.fire[a.x, a.y] > 0
    a.ai["frightened"] = danger
    a.stance = 1 if danger else 0
    if a.ai.get("following"):
        goal = game.player.pos
    elif danger:
        homes = [(x + w // 2, y + h // 2) for x, y, w, h, _ in game.map.buildings]
        goal = min(homes, key=lambda xy: math.hypot(xy[0] - a.x, xy[1] - a.y), default=a.pos)
    else:
        goal = a.ai["home"]
        if game.turn % 60 < 5:
            goal = (goal[0] + game.rng.randint(-4, 4), goal[1] + game.rng.randint(-4, 4))
    options = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = a.x + dx, a.y + dy
            m = game.map
            if not (dx or dy) or not m.in_bounds(x, y) or not (m.walk[x, y] or T.DOOR[m.t[x, y]]) or \
                    (x, y) in game.soldier_at or (x, y) in game.vehicle_at or m.water[x, y] >= 2:
                continue
            score = math.hypot(x - goal[0], y - goal[1]) + m.fire[x, y] * 50
            if danger:
                score -= m.pos_cover[x, y] / 15
                score += sum(20 / max(1, math.hypot(x - t.x, y - t.y)) for t in threats)
            options.append((score, dx, dy))
    if options and (danger or max(abs(a.x - goal[0]), abs(a.y - goal[1])) > 2):
        _, dx, dy = min(options)
        return move(game, a, dx, dy, allow_swap=False) or 100
    return 100


def casualty(game, a, killer):
    hf = game.sector.__dict__.get("homefront")
    if hf is not None:
        hf["casualties"] += 1
        hf["goodwill"] = max(-100, hf["goodwill"] - 8)
    if killer is game.player or killer is getattr(game.player, "vehicle", None) and killer is not None:
        game.stats["civilian_deaths"] += 1
        # Local grief and losses are real even in an accident. Military discipline
        # separately requires witnessed intent (conduct.py), not an automatic fine.
        game.msg("A civilian is dead. Word of this will travel through the district.", "death")


def tick(game):
    from . import sustain
    for rec in getattr(game.map, "gen_positions", []):
        if rec.get("kind") not in FACILITIES or rec.get("destroyed"):
            continue
        targets = rec.get("targets", [])
        if targets and sum(game.map.t[x, y] == rec["target_tile"] for x, y in targets) <= len(targets) * .35:
            rec["destroyed"] = True
            for inst in game.sector.installations:
                if inst[:2] == [rec["kind"], rec["side"]]:
                    inst[2] = False
            resource = FACILITIES[rec["kind"]][2]
            stores = sustain.stores(game.sector, rec["side"])
            if resource in stores:
                stores[resource] *= .15
            game.strategic.interdict(rec["side"], game.sector, .45,
                                     f"{rec['name'].capitalize()} at {game.sector.name} is out of action.")
            if game.can_see(rec["x"], rec["y"]):
                game.msg(f"{rec['name'].capitalize()} is out of action. The district loses its supplies.", "warn")
    from .medical import at_aid_post
    for a in list(game.actors):
        if a.ai.get("civilian") and a.ai.get("following") and at_aid_post(game, a):
            a.ai.pop("following", None)
            a.ai["home"] = a.pos
            if not a.ai.get("rescued"):
                a.ai["rescued"] = True
                game.sector.homefront["evacuated"] += 1
                game.sector.homefront["goodwill"] += 5
                game.command.merit += .5
                game.msg(f"{a.name} reaches the hospital. The orderlies take over.", "good")


def talk(ps, a):
    from .render import Popup
    opts = [("Ask about the district", "news", None, True), ("Give food or water", "relief", None, True),
            ("Ask them to follow you to safety", "follow", None, True), ("Treat their wounds", "treat", None, True)]

    if ps.game.player.role in ("mp", "intel", "officer"):
        opts.append(("Check identity and movement papers", "papers", None, True))

    def choose(what):
        g, p = ps.game, ps.game.player
        if what == "papers":
            from .counterintel import examine
            examine(g, p, a)
        elif what == "news":
            facilities = [r for r in getattr(g.map, "gen_positions", []) if r.get("kind") in FACILITIES
                          and not r.get("destroyed")]
            r = min(facilities, key=lambda r: abs(r["x"] - a.x) + abs(r["y"] - a.y), default=None)
            g.msg(f"{a.name}: " + (f"'{r['name'].capitalize()} is still working. I'll mark it on your map.'" if r
                                  else "'We hide when the guns start. We need food and dressings.'"), "shout")
            if r:
                x, y = r["x"], r["y"]
                g.map.explored[max(0, x - 2):x + 3, max(0, y - 2):y + 3] = True
        elif what == "relief":
            it = p.find(lambda i: i.t.tool in ("ration", "canteen"))
            if it is None:
                g.msg("You have no food or water to share.", "info")
                return
            from .actions import _consume
            _consume(p, it)
            a.body.heal_blood(40)
            a.morale = min(100, a.morale + 15)
            g.sector.homefront["goodwill"] = min(100, g.sector.homefront["goodwill"] + 3)
            g.msg(f"{a.name} accepts the supplies.", "good")
        elif what == "follow":
            a.ai["following"] = True
            g.msg(f"{a.name} will follow you. Take them to a hospital or aid post.", "info")
        elif what == "treat":
            from .medical import first_aid
            cost = first_aid(g, p, a)
            if cost:
                return ps.act(cost)
            g.msg("You cannot do more for those wounds with your kit.", "info")
            return
        ps.act(100)
    ps.open_popup(Popup(a.name + ", " + a.ai.get("occupation", "civilian"), opts, ps._screen_anchor()), choose)
