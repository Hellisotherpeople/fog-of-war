"""Ballistics, explosions, damage to people, vehicles and terrain."""
from __future__ import annotations

from .constants import cap

import math

import numpy as np
import tcod

from . import tiles as T
from .body import PART_NAME
from .constants import other_side
from .data.items import ITEMS
from .entities import riding
from .gamemap import octant

# silhouette half-width (tiles) and vertical exposure by stance
HALF_WIDTH = {0: 0.34, 1: 0.30, 2: 0.26}
VERTICAL = {0: 0.95, 1: 0.78, 2: 0.52}
LOW_COVER_STANCE = {0: 0.45, 1: 0.85, 2: 1.0}


# ====================================================================== accuracy

# ====================================================================== marksmanship
#
# Aim is a sight picture that takes time to build: a snap shot, an aimed shot, careful aim, a
# precise shot (and, through a scope, a long steady one).  Every level costs time - more for a
# long, heavy rifle than a pistol, more still if you're blown or hurt - and moving, flinching or
# switching targets throws it away.  Recoil is what each shot does to the next: it kicks the muzzle
# off the target and takes a moment to settle.  Full-power rifle rounds kick hard; a pistol-calibre
# SMG barely does, but a burst climbs.  Prone, braced, on a bipod or tripod, it's tamed.

CAL_KICK = {"3006": 1.0, "303": 0.95, "762r": 1.0, "792": 1.0, "792ds": 1.0, "8x56": 1.05, "8lebel": 1.0,
            "77jp": 0.95, "75fr": 0.9, "65jp": 0.7, "65it": 0.75, "792k": 0.6, "30carb": 0.4, "12ga": 1.3,
            "45acp": 0.42, "9mm": 0.3, "9glis": 0.3, "9x25": 0.34, "762t": 0.3, "763m": 0.3, "765l": 0.22,
            "8nambu": 0.25, "38200": 0.3, "55boys": 2.6, "145": 2.8, "20mm": 3.2}
AIM_MULT = (1.0, 0.78, 0.63, 0.53, 0.45)
AIM_WORD = ("snap shot", "aimed", "careful aim", "precise", "dead steady")
AIM_BASE = {"pistol": 45, "smg": 55, "shotgun": 50, "carbine": 60, "rifle": 75, "sniper": 90, "lmg": 90,
            "hmg": 70, "at_rifle": 100, "at_launcher": 110, "at_disposable": 100, "assault": 65}


def kick(t) -> float:
    """Degrees the muzzle jumps per round, standing, for an average man."""
    k = t.get("kick")
    if k:
        return k
    e = CAL_KICK.get(t.cal, max(0.2, t.dmg / 42.0))
    return 1.6 * e / max(0.6, t.weight / 4.0) ** 0.6


def recoil_per_round(a, t) -> float:
    r = kick(t)
    st = a.stance
    r *= {0: 1.0, 1: 0.75, 2: 0.45}[st]
    if t.deploy and a.deployed:
        r *= 0.3                                  # tripod
    elif t.cat == "lmg" and st == 2:
        r *= 0.7                                  # on its bipod
    from .skills import level
    r *= max(0.6, 1.25 - level(a, "marksmanship") * 0.05)
    if "strong" in a.traits:
        r *= 0.85
    if "shaky" in a.traits:
        r *= 1.15
    return r


def settle_recoil(a):
    """Once a second: the muzzle comes back down."""
    r = getattr(a, "recoil", 0.0)
    if r:
        a.recoil = 0.0 if r < 0.08 else r * 0.35


def max_aim(a, t) -> int:
    if t.cat == "shotgun":
        return 1
    if t.cat in ("pistol", "smg"):
        return 2
    if t.cat in ("at_launcher", "at_disposable"):
        return 2
    return 4 if t.scope else 3


def aim_time(a, t) -> int:
    """Moves to add one level of aim."""
    c = AIM_BASE.get(t.cat, 70)
    if t.cat in ("lmg", "hmg") and (a.stance == 2 or a.deployed):
        c *= 0.8
    elif t.weight > 6 and a.stance == 0:
        c *= 1.3                                   # a heavy gun held up offhand
    c *= 1 + a.body.aim_penalty() * 0.25
    if getattr(a, "stamina", 100.0) < 35:
        c *= 1.3                                   # chest heaving, the sights won't settle
    if a.suppression > 30:
        c *= 1 + (a.suppression - 30) / 70
    from .skills import level
    c *= max(0.7, 1.2 - level(a, "gunnery" if t.cat == "hmg" else "marksmanship") * 0.045)   # a trained eye
    from .familiar import slow
    c *= slow(a, t)                                # whose sights are these?
    return int(c)


def aim_level(a, tx, ty) -> int:
    """The aim you'd have on (tx, ty) right now."""
    if a.aim_turns <= 0 or a.aim_target is None:
        return 0
    ax, ay = a.aim_target
    d = max(abs(ax - tx), abs(ay - ty))
    if d == 0:
        return a.aim_turns
    if d == 1:
        return max(0, a.aim_turns - 1)             # he moved a step: follow him, lose a little
    return 0


def after_shot_aim(a, t, rounds):
    """What firing does to the sight picture."""
    if rounds > 1:
        a.aim_turns = 0
        return
    bolt = t.cat in ("rifle", "sniper", "at_rifle") and t.shot_cost >= 100
    a.aim_turns = max(0, a.aim_turns - (2 if bolt else 1))


def dispersion(game, shooter, weapon, tx: int, ty: int, burst_index: int = 0) -> float:
    """Total angular error (degrees, 1 sigma) for a shot."""
    t = weapon.t
    d = t.disp
    from .skills import level
    skill = level(shooter, "gunnery" if t.cat == "hmg" else "marksmanship")
    d += max(0.0, (8 - skill)) * 0.14
    st = shooter.stance
    if t.deploy and not (st == 2 or shooter.deployed):
        d += 2.4                     # firing a tripod MG from the hip
    d += {0: 0.9, 1: 0.45, 2: 0.0}[st] * (1.4 if t.cat in ("lmg", "hmg") else 1.0)
    if shooter.moved_turn >= game.turn - 1:
        d += 1.2
    d += shooter.suppression / 28.0
    d += shooter.body.aim_penalty()
    d += max(0.0, 35.0 - getattr(shooter, "stamina", 100.0)) / 35.0 * 0.9     # heaving chest
    if weapon.heat > 60:
        d += (weapon.heat - 60) / 25
    from .familiar import sloppy
    d += sloppy(shooter, t)
    if "temp" in shooter.body.__dict__:
        from .thermal import aim_penalty
        d += aim_penalty(shooter)                  # shaking with cold, or reeling in the heat
    if getattr(shooter, "ai", None) is not None:
        from .pace import aim_penalty as pace_penalty
        d += pace_penalty(game, shooter)           # firing on the run, or too tired to hold it steady
    # careful aim
    lvl = min(aim_level(shooter, tx, ty), len(AIM_MULT) - 1)
    d *= AIM_MULT[lvl]
    # the last round's kick (and this burst's climb) hasn't settled
    d += getattr(shooter, "recoil", 0.0)
    if t.scope:
        dist = math.hypot(tx - shooter.x, ty - shooter.y)
        if dist < 8:
            d += 0.8                 # scopes are useless up close
    if "crack_shot" in shooter.traits:
        d *= 0.8
    if "shaky" in shooter.traits:
        d *= 1.25
    return max(0.08, d)


