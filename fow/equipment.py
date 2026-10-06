"""Physical condition of kit. Damage follows exposure; storage shields its contents."""
from __future__ import annotations

import math


def toughness(item):
    t = item.t
    if t.tool in ("papers", "cover_papers", "letter", "photo", "orders", "code"):
        return 24.
    if t.tool in ("binoculars", "camera", "wireless", "radio", "handradio", "watch", "compass"):
        return 75.
    return {"gun": 260., "melee": 320., "armor": 220., "container": 130., "mag": 160.,
            "clip": 90., "ammo": 100., "medical": 55., "grenade": 180., "explosive": 120.}.get(t.kind, 100.)


def repairable(item):
    return item.t.kind in ("gun", "melee", "armor", "container", "mag") or \
        item.t.tool in ("binoculars", "camera", "wireless", "radio", "handradio", "watch", "compass", "shovel", "wirecutters")


def damage(game, item, energy, x, y):
    """Returns whether the item survives. Contents spill when their remaining storage tears away."""
    if energy <= 0 or item.t.kind == "corpse":
        return True
    before = item.condition
    item.condition -= energy / toughness(item)
    from .inventory import container_grids
    if item.t.get("grids"):
        for grid in container_grids(item):
            for child in list(grid.items):
                survives = damage(game, child, energy * (.18 + .5 * (1 - before)), x, y)
                if not survives:
                    grid.remove(child)
                elif not grid.fits(child, *child.gpos, child.rot, ignore=child):
                    grid.remove(child)
                    child.where = "ground"
                    game.map.add_item(x, y, child)
    if item.mag_item is not None:
        damage(game, item.mag_item, energy * .45, x, y)
    # Packaging damage loses part of a stack, rather than duplicating ruined and intact rounds.
    if item.count > 1 and item.t.kind in ("ammo", "clip", "medical") and before > 0:
        item.count = max(1, math.ceil(item.count * item.condition / before))
    return item.functional or repairable(item)


def _inventory(game, inv, energy, x, y):
    roots = [(it, "worn") for it in list(inv.slots.values()) if it is not None]
    if inv.hands is not None:
        roots.append((inv.hands, "carried"))
    for grid in inv.pockets:
        roots.extend((it, "pocket") for it in list(grid.items))
    for it, loc in roots:
        if not damage(game, it, energy * (.2 if loc == "pocket" else .65), x, y):
            inv.remove(it)


def blast(game, x, y, power, radius):
    from .combat import blast_clear
    import tcod
    m, rng = game.map, game.rng
    piles = [(xy, list(pile)) for xy, pile in list(m.items.items())
             if math.hypot(xy[0] - x, xy[1] - y) <= radius]
    for a in list(game.actors):
        d = math.hypot(a.x - x, a.y - y)
        if a.alive and a.vehicle is None and d <= radius and blast_clear(m, x, y, a.x, a.y):
            energy = power * .4 * (1 - d / (radius + 1)) ** 1.6
            energy *= 1 - m.pos_cover[a.x, a.y] / 140
            if getattr(a, "z", 0) < 0:
                energy *= .08
            _inventory(game, a.invent, energy, a.x, a.y)
    for (sx, sy), pile in piles:
        if not blast_clear(m, x, y, sx, sy):
            continue
        energy = power * .65 * (1 - math.hypot(sx - x, sy - y) / (radius + 1)) ** 1.6
        exposed = list(pile)
        for body in pile:
            if body.t.kind != "corpse" or not (body.data or {}).get("inv"):
                continue
            inv = body.data["inv"]
            _inventory(game, inv, energy, sx, sy)
            # Slung weapons and exposed webbing can be torn loose; the body's pockets stay with it.
            from .entities import visible_body_items
            for kit, loc in visible_body_items(body):
                if loc in ("body", "pack", "pockets") or rng.random() >= min(.85, energy / 180):
                    continue
                inv.remove(kit)
                kit.where = "ground"
                m.add_item(sx, sy, kit)
                # Already damaged with the body: scatter it without applying a second hit.
                exposed.append(kit)
        for it in exposed:
            if it.t.kind == "corpse":
                continue
            if it in pile and not damage(game, it, energy, sx, sy):
                m.remove_item(sx, sy, it)
                continue
            if it.data and it.data.get("live") is not None:
                continue  # live fuses retain their physical position in the ordnance system
            distance = min(8, int(energy / (18 + it.weight * 12)))
            if not distance:
                continue
            angle = math.atan2(sy - y, sx - x) if (sx, sy) != (x, y) else rng.uniform(0, math.tau)
            tx, ty = sx + round(math.cos(angle) * distance), sy + round(math.sin(angle) * distance)
            end = (sx, sy)
            for px, py in tcod.los.bresenham((sx, sy), (tx, ty))[1:]:
                if not m.in_bounds(px, py) or not m.walk[px, py]:
                    break
                end = (int(px), int(py))
            if end != (sx, sy):
                m.remove_item(sx, sy, it)
                it.where = "ground"
                m.add_item(*end, it)


def description(item):
    if item.t.kind == "corpse":
        return []
    kind = item.t.kind
    effect = {"gun": "Worn sights widen shots; damaged actions jam more.",
              "mag": "Bent feed lips cause stoppages.", "armor": "Protection and warmth fall with condition.",
              "container": "Torn storage loses usable space; contents can spill.",
              "medical": "Damaged supplies provide less effective treatment.",
              "ammo": "Damaged cartridges are less reliable.", "clip": "Damaged cartridges are less reliable.",
              "melee": "Damage reduces the edge's effectiveness.",
              "grenade": "A damaged fuse is more likely to fail.", "explosive": "A damaged fuse is more likely to fail."}.get(kind,
              "Damage impairs use; destroyed equipment cannot be used.")
    return [f"Condition: {round(item.condition * 100)}%" + (" - destroyed / unusable." if not item.functional else "."), effect]


def fire_tick(game):
    m = game.map
    # One bounded pass every five seconds, only while something is burning.
    for (x, y), pile in list(m.items.items()):
        if m.fire[x, y] <= 0:
            continue
        for it in list(pile):
            inv = (it.data or {}).get("inv") if it.t.kind == "corpse" else None
            if inv is not None:
                _inventory(game, inv, 12, x, y)
            elif not damage(game, it, 18, x, y):
                m.remove_item(x, y, it)
    for a in game.actors:
        if a.alive and a.vehicle is None and (m.fire[a.x, a.y] > 0 or a.body.burning):
            _inventory(game, a.invent, 10, a.x, a.y)
