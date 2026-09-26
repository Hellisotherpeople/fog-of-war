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

    # ------------------------------------------------------------ artillery
    def capacity_mult(self, side) -> float:
        """Installations in this and nearby sectors change what is available."""
        g = self.game
        mult = 1.0
        if g.strategic is not None:
            mult = g.strategic.support_mult(side, "arty", g.sector)
        return mult

    def request_fire(self, side, x, y, caller=None, battery=None, rounds=None, delay=None,
                     silent=False) -> bool:
        g = self.game
        if self.missions[side] < 1 and caller is not None and not getattr(caller, "is_player", False):
            return False
        grade = getattr(caller, "rank", 0) if caller is not None and getattr(caller, "is_player", False) else 0
        if self.missions[side] < 1 and caller is not None and caller.is_player:
            if grade >= 12:
                self.missions[side] = 1
                if not silent:
                    g.msg("Radio: 'All guns are committed - wait... Regiment gives you priority. Stand by.'",
                          "radio")
            else:
                if not silent:
                    g.msg("Radio: 'Negative, no guns available. Wait one.'", "radio")
                return False
        bats = self.batteries.get(side) or []
        if battery is None:
            if not bats:
                return False
            weights = [b.freq if b.freq > 0 else 1 for b in bats]
            if caller is not None and any(b.naval for b in bats) and g.rng.random() < 0.4:
                battery = next(b for b in bats if b.naval)
            else:
                battery = g.rng.choices(bats, weights)[0]
        if caller is not None:
            self.missions[side] -= 1
        rng = g.rng
        skill = getattr(caller, "skill", 5) if caller is not None else 5
        spread = battery.spread + max(0, 7 - skill) * 0.5
        # a systematic error: map reading, wind, worn barrels. Sometimes horribly wrong.
        bias_d = abs(rng.gauss(0, 3 + (8 - skill)))
        if rng.random() < 0.06:
            bias_d += rng.uniform(15, 35)          # short round / wrong grid
        ba = rng.uniform(0, math.tau)
        bias = (math.cos(ba) * bias_d, math.sin(ba) * bias_d)
        d = battery.delay + rng.randint(-10, 25) if delay is None else delay
        n = rounds or battery.salvo
        if grade >= 11:
            # the more senior the caller, the more guns answer - and the faster
            n = int(n * (1 + 0.15 * (grade - 10)))
            d = int(d * max(0.5, 1 - 0.06 * (grade - 10)))
        mult = self.capacity_mult(side)
        n = max(2, int(n * mult))
        fm = FireMission(side, battery, x, y, g.turn + d, caller, n, spread, bias)
        self.queue.append(fm)
        if caller is not None and (caller.is_player or g.player_near_radio(side)):
            if not silent:
                g.msg(f"Radio: 'Fire mission, {battery.name}. {n} rounds. Shot, over.'", "radio")
        return True

    def barrage(self, side, x, y, radius, rounds, delay=0, naval=False):
        """A scheduled bombardment (preparation, harassing fire, or the navy offshore)."""
        bats = self.batteries.get(side) or []
        g = self.game
        if naval:
            from .data.vehicles import BATTERIES
            nat = g.side_nation(side)
            bats = [b for b in BATTERIES.values() if b.naval and nat in b.nations
                    and b.years[0] <= g.year < b.years[1]]
        if not bats:
            return False
        land = [b for b in bats if not b.naval]
        pool = bats if (naval or not land or g.rng.random() < 0.25) else land
        b = g.rng.choice(pool)
        for i in range(max(1, rounds // b.salvo)):
            px = x + g.rng.randint(-radius, radius)
            py = y + g.rng.randint(-radius, radius)
            fm = FireMission(side, b, px, py, g.turn + delay + i * 20, None, b.salvo, b.spread + radius / 3, (0, 0))
            self.queue.append(fm)
        return True

    def update(self):
        g = self.game
        rng = g.rng
        for s in SIDES:
            self.missions[s] = min(8.0, self.missions[s] + self.arty_level.get(s, 0.5) * 0.004 * self.capacity_mult(s))
        keep = []
        for fm in self.queue:
            if g.turn < fm.fire_turn:
                keep.append(fm)
                continue
            b = fm.battery
            per_turn = 4 if b.rocket else 2
            for _ in range(min(per_turn, fm.rounds)):
                fm.rounds -= 1
                ix = int(round(fm.x + fm.bias[0] + rng.gauss(0, fm.spread)))
                iy = int(round(fm.y + fm.bias[1] + rng.gauss(0, fm.spread)))
                flight = rng.randint(2, 4)
                g.schedule_shell(ix, iy, flight, b.power, b.radius, b.frags, 24, None,
                                 f"a {b.cal} shell" if not b.rocket else f"a {b.cal}",
                                 whistle=True, sound=b.sound, side=fm.side)
            if fm.rounds > 0:
                fm.fire_turn = g.turn + (1 if b.rocket else rng.randint(1, 3))
                keep.append(fm)
            elif fm.caller is not None and getattr(fm.caller, "is_player", False):
                g.msg("Radio: 'Rounds complete, over.'", "radio")
        self.queue = keep
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
        planes = [p for p in self.planes.get(side, []) if (p.night if night else True)]
        if night:
            planes = [p for p in planes if p.night] or []
        if roles:
            planes = [p for p in planes if p.role in roles]
        if not planes:
            return False
        at = rng.choices(planes, [p.freq for p in planes])[0]
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
        # approach from a random direction, starting off-map
        ang = rng.uniform(0, math.tau)
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
        for i in range(n):
            off = (rng.uniform(-4, 4), rng.uniform(-4, 4))
            ac = Aircraft(at, side, g.side_nation(side), sx + off[0] - i * 6 * math.cos(ang),
                          sy + off[1] - i * 6 * math.sin(ang), tx + off[0] * 2, ty + off[1] * 2, mode)
            self.aircraft.append(ac)
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
                continue
            # left the map
            if (ac.x < -40 or ac.x > m.w + 40 or ac.y < -40 or ac.y > m.h + 40) and ac.attacked:
                ac.done = True
                continue
            keep.append(ac)
        self.aircraft = keep

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
