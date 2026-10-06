"""The war in the air and at sea.

One world at a larger scale: 100 m tiles, a strategic sector 30 tiles across, the same
endless map of the land war seen from above.  Aircraft and ships share it, so a carrier
can launch a strike that flies to an enemy fleet, a bomber stream can be met by
fighters and flak over the enemy's cities, and a pilot who bails out comes down in
whatever sector is below him.

Aircraft fly with real limits: speed, turn rate, climb, a stall.  Guns fire along the
nose (or from turrets with arcs, for a bomber's gunners); hits damage engines, wings,
tail, fuel and crew.  Ships steer and change speed ponderously; gunnery walks onto the
target salvo by salvo; torpedoes run straight and true or not at all; submarines dive
and escorts hunt them with sonar and depth charges.
"""
from __future__ import annotations

import math
import random

from .constants import other_side
from .data.ships import CLASS_NAME, SHIPS, available
from .data.vehicles import AIRCRAFT

SEC = 30                    # tiles per strategic sector
KMH_PER_TILE_S = 360.0      # 100 m/s = 360 km/h: one tile per second
KNOT_TILES_S = 0.005144     # a knot in tiles per second

TURN = {"fighter": 22, "fighterbomber": 18, "divebomber": 15, "torpedo": 12, "attacker": 14, "bomber": 9,
        "heavybomber": 7, "nightbomber": 24}
TURN_ID = {"zero": 27, "spitfire": 25, "i16": 25, "ki43": 27, "bf109": 21, "fw190": 20, "p47": 16, "p38": 17,
           "me262": 13, "f6f": 20, "f4f": 20, "la5": 22, "yak9": 23, "ki84": 22, "bf110": 15, "po2": 26,
           "swordfish": 18, "hurricane": 22, "mc202": 22, "cr42": 26, "pzl11": 23, "buffalo": 20}
CLIMB = {"fighter": 16, "fighterbomber": 13, "divebomber": 9, "torpedo": 7, "attacker": 8, "bomber": 6,
         "heavybomber": 4, "nightbomber": 3}
ENGINES = {"heavybomber": 4, "bomber": 2}
ENGINES_ID = {"p38": 2, "bf110": 2, "beaufighter": 2, "me262": 2, "sm79": 3, "blenheim": 2, "pe2": 2}
# defensive turrets: (station, arc centre (degrees off the nose, clockwise), half-arc, damage, range tiles, rounds)
TURRETS = {
    "divebomber": [("rear gunner", 180, 70, 50, 5, 8)],
    "torpedo": [("rear gunner", 180, 70, 50, 5, 8)],
    "bomber": [("nose gunner", 0, 50, 50, 5, 8), ("top gunner", 0, 180, 50, 5, 8), ("tail gunner", 180, 60, 50, 5, 8)],
    "heavybomber": [("nose gunner", 0, 50, 70, 6, 10), ("top turret", 0, 180, 70, 6, 10),
                    ("ball turret", 0, 180, 70, 6, 10), ("left waist", 270, 50, 70, 6, 10),
                    ("right waist", 90, 50, 70, 6, 10), ("tail gunner", 180, 50, 70, 6, 10)],
}
CARRIER_AIR = {"usa": (("f4f", "f6f"), ("sbd", "sb2c"), ("tbf",)),
               "japan": (("zero",), ("d3a", "d4y"), ("b5n", "b6n")),
               "uk": (("f4f", "f6f"), ("sbd", "barracuda"), ("swordfish", "tbf", "barracuda"))}


def _latest(nation, year, ids):
    ok = [i for i in ids if i in AIRCRAFT and AIRCRAFT[i].years[0] <= year < AIRCRAFT[i].years[1]]
    return ok[-1] if ok else (ids[0] if ids else None)


def flight(at):
    from .parked import DIMS
    role = at.role
    kmh = at.speed * 60
    return dict(kmh=kmh, turn=TURN_ID.get(at.id, TURN.get(role, 15)), climb=CLIMB.get(role, 8),
                engines=DIMS[at.id][2] if at.id in DIMS else ENGINES_ID.get(at.id, ENGINES.get(role, 1)),
                stall=kmh * 0.33,
                ceiling=11000 if role == "heavybomber" else 9000 if role in ("fighter", "fighterbomber") else 7000,
                turrets=TURRETS.get(role, []))


def bearing(x0, y0, x1, y1):
    """Compass bearing (0 = north, clockwise) from one point to another."""
    return math.degrees(math.atan2(x1 - x0, -(y1 - y0))) % 360


def angdiff(a, b):
    return (b - a + 180) % 360 - 180


def compass(h):
    return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][
        int((h % 360) / 22.5 + 0.5) % 16]


# ====================================================================== the things in it

class Plane:
    _next = 1

    def __init__(self, at_id, side, nation, x, y, hdg, alt, kmh=None, rng=None):
        at = AIRCRAFT[at_id]
        f = flight(at)
        self.id = Plane._next
        Plane._next += 1
        self.at_id = at_id
        self.name = at.name
        self.role = at.role
        self.side, self.nation = side, nation
        self.x, self.y, self.hdg, self.alt = float(x), float(y), float(hdg), float(alt)
        self.f = f
        self.kmh = kmh if kmh is not None else f["kmh"] * 0.8
        self.throttle = 0.85
        self.pitch = 0
        self.hp = dict(engine=[100.0] * f["engines"], wing_l=100.0, wing_r=100.0, tail=100.0, cockpit=100.0,
                       fuel=100.0)
        self.fire = 0
        self.fuel = 100.0
        self.ammo = 300 * max(1, len(at.guns))
        self.bombs = [list(b) for b in at.bombs]
        self.torpedo = at.role == "torpedo"
        rng = rng or random
        self.crew = [dict(station="pilot", alive=True, skill=rng.uniform(4, 8), turret=None, ammo=0)]
        for t in f["turrets"]:
            self.crew.append(dict(station=t[0], alive=True, skill=rng.uniform(3, 7), turret=t, ammo=500))
        if at.role in ("bomber", "heavybomber"):
            self.crew.insert(1, dict(station="bombardier", alive=True, skill=rng.uniform(4, 8), turret=None, ammo=0))
        self.state = "flying"
        self.ai = {}
        self.player = False
        self.kills = 0
        self.home = None          # (x, y) of its airfield or carrier id
        self.carrier = None
        self.dive_t = 0           # seconds in a steep dive (dive bombing accuracy)
        self.last_hit_by = None

    @property
    def alive(self):
        return self.state == "flying"

    def max_kmh(self):
        eng = self.hp["engine"]
        frac = sum(1 for e in eng if e > 0) / len(eng)
        return self.f["kmh"] * (0.35 + 0.65 * frac) * (0.85 if self.bombs or self.torpedo else 1.0)

    def turn_rate(self):
        r = self.f["turn"]
        wing = min(self.hp["wing_l"], self.hp["wing_r"])
        if wing < 40:
            r *= 0.55
        if self.hp["tail"] < 40:
            r *= 0.5
        return r

    def dirv(self):
        h = math.radians(self.hdg)
        return math.sin(h), -math.cos(h)


class Ship:
    _next = 1

    def __init__(self, sid, side, nation, x, y, hdg, name=None, rng=None):
        st = SHIPS[sid]
        self.id = Ship._next
        Ship._next += 1
        self.sid = sid
        self.st = st
        self.cls = st["cls"]
        self.side, self.nation = side, nation
        self.x, self.y, self.hdg = float(x), float(y), float(hdg)
        self.order_hdg = float(hdg)
        self.kn = st["speed"] * 0.6
        self.order_kn = st["speed"] * 0.6
        self.hp = float(st["hp"])
        self.flood = 0.0
        self.fires = 0
        self.main_ready = 0.0
        self.sec_ready = 0.0
        self.torps = st["torps"][0] if st["torps"] else 0
        self.dc = st["dc"]
        self.depth = 0            # submarines: 0 surfaced, 1 periscope depth, 2 deep
        self.battery = 100.0
        self.air = list(st["air"]) if st["air"] else None
        self.ranging = {}
        self.sunk = False
        self.player = False
        self.ai = {}
        self.name = name or f"{CLASS_NAME.get(self.cls, 'ship').title()} {self.id}"
        self.target = None
        self.turret_out = 0
        self.fuel = 100.0         # per cent of her bunkers (three days' steaming at 20 knots)

    @property
    def alive(self):
        return not self.sunk

    def dirv(self):
        h = math.radians(self.hdg)
        return math.sin(h), -math.cos(h)

    def cells(self):
        dx, dy = self.dirv()
        L = self.st["length"]
        return [(self.x + dx * (i - (L - 1) / 2), self.y + dy * (i - (L - 1) / 2)) for i in range(L)]


# ====================================================================== the world