def estimate_hit(game, shooter, weapon, target) -> float:
    """Rough probability that a single aimed shot hits the target (for AI and UI)."""
    dx, dy = target.x - shooter.x, target.y - shooter.y
    dist = max(1.0, math.hypot(dx, dy))
    sig = math.radians(dispersion(game, shooter, weapon, target.x, target.y))
    lateral_sigma = max(0.02, dist * math.tan(sig))
    stance = getattr(target, "stance", 0)
    hw = HALF_WIDTH.get(stance, 0.3) if not hasattr(target, "vt") else 0.55
    # probability |N(0, s)| < hw
    p_lat = math.erf(hw / (lateral_sigma * math.sqrt(2)))
    p_vert = VERTICAL.get(stance, 0.9) if not hasattr(target, "vt") else 1.0
    m = game.map
    if not hasattr(target, "vt"):
        cov = m.cover_toward(target.x, target.y, shooter.x, shooter.y) / 100.0
        pos = m.pos_cover[target.x, target.y] / 100.0
        p_vert *= (1 - pos * {0: 0.4, 1: 0.75, 2: 0.95}[stance])
        p_cover = 1 - cov * LOW_COVER_STANCE[stance]
    else:
        p_cover = 1.0
    rng_pen = 1.0
    if dist > weapon.t.rng:
        rng_pen = max(0.1, 1 - (dist - weapon.t.rng) / (weapon.t.rng * 1.5))
    return max(0.0, min(0.99, p_lat * p_vert * p_cover * rng_pen))


def describe_chance(p: float) -> tuple[str, tuple]:
    if p > 0.75:
        return "a sure thing", (140, 240, 140)
    if p > 0.5:
        return "a good shot", (180, 230, 120)
    if p > 0.3:
        return "a fair chance", (230, 210, 100)
    if p > 0.15:
        return "a long shot", (240, 160, 80)
    if p > 0.05:
        return "a prayer", (240, 110, 80)
    return "hopeless", (200, 70, 70)


# ====================================================================== firing

def fire_weapon(game, shooter, weapon, tx: int, ty: int, target=None, *, mode=None,
                area=False) -> int:
    """Fire the wielded gun at a tile.  Returns moves spent."""
    t = weapon.t
    if t.cat == "flamer":
        return fire_flamer(game, shooter, weapon, tx, ty)
    if t.cat == "mortar":
        return fire_mortar(game, shooter, weapon, tx, ty)
    if t.cat in ("at_launcher", "at_disposable"):
        return fire_launcher(game, shooter, weapon, tx, ty, target)
    if weapon.jammed:
        return 50
    if weapon.loaded <= 0:
        game.emit_sound(shooter.x, shooter.y, 8, "click", "a dry click", shooter.side, shooter)
        return 50
    mode = mode or weapon.mode_name
    if target is not None or area:
        from .skills import use
        use(game, shooter, "gunnery" if t.cat == "hmg" else "marksmanship", 0.4)   # practice at a real target
    rounds = 1
    cost = t.shot_cost
    if mode == "auto" or (t.modes == ("auto",)):
        rounds = min(weapon.loaded, t.burst + game.rng.randint(-1, 2))
        cost = t.burst_cost
    rounds = max(1, rounds)
    ox, oy = shooter.x, shooter.y
    base_ang = math.atan2(ty + 0.5 - (oy + 0.5), tx + 0.5 - (ox + 0.5))
    max_range = max(t.rng * 3, 30)
    hits = 0
    # sustained fire wanders
    wander = 0.0
    for i in range(rounds):
        if weapon.loaded <= 0:
            break
        weapon.loaded -= 1
        weapon.heat += t.heat
        shooter.stats["shots"] += 1
        # jam check
        jam = t.jam * (1 + max(0.0, weapon.heat - 70) / 40)
        if game.map.climate in ("desert", "volcanic"):
            jam *= 1.8
        if game.map.climate == "winter":
            jam *= 1.3
        if game.rng.random() < jam:
            weapon.jammed = True
            if shooter.is_player:
                game.msg(f"Your {t.name} jams!", "warn")
            break
        disp = dispersion(game, shooter, weapon, tx, ty, i)
        if area:
            disp += 2.0
        err = math.radians(game.rng.gauss(0, disp)) + wander
        if rounds > 1:
            wander += math.radians(game.rng.gauss(0, 0.25))
        shooter.recoil = min(6.0, getattr(shooter, "recoil", 0.0) + recoil_per_round(shooter, t))
        for _ in range(t.pellets):
            ang = base_ang + err + (math.radians(game.rng.gauss(0, 2.5)) if t.pellets > 1 else 0)
            res = trace_projectile(game, ox, oy, ang, max_range, t.dmg, t.pen, "bullet", shooter,
                                   target, t.name, mg=(t.cat in ("lmg", "hmg")),
                                   eff_range=t.rng)
            if res == "hit":
                hits += 1
    shooter.stats["hits"] += hits
    shooter.fired_turn = game.turn
    shooter.deployed = shooter.deployed or (t.deploy and shooter.stance == 2)
    loud = t.loud
    game.emit_sound(ox, oy, loud, "gunfire", t.sound, shooter.side, shooter, weapon=t.id, extra=rounds)
    game.effect_flash(ox, oy)
    # en-bloc clips fly out when empty (and a Garand pings)
    if t.feed == "clip" and weapon.loaded == 0 and weapon.mag_item is not None:
        weapon.mag_item = None
    if t.feed == "clip" and weapon.loaded == 0 and t.id == "m1_garand":
        game.emit_sound(ox, oy, 25, "ping", "the ping of an ejected Garand clip", shooter.side, shooter)
        if shooter.is_player:
            game.msg("*ping* The empty clip flies out.", "info")
    after_shot_aim(shooter, t, rounds)
    from .familiar import learn, level
    fam = level(shooter, t)
    if fam < 1.0:
        if t.cat in ("rifle", "sniper", "at_rifle", "shotgun") and t.shot_cost >= 100:
            cost = int(cost * (1 + (1 - fam) * 0.4))   # fumbling the bolt
        learn(game, shooter, t, 0.0035 * min(rounds, 4))
    return cost


