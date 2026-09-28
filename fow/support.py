"""Off-map artillery, naval gunfire and air power."""
from __future__ import annotations

import math

from . import tiles as T
from .combat import explode, hit_actor, hit_vehicle, trace_projectile
from .constants import SIDES, other_side
from .data.nations import equip_sources
from .data.vehicles import AIRCRAFT, BATTERIES


def available(pool: dict, nation: str, year: float):
    srcs = equip_sources(nation, year) + [nation]
    out = [t for t in pool.values() if any(s in t.nations for s in srcs) and t.years[0] <= year < t.years[1]]
    return out


class FireMission:
    def __init__(self, side, battery, x, y, fire_turn, caller, rounds, spread, bias):
        self.side = side
        self.battery = battery
        self.x = x
        self.y = y
        self.fire_turn = fire_turn
        self.caller = caller
        self.rounds = rounds
        self.spread = spread
        self.bias = bias


class Aircraft:
    def __init__(self, at, side, nation, x, y, tx, ty, mode):
        self.at = at
        self.side = side
        self.nation = nation
        self.x = float(x)
        self.y = float(y)
        self.tx = tx
        self.ty = ty
        self.mode = mode          # strafe, dive, bomb, carpet, recon
        self.hp = at.hp
        self.dead = False
        self.done = False
        ang = math.atan2(ty - y, tx - x)
        self.dx = math.cos(ang)
        self.dy = math.sin(ang)
        self.attacked = False
        self.bombs = [list(b) for b in at.bombs]
        self.rockets = [list(r) for r in at.rockets]
        self.passes = 0

    @property
    def glyph(self):
        a = math.atan2(self.dy, self.dx)
        o = int(round(a / (math.pi / 2))) % 4
        return "►▼◄▲"[o]


