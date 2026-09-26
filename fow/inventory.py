"""Grid inventory (in the spirit of Escape from Tarkov).

A soldier has equipment slots (helmet, coat, webbing, pack, primary/secondary
long guns, holster, melee) and pockets.  Webbing and packs are made of grids;
items occupy w x h cells and may be rotated.  Magazines, stripper clips and
belts are individual items with round counts.  Bodies keep their kit.
"""
from __future__ import annotations

from .data.items import ITEMS

SLOTS = ("head", "body", "rig", "pack", "primary", "secondary", "holster", "melee")
SLOT_NAME = {"head": "Head", "body": "Body", "rig": "Webbing", "pack": "Pack", "primary": "Primary (sling)",
             "secondary": "On your back", "holster": "Holster", "melee": "Scabbard / belt"}
ACCESS = {"hands": 0, "primary": 110, "secondary": 180, "holster": 70, "melee": 60, "rig": 60,
          "pockets": 80, "pack": 260, "head": 120, "body": 200, "ground": 100, "carried": 100}


def item_size(t) -> tuple[int, int]:
    s = t.get("size")
    if s:
        return s
    k = t.kind
    if k == "gun":
        c = t.cat
        return {"rifle": (5, 1), "sniper": (5, 1), "carbine": (4, 1), "smg": (3, 2), "assault": (4, 2),
                "lmg": (5, 2), "hmg": (5, 2), "pistol": (2, 1), "shotgun": (5, 1), "at_rifle": (6, 1),
                "at_launcher": (5, 1), "at_disposable": (4, 1), "flamer": (4, 2), "mortar": (4, 2)}.get(c, (4, 1))
    if k == "melee":
        return {"katana": (4, 1), "dadao": (3, 1), "szabla": (4, 1), "shovel": (2, 2), "kukri": (2, 1),
                "bayonet": (2, 1)}.get(t.id, (1, 1))
    if k == "grenade":
        return (1, 2) if t.gtype == "stick" else (1, 1)
    if k == "explosive":
        return (5, 1) if t.charge == "bangalore" else (2, 2) if t.charge in ("satchel", "bundle") else (1, 1)
    if k in ("ammo", "clip"):
        return (1, 2) if t.cal in ("rkt_bazooka", "rkt_schreck", "piat", "m81") else (1, 1)
    if k == "medical":
        return (2, 2) if t.med == "kit" else (1, 2) if t.med == "plasma" else (1, 1)
    if k == "armor":
        return (2, 2) if t.slot == "head" else (3, 3)
    if k == "tool":
        return {"radio": (3, 3), "binoculars": (2, 1), "wirecutters": (1, 2), "flaregun": (2, 1),
                "canteen": (1, 2), "wire": (3, 3), "sandbags": (2, 2), "detector": (2, 4), "ammo_crate": (4, 3),
                "pack": (3, 3)}.get(t.tool, (1, 1))
    if k == "container":
        return t.get("fold", (3, 3))
    if k == "corpse":
        return (6, 3)
    return (1, 1)


def stack_max(t) -> int:
    s = t.get("stack_max")
    if s:
        return s
    if t.kind == "ammo":
        w = t.weight
        if t.cal in ("rkt_bazooka", "rkt_schreck", "piat", "m81", "m60", "m50", "knee", "m45", "m46", "fuel"):
            return 1 if w > 1.0 else 3
        if w < 0.016:
            return 50
        if w < 0.035:
            return 30
        return 5
    if t.kind == "clip":
        return 3
    if t.kind == "medical":
        return {"bandage": 3, "morphine": 4, "sulfa": 3, "tourniquet": 2}.get(t.med, 1)
    if t.kind == "grenade" and t.gtype not in ("stick", "molotov", "at", "gammon"):
        return 1
    if t.tool in ("cigarettes", "ration", "letter", "photo"):
        return 2
    return 1


