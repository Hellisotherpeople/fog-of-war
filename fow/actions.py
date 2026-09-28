"""Verbs shared by the player and the AI.  Each returns the moves it costs (or None if impossible)."""
from __future__ import annotations

from .constants import cap

import math

import tcod

from . import tiles as T
from .combat import explode, fire_weapon, hit_actor, ignite, melee_attack
from .data.items import ITEMS, ammo_id
from .entities import ACCESS_COST, Item

STANCE_MOVE = {0: 1.0, 1: 1.45, 2: 3.2}
STANCE_NAME = {0: "standing", 1: "crouching", 2: "prone"}


# ====================================================================== movement

def can_enter(game, a, x, y) -> bool:
    m = game.map
    if not m.in_bounds(x, y):
        return False
    tid = m.t[x, y]
    if not T.WALK[tid] and not T.DOOR[tid]:
        return False
    if (x, y) in game.vehicle_at:
        return False
    return True


FLOOR_WORD = {-1: "the cellar", 0: "the ground floor", 1: "the first floor", 2: "the second floor",
              3: "the top of the tower"}


def floor_word(game, a) -> str:
    z = getattr(a, "z", 0)
    if z <= 0:
        return FLOOR_WORD.get(z, "the ground floor")
    b = game.map.building_at(a.x, a.y)
    if b is not None and z >= b[1] - 1:
        style = next((bb[4] for bb in game.map.buildings if tuple(bb[:4]) == b[0]), "")
        top = {"church": "the bell tower", "desert_house": "the flat roof", "barn": "the hayloft",
               "white_church": "the bell tower", "tower": "the top of the tower", "keep": "the battlements",
               "lighthouse": "the lantern gallery", "pagoda": "the top of the pagoda",
               "elevator": "the top of the elevator", "marabout": "the roof", "white_house": "the flat roof",
               "windmill": "the cap of the mill", "post_mill": "the cap of the mill"}.get(style)
        if top:
            return top
    return FLOOR_WORD.get(z, f"floor {z}")


def climb(game, a, dz: int) -> int | None:
    """Up the stairs (a floor at a time) or down them; down through the trapdoor into the cellar, and up
    again.  None if there's no way that way from here."""
    m = game.map
    t = m.tile(a.x, a.y).key
    z = getattr(a, "z", 0)
    b = m.building_at(a.x, a.y)
    if a.vehicle is not None or a.carrying is not None:
        return None
    if dz > 0:
        if z < 0 and t == "trapdoor":
            a.z = 0
        elif z >= 0 and t == "stairs" and b is not None and z < b[1] - 1:
            a.z = z + 1
        else:
            return None
    else:
        if z > 0 and t == "stairs":
            a.z = z - 1
        elif z == 0 and t == "trapdoor":
            a.z = -1
        else:
            return None
    a.stance = min(a.stance, 1)
    game.note_move(a)
    if a.is_player:
        game.msg(f"You {'climb' if a.z > z else 'go down'} to {floor_word(game, a)}.", "info")
    return 400 if abs(a.z - z) else 100


