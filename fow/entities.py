"""Items, soldiers and vehicles."""
from __future__ import annotations

import itertools

from .body import Body
from .constants import BASE_SPEED, SIDE_COLOR
from .data.items import ITEMS, ammo_id
from .data.nations import NATIONS, rank_name
from .data.roles import ROLES
from .data.vehicles import MOUNTS, VEHICLES

_ids = itertools.count(1)

FEMALE_NAMES = {"Lyudmila", "Roza", "Nina", "Maria", "Natalya", "Klavdiya", "Mariya", "Yevdokiya",
                "Olga", "Tatiana", "Valentina", "Irina"}

# where an item can be carried, and how long it takes to get it out (moves)
LOCATIONS = ("hands", "sling", "belt", "pockets", "pack", "worn", "carried")
from .inventory import ACCESS as ACCESS_COST  # noqa: E402
LOC_NAME = {"hands": "in your hands", "primary": "slung", "secondary": "on your back", "holster": "in the holster",
            "melee": "on your belt", "rig": "in your webbing", "pockets": "in your pockets", "pack": "in your pack",
            "head": "worn", "body": "worn", "carried": "in your hands", "ground": "on the ground"}


class Item:
    __slots__ = ("tid", "count", "loaded", "jammed", "heat", "uses", "mode", "data", "where",
                 "iid", "known_rounds", "grid", "gpos", "rot", "mag_item")

    def __init__(self, tid: str, count: int = 1, full: bool = True):
        self.iid = next(_ids)
        self.tid = tid
        t = ITEMS[tid]
        self.count = count
        self.loaded = 0
        self.mag_item = None
        self.grid = None
        self.gpos = None
        self.rot = False
        if t.kind == "gun":
            if t.cat == "at_disposable":
                self.loaded = 1
            elif t.get("magtype"):
                # magazine-fed: a full magazine is seated
                m = Item(t.magtype, full=full)
                self.mag_item = m
                self.loaded = m.loaded
            else:
                self.loaded = t.mag if full else 0
        elif t.kind in ("mag", "clip"):
            self.loaded = t.mag if full else 0
        self.jammed = False
        self.heat = 0.0
        self.uses = t.uses
        self.mode = len(t.modes) - 1 if t.kind == "gun" else 0
        self.data = None
        self.where = "ground"
        self.known_rounds = True

    @property
    def t(self):
        return ITEMS[self.tid]

    def dims(self, rot=None):
        from .inventory import item_size
        w, h = item_size(self.t)
        if rot is None:
            rot = self.rot
        return (h, w) if rot else (w, h)

    @property
    def weight(self) -> float:
        t = self.t
        if t.kind == "ammo":
            return t.weight * self.count
        if t.kind == "mag":
            return t.weight + self.loaded * t.get("round_weight", 0.02)
        if t.kind == "clip":
            return self.count * (t.weight + t.mag * t.get("round_weight", 0.02))
        if t.kind == "container" and self.data and self.data.get("grids"):
            return t.weight + sum(i.weight for g in self.data["grids"] for i in g.items)
        if t.kind == "corpse":
            return t.weight
        return t.weight * self.count

    @property
    def volume(self) -> float:
        w, h = self.dims(False)
        return w * h * 0.5

    @property
    def name(self) -> str:
        t = self.t
        if t.kind == "corpse" and self.data:
            return f"corpse of {self.data.get('name', 'a soldier')}"
        if t.kind == "ammo":
            return f"{self.count} x {t.name}"
        if t.kind == "mag":
            return t.name
        if t.kind == "clip" and self.count > 1:
            return f"{self.count} x {t.name}"
        if self.count > 1:
            return f"{self.count} x {t.name}"
        if t.kind == "tool" and t.uses > 1 and self.uses < t.uses:
            return f"{t.name} ({self.uses} left)"
        return t.name

    def short(self) -> str:
        return self.t.get("short") or self.t.name

    @property
    def mode_name(self) -> str:
        t = self.t
        if t.kind != "gun":
            return ""
        return t.modes[self.mode % len(t.modes)]

    def rounds_text(self) -> str:
        """What you know about the rounds in a magazine (Tarkov-style: you have to check)."""
        t = self.t
        if t.kind not in ("mag", "gun"):
            return ""
        cap = t.mag
        if self.known_rounds:
            return f"{self.loaded}/{cap}"
        r = self.loaded / max(1, cap)
        if self.loaded == 0:
            return "empty"
        return "full" if r > 0.85 else "most" if r > 0.55 else "about half" if r > 0.3 else "low"

    def ammo_estimate(self) -> str:
        """Diegetic magazine state."""
        t = self.t
        if t.kind != "gun":
            return ""
        if t.cat in ("at_disposable",):
            return "ready" if self.loaded else "spent"
        if t.cat == "mortar":
            return ""
        if self.jammed:
            return "JAMMED"
        if t.get("magtype") and self.mag_item is None:
            return "no magazine"
        if t.mag <= 1:
            return "loaded" if self.loaded else "empty"
        if self.known_rounds:
            return f"{self.loaded}/{t.mag}"
        r = self.loaded / t.mag
        if self.loaded == 0:
            return "empty"
        if r > 0.85:
            return "full"
        if r > 0.55:
            return "most"
        if r > 0.3:
            return "about half"
        if r > 0.12:
            return "low"
        return "nearly empty"