class Grid:
    __slots__ = ("w", "h", "name", "allow", "cells", "items")

    def __init__(self, w: int, h: int, name: str = "", allow=None):
        self.w = w
        self.h = h
        self.name = name
        self.allow = allow          # None = anything, else a set of allowed kinds / "small"
        self.cells = [[None] * h for _ in range(w)]
        self.items = []

    def allows(self, item) -> bool:
        if self.allow is None:
            return True
        t = item.t
        if "small" in self.allow and max(item_size(t)) <= 1:
            return True
        return t.kind in self.allow or t.get("cat") in self.allow

    def fits(self, item, x, y, rot, ignore=None) -> bool:
        w, h = item.dims(rot)
        if x < 0 or y < 0 or x + w > self.w or y + h > self.h:
            return False
        for i in range(x, x + w):
            col = self.cells[i]
            for j in range(y, y + h):
                o = col[j]
                if o is not None and o is not ignore:
                    return False
        return self.allows(item)

    def place(self, item, x, y, rot):
        w, h = item.dims(rot)
        for i in range(x, x + w):
            for j in range(y, y + h):
                self.cells[i][j] = item
        item.rot = rot
        item.grid = self
        item.gpos = (x, y)
        self.items.append(item)

    def remove(self, item):
        if item in self.items:
            self.items.remove(item)
        for col in self.cells:
            for j, o in enumerate(col):
                if o is item:
                    col[j] = None
        item.grid = None
        item.gpos = None

    def find_spot(self, item):
        if not self.allows(item):
            return None
        for rot in (False, True):
            w, h = item.dims(rot)
            if w > self.w or h > self.h:
                continue
            for y in range(self.h - h + 1):
                for x in range(self.w - w + 1):
                    if self.fits(item, x, y, rot):
                        return x, y, rot
        return None

    def item_at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.cells[x][y]
        return None

    def free_cells(self) -> int:
        return sum(1 for col in self.cells for o in col if o is None)


def container_grids(item) -> list:
    """The grids inside a container item (created on first use)."""
    if item.data is None:
        item.data = {}
    gs = item.data.get("grids")
    if gs is None:
        spec = item.t.get("grids") or ()
        gs = [Grid(w, h, name, set(allow) if allow else None) for (w, h, name, allow) in spec]
        item.data["grids"] = gs
    return gs


