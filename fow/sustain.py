"""Finite stocks, deliveries, field repairs and the daily needs of soldiers."""
from __future__ import annotations

RESOURCES = ("ammo", "fuel", "food", "medical", "parts")


def stores(sector, side):
    all_stores = sector.__dict__.setdefault("stores", {})
    if side not in all_stores:
        depth = sector.__dict__.get("homefront", {}).get("depth", 0)
        amount = 80 + min(120, depth * 5) if sector.control == side else 25
        all_stores[side] = {k: float(amount) for k in RESOURCES}
    return all_stores[side]


def take(sector, side, kind, amount):
    st = stores(sector, side)
    if st[kind] + 1e-6 < amount:
        return False
    st[kind] = max(0, st[kind] - amount)
    return True


def deliver(sector, side, kind, amount):
    st = stores(sector, side)
    st[kind] = min(500., st[kind] + amount)


def category(t):
    if t.kind in ("ammo", "mag", "clip", "grenade", "explosive", "gun"):
        return "ammo"
    if t.kind == "medical":
        return "medical"
    return {"ration": "food", "canteen": "food", "fuel": "fuel"}.get(t.tool, "parts")


def strategic_tick(strategic):
    """Imports need a route to the rear, not just an encircled depot calling itself a source."""
    from collections import deque
    from .constants import SIDES
    from .strategic import DIRS, OPP, power
    for side in SIDES:
        edge = strategic.att_from if side == strategic.attacker else OPP[strategic.att_from]
        connected = set()
        queue = deque()
        for s in strategic.sectors():
            if s.control != side:
                continue
            external = strategic._depth_from(s, edge) <= 0 or (not strategic.in_core(s) and
                any((s.x + dx, s.y + dy) not in strategic.cells and
                    strategic.predict_control(s.x + dx, s.y + dy) == side for dx, dy in DIRS.values()))
            if external and strategic.cut_of(side, s) < .85:
                connected.add((s.x, s.y))
                queue.append(s)
        while queue:
            for n in strategic.neighbors(queue.popleft()):
                if n.control == side and (n.x, n.y) not in connected and strategic.cut_of(side, n) < .85:
                    connected.add((n.x, n.y))
                    queue.append(n)
        for s in strategic.active():
            if s.control != side or not s.playable:
                continue
            st = stores(s, side)
            transport = strategic.__dict__.get("weather_transport", 1.)
            incoming = 4 * strategic.supply_of(side, s) * transport if (s.x, s.y) in connected else 0
            facilities = {k for k, sd, ok in s.installations if sd == side and ok}
            if "rail_yard" in facilities:
                incoming *= 1.8
            demand = max(.4, power(s.units[side]) * .12)
            for k in RESOURCES:
                st[k] = max(0., min(500., st[k] + incoming - demand * (1.3 if k == "food" else .5)))
            if "factory" in facilities:
                st["parts"] = min(500, st["parts"] + (5 if "power_station" in facilities else 2))
            if "food_depot" in facilities:
                st["food"] = min(500, st["food"] + 3)


def tick(game):
    from .weather import exposure, precipitation
    for a in game.actors:
        if not a.alive:
            continue
        a.ai["splinted"] = a.ai.get("splinted_until", 0) > game.turn
        need = a.ai.setdefault("needs", dict(hunger=0., thirst=0., infection=0.))
        need["hunger"] = min(100, need["hunger"] + 100 / 1440)  # a day without food
        need["thirst"] = min(100, need["thirst"] + 100 / 720 * (1.7 if getattr(a.body, "temp", 37) > 38 else 1))
        if not a.is_player:
            for key, tool in (("hunger", "ration"), ("thirst", "canteen")):
                if need[key] > 35:
                    item = a.find(lambda i: i.t.tool == tool and i.uses > 0)
                    if item:
                        from .actions import _consume
                        _consume(a, item)
                        need[key] = max(0, need[key] - 60)
                    elif game.sector.control == a.side and game.turn - a.fired_turn > 300 and \
                            take(game.sector, a.side, "food", .2):
                        need[key] = max(0, need[key] - 40)
        if max(need["hunger"], need["thirst"]) > 70:
            a.stamina = max(0, a.stamina - 2)
            a.fatigue = min(100, a.fatigue + .15)
            if a.is_player and game.turn % 900 < 60:
                game.msg("You're desperately thirsty." if need["thirst"] > 70 else "Hunger is wearing you down.", "warn")
        # Open wounds in mud deteriorate over hours. Antiseptic and supplied care matter.
        dirty = any(not w.bandaged and not w.tourniquet for w in a.body.wounds)
        from .medical import at_aid_post
        clean = at_aid_post(game, a) and stores(game.sector, a.side)["medical"] > 0
        if dirty and a.ai.get("antiseptic_until", 0) < game.turn:
            need["infection"] = min(100, need["infection"] + .06 + .12 * precipitation(game) * exposure(game, a))
        elif clean or a.ai.get("antiseptic_until", 0) >= game.turn:
            need["infection"] = max(0, need["infection"] - .5)
        if need["infection"] > 40:
            a.body.pain = min(150, a.body.pain + .2)
            a.fatigue = min(100, a.fatigue + .1)
        if a.is_player and need["infection"] > 40 and not a.ai.get("infection_warned"):
            a.ai["infection_warned"] = True
            game.msg("The wound is hot and swollen. You need antiseptic and medical care.", "hurt")
    for v in game.vehicles:
        if v.dead or v.static or v.vt.vtype in ("wagon",) or "wagon" in v.vid:
            continue
        if v.moved_turn >= game.turn - 60:
            v.ai["fuel"] = max(0, v.ai.get("fuel", 100.) - .12)
        from .maintenance import at_motor_pool, quiet
        if v.ai.get("fuel", 100) < 95 and at_motor_pool(game, v) and quiet(game, v) and \
                take(game.sector, v.side, "fuel", .5):
            v.ai["fuel"] = min(100, v.ai.get("fuel", 100) + 3)