def move(game, a, dx: int, dy: int, allow_swap=True):
    m = game.map
    if getattr(a, "peek", None):
        unpeek(game, a)
    nx, ny = a.x + dx, a.y + dy
    if not m.in_bounds(nx, ny):
        return None
    tid = int(m.t[nx, ny])
    d = T.DEFS[tid]
    z = getattr(a, "z", 0)
    if z != 0:
        # upstairs you can walk the floor (the same plan as below) but not out of the door; in the cellar, nowhere
        b0 = m.building_at(a.x, a.y)
        if z < 0 or b0 is None or m.building_at(nx, ny) is None or m.building_at(nx, ny)[0] != b0[0] or \
                not T.FLOOR[tid]:
            if a.is_player:
                game.msg("You're in the cellar: up through the trapdoor first (<)." if z < 0 else
                         "You're upstairs: the stairs are the way down (>).", "info")
            return None
    # doors open when walked into
    if d.door == 1:
        m.set(nx, ny, "door_open")
        m.refresh()
        game.emit_sound(nx, ny, 20, "door", "a door creaking open", a.side, a)
        return 100
    if not d.walk:
        return None
    if (nx, ny) in game.vehicle_at:
        v = game.vehicle_at[(nx, ny)]
        return None
    other = game.soldier_at.get((nx, ny))
    if other is not None and other is not a:
        own_pw = a.is_player and other.state == "surrendered" and other.ai.get("captor") == a.id and not other.downed
        if not own_pw and (not allow_swap or other.side != a.side or other.is_player or (
                not other.active and not other.downed)):
            return None
        # swap places with a friendly (but not back and forth)
        if other.downed and not a.is_player:
            return None
        if not a.is_player and (other.ai.get("swapped", -9) >= game.turn - 2 or a.ai.get("swapped", -9) >= game.turn - 2):
            return None
        a.ai["swapped"] = game.turn
        other.ai["swapped"] = game.turn
        game.soldier_at[(a.x, a.y)] = other
        game.soldier_at[(nx, ny)] = a
        other.x, other.y = a.x, a.y
        a.x, a.y = nx, ny
        a.moved_turn = game.turn
        game.note_move(a)
        game.note_move(other)
        return int(150 * STANCE_MOVE[a.stance])
    # entanglement
    if a.entangled > 0:
        a.entangled -= 1
        game.emit_sound(a.x, a.y, 25, "wire", "the clink of someone caught on wire", a.side, a)
        if a.is_player:
            game.msg("You struggle against the barbed wire.", "warn")
        return 100
    cost = T.COST[tid]
    water = T.WATER[tid]
    if water >= 1 and a.stance == 2:
        a.stance = 1
    mult = STANCE_MOVE[a.stance]
    if a.body.downed() and a.body.conscious:
        mult = max(mult, 3.5)
        a.stance = 2
    from .pace import COST as PACE_COST, pace_of
    pace = pace_of(game, a) if water < 2 else "walk"
    a.ai["pace_now"] = pace
    mult *= PACE_COST[pace]
    from .relief import climb
    cost = int(cost * mult * climb(game.map, a.x, a.y, a.x + dx, a.y + dy))     # the slope: up is slow
    if dx != 0 and dy != 0:
        cost = int(cost * 1.1)
    # carrying a wounded comrade
    if a.carrying is not None:
        cost = int(cost * 1.8)
    old = (a.x, a.y)
    del_ok = game.soldier_at.get(old) is a
    if del_ok:
        del game.soldier_at[old]
    a.x, a.y = nx, ny
    if dx:
        a.face = 1 if dx > 0 else -1
    game.soldier_at[(nx, ny)] = a
    game.note_move(a)
    a.moved_turn = game.turn
    a.deployed = False
    a.aim_turns = 0
    a.stats["distance"] += 1
    if a.carrying is not None:
        c = a.carrying
        if c.alive and max(abs(c.x - old[0]), abs(c.y - old[1])) > 2:
            put_down(game, a)                     # he isn't with you any more
        elif c.alive and game.soldier_at.get((c.x, c.y)) is c and game.soldier_at.get(old) is None:
            del game.soldier_at[(c.x, c.y)]
            c.x, c.y = old
            game.soldier_at[old] = c
            game.note_move(c)
        elif not c.alive:
            put_down(game, a)
    # wire
    if d.key == "wire":
        if game.rng.random() < 0.6:
            a.entangled = game.rng.randint(1, 4)
            if a.is_player:
                game.msg("Barbs snag your uniform and flesh!", "hurt")
            if game.rng.random() < 0.4:
                hit_actor(game, a, game.rng.uniform(2, 6), "cut", None, "barbed wire", silent=True)
    # footsteps
    from .pace import LOUD as PACE_LOUD
    from .stealth import fieldcraft
    loud = ({0: 30, 1: 24, 2: 16}[a.stance] + T.SOUND[tid] * 2) * PACE_LOUD.get(pace, 1.0) * \
        (fieldcraft(a) if pace in ("sneak", "walk") else 1.0)
    if loud > 0 and game.rng.random() < 0.35 * PACE_LOUD[pace]:
        game.emit_sound(nx, ny, int(loud), "footsteps", "running feet" if pace != "walk" else "movement", a.side, a)
    # mines
    mn = m.mines.get((nx, ny))
    if mn is not None:
        trigger_mine(game, a, nx, ny, mn)
    # breath: crawling and heavy loads wear you out
    from .pace import DRAIN as PACE_DRAIN, FATIGUE as PACE_FATIGUE
    load = 1.0 + max(0.0, a.weight_now(game.turn) - 18.0) / 22.0
    drain = (0.22, 0.45, 0.9)[a.stance] * (T.COST[tid] / 100.0) * load * PACE_DRAIN[pace]
    if a.carrying is not None:
        drain *= 2.0
    if water >= 2:
        drain += 1.5
    if getattr(a.body, "temp", 37.0) > 38.5:
        drain *= 1.4                           # labouring in the heat
    from .skills import fitness_mult, use
    drain *= fitness_mult(a)                   # the fit keep their wind
    if drain > 0.6 and game.rng.random() < 0.05:
        use(game, a, "fitness", 1.0)
    if pace == "sneak" and game.rng.random() < 0.08 and a.ai.get("near_enemy_turn", -99) > game.turn - 30:
        use(game, a, "stealth", 1.0)           # creeping with the enemy close: it teaches you
    a.stamina = max(0.0, getattr(a, "stamina", 100.0) - drain)
    a.fatigue = min(100.0, getattr(a, "fatigue", 0.0) + PACE_FATIGUE[pace] * load * (T.COST[tid] / 100.0)
                    * (2.0 if a.carrying is not None else 1.0))
    # deep water
    if water >= 2:
        game.swimming(a)
    else:
        a.body.drown = 0
    return max(40, cost)


