"""Hand to hand: the fight at arm's length.

It was rare - a few wounds in a hundred were ever made with a bayonet - and when it came it was short,
desperate and ugly: a thrust, a rifle butt swung at a head, a sharpened entrenching tool, a knife, two
men rolling in the mud of a trench.  Each blow here is one exchange of about a second:

- the attacker's move, from what's in his hands and the moment (a bayonet thrusts, a rifle butt smashes,
  a kukri or a spade chops, a knife stabs, empty hands punch or grab);
- the defender's answer: a parry with his own rifle or blade, a twist aside, an arm up - or nothing, if
  he never saw it coming, is on the ground, or has two men on him;
- where it lands: a real part of the body, with the wound its weapon makes (hit_actor), and what it did -
  a gash, a broken arm, a man folded over the blade; a blow that rings off a helmet; a bayonet stuck in
  ribs that has to be wrenched out; a rifle knocked out of a man's hands; a man knocked flat.

Close enough, two men can lock together: then it's knives, thumbs, a throat, a throw to the ground, or
tearing free.  A man who hasn't seen you - from behind, in the dark, looking the other way - can be
killed with a knife or strangled before he makes a sound: what commandos and agents trained for.

Skill (hand to hand), strength and wind, wounds, reach and surprise decide it.  Everyone fights by the
same rules; the player just chooses the move (or lets the obvious one be chosen).
"""
from __future__ import annotations

from .constants import cap

# ---------------------------------------------------------------- moves
# kind: the wound (body damage kind); mult: of the weapon's damage; cost: moves (100 = a second);
# reach: tiles of "length" (a rifle and bayonet outreaches a knife); parts: where it goes
MOVES = {
    "thrust": dict(name="Thrust with the bayonet", kind="cut", mult=1.5, cost=110, reach=2,
                   parts={"torso": 0.68, "l_leg": 0.06, "r_leg": 0.06, "l_arm": 0.06, "r_arm": 0.06, "head": 0.08}),
    "butt": dict(name="Smash the rifle butt into him", kind="blunt", mult=1.0, cost=110, reach=1,
                 parts={"head": 0.55, "torso": 0.25, "l_arm": 0.1, "r_arm": 0.1}),
    "slash": dict(name="Slash", kind="cut", mult=1.0, cost=100, reach=1,
                  parts={"head": 0.3, "torso": 0.3, "l_arm": 0.2, "r_arm": 0.2}),
    "chop": dict(name="Chop with the spade", kind="cut", mult=1.1, cost=120, reach=1,
                 parts={"head": 0.4, "torso": 0.25, "l_arm": 0.15, "r_arm": 0.15, "l_leg": 0.025, "r_leg": 0.025}),
    "stab": dict(name="Stab with the knife", kind="cut", mult=1.25, cost=80, reach=0,
                 parts={"torso": 0.7, "head": 0.12, "l_arm": 0.09, "r_arm": 0.09}),
    "punch": dict(name="Punch", kind="blunt", mult=1.0, cost=70, reach=0,
                  parts={"head": 0.7, "torso": 0.3}),
    "grab": dict(name="Grab him and wrestle", kind=None, mult=0, cost=90, reach=0, parts={}),
    "disarm": dict(name="Knock his weapon aside", kind=None, mult=0, cost=90, reach=1, parts={}),
    "shove": dict(name="Shove him away (room to shoot)", kind=None, mult=0, cost=70, reach=1, parts={}),
    # only when locked together
    "choke": dict(name="Throttle him", kind=None, mult=0, cost=100, reach=0, parts={}),
    "throw": dict(name="Throw him down", kind="blunt", mult=0.6, cost=100, reach=0, parts={"torso": 0.6, "head": 0.4}),
    "break": dict(name="Tear free", kind=None, mult=0, cost=80, reach=0, parts={}),
    # only on a man who hasn't seen you
    "silent": dict(name="Knife him before he can shout", kind="cut", mult=4.0, cost=120, reach=0,
                   parts={"torso": 0.5, "head": 0.5}),
    "strangle": dict(name="Strangle him from behind", kind=None, mult=0, cost=150, reach=0, parts={}),
}
FIST = 7                         # damage of a fist or a boot
BUTT = 12                        # a rifle butt