def trace_projectile(game, ox: int, oy: int, ang: float, max_range: float, dmg: float, pen: float,
                     kind: str, shooter, intended, source_name: str, *, mg=False,
                     from_explosion=False, eff_range=40, skip_first=True, air=False) -> str:
    """Trace a single projectile.  Returns 'hit', 'terrain', 'vehicle' or 'miss'."""
    m = game.map
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    fx = ox + 0.5 + cos_a * max_range
    fy = oy + 0.5 + sin_a * max_range
    path = tcod.los.bresenham((ox, oy), (int(math.floor(fx)), int(math.floor(fy))))
    sx, sy = ox + 0.5, oy + 0.5
    rng = game.rng
    shooter_side = shooter.side if shooter is not None else None
    up = getattr(shooter, "z", 0) > 0 if shooter is not None and hasattr(shooter, "body") else False
    own_top = None
    if up:
        from .floors import inside, open_top
        own_top = open_top(game, shooter)
    endx, endy = ox, oy
    result = "miss"
    n = len(path)
    energy = dmg
    through = 1.0          # energy left after punching through cover
    for i in range(1 if skip_first else 0, n):
        x, y = int(path[i][0]), int(path[i][1])
        if not (0 <= x < m.w and 0 <= y < m.h):
            break
        endx, endy = x, y
        dist = math.hypot(x - ox, y - oy)
        # damage falloff past effective range
        if kind == "bullet":
            energy = dmg * through * (max(0.35, 1 - (dist - eff_range) / (eff_range * 2.5)) if dist > eff_range else 1.0)
        elif kind == "frag":
            energy = dmg * through * max(0.25, 1 - dist / max_range)
        # ---- creatures
        a = game.soldier_at.get((x, y))
        if a is not None and getattr(a, "z", 0) < 0:
            a = None                                  # (under the floor: nothing flying reaches the cellar)
        if a is not None and (a is not shooter or from_explosion) and a.alive:
            cx, cy = x + 0.5 - sx, y + 0.5 - sy
            perp = abs(cx * sin_a - cy * cos_a)
            st = 2 if a.downed else a.stance
            hw = HALF_WIDTH[st]
            if a.moved_turn >= game.turn - 1 and a.ai.get("pace_now") in ("run", "sprint") and not from_explosion:
                hw *= 0.75 if a.ai.get("pace_now") == "run" else 0.6     # a running man is hard to lead
            if from_explosion:
                hw += 0.15
            if perp < hw + 0.02:
                vert = VERTICAL[st]
                pc = m.pos_cover[x, y] / 100.0
                if not air:
                    vert *= (1 - pc * {0: 0.4, 1: 0.75, 2: 0.95}[st])
                else:
                    vert = 0.8 * (1 - pc * 0.5)
                if from_explosion and st == 2:
                    vert *= 0.6
                if rng.random() < vert:
                    hit_actor(game, a, energy, "fragment" if kind == "frag" else "gunshot",
                              shooter, source_name, from_pos=(ox, oy))
                    result = "hit"
                    break
            # near miss: heavy suppression handled below
        # ---- someone leaning out of cover into this tile
        pa = getattr(game, "peek_at", {}).get((x, y))
        if pa is not None and pa is not shooter and pa.alive and getattr(pa, "peek", None) and \
                (pa.x + pa.peek[0], pa.y + pa.peek[1]) == (x, y):
            cx, cy = x + 0.5 - sx, y + 0.5 - sy
            if abs(cx * sin_a - cy * cos_a) < 0.35 and rng.random() < 0.3:
                hit_actor(game, pa, energy, "fragment" if kind == "frag" else "gunshot", shooter, source_name,
                          from_pos=(ox, oy), part=rng.choice(("head", "head", "r_arm", "l_arm", "torso")))
                result = "hit"
                break
        # ---- vehicles
        v = game.vehicle_at.get((x, y))
        if v is not None and v is not shooter and v is not getattr(shooter, "vehicle", None) and not v.dead:
            if i > 0 or not skip_first:
                hit_vehicle(game, v, pen if pen else (4 if kind == "bullet" else 2), energy, ox, oy,
                            shooter, source_name, kind="bullet" if kind == "bullet" else "frag")
                result = "vehicle"
                break
        # ---- terrain
        tid = m.t[x, y]
        if own_top is not None and inside(own_top, x, y):
            continue                                  # out through the belfry, over the parapet
        cover = T.COVER[tid]
        if up and cover > 0 and T.SEE[tid] and not T.TALL[tid]:
            cover = 0                                 # fired down from a window: over the hedges and the walls
        if cover > 0 and not air:
            see = T.SEE[tid]
            tall = T.TALL[tid]
            chance = 0.0
            if not see and cover >= 90:
                chance = 1.0
            elif dist <= 1.5 and see:
                chance = 0.0          # shooting over/through your own cover
            else:
                nxt = None
                if i + 1 < n:
                    nx_, ny_ = int(path[i + 1][0]), int(path[i + 1][1])
                    nxt = game.soldier_at.get((nx_, ny_))
                if nxt is not None:
                    st = 2 if nxt.downed else nxt.stance
                    chance = cover / 100.0 * (0.85 if tall else LOW_COVER_STANCE[st])
                else:
                    chance = cover / 100.0 * (0.55 if tall else 0.2)
            if from_explosion:
                chance = min(1.0, chance * 1.3)
            if chance > 0 and rng.random() < chance:
                passed = projectile_hits_tile(game, x, y, energy, pen, kind)
                if not passed:
                    result = "terrain"
                    break
                through *= 0.5
                energy *= 0.5
                if energy < 8:
                    result = "terrain"
                    break
        elif not T.SEE[tid] and not T.WALK[tid]:
            if not air:
                result = "terrain"
                break
    # suppression along the path
    if kind == "bullet":
        amt = 9.0 if mg else 6.0
        if dmg >= 60:
            amt = 14.0
        suppress_line(game, ox, oy, endx, endy, amt, shooter_side, exclude=shooter)
    elif kind == "frag":
        suppress_line(game, ox, oy, endx, endy, 2.0, None, exclude=None)
    if kind == "bullet":
        game.effect_tracer(ox, oy, endx, endy, mg)
    return result


def projectile_hits_tile(game, x, y, energy, pen, kind) -> bool:
    """Damage a tile from a bullet/fragment.  Returns True if it passes through."""
    m = game.map
    tid = int(m.t[x, y])
    d = T.DEFS[tid]
    if d.window and d.key == "window":
        damage_tile(game, x, y, 999)
        if game.player and math.hypot(x - game.player.x, y - game.player.y) < 20:
            game.emit_sound(x, y, 35, "glass", "breaking glass", None, None)
        return True
    material_pen = energy * 0.6 + pen * 2
    if T.HP[tid] > 0:
        damage_tile(game, x, y, max(1, energy / 12))
    return material_pen > T.ARMOR[tid] and T.ARMOR[tid] < 60


def suppress_line(game, x0, y0, x1, y1, amount, shooter_side, exclude=None):
    pos, actors = game.actor_array()
    if not actors:
        return
    p0 = np.array([x0, y0], np.float32)
    seg = np.array([x1 - x0, y1 - y0], np.float32)
    L2 = float(seg @ seg)
    if L2 < 1:
        return
    rel = pos - p0
    tproj = np.clip((rel @ seg) / L2, 0.0, 1.0)
    closest = p0 + np.outer(tproj, seg)
    d = np.sqrt(((pos - closest) ** 2).sum(axis=1))
    idx = np.nonzero((d < 2.2) & (tproj > 0.02))[0]
    for k in idx:
        a = actors[k]
        if a is exclude or not a.alive:
            continue
        f = (1 - d[k] / 2.2)
        mult = 0.35 if (shooter_side is not None and a.side == shooter_side) else 1.0
        a.suppression = min(100.0, a.suppression + amount * f * mult * (0.6 if a.stance == 2 else 1.0))
        if shooter_side is not None and a.side != shooter_side:
            a.ai["fired_on"] = (int(x0), int(y0), game.turn)      # the crack and the thump: where it came from
        if a.is_player and d[k] < 1.3 and game.turn != game.ai_last_whizz:
            game.ai_last_whizz = game.turn
            game.near_miss()


