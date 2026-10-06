"""Keeping the vehicles going: field repairs, re-arming, and the ammunition trucks.

A thrown track isn't the end of a tank.  When it's quiet the crew climb out with the track tools and
put it back on - half an hour's hard labour for four men, less with infantry lending a hand.  An engine
or a gun needs fitters (the mechanics who come up with the ammunition truck, or the motor pool);
real hull damage needs the motor pool.

Rounds don't appear in the racks by themselves either.  Shells come up on ammunition trucks, are
stacked at depots, or are carried forward a crate at a time, and the crew (and anyone who helps)
pass them up one by one.  When a side's vehicles are running low and the side is in supply, a truck
comes up from the rear to find them, and goes back when it's empty.

The same rules for both sides, and the player can be part of it: help fix a track, carry shells up to
a tank, take a crate off a truck, call a truck up by radio, drive a supply run for the motor sergeant.
"""
from __future__ import annotations

import math

STEP = 5                          # the work is done in five-second slices
TRACK_WORK = 7200                 # man-seconds: four men, half an hour
ENGINE_WORK = 14400               # fitters only
GUN_WORK = 10800                  # fitters only
PASS_TIME = 60.0                  # man-seconds a round: out of its packing tube, wiped, carried and passed up
STOW_TIME = 8.0                   # but the one man inside can stow no faster than a round in eight seconds
CRATE_ROUNDS = 10                 # rounds in a crate of shells
TRUCK_CARGO = 160                 # rounds on an ammunition truck
RIDERS = 6                        # infantry who can ride on a tank's hull


# ============================================================================ what a vehicle needs
def full_load(v):
    return v.vt.ap, v.vt.he, (1500 * len(v.vt.mgs) if v.vt.mgs else 0)


def shells_short(v) -> int:
    ap, he, _ = full_load(v)
    return max(0, ap - v.ap) + max(0, he - v.he)


def mg_short(v) -> int:
    return max(0, full_load(v)[2] - v.mg_ammo)


def low_on_ammo(v) -> bool:
    ap, he, mg = full_load(v)
    tot = ap + he
    return bool((tot and v.ap + v.he < tot * 0.5) or (mg and v.mg_ammo < mg * 0.3))


# the jobs: (part, man-seconds, does it need fitters?, the words).  "track" is a thrown or broken track the
# crew can put back themselves with the tools on the hull; the rest wants the motor pool's men.
JOBS = {
    "track": ("tracks", TRACK_WORK, False, "the thrown track"),
    "running gear": ("tracks", 10800, True, "the running gear"),
    "engine": ("engine", ENGINE_WORK, True, "the engine"),
    "transmission": ("transmission", 14400, True, "the transmission"),
    "gun": ("gun", GUN_WORK, True, "the gun"),
    "turret": ("turret", 10800, True, "the turret ring"),
    "optics": ("optics", 2400, False, "the sights and periscopes"),
    "radio": ("radio", 3600, True, "the radio"),
    "fuel": ("fuel", 3600, True, "the fuel tanks"),
    "mg": (None, 1200, False, "a machine gun"),
}


def repairs(v) -> list[str]:
    """What needs mending, most urgent first."""
    from .vdamage import OK, OUT, state
    out = []
    if "tracks" in v.parts and v.vt.speed:
        if state(v, "tracks") == OUT:
            out.append("track")
    for job in ("engine", "transmission", "gun", "turret"):
        part = JOBS[job][0]
        if part in v.parts and state(v, part) < OK:
            out.append(job)
    if "tracks" in v.parts and state(v, "tracks") == 1:
        out.append("running gear")
    if any(p.startswith("mg") and st == OUT for p, st in v.parts.items()):
        out.append("mg")
    for job in ("optics", "radio", "fuel"):
        if job in v.parts and state(v, job) < OK:
            out.append(job)
    return out


REPAIR_WORD = {k: j[3] for k, j in JOBS.items()}


def _mend(v, job):
    from .vdamage import OK, OUT
    if job == "mg":
        for p, st in v.parts.items():
            if p.startswith("mg") and st == OUT:
                v.parts[p] = OK                   # a new barrel, the feed cleared
                return
        return
    v.parts[JOBS[job][0]] = OK