def trigger_mine(game, a, x, y, mn):
    m = game.map
    known = a.side in mn.known
    if mn.kind == "at" and game.rng.random() > 0.05:
        return
    if known and game.rng.random() > 0.08:
        return
    del m.mines[(x, y)]
    if mn.kind == "smine":
        if a.is_player:
            game.msg("*click* ... Something under your boot. S-mine!", "death")
        else:
            game.msg("A metallic click...", "sound", (x, y), heard=True)
        game.pending_explosions.append([x, y, 60, 3, 0, 1, "smine"])
        return
    game.msg("A mine goes off!" if not a.is_player else "The ground erupts beneath you - a mine!",
             "death", (x, y))
    leg = game.rng.choice(("l_leg", "r_leg"))
    hit_actor(game, a, game.rng.uniform(55, 95), "blast", None, "an anti-personnel mine", part=leg)
    explode(game, x, y, 30, 1, frags=0, source="an anti-personnel mine", crater=False)


def set_stance(game, a, s: int) -> int:
    if s == a.stance:
        return 0
    if s < 2 and a.body.downed():
        if a.is_player:
            game.msg("You can't get up. Your legs won't hold you.", "hurt")
        return 0
    if game.map.water[a.x, a.y] >= 1 and s == 2:
        return 0
    cost = {(0, 1): 40, (1, 0): 40, (0, 2): 70, (1, 2): 50, (2, 1): 70, (2, 0): 110}[(a.stance, s)]
    a.stance = s
    a.aim_turns = 0
    if s < 2:
        a.deployed = False
    return cost


# ====================================================================== weapons

def reload(game, a, weapon=None, speed=False) -> int | None:
    from .ammo import reload as ammo_reload
    w = weapon or a.weapon
    if w is None or w.t.kind != "gun":
        return None
    if w.jammed:
        return unjam(game, a)
    cost = ammo_reload(game, a, w, speed=speed)
    if cost:
        from .familiar import learn, level, slow
        f = level(a, w.t)
        if f < 1.0:
            if a.is_player and f < 0.35 and a.ai.get("fumble_msg") != w.t.id:
                a.ai["fumble_msg"] = w.t.id
                game.msg(f"You fumble with the {w.t.name}'s unfamiliar catch before it gives.", "info")
            cost = int(cost * slow(a, w.t))
            learn(game, a, w.t, 0.025)
    return cost


def unjam(game, a) -> int:
    w = a.weapon
    if w is None or not w.jammed:
        return 0
    from .familiar import learn, level, slow
    f = level(a, w.t)
    learn(game, a, w.t, 0.03)
    if game.rng.random() < 0.7 * (0.5 + 0.5 * f):
        w.jammed = False
        if a.is_player:
            game.msg(f"You clear the jam in your {w.t.name}.", "info")
        if w.loaded > 0:
            w.loaded -= 1
    elif a.is_player:
        game.msg("You work the action. Still stuck." if f > 0.5 else
                 "You work the action - or what you think is the action. Still stuck.", "warn")
    return int(game.rng.randint(120, 260) * slow(a, w.t))


def cycle_mode(a) -> str:
    w = a.weapon
    if w is None or w.t.kind != "gun":
        return ""
    w.mode = (w.mode + 1) % len(w.t.modes)
    return w.mode_name