def make_corpse(actor) -> Item:
    c = Item("corpse")
    c.data = dict(name=actor.full_name, nation=actor.nation, side=actor.side,
                  cause=actor.body.cause, role=actor.role, id=actor.id, inv=actor.invent)
    return c


class Actor:
    """A soldier."""

    def __init__(self, nation: str, role: str, rank: int, name: str, x: int = 0, y: int = 0):
        self.id = next(_ids)
        self.nation = nation
        self.side = NATIONS[nation]["side"]
        self.role = role
        self.rank = rank
        self.name = name
        self.x = x
        self.y = y
        self.stance = 0                 # 0 standing, 1 crouching, 2 prone
        self.body = Body()
        from .inventory import Inventory
        self.invent = Inventory()
        self.weapon: Item | None = None
        self.skill = 5.0
        self.bravery = 50.0
        self.morale = 60.0
        self.suppression = 0.0
        self.moves = 0
        self.squad = None
        self.vehicle = None
        self.is_player = False
        self.state = "ok"               # ok, surrendered, fled, captured
        self.kills = 0
        self.xp = 0
        self.aim_target = None
        self.aim_turns = 0              # aim level on aim_target (0 snap .. 4 dead steady)
        self.recoil = 0.0               # degrees of muzzle still coming down from the last shots
        self.moved_turn = -99
        self.fired_turn = -99
        self.hit_turn = -99
        self.deployed = False
        self.entangled = 0
        self.shout = None               # (text, until_turn)
        self.traits: set[str] = set()
        self.ai: dict = {}
        self.known: dict = {}           # enemy id -> (x, y, turn, kind)
        self.visible: list = []         # cached visible enemies
        self.vis_turn = -99
        self.unit = ""
        self.dig_progress = 0
        self.last_sound = None
        self.carrying = None            # wounded comrade being dragged
        self.stats = dict(shots=0, hits=0, distance=0, grenades=0, bandaged=0)
        self.orders_text = ""
        self.female = name.split()[0] in FEMALE_NAMES
        self.stamina = 100.0            # breath: spent moving (crawling, heavy loads), regained at rest
        self.fatigue = 0.0              # the long account: hours of exertion; caps breath until you rest
        self.pace = "walk"              # walk / run / sprint (the player's choice; the AI picks its own)

    @property
    def his(self) -> str:
        return "her" if self.female else "his"

    @property
    def him(self) -> str:
        return "her" if self.female else "him"

    @property
    def himself(self) -> str:
        return "herself" if self.female else "himself"

    # ------------------------------------------------------------ naming
    @property
    def rank_short(self) -> str:
        return rank_name(self.nation, self.rank, True, self.__dict__.get("service", "army"))

    @property
    def rank_full(self) -> str:
        return rank_name(self.nation, self.rank, False, self.__dict__.get("service", "army"))

    @property
    def full_name(self) -> str:
        return f"{self.rank_short} {self.name}"

    @property
    def role_name(self) -> str:
        return ROLES.get(self.role, {}).get("name", self.role)

    @property
    def last_name(self) -> str:
        return self.name.split()[-1]

    def describe_short(self) -> str:
        return f"{NATIONS[self.nation]['adj']} {self.role_name.lower()}"

    # ------------------------------------------------------------ state
    @property
    def alive(self) -> bool:
        return not self.body.dead

    @property
    def active(self) -> bool:
        """Alive, conscious, not surrendered - can act."""
        return self.body.alive and self.body.conscious and self.state == "ok"

    @property
    def downed(self) -> bool:
        return self.body.downed() or not self.body.conscious

    @property
    def pos(self):
        return (self.x, self.y)

    @property
    def color(self):
        return SIDE_COLOR[self.side]

    def is_officer(self) -> bool:
        return self.role == "officer"

    def is_leader(self) -> bool:
        return self.squad is not None and self.squad.leader is self

    # ------------------------------------------------------------ inventory
    @property
    def inv(self) -> list:
        return self.invent.items()

    @property
    def helmet(self):
        return self.invent.slots["head"]

    @helmet.setter
    def helmet(self, item):
        self.invent.slots["head"] = item
        if item is not None:
            item.where = "head"

    def loc(self, item) -> str:
        return self.invent.location(item)

    def access_cost(self, item) -> int:
        from .inventory import ACCESS
        return ACCESS.get(self.loc(item), 100)

    def carried_weight(self) -> float:
        return self.invent.weight()

    def has_pack(self) -> bool:
        return self.invent.slots["pack"] is not None

    def add_item(self, item: Item, where: str | None = None) -> Item | None:
        loc = self.invent.add(item, prefer=where)
        if loc is None:
            return None
        if loc != "merged":
            item.where = loc
        return item

    def remove_item(self, item: Item, count: int | None = None) -> Item:
        if count is not None and count < item.count:
            item.count -= count
            new = Item(item.tid, count)
            new.loaded = item.loaded
            return new
        self.invent.remove(item)
        if self.weapon is item:
            self.weapon = None
        item.where = "ground"
        return item

    def find(self, pred) -> Item | None:
        for i in self.inv:
            if pred(i):
                return i
        return None

    def items_of(self, pred) -> list[Item]:
        return [i for i in self.inv if pred(i)]

    def ammo_for(self, gun: Item | None) -> Item | None:
        from .ammo import best_source
        return best_source(self, gun)

    def ammo_count(self, gun: Item | None) -> int:
        from .ammo import spare_rounds
        return spare_rounds(self, gun)

    def grenades(self, kinds=None) -> list[Item]:
        return [i for i in self.inv if i.t.kind == "grenade" and (kinds is None or i.t.gtype in kinds)
                and not (i.data and i.data.get("dud"))]

    def has_tool(self, tool: str) -> Item | None:
        for i in self.inv:
            if i.t.tool == tool or (tool == "shovel" and i.tid == "shovel"):
                return i
        return None

    def wield(self, item: Item | None) -> bool:
        """Take an item into your hands.  It lives in a weapon slot (or your hands)."""
        self.deployed = False
        self.aim_turns = 0
        if item is None:
            self.weapon = None
            return True
        inv = self.invent
        loc = inv.location(item)
        if loc in ("primary", "secondary", "holster", "melee", "carried"):
            self.weapon = item
            return True
        if loc != "ground":
            inv.remove(item)
        slot = inv.best_slot(item)
        if slot in ("primary", "secondary", "holster", "melee"):
            inv.slots[slot] = item
            item.where = slot
        elif inv.hands is None:
            inv.hands = item
            item.where = "carried"
        else:
            # hands full: put what's there away first
            old = inv.hands
            inv.hands = None
            if inv.add(old) is None:
                inv.hands = old
                if loc != "ground":
                    inv.add(item)
                return False
            inv.hands = item
            item.where = "carried"
        self.weapon = item
        return True

    def medical(self, med: str) -> Item | None:
        best = None
        for i in self.inv:
            if i.t.kind == "medical" and (i.t.med == med or (med == "bandage" and i.t.med == "kit")):
                if best is None or (best.t.med == "kit" and i.t.med != "kit"):
                    best = i
        return best

    # ------------------------------------------------------------ physical
    def encumbrance(self, turn: int | None = None) -> float:
        w = self.carried_weight() if turn is None else self.weight_now(turn)
        cap = 26.0
        if w <= cap:
            return 1.0
        return max(0.35, 1.0 - (w - cap) * 0.02)

    def speed(self, turn: int | None = None) -> int:
        breath = 0.6 + 0.4 * min(1.0, getattr(self, "stamina", 100.0) / 30.0)
        cold = 1.0
        if "temp" in self.body.__dict__:
            from .thermal import speed_mult
            cold = speed_mult(self)
        tired = 1.0 - max(0.0, self.__dict__.get("fatigue", 0.0) - 60) / 200.0
        return int(BASE_SPEED * self.body.speed_mult() * self.encumbrance(turn) * breath * cold * tired)

    def weight_now(self, turn: int) -> float:
        """Carried weight, recomputed every few seconds (it doesn't change often)."""
        c = self.ai.get("_wt")
        if c is not None and c[0] == turn // 10:
            return c[1]
        w = self.carried_weight()
        self.ai["_wt"] = (turn // 10, w)
        return w

    def breath_word(self) -> str | None:
        st = getattr(self, "stamina", 100.0)
        if st < 8:
            return "Exhausted"
        if st < 20:
            return "Winded"
        if st < 40:
            return "Breathing hard"
        return None

    def say(self, text: str, turn: int, duration: int = 3, voice: str | None = None, tone: str | None = None):
        """A speech bubble - and, for the sound system, the line as it's actually spoken."""
        self.shout = (text, turn + duration)
        if text:
            self.spoken = (voice if voice is not None else text, turn,
                           tone or ("shout" if text.rstrip().endswith("!") else "talk"))

    def weapon_ready(self) -> bool:
        w = self.weapon
        return w is not None and w.t.kind == "gun" and not w.jammed and w.loaded > 0


class Vehicle:
    def __init__(self, vid: str, side: str, nation: str, x: int, y: int, facing: int = 0):
        self.id = next(_ids)
        self.vid = vid
        self.vt = VEHICLES[vid]
        vt = self.vt
        self.side = side
        self.nation = nation
        self.x = x
        self.y = y
        self.facing = facing
        self.base_facing = facing       # an emplaced gun's carriage doesn't turn with the barrel
        self.turret = facing
        self.hp = vt.hp
        from .vdamage import parts_for
        self.parts = parts_for(vt)      # tracks, engine, gun, turret ring, sights... (vdamage.py)
        self.crew = vt.crew
        self.passengers: list[Actor] = []
        self.ap = vt.ap
        self.he = vt.he
        self.mg_ammo = 1500 * len(vt.mgs) if vt.mgs else 0
        self.player_station = None      # your seat, when you're one of the crew
        self.reload = 0
        self.moves = 0
        self.burning = 0
        self.dead = False
        self.abandoned = False
        self.squad = None
        self.ai: dict = {}
        self.player_crewed = False
        self.smoke = vt.smoke
        self.stuck = 0
        self.fired_turn = -99
        self.moved_turn = -99
        self.known: dict = {}
        self.visible: list = []
        self.vis_turn = -99
        self.crew_actors: list[Actor] = []
        self.name = vt.name
        self.ammo_choice = "ap"
        self.buttoned = True
        self.state = "ok"
        self.kills = 0

    @property
    def pos(self):
        return (self.x, self.y)

    # ------------------------------------------------------------ its parts (see vdamage.py)
    @property
    def engine(self) -> bool:
        return self.parts.get("engine", 2) > 0

    @engine.setter
    def engine(self, ok):
        if "engine" in self.parts:
            self.parts["engine"] = 2 if ok else 0

    @property
    def tracks(self) -> bool:
        return self.parts.get("tracks", 2) > 0 and self.parts.get("transmission", 2) > 0

    @tracks.setter
    def tracks(self, ok):
        if "tracks" in self.parts:
            self.parts["tracks"] = 2 if ok else 0

    @property
    def gun_ok(self) -> bool:
        return self.parts.get("gun", 0) > 0

    @gun_ok.setter
    def gun_ok(self, ok):
        if "gun" in self.parts:
            self.parts["gun"] = 2 if ok else 0

    def __setstate__(self, st):
        # saves from before vehicles had parts: engine / tracks / gun_ok were plain flags
        eng, trk, gun = st.pop("engine", True), st.pop("tracks", True), st.pop("gun_ok", True)
        self.__dict__.update(st)
        if "parts" not in st:
            from .vdamage import parts_for
            self.parts = parts_for(self.vt)
            self.engine, self.tracks, self.gun_ok = eng, trk, gun

    # ------------------------------------------------------------ the ground it covers
    @property
    def size(self):
        s = self.__dict__.get("_size")
        if s is None:
            from .footprint import vehicle_size
            s = self._size = vehicle_size(self.vt)
        return s

    @property
    def body_facing(self) -> int:
        if self.vt.static:
            return self.__dict__.get("base_facing", self.facing)
        return self.facing

    def cells(self, x=None, y=None, facing=None) -> list:
        from .footprint import offsets
        L, W = self.size
        x = self.x if x is None else x
        y = self.y if y is None else y
        f = self.body_facing if facing is None else facing
        return [(x + dx, y + dy) for dx, dy in offsets(L, W, f)]

    def near(self, x, y) -> int:
        """Chebyshev distance from a tile to the nearest part of the vehicle."""
        return min(max(abs(cx - x), abs(cy - y)) for cx, cy in self.cells())

    @property
    def mount(self):
        return MOUNTS.get(self.vt.main) if self.vt.main else None

    @property
    def alive(self) -> bool:
        return not self.dead

    @property
    def active(self) -> bool:
        return not self.dead and not self.abandoned and self.crew > 0

    @property
    def static(self) -> bool:
        return self.vt.static

    @property
    def mobile(self) -> bool:
        return self.active and self.engine and self.tracks and not self.static

    def speed(self) -> int:
        # vt.speed is moves per tile; convert to moves gained per turn (100 base)
        return 100

    def move_cost(self, tile_vcost: int) -> int:
        vt = self.vt
        base = vt.speed
        mult = tile_vcost / 100.0
        if vt.vtype in ("car", "truck", "armcar") and tile_vcost > 100:
            mult *= 1.4
        from .vdamage import move_mult
        return max(20, int(base * mult * move_mult(self)))

    def describe_short(self) -> str:
        return f"{NATIONS[self.nation]['adj']} {self.name}"

    def status_text(self) -> str:
        if self.dead:
            return "destroyed"
        if self.abandoned:
            return "abandoned"
        bits = []
        if self.burning:
            bits.append("burning")
        from .vdamage import damage_list
        bits += damage_list(self)
        r = self.hp / self.vt.hp
        if r < 0.35:
            bits.append("badly damaged")
        elif r < 0.75:
            bits.append("damaged")
        return ", ".join(bits) or "operational"