def needs_words(v) -> list[str]:
    out = [REPAIR_WORD[r] for r in repairs(v)]
    if shells_short(v) > max(4, sum(full_load(v)[:2]) * 0.2):
        out.append("shells")
    if mg_short(v) > full_load(v)[2] * 0.4:
        out.append("belts for the machine guns")
    return out


def is_supply_truck(v) -> bool:
    return v.vt.vtype == "truck" and v.ai.get("cargo", 0) > 0 and not v.dead


# ============================================================================ circumstances
def quiet(game, v) -> bool:
    """Nobody shooting at it, and nobody it can see to shoot at: the crew can get out and work."""
    t = game.turn
    sq = v.squad
    if sq is not None and t - sq.last_contact < 60:
        return False
    if v.fired_turn >= t - 30 or t - v.ai.get("hit_turn", -999) < 60:
        return False
    for e in getattr(v, "visible", ()) or ():
        if getattr(e, "alive", True) and abs(e.x - v.x) + abs(e.y - v.y) < 40:
            return False
    return True


def helpers(game, v) -> list:
    """Men on foot beside the hull who aren't busy fighting: they lend a hand."""
    p = game.player
    if p is not None and p.ai.get("helping") == v.id and (p.vehicle is not None or v.near(p.x, p.y) > 1):
        p.ai.pop("helping", None)                     # you've walked off (or climbed in): you're not helping now
    out = []
    for a in game.near(v.x, v.y, 4, v.side):
        if not a.active or a.vehicle is not None or a.downed:
            continue
        if v.near(a.x, a.y) > 1:
            continue
        if a is p:
            if p.ai.get("helping") == v.id:
                out.append(a)
            continue
        if a.squad is not None and game.turn - a.squad.last_contact < 30:
            continue
        out.append(a)
    return out


def needy(game) -> list:
    """Vehicles that could use a hand right now (a track to put back, rounds being passed up), refreshed
    every few seconds: what idle infantry nearby look for."""
    c = game.__dict__.get("_needy")
    if c is not None and c[0] > game.turn - STEP:
        return c[1]
    out = [v for v in game.vehicles if not v.dead and not v.abandoned and v.crew > 0 and
           ("track" in repairs(v) or v.ai.get("rearming")) and quiet(game, v)]
    game.__dict__["_needy"] = (game.turn, out)
    return out


HELP_MAX = 3                      # men beside a hull before there's no room to swing the hammer


def help_act(game, a, vis, sq) -> int | None:
    """An infantryman with nothing to do walks over to a tank that's thrown a track, or is loading, and
    lends a hand.  (The work itself is counted in _repair and _rearm: he's one of the helpers.)"""
    if a.is_player or a.vehicle is not None or a.carrying is not None or a.downed or a.ai.get("post"):
        return None
    if vis or sq is None or game.turn - sq.last_contact < 60:
        return None
    ordered = sq.__dict__.get("help_v")               # "give the tankers a hand!" from the man in charge
    if ordered is None and (sq.player_led or sq.order.kind in ("attack", "assault", "move", "retreat") or
                            sq.kind in ("staff", "rear", "aid", "supply")):
        return None
    cands = needy(game)
    if ordered is not None:
        cands = [v for v in game.vehicles if v.id == ordered and not v.dead and
                 ("track" in repairs(v) or shells_short(v) > 0)]
        if not cands or sq.order.kind != "hold":
            sq.__dict__.pop("help_v", None)            # done, or they've been given something else to do
            return None
    if not cands:
        return None
    best = None
    for v in cands:
        if v.side != a.side:
            continue
        d = v.near(a.x, a.y)
        if d > (30 if ordered is not None else 12):
            continue
        if d <= 1:
            a.ai["helping_v"] = v.id
            return 100                           # heave
        if len(helpers(game, v)) >= (HELP_MAX + 2 if ordered is not None else HELP_MAX):
            continue
        if best is None or d < best[0]:
            best = (d, v)
    if best is None:
        return None
    v = best[1]
    cells = set(v.cells())
    m = game.map
    spots = [(cx + dx, cy + dy) for cx, cy in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)
             if (cx + dx, cy + dy) not in cells and m.in_bounds(cx + dx, cy + dy) and m.walk[cx + dx, cy + dy]
             and game.soldier_at.get((cx + dx, cy + dy)) is None and (cx + dx, cy + dy) not in game.vehicle_at]
    if not spots:
        return None
    tx, ty = min(spots, key=lambda q: max(abs(q[0] - a.x), abs(q[1] - a.y)))
    from .ai import path_step
    return path_step(game, a, tx, ty)