def throw_range(a, item) -> int:
    t = item.t
    base = 13 + t.throw
    if t.weight > 1.0:
        base -= int((t.weight - 1.0) * 5)
    if a.stance == 2:
        base -= 4
    elif a.stance == 1:
        base -= 1
    if a.body.hp["r_arm"] <= 0 and a.body.hp["l_arm"] <= 0:
        base = 2
    elif a.body.hp["r_arm"] <= 0 or a.body.hp["l_arm"] <= 0:
        base -= 4
    return max(2, base)


def throw(game, a, item, tx, ty, cook: int = 0) -> int | None:
    face(a, tx)
    t = item.t
    if t.kind not in ("grenade", "explosive"):
        return None
    rng = game.rng
    maxr = throw_range(a, item)
    dx, dy = tx - a.x, ty - a.y
    dist = math.hypot(dx, dy)
    if dist > maxr:
        s = maxr / dist
        tx, ty = a.x + int(round(dx * s)), a.y + int(round(dy * s))
        dist = maxr
    # scatter
    sig = 0.5 + dist * 0.09 + (8 - a.skill) * 0.12 + a.suppression / 35
    if a.stance == 2:
        sig += 0.6
    lx = int(round(tx + rng.gauss(0, sig)))
    ly = int(round(ty + rng.gauss(0, sig)))
    # trace flight: stops at walls, bounces off trees/windows
    m = game.map
    pk = getattr(a, "peek", None)
    ox, oy = (a.x + pk[0], a.y + pk[1]) if pk else (a.x, a.y)     # thrown from round the corner
    path = tcod.los.bresenham((ox, oy), (lx, ly))
    land = (ox, oy)
    for i in range(1, len(path)):
        x, y = int(path[i][0]), int(path[i][1])
        if not m.in_bounds(x, y):
            break
        tid = m.t[x, y]
        d = T.DEFS[int(tid)]
        if d.window and d.key == "window":
            m.set(x, y, "window_broken")
            m.refresh()
            game.emit_sound(x, y, 35, "glass", "breaking glass", a.side, a)
        if not d.walk and not d.window:
            # a solid wall stops it dead (it drops back where it last was); a hedge or a tree mostly does;
            # a low wall or a sandbag parapet it sails over - but it never comes to rest on top of one
            if (not d.see and d.cover >= 90) or (d.tall and rng.random() < 0.4):
                break
            continue
        land = (x, y)
    # take it out of inventory
    access = a.access_cost(item)
    thrown = a.remove_item(item, 1) if item.count > 1 else a.remove_item(item)
    thrown.count = 1
    a.stats["grenades"] += 1
    if a.is_player:
        game.msg(f"You throw the {t.name}.", "combat")
    elif game.can_see(a.x, a.y):
        game.msg(f"{cap(game.name_of(a))} throws a grenade!", "warn", a.pos)
    a.say(game.shout(a, "grenade"), game.turn)
    game.effect_throw(a.x, a.y, land[0], land[1])
    if thrown.data and thrown.data.get("live") is not None:
        # throwing back a live grenade: the same fuse keeps burning
        game.drop_live(thrown, land[0], land[1])
        game.map.add_item(land[0], land[1], thrown)
    else:
        game.land_explosive(thrown, land[0], land[1], a, cook)
    a.fired_turn = game.turn
    return 140 + access // 2


def place_charge(game, a, item, x, y) -> int | None:
    t = item.t
    if t.kind != "explosive":
        return None
    placed = a.remove_item(item, 1) if item.count > 1 else a.remove_item(item)
    placed.count = 1
    v = game.vehicle_at.get((x, y))
    if v is not None:
        placed.data = {"on_vehicle": v.id}
    pencil = next((i for i in a.inv if i.t.tool == "time_pencil"), None) if t.charge in (
        "plastic", "block", "magnetic", "satchel") else None
    if pencil is not None:
        # a time pencil: ten minutes on the band - and they ran fast in the heat and slow in the cold
        a.remove_item(pencil, 1) if pencil.count > 1 else a.remove_item(pencil)
        from .thermal import ambient
        temp = ambient(game)
        delay = int(600 * game.rng.uniform(0.75, 1.3) * (1.0 - (temp - 12) * 0.01))
        game.land_explosive(placed, x, y, a, t.fuse - delay, placed_charge=True, hidden=True)
        if a.is_player:
            game.msg(f"You press the {t.name} home, squeeze the time pencil to break the ampoule and pull the "
                     f"safety strip. Ten minutes on the band - give or take. Walk away.", "warn")
        from .skills import level, use
        use(game, a, "demolitions", 3.0)
        return int(400 * max(0.55, 1.35 - level(a, "demolitions") * 0.09))
    game.land_explosive(placed, x, y, a, 0, placed_charge=True)
    if a.is_player:
        game.msg(f"You set the {t.name}. {t.fuse} seconds. MOVE!", "warn")
    a.say(game.shout(a, "grenade"), game.turn)
    from .skills import level, use
    use(game, a, "demolitions", 3.0)
    return int(250 * max(0.55, 1.35 - level(a, "demolitions") * 0.09))   # the trained set it fast


