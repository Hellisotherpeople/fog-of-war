"""Two ways of not being one man: the autopilot, and carrying on in someone else's boots.

Autopilot (A): your soldier does what his training and his orders tell him - the same soldier AI every man on
the field runs - while you watch, and A (or Esc) gives him back to you.  If you lead a squad, it takes its orders
from the chain of command while you're not giving them; if you crew a vehicle, the crew fights it.

Succession (Options, WHEN YOU DIE): when you die the battle doesn't end.  The war goes on - the same field, the same
men, the dead where they fell - and you're someone else, chosen by the rule you set:
  squad    - a man of your own squad (then your unit, then anyone near)
  unit     - a man of your company, platoon or battery
  nearest  - whoever's nearest on your side
  role     - the nearest man doing the job you did
  rank     - the most senior man near (command falls to him anyway)
  random   - anyone on your side on this field
  killer   - the man who killed you (the other side: you'll be him)
and on which side ("own" or "any": any lets the random and nearest rules cross the line), with or without a
limit on lives, or ask - a list of candidates to choose from.  The fallen go in the memorial as always.
"""
from __future__ import annotations

import math

RULES = ("squad", "unit", "nearest", "role", "rank", "random", "killer")
RULE_WORD = {"squad": "a man of your own squad", "unit": "a man of your unit", "nearest": "whoever's nearest",
             "role": "the nearest man in your job", "rank": "the most senior man near", "random": "anyone on the field",
             "killer": "the man who killed you"}


# ============================================================================ autopilot
def autopilot_on(game) -> bool:
    return bool(game.__dict__.get("autopilot"))


def set_autopilot(game, on):
    """Hand your soldier over to his training (or take him back)."""
    p = game.player
    if on == autopilot_on(game):
        return
    if on:
        keep = {}
        sq = p.squad
        if sq is not None and sq.player_led:
            from .ai import Order
            keep["led"] = sq.id
            keep["order"] = sq.order
            sq.player_led = False                      # the chain of command gives the section its orders now
            if sq.order.kind == "follow" or getattr(sq.order, "src", "ai") == "player":
                sq.order = Order("hold", target=(p.x, p.y), radius=6, issued=game.turn)
                from .commander import commander_update
                commander_update(game, p.side)
        v = p.vehicle
        if v is not None and v.player_crewed:
            keep["veh"] = (v.id, v.player_station)
            v.player_crewed = False                    # the crew drives and fights it
        game.autopilot = keep or True
        game.msg("You let your training take over. (A or Esc: take control again)", "info")
    else:
        keep = game.__dict__.get("autopilot")
        game.autopilot = False
        if isinstance(keep, dict):
            sq = p.squad
            if sq is not None and keep.get("led") == sq.id and sq.leader is p:
                sq.player_led = True
                from .ai import Order
                old = keep.get("order")
                if old is not None and old.kind not in ("follow",) and getattr(old, "src", "ai") == "player":
                    old.issued = game.turn
                    sq.order = old                     # the order you'd given them before you let go
                else:
                    sq.order = Order("follow", issued=game.turn, src="player")
            if keep.get("veh") and p.vehicle is not None and p.vehicle.id == keep["veh"][0]:
                p.vehicle.player_crewed = True
                p.vehicle.player_station = keep["veh"][1]
        game.msg("You take control again.", "info")


# ============================================================================ succession
def enabled(settings) -> bool:
    return settings.get("succession", "off") != "off"


def candidates(game, dead, rule, side_rule="own", killer=None, limit=12) -> list:
    """Who could carry on, best first, by the rule (the rule's own choice, then sensible fall-backs)."""
    alive = [a for a in game.actors if a.alive and a is not dead and a.state == "ok" and not a.body.dead
             and a.body.conscious]
    own = [a for a in alive if a.side == dead.side]
    pool = own if side_rule == "own" or not alive else alive
    if not pool:
        pool = alive if side_rule != "own" else []
    if not pool:
        return []

    def d(a):
        return math.hypot(a.x - dead.x, a.y - dead.y)
    unit = getattr(dead.squad, "formation", None) if dead.squad is not None else None
    if rule == "killer" and killer is not None and getattr(killer, "alive", False) and hasattr(killer, "body"):
        first = [killer]
    elif rule == "killer" and killer is not None and getattr(killer, "vt", None) is not None:
        first = [a for a in killer.crew_actors if a.alive] or [a for a in alive if a.vehicle is killer]
    elif rule == "squad":
        first = sorted([a for a in pool if a.squad is dead.squad], key=d)
    elif rule == "unit":
        first = sorted([a for a in pool if a.squad is not None and getattr(a.squad, "formation", None) is unit
                        and unit is not None], key=d)
    elif rule == "role":
        first = sorted([a for a in pool if a.role == dead.role], key=d)
    elif rule == "rank":
        first = sorted([a for a in pool if d(a) < 60], key=lambda a: (-a.rank, d(a)))
    elif rule == "random":
        first = list(pool)
        game.rng.shuffle(first)
    else:
        first = sorted(pool, key=d)
    rest = sorted([a for a in pool if a not in first], key=lambda a: (a.squad is not dead.squad, d(a)))
    return (first + rest)[:limit]