class Inventory:
    """Everything a soldier (or a body) carries."""

    def __init__(self):
        self.slots = {s: None for s in SLOTS}
        self.pockets = [Grid(1, 1, "pocket") for _ in range(4)]
        self.hands = None              # something carried in both hands (crate, second body...)

    # ------------------------------------------------------------ enumeration
    def grids(self):
        """(grid, location) for every grid, fastest to reach first."""
        out = []
        rig = self.slots["rig"]
        if rig is not None:
            out += [(g, "rig") for g in container_grids(rig)]
        out += [(g, "pockets") for g in self.pockets]
        body = self.slots["body"]
        if body is not None and body.t.get("grids"):
            out += [(g, "pockets") for g in container_grids(body)]
        pack = self.slots["pack"]
        if pack is not None and pack.t.get("grids"):
            out += [(g, "pack") for g in container_grids(pack)]
        return out

    def items(self):
        out = [it for it in self.slots.values() if it is not None]
        for g, _ in self.grids():
            out += g.items
        if self.hands is not None:
            out.append(self.hands)
        return out

    def location(self, item) -> str:
        for s, it in self.slots.items():
            if it is item:
                return s
        if self.hands is item:
            return "carried"
        for g, loc in self.grids():
            if item in g.items:
                return loc
        return "ground"

    def contains(self, item) -> bool:
        return self.location(item) != "ground"

    # ------------------------------------------------------------ adding and removing
    def _merge(self, item):
        t = item.t
        mx = stack_max(t)
        if mx <= 1 or item.data:
            return False
        for g, _ in self.grids():
            for o in g.items:
                if o.tid == item.tid and not o.data and o.count < mx:
                    room = mx - o.count
                    take = min(room, item.count)
                    o.count += take
                    item.count -= take
                    if item.count <= 0:
                        return True
        return False

    def best_slot(self, item) -> str | None:
        t = item.t
        k = t.kind
        if k == "armor":
            want = "head" if t.slot == "head" else "body"
            return want if self.slots[want] is None else None
        if k == "container":
            want = t.slot
            return want if self.slots.get(want) is None else None
        if item.tid == "backpack":
            return "pack" if self.slots["pack"] is None else None
        if t.tool == "radio" and self.slots["pack"] is None:
            return "pack"
        if k == "gun":
            if t.cat == "pistol":
                return "holster" if self.slots["holster"] is None else None
            if self.slots["primary"] is None:
                return "primary"
            if self.slots["secondary"] is None and item_size(t)[0] >= 3:
                return "secondary"
            return None
        if k == "melee":
            return "melee" if self.slots["melee"] is None else None
        return None

    def add(self, item, prefer: str | None = None) -> str | None:
        """Put an item somewhere sensible.  Returns the location, or None if there's no room."""
        if self._merge(item):
            return "merged"
        if prefer in SLOTS and self.slots[prefer] is None and self._slot_ok(item, prefer):
            self.slots[prefer] = item
            item.grid = None
            return prefer
        s = self.best_slot(item)
        if s is not None and prefer not in ("rig", "pack", "pockets"):
            self.slots[s] = item
            item.grid = None
            return s
        order = self._grid_order(item, prefer)
        for g, loc in order:
            spot = g.find_spot(item)
            if spot is not None:
                g.place(item, *spot)
                return loc
        if s is not None:
            self.slots[s] = item
            item.grid = None
            return s
        return None

    def _slot_ok(self, item, slot) -> bool:
        t = item.t
        if slot == "head":
            return t.kind == "armor" and t.slot == "head"
        if slot == "body":
            return t.kind == "armor" and t.slot == "body" or (t.kind == "container" and t.slot == "body")
        if slot == "rig":
            return t.kind == "container" and t.slot == "rig"
        if slot == "pack":
            return (t.kind == "container" and t.slot == "pack") or t.tool == "radio" or item.tid == "backpack"
        if slot in ("primary", "secondary"):
            return t.kind == "gun" and t.cat != "pistol" or (t.kind == "melee" and t.hands == 2)
        if slot == "holster":
            return t.kind == "gun" and t.cat == "pistol"
        if slot == "melee":
            return t.kind == "melee"
        return False

    def _grid_order(self, item, prefer):
        gs = self.grids()
        small = max(item.dims(False)) <= 2
        k = item.t.kind
        def rank(entry):
            g, loc = entry
            if prefer and loc == prefer:
                return 0
            if k in ("mag", "clip", "grenade") or (k == "ammo" and small):
                return {"rig": 1, "pockets": 2, "pack": 3}[loc]
            if k in ("medical",) or item.t.tool in ("watch", "compass", "map", "orders", "letter", "photo",
                                                     "dogtags", "rosary", "coin", "cigarettes", "cards"):
                return {"pockets": 1, "rig": 2, "pack": 3}[loc]
            return {"pack": 1, "rig": 2, "pockets": 3}[loc] if not small else {"rig": 1, "pockets": 2, "pack": 3}[loc]
        return sorted(gs, key=rank)

    def remove(self, item) -> bool:
        for s, it in self.slots.items():
            if it is item:
                self.slots[s] = None
                return True
        if self.hands is item:
            self.hands = None
            return True
        g = getattr(item, "grid", None)
        if g is not None:
            g.remove(item)
            return True
        for gg, _ in self.grids():
            if item in gg.items:
                gg.remove(item)
                return True
        return False

    def move(self, item, dest, x=0, y=0, rot=False) -> bool:
        """Move an item to a grid position or an equipment slot name."""
        if isinstance(dest, str):
            if dest not in SLOTS or not self._slot_ok(item, dest):
                return False
            cur = self.slots[dest]
            if cur is not None and cur is not item:
                return False
            self.remove(item)
            self.slots[dest] = item
            item.grid = None
            return True
        if not dest.fits(item, x, y, rot, ignore=item):
            return False
        self.remove(item)
        dest.place(item, x, y, rot)
        return True

    # ------------------------------------------------------------ weight
    def weight(self) -> float:
        w = 0.0
        for it in self.items():
            w += it.weight
            if it.t.kind == "container":
                pass
        return w