def fitters_near(game, v) -> bool:
    """Mechanics: the motor pool's, or the fitters who ride up with an ammunition truck."""
    for a in game.near(v.x, v.y, 6, v.side):
        if a.active and not a.downed and a.role in ("motor_sergeant", "mechanic"):
            return True
    for t in game.vehicles:
        if t is not v and t.side == v.side and t.active and t.ai.get("fitters") and v.near(t.x, t.y) <= 8:
            return True
    return at_motor_pool(game, v)


def at_motor_pool(game, v) -> bool:
    for rec in getattr(game.map, "gen_positions", None) or []:
        if rec.get("kind") in ("motor_pool", "factory") and rec.get("side") == v.side and not rec.get("destroyed"):
            x0, y0, sw, sh = rec.get("rect", (rec["x"] - 8, rec["y"] - 8, 16, 16))
            if x0 - 4 <= v.x <= x0 + sw + 4 and y0 - 4 <= v.y <= y0 + sh + 4:
                return True
    return False


def source(game, v):
    """Where rounds can come from: ('truck', truck), ('depot', None), ('crate', (x, y, item)) or None."""
    for t in game.vehicles:
        if t is not v and t.side == v.side and is_supply_truck(t) and v.near(t.x, t.y) <= 8:
            return "truck", t
    m = game.map
    from . import tiles as T
    x0, x1 = max(0, v.x - 6), min(m.w, v.x + 7)
    y0, y1 = max(0, v.y - 6), min(m.h, v.y + 7)
    if (m.t[x0:x1, y0:y1] == T.ID["ammo_stack"]).any() and _own_ground(game, v):
        return "depot", None
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            for it in m.items_at(v.x + dx, v.y + dy):
                if it.tid == "shell_crate":
                    return "crate", (v.x + dx, v.y + dy, it)
    return None


def _own_ground(game, v) -> bool:
    return game.sector.control == v.side or any(r.get("kind") == "depot" and r.get("side") == v.side
                                                for r in getattr(game.map, "gen_positions", None) or [])


def _tell(game, v, text, kind="info"):
    """Only what the player would know: his own vehicle, or one he can see."""
    p = game.player
    if p is None:
        return
    if p.vehicle is v or (v.side == p.side and game.can_see(v.x, v.y) and abs(v.x - p.x) + abs(v.y - p.y) < 30):
        game.msg(text, kind)


