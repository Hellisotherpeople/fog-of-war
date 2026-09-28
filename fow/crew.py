"""Crew stations.

A tank is five men doing five jobs.  The driver drives and sees through a slit; the
gunner lays and fires the main gun and the coaxial MG; the loader feeds it; the bow
gunner (the radio operator, usually) has a hull machine gun that points where the hull
points; the commander, head out of the hatch, finds targets and tells everyone else
what to do.  Short-handed crews double up: a three-man turret, a commander who is also
the gunner, a gun nobody's firing.

Every weapon belongs to a station.  Each manned station works on its own: the bow
gunner hoses a treeline while the gunner lays on a tank, and neither waits on the
other.  If you're in one of the seats you do that job and no other - the others are
done by the men around you, or not at all.
"""
from __future__ import annotations

from .gamemap import octant

NAMES = {"commander": "Commander", "gunner": "Gunner", "loader": "Loader", "driver": "Driver",
         "mg1": "Bow gunner", "mg2": "Machine gunner", "mg3": "Machine gunner", "mg0": "Machine gunner"}
SHORT = {"commander": "Cdr", "gunner": "Gun", "loader": "Ldr", "driver": "Drv", "mg0": "MG", "mg1": "Bow",
         "mg2": "MG", "mg3": "MG"}


def _mg_station(vt, i) -> str:
    """Which seat works machine gun i."""
    if vt.aa and not vt.main:
        return "gunner"                    # the quad mount: one man, four guns
    if i == 0 and (vt.main is None or vt.turret):
        return "gunner"                    # the coax - or the only gun
    return f"mg{i}"


def stations(vt) -> list[str]:
    """Seats in the order a crew fills them."""
    out = []
    if not vt.static:
        out.append("driver")
    if vt.main or vt.mgs:
        out.append("gunner")
    if vt.main and vt.crew >= 3:
        out.append("loader")
    for i in range(len(vt.mgs or ())):
        s = _mg_station(vt, i)
        if s not in out:
            out.append(s)
    if vt.crew >= 3:
        out.append("commander")
    return out


def name(vt, st) -> str:
    if st.startswith("mg"):
        if vt.open_top or vt.static:
            return "Machine gunner"
        return "Bow gunner" if vt.main else "Hull gunner"
    if st == "gunner" and not vt.main:
        return "Gunner"
    return NAMES.get(st, st.title())


def manned(v) -> set:
    """The seats with a man in them.  The crew fills the important seats first - but a man just hit
    leaves his seat empty until the others have pulled him clear and one of them climbed across
    (v.ai["seat_out"], cleared by vdamage.tick)."""
    out_now = v.ai.get("seat_out") or {}
    key = (v.crew, v.player_crewed, v.__dict__.get("player_station"), tuple(sorted(out_now)))
    cache = v.__dict__.get("_manned")
    if cache and cache[0] == key:
        return cache[1]
    seats = stations(v.vt)
    n = v.crew
    out = set()
    ps = v.__dict__.get("player_station") if v.player_crewed else None
    if ps in seats:
        out.add(ps)
        n -= 1
    for s in seats:
        if n <= 0:
            break
        if s not in out and s not in out_now:
            out.add(s)
            n -= 1
    v._manned = (key, out)
    return out


def is_manned(v, st) -> bool:
    return st in manned(v)


def ai_manned(v, st) -> bool:
    """Manned by someone other than you."""
    return st in manned(v) and not (v.player_crewed and v.__dict__.get("player_station") == st)


def player_seat(v):
    return v.__dict__.get("player_station") if v.player_crewed else None


def default_seat(v, role=None) -> str:
    """Where you sit when you climb in: the most important empty seat (or the commander's)."""
    seats = stations(v.vt)
    # the seats not already filled by the rest of the crew (who fill them in order)
    others = v.crew - 1 if v.player_crewed else v.crew
    free = seats[max(0, others):]
    if free:
        return free[0]
    return seats[0] if seats else "driver"


def mgs_for(v, st) -> list[int]:
    return [i for i in range(len(v.vt.mgs or ())) if _mg_station(v.vt, i) == st]