# the words: where on a part, and how bad, by the kind of wound
WHERE = {"head": ["face", "jaw", "temple", "skull", "throat", "cheek"],
         "torso": ["belly", "chest", "ribs", "side", "gut", "shoulder"],
         "l_arm": ["left forearm", "left shoulder", "left hand", "left arm"],
         "r_arm": ["right forearm", "right shoulder", "right hand", "right arm"],
         "l_leg": ["left thigh", "left knee", "left shin"],
         "r_leg": ["right thigh", "right knee", "right shin"]}
BEHIND = {"torso": ["back", "kidneys", "back"], "head": ["neck", "throat", "back of the skull"]}
HOW = {"cut": [(0.2, "a shallow gash"), (0.45, "deep"), (0.8, "to the bone"), (9, "through and through")],
       "blunt": [(0.2, "a glancing blow"), (0.45, "a sickening crack"), (0.8, "bone breaking"), (9, "caving it in")]}


def _who(game, a) -> str:
    n = game.name_of(a)
    for art in ("a ", "an "):
        if n.startswith(art):
            return "the " + n[len(art):]
    return n


def _whose(game, a) -> str:
    return "your" if a.is_player else _who(game, a) + "'s"


def _weapon(a):
    """What he fights with: (kind of weapon, damage, words)."""
    w = a.weapon
    if w is not None and w.functional and w.t.kind == "melee":
        if w.t.tool == "shovel":
            return "spade", w.t.dmg * w.condition, w.t.name
        big = w.t.hands >= 2 or w.t.dmg >= 24
        return ("blade" if big else "knife"), w.t.dmg * w.condition, w.t.name
    if w is not None and w.t.kind == "gun":
        if w.t.bayonet:                                # (every rifleman had his bayonet in its scabbard)
            return "bayonet", w.t.bayonet, "bayonet"
        if w.t.weight >= 2.5:
            return "rifle", BUTT, "rifle butt"
        return "pistol", FIST + 2, w.t.name
    return "hands", FIST, "fists"


def _knife(a):
    """A knife on him he could get at in a scramble (his belt, his boot)."""
    for it in a.inv:
        if it.functional and it.t.kind == "melee" and it.t.tool != "shovel" and it.t.dmg <= 26:
            return it
    return None


def moves_for(game, a, target) -> list[str]:
    """The moves open to him against this man, right now (the first is the obvious one)."""
    wk, _dmg, _nm = _weapon(a)
    g = grappling(game, a)
    if g is target:
        out = []
        if _knife(a) is not None or wk == "knife":
            out.append("stab")
        out += ["choke", "throw", "break"]
        return out
    out = []
    if surprised(game, target, a):
        if wk == "knife" or _knife(a) is not None:
            out.append("silent")
        out.append("strangle")
    out += {"bayonet": ["thrust", "butt"], "rifle": ["butt"], "blade": ["slash"], "spade": ["chop"],
            "knife": ["stab"], "pistol": ["punch"], "hands": ["punch"]}[wk]
    out += ["grab", "disarm" if target.weapon is not None else None, "shove"]
    return [m for m in out if m]


def grappling(game, a):
    gid = a.ai.get("grapple")
    if gid is None:
        return None
    o = next((x for x in game.actors if x.id == gid), None)
    if o is None or not o.alive or o.downed or max(abs(o.x - a.x), abs(o.y - a.y)) > 1 or o.ai.get("grapple") != a.id:
        a.ai.pop("grapple", None)
        return None
    return o


