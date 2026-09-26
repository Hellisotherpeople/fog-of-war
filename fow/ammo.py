"""Magazines, clips, belts and loose rounds: reloading, counting, refilling."""
from __future__ import annotations

from .data.items import ITEMS, ammo_id


def feed(gun) -> str:
    t = gun.t
    if t.get("magtype"):
        return "mag"
    if t.get("stripper"):
        return "stripper"
    return t.feed


def compatible(item, gun) -> bool:
    t = item.t
    gt = gun.t
    if t.kind in ("mag", "clip"):
        return gun.tid in t.compat or (t.kind == "mag" and gt.get("magtype") == item.tid) or \
            (t.kind == "clip" and gt.get("stripper") == item.tid)
    if t.kind == "ammo":
        return t.cal == gt.cal
    return False


def sources(actor, gun):
    """All carried items that can feed this gun, quickest to reach first."""
    if gun is None or gun.t.kind != "gun" or not gun.t.cal:
        return []
    out = []
    for g, loc in actor.invent.grids():
        for it in g.items:
            if compatible(it, gun):
                out.append((loc, it))
    order = {"rig": 0, "pockets": 1, "pack": 2}
    out.sort(key=lambda e: (order.get(e[0], 3), -(e[1].loaded if e[1].t.kind == "mag" else 0)))
    return [it for _, it in out]


def best_source(actor, gun):
    f = feed(gun) if gun is not None else None
    for it in sources(actor, gun):
        t = it.t
        if f == "mag" and t.kind == "mag" and it.loaded > 0:
            return it
        if f == "stripper" and t.kind in ("clip", "ammo"):
            return it
        if f in ("tube", "single", "clip") and t.kind == "ammo":
            return it
        if f == "mag" and t.kind == "ammo" and gun.t.kind == "gun" and gun.t.cat in ("at_launcher",):
            return it
    return None


def spare_rounds(actor, gun) -> int:
    n = 0
    for it in sources(actor, gun):
        t = it.t
        if t.kind == "mag":
            n += it.loaded
        elif t.kind == "clip":
            n += it.count * t.mag
        elif t.kind == "ammo":
            n += it.count
    return n


def spare_description(actor, gun) -> str:
    """How you'd describe your spare ammunition after a glance at your pouches."""
    if gun is None or gun.t.kind != "gun" or not gun.t.cal or gun.t.cat in ("at_disposable",):
        return ""
    f = feed(gun)
    srcs = sources(actor, gun)
    mags = [s for s in srcs if s.t.kind == "mag" and s.loaded > 0]
    clips = sum(s.count for s in srcs if s.t.kind == "clip")
    loose = sum(s.count for s in srcs if s.t.kind == "ammo")
    parts = []
    if f == "mag":
        full = sum(1 for m in mags if m.loaded >= m.t.mag)
        part = len(mags) - full
        if gun.t.feed == "clip":
            word = "clip"
        elif gun.t.feed == "belt":
            word = "belt"
        else:
            word = "mag"
        if full:
            parts.append(f"{full} {word}{'s' if full != 1 else ''}")
        if part:
            parts.append(f"{part} part-used")
    if clips:
        parts.append(f"{clips} stripper clip{'s' if clips != 1 else ''}")
    if loose:
        parts.append("a handful of loose rounds" if loose < 15 else f"~{int(round(loose / 10.0) * 10)} loose rounds")
    return ", ".join(parts) if parts else "no spare ammunition"


def reload(game, actor, gun=None, speed=False) -> int | None:
    """Reload the gun.  Returns moves spent, or None if impossible."""
    gun = gun or actor.weapon
    if gun is None or gun.t.kind != "gun":
        return None
    t = gun.t
    if t.cat in ("at_disposable", "flamer"):
        return None
    f = feed(gun)
    inv = actor.invent
    if f == "mag":
        new = None
        if t.cat == "at_launcher" or t.cat == "mortar":
            return _reload_loose(game, actor, gun)
        for it in sources(actor, gun):
            if it.t.kind == "mag" and it.loaded > 0 and (gun.mag_item is None or it.loaded > gun.loaded):
                new = it
                break
        if new is None:
            return None
        loc = actor.loc(new)
        grid, gpos, rot = new.grid, new.gpos, new.rot
        cost = t.reload_cost + actor.access_cost(new) // 2
        inv.remove(new)
        old = gun.mag_item
        if old is not None:
            old.loaded = gun.loaded
            old.known_rounds = gun.known_rounds
            if t.feed == "clip" and old.loaded == 0:
                old = None             # the empty en-bloc clip was ejected
            elif speed or grid is None or not grid.fits(old, gpos[0], gpos[1], rot):
                if speed:
                    game.map.add_item(actor.x, actor.y, old)
                    old = None
                elif inv.add(old) is None:
                    game.map.add_item(actor.x, actor.y, old)
                else:
                    cost += 40
            else:
                grid.place(old, gpos[0], gpos[1], rot)
                cost += 60
        gun.mag_item = new
        gun.loaded = new.loaded
        gun.known_rounds = new.known_rounds
        if speed:
            cost = int(cost * 0.7)
        game.emit_sound(actor.x, actor.y, 18, "reload", "the clatter of a reload", actor.side, actor)
        return cost
    if f == "stripper":
        need = t.mag - gun.loaded
        if need <= 0:
            return None
        cost = 0
        for it in sources(actor, gun):
            if need <= 0:
                break
            if it.t.kind == "clip":
                while it.count > 0 and need > 0:
                    n = it.t.mag
                    use = min(n, need)
                    gun.loaded += use
                    need -= use
                    if use < n:
                        # leftover rounds go loose into a pocket
                        actor.add_item(_loose(gun, n - use))
                    it.count -= 1
                    cost += 70
                if it.count <= 0:
                    inv.remove(it)
        if need > 0:
            c = _reload_loose(game, actor, gun)
            cost += c or 0
        if cost == 0:
            return None
        gun.known_rounds = True
        game.emit_sound(actor.x, actor.y, 16, "reload", "the clatter of a reload", actor.side, actor)
        return cost + actor.access_cost(gun) // 4
    return _reload_loose(game, actor, gun)