# ====================================================================== damage to people

def hit_actor(game, a, dmg, kind, attacker, source, from_pos=None, part=None, silent=False):
    if not a.alive:
        return None
    rng = game.rng
    covered = False
    if from_pos is not None and a.stance > 0:
        cov = game.map.cover_toward(a.x, a.y, from_pos[0], from_pos[1])
        covered = cov >= 50
    if part is None:
        part = a.body.pick_part(rng, 2 if a.downed else a.stance, covered)
    # helmet
    if part == "head" and a.helmet is not None and kind in ("gunshot", "fragment", "blast") and dmg < 60:
        p = a.helmet.t.prot_frag if kind in ("fragment", "blast") else a.helmet.t.prot_bullet
        if rng.random() < p:
            if a.is_player:
                game.msg("Something slams into your helmet! Your ears ring.", "hurt")
            elif game.can_see(a.x, a.y):
                game.msg(f"A round spangs off {game.name_of(a)}'s helmet.", "combat", a.pos)
            a.body.stunned = max(a.body.stunned, 2)
            a.suppression = min(100, a.suppression + 30)
            return None
    dmg *= rng.uniform(0.75, 1.25)
    res = a.body.damage(rng, part, dmg, kind)
    a.hit_turn = game.turn
    pl = game.player
    if pl is not None and attacker is not None and (attacker is pl or attacker is pl.vehicle) and a is not pl:
        duty = getattr(game, "duty", None)
        if duty is not None:
            if a.side == pl.side:
                duty.on_friendly_hit(game, a, killed=res.get("dead", False))
            elif a.state == "surrendered" and not a.ai.get("_shot_as_pow"):
                a.ai["_shot_as_pow"] = True
                duty.on_prisoner_shot(game, a)
    a.suppression = min(100, a.suppression + 35)
    game.map.blood[a.x, a.y] = min(255, int(game.map.blood[a.x, a.y]) + 60)
    if dmg > 30:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = a.x + dx, a.y + dy
            if game.map.in_bounds(xx, yy) and rng.random() < 0.3:
                game.map.blood[xx, yy] = min(255, int(game.map.blood[xx, yy]) + 30)
    if attacker is not None and hasattr(attacker, "side"):
        a.body.killer = attacker
    pname = PART_NAME[part]
    if not silent:
        game.report_hit(a, attacker, pname, res, kind, source)
    if res.get("dead"):
        cause = {"gunshot": f"a {source} round", "fragment": f"{source} fragments",
                 "blast": source, "burn": "burns", "cut": source, "blunt": source}.get(kind, source)
        if part == "head" and kind == "gunshot":
            cause += " to the head"
        a.body.cause = a.body.cause or cause
        game.kill(a, attacker)
    else:
        if res.get("disabled") and part in ("l_leg", "r_leg"):
            a.stance = 2
        if a.body.downed() or not a.body.conscious:
            a.stance = 2
        game.on_wounded(a, attacker, res)
    return res


# ====================================================================== vehicles

FACE_NAMES = ("front", "side", "rear", "top")


def vehicle_face(v, ox, oy) -> int:
    o = octant(ox - v.x, oy - v.y)
    if o < 0:
        return 3
    rel = (o - v.facing) % 8
    if rel in (0,):
        return 0
    if rel in (1, 7):
        return 0 if hash((ox, oy, v.id)) % 2 else 1
    if rel in (2, 6):
        return 1
    if rel in (3, 5):
        return 1 if hash((ox, oy, v.id)) % 2 else 2
    return 2


def _riders_hit(game, v, source):
    """Men riding on the outside of a tank take what hits it: splinters, spall, the blast."""
    for a in list(v.passengers):
        if riding(a) and a.alive and game.rng.random() < 0.45:
            hit_actor(game, a, game.rng.uniform(10, 45), "fragment", None, f"a hit on the {v.vt.name} ({source})")


def hit_vehicle(game, v, pen, dmg, ox, oy, attacker, source, kind="ap", he_power=0, face=None):
    v.ai["hit_turn"] = game.turn
    if v.passengers:
        _riders_hit(game, v, source)
    return _hit_vehicle(game, v, pen, dmg, ox, oy, attacker, source, kind, he_power, face)


def _hit_vehicle(game, v, pen, dmg, ox, oy, attacker, source, kind="ap", he_power=0, face=None):
    """A hit on a vehicle: what it came through, and what it broke (vdamage.py)."""
    from . import vdamage as VD
    if v.dead:
        return
    rng = game.rng
    vt = v.vt
    if face is None:
        face = vehicle_face(v, ox, oy)
    armor = vt.armor[face] * rng.uniform(0.85, 1.15)
    seen = game.can_see(v.x, v.y)
    name = game.name_of_vehicle(v)
    if source == "a mine" and not vt.static:
        VD.break_part(game, v, "tracks", VD.OUT, attacker, source, seen)     # the blast takes the track off
    # open-topped vehicles and gun crews: small arms can hit the crew
    exposed_crew = (vt.open_top or v.static) and kind in ("bullet", "frag")
    if exposed_crew and face != 0 or (exposed_crew and v.static and rng.random() < 0.25):
        if rng.random() < (0.35 if kind == "bullet" else 0.25) and (v.crew > 0 or v.passengers):
            _vehicle_crew_casualty(game, v, attacker, source, seen)
            return
    if kind in ("bullet", "frag"):
        if VD.exposed_hit(game, v, kind, attacker, source, seen):
            return                                # the commander, head out of the hatch
        if pen >= armor and armor < 25:
            v.hp -= dmg * 0.3
            if rng.random() < 0.08:
                _vehicle_crew_casualty(game, v, attacker, source, seen)
            if rng.random() < 0.04:
                VD.break_part(game, v, rng.choice([p for p in ("engine", "fuel", "radio") if p in v.parts] or
                                                  ["engine"]), VD.DAMAGED, attacker, source, seen)
            if seen and rng.random() < 0.3:
                game.msg(f"Rounds punch through {name}!", "combat", v.pos)
        else:
            VD.glanced(game, v, face, kind, pen, armor, attacker=attacker, source=source, seen=seen)
            if seen and attacker is game.player:
                game.msg(f"Your rounds spark harmlessly off {name}.", "combat", v.pos)
        _check_vehicle_dead(game, v, attacker, source)
        return
    penetrated = pen >= armor
    if kind == "he":
        # HE: blast damage, may break tracks and periscopes, penetrates thin armour
        eff = he_power / 8.0
        if face == 3:
            eff *= 1.5
        penetrated = eff >= max(armor, 6) and rng.random() < min(1.0, eff / (max(armor, 6) * 2.5))
        if not penetrated:
            v.hp -= he_power * 0.05
            VD.exposed_hit(game, v, "he", attacker, source, seen)
            VD.glanced(game, v, face, "he", pen, armor, he_power, attacker, source, seen)
            if vt.open_top:
                for _ in range(rng.randint(0, 2)):
                    _vehicle_crew_casualty(game, v, attacker, source, seen)
            _check_vehicle_dead(game, v, attacker, source)
            return
        dmg = max(dmg, he_power * 0.6)
    if not penetrated:
        v.hp -= dmg * 0.05
        if seen or attacker is game.player:
            game.msg(f"The round glances off {name}'s {FACE_NAMES[face]} armour!", "combat", v.pos)
        game.emit_sound(v.x, v.y, 70, "ricochet", "the clang of a ricochet", None, None)
        if rng.random() < 0.15:
            v.ai["shaken"] = game.turn + 10
        VD.glanced(game, v, face, "ap", pen, armor, attacker=attacker, source=source, seen=seen)
        _check_vehicle_dead(game, v, attacker, source)
        return
    # ---- penetration: the round and its spall go through whatever's inside.  The hull itself takes
    # a share (three or four big holes and it's scrap); what it breaks inside decides the rest.
    v.hp -= dmg * 0.35
    game.emit_sound(v.x, v.y, 75, "penetration", "the crack of a penetrating hit", None, None)
    if seen or attacker is game.player:
        if kind == "he":
            game.msg(f"The blast tears into {name}!", "hit", v.pos)
        else:
            game.msg(f"A round penetrates {name}'s {FACE_NAMES[face]} armour!", "hit", v.pos)
    hit = VD.penetrated(game, v, face, dmg, kind, attacker, source, seen)
    if "boom" in hit or v.dead:
        return
    fire = 0.08 + (0.25 if VD.state(v, "fuel") < VD.OK else 0)       # hot spall among oil, fuel and cordite
    if not v.burning and rng.random() < fire:
        v.burning = rng.randint(15, 60)
        if seen:
            game.msg(f"Smoke pours from {name} - it's on fire!", "combat", v.pos)
    if v.crew > 0 and not v.player_crewed and rng.random() < VD.bail_chance(v, hit):
        abandon_vehicle(game, v)
    _check_vehicle_dead(game, v, attacker, source)