def _release(a, b):
    a.ai.pop("grapple", None)
    b.ai.pop("grapple", None)


def surprised(game, target, attacker) -> bool:
    """He hasn't seen you coming: not properly aware of you (stealth.notice), or asleep, or out cold."""
    if not target.active:
        return False
    if target.body.unconscious > 0:
        return True
    if target.is_player:
        # you: if you can't see him - behind you, in the dark - you never get your hands up
        from .senses import player_can_see_actor
        return not player_can_see_actor(game, attacker)
    lvl, last = target.ai.get("aware", {}).get(attacker.id, (0.0, -999))
    if lvl >= 1.0 and game.turn - last <= 4:
        return False
    # not yet aware of you - but a man looking your way, awake, in any light, sees you step up to him
    looking_away = _from_behind(target, attacker) or target.fired_turn >= game.turn - 1
    return looking_away or bool(game.is_dark)


def _from_behind(target, attacker) -> bool:
    return attacker.x != target.x and (attacker.x - target.x) * getattr(target, "face", 1) < 0


def _strength(a) -> float:
    from .skills import level
    s = 0.8 + level(a, "fitness") * 0.03 + (0.2 if "strong" in a.traits else 0)
    s *= 0.6 + 0.4 * min(1.0, getattr(a, "stamina", 100) / 60.0)          # blown men hit like children
    return s


def _arms_ok(a) -> float:
    b = a.body
    return max(0.3, min(b.hp["l_arm"] / b.max["l_arm"], 1.0) * 0.4 + min(b.hp["r_arm"] / b.max["r_arm"], 1.0) * 0.6)


def _fighting(a) -> float:
    """His skill at it, as it is now: training, wounds, wind, nerves."""
    from .skills import level
    s = level(a, "melee") + (1.5 if "brawler" in a.traits else 0)
    s *= _arms_ok(a)
    s -= a.suppression / 40
    if a.body.stunned:
        s -= 3
    return s


def odds(game, a, target, move) -> float:
    """Roughly how likely the move is to come off (for the menu's words; the dice decide)."""
    return _land_chance(game, a, target, move)


def _land_chance(game, a, target, move):
    if move in ("silent", "strangle"):
        return 0.92 if surprised(game, target, a) else 0.1
    if target.downed or not target.active or target.body.unconscious > 0:
        return 0.95
    att, dfn = _fighting(a), _fighting(target)
    ch = 0.62 + (att - dfn) * 0.05
    wk, _d, _n = _weapon(a)
    tk, _d2, _n2 = _weapon(target)
    reach = {"bayonet": 2, "blade": 1, "spade": 1, "rifle": 1, "knife": 0, "pistol": 0, "hands": 0}
    if move not in ("grab", "choke", "throw", "break", "stab") or grappling(game, a) is not target:
        ch += (reach.get(wk, 0) - reach.get(tk, 0)) * 0.05
    if target.stance == 2:
        ch += 0.12                                      # stabbing down at a man on the ground
    if a.stance == 2 and target.stance < 2:
        ch -= 0.15
    others = sum(1 for o in game.actors if o is not a and o.side == a.side and o.active and not o.downed and
                 max(abs(o.x - target.x), abs(o.y - target.y)) <= 1)
    ch += 0.1 * min(2, others)                          # two on one
    if surprised(game, target, a):
        ch += 0.3
    if move == "grab":
        ch += (_strength(a) - _strength(target)) * 0.3
    if move == "disarm":
        ch -= 0.12
    if move == "shove":
        ch += 0.1 + (_strength(a) - _strength(target)) * 0.3
    return max(0.05, min(0.97, ch))


def _say(game, a, target, text, cat="combat"):
    """The blow, told to the player if it's his fight or he can see it."""
    if a.is_player or target.is_player:
        game.msg(cap(text), "hurt" if target.is_player else "combat")
    elif game.can_see(a.x, a.y) or game.can_see(target.x, target.y):
        game.msg(cap(text), cat, target.pos)


