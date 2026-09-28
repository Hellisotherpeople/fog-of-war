"""Fire support that exists.

Every shell that falls and every aircraft that comes over is fired or flown by a unit that is
somewhere: a battery of guns at the artillery position on the war map, with its guns, its crews and
the rounds in its limbers; a battalion's mortar platoon, up behind the companies in the line; a
destroyer or a battleship offshore; a squadron at an airfield, with so many aircraft serviceable.

A call for fire goes to a battery that can reach and isn't already firing, and it has only the rounds
it has.  If the battery is on your map its guns (or its mortar teams) fire them, and you can watch - or
walk up and put a stop to it; if it's elsewhere you hear it, far off, from where it is, and the rounds
come in after their time of flight.  Batteries are resupplied from the depots, overrun when their ground
is taken, and fire at the war around you as well as at your calls.  Aircraft come from their airfield's
direction, are lost to flak, and need an hour on the ground between sorties.
"""
from __future__ import annotations

import math

from .constants import SIDES, other_side

# guns in a battery, tubes in a mortar platoon, launchers in a rocket battery
GUNS = {"uk": 8, "canada": 8, "australia": 8, "newzealand": 8, "india": 8}
MORTARS = {"ussr": 9, "japan": 4, "china": 4}
ROCKETS = {"ussr": 4, "germany": 6}

# range (km) by calibre, and sustained rounds a minute per gun
RANGE_KM = [("320mm", 1.2), ("132mm rocket", 8.5), ("150mm rocket", 6.9), ("14-inch", 30.0), ("5-inch", 16.0),
            ("120mm mortar", 5.7), ("3-inch mortar", 2.5), ("81mm", 3.0), ("82mm", 3.0), ("75mm", 10.5),
            ("76mm", 13.0), ("25-pdr", 12.2), ("100mm", 9.0), ("105mm", 11.0), ("122mm", 11.8),
            ("5.5-inch", 14.8), ("150mm", 13.3), ("152mm", 17.0), ("155mm", 14.6)]
RPM = [("rocket", 0.0), ("320mm", 0.5), ("14-inch", 1.5), ("5-inch", 15.0), ("120mm mortar", 8.0),
       ("mortar", 15.0), ("81mm", 15.0), ("82mm", 15.0), ("75mm", 6.0), ("76mm", 6.0), ("25-pdr", 5.0),
       ("100mm", 4.0), ("105mm", 3.0), ("122mm", 3.0), ("5.5-inch", 2.0), ("150mm", 2.0), ("152mm", 2.0),
       ("155mm", 2.0)]

# the piece each kind of battery serves (data/vehicles.py)
PIECE = {"us_105": "m2a1_how", "us_155": "m1_155", "uk_25pdr": "25pdr_gun", "uk_55": "55in_gun", "su_76": "zis3_div_gun",
         "su_122": "m30_gun", "su_152": "ml20_gun", "su_katyusha": "katyusha", "de_105": "lefh18_gun",
         "de_150": "sfh18_gun", "de_nebelwerfer": "nebelwerfer", "it_75": "it75_gun", "it_100": "it100_gun",
         "jp_75": "type38_gun", "jp_105": "type91_gun", "fr_75": "75mm_gun", "fr_155": "gpf155_gun",
         "pl_100": "wz14_gun", "cn_75": "type38_gun", "fi_122": "m30_gun", "hu_105": "lefh18_gun"}

SHIPS = {
    "omaha44": [("USS Texas (BB-35)", "us_bb"), ("USS Arkansas (BB-33)", "us_bb"), ("USS Carmick (DD-493)", "us_naval"),
                ("USS McCook (DD-496)", "us_naval"), ("USS Doyle (DD-494)", "us_naval"),
                ("USS Emmons (DD-457)", "us_naval"), ("USS Frankford (DD-497)", "us_naval")],
    "sicily43": [("USS Boise (CL-47)", "us_naval"), ("USS Shubrick (DD-639)", "us_naval"),
                 ("USS Jeffers (DD-621)", "us_naval")],
    "iwojima45": [("USS Tennessee (BB-43)", "us_bb"), ("USS Nevada (BB-36)", "us_bb"), ("USS Idaho (BB-42)", "us_bb"),
                  ("USS Henry A. Wiley (DM-29)", "us_naval"), ("USS Bryant (DD-665)", "us_naval")],
    "okinawa45": [("USS Colorado (BB-45)", "us_bb"), ("USS Maryland (BB-46)", "us_bb"),
                  ("USS Longshaw (DD-559)", "us_naval"), ("USS Callaghan (DD-792)", "us_naval")],
    "guadalcanal42": [("USS Monssen (DD-436)", "us_naval"), ("USS Aaron Ward (DD-483)", "us_naval")],
}


def _lookup(table, cal, default):
    for key, v in table:
        if key in cal:
            return v
    return default


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


class Battery:
    def __init__(self, bid, side, nation, btype, kind, sec, guns, name):
        self.id = bid
        self.side = side
        self.nation = nation
        self.btype = btype                # a BatteryType id (data/vehicles.py)
        self.kind = kind                  # gun / mortar / rocket / naval
        self.sec = tuple(sec)             # the sector it's in (for ships, the sea offshore)
        self.pos = None                   # where in that sector, once it's been put on a map
        self.guns = guns
        self.guns_max = guns
        per = {"gun": 80, "mortar": 60, "rocket": 32, "naval": 200}[kind]
        self.ammo = self.ammo_max = guns * per
        self.name = name
        self.busy_until = 0
        self.mission = None
        self.fired = 0
        self.lost = False
        self.vids: list = []              # its guns on the map, when it's on yours
        self.squad_id = None              # a mortar platoon on your map: the squad whose tubes they are
        self.next_shot = {}               # per gun: the turn it can fire again

    @property
    def bt(self):
        from .data.vehicles import BATTERIES
        return BATTERIES[self.btype]

    @property
    def range_km(self) -> float:
        return _lookup(RANGE_KM, self.bt.cal, 10.0)

    @property
    def interval(self) -> int:
        """Turns between rounds from one gun."""
        rpm = _lookup(RPM, self.bt.cal, 3.0)
        return 2 if rpm <= 0 else max(2, int(60 / rpm))

    def describe(self) -> str:
        bt = self.bt
        what = {"gun": f"{self.guns} x {bt.cal}", "mortar": f"{self.guns} x {bt.cal}",
                "rocket": f"{self.guns} launchers", "naval": bt.cal + " guns"}[self.kind]
        return f"{self.name} ({what})"


class Squadron:
    def __init__(self, sid, side, nation, atype, sec, planes, name):
        self.id = sid
        self.side = side
        self.nation = nation
        self.atype = atype                # an AircraftType id
        self.sec = tuple(sec)
        self.planes = planes
        self.planes_max = planes
        self.out = 0                      # in the air now
        self.ready_at = 0                 # back, refuelled and rearmed
        self.sorties = 0
        self.lost = 0
        self.name = name

    @property
    def at(self):
        from .data.vehicles import AIRCRAFT
        return AIRCRAFT[self.atype]

    def ready(self, turn) -> int:
        return 0 if turn < self.ready_at else max(0, self.planes - self.out)