def peek(game, a, dx, dy) -> int | None:
    """Lean out of cover (round a corner, over a wall, out of a window) without leaving it."""
    m = game.map
    x, y = a.x + dx, a.y + dy
    if (dx, dy) == (0, 0) or not m.in_bounds(x, y) or a.vehicle is not None:
        return None
    if not m.see[x, y]:
        return None                      # solid wall: nothing to lean into
    if (x, y) in game.vehicle_at:
        return None
    unpeek(game, a)
    a.peek = (dx, dy)
    game.peek_at = getattr(game, "peek_at", {})
    game.peek_at[(x, y)] = a
    if dx:
        a.face = 1 if dx > 0 else -1
    return 40


def unpeek(game, a):
    pk = getattr(a, "peek", None)
    if pk:
        pa = getattr(game, "peek_at", {})
        if pa.get((a.x + pk[0], a.y + pk[1])) is a:
            del pa[(a.x + pk[0], a.y + pk[1])]
    a.peek = None


class _Leaning:
    """Shoot or throw from where your head is, not from behind the wall."""

    def __init__(self, a):
        self.a = a
        self.pk = getattr(a, "peek", None)

    def __enter__(self):
        if self.pk:
            self.a.x += self.pk[0]
            self.a.y += self.pk[1]

    def __exit__(self, *exc):
        if self.pk:
            self.a.x -= self.pk[0]
            self.a.y -= self.pk[1]


def pick_up(game, a, patient) -> int | None:
    """Take a casualty over your shoulder (or by the webbing) to drag him out."""
    if a.carrying is not None or patient is a or patient.vehicle is not None or a.vehicle is not None:
        return None
    if max(abs(a.x - patient.x), abs(a.y - patient.y)) > 1 or not patient.alive:
        return None
    if patient.ai.get("carried_by") is not None or patient.ai.get("surgery") is not None:
        return None
    a.carrying = patient
    patient.ai["carried_by"] = a.id
    patient.stance = 2
    game.msg_for(a, patient, f"grab{'s' if not a.is_player else ''} "
                             f"{'you' if patient.is_player else game.name_of(patient)} by the webbing", "info")
    return 150


def put_down(game, a, spot=None):
    """Let go of whoever you're carrying (onto a cot, if you name one)."""
    c = a.carrying
    a.carrying = None
    if c is None:
        return
    c.ai.pop("carried_by", None)
    if spot is not None and c.alive and game.soldier_at.get(spot) is None:
        if game.soldier_at.get((c.x, c.y)) is c:
            del game.soldier_at[(c.x, c.y)]
        c.x, c.y = spot
        game.soldier_at[spot] = c
        game.note_move(c)


def face(a, tx):
    """Turn to face a point (left or right: that's all a figure on the map can show)."""
    if tx != a.x:
        a.face = 1 if tx > a.x else -1


def melee(game, a, target, move=None) -> int:
    face(a, target.x)
    return melee_attack(game, a, target, move)


def fire(game, a, tx, ty, target=None, area=False) -> int | None:
    w = a.weapon
    if w is None or w.t.kind != "gun":
        return None
    if a.ai.get("grapple") is not None and w.t.cat != "pistol":
        from .melee import grappling
        if grappling(game, a) is not None:
            if a.is_player:
                game.msg("You can't bring a long gun round with a man locked onto you. Fight - or tear free.", "warn")
            return None
    a.ai.pop("stuck_in", None)                   # (a round fired frees a stuck bayonet - they were taught that)
    face(a, tx)
    if w.jammed:
        return unjam(game, a)
    t = w.t
    if t.cat == "mortar":
        if a.stance != 2:
            set_stance(game, a, 2)
        ammo = a.ammo_for(w)
        if ammo is None:
            return None
        return fire_weapon(game, a, w, tx, ty, target)
    if w.loaded <= 0:
        return reload(game, a)
    if a.is_player:
        a.ai["last_shot"] = (tx, ty, game.turn)
    with _Leaning(a):
        return fire_weapon(game, a, w, tx, ty, target, area=area)