def mg_arc_ok(v, i, tx, ty) -> bool:
    """Can MG i bear on the tile?  A bow gun only points where the hull does."""
    vt = v.vt
    st = _mg_station(vt, i)
    if st == "gunner" or vt.open_top or vt.static:
        return True
    want = octant(tx - v.x, ty - v.y)
    return (want - v.facing) % 8 in (0, 1, 7)


def gunner_can_drive(v) -> bool:
    """Does the vehicle have nobody at the wheel but you?"""
    return not is_manned(v, "driver")


def can(v, action) -> tuple[bool, str]:
    """May the player, in their seat, do this?  Returns (ok, why not)."""
    st = player_seat(v)
    if st is None:
        return False, "You're a passenger."
    vt = v.vt
    if action == "drive":
        if vt.static:
            return False, "It doesn't drive."
        if st == "driver":
            return True, ""
        if st == "commander":
            return (True, "") if is_manned(v, "driver") else (False, "Nobody's in the driver's seat.")
        return False, f"You're the {name(vt, st).lower()} - the driver drives."
    if action == "main":
        if not vt.main:
            return False, "There's no main gun."
        if st == "gunner":
            return True, ""
        if st == "commander":
            return (True, "") if is_manned(v, "gunner") else (False, "Nobody's on the gun.")
        return False, f"You're the {name(vt, st).lower()} - the gunner has the gun."
    if action == "mg":
        if st == "commander":
            return (True, "") if any(ai_manned(v, _mg_station(vt, i)) for i in range(len(vt.mgs or ()))) \
                else (False, "Nobody's on the machine guns.")
        if mgs_for(v, st):
            return True, ""
        return False, f"You're the {name(vt, st).lower()} - there's no machine gun at your seat."
    if action == "ammo":
        return (True, "") if st in ("loader", "gunner", "commander") else (False, "The loader chooses the rounds.")
    return True, ""


def target_word(e) -> str:
    vt = getattr(e, "vt", None)
    if vt is not None:
        return {"tank": "tank", "ltank": "light tank", "tankette": "tankette", "td": "tank destroyer",
                "spg": "assault gun", "halftrack": "half-track", "armcar": "armoured car", "truck": "truck",
                "car": "car", "atgun": "anti-tank gun", "aagun": "flak gun", "fieldgun": "gun",
                "lc": "landing craft", "amtrac": "amtrac"}.get(vt.vtype, "vehicle")
    role = getattr(e, "role", "")
    if role in ("lmg_gunner", "hmg_gunner"):
        return "machine gun"
    if role == "at_soldier":
        return "bazooka team"
    return "infantry"


def clock_word(v, tx, ty) -> str:
    """Target direction as a clock bearing off the hull's nose."""
    import math
    fx, fy = _FV[v.facing % 8]
    hull = math.atan2(fy, fx)
    ang = math.atan2(ty - v.y, tx - v.x)
    rel = (ang - hull) % (2 * math.pi)                 # clockwise on screen (y down)
    hour = int(round(rel / (2 * math.pi) * 12)) % 12
    return f"{12 if hour == 0 else hour} o'clock"


from .footprint import FACING_VEC as _FV   # noqa: E402


def seat_help(v, st) -> str:
    vt = v.vt
    if st == "driver":
        return "Move keys drive."
    if st == "gunner":
        bits = []
        if vt.main:
            bits.append("f fires the " + ("gun" if not vt.turret else "main gun") + ", F picks the round")
            if vt.turret:
                bits.append("move keys traverse the turret")
        if mgs_for(v, "gunner"):
            bits.append("v the " + ("coax" if vt.main else "machine gun"))
        return ("; ".join(bits) + ".").capitalize() if bits else ""
    if st == "loader":
        return "r hurries the next round, F changes the round."
    if st.startswith("mg"):
        return "v fires your gun" + ("" if vt.open_top or vt.static else " (it points where the hull points)") + "."
    if st == "commander":
        return "Move keys order the driver; f and v give the gunners a target; e for crew orders."
    return ""