class Fires:
    def __init__(self, game):
        self.batteries: list[Battery] = []
        self.squadrons: list[Squadron] = []
        self._next = 1
        self._seen = set()                # (sector, kind, side) installations already turned into units
        self.populate(game)

    def _id(self) -> int:
        self._next += 1
        return self._next

    # ================================================================ who there is
    def populate(self, game):
        """Batteries at the artillery positions, a mortar platoon with each battalion in the line, warships off
        a landing beach, squadrons at the airfields.  Called at the start and as the war map grows."""
        st = game.strategic
        if st is None:
            return
        from .data.vehicles import AIRCRAFT, BATTERIES
        from .support import available
        rng = game.rng
        for s in st.sectors():
            if not s.playable:
                continue
            for kind, side, ok in s.installations:
                key = ((s.x, s.y), kind, side)
                if not ok or key in self._seen or kind not in ("artillery", "airfield"):
                    continue
                self._seen.add(key)
                nat = game.side_nation(side)
                if kind == "artillery":
                    types = [b for b in available(BATTERIES, nat, game.year) if not b.naval and "mortar" not in b.cal
                             and "mortar" not in b.name and b.freq > 0]
                    if not types:
                        continue
                    lvl = game.theatre["arty"].get(side, 0.5)
                    for _ in range(1 + int(lvl * 2.5 + rng.random())):
                        bt = rng.choices(types, [b.freq for b in types])[0]
                        self._add_battery(game, side, nat, bt, (s.x, s.y))
                else:
                    self._add_squadrons(game, side, nat, (s.x, s.y), AIRCRAFT)
            # the battalions in the line each have their mortars
            for side in SIDES:
                key = ((s.x, s.y), "mortar", side)
                if key in self._seen or not s.units[side].get("inf"):
                    continue
                # our battalions in the line - and anyone's fighting on your own ground
                if s is not game.sector and (s.control != side or not st.is_front(s, side)):
                    continue
                self._seen.add(key)
                nat = game.side_nation(side)
                types = [b for b in available(BATTERIES, nat, game.year) if ("mortar" in b.cal or "mortar" in b.name)
                         and "120" not in b.cal and b.freq > 0]
                if types:
                    self._add_battery(game, side, nat, rng.choice(types), (s.x, s.y))
        # ships off a landing beach (the attacker's), and air from the rear when there's no airfield near
        for side in SIDES:
            key = ("navy", side)
            if key not in self._seen and "landing" in game.theatre.get("special", ()) and side == game.attacker:
                self._seen.add(key)
                sea = [c for c in st.sectors() if c.biome == "sea"]
                spot = min(sea, key=lambda c: abs(c.x - game.sector.x) + abs(c.y - game.sector.y)) if sea else game.sector
                ships = SHIPS.get(game.theatre_id) or [("a destroyer offshore", "us_naval")]
                for nm, bid in ships:
                    if bid in BATTERIES:
                        b = Battery(self._id(), side, game.side_nation(side), bid, "naval", (spot.x, spot.y),
                                    10 if bid == "us_bb" else 5, nm)
                        self.batteries.append(b)
            key = ("rear_air", side)
            if key not in self._seen:
                self._seen.add(key)
                lvl = game.theatre["air"].get(side, 0.5)
                have = sum(1 for q in self.squadrons if q.side == side)
                want = int(1 + 3 * lvl)
                if have < want and lvl > 0.1:
                    back = self._rear_point(game, side)
                    for _ in range(want - have):
                        self._add_squadrons(game, side, game.side_nation(side), back, AIRCRAFT, n=1)

    def _rear_point(self, game, side):
        """A sector well behind a side's lines (where its airfields are, off the edge of what's mapped)."""
        from .strategic import DIRS, OPP
        st = game.strategic
        e = st.att_from if side == st.attacker else OPP[st.att_from]
        dx, dy = DIRS[e]
        s = game.sector
        return (s.x + dx * 12, s.y + dy * 12)

    def _add_battery(self, game, side, nat, bt, sec):
        rng = game.rng
        mortar = "mortar" in bt.cal or "mortar" in bt.name
        kind = "rocket" if bt.rocket else "mortar" if mortar else "gun"
        guns = (MORTARS.get(nat, 6) if mortar else ROCKETS.get(nat, 4) if bt.rocket else GUNS.get(nat, 4))
        if bt.id == "jp_320":
            guns = 2
        b = Battery(self._id(), side, nat, bt.id, kind, sec, guns, self._battery_name(rng, nat, kind))
        self.batteries.append(b)
        return b

    def _battery_name(self, rng, nat, kind) -> str:
        n = rng.randint(1, 3)
        reg = rng.choice([12, 18, 26, 42, 57, 81, 106, 115, 187, 230, 338, 406, 502, 953])
        if kind == "mortar":
            return {"usa": f"81mm mortar platoon, {'HMD'[n - 1]} Company, {_ordinal(reg % 400 + 8)} Infantry",
                    "uk": f"mortar platoon, {_ordinal(n)} Battalion", "germany": f"Granatwerferzug, {n + 3}. Kompanie",
                    "ussr": f"mortar company, {_ordinal(n)} rifle battalion, {reg}th Rifle Regiment",
                    "japan": f"mortar platoon, {_ordinal(n)} Battalion", "italy": f"plotone mortai, {_ordinal(n)} battaglione",
                    }.get(nat, f"mortar platoon, {_ordinal(n)} Battalion")
        if kind == "rocket":
            return {"ussr": f"{_ordinal(reg)} Guards Mortar Battalion", "germany": f"{n}./Werfer-Regiment {reg % 90 + 51}",
                    }.get(nat, f"{_ordinal(n)} rocket battery")
        return {"usa": f"{'ABC'[n - 1]} Battery, {_ordinal(reg)} Field Artillery Battalion",
                "uk": f"{reg % 500 + 1} Battery, {_ordinal(reg % 150 + 1)} Field Regiment RA",
                "canada": f"{reg % 100 + 1} Battery RCA", "germany": f"{n}./Artillerie-Regiment {reg % 300 + 1}",
                "ussr": f"{_ordinal(n)} battery, {reg}th Artillery Regiment",
                "japan": f"{_ordinal(n)} Battery, {_ordinal(reg % 60 + 1)} Field Artillery Regiment",
                "italy": f"{n}a batteria, {reg % 150 + 1}o reggimento artiglieria",
                "france": f"{n}e batterie, {reg % 120 + 1}e RA", "poland": f"{n}. bateria, {reg % 30 + 1}. pal",
                "finland": f"{n}. patteri, KTR {reg % 20 + 1}"}.get(nat, f"{_ordinal(n)} Battery")

    NAVAL_AIR = {"f4u", "sbd", "f4f", "f6f", "tbf", "sb2c", "swordfish", "zero", "d3a", "b5n"}

    def _add_squadrons(self, game, side, nat, sec, AIRCRAFT, n=None):
        """Squadrons at an airfield: the aircraft its air force flew there and then (carrier types only in the
        Pacific, where the Marines and the Navy flew them from land too)."""
        from .data.roles import PACIFIC_THEATRES
        from .support import available
        rng = game.rng
        pacific = game.theatre_id in PACIFIC_THEATRES
        pool = [a for a in available(AIRCRAFT, nat, game.year)
                if a.role in ("fighter", "fighterbomber", "attacker", "divebomber", "bomber", "nightbomber")
                and (pacific or a.id not in self.NAVAL_AIR)]
        if not pool:
            return
        for _ in range(n or rng.randint(1, 2)):
            at = rng.choices(pool, [a.freq for a in pool])[0]
            planes = {"usa": 16, "uk": 12, "germany": 12, "ussr": 10, "japan": 9, "italy": 9}.get(nat, 10)
            num = rng.choice([18, 22, 36, 48, 56, 174, 181, 245, 366, 391, 404, 609])
            bomb = at.role in ("bomber", "nightbomber")
            us = ("Bombardment" if bomb else "Fighter-Bomber" if at.role == "divebomber" else "Fighter")
            if at.id in self.NAVAL_AIR and nat == "usa":
                name = f"VM{'SB' if at.role == 'divebomber' else 'TB' if at.role == 'torpedo' else 'F'}-{num % 500} ({at.name})"
            else:
                name = {"usa": f"{_ordinal(num)} {us} Squadron ({at.name})", "uk": f"No. {num} Squadron RAF ({at.name})",
                        "germany": f"{rng.randint(1, 9)}./{'StG' if at.role == 'divebomber' else 'KG' if bomb else 'SG' if at.role != 'fighter' else 'JG'} "
                                   f"{rng.randint(1, 77)} ({at.name})",
                        "ussr": f"{_ordinal(num)} {'Bomber' if bomb else 'Ground Attack' if at.role == 'attacker' else 'Fighter'} "
                                f"Aviation Regiment ({at.name})",
                        "japan": f"{_ordinal(num % 100)} Sentai ({at.name})",
                        "italy": f"{num % 400}a Squadriglia ({at.name})"}.get(nat, f"{_ordinal(num)} Squadron ({at.name})")
            self.squadrons.append(Squadron(self._id(), side, nat, at.id, sec, planes, name))

    # ================================================================ distances
    def _global(self, game, sec, pos):
        mw, mh = game.map_w, game.map_h
        x, y = pos if pos is not None else (mw // 2, mh // 2)
        return sec[0] * mw + x, sec[1] * mh + y

    def km(self, game, b, sec, pos) -> float:
        bx, by = self._global(game, b.sec, b.pos)
        tx, ty = self._global(game, sec, pos)
        return math.hypot(bx - tx, by - ty) * 0.002

    def bearing_point(self, game, sec, pos):
        """For something off your map: the point on its edge in its direction (for its sound, its aircraft)."""
        m = game.map
        here = (game.sector.x, game.sector.y)
        gx, gy = self._global(game, sec, pos)
        cx, cy = self._global(game, here, (m.w // 2, m.h // 2))
        ang = math.atan2(gy - cy, gx - cx)
        # walk from the centre toward it until the edge
        r = max(m.w, m.h)
        x = m.w / 2 + math.cos(ang) * r
        y = m.h / 2 + math.sin(ang) * r
        k = min((m.w / 2 - 1) / max(1e-6, abs(x - m.w / 2)), (m.h / 2 - 1) / max(1e-6, abs(y - m.h / 2)))
        return int(m.w / 2 + (x - m.w / 2) * k), int(m.h / 2 + (y - m.h / 2) * k), math.hypot(gx - cx, gy - cy)

    def here(self, game, b) -> bool:
        return game.sector is not None and b.sec == (game.sector.x, game.sector.y) and b.kind != "naval"

    # ================================================================ calling for fire
    def reach_km(self, game, b) -> float:
        """How far it can fire: its guns' range - or, for a mortar platoon that's on your map as men with
        tubes, the range of those tubes."""
        if b.kind == "mortar" and b.squad_id is not None and self.here(game, b):
            sq = next((s for s in game.squads if s.id == b.squad_id), None)
            rs = [a.weapon.t.rng for a in (sq.members if sq else ()) if a.active and a.weapon is not None
                  and a.weapon.t.cat == "mortar"]
            if rs:
                return max(rs) * 0.002
        return b.range_km

    def ready(self, game, side, sec=None, pos=None, kinds=None) -> list:
        """Batteries of a side that could fire on that spot now: in range, guns manned, rounds left, not busy."""
        sec = sec or (game.sector.x, game.sector.y)
        out = []
        for b in self.batteries:
            if b.side != side or b.lost or b.guns <= 0 or b.ammo <= 0 or b.mission is not None:
                continue
            if kinds and b.kind not in kinds:
                continue
            if self.km(game, b, sec, pos) > self.reach_km(game, b):
                continue
            out.append(b)
        return out

    def in_range(self, game, side, sec=None, pos=None) -> list:
        sec = sec or (game.sector.x, game.sector.y)
        return [b for b in self.batteries if b.side == side and not b.lost and b.guns > 0
                and self.km(game, b, sec, pos) <= self.reach_km(game, b)]

    def call(self, game, side, x, y, caller=None, rounds=None, delay=None, silent=False, kinds=None,
             prefer=None, smoke=False):
        """A fire mission on (x, y) of your map.  Returns the battery that takes it, or None."""
        here = (game.sector.x, game.sector.y)
        cands = self.ready(game, side, here, (x, y), kinds)
        if not cands:
            if caller is not None and getattr(caller, "is_player", False) and not silent:
                allb = self.in_range(game, side, here, (x, y))
                why = ("every battery in range is already firing" if any(b.mission for b in allb) else
                       "the guns in range are out of ammunition" if allb else "no guns within range of you")
                game.msg(f"Radio: 'Negative, {why}. Wait, out.'", "radio")
            return None
        # the caller's own mortars for anything close to him; the heavier guns for the rest; ships for a landing
        def score(b):
            d = self.km(game, b, here, (x, y))
            s = d / b.range_km
            if prefer and b.kind in prefer:
                s -= 1.0
            if b.kind == "mortar" and caller is not None and getattr(caller, "squad", None) is not None:
                s -= 0.3
            return s
        if smoke:
            cands = [b for b in cands if b.kind in ("gun", "mortar")] or cands     # (rockets and ships fire HE)
        b = min(cands, key=score)
        self.start(game, b, ("map", here, (x, y)), caller, rounds, delay, silent)
        if smoke:
            b.mission["smoke"] = True
        return b

    def start(self, game, b, target, caller=None, rounds=None, delay=None, silent=False):
        rng = game.rng
        bt = b.bt
        per = {"gun": 3, "mortar": 4, "rocket": 16, "naval": 4}[b.kind]
        n = rounds or b.guns * per
        grade = getattr(caller, "rank", 0) if caller is not None else 0
        if caller is not None and grade >= 11:
            n = int(n * (1 + 0.15 * (grade - 10)))          # a senior caller gets the battalion
        n = max(1, min(n, b.ammo))
        skill = getattr(caller, "skill", 5) if caller is not None else 5
        # a systematic error: map reading, wind, worn barrels - and now and then a wrong grid altogether
        bias_d = abs(rng.gauss(0, 3 + (8 - skill)))
        if rng.random() < 0.06:
            bias_d += rng.uniform(15, 35)
        ba = rng.uniform(0, math.tau)
        dist_km = self.km(game, b, target[1], target[2])
        flight = int(4 + dist_km * (6 if b.kind == "mortar" else 3))   # seconds in the air
        proc = bt.delay + rng.randint(-10, 25) if delay is None else delay
        if grade >= 11:
            proc = int(proc * max(0.5, 1 - 0.06 * (grade - 10)))
        b.mission = dict(target=target, rounds=n, caller=getattr(caller, "id", None),
                         player=bool(caller is not None and getattr(caller, "is_player", False)),
                         bias=[math.cos(ba) * bias_d, math.sin(ba) * bias_d], spread=bt.spread + max(0, 7 - skill) * 0.5,
                         start=game.turn + max(0, proc), flight=flight, splashed=False, fired=0,
                         observer_skill=skill)
        b.next_shot = {}
        if self.player_battery(game) is b:
            m = b.mission
            guns = max(1, len(self._guns_now(game, b)) + 1)
            share = max(1, n // guns)
            m["rounds"] = max(0, n - share)
            m["player_left"] = m["player_total"] = share
            m["deadline"] = m["start"] + share * 90 + 240
            m["data"] = self.firing_data(game, b, target)
        if b.mission["player"] and not silent:
            km = dist_km
            where = "offshore" if b.kind == "naval" else f"{km:.1f} km {self._compass(game, b)}"
            game.msg(f"Radio: 'Fire mission. {b.describe()}, {where}. {n} rounds. Wait.'", "radio")
        return b

    def _compass(self, game, b) -> str:
        from .senses import direction_word
        here = (game.sector.x, game.sector.y)
        m = game.map
        bx, by = self._global(game, b.sec, b.pos)
        cx, cy = self._global(game, here, (m.w // 2, m.h // 2))
        return direction_word(bx - cx, by - cy)

    def barrage(self, game, side, x, y, radius, rounds, delay=0, naval=False, kinds=None, error=0.0,
                tag=None) -> list:
        """A planned bombardment of a spot on your map: every battery that can reach it and is free joins in,
        as far as its rounds go.  `error`: how far off (tiles) they think the target is.  Returns the
        batteries that took part (none: nobody could)."""
        here = (game.sector.x, game.sector.y)
        kinds = kinds or (("naval",) if naval else ("gun", "rocket", "naval", "mortar"))
        cands = self.ready(game, side, here, (x, y), kinds)
        if not cands:
            return []
        took = []
        rng = game.rng
        rng.shuffle(cands)
        left = rounds
        for b in cands:
            if left <= 0:
                break
            n = min(left, b.guns * (4 if b.kind != "rocket" else 16), b.ammo)
            px, py = x + rng.randint(-radius, radius), y + rng.randint(-radius, radius)
            self.start(game, b, ("map", here, (px, py)), None, n, delay + rng.randint(0, 20), True)
            b.mission["spread"] += radius / 3
            b.mission["bias"] = [rng.gauss(0, error), rng.gauss(0, error)] if error else [0.0, 0.0]
            if tag:
                b.mission[tag] = True
            left -= n
            took.append(b)
        return took

    # ================================================================ firing
    def update(self, game):
        """Every turn: the batteries with a mission fire it, gun by gun."""
        if game.map is None or game.__dict__.get("domain", "land") != "land":
            return
        for b in self.batteries:
            m = b.mission
            if m is None:
                continue
            if b.lost or b.guns <= 0 or b.ammo <= 0:
                self._end(game, b, "out" if b.ammo <= 0 else "gone")
                continue
            if game.turn < m["start"]:
                continue
            if m.get("player_left") and not m.get("announced"):
                m["announced"] = True
                d = m["data"]
                game.msg(f"{'Platoon sergeant' if b.kind == 'mortar' else 'Section chief'}: 'FIRE MISSION! "
                         f"{d['shell']}, charge {d['charge']}, azimuth {d['az']:04d}, elevation {d['qe']:04d}, "
                         f"{m['player_left']} round{'s' if m['player_left'] > 1 else ''}!'", "shout")
                game.update_orders(force=True)
            guns = self._guns_now(game, b)
            if not guns:
                if self.here(game, b):
                    self._end(game, b, "gone")
                continue
            volley = 0
            for gi, gun in enumerate(guns):
                if m["rounds"] <= 0 or b.ammo <= 0:
                    break
                if b.next_shot.get(gi, 0) > game.turn:
                    continue
                if b.kind == "rocket":
                    b.next_shot[gi] = game.turn + 1
                else:
                    b.next_shot[gi] = game.turn + b.interval + game.rng.randint(0, 3)
                if self._fire_round(game, b, gun, m):
                    volley += 1
            if volley and not self.here(game, b):
                self._distant_report(game, b, volley)
            if not volley and b.kind == "mortar" and self.here(game, b) and m["rounds"] > 0 and \
                    game.turn > m["start"] + 120 and not m.get("player_left"):
                self._end(game, b, "done")              # nobody could reach it: the mission's dropped
            if m.get("player_left", 0) > 0 and (m["rounds"] <= 0 or b.ammo <= 0) and game.turn > m.get("deadline", 0):
                self._chief_fires(game, b, m)
            if (m["rounds"] <= 0 or b.ammo <= 0) and m.get("player_left", 0) <= 0:
                self._end(game, b, "done" if m["rounds"] <= 0 else "out")

    def _guns_now(self, game, b) -> list:
        """Its guns, as things that can fire: the vehicles on your map, the mortarmen of its squad, or (away
        from you) just its number."""
        if self.here(game, b):
            if b.kind == "mortar" and b.squad_id is not None:
                sq = next((s for s in game.squads if s.id == b.squad_id), None)
                if sq is not None:
                    men = [a for a in sq.members if a.active and not a.downed and a.weapon is not None
                           and a.weapon.t.cat == "mortar" and not a.is_player]
                    return men
            if b.vids:
                vs = [v for v in game.vehicles if v.id in b.vids and not v.dead and not v.abandoned and v.crew > 0
                      and v.gun_ok]
                from .crew import ai_manned
                return [v for v in vs if ai_manned(v, "gunner")]
        return list(range(b.guns))

    def _concrete(self, game, b, m):
        """A mission on another sector whose ground has become your map (you've walked into it): the rounds
        now fall on a spot of it - where the battery's side last knew the enemy to be, or the middle."""
        kind, sec, pos = m["target"]
        if pos is None and sec == (game.sector.x, game.sector.y):
            brain = game.brains.get(b.side)
            cs = brain.clusters(radius=6, min_size=1, max_age=300) if brain is not None else []
            if cs:
                pos = (cs[0][1], cs[0][2])
            else:
                lc = brain.live_contacts(300, False) if brain is not None else []
                pos = (lc[0].x, lc[0].y) if lc else (game.map.w // 2, game.map.h // 2)
            m["target"] = ("map", sec, pos)
        return m["target"]

    def _fire_round(self, game, b, gun, m) -> bool:
        """One round from one gun (a vehicle, a mortarman, or a number)."""
        from .combat import fire_mortar
        rng = game.rng
        bt = b.bt
        kind, sec, pos = self._concrete(game, b, m)
        on_map = sec == (game.sector.x, game.sector.y)
        if getattr(gun, "vt", None) is not None:
            # a real gun: it fires where the fire direction centre says
            from .gamemap import octant
            if on_map:
                gun.turret = octant(pos[0] - gun.x, pos[1] - gun.y)
                if gun.vt.static:
                    gun.facing = gun.turret
            game.effect_flash(gun.x, gun.y)
            game.emit_sound(gun.x, gun.y, 112 if b.kind != "mortar" else 80, "cannon",
                            f"the crash of a {bt.cal} gun firing", b.side, gun)
            gun.fired_turn = game.turn
        elif getattr(gun, "weapon", None) is not None:
            # a mortarman of the platoon, with his own tube and the bombs he's carrying
            if not on_map:
                return False
            ix, iy = self._aim(game, m, pos)
            if gun.ammo_for(gun.weapon) is not None:
                c = fire_mortar(game, gun, gun.weapon, ix, iy)       # a bomb from his own bag
            else:
                c = self._drop_bomb(game, b, gun, gun.weapon, ix, iy)  # one handed up from the carts
            if not c:
                return False                          # out of his range: the mission's too far for the platoon
            gun.moves -= c
            gun.ai["fire_mission"] = game.turn
            m["rounds"] -= 1
            m["fired"] += 1
            b.fired += 1
            return True
        m["rounds"] -= 1
        m["fired"] += 1
        b.fired += 1
        b.ammo -= 1
        if on_map:
            ix, iy = self._aim(game, m, pos)
            src = f"a {bt.cal} shell" if not bt.rocket else f"a {bt.cal}"
            game.schedule_shell(ix, iy, m["flight"], bt.power, bt.radius, bt.frags, 24, None, src,
                                whistle=True, sound=bt.sound, side=b.side, smoke=bool(m.get("smoke")))
            if m["player"] and not m["splashed"]:
                m["splashed"] = True
                game.msg("Radio: 'Shot, over.'", "radio")
                m["splash_at"] = game.turn + max(0, m["flight"] - 5)
            if m.get("cb") and not m.get("cb_warned"):
                m["cb_warned"] = True                             # the first rounds landing among the guns
                game.__dict__.setdefault("_cb_warn", []).append((game.turn + m["flight"], m["cb_near"],
                                                                  m.get("cb_mortar", False)))
        else:
            self._shell_sector(game, b, sec, 1)
        return True

    def _drop_bomb(self, game, b, shooter, weapon, tx, ty) -> int:
        """A bomb handed up by the ammunition bearer from the platoon's carts (not from the man's own bag),
        dropped down his tube: as combat.fire_mortar, from the platoon's stock.  0 if it's out of his range."""
        t = weapon.t
        dist = math.hypot(tx - shooter.x, ty - shooter.y)
        if dist < t.min_rng or dist > t.rng or b.ammo <= 0:
            return 0
        b.ammo -= 1
        game.emit_sound(shooter.x, shooter.y, t.loud, "mortar", t.sound, shooter.side, shooter)
        sig = dist * 0.06 + (8 - shooter.skill) * 0.3 + shooter.suppression / 40
        ix = int(round(tx + game.rng.gauss(0, sig)))
        iy = int(round(ty + game.rng.gauss(0, sig)))
        game.schedule_shell(ix, iy, 3 + int(dist / 15), t.blast, t.blast_r, t.frags, t.frag_dmg, shooter,
                            f"a {t.name} bomb", whistle=True)
        shooter.fired_turn = game.turn
        if shooter.stance != 2:
            shooter.stance = 2
        return t.shot_cost

    def _aim(self, game, m, pos):
        """Where this round lands: the error of the whole mission (it walks in, if someone is watching), and the
        round's own scatter."""
        rng = game.rng
        bias = m["bias"]
        if m["fired"] and m["fired"] % 4 == 0:
            bias[0] *= 0.55
            bias[1] *= 0.55                           # corrections: 'right fifty, drop one hundred'
        mm = game.map
        ix = int(round(pos[0] + bias[0] + rng.gauss(0, m["spread"])))
        iy = int(round(pos[1] + bias[1] + rng.gauss(0, m["spread"])))
        return max(0, min(mm.w - 1, ix)), max(0, min(mm.h - 1, iy))

    def _distant_report(self, game, b, n):
        """Guns firing somewhere off your map: you hear them, from their direction, a moment before anything else
        (once a half-minute a battery: the log isn't a drum)."""
        if game.map is None or game.turn - b.__dict__.get("_heard", -99) < 30:
            return
        b._heard = game.turn
        x, y, d = self.bearing_point(game, b.sec, b.pos)
        loud = 118 - 20 * math.log10(max(1.0, d)) + 6 * math.log10(max(1, n))
        if loud > 30:
            what = {"mortar": f"{b.bt.cal.replace(' mortar', '')} mortars", "rocket": "rocket launchers",
                    "naval": "naval guns"}.get(
                b.kind, f"a {b.bt.cal} battery")
            game.emit_sound(x, y, loud, "cannon", f"{what} firing", b.side, None)

    def _shell_sector(self, game, b, sec, n):
        """Rounds falling somewhere that isn't your map: counted on the mission; the war map feels them when it's
        fired (see _end)."""
        m = b.mission
        if m is not None:
            m["weight"] = m.get("weight", 0.0) + n * b.bt.power / 100.0

    def _sector_effect(self, game, b, m):
        """What a mission on another sector did to the enemy there - done for real on the war map, and so what
        an observer can honestly report."""
        from .strategic import UNIT_POWER
        kind, sec, pos = m["target"]
        st = game.strategic
        s = st.at(*sec) if st else None
        w = m.get("weight", 0.0)
        if s is None or w <= 0:
            return None
        enemy = other_side(b.side)
        before = dict(s.units[enemy])
        if not before:
            return "nothing there"
        st._attrit(s.units[enemy], min(4.0, w * 0.035 * game.rng.uniform(0.4, 1.4)), enemy)
        lost = {k: before[k] - s.units[enemy].get(k, 0) for k in before if before[k] > s.units[enemy].get(k, 0)}
        s.__dict__.setdefault("shelled_last", {})[b.side] = st.ticks
        if not lost:
            return "no observed effect"
        words = {"inf": ("an infantry section broken up", "infantry sections broken up"),
                 "mg": ("a machine-gun team knocked out", "machine-gun teams knocked out"),
                 "mortar": ("a mortar knocked out", "mortars knocked out"), "at": ("an anti-tank team hit", "anti-tank teams hit"),
                 "atgun": ("an anti-tank gun destroyed", "anti-tank guns destroyed"), "tank": ("a tank knocked out", "tanks knocked out"),
                 "td": ("a tank destroyer knocked out", "tank destroyers knocked out"), "ht": ("a half-track burning", "half-tracks burning"),
                 "hq": ("a command post hit", "command posts hit")}
        bits = []
        for k, n in lost.items():
            one, many = words.get(k, (f"a {k} hit", f"{k}s hit"))
            bits.append(one if n == 1 else f"{n} {many}")
        return ", ".join(bits)

    def _chief_fires(self, game, b, m):
        """You didn't fire your gun's rounds: the section chief (or the platoon sergeant) did, and he won't forget."""
        left = m.get("player_left", 0)
        m["player_left"] = 0
        b.ammo = max(0, b.ammo - left)
        b.fired += left
        m["fired"] += left
        kind, sec, pos = m["target"]
        if sec != (game.sector.x, game.sector.y):
            self._shell_sector(game, b, sec, left)
        game.msg("Your section chief shoves you off the sights and fires the rounds himself. 'When I say fire, "
                 "you FIRE!'" if b.kind != "mortar" else "The platoon sergeant fires your tube's bombs himself. "
                 "'Asleep, were you?'", "warn")
        duty = getattr(game, "duty", None)
        if duty is not None:
            duty.rep -= 3
            duty.strikes += 1

    def _end(self, game, b, why):
        m = b.mission
        b.mission = None
        b.next_shot = {}
        if m is None:
            return
        b.busy_until = game.turn
        report = None
        if m.get("cb_target") is not None:
            t = next((o for o in self.batteries if o.id == m["cb_target"]), None)
            if t is not None and not t.lost and not self.here(game, t):
                # each dozen rounds a fair chance of a gun wrecked or its crew gone
                for _ in range(max(1, m["fired"] // 12)):
                    if t.guns > 0 and game.rng.random() < 0.35:
                        t.guns -= 1
                if t.guns <= 0:
                    t.lost = True
                    game.strategic.news.append(f"{t.name} was silenced by counter-battery fire.")
        elif m["target"][0] == "sector":
            report = self._sector_effect(game, b, m)
        if m.get("player_total"):
            game.msg(f"{'Platoon sergeant' if b.kind == 'mortar' else 'Section chief'}: 'Cease fire - end of mission.'"
                     + (f" The observer reports: {report}." if report else ""), "shout")
            if m.get("player_fired", 0) >= m["player_total"]:
                duty = getattr(game, "duty", None)
                if duty is not None:
                    duty.rep = min(100.0, duty.rep + 1)
                game.command.merit += 0.4
            game.update_orders(force=True)
        if m.get("player"):
            game.msg({"done": "Radio: 'Rounds complete, over.'",
                      "out": f"Radio: '{b.name}: out of ammunition. That's all we had.'",
                      "gone": f"Radio: 'No answer from {b.name}.'"}[why], "radio")
        # counter-battery: guns that fire give themselves away to the enemy's sound-rangers and flash-spotters.
        # Mortars are harder to find - a short, high flight, from behind cover - until the counter-mortar
        # organisations and radars of 1944; then their fire is answered by guns and mortars both
        if self.here(game, b) and b.pos is not None:
            enemy = other_side(b.side)
            if b.kind in ("gun", "rocket") and game.rng.random() < 0.3:
                x, y = b.pos
                game.__dict__.setdefault("_counter_battery", []).append(
                    (game.turn + game.rng.randint(120, 480), enemy, x, y, False))
            elif b.kind == "mortar" and game.rng.random() < (0.24 if game.year >= 1944 else 0.12):
                sq = next((q for q in game.squads if q.id == b.squad_id), None)
                x, y = (sq.anchor() if sq is not None and sq.anchor() else b.pos)
                game.__dict__.setdefault("_counter_battery", []).append(
                    (game.turn + game.rng.randint(60, 300), enemy, x, y, True))

    def tick(self, game):
        """Every few seconds: splash warnings, counter-battery fire landing on a gun line that gave itself away,
        and the calls from the front for the battery you serve."""
        pb = self.player_battery(game)
        if pb is not None and pb.mission is None and pb.ammo > pb.ammo_max * 0.15 and \
                game.turn >= pb.__dict__.get("_next_call", 0):
            pb._next_call = game.turn + game.rng.randint(240, 720)
            self._call_from_front(game, pb)
        for b in self.batteries:
            m = b.mission
            if m is not None and m.get("splash_at") is not None and game.turn >= m["splash_at"]:
                m["splash_at"] = None
                game.msg("Radio: 'Splash, over.'", "radio")
        cb = game.__dict__.get("_counter_battery")
        if cb:
            keep = []
            for entry in cb:
                t, side, x, y = entry[:4]
                mortar = len(entry) > 4 and entry[4]
                if game.turn < t:
                    keep.append(entry)
                    continue
                # the enemy's own batteries - in range, free and with rounds - fire where their sound-rangers
                # and flash-spotters put the guns: near enough, not exactly.  Against mortars (counter-mortar),
                # their mortars join in; against a gun line, only guns reach and have the business of it
                kinds = ("gun", "rocket", "naval", "mortar") if mortar else ("gun", "rocket", "naval")
                took = self.barrage(game, side, x, y, 4 if mortar else 6, 12 if mortar else 16, delay=0,
                                    kinds=kinds, error=4.0 if mortar else 6.0, tag="cb")
                for b in took:
                    b.mission["cb_near"] = (x, y)
                    b.mission["cb_mortar"] = mortar
            game._counter_battery = keep
        warn = game.__dict__.get("_cb_warn")
        if warn:
            p = game.player
            for w in [w for w in warn if game.turn >= w[0]]:
                x, y = w[1]
                if p is not None and abs(p.x - x) + abs(p.y - y) < 60:
                    game.msg("Counter-mortar fire! They've found the mortars - get down!" if len(w) > 2 and w[2]
                             else "Counter-battery! Their guns have found ours - get down!", "warn")
            game._cb_warn = [w for w in warn if game.turn < w[0]]

    # ================================================================ the war map
    def strategic_tick(self, game):
        """Every strategic tick: new units where the map has grown, resupply, batteries lost with their ground,
        and the guns fire at the fighting in their reach."""
        st = game.strategic
        self.populate(game)
        rng = game.rng
        for b in self.batteries:
            if b.lost or b.kind == "naval":
                continue
            s = st.at(*b.sec)
            if s is None or s.control != b.side:
                b.lost = True
                st.news.append(f"{b.name} was overrun at {s.name if s else 'its position'}; its guns are lost.")
                continue
            if b.kind == "mortar" and b.mission is None and not st.is_front(s, b.side) and s is not game.sector:
                b.sec = self._follow_front(game, b) or b.sec   # the battalion moved: its mortars went with it
            sup = st.supply_of(b.side, s)
            if sup >= 0.3:
                b.ammo = min(b.ammo_max, b.ammo + int(b.ammo_max * 0.2 * sup))
            if not self.here(game, b) and b.guns < b.guns_max and sup >= 0.5 and rng.random() < 0.1:
                b.guns += 1                               # a replacement gun comes up
        for q in self.squadrons:
            if q.planes < q.planes_max and rng.random() < 0.15:
                q.planes += 1                             # a replacement aircraft and pilot
            a = st.at(*q.sec) if st else None
            if a is not None and a.playable and a.control not in (None, q.side):
                # the airfield's gone: what's left flies back to one further off
                q.sec = self._rear_point(game, q.side)
        self._counter_battery_elsewhere(game)
        self._fire_at_the_front(game)

    def _counter_battery_elsewhere(self, game):
        """Batteries firing somewhere off your map give themselves away as well: an enemy gun battery that can
        reach them, is free and has rounds, fires on them - its own rounds, from where it is - and may knock out
        a gun or two (see _end)."""
        rng = game.rng
        for b in self.batteries:
            if b.lost or b.kind not in ("gun", "rocket", "mortar") or self.here(game, b):
                continue
            fired = b.fired - b.__dict__.get("_fired_seen", 0)
            b._fired_seen = b.fired
            mortar = b.kind == "mortar"
            odds = min(0.5, 0.1 + fired / 120) * ((1.0 if game.year >= 1944 else 0.5) if mortar else 1.0)
            if fired <= 0 or rng.random() > odds:
                continue
            enemy = other_side(b.side)
            kinds = ("gun", "rocket", "naval", "mortar") if mortar else ("gun", "rocket", "naval")
            hunters = [h for h in self.ready(game, enemy, b.sec, b.pos, kinds)]
            if not hunters:
                continue
            h = min(hunters, key=lambda h: self.km(game, h, b.sec, b.pos) / self.reach_km(game, h))
            self.start(game, h, ("sector", b.sec, b.pos), None, h.guns * 3, delay=rng.randint(60, 400), silent=True)
            h.mission["cb_target"] = b.id

    def _call_from_front(self, game, b):
        """An observer somewhere up the line wants this battery: a target in an enemy sector it can reach - or, if
        the enemy's on your own map, there."""
        st = game.strategic
        rng = game.rng
        here = (game.sector.x, game.sector.y)
        if b.kind == "mortar" and self.here(game, b):
            # the company commander up front wants something shelled that he's seen
            brain = game.brains[b.side]
            cs = brain.clusters(radius=5, min_size=1, max_age=60) or [(1, c.x, c.y, [c]) for c in brain.live_contacts(30, False)]
            p = game.player
            reach = self.reach_km(game, b)
            cs = [c for c in cs if self.km(game, b, here, (c[1], c[2])) <= reach and
                  (p is None or math.hypot(c[1] - p.x, c[2] - p.y) <= (p.weapon.t.rng if p.weapon is not None else 99))
                  and not any(o.side == b.side and o.alive and abs(o.x - c[1]) + abs(o.y - c[2]) < 6 for o in game.actors)]
            if cs:
                _w, x, y, _g = cs[0]
                self.start(game, b, ("map", here, (x, y)), None, b.guns * 2, delay=rng.randint(20, 60), silent=True)
            return
        targets = [s for s in st.sectors() if s.playable and s.control not in (None, b.side) and
                   any(n.control == b.side for n in st.neighbors(s)) and
                   self.km(game, b, (s.x, s.y), None) <= b.range_km and (s.x, s.y) != here]
        if not targets:
            return
        s = min(targets, key=lambda c: self.km(game, b, (c.x, c.y), None) + rng.random())
        self.start(game, b, ("sector", (s.x, s.y), None), None, None, delay=rng.randint(20, 90), silent=True)
        b.mission["front"] = s.name

    def _follow_front(self, game, b):
        st = game.strategic
        for s in st.sectors():
            if s.control == b.side and st.is_front(s, b.side) and \
                    abs(s.x - b.sec[0]) + abs(s.y - b.sec[1]) <= 2:
                return (s.x, s.y)
        return None

    def _fire_at_the_front(self, game):
        """The observers up the line call their own missions: each free battery fires on the fighting it can reach
        (what an artilleryman at the guns spends his day doing)."""
        st = game.strategic
        rng = game.rng
        for b in self.batteries:
            if b.lost or b.mission is not None or b.ammo < b.ammo_max * 0.3 or b.kind == "naval":
                continue
            if rng.random() > 0.5:
                continue
            targets = [s for s in st.sectors() if s.playable and s.control not in (None, b.side) and
                       any(n.control == b.side for n in st.neighbors(s)) and
                       self.km(game, b, (s.x, s.y), None) <= b.range_km]
            here = (game.sector.x, game.sector.y) if game.sector else None
            targets = [s for s in targets if (s.x, s.y) != here]       # (your own map's fire comes from its men's calls)
            if not targets:
                continue
            s = rng.choice(targets)
            self.start(game, b, ("sector", (s.x, s.y), None), None, b.guns * rng.randint(2, 4),
                       delay=rng.randint(0, 300), silent=True)
            b.mission["front"] = s.name

    # ================================================================ your map
    def sync(self, game):
        """Guns knocked out on your map are guns the battery hasn't got any more."""
        for b in self.batteries:
            if not self.here(game, b) or b.lost:
                continue
            if b.vids:
                alive = [v for v in game.vehicles if v.id in b.vids and not v.dead and v.crew > 0 and v.gun_ok
                         and not v.abandoned]
                mine = [v for v in game.vehicles if v.id in b.vids and not v.dead and v.side == b.side]
                b.guns = len(alive)
                if not mine and b.guns == 0:
                    b.lost = True
                    if game.player is not None:
                        game.stats["batteries_silenced"] += 1
            elif b.kind == "mortar" and b.squad_id is not None:
                sq = next((s for s in game.squads if s.id == b.squad_id), None)
                n = sum(1 for a in (sq.members if sq else ()) if a.active and a.weapon is not None
                        and a.weapon.t.cat == "mortar")
                b.guns = n
                if sq is None or sq.gone or not sq.members:
                    b.squad_id = None
                    self.link_mortars(game, spawn=False)     # what's left of the tubes, in whatever squad they're in

    def place_guns(self, game, rec):
        """An artillery position on your map: its batteries' guns, crewed, in their pits (spawn.spawn_installation
        calls this with the position's record).  Returns the guns it put down."""
        self.populate(game)
        from .ai import Order, Squad
        from .data.vehicles import VEHICLES
        from .entities import Vehicle
        from .spawn import facing_toward_edge, pick_vehicle, spot_and_facing
        here = (game.sector.x, game.sector.y)
        side = rec.get("side")
        bats = [b for b in self.batteries if b.sec == here and b.side == side and b.kind in ("gun", "rocket")
                and not b.lost]
        placed = []
        rng = game.rng
        spots = [(x, y) for k, x, y in rec.get("spots", []) if k == "howitzer"]
        cx, cy = rec.get("x", game.map.w // 2), rec.get("y", game.map.h // 2)
        enemy_edge = game.home_edge(other_side(side))
        for b in bats:
            b.vids = []
            b.pos = (cx, cy)
            vid = PIECE.get(b.btype)
            if vid not in VEHICLES:
                vid = pick_vehicle(rng, b.nation, game.year, "fieldgun", include_zero=True)
            if vid is None:
                continue
            for i in range(b.guns):
                x, y = spots.pop(0) if spots else (cx + rng.randint(-10, 10), cy + rng.randint(-5, 5))
                pt, f = spot_and_facing(game, x, y, VEHICLES[vid], 4, facing_toward_edge(enemy_edge) if enemy_edge else 0)
                if pt is None:
                    continue
                v = Vehicle(vid, side, b.nation, pt[0], pt[1], f)
                sq = Squad(side, b.nation, "atgun", f"{b.name}, gun {i + 1}")
                sq.no_count = True
                sq.order = Order("hold", target=pt)
                v.squad = sq
                sq.vehicles.append(v)
                game.squads.append(sq)
                game.add_vehicle(v)
                v.ai["battery"] = b.id
                b.vids.append(v.id)
                placed.append(v)
        return placed

    def link_mortars(self, game, spawn=True):
        """The mortar platoons in your sector are real: a mortar squad on the map is the platoon's tubes (if
        there's none, the platoon is put down behind its own companies - on arrival, not mid-battle)."""
        here = (game.sector.x, game.sector.y)
        taken = {b.squad_id for b in self.batteries if b.squad_id is not None}
        for b in self.batteries:
            if b.sec != here or b.kind != "mortar" or b.lost:
                continue
            if b.squad_id is not None and any(s.id == b.squad_id for s in game.squads):
                continue
            b.squad_id = None
            sqs = [s for s in game.squads if s.side == b.side and s.kind == "mortar" and s.members and
                   s.id not in taken and not s.player_led]
            if not sqs and not spawn:
                continue
            if not sqs:
                from .spawn import edge_band_point, make_squad
                e = game.home_edge(b.side)
                if e is None:
                    continue
                x, y = edge_band_point(game, e, game.rng, depth=(8, 18))
                sq = make_squad(game, b.side, b.nation, "mortar", x, y, name=b.name)
                sq.no_count = True
                sqs = [sq]
            sq = sqs[0]
            b.squad_id = sq.id
            taken.add(sq.id)
            b.pos = sq.anchor()

    # ================================================================ you, on a gun or a mortar
    def player_battery(self, game):
        """The battery (or mortar platoon) you serve in, if you're on one of its guns or tubes."""
        p = game.player
        if p is None:
            return None
        v = p.vehicle
        if v is not None and v.player_crewed and v.player_station == "gunner" and v.ai.get("battery"):
            return next((b for b in self.batteries if b.id == v.ai["battery"] and not b.lost), None)
        sq = p.squad
        if v is None and sq is not None and p.weapon is not None and p.weapon.t.cat == "mortar":
            return next((b for b in self.batteries if b.squad_id == sq.id and not b.lost), None)
        return None

    def player_mission(self, game):
        b = self.player_battery(game)
        if b is None or b.mission is None:
            return None
        m = b.mission
        if m.get("player_left", 0) <= 0 or game.turn < m["start"]:
            return None
        return b, m

    def firing_data(self, game, b, target) -> dict:
        """The numbers the fire direction centre sends down: the shell, the charge, the azimuth and the elevation
        in mils (6400 to the circle) - worked out from where your gun is and where the target is."""
        p = game.player
        kind, sec, pos = target
        here = (game.sector.x, game.sector.y)
        gx, gy = self._global(game, here, (p.x, p.y))
        tx, ty = self._global(game, sec, pos)
        dx, dy = tx - gx, ty - gy
        az = int(round(((math.degrees(math.atan2(dx, -dy)) + 360) % 360) * 6400 / 360)) % 6400
        km = math.hypot(dx, dy) * 0.002
        f = min(1.0, km / b.range_km)
        if b.kind == "mortar":
            qe = int(round(math.degrees(math.pi / 2 - 0.5 * math.asin(f)) * 6400 / 360))
        else:
            qe = int(round(math.degrees(0.5 * math.asin(f)) * 6400 / 360)) + 10
        return dict(az=az, qe=qe, charge=max(1, min(7, int(math.ceil(f * 7)))), km=km,
                    shell="smoke" if (b.mission or {}).get("smoke") else "shell HE")

    def order_text(self, game):
        pm = self.player_mission(game)
        if pm is None:
            return None
        b, m = pm
        d = m["data"]
        what = m.get("front") or ("here" if m["target"][1] == (game.sector.x, game.sector.y) else "the front")
        return (f"FIRE MISSION ({what}): {d['shell']}, charge {d['charge']}, azimuth {d['az']:04d}, elevation "
                f"{d['qe']:04d} - {m['player_left']} more from your {'tube' if b.kind == 'mortar' else 'gun'}.")

    def fire_player_round(self, ps) -> int | None:
        """You lay the gun on the data and pull the lanyard (or drop a bomb down the tube).  Returns the time it
        took, or None if it couldn't be done."""
        g = ps.game
        pm = self.player_mission(g)
        if pm is None:
            return None
        b, m = pm
        p = g.player
        rng = g.rng
        kind, sec, pos = self._concrete(g, b, m)
        on_map = sec == (g.sector.x, g.sector.y)
        v = p.vehicle
        if v is not None:
            if v.reload > 0:
                g.msg("Not loaded yet - the loader's still ramming the round home.", "info")
                return 100
            if not v.gun_ok:
                g.msg("The gun's knocked out.", "warn")
                return None
            # laying: the first round of a mission takes setting the sights and cranking her round; after that,
            # a touch on the handwheels between rounds
            lay = int((2000 if not m.get("laid") else 500) * max(0.6, 1.4 - p.skill * 0.06))
            m["laid"] = True
            from .gamemap import octant
            from .vdamage import reload_mult
            if on_map:
                v.turret = v.facing = octant(pos[0] - v.x, pos[1] - v.y)
            g.effect_flash(v.x, v.y)
            g.emit_sound(v.x, v.y, 112, "cannon", f"the crash of your {b.bt.cal} gun", b.side, v)
            v.fired_turn = g.turn
            v.reload = int((v.mount.reload_cost if v.mount else 500) * reload_mult(v))
            b.ammo = max(0, b.ammo - 1)
            b.fired += 1
            if on_map:
                err = max(0.5, (8 - p.skill) * 0.4)
                ix, iy = self._aim(g, m, pos)
                ix, iy = int(round(ix + rng.gauss(0, err))), int(round(iy + rng.gauss(0, err)))
                mm = g.map
                bt = b.bt
                g.schedule_shell(max(0, min(mm.w - 1, ix)), max(0, min(mm.h - 1, iy)), m["flight"], bt.power,
                                 bt.radius, bt.frags, 24, p, f"a {bt.cal} shell from your gun", whistle=True,
                                 sound=bt.sound, side=b.side, smoke=bool(m.get("smoke")))
            else:
                self._shell_sector(g, b, sec, 1)
            cost = lay
        else:
            # a mortarman: the bomb from your own tube, on the mission's spot
            if not on_map:
                return None
            from . import actions as A
            tx, ty = self._aim(g, m, pos)
            d = math.hypot(tx - p.x, ty - p.y)
            t = p.weapon.t
            if not (t.min_rng <= d <= t.rng):
                g.msg("Too close for your mortar - you'd drop it on yourself." if d < t.min_rng else
                      "Out of your mortar's range from here.", "warn")
                return None
            if p.ammo_for(p.weapon) is not None:
                c = A.fire(g, p, tx, ty)                           # a bomb from your own bag
            elif b.ammo > 0:
                if not m.get("bearer"):
                    m["bearer"] = True
                    g.msg("Your bag's empty: an ammunition bearer crouches beside the tube, handing you bombs "
                          "from the platoon's carts.", "info")
                c = self._drop_bomb(g, b, p, p.weapon, tx, ty)
            else:
                g.msg("No bombs left - not in your bag, not on the platoon's carts.", "warn")
                m["player_left"] = 0
                return None
            if not c:
                return None
            cost = c
        m["fired"] += 1
        m["player_left"] -= 1
        m["player_fired"] = m.get("player_fired", 0) + 1
        if m["player_fired"] == 1 and m["player_total"] > 1:
            g.msg(f"Radio, the observer: '{self._correction(g, b, m)}'", "radio")
        if m["player_left"] <= 0:
            g.update_orders(force=True)
        return cost

    def _correction(self, g, b, m) -> str:
        """The observer's correction, from where the rounds are really falling: left or right of the line from the
        guns, and over or short of the target, in metres."""
        bx, by = m["bias"]
        kind, sec, pos = m["target"]
        here = (g.sector.x, g.sector.y)
        p = g.player
        gx, gy = self._global(g, here, (p.x, p.y))
        tx, ty = self._global(g, sec, pos)
        L = math.hypot(tx - gx, ty - gy) or 1.0
        ux, uy = (tx - gx) / L, (ty - gy) / L
        along = (bx * ux + by * uy) * 2           # metres long (+) or short (-)
        across = (bx * -uy + by * ux) * 2         # metres right (+) or left (-) of the line
        if abs(along) < 25 and abs(across) < 25:
            return "On target. Fire for effect!"
        parts = []
        if abs(across) >= 25:
            parts.append(f"{'left' if across > 0 else 'right'} {int(round(abs(across), -1))}")
        if abs(along) >= 25:
            parts.append(f"{'drop' if along > 0 else 'add'} {int(round(abs(along), -1))}")
        return (", ".join(parts)).capitalize() + ". Fire for effect!"

    # ================================================================ air
    def squadron_for(self, game, side, roles=None, night=False):
        cands = []
        for q in self.squadrons:
            if q.side != side or q.ready(game.turn) <= 0:
                continue
            at = q.at
            if roles and at.role not in roles:
                continue
            if night and not at.night:
                continue
            cands.append(q)
        if not cands:
            return None
        return max(cands, key=lambda q: q.ready(game.turn))

    def sortie_out(self, game, q, n):
        q.out += n
        q.sorties += 1

    def plane_lost(self, game, q):
        q.planes = max(0, q.planes - 1)
        q.out = max(0, q.out - 1)
        q.lost += 1

    def plane_back(self, game, q):
        q.out = max(0, q.out - 1)
        if q.out == 0:
            q.ready_at = game.turn + 3600               # an hour to refuel, rearm and patch the holes

    # ================================================================ words
    def summary(self, game, side) -> str:
        here = (game.sector.x, game.sector.y)
        inr = self.in_range(game, side, here, None)
        rdy = [b for b in inr if b.mission is None and b.ammo > 0]
        return f"Batteries in range: {len(rdy)} ready of {len(inr)}"