class Support:
    def __init__(self, game):
        self.game = game
        th = game.theatre
        self.arty_level = dict(th["arty"])
        self.air_level = dict(th["air"])
        self.missions = {s: 0.0 for s in SIDES}
        self.queue: list[FireMission] = []
        self.aircraft: list[Aircraft] = []
        self.next_sortie = {s: game.turn + game.rng.randint(120, 600) for s in SIDES}
        self.batteries = {}
        for s in SIDES:
            nat = game.side_nation(s)
            bats = [b for b in available(BATTERIES, nat, game.year) if b.freq > 0]
            if "landing" in th.get("special", ()) and s == game.attacker:
                bats += [BATTERIES["us_naval"], BATTERIES["us_bb"]]
            self.batteries[s] = bats
            self.missions[s] = 1 + 3 * self.arty_level.get(s, 0.5)
        self.planes = {s: [p for p in available(AIRCRAFT, game.side_nation(s), game.year)] for s in SIDES}

    # ------------------------------------------------------------ artillery: real batteries (fires.py)
    @property
    def fires(self):
        g = self.game
        f = g.__dict__.get("fires")
        if f is None:
            from .fires import Fires
            f = g.fires = Fires(g)
        return f

    def capacity_mult(self, side) -> float:
        """Installations in this and nearby sectors change what is available."""
        g = self.game
        mult = 1.0
        if g.strategic is not None:
            mult = g.strategic.support_mult(side, "arty", g.sector)
        return mult

    def request_fire(self, side, x, y, caller=None, battery=None, rounds=None, delay=None,
                     silent=False, smoke=False) -> bool:
        """A call for fire: a battery that can reach and is free takes it, and fires the rounds it has."""
        return self.fires.call(self.game, side, x, y, caller=caller, rounds=rounds, delay=delay, silent=silent,
                               smoke=smoke) is not None

    def barrage(self, side, x, y, radius, rounds, delay=0, naval=False):
        """A scheduled bombardment (preparation, harassing fire, or the navy offshore): every battery in range
        that's free takes a share."""
        return self.fires.barrage(self.game, side, x, y, radius, rounds, delay, naval)

    def update(self):
        g = self.game
        rng = g.rng
        self.fires.update(g)
        if g.sector is not None and g.turn % 10 == 0:
            self.missions = {s: float(len(self.fires.ready(g, s))) for s in SIDES}    # (batteries free, for anyone asking)
        # air (at sea, the aircraft that come are the ones the war at sea sends: aboard.py)
        for s in SIDES:
            if g.__dict__.get("domain") == "aboard":
                self.next_sortie[s] = g.turn + 600
                continue
            if g.turn >= self.next_sortie[s]:
                lvl = self.air_level.get(s, 0.3) * (g.strategic.support_mult(s, "air", g.sector)
                                                     if g.strategic else 1.0)
                gap = int(1400 * (1.2 - lvl)) + rng.randint(200, 900)
                self.next_sortie[s] = g.turn + gap
                if rng.random() < lvl and g.weather not in ("fog", "sandstorm") or \
                        (rng.random() < lvl * 0.3):
                    self.launch_sortie(s)
        self.update_aircraft()

    # ------------------------------------------------------------ air
    def launch_sortie(self, side, target=None, roles=None, quiet=False):
        g = self.game
        rng = g.rng
        night = g.is_night()
        # a squadron with aircraft on the ground, fuelled and armed: what flies is what it has
        sqn = self.fires.squadron_for(g, side, roles, night)
        if sqn is None:
            if not quiet and side == g.player.side and target is not None:
                g.msg("Radio: 'Negative on air - nothing's available. Every squadron's up or refuelling.'", "radio")
            return False
        at = sqn.at
        # pick a target: the densest known enemy cluster, sometimes a mistake
        brain = g.brains[side]
        cl = brain.clusters(radius=8, min_size=2, max_age=60)
        if target is None:
            if cl:
                _, tx, ty, _ = cl[0]
            else:
                # hunt along the enemy's side of the map
                e_edge = g.home_edge(other_side(side))
                tx, ty = g.random_point_near_edge(e_edge, depth=0.35)
            if rng.random() < 0.15:
                # misidentification: the pilot picks the wrong hedgerow
                tx += rng.randint(-40, 40)
                ty += rng.randint(-30, 30)
        else:
            tx, ty = target
        m = g.map
        tx = max(2, min(m.w - 3, tx))
        ty = max(2, min(m.h - 3, ty))
        # they come from their airfield's direction (from the runway itself, if it's on this map)
        here = (g.sector.x, g.sector.y)
        if sqn.sec == here:
            field = next((r for r in (getattr(m, "gen_positions", None) or []) if r.get("kind") == "airfield"
                          and r.get("side") == side), None)
            sx, sy = (field["x"], field["y"]) if field else (m.w // 2, m.h // 2)
            ang = math.atan2(ty - sy, tx - sx)
        else:
            ex, ey, _d = self.fires.bearing_point(g, sqn.sec, None)
            ang = math.atan2(ty - ey, tx - ex)
            sx = tx - math.cos(ang) * (m.w * 0.8)
            sy = ty - math.sin(ang) * (m.h * 0.8)
        role = at.role
        mode = {"fighter": "strafe", "fighterbomber": rng.choice(["strafe", "bomb"]),
                "divebomber": "dive", "attacker": "strafe", "bomber": "bomb", "heavybomber": "carpet",
                "nightbomber": "bomb"}.get(role, "strafe")
        n = 1 if mode in ("dive", "strafe") else 1
        if role in ("fighterbomber", "fighter", "attacker") and rng.random() < 0.6:
            n = 2
        if role in ("bomber",):
            n = rng.randint(2, 3)
        if role == "heavybomber":
            n = rng.randint(3, 6)
        n = max(1, min(n, sqn.ready(g.turn)))
        for i in range(n):
            off = (rng.uniform(-4, 4), rng.uniform(-4, 4))
            ac = Aircraft(at, side, g.side_nation(side), sx + off[0] - i * 6 * math.cos(ang),
                          sy + off[1] - i * 6 * math.sin(ang), tx + off[0] * 2, ty + off[1] * 2, mode)
            ac.squadron = sqn.id
            self.aircraft.append(ac)
        self.fires.sortie_out(g, sqn, n)
        if side == g.player.side and target is not None and not quiet:
            g.msg(f"Radio: '{n} {at.name}{'s' if n > 1 else ''} of {sqn.name.split(' (')[0]} on the way.'", "radio")
        friendly = side == g.player.side
        g.audio("aircraft", int(ac.x) if False else g.player.x, g.player.y, 58)
        if at.siren and not friendly:
            g.audio("siren", tx, ty, 90)
        if not quiet:
            g.msg(f"You hear {at.sound} - {'friendly' if friendly else 'enemy'} aircraft!"
                  if g.player.body.deaf <= 0 else "Something roars overhead.", "warn" if not friendly else "radio")
        if at.siren and not friendly:
            g.msg("A rising, unearthly wail - a Stuka is diving!", "death")
        return True

    def update_aircraft(self):
        g = self.game
        m = g.map
        rng = g.rng
        keep = []
        for ac in self.aircraft:
            if ac.done:
                continue
            spd = ac.at.speed
            for _ in range(spd):
                ac.x += ac.dx
                ac.y += ac.dy
                dtt = math.hypot(ac.tx - ac.x, ac.ty - ac.y)
                if not ac.attacked and dtt < (7 if ac.mode in ("strafe",) else 2):
                    self.attack(ac)
                    ac.attacked = True
            # AA fire at the aircraft
            if 0 <= ac.x < m.w and 0 <= ac.y < m.h:
                self.aa_fire(ac)
            if ac.dead:
                q = self._squadron(ac)
                if q is not None:
                    self.fires.plane_lost(g, q)
                continue
            # left the map: home to its airfield
            if (ac.x < -40 or ac.x > m.w + 40 or ac.y < -40 or ac.y > m.h + 40) and ac.attacked:
                ac.done = True
                q = self._squadron(ac)
                if q is not None:
                    self.fires.plane_back(g, q)
                continue
            keep.append(ac)
        self.aircraft = keep

    def clear_air(self):
        """You've gone elsewhere: whatever was overhead flies home as usual, off-screen."""
        for ac in self.aircraft:
            if ac.dead or getattr(ac, "done", False):
                continue
            q = self._squadron(ac)
            if q is not None:
                self.fires.plane_back(self.game, q)
        self.aircraft = []

    def _squadron(self, ac):
        sid = getattr(ac, "squadron", None)
        if sid is None:
            return None
        return next((q for q in self.fires.squadrons if q.id == sid), None)

    def attack(self, ac):
        g = self.game
        rng = g.rng
        at = ac.at
        tx, ty = int(ac.tx), int(ac.ty)
        if ac.mode in ("strafe",) or (ac.mode == "bomb" and not ac.bombs):
            # a line of fire along the flight path
            for dmg, rng_t, rounds in at.guns:
                for i in range(rounds):
                    k = rng.uniform(-8, 8)
                    x = int(round(tx + ac.dx * k + rng.gauss(0, 1.2)))
                    y = int(round(ty + ac.dy * k + rng.gauss(0, 1.2)))
                    self.air_round(ac, x, y, dmg, at.cannon_pen if dmg >= 90 else 0)
            for r in ac.rockets:
                pen, power, count = r
                for _ in range(count):
                    x = tx + rng.randint(-5, 5)
                    y = ty + rng.randint(-5, 5)
                    g.schedule_shell(x, y, 1, power, 3, 20, 22, None, f"a rocket from a {at.name}",
                                     whistle=False, side=ac.side, pen=pen)
                r[2] = 0
            g.emit_sound(tx, ty, 90, "aircraft", f"a {at.name} strafing", ac.side, None)
        if ac.bombs:
            for b in ac.bombs:
                power, radius, count = b
                for _ in range(count):
                    if ac.mode == "carpet":
                        k = rng.uniform(-25, 25)
                        x = int(tx + ac.dx * k + rng.gauss(0, 6))
                        y = int(ty + ac.dy * k + rng.gauss(0, 6))
                    elif ac.mode == "dive":
                        x = int(tx + rng.gauss(0, 2.5))
                        y = int(ty + rng.gauss(0, 2.5))
                    else:
                        x = int(tx + rng.gauss(0, 6))
                        y = int(ty + rng.gauss(0, 6))
                    g.schedule_shell(x, y, rng.randint(1, 3), power, radius, int(power / 8), 26, None,
                                     f"a bomb from a {at.name}", whistle=True, side=ac.side,
                                     sound="the whistle of falling bombs")
                b[2] = 0
            ac.bombs = []

    def air_round(self, ac, x, y, dmg, pen):
        g = self.game
        m = g.map
        if not m.in_bounds(x, y):
            return
        rng = g.rng
        a = g.soldier_at.get((x, y))
        if a is not None and a.alive:
            st = 2 if a.downed else a.stance
            chance = {0: 0.55, 1: 0.45, 2: 0.4}[st] * (1 - m.pos_cover[x, y] / 140)
            if T.FLOOR[m.t[x, y]] or T.TALL[m.t[x, y]]:
                chance *= 0.35    # roofs and canopy
            if rng.random() < chance:
                hit_actor(g, a, dmg * 0.6, "gunshot", None, f"{ac.at.name} gunfire")
        v = g.vehicle_at.get((x, y))
        if v is not None and not v.dead:
            hit_vehicle(g, v, pen or 12, dmg, x, y, None, f"{ac.at.name} cannon", kind="ap" if pen else "bullet",
                        face=3)
        # suppression everywhere near the line
        pos, actors = g.actor_array()
        for k, o in enumerate(actors):
            if abs(o.x - x) <= 2 and abs(o.y - y) <= 2:
                o.suppression = min(100.0, o.suppression + 6)
        if rng.random() < 0.3:
            m.blood[x, y] = m.blood[x, y]
        g.effect_explosion(x, y, 0)

    def aa_fire(self, ac):
        g = self.game
        rng = g.rng
        enemy = other_side(ac.side)
        # dedicated AA guns
        for v in g.vehicles:
            if v.side != enemy or not v.active or not v.vt.aa:
                continue
            d = math.hypot(v.x - ac.x, v.y - ac.y)
            if d < 60 and rng.random() < 0.5:
                g.emit_sound(v.x, v.y, 85, "cannon", "the pom-pom of flak", v.side, v)
                if rng.random() < 0.10 * (1 - d / 80):
                    ac.hp -= rng.uniform(30, 80)
        # machine guns and riflemen blaze away
        shooters = 0
        for a in g.actors:
            if a.side != enemy or not a.active or a.is_player or a.weapon is None:
                continue
            if a.weapon.t.kind != "gun" or a.weapon.t.cat not in ("lmg", "hmg"):
                continue
            if math.hypot(a.x - ac.x, a.y - ac.y) < 30:
                shooters += 1
                if shooters > 6:
                    break
                if rng.random() < 0.3:
                    a.fired_turn = g.turn
                    if rng.random() < 0.02:
                        ac.hp -= rng.uniform(10, 40)
        if ac.hp <= 0 and not ac.dead:
            ac.dead = True
            cx = int(ac.x + ac.dx * rng.randint(3, 15))
            cy = int(ac.y + ac.dy * rng.randint(3, 15))
            g.msg(f"A {ac.at.name} is hit! It trails smoke and plunges "
                  f"{'into the sea' if g.__dict__.get('domain') == 'aboard' else 'toward the ground'}!", "warn",
                  (int(ac.x), int(ac.y)))
            if g.map.in_bounds(cx, cy):
                g.schedule_shell(cx, cy, 2, 200, 3, 20, 20, None, f"a crashing {ac.at.name}",
                                 whistle=False, fire=3, side=None)