# ====================================================================== items

def pickup(game, a, item, x=None, y=None) -> int | None:
    """Pick an item up off the ground.  None if there's no room for it."""
    m = game.map
    x = a.x if x is None else x
    y = a.y if y is None else y
    if item.t.kind == "corpse":
        return None
    live = item.data and item.data.get("live") is not None
    if live:
        m.remove_item(x, y, item)
        game.pick_live(item, a)
        a.invent.hands = a.invent.hands or item
        if a.invent.hands is not item:
            a.add_item(item)
        return 60
    if item.t.kind == "armor" and item.t.slot == "head" and a.helmet is None:
        m.remove_item(x, y, item)
        a.helmet = item
        _enemy_helmet_warning(game, a, item)
        return 150
    if a.add_item(item) is None:
        return None
    m.remove_item(x, y, item)
    if a.is_player:
        from .entities import lose_count
        lose_count(item)
    return 80 + a.access_cost(item) // 3


def _enemy_helmet_warning(game, a, item):
    if not a.is_player:
        return
    from .data.items import HELMETS
    from .data.nations import NATIONS
    owners = [n for n, hid in HELMETS.items() if hid == item.tid]
    if owners and all(NATIONS.get(n, {}).get("side") != a.side for n in owners):
        game.msg(f"You put on the {item.t.name}. At a distance, your own side will see an enemy helmet.", "warn")


def drop(game, a, item, count=None) -> int:
    if item is a.helmet:
        a.helmet = None
        game.map.add_item(a.x, a.y, item)
        return 60
    it = a.remove_item(item, count)
    game.map.add_item(a.x, a.y, it)
    if item.data and item.data.get("live") is not None:
        game.drop_live(item, a.x, a.y)
    return 50


def wield(game, a, item) -> int | None:
    if item is a.weapon:
        return 0
    cost = a.access_cost(item) + 50
    if not a.wield(item):
        return None
    if item.t.kind == "gun":
        from .familiar import first_look, level
        first_look(game, a, item.t)
        cost = int(cost * (1 + (1 - level(a, item.t)) * 0.3))
    return cost


def drink(game, a, item) -> int:
    t = item.t
    if t.tool == "canteen":
        a.morale = min(100, a.morale + 4)
        a.suppression = max(0, a.suppression - 10)
        if getattr(a.body, "temp", 37.0) > 37.4:
            a.body.temp -= 0.5                 # water, in the heat, is life
        a.stamina = min(100.0, getattr(a, "stamina", 100.0) + 8)
    elif t.tool == "flask":
        a.body.alcohol += 1.0
        a.body.pain = max(0, a.body.pain - 10)
        a.morale = min(100, a.morale + 8)
    item.uses -= 1
    if item.uses <= 0:
        a.remove_item(item)
    return 150


