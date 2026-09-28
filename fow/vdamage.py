"""What a vehicle is made of, and what breaking each part costs it.

A vehicle isn't a bag of hit points (the hull's "hp" is only how much more it can take before it's a
wreck).  It is running gear, an engine and a transmission that move it; a gun, a turret ring and
sights that fight it; machine guns; a radio that ties it to everyone else; fuel and ammunition that
can burn it; and the men in its seats.  A hit breaks particular things, and each broken thing takes
away its own work and nothing else:

- a thrown track or a smashed transmission: it can't move - but it can still shoot;
- a dead engine: it can't move, and without power the turret is cranked round by hand;
- a jammed turret ring: the gun points where it pointed, and the hull has to swing to aim it;
- smashed sights: the gunner lays over open sights, and buttoned up the crew is half blind;
- a damaged gun fires wild and loads slowly; a knocked-out one doesn't fire at all;
- a dead radio: orders come by flag and shout, and there's no calling for anything;
- holed fuel tanks make the next hit likelier to set it alight; a hit in the ammunition racks can
  send the whole thing up.

Each part is 2 (working), 1 (damaged: it works, badly) or 0 (knocked out).  A crewman hit in his
seat leaves it empty until the others shift round to cover it (crew.manned).
"""
from __future__ import annotations

OK, DAMAGED, OUT = 2, 1, 0

WHEELED = ("truck", "car", "armcar")
ARMOURED = ("tank", "ltank", "tankette", "td", "spg", "armcar", "halftrack", "amtrac")


def parts_for(vt) -> dict:
    p = {}
    boat = vt.vtype == "lc"
    if vt.speed and not vt.static:
        if not boat:
            p["tracks"] = OK
        p["engine"] = OK
        p["transmission"] = OK
        p["fuel"] = OK
    if vt.main:
        p["gun"] = OK
        if vt.turret and not vt.static:
            p["turret"] = OK
    if vt.main or (vt.vtype in ARMOURED and not vt.open_top):
        p["optics"] = OK
    for i in range(len(vt.mgs or ())):
        p[f"mg{i}"] = OK
    if vt.vtype in ARMOURED:
        p["radio"] = OK
    if vt.ap or vt.he:
        p["ammo"] = OK
    return p


def state(v, part) -> int:
    return v.parts.get(part, OK)


# ============================================================================ what each part does
def can_move(v) -> bool:
    return state(v, "engine") > OUT and state(v, "transmission") > OUT and state(v, "tracks") > OUT


def move_mult(v) -> float:
    """Damaged, not broken: an engine running rough, a gearbox stuck in low, a bent road wheel."""
    m = 1.0
    if state(v, "engine") == DAMAGED:
        m *= 1.6
    if state(v, "transmission") == DAMAGED:
        m *= 1.4
    if state(v, "tracks") == DAMAGED:
        m *= 1.5
    return m


def traverse(v) -> str:
    """How the gun is swung: 'power', 'hand' (a dead engine, a damaged ring) or 'jammed'.  Turretless
    guns and gun shields are 'hull'."""
    if "turret" not in v.parts:
        return "hull"
    t = state(v, "turret")
    if t == OUT:
        return "jammed"
    if t == DAMAGED or state(v, "engine") == OUT:
        return "hand"
    return "power"


HAND_TRAVERSE = 300               # moves to crank the turret an eighth of the way round


def turret_turns(v) -> bool:
    """Does the gun turn independently of the hull?"""
    return traverse(v) in ("power", "hand")


def gun_disp(v) -> float:
    """Extra spread (degrees) from a damaged gun and damaged sights."""
    d = 0.0
    if state(v, "gun") == DAMAGED:
        d += 1.2
    o = state(v, "optics")
    if o == DAMAGED:
        d += 0.8
    elif o == OUT:
        d += 2.5
    return d


def reload_mult(v) -> float:
    return 1.3 if state(v, "gun") == DAMAGED else 1.0


def optics_mult(v) -> float:
    return {OK: 1.0, DAMAGED: 0.75, OUT: 0.5}[state(v, "optics")]


def mg_ok(v, i) -> bool:
    return state(v, f"mg{i}") > OUT


