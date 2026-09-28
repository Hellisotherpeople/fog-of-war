"""Squad, soldier, vehicle and commander AI.

Movement is decided by rolling downhill on a weighted sum of Dijkstra maps
(see brain.py).  Behaviour states only change the weights:

  advance        objective(covered) 1.0, exposure 3, cohesion
  bound          objective(covered) 1.0, exposure 6        (half the squad at a time)
  take cover     safety 1.0, objective 0.1
  assault        threat_dist 1.0, exposure 0.5
  flank          flank map 1.0, exposure 4
  keep range     |threat_dist - R| 1.0, exposure 2          (MGs, snipers, tanks)
  retreat        home 1.0, exposure 3
  rout           flee 1.0
  banzai         threat_dist 1.0
"""
from __future__ import annotations

import math

import numpy as np
import tcod

from . import actions as A
from . import tiles as T
from .brain import contact_kind
from .combat import aim_level, aim_time, estimate_hit, hit_vehicle, max_aim, vehicle_fire_main, vehicle_fire_mg
from .constants import BIG, other_side
from .data.items import ITEMS
from .data.nations import NATIONS
from .data.phrases import phrase
from .footprint import FACING_VEC
from .gamemap import octant
from .senses import update_actor_vision

UNIT = 4.0   # dijkstra units per tile (cost 2 * cardinal 2)


ROE_NAME = {"free": "fire at will", "return": "return fire only", "hold": "hold fire"}


class Order:
    __slots__ = ("kind", "target", "obj", "radius", "issued", "src", "roe", "until")

    def __init__(self, kind: str, target=None, obj=None, radius=6, issued=0, src="ai", roe="free"):
        # attack, assault, defend, move, hold, retreat, follow, suppress, flank, ambush, dig,
        # mount, dismount, regroup
        self.kind = kind
        self.target = target
        self.obj = obj
        self.radius = radius
        self.issued = issued
        self.src = src            # "ai" (the side's plan) or "player" (your orders stand until changed)
        self.roe = roe            # free / return / hold
        self.until = None

    def __setstate__(self, state):
        # saves from before orders had a source and rules of engagement
        slots = state[1] if isinstance(state, tuple) else state
        self.src = "ai"
        self.roe = "free"
        self.until = None
        for k, v in (slots or {}).items():
            setattr(self, k, v)

    def describe(self, game) -> str:
        m = game.map
        if self.obj is not None and self.obj < len(m.objectives):
            name = m.objectives[self.obj].name
        else:
            name = "the marked position"
        return {"attack": f"Take {name}", "defend": f"Hold {name}", "move": f"Move to {name}",
                "hold": "Hold this position", "retreat": "Fall back", "follow": "Follow the leader",
                "assault": f"Assault {name}", "suppress": f"Suppress {name}", "flank": f"Flank {name}",
                "ambush": f"Ambush at {name}", "dig": "Dig in", "mount": "Mount up",
                "dismount": "Dismount", "regroup": "Regroup on the leader",
                "resupply": "Draw ammunition"}.get(self.kind, self.kind)