def _vehicle_crew_casualty(game, v, attacker, source, seen, quiet=False):
    """A crewman (or a man riding) hit: one of the manned seats, at random."""
    from . import vdamage as VD
    from .crew import manned
    rng = game.rng
    if v.passengers and rng.random() < 0.5:
        p = rng.choice(v.passengers)
        hit_actor(game, p, rng.uniform(25, 60), "fragment", attacker, source)
        if not p.alive and p in v.passengers:
            v.passengers.remove(p)
        return
    seats = sorted(manned(v))
    if v.player_crewed and v.player_station and v.player_station not in seats:
        seats.append(v.player_station)
    if not seats:
        return
    VD.crew_hit(game, v, rng.choice(seats), attacker, source, seen, quiet=quiet)


def _check_vehicle_dead(game, v, attacker, source):
    if v.hp <= 0 and not v.dead:
        destroy_vehicle(game, v, attacker, source)


def destroy_vehicle(game, v, attacker, source, catastrophic=False):
    if v.dead:
        return
    v.dead = True
    v.hp = 0
    if v.ai.get("convoy"):
        from .rear import convoy_hit
        convoy_hit(game, v, attacker)             # a cut in the road on the war map
    m = game.map
    rng = game.rng
    cells = v.cells()
    game.lift_vehicle(v)
    # the hulk stays where it died, as big as the vehicle was
    wrecked = False
    for cx, cy in cells:
        if m.in_bounds(cx, cy) and not T.WATER[m.t[cx, cy]]:
            m.set(cx, cy, "wreck")
            wrecked = True
    if wrecked:
        m.refresh()
    m.fire[v.x, v.y] = max(int(m.fire[v.x, v.y]), 3)
    m.lights.append([v.x, v.y, 5, game.turn + 400])
    if attacker is not None and hasattr(attacker, "kills"):
        attacker.kills += 1
        pv = game.player.vehicle if game.player is not None else None
        if attacker is game.player or (pv is not None and attacker is pv):
            game.stats["vehicles_killed"] += 1
    if game.can_see(v.x, v.y):
        game.msg(f"{game.name_of_vehicle(v)} is destroyed!", "death", v.pos)
    game.emit_sound(v.x, v.y, 95 if catastrophic else 80, "explosion",
                    "a vehicle cooking off" if catastrophic else "a heavy explosion", None, None)
    if catastrophic:
        explode(game, v.x, v.y, 180, 3, frags=20, frag_dmg=22, attacker=attacker,
                source=f"an exploding {v.vt.name}", crater=False, fire=2, self_vehicle=v)
    # survivors bail out
    survivors = 0 if catastrophic else sum(rng.random() < 0.55 for _ in range(v.crew))
    game.bail_out(v, survivors, catastrophic)


def abandon_vehicle(game, v):
    if v.abandoned or v.dead:
        return
    v.abandoned = True
    game.bail_out(v, v.crew, False)
    v.crew = 0
    if game.can_see(v.x, v.y):
        game.msg(f"The crew of {game.name_of_vehicle(v)} bail out!", "combat", v.pos)


# ====================================================================== terrain

def damage_tile(game, x: int, y: int, dmg: float) -> bool:
    m = game.map
    if not m.in_bounds(x, y):
        return False
    tid = int(m.t[x, y])
    if T.HP[tid] <= 0:
        return False
    m.hp[x, y] -= int(dmg)
    if m.hp[x, y] > 0:
        return False
    into = int(T.INTO[tid])
    if tid in T.EXPLODE:
        p, r, f = T.EXPLODE[tid]
        game.pending_explosions.append([x, y, p, r, f, game.rng.randint(0, 3)])
    if T.DOOR[tid] and game.can_see(x, y):
        game.msg("A door is blown off its hinges.", "combat", (x, y))
    m.t[x, y] = into
    m.hp[x, y] = T.HP[into]
    game.terrain_dirty = True
    # bridge collapse
    if T.DEFS[tid].key == "bridge":
        game.msg("The bridge collapses into the water!", "warn", (x, y))
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                xx, yy = x + dx, y + dy
                if m.in_bounds(xx, yy) and m.t[xx, yy] == tid and game.rng.random() < 0.6:
                    m.t[xx, yy] = into
    return True


# ====================================================================== explosions