def has_radio(game, v) -> bool:
    """A set fitted (command.vehicle_has_radio: early Soviet, Japanese and French tanks mostly had none),
    and not shot to pieces."""
    from .command import vehicle_has_radio
    return vehicle_has_radio(game, v)


# ============================================================================ words
PART_NAME = {"tracks": "tracks", "engine": "engine", "transmission": "transmission", "gun": "main gun",
             "turret": "turret ring", "optics": "sights and periscopes", "radio": "radio", "fuel": "fuel tanks",
             "ammo": "ammunition racks"}
BROKEN = {
    "tracks": ("running gear damaged", "a track broken - immobilised"),
    "engine": ("engine running rough", "engine dead"),
    "transmission": ("stuck in low gear", "transmission smashed - immobilised"),
    "gun": ("gun damaged - fires wild", "gun knocked out"),
    "turret": ("turret cranked by hand", "turret jammed"),
    "optics": ("sights cracked", "sights smashed"),
    "radio": ("radio damaged", "radio dead"),
    "fuel": ("fuel tanks holed", "fuel tanks holed"),
    "ammo": ("ammunition racks hit", "ammunition racks hit"),
}


def part_name(v, part) -> str:
    if part == "tracks":
        return "wheels" if v.vt.vtype in WHEELED else "running gear" if v.vt.vtype == "halftrack" else "tracks"
    if part.startswith("mg"):
        from .data.items import ITEMS
        i = int(part[2:])
        mgs = v.vt.mgs or ()
        nm = ITEMS[mgs[i]].name if i < len(mgs) and mgs[i] in ITEMS else "machine gun"
        from .crew import _mg_station
        where = {"gunner": "coaxial" if v.vt.main else ""}.get(_mg_station(v.vt, i), "bow" if v.vt.main else "hull")
        return f"{where} {nm}".strip()
    return PART_NAME.get(part, part)


def broken_word(v, part) -> str | None:
    s = state(v, part)
    if s == OK:
        return None
    if part.startswith("mg"):
        return f"{part_name(v, part)} out" if s == OUT else f"{part_name(v, part)} damaged"
    words = BROKEN.get(part)
    if words is None:
        return f"{part_name(v, part)} damaged"
    w = words[1 if s == OUT else 0]
    if part == "tracks" and v.vt.vtype in WHEELED:
        w = w.replace("a track broken", "a wheel shot off").replace("running gear", "wheels")
    return w


def damage_list(v) -> list[str]:
    order = ("tracks", "engine", "transmission", "gun", "turret", "optics", "radio", "fuel", "ammo")
    out = [w for p in order if p in v.parts and (w := broken_word(v, p))]
    out += [w for p in sorted(v.parts) if p.startswith("mg") and (w := broken_word(v, p))]
    return out


def visible_damage(v) -> list[str]:
    """What you can see of it from outside: a track lying off, a gun barrel split, smoke, holes."""
    out = []
    if state(v, "tracks") == OUT:
        out.append("a wheel shot off" if v.vt.vtype in WHEELED else "a track lying off")
    if state(v, "gun") == OUT:
        out.append("gun barrel wrecked")
    if v.burning:
        out.append("burning")
    elif state(v, "engine") == OUT and v.ai.get("smoking", 0) > 0:
        out.append("smoke from the engine deck")
    holes = v.ai.get("holes", 0)
    if holes:
        out.append(f"holed{' ' + str(holes) + ' times' if holes > 1 else ''}")
    if v.abandoned:
        out.append("hatches open, crew gone")
    return out