def treat(game, medic, patient, item=None) -> int | None:
    """Apply first aid.  medic may be the patient."""
    b = patient.body
    self_aid = medic is patient
    rng = game.rng
    quality = 1.0 if medic.role == "medic" else 0.8
    if self_aid:
        quality -= 0.15
        if b.arms_ok() == 0:
            return None
    if item is None:
        # pick the right treatment automatically - and if there's nothing for the wound, the pain or the blood
        if b.worst_wound() is not None:
            limbs = [w for w in b.wounds if w.part not in ("head", "torso") and not w.bandaged and w.bleed > 5]
            if limbs and medic.medical("tourniquet"):
                item = medic.medical("tourniquet")
            else:
                item = medic.medical("bandage") or medic.medical("sulfa")
        if item is None and b.effective_pain() > 70 and medic.medical("morphine"):
            item = medic.medical("morphine")
        if item is None and b.blood < 3800 and medic.medical("plasma"):
            item = medic.medical("plasma")
    if item is None:
        return None
    med = item.t.med
    cost = 300
    if self_aid:
        who = "yourself" if medic.is_player else medic.himself
    else:
        who = "you" if patient.is_player else game.name_of(patient)
    if med in ("bandage", "kit"):
        w = b.bandage(quality)
        if w is None:
            return None
        cost = 280 if not self_aid else 380
        if med == "kit":
            item.uses -= 1
            # a medic's bag treats everything at once over time
            while b.worst_wound() is not None and item.uses > 0 and rng.random() < 0.7:
                b.bandage(quality)
                item.uses -= 1
                cost += 150
            if b.effective_pain() > 60:
                b.morphine += 50
            if item.uses <= 0:
                medic.remove_item(item)
        else:
            _consume(medic, item)
        medic.stats["bandaged"] += 1
        game.msg_for(medic, patient, f"bandage{'s' if not medic.is_player else ''} {who}", "good")
    elif med == "sulfa":
        w = b.worst_wound()
        if w:
            w.bleed *= 0.75
        _consume(medic, item)
        cost = 120
        game.msg_for(medic, patient, f"sprinkle{'s' if not medic.is_player else ''} sulfa powder on the wound", "good")
    elif med == "tourniquet":
        if b.tourniquet() is None:
            return None
        _consume(medic, item)
        cost = 200
        game.msg_for(medic, patient, f"cinch{'es' if not medic.is_player else ''} a tourniquet on {who}", "good")
    elif med == "morphine":
        b.morphine += item.t.power
        _consume(medic, item)
        cost = 100
        game.msg_for(medic, patient, f"jab{'s' if not medic.is_player else ''} a morphine syrette into {who}", "good")
    elif med == "plasma":
        b.heal_blood(item.t.power)
        _consume(medic, item)
        cost = 600
        game.msg_for(medic, patient, f"rig{'s' if not medic.is_player else ''} a bottle of plasma for {who}", "good")
    return cost


def _consume(owner, item):
    if item.count > 1:
        item.count -= 1
    else:
        owner.remove_item(item)


def dig(game, a) -> int | None:
    m = game.map
    tid = m.t[a.x, a.y]
    if not T.DIG[tid] or T.DEFS[int(tid)].key in ("foxhole", "trench", "trench_snow"):
        return None
    if not a.has_tool("shovel"):
        return None
    if a.ai.get("dig_at") != (a.x, a.y):
        a.ai["dig_at"] = (a.x, a.y)
        a.dig_progress = 0
    rate = 2 if m.climate not in ("winter",) else 1
    if T.DEFS[int(tid)].key in ("crater", "crater_big"):
        rate *= 2
    a.dig_progress += rate
    if a.dig_progress % 10 == 0:
        game.emit_sound(a.x, a.y, 22, "digging", "digging", a.side, a)
    if a.dig_progress >= 60:
        a.dig_progress = 0
        m.set(a.x, a.y, "foxhole" if m.climate != "winter" else "trench_snow")
        m.refresh()
        if a.is_player:
            game.msg("You finish your foxhole. It isn't much, but it's home.", "good")
        return 100
    return 100


def cut_wire(game, a, x, y) -> int | None:
    m = game.map
    if T.DEFS[int(m.t[x, y])].key != "wire":
        return None
    if not a.has_tool("wirecutters"):
        if a.is_player:
            game.msg("You need wire cutters.", "warn")
        return None
    m.set(x, y, "dirt")
    m.refresh()
    game.emit_sound(x, y, 18, "wire", "the snip of wire cutters", a.side, a)
    return 300


def fire_flare(game, a, tx, ty) -> int | None:
    fg = a.has_tool("flaregun")
    if fg is None or fg.uses <= 0:
        return None
    fg.uses -= 1
    dist = min(35, math.hypot(tx - a.x, ty - a.y))
    ang = math.atan2(ty - a.y, tx - a.x)
    fx = int(a.x + math.cos(ang) * dist + game.rng.gauss(0, 3))
    fy = int(a.y + math.sin(ang) * dist + game.rng.gauss(0, 3))
    fx = max(0, min(game.map.w - 1, fx))
    fy = max(0, min(game.map.h - 1, fy))
    game.map.lights.append([fx, fy, 16, game.turn + 70])
    game.emit_sound(a.x, a.y, 55, "flare", "the pop of a flare pistol", a.side, a)
    game.msg("A flare arcs up and bursts, bathing the ground in white light." if a.is_player
             else "A flare goes up!", "warn", (fx, fy))
    return 120