def _noise(game, a, loud=30, what="a scream and the sound of hand-to-hand fighting"):
    game.emit_sound(a.x, a.y, loud, "melee", what, a.side, a)


def _wound_words(game, target, part, kind, dmg, from_behind):
    rng = game.rng
    spots = BEHIND.get(part) if from_behind and part in BEHIND else WHERE[part]
    where = rng.choice(spots)
    frac = dmg / max(1, target.body.max[part])
    how = next(w for top, w in HOW["blunt" if kind == "blunt" else "cut"] if frac < top)
    return where, how


# ---------------------------------------------------------------- the blow
def attack(game, a, target, move=None) -> int:
    from .conduct import attack as evidence
    with evidence(game, a, target.pos, target):
        return _attack(game, a, target, move)


def _attack(game, a, target, move=None):
    """One exchange.  Returns the time it took (moves)."""
    from .actions import face
    face(a, target.x)
    rng = game.rng
    opts = moves_for(game, a, target)
    if move is None or move not in opts:
        move = choose(game, a, target, opts)
    mv = MOVES[move]
    cost = mv["cost"]
    use_skill(game, a, 2 if move != "shove" else 1)
    a.ai["melee_turn"] = game.turn
    target.ai["melee_turn"] = game.turn
    if a.ai.get("stuck_in"):
        return _free_blade(game, a)
    a.stamina = max(0.0, getattr(a, "stamina", 100) - 2.5)
    if move in ("silent", "strangle"):
        return _silent(game, a, target, move, cost)
    if move in ("choke", "throw", "break") or (move == "stab" and grappling(game, a) is target):
        return _grapple_move(game, a, target, move, cost)
    ch = _land_chance(game, a, target, move)
    if rng.random() >= ch:
        _defended(game, a, target, move)
        _noise(game, a, 25, "grunting and the clatter of a fight hand to hand")
        return cost
    if move == "grab":
        a.ai["grapple"] = target.id
        target.ai["grapple"] = a.id
        _say(game, a, target, f"{_who(game, a)} {'grab' if a.is_player else 'grabs'} {_who(game, target)} - "
                              f"you're locked together, clawing." if a.is_player or target.is_player else
             f"{_who(game, a)} and {_who(game, target)} go down in a clinch.")
        return cost
    if move == "disarm":
        w = target.weapon
        if w is not None:
            from .actions import drop
            drop(game, target, w)
            _say(game, a, target, f"{_who(game, a)} {'knock' if a.is_player else 'knocks'} the {w.t.name} out of "
                                  f"{_whose(game, target)} hands!")
        return cost
    if move == "shove":
        dx, dy = target.x - a.x, target.y - a.y
        nx, ny = target.x + dx, target.y + dy
        m = game.map
        if m.in_bounds(nx, ny) and m.walk[nx, ny] and (nx, ny) not in game.soldier_at and (nx, ny) not in game.vehicle_at:
            game.soldier_at.pop((target.x, target.y), None)
            target.x, target.y = nx, ny
            game.soldier_at[(nx, ny)] = target
            game.note_move(target)
        if rng.random() < 0.35:
            target.stance = 2
            target.body.stunned = max(target.body.stunned, 1)
        _say(game, a, target, f"{_who(game, a)} {'shove' if a.is_player else 'shoves'} {_who(game, target)} "
                              f"back{' - he goes sprawling' if target.stance == 2 else ''}.")
        return cost
    return _land(game, a, target, move, cost)