# ============================================================================ taking hits
# where a round that gets inside goes, by the face it came through (a crewman's seat, or a part)
LOCATIONS = {
    0: [("driver", 12), ("mg1", 8), ("gun", 10), ("optics", 8), ("transmission", 12), ("gunner", 10),
        ("loader", 6), ("commander", 6), ("ammo", 12), ("turret", 8), ("radio", 4), ("engine", 4)],
    1: [("tracks", 14), ("engine", 12), ("fuel", 10), ("ammo", 16), ("gunner", 8), ("loader", 8), ("driver", 8),
        ("commander", 6), ("turret", 8), ("transmission", 5), ("radio", 5)],
    2: [("engine", 30), ("fuel", 20), ("transmission", 15), ("tracks", 10), ("ammo", 5), ("loader", 5),
        ("commander", 5)],
    3: [("engine", 20), ("fuel", 10), ("turret", 12), ("optics", 10), ("commander", 10), ("loader", 8),
        ("gunner", 8), ("driver", 8), ("ammo", 10), ("radio", 4)],
}
SEATS = ("driver", "gunner", "loader", "commander", "mg0", "mg1", "mg2", "mg3")


def _candidates(v, face):
    from .crew import manned, stations
    here = set(stations(v.vt))
    men = manned(v)
    out = []
    for loc, w in LOCATIONS.get(face, LOCATIONS[1]):
        if loc in SEATS:
            if loc in here and (loc in men or v.player_crewed and v.player_station == loc):
                out.append((loc, w))
        elif loc in v.parts:
            out.append((loc, w))
    # the machine guns themselves, wherever they are
    for p in v.parts:
        if p.startswith("mg"):
            out.append((f"part:{p}", 3))
    return out


def _pick(rng, cands):
    tot = sum(w for _, w in cands)
    if tot <= 0:
        return None
    r = rng.random() * tot
    for loc, w in cands:
        r -= w
        if r <= 0:
            return loc
    return cands[-1][0]


def penetrated(game, v, face, dmg, kind, attacker, source, seen) -> list[str]:
    """Inside: the round (or the spall it knocks off the armour) hits one to three things.  Returns
    what it hit, for the messages and the crew's decision."""
    rng = game.rng
    v.ai["holes"] = v.ai.get("holes", 0) + 1
    n = 1 + (rng.random() < 0.55) + (dmg > 250 and rng.random() < 0.5)
    hit = []
    for _ in range(n):
        cands = [c for c in _candidates(v, face) if c[0] not in hit]
        loc = _pick(rng, cands)
        if loc is None:
            break
        hit.append(loc)
        if loc.startswith("part:"):             # a machine gun itself (its seat has the same name)
            if break_part(game, v, loc[5:], OUT, attacker, source, seen) == "boom":
                return hit + ["boom"]
        elif loc in SEATS:
            crew_hit(game, v, loc, attacker, source, seen)
        elif break_part(game, v, loc, OUT if rng.random() < 0.6 else DAMAGED, attacker, source, seen) == "boom":
            return hit + ["boom"]
    return hit


def break_part(game, v, part, to, attacker=None, source=None, seen=False) -> str | None:
    """Knock a part down to `to` (never mends it).  Returns 'boom' if the vehicle went up."""
    if part not in v.parts or v.dead:
        return None
    rng = game.rng
    before = v.parts[part]
    if to >= before:
        return None
    v.parts[part] = to
    name = game.name_of_vehicle(v)
    mine = game.player is not None and game.player.vehicle is v
    tell = mine or seen
    if part == "ammo":
        rounds = v.ap + v.he
        # a round among the racks: propellant catches, and the whole load may go
        if rounds and rng.random() < min(0.75, 0.25 + rounds / 150):
            from .combat import destroy_vehicle
            if seen or mine:
                game.msg(f"{name} explodes in a sheet of flame as its ammunition goes up!", "death", v.pos)
            destroy_vehicle(game, v, attacker, source, catastrophic=True)
            return "boom"
        lost = int(rounds * rng.uniform(0.1, 0.3))
        for _ in range(lost):
            if v.he > 0 and (v.ap <= 0 or rng.random() < 0.5):
                v.he -= 1
            elif v.ap > 0:
                v.ap -= 1
        v.burning = max(v.burning, rng.randint(10, 40)) if rng.random() < 0.5 else v.burning
    elif part == "fuel" and rng.random() < 0.3:
        v.burning = max(v.burning, rng.randint(20, 60))
    elif part == "engine":
        v.ai["smoking"] = game.turn
        if rng.random() < 0.2:
            v.burning = max(v.burning, rng.randint(15, 45))
    if tell:
        w = broken_word(v, part)
        if mine:
            game.msg(f"{_crew_shout(part, to)} ({w})", "warn")
        elif part in ("tracks", "gun") and to == OUT:
            game.msg(f"{name}: {w}.", "combat", v.pos)
    return None