def take_over(game, new, why=""):
    """You are now `new`: his body, his kit, his rank, his unit, his standing (none, yet)."""
    from .ai import Order
    from .duty import Duty
    old = game.player
    game.autopilot = False                        # (a new man, with his own hands on him)
    osq = old.squad
    if osq is not None and osq.player_led and not (new.squad is osq and osq.leader is new):
        osq.player_led = False                    # the section you led goes back to the chain of command
        if osq.order.kind == "follow" or getattr(osq.order, "src", "ai") == "player":
            osq.order = Order("hold", target=(old.x, old.y), radius=6, issued=game.turn)
    old.is_player = False
    new.is_player = True
    game.player = new
    game.player_nation = new.nation
    game.player_side = new.side
    game.game_over = False
    game.death_text = None
    # a new man: nobody knows him yet, and his record starts here
    game.duty = Duty()
    cmd = game.command
    cmd.merit = cmd.merit_at_promotion = 0.0
    cmd.medals = []
    cmd.promotions = []
    cmd.battle = {"kills": 0, "objectives": 0, "acting": 0, "wounds": 0, "orders": 0}
    cmd.__dict__.pop("record", None)
    game.__dict__.pop("base_order", None)
    game.__dict__.pop("order_focus", None)
    # and none of the dead man's troubles: his own side hunting him, the warrant, the missed ship
    game.renegade = False
    for k in ("wanted", "awol", "ship_ashore"):
        game.__dict__.pop(k, None)
    for a in game.actors:
        a.ai.pop("op", None)                      # (what they thought of him isn't what they think of you)
    game.__dict__.pop("mission", None) if game.__dict__.get("mission") and \
        game.mission.get("kind") in ("agent", "raid", "patrol", "sniper") else None
    sq = new.squad
    if sq is not None and sq.leader is new and not sq.player_led:
        sq.player_led = True
        sq.order = Order("follow", issued=game.turn, src="player")
    try:
        cmd.organise(game)
    except Exception:
        import os
        if os.environ.get("FOW_DEBUG"):
            raise
    new.moves = max(new.moves, 100)
    lives = game.__dict__.setdefault("lives", [])
    lives.append(dict(name=old.name, rank=old.rank_full, fell=game.turn))
    side_word = "" if new.side == old.side else " - on the other side of the line"
    game.msg(f"{why}You are {new.rank_full} {new.name}, {new.role_name.lower()}, {new.unit}{side_word}. "
             f"The war goes on.", "good")
    game.update_orders(force=True)
    game.player_fov()


def on_death(game, settings, killer=None) -> bool:
    """Called as the player dies.  True if someone carries on (and the game isn't over)."""
    if not enabled(settings):
        return False
    lives = len(game.__dict__.get("lives", []))
    cap = int(settings.get("succession_lives", 0) or 0)
    if cap and lives >= cap:
        return False
    dead = game.player
    cands = candidates(game, dead, settings.get("succession_rule", "squad"), settings.get("succession_side", "own"),
                       killer)
    if not cands:
        return False
    if settings.get("succession") == "choose":
        game.__dict__["succession_pending"] = [a.id for a in cands]
        return True
    take_over(game, cands[0], "")
    return True


def pending(game):
    ids = game.__dict__.get("succession_pending")
    if not ids:
        return []
    return [a for a in game.actors if a.id in ids and a.alive]


def choose(game, actor):
    old = game.player
    game.__dict__.pop("succession_pending", None)
    take_over(game, actor, "")
    if not old.alive:
        game.body_falls(old, None)                # (the man you were: one of the war's dead now)
