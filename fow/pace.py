"""Walking, running, sprinting - and what it costs.

Breath (stamina) is the short account: spent in a rush, got back in a minute's rest.
Fatigue is the long one: hours of marching, digging and sprinting build it up, and it
lowers the ceiling on your breath until you really rest.  A walking man can shoot,
listen and keep going all day.  A running man covers ground and can't hit anything.
A sprinting man crosses the open in seconds - loud, conspicuous, gasping, and harder to
hit - and after thirty yards of it he's done.

Everyone plays by these rules: you, your squad, the enemy.
"""
from __future__ import annotations

PACES = ("sneak", "walk", "run", "sprint")
COST = {"sneak": 1.9, "walk": 1.0, "run": 0.62, "sprint": 0.45}           # move time
DRAIN = {"sneak": 0.8, "walk": 1.0, "run": 3.5, "sprint": 9.0}             # breath per tile, on top of stance and load
FATIGUE = {"sneak": 0.0005, "walk": 0.0004, "run": 0.004, "sprint": 0.014}  # fatigue per tile
LOUD = {"sneak": 0.35, "walk": 1.0, "run": 1.4, "sprint": 1.8}
WORD = {"sneak": "creeping", "walk": "walking", "run": "running", "sprint": "sprinting"}


def max_breath(a) -> float:
    return 100.0 - 0.6 * getattr(a, "fatigue", 0.0)


def allowed(a, turn=None) -> str:
    """The fastest this man can go right now."""
    b = a.body
    if a.stance == 2 or b.downed() or a.carrying is not None:
        return "walk"
    legs = min(b.hp["l_leg"] / b.max["l_leg"], b.hp["r_leg"] / b.max["r_leg"])
    if legs < 0.35 or b.effective_pain() > 110:
        return "walk"
    if legs < 0.6 or a.stance == 1:
        return "run"                         # a crouching run, or a limp
    w = a.weight_now(turn) if turn is not None else a.carried_weight()
    if w > 32 or getattr(a, "fatigue", 0.0) > 85:
        return "run"
    return "sprint"


def effective(a, want, turn=None) -> str:
    """What he actually manages: no sprinting on empty lungs."""
    order = {"sneak": 0, "walk": 0, "run": 1, "sprint": 2}
    if want == "sneak":
        return "sneak"
    cap = allowed(a, turn)
    pace = want if order[want] <= order[cap] else cap
    st = getattr(a, "stamina", 100.0)
    if pace == "sprint" and st < 15:
        pace = "run"
    if pace == "run" and st < 5:
        pace = "walk"
    return pace


def ai_pace(game, a) -> str:
    """How a soldier moves, from what his squad is doing and how he's holding up."""
    sq = a.squad
    st = getattr(sq, "state", "idle") if sq is not None else "idle"
    want = "walk"
    if st in ("assault", "banzai", "rout"):
        want = "sprint"
    elif st == "bound":
        want = "sprint" if a.suppression < 70 else "run"
    elif st in ("retreat", "flank", "resupply"):
        want = "run"
    elif st in ("advance", "follow", "move", "regroup"):
        ld = sq.leader if sq is not None else None
        if ld is not None and ld is not a and max(abs(ld.x - a.x), abs(ld.y - a.y)) > 7:
            want = "run"                      # catching up
    if (a.role == "medic" and a.ai.get("patient")) or a.ai.get("support_job"):
        want = "run"
    # the stalkers: snipers, scouts, raiders creep when they aren't already in a fight
    if want == "walk" and (a.role in ("sniper", "scout") or (sq is not None and getattr(sq, "kind", "") in
                                                              ("recon", "raid", "commando")) or
                           (sq is not None and sq.order.kind == "ambush")) and \
            (sq is None or game.turn - sq.last_contact > 30):
        want = "sneak"
    if a.suppression > 50 and st not in ("rout", "hold", "idle") and a.stance == 0:
        want = "sprint"                       # get across and get down
    breath = getattr(a, "stamina", 100.0)
    if want == "sprint" and breath < 35 and st not in ("rout", "banzai"):
        want = "run"
    if breath < 15:
        want = "walk"
    if getattr(a, "fatigue", 0.0) > 75 and st not in ("rout", "banzai", "assault"):
        want = "walk"
    return effective(a, want, game.turn)


def pace_of(game, a) -> str:
    if a.is_player:
        return effective(a, getattr(a, "pace", "walk"), game.turn)
    return ai_pace(game, a)


def recent(game, a) -> str:
    """How he was moving a moment ago (for aim, being seen, being hit)."""
    if a.moved_turn < game.turn - 1:
        return "still"
    return a.ai.get("pace_now", "walk")


def aim_penalty(game, a) -> float:
    r = recent(game, a)
    p = {"run": 0.9, "sprint": 2.6}.get(r, 0.0)
    f = getattr(a, "fatigue", 0.0)
    if f > 50:
        p += (f - 50) / 60.0
    return p


def fatigue_word(a):
    f = getattr(a, "fatigue", 0.0)
    if f > 85:
        return "Dead on your feet", (255, 90, 70)
    if f > 65:
        return "Exhausted", (240, 150, 80)
    if f > 40:
        return "Tired", (220, 200, 120)
    return None, None


def speed_mult(a) -> float:
    f = getattr(a, "fatigue", 0.0)
    return 1.0 - max(0.0, f - 60) / 200.0