def explode(game, x: int, y: int, power: float, radius: int, *, frags: int = 0,
            frag_dmg: float = 20, pen: float = 0, attacker=None, source="an explosion",
            crater=True, fire: int = 0, smoke: float = 0, self_vehicle=None, air_burst=False):
    m = game.map
    rng = game.rng
    if not m.in_bounds(x, y):
        return
    game.effect_explosion(x, y, radius)
    loud = min(120, 80 + power / 12)
    game.emit_sound(x, y, loud, "explosion", source, None, None, power=power)
    water = T.WATER[m.t[x, y]]
    if water >= 2:
        power *= 0.6
        frags = frags // 4
        crater = False
        game.effect_splash(x, y)
        game.audio("splash", x, y, 70)
    # ---- blast on soldiers
    pos, actors = game.actor_array()
    if power >= 20:
        imp = game.__dict__.setdefault("impacts", [])      # (where the shells are falling: ai.beaten_zone)
        imp.append((x, y, game.turn))
        if len(imp) > 60:
            del imp[:len(imp) - 60]
    if actors:
        d = np.sqrt(((pos - np.array([x, y], np.float32)) ** 2).sum(axis=1))
        if power >= 20:
            for k in np.nonzero(d <= radius + 10)[0]:
                actors[k].ai["near_shell"] = game.turn          # close enough to throw yourself flat
        for k in np.nonzero(d <= radius + 0.5)[0]:
            a = actors[k]
            if not a.alive or a.vehicle is not None:
                continue
            dist = float(d[k])
            if dist > 0.5 and not blast_clear(m, x, y, a.x, a.y):
                continue
            f = max(0.0, 1 - dist / (radius + 1)) ** 1.6
            dmg = power * 0.55 * f
            a.ai["shelled"] = game.turn
            if getattr(a, "z", 0) < 0:
                dmg *= 0.08                          # in the cellar: dust, a ringing in the ears, and alive
                f *= 0.3
            st = 2 if a.downed else a.stance
            if dist >= 1:
                dmg *= {0: 1.0, 1: 0.8, 2: 0.55}[st]
                pc = m.pos_cover[a.x, a.y] / 100.0
                dmg *= (1 - pc * 0.8) if not air_burst else (1 - pc * 0.3)
            else:
                dmg *= 1.6
            if dmg >= 3:
                hits = 1 + (dmg > 40) + (dmg > 90)
                for _ in range(hits):
                    part = a.body.pick_part(rng, st)
                    hit_actor(game, a, dmg / hits, "blast", attacker, source, part=part,
                              silent=(_ > 0))
                    if not a.alive:
                        break
            if a.alive:
                a.suppression = min(100.0, a.suppression + 50 * f + 15)
                if f > 0.15:
                    a.body.deaf = max(a.body.deaf, int(40 * f) + 5)
                    if a.stance < 2 and rng.random() < f:
                        a.stance = 2
                        a.moves -= 100
    # ---- fragments
    if frags > 0:
        n = min(frags, 48)
        fd = frag_dmg * (frags / n) ** 0.5
        rrange = radius * 2.6 + 3
        for _ in range(n):
            ang = rng.uniform(0, math.tau)
            trace_projectile(game, x, y, ang, rrange * rng.uniform(0.5, 1.0), fd, 2, "frag",
                             attacker if attacker is not None else None, None, source,
                             from_explosion=True, skip_first=False, air=air_burst)
    # ---- vehicles
    for v in list(game.vehicles):
        if v.dead or v is self_vehicle:
            continue
        if abs(v.x - x) + abs(v.y - y) > radius + 16:
            continue
        dist = min(math.hypot(cx - x, cy - y) for cx, cy in v.cells())
        if dist <= radius + 8:
            v.ai["near_blast"] = game.turn          # shells bursting close: heads down, hatches shut
        if dist <= radius:
            f = max(0.0, 1 - dist / (radius + 1))
            face = 3 if dist < 1 else None
            hit_vehicle(game, v, pen, power * 0.4 * f, x, y, attacker, source, kind="he",
                        he_power=power * f + pen * 8 * (dist < 1), face=face)
    # ---- terrain
    rt = int(max(0, min(radius, power / 110)))
    for dx in range(-rt, rt + 1):
        for dy in range(-rt, rt + 1):
            dist = math.hypot(dx, dy)
            if dist > rt + 0.3:
                continue
            xx, yy = x + dx, y + dy
            if not m.in_bounds(xx, yy):
                continue
            tdmg = power * 2.2 * (1 - dist / (rt + 1.2))
            damage_tile(game, xx, yy, tdmg)
            m.scorch[xx, yy] = 1
            if fire and rng.random() < 0.5:
                ignite(game, xx, yy, fire)
            elif power > 150 and T.FLAM[m.t[xx, yy]] > 20 and rng.random() < 0.15:
                ignite(game, xx, yy, 1)
    if crater and power >= 70 and not water:
        key = "crater_big" if power >= 380 else "crater"
        cx, cy = x, y
        if T.DIG[m.t[cx, cy]] or T.DEFS[int(m.t[cx, cy])].key in ("road", "paved", "cobble", "runway",
                                                                   "rubble_light", "burnt", "shingle"):
            m.set(cx, cy, key)
            game.terrain_dirty = True
        if power >= 700:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if m.in_bounds(cx + dx, cy + dy) and T.DIG[m.t[cx + dx, cy + dy]]:
                    m.set(cx + dx, cy + dy, "crater")
    # dust / smoke puff
    dust = smoke if smoke else min(3.0, power / 120)
    if dust > 0:
        r = max(1, int(radius / 2)) if not smoke else 3
        m.smoke[max(0, x - r):x + r + 1, max(0, y - r):y + r + 1] += dust
    if game.is_night():
        m.lights.append([x, y, max(3, radius + 2), game.turn + 1])
    # sympathetic mine detonation
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            mn = m.mines.get((x + dx, y + dy))
            if mn and rng.random() < 0.3 * power / 200:
                del m.mines[(x + dx, y + dy)]
                game.pending_explosions.append([x + dx, y + dy, 70 if mn.kind != "at" else 200,
                                                2 if mn.kind != "at" else 3, 0, 1])
    game.terrain_dirty = True


def blast_clear(m, x0, y0, x1, y1) -> bool:
    for px, py in tcod.los.bresenham((x0, y0), (x1, y1))[1:-1]:
        tid = m.t[px, py]
        if not T.WALK[tid] and not T.SEE[tid] and T.COVER[tid] >= 90:
            return False
    return True


def ignite(game, x, y, intensity=2):
    m = game.map
    if not m.in_bounds(x, y):
        return
    if T.WATER[m.t[x, y]]:
        return
    if T.FLAM[m.t[x, y]] > 0 or intensity >= 3:
        m.fire[x, y] = max(int(m.fire[x, y]), intensity * 20)


# ====================================================================== special weapons