def resupply(game, a) -> int | None:
    """Take ammunition from an adjacent ammo stack / crate."""
    m = game.map
    near = False
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = a.x + dx, a.y + dy
            if not m.in_bounds(x, y):
                continue
            if T.DEFS[int(m.t[x, y])].key == "ammo_stack":
                near = True
            for it in m.items_at(x, y):
                if it.tid == "ammo_crate":
                    near = True
    if not near:
        return None
    got = []
    from .ammo import give_ammo, sources
    guns = [i for i in a.inv if i.t.kind == "gun" and i.t.cal]
    for g in guns:
        # top up part-used magazines first, then draw full ones
        for src in sources(a, g):
            if src.t.kind == "mag" and src.loaded < src.t.mag:
                src.loaded = src.t.mag
                src.known_rounds = True
        have = a.ammo_count(g)
        want = max(0, g.t.mag * (4 if g.t.cat not in ("lmg", "hmg") else 3) - have)
        if want > 0:
            before = a.ammo_count(g)
            give_ammo(a, g, want)
            if a.ammo_count(g) > before:
                got.append(ITEMS[g.t.magtype].name if g.t.get("magtype") else ITEMS[ammo_id(g.t.cal)].name)
    from .data.roles import pick_grenade
    if len(a.grenades()) < 2:
        gid = pick_grenade(game.rng, a.nation, game.year)
        if gid:
            a.add_item(Item(gid, 2))
            got.append(ITEMS[gid].name)
    if got:
        a.ai["resupplied_turn"] = game.turn
    if a.is_player:
        game.msg(("You fill your pouches: " + ", ".join(got) + ".") if got else
                 "You're already carrying all you can use.", "good" if got else "info")
    return 400 if got else 100


# ====================================================================== vehicles

def enter_vehicle(game, a, v) -> int | None:
    if v.dead:
        return None
    if a.side != v.side and not (v.abandoned or v.crew == 0):
        return None
    if v.near(a.x, a.y) > 1:
        return None
    cap = v.vt.seats
    if a.role == "tank_crew" or v.crew == 0 or v.abandoned:
        # crew position
        if v.abandoned or v.crew < v.vt.crew:
            v.crew += 1
            v.abandoned = False
            if v.side != a.side or (v.squad is not None and v.squad.side != a.side):
                # changing hands: it leaves the old owners' squad (and their strength, and their orders)
                if v.squad is not None and v in v.squad.vehicles:
                    v.squad.vehicles.remove(v)
                v.squad = a.squad if a.squad is not None and a.squad.side == a.side else None
                if v.squad is not None and v not in v.squad.vehicles:
                    v.squad.vehicles.append(v)
            v.side = a.side
            if getattr(a, "peek", None):
                unpeek(game, a)
            game.remove_from_map(a)
            a.vehicle = v
            a.x, a.y = v.x, v.y
            v.crew_actors.append(a)
            # someone else's machine: the gears, the traverse, the breech are all strange
            from .data.nations import NATIONS
            vside = NATIONS.get(v.nation, {}).get("side")
            if vside is not None and vside != a.side and not v.ai.get("captured"):
                v.ai["captured"] = True
                v.ai["fam"] = 0.15 + (0.1 if "veteran" in a.traits else 0)
                v.ai["captured_turn"] = game.turn
                if a.is_player:
                    game.msg(f"You drop into the enemy {v.vt.name}. Nothing is where it should be. And to your own "
                             f"side it's an enemy {v.vt.name}, until you paint something on it.", "warn")
            if a.is_player:
                from .crew import default_seat
                v.player_crewed = True
                v.player_station = default_seat(v, a.role)
            return 200
    from .maintenance import riders_capacity
    cap = riders_capacity(v)                     # (a tank with no seats inside has room on the hull)
    if len(v.passengers) >= cap:
        return None
    if getattr(a, "peek", None):
        unpeek(game, a)
    game.remove_from_map(a)
    a.vehicle = v
    a.x, a.y = v.x, v.y
    v.passengers.append(a)                       # (no seat inside: on the outside - entities.riding)
    a.ai.pop("rider", None)
    return 150


def exit_vehicle(game, a) -> int | None:
    v = a.vehicle
    if v is None:
        return None
    if getattr(a, "peek", None):
        unpeek(game, a)
    spot = game.free_around(v, prefer_away_from=game.brain_enemy_center(a.side))
    if spot is None:
        return None
    if a in v.passengers:
        v.passengers.remove(a)
        a.ai.pop("rider", None)
    if a in v.crew_actors:
        v.crew_actors.remove(a)
        v.crew = max(0, v.crew - 1)
        if a.is_player:
            v.player_crewed = False
            v.player_station = None
    a.vehicle = None
    a.x, a.y = spot
    game.place_on_map(a)
    a.stance = 1
    return 150