class Squad:
    _next = 1

    def __init__(self, side: str, nation: str, kind: str, name: str = ""):
        self.id = Squad._next
        Squad._next += 1
        self.side = side
        self.nation = nation
        self.kind = kind
        self.name = name or f"squad {self.id}"
        self.members: list = []
        self.vehicles: list = []
        self.leader = None
        self.order = Order("hold")
        self.state = "idle"
        self.state_turn = 0
        self.last_contact = -999
        self.morale = 60.0
        self.initial = 0
        self.positions: dict = {}
        self.phase = 0
        self.flank_target = None
        self.home_edge = None
        self.player_led = False
        self.arrived = False
        self.embarked = None
        self.casualty_report = 0
        self.shouted = {}
        self.positions_order = None
        # command
        self.formation = None
        self.gone = False
        self.short = ""
        self.callsign = ""
        self.leader_grade = 3        # for crews with no individual leader on the map (tanks, guns)
        self.next_report = 0
        self.rep = {}                # what the unit last told its commander

    def active_members(self):
        return [m for m in self.members if m.active and m.vehicle is None]

    def alive_members(self):
        return [m for m in self.members if m.alive and m.state == "ok"]

    def strength(self) -> float:
        s = sum(1 for m in self.members if m.active and not m.downed)
        s += sum(4 for v in self.vehicles if v.active)
        return s

    def anchor(self):
        if self.leader is not None and self.leader.active:
            if self.leader.vehicle is not None:
                return self.leader.vehicle.pos
            return self.leader.pos
        act = self.active_members()
        if act:
            return (sum(m.x for m in act) // len(act), sum(m.y for m in act) // len(act))
        if self.vehicles:
            v = self.vehicles[0]
            return v.pos
        return None


# ====================================================================== movement helpers

def crowd_penalty(game, a, x, y, mates=None) -> float:
    """Discourage bunching up: one buddy is fine, a clump draws fire."""
    if mates is None:
        mates = _mates_near(game, a)
    n = sum(1 for mx, my in mates if abs(mx - x) <= 1 and abs(my - y) <= 1)
    return max(0, n - 1) * 1.2


def _mates_near(game, a):
    """Friends within two tiles (every step a man considers is within one of him)."""
    sa = game.soldier_at
    out = []
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            o = sa.get((a.x + dx, a.y + dy))
            if o is not None and o is not a and o.side == a.side:
                out.append((o.x, o.y))
    return out


def best_step(game, a, maps, exposure_w=0.0, cohesion=None, spread=4, stay_bias=0.0,
              avoid_fire=True, crowd=True, keep_range=None):
    """Choose the neighbour (or stay) minimising the weighted desire.  Returns (dx,dy) or None."""
    m = game.map
    brain = game.brains[a.side]
    exp = brain.exposure if exposure_w else None
    rng = game.rng
    best = None
    best_score = None
    mates = _mates_near(game, a) if crowd else None
    # (this runs for every man who moves, every second: locals, and .item() for single cells)
    mt, fire, mines = m.t, m.fire, m.mines
    walk_t, door_t, water_t = T.WALK, T.DOOR, T.WATER
    sa, va = game.soldier_at, game.vehicle_at
    w_, h_ = m.w, m.h
    side = a.side
    half = BIG // 2
    live = [(mp, w) for mp, w in maps if mp is not None and w != 0]
    kr = keep_range if keep_range is not None and keep_range[0] is not None else None
    ax, ay = a.x, a.y
    for dx in (-1, 0, 1):
        x = ax + dx
        if x < 0 or x >= w_:
            continue
        for dy in (-1, 0, 1):
            y = ay + dy
            if y < 0 or y >= h_:
                continue
            stay = dx == 0 and dy == 0
            s = 0.0
            if not stay:
                tid = mt.item(x, y)
                if not (walk_t[tid] or door_t[tid]):
                    continue
                if (x, y) in va:
                    continue
                o = sa.get((x, y))
                if o is not None:
                    if o.side != side or o.is_player or o.downed:
                        continue
                    s = 2 * UNIT
            ok = True
            for mp, w in live:
                v = mp.item(x, y)
                if v >= half:
                    ok = False
                    break
                s += w * v
            if not ok:
                continue
            if kr is not None:
                v = kr[0].item(x, y)
                if v < half:
                    s += kr[2] * abs(v - kr[1] * UNIT)
            if exp is not None:
                s += exposure_w * exp.item(x, y) * UNIT
            if cohesion is not None:
                d = max(abs(x - cohesion[0]), abs(y - cohesion[1]))
                if d > spread:
                    s += (d - spread) * UNIT * 1.5
            if mates:
                s += crowd_penalty(game, a, x, y, mates)
            if avoid_fire and fire.item(x, y) > 0:
                s += 60
            if not stay:
                mn = mines.get((x, y))
                if mn is not None and side in mn.known:
                    s += 200
                if water_t[tid] >= 2:
                    s += 40
                # moving costs a little so units don't jitter
                s += 0.4
            else:
                s -= stay_bias
            s += rng.random() * 0.5
            if best_score is None or s < best_score:
                best_score = s
                best = (dx, dy)
    if best is None or best == (0, 0):
        return None
    return best


def do_step(game, a, step) -> int | None:
    if step is None:
        return None
    cost = A.move(game, a, step[0], step[1])
    return cost


def path_step(game, a, tx, ty, margin=10) -> int | None:
    """Follow a short A*-style path to (tx,ty) computed on a cropped window."""
    if (a.x, a.y) == (tx, ty):
        return None
    ai = a.ai
    path = ai.get("path")
    if path and ai.get("path_goal") == (tx, ty) and ai.get("path_turn", -99) > game.turn - 15:
        if path and path[0] == (a.x, a.y):
            path.pop(0)
        if path:
            nx, ny = path[0]
            if max(abs(nx - a.x), abs(ny - a.y)) == 1:
                o = game.soldier_at.get((nx, ny))
                if o is None or (o.side == a.side and not o.is_player and not o.downed):
                    c = A.move(game, a, nx - a.x, ny - a.y)
                    if c is not None:
                        if (a.x, a.y) == (nx, ny):
                            path.pop(0)
                        return c
    m = game.map
    x0 = max(0, min(a.x, tx) - margin)
    x1 = min(m.w, max(a.x, tx) + margin + 1)
    y0 = max(0, min(a.y, ty) - margin)
    y1 = min(m.h, max(a.y, ty) + margin + 1)
    brain = game.brains[a.side]
    cost = brain.exp_cost[x0:x1, y0:y1].copy() if brain.exp_cost is not None else \
        np.maximum(1, T.COST[m.t[x0:x1, y0:y1]] // 50).astype(np.int32)
    # doors are passable
    doors = T.DOOR[m.t[x0:x1, y0:y1]] == 1
    cost[doors] = 3
    # other soldiers are soft obstacles
    for (sx, sy), o in game.soldier_at.items():
        if x0 <= sx < x1 and y0 <= sy < y1 and o is not a:
            if cost[sx - x0, sy - y0] > 0:
                cost[sx - x0, sy - y0] += 8
    if cost[tx - x0, ty - y0] == 0:
        # target not walkable: go next to it
        cost[tx - x0, ty - y0] = 1
    try:
        p = tcod.path.path2d(cost, start_points=[(a.x - x0, a.y - y0)],
                             end_points=[(tx - x0, ty - y0)], cardinal=2, diagonal=3)
    except Exception:
        return None
    pts = [(int(px) + x0, int(py) + y0) for px, py in p]
    if len(pts) < 2:
        return None
    ai["path"] = pts[1:]
    ai["path_goal"] = (tx, ty)
    ai["path_turn"] = game.turn
    nx, ny = pts[1]
    if (nx, ny) == (tx, ty) and not T.WALK[m.t[nx, ny]] and not T.DOOR[m.t[nx, ny]]:
        return None
    c = A.move(game, a, nx - a.x, ny - a.y)
    if c is not None and (a.x, a.y) == (nx, ny):
        ai["path"].pop(0)
    return c


def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def friends_in_line(game, a, tx, ty, cone=0.04, extra=12.0) -> bool:
    """True if a friendly soldier is inside the cone of fire short of (or just past) the target."""
    pos, acts = game.actor_array()
    if not acts:
        return False
    x0, y0 = a.x, a.y
    dx, dy = tx - x0, ty - y0
    L = math.hypot(dx, dy)
    if L < 0.5:
        return False
    ux, uy = dx / L, dy / L
    rel = pos - np.array([x0, y0], np.float32)
    along = rel[:, 0] * ux + rel[:, 1] * uy
    perp = np.abs(rel[:, 0] * uy - rel[:, 1] * ux)
    idx = np.nonzero((along > 0.4) & (along < L + extra) & (perp < 1.1 + along * cone))[0]
    renegade = getattr(game, "renegade", False)
    for k in idx:
        o = acts[k]
        if o is not a and o.side == a.side and o.alive and not (renegade and o.is_player):
            return True
    return False


def safe_fire(game, a, tx, ty, target=None, area=False):
    """Fire only if no friend is in the way; otherwise shuffle sideways."""
    w = a.weapon
    cone = 0.04 if w is None or w.t.kind != "gun" else max(0.03, math.radians(w.t.disp * 2.5))
    if friends_in_line(game, a, tx, ty, cone=cone + (0.03 if area else 0)):
        brain = game.brains[a.side]
        st = best_step(game, a, [(brain.safety, 0.3)], exposure_w=0.5) if brain.safety is not None else None
        c = do_step(game, a, st)
        return c or 100
    return A.fire(game, a, tx, ty, target, area=area) or 100


# ====================================================================== targeting

def respects_red_cross(shooter, e) -> bool:
    """An unarmed medic wearing the armband: most armies held their fire.  The Japanese didn't, and
    on the Eastern Front neither side did."""
    if e.role not in ("medic", "surgeon") or not e.has_tool("brassard"):
        return False
    w = e.weapon
    if w is not None and w.t.kind == "gun":
        return False                              # a medic with a rifle in his hands is a rifleman
    if shooter.nation == "japan":
        return False
    east = {shooter.nation, e.nation}
    if "ussr" in east and east & {"germany", "finland", "hungary", "romania", "italy"}:
        return False
    return True


def threat_value(e, shooter) -> float:
    if getattr(e, "vt", None) is not None:
        return 5.0
    if e.state != "ok":
        return 0.0
    if respects_red_cross(shooter, e):
        return 0.05                               # not a target - though bullets don't read armbands
    if e.downed:
        return 0.15
    k = contact_kind(e)
    v = {"mg": 3.0, "hmg": 3.5, "sniper": 2.5, "officer": 2.2, "mortar": 1.4}.get(k, 1.0)
    if e.role in ("at_soldier",) and shooter.squad and shooter.squad.vehicles:
        v = 3.0
    if e.role == "radioman":
        v = 1.8
    if e.is_player:
        v *= 1.0
    return v


def can_hurt_vehicle(a, v) -> bool:
    w = a.weapon
    if w is None or w.t.kind != "gun":
        return False
    t = w.t
    if t.cat in ("at_launcher", "at_disposable"):
        return True
    if t.cat == "at_rifle":
        return min(v.vt.armor[1], v.vt.armor[2]) < t.pen + 5
    if v.vt.open_top or v.static or max(v.vt.armor[:3]) <= 6:
        return True
    if t.pen and min(v.vt.armor[:3]) < t.pen:
        return True
    return False


def choose_target(game, a, vis):
    w = a.weapon
    if w is None or w.t.kind != "gun":
        return None
    best = None
    best_s = 0.0
    for e in vis:
        if getattr(e, "vt", None) is not None:
            if e.dead or e.abandoned or not can_hurt_vehicle(a, e):
                continue
            d = dist(a, e)
            if d > w.t.rng * 1.2:
                continue
            s = 6.0 / (1 + d / 20)
        else:
            if not e.alive or e.state != "ok":
                continue
            d = dist(a, e)
            if w.t.cat in ("at_launcher", "at_disposable"):
                # don't waste rockets on single riflemen unless close or in a building
                if d > 12 and not T.FLOOR[game.map.t[e.x, e.y]]:
                    continue
            if respects_red_cross(a, e) and (w.t.cat == "sniper" or d > 3):
                continue                          # a man picking his shot doesn't pick the medic
            p = estimate_hit(game, a, w, e)
            s = threat_value(e, a) * (0.2 + p) / (1 + d / 30)
            if e.is_player:
                s *= 1.05
        if s > best_s:
            best_s = s
            best = e
    return best


def in_cover_from(game, a, ex, ey) -> float:
    m = game.map
    return max(m.cover_toward(a.x, a.y, ex, ey), float(m.pos_cover[a.x, a.y]))


def want_stance(game, a, engaged: bool, moving: bool, threat_close: bool) -> int:
    m = game.map
    pos = m.pos_cover[a.x, a.y]
    if m.water[a.x, a.y] >= 1:
        return 1
    if a.body.downed():
        return 2
    if not engaged:
        return 0 if moving else (1 if a.suppression > 5 or pos > 30 else 0)
    if pos >= 45:
        return 1 if not moving else 1
    if moving:
        return 2 if a.suppression > 55 else 1
    w = a.weapon
    if w is not None and w.t.kind == "gun" and w.t.cat in ("lmg", "hmg", "sniper", "mortar", "at_rifle"):
        return 2
    if threat_close:
        return 1
    # behind a window or tall cover, crouch to see out
    if T.FLOOR[m.t[a.x, a.y]]:
        return 1
    return 2


def fix_stance(game, a, s) -> int:
    if a.stance != s:
        return A.set_stance(game, a, s) or 0
    return 0


# ====================================================================== squad logic

def squad_update(game, sq: Squad):
    t = game.turn
    sq.members = [m for m in sq.members if m.alive and m.state == "ok"]
    sq.vehicles = [v for v in sq.vehicles if v.active]
    if not sq.members and not sq.vehicles:
        sq.gone = True
        return False
    # leader succession
    if sq.leader is None or not sq.leader.active or sq.leader not in sq.members or sq.leader.downed:
        cands = [m for m in sq.members if m.active and not m.downed]
        if cands:
            new = max(cands, key=lambda m: (m.is_player and sq.player_led, m.rank, m.skill))
            old_leader = sq.leader
            if old_leader is not None and new is not old_leader and old_leader.is_player is False:
                if game.rng.random() < 0.7 and not new.is_player:
                    new.say(phrase(game.rng, new.nation, "follow_me"), t)
            sq.leader = new
            cmd = getattr(game, "command", None)
            if cmd is not None and new is not old_leader:
                cmd.on_leader_change(game, sq, old_leader, new)
    if sq.initial == 0:
        sq.initial = max(1, len(sq.members) + 4 * len(sq.vehicles))
    brain = game.brains[sq.side]
    # contact
    seen = False
    for m in sq.members:
        if m.visible and m.vis_turn >= t - 3:
            seen = True
            break
    for v in sq.vehicles:
        if v.visible and v.vis_turn >= t - 3:
            seen = True
    if seen:
        sq.last_contact = t
    # morale
    doc = NATIONS[sq.nation]["doctrine"]
    alive = sq.strength()
    cas = 1 - alive / max(1, sq.initial)
    act = [m for m in sq.members if m.active]
    avg_sup = sum(m.suppression for m in act) / max(1, len(act))
    avg_mor = sum(m.morale for m in act) / max(1, len(act)) if act else 50.0
    lead_bonus = 8 if sq.leader is not None and sq.leader.active else -10
    sq.morale = avg_mor - cas * 35 - avg_sup * 0.15 + lead_bonus
    # enemy tanks nearby with no AT weapon
    if brain.contacts:
        tanks = [c for c in brain.live_contacts(15, False) if c.kind == "tank"]
        anc = sq.anchor()
        if tanks and anc:
            near = [c for c in tanks if abs(c.x - anc[0]) + abs(c.y - anc[1]) < 25]
            if near and not any(m.weapon and m.weapon.t.cat in ("at_launcher", "at_disposable", "at_rifle")
                                for m in act):
                sq.morale -= 15
    # state machine
    old = sq.state
    o = sq.order
    kind = o.kind
    if kind == "ambush" and _ambush_sprung(game, sq):
        o.kind = kind = "defend" if o.obj is not None else "hold"
        o.roe = "free"
        sq.arrived = True
        lead = sq.leader if sq.leader is not None and sq.leader.active else None
        if lead is not None:
            lead.say(phrase(game.rng, lead.nation, "ambush_fire"), t, 3)
            if lead.has_tool("whistle"):
                game.emit_sound(lead.x, lead.y, 60, "whistle", "a whistle blast", sq.side, lead)
    collapse = sq.morale < 5 and cas > 0.45 and not sq.player_led
    if collapse and kind in ("suppress", "ambush", "flank", "dig", "mount", "regroup", "resupply"):
        if sq.state not in ("banzai", "rout"):          # roll once, don't flip every update
            sq.state = "banzai" if doc.get("banzai") and game.rng.random() < 0.7 else "rout"
    elif kind == "suppress":
        sq.state = "suppress"
    elif kind == "ambush":
        sq.state = "hold" if sq.arrived else "advance"
    elif kind in ("dig", "mount", "dismount"):
        sq.state = "hold"
        sq.arrived = True
    elif kind == "regroup":
        sq.state = "follow"
    elif kind == "resupply":
        sq.state = "resupply"
    elif kind == "flank" and o.target is not None:
        anc0 = sq.anchor()
        far = anc0 is None or max(abs(anc0[0] - o.target[0]), abs(anc0[1] - o.target[1])) > 7
        if far and sq.state != "assault":
            sq.flank_target = o.target
            sq.state = "flank"
        else:
            sq.state = "assault"
    elif sq.player_led and o.kind not in ("move", "attack", "assault", "retreat"):
        if o.kind == "hold":
            sq.state = "hold"
        elif o.kind == "defend":
            sq.state = "hold" if sq.arrived else "advance"
        else:
            sq.state = "engaged" if t - sq.last_contact < 6 else "follow"
    elif o.kind == "retreat":
        sq.state = "retreat"
    elif sq.player_led and o.kind in ("move", "attack", "assault") and t - sq.last_contact >= 8:
        sq.state = "hold" if sq.arrived else "advance"
    elif sq.morale < 5 and cas > 0.45:
        if sq.state not in ("banzai", "rout"):
            sq.state = "banzai" if doc.get("banzai") and game.rng.random() < 0.7 else "rout"
    elif sq.morale < 18 and cas > 0.35 and o.kind not in ("defend",) and sq.state != "hold":
        sq.state = "retreat"
    elif t - sq.last_contact < 8:
        if sq.state not in ("assault", "flank", "banzai") or t - sq.state_turn > 40:
            sq.state = decide_engagement(game, sq)
    elif t - sq.last_contact < 30 and o.kind in ("attack", "move"):
        sq.state = "advance"
    else:
        if o.kind in ("attack", "move", "assault"):
            if sq.arrived:
                sq.state = "hold"
            else:
                sq.state = "advance"
        elif o.kind in ("defend", "hold"):
            sq.state = "hold" if sq.arrived else "advance"
        else:
            sq.state = "hold"
    if sq.state != old:
        sq.state_turn = t
        on_state_change(game, sq, old)
    # arrival
    anc = sq.anchor()
    tgt = order_target(game, sq)
    if anc and tgt and o.kind not in ("suppress", "flank", "regroup"):
        d = max(abs(anc[0] - tgt[0]), abs(anc[1] - tgt[1]))
        near_r = max(3, o.radius // 2) if o.kind == "attack" else max(4, o.radius)
        if o.kind == "attack" and sq.kind in ("mg", "mortar", "hq", "sniper", "at"):
            near_r = {"mortar": 28, "hq": 18, "sniper": 24, "mg": 14, "at": 10}[sq.kind]
        if d <= near_r:
            if not sq.arrived:
                sq.arrived = True
                sq.positions = {}
        elif d > o.radius + 12:
            sq.arrived = False
    sq.phase = (t // 10) % 2
    return True


def leashed(sq) -> bool:
    """A squad the player leads in person keeps to the player - unless sent off with an order."""
    return sq.player_led and sq.order.kind in ("follow", "hold", "defend", "dig", "ambush", "regroup")


def _ambush_sprung(game, sq) -> bool:
    """An ambush fires when the enemy walks into it - or when it's discovered."""
    t = game.turn
    for m in sq.members:
        if not m.active:
            continue
        if m.hit_turn >= t - 3 or m.suppression > 35:
            return True
        for e in m.visible:
            if getattr(e, "alive", True) and max(abs(e.x - m.x), abs(e.y - m.y)) <= 7:
                return True
    return False


def roe_allows(game, a, target) -> bool:
    """Rules of engagement: may this soldier open fire on this target?"""
    sq = a.squad
    if sq is None or a.is_player:
        return True
    roe = getattr(sq.order, "roe", "free")
    if roe == "free":
        return True
    t = game.turn
    d = max(abs(target.x - a.x), abs(target.y - a.y))
    under_fire = a.hit_turn >= t - 20 or a.suppression > 20 or \
        any(m.hit_turn >= t - 10 for m in sq.members if m.alive)
    if roe == "return":
        return under_fire or d <= 8
    # hold fire: only in self-defence
    if d <= 3 or a.hit_turn >= t - 5:
        if sq.order.kind != "ambush":
            sq.order.roe = "free"
            if sq.leader is not None and sq.leader.active:
                sq.leader.say(phrase(game.rng, sq.leader.nation, "seen_fire"), t)
        return True
    return False


def decide_engagement(game, sq) -> str:
    doc = NATIONS[sq.nation]["doctrine"]
    brain = game.brains[sq.side]
    anc = sq.anchor()
    if anc is None:
        return "engaged"
    contacts = brain.nearest_contacts(anc[0], anc[1], 8, max_age=10)
    if not contacts:
        return "engaged"
    near = [c for c in contacts if abs(c.x - anc[0]) + abs(c.y - anc[1]) < 14]
    ours = sq.strength()
    theirs = len([c for c in contacts if abs(c.x - anc[0]) + abs(c.y - anc[1]) < 25])
    enemy_sup = 0.0
    for c in contacts:
        r = c.ref
        if r is not None and getattr(r, "vt", None) is None:
            enemy_sup += r.suppression
    enemy_sup /= max(1, len(contacts))
    o = sq.order.kind
    rng = game.rng
    if sq.kind in ("mg", "mortar", "sniper", "hq", "at"):
        return "engaged"
    if doc.get("banzai") and sq.morale < 30 and rng.random() < 0.5:
        return "banzai"
    if o in ("attack", "assault", "move") or (o == "defend" and near and ours > theirs * 2):
        if near and (ours >= theirs * 1.5 or enemy_sup > 45) and rng.random() < 0.3 + doc["aggression"] * 0.5:
            return "assault"
        big = [c for c in contacts if c.kind in ("mg", "hmg", "bunker", "atgun")]
        if big and ours >= 4 and rng.random() < 0.35 + (1 - doc["aggression"]) * 0.3:
            sq.flank_target = (big[0].x, big[0].y)
            return "flank"
        return "bound"
    return "engaged"


def on_state_change(game, sq, old):
    leader = sq.leader
    if leader is None or not leader.active:
        return
    st = sq.state
    key = {"assault": "attack", "bound": "attack", "banzai": "attack", "retreat": "retreat",
           "rout": "retreat", "flank": None, "engaged": "contact"}.get(st)
    if key:
        leader.say(game.shout(leader, key), game.turn)
        if st in ("assault", "banzai") and leader.has_tool("whistle"):
            game.emit_sound(leader.x, leader.y, 60, "whistle", "a whistle blast", sq.side, leader)
    if st == "flank" and game.rng.random() < 0.8:
        leader.say(phrase(game.rng, leader.nation, "flank"), game.turn)
    if st == "hold" and sq.order.kind in ("attack", "move", "defend") and sq.positions_order is not sq.order:
        sq.positions = {}


def order_target(game, sq):
    o = sq.order
    if o.kind in ("follow", "regroup") and sq.leader is not None:
        return sq.leader.pos
    if o.obj is not None and o.obj < len(game.map.objectives):
        ob = game.map.objectives[o.obj]
        return (ob.x, ob.y)
    return o.target


def assign_positions(game, sq):
    """Pick defensive positions around the order target for each member."""
    tgt = order_target(game, sq)
    anc = sq.anchor()
    if tgt is None:
        tgt = anc
    if tgt is None:
        return
    m = game.map
    brain = game.brains[sq.side]
    ec = brain.enemy_center
    if ec is None:
        e_edge = game.home_edge(other_side(sq.side))
        ec = {"N": (tgt[0], 0), "S": (tgt[0], m.h - 1), "W": (0, tgt[1]), "E": (m.w - 1, tgt[1])}.get(
            e_edge, (m.w // 2, m.h // 2))
    r = max(6, sq.order.radius + 2)
    x0, x1 = max(1, tgt[0] - r), min(m.w - 1, tgt[0] + r + 1)
    y0, y1 = max(1, tgt[1] - r), min(m.h - 1, tgt[1] + r + 1)
    xs = np.arange(x0, x1)[:, None]
    ys = np.arange(y0, y1)[None, :]
    dx = ec[0] - xs
    dy = ec[1] - ys
    oct_idx = (np.round(np.arctan2(-dy, dx) / (math.pi / 4)).astype(np.int32)) % 8
    cov = np.take_along_axis(m.cover_dir[:, x0:x1, y0:y1], oct_idx[None], axis=0)[0]
    score = np.maximum(cov, m.pos_cover[x0:x1, y0:y1]) + m.conceal[x0:x1, y0:y1] * 0.25
    win = T.WINDOW[m.t[x0:x1, y0:y1]]
    # tiles just inside windows / embrasures are prime firing positions
    near_win = np.zeros_like(win)
    near_win[1:, :] |= win[:-1, :]
    near_win[:-1, :] |= win[1:, :]
    near_win[:, 1:] |= win[:, :-1]
    near_win[:, :-1] |= win[:, 1:]
    score = score + near_win * 45
    d2 = (xs - tgt[0]) ** 2 + (ys - tgt[1]) ** 2
    score = score - np.sqrt(d2) * 1.5
    walk = m.walk[x0:x1, y0:y1] & (T.DOOR[m.t[x0:x1, y0:y1]] == 0)
    score = np.where(walk, score, -1e9)
    flat = np.argsort(score, axis=None)[::-1]
    claimed = set()
    for other in game.squads:
        if other is not sq and other.side == sq.side and other.positions:
            claimed.update(other.positions.values())
    taken = list(claimed)
    n_claimed = len(taken)
    members = [mm for mm in sq.members if mm.active and not mm.is_player]
    sq.positions = {}
    sq.positions_order = sq.order
    W = x1 - x0
    Hh = y1 - y0
    # a spot within two steps (Manhattan) of one already claimed is no good: mark those on a grid of the
    # window once, instead of checking every candidate against every claimed spot on the field
    blocked = [[False] * Hh for _ in range(W)]

    def block(tx, ty):
        for ddx in (-2, -1, 0, 1, 2):
            bx = tx - x0 + ddx
            if bx < 0 or bx >= W:
                continue
            k = 2 - abs(ddx)
            col = blocked[bx]
            for ddy in range(-k, k + 1):
                by = ty - y0 + ddy
                if 0 <= by < Hh:
                    col[by] = True
    for tx, ty in taken:
        if x0 - 3 < tx < x1 + 3 and y0 - 3 < ty < y1 + 3:
            block(tx, ty)
    need = len(members)
    got = 0
    for idx in flat:
        if got >= need:
            break
        px, py = divmod(int(idx), Hh)
        if score[px, py] < -1e8:
            break
        if blocked[px][py]:
            continue
        X, Y = px + x0, py + y0
        taken.append((X, Y))
        got += 1
        block(X, Y)
    # MG and snipers get the best spots
    members.sort(key=lambda mm: 0 if (mm.weapon and mm.weapon.t.cat in ("lmg", "hmg")) else 1)
    for mm, p in zip(members, taken[n_claimed:]):
        sq.positions[mm.id] = p
    del W


# ====================================================================== soldier AI

def soldier_act(game, a) -> int:
    if not a.alive:
        return 100
    b = a.body
    if not b.conscious:
        return 100
    if a.vehicle is not None:
        return 100
    if a.state == "surrendered":
        return surrendered_act(game, a)
    if a.state != "ok":
        return 100
    if a.ai.get("grapple") is not None:
        from .melee import attack, grappling
        g = grappling(game, a)
        if g is not None:
            return attack(game, a, g)                 # locked together: nothing else exists
    if a.z or (a.suppression > 70 and a.ai.get("shelled", -999) >= game.turn - 20):
        from .floors import ai_act
        c = ai_act(game, a, None, a.squad)            # the stairs, the cellar
        if c:
            return c
    m = game.map
    sq = a.squad
    brain = game.brains[a.side]
    # ---- immediate survival
    if m.water[a.x, a.y] >= 2:
        return swim_act(game, a)
    if m.fire[a.x, a.y] > 0 or b.burning:
        st = best_step(game, a, [(brain.safety, 0.2)], avoid_fire=True)
        if b.burning and game.rng.random() < 0.5:
            b.burning = max(0, b.burning - 2)
            a.stance = 2
            return 100
        c = do_step(game, a, st)
        if c:
            return c
    danger = game.explosive_danger(a.x, a.y, 4)
    if danger is not None:
        return evade_explosive(game, a, danger)
    if a.entangled:
        return A.move(game, a, 0, 0) or 100
    # ---- wounded
    if a.downed:
        return downed_act(game, a)
    if a.ai.get("litter"):
        from .medevac import bearer_act
        update_actor_vision(game, a)
        return bearer_act(game, a) or 100         # a stretcher-bearer on a call: to the man, and back
    vis = update_actor_vision(game, a)
    if vis:
        for e in vis:
            brain.report(e, game.turn)
        if sq is not None:
            sq.last_contact = game.turn
        if a.ai.get("last_contact_shout", -99) < game.turn - 40 and game.rng.random() < 0.3:
            a.ai["last_contact_shout"] = game.turn
            e = vis[0]
            if getattr(e, "vt", None) is not None:
                a.say(game.shout(a, "tank"), game.turn)
            elif contact_kind(e) in ("mg", "hmg"):
                a.say(game.shout(a, "mg"), game.turn)
            elif contact_kind(e) == "sniper":
                a.say(game.shout(a, "sniper"), game.turn)
            else:
                a.say(game.shout(a, "contact"), game.turn)
    near_enemy = min((dist(a, e) for e in vis), default=999)
    bleed = b.bleed_rate()
    if bleed > 1.5 and (near_enemy > 12 or bleed > 5):
        c = A.treat(game, a, a)                   # (a medic bleeding out patches himself first too)
        if c:
            return c
    # ---- the weather: water in the heat; a roof when freezing (if nobody's shooting)
    tmp = getattr(b, "temp", 37.0)
    if tmp > 38.8 and a.ai.get("drank", -99) < game.turn - 300:
        cw = a.find(lambda i: i.t.tool == "canteen" and i.uses > 0)
        if cw is not None:
            a.ai["drank"] = game.turn
            return A.drink(game, a, cw)
    if (tmp < 35.4 or tmp > 39.3) and near_enemy > 25 and \
            (sq is None or getattr(sq, "state", "idle") in ("idle", "hold", "follow", "regroup", "dig")):
        c = seek_shelter(game, a)
        if c:
            return c
    # ---- personal morale
    doc = NATIONS[a.nation]["doctrine"]
    if a.suppression > 85 and a.morale < 35 and game.rng.random() < 0.3 and not doc.get("banzai"):
        # cower
        fix_stance(game, a, 2)
        return 100
    sstate = sq.state if sq is not None else "hold"
    if sstate == "rout" or (a.morale < 10 and a.suppression > 50):
        return rout_act(game, a, vis, near_enemy)
    # ---- weapon upkeep
    w = a.weapon
    if w is not None and w.t.kind == "gun":
        if w.jammed:
            return A.unjam(game, a)
        if w.loaded <= 0 and w.t.cat not in ("mortar",):
            if a.ammo_for(w) is not None:
                if near_enemy < 20 and in_cover_from(game, a, *(vis[0].pos if vis else (a.x, a.y))) < 40:
                    st = best_step(game, a, [(brain.safety, 1.0)])
                    c = do_step(game, a, st)
                    if c:
                        return c
                if game.rng.random() < 0.2:
                    a.say(game.shout(a, "reload"), game.turn)
                return A.reload(game, a) or 100
            else:
                from .ammo import needs_refill, fill_magazine, sources
                if needs_refill(a, w) and near_enemy > 12:
                    mags = [m for m in sources(a, w) if m.t.kind == "mag" and m.loaded < m.t.mag]
                    if mags:
                        n = fill_magazine(a, mags[0], 10)
                        if n:
                            return 60 * n
                alt = switch_weapon(game, a)
                if alt:
                    return alt
    elif w is None or w.t.kind not in ("gun", "melee"):
        alt = switch_weapon(game, a)
        if alt:
            return alt
    # ---- walking a prisoner of ours back to the rear
    if a.ai.get("escort_prisoner") is not None and a.side == game.player_side:
        c = prisoner_escort_act(game, a)
        if c:
            return c
    # ---- escorting a prisoner (you) to the rear
    if a.ai.get("escort") is not None:
        c = escort_act(game, a)
        if c:
            return c
    # ---- carrying a message
    if a.ai.get("runner"):
        c = runner_act(game, a, vis)
        if c:
            return c
    # ---- roles
    role_cost = role_act(game, a, vis, sq, sstate)
    if role_cost:
        return role_cost
    # ---- squad behaviour
    if sstate == "banzai":
        return banzai_act(game, a, vis)
    if sstate == "retreat":
        return retreat_act(game, a, vis)
    if sstate == "suppress" and not (vis and near_enemy < 10):
        c = suppress_order_act(game, a, sq)
        if c:
            return c
    if vis:
        return engage_act(game, a, vis, sq, sstate)
    if sq is not None and game.turn - sq.last_contact < 12:
        c = suppress_known(game, a, sq)
        if c:
            return c
    if sq is not None and not leashed(sq) and sstate in ("flank", "assault", "bound"):
        team = a.id % 2
        if sstate != "bound" or team == sq.phase:
            c = maneuver_step(game, a, sq, sstate, None)
            if c:
                return c
    return move_with_squad(game, a, sq, sstate)


def switch_weapon(game, a) -> int | None:
    # prefer any loaded gun or gun with ammo, then a melee weapon
    guns = [i for i in a.inv if i.t.kind == "gun" and i is not a.weapon and
            (i.loaded > 0 or a.ammo_for(i) is not None) and i.t.cat not in ("mortar",)]
    if guns:
        g = max(guns, key=lambda i: (i.t.cat not in ("at_disposable",), i.t.dmg * max(1, i.t.burst)))
        return A.wield(game, a, g)
    if a.weapon is None or a.weapon.t.kind != "melee":
        mel = [i for i in a.inv if i.t.kind == "melee"]
        if mel and (a.weapon is None or not (a.weapon.t.kind == "gun" and a.weapon.t.bayonet)):
            return A.wield(game, a, max(mel, key=lambda i: i.t.dmg))
    return None


def engage_act(game, a, vis, sq, sstate) -> int:
    brain = game.brains[a.side]
    m = game.map
    rng = game.rng
    w = a.weapon
    target = choose_target(game, a, vis)
    near = [e for e in vis if getattr(e, "vt", None) is None and e.active]
    closest = min(near, key=lambda e: dist(a, e)) if near else None
    cd = dist(a, closest) if closest else 999
    # melee range
    if closest is not None and cd < 1.5:
        if w is None or w.t.kind == "melee" or (w.t.kind == "gun" and (w.loaded == 0 or w.t.cat in ("at_launcher", "mortar", "at_rifle")) ) or rng.random() < 0.35:
            return A.melee(game, a, closest)
    # grenades at enemies in cover / groups
    c = maybe_grenade(game, a, near) if (closest is None or roe_allows(game, a, closest)) else None
    if c:
        return c
    if target is None:
        # nothing we can hurt: e.g. tanks with no AT weapon -> take cover
        st = best_step(game, a, [(brain.safety, 1.0)], exposure_w=2.0)
        c = do_step(game, a, st)
        if c:
            return c
        fix_stance(game, a, 2)
        return 100
    td = dist(a, target)
    cover = in_cover_from(game, a, target.x, target.y)
    # bounding / assault / flank movement takes priority for the maneuver element
    moving = False
    if sq is not None and not leashed(sq):
        team = a.id % 2
        if sstate == "bound" and team == sq.phase and a is not sq.leader:
            moving = True
        elif sstate == "assault":
            moving = rng.random() < 0.75
        elif sstate == "flank" and team == 0:
            moving = True
    if sq is not None and sq.player_led and not a.is_player and sq.order.kind == "follow":
        # stay near the player-leader, whatever the enemy is doing
        anc = sq.anchor()
        if anc and max(abs(a.x - anc[0]), abs(a.y - anc[1])) > 7:
            c = path_step(game, a, anc[0], anc[1])
            if c:
                fix_stance(game, a, 1)
                return c
    if moving:
        c = maneuver_step(game, a, sq, sstate, target)
        if c:
            return c
    # exposed? find cover first unless the enemy is very close or we're an assault
    if cover < 35 and td > 6 and sstate not in ("assault",) and a.suppression + (20 if td < 25 else 0) > 15:
        if brain.safety is not None and int(brain.safety[a.x, a.y]) <= 20:
            st = best_step(game, a, [(brain.safety, 1.0)], exposure_w=1.0)
            c = do_step(game, a, st)
            if c:
                fix_stance(game, a, 1)
                return c
    s = want_stance(game, a, True, False, td < 6)
    c = fix_stance(game, a, s)
    if c:
        return c
    # fire - if the rules of engagement allow it
    if not roe_allows(game, a, target):
        fix_stance(game, a, 2 if a.stance < 2 else a.stance)
        return 100
    if w is not None and w.t.kind == "gun":
        p = estimate_hit(game, a, w, target) if getattr(target, "vt", None) is None else 0.5
        suppressor = w.t.cat in ("lmg", "hmg")
        thresh = 0.02 if suppressor else (0.05 if td < w.t.rng else 0.1)
        if a.suppression > 60:
            thresh *= 2
        if p >= thresh or td < 8:
            # aim at long range
            # take aim when there's time for it: at range, not under the gun, and it'd help
            lvl = aim_level(a, target.x, target.y)
            want = 0
            if w.t.cat in ("rifle", "sniper", "at_rifle", "at_launcher", "at_disposable", "carbine") and p < 0.6:
                want = 1 if td > 12 else 0
                if td > 25:
                    want = 2
                if w.t.cat == "sniper":
                    want = max_aim(a, w.t)
                if a.suppression > 40:
                    want = min(want, 1)
                if "veteran" in a.traits or a.skill >= 7:
                    want = min(max_aim(a, w.t), want + (1 if td > 18 else 0))
            elif w.t.cat == "lmg" and td > 20 and a.stance == 2 and p < 0.3:
                want = 1
            if lvl < want:
                a.aim_target, a.aim_turns = target.pos, lvl + 1
                return aim_time(a, w.t)
            a.aim_target = target.pos
            if w.t.modes and "auto" in w.t.modes and "single" in w.t.modes:
                w.mode = w.t.modes.index("auto" if td < 15 or suppressor else "single")
            return safe_fire(game, a, target.x, target.y, target)
        # too far to hit: close the distance if attacking, else wait
        if sq is not None and sq.order.kind in ("attack", "move") and sstate != "hold":
            c = maneuver_step(game, a, sq, "bound", target)
            if c:
                return c
        return 100
    if w is not None and w.t.kind == "melee":
        if sstate in ("assault", "banzai") or cd < 6:
            c = path_step(game, a, closest.x, closest.y) if closest else None
            if c:
                return c
    return 100


def maneuver_step(game, a, sq, sstate, target) -> int | None:
    brain = game.brains[a.side]
    anc = sq.anchor() if sq else None
    if sstate == "assault" and brain.threat_dist is not None:
        st = best_step(game, a, [(brain.threat_dist, 1.0)], exposure_w=0.5, cohesion=anc, spread=6)
        fix_stance(game, a, 1 if a.stance == 2 else a.stance)
        return do_step(game, a, st)
    if sstate == "flank" and sq is not None and sq.flank_target is not None:
        fx, fy = sq.flank_target
        mp = brain.flank_map(("sq", sq.id), fx, fy, anc[0] if anc else a.x, anc[1] if anc else a.y)
        if mp is not None:
            if int(mp[a.x, a.y]) <= 1:
                return None
            st = best_step(game, a, [(mp, 1.0)], exposure_w=4.0, cohesion=anc, spread=5)
            return do_step(game, a, st)
    # bound toward the objective (or the enemy) through covered ground
    tgt = order_target(game, sq) if sq else None
    mp = None
    if sq is not None and sq.order.obj is not None and sq.order.obj < len(game.map.objectives):
        mp = brain.objective_map(sq.order.obj, covered=True)
    elif tgt is not None:
        mp = brain.point_map(tgt[0], tgt[1], covered=True, radius=2)
    elif brain.threat_dist is not None:
        mp = brain.threat_dist
    if mp is None:
        return None
    # don't advance into point-blank range of the enemy unless assaulting
    if target is not None and dist(a, target) < 8:
        return None
    st = best_step(game, a, [(mp, 1.0)], exposure_w=6.0, cohesion=anc, spread=6)
    c = do_step(game, a, st)
    if c:
        fix_stance(game, a, 1 if a.suppression < 55 else 2)
    return c


def maybe_grenade(game, a, near) -> int | None:
    if not near:
        return None
    gr = [g for g in a.grenades() if g.t.gtype in ("frag", "stick", "gammon")]
    if not gr:
        return None
    g = gr[0]
    rng_max = A.throw_range(a, g)
    m = game.map
    for e in sorted(near, key=lambda e: dist(a, e)):
        d = dist(a, e)
        if d < 4 or d > rng_max:
            continue
        in_cover = m.pos_cover[e.x, e.y] > 40 or m.cover_toward(e.x, e.y, a.x, a.y) > 50 or T.FLOOR[m.t[e.x, e.y]]
        cluster = sum(1 for o in near if abs(o.x - e.x) <= 2 and abs(o.y - e.y) <= 2) >= 2
        if not (in_cover or cluster):
            continue
        # friendlies too close to the target?
        friendly = False
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                o = game.soldier_at.get((e.x + dx, e.y + dy))
                if o is not None and o.side == a.side:
                    friendly = True
        if friendly:
            continue
        if game.rng.random() < 0.35:
            return A.throw(game, a, g, e.x, e.y, cook=1 if game.rng.random() < 0.3 else 0)
    return None


def suppress_known(game, a, sq) -> int | None:
    """Fire at the last known position of an unseen enemy (MG teams especially)."""
    w = a.weapon
    if w is None or w.t.kind != "gun" or w.loaded <= 0:
        return None
    if getattr(sq.order, "roe", "free") != "free":
        return None
    if w.t.cat not in ("lmg", "hmg") and not (sq.state in ("bound", "engaged") and game.rng.random() < 0.25):
        return None
    brain = game.brains[a.side]
    cs = brain.nearest_contacts(a.x, a.y, 4, max_age=10)
    for c in cs:
        d = math.hypot(c.x - a.x, c.y - a.y)
        if d > w.t.rng * 1.3 or d < 3:
            continue
        # need a line of fire to near the contact
        from .senses import los_clear
        if los_clear(game, a.x, a.y, c.x, c.y):
            near_friend = any(o.side == a.side and o.alive and abs(o.x - c.x) <= 3 and abs(o.y - c.y) <= 3
                              for o in game.actors if o.vehicle is None)
            if near_friend:
                continue
            fix_stance(game, a, want_stance(game, a, True, False, False))
            return safe_fire(game, a, c.x, c.y, None, area=True)
    return None


def move_with_squad(game, a, sq, sstate) -> int:
    brain = game.brains[a.side]
    m = game.map
    if sq is None:
        fix_stance(game, a, want_stance(game, a, False, False, False))
        return 100
    anc = sq.anchor()
    kind = sq.order.kind
    if kind == "resupply":
        c = resupply_act(game, a, sq)
        if c:
            return c
    if kind == "mount":
        c = mount_act(game, a, sq)
        if c:
            return c
    if kind == "regroup" and anc is not None and a is not sq.leader:
        if max(abs(a.x - anc[0]), abs(a.y - anc[1])) > 2:
            c = path_step(game, a, anc[0], anc[1])
            if c:
                fix_stance(game, a, 1)
                return c
        fix_stance(game, a, 1 if a.stance == 0 else a.stance)
        return 100
    if sstate == "suppress":
        fix_stance(game, a, 1 if a.stance == 0 else a.stance)
        return 100
    # hold: go to the assigned position, dig in
    if sstate == "hold" or (sq.arrived and kind in ("defend", "hold", "attack", "move", "ambush", "dig")):
        if not sq.positions and game.turn - sq.__dict__.get("_pos_try", -99) > 15:
            # (if there was nowhere to go, don't look again for every man, every second)
            sq._pos_try = game.turn
            assign_positions(game, sq)
        pos = sq.positions.get(a.id)
        if pos is not None and (a.x, a.y) != pos:
            c = path_step(game, a, pos[0], pos[1])
            if c:
                fix_stance(game, a, 0 if brain.exposure_at(a.x, a.y) < 0.5 else 1)
                return c
        s = want_stance(game, a, False, False, False)
        if kind == "ambush":
            s = 2                      # lie still and let them come
        c = fix_stance(game, a, 1 if s == 0 and game.turn - sq.last_contact < 60 else s)
        if c:
            return c
        quiet = 30 if kind != "dig" else 5
        if m.pos_cover[a.x, a.y] < (40 if kind != "dig" else 55) and a.has_tool("shovel") \
                and T.DIG[m.t[a.x, a.y]] and game.turn - sq.last_contact > quiet and kind != "ambush":
            return A.dig(game, a) or 100
        return 100
    if sstate == "follow" or sq.order.kind == "follow":
        if anc and max(abs(a.x - anc[0]), abs(a.y - anc[1])) > 3:
            c = path_step(game, a, anc[0], anc[1])
            if c:
                fix_stance(game, a, sq.leader.stance if sq.leader else 0)
                return c
        fix_stance(game, a, sq.leader.stance if sq.leader is not None else 0)
        return 100
    # advance toward the order target
    mp = None
    if sq.order.obj is not None and sq.order.obj < len(m.objectives):
        mp = brain.objective_map(sq.order.obj, covered=True)
    else:
        tgt = order_target(game, sq)
        if tgt is not None:
            mp = brain.point_map(tgt[0], tgt[1], covered=True, radius=2)
    if mp is None:
        return 100
    if a is sq.leader:
        # wait for stragglers
        mem = sq.active_members()
        far = [mm for mm in mem if max(abs(mm.x - a.x), abs(mm.y - a.y)) > 8]
        if len(far) > len(mem) // 2 and game.rng.random() < 0.6:
            fix_stance(game, a, 1)
            return 100
        # attacks go in together: don't run far ahead of the other squads on this objective
        if sq.order.kind == "attack" and sq.order.obj is not None and game.turn - sq.order.issued < 600:
            mine = int(mp[a.x, a.y])
            others = []
            for o2 in game.squads:
                if o2 is sq or o2.side != sq.side or o2.order.obj != sq.order.obj or o2.order.kind != "attack":
                    continue
                an2 = o2.anchor()
                if an2 is not None and o2.state in ("advance", "bound", "engaged"):
                    others.append(int(mp[an2[0], an2[1]]))
            if others and mine < min(others) - 14 * UNIT and game.rng.random() < 0.8:
                fix_stance(game, a, 1)
                return 100
        st = best_step(game, a, [(mp, 1.0)], exposure_w=2.0 if sstate == "advance" else 0.8)
    else:
        st = best_step(game, a, [(mp, 1.0)], exposure_w=2.0, cohesion=anc, spread=4)
    c = do_step(game, a, st)
    if c:
        fix_stance(game, a, 1 if (game.turn - sq.last_contact < 30 or brain.exposure_at(a.x, a.y) > 0.8) else 0)
        return c
    return 100


def suppress_order_act(game, a, sq) -> int | None:
    """Ordered to suppress a position: put rounds into it whether or not anyone is seen."""
    from .senses import los_clear
    tgt = sq.order.target
    w = a.weapon
    if tgt is None or w is None or w.t.kind != "gun" or w.t.cat in ("mortar", "at_launcher", "at_disposable",
                                                                       "flamer"):
        return None
    if w.loaded <= 0:
        return None
    tx, ty = tgt
    d = math.hypot(tx - a.x, ty - a.y)
    if d > w.t.rng * 1.6:
        return None
    rng = game.rng
    if los_clear(game, a.x, a.y, tx, ty):
        heavy = w.t.cat in ("lmg", "hmg")
        # riflemen fire steadily, the guns keep up a beaten zone
        if not heavy and rng.random() < 0.45:
            fix_stance(game, a, 2 if a.stance < 2 and a.suppression > 20 else a.stance)
            return 100
        fix_stance(game, a, want_stance(game, a, True, False, False))
        jx = tx + rng.randint(-2, 2)
        jy = ty + rng.randint(-2, 2)
        return safe_fire(game, a, jx, jy, None, area=True)
    # shift a few yards to get a line of fire
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = a.x + dx, a.y + dy
            if (dx or dy) and game.map.in_bounds(x, y) and game.map.walk[x, y] and \
                    (x, y) not in game.soldier_at and los_clear(game, x, y, tx, ty):
                best = (dx, dy)
                break
        if best:
            break
    if best is not None:
        fix_stance(game, a, 1)
        return do_step(game, a, best)
    return None


def resupply_act(game, a, sq) -> int | None:
    """Walk back to the dump, fill your pouches, wait for the others."""
    o = sq.order
    if o.target is None:
        return None
    tx, ty = o.target
    done = a.ai.get("resupplied") == o.issued
    if not done:
        if max(abs(a.x - tx), abs(a.y - ty)) <= 1:
            a.ai["resupplied"] = o.issued
            return A.resupply(game, a) or 100
        # stand next to the stack (it can't be walked on)
        c = path_step(game, a, tx, ty, margin=20)
        if c:
            fix_stance(game, a, 0)
            return c
        a.ai["resupplied"] = o.issued       # can't get there: give up
        return 100
    if all(m.ai.get("resupplied") == o.issued for m in sq.members if m.active and not m.downed) or \
            game.turn - o.issued > 300:
        o.kind = "hold"
        o.target = sq.anchor()
        sq.arrived = True
        sq.positions = {}
        if sq.leader is not None and sq.leader.active and game.rng.random() < 0.7:
            sq.leader.say(phrase(game.rng, sq.leader.nation, "resupplied"), game.turn, tone="talk")
    return None


def mount_act(game, a, sq) -> int | None:
    """Climb aboard the unit's transport (or any friendly one close by with room)."""
    if a.vehicle is not None:
        return 100
    cands = [v for v in sq.vehicles if v.active and len(v.passengers) < v.vt.seats]
    if not cands:
        cands = [v for v in game.vehicles if v.side == a.side and v.active and not v.dead and v.vt.seats > 0
                 and len(v.passengers) < v.vt.seats and v.near(a.x, a.y) < 20]
    if not cands:
        return None
    v = min(cands, key=lambda v: v.near(a.x, a.y))
    if v.near(a.x, a.y) <= 1:
        c = A.enter_vehicle(game, a, v)
        if c and v not in sq.vehicles:
            sq.vehicles.append(v)
            if v.squad is None or not v.squad.members:
                v.squad = sq
        return c or 100
    return path_step(game, a, v.x, v.y)


def escort_act(game, a) -> int | None:
    """Walk the prisoner back: a few paces ahead, waiting when he lags."""
    p = game.player
    if p is None or p.id != a.ai.get("escort") or getattr(game, "pow", None) is None or \
            game.pow.get("stage") != "march":
        a.ai.pop("escort", None)
        return None
    brain = game.brains[a.side]
    d = max(abs(p.x - a.x), abs(p.y - a.y))
    if d > 4:
        c = path_step(game, a, p.x, p.y)
        return c or 100
    if brain.home is None:
        return 100
    st = best_step(game, a, [(brain.home, 1.0)], crowd=False)
    fix_stance(game, a, 0)
    return do_step(game, a, st) or 100


def runner_act(game, a, vis) -> int | None:
    """A runner carries an order across the battlefield on foot."""
    job = a.ai.get("runner")
    cmd = getattr(game, "command", None)
    if not job or cmd is None:
        a.ai["runner"] = None
        return None
    dest = cmd.runner_destination(game, job)
    if dest is None:
        a.ai["runner"] = None
        return None
    if max(abs(a.x - dest[0]), abs(a.y - dest[1])) <= 2:
        cmd.runner_arrived(game, a, job)
        a.ai["runner"] = None
        return 100
    if vis and min(dist(a, e) for e in vis) < 6 and game.rng.random() < 0.3:
        return None        # fight for your life first
    c = path_step(game, a, dest[0], dest[1], margin=30)
    if c:
        fix_stance(game, a, 0 if a.suppression < 30 else 1)
    return c


def retreat_act(game, a, vis) -> int:
    brain = game.brains[a.side]
    if brain.home is None:
        return 100
    if int(brain.home[a.x, a.y]) == 0:
        game.exit_map(a, "withdrew")
        return 100
    # covering fire now and then
    if vis and a.weapon and a.weapon.t.kind == "gun" and a.weapon.loaded > 0 and game.rng.random() < 0.25:
        t = choose_target(game, a, vis)
        if t:
            return safe_fire(game, a, t.x, t.y, t)
    st = best_step(game, a, [(brain.home, 1.0)], exposure_w=3.0, crowd=True)
    c = do_step(game, a, st)
    if c:
        fix_stance(game, a, 1 if a.suppression < 60 else 2)
        return c
    return 100


def seek_shelter(game, a):
    """Get under a roof (or into shade): out of the wind and the snow, or out of the sun."""
    m = game.map
    if T.FLOOR[m.t[a.x, a.y]]:
        if a.stance == 0:
            a.stance = 1
        return None                              # already in; stay put and let the squad carry on
    cache = m.__dict__.get("_floors")
    if cache is None or cache[0] != game.turn // 600:
        pts = np.argwhere(T.FLOOR[m.t])
        m._floors = cache = (game.turn // 600, pts)
    pts = cache[1]
    if len(pts) == 0:
        return None
    d = np.abs(pts[:, 0] - a.x) + np.abs(pts[:, 1] - a.y)
    i = int(np.argmin(d))
    if d[i] > 30:
        return None
    tx, ty = int(pts[i][0]), int(pts[i][1])
    if a.ai.get("shelter_msg", -99) < game.turn - 600 and game.rng.random() < 0.3:
        a.ai["shelter_msg"] = game.turn
        a.say({"germany": "Mir ist so kalt...", "ussr": "Kholodno...", "usa": "I can't feel my feet.",
               "uk": "Bloody freezing."}.get(a.nation, "...") if getattr(a.body, "temp", 37) < 36 else
              {"germany": "Wasser...", "usa": "Gotta get out of this sun."}.get(a.nation, "..."), game.turn, 3)
    return path_step(game, a, tx, ty)


def rout_act(game, a, vis, near_enemy) -> int:
    brain = game.brains[a.side]
    doc = NATIONS[a.nation]["doctrine"]
    nq = getattr(game, "no_quarter", {}).get(a.side, 0)
    from .data.special import SPECIAL
    fan = 0.15 if "fanatic" in SPECIAL.get(a.__dict__.get("unit_type"), {}).get("flags", ()) else 1.0
    if near_enemy < 7 and game.rng.random() < 0.25 * doc.get("surrender", 1.0) * (0.35 ** min(3, nq)) * fan:
        game.surrender(a)
        return 100
    if a.ai.get("routing") is None:
        a.ai["routing"] = game.turn
        a.say(game.shout(a, "retreat"), game.turn)
        # throw away heavy stuff
        if a.weapon is not None and a.weapon.t.weight > 9 and game.rng.random() < 0.5:
            A.drop(game, a, a.weapon)
    if brain.home is not None and int(brain.home[a.x, a.y]) == 0:
        game.exit_map(a, "fled")
        return 100
    rm = brain.rout_map()
    maps = [(rm, 1.0)] if rm is not None else ([(brain.home, 1.0)] if brain.home is not None else [])
    st = best_step(game, a, maps, crowd=False)
    c = do_step(game, a, st)
    if c:
        fix_stance(game, a, 0 if a.suppression < 70 else 1)
        return c
    return 100


def banzai_act(game, a, vis) -> int:
    brain = game.brains[a.side]
    if a.ai.get("banzai") is None:
        a.ai["banzai"] = game.turn
        a.say(game.shout(a, "attack"), game.turn, 5)
        a.suppression = 0
        a.morale = 100
        if a.weapon is not None and a.weapon.t.kind == "gun" and not a.weapon.t.bayonet:
            mel = [i for i in a.inv if i.t.kind == "melee"]
            if mel:
                A.wield(game, a, mel[0])
    near = [e for e in vis if getattr(e, "vt", None) is None and e.active]
    if near:
        e = min(near, key=lambda e: dist(a, e))
        if dist(a, e) < 1.5:
            return A.melee(game, a, e)
        if dist(a, e) < 5 and a.weapon and a.weapon.t.kind == "gun" and a.weapon.loaded > 0 and game.rng.random() < 0.3:
            return safe_fire(game, a, e.x, e.y, e)
    fix_stance(game, a, 0)
    if brain.threat_dist is not None:
        st = best_step(game, a, [(brain.threat_dist, 1.0)], crowd=True)
        c = do_step(game, a, st)
        if c:
            return c
    return 100


def downed_act(game, a) -> int:
    b = a.body
    brain = game.brains[a.side]
    cb = a.ai.get("carried_by")
    if cb is not None:
        # still being carried?  Not if the man carrying him is down, gone, or has let go
        carrier = next((o for o in game.actors if o.id == cb), None)
        if carrier is None or not carrier.active or carrier.downed or carrier.carrying is not a:
            if carrier is not None and carrier.carrying is a:
                A.put_down(game, carrier)
            a.ai.pop("carried_by", None)
    if a.ai.get("carried_by") is not None or a.ai.get("surgery") is not None or a.ai.get("at_aid") is not None:
        return 100
    if b.bleed_rate() > 0.4:
        c = A.treat(game, a, a)
        if c:
            return c
    if a.ai.get("medic_call", -99) < game.turn - 25 and game.rng.random() < 0.5:
        a.ai["medic_call"] = game.turn
        a.say(game.shout(a, "medic"), game.turn, 3)
        game.emit_sound(a.x, a.y, 45, "scream", game.shout(a, "medic"), a.side, a)
    # crawl to safety
    if brain.safety is not None and int(brain.safety[a.x, a.y]) > 0 and b.legs_ok() + b.arms_ok() >= 2:
        st = best_step(game, a, [(brain.safety, 1.0)], crowd=False)
        c = do_step(game, a, st)
        if c:
            return c
    # the badly wounded may still fire a pistol
    return 100


def prisoner_escort_act(game, a) -> int | None:
    """A soldier you've handed a prisoner to: back to the rear with him, then back to the war (off the map)."""
    pid = a.ai.get("escort_prisoner")
    pw = next((o for o in game.actors if o.id == pid and o.alive and o.state == "surrendered"), None)
    if pw is None:
        a.ai.pop("escort_prisoner", None)
        return None
    brain = game.brains[a.side]
    if brain.home is None:
        return None
    if int(brain.home[a.x, a.y]) == 0:
        credit = pw.ai.get("credit")
        game.exit_map(pw, "captured")
        if credit is not None and game.player is not None and credit == game.player.id:
            game.duty.on_prisoner_delivered(game, pw)
        a.ai.pop("escort_prisoner", None)
        game.exit_map(a, "withdrew")
        return 100
    if max(abs(pw.x - a.x), abs(pw.y - a.y)) > 4:
        return 100                               # wait for him
    st = best_step(game, a, [(brain.home, 1.0)], exposure_w=2.0, crowd=False)
    c = do_step(game, a, st)
    return c or 100


def surrendered_act(game, a) -> int:
    # a prisoner follows the man who took him (or sits where he's told, or walks back on his own);
    # otherwise he walks toward the captor's rear
    enemy = other_side(a.side)
    brain = game.brains[enemy]
    cap = a.ai.get("captor")
    p = game.player
    order = a.ai.get("pw_order", "follow")
    if a.downed:
        return 100
    if order == "stay" and cap is not None:
        a.stance = 2 if a.stance != 2 else a.stance
        return 100
    if order == "rear" and brain.home is not None:
        if int(brain.home[a.x, a.y]) == 0:
            game.exit_map(a, "captured")
            return 100
        st = best_step(game, a, [(brain.home, 1.0)], crowd=False)
        return do_step(game, a, st) or 100
    escort = None
    if cap is not None and (p is None or cap != p.id):
        escort = next((o for o in game.actors if o.id == cap and o.active), None)
    if escort is not None:
        # a comrade of yours is walking him back
        d = max(abs(escort.x - a.x), abs(escort.y - a.y))
        if int(brain.home[a.x, a.y]) <= 2 * UNIT if brain.home is not None else False:
            game.exit_map(a, "captured")
            return 100
        if d > 1:
            c = path_step(game, a, escort.x, escort.y)
            if c:
                return c
        return 100
    if cap is not None and p is not None and cap == p.id and p.alive and p.state == "ok":
        d = max(abs(p.x - a.x), abs(p.y - a.y))
        # handed over behind our lines: near our own map edge, or at one of our posts
        behind = brain.home is not None and int(brain.home[a.x, a.y]) <= 7 * UNIT
        at_post = any(r.get("side") == enemy and r.get("kind") in ("hq", "depot", "aid") and
                      r["rect"][0] <= a.x < r["rect"][0] + r["rect"][2] and r["rect"][1] <= a.y < r["rect"][1] + r["rect"][3]
                      for r in getattr(game.map, "gen_positions", []) or [])
        if (behind or at_post) and d <= 5:
            game.exit_map(a, "captured")
            return 100
        if 2 < d < 30:
            c = path_step(game, a, p.x, p.y)
            if c:
                a.stance = 0
                return c
        if d <= 2:
            return 100
    if brain.home is None:
        return 100
    if int(brain.home[a.x, a.y]) == 0:
        game.exit_map(a, "captured")
        return 100
    if a.ai.get("guarded", False) or game.rng.random() < 0.5:
        return 100
    st = best_step(game, a, [(brain.home, 1.0)], crowd=False)
    return do_step(game, a, st) or 100


def swim_act(game, a) -> int:
    # drop heavy things if drowning
    if a.body.drown > 2 and a.carried_weight() > 14:
        heavy = sorted(a.inv, key=lambda i: -i.weight)
        if heavy:
            A.drop(game, a, heavy[0])
            return 100
    m = game.map
    best = None
    bd = 999
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = a.x + dx, a.y + dy
            if m.in_bounds(x, y) and m.walk[x, y] and m.water[x, y] < 2 and (x, y) not in game.soldier_at:
                return A.move(game, a, dx, dy) or 150
    # swim toward the shore / away from our entry edge
    brain = game.brains[a.side]
    mp = brain.threat_dist if brain.threat_dist is not None else brain.home
    tgt = order_target(game, a.squad) if a.squad else None
    if tgt is not None:
        return path_step(game, a, tgt[0], tgt[1]) or 150
    st = best_step(game, a, [(mp, 1.0)] if mp is not None else [])
    return do_step(game, a, st) or 150


def evade_explosive(game, a, ex) -> int:
    x, y = ex
    a.say(game.shout(a, "grenade"), game.turn)
    best = None
    bs = -1
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            nx, ny = a.x + dx, a.y + dy
            if not game.map.in_bounds(nx, ny):
                continue
            if (dx or dy) and (not game.map.walk[nx, ny] or (nx, ny) in game.soldier_at or (nx, ny) in game.vehicle_at):
                continue
            d = math.hypot(nx - x, ny - y) + game.map.pos_cover[nx, ny] / 30.0
            if d > bs:
                bs = d
                best = (dx, dy)
    if best and best != (0, 0) and math.hypot(a.x - x, a.y - y) < 3.5:
        c = A.move(game, a, *best)
        if c:
            return c
    return A.set_stance(game, a, 2) or 60


# ====================================================================== roles

def _willing(game, receiver) -> bool:
    """Your standing decides whether they'll bother with you."""
    if not receiver.is_player:
        return True
    if getattr(game, "renegade", False):
        return False
    rep = getattr(game, "duty", None).rep if getattr(game, "duty", None) is not None else 0.0
    return game.rng.random() < max(0.1, min(0.97, 0.75 + rep / 120))


def buddy_aid_act(game, a, vis) -> int | None:
    """A mate bleeding near you and no medic about: patch him up."""
    if vis and min(dist(a, e) for e in vis) < 12:
        return None
    if a.ai.get("aid_cd", -99) > game.turn - 25:
        return None
    if a.medical("bandage") is None and a.medical("tourniquet") is None:
        return None
    best = None
    for o in game.near(a.x, a.y, 4, a.side):
        if o is a or not o.alive or o.vehicle is not None or o.state != "ok":
            continue
        if max(abs(o.x - a.x), abs(o.y - a.y)) > 4 or o.body.bleed_rate() < 0.8 or o.ai.get("carried_by"):
            continue
        if any(m is not o and m.role in ("medic", "surgeon") and m.active for m in game.near(o.x, o.y, 6, a.side)):
            continue
        if best is None or o.body.bleed_rate() > best.body.bleed_rate():
            best = o
    if best is None:
        a.ai["aid_cd"] = game.turn - 19          # nobody needs him: look again in a few seconds
        return None
    if not _willing(game, best):
        a.ai["aid_cd"] = game.turn
        return None
    if dist(a, best) <= 1.5:
        a.ai["aid_cd"] = game.turn
        return A.treat(game, a, best)
    return path_step(game, a, best.x, best.y)


def share_ammo_act(game, a, vis) -> int | None:
    """A gunner running dry and you carry his calibre: take it over."""
    from .ammo import hand_over_possible, hand_over, spare_rounds
    if vis and min(dist(a, e) for e in vis) < 12:
        return None
    if a.ai.get("ammo_cd", -99) > game.turn - 40:
        return None
    best = None
    for o in game.near(a.x, a.y, 6, a.side):
        if o is a or not o.active or o.vehicle is not None:
            continue
        w = o.weapon
        if w is None or w.t.kind != "gun" or not w.t.cal or w.t.cat in ("at_disposable", "flamer"):
            continue
        if max(abs(o.x - a.x), abs(o.y - a.y)) > 6:
            continue
        if w.loaded > w.t.mag // 2 or spare_rounds(o, w) >= w.t.mag:
            continue
        if hand_over_possible(a, w):
            best = o
            break
    if best is None:
        a.ai["ammo_cd"] = game.turn - 30          # nobody short: look again in ten seconds
        return None
    if not _willing(game, best):
        a.ai["ammo_cd"] = game.turn
        return None
    if dist(a, best) <= 1.5:
        a.ai["ammo_cd"] = game.turn
        n = hand_over(game, a, best, best.weapon)
        if n:
            a.say(phrase(game.rng, a.nation, "share_ammo"), game.turn)
            if best.is_player:
                game.msg(f"{a.rank_short} {a.last_name} hands you ammunition for your {best.weapon.t.name}.", "good")
        return 120
    return path_step(game, a, best.x, best.y)


# who'll put down his rifle to heave on a track or pass up shells when it's quiet
HANDS = frozenset(("rifleman", "smg_gunner", "engineer", "at_soldier", "lmg_assistant", "hmg_assistant", "tank_crew",
                   "partisan", "volkssturm"))


def role_act(game, a, vis, sq, sstate) -> int | None:
    r = a.role
    if a.carrying is not None:
        return evacuate_act(game, a, vis)
    if sq is not None and sq.__dict__.get("task") is not None:
        from .tasks import act as task_act
        c = task_act(game, a, vis, sq)            # the job his leader gave the squad: scavenging, the wounded...
        if c:
            return c
    post = a.ai.get("post")
    if post is not None and game.__dict__.get("domain") != "aboard" and not vis and \
            game.turn - getattr(sq, "last_contact", -9999) > 60 and max(abs(a.x - post[0]), abs(a.y - post[1])) > 1:
        # a man with a post goes back to it when nothing's happening (the clerk to his typewriter)
        c = path_step(game, a, post[0], post[1], margin=20)
        if c:
            return c
    if r == "surgeon":
        return surgeon_act(game, a, vis)
    if r == "medic":
        return medic_act(game, a, vis)
    c = wounded_act(game, a, vis)
    if c:
        return c
    if r not in ("medic", "surgeon") and game.turn % 3 == a.id % 3:
        c = buddy_aid_act(game, a, vis) or share_ammo_act(game, a, vis)
        if c:
            return c
    if game.vehicles and r in HANDS and (a.ai.get("helping_v") is not None or game.turn % 5 == a.id % 5):
        from .maintenance import help_act
        c = help_act(game, a, vis, sq)
        if c:
            return c
        a.ai.pop("helping_v", None)
    if r in ("officer", "radioman"):
        c = officer_act(game, a, vis, sq)
        if c:
            return c
    w = a.weapon
    if w is not None and w.t.kind == "gun":
        cat = w.t.cat
        if cat == "mortar":
            return mortar_act(game, a, vis, sq)
        if cat in ("at_launcher", "at_disposable", "at_rifle"):
            c = at_act(game, a, vis, sq)
            if c:
                return c
        if cat == "sniper":
            c = sniper_act(game, a, vis, sq)
            if c:
                return c
        if cat == "flamer":
            c = flamer_act(game, a, vis, sq)
            if c:
                return c
    if r == "engineer":
        c = engineer_act(game, a, vis, sq)
        if c:
            return c
    if r in ("lmg_assistant", "hmg_assistant") and sq is not None:
        c = assistant_act(game, a, sq)
        if c:
            return c
    return None


def medic_act(game, a, vis) -> int | None:
    """Triage: the worst case you can reach first.  Treat, then get him out."""
    from . import medical as MED
    if a.carrying is not None:
        return evacuate_act(game, a, vis)
    near_enemy = min((dist(a, e) for e in vis), default=999)
    best = None
    bs = 0.0
    for o in game.near(a.x, a.y, 30, a.side):
        if not o.alive or o.state != "ok" or o.vehicle is not None or o is a:
            continue
        if o.ai.get("surgery") is not None or o.ai.get("carried_by") is not None:
            continue
        d = dist(a, o)
        if d > 30:
            continue
        b = o.body
        need = MED.needs_care(b)
        if need >= 1.0 and not MED.can_help(game, a, o):
            need = 0.0
        # a stabilised man who can't walk still needs carrying out
        if o.downed and b.bleed_rate() < 0.05 and not MED.at_aid_post(game, o) and near_enemy > 10:
            need = max(need, 12.0)
        if need < 1.0:
            continue
        s = need / (1.0 + d * 0.12)
        if s > bs:
            bs, best = s, o
    if best is None:
        a.ai.pop("patient", None)
        return None
    a.ai["patient"] = best.id                     # (pace.py: a medic with a patient runs)
    if dist(a, best) <= 1.5:
        a.ai.pop("patient", None)
        fix_stance(game, a, 1 if a.stance == 0 else a.stance)
        c = MED.first_aid(game, a, best) if MED.can_help(game, a, best) else None
        if c:
            if best.is_player and game.rng.random() < 0.5:
                a.say(phrase(game.rng, a.nation, "medic_comfort"), game.turn, tone="talk")
            return c
        # nothing more to be done here: carry him out of it
        if best.downed and best.body.bleed_rate() < 0.3:
            post = MED.nearest_aid(game, a)
            if post is not None or near_enemy < 15:
                return A.pick_up(game, a, best)
        return None
    if a.ai.get("coming_shout", -99) < game.turn - 30:
        a.ai["coming_shout"] = game.turn
        a.say(phrase(game.rng, a.nation, "medic_coming"), game.turn)
    c = path_step(game, a, best.x, best.y)
    if c:
        fix_stance(game, a, 1)
    return c


def evacuate_act(game, a, vis) -> int | None:
    """Dragging a casualty: to the aid station if there is one, else to cover and down."""
    from . import medical as MED
    c = a.carrying
    if c is None or not c.alive:
        A.put_down(game, a)
        return None
    post = MED.nearest_aid(game, a)
    brain = game.brains[a.side]
    if post is not None:
        px, py, rect = post
        if MED.at_aid_post(game, a):
            spot = MED.cot_near(game, a.x, a.y, 6)
            A.put_down(game, a, spot)
            c.ai["at_aid"] = game.turn
            c.ai["to_aid"] = game.turn
            if game.can_see(a.x, a.y):
                game.msg_for(a, c, f"lay{'s' if not a.is_player else ''} "
                                   f"{'you' if c.is_player else game.name_of(c)} on a cot at the aid station", "info")
            return 150
        step = path_step(game, a, px, py, margin=30)
        if step:
            fix_stance(game, a, 1)
            return step
    # no aid station (or no way there): out of the line of fire, then set him down
    if brain.safety is not None and int(brain.safety[a.x, a.y]) > 0:
        st = best_step(game, a, [(brain.safety, 1.0)], crowd=False)
        cst = do_step(game, a, st)
        if cst:
            return cst
    A.put_down(game, a)
    return 100


def surgeon_act(game, a, vis) -> int | None:
    """The aid station: stabilise, operate, send the mended back."""
    from . import medical as MED
    op = a.ai.get("operating")
    if op is not None:
        pt = next((o for o in game.actors if o.id == op), None)
        if pt is not None and pt.alive and pt.ai.get("surgery") is not None:
            return 100                  # at the table
        a.ai.pop("operating", None)
    if a.carrying is not None:
        return evacuate_act(game, a, vis)
    if not MED.at_aid_post(game, a):
        post = MED.nearest_aid(game, a)
        if post is not None:
            return path_step(game, a, post[0], post[1], margin=30)
        return medic_act(game, a, vis)
    best = None
    bs = 0.0
    for o in game.actors:
        if o.side != a.side or not o.alive or o is a or o.vehicle is not None or o.ai.get("surgery") is not None:
            continue
        if max(abs(o.x - a.x), abs(o.y - a.y)) > 14 or not MED.at_aid_post(game, o):
            continue
        need = MED.needs_care(o.body) + (40 if MED.needs_surgery(o.body) else 0)
        if need > bs:
            bs, best = need, o
    if best is None:
        return medic_act(game, a, vis)
    if dist(a, best) > 1.5:
        return path_step(game, a, best.x, best.y)
    if best.body.bleed_rate() > 0.3 and MED.can_help(game, a, best):
        return MED.first_aid(game, a, best)
    if MED.needs_surgery(best.body):
        return MED.begin_surgery(game, a, best) or 100
    return MED.first_aid(game, a, best) if MED.can_help(game, a, best) else 100


def wounded_act(game, a, vis) -> int | None:
    """The walking wounded head back to the aid station, and come back when they're mended."""
    from . import medical as MED
    if a.ai.get("to_aid") is None:
        return None
    if vis and min(dist(a, e) for e in vis) < 10:
        return None                     # fight first
    if MED.at_aid_post(game, a):
        if MED.fit_for_duty(a):
            a.ai.pop("to_aid", None)
            a.ai.pop("at_aid", None)
            if game.rng.random() < 0.5:
                a.say(game.rng.choice(["Back to it.", "Right. Where's my squad?"]) if a.nation in
                      ("usa", "uk", "canada", "australia", "newzealand") else "", game.turn, tone="talk")
            return None
        fix_stance(game, a, 2)
        return 100
    post = MED.nearest_aid(game, a)
    if post is None:
        a.ai.pop("to_aid", None)
        return None
    return path_step(game, a, post[0], post[1], margin=30)


def officer_act(game, a, vis, sq) -> int | None:
    brain = game.brains[a.side]
    if brain.arty_cooldown > 0 or game.turn % 5 != a.id % 5:
        return None
    # need a radio: carry one or have the radioman adjacent
    has_radio = a.has_tool("radio") is not None
    if not has_radio and sq is not None:
        for mm in sq.members:
            if mm is not a and mm.active and mm.has_tool("radio") and dist(mm, a) <= 3:
                has_radio = True
                break
    if not has_radio:
        return None
    if a.role == "radioman" and sq is not None and any(mm.role == "officer" and mm.active for mm in sq.members):
        return None
    doc = NATIONS[a.nation]["doctrine"]
    if game.rng.random() > doc.get("arty", 0.7):
        return None
    clusters = brain.clusters(radius=7, min_size=3, max_age=12)
    for weight, cx, cy, group in clusters:
        # danger close check
        danger_close = any(o.side == a.side and o.alive and abs(o.x - cx) + abs(o.y - cy) < 12
                           for o in game.actors)
        if danger_close and game.rng.random() > 0.08:
            continue
        ok = game.support.request_fire(a.side, cx, cy, caller=a)
        if ok:
            brain.arty_cooldown = 120
            a.say(phrase(game.rng, a.nation, "fire_mission"), game.turn, 4)
            return 300
    return None


def mortar_act(game, a, vis, sq) -> int | None:
    w = a.weapon
    brain = game.brains[a.side]
    if a.ammo_for(w) is None:
        return None
    cs = brain.clusters(radius=5, min_size=2, max_age=10) or \
        [(1, c.x, c.y, [c]) for c in brain.live_contacts(8, False)]
    for weight, cx, cy, group in cs:
        d = math.hypot(cx - a.x, cy - a.y)
        if w.t.min_rng <= d <= w.t.rng:
            if any(o.side == a.side and o.alive and abs(o.x - cx) + abs(o.y - cy) < 5 for o in game.actors):
                continue
            fix_stance(game, a, 2)
            return A.fire(game, a, cx, cy)
    # enemies too close: pull back a little
    return None


def at_act(game, a, vis, sq) -> int | None:
    brain = game.brains[a.side]
    w = a.weapon
    # visible vehicles first
    vehs = [e for e in vis if getattr(e, "vt", None) is not None and not e.dead and not e.abandoned]
    if not vehs:
        cs = [c for c in brain.live_contacts(20, False) if c.kind in ("tank", "vehicle", "atgun")]
        if not cs:
            return None
        c = min(cs, key=lambda c: (c.x - a.x) ** 2 + (c.y - a.y) ** 2)
        if math.hypot(c.x - a.x, c.y - a.y) > 45:
            return None
        v = c.ref
        if v is None:
            return None
        if getattr(v, "side", None) == a.side:
            # an old sighting of a tank that's since been taken by our side
            from .familiar import mistakable
            if not mistakable(game, v, a.side) or max(abs(a.x - v.x), abs(a.y - v.y)) < 10:
                brain.contacts.pop(c.id, None) if hasattr(c, "id") else None
                if v.ai.get("captured"):
                    v.ai["recognised"] = max(v.ai.get("recognised", -1), game.turn + 240)
                return None
        if (v.x, v.y) != (c.x, c.y):
            # stalk toward where it was last seen
            return path_step(game, a, c.x, c.y) if max(abs(a.x - c.x), abs(a.y - c.y)) > 6 else None
    else:
        v = min(vehs, key=lambda e: dist(a, e))
    d = dist(a, v)
    in_range = d <= w.t.rng and d >= w.t.min_rng
    visible = v in vis
    # side/rear shots preferred: stalk around the flank
    rel = (octant(a.x - v.x, a.y - v.y) - v.facing) % 8
    good_angle = rel in (2, 3, 4, 5, 6)
    if visible and in_range and (good_angle or d < 10 or w.t.cat == "at_disposable" or game.rng.random() < 0.4):
        fix_stance(game, a, 1 if w.t.cat != "at_rifle" else 2)
        if w.t.cat == "at_launcher" and w.loaded <= 0:
            return A.reload(game, a)
        if a.ai.get("at_aim") != v.id or aim_level(a, v.x, v.y) < 1:
            a.ai["at_aim"] = v.id
            a.aim_target = v.pos
            a.aim_turns = 1
            return aim_time(a, w.t)
        a.ai["at_aim"] = None
        return safe_fire(game, a, v.x, v.y, v)
    # stalk
    fx = v.x + {0: 1, 1: 1, 2: 0, 3: -1, 4: -1, 5: -1, 6: 0, 7: 1}[v.facing] * -6
    fy = v.y + {0: 0, 1: -1, 2: -1, 3: -1, 4: 0, 5: 1, 6: 1, 7: 1}[v.facing] * -6
    mp = brain.flank_map(("veh", v.id, a.side), v.x, v.y, fx * 2 - v.x, fy * 2 - v.y,
                         rmin=max(3, w.t.min_rng), rmax=max(8, int(w.t.rng * 0.8)))
    if mp is not None and int(mp[a.x, a.y]) > 0:
        st = best_step(game, a, [(mp, 1.0)], exposure_w=3.0)
        c = do_step(game, a, st)
        if c:
            fix_stance(game, a, 1)
            return c
    if visible and in_range:
        return safe_fire(game, a, v.x, v.y, v)
    return None


def sniper_act(game, a, vis, sq) -> int | None:
    shots = a.ai.get("shots_here", 0)
    brain = game.brains[a.side]
    if shots >= 3 or (a.hit_turn > game.turn - 5 and a.suppression > 30):
        # relocate to another concealed spot
        tgt = a.ai.get("reloc")
        if tgt is None or (a.x, a.y) == tgt:
            m = game.map
            best = None
            bs = -1e9
            for _ in range(30):
                x = a.x + game.rng.randint(-14, 14)
                y = a.y + game.rng.randint(-14, 14)
                if not m.in_bounds(x, y) or not m.walk[x, y]:
                    continue
                s = m.conceal[x, y] + m.pos_cover[x, y] - brain.exposure_at(x, y) * 30
                if s > bs:
                    bs, best = s, (x, y)
            a.ai["reloc"] = best
            tgt = best
        if tgt is not None and (a.x, a.y) != tgt:
            c = path_step(game, a, tgt[0], tgt[1])
            if c:
                fix_stance(game, a, 1)
                return c
        a.ai["shots_here"] = 0
        a.ai["reloc"] = None
    if vis:
        # snipers pick officers, gunners and radiomen
        pref = [e for e in vis if getattr(e, "vt", None) is None and e.active and
                (e.role in ("officer", "radioman", "squad_leader", "sniper") or contact_kind(e) in ("mg", "hmg"))]
        tgt = pref[0] if pref else None
        if tgt is not None:
            w = a.weapon
            if w.loaded <= 0:
                return A.reload(game, a)
            fix_stance(game, a, 2)
            lvl = aim_level(a, tgt.x, tgt.y)
            if lvl < max_aim(a, w.t):
                a.aim_turns = lvl + 1
                a.aim_target = tgt.pos
                return aim_time(a, w.t)
            a.ai["shots_here"] = shots + 1
            return safe_fire(game, a, tgt.x, tgt.y, tgt)
    return None


def flamer_act(game, a, vis, sq) -> int | None:
    w = a.weapon
    if w.loaded <= 0:
        return None
    near = [e for e in vis if getattr(e, "vt", None) is None and e.active and dist(a, e) <= w.t.rng + 6]
    m = game.map
    for e in near:
        d = dist(a, e)
        entrenched = m.pos_cover[e.x, e.y] > 40 or T.FLOOR[m.t[e.x, e.y]]
        if d <= w.t.rng and not friends_in_line(game, a, e.x, e.y, cone=0.15):
            return A.fire(game, a, e.x, e.y, e)
        if entrenched:
            c = path_step(game, a, e.x, e.y)
            if c:
                fix_stance(game, a, 1)
                return c
    return None


def engineer_act(game, a, vis, sq) -> int | None:
    m = game.map
    # cut wire blocking the way
    if a.has_tool("wirecutters"):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = a.x + dx, a.y + dy
                if m.in_bounds(x, y) and T.DEFS[int(m.t[x, y])].key == "wire" and game.rng.random() < 0.5:
                    return A.cut_wire(game, a, x, y)
    ch = a.find(lambda i: i.t.kind == "explosive")
    if ch is None:
        return None
    # target: enemy bunker positions (occupied embrasures) or vehicles within 12
    vehs = [e for e in vis if getattr(e, "vt", None) is not None and not e.dead and dist(a, e) < 12]
    tgt = None
    if vehs:
        v = vehs[0]
        # a tank is several tiles long: go for the nearest part of the hull, not its centre
        tgt = min(v.cells(), key=lambda c: max(abs(c[0] - a.x), abs(c[1] - a.y)))
        if v.near(a.x, a.y) <= 1:
            return A.place_charge(game, a, ch, tgt[0], tgt[1])
        # walk to a free tile beside that hull cell (the hull itself can't be stood on)
        side = next(((tgt[0] + dx, tgt[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                     if m.in_bounds(tgt[0] + dx, tgt[1] + dy) and m.walk[tgt[0] + dx, tgt[1] + dy]
                     and (tgt[0] + dx, tgt[1] + dy) not in game.vehicle_at), None)
        c = path_step(game, a, *(side or tgt))
        if c:
            fix_stance(game, a, 1)
        return c
    else:
        for e in vis:
            if getattr(e, "vt", None) is None and m.pos_cover[e.x, e.y] >= 45 and dist(a, e) < 14:
                tgt = e.pos
                break
    if tgt is None:
        return None
    if max(abs(a.x - tgt[0]), abs(a.y - tgt[1])) <= 1:
        return A.place_charge(game, a, ch, tgt[0], tgt[1])
    c = path_step(game, a, tgt[0], tgt[1])
    if c:
        fix_stance(game, a, 1)
    return c


def assistant_act(game, a, sq) -> int | None:
    """Feed the gunner: carry magazines or belts to him when he runs low."""
    from .ammo import sources
    for g in sq.members:
        if g is a or not g.active or g.weapon is None or g.weapon.t.kind != "gun":
            continue
        if g.weapon.t.cat not in ("lmg", "hmg"):
            continue
        if g.ammo_count(g.weapon) >= g.weapon.t.mag:
            continue
        mine = [m for m in sources(a, g.weapon) if (m.t.kind == "mag" and m.loaded > 0) or m.t.kind == "ammo"]
        if not mine:
            continue
        if dist(a, g) <= 1.5:
            it = mine[0]
            a.invent.remove(it)
            if g.add_item(it) is None:
                a.add_item(it)
                continue
            a.say(phrase(game.rng, a.nation, "ammo"), game.turn)
            return 150
        return path_step(game, a, g.x, g.y)
    return None


# ====================================================================== vehicles

VEH_RANGE = {"tank": 45, "td": 55, "spg": 50, "ltank": 35, "tankette": 25, "armcar": 30,
             "halftrack": 25, "truck": 0, "car": 20, "lc": 20, "amtrac": 25}


def vehicle_act(game, v) -> int:
    if v.dead:
        return 100
    if v.burning:
        v.burning -= 1
        if game.rng.random() < 0.03:
            from .combat import destroy_vehicle
            destroy_vehicle(game, v, None, "fire", catastrophic=game.rng.random() < 0.3)
            return 100
        if v.crew > 0 and not v.player_crewed and game.rng.random() < 0.1:
            from .combat import abandon_vehicle
            abandon_vehicle(game, v)
            return 100
    if not v.active:
        return 100
    if v.ai.get("reload_turn") != game.turn:
        v.ai["reload_turn"] = game.turn
        v.reload = max(0, v.reload - 100 * max(0.4, v.crew / max(1, v.vt.crew))
                       * (0.5 + 0.5 * v.ai.get("fam", 1.0) if v.ai.get("captured") else 1.0))
    vis = update_actor_vision(game, v)
    brain = game.brains[v.side]
    for e in vis:
        brain.report(e, game.turn)
    sq = v.squad
    if sq is not None and vis:
        sq.last_contact = game.turn
    vt = v.vt
    from . import crew as C
    seat = C.player_seat(v)
    if not v.player_crewed:
        # empty landing craft back off to the sea and leave
        if vt.vtype == "lc" and not v.passengers and v.ai.get("ramp"):
            return landing_craft_withdraw(game, v)
        # landing craft & transports
        if vt.vtype in ("lc", "amtrac", "truck", "halftrack", "car") and v.passengers:
            c = transport_act(game, v, vis)
            if c:
                return c
    if sq is not None and sq.order.kind == "mount" and v.vt.seats > 0 and not v.player_crewed:
        return 100               # wait for the infantry to climb aboard
    # ---- shoot: every manned station on its own
    res, tgt = vehicle_gunnery(game, v, vis, sq)
    if res == "traverse":
        return 150 if not v.static else 250
    if res == "crank":
        from .vdamage import HAND_TRAVERSE
        return HAND_TRAVERSE
    # ---- move: the driver, on the commander's word (yours, if you're the commander or at the wheel)
    if not v.mobile or not C.ai_manned(v, "driver"):
        return 100
    if seat in ("driver", "commander"):
        return 100
    if res == "main":
        return 100               # a short halt to fire
    return vehicle_move(game, v, vis, tgt)


def _roe_ok(v, sq, tgt) -> bool:
    if tgt is None or sq is None or getattr(sq.order, "roe", "free") == "free":
        return True
    d = max(abs(tgt.x - v.x), abs(tgt.y - v.y))
    under_fire = getattr(v, "suppression", 0) > 10 or v.hp < v.vt.hp * 0.9
    return d <= 4 or (sq.order.roe == "return" and (under_fire or d <= 10))


def _soft(e) -> bool:
    """A machine gun's business: men, and things without armour."""
    vt = getattr(e, "vt", None)
    if vt is None:
        return e.active
    return not e.dead and not e.abandoned and max(vt.armor) <= 8


def _designated(game, v, vis):
    """The commander's target, if it's still there to be shot at."""
    tid = v.ai.get("designated")
    if tid is None:
        return None
    for e in vis:
        if e.id == tid:
            if getattr(e, "vt", None) is not None and (e.dead or e.abandoned):
                break
            if getattr(e, "vt", None) is None and not e.active:
                break
            return e
    if game.turn - v.ai.get("designated_turn", game.turn) > 30:
        v.ai.pop("designated", None)
    return None


def vehicle_gunnery(game, v, vis, sq):
    """The gunner on the main gun and coax, each other machine gunner on his own gun.
    Returns (what happened, the main target): 'main', 'traverse', 'mg' or None."""
    from . import crew as C
    vt = v.vt
    if sq is not None and sq.order.kind == "mount" and vt.seats > 0 and not v.player_crewed:
        return None, None
    res = None
    des = _designated(game, v, vis)
    tgt, ammo = vehicle_choose_target(game, v, vis)
    if des is not None:
        tgt = des
        if getattr(des, "vt", None) is not None:
            ammo = "ap" if v.ap > 0 and not _soft(des) else ("he" if v.he > 0 else None)
        else:
            ammo = "he" if v.he > 0 and max(abs(des.x - v.x), abs(des.y - v.y)) > 3 else ammo
        if v.mount is not None and v.mount.flame:
            ammo = "flame" if max(abs(des.x - v.x), abs(des.y - v.y)) <= v.mount.rng else None
    hold = v.player_crewed and C.player_seat(v) == "commander" and v.ai.get("hold_fire")
    if hold and des is None:
        tgt = None
    if des is None and not _roe_ok(v, sq, tgt):
        tgt = None
    mg_cd = v.ai.setdefault("mg_cd", {})
    # the gunner: main gun, or the coax when the target's soft
    if tgt is not None and C.ai_manned(v, "gunner"):
        if vt.main:
            from . import vdamage as VD
            want = octant(tgt.x - v.x, tgt.y - v.y)
            tr = VD.traverse(v)
            if not vt.turret or v.static or tr == "jammed":
                gun = v.turret if tr == "jammed" else v.facing
                diff = (want - gun) % 8
                if diff not in (0, 1, 7):
                    # traverse the hull / gun carriage - unless you're driving and haven't turned it
                    if C.player_seat(v) == "driver":
                        if v.ai.get("asked_turn", -99) < game.turn - 20:
                            v.ai["asked_turn"] = game.turn
                            side = "left" if diff <= 4 else "right"
                            game.msg(f"Gunner: 'Target {side}! Swing her {side}!'" +
                                     (" The turret's jammed!" if tr == "jammed" else ""), "radio")
                        tgt = None
                    elif not v.static and not (VD.can_move(v) and C.ai_manned(v, "driver")):
                        tgt = None                  # the gun can't be brought to bear: it waits for something in its arc
                    else:
                        step = 1 if diff <= 4 else -1
                        if game.turn_vehicle(v, v.facing + step) and tr != "jammed":
                            v.turret = v.facing
                        return "traverse", tgt
            elif tr == "hand":
                diff = (want - v.turret) % 8
                if diff not in (0, 1, 7):
                    v.turret = (v.turret + (1 if diff <= 4 else -1)) % 8     # cranking the handwheel
                    return "crank", tgt
        if tgt is not None:
            blocked = friends_in_line(game, v, tgt.x, tgt.y, cone=0.05)
            if not blocked and vt.main and v.gun_ok and v.reload <= 0 and ammo is not None:
                if vehicle_fire_main(game, v, tgt.x, tgt.y, tgt, ammo):
                    res = "main"
            idxs = C.mgs_for(v, "gunner")
            if res is None and idxs and not blocked and _soft(tgt) and dist(v, tgt) < 45 \
                    and mg_cd.get("gunner", -1) < game.turn:
                if vehicle_fire_mg(game, v, tgt.x, tgt.y, tgt, idxs=idxs):
                    mg_cd["gunner"] = game.turn
                    res = "mg"
    # the other machine guns: each gunner finds his own work in his own arc
    for st in C.stations(vt):
        if st in ("gunner", "driver", "loader", "commander") or not C.ai_manned(v, st):
            continue
        if mg_cd.get(st, -1) >= game.turn:
            continue
        idxs = C.mgs_for(v, st)
        if not idxs:
            continue
        cands = []
        if des is not None and _soft(des):
            cands.append(des)
        if hold:
            cands = cands[:1]
        else:
            cands += sorted((e for e in vis if _soft(e) and e is not des), key=lambda e: dist(v, e))
        for e in cands[:6]:
            if dist(v, e) >= 40 or not C.mg_arc_ok(v, idxs[0], e.x, e.y):
                continue
            if e is not des and not _roe_ok(v, sq, e):
                continue
            if friends_in_line(game, v, e.x, e.y, cone=0.06):
                continue
            if vehicle_fire_mg(game, v, e.x, e.y, e, idxs=idxs):
                mg_cd[st] = game.turn
                res = res or "mg"
            break
    return res, tgt


def vehicle_choose_target(game, v, vis):
    best = None
    bs = 0.0
    ammo = None
    mt = v.mount
    for e in vis:
        d = dist(v, e)
        if getattr(e, "vt", None) is not None:
            if e.dead or e.abandoned:
                continue
            if mt is None or mt.flame:
                continue
            from .combat import vehicle_face
            face = vehicle_face(e, v.x, v.y)
            arm = e.vt.armor[min(face, 2)]
            pen = mt.ap_pen * max(0.6, 1 - d / (mt.rng * 3))
            if v.ap <= 0:
                continue
            s = (8.0 if pen > arm * 0.9 else 1.5) / (1 + d / 40)
            if e.vt.vtype in ("tank", "td", "spg"):
                s *= 1.5
            if s > bs:
                bs, best, ammo = s, e, "ap"
        else:
            if not e.active:
                continue
            if mt is not None and mt.flame:
                if d <= mt.rng:
                    s = 4.0
                    if s > bs:
                        bs, best, ammo = s, e, "flame"
                continue
            cluster = sum(1 for o in vis if getattr(o, "vt", None) is None and abs(o.x - e.x) <= 3 and abs(o.y - e.y) <= 3)
            fort = game.map.pos_cover[e.x, e.y] > 40 or T.FLOOR[game.map.t[e.x, e.y]]
            use_he = mt is not None and v.he > 0 and (cluster >= 2 or fort or contact_kind(e) in ("mg", "hmg", "atgun")
                                                      or e.role == "at_soldier") and d > 3
            s = (1.0 + cluster * 0.8 + (2 if e.role == "at_soldier" else 0)) / (1 + d / 30)
            if use_he:
                s *= 1.6
            if s > bs:
                bs, best, ammo = s, e, ("he" if use_he else None)
    return best, ammo


def vehicle_move(game, v, vis, tgt) -> int:
    brain = game.brains[v.side]
    sq = v.squad
    vt = v.vt
    wheeled = vt.vtype in ("car", "truck", "armcar")
    # hold at good range if engaging
    if tgt is not None:
        d = dist(v, tgt)
        rng_want = VEH_RANGE.get(vt.vtype, 35)
        if d < 8 and getattr(tgt, "vt", None) is None and tgt.role == "at_soldier":
            return vehicle_step_away(game, v, tgt)
        if d <= rng_want and (v.reload > 0 or game.rng.random() < 0.8):
            return 100
    dest = None
    if sq is not None:
        dest = order_target(game, sq)
        if sq.members and sq.leader is not None and sq.leader.active and sq.kind != "tank" \
                and sq.leader.vehicle is not v:
            dest = sq.leader.pos
    if dest is None:
        return 100
    if max(abs(v.x - dest[0]), abs(v.y - dest[1])) <= 3:
        return 100
    crush = vt.crush
    wide = v.size[1] >= 2
    mp = brain.vehicle_map(dest[0], dest[1], crush, wheeled, wide=wide)
    if wide and (mp is None or int(mp[v.x, v.y]) >= BIG // 2):
        # no way through at full width: try the narrow way and squeeze where it can
        mp = brain.vehicle_map(dest[0], dest[1], crush, wheeled)
    if mp is None:
        return 100
    here = int(mp[v.x, v.y]) + brain.exposure_at(v.x, v.y) * 2
    # places it recently couldn't fit into: try another line for a while
    avoid = v.ai.setdefault("avoid", {})
    for k in [k for k, t0 in avoid.items() if game.turn - t0 > 90]:
        del avoid[k]
    steps = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == dy == 0:
                continue
            x, y = v.x + dx, v.y + dy
            if not game.map.in_bounds(x, y):
                continue
            val = int(mp[x, y])
            if val >= BIG // 2:
                continue
            ov = game.vehicle_at.get((x, y))
            if ov is not None and ov is not v:
                continue
            if (x, y) in avoid:
                continue
            o = game.soldier_at.get((x, y))
            if o is not None and (o.side == v.side or not o.downed):
                continue
            # prefer to keep the front toward the enemy
            val += brain.exposure_at(x, y) * 2
            val += game.rng.random()
            if val < here:
                steps.append((val, dx, dy))
    steps.sort()
    for val, dx, dy in steps[:4]:
        c = game.try_move_vehicle(v, dx, dy)
        if c is not None:
            return c
        avoid[(v.x + dx, v.y + dy)] = game.turn
    if steps:
        # boxed in: back up a tile and try another line
        v.stuck += 1
        if v.stuck > 2:
            fx, fy = FACING_VEC[v.facing]
            c = game.try_move_vehicle(v, -fx, -fy, reverse=True)
            if c is not None:
                return c
    return 100


def vehicle_step_away(game, v, threat) -> int:
    if not v.mobile:
        return 100
    cands = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = v.x + dx, v.y + dy
            if (dx or dy) and game.map.in_bounds(x, y):
                d = math.hypot(x - threat.x, y - threat.y)
                if d > dist(v, threat):
                    cands.append((-d, dx, dy))
    cands.sort()
    for _, dx, dy in cands[:4]:
        c = game.try_move_vehicle(v, dx, dy, reverse=True)
        if c is not None:
            return c
    return 100


def transport_act(game, v, vis) -> int | None:
    """Carry passengers toward the objective; dismount on contact or arrival."""
    vt = v.vt
    m = game.map
    sq = v.squad
    if sq is not None and sq.order.kind == "mount" and vt.vtype != "lc":
        return 100                 # loaded and waiting for the word
    dest = order_target(game, sq) if sq is not None else None
    near_enemy = min((dist(v, e) for e in vis), default=999)
    arrived = dest is not None and max(abs(v.x - dest[0]), abs(v.y - dest[1])) < 12
    if vt.vtype == "lc":
        # landing craft: keep going until shallow water blocks us, then drop the ramp
        ahead_blocked = True
        mp = game.brains[v.side].vehicle_map(dest[0], dest[1], 0, False) if dest else None
        shallow = m.water[v.x, v.y] <= 1
        stuck = v.stuck > 2
        if shallow or stuck or v.ai.get("ramp"):
            if not v.ai.get("ramp"):
                v.ai["ramp"] = game.turn
                game.msg_near(v.x, v.y, "The ramp slams down!", "warn")
                game.emit_sound(v.x, v.y, 60, "ramp", "a landing craft ramp dropping", v.side, v)
            game.disembark_all(v)
            return 100
        # move toward the beach through water
        return landing_craft_step(game, v)
    if near_enemy < 22 or arrived or v.hp < vt.hp * 0.6:
        game.disembark_all(v)
        return 150
    return None


def landing_craft_step(game, v) -> int:
    m = game.map
    from .vdamage import can_move
    if not can_move(v):
        v.stuck += 1                     # dead in the water: the ramp goes down where she lies
        return 100
    edge = game.home_edge(v.side)
    step = {"N": (0, 1), "S": (0, -1), "W": (1, 0), "E": (-1, 0)}.get(edge, (0, 1))
    tries = [step, (step[0] + (step[1] != 0), step[1] + (step[0] != 0)),
             (step[0] - (step[1] != 0), step[1] - (step[0] != 0))]
    for dx, dy in tries:
        x, y = v.x + dx, v.y + dy
        if not m.in_bounds(x, y):
            continue
        if m.water[x, y] >= 1 and game.vehicle_at.get((x, y)) in (None, v) and m.t[x, y] != T.ID["hedgehog"]:
            v.stuck = 0
            return game.move_vehicle(v, dx, dy)
        if T.DEFS[int(m.t[x, y])].key == "hedgehog":
            # ripped open on the obstacles
            if game.rng.random() < 0.15:
                hit_vehicle(game, v, 100, 40, x, y, None, "a beach obstacle", kind="ap", face=0)
    v.stuck += 1
    return 100


def landing_craft_withdraw(game, v) -> int:
    from .vdamage import can_move
    if not can_move(v):
        return 100                       # she's going nowhere: a wreck in the surf
    edge = game.home_edge(v.side)
    step = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}.get(edge, (0, -1))
    x, y = v.x + step[0], v.y + step[1]
    m = game.map
    gap = {"N": v.y, "S": m.h - 1 - v.y, "W": v.x, "E": m.w - 1 - v.x}.get(edge, 99)
    if not m.in_bounds(x, y) or gap <= max(v.size):
        game.lift_vehicle(v)                 # her stern's at the edge of the map: off she goes
        v.dead = True
        v.x = v.y = -1
        return 100
    if m.water[x, y] >= 1 and game.vehicle_at.get((x, y)) in (None, v):
        return game.move_vehicle(v, step[0], step[1], reverse=True)
    return 100
