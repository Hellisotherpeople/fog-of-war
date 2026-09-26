"""The Game: owns the world and runs the turn loop."""
from __future__ import annotations

from .constants import cap

import datetime as dt
import math
import os
import pickle
import random
import time
from collections import Counter, deque

import numpy as np

from . import ai as AI
from . import tiles as T
from .ai import Order, Squad
from .body import PART_NAME
from .brain import SideBrain
from .combat import explode, hit_actor, ignite, settle_recoil
from .command import CommandState
from .commander import commander_update, update_objectives
from .constants import (ALLIES, AXIS, BASE_SPEED, MAP_H, MAP_W, SIDES, STRATEGIC_TICK,
                        other_side)
from .data.items import ITEMS
from .data.nations import NATIONS, random_name
from .data.theatres import THEATRES, theatre_year
from .entities import Actor, Item, Vehicle, make_corpse
from .mapgen import generate
from .senses import (HEAR_THRESHOLD, ONOMATOPOEIA, base_view_range, compute_light, daylight,
                     direction_word, distance_word, player_can_see_actor, player_fov, sound_at)
from .strategic import OPP, Strategic, power
from .support import Support

SAVE_DIR = os.path.join(os.path.expanduser("~"), ".fogofwar")
_NATIVE = {}


def native_lines(nation):
    """Every fixed line this army says in its own language (shouts, acknowledgements, phrases)."""
    s = _NATIVE.get(nation)
    if s is None:
        from .data import ranks as R
        from .data.phrases import all_lines
        s = set(x for v in NATIONS[nation]["shouts"].values() for x in v) | set(all_lines(nation))
        for lst in (R.ACK.get(nation, []), R.REFUSE.get(nation, [])):
            for x in lst:
                s.add(x)
        _NATIVE[nation] = s
    return s


def is_native(nation, line):
    import re
    s = native_lines(nation)
    if line in s:
        return True
    for t in s:
        if "{rank}" in t and re.fullmatch(re.escape(t).replace(re.escape("{rank}"), ".+"), line):
            return True
    return False


def an(word: str) -> str:
    return ("an " if word[:1].upper() in "AEIOU" else "a ") + word
EDGE_VEC = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
# battlefield sizes (tiles of about two yards) and how many troops a sector holds against the standard one
BATTLEFIELDS = {"standard": (MAP_W, MAP_H, 1.0), "large": (270, 180, 2.0), "huge": (360, 240, 3.0)}
DEFAULT_BATTLEFIELD = "large"


class Message:
    __slots__ = ("text", "cat", "turn", "count")

    def __init__(self, text, cat, turn):
        self.text = text
        self.cat = cat
        self.turn = turn
        self.count = 1


class SoundMark:
    __slots__ = ("x", "y", "text", "until", "kind", "color")

    def __init__(self, x, y, text, until, kind, color):
        self.x = x
        self.y = y
        self.text = text
        self.until = until
        self.kind = kind
        self.color = color