def _loose(gun, n):
    from .entities import Item
    return Item(ammo_id(gun.t.cal), n)


def _reload_loose(game, actor, gun) -> int | None:
    t = gun.t
    need = t.mag - gun.loaded
    if need <= 0:
        return None
    cost = 0
    for it in sources(actor, gun):
        if need <= 0:
            break
        if it.t.kind != "ammo":
            continue
        take = min(need, it.count)
        it.count -= take
        need -= take
        gun.loaded += take
        cost += take * (45 if t.mag > 1 else t.reload_cost)
        if it.count <= 0:
            actor.invent.remove(it)
    if cost == 0:
        return None
    gun.known_rounds = True
    game.emit_sound(actor.x, actor.y, 15, "reload", "rounds being loaded", actor.side, actor)
    return min(cost, 900)


def unload(actor, gun):
    """Pull the magazine (or the loose rounds) out of a gun into your kit."""
    from .entities import Item
    if gun.mag_item is not None:
        m = gun.mag_item
        m.loaded = gun.loaded
        gun.mag_item = None
        gun.loaded = 0
        if actor.add_item(m) is None:
            return m          # caller drops it
        return None
    if gun.loaded > 0 and gun.t.cal:
        rounds = Item(ammo_id(gun.t.cal), gun.loaded)
        gun.loaded = 0
        if actor.add_item(rounds) is None:
            return rounds
    return None


def fill_magazine(actor, mag, max_rounds=None) -> int:
    """Thumb loose rounds into a magazine.  Returns rounds loaded (time: ~0.5s each)."""
    t = mag.t
    need = t.mag - mag.loaded
    if max_rounds is not None:
        need = min(need, max_rounds)
    loaded = 0
    for g, _ in actor.invent.grids():
        for it in list(g.items):
            if need <= 0:
                break
            if it.t.kind == "ammo" and it.t.cal == t.cal:
                take = min(need, it.count)
                it.count -= take
                need -= take
                loaded += take
                if it.count <= 0:
                    g.remove(it)
    mag.loaded += loaded
    if loaded:
        mag.known_rounds = True
    return loaded


def loose_rounds(actor, cal) -> int:
    return sum(it.count for it in actor.inv if it.t.kind == "ammo" and it.t.cal == cal)


def needs_refill(actor, gun) -> bool:
    """Out of loaded magazines but carrying loose rounds that fit them."""
    if gun is None or feed(gun) != "mag":
        return False
    mags = [s for s in sources(actor, gun) if s.t.kind == "mag"]
    if any(m.loaded > 0 for m in mags):
        return False
    return bool(mags) and loose_rounds(actor, gun.t.cal) > 0


def _spare_for(giver, gun):
    """What the giver can part with for someone else's gun: never his own last magazine."""
    own = giver.weapon
    items = sources(giver, gun)
    if own is not None and own.t.kind == "gun" and own is not gun and any(compatible(it, own) for it in items):
        keep = 2           # same calibre as his own weapon: he keeps a couple
        mine = [it for it in items if compatible(it, own)]
        items = [it for it in items if it not in mine[:keep]]
    return items


def hand_over_possible(giver, gun) -> bool:
    return bool(_spare_for(giver, gun))


def hand_over(game, giver, receiver, gun, max_items=2) -> int:
    """Pass magazines, clips or loose rounds that fit the receiver's gun.  Returns items passed."""
    n = 0
    for it in _spare_for(giver, gun)[:max_items]:
        giver.invent.remove(it)
        if receiver.add_item(it) is None:
            game.map.add_item(receiver.x, receiver.y, it)
        n += 1
    duty = getattr(game, "duty", None)
    if n and duty is not None and giver.is_player and receiver.side == giver.side:
        duty.good_deed(game, "ammo", receiver)
    return n


def give_ammo(actor, gun, rounds: int):
    """Issue ammunition for a gun as it would be carried: magazines, clips, or loose."""
    from .entities import Item
    t = gun.t
    f = feed(gun)
    if f == "mag" and t.cat not in ("at_launcher", "mortar"):
        per = t.mag
        n = rounds // per
        for _ in range(n):
            m = Item(t.magtype)
            if actor.add_item(m) is None:
                if actor.invent.slots["pack"] is None:
                    from .data.items import PACKS
                    actor.invent.slots["pack"] = Item(PACKS.get(actor.nation, "backpack"))
                    if actor.add_item(m) is not None:
                        continue
                break
        rest = rounds - n * per
        if rest > per // 2:
            m = Item(t.magtype, full=False)
            m.loaded = rest
            actor.add_item(m)
        return
    if f == "stripper":
        from .inventory import stack_max
        s = ITEMS[t.stripper]
        n = rounds // s.mag
        mx = stack_max(s)
        left = n
        while left > 0:
            k = min(mx, left)
            if actor.add_item(Item(t.stripper, k)) is None:
                break
            left -= k
        rest = rounds - n * s.mag
        if rest:
            actor.add_item(Item(ammo_id(t.cal), rest))
        return
    if t.cal:
        actor.add_item(Item(ammo_id(t.cal), rounds))