def _crew_shout(part, to) -> str:
    return {
        "tracks": "'We've lost a track! We're not going anywhere!'" if to == OUT else "'Running gear's hit - she's dragging!'",
        "engine": "'Engine's gone!'" if to == OUT else "'Engine's hit - she's running rough!'",
        "transmission": "'Transmission's smashed - she won't move!'" if to == OUT else "'Gearbox is jammed in low!'",
        "gun": "'The gun's knocked out!'" if to == OUT else "'Gun's damaged - the recoil's all wrong!'",
        "turret": "'Turret's jammed!'" if to == OUT else "'Traverse is shot - cranking by hand!'",
        "optics": "'Sights are smashed - I'm blind in here!'" if to == OUT else "'Sight's cracked!'",
        "radio": "'Radio's dead!'",
        "fuel": "'Fuel tank's holed - I can smell petrol!'",
        "ammo": "'Hit in the racks!'",
    }.get(part, "'Machine gun's out!'")


def crew_hit(game, v, seat, attacker, source, seen, quiet=False):
    """A man hit in his seat: you, if it's yours; otherwise the seat is empty until the crew shifts."""
    from .combat import hit_actor
    rng = game.rng
    p = game.player
    if v.player_crewed and p is not None and p.vehicle is v and v.player_station == seat:
        hit_actor(game, p, rng.uniform(20, 55), "fragment", attacker, source)
        return
    from .crew import manned
    if seat not in manned(v) or v.crew <= 0:
        return
    v.crew -= 1
    if attacker is not None and hasattr(attacker, "kills"):
        attacker.kills += 1
    so = v.ai.setdefault("seat_out", {})
    so[seat] = game.turn + rng.randint(20, 60)          # dragging him clear, and someone climbing across
    v.__dict__.pop("_manned", None)
    mine = p is not None and p.vehicle is v
    if mine:
        from .crew import name as seat_name
        game.msg(f"The {seat_name(v.vt, seat).lower()} is hit!", "warn")
    elif seen and not quiet:
        game.msg(f"A crewman of {game.name_of_vehicle(v)} is hit.", "combat", v.pos)
    if v.crew <= 0 and not v.player_crewed:
        v.abandoned = True
        if v.passengers:
            game.disembark_all(v)


def glanced(game, v, face, kind, pen, armor, he_power=0, attacker=None, source=None, seen=False):
    """It didn't get in - but things outside the armour still break."""
    rng = game.rng
    if kind in ("bullet", "frag"):
        # periscopes and vision blocks, the aerial, a machine gun's barrel
        if rng.random() < (0.03 if kind == "bullet" else 0.05):
            break_part(game, v, "optics", max(OUT, state(v, "optics") - 1), attacker, source, seen)
        elif rng.random() < 0.01:
            break_part(game, v, "radio", OUT, attacker, source, seen)
        return
    if kind == "he":
        if rng.random() < he_power / 1500 and not v.vt.static:
            break_part(game, v, "tracks", OUT if rng.random() < 0.7 else DAMAGED, attacker, source, seen)
        if rng.random() < he_power / 2500:
            break_part(game, v, "optics", max(OUT, state(v, "optics") - 1), attacker, source, seen)
        if rng.random() < he_power / 4000:
            break_part(game, v, "radio", OUT, attacker, source, seen)
        return
    # a solid shot that didn't get in: it can still jam the ring, split the barrel, break the running gear
    r = rng.random()
    if face == 0 and r < 0.04:
        break_part(game, v, "gun", DAMAGED if rng.random() < 0.6 else OUT, attacker, source, seen)
    elif r < 0.08:
        break_part(game, v, "turret", DAMAGED if rng.random() < 0.5 else OUT, attacker, source, seen)
    elif face == 1 and r < 0.2:
        break_part(game, v, "tracks", OUT if rng.random() < 0.6 else DAMAGED, attacker, source, seen)