def _land(game, a, target, move, cost, mult=1.0, part=None):
    rng = game.rng
    mv = MOVES[move]
    wk, base, wname = _weapon(a)
    if move == "stab" and wk != "knife":
        k = _knife(a)
        base, wname = (k.t.dmg * k.condition, k.t.name) if k is not None else (base, wname)
    if move == "butt":
        base, wname = BUTT, "rifle butt"
    if move in ("punch", "throw"):
        base, wname = FIST, "fists" if move == "punch" else "the ground"
    parts = mv["parts"]
    if part is None:
        part = rng.choices(list(parts), list(parts.values()))[0]
    behind = _from_behind(target, a)
    dmg = base * mv["mult"] * mult * _strength(a) * rng.uniform(0.75, 1.3)
    kind = mv["kind"]
    helmet = part == "head" and target.helmet is not None and kind in ("blunt", "cut") and rng.random() < 0.55
    if helmet:
        dmg *= 0.3
    where, how = _wound_words(game, target, part, kind, dmg, behind)
    verb_you, verb = {
        "thrust": ("drive your bayonet into", "drives a bayonet into"),
        "butt": ("smash your rifle butt into", "smashes a rifle butt into"),
        "slash": (f"slash your {wname} across", f"slashes a {wname} across"),
        "chop": ("bring the spade down on", "brings a spade down on"),
        "stab": (f"stab your {wname} into", f"stabs a {wname} into"),
        "punch": ("punch", "punches"),
        "throw": ("slam", "slams"),
    }[move]
    victim = "your" if target.is_player else _whose(game, target)
    if move == "throw":
        text = f"{_who(game, a)} {verb_you if a.is_player else verb} {_who(game, target)} down into the dirt"
    elif helmet:
        text = f"{_who(game, a)} {verb_you if a.is_player else verb} {victim} head - it rings off the helmet"
    else:
        text = f"{_who(game, a)} {verb_you if a.is_player else verb} {victim} {where} - {how}"
    if target.is_player:
        # you hear it before you know what it did (and before "You die...", if that's what it did)
        _say(game, a, target, text + ("." if helmet else "!"))
    res = _hit(game, target, dmg, kind, a, wname, part)
    if target.is_player:
        if res is not None and not res.get("dead"):
            if res.get("knocked_out"):
                game.msg("The world goes white...", "hurt")
            elif res.get("disabled"):
                game.msg(f"Your {PART_WORD[part]} won't work any more.", "hurt")
        text = None
    tail = ""
    if res is not None and text is not None:
        if res.get("dead"):
            tail = {"thrust": ". He folds over the blade.", "stab": ". He sags, and is still.",
                    "butt": ". He drops without a sound.", "chop": ". He goes down and doesn't move.",
                    "slash": ". He falls.", "punch": ". He doesn't get up.", "throw": ". He doesn't get up."}.get(move, ".")
            if target.is_player:
                tail = "."
        elif res.get("knocked_out"):
            tail = ". He goes limp." if not target.is_player else ". The world goes white."
        elif res.get("disabled"):
            tail = f". The {where.split()[-1]} hangs useless." if part not in ("head", "torso") else "!"
        else:
            tail = "!"
    if text is not None:
        _say(game, a, target, text + tail)
    if kind == "blunt" and part == "head" and res is not None and not res.get("dead"):
        target.body.stunned = max(target.body.stunned, rng.randint(1, 3 if not helmet else 1))
        if rng.random() < (0.3 if not helmet else 0.1):
            target.stance = 2                                 # knocked flat
    if move == "throw":
        target.stance = 2
        target.body.stunned = max(target.body.stunned, 2)
        _release(a, target)
    # a bayonet in deep can stick - between ribs, in webbing - and has to be wrenched out
    if move == "thrust" and part == "torso" and res is not None and not res.get("dead") and dmg > 20 and \
            rng.random() < 0.18:
        a.ai["stuck_in"] = target.id
        _say(game, a, target, "The bayonet sticks fast." if not a.is_player else
             "Your bayonet sticks fast in him - wrench it free!")
    _noise(game, a, 32 if res and res.get("dead") else 30)
    return cost


PART_WORD = {"head": "head", "torso": "body", "l_arm": "left arm", "r_arm": "right arm", "l_leg": "left leg",
             "r_leg": "right leg"}