class SkySea:
    def __init__(self, game, cx, cy):
        self.game = game
        self.planes: list[Plane] = []
        self.ships: list[Ship] = []
        self.torps = []           # dict(x, y, hdg, kn, left, side, src, dmg, dud)
        self.shells = []          # dict(x, y, eta, dmg, pen, side, src, target, plunge)
        self.ground = []          # ground targets: dict(kind, x, y, hp, side, name, sector, dead, vx, vy)
        self.effects = []         # dict(kind, x, y, t)
        self.flak = []            # dict(x, y, r, heavy, light, side)
        self.t = 0.0
        self.cx, self.cy = cx, cy
        self.mission = None
        self.player_plane = None
        self.player_ship = None
        self.station = "pilot"
        self.target = None        # the player's chosen target id (plane, ship or ground)
        self.last_strategic = 0.0
        self.contacts = set()     # ids the player's side can see
        self.over = None          # how it ended, for the UI
        self.chute = None         # (x, y, alt) while hanging under a parachute
        self.raft = None          # (x, y) adrift
        self.news = []
        self.hit_hook = None      # aboard.py: what a hit on your ship does to the deck you're on
        self.local_hook = None    # aboard.py: an attack run on your ship, flown over your deck
        self.plane_hook = None    # aboard.py: fire through the fuselage you're standing in

    def __getstate__(self):
        d = dict(self.__dict__)
        for k in ("hit_hook", "local_hook", "plane_hook"):
            d[k] = None                     # re-attached each second while you're aboard (aboard.py)
        return d

    # ------------------------------------------------------------ geometry
    def sector_at(self, x, y):
        return self.game.strategic.at(int(math.floor(x / SEC)), int(math.floor(y / SEC)), create=True)

    def is_sea(self, x, y):
        c = self.sector_at(x, y)
        return c is None or c.biome == "sea"

    def rng(self):
        return self.game.rng

    def add_effect(self, kind, x, y, dur=1.5):
        self.effects.append(dict(kind=kind, x=x, y=y, t=self.t + dur))

    def entity(self, eid):
        for p in self.planes:
            if p.id == eid:
                return p
        for s in self.ships:
            if -s.id == eid:
                return s
        for g in self.ground:
            if g["id"] == eid:
                return g
        return None

    # ------------------------------------------------------------ flak and ground
    def build_flak(self, side_against, radius=6):
        """Enemy flak over their installations, airfields, towns - and their ships."""
        st = self.game.strategic
        self.flak = []
        enemy = other_side(side_against)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                c = st.at(self.cx + dx, self.cy + dy, create=True)
                if c is None or c.control != enemy or not c.playable:
                    continue
                heavy = 8 * len(c.installs(enemy, "aa")) + 5 * len(c.installs(enemy, "airfield"))
                light = 3 * len(c.installs(enemy)) + (4 if c.biome in ("town", "city_ruins", "factory") else 1)
                if st.is_front(c, enemy):
                    light += 3
                if heavy or light:
                    self.flak.append(dict(x=(c.x + 0.5) * SEC, y=(c.y + 0.5) * SEC, r=SEC * 0.7, heavy=heavy,
                                          light=light, side=enemy))

    # ------------------------------------------------------------ time passes
    def step(self, seconds=1, clock=True):
        """Time passes.  clock=False: aboard, the game's own turn keeps the clock and the war map."""
        g = self.game
        for _ in range(int(seconds)):
            self.t += 1
            for p in list(self.planes):
                if p.alive and not p.ai.get("local"):
                    self._fly(p)
            for s in list(self.ships):
                if s.alive:
                    self._sail(s)
            self._shells()
            self._torpedoes()
            self._flak_fire()
            self._chute()
            self._detect()
            self.effects = [e for e in self.effects if e["t"] > self.t]
            if self.t % 60 == 0:
                from .sealogistics import tick as replenish
                replenish(self)
                # aircraft that have landed or gone down are out of the story
                self.planes = [p for p in self.planes if p.alive or p.player or p.ai.get("local") or
                               p is self.player_plane]
            if not clock:
                if self.mission:
                    from .skysea_missions import check
                    check(self)
                if self.over:
                    break
                continue
            g.advance_clock(1)
            g.turn += 1
            g._weather_tick()
            if self.t - self.last_strategic >= 600:
                self.last_strategic = self.t
                try:
                    g._strategic_tick()
                except Exception:
                    pass
            if self.mission:
                from .skysea_missions import check
                check(self)
            if self.over:
                break

    # ------------------------------------------------------------ flight
    def _fly(self, p: Plane):
        from .weather import state as weather_state
        rng = self.rng()
        if not p.player or self.station != "pilot":
            self._pilot_ai(p)
        if not p.alive:
            return
        # speed toward the throttle setting, minus climbing, plus diving
        target = p.max_kmh() * (0.45 + 0.55 * p.throttle)
        if p.pitch > 0:
            target -= 90
        elif p.pitch < 0:
            target += 160
        p.kmh += max(-22, min(22, (target - p.kmh) * 0.25))
        p.kmh = max(60.0, min(p.f["kmh"] * 1.35, p.kmh))
        # altitude
        steep = p.pitch < 0 and p.role == "divebomber" and (p.ai.get("role") == "dive" or p.player)
        climb = p.f["climb"] * (p.kmh / p.f["kmh"]) if p.pitch > 0 else \
            (-90 if steep else -p.f["climb"] * 3) if p.pitch < 0 else 0
        if p.kmh < p.f["stall"]:
            climb = min(climb, -25)              # stalled: the nose drops
            p.hdg += rng.uniform(-8, 8)
        if p.hp["tail"] <= 0 or min(p.hp["wing_l"], p.hp["wing_r"]) <= 0:
            climb = -60                          # out of control, spinning in
            p.hdg += 25
        p.alt = max(0.0, min(p.f["ceiling"], p.alt + climb))
        p.dive_t = p.dive_t + 1 if p.pitch < 0 and p.kmh > p.f["kmh"] * 0.9 else 0
        dx, dy = p.dirv()
        v = p.kmh / KMH_PER_TILE_S * (0.3 if steep else 1.0)      # a steep dive covers little ground
        p.x += dx * v
        p.y += dy * v
        wind = weather_state(self.game)["wind"] / 100
        wx, wy = self.game.wind
        norm = max(1, math.hypot(wx, wy))
        p.x += wx * wind / norm
        p.y += wy * wind / norm
        if self.game.weather in ("storm", "blizzard"):
            p.hdg = (p.hdg + rng.uniform(-1.5, 1.5)) % 360
            p.alt = max(1, p.alt + rng.uniform(-8, 8))
        # fuel, fire
        p.fuel -= (0.004 + 0.012 * p.throttle) * (2.5 if p.hp["fuel"] < 50 else 1.0)
        if p.fire:
            p.fire += 1
            p.hp["fuel"] -= 2
            p.hp["wing_l"] -= 1
            if p.fire > 25 or p.hp["fuel"] <= 0:
                self._down(p, "blew up in the air")
                return
        if p.fuel <= 0:
            p.hp["engine"] = [0] * len(p.hp["engine"])
        if p.alt <= 0:
            if self.is_sea(p.x, p.y) and p.kmh < 260 and rng.random() < 0.5:
                self._down(p, "ditched in the sea")
            else:
                self._down(p, "crashed")
            return
        # guns (AI), gunners, bombs (AI)
        self._turrets(p)

    def _pilot_ai(self, p: Plane):
        rng = self.rng()
        role = p.ai.get("role", "fighter")
        tgt = self.entity(p.ai.get("target")) if p.ai.get("target") else None
        if isinstance(tgt, Plane) and not tgt.alive:
            tgt = None
        ship_tgt = tgt if isinstance(tgt, Ship) and tgt.alive else None
        if not isinstance(tgt, Plane):
            tgt = None
        low = p.fuel < 20 or p.ammo <= 0 and role in ("fighter", "escort", "cap") or \
            sum(1 for e in p.hp["engine"] if e > 0) < len(p.hp["engine"]) / 2
        if low and role != "kamikaze":
            role = "home"
        p.throttle = 0.9
        want_hdg, want_alt = p.hdg, p.alt
        if role in ("fighter", "escort", "cap", "intercept"):
            # someone on my tail? break
            threat = None
            for e in self.planes:
                if e.alive and e.side != p.side and e.role in ("fighter", "fighterbomber"):
                    d = math.hypot(e.x - p.x, e.y - p.y)
                    if d < 5 and abs(angdiff(e.hdg, bearing(e.x, e.y, p.x, p.y))) < 25 and abs(e.alt - p.alt) < 250:
                        threat = e
            if threat is not None and rng.random() < 0.7:
                want_hdg = p.hdg + (90 if angdiff(threat.hdg, p.hdg) > 0 else -90)
                want_alt = p.alt - 400
                p.throttle = 1.0
            else:
                if tgt is None or not getattr(tgt, "alive", False):
                    tgt = self._pick_air_target(p, prefer=("bomber", "heavybomber", "torpedo", "divebomber")
                                                if role == "intercept" else None)
                    p.ai["target"] = tgt.id if tgt is not None else None
                if tgt is not None:
                    lead = 2.0
                    tv = tgt.kmh / KMH_PER_TILE_S
                    tdx, tdy = tgt.dirv()
                    want_hdg = bearing(p.x, p.y, tgt.x + tdx * tv * lead, tgt.y + tdy * tv * lead)
                    want_alt = tgt.alt + 100
                    p.throttle = 1.0
                    self._ai_fire(p, tgt)
                else:
                    # patrol: orbit a point
                    cx, cy = p.ai.get("station", (p.x, p.y))
                    if math.hypot(cx - p.x, cy - p.y) > 8:
                        want_hdg = bearing(p.x, p.y, cx, cy)
                    else:
                        want_hdg = p.hdg + 15
                    want_alt = p.ai.get("alt", 3000)
                    p.throttle = 0.75
                    if role == "escort" and p.ai.get("leader"):
                        ldr = self.entity(p.ai["leader"])
                        if ldr is not None and ldr.alive and ldr.ai.get("role") != "home":
                            want_hdg = bearing(p.x, p.y, ldr.x + 2, ldr.y - 2)
                            want_alt = ldr.alt + 600
                        elif p.ai.get("home_pt") or p.home:
                            p.ai["role"] = "home"           # the strike's done: the fighters go home with it
        elif role in ("bomber", "strike", "dive", "torpedo", "attack", "recon", "resupply"):
            wp = p.ai.get("wp")
            if p.ai.get("leader") and p.ai.get("offset"):
                ldr = self.entity(p.ai["leader"])
                if ldr is not None and ldr.alive:
                    ox, oy = p.ai["offset"]
                    want_hdg = bearing(p.x, p.y, ldr.x + ox, ldr.y + oy)
                    if math.hypot(ldr.x + ox - p.x, ldr.y + oy - p.y) < 1.2:
                        want_hdg = ldr.hdg
                    want_alt = ldr.alt
                    p.throttle = 0.8 if math.hypot(ldr.x + ox - p.x, ldr.y + oy - p.y) < 3 else 1.0
                    if ldr.ai.get("drop") and (p.bombs or p.torpedo) and role == "bomber":
                        self.drop(p)
                    wp = None
                else:
                    p.ai.pop("leader", None)
            if wp is not None:
                tx, ty = wp
                want_hdg = (bearing(p.x, p.y, tx, ty) + p.ai.get("bomb_trim", 0)) % 360   # (the bomb aimer's trim)
                d = math.hypot(tx - p.x, ty - p.y)
                if role == "resupply":
                    p.throttle = min(.6, max(0., (260 / max(1, p.max_kmh()) - .45) / .55))
                    if d < 2 and 80 <= p.alt <= 600 and p.kmh <= 300:
                        self.drop(p)
                want_alt = p.ai.get("alt", 4000)
                if role == "dive":
                    want_alt = 3000 if d > 9 else 400
                    if d < 9 and p.alt > 700:
                        p.pitch = -1
                elif role in ("torpedo",):
                    want_alt = 1200 if d > 25 else 40
                    if d < 25 and not p.player:
                        p.throttle = 0.4 if p.kmh > 290 else 0.7     # slow for the run, or the fish breaks up
                elif role == "attack":
                    want_alt = 1500 if d > 10 else 200
                tgt = ship_tgt
                if tgt is None and role in ("torpedo", "dive") and any(s2.side != p.side for s2 in self.ships):
                    # find the nearest enemy ship we can see
                    seen = [s2 for s2 in self.ships if s2.alive and s2.side != p.side and not (s2.cls == "ss" and s2.depth)
                            and math.hypot(s2.x - p.x, s2.y - p.y) < 60]
                    if seen:
                        tgt = min(seen, key=lambda s2: math.hypot(s2.x - p.x, s2.y - p.y))
                        p.ai["target"] = -tgt.id
                if tgt is not None and isinstance(tgt, Ship) and tgt.alive:
                    tdx, tdy = tgt.dirv()
                    tv = tgt.kn * KNOT_TILES_S
                    # lead him by as long as the weapon takes to get there
                    d0 = math.hypot(tgt.x - p.x, tgt.y - p.y)
                    lead = d0 / (33 * KNOT_TILES_S) if role == "torpedo" else \
                        math.sqrt(2 * max(p.alt, 1) / 9.8) + 2 if role == "dive" else 20
                    tx, ty = tgt.x + tdx * tv * lead, tgt.y + tdy * tv * lead
                    want_hdg = bearing(p.x, p.y, tx, ty)
                    d = math.hypot(tx - p.x, ty - p.y)
                    if tgt.player and self.local_hook is not None and d < 10 and (p.bombs or p.torpedo) and \
                            self.local_hook(p, tgt):
                        return
                if (p.bombs or p.torpedo) and self._release_ok(p, tx, ty, d):
                    self.drop(p)
                    p.ai["drop"] = True
                    p.ai["wp"] = p.ai.get("home_pt")
                    p.ai["role"] = "home"
                if role == "attack" and d < 6:
                    for g2 in self.ground:
                        if not g2["dead"] and g2["side"] != p.side and math.hypot(g2["x"] - p.x, g2["y"] - p.y) < 3:
                            self._strafe(p, g2)
                            break
                if role == "recon" and d < 2:
                    p.ai["photo"] = True
                    p.ai["wp"] = p.ai.get("home_pt")
                    p.ai["role"] = "home"
        elif role == "kamikaze":
            tgt = ship_tgt
            if tgt is not None and getattr(tgt, "alive", False):
                want_hdg = bearing(p.x, p.y, tgt.x, tgt.y)
                d = math.hypot(tgt.x - p.x, tgt.y - p.y)
                if getattr(tgt, "player", False) and self.local_hook is not None and d < 10 and \
                        self.local_hook(p, tgt):
                    return
                want_alt = 20 if d < 6 else 1500
                p.throttle = 1.0
                if d < 0.8 and p.alt < 120 and isinstance(tgt, Ship):
                    self._ship_hit(tgt, 500, 200, "a kamikaze", fire=True)
                    self._down(p, "dived into the ship")
                    return
        if role == "home":
            hp = p.ai.get("home_pt") or p.home
            car = self.entity(-p.carrier) if p.carrier else None
            if isinstance(car, Ship) and car.alive:
                hp = (car.x, car.y)              # the carrier has steamed on since the launch
            if hp is not None:
                want_hdg = bearing(p.x, p.y, hp[0], hp[1])
                d = math.hypot(hp[0] - p.x, hp[1] - p.y)
                want_alt = 1200 if d > 6 else 100
                p.throttle = 0.7
                if d < 1.5:
                    from .weather import flight_factor
                    if flight_factor(self.game) < .2:
                        p.hdg = (p.hdg + 12) % 360
                        p.pitch = 0
                        return                  # hold above the field/deck until it can receive us
                    p.state = "landed"
                    car = self.entity(-p.carrier) if p.carrier else None
                    if isinstance(car, Ship) and car.alive and car.air is not None:
                        car.air[{"fighter": 0, "divebomber": 1, "torpedo": 2}.get(p.role, 0)] += 1
                    return
        # nobody flies into the ground on purpose
        floor = 30 if role in ("torpedo", "kamikaze") else 150 if role == "attack" else 250
        if p.alt < floor + 150 and want_alt < floor:
            want_alt = floor
        if p.alt < floor + 100 and p.pitch < 0:
            p.pitch = 0
        # steer and climb toward what we want, within the aircraft's limits
        dh = angdiff(p.hdg, want_hdg)
        tr = p.turn_rate()
        p.hdg = (p.hdg + max(-tr, min(tr, dh))) % 360
        if not (p.ai.get("role") == "dive" and p.pitch < 0 and p.alt > 700):
            p.pitch = 1 if want_alt > p.alt + 60 else -1 if want_alt < p.alt - 60 else 0

    def _release_ok(self, p, tx, ty, d):
        role = p.ai.get("role", p.role)
        if role == "torpedo" or p.torpedo:
            return d < 9 and p.alt < 90
        if role == "dive":
            # let go when the bomb's own short fall along the dive line will carry it there
            return p.alt < 900 and d < p.alt * 0.4 / 100.0 + 0.4
        # level bombing: the bombs fall forward as far as the aircraft flies while they fall
        fall = math.sqrt(2 * max(p.alt, 1) / 9.8)
        throw = p.kmh / 3.6 * fall / 100.0
        dx, dy = p.dirv()
        return math.hypot(p.x + dx * throw - tx, p.y + dy * throw - ty) < 1.2

    def _pick_air_target(self, p, prefer=None):
        best, bd = None, 1e9
        for e in self.planes:
            if not e.alive or e.side == p.side or not self._seen_by(p, e):
                continue
            d = math.hypot(e.x - p.x, e.y - p.y) + abs(e.alt - p.alt) / 300
            if prefer and e.role in prefer:
                d *= 0.5
            if d < bd and d < 60:
                best, bd = e, d
        return best

    # ------------------------------------------------------------ guns
    def _ai_fire(self, p, tgt):
        if p.ammo <= 0:
            return
        d = math.hypot(tgt.x - p.x, tgt.y - p.y)
        off = abs(angdiff(p.hdg, bearing(p.x, p.y, tgt.x, tgt.y)))
        rng = max(g[1] for g in AIRCRAFT[p.at_id].guns) / 3.0 if AIRCRAFT[p.at_id].guns else 3
        if d < rng and off < 9 and abs(tgt.alt - p.alt) < 150:
            self.fire_guns(p, tgt)

    def fire_guns(self, p, tgt=None):
        """A burst from the nose guns at whatever is in front."""
        at = AIRCRAFT[p.at_id]
        if not at.guns or p.ammo <= 0:
            return 0
        p.ammo -= sum(g[2] for g in at.guns) // 2
        rng = max(g[1] for g in at.guns) / 3.0
        cands = [tgt] if tgt is not None else [e for e in self.planes if e.alive and e is not p]
        hits = 0
        best = None
        for e in cands:
            if e is None or not getattr(e, "alive", False) or not isinstance(e, Plane):
                continue
            d = math.hypot(e.x - p.x, e.y - p.y)
            off = abs(angdiff(p.hdg, bearing(p.x, p.y, e.x, e.y)))
            if d <= rng and off < 10 and abs(e.alt - p.alt) < 160:
                if best is None or d < best[0]:
                    best = (d, e, off)
        sk = p.crew[0]["skill"]
        if best is not None:
            d, e, off = best
            rel = abs(angdiff(p.hdg, e.hdg))
            defl = 1.0 if rel < 30 else 0.55 if rel > 150 else 0.35
            pr = 0.3 * (1 - d / (rng + 0.1)) ** 0.5 * defl * (0.6 + sk * 0.07) * (1 - off / 14)
            for gdmg, grng, grounds in at.guns:
                for _ in range(max(1, grounds // 12)):
                    if self.rng().random() < pr:
                        hits += 1
                        self._plane_hit(e, gdmg, p, aspect=rel)
        dx, dy = p.dirv()
        self.add_effect("tracer", p.x + dx * rng, p.y + dy * rng, 0.6)
        if p.alt < 400:
            for g2 in self.ground:
                if not g2["dead"] and g2["side"] != p.side and math.hypot(g2["x"] - (p.x + dx * 2), g2["y"] - (p.y + dy * 2)) < 2:
                    self._strafe(p, g2)
                    break
        return hits

    def _turrets(self, p):
        """Every gunner aboard, firing at whatever comes into his arc."""
        rng = self.rng()
        for c in p.crew:
            t = c.get("turret")
            if not t or not c["alive"] or c["ammo"] <= 0:
                continue
            if p.player and self.station == c["station"]:
                continue                        # that's you: you choose when to fire
            for e in self.planes:
                if not e.alive or e.side == p.side or e.role not in ("fighter", "fighterbomber", "attacker"):
                    continue
                d = math.hypot(e.x - p.x, e.y - p.y)
                if d > t[4] or abs(e.alt - p.alt) > 300:
                    continue
                rel = angdiff(p.hdg + t[1], bearing(p.x, p.y, e.x, e.y))
                if abs(rel) > t[2]:
                    continue
                c["ammo"] -= t[5]
                if rng.random() < 0.10 * (0.6 + c["skill"] * 0.07) * (1 - d / (t[4] + 1)):
                    self._plane_hit(e, t[3], p, aspect=90)
                break

    def gunner_fire(self, p, station, tgt):
        """You, at a turret: a burst at the target (if it's in your arc)."""
        c = next((c for c in p.crew if c["station"] == station), None)
        if c is None or not c.get("turret") or not isinstance(tgt, Plane) or not tgt.alive:
            return "Nothing to shoot at."
        t = c["turret"]
        d = math.hypot(tgt.x - p.x, tgt.y - p.y)
        rel = angdiff(p.hdg + t[1], bearing(p.x, p.y, tgt.x, tgt.y))
        if abs(rel) > t[2]:
            return "He's outside your arc."
        if d > t[4] + 1:
            return "Out of range - wait for him."
        c["ammo"] -= t[5]
        rv = abs(angdiff(p.hdg, tgt.hdg))
        defl = 1.0 if rv < 30 or rv > 150 else 0.55
        pr = 0.28 * (1 - d / (t[4] + 1.5)) * defl * (0.6 + self.game.player.skill * 0.07)
        if self.rng().random() < pr:
            self._plane_hit(tgt, t[3], p, aspect=90)
            return "Hits! Pieces fly off him."
        return "Tracers curve past him."

    def _plane_hit(self, e, dmg, src, aspect=0):
        rng = self.rng()
        e.last_hit_by = src.id if src is not None else None
        if aspect < 40:
            w = [("tail", 3), ("engine", 2), ("cockpit", 1.2), ("fuel", 2), ("wing", 2)]
        elif aspect > 140:
            w = [("engine", 4), ("cockpit", 2), ("wing", 2), ("fuel", 1)]
        else:
            w = [("wing", 3), ("fuel", 2), ("cockpit", 1.5), ("engine", 1.5), ("tail", 1)]
        part = rng.choices([a for a, _ in w], [b for _, b in w])[0]
        amt = dmg * rng.uniform(0.25, 0.6) * (1.6 if dmg >= 90 else 1.0)
        if part == "engine":
            i = rng.randrange(len(e.hp["engine"]))
            e.hp["engine"][i] = max(0.0, e.hp["engine"][i] - amt)
            if e.hp["engine"][i] <= 0 and rng.random() < 0.3:
                e.fire = max(e.fire, 1)
        elif part == "wing":
            k = rng.choice(("wing_l", "wing_r"))
            e.hp[k] = max(0.0, e.hp[k] - amt)
        elif part == "fuel":
            e.hp["fuel"] = max(0.0, e.hp["fuel"] - amt)
            if rng.random() < 0.12 + (0.25 if e.nation == "japan" else 0):
                e.fire = max(e.fire, 1)          # (the Zero had no self-sealing tanks)
        elif part == "cockpit":
            e.hp["cockpit"] = max(0.0, e.hp["cockpit"] - amt)
            crew = [c for c in e.crew if c["alive"]]
            if crew and rng.random() < 0.35:
                c = rng.choice(crew)
                if c["station"] == "pilot" and e.player and self.station == "pilot" or \
                        (e.player and c["station"] == self.station):
                    self._player_wounded(amt)
                elif rng.random() < 0.5:
                    c["alive"] = False
                    if c["station"] == "pilot" and not e.player:
                        if not any(x["alive"] and x["station"] in ("copilot", "bombardier") for x in e.crew):
                            e.hp["tail"] = 0          # nobody flying it
        else:
            e.hp[part] = max(0.0, e.hp[part] - amt)
        if e.player and self.plane_hook is not None:
            self.plane_hook(e, dmg, part)
        dead_pilot = not e.crew[0]["alive"] and not e.player
        if (e.hp["tail"] <= 0 or min(e.hp["wing_l"], e.hp["wing_r"]) <= 0 or dead_pilot) and not getattr(e, "_doomed", False):
            e._doomed = True
            if src is not None and hasattr(src, "kills"):
                src.kills += 1
                self._victory(src, e)

    def _victory(self, src, e):
        g = self.game
        if src.player:
            g.player.kills += 1
            n = src.kills
            g.msg(f"The {e.name} goes down in flames! (victory {n})" if e.fire else
                  f"The {e.name} spins away, out of control! (victory {n})", "good")
            g.command.merit += 3 if e.role in ("fighter", "fighterbomber") else 2
            if n == 5:
                g.msg("Five victories. You're an ace.", "good")
                g.command._award(g, 2, "for five aerial victories")
        elif e.player:
            crewed = (g.__dict__.get("aboard") or {}).get("kind") == "plane"
            g.msg(f"You've been hit hard - the {e.name} is going down! Bail out! "
                  + ("(back into the fuselage, e at the hatch)" if crewed else "(e)"), "death")

    def _player_wounded(self, amt):
        from .combat import hit_actor
        g = self.game
        part = self.rng().choice(("torso", "l_arm", "r_arm", "l_leg", "head"))
        hit_actor(g, g.player, amt * 0.5, "fragment", None, "cannon fire in the cockpit")
        g.msg("Something smashes into the cockpit - you're hit!", "hurt")

    def _down(self, p, how):
        rng = self.rng()
        if p.state != "flying":
            return
        p.state = "down"
        self.add_effect("explosion", p.x, p.y, 3)
        if p.player:
            self.game.msg(f"Your {p.name} {how}.", "death")
            if how in ("crashed", "blew up in the air", "dived into the ship"):
                if self.chute is None:
                    g = self.game
                    g.player.body.dead = True
                    g.player.body.cause = f"your {p.name} {how}"
                    self.over = "dead"
            elif how == "ditched in the sea":
                self.raft = (p.x, p.y)
                self.game.msg("You scramble out as it sinks and inflate the dinghy.", "warn")
                self.over = "raft"
        # bombers' crews bail out, sometimes
        if not p.player and p.role in ("bomber", "heavybomber") and rng.random() < 0.6:
            n = sum(1 for c in p.crew if c["alive"])
            self.news.append(f"{rng.randint(0, n)} parachutes blossom from the stricken {p.name}.")

    def bail_out(self, p):
        if p.alt < 120:
            return "Too low to jump!"
        self.chute = (p.x, p.y, p.alt)
        p.hp["tail"] = 0                      # the empty aircraft spins in
        p.player = False
        self.player_plane = None
        self.game.msg("You roll the canopy back and go over the side. The chute cracks open.", "warn")
        return None

    def _chute(self):
        if self.chute is None:
            return
        x, y, alt = self.chute
        alt -= 6
        x += self.game.wind[0] * 0.05
        y += self.game.wind[1] * 0.05
        self.chute = (x, y, alt)
        if alt <= 0:
            self.chute = None
            if self.is_sea(x, y):
                self.raft = (x, y)
                self.over = "raft"
                self.game.msg("You hit the water hard, and fight free of the harness.", "warn")
            else:
                self.over = ("landed_chute", x, y)

    # ------------------------------------------------------------ bombs, torpedoes, strafing
    def drop(self, p):
        """Bombs away (or the torpedo) - and then, as for any bomber that's let go, the turn for home."""
        if p is self.player_plane and (self.mission or {}).get("kind") == "resupply":
            from .airlogistics import drop_supplies
            return drop_supplies(self, p)
        self._drop(p)
        if not p.bombs and not p.torpedo and p.ai.get("role") in ("bomber", "dive", "torpedo", "attack", "strike"):
            p.ai["drop"] = True                   # (the formation keys its own release off the leader's)
            p.ai.pop("bomb_trim", None)
            if p.ai.get("home_pt") or p.home:
                p.ai["wp"] = p.ai.get("home_pt") or p.home
                p.ai["role"] = "home"

    def _drop(self, p):
        rng = self.rng()
        if p.torpedo:
            p.torpedo = False
            p.bombs = []
            if p.kmh > 330 or p.alt > 90:
                if p.player:
                    self.game.msg("Too fast, too high - the torpedo breaks up as it hits the water.", "warn")
                return
            self.torps.append(dict(x=p.x, y=p.y, hdg=p.hdg, kn=33, left=40, side=p.side, src=p.id,
                                   dmg=450, dud=rng.random() < (0.25 if p.nation == "usa" and self.game.year < 1943.5
                                                                 else 0.06)))
            if p.player:
                self.game.msg("Torpedo away! It drops, hits the water, and runs.", "good")
            return
        if not p.bombs:
            return
        fall = math.sqrt(2 * max(p.alt, 1) / 9.8)
        throw = p.kmh / 3.6 * fall / 100.0
        if p.dive_t >= 3 or (p.ai.get("role") == "dive" and not p.player):
            throw = p.alt * 0.4 / 100.0         # in a 70-degree dive the bomb goes where the nose points
        dx, dy = p.dirv()
        cx, cy = p.x + dx * throw, p.y + dy * throw
        sk = next((c["skill"] for c in p.crew if c["station"] == "bombardier" and c["alive"]), p.crew[0]["skill"])
        if p.player and self.station in ("bombardier", "pilot"):
            sk = self.game.player.skill
        scatter = (p.alt / 1000.0) * 0.45 + 0.4 - sk * 0.03
        if p.dive_t >= 3:
            scatter = 0.25 + p.alt / 4000.0     # dive bombing: point at it and let go
        if any(math.hypot(f["x"] - p.x, f["y"] - p.y) < f["r"] for f in self.flak if f["side"] != p.side):
            scatter *= 1.3
        for power, radius, count in p.bombs:
            for _ in range(count):
                bx, by = cx + rng.gauss(0, scatter), cy + rng.gauss(0, scatter)
                self._impact(bx, by, power, p)
        p.bombs = []
        if p.player:
            self.game.msg("Bombs gone!", "good")

    def _impact(self, x, y, power, src):
        rng = self.rng()
        self.add_effect("blast", x, y, 2.0)
        r = 0.35 + power / 1500.0
        for s in self.ships:
            if not s.alive or s.side == src.side:
                continue
            if any(math.hypot(cx - x, cy - y) < r + 0.25 for cx, cy in s.cells()):
                self._ship_hit(s, power * 0.9, power * 0.3, f"a bomb from a {src.name}", fire=rng.random() < 0.4,
                               deck=True)
        for g2 in self.ground:
            if not g2["dead"] and g2["side"] != src.side and math.hypot(g2["x"] - x, g2["y"] - y) < r + 0.6:
                g2["hp"] -= power
                if g2["hp"] <= 0:
                    self._ground_dead(g2, src)

    def _strafe(self, p, g2):
        rng = self.rng()
        dmg = sum(d for d, _, _ in AIRCRAFT[p.at_id].guns) * (2.0 if AIRCRAFT[p.at_id].rockets else 1.0)
        if rng.random() < 0.5:
            g2["hp"] -= dmg
            self.add_effect("blast", g2["x"], g2["y"], 1.0)
            if g2["hp"] <= 0:
                self._ground_dead(g2, p)

    def _ground_dead(self, g2, src):
        g2["dead"] = True
        g = self.game
        st = g.strategic
        c = st.at(*g2["sector"]) if g2.get("sector") else None
        if c is not None:
            from .homefront import FACILITIES
            kind = "rail_yard" if g2["kind"] == "railyard" else g2["kind"]
            if kind in ("depot", "artillery", "aa", "airfield", "hq", "motor_pool", "bridge") or kind in FACILITIES:
                for inst in c.installations:
                    if inst[0] == kind and inst[1] == g2["side"] and inst[2]:
                        inst[2] = False
                        break
                if kind in FACILITIES:
                    from .sustain import stores
                    resource = FACILITIES[kind][2]
                    stock = stores(c, g2["side"])
                    if resource in stock:
                        stock[resource] *= .15
                    st.interdict(g2["side"], c, .45, f"Air attack has knocked out the {g2['name']}.")
                if g2["kind"] in ("factory", "railyard", "city"):
                    g.__dict__.setdefault("bombed", {})[g2["side"]] = g.__dict__.get("bombed", {}).get(g2["side"], 0) + 1
            elif g2["kind"] in ("column", "tanks", "train"):
                st._attrit(c.units[g2["side"]], 2.0, g2["side"])
        if src is not None and getattr(src, "player", False):
            g.msg(f"The {g2['name']} is destroyed!", "good")
            g.command.merit += 2

    # ------------------------------------------------------------ flak
    def _flak_fire(self):
        rng = self.rng()
        for p in self.planes:
            if not p.alive:
                continue
            for f in self.flak:
                if f["side"] == p.side or math.hypot(f["x"] - p.x, f["y"] - p.y) > f["r"]:
                    continue
                heavy = f["heavy"] if 1200 < p.alt < 8500 else 0
                light = f["light"] if p.alt < 2200 else 0
                if rng.random() < 0.02 * heavy + 0.03 * light:
                    self.add_effect("flak", p.x + rng.uniform(-1, 1), p.y + rng.uniform(-1, 1), 1.2)
                    if rng.random() < 0.18:
                        self._plane_hit(p, 60 if heavy else 30, None, aspect=90)
                        if p.player:
                            self.game.msg("Flak bursts all around - shrapnel rattles through the airframe!", "warn")
            for s in self.ships:
                if not s.alive or s.side == p.side or (s.cls == "ss" and s.depth > 0):
                    continue
                d = math.hypot(s.x - p.x, s.y - p.y)
                light, heavy = s.st["aa"]
                if d < 9 and p.alt < 2500 and rng.random() < 0.012 * light * (1 - d / 10):
                    self.add_effect("flak", p.x + rng.uniform(-0.6, 0.6), p.y + rng.uniform(-0.6, 0.6), 1.0)
                    if rng.random() < 0.22:
                        self._plane_hit(p, 45, None, aspect=90)

    # ------------------------------------------------------------ ships
    def _sail(self, s: Ship):
        rng = self.rng()
        if not s.player or self.station not in ("bridge", "captain"):
            self._ship_ai(s)
            s.order_hdg = self._clear_heading(s, s.order_hdg)
        # steer, change speed
        rate = {"pt": 6, "dd": 3.5, "de": 3.5, "ss": 3, "cl": 2.5, "ca": 2.2, "bb": 1.6, "cv": 1.6, "cve": 2,
                "ap": 1.5, "lst": 1.5}.get(s.cls, 2)
        dh = angdiff(s.hdg, s.order_hdg)
        s.hdg = (s.hdg + max(-rate, min(rate, dh))) % 360
        top = s.st["speed"] if not (s.cls == "ss" and s.depth > 0) else s.st["subspeed"]
        top *= max(0.3, 1 - s.flood / 120)
        from .weather import sea_state
        if s.depth == 0:
            top *= max(.35, 1 - sea_state(self.game) * (.1 if s.cls in ("pt", "de", "lst") else .045))
        # fuel: burnt roughly with the square of the speed; dry bunkers leave her creeping
        fuel = s.__dict__.get("fuel", 100.0)
        if s.cls not in ("ss",) or s.depth == 0:
            s.fuel = max(0.0, fuel - 0.000386 * (s.kn / 20.0) ** 2)
        if s.fuel <= 0:
            top = min(top, 5.0)
        want = min(s.order_kn, top)
        s.kn += max(-0.6, min(0.4, want - s.kn))
        dx, dy = s.dirv()
        v = s.kn * KNOT_TILES_S
        nx, ny = s.x + dx * v, s.y + dy * v
        if self.is_sea(nx, ny) and self.is_sea(nx + dx, ny + dy):
            s.x, s.y = nx, ny
        else:
            s.order_hdg = (s.hdg + 90) % 360       # land ahead: turn away
            s.kn *= 0.5
        if s.cls == "ss" and s.depth > 0:
            s.battery = max(0.0, s.battery - 0.004 * s.kn)
            if s.battery <= 0:
                s.depth = 0
        elif s.cls == "ss":
            s.battery = min(100.0, s.battery + 0.01)
        # damage: fires and flooding
        if s.fires:
            s.hp -= 0.4 * s.fires
            if rng.random() < 0.004:
                s.fires = max(0, s.fires - 1)
        if s.flood > 0:
            s.hp -= s.flood * 0.01
            s.flood = max(0.0, s.flood - 0.01)
        if s.hp <= 0 or s.flood >= 100:
            self._sink(s)
            return
        self._ship_guns(s)

    def shore_salvo(self, ship, m):
        """A salvo at the shore target of a bombardment mission.  (ok, what the spotters say)."""
        gun = ship.st["main"] or ship.st["sec"]
        if gun is None or self.t < ship.main_ready:
            return True, ("Reloading." if gun else "No guns.")
        sx, sy, name, sec = m["shore"]
        d = math.hypot(sx - ship.x, sy - ship.y)
        if d > gun[2]:
            return False, f"The shore target is out of range ({d / 10:.1f} km). Close the coast."
        ship.main_ready = self.t + gun[3]
        m["shots"] = m.get("shots", 0) + 1
        st = self.game.strategic
        c = st.at(*sec)
        if c is not None and c.control in c.units:
            st._attrit(c.units[c.control], gun[1] * gun[0] / 600.0, c.control)
            c.fort = max(0, c.fort - (1 if self.rng().random() < 0.1 else 0))
        self.add_effect("blast", sx, sy, 2)
        return True, f"A salvo roars off toward {name}. Spotters report the fall of shot."

    def _clear_heading(self, s, want):
        """The nearest heading to the one wanted that doesn't put her on the rocks (the navigator's job).
        Keeps to the same side of an island once it's picked one, so she doesn't dither."""
        def clear(h):
            r = math.radians(h)
            dx, dy = math.sin(r), -math.cos(r)
            return all(self.is_sea(s.x + dx * k, s.y + dy * k) for k in (1, 3, 6, 10))
        if clear(want):
            s.ai.pop("detour", None)
            return want
        side = s.ai.get("detour", 1)
        for off in (25, 50, 75, 100, 130, 160):
            for sg in (side, -side):
                if clear((want + sg * off) % 360):
                    s.ai["detour"] = sg
                    return (want + sg * off) % 360
        return want

    def _ship_ai(self, s: Ship):
        if s.ai.get("holding_for_replenishment"):
            s.order_kn = 0.
            return
        rng = self.rng()
        role = s.ai.get("role", "line")
        ldr = self.entity(-s.ai["leader"]) if s.ai.get("leader") else None
        if s.ai.get("leader") and (ldr is None or not ldr.alive):
            # the flagship's gone: the senior ship left takes the force on to the same rendezvous
            old = s.ai["leader"]
            group = [o for o in self.ships if o.alive and o.side == s.side and o.ai.get("leader") == old]
            new = max(group, key=lambda o: (o.st["hp"], -o.id))
            new.ai.pop("leader", None)
            new.ai.pop("offset", None)
            new.ai["wp"] = (ldr.ai.get("wp") if ldr is not None else None) or (new.x, new.y)
            for o in group:
                if o is not new:
                    o.ai["leader"] = new.id
            ldr = self.entity(-s.ai["leader"]) if s.ai.get("leader") else None
        enemies = [e for e in self.ships if e.alive and e.side != s.side and self._seen_by(s, e)]
        if role in ("line", "screen", "escort") and ldr is not None and ldr.alive:
            ox, oy = s.ai.get("offset", (0, 2))
            h = math.radians(ldr.hdg)
            rx = ox * math.cos(h) - oy * math.sin(h) * -1
            ry = ox * math.sin(h) + oy * math.cos(h)
            tx, ty = ldr.x + rx, ldr.y + ry
            d = math.hypot(tx - s.x, ty - s.y)
            s.order_hdg = bearing(s.x, s.y, tx, ty) if d > 0.7 else ldr.hdg
            s.order_kn = ldr.kn + (4 if d > 2 else 0)
        elif role in ("line", "screen", "escort", "strike") and s.ai.get("wp"):
            tx, ty = s.ai["wp"]
            s.order_hdg = bearing(s.x, s.y, tx, ty)
            s.order_kn = s.ai.get("kn", s.st["speed"] * 0.7)
        if role in ("screen", "escort", "strike") and enemies and s.cls in ("dd", "de", "pt", "cl"):
            e = min(enemies, key=lambda e: math.hypot(e.x - s.x, e.y - s.y))
            d = math.hypot(e.x - s.x, e.y - s.y)
            if e.cls == "ss":
                # sub hunting: run over where the sonar says he is, and drop a pattern
                s.order_hdg = bearing(s.x, s.y, e.x, e.y)
                s.order_kn = s.st["speed"] * 0.6
                if d < 1.0 and s.dc > 0 and s.ai.get("dc_t", -99) < self.t - 30:
                    self.depth_charges(s, e)
            elif d < 90 and s.torps and s.ai.get("torp_t", -99) < self.t - 120 and \
                    d < (s.st["torps"][1] * 0.7 if s.st["torps"] else 0):
                self.fire_torpedoes(s, e, spread=min(4, s.torps))
                s.ai["torp_t"] = self.t
            elif role == "strike":
                s.order_hdg = bearing(s.x, s.y, e.x, e.y)
                s.order_kn = s.st["speed"]
        if role == "sub":
            tgts = [e for e in self.ships if e.alive and e.side != s.side and e.cls in ("ap", "lst", "cv", "cve", "bb",
                                                                                      "ca", "cl")]
            esc = [e for e in self.ships if e.alive and e.side != s.side and e.cls in ("dd", "de")]
            if esc and min(math.hypot(e.x - s.x, e.y - s.y) for e in esc) < 6 and s.depth < 2:
                s.depth = 2                        # go deep, go quiet
                s.order_kn = 2
            elif tgts:
                t = min(tgts, key=lambda e: math.hypot(e.x - s.x, e.y - s.y))
                d = math.hypot(t.x - s.x, t.y - s.y)
                s.depth = 1 if d < 60 else 0
                s.order_hdg = bearing(s.x, s.y, t.x, t.y)
                s.order_kn = 6 if s.depth else 14
                if d < 22 and s.torps and s.ai.get("torp_t", -99) < self.t - 180:
                    self.fire_torpedoes(s, t, spread=min(3, s.torps))
                    s.ai["torp_t"] = self.t
        if s.player and role != "sub" and ldr is None:
            self._captain(s, enemies)
        if s.cls in ("cv", "cve") and s.air:
            self._carrier_ops(s, enemies)
        if role != "sub" and enemies and s.target is None:
            s.target = min(enemies, key=lambda e: math.hypot(e.x - s.x, e.y - s.y)).id

    def _captain(self, s, enemies):
        """Your own ship when you're not the one conning her: the captain fights her to her orders.
        Surface ships close to gun range and then run parallel; a carrier stands off at strike range
        and turns into the wind to fly; a convoy escort keeps her course; when it's over, home."""
        m = self.mission or {}
        k = m.get("kind")
        top = s.st["speed"]
        if k == "rtb":
            # making for the base; once there, she anchors
            px, py = m["port_pt"]
            d = math.hypot(px - s.x, py - s.y)
            if m.get("stage") in ("arrived", "port"):
                s.order_kn = 0.0
                return
            s.order_hdg = bearing(s.x, s.y, px, py)
            s.order_kn = top * (0.6 if d > 12 else 0.3)
            return
        if k == "cover" and m.get("stage") not in ("done", "failed"):
            cx, cy = m["cover_pt"]
            d = math.hypot(cx - s.x, cy - s.y)
            s.order_hdg = bearing(s.x, s.y, cx, cy) if d > 6 else (s.hdg + 4) % 360      # on station: circling
            s.order_kn = top * (0.7 if d > 6 else 0.45)
            return
        if k == "rescue" and m.get("stage") not in ("done", "failed"):
            rx, ry = m["rescue_pt"]
            d = math.hypot(rx - s.x, ry - s.y)
            s.order_hdg = bearing(s.x, s.y, rx, ry)
            s.order_kn = top if d > 8 else max(4.0, top * 0.2)
            return
        if m.get("stage") in ("done", "failed") or k is None:
            hx, hy = m.get("home", (s.x, s.y))
            if math.hypot(hx - s.x, hy - s.y) > 5:
                s.order_hdg = bearing(s.x, s.y, hx, hy)
            s.order_kn = top * 0.6
            return
        if k == "convoy":
            s.order_kn = min(top, 12)             # convoy speed: the slowest merchantman's
            return
        known = [e for e in (self.entity(-i) for i in m.get("enemies", [])) if e is not None and e.alive]
        if k == "bombard" and m.get("shore") and not enemies:
            tx, ty = m["shore"][0], m["shore"][1]
            d = math.hypot(tx - s.x, ty - s.y)
            rng_ = (s.st["main"][2] if s.st.get("main") else 60) * 0.7
            s.order_hdg = bearing(s.x, s.y, tx, ty) if d > rng_ else (bearing(s.x, s.y, tx, ty) + 90) % 360
            s.order_kn = top * (0.7 if d > rng_ else 0.4)
            if d <= rng_ / 0.7 and self.t >= s.main_ready:
                self.shore_salvo(s, m)            # the captain works the target over himself
            return
        if not known:
            s.order_kn = top * 0.5
            return
        # where the enemy is thought to be: exact once he's in contact, else the scouts' estimate
        tgt = min(known, key=lambda e: math.hypot(e.x - s.x, e.y - s.y))
        if -tgt.id in self.contacts or tgt in enemies:
            tx, ty = tgt.x, tgt.y
            m["est"] = (tx, ty)
        else:
            if "est" not in m:
                r = self.rng()
                m["est"] = (tgt.x + r.uniform(-25, 25), tgt.y + r.uniform(-25, 25))
            tx, ty = m["est"]
        d = math.hypot(tx - s.x, ty - s.y)
        brg = bearing(s.x, s.y, tx, ty)
        if s.cls in ("cv", "cve"):
            if d > 170:
                s.order_hdg, s.order_kn = brg, top * 0.8
            elif d < 100:
                s.order_hdg, s.order_kn = (brg + 180) % 360, top
            else:
                s.order_hdg, s.order_kn = (brg + 90) % 360, top * 0.6
            return
        if tgt.cls == "ss":
            # a submarine: run in over where the sonar says he is, and drop a pattern
            s.order_hdg = brg
            s.order_kn = top * (0.6 if d > 3 else 0.5)
            if d < 1.0 and s.dc > 0 and s.ai.get("dc_t", -99) < self.t - 30 and \
                    (-tgt.id in self.contacts or tgt in enemies):
                self.depth_charges(s, tgt)
                s.ai["dc_t"] = self.t
            return
        gun = (s.st["main"][2] if s.st.get("main") else 60) * 0.8
        if s.cls in ("dd", "de", "pt") and s.torps:
            gun = min(gun, (s.st["torps"][1] if s.st.get("torps") else 60) * 0.6)
        if d > gun:
            s.order_hdg, s.order_kn = brg, top
        else:
            # open the arcs: turn to bring every turret to bear
            s.order_hdg = (brg + (90 if angdiff(s.hdg, (brg + 90) % 360) < 90 else -90)) % 360
            s.order_kn = top * 0.8
        s.target = tgt.id if (-tgt.id in self.contacts or tgt in enemies) else s.target

    def _seen_by(self, viewer, e):
        d = math.hypot(e.x - viewer.x, e.y - viewer.y)
        g = self.game
        night = g.is_night()
        vis = (60 if isinstance(viewer, Plane) else 90) if isinstance(e, Plane) else 180
        if night:
            vis = min(vis, 35)
        from .weather import visibility, sea_state
        vis *= visibility(g)
        radar = viewer.st.get("radar") if isinstance(viewer, Ship) else \
            (1944.5 if AIRCRAFT[viewer.at_id].get("radar") else 0)
        if radar and g.year >= radar:
            vis = max(vis, 220 if isinstance(viewer, Ship) else 75)
        if isinstance(e, Ship) and e.cls == "ss":
            if e.depth == 2:
                return isinstance(viewer, Ship) and viewer.st["sonar"] and d < max(4, 12 - sea_state(g)) and \
                    self.rng().random() < .5
            if e.depth == 1:
                return d < 10 or (isinstance(viewer, Ship) and viewer.st["sonar"] and d < 14)
            vis *= 0.5
        return d < vis

    def _detect(self):
        """What your side can see."""
        side = self.game.player.side
        eyes = [x for x in self.planes if x.alive and x.side == side] + \
            [x for x in self.ships if x.alive and x.side == side]
        cont = set()
        for e in self.planes:
            if e.alive and e.side != side and any(self._seen_by(v, e) for v in eyes):
                cont.add(e.id)
        for s in self.ships:
            if s.alive and s.side != side and any(self._seen_by(v, s) for v in eyes):
                cont.add(-s.id)
        for g2 in self.ground:
            if not g2["dead"] and g2["side"] != side:
                cont.add(g2["id"])
        self.contacts = cont

    def _ship_guns(self, s: Ship):
        """Main battery at the chosen target; secondaries at whatever is close."""
        rng = self.rng()
        if s.cls == "ss" and s.depth > 0:
            return
        if s.player and self.station in ("main battery", "gunnery") and not s.ai.get("auto_fire"):
            pass
        tgt = self.entity(-s.target) if s.target else None
        if s.target and tgt is None:
            tgt = self.entity(s.target)
        if isinstance(tgt, Ship) and tgt.alive and self._seen_by(s, tgt):
            m = s.st["main"]
            if m and self.t >= s.main_ready and not (s.player and self.station in ("bridge", "captain", "main battery")
                                                     and not s.ai.get("auto_fire", True)):
                d = math.hypot(tgt.x - s.x, tgt.y - s.y)
                if d <= m[2]:
                    self.salvo(s, tgt, m)
        sec = s.st["sec"]
        if sec and self.t >= s.sec_ready:
            near = [e for e in self.ships if e.alive and e.side != s.side and self._seen_by(s, e)
                    and math.hypot(e.x - s.x, e.y - s.y) <= sec[2] * 0.6]
            if near:
                self.salvo(s, min(near, key=lambda e: math.hypot(e.x - s.x, e.y - s.y)), sec, secondary=True)

    def salvo(self, s, tgt, gun, secondary=False):
        """A salvo: shells in the air, landing in d/7 seconds."""
        rng = self.rng()
        cal, n, rngt, reload, pen, dmg = gun
        n = max(1, n - (s.turret_out if not secondary else 0))
        d = math.hypot(tgt.x - s.x, tgt.y - s.y)
        rkey = tgt.id
        acc = s.ranging.get(rkey, 0.0)
        s.ranging[rkey] = min(1.0, acc + 0.12)
        night = self.game.is_night()
        radar = s.st.get("radar") and self.game.year >= s.st["radar"]
        size = {"pt": 0.4, "dd": 0.6, "de": 0.6, "ss": 0.5, "cl": 0.9, "ca": 1.0, "bb": 1.3, "cv": 1.4, "cve": 1.1,
                "ap": 1.1, "lst": 0.9}.get(tgt.cls, 1.0)
        p_hit = (0.008 + 0.04 * acc) * size * (1 - d / (rngt * 1.1)) * (0.5 if night and not radar else 1.0) * \
            (1.3 if radar else 1.0)
        from .weather import sea_state, visibility
        p_hit *= max(.3, 1 - sea_state(self.game) * .1) * (1 if radar else visibility(self.game))
        for _ in range(n):
            hit = rng.random() < p_hit
            ox, oy = (0, 0) if hit else (rng.gauss(0, 1.5 + (1 - acc) * 3), rng.gauss(0, 1.5 + (1 - acc) * 3))
            self.shells.append(dict(x=tgt.x + ox, y=tgt.y + oy, eta=self.t + max(1, d / 7), dmg=dmg, pen=pen,
                                    side=s.side, src=s.id, target=tgt.id, hit=hit, plunge=d > rngt * 0.6,
                                    cal=cal))
        if secondary:
            s.sec_ready = self.t + reload
        else:
            s.main_ready = self.t + reload
        self.add_effect("muzzle", s.x, s.y, 1.0)

    def _shells(self):
        keep = []
        for sh in self.shells:
            if self.t < sh["eta"]:
                keep.append(sh)
                continue
            tgt = self.entity(-sh["target"]) if sh["target"] and self.entity(-sh["target"]) else None
            if sh["hit"] and isinstance(tgt, Ship) and tgt.alive:
                armour = tgt.st["deck"] if sh["plunge"] else tgt.st["belt"]
                if sh["pen"] >= armour:
                    self._ship_hit(tgt, sh["dmg"], sh["dmg"] * 0.2 if self.rng().random() < 0.3 else 0,
                                   f"a {sh['cal']}mm shell", fire=self.rng().random() < 0.25)
                else:
                    self._ship_hit(tgt, sh["dmg"] * 0.12, 0, f"a {sh['cal']}mm shell (it bounces off the armour)")
                self.add_effect("hit", tgt.x, tgt.y, 1.5)
            else:
                self.add_effect("splash", sh["x"], sh["y"], 1.5)
        self.shells = keep

    DMG_SCALE = {"shell": 0.3, "torpedo": 0.6, "bomb": 0.6, "depth charges": 1.0, "a kamikaze": 0.6}

    def _ship_hit(self, s, dmg, flood, what, fire=False, deck=False):
        rng = self.rng()
        # a ship is a big steel box full of compartments: it takes a lot of hits to sink one
        k = 0.3 if "shell" in what else 0.6 if ("torpedo" in what or "bomb" in what or "kamikaze" in what) else 1.0
        dmg *= k
        s.hp -= dmg
        if flood:
            s.flood = min(100.0, s.flood + flood / max(1, s.st["hp"] / 100))
        if fire:
            s.fires += 1
        if rng.random() < 0.08 and s.st["main"]:
            s.turret_out = min(s.st["main"][1] - 1, s.turret_out + 1)
        if s.cls in ("cv", "cve") and deck and s.air is not None and rng.random() < 0.5:
            s.air = [max(0, a - rng.randint(1, 4)) for a in s.air]   # aircraft burning on deck
        if s.player:
            self.game.msg(f"We're hit - {what}!" + (" Fire below decks!" if fire else "") +
                          (" We're taking water!" if flood else ""), "death")
            if self.hit_hook is not None:
                self.hit_hook(s, dmg, flood, what, fire, deck)
        elif -s.id in self.contacts:
            self.news.append(f"{s.name} is hit by {what}.")

    def _sink(self, s):
        s.sunk = True
        self.add_effect("explosion", s.x, s.y, 6)
        g = self.game
        if s.player:
            g.msg(f"{s.name} is going down. 'Abandon ship!'", "death")
            if g.__dict__.get("aboard"):
                return                        # it happens under your feet (aboard.py)
            self.raft = (s.x, s.y)
            self.over = "raft"
        else:
            g.msg(f"{s.name} ({CLASS_NAME.get(s.cls, 'ship')}) rolls over and sinks.",
                  "good" if s.side != g.player.side else "death")
            if s.side != g.player.side:
                g.command.merit += {"bb": 12, "cv": 14, "ca": 8, "cl": 6, "dd": 4, "ss": 4}.get(s.cls, 2)

    def fire_torpedoes(self, s, tgt, spread=3):
        rng = self.rng()
        if not s.torps or not s.st["torps"]:
            return "No torpedoes left."
        _, rng_t, kn = s.st["torps"]
        # aim ahead of the target where he'll be when the fish arrives
        d = math.hypot(tgt.x - s.x, tgt.y - s.y)
        t_run = d / (kn * KNOT_TILES_S)
        tdx, tdy = tgt.dirv()
        tv = tgt.kn * KNOT_TILES_S
        ax, ay = tgt.x + tdx * tv * t_run, tgt.y + tdy * tv * t_run
        base = bearing(s.x, s.y, ax, ay)
        n = min(spread, s.torps)
        for i in range(n):
            h = base + (i - (n - 1) / 2) * 3
            dud = rng.random() < (0.3 if s.nation == "usa" and self.game.year < 1943.6 else 0.05)
            self.torps.append(dict(x=s.x, y=s.y, hdg=h, kn=kn, left=rng_t, side=s.side, src=s.id, dmg=500, dud=dud))
        s.torps -= n
        return f"{n} torpedo{'es' if n > 1 else ''} away - running {int(t_run)} seconds."

    def _torpedoes(self):
        keep = []
        for tp in self.torps:
            h = math.radians(tp["hdg"])
            v = tp["kn"] * KNOT_TILES_S
            tp["x"] += math.sin(h) * v
            tp["y"] -= math.cos(h) * v
            tp["left"] -= v
            hit = None
            for s in self.ships:
                if not s.alive or s.side == tp["side"] or (s.cls == "ss" and s.depth > 0):
                    continue
                if any(math.hypot(cx - tp["x"], cy - tp["y"]) < 0.45 for cx, cy in s.cells()):
                    hit = s
                    break
            if hit is not None:
                if tp["dud"]:
                    if hit.player or -hit.id in self.contacts:
                        self.game.msg(f"A torpedo clangs against {hit.name}'s hull - a dud!", "info")
                else:
                    self.add_effect("explosion", tp["x"], tp["y"], 3)
                    self._ship_hit(hit, tp["dmg"], 60, "a torpedo")
                continue
            if tp["left"] > 0 and self.is_sea(tp["x"], tp["y"]):
                keep.append(tp)
        self.torps = keep

    def depth_charges(self, s, sub):
        rng = self.rng()
        if s.dc <= 0:
            return "No depth charges left."
        s.dc = max(0, s.dc - 10)
        s.ai["dc_t"] = self.t
        self.add_effect("dc", s.x, s.y, 3)
        d = math.hypot(sub.x - s.x, sub.y - s.y)
        p = (0.35 if sub.depth < 2 else 0.18) * max(0.0, 1 - d / 2.5)
        if rng.random() < p:
            self._ship_hit(sub, sub.st["hp"] * rng.uniform(0.3, 0.8), 40, "depth charges")
            return "The pattern straddles him - oil and bubbles on the surface!"
        return "The charges explode astern. Nothing comes up."

    def _carrier_ops(self, s, enemies):
        """A carrier's air group: a combat air patrol over the fleet, strikes at whatever's found."""
        from .weather import flight_factor, sea_state
        if flight_factor(self.game) < .25 or sea_state(self.game) > 4.5:
            return
        rng = self.rng()
        f, d, t = s.air
        mine = [p for p in self.planes if p.alive and p.carrier == s.id]
        cap = [p for p in mine if p.ai.get("role") == "cap"]
        yr = self.game.year
        types = CARRIER_AIR.get(s.nation, CARRIER_AIR["usa"])
        if len(cap) < 4 and f > 0 and s.ai.get("cap", True):
            at = _latest(s.nation, yr, types[0])
            if at:
                p = Plane(at, s.side, s.nation, s.x, s.y, s.hdg, 300, rng=rng)
                p.carrier, p.home = s.id, (s.x, s.y)
                p.ai = dict(role="cap", station=(s.x, s.y), alt=3000)
                self.planes.append(p)
                s.air[0] -= 1
        if s.side == self.game.player.side:
            # the scouts and the CAP report more than the ship herself can see
            enemies = enemies + [e for e in self.ships if e.alive and e.side != s.side and -e.id in self.contacts
                                 and e not in enemies]
        if enemies and s.ai.get("strike_t", -9999) < self.t - 1800 and \
                not (s.player and self.station in ("bridge", "captain")):
            tgt = max(enemies, key=lambda e: {"cv": 5, "cve": 4, "bb": 3, "ca": 2}.get(e.cls, 1))
            if math.hypot(tgt.x - s.x, tgt.y - s.y) < 400:
                self.launch_strike(s, tgt)

    def launch_strike(self, s, tgt, share=0.6):
        """Dive bombers and torpedo bombers, with fighters over them, off to find the enemy."""
        rng = self.rng()
        if s.air is None:
            return "This ship has no aircraft."
        from .weather import flight_factor, sea_state
        if flight_factor(self.game) < .25 or sea_state(self.game) > 4.5:
            return "Flying is suspended: the weather has closed the flight deck."
        f, d, t = s.air
        types = CARRIER_AIR.get(s.nation, CARRIER_AIR["usa"])
        yr = self.game.year
        # (a deck load: at most a dozen of each type go in one strike - the rest stay aboard)
        nf, nd, nt = min(12, int(f * 0.4)), min(12, int(d * share)), min(12, int(t * share))
        if nd + nt == 0:
            return "Nothing left on deck to send."
        s.air = [f - nf, d - nd, t - nt]
        s.ai["strike_t"] = self.t
        leader = None
        made = 0
        for count, ti, role in ((nd, 1, "dive"), (nt, 2, "torpedo"), (nf, 0, "escort")):
            at = _latest(s.nation, yr, types[ti])
            for i in range(min(count, 12)):
                p = Plane(at, s.side, s.nation, s.x + rng.uniform(-1, 1), s.y + rng.uniform(-1, 1), s.hdg,
                          400 + 100 * i, rng=rng)
                p.carrier, p.home = s.id, (s.x, s.y)
                p.ai = dict(role=role if role != "escort" else "escort", wp=(tgt.x, tgt.y), target=-tgt.id,
                            home_pt=(s.x, s.y), alt=3500 if role == "dive" else 1500)
                if role == "escort" and leader is not None:
                    p.ai["leader"] = leader.id
                if leader is None and role != "escort":
                    leader = p
                self.planes.append(p)
                made += 1
        return f"Strike launched: {nd} dive bombers, {nt} torpedo bombers, {nf} fighters - {made} aircraft."