def use(ps, item):
    """New kit uses the normal apply menu and spends real time and supplies."""
    g, p = ps.game, ps.game.player
    tool = item.t.tool
    if not item.functional:
        g.msg("It's broken and cannot be used.", "warn")
        return
    from .actions import _consume
    from .medical import missing_hp
    if tool in ("antiseptic", "splint"):
        if not p.body.wounds and missing_hp(p.body) == 0:
            g.msg("You have no wound to treat.", "info")
            return
        if tool == "antiseptic":
            p.ai["antiseptic_until"] = g.turn + int(21600 * item.condition)
            p.ai.setdefault("needs", dict(hunger=0., thirst=0., infection=0.))["infection"] *= 1 - .7 * item.condition
            g.msg("You clean the wound with antiseptic. It still needs a dressing if it is bleeding.", "good")
        else:
            p.ai["splinted_until"] = g.turn + int(21600 * item.condition)
            p.body.pain = max(0, p.body.pain - 8 * item.condition)
            g.msg("You secure the splint. It supports the limb while you seek proper treatment.", "good")
        _consume(p, item)
        ps.act(600)
    elif tool == "blanket":
        if g.turn - p.fired_turn < 20:
            g.msg("You need a quiet moment to wrap up and rest.", "info")
            return
        p.ai["blanket_until"] = g.turn + int(1800 * item.condition)
        g.msg("You wrap the blanket around you. It keeps the wind off while you rest.", "info")
        ps.act(300)
    elif tool == "gun_oil":
        w = p.weapon
        if w is None or not w.functional or w.t.kind != "gun":
            g.msg("Put a firearm in your hands first.", "info")
            return
        w.jammed = False
        w.heat = 0
        _consume(p, item)
        g.msg("You clean the action, clear the stoppage and oil the working parts.", "good")
        ps.act(1800)
    elif tool in ("fuel", "repair", "spares"):
        from .maintenance import repairs, quiet
        vehicles = [v for v in g.vehicles if not v.dead and v.side == p.side and v.near(p.x, p.y) <= 2]
        v = min(vehicles, key=lambda v: v.near(p.x, p.y), default=None)
        if v is None:
            g.msg("You need a friendly vehicle within reach.", "info")
            return
        if not quiet(g, v):
            g.msg("The crew cannot work under fire.", "warn")
            return
        if tool == "fuel":
            if v.ai.get("fuel", 100) >= 100:
                g.msg("The tank is already full.", "info")
                return
            v.ai["fuel"] = min(100, v.ai.get("fuel", 100) + 25 * item.condition)
            _consume(p, item)
            g.msg("You pour the jerrycan into the fuel tank.", "good")
            ps.act(12000)
        else:
            todo = repairs(v)
            if not todo:
                g.msg("This needs workshop hull repairs." if v.hp < v.vt.hp else "Nothing needs repairing.", "info")
                return
            kit = p.has_tool("repair")
            parts = p.has_tool("spares")
            if kit is None or parts is None:
                g.msg("You need a tool roll and spare parts.", "info")
                return
            from .maintenance import JOBS, fitters_near
            job = todo[0]
            if JOBS[job][2] and not (p.role in ("mechanic", "motor_sergeant") or fitters_near(g, v)):
                g.msg("That job needs a fitter or a workshop.", "info")
                return
            # Start a job in the existing interruptible crew repair system, rather than
            # instantly healing an engine when the player clicks an item.
            _consume(p, parts)
            v.ai["field_parts"] = v.ai.get("field_parts", 0) + 1
            v.ai["maint"] = v.ai.get("maint", {})
            v.ai["maint"][job] = v.ai["maint"].get(job, 0) + JOBS[job][1] * .25 * min(kit.condition, parts.condition)
            p.ai["helping"] = v.id
            g.msg("You lay out the parts and tools. The crew can continue the repair while it stays quiet.", "info")
            ps.act(6000)


def needs_words(a):
    n = a.ai.get("needs", {})
    return [word for k, word in (("hunger", "hungry"), ("thirst", "thirsty"), ("infection", "infected wound"))
            if n.get(k, 0) > (40 if k == "infection" else 60)]