def _hit(game, target, dmg, kind, a, wname, part):
    """The wound (combat.hit_actor), with the usual "You kill..." left to our own words."""
    from .combat import hit_actor
    game.__dict__["_quiet_kill"] = True
    target.body.__dict__["melee_death"] = True        # (if this is what kills him: 'at the hands of', not 'fired by')
    try:
        return hit_actor(game, target, dmg, kind, a, wname, part=part, silent=True)
    finally:
        game.__dict__["_quiet_kill"] = False
        if target.alive:
            target.body.__dict__.pop("melee_death", None)


def _defended(game, a, target, move):
    """The blow didn't land: how he stopped it."""
    rng = game.rng
    tk, _d, _n = _weapon(target)
    if move in ("grab",):
        text = f"{_who(game, target)} {'twist' if target.is_player else 'twists'} out of {_whose(game, a)} grip."
    elif move == "disarm":
        text = f"{_who(game, target)} {'keep' if target.is_player else 'keeps'} hold of {'your' if target.is_player else 'his'} weapon."
    elif move == "shove":
        text = f"{_who(game, target)} {'stand' if target.is_player else 'stands'} {'your' if target.is_player else 'his'} ground."
    elif tk in ("bayonet", "rifle") and rng.random() < 0.6:
        text = f"{_who(game, target)} {'parry' if target.is_player else 'parries'} with {'your' if target.is_player else 'his'} rifle."
    elif tk in ("blade", "spade", "knife") and rng.random() < 0.5:
        text = f"{_who(game, target)} {'turn' if target.is_player else 'turns'} the blow with {'your' if target.is_player else 'his'} {_n}."
    elif move in ("slash", "chop", "punch", "butt") and rng.random() < 0.3:
        # an arm thrown up: the blow lands, softened, on the arm
        _land(game, a, target, move, 0, mult=0.45, part=rng.choice(("l_arm", "r_arm")))
        return
    elif target.is_player:
        text = f"You twist aside - {_who(game, a)} misses."
    elif a.is_player:
        text = f"{_who(game, target)} twists aside - you miss."
    else:
        text = f"{_who(game, target)} twists aside."
    _say(game, a, target, text)


def _free_blade(game, a):
    tid = a.ai.pop("stuck_in", None)
    t = next((o for o in game.actors if o.id == tid), None)
    if t is not None and t.alive and game.rng.random() < 0.5:
        from .combat import hit_actor
        hit_actor(game, t, 6, "cut", a, "bayonet", part="torso", silent=True)
    if a.is_player:
        game.msg("You wrench the bayonet free.", "combat")
    return 120


def _grapple_move(game, a, target, move, cost):
    rng = game.rng
    att, dfn = _fighting(a) + _strength(a) * 3, _fighting(target) + _strength(target) * 3
    ch = max(0.1, min(0.9, 0.5 + (att - dfn) * 0.04))
    if move == "break":
        if rng.random() < ch + 0.2:
            _release(a, target)
            _say(game, a, target, f"{_who(game, a)} {'tear' if a.is_player else 'tears'} free.")
        else:
            _say(game, a, target, f"{_who(game, target)} {'hang' if target.is_player else 'hangs'} on.")
        return cost
    if rng.random() >= ch:
        _say(game, a, target, f"{_who(game, a)} and {_who(game, target)} roll in the dirt, neither getting the "
                              f"better of it.")
        return cost
    if move == "stab":
        return _land(game, a, target, "stab", cost, mult=1.2)
    if move == "throw":
        return _land(game, a, target, "throw", cost)
    # choke: a few seconds and he's out; held on, he's dead
    n = target.ai.get("choked", 0) + 1
    target.ai["choked"] = n
    if n >= 3:
        target.body.unconscious = max(target.body.unconscious, rng.randint(60, 180))
        target.stance = 2
        _release(a, target)
        _say(game, a, target, f"{_who(game, target)} {'go' if target.is_player else 'goes'} limp in "
                              f"{_whose(game, a)} hands." if not target.is_player else "The world narrows to a "
                                                                                      "grey tunnel, and goes out.")
    else:
        _say(game, a, target, f"{_who(game, a)} {'get' if a.is_player else 'gets'} "
                              f"{'your' if a.is_player else 'his'} hands round {_whose(game, target)} throat.")
    return cost