class Game:
    def __init__(self, theatre_id: str, nation: str, role: str | None = None, seed: int | None = None,
                 setup: dict | None = None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.theatre = THEATRES[theatre_id]
        # the character / scenario creator's choices (anything left out is up to chance or the army)
        self.setup = dict(setup or {})
        self.mission = None
        self.theatre_id = theatre_id
        self.year = theatre_year(self.theatre)
        y, mo, d, h, mi = self.theatre["date"]
        self.start_dt = dt.datetime(y, mo, d, h, mi)
        self.clock = 0                    # seconds since start
        self.turn = 0
        self.player_nation = nation
        self.player_side = NATIONS[nation]["side"]
        self.attacker = self.theatre["attacker"]
        self.messages: deque[Message] = deque(maxlen=400)
        self.msg_total = 0
        self.audio_events = []
        self.effects: list[dict] = []
        self.sound_marks: list[SoundMark] = []
        self.shouts_seen: list = []
        self._sound_msgs: dict = {}
        self.pending_explosions: list = []
        self.explosives: list[dict] = []
        self.shells: list[dict] = []
        self.smoke_sources: list[list] = []
        self.waves: list[dict] = []
        self.terrain_dirty = False
        self.ai_last_whizz = -1
        self.lit = None
        self.view_range_cache = 60
        self.player_binoculars = False
        self.stats = Counter()
        self.kills_by: Counter = Counter()
        self.initial_strength = {}
        self.withdrawing = {}
        self.first_battle = True
        self.game_over = False
        self.death_text = None
        self.victory_text = None
        self.last_whizz_msg = -99
        self.player_orders = ""
        self.orders_turn = -99
        self.weather = self._roll_weather()
        self.weather_turn = 0
        self.wind = (self.rng.choice((-1, 0, 1)), self.rng.choice((-1, 0, 1)))
        # the size of each battlefield, and so how many men a sector holds (see BATTLEFIELDS)
        size = self.setup.get("battlefield") or DEFAULT_BATTLEFIELD
        self.map_w, self.map_h, self.troop_scale = BATTLEFIELDS.get(size, BATTLEFIELDS[DEFAULT_BATTLEFIELD])
        self.strategic = Strategic(self.theatre, self.rng, self.year, scale=self.troop_scale)
        self.sector = None
        self.map = None
        self.actors: list[Actor] = []
        self.vehicles: list[Vehicle] = []
        self.squads: list[Squad] = []
        self.soldier_at: dict = {}
        self.vehicle_at: dict = {}
        self.brains = {}
        self.player = None
        self.briefing: list[str] = []
        self._arr_turn = -1
        self._arr = None
        self._enemy_arr = {}
        self.support = None
        self.companions: list[Actor] = []
        self.auto_path = None
        self.sector_log: list[str] = []
        self.last_strategic = 0
        self.captured = Counter()
        self.start_real = time.time()
        self.command = CommandState()
        from .duty import Duty
        self.duty = Duty()
        from .hierarchy import Hierarchy
        self.hierarchy = Hierarchy()      # who commands what, all the way up (and what you know of it)
        from .operations import Operations
        self.ops = Operations()           # your divisions and corps, if you command on that scale
        self.domain = "land"              # land / air / sea: where the war is for you right now
        self.skysea = None                # the air and sea world, while you're in it
        self.renegade = False             # your own side has turned on you
        self.pow = None                   # captivity, if you surrendered
        self.no_quarter = Counter()       # sides that have seen their surrendered men shot
        self.noise = 0.0                  # how loud the battle is around you (drowns out shouted orders)
        self._banter_replies = []
        from . import scenarios as SC
        sid = self.setup.get("scenario") or "front"
        service = self.setup.get("service") or "army"
        unit = self.setup.get("unit")
        if unit and unit != "regular":
            from .data.special import SPECIAL
            d = SPECIAL.get(unit, {})
            if role is None:
                role = d.get("role")
            if sid == "random" and d.get("scenario"):
                sid = d["scenario"]
                if sid.startswith("air:"):
                    service = self.setup["service"] = "air"
        if sid == "random" and service == "army":
            sid = SC.pick(self.rng, self.theatre, self.player_side)
        if not SC.eligible(sid, self.theatre, self.player_side):
            sid = "front"
        if sid == "partisans" and SC.partisan_nation(self.theatre):
            self.player_nation = SC.partisan_nation(self.theatre)
        self.scenario = sid
        if service != "army" and role is None:
            from .data.roles import SERVICE_ROLES
            role = self.rng.choice(SERVICE_ROLES[service][:4] if service == "navy" else SERVICE_ROLES[service])
        if role is None and sid in SC.SCENARIOS and SC.SCENARIOS[sid]["role"] and not self.setup.get("role_random"):
            role = SC.SCENARIOS[sid]["role"]
        self._start(role)

    # ================================================================== setup
    def _roll_weather(self):
        w = self.theatre.get("weather", {"clear": 1})
        return self.rng.choices(list(w), list(w.values()))[0]

    def _start(self, role):
        rng = self.rng
        st = self.strategic
        side = self.player_side
        special = self.theatre.get("special", set())
        # choose a starting sector
        cands = []
        for s in st.sectors():
            if not s.playable:
                continue
            if f"paradrop_{side}" in special:
                if s.units[side] and s.control == other_side(side):
                    cands.append(s)
            elif "landing" in special:
                if s.biome == "beach":
                    cands.append(s)
            elif st.is_front(s, side) and s.control == side:
                cands.append(s)
            elif s.control == other_side(side) and st.is_front(s, other_side(side)) and side == self.attacker:
                pass
        if not cands:
            cands = [s for s in st.sectors() if s.playable and s.control == side] or \
                    [s for s in st.sectors() if s.playable]
        start = rng.choice(cands)
        from . import scenarios as SC
        forced = SC.choose_start(self, self.scenario, side)
        if forced is not None:
            start = forced
        # attacker front sectors: the battle is in the enemy sector next door
        if forced is not None:
            pass
        elif "landing" in special and side == self.attacker and start.biome == "beach":
            sea = [n for n in st.neighbors(start) if n.biome == "sea"]
            if sea:
                start.units[side].update(st._detach(sea[0].units[side], 0.35))
                if sum(start.units[side].values()) < 4 * self.troop_scale:
                    start.units[side]["inf"] += st.sc(rng.randint(5, 8))
                    start.units[side]["mg"] += st.sc(1)
                    start.units[side]["eng"] += st.sc(1)
                    start.units[side]["hq"] += 1
        elif not any(k.startswith("paradrop") for k in special):
            enemy_nb = [n for n in st.neighbors(start) if n.control == other_side(side) and n.playable]
            if enemy_nb:
                if side == self.attacker or rng.random() < 0.5:
                    # we attack into the enemy sector
                    target = rng.choice(enemy_nb)
                    target.units[side].update(st._detach(start.units[side], 0.6))
                    start = target
                else:
                    # the enemy attacks us
                    src = rng.choice(enemy_nb)
                    start.units[other_side(side)].update(st._detach(src.units[other_side(side)], 0.6))
        # make sure there is a fight
        for s2 in SIDES:
            if sum(start.units[s2].values()) == 0:
                start.units[s2]["inf"] += st.sc(rng.randint(3, 6))
                start.units[s2]["mg"] += st.sc(1)
        # attackers concentrate for the assault: give them a fighting chance
        att_side, _ = self._local_attacker(start)
        if att_side is not None:
            dfn = other_side(att_side)
            pa, pd = power(start.units[att_side]), power(start.units[dfn])
            while pa < pd * 1.25:
                start.units[att_side]["inf"] += 1
                if rng.random() < 0.25:
                    start.units[att_side]["mg"] += 1
                if rng.random() < self.theatre["armor"].get(att_side, 0.3) * 0.4:
                    start.units[att_side]["tank"] += 1
                pa = power(start.units[att_side])
        self.enter_sector(start, entry_edge=None)
        p, notes = __import__("fow.spawn", fromlist=["create_player"]).create_player(self, self.player_nation, role)
        self.player = p
        from .data.roles import service_of
        p.service = self.setup.get("service") or service_of(p.role)
        self._apply_setup(p, notes)
        if p.service in ("air", "navy") and not self.scenario.startswith(("air:", "sea:")):
            self.scenario = SC.pick_service_mission(self, p.service, p.role) or "front"
        SC.setup_player(self, self.scenario, notes)
        self.first_battle = False
        self.initial_strength = {s: self.side_strength(s) for s in SIDES}
        self.command.organise(self)
        notes += self._command_notes()
        if self.scenario == "pow":
            from .pow import start_in_camp
            notes.append(start_in_camp(self))
        if self.scenario in SC.SCENARIOS and self.scenario != "front":
            notes.insert(0, f"[{SC.SCENARIOS[self.scenario]['name']}] {SC.SCENARIOS[self.scenario]['desc']}")
        self.briefing = self._make_briefing(notes)
        self.update_orders(force=True)
        self.player_fov()

    def _apply_setup(self, p, notes):
        """The creator's choices: name, rank, traits, weapon, extra kit, and whether the start is kind."""
        su = self.setup
        unit = su.get("unit")
        if unit is None and not su.get("no_special"):
            # now and then the army sends you somewhere unusual
            from .data.special import SPECIAL, for_player
            cands = [k for k in for_player(p.nation, self.year, self.theatre_id, p.__dict__.get("service", "army"))
                     if SPECIAL[k]["role"] == p.role or self.rng.random() < 0.3]
            if cands and self.rng.random() < 0.04:
                unit = self.rng.choice(cands)
        if unit and unit != "regular":
            from .data.special import SPECIAL
            from .spawn import apply_special
            apply_special(self, p, unit)
            notes.append(f"You serve with the {SPECIAL[unit]['name']}. {SPECIAL[unit]['desc']}")
        from .entities import Item
        from .data.items import ITEMS
        if su.get("name"):
            nm = su["name"].strip()
            if nm:
                p.name = nm                       # (last name and full name follow from it)
        if su.get("rank") is not None:
            p.rank = max(0, min(18, int(su["rank"])))
        if su.get("traits") is not None:
            p.traits = set(su["traits"])
        wid = su.get("weapon")
        if wid and wid in ITEMS:
            w = Item(wid)
            if p.add_item(w) is not None or True:
                p.wield(w)
                from .ammo import give_ammo
                try:
                    give_ammo(p, w, 4)
                except Exception:
                    pass
        for tid, n in (su.get("kit") or {}).items():
            if tid in ITEMS and n:
                it = Item(tid, n)
                if p.add_item(it) is None:
                    # no room: you'd have found a haversack for it
                    if p.invent.slots.get("pack") is None and "backpack" in ITEMS:
                        p.invent.slots["pack"] = Item("backpack")
                        p.invent.slots["pack"].where = "pack"
                    if p.add_item(it) is None:
                        notes.append(f"You couldn't find room for the {it.name}.")
        if su.get("fair"):
            # no unfair start: heal whatever the opening did, clear jams, rejoin the squad
            for k in p.body.hp:
                p.body.hp[k] = p.body.max[k]
            p.body.wounds = [] if hasattr(p.body, "wounds") else p.body.__dict__.get("wounds")
            if p.weapon is not None:
                p.weapon.jammed = False

    def _make_briefing(self, notes):
        p = self.player
        th = self.theatre
        n = NATIONS[p.nation]
        lines = [
            f"{th['name'].upper()}: {th['battle']}",
            f"{self.datetime_str(exact=True)}",
            "",
            th["desc"],
            "",
            f"You are {p.rank_full} {p.name}, {n['adj']} {n['army']}.",
            f"{p.unit}.",
            f"Role: {p.role_name}. {__import__('fow.data.roles', fromlist=['ROLES']).ROLES[p.role]['desc']}",
        ]
        if p.traits:
            from .spawn import TRAITS
            lines.append("You are: " + ", ".join(TRAITS[t] for t in sorted(p.traits)) + ".")
        kit = []
        if p.weapon is not None:
            kit.append(p.weapon.t.name)
        for i in p.inv:
            if i is p.weapon:
                continue
            kit.append(i.name)
        lines.append("")
        lines.append("You carry: " + ", ".join(kit[:14]) + ("..." if len(kit) > 14 else "") + ".")
        lines.append("")
        lines.append(f"Sector: {self.sector.name} ({self.sector_desc()}).")
        lines += notes
        return lines

    def _command_notes(self):
        cmd = self.command
        p = self.player
        out = []
        f = cmd.billet
        if f is not None:
            n = len(f.live_squads())
            head = f"You command {f.title() if f.echelon == 'platoon' else f.name}"
            if f.acting:
                head += " - acting: there's no one more senior left"
            out.append(f"{head}. {n} unit{'s' if n != 1 else ''} on this field answer to you. (C: command)")
            if f.echelon not in ("platoon", "company", "battalion"):
                out.append("The rest of your command is spread across the front. The war map (m) is where "
                           "you move it.")
        elif cmd.billet_squad is not None:
            out.append("Your men look to you for orders. (O: orders, C: command)")
        from .data.ranks import LT2
        if p.rank >= LT2 and f is None:
            out.append("As an officer you can take command of any unit whose leader you outrank. (C)")
        return out

    def sector_desc(self):
        from .strategic import BIOME_NAME
        s = self.sector
        return BIOME_NAME.get(s.biome if s.biome != "beach" else "beach", s.biome)

    # ================================================================== sectors
    def enter_sector(self, sector, entry_edge=None, companions=()):
        rng = self.rng
        st = self.strategic
        self.sector = sector
        sector.visited = True
        st.touch(sector.x, sector.y, 3)          # the world goes on: make the ground around here
        going_in = self._attack_arrives(sector)
        spec, att, att_edge = self.sector_spec(sector)
        self.attacker = att
        self.att_edge = att_edge
        self.def_edge = OPP.get(att_edge) if att_edge else None
        self.actors = []
        self.vehicles = []
        self.squads = []
        self.peek_at = {}
        if self.player is not None:
            self.player.peek = None
        self.soldier_at = {}
        self.vehicle_at = {}
        self.explosives = []
        self.shells = []
        self.pending_explosions = []
        self.waves = []
        self.smoke_sources = []
        self.effects = []
        self.sound_marks = []
        if self.support is not None:
            self.support.queue = []
            self.support.aircraft = []
        fresh = sector.saved is None
        if not fresh:
            self.map = self._load_map(sector)
        else:
            # the ground you've been looking at across the edge is the ground you walk into
            hit = self.__dict__.get("_nb_cache", {}).pop((sector.x, sector.y), None)
            self.map = hit[1] if hit is not None and hit[0] == self._spec_key(sector, spec) and \
                not isinstance(hit[1], tuple) else generate(spec)
        self.__dict__.get("_nb_cache", {}).clear()
        m = self.map
        self.brains = {s: SideBrain(self, s) for s in SIDES}
        if self.support is None:
            self.support = Support(self)
        self.update_view_range()
        from .spawn import populate
        populate(self, sector, att, att_edge)
        if fresh:
            from .loot import scatter
            try:
                scatter(self)
            except Exception:
                if os.environ.get("FOW_DEBUG"):
                    raise
        # companions arrive with the player
        if companions:
            self._place_companions(companions, entry_edge)
        for b in self.brains.values():
            b.update(force=True)
        self.brains[SIDES[1]].last_update -= SideBrain.EVERY // 2      # the two sides think on different turns
        # initial orders
        for s in SIDES:
            commander_update(self, s)
        if going_in and att:
            self._attack_under_way(sector, att, att_edge)
        self.sector_log.append(f"{self.datetime_str()} - entered {sector.name}")
        if getattr(self, "command", None) is not None:
            self.command.on_new_battle(self)

    def _attack_arrives(self, sector):
        """Walking into ground that's being attacked on the war map: the attackers are on their way in,
        from the sector they're attacking out of.  Returns the attack (or None)."""
        st = self.strategic
        at = st.attack_on(sector.x, sector.y) if hasattr(st, "attack_on") else None
        if at is None:
            return None
        side = at["side"]
        if power(sector.units[side]) < 1.0 and at.get("src"):
            src = st.at(*at["src"])
            if src is not None and src is not sector and src.control == side:
                sector.units[side].update(st._detach(src.units[side], 0.5))
        return at if power(sector.units[side]) > 0 and power(sector.units[other_side(side)]) > 0 else None

    def _attack_under_way(self, sector, att, att_edge):
        """You've arrived in the middle of it: the guns are already firing and the first wave is going in."""
        from .constants import COMPASS_WORD
        where = COMPASS_WORD.get(att_edge, "")
        p = self.player
        lvl = self.theatre["arty"].get(att, 0.5)
        objs = self.map.objectives
        if objs and self.rng.random() < 0.35 + lvl * 0.6:
            for o in objs:
                if o.owner != att and self.rng.random() < 0.7:
                    self.support.barrage(att, o.x, o.y, 7, int(14 * lvl) + 5, delay=self.rng.randint(15, 120))
        if att == p.side:
            self.msg(f"The attack on {sector.name} is going in. Our first wave is moving up from the {where}; "
                     f"the rest are coming behind.", "radio")
        else:
            self.msg(f"{sector.name} is under attack from the {where}. The shelling has started - they're coming.",
                     "warn")

    # ------------------------------------------------ attacks out of this battlefield, and next door
    SALLY_KIND = {"rifle": "inf", "assault": "inf", "volkssturm": "inf", "mg": "mg", "mortar": "mortar",
                  "at": "at", "sniper": "sniper", "engineer": "eng"}

    def _sally(self, side, dst_key, edge):
        """A war-map attack out of the sector you're standing in: part of the troops here form up and
        march off the map edge into it - you watch them go (and can follow them)."""
        st = self.strategic
        dst = st.at(*dst_key)
        if dst is None or edge is None:
            return
        sal = self.__dict__.setdefault("sallies", {})
        if self.turn - sal.get(dst_key, -99999) < 1800:
            return                                         # the last lot is still on its way
        p = self.player
        cands = []
        for sq in self.squads:
            if sq.side != side or sq.gone or sq is p.squad or sq.player_led or sq.__dict__.get("sally"):
                continue
            if getattr(sq, "no_count", False) or sq.kind in ("hq",) or sq.order.kind == "retreat":
                continue
            if any(v.static for v in sq.vehicles):
                continue                                   # the guns stay in their pits
            men = [a for a in sq.members if a.active and not a.downed and not a.is_player]
            veh = [v for v in sq.vehicles if v.active and v.mobile]
            if len(men) >= 3 or veh:
                cands.append(sq)
        if len(cands) < 2:
            return                                         # a garrison stays
        self.rng.shuffle(cands)
        cands.sort(key=lambda q: -q.strength())
        go = cands[:max(1, len(cands) // 2)]
        sal[dst_key] = self.turn
        from .ai import Order
        for sq in go:
            anc = sq.anchor() or (self.map.w // 2, self.map.h // 2)
            tgt = self._edge_exit_point(edge, anc)
            sq.sally = dict(dst=dst_key, edge=edge, turn=self.turn, out=0, tgt=tgt,
                            ht=any(v.vt.vtype == "halftrack" for v in sq.vehicles))
            sq.order = Order("move", target=tgt, radius=2, issued=self.turn, src="player")
            sq.arrived = False
        from .constants import COMPASS_WORD
        n = sum(len([a for a in sq.members if a.active]) for sq in go)
        nv = sum(len([v for v in sq.vehicles if v.active]) for sq in go)
        self.msg(f"Orders come down: {len(go)} of the units here form up and move out to the "
                 f"{COMPASS_WORD.get(edge, edge)} - {n} men" + (f" and {nv} vehicles" if nv else "") +
                 f" - for the attack on {dst.name}.", "radio")

    def _edge_exit_point(self, edge, near, radius=10):
        from .spawn import free_tile_near
        m = self.map
        x, y = near
        if edge == "N":
            x, y = max(3, min(m.w - 4, x)), 0
        elif edge == "S":
            x, y = max(3, min(m.w - 4, x)), m.h - 1
        elif edge == "W":
            x, y = 0, max(3, min(m.h - 4, y))
        else:
            x, y = m.w - 1, max(3, min(m.h - 4, y))
        pt = free_tile_near(self, x, y, radius) or free_tile_near(self, x, y, 10)
        return pt or (x, y)

    def _edge_gap(self, edge, x, y):
        m = self.map
        return {"N": y, "S": m.h - 1 - y, "W": x, "E": m.w - 1 - x}.get(edge, 99)

    def _sally_tick(self):
        """Men and vehicles who reach the edge are gone into the attack next door."""
        st = self.strategic
        for sq in list(self.squads):
            sal = sq.__dict__.get("sally")
            if not sal:
                continue
            dst = st.at(*sal["dst"])
            e = sal["edge"]
            if sq.order.kind != "move" or tuple(sq.order.target or ()) != tuple(sal["tgt"]):
                sq.sally = None                            # re-tasked on the way (a fight here, new orders)
                continue
            if sq.arrived:
                # at the start line: over the edge, every man of them, not a defensive line short of it
                for a in sq.members:
                    if not a.active or a.vehicle is not None:
                        continue
                    pos = sq.positions.get(a.id)
                    if pos is None or self._edge_gap(e, *pos) > 1:
                        sq.positions[a.id] = self._edge_exit_point(e, (a.x, a.y), 3)
            for a in list(sq.members):
                if a.active and not a.downed and not a.is_player and a.vehicle is None and \
                        self._edge_gap(e, a.x, a.y) <= 2:
                    self.remove_actor(a)
                    a.state = "departed"
                    sq.members.remove(a)
                    sal["out"] += 1
                    self.stats["sent_forward"] = self.stats.get("sent_forward", 0) + 1
            for v in list(sq.vehicles):
                if v.active and self._edge_gap(e, v.x, v.y) <= 5 and not v.player_crewed:
                    for pa in list(v.passengers):
                        self.remove_actor(pa)
                        pa.state = "departed"
                        if pa in sq.members:
                            sq.members.remove(pa)
                    self.lift_vehicle(v)
                    v.x = v.y = -99
                    if v in self.vehicles:
                        self.vehicles.remove(v)
                    sq.vehicles.remove(v)
                    if dst is not None:
                        k = "ht" if v.vt.vtype == "halftrack" else "td" if v.vt.vtype in ("td", "spg") else "tank"
                        if v.vt.vtype not in ("truck", "car"):
                            dst.units[sq.side][k] += 1
            left = [a for a in sq.members if a.active and not a.downed and a.vehicle is None]
            if not left and not sq.vehicles:
                if dst is not None and not sal["ht"] and sal["out"] >= max(2, sq.initial * 0.3):
                    dst.units[sq.side][self.SALLY_KIND.get(sq.kind, "inf")] += 1
                    st.note_attack(dst, sq.side, self.sector, planned=True)
                sq.sally = None
                sq.gone = not sq.members
            elif self.turn - sal["turn"] > 2400 or sq.order.kind == "retreat" or sq.state == "rout":
                sq.sally = None                            # couldn't get through: they stay and fight here
                from .ai import Order
                sq.order = Order("hold", issued=self.turn)

    def _front_noise(self):
        """An attack going in next door: you hear it, and at night you see the flashes over the edge."""
        st = self.strategic
        near = st.attacks_near(self.sector) if hasattr(st, "attacks_near") else []
        if not near:
            return
        rng = self.rng
        m = self.map
        heard = self.__dict__.setdefault("front_heard", {})
        for n, at in near:
            e = st.neighbor_dir(self.sector, n)
            if e is None:
                continue
            k = (n.x, n.y)
            heat = 0.5 + 0.5 * min(1.0, power(n.units[at["side"]]) / 12.0) if n.units else 0.5
            if rng.random() > 0.35 * heat:
                continue
            # somewhere in the near half of the next sector, roughly across from you
            p = self.player
            ax = int(max(-10, min(m.w + 10, p.x + rng.gauss(0, 30))))
            ay = int(max(-10, min(m.h + 10, p.y + rng.gauss(0, 22))))
            deep = rng.randint(12, 70)
            x, y = {"N": (ax, -deep), "S": (ax, m.h - 1 + deep), "W": (-deep, ay), "E": (m.w - 1 + deep, ay)}[e]
            r = rng.random()
            if r < 0.55:
                self.distant_sound(x, y, rng.randint(62, 80), "gunfire", "rifle and machine-gun fire")
            elif r < 0.85:
                self.distant_sound(x, y, rng.randint(85, 105), "explosion", "the crump of shells",
                                   power=rng.randint(40, 160))
            else:
                self.distant_sound(x, y, rng.randint(78, 95), "cannon", "tank guns")
            # flashes and smoke over the edge, where you can see it
            near = rng.randint(3, 12)
            bx, by = {"N": (x, -near), "S": (x, m.h - 1 + near), "W": (-near, y), "E": (m.w - 1 + near, y)}[e]
            if r >= 0.55 or self.is_night():
                self.effects.append(dict(t=self.turn, kind="flash", x=bx, y=by))
            marks = self.__dict__.setdefault("front_marks", [])
            if r >= 0.55 and len(marks) < 40:
                marks.append(dict(x=bx, y=by, until=self.turn + rng.randint(60, 240)))
            if heard.get(k, -1e9) < self.turn - 1200:
                heard[k] = self.turn
                from .constants import COMPASS_WORD
                who = "our" if at["side"] == self.player_side else "their"
                self.msg(f"Heavy firing to the {COMPASS_WORD.get(e, e)}: {who} attack on {n.name} has gone in.",
                         "sound")
        marks = self.__dict__.get("front_marks")
        if marks:
            self.front_marks = [mk for mk in marks if mk["until"] >= self.turn]

    def distant_sound(self, x, y, loud, kind, desc, power=0):
        """A sound from off the map - the battle next door: heard, and guessed at, never seen."""
        from .senses import WEATHER_SOUND, direction_word, distance_word
        p = self.player
        if p is None or not p.body.conscious:
            return
        self.audio(kind, x, y, loud, None, power, None)
        lx, ly = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        d = math.hypot(x - lx, y - ly)
        lvl = loud - 20 * math.log10(max(1.0, d)) - WEATHER_SOUND.get(self.weather, 0)
        if p.body.deaf > 0:
            lvl -= 35
        if lvl < HEAR_THRESHOLD:
            return
        err = d * 0.12
        text = self._onomatopoeia(kind, None, power)
        if text:
            self.add_sound_mark(int(x + self.rng.gauss(0, err)), int(y + self.rng.gauss(0, err)), text,
                                3 if kind == "explosion" else 2, kind)
        key = (kind, desc, direction_word(x - lx, y - ly), distance_word(d))
        self._sound_msgs[key] = self._sound_msgs.get(key, 0) + 1

    def go_forward(self, target_key):
        """A staff car (or your own feet) to the front: sector by sector, time passing on the way."""
        st = self.strategic
        s = self.sector
        p = self.player
        if (s.x, s.y) == tuple(target_key):
            return "You're there."
        # the way through our own ground
        from collections import deque
        prev = {(s.x, s.y): None}
        q = deque([(s.x, s.y)])
        goal = tuple(target_key)
        found = False
        while q:
            k = q.popleft()
            if k == goal:
                found = True
                break
            if abs(k[0] - s.x) + abs(k[1] - s.y) > 14:
                continue
            for e, (dx, dy) in EDGE_VEC.items():
                nk = (k[0] + dx, k[1] + dy)
                if nk in prev:
                    continue
                c = st.at(*nk, create=True)
                if c is None or not c.playable:
                    continue
                if nk != goal and c.control != p.side:
                    continue
                prev[nk] = (k, e)
                q.append(nk)
        if not found:
            return "There's no road there through our own lines."
        path = []
        k = goal
        while prev[k] is not None:
            k0, e = prev[k]
            path.append(e)
            k = k0
        path.reverse()
        car = p.rank >= 12 and self.theatre.get("id") not in ("iwojima45", "kohima44")
        hop = 420 if car else 2400
        for i, e in enumerate(path):
            self._skip_time(hop)
            if not p.alive:
                break
            if not self.travel(e):
                break
        return (f"{'Your driver gets you forward' if car else 'You make your way forward'} to "
                f"{self.sector.name} ({len(path)} sector{'s' if len(path) != 1 else ''}, "
                f"about {len(path) * hop // 60} minutes).")

    def _skip_time(self, n):
        """Time on the road: the war goes on without you watching it."""
        t0 = self.turn
        self.turn += n
        for k in range(t0 // STRATEGIC_TICK + 1, self.turn // STRATEGIC_TICK + 1):
            self._strategic_tick()
        for w in self.waves:
            w["turn"] = max(self.turn, w["turn"])

    def _road_edges(self, sector):
        return list(self._road_fracs(sector)) or ["N", "S"]

    def _road_fracs(self, sector):
        """Roads cross each border (or don't) at the same place seen from either side."""
        out = {}
        seed = getattr(self.strategic, "seed", 0)
        for e, (dx, dy) in EDGE_VEC.items():
            n = self.strategic.at(sector.x + dx, sector.y + dy)
            if n is None or not n.playable:
                continue
            a, b = sorted(((sector.x, sector.y), (n.x, n.y)))
            h = hash((seed, a, b)) & 0x7FFFFFFF
            if h % 1000 < 600:
                out[e] = 0.15 + ((h // 1000) % 700) / 1000.0
        return out

    def sector_spec(self, sector):
        """How a sector's battlefield is to be made, as things stand."""
        att, att_edge = self._local_attacker(sector)
        spec = dict(w=self.__dict__.get("map_w", MAP_W), h=self.__dict__.get("map_h", MAP_H),
                    biome=sector.biome if sector.biome != "beach" else "bocage", climate=self.theatre["climate"],
                    seed=sector.seed, attacker_edge=att_edge, defender_side=other_side(att) if att else None,
                    fort=sector.fort if att else 0, river=sector.river, sea_edge=sector.sea_edge,
                    inland=sector.inland, intensity=0.4 + 0.4 * self.theatre.get("intensity", 1),
                    name=sector.name, special=self.theatre.get("special", set()),
                    installations=[(k, s) for k, s, ok in sector.installations if ok],
                    east=self.theatre["sides"][ALLIES][0][0] == "ussr", roads=self._road_edges(sector),
                    road_fracs=self._road_fracs(sector))
        if sector.biome == "beach":
            spec["biome"] = "beach"
        return spec, att, att_edge

    @staticmethod
    def _spec_key(sector, spec):
        return (sector.seed, spec["biome"], spec["attacker_edge"], spec["fort"], spec["river"],
                tuple(spec["installations"]), tuple(spec["roads"]))

    def neighbour_terrain(self, sx, sy):
        """The ground in the sector at (sx, sy), as seen across the edge: (t, var) arrays, or 'sea'.
        Made once and kept (and used for real if you walk in)."""
        cache = self.__dict__.setdefault("_nb_cache", {})
        c = self.strategic.at(sx, sy, create=True)
        if c is None or not c.playable:
            return "sea"
        if c.saved is not None:
            hit = cache.get((sx, sy))
            if hit is None or hit[0] != ("saved", id(c.saved)):
                t = self._unpack(c.saved["t"])
                var = c.saved.get("var")
                hit = cache[(sx, sy)] = (("saved", id(c.saved)), (t, var))
            return hit[1]
        spec, att, ae = self.sector_spec(c)
        key = self._spec_key(c, spec)
        hit = cache.get((sx, sy))
        if hit is None or hit[0] != key:
            hit = cache[(sx, sy)] = (key, generate(spec))
        m = hit[1]
        return (m.t, m.var) if not isinstance(m, tuple) else m

    def __getstate__(self):
        d = dict(self.__dict__)
        d.pop("_nb_cache", None)            # regenerated on demand
        d.pop("_prefs", None)               # the player's settings live in settings.json, not the save
        d.pop("_order_hint", None)
        return d

    def _local_attacker(self, sector):
        st = self.strategic
        pa = power(sector.units[ALLIES])
        pb = power(sector.units[AXIS])
        if pa > 0 and pb > 0:
            if sector.control == ALLIES:
                att = AXIS
            elif sector.control == AXIS:
                att = ALLIES
            else:
                att = self.theatre["attacker"]
        elif pa > 0 or pb > 0:
            att = None
        else:
            att = None
        if sector.biome == "beach" and sector.sea_edge and (att is None or att == self.theatre["attacker"]):
            return (att or self.theatre["attacker"]), sector.sea_edge
        if sector.biome == "beach" and sector.sea_edge and att is not None:
            return att, OPP[sector.sea_edge]
        if att is None:
            return None, None
        # the attacker comes from the sector the attack is going in from (or any next door they hold)
        best = None
        at = st.attack_on(sector.x, sector.y) if hasattr(st, "attack_on") else None
        if at is not None and at["side"] == att and at.get("src"):
            src = st.at(*at["src"])
            if src is not None:
                best = st.neighbor_dir(sector, src)
        if best is not None:
            return att, best
        for e, (dx, dy) in EDGE_VEC.items():
            n = st.at(sector.x + dx, sector.y + dy)
            if n is not None and n.control == att:
                best = e
                break
        if best is None:
            best = self.theatre["attacker_from"] if att == self.theatre["attacker"] else OPP[self.theatre["attacker_from"]]
        return att, best

    def home_edge(self, side):
        if self.attacker is None:
            # quiet sector: each side's edge toward its own territory
            st = self.strategic
            s = self.sector
            for e, (dx, dy) in EDGE_VEC.items():
                n = st.at(s.x + dx, s.y + dy)
                if n is not None and n.control == side:
                    return e
            return self.theatre["attacker_from"] if side == self.theatre["attacker"] else OPP[self.theatre["attacker_from"]]
        if side == self.attacker:
            return self.att_edge
        return self.def_edge

    @staticmethod
    def _pack(a):
        import zlib
        return ("z", a.dtype.str, a.shape, zlib.compress(np.ascontiguousarray(a).tobytes(), 1))

    @staticmethod
    def _unpack(v):
        if isinstance(v, tuple) and v and v[0] == "z":
            import zlib
            return np.frombuffer(zlib.decompress(v[3]), dtype=np.dtype(v[1])).reshape(v[2]).copy()
        return v

    def _save_map(self):
        m = self.map
        s = self.sector
        pk = self._pack
        s.saved = dict(t=pk(m.t), hp=pk(m.hp), blood=pk(m.blood), scorch=pk(m.scorch),
                       items=m.items, mines=m.mines, objectives=m.objectives, explored=pk(m.explored),
                       name=m.name, biome=m.biome, climate=m.climate, buildings=m.buildings, var=m.var)

    def _load_map(self, sector):
        from .gamemap import GameMap
        sv = sector.saved
        up = self._unpack
        t = up(sv["t"])
        m = GameMap(t.shape[0], t.shape[1], sector.seed)
        m.t = t
        m.hp = up(sv["hp"])
        m.blood = up(sv["blood"])
        m.scorch = up(sv["scorch"])
        m.items = sv["items"]
        m.mines = sv["mines"]
        m.objectives = sv["objectives"]
        m.explored = up(sv["explored"])
        m.name, m.biome, m.climate = sv["name"], sv["biome"], sv["climate"]
        m.buildings = sv["buildings"]
        m.var = sv["var"]
        m.gen_positions = []
        m.refresh()
        return m

    def local_units(self) -> dict:
        out = {s: Counter() for s in SIDES}
        for sq in self.squads:
            if sq.side not in out:
                continue
            if getattr(sq, "no_count", False):
                continue
            act = [a for a in sq.members if a.alive and a.state == "ok" and not a.is_player]
            if act and not any(v.vt.vtype == "halftrack" for v in sq.vehicles):
                k = {"rifle": "inf", "assault": "inf", "volkssturm": "inf", "mg": "mg", "mortar": "mortar",
                     "at": "at", "hq": "hq", "sniper": "sniper", "engineer": "eng"}.get(sq.kind, "inf")
                if len(act) >= max(2, sq.initial * 0.3):
                    out[sq.side][k] += 1
            for v in sq.vehicles:
                if v.active:
                    k = "atgun" if v.static else ("ht" if v.vt.vtype == "halftrack" else
                                                   "td" if v.vt.vtype in ("td", "spg") else "tank")
                    if v.vt.vtype in ("truck", "car", "lc", "amtrac", "aagun", "fieldgun"):
                        continue
                    out[sq.side][k] += 1
        for w in self.waves:
            out[w["side"]].update(w["units"])
        return out

    def can_travel(self, edge) -> bool:
        st = self.strategic
        s = self.sector
        dx, dy = EDGE_VEC[edge]
        n = st.at(s.x + dx, s.y + dy, create=True)
        return n is not None and n.playable

    def travel(self, edge):
        st = self.strategic
        s = self.sector
        dx, dy = EDGE_VEC[edge]
        n = st.at(s.x + dx, s.y + dy, create=True)
        if n is None or not n.playable:
            return False
        p = self.player
        # who comes along: nearby squad mates, your prisoners, the man you're carrying
        comp = []
        if p.squad is not None:
            for a in p.squad.members:
                if a is not p and a.active and not a.downed and a.vehicle is None and \
                        max(abs(a.x - p.x), abs(a.y - p.y)) <= 15:
                    comp.append(a)
        from .prisoners import bring_along
        pows = [a for a in bring_along(self, p) if a not in comp]
        carried = p.carrying
        if carried is not None:
            from .actions import put_down
            put_down(self, p)
        vehicle = p.vehicle
        # store what's left behind (the companions and player are no longer part of it)
        old_sq_ref = p.squad
        if old_sq_ref is not None:
            old_sq_ref.members = [m for m in old_sq_ref.members if m not in comp and m is not p]
        self._save_map()
        units = self.local_units()
        s.units = units
        # contested sector control
        if power(units[ALLIES]) > 0 and power(units[AXIS]) == 0:
            st._capture(s, ALLIES)
        elif power(units[AXIS]) > 0 and power(units[ALLIES]) == 0:
            st._capture(s, AXIS)
        # no time skipped: you step straight across into the next stretch of ground
        # remove companions from the old squad
        old_sq = p.squad
        for a in comp:
            a.x = a.y = -1
        if vehicle is not None:
            vehicle.x = vehicle.y = -1
        self.enter_sector(n, entry_edge=OPP[edge])
        # rebuild the player's squad in the new sector
        sq = Squad(p.side, p.nation, old_sq.kind if old_sq else "rifle", old_sq.name if old_sq else "squad")
        sq.player_led = bool(old_sq and old_sq.player_led)
        sq.order = Order("follow") if sq.player_led else Order("hold")
        members = [p] + comp
        sq.members = members
        sq.initial = len(members)
        sq.no_count = True
        old_leader = old_sq.leader if old_sq else None
        sq.leader = old_leader if old_leader in members else (p if sq.player_led else (comp[0] if comp else p))
        for a in members:
            a.squad = sq
        self.squads.append(sq)
        ex, ey = self._edge_entry_point(OPP[edge])
        if vehicle is not None:
            from .spawn import vehicle_spot
            spot = vehicle_spot(self, ex, ey, vehicle.vt, 12, vehicle.body_facing)
            if spot:
                vehicle.x, vehicle.y = spot
            self.add_vehicle(vehicle)
            vehicle.squad = sq
            sq.vehicles.append(vehicle)
            p.x, p.y = vehicle.x, vehicle.y
            self.actors.append(p)
        else:
            from .spawn import place
            place(self, p, ex, ey, 6)
        from .spawn import place
        for a in comp:
            a.ai = {}
            place(self, a, p.x, p.y, 5)
        # prisoners of yours, still prisoners, still yours
        pw_sq = None
        for a in pows:
            keep = {k: a.ai[k] for k in ("captor", "pw_order", "searched") if k in a.ai}
            a.ai = keep
            a.x = a.y = -1
            place(self, a, p.x, p.y, 6)
            if pw_sq is None:
                pw_sq = Squad(a.side, a.nation, "rifle", "prisoners")
                pw_sq.no_count = True
                pw_sq.order = Order("hold")
                self.squads.append(pw_sq)
            a.squad = pw_sq
            pw_sq.members.append(a)
        if pw_sq is not None:
            pw_sq.leader = pw_sq.members[0]
            pw_sq.initial = len(pw_sq.members)
            self.msg(f"Your prisoner{'s come' if len(pows) > 1 else ' comes'} along with you.", "info")
        if carried is not None and carried.alive:
            carried.ai = {k: carried.ai[k] for k in ("captor", "pw_order", "searched") if k in carried.ai}
            carried.x = carried.y = -1
            place(self, carried, p.x, p.y, 2)
            if carried.squad is None or carried.squad not in self.squads:
                carried.squad = sq
                sq.members.append(carried)
            from .actions import pick_up
            pick_up(self, p, carried)
        self.command.organise(self)
        commander_update(self, p.side)
        for b in self.brains.values():
            b.update(force=True)
        self.update_orders(force=True)
        from .world import COUNTRY
        lang = getattr(n, "lang", None)
        crossed = lang and lang != getattr(s, "lang", lang)
        held = "our" if n.control == p.side else "enemy" if n.control else "nobody's"
        self.msg(f"You cross into {n.name}" + (f" - {COUNTRY.get(lang, 'new country')} now" if crossed else "")
                 + (f" ({held} ground)." if p.has_tool("map") else "."), "info")
        self.player_fov()
        return True

    def _edge_entry_point(self, edge):
        m = self.map
        p = self.player
        if edge == "N":
            return (max(2, min(m.w - 3, p.x if p.x > 0 else m.w // 2)), 1)
        if edge == "S":
            return (max(2, min(m.w - 3, p.x if p.x > 0 else m.w // 2)), m.h - 2)
        if edge == "W":
            return (1, max(2, min(m.h - 3, p.y if p.y > 0 else m.h // 2)))
        return (m.w - 2, max(2, min(m.h - 3, p.y if p.y > 0 else m.h // 2)))

    def _place_companions(self, comp, edge):
        pass

    # ================================================================== entity management
    def add_actor(self, a):
        if a not in self.actors:
            self.actors.append(a)
        if a.vehicle is None:
            self.soldier_at[(a.x, a.y)] = a
        self._arr_turn = -1

    def remove_actor(self, a):
        if a in self.actors:
            self.actors.remove(a)
        if self.soldier_at.get((a.x, a.y)) is a:
            del self.soldier_at[(a.x, a.y)]
        self._arr_turn = -1

    def remove_from_map(self, a):
        if self.soldier_at.get((a.x, a.y)) is a:
            del self.soldier_at[(a.x, a.y)]
        self._arr_turn = -1

    def place_on_map(self, a):
        self.soldier_at[(a.x, a.y)] = a
        if a not in self.actors:
            self.actors.append(a)
        self._arr_turn = -1

    def add_vehicle(self, v):
        if v not in self.vehicles:
            self.vehicles.append(v)
        self.place_vehicle(v)

    def place_vehicle(self, v):
        v._cells = v.cells()
        for c in v._cells:
            self.vehicle_at[c] = v

    def lift_vehicle(self, v):
        for c in getattr(v, "_cells", None) or [(v.x, v.y)]:
            if self.vehicle_at.get(c) is v:
                del self.vehicle_at[c]
        if (v.x, v.y) in self.vehicle_at and self.vehicle_at[(v.x, v.y)] is v:
            del self.vehicle_at[(v.x, v.y)]

    def free_around(self, v, prefer_away_from=None):
        """A free tile beside any part of a vehicle (for getting out of it)."""
        m = self.map
        mine = set(v.cells())
        best = None
        bs = -1e9
        for cx, cy in mine:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    xx, yy = cx + dx, cy + dy
                    if (xx, yy) in mine or not m.in_bounds(xx, yy) or not m.walk[xx, yy] or \
                            (xx, yy) in self.soldier_at or (xx, yy) in self.vehicle_at:
                        continue
                    s = self.rng.random()
                    if prefer_away_from is not None:
                        s += math.hypot(xx - prefer_away_from[0], yy - prefer_away_from[1]) * 0.1
                    s -= m.water[xx, yy] * 2
                    if s > bs:
                        bs, best = s, (xx, yy)
        return best

    def free_adjacent(self, x, y, prefer_away_from=None):
        m = self.map
        best = None
        bs = -1e9
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                xx, yy = x + dx, y + dy
                if not m.in_bounds(xx, yy) or not m.walk[xx, yy] or (xx, yy) in self.soldier_at \
                        or (xx, yy) in self.vehicle_at:
                    continue
                s = self.rng.random()
                if prefer_away_from is not None:
                    s += math.hypot(xx - prefer_away_from[0], yy - prefer_away_from[1]) * 0.1
                s -= m.water[xx, yy] * 2
                if s > bs:
                    bs, best = s, (xx, yy)
        return best

    def brain_enemy_center(self, side):
        b = self.brains.get(side)
        return b.enemy_center if b else None

    def actor_array(self):
        if self._arr_turn == self.turn and self._arr is not None:
            return self._arr
        acts = [a for a in self.actors if a.alive and a.vehicle is None]
        pos = np.array([(a.x, a.y) for a in acts], np.float32).reshape(-1, 2)
        self._arr = (pos, acts)
        self._arr_index = {a.id: i for i, a in enumerate(acts)}
        self._arr_turn = self.turn
        self._enemy_arr = {}
        return self._arr

    def near(self, x, y, r, side=None):
        """Soldiers on foot within r tiles (square) of (x, y) - found with arrays, not a loop over everyone."""
        pos, acts = self.actor_array()
        if not acts:
            return []
        idx = np.nonzero((np.abs(pos[:, 0] - x) <= r) & (np.abs(pos[:, 1] - y) <= r))[0]
        return [acts[i] for i in idx if side is None or acts[i].side == side]

    def note_move(self, a):
        """Keep the cached position arrays in step with a soldier who just moved."""
        if self._arr is not None and self._arr_turn == self.turn:
            i = self._arr_index.get(a.id)
            if i is not None:
                self._arr[0][i, 0] = a.x
                self._arr[0][i, 1] = a.y
        for side, (pos, ents) in self._enemy_arr.items():
            for k, e in enumerate(ents):
                if e is a:
                    pos[k, 0] = a.x
                    pos[k, 1] = a.y
                    break

    def enemies_of(self, side):
        pl = self.player
        hidden = pl is not None and pl.ai.get("disguise") and pl.side != side
        out = [a for a in self.actors if a.side != side and a.alive and a.state == "ok" and a.vehicle is None
               and not (hidden and a is pl)] + \
              [v for v in self.vehicles if v.side != side and not v.dead and (v.active or v.static)]
        p = self.player
        if getattr(self, "renegade", False) and p is not None and p.side == side and p.alive and p.state == "ok" \
                and p.vehicle is None:
            out.append(p)                  # a man who murders his own is fair game
        return out

    def enemy_array(self, side):
        self.actor_array()
        cached = self._enemy_arr.get(side)
        if cached is not None:
            return cached
        ents = self.enemies_of(side)
        pos = np.array([(e.x, e.y) for e in ents], np.float32).reshape(-1, 2)
        self._enemy_arr[side] = (pos, ents)
        return pos, ents

    def side_strength(self, side):
        return sum(sq.strength() for sq in self.squads if sq.side == side)

    def side_nation(self, side):
        if side == self.player_side:
            return self.player_nation
        return self.theatre["sides"][side][0][0]

    # ================================================================== time
    def now(self) -> dt.datetime:
        return self.start_dt + dt.timedelta(seconds=self.clock)

    def hour_float(self) -> float:
        n = self.now()
        return n.hour + n.minute / 60 + n.second / 3600

    def month(self) -> int:
        return self.now().month

    def advance_clock(self, seconds):
        self.clock += seconds

    def datetime_str(self, exact=False) -> str:
        n = self.now()
        if exact:
            return n.strftime("%d %B %Y, %H:%M")
        return n.strftime("%d %b %Y %H:%M")

    def time_feel(self) -> str:
        """What you can tell about the time without a watch."""
        h = self.hour_float()
        d = daylight(self)
        if d <= 0:
            return "Night" if not (4 <= h < 6) else "Before dawn"
        if d < 1:
            return "Dawn" if h < 12 else "Dusk"
        if h < 10:
            return "Morning"
        if h < 14:
            return "Midday"
        if h < 17:
            return "Afternoon"
        return "Evening"

    def is_night(self) -> bool:
        return daylight(self) < 0.3

    @property
    def is_dark(self) -> bool:
        return daylight(self) < 0.6

    def update_view_range(self):
        self.view_range_cache = base_view_range(self)

    # ================================================================== messages
    def msg(self, text, cat="info", pos=None, heard=False):
        self.msg_total = getattr(self, "msg_total", 0) + 1
        if pos is not None and not heard and self.player is not None:
            x, y = pos
            if not (self.map.in_bounds(x, y) and self.map.visible[x, y]):
                return
        if self.messages and self.messages[-1].text == text and self.messages[-1].turn >= self.turn - 3:
            self.messages[-1].count += 1
            self.messages[-1].turn = self.turn
            return
        self.messages.append(Message(text, cat, self.turn))
        if cat == "radio":
            self._radio_voice(text)

    def _radio_voice(self, text):
        """Radio traffic you hear is spoken, through the set."""
        import re
        from .data.phrases import lang
        p = self.player
        if p is None:
            return
        m = re.search(r"'(.+)'", text)
        if not m:
            return
        line = m.group(1)
        mine = text.startswith("You")
        who = text.split(":")[0]
        nation = p.nation
        if lang(nation) != "en" and not is_native(nation, line):
            return            # the report is in the game's language, not his: the set just crackles
        self.audio("voice", p.x, p.y, 62, extra=dict(text=line, nation=nation, sid=("radio", who) if not mine else p.id,
                                                      female=p.female if mine else False, role="",
                                                      style="talk" if mine else "radio", own=mine))

    def _collect_speech(self):
        """Every line spoken this turn becomes a sound (the audio system decides who hears it)."""
        for a in self.actors:
            sp = a.__dict__.get("spoken")
            if sp is None:
                continue
            a.spoken = None
            line, turn, tone = sp
            if not line or not a.alive or (a.vehicle is not None and a is not self.player and
                                           (self.player is None or self.player.vehicle is not a.vehicle)):
                continue
            self.audio("voice", a.x, a.y, 50 if tone == "talk" else 66,
                       extra=dict(text=line, nation=a.nation, sid=a.id, female=a.female, role=a.role,
                                  style=tone, own=a.is_player))

    def msg_near(self, x, y, text, cat="info"):
        if self.player is not None and math.hypot(x - self.player.x, y - self.player.y) < 25:
            self.msg(text, cat)

    def msg_for(self, actor, patient, verb, cat="info"):
        if actor.is_player:
            self.msg(f"You {verb}.", cat)
        elif patient.is_player:
            self.msg(f"{cap(self.name_of(actor))} {verb}.", cat)
        elif self.can_see(actor.x, actor.y):
            self.msg(f"{cap(self.name_of(actor))} {verb}.", cat)

    def can_see(self, x, y) -> bool:
        m = self.map
        return self.player is not None and m.in_bounds(x, y) and bool(m.visible[x, y])

    def name_of(self, a) -> str:
        if a is None:
            return "someone"
        if getattr(a, "vt", None) is not None:
            return self.name_of_vehicle(a)
        if a.is_player:
            return "you"
        p = self.player
        if p is not None and a.side == p.side:
            if a.squad is not None and a.squad is p.squad:
                return f"{a.rank_short} {a.last_name}"
            return f"{an(NATIONS[a.nation]['adj'])} {a.role_name.lower()}"
        return f"{an(NATIONS[a.nation]['adj'])} {a.role_name.lower()}"

    def name_of_vehicle(self, v) -> str:
        p = self.player
        if p is not None and v.side == p.side:
            return f"the friendly {v.vt.name}"
        return f"the {NATIONS[v.nation]['adj']} {v.vt.name}"

    def shout(self, a, key) -> str:
        sh = NATIONS[a.nation]["shouts"].get(key)
        if not sh:
            return "!"
        return self.rng.choice(sh)

    def report_hit(self, a, attacker, pname, res, kind, source):
        p = self.player
        if a.is_player:
            self.audio("thud", a.x, a.y, 70)
            if res.get("dead"):
                return
            verb = {"gunshot": "A round tears into", "fragment": "Shrapnel rips into", "blast": "The blast batters",
                    "burn": "Fire sears", "cut": "A blade slashes", "blunt": "Something smashes into"}.get(kind, "Something hits")
            sev = res["dmg"]
            tail = "!" if sev < 25 else " - it's bad!" if sev < 45 else " - oh God!"
            self.msg(f"{verb} your {pname}{tail}", "hurt")
            if res.get("disabled"):
                self.msg(f"Your {pname} won't work anymore.", "hurt")
            if res.get("knocked_out"):
                self.msg("The world goes white...", "hurt")
            return
        seen = self.can_see(a.x, a.y)
        if attacker is p or (p is not None and p.vehicle is not None and attacker is p.vehicle):
            if res.get("dead"):
                return
            if seen:
                self.msg(f"You hit {self.name_of(a)} in the {pname}!", "hit")
            return
        if seen and not res.get("dead"):
            if a.side == p.side and a.squad is p.squad:
                self.msg(f"{cap(self.name_of(a))} is hit in the {pname}!", "warn")
            elif self.rng.random() < 0.35:
                self.msg(f"{cap(self.name_of(a))} is hit.", "combat")

    # ================================================================== death & wounds
    def on_wounded(self, a, attacker, res):
        if a.is_player:
            self.stats["wounds"] += 1
            self.command.on_wounded(self)
            return
        if res["dmg"] > 15 and self.rng.random() < 0.5:
            a.say(self.shout(a, "pain"), self.turn, 2, tone="scream")
        if a.squad is not None:
            for m in a.squad.members:
                if m.active:
                    m.morale -= 0.8
        a.morale -= 4

    def kill(self, a, killer):
        if a.body.dead is False:
            a.body.dead = True
        if getattr(a, "_killed", False):
            return
        a._killed = True
        m = self.map
        seen = self.can_see(a.x, a.y) or a.is_player
        if killer is not None and hasattr(killer, "kills") and killer is not a:
            killer.kills += 1
            if killer is self.player or (self.player is not None and killer is self.player.vehicle):
                self.stats["kills"] += 1
                self.kills_by[a.nation] += 1
                self.command.on_kill(self, a)
        if a.is_player:
            self.player_died(killer)
            return
        if seen:
            if killer is self.player:
                self.msg(f"You kill {self.name_of(a)}.", "hit")
            elif self.player is not None and a.squad is self.player.squad:
                self.msg(f"{a.full_name} is dead.", "death")
            else:
                self.msg(f"{cap(self.name_of(a))} goes down and doesn't move.", "combat")
        # the weapon in his hands falls; everything else stays on the body to be searched
        if a.vehicle is None and m.in_bounds(a.x, a.y) and not (m.walk[a.x, a.y] or T.DOOR[m.t[a.x, a.y]]):
            # he died on something you can't walk onto (a burning wreck): he and his kit fall beside it
            from .spawn import free_tile_near
            spot = free_tile_near(self, a.x, a.y, 3)
            if spot is not None:
                if self.soldier_at.get((a.x, a.y)) is a:
                    del self.soldier_at[(a.x, a.y)]
                a.x, a.y = spot
        if a.vehicle is None and m.in_bounds(a.x, a.y):
            for it in list(a.inv):
                if it.data and it.data.get("live") is not None:
                    a.invent.remove(it)
                    self.drop_live(it, a.x, a.y)
                    m.add_item(a.x, a.y, it)
            w = a.weapon
            if w is not None:
                a.invent.remove(w)
                m.add_item(a.x, a.y, w)
            if a.invent.hands is not None:
                m.add_item(a.x, a.y, a.invent.hands)
                a.invent.hands = None
            m.add_item(a.x, a.y, make_corpse(a))
            m.blood[a.x, a.y] = 255
        a.weapon = None
        # let go of (or be let go by) whoever was carrying
        if a.carrying is not None:
            from .actions import put_down
            put_down(self, a)
        cb = a.ai.get("carried_by")
        if cb is not None:
            for o in self.actors:
                if o.id == cb and o.carrying is a:
                    o.carrying = None
        self.remove_actor(a)
        if a.vehicle is not None:
            v = a.vehicle
            if a in v.passengers:
                v.passengers.remove(a)
            if a in v.crew_actors:
                v.crew_actors.remove(a)
        # morale shock
        for o in self.actors:
            if o.side == a.side and o.alive and abs(o.x - a.x) + abs(o.y - a.y) < 10:
                o.morale -= 1.5 if o.squad is not a.squad else 4
            elif o.side != a.side and o.alive and abs(o.x - a.x) + abs(o.y - a.y) < 20:
                o.morale += 0.5
        if self.player is not None and a.squad is not None and a.squad is self.player.squad:
            self.player.morale -= 6
        # losing an officer shakes everyone who saw it
        if a.rank >= 8:
            witness = None
            for o in self.actors:
                if o.side == a.side and o.active and abs(o.x - a.x) + abs(o.y - a.y) < 14:
                    o.morale -= 6
                    if witness is None and not o.is_player:
                        witness = o
            if witness is not None and self.rng.random() < 0.7:
                from .data.phrases import phrase
                witness.say(phrase(self.rng, witness.nation, "lt_down" if a.rank < 10 else "capt_down"), self.turn, 3)

    def player_died(self, killer):
        p = self.player
        b = p.body
        self.game_over = True
        cause = b.cause or "wounds"
        where = f"{self.sector.name}"
        who = ""
        k = killer if killer is not None else b.killer
        if k is not None and getattr(k, "vt", None) is not None:
            who = f", fired by {an(NATIONS[k.nation]['adj'])} {k.vt.name}"
        elif k is not None and hasattr(k, "nation"):
            who = f", fired by {an(NATIONS[k.nation]['adj'])} {k.role_name.lower()}"
            if k.side == p.side:
                who += " - one of your own"
        self.death_text = (f"{p.rank_full} {p.name}, {p.unit}. Killed by {cause}{who}, "
                           f"near {where}, {self.datetime_str(exact=True)}.")
        award = self.command.posthumous(self)
        if award:
            self.death_text += f" Posthumously awarded the {award}."
        self.msg("You die...", "death")
        self.write_memorial()

    def write_memorial(self):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            p = self.player
            with open(os.path.join(SAVE_DIR, "memorial.txt"), "a", encoding="utf-8") as f:
                f.write("=" * 70 + "\n")
                f.write((self.death_text or self.victory_text or "") + "\n")
                f.write(f"  {self.theatre['name']}: {self.theatre['battle']}\n")
                f.write(f"  Role: {p.role_name}. Kills: {self.stats['kills']}. Wounds: {self.stats['wounds']}. "
                        f"Survived {self.clock // 60} minutes of battle across {len(self.sector_log)} sector(s).\n")
                cmd = getattr(self, "command", None)
                if cmd is not None and cmd.medals:
                    f.write(f"  Decorations: {', '.join(cmd.medals)}.\n")
                if cmd is not None and cmd.promotions:
                    f.write(f"  Promoted {len(cmd.promotions)} time(s) in the field.\n")
        except OSError:
            pass

    def surrender(self, a):
        if a.state != "ok":
            return
        a.state = "surrendered"
        a.say(self.shout(a, "surrender"), self.turn, 5)
        if a.weapon is not None and self.map.in_bounds(a.x, a.y):
            self.map.add_item(a.x, a.y, a.weapon)
            a.remove_item(a.weapon)
        a.stance = 0
        if self.can_see(a.x, a.y):
            self.msg(f"{cap(self.name_of(a))} throws down {a.his} weapon and raises {a.his} hands!", "good")
        self.brains[other_side(a.side)].contacts.pop(a.id, None)
        if self.player is not None and a.side != self.player.side:
            self.duty.on_surrender_near(self, a)

    def exit_map(self, a, how):
        if a.is_player:
            return
        self.remove_actor(a)
        a.state = "fled" if how != "captured" else "captured"
        if how == "captured":
            self.captured[other_side(a.side)] += 1
            if self.player is not None and a.ai.get("captor") == self.player.id:
                self.duty.on_prisoner_delivered(self, a)
        # survivors go back to the strategic pool
        if how in ("withdrew", "fled"):
            e = self.home_edge(a.side)
            if e:
                dx, dy = EDGE_VEC[e]
                n = self.strategic.at(self.sector.x + dx, self.sector.y + dy)
                if n is not None and a.squad is not None and a.squad.leader is a:
                    n.units[a.side]["inf"] += 1

    def bail_out(self, v, survivors, catastrophic):
        from .spawn import make_soldier
        rng = self.rng
        # passengers get out (or burn)
        for p in list(v.passengers):
            v.passengers.remove(p)
            p.vehicle = None
            spot = self.free_around(v, self.brain_enemy_center(v.side))
            if spot is None or (catastrophic and rng.random() < 0.6):
                hit_actor(self, p, rng.uniform(40, 120), "burn", None, f"a burning {v.vt.name}")
                if p.alive:
                    p.body.dead = True
                    p.body.cause = f"burns in a burning {v.vt.name}"
                    self.kill(p, None)
                continue
            p.x, p.y = spot
            self.place_on_map(p)
            p.stance = 2
            p.suppression = 80
        # the player inside
        pl = self.player
        if pl is not None and pl.vehicle is v:
            spot = self.free_around(v, self.brain_enemy_center(v.side))
            if catastrophic or spot is None or rng.random() < 0.15:
                pl.body.cause = f"the destruction of your {v.vt.name}"
                hit_actor(self, pl, rng.uniform(80, 200), "burn", None, f"a burning {v.vt.name}")
                if pl.alive:
                    pl.body.dead = True
                    self.kill(pl, None)
                return
            v.crew_actors = [c for c in v.crew_actors if c is not pl]
            v.player_crewed = False
            v.player_station = None
            pl.vehicle = None
            pl.x, pl.y = spot
            self.place_on_map(pl)
            pl.stance = 2
            self.msg(f"You haul yourself out of the hatch of the stricken {v.vt.name} and drop to the ground!", "warn")
            if rng.random() < 0.5:
                hit_actor(self, pl, rng.uniform(5, 25), "burn", None, "flames")
            survivors = max(0, survivors - 1)
        # AI crew bail out as soldiers
        crew_sq = None
        for i in range(survivors):
            spot = self.free_around(v, self.brain_enemy_center(v.side))
            if spot is None:
                break
            c = make_soldier(self, v.nation, "tank_crew")
            c.x, c.y = spot
            c.stance = 2
            c.suppression = 70
            if crew_sq is None:
                crew_sq = Squad(v.side, v.nation, "rifle", f"{v.vt.name} crew")
                crew_sq.order = Order("retreat", issued=self.turn)
                self.squads.append(crew_sq)
            c.squad = crew_sq
            crew_sq.members.append(c)
            self.add_actor(c)
            if rng.random() < 0.4:
                c.body.damage(rng, rng.choice(("l_arm", "r_arm", "torso", "l_leg")), rng.uniform(5, 30), "burn")
        if crew_sq:
            crew_sq.leader = crew_sq.members[0]
        v.crew = 0

    def disembark_all(self, v):
        for p in list(v.passengers):
            spot = self.free_around(v, None)
            if spot is None:
                # jump into the water off the side
                m = self.map
                for cx, cy in v.cells():
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            xx, yy = cx + dx, cy + dy
                            if m.in_bounds(xx, yy) and (xx, yy) not in self.soldier_at and \
                                    (xx, yy) not in self.vehicle_at and (m.walk[xx, yy] or m.water[xx, yy] >= 2):
                                spot = (xx, yy)
                if spot is None:
                    continue
            v.passengers.remove(p)
            p.vehicle = None
            p.x, p.y = spot
            self.place_on_map(p)
            p.stance = 1
            if p.is_player:
                self.msg("You pile out!", "warn")
        if v.squad is not None and v.squad.members:
            sq = v.squad
            if v in sq.vehicles and v.vt.vtype in ("lc", "truck", "car"):
                sq.vehicles.remove(v)
            if sq.order.kind == "attack" and sq.order.obj is None:
                commander_update(self, sq.side)

    # ================================================================== vehicles
    def _vehicle_room(self, v, x, y, facing):
        """Can the vehicle stand here, facing so?  Returns (cells, things to crush, men to run over) or None."""
        m = self.map
        vt = v.vt
        cells = v.cells(x, y, facing)
        crush = []
        victims = []
        for cx, cy in cells:
            if not m.in_bounds(cx, cy):
                return None
            o = self.vehicle_at.get((cx, cy))
            if o is not None and o is not v:
                return None
            tid = int(m.t[cx, cy])
            d = T.DEFS[tid]
            if vt.water == "water":
                if d.water < 1:
                    return None
            elif d.water >= 2 and vt.water != "amphib":
                return None
            if not d.walk and d.water < 1:
                if d.crush == 0 or d.crush > vt.crush:
                    return None
                crush.append((cx, cy))
            a = self.soldier_at.get((cx, cy))
            if a is not None and a.alive:
                victims.append(a)
        return cells, crush, victims

    def _clear_of(self, a, cells):
        """A free tile next to a soldier that's out of the way of a vehicle's new footprint."""
        m = self.map
        opts = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                xx, yy = a.x + dx, a.y + dy
                if (dx or dy) and (xx, yy) not in cells and m.in_bounds(xx, yy) and m.walk[xx, yy] and \
                        (xx, yy) not in self.soldier_at and (xx, yy) not in self.vehicle_at and m.water[xx, yy] < 2:
                    opts.append((xx, yy))
        return self.rng.choice(opts) if opts else None

    def turn_vehicle(self, v, facing) -> bool:
        """Swing the hull round on the spot, if there's room."""
        facing %= 8
        if facing == v.facing:
            return True
        if v.vt.static:
            v.facing = facing
            return True
        room = self._vehicle_room(v, v.x, v.y, facing)
        if room is None or room[1] or room[2]:
            return False
        self.lift_vehicle(v)
        v.facing = facing
        self.place_vehicle(v)
        return True

    def try_move_vehicle(self, v, dx, dy, reverse=False):
        """Drive one tile.  Returns the time it took, or None if the way is blocked."""
        from .gamemap import octant
        m = self.map
        nx, ny = v.x + dx, v.y + dy
        if not m.in_bounds(nx, ny):
            return None
        vt = v.vt
        want = v.facing if (reverse or vt.static) else octant(dx, dy)
        # the heading we want - or, where there isn't room to swing, part of the way round, or none
        cands = [want]
        if want != v.facing:
            diff = (want - v.facing) % 8
            step = 1 if diff <= 4 else -1
            cands += [(v.facing + step) % 8, v.facing]
        room = None
        for f in cands:
            room = self._vehicle_room(v, nx, ny, f)
            if room is not None:
                break
        if room is None:
            if vt.water == "water":
                v.stuck += 1
            return None
        cells, crush, victims = room
        old = set(getattr(v, "_cells", None) or v.cells())
        # men in the way: the enemy may be run down; our own scramble clear (but not the wounded)
        newset = set(cells)
        for o in victims:
            if o.side != v.side:
                if o.downed or self.rng.random() < 0.3:
                    o.body.cause = f"being crushed under a {vt.name}"
                    hit_actor(self, o, 200, "blunt", v, f"the tracks of a {vt.name}")
                    if o.alive:
                        return 100
                    continue
                return None
            if o.downed or o.is_player or not o.active:
                return None
            spot = self._clear_of(o, newset)
            if spot is None:
                return None
            del self.soldier_at[(o.x, o.y)]
            o.x, o.y = spot
            self.soldier_at[spot] = o
            self.note_move(o)
            if self.rng.random() < 0.05:
                o.say(self.rng.choice(["Watch it!", "Christ!", "Hey!"]) if o.nation in (
                    "usa", "uk", "canada", "australia", "newzealand") else "!", self.turn)
        cost = v.move_cost(int(np.mean([T.VCOST[int(m.t[cx, cy])] for cx, cy in cells])))
        # smash through what's in the way
        for cx, cy in crush:
            if (cx, cy) in old:
                continue
            tid = int(m.t[cx, cy])
            d = T.DEFS[tid]
            if d.key == "hedge" and self.rng.random() < 0.25:
                v.stuck += 1
                if self.can_see(v.x, v.y):
                    self.msg(f"{cap(self.name_of_vehicle(v))} rears up on the hedgerow, exposing its belly.", "combat")
                return 300
            m.t[cx, cy] = T.INTO[tid]
            m.hp[cx, cy] = T.HP[m.t[cx, cy]]
            self.terrain_dirty = True
            self.emit_sound(cx, cy, 60, "crash", f"a {vt.name} smashing through {d.name}", v.side, v)
            cost += 150
        self.lift_vehicle(v)
        v.facing = f
        v.x, v.y = nx, ny
        self.place_vehicle(v)
        v.moved_turn = self.turn
        v.stuck = 0
        for p in v.passengers + v.crew_actors:
            p.x, p.y = nx, ny
        # mines under any new part of it
        for cx, cy in cells:
            if (cx, cy) in old:
                continue
            mn = m.mines.get((cx, cy))
            if mn is not None and (mn.kind == "at" or self.rng.random() < 0.4):
                del m.mines[(cx, cy)]
                from .combat import hit_vehicle
                self.msg("A mine detonates under a vehicle!", "death", (cx, cy))
                explode(self, cx, cy, 120 if mn.kind == "at" else 50, 2, frags=10, source="a mine", self_vehicle=v)
                hit_vehicle(self, v, 60 if mn.kind == "at" else 10, 150, cx, cy, None, "a mine", kind="ap", face=3)
                if mn.kind == "at":
                    v.tracks = False
                break
        if self.rng.random() < 0.3:
            self.emit_sound(nx, ny, 55 if vt.vtype in ("tank", "td", "spg", "ltank") else 45, "engine",
                            f"the clank and rumble of {'tracks' if vt.vtype in ('tank', 'td', 'spg', 'ltank', 'halftrack', 'tankette') else 'an engine'}",
                            v.side, v)
        return cost

    def move_vehicle(self, v, dx, dy, reverse=False) -> int:
        c = self.try_move_vehicle(v, dx, dy, reverse)
        return 100 if c is None else c

    # ================================================================== explosives
    def land_explosive(self, item, x, y, thrower, cook=0, placed_charge=False):
        t = item.t
        m = self.map
        if t.kind == "grenade" and (t.gtype in ("molotov", "gammon", "at") or t.fuse <= 1):
            self._detonate_item(item, x, y, thrower)
            return
        fuse = max(1, t.fuse - cook + self.rng.randint(-1, 1 if t.id not in ("type97", "type99_gr") else 3))
        item.data = dict(item.data or {}, live=fuse)
        m.add_item(x, y, item)
        self.explosives.append(dict(item=item, x=x, y=y, fuse=fuse, thrower=thrower, holder=None,
                                    placed=placed_charge))
        if self.player and math.hypot(x - self.player.x, y - self.player.y) < 3 and thrower is not self.player:
            self.msg("A grenade lands right next to you!" if t.kind == "grenade" else "A charge lands beside you!",
                     "death")

    def pick_live(self, item, a):
        for e in self.explosives:
            if e["item"] is item:
                e["holder"] = a
                if a.is_player:
                    self.msg(f"You snatch up the live {item.t.name}! THROW IT!", "death")

    def drop_live(self, item, x, y):
        for e in self.explosives:
            if e["item"] is item:
                e["holder"] = None
                e["x"], e["y"] = x, y

    def explosive_danger(self, x, y, r):
        best = None
        bd = r + 0.5
        for e in self.explosives:
            if e["holder"] is not None:
                continue
            d = math.hypot(e["x"] - x, e["y"] - y)
            if d < bd and e["item"].t.blast_r > 0:
                bd, best = d, (e["x"], e["y"])
        return best

    def _tick_explosives(self):
        keep = []
        for e in self.explosives:
            e["fuse"] -= 1
            it = e["item"]
            if e["fuse"] > 0:
                if it.data is not None:
                    it.data["live"] = e["fuse"]
                keep.append(e)
                continue
            h = e["holder"]
            if h is not None:
                if it in h.inv or h.weapon is it:
                    h.remove_item(it)
                x, y = h.x, h.y
                if h.vehicle is not None:
                    x, y = h.vehicle.x, h.vehicle.y
            else:
                x, y = e["x"], e["y"]
                self.map.remove_item(x, y, it)
                # thrown back by the player, or picked up and thrown by anyone: find it
            if it.t.dud and self.rng.random() < it.t.dud:
                it.data = {"dud": True}
                self.map.add_item(x, y, it)
                if self.can_see(x, y):
                    self.msg(f"The {it.t.name} fizzles. A dud.", "info", (x, y))
                continue
            self._detonate_item(it, x, y, e["thrower"])
        self.explosives = keep

    def _detonate_item(self, item, x, y, thrower):
        t = item.t
        m = self.map
        if t.kind == "grenade" and t.gtype == "molotov":
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    ignite(self, x + dx, y + dy, 3)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    a = self.soldier_at.get((x + dx, y + dy))
                    if a is not None and a.alive:
                        a.body.burning = max(a.body.burning, 4)
                        hit_actor(self, a, self.rng.uniform(10, 30), "burn", thrower, "a Molotov cocktail")
            v = self.vehicle_at.get((x, y))
            if v is not None and not v.dead and self.rng.random() < 0.35:
                v.burning = max(v.burning, 25)
                self.msg(f"Flames lick over the engine deck of {self.name_of_vehicle(v)}!", "combat", v.pos)
            self.emit_sound(x, y, 40, "glass", "a bottle smashing and the whoomp of fuel", None, thrower)
            self.effect_explosion(x, y, 1)
            return
        if t.smoke:
            self.smoke_sources.append([x, y, 25, t.smoke / 10.0])
            self.emit_sound(x, y, 25, "smoke", "the hiss of a smoke grenade", None, thrower)
        if t.fire:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if self.rng.random() < 0.6:
                        ignite(self, x + dx, y + dy, t.fire)
        if t.blast > 0:
            pen = t.pen
            v = self.vehicle_at.get((x, y))
            if item.data and item.data.get("on_vehicle"):
                for vv in self.vehicles:
                    if vv.id == item.data["on_vehicle"] and not vv.dead:
                        x, y = vv.x, vv.y
            explode(self, x, y, t.blast, t.blast_r, frags=t.frags, frag_dmg=t.frag_dmg, pen=pen,
                    attacker=thrower, source=f"a {t.name}", crater=t.kind == "explosive")

    def schedule_shell(self, x, y, flight, power, radius, frags, frag_dmg, attacker, source,
                       whistle=True, sound=None, side=None, fire=0, pen=0):
        self.shells.append(dict(x=x, y=y, t=self.turn + flight, power=power, radius=radius, frags=frags,
                                frag_dmg=frag_dmg, attacker=attacker, source=source, whistle=whistle,
                                sound=sound, side=side, fire=fire, pen=pen))

    def _tick_shells(self):
        keep = []
        warned = False
        m = self.map
        p = self.player
        for s in self.shells:
            dtt = s["t"] - self.turn
            if dtt == 1 and s["whistle"]:
                # the whistle: everyone near drops flat
                for a in self.actors:
                    if a.alive and a.vehicle is None and abs(a.x - s["x"]) <= s["radius"] + 4 and \
                            abs(a.y - s["y"]) <= s["radius"] + 4 and not a.is_player:
                        if a.stance < 2 and self.rng.random() < 0.8:
                            a.stance = 2
                        a.suppression = min(100, a.suppression + 15)
                if p is not None and math.hypot(s["x"] - p.x, s["y"] - p.y) < 30:
                    self.audio("shell", s["x"], s["y"], 72)
                if p is not None and not warned and math.hypot(s["x"] - p.x, s["y"] - p.y) < 22 and p.body.deaf <= 0:
                    warned = True
                    self.msg(f"INCOMING! You hear {s['sound'] or 'the shriek of an incoming shell'}!", "death")
                    self.add_sound_mark(s["x"], s["y"], "!", 1, "shell")
            if dtt <= 0:
                x, y = s["x"], s["y"]
                if m.in_bounds(x, y):
                    explode(self, x, y, s["power"], s["radius"], frags=s["frags"], frag_dmg=s["frag_dmg"],
                            attacker=s["attacker"], source=s["source"], fire=s["fire"], pen=s["pen"])
                continue
            keep.append(s)
        self.shells = keep

    def _tick_pending(self):
        keep = []
        for pe in self.pending_explosions:
            pe[5] -= 1
            if pe[5] > 0:
                keep.append(pe)
                continue
            x, y, pw, r, fire = pe[:5]
            src = "a bouncing S-mine" if len(pe) > 6 and pe[6] == "smine" else "secondary explosions"
            if len(pe) > 6 and pe[6] == "smine":
                explode(self, x, y, pw, r, frags=36, frag_dmg=24, source=src, crater=False, air_burst=True)
            else:
                explode(self, x, y, pw, r, frags=int(pw / 8), frag_dmg=22, source=src, fire=fire)
                if self.can_see(x, y):
                    self.msg("Stored munitions cook off in a chain of blasts!", "warn", (x, y))
        self.pending_explosions = keep

    # ================================================================== sound
    def audio(self, kind, x, y, loud=60, weapon=None, power=0, extra=None):
        """Queue a sound for the audio system (it decides what the player actually hears)."""
        ev = getattr(self, "audio_events", None)
        if ev is None:
            ev = self.audio_events = []
        if len(ev) < 400:
            ev.append((kind, weapon, x, y, loud, power, self.turn, extra))

    def emit_sound(self, x, y, loud, kind, desc, side, source, weapon=None, power=0, extra=None):
        m = self.map
        if not m.in_bounds(x, y):
            return
        if kind == "engine" and source is not None and getattr(source, "vt", None) is not None:
            extra = "wheels" if source.vt.vtype in ("truck", "car", "armcar") else None
        self.audio(kind, x, y, loud, weapon, power, extra)
        p = self.player
        if loud >= 50 and p is not None and kind != "shout":
            d = abs(p.x - x) + abs(p.y - y)
            if d < 40:
                self.noise = min(100.0, self.noise + loud / (12.0 + d))
        # AI hearing: each side hears it at its nearest soldier
        for s in SIDES:
            if side == s:
                continue
            pos, acts = self.actor_array()
            if not acts:
                continue
            d2 = (pos[:, 0] - x) ** 2 + (pos[:, 1] - y) ** 2
            best = None
            side_idx = [k for k, a in enumerate(acts) if a.side == s and a.active]
            if side_idx:
                k = min(side_idx, key=lambda k: d2[k])
                best = acts[k]
            if best is None:
                continue
            lvl = sound_at(self, x, y, loud, best.x, best.y)
            if lvl < HEAR_THRESHOLD + (30 if best.body.deaf else 0):
                continue
            if source is not None and kind in ("gunfire", "cannon", "rocket", "flamer", "mortar",
                                               "footsteps", "engine", "reload", "digging", "wire",
                                               "whistle", "scream", "door", "crash", "flare"):
                dd = math.sqrt(float(d2[k]))
                err = dd * 0.12
                ex = int(x + self.rng.gauss(0, err))
                ey = int(y + self.rng.gauss(0, err))
                self.brains[s].report(None, self.turn, sound=True, x=max(0, min(m.w - 1, ex)),
                                      y=max(0, min(m.h - 1, ey)))
                # squads nearby perk up
                if best.squad is not None and dd < 40 and kind not in ("footsteps",):
                    best.squad.last_contact = max(best.squad.last_contact, self.turn - 20)
        # the player
        p = self.player
        if p is None or source is p or not p.body.conscious:
            return
        lx, ly = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        lvl = sound_at(self, x, y, loud, lx, ly)
        if p.body.deaf > 0:
            lvl -= 35
        if lvl < HEAR_THRESHOLD:
            return
        seen = m.visible[x, y] and kind not in ("explosion", "shell")
        if source is not None and hasattr(source, "side") and source.side == p.side and kind in ("footsteps", "reload", "digging"):
            return
        d = math.hypot(x - lx, y - ly)
        if not seen or kind in ("explosion",):
            err = d * 0.12
            mx = int(x + self.rng.gauss(0, err))
            my = int(y + self.rng.gauss(0, err))
            text = self._onomatopoeia(kind, weapon, power)
            if text:
                self.add_sound_mark(mx, my, text, 2 if kind != "explosion" else 3, kind)
            if kind in ("footsteps",) and d > 10:
                return
            key = (kind, desc, direction_word(x - lx, y - ly), distance_word(d))
            self._sound_msgs[key] = self._sound_msgs.get(key, 0) + 1

    def _onomatopoeia(self, kind, weapon, power):
        if kind == "gunfire" and weapon:
            cat = ITEMS[weapon].cat if weapon in ITEMS else ""
            if cat in ("lmg", "hmg"):
                return "brrrt"
            if cat in ("smg", "assault"):
                return "rat-tat"
            return "crack"
        if kind == "explosion":
            return "BOOM" if power >= 150 else "bang"
        return ONOMATOPOEIA.get(kind, "")

    def add_sound_mark(self, x, y, text, ttl, kind):
        col = {"gunfire": (230, 200, 120), "explosion": (255, 120, 60), "shell": (255, 60, 60),
               "footsteps": (150, 150, 170), "engine": (170, 170, 200), "scream": (255, 150, 150),
               "shout": (240, 240, 170)}.get(kind, (200, 200, 220))
        self.sound_marks.append(SoundMark(x, y, text, self.turn + ttl, kind, col))

    SOUND_CAT = {"gunfire": "gunfire", "cannon": "cannon fire", "explosion": "explosions",
                 "mortar": "mortars firing", "rocket": "rockets", "flamer": "a flamethrower",
                 "engine": "engines", "crash": "something heavy smashing through", "scream": "screaming",
                 "whistle": "a whistle", "footsteps": "movement", "reload": "movement",
                 "digging": "digging", "wire": "someone on the wire", "glass": "breaking glass",
                 "ricochet": "ricochets", "penetration": "armour being hit", "ping": "a Garand clip",
                 "melee": "hand-to-hand fighting", "door": "a door", "flare": "a flare pistol",
                 "smoke": "a smoke grenade", "aircraft": "aircraft", "click": "a click", "ramp": "a ramp"}

    def _flush_sound_msgs(self):
        if not self._sound_msgs:
            return
        mode = (self.__dict__.get("_prefs") or {}).get("sound_log", "all")
        if mode != "all":
            # the Options screen: only what's close (or nothing at all) goes in the log
            keep = ("very close", "close by", "nearby") if mode == "near" else ()
            self._sound_msgs = {k: n for k, n in self._sound_msgs.items() if k[3] in keep}
            if not self._sound_msgs:
                return
        p = self.player
        compass = p is not None and (p.has_tool("compass") is not None or p.has_tool("map") is not None)
        if not hasattr(self, "_sound_last"):
            self._sound_last = {}
        # bucket by category, direction and distance
        buckets = {}
        for (kind, desc, dirw, distw), n in self._sound_msgs.items():
            cat = self.SOUND_CAT.get(kind, kind)
            b = buckets.setdefault((cat, dirw, distw), [0, []])
            b[0] += n
            if desc not in b[1]:
                b[1].append(desc)
        out = sorted(buckets.items(), key=lambda kv: (kv[0][2] != "very close", kv[0][2] != "close by", -kv[1][0]))
        shown = 0
        for (cat, dirw, distw), (n, descs) in out:
            key = (cat, dirw, distw)
            last = self._sound_last.get(key)
            new_descs = [d for d in descs if last is None or d not in last[1]]
            if last is not None and self.turn - last[0] < 8 and not new_descs:
                continue
            self._sound_last[key] = (self.turn, set(descs) | (last[1] if last else set()))
            where = f"to the {dirw}" if compass else f"off to the {dirw}"
            if self.__dict__.get("domain") == "aboard":
                # aboard, the bow is to the right of the plan: a sailor's directions
                where = {"E": "ahead", "W": "astern", "N": "to port", "S": "to starboard", "NE": "off the port bow",
                         "SE": "off the starboard bow", "NW": "off the port quarter",
                         "SW": "off the starboard quarter"}.get(dirw, where)
            detail = ""
            if cat in ("gunfire", "cannon fire", "explosions") and descs:
                detail = " (" + ", ".join(descs[:2]) + ")"
            if cat == "movement":
                text = f"You hear movement {distw}" + (f", {where}." if distw not in ("very close",) else "!")
            elif cat == "screaming":
                text = f"Someone is screaming {distw}: '{descs[0]}'" if descs else f"Screams {distw}."
            else:
                heavy = n >= 6 and cat == "gunfire"
                text = f"{'Heavy ' if heavy else ''}{cat[0].upper() + cat[1:] if heavy else 'You hear ' + cat} {where}, {distw}{detail}."
            self.msg(text, "sound")
            shown += 1
            if shown >= 2:
                break
        self._sound_msgs = {}

    def near_miss(self):
        p = self.player
        self.last_near_miss = self.turn
        if p is not None:
            self.audio("whizz", p.x, p.y, 72)
            if self.rng.random() < 0.2:
                self.audio("ricochet", p.x + self.rng.randint(-2, 2), p.y + self.rng.randint(-2, 2), 65)
        if self.turn - self.last_whizz_msg < 3:
            return
        self.last_whizz_msg = self.turn
        self.msg(self.rng.choice(["Bullets snap past your head!", "Rounds crack overhead!",
                                  "Something zips past your ear!", "Dirt kicks up beside you!",
                                  "A bullet whines off something next to you!"]), "warn")

    # ================================================================== effects (render hints)
    def _vis_effect(self, x, y):
        return self.map.in_bounds(x, y) and self.map.visible[x, y]

    def effect_flash(self, x, y):
        if self._vis_effect(x, y):
            self.effects.append(dict(t=self.turn, kind="flash", x=x, y=y))
        if self.is_night():
            self.map.lights.append([x, y, 2, self.turn])

    def effect_tracer(self, x0, y0, x1, y1, mg=False, rocket=False):
        if self._vis_effect(x0, y0) or self._vis_effect(x1, y1):
            self.effects.append(dict(t=self.turn, kind="tracer", x0=x0, y0=y0, x1=x1, y1=y1, mg=mg, rocket=rocket))

    def effect_explosion(self, x, y, r):
        if self._vis_effect(x, y) or r >= 3:
            self.effects.append(dict(t=self.turn, kind="explosion", x=x, y=y, r=r))

    def effect_splash(self, x, y):
        if self._vis_effect(x, y):
            self.effects.append(dict(t=self.turn, kind="splash", x=x, y=y))

    def effect_flame(self, pts):
        if pts and any(self._vis_effect(x, y) for x, y in pts):
            self.effects.append(dict(t=self.turn, kind="flame", pts=pts))

    def effect_throw(self, x0, y0, x1, y1):
        if self._vis_effect(x0, y0) or self._vis_effect(x1, y1):
            self.effects.append(dict(t=self.turn, kind="throw", x0=x0, y0=y0, x1=x1, y1=y1))

    # ================================================================== environment
    def swimming(self, a):
        heavy = a.carried_weight() > 15 and not a.find(lambda i: i.tid == "mae_west")
        if heavy:
            a.body.drown += 1
            if a.is_player:
                if a.body.drown == 1:
                    self.msg("The water closes over your head. Your kit drags you down!", "death")
                elif a.body.drown == 3:
                    self.msg("You're drowning! Drop your heavy gear!", "death")
            if a.body.drown >= 5:
                hit_actor(self, a, self.rng.uniform(4, 10), "blunt", None, "drowning", part="torso", silent=True)
                a.body.cause = "drowning"
            if a.body.drown >= 12:
                a.body.dead = True
                a.body.cause = "drowning"
                self.kill(a, None)
        else:
            a.body.drown = max(0, a.body.drown - 1)

    def _environment(self):
        m = self.map
        rng = self.rng
        f = m.fire
        burning = f > 0
        rain = self.weather in ("rain", "snow")
        if burning.any():
            f[burning] -= 1
            ended = burning & (f == 0)
            if ended.any():
                m.t[ended] = T.BURNT[m.t[ended]]
                m.hp[ended] = T.HP[m.t[ended]]
                self.terrain_dirty = True
            # spread
            if self.turn % 2 == 0:
                src = (f > 0).astype(np.float32)
                nb = np.zeros_like(src)
                nb[1:, :] += src[:-1, :]
                nb[:-1, :] += src[1:, :]
                nb[:, 1:] += src[:, :-1]
                nb[:, :-1] += src[:, 1:]
                wx, wy = self.wind
                if wx or wy:
                    shifted = np.roll(np.roll(src, wx, axis=0), wy, axis=1)
                    nb += shifted * 1.5
                p = nb * (T.FLAM[m.t] / 100.0) * (0.04 if not rain else 0.01)
                ign = (rng.random() < p) if False else (np.random.random(p.shape) < p)
                ign &= (f == 0) & (T.FLAM[m.t] > 0)
                f[ign] = np.random.randint(15, 45, size=int(ign.sum())).astype(np.int16)
            m.smoke[f > 0] += 0.35
            # burning soldiers
            for a in list(self.actors):
                if a.alive and a.vehicle is None and f[a.x, a.y] > 0:
                    hit_actor(self, a, rng.uniform(4, 10), "burn", None, "fire", silent=not a.is_player)
                    a.suppression = min(100, a.suppression + 20)
            # burning vehicles
            for v in self.vehicles:
                if not v.dead and f[v.x, v.y] > 0 and rng.random() < 0.02:
                    v.burning = max(v.burning, 10)
        for a in self.actors:
            if a.alive and a.body.burning and a.vehicle is None:
                a.body.burning -= 1
                hit_actor(self, a, rng.uniform(3, 8), "burn", None, "burning", silent=True)
                if m.in_bounds(a.x, a.y) and T.FLAM[m.t[a.x, a.y]] > 20 and rng.random() < 0.2:
                    ignite(self, a.x, a.y, 1)
        # smoke sources
        keep = []
        for s in self.smoke_sources:
            x, y, ttl, amt = s
            m.smoke[max(0, x - 2):x + 3, max(0, y - 2):y + 3] += amt * 0.5
            s[2] -= 1
            if s[2] > 0:
                keep.append(s)
        self.smoke_sources = keep
        # smoke diffusion and decay
        sm = m.smoke
        if sm.max() > 0.01:
            nb = np.zeros_like(sm)
            nb[1:, :] += sm[:-1, :]
            nb[:-1, :] += sm[1:, :]
            nb[:, 1:] += sm[:, :-1]
            nb[:, :-1] += sm[:, 1:]
            sm = sm * 0.55 + nb * 0.1
            wx, wy = self.wind
            if self.turn % 3 == 0 and (wx or wy):
                sm = np.roll(np.roll(sm, wx, axis=0), wy, axis=1) * 0.97
            sm *= 0.96 if not rain else 0.9
            sm[sm < 0.02] = 0
            m.smoke = sm.astype(np.float32)
        m.update_see()

    def _weather_tick(self):
        if self.turn - self.weather_turn < 900:
            return
        self.weather_turn = self.turn
        if self.rng.random() < 0.3:
            old = self.weather
            self.weather = self._roll_weather()
            if self.weather != old:
                msgs = {"rain": "It starts to rain.", "snow": "Snow begins to fall.", "fog": "Fog rolls in.",
                        "clear": "The sky clears.", "overcast": "Clouds roll over.",
                        "sandstorm": "The wind rises, driving sand into everything."}
                self.msg(msgs.get(self.weather, "The weather changes."), "info")
        if self.rng.random() < 0.2:
            self.wind = (self.rng.choice((-1, 0, 1)), self.rng.choice((-1, 0, 1)))

    # ================================================================== waves & strategic
    def schedule_wave(self, side, units, edge, delay=200, landing=False):
        self.waves.append(dict(side=side, units=Counter(units), edge=edge, turn=self.turn + delay,
                               landing=landing))

    def _tick_waves(self):
        from .spawn import spawn_units, split_local
        keep = []
        for w in self.waves:
            if self.turn < w["turn"]:
                keep.append(w)
                continue
            now, later = split_local(w["units"], scale=self.__dict__.get("troop_scale", 1.0))
            # only send in what the map can take
            live = sum(1 for a in self.actors if a.side == w["side"] and a.alive)
            if live > 110 * self.__dict__.get("troop_scale", 1.0):
                w["turn"] = self.turn + 200
                keep.append(w)
                continue
            half = Counter({k: max(1, n // 2) if n else 0 for k, n in now.items()})
            rest = now - half
            spawn_units(self, w["side"], half, w["edge"], w["side"] == self.attacker, [], landing=w.get("landing", False))
            for sq in self.squads:
                if getattr(sq, "formation", None) is None:
                    self.command.attach_squad(self, sq)
            later.update(rest)
            commander_update(self, w["side"])
            if w["side"] == self.player_side:
                self.msg("Reinforcements are coming up behind you.", "radio")
            else:
                self.msg("You hear engines and shouting - more of them are coming.", "sound") \
                    if self.rng.random() < 0.6 else None
            if sum(later.values()) > 0:
                keep.append(dict(side=w["side"], units=later, edge=w["edge"],
                                 turn=self.turn + self.rng.randint(200, 420), landing=w.get("landing", False)))
        self.waves = keep

    def _strategic_tick(self):
        st = self.strategic
        cmd = self.command
        ops = self.__dict__.get("ops")
        if ops is not None and cmd.strategic_reach(self) > 0 and self.player.alive:
            ops.organise(self)
            ops.before_tick(self)
        else:
            st.concentration = {}
        st.player_orders = {self.player_side: cmd.strategic_orders}
        if not hasattr(st, "order_news"):
            st.order_news = []
        if self.__dict__.get("domain") == "aboard":
            events = st.tick(None, None)        # at sea: the land war goes on without you in it
            events = [e for e in events if e[0] not in ("reinforce", "sally")]
        else:
            events = st.tick(self.sector, self.local_units())
        for n in st.order_news:
            self.msg(n, "radio")
        st.order_news = []
        cmd.strategic_orders = [o for o in cmd.strategic_orders if o["kind"] in ("hold", "arty", "air")]
        if ops is not None and cmd.strategic_reach(self) > 0 and self.player.alive:
            ops.after_tick(self)
        if self.player.alive:
            cmd.consider_promotion(self)
        for ev in events:
            if ev[0] == "sally":
                self._sally(ev[1], ev[2], ev[3])
                continue
            if ev[0] == "reinforce":
                side, units, direction = ev[1], ev[2], ev[3]
                landing = len(ev) > 4 and ev[4] == "landing"
                edge = direction or self.home_edge(side)
                self.schedule_wave(side, units, edge, delay=self.rng.randint(10, 90), landing=landing)
        # news from elsewhere
        for n in st.news[-3:]:
            if self.player_near_radio(self.player_side) or self.rng.random() < 0.3:
                self.msg(f"Word comes down the line: {n}", "radio")
        st.news = []

    def player_near_radio(self, side) -> bool:
        p = self.player
        if p is None:
            return False
        if p.has_tool("radio"):
            return True
        for a in self.actors:
            if a.side == side and a.alive and a.has_tool("radio") and abs(a.x - p.x) + abs(a.y - p.y) <= 4:
                return True
        return False

    def random_point_near_edge(self, edge, depth=0.3):
        m = self.map
        r = self.rng
        if edge is None:
            return r.randint(10, m.w - 10), r.randint(10, m.h - 10)
        d = r.uniform(0.05, depth)
        if edge == "N":
            return r.randint(5, m.w - 5), int(d * m.h)
        if edge == "S":
            return r.randint(5, m.w - 5), int((1 - d) * m.h)
        if edge == "W":
            return int(d * m.w), r.randint(5, m.h - 5)
        return int((1 - d) * m.w), r.randint(5, m.h - 5)

    def on_objective_taken(self, i, side, prev):
        o = self.map.objectives[i]
        p = self.player
        mine = side == p.side
        if prev is None and not mine:
            return
        self.command.on_objective(self, i, side)
        for a in self.actors:
            if a.active:
                a.morale += 5 if a.side == side else -5
        if mine:
            self.msg(f"{cap(o.name)} is ours!", "good")
            self.stats["objectives"] += 1 if p.squad is not None and p.squad.order.obj == i else 0
        else:
            self.msg(f"We've lost {o.name}!", "warn")
        self.update_orders(force=True)

    def on_withdrawal(self, side):
        if side == self.player_side:
            self.msg("Word spreads along the line: we're pulling out. Fall back!", "warn")
        else:
            self.msg("The enemy is falling back!", "good")

    def _battle_check(self):
        s = self.sector
        present = {side: any(a.side == side and a.active and not a.is_player for a in self.actors) or
                   any(v.side == side and v.active for v in self.vehicles) or
                   any(w["side"] == side for w in self.waves) for side in SIDES}
        p = self.player
        if p.alive and p.state == "ok":
            present[p.side] = True
        if present[ALLIES] and not present[AXIS] and s.control != ALLIES:
            self.strategic._capture(s, ALLIES)
            self._sector_won(ALLIES)
        elif present[AXIS] and not present[ALLIES] and s.control != AXIS:
            self.strategic._capture(s, AXIS)
            self._sector_won(AXIS)

    def _sector_won(self, side):
        p = self.player
        if side == p.side:
            self.msg(f"{self.sector.name} is clear of the enemy. The sector is ours.", "good")
            self.stats["sectors_won"] += 1
            self.command.on_sector_won(self, side)
        else:
            self.msg(f"{self.sector.name} is in enemy hands. You're behind their lines.", "warn")
        self.update_orders(force=True)

    # ================================================================== orders (diegetic)
    def update_orders(self, force=False):
        p = self.player
        if p is None or (not force and self.turn - self.orders_turn < 30):
            return
        if self.__dict__.get("domain") == "aboard" and self.__dict__.get("skysea") is not None:
            from . import aboard as _AB
            ss = self.skysea
            self.orders_turn = self.turn
            mis = (ss.mission or {}).get("text", "")
            where = {"sailor": "Man your mount (e beside it).", "petty_officer": "See to your gun crew.",
                     "deck_officer": "The bridge: e at the helm or the plot for the conn.",
                     "ship_captain": "The bridge: e at the helm or the plot to command her.",
                     "sub_commander": "The conning tower: e at the periscope to command her.",
                     "admiral": "The flag bridge: e at the plot to signal the force."}.get(p.role, "")
            if (self.aboard or {}).get("kind") == "ship":
                from . import shipboard as _SB
                from .shipyard import DECK_NAME
                ab = self.aboard
                cond = "GENERAL QUARTERS" if ab["condition"] == "GQ" else \
                    ("Condition III - you're on watch" if _SB.on_watch(self) else "Condition III - off watch")
                job = _SB.task_line(self)
                self.player_orders = ((f"{job} " if job else "") + f"{cond}. On {DECK_NAME.get(ab['deck'], ab['deck'])}. "
                                      + _SB.station_words(self) + f" {mis}")
                return
            self.player_orders = f"{mis} {where} ({_AB.status_line(self) or ''})"
            return
        from .scenarios import mission_line
        ml = mission_line(self)
        if ml:
            self.orders_turn = self.turn
            self.player_orders = "MISSION: " + ml
            return
        self.orders_turn = self.turn
        sq = p.squad
        m = self.map
        text = ""
        cmd = self.command
        if sq is None:
            text = "No orders. Find your unit."
        elif cmd.billet is not None:
            text = f"You command {cmd.billet_title(self)}. C for command, m for the front."
            enemy_obj = [o for o in m.objectives if o.owner != p.side]
            if enemy_obj and cmd.billet.echelon in ("platoon", "company"):
                o = min(enemy_obj, key=lambda o: abs(o.x - p.x) + abs(o.y - p.y))
                text = f"You command {cmd.billet_title(self)}. Battalion wants {o.name} taken. (C: command)"
        elif sq.player_led:
            text = "You lead. Press O to give your men orders."
            enemy_obj = [o for o in m.objectives if o.owner != p.side]
            if enemy_obj:
                o = min(enemy_obj, key=lambda o: abs(o.x - p.x) + abs(o.y - p.y))
                text = f"Company wants {o.name} taken. You lead."
        else:
            o = sq.order
            leader = sq.leader
            lname = leader.full_name if leader is not None and not leader.is_player else "HQ"
            where = self._pointing(o)
            if o.kind == "attack":
                text = f"{lname}: 'We're taking {o.describe(self)[5:]}{where}. Keep moving!'"
            elif o.kind == "defend":
                text = f"{lname}: 'Dig in. We hold {o.describe(self)[5:]}{where}.'"
            elif o.kind == "retreat":
                text = f"{lname}: 'Fall back! Get out of here!'"
            elif o.kind == "follow":
                text = f"{lname}: 'Stay on me.'"
            else:
                text = f"{lname}: 'Hold here and keep your eyes open.'"
        duty = getattr(self, "duty", None)
        if duty is not None and duty.task is not None:
            text = duty.task_text(self)
        if getattr(self, "renegade", False):
            text = "Your own side wants you dead. Get away - or go down fighting."
        if self.sector.control != p.side and not any(a.side == p.side and a.active and not a.is_player for a in self.actors):
            text = f"You're alone behind enemy lines. Get back to friendly territory ({self.home_edge(p.side) or '?'})."
        if text != self.player_orders:
            self.player_orders = text
            it = p.find(lambda i: i.tid == "orders")
            if it is not None:
                it.data = {"text": text}
            if not force or self.turn > 0:
                self.msg(text, "radio" if "HQ" in text else "shout")

    def _pointing(self, o):
        """The leader points: a direction and a rough distance."""
        from .ai import order_target
        p = self.player
        sq = p.squad
        t = order_target(self, sq) if sq is not None else None
        if t is None:
            return ""
        d = math.hypot(t[0] - p.x, t[1] - p.y)
        if d < 8:
            return " - right here"
        yd = int(round(d * 2.2 / 50.0) * 50) or 50
        return f" - there, {direction_word(t[0] - p.x, t[1] - p.y)}, {yd} yards"

    def order_target_for_player(self):
        p = self.player
        sq = p.squad
        if sq is None:
            return None
        from .ai import order_target
        t = order_target(self, sq)
        if sq.player_led:
            enemy_obj = [o for o in self.map.objectives if o.owner != p.side]
            if enemy_obj:
                o = min(enemy_obj, key=lambda o: abs(o.x - p.x) + abs(o.y - p.y))
                return (o.x, o.y)
        return t

    def order_pointer(self):
        """(x, y, label) of where your orders send you - what your leader pointed at, or your objective."""
        p = self.player
        duty = getattr(self, "duty", None)
        if duty is not None and duty.task is not None:
            pt = duty.task_point(self)
            if pt is not None and max(abs(pt[0] - p.x), abs(pt[1] - p.y)) > 1:
                from .duty import TASK_TEXT
                return int(pt[0]), int(pt[1]), TASK_TEXT[duty.task["kind"]].split("!")[0].split(".")[0]
        sq = p.squad
        if sq is None or p.state != "ok":
            return None
        t = self.order_target_for_player()
        if t is None:
            return None
        o = sq.order
        if sq.player_led:
            names = [ob.name for ob in self.map.objectives if (ob.x, ob.y) == tuple(t)]
            label = f"Take {names[0]}" if names else "Objective"
        elif o.kind == "follow":
            return None
        else:
            label = o.describe(self)
        if max(abs(t[0] - p.x), abs(t[1] - p.y)) <= 3:
            return None
        return int(t[0]), int(t[1]), label

    # ================================================================== turn engine
    def player_fov(self):
        compute_light(self)
        player_fov(self)

    def player_done(self, max_turns=600):
        """After the player acts: run the world until the player may act again."""
        n = 0
        p = self.player
        while (p.moves <= 0 or not p.body.conscious) and not self.game_over and n < max_turns:
            self.world_turn()
            n += 1
            if not p.body.conscious and n % 5 == 0:
                break
        self.player_fov()
        return n

    def world_turn(self):
        self.turn += 1
        self.clock += 1
        rng = self.rng
        m = self.map
        p = self.player
        if self.turn % 30 == 0:
            self.update_view_range()
        if self.is_night() or self.lit is not None:
            compute_light(self)
        self._arr_turn = -1
        # brains
        for i, s in enumerate(SIDES):
            b = self.brains[s]
            if b.due(self.turn):
                b.update(force=True)
        # squads
        if self.turn % 2 == 0:
            alive = []
            for sq in self.squads:
                if AI.squad_update(self, sq):
                    alive.append(sq)
            self.squads = alive
        if self.turn % 5 == 0:
            update_objectives(self, 5)
        if self.turn % 20 == 0:
            for s in SIDES:
                commander_update(self, s)
        # actors
        acts = [a for a in self.actors if a.alive]
        rng.shuffle(acts)
        for a in acts:
            if not a.alive:
                continue
            a.moves += a.speed(self.turn) if a is not p else a.speed()
            if a is p:
                continue
            guard = 0
            while a.moves > 0 and a.alive and guard < 4:
                guard += 1
                try:
                    cost = AI.soldier_act(self, a)
                except Exception as e:     # never let one soldier crash the war
                    cost = 100
                    if os.environ.get("FOW_DEBUG"):
                        raise
                a.moves -= max(25, cost or 100)
            if a.moves > 200:
                a.moves = 200
        for v in list(self.vehicles):
            if v.dead:
                continue
            v.moves += 100
            guard = 0
            while v.moves > 0 and not v.dead and guard < 3:
                guard += 1
                try:
                    cost = AI.vehicle_act(self, v)
                except Exception:
                    cost = 100
                    if os.environ.get("FOW_DEBUG"):
                        raise
                v.moves -= max(25, cost or 100)
        self.vehicles = [v for v in self.vehicles if not (v.dead and v.x < 0)]
        # physiology & nerves
        officers = [a for a in self.actors if a.rank >= 8 and a.active and not a.downed] if self.turn % 2 == 0 else []
        for a in list(self.actors):
            if not a.alive:
                continue
            if a.__dict__.get("recoil"):
                settle_recoil(a)
            ev = a.body.update(rng)
            if a.body.dead:
                self.kill(a, a.body.killer)
                continue
            if a.is_player:
                for e in ev:
                    if e == "fainted":
                        self.msg("Your vision tunnels to black...", "hurt")
                    elif e == "woke":
                        self.msg("You come to. Everything hurts.", "hurt")
                    elif e == "shock":
                        self.msg("You slip into shock...", "hurt")
            decay = 3.0 + m.pos_cover[a.x, a.y] / 25 if a.vehicle is None else 5
            a.suppression = max(0.0, a.suppression - decay)
            base = NATIONS[a.nation]["doctrine"]["morale"]
            if a.morale < base:
                a.morale += 0.05 + self._leadership(a, officers)
            st = getattr(a, "stamina", 100.0)
            ceiling = 100.0 - 0.6 * getattr(a, "fatigue", 0.0)
            rest = a.moved_turn < self.turn - 1 or a.vehicle is not None
            if st < ceiling:
                regen = (0.7 + (0.4 if a.stance == 2 else 0.0)) if rest else 0.08
                if a.body.effective_pain() > 60:
                    regen *= 0.5
                if getattr(a.body, "temp", 37.0) > 39.0 or getattr(a.body, "temp", 37.0) < 34.5:
                    regen *= 0.5
                a.stamina = min(ceiling, st + regen)
                if a is p:
                    self._breath_msgs(st, a.stamina)
            elif st > ceiling:
                a.stamina = ceiling
            fat = getattr(a, "fatigue", 0.0)
            if fat > 0 and a.moved_turn < self.turn - 5:
                a.fatigue = max(0.0, fat - (0.006 if a.stance == 2 and a.suppression < 10 else 0.003))
            # the weather, on everyone (you get the messages)
            if a is not p and (self.turn + a.id) % 30 == 0:
                from . import thermal
                thermal.update(self, a)
            w = a.weapon
            if w is not None and w.heat > 0:
                w.heat = max(0.0, w.heat - 1.5)
        self.noise *= 0.93
        if getattr(self, "pow", None) is not None:
            from .pow import march_update
            march_update(self)
        self.command.update(self)
        if self.turn % 10 == 4:
            self.duty.update(self)
        if self.turn % 30 == 0:
            self._medical_tick()
        if self.turn % 40 == 17:
            self._banter_tick()
        if self.turn % 20 == 9:
            self._execution_tick()
        if self.turn % 15 == 11:
            self._mistaken_identity_tick()
        if self.turn % 2 == 1:
            from . import prisoners as _PW
            _PW.pending_surrenders(self)
            if self.turn % 60 == 31:
                _PW.treachery_tick(self)
        aboard = self.__dict__.get("domain") == "aboard"
        if aboard:
            from . import aboard as _AB
            _AB.tick(self)
        if self.turn % 60 == 23 and not aboard:
            from . import threat
            threat.update(self)
        if self.turn % 10 == 3 and self.__dict__.get("mission"):
            from . import scenarios as SC
            SC.update(self)
        if self.turn % 5 == 2 and self.player is not None and self.player.ai.get("disguise"):
            self._disguise_tick()
        if self.turn % 30 == 13 and self.player is not None and self.player.alive:
            self._weather_on_you()
        if self.turn % 60 == 41:
            h = self.__dict__.get("hierarchy")
            if h is None:
                from .hierarchy import Hierarchy
                h = self.hierarchy = Hierarchy()
            h.tick(self)
        if self._banter_replies:
            self._banter_reply()
        # environment and ordnance
        self._tick_explosives()
        self._tick_pending()
        self._tick_shells()
        self.support.update()
        self._environment()
        if self.terrain_dirty:
            m.refresh()
            self.terrain_dirty = False
        if not aboard:
            self._tick_waves()
            if self.turn % 3 == 1 and self.__dict__.get("sallies"):
                self._sally_tick()
            if self.turn % 2 == 0 and getattr(self.strategic, "attacks", None):
                self._front_noise()
        if self.turn % STRATEGIC_TICK == 0:
            self._strategic_tick()
        if self.turn % 30 == 0:
            if not aboard:
                self._battle_check()
            self.update_orders()
        self._weather_tick()
        self._collect_speech()
        self._flush_sound_msgs()
        self.sound_marks = [s for s in self.sound_marks if s.until >= self.turn]
        if p is not None and p.alive and p.vehicle is not None and p.vehicle.dead:
            pass

    def medic_bound(self, a) -> bool:
        """On his way to the aid station, legitimately."""
        return a.ai.get("to_aid") is not None or a.body.bleed_rate() > 0.5

    def _banter_tick(self):
        """Nothing happening: men talk."""
        from .data.banter import BANTER
        from .data.phrases import lang
        if not hasattr(self, "_banter_replies"):
            self._banter_replies = []
        rng = self.rng
        p = self.player
        for sq in self.squads:
            if sq.gone or self.turn - sq.last_contact < 300 or self.turn - sq.rep.get("banter", -9999) < 500:
                continue
            if rng.random() > 0.25:
                continue
            men = [m for m in sq.members if m.active and not m.downed and not m.is_player and m.vehicle is None]
            if len(men) < 2:
                continue
            a = rng.choice(men)
            near = [m for m in men if m is not a and max(abs(m.x - a.x), abs(m.y - a.y)) <= 3]
            if not near:
                continue
            b = rng.choice(near)
            lines = BANTER.get(lang(a.nation)) or BANTER["en"]
            line, reply = rng.choice(lines)
            a.say(line, self.turn, 4, tone="talk")
            self._banter_replies.append((self.turn + rng.randint(4, 7), b.id, reply))
            sq.rep["banter"] = self.turn
            if p is not None and p.side == sq.side and max(abs(a.x - p.x), abs(a.y - p.y)) <= 8 and \
                    rng.random() < 0.3:
                break               # one conversation at a time near you

    def _banter_reply(self):
        keep = []
        for when, bid, text in self._banter_replies:
            if self.turn < when:
                keep.append((when, bid, text))
                continue
            b = next((o for o in self.actors if o.id == bid), None)
            if b is not None and b.active:
                b.say(text, self.turn, 4, tone="talk")
        self._banter_replies = keep

    def _weather_on_you(self):
        from . import thermal
        p = self.player
        before = thermal.words(p)[0]
        ev = thermal.update(self, p)
        now = thermal.words(p)[0]
        if now != before:
            text = {"Cold": "You're getting cold.", "Shivering hard": "You can't stop shivering. Your hands shake.",
                    "Hypothermic - clumsy, confused": "Your hands won't work and your thoughts come slowly. You need "
                    "warmth, now.", "Freezing to death": "You stop feeling cold. That's very bad.",
                    "Overheating": "Sweat pours off you.", "Heat exhaustion": "Your head pounds; the world swims. "
                    "Water, shade.", "Heatstroke": "You've stopped sweating. You're burning up.",
                    "Comfortable": "You're warm enough again." if "Cold" in before or "Shiver" in before or "Hypo" in before
                    else "You've cooled off."}.get(now)
            if text:
                self.msg(text, "hurt" if now not in ("Comfortable",) else "info")
        if getattr(p.body, "frost", 0) > 60 and self.rng.random() < 0.05:
            self.msg("You can't feel your toes any more.", "hurt")
        for e in ev:
            self.msg("You fold up in the cold..." if e == "collapse_cold" else "You collapse in the heat...", "hurt")

    def _disguise_tick(self):
        """Walking among them in civilian clothes: every look is a risk."""
        p = self.player
        rng = self.rng
        body = p.invent.slots.get("body")
        why = None
        if body is None or body.tid != "civvies":
            why = "Out of your civilian clothes, you're just an enemy soldier to them."
        elif p.fired_turn >= self.turn - 2:
            why = "The shot gives you away."
        elif p.weapon is not None and p.weapon.t.kind == "gun" and p.weapon.t.cat not in ("pistol",):
            why = f"Someone sees the {p.weapon.t.name} in your hands."
        near = [a for a in self.actors if a.side != p.side and a.active and a.vehicle is None
                and max(abs(a.x - p.x), abs(a.y - p.y)) <= 3]
        if why and not any(max(abs(a.x - p.x), abs(a.y - p.y)) <= 15 for a in self.actors
                           if a.side != p.side and a.active):
            why = None if "clothes" not in why else why      # nobody there to see
        if why is None and near:
            sus = p.ai.get("suspicion", 0) + 6 * len(near) + (8 if p.stance > 0 else 0) + \
                (6 if self.is_night() else 0)
            if p.ai.get("papers_checked", -999) > self.turn - 600:
                sus -= 5
            p.ai["suspicion"] = sus
            if sus >= 60:
                a = near[0]
                a.say({"germany": "Halt! Papiere!", "japan": "Tomare!", "italy": "Alt! Documenti!",
                       "ussr": "Stoy! Dokumenty!", "finland": "Seis! Paperit!"}.get(a.nation, "Halt! Papers!"),
                      self.turn, 3)
                good = p.find(lambda i: i.tid == "forged_papers") is not None
                if good and rng.random() < 0.75 + (0.05 * p.skill - 0.25):
                    rk = a.rank_full or "soldier"
                    self.msg(f"{'An' if rk[:1].lower() in 'aeiou' else 'A'} {rk} checks your papers, looks at your "
                             f"face, and waves you on.", "info")
                    p.ai["suspicion"] = 0
                    p.ai["papers_checked"] = self.turn
                else:
                    why = "Your papers don't satisfy him. He reaches for his rifle."
        elif why is None:
            p.ai["suspicion"] = max(0, p.ai.get("suspicion", 0) - 3)
        if why:
            p.ai["disguise"] = False
            p.ai["suspicion"] = 0
            self._enemy_arr = {}
            self.msg(why + " Your cover is blown!", "death")
            enemy = other_side(p.side)
            self.brains[enemy].report(p, self.turn)
            self.noise = min(100.0, self.noise + 40)

    def _mistaken_identity_tick(self):
        """An enemy tank with our men in it, a man in an enemy helmet: at a distance, the shape is all anyone sees."""
        from .combat import vehicle_fire_main
        from .data.items import HELMETS
        from .data.nations import NATIONS
        from .senses import can_detect
        rng = self.rng
        p = self.player
        # captured vehicles nobody has marked
        for v in self.vehicles:
            if not v.ai.get("captured") or v.ai.get("marked") or v.dead or v.ai.get("recognised", -1) > self.turn:
                continue
            for o in self.vehicles:
                if o is v or o.side != v.side or not o.active or o.player_crewed or o.mount is None or o.reload > 0:
                    continue
                d = max(abs(o.x - v.x), abs(o.y - v.y))
                if not (12 <= d <= 45) or not can_detect(self, o, v, d) or rng.random() > 0.05:
                    continue
                if vehicle_fire_main(self, o, v.x, v.y, v, "ap"):
                    self.msg(f"A {o.vt.name} fires on the captured {v.vt.name}! "
                             f"'Cease fire, cease fire - that's one of ours!'", "death" if p.vehicle is v else "radio",
                             (o.x, o.y))
                    v.ai["recognised"] = self.turn + 240
                    break
        # you, in their helmet
        h = p.helmet
        if h is None or not p.alive or p.vehicle is not None or p.state != "ok":
            return
        owner = next((n for n, hid in HELMETS.items() if hid == h.tid), None)
        if owner is None or NATIONS.get(owner, {}).get("side") == p.side:
            return
        if any(hid == h.tid for n, hid in HELMETS.items() if NATIONS.get(n, {}).get("side") == p.side):
            return                        # the Chinese and the Germans both wore Stahlhelme
        if p.ai.get("recognised", -1) > self.turn:
            return
        for o in self.actors:
            if o.side != p.side or o.is_player or not o.active or o.squad is p.squad:
                continue
            d = max(abs(o.x - p.x), abs(o.y - p.y))
            if not (15 <= d <= 45) or o.weapon is None or o.weapon.t.kind != "gun" or o.weapon.loaded <= 0:
                continue
            if not can_detect(self, o, p, d) or rng.random() > 0.03:
                continue
            from .actions import fire
            o.say(self.shout(o, "contact"), self.turn, 3)
            fire(self, o, p.x, p.y, p)
            self.msg(f"Your own side is shooting at you - it's the {h.t.name}! Someone yells 'Hold fire!'", "death")
            p.ai["recognised"] = self.turn + 300
            break

    def _execution_tick(self):
        """Some armies, some fronts, some units: prisoners don't reach the rear."""
        from .duty import EXECUTES
        rng = self.rng
        for a in self.actors:
            if a.state != "surrendered" or not a.alive or a.is_player:
                continue
            cap_side = other_side(a.side)
            guards = [o for o in self.actors if o.side == cap_side and o.active and not o.is_player and
                      o.weapon is not None and o.weapon.t.kind == "gun" and o.weapon.loaded > 0 and
                      max(abs(o.x - a.x), abs(o.y - a.y)) <= 4]
            if not guards:
                continue
            g = guards[0]
            rate = EXECUTES.get((g.nation, a.nation), EXECUTES.get((g.nation, "*"), 0.0))
            from .data.special import SPECIAL
            if "executes" in SPECIAL.get(g.__dict__.get("unit_type"), {}).get("flags", ()):
                rate = min(0.9, rate + 0.3)
            if "no_quarter" in self.theatre.get("special", ()):
                rate = max(rate, 0.3)
            rate *= 1 + 0.5 * self.no_quarter.get(cap_side, 0)          # it spreads
            if rng.random() > rate * 0.15:
                continue
            from .actions import fire
            if self.can_see(a.x, a.y):
                self.msg(f"{cap(self.name_of(g))} raises {g.his} rifle at {self.name_of(a)}, who is on {a.his} knees.",
                         "death")
            fire(self, g, a.x, a.y, a)
            if not a.alive or a.body.downed():
                self.no_quarter[a.side] += 1     # word gets round: they'll fight to the end now

    def _medical_tick(self):
        """Operations finish, wounds mend, the walking wounded go back for treatment."""
        from . import medical as MED
        by_id = {a.id: a for a in self.actors}
        for a in list(self.actors):
            if not a.alive:
                continue
            job = a.ai.get("surgery")
            if job is not None:
                sg = by_id.get(job["by"])
                if self.turn >= job["end"]:
                    MED.finish_surgery(self, sg, a)
                elif sg is None or not sg.alive or not sg.active or max(abs(sg.x - a.x), abs(sg.y - a.y)) > 1:
                    MED.finish_surgery(self, None, a)       # the surgeon's gone: someone closes up
                    if sg is not None and sg.is_player:
                        self.msg("You leave the table half-done. An orderly closes him up as best he can.", "warn")
                continue
            MED.recover(self, a, 30)
            if a.is_player or a.role in ("surgeon",) or a.ai.get("to_aid") is not None or a.vehicle is not None:
                continue
            if MED.should_evacuate(a.body) and not a.downed and a.body.bleed_rate() < 0.3 and \
                    MED.nearest_aid(self, a) is not None:
                sq = a.squad
                if sq is None or self.turn - sq.last_contact > 40:
                    a.ai["to_aid"] = self.turn
                    if self.rng.random() < 0.3 and sq is not None and sq.leader is not None and sq.leader.active:
                        sq.leader.say("Get yourself back to the aid station." if sq.leader.nation in
                                      ("usa", "uk", "canada", "australia", "newzealand") else "", self.turn, tone="talk")

    def _leadership(self, a, officers) -> float:
        """Men steady faster with their leader beside them - and an officer in sight."""
        if self.turn % 2:
            return 0.0
        bonus = 0.0
        sq = a.squad
        if sq is not None:
            ld = sq.leader
            if ld is not None and ld is not a and ld.active and max(abs(ld.x - a.x), abs(ld.y - a.y)) <= 6:
                bonus += 0.06 + 0.01 * ld.rank
        for o in officers:
            if o is not a and o.side == a.side and max(abs(o.x - a.x), abs(o.y - a.y)) <= 10:
                bonus += 0.05
                break
        return bonus

    def _breath_msgs(self, before, after):
        p = self.player
        if after < 20 and not p.ai.get("winded_msg"):
            p.ai["winded_msg"] = True
            self.msg("Your lungs are burning. You need a breather.", "warn")
        elif after >= 60:
            p.ai["winded_msg"] = False
        from .pace import fatigue_word
        fw, _ = fatigue_word(p)
        if fw != p.ai.get("fatigue_word"):
            if fw and (p.ai.get("fatigue_word") is None or fw != "Tired"):
                self.msg({"Tired": "You're tiring. Your legs are heavy.",
                          "Exhausted": "You're exhausted. You need real rest - hours of it.",
                          "Dead on your feet": "You're dead on your feet. You can barely lift your rifle."}[fw], "warn")
            p.ai["fatigue_word"] = fw

    # ================================================================== save/load
    def save(self, path=None):
        import gzip
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = path or os.path.join(SAVE_DIR, "save.pkl")
        tmp = path + ".tmp"
        with gzip.open(tmp, "wb", compresslevel=5) as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
        return path

    @staticmethod
    def load(path=None):
        import gzip
        path = path or os.path.join(SAVE_DIR, "save.pkl")
        with gzip.open(path, "rb") as f:
            g = pickle.load(f)
        g._reset_counters()
        if not hasattr(g, "noise"):
            g.noise = 0.0
        if not hasattr(g, "pow"):
            g.pow = None
        if not hasattr(g, "_banter_replies"):
            g._banter_replies = []
        if not hasattr(g, "duty"):
            from .duty import Duty
            g.duty = Duty()
            g.renegade = False
            g.no_quarter = Counter()
        if not hasattr(g, "command"):
            for sq in g.squads:
                for k, v in dict(formation=None, gone=False, short="", callsign="", leader_grade=3,
                                 next_report=0, rep={}).items():
                    if not hasattr(sq, k):
                        setattr(sq, k, v)
            g.command = CommandState()
            g.command.organise(g)
        for a in g.actors:
            if "recoil" not in a.__dict__:
                a.recoil = 0.0
        if "domain" not in g.__dict__:
            g.domain, g.skysea = "land", None
        if g.__dict__.get("skysea") is not None:
            from .skysea import Plane, Ship
            Plane._next = max([pl.id for pl in g.skysea.planes] + [0]) + 1
            Ship._next = max([sh.id for sh in g.skysea.ships] + [0]) + 1
        if "ops" not in g.__dict__:
            from .operations import Operations
            g.ops = Operations()
        if "mission" not in g.__dict__:
            g.mission = None
            g.setup = {}
            g.scenario = "front"
        if "hierarchy" not in g.__dict__:
            from .hierarchy import Hierarchy
            g.hierarchy = Hierarchy()
        return g

    def _reset_counters(self):
        import itertools
        from . import entities
        top = 1
        for a in self.actors:
            top = max(top, a.id)
            for it in a.inv:
                top = max(top, getattr(it, "iid", 0))
        for v in self.vehicles:
            top = max(top, v.id)
        entities._ids = itertools.count(top + 1)
        Squad._next = max([sq.id for sq in self.squads] + [0]) + 1

    @staticmethod
    def delete_save(path=None):
        path = path or os.path.join(SAVE_DIR, "save.pkl")
        try:
            os.remove(path)
        except OSError:
            pass