# ============================================================================ the work, every few seconds
def tick(game):
    if game.__dict__.get("domain", "land") != "land" or game.map is None:
        return
    from . import vdamage
    vdamage.tick(game)                                # seats covered again, hatches opened or shut
    for v in list(game.vehicles):
        if v.dead or v.abandoned:
            continue
        try:
            _repair(game, v)
            _rearm(game, v)
            _seek_supply(game, v)
        except Exception:
            import os
            if os.environ.get("FOW_DEBUG"):
                raise
    _trucks(game)
    from .tasks import tick as _tasks_tick
    _tasks_tick(game)
    if (game.turn // STEP) % 60 == 30:           # (called every STEP turns: once in five minutes)
        from .constants import SIDES
        for side in SIDES:
            call_truck(game, side)


def _repair(game, v):
    todo = repairs(v)
    hull = v.hp < v.vt.hp and at_motor_pool(game, v)
    if not todo and not hull:
        v.ai.pop("maint", None)
        return
    w = v.ai.setdefault("maint", {})
    if not quiet(game, v):
        return
    hands = max(0, v.crew) + len(helpers(game, v))
    if hands == 0:
        return
    fitters = fitters_near(game, v)
    speed = hands * STEP * (1.6 if fitters else 1.0)
    v.ai["maint_rate"] = speed / STEP                  # man-seconds a second, for the estimate in the tooltip
    for job in todo:
        part, need, skilled, word = JOBS[job]
        if skilled and not fitters:
            continue
        if job not in w:
            w[job] = 0.0
            _tell(game, v, {"track": f"The {v.vt.name}'s crew climb out with the track tools and the sledgehammer.",
                            "engine": f"Fitters get the {v.vt.name}'s engine decks open.",
                            "transmission": f"Fitters start pulling the {v.vt.name}'s transmission.",
                            "gun": f"Fitters strip the {v.vt.name}'s gun.",
                            "turret": f"Fitters crawl under the {v.vt.name}'s turret ring with bars and jacks.",
                            "optics": f"The {v.vt.name}'s crew swap out the smashed periscope heads.",
                            "mg": f"The {v.vt.name}'s crew strip a jammed machine gun."}.get(
                job, f"Work starts on the {v.vt.name}'s {word[4:] if word.startswith('the ') else word}."))
        w[job] += speed
        if w[job] >= need:
            from .sustain import take
            if v.ai.get("field_parts", 0) > 0:
                v.ai["field_parts"] -= 1
            elif not consume_parts(game, v, 0 if job == "track" else 1 if skilled else .25):
                if not v.ai.get("parts_warned"):
                    _tell(game, v, f"The {v.vt.name}'s repair is waiting for spare parts.", "warn")
                    v.ai["parts_warned"] = True
                return
            v.ai.pop("parts_warned", None)
            del w[job]
            _mend(v, job)
            _tell(game, v, {"track": f"The track's back on the {v.vt.name}.",
                            "engine": f"The {v.vt.name}'s engine coughs and catches.",
                            "gun": f"The {v.vt.name}'s gun is back in action.",
                            "turret": f"The {v.vt.name}'s turret swings free again."}.get(
                job, f"{word[0].upper() + word[1:]} of the {v.vt.name}: fixed."), "good")
        break                                   # one job at a time
    if hull and not todo:
        from .sustain import take
        if not take(game.sector, v.side, "parts", .02 * speed / STEP):
            return
        v.hp = min(v.vt.hp, v.hp + v.vt.hp * 0.002 * speed / STEP)
        if v.hp >= v.vt.hp:
            _tell(game, v, f"The motor pool signs the {v.vt.name} off as fit.", "good")


def work_left(v) -> tuple[str, int] | None:
    """(job, about how many minutes more at the rate the men on it are going) - for the look tooltip."""
    w = v.ai.get("maint") or {}
    rate = max(1.0, v.ai.get("maint_rate", v.crew or 1))
    for job, done in w.items():
        if job in JOBS:
            mins = max(1, int((JOBS[job][1] - done) / rate / 60))
            return job, mins
    return None


def _rearm(game, v):
    short = shells_short(v)
    belts = mg_short(v)
    if short <= 0 and belts <= 0:
        v.ai.pop("rearming", None)
        return
    if not quiet(game, v):
        return
    src = source(game, v)
    if src is None:
        return
    kind, s = src
    hands = max(1, v.crew) + len(helpers(game, v))
    if not v.ai.get("rearming"):
        v.ai["rearming"] = True
        where = {"truck": "the ammunition truck", "depot": "the dump", "crate": "the crates"}[kind]
        _tell(game, v, f"The {v.vt.name}'s crew start passing rounds up from {where}.")
    acc = v.ai.get("pass_acc", 0.0) + min(hands / PASS_TIME, 1.0 / STOW_TIME) * STEP
    n = int(acc)
    v.ai["pass_acc"] = acc - n
    if n > 0 and short > 0:
        if kind == "truck":
            n = min(n, s.ai["cargo"])
            s.ai["cargo"] -= n
            s.ai["delivered"] = s.ai.get("delivered", 0) + n
        elif kind == "crate":
            x, y, it = s
            n = min(n, it.count * CRATE_ROUNDS if it.count else CRATE_ROUNDS)
            left = (it.data or {}).get("rounds", CRATE_ROUNDS) - n
            if left <= 0:
                game.map.remove_item(x, y, it)
            else:
                it.data = dict(it.data or {}, rounds=left)
        elif kind == "depot":
            from .sustain import stores, take
            n = min(n, int(stores(game.sector, v.side)["ammo"] * 4))
            take(game.sector, v.side, "ammo", n / 4)
        _load_rounds(v, n)
    if belts > 0:
        from .sustain import take
        rounds = min(belts, 50 * hands)
        if take(game.sector, v.side, "ammo", rounds / 250):
            v.mg_ammo += rounds
    if shells_short(v) <= 0 and mg_short(v) <= 0:
        v.ai.pop("rearming", None)
        if "ammo" in v.parts:
            v.parts["ammo"] = 2                      # the broken rounds thrown out, the racks restocked
        _tell(game, v, f"The {v.vt.name}'s racks are full again.", "good")


def _load_rounds(v, n):
    """Into the racks, armour-piercing and high explosive in proportion to what's missing."""
    ap, he, _ = full_load(v)
    for _ in range(n):
        dap, dhe = ap - v.ap, he - v.he
        if dap <= 0 and dhe <= 0:
            return
        if dap >= dhe:
            v.ap += 1
        else:
            v.he += 1


def _seek_supply(game, v):
    """An AI vehicle low on rounds, and a truck about: it goes to the truck when things are quiet."""
    if v.player_crewed or v.vt.static or not v.vt.speed or not v.tracks or not v.engine:
        return
    sq = v.squad
    if sq is None or sq.player_led or getattr(sq.order, "src", "ai") == "player":
        return
    if not low_on_ammo(v) or not quiet(game, v) or source(game, v) is not None:
        if sq.order.kind == "resupply" and v.ai.get("to_truck") and not low_on_ammo(v):
            v.ai.pop("to_truck", None)
            from .ai import Order
            sq.order = Order("hold", target=(v.x, v.y), issued=game.turn)
        return
    trucks = [t for t in game.vehicles if t.side == v.side and is_supply_truck(t)]
    if not trucks:
        return
    t = min(trucks, key=lambda t: abs(t.x - v.x) + abs(t.y - v.y))
    if abs(t.x - v.x) + abs(t.y - v.y) > 160:
        return
    from .ai import Order
    sq.order = Order("resupply", target=(t.x, t.y), radius=4, issued=game.turn)
    sq.arrived = False
    v.ai["to_truck"] = t.id


# ============================================================================ the ammunition trucks
def call_truck(game, side, target=None, why=None) -> str | None:
    """A truck of shells (and a couple of fitters) up from the rear to where the vehicles are.  Returns a
    line to say, or None if none can come."""
    def on_its_way(t):
        run = t.ai.get("supply_run")
        if not run:
            return False
        lp = t.ai.get("run_pos")
        if lp is None or (lp[0], lp[1]) != (t.x, t.y):
            t.ai["run_pos"] = lp = (t.x, t.y, game.turn)
        return game.turn - lp[2] < 600            # (a truck that hasn't moved in ten minutes isn't coming)
    if any(t.side == side and is_supply_truck(t) and on_its_way(t) for t in game.vehicles):
        return "There's a truck up here already." if why else None
    if target is None:
        low = [v for v in game.vehicles if v.side == side and not v.dead and not v.abandoned and
               (v.vt.ap or v.vt.he or v.vt.mgs) and (low_on_ammo(v) or repairs(v))]
        if not low:
            return None
        target = (int(sum(v.x for v in low) / len(low)), int(sum(v.y for v in low) / len(low)))
    from .logistics import sector_supply
    if sector_supply(game, side) < 0.3:
        return "Nothing's getting through - we're cut off." if why else None
    edge = game.home_edge(side)
    if edge is None:
        return "No road back to the rear from here." if why else None
    from .sustain import stores, take
    if max(stores(game.sector, side)["ammo"], stores(game.sector, side)["parts"], stores(game.sector, side)["materials"]) < 1:
        return "The shell dump is empty. We need a delivery first." if why else None
    from .ai import Order
    from .spawn import edge_band_point, make_vehicle_squad, pick_nation
    x, y = edge_band_point(game, edge, game.rng, depth=(2, 6))
    sq = make_vehicle_squad(game, side, pick_nation(game, side), "truck", x, y, 1,
                            Order("move", target=tuple(target), radius=4, issued=game.turn), edge=edge)
    if sq is None:
        return "No trucks to send." if why else None
    sq.no_count = True
    sq.kind = "supply"                            # (the commander leaves it to its run)
    sq.name = "ammunition truck"
    t = sq.vehicles[0]
    t.crew = max(1, t.vt.crew)
    t.abandoned = False
    load = min(TRUCK_CARGO, int(stores(game.sector, side)["ammo"] * 4))
    take(game.sector, side, "ammo", load / 4)
    parts = min(10., stores(game.sector, side)["parts"])
    materials = min(30., stores(game.sector, side)["materials"])
    take(game.sector, side, "parts", parts)
    take(game.sector, side, "materials", materials)
    t.ai.update(cargo=load, parts_cargo=parts, material_cargo=materials, delivered=0, fitters=True,
                supply_run=dict(until=game.turn + 3600, target=tuple(target), edge=edge))
    if why or (game.player is not None and game.player.side == side and game.player.vehicle is not None):
        game.msg("Radio: 'Ammunition truck on its way up to you - fitters aboard.'", "radio")
    return "An ammunition truck is on its way up."


def _trucks(game):
    """Trucks on a supply run follow their vehicles, and go back when they're empty or it's late."""
    from .ai import Order
    for t in list(game.vehicles):
        run = t.ai.get("supply_run")
        if not run or t.dead:
            continue
        sq = t.squad
        home = run.get("edge")
        busy = any(v is not t and v.side == t.side and v.active and repairs(v) and v.near(t.x, t.y) <= 8
                   for v in game.vehicles)
        done = (t.ai.get("cargo", 0) <= 0 and t.ai.get("parts_cargo", 0) <= 0 and
                t.ai.get("material_cargo", 0) <= 0) or (game.turn > run["until"] and not busy)
        if done and not run.get("going"):
            run["going"] = True
            if home and sq is not None:
                x, y = game._edge_exit_point(home, (t.x, t.y), 4)
                sq.order = Order("move", target=(x, y), radius=2, issued=game.turn)
                sq.arrived = False
        if run.get("going"):
            if home and game._edge_gap(home, t.x, t.y) <= 3 or t.crew <= 0:
                _gone(game, t)
            continue
        # keep up with the vehicles it came for
        low = [v for v in game.vehicles if v.side == t.side and v is not t and not v.dead and not v.abandoned
               and (low_on_ammo(v) or shells_short(v) > 0 or repairs(v)) and v.vt.vtype != "truck"]
        if low and sq is not None and (game.turn // STEP) % 6 == 0:      # (twice a minute)
            c = min(low, key=lambda v: abs(v.x - t.x) + abs(v.y - t.y))
            if abs(c.x - t.x) + abs(c.y - t.y) > 6:
                sq.order = Order("move", target=(c.x, c.y), radius=4, issued=game.turn)
                sq.arrived = False


def _gone(game, t):
    """Off the map, back to the rear - but not with you in it."""
    p = game.player
    if p is not None and p.vehicle is t:
        if t.player_crewed:
            t.ai.pop("supply_run", None)                 # you've taken the wheel: it's yours now
            return
        from .actions import exit_vehicle
        if exit_vehicle(game, p) is None:
            return                                       # nowhere to set you down: the driver waits
        game.msg(f"The {t.vt.name} stops at the edge of the map. \"End of the line, mate - I'm off back.\" "
                 f"You climb down.", "info")
    if t.passengers:
        game.disembark_all(t)
        if t.passengers:
            return
    try:
        game.lift_vehicle(t)
    except Exception:
        pass
    if t in game.vehicles:
        game.vehicles.remove(t)
    sq = t.squad
    if sq is not None:
        if t in sq.vehicles:
            sq.vehicles.remove(t)
        if not sq.vehicles and not sq.members and sq in game.squads:
            game.squads.remove(sq)
    t.dead = True


# ============================================================================ the player's part
def help_with(ps, v):
    """Lend the crew a hand: you work beside the hull while the time passes (any key stops)."""
    g = ps.game
    p = g.player
    jobs = repairs(v)
    if not jobs:
        g.msg(f"The {v.vt.name} doesn't need anything fixing.", "info")
        return
    if v.near(p.x, p.y) > 1:
        g.msg("Get next to it first.", "info")
        return
    p.ai["helping"] = v.id
    word = REPAIR_WORD[jobs[0]]
    if not quiet(g, v):
        g.msg(f"Not now: nobody climbs out to work on {word} while it's being shot at.", "info")
        return
    if JOBS[jobs[0]][2] and not fitters_near(g, v):
        g.msg(f"You can't fix {word} with a spanner and good intentions: it needs fitters (the ammunition truck "
              f"brings some) or the motor pool.", "info")
        return
    g.msg(f"You put your shoulder to it with the crew: {word}. (any key stops)", "info")
    ps.auto_wait = max(ps.auto_wait, 900)
    ps.mark_interrupt()


def take_crate(ps, truck):
    g = ps.game
    p = g.player
    if not is_supply_truck(truck):
        g.msg("There's nothing left on that truck.", "info")
        return
    if p.invent.hands is not None:
        g.msg("Your hands are full.", "info")
        return
    from .entities import Item
    it = Item("shell_crate")
    it.data = dict(rounds=CRATE_ROUNDS)
    p.invent.hands = it
    truck.ai["cargo"] = max(0, truck.ai["cargo"] - CRATE_ROUNDS)
    g.msg("The driver swings a crate of shells down into your arms. It's heavy.", "info")
    ps.act(300)


def hand_up(ps, v):
    """The crate you're carrying, passed up into the tank."""
    g = ps.game
    p = g.player
    it = p.invent.hands if p.invent.hands is not None and p.invent.hands.tid == "shell_crate" else \
        next((i for i in p.inv if i.tid == "shell_crate"), None)
    if it is None:
        g.msg("You've no shells to hand up.", "info")
        return
    if shells_short(v) <= 0:
        g.msg(f"The {v.vt.name}'s racks are full.", "info")
        return
    n = min(shells_short(v), (it.data or {}).get("rounds", CRATE_ROUNDS))
    _load_rounds(v, n)
    if p.invent.hands is it:
        p.invent.hands = None
    else:
        p.remove_item(it)
    v.ai["handed_by_player"] = v.ai.get("handed_by_player", 0) + n
    g.msg(f"You pass {n} rounds up to the loader, one at a time. '{'Danke' if v.nation == 'germany' else 'Thanks, mate' if v.nation in ('uk', 'australia', 'newzealand', 'canada') else 'Spasibo' if v.nation == 'ussr' else 'Thanks'}.'",
          "good")
    ps.act(int(n * STOW_TIME * 1.5 * 100))       # you and the loader, a round at a time


def riders_capacity(v) -> int:
    """Seats inside - or, for a tank with none, room on the engine deck for a section of riders."""
    if v.vt.seats:
        return v.vt.seats
    return RIDERS if v.vt.vtype in ("tank", "td", "spg") else 0


def consume_parts(game, vehicle, amount):
    if amount <= 0:
        return True
    for truck in game.vehicles:
        if truck is not vehicle and truck.active and truck.side == vehicle.side and vehicle.near(truck.x, truck.y) <= 8:
            if truck.ai.get("parts_cargo", 0) >= amount:
                truck.ai["parts_cargo"] -= amount
                return True
    if at_motor_pool(game, vehicle):
        from .sustain import take
        return take(game.sector, vehicle.side, "parts", amount)
    return False