def _silent(game, a, target, move, cost):
    """From behind, unseen: a hand over the mouth and a knife, or an arm round the neck."""
    rng = game.rng
    if rng.random() >= _land_chance(game, a, target, move):
        _say(game, a, target, f"{_who(game, target)} {'twist' if target.is_player else 'twists'} round at the last "
                              f"instant!")
        target.ai.setdefault("aware", {})[a.id] = (1.0, game.turn)
        a.ai["grapple"] = target.id
        target.ai["grapple"] = a.id
        _noise(game, a, 35, "a shout, cut off, and a struggle")
        return cost
    if move == "silent":
        k = _knife(a) or a.weapon
        dmg = (k.t.dmg * k.condition if k is not None and k.t.kind == "melee" else FIST) * MOVES["silent"]["mult"] * rng.uniform(0.9, 1.3)
        part = rng.choice(["torso", "head"])
        where = rng.choice(BEHIND[part])
        res = _hit(game, target, dmg, "cut", a, k.t.name if k is not None else "knife", part)
        dead = bool(res and res.get("dead"))
        if not dead and target.alive:
            target.body.unconscious = max(target.body.unconscious, rng.randint(30, 120))
        _say(game, a, target, (f"You clamp a hand over {_whose(game, target)} mouth and drive the "
                               f"{k.t.name if k is not None else 'knife'} into his {where}." if a.is_player else
                               f"{_who(game, a)} rises behind {_who(game, target)} - a hand over the mouth, a knife "
                               f"in the {where}.") + (" He sags without a sound." if dead else " He sags."))
    else:
        target.body.unconscious = max(target.body.unconscious, rng.randint(90, 240))
        target.stance = 2
        _say(game, a, target, f"You get an arm round {_whose(game, target)} neck from behind and hold on while he "
                              f"kicks. Then he's still." if a.is_player else
             f"{_who(game, a)} takes {_who(game, target)} from behind, an arm round the neck. He goes limp.")
    use_skill(game, a, 4, "stealth")
    _noise(game, a, 8, "a scuffle, very quiet")
    return cost


# ---------------------------------------------------------------- choosing
def choose(game, a, target, opts=None) -> str:
    """The obvious move: silent if he hasn't seen you and you can; in a clinch, the knife or the throat; else
    whatever's in your hands - and a man with an empty rifle and a stronger enemy may just grab."""
    opts = opts or moves_for(game, a, target)
    rng = game.rng
    if "silent" in opts:
        return "silent"
    if "strangle" in opts:
        return "strangle"
    if grappling(game, a) is target:
        if "stab" in opts:
            return "stab"
        return "choke" if _strength(a) >= _strength(target) else ("throw" if rng.random() < 0.5 else "break")
    first = next((m for m in opts if m not in ("silent", "strangle")), "punch")
    if not a.is_player:
        # a man with only his fists and the bigger build goes for a hold; now and then one goes for the weapon
        if first == "punch" and _strength(a) > _strength(target) and rng.random() < 0.4:
            return "grab"
        if "disarm" in opts and rng.random() < 0.08:
            return "disarm"
    return first


def use_skill(game, a, amount, k="melee"):
    from .skills import use
    use(game, a, k, amount)


def odds_word(p) -> str:
    return ("almost certain" if p > 0.9 else "good odds" if p > 0.7 else "even odds" if p > 0.45 else
            "poor odds" if p > 0.25 else "long odds")