def fire_flamer(game, shooter, weapon, tx, ty) -> int:
    t = weapon.t
    if weapon.loaded <= 0:
        return 50
    weapon.loaded -= 1
    ox, oy = shooter.x, shooter.y
    dist = min(t.rng, max(1, int(math.hypot(tx - ox, ty - oy))))
    ang = math.atan2(ty - oy, tx - ox)
    game.emit_sound(ox, oy, t.loud, "flamer", t.sound, shooter.side, shooter)
    m = game.map
    pts = []
    for k in range(1, dist + 1):
        wob = game.rng.gauss(0, 0.12)
        x = int(round(ox + math.cos(ang + wob) * k))
        y = int(round(oy + math.sin(ang + wob) * k))
        if not m.in_bounds(x, y):
            break
        pts.append((x, y))
        if not T.WALK[m.t[x, y]] and not T.SEE[m.t[x, y]]:
            # splashes against walls and through embrasures
            break
    for i, (x, y) in enumerate(pts):
        spread = [(x, y)] + ([(x + game.rng.randint(-1, 1), y + game.rng.randint(-1, 1))]
                             if i > dist // 2 else [])
        for sx, sy in spread:
            if not m.in_bounds(sx, sy):
                continue
            ignite(game, sx, sy, 3)
            a = game.soldier_at.get((sx, sy))
            if a and a is not shooter and a.alive:
                a.body.burning = max(a.body.burning, game.rng.randint(3, 8))
                hit_actor(game, a, t.dmg * game.rng.uniform(0.7, 1.3), "burn", shooter, "a flamethrower")
                a.suppression = 100
            v = game.vehicle_at.get((sx, sy))
            if v and not v.dead:
                if v.vt.open_top or v.static:
                    for _ in range(2):
                        _vehicle_crew_casualty(game, v, shooter, "a flamethrower", True)
                elif game.rng.random() < 0.25:
                    v.burning = max(v.burning, 20)
    # flames through embrasures roast bunker occupants
    if pts:
        ex, ey = pts[-1]
        if T.WINDOW[m.t[ex, ey]]:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    a = game.soldier_at.get((ex + dx, ey + dy))
                    if a and a.alive and a is not shooter and game.rng.random() < 0.6:
                        hit_actor(game, a, t.dmg, "burn", shooter, "a flamethrower")
                        a.suppression = 100
    game.effect_flame(pts)
    shooter.fired_turn = game.turn
    return t.shot_cost


def fire_launcher(game, shooter, weapon, tx, ty, target=None) -> int:
    t = weapon.t
    if weapon.loaded <= 0:
        return 50
    ox, oy = shooter.x, shooter.y
    dist = math.hypot(tx - ox, ty - oy)
    if dist < t.min_rng:
        if shooter.is_player:
            game.msg("Too close - the warhead won't even arm at this range.", "warn")
        return 0
    weapon.loaded -= 1
    disp = dispersion(game, shooter, weapon, tx, ty) + (0.5 if dist > t.rng else 0)
    ang = math.atan2(ty + 0.5 - (oy + 0.5), tx + 0.5 - (ox + 0.5)) + math.radians(game.rng.gauss(0, disp))
    game.emit_sound(ox, oy, t.loud, "rocket", t.sound, shooter.side, shooter)
    game.effect_flash(ox, oy)
    # backblast
    if t.backblast:
        bx, by = int(round(ox - math.cos(ang) * 2)), int(round(oy - math.sin(ang) * 2))
        a = game.soldier_at.get((bx, by))
        if a and a.alive:
            hit_actor(game, a, game.rng.uniform(10, 30), "burn", shooter, "backblast")
        game.map.smoke[max(0, bx - 1):bx + 2, max(0, by - 1):by + 2] += 1.0
        # firing from inside a room is dangerous
        if T.FLOOR[game.map.t[ox, oy]]:
            hit_actor(game, shooter, game.rng.uniform(5, 20), "blast", shooter, "backblast in an enclosed space")
    m = game.map
    max_r = int(t.rng * 1.6)
    path = tcod.los.bresenham((ox, oy), (int(ox + math.cos(ang) * max_r), int(oy + math.sin(ang) * max_r)))
    impact = None
    for i in range(1, len(path)):
        x, y = int(path[i][0]), int(path[i][1])
        if not m.in_bounds(x, y):
            break
        v = game.vehicle_at.get((x, y))
        if v and not v.dead:
            hit_vehicle(game, v, t.pen * game.rng.uniform(0.9, 1.05), 220, ox, oy, shooter, t.name, kind="ap")
            impact = (x, y)
            break
        a = game.soldier_at.get((x, y))
        if a and a is not shooter and a.alive and (a is target or game.rng.random() < 0.35):
            impact = (x, y)
            break
        tid = m.t[x, y]
        if (not T.WALK[tid] and T.COVER[tid] > 40) or (T.COVER[tid] > 60 and game.rng.random() < 0.5):
            impact = (x, y)
            damage_tile(game, x, y, t.pen * 3)
            break
        if target is None and i >= max(abs(tx - ox), abs(ty - oy)) + game.rng.randint(-1, 1):
            impact = (x, y)
            break
    if impact is None:
        impact = (int(path[-1][0]), int(path[-1][1]))
        if not m.in_bounds(*impact):
            impact = (max(0, min(m.w - 1, impact[0])), max(0, min(m.h - 1, impact[1])))
    game.effect_tracer(ox, oy, impact[0], impact[1], False, rocket=True)
    explode(game, impact[0], impact[1], t.blast, t.blast_r, frags=t.frags, frag_dmg=t.frag_dmg,
            attacker=shooter, source=f"a {t.name} warhead", crater=False)
    shooter.fired_turn = game.turn
    if t.cat == "at_disposable" and shooter.weapon is weapon:
        shooter.remove_item(weapon)
        game.map.add_item(ox, oy, weapon)  # spent tube
        weapon.data = {"spent": True}
    return t.shot_cost


def fire_mortar(game, shooter, weapon, tx, ty) -> int:
    t = weapon.t
    ammo = shooter.ammo_for(weapon)
    if ammo is None:
        return 50
    dist = math.hypot(tx - shooter.x, ty - shooter.y)
    if dist < t.min_rng or dist > t.rng:
        return 0
    ammo.count -= 1
    if ammo.count <= 0:
        shooter.remove_item(ammo)
    game.emit_sound(shooter.x, shooter.y, t.loud, "mortar", t.sound, shooter.side, shooter)
    # scatter grows with range and skill
    from .skills import level, use
    sig = dist * 0.06 + (8 - level(shooter, "gunnery")) * 0.3 + shooter.suppression / 40
    use(game, shooter, "gunnery", 0.5)
    ix = int(round(tx + game.rng.gauss(0, sig)))
    iy = int(round(ty + game.rng.gauss(0, sig)))
    flight = 3 + int(dist / 15)
    game.schedule_shell(ix, iy, flight, t.blast, t.blast_r, t.frags, t.frag_dmg, shooter,
                        f"a {t.name} bomb", whistle=True)
    shooter.fired_turn = game.turn
    return t.shot_cost


def melee_attack(game, attacker, target, move=None) -> int:
    """Hand to hand: see melee.py."""
    from .melee import attack
    return attack(game, attacker, target, move)


def vehicle_fire_main(game, v, tx, ty, target=None, ammo=None) -> bool:
    mt = v.mount
    if mt is None or not v.gun_ok or v.reload > 0:
        return False
    from . import vdamage as VD
    if v.vt.turret and not v.static and VD.traverse(v) in ("hand", "jammed") and \
            (octant(tx - v.x, ty - v.y) - v.turret) % 8 not in (0, 1, 7):
        return False                                   # the gun doesn't point there, and won't swing quickly
    rng = game.rng
    ammo = ammo or v.ammo_choice
    if mt.flame:
        # the fuel trailer: 400 gallons, about eighty one-second bursts
        fuel = v.ai.setdefault("flame_fuel", 80)
        if fuel <= 0:
            if v.player_crewed:
                game.msg(f"The {v.vt.name}'s flame fuel is gone.", "warn")
            return False
        v.ai["flame_fuel"] = fuel - 1
        pts = []
        ang = math.atan2(ty - v.y, tx - v.x)
        dist = min(mt.rng, int(math.hypot(tx - v.x, ty - v.y)))
        for k in range(1, dist + 1):
            x, y = int(round(v.x + math.cos(ang) * k)), int(round(v.y + math.sin(ang) * k))
            if not game.map.in_bounds(x, y):
                break
            pts.append((x, y))
            if not T.WALK[game.map.t[x, y]] and not T.SEE[game.map.t[x, y]]:
                break
        for x, y in pts:
            ignite(game, x, y, 3)
            a = game.soldier_at.get((x, y))
            if a and a.alive:
                hit_actor(game, a, 45, "burn", v, f"{v.vt.name}'s flame gun")
                a.suppression = 100
        game.effect_flame(pts)
        game.emit_sound(v.x, v.y, 70, "flamer", "the roar of a flame tank", v.side, v)
        v.reload = mt.reload_cost
        v.fired_turn = game.turn
        return True
    if ammo == "ap" and v.ap <= 0:
        ammo = "he"
    if ammo == "he" and v.he <= 0:
        ammo = "ap" if v.ap > 0 else None
    if ammo is None:
        return False
    if ammo == "ap":
        v.ap -= 1
    else:
        v.he -= 1
    if v.vt.turret and VD.turret_turns(v):
        v.turret = octant(tx - v.x, ty - v.y)
    elif not v.vt.turret:
        v.turret = v.facing
    dist = math.hypot(tx - v.x, ty - v.y)
    disp = mt.disp + (0.6 if v.moved_turn >= game.turn - 1 else 0) + (0.8 if v.ai.get("shaken", 0) > game.turn else 0)
    disp += VD.gun_disp(v)                             # a damaged gun, cracked or smashed sights
    disp += 0.4 * max(0, 4 - v.crew)
    gl = v.ai.get("gunnery")
    if gl is None:
        gl = v.ai["gunnery"] = round(game.rng.gauss(5.5, 1.3), 1)      # the crew's skill at their gun
    p = game.player
    if p is not None and p.vehicle is v and v.player_station == "gunner":
        from .skills import level, use
        gl = level(p, "gunnery")
        use(game, p, "gunnery", 1.0)
    disp += max(0.0, 6 - gl) * 0.15
    from .familiar import vehicle_learn, vehicle_level
    disp += (1 - vehicle_level(v)) * 0.8               # a captured gun's strange sight
    vehicle_learn(v, 0.03)
    ang = math.atan2(ty + 0.5 - (v.y + 0.5), tx + 0.5 - (v.x + 0.5)) + math.radians(rng.gauss(0, disp))
    game.emit_sound(v.x, v.y, 95, "cannon", f"the boom of a {mt.name}", v.side, v)
    game.effect_flash(v.x, v.y)
    m = game.map
    max_r = int(mt.rng * 1.5)
    path = tcod.los.bresenham((v.x, v.y), (int(v.x + math.cos(ang) * max_r), int(v.y + math.sin(ang) * max_r)))
    impact = None
    for i in range(1, len(path)):
        x, y = int(path[i][0]), int(path[i][1])
        if not m.in_bounds(x, y):
            break
        ov = game.vehicle_at.get((x, y))
        if ov and ov is not v and not ov.dead:
            if ammo == "ap":
                pen = mt.ap_pen * max(0.6, 1 - dist / (mt.rng * 3))
                hit_vehicle(game, ov, pen * rng.uniform(0.9, 1.05), mt.ap_dmg, v.x, v.y, v, mt.name, kind="ap")
                impact = (x, y)
                game.effect_tracer(v.x, v.y, x, y, False, rocket=True)
                v.reload = int(mt.reload_cost * VD.reload_mult(v))
                v.fired_turn = game.turn
                return True
            impact = (x, y)
            break
        a = game.soldier_at.get((x, y))
        if a and a.alive and (a is target or rng.random() < 0.25):
            if ammo == "ap":
                hit_actor(game, a, 150, "gunshot", v, f"{mt.name} shell")
                continue
            impact = (x, y)
            break
        tid = m.t[x, y]
        if (not T.WALK[tid] and T.COVER[tid] >= 40 and i > 1) or (T.COVER[tid] > 55 and rng.random() < 0.3 and i > 1):
            impact = (x, y)
            if ammo == "ap":
                damage_tile(game, x, y, mt.ap_pen * 4)
            break
        if (x, y) == (tx, ty) and ammo == "he" and rng.random() < 0.7:
            impact = (x, y)
            break
    if impact is None:
        impact = (int(path[-1][0]), int(path[-1][1]))
        impact = (max(0, min(m.w - 1, impact[0])), max(0, min(m.h - 1, impact[1])))
    game.effect_tracer(v.x, v.y, impact[0], impact[1], False, rocket=True)
    if ammo == "he":
        explode(game, impact[0], impact[1], mt.he_power, mt.he_radius, frags=mt.he_frags,
                frag_dmg=22, attacker=v, source=f"a {mt.name} HE shell")
    else:
        game.effect_explosion(impact[0], impact[1], 0)
    v.reload = int(mt.reload_cost * VD.reload_mult(v))
    v.fired_turn = game.turn
    return True


def vehicle_fire_mg(game, v, tx, ty, target=None, idxs=None) -> bool:
    """A burst from machine gun(s) idxs (default: the first).  Each gun has its own burst."""
    if not v.vt.mgs or v.mg_ammo <= 0 or v.crew <= 0:
        return False
    from .vdamage import mg_ok
    idxs = [i for i in (idxs if idxs is not None else [0]) if i < len(v.vt.mgs) and mg_ok(v, i)]
    if not idxs:
        return False
    base = math.atan2(ty + 0.5 - (v.y + 0.5), tx + 0.5 - (v.x + 0.5))
    fired = 0
    for gi in idxs:
        if v.mg_ammo <= 0:
            break
        mid = v.vt.mgs[gi]
        mg = ITEMS[mid]
        rounds = min(v.mg_ammo, mg.burst + game.rng.randint(0, 3))
        v.mg_ammo -= rounds
        fired += rounds
        for i in range(rounds):
            disp = mg.disp + 0.6 + (0.8 if v.moved_turn >= game.turn - 1 else 0) + i * 0.1 + \
                (1 - v.ai.get("fam", 1.0) if v.ai.get("captured") else 0) * 0.6
            ang = base + math.radians(game.rng.gauss(0, disp))
            trace_projectile(game, v.x, v.y, ang, mg.rng * 3, mg.dmg, mg.pen, "bullet", v, target, mg.name,
                             mg=True, eff_range=mg.rng)
    mid = v.vt.mgs[idxs[0]]
    mg = ITEMS[mid]
    game.emit_sound(v.x, v.y, mg.loud, "gunfire", mg.sound, v.side, v, weapon=mid, extra=fired)
    game.effect_flash(v.x, v.y)
    v.fired_turn = game.turn
    return True