def exposed_hit(game, v, kind, attacker, source, seen) -> bool:
    """A commander with his head out of the hatch, when bullets or splinters are flying round the turret."""
    seat = hatch_user(v)
    if v.buttoned or seat is None:
        return False
    from .crew import manned
    if seat not in manned(v) and not (v.player_crewed and v.player_station == seat):
        return False
    ch = {"bullet": 0.12, "frag": 0.2, "he": 0.3}.get(kind, 0.0)
    if game.rng.random() >= ch:
        return False
    crew_hit(game, v, seat, attacker, source, seen)
    return True


def bail_chance(v, hit) -> float:
    """After a penetration: the crew's decision to get out.  Most crews didn't wait to see whether it would
    catch: a round inside was reason enough, a man hit or a smell of smoke more so."""
    c = 0.3
    if v.burning:
        c += 0.55
    if state(v, "gun") == OUT or (v.vt.main is None and all(state(v, f"mg{i}") == OUT for i in
                                                             range(len(v.vt.mgs or ())))):
        c += 0.3
    if not can_move(v):
        c += 0.12
    c += 0.15 * sum(1 for h in hit if h in SEATS)
    if v.hp < v.vt.hp * 0.3:
        c += 0.2
    return min(0.95, c)


# ============================================================================ hatches
# how readily a nation's tank commanders fought head-out (the Germans, British and Americans as a rule;
# Soviet crews mostly buttoned up - the T-34 had no cupola to speak of until 1943)
HEADS_OUT = {"ussr": 0.3, "japan": 0.5, "italy": 0.6, "france": 0.5, "china": 0.5}


def hatch_user(v) -> str | None:
    """The seat whose hatch matters for seeing out: the commander's (or, in a two-man vehicle, the gunner
    doubling as commander).  None if it's open-topped, a gun, or soft-skinned."""
    vt = v.vt
    if vt.open_top or vt.static or vt.vtype in ("truck", "car", "lc"):
        return None
    from .crew import stations
    st = stations(vt)
    return "commander" if "commander" in st else "gunner" if "gunner" in st else "driver"


def hatch_ai(game, v):
    """The commander's head: out to see when it's quiet (or, for some, even in a fight at a distance);
    down, hatch shut, when he's being shot at, shelled, or there are infantry close."""
    seat = hatch_user(v)
    if seat is None or v.crew <= 0 or v.abandoned:
        return
    if v.player_crewed and v.player_station == seat:
        return                                        # yours to open and shut
    from .crew import is_manned
    if not is_manned(v, seat):
        v.buttoned = True                             # nobody in the seat: nobody's head out of the hatch
        return
    t = game.turn
    close_inf = any(getattr(e, "vt", None) is None and abs(e.x - v.x) + abs(e.y - v.y) < 14
                    for e in (v.visible or ()))
    danger = t - v.ai.get("hit_turn", -999) < 60 or t - v.ai.get("near_blast", -999) < 30 or close_inf
    sq = v.squad
    contact = bool(v.visible) or (sq is not None and t - sq.last_contact < 60)
    style = v.ai.get("heads_out")
    if style is None:
        style = v.ai["heads_out"] = game.rng.random() < HEADS_OUT.get(v.nation, 0.85)
    want_open = not danger and (not contact or style)
    if want_open == v.buttoned:
        v.buttoned = not want_open
        p = game.player
        if p is not None and p.vehicle is v:
            game.msg("The commander pushes his hatch open and stands up to look." if want_open else
                     "The commander drops down and slams his hatch shut.", "info")


def tick(game):
    """Every few seconds: the men who shifted seats have settled; engines stop smoking; hatches."""
    for v in game.vehicles:
        if not v.dead:
            hatch_ai(game, v)
        so = v.ai.get("seat_out")
        if so:
            for s, until in list(so.items()):
                if game.turn >= until:
                    del so[s]
                    v.__dict__.pop("_manned", None)
            if not so:
                v.ai.pop("seat_out", None)
        sm = v.ai.get("smoking")
        if sm is not None and game.turn - sm > 600:
            v.ai.pop("smoking", None)


def repair(v, part):
    v.parts[part] = OK
