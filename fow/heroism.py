"""Seeing a man be brave, and seeing one quit.

A section is not steered only by orders.  The man who stands up and fires into them at ten yards, or
goes out under the machine gun to drag a mate in, steadies everybody who can see it.  The man who
throws his rifle down and runs does the opposite.  The worst is an officer: a lieutenant on his knees
with his hands up tells the whole line what the morning has come to.

Effects are deliberately local and short.  Heroism moves the men who saw it; it is not a buff for the
army.  Cowardice spreads about as far as a shout carries.  An officer's surrender reaches further,
takes the leaders with it, and delays the orders that were travelling.
"""
from __future__ import annotations

HERO_RANGE = 16
COWARD_RANGE = 22
OFFICER_RANGE = 45
COOLDOWN = 50


def _key(game, kind):
    return f"{kind}"


def _seen(game, actor, kind) -> bool:
    last = game.__dict__.setdefault("_renown_at", {})
    sid = (actor.side, actor.squad.id if actor.squad is not None else 0)
    if game.turn - last.get(sid, -999) < COOLDOWN:
        return False
    last[sid] = game.turn
    return True


def _friends(game, actor, radius):
    p = game.player
    out = []
    for a in game.near(actor.x, actor.y, radius, actor.side):
        if a is actor or not a.active or a.downed or a.vehicle is not None:
            continue
        if game.map.visible[a.x, a.y] or (p is not None and max(abs(a.x - p.x), abs(a.y - p.y)) <= 20):
            out.append(a)
    return out


def _say_if_player(game, actor, text):
    p = game.player
    if p is not None and p.side == actor.side and max(abs(actor.x - p.x), abs(actor.y - p.y)) <= 20:
        game.msg(text, "good")


def brave(game, actor, kind, target=None):
    """One of the small things that holds a line together."""
    if actor is None or not actor.active or actor.vehicle is not None:
        return
    if not _seen(game, actor, kind):
        return
    friends = _friends(game, actor, HERO_RANGE)
    scale = {"kill_close": 1.0, "charge": 1.3, "rescue": 1.6, "hold": 0.7, "stand": 1.1}.get(kind, 1.0)
    for f in friends:
        f.morale = min(100.0, f.morale + 4 * scale)
        f.suppression = max(0.0, f.suppression - 6 * scale)
    lead = actor.squad.leader if actor.squad is not None else None
    if lead is not None and lead is not actor and lead.active and game.rng.random() < 0.55:
        line = {"kill_close": "Good shooting! Keep at 'em!",
                "charge": "That's it! With him!",
                "rescue": "Get him in - cover them!",
                "hold": "Hold there! Steady!",
                "stand": "Stand to! Nobody moves!"}.get(kind)
        if line:
            lead.say(line, game.turn, 4)
    if kind in ("rescue", "charge", "kill_close"):
        p = game.player
        own = {"kill_close": f"{actor.rank_short} {actor.last_name} drops one at close range and stays up. "
                             f"The men round him steady.",
               "rescue": f"{actor.rank_short} {actor.last_name} goes out under fire. The section steadies "
                         f"and the fire comes back on it.",
               "charge": f"{actor.rank_short} {actor.last_name} takes the lead in. The line follows."}[kind]
        foe = {"kill_close": f"An enemy {actor.role_name.lower()} drops one of ours at close range and "
                             f"does not get down. Their line steadies.",
               "rescue": f"An enemy {actor.role_name.lower()} goes out under the fire. Their line steadies.",
               "charge": f"An enemy {actor.role_name.lower()} leads a rush in. Their line follows."}[kind]
        if p is not None and p.side != actor.side and game.can_see(actor.x, actor.y) and \
                max(abs(actor.x - p.x), abs(actor.y - p.y)) <= 22:
            game.msg(foe, "info")
        else:
            _say_if_player(game, actor, own)
    if game.player is not None and actor is game.player:
        from .skills import use
        use(game, actor, "leadership", 0.15)


def cowardly(game, actor, kind="break"):
    """A man packs it in where others can see."""
    if actor is None or actor.vehicle is not None:
        return
    if not _seen(game, actor, kind):
        return
    for f in _friends(game, actor, COWARD_RANGE):
        f.morale = max(0.0, f.morale - 4.5)
        f.suppression = min(100.0, f.suppression + 4)
    _say_if_player(game, actor, f"{actor.rank_short} {actor.last_name} throws his rifle down and runs. "
                                f"Somebody near you follows him with his eyes.")


def officer_surrenders(game, actor):
    """A commander with his hands up: the line tells itself the day is lost."""
    from .data.ranks import LT2
    if actor.command_grade < LT2 and actor.rank < LT2:
        brave(game, actor, "stand")             # a private surrendering is one man's war ending
        return
    for f in _friends(game, actor, OFFICER_RANGE):
        f.morale = max(0.0, f.morale - 11)
        f.suppression = min(100.0, f.suppression + 8)
    # the orders that were still travelling lose their author's certainty
    cmd = getattr(game, "command", None)
    if cmd is not None:
        for job in cmd.pending:
            if job.get("sq") in {s.id for s in (actor.squad,) if s is not None}:
                job["due"] += 25
    if actor.squad is not None:
        for m in actor.squad.members:
            if m is not actor and m.active and m.ai.get("resolve", -99) < game.turn - 40:
                m.ai["resolve"] = game.turn
                m.ai["cohesion_hit"] = game.turn + 120
    if game.player is not None and game.player.side == actor.side:
        game.msg(f"{actor.rank_full} {actor.last_name} has his hands up. Men along the line are looking "
                 f"at him instead of their front.", "warn")
        if actor.is_player:
            game.duty.rep -= 12
    # sections nearby lose the thread of what they were doing until a leader picks it up again
    for sq in game.squads:
        if sq.side != actor.side or sq.gone or sq.player_led or sq.leader is None:
            continue
        anc = sq.anchor()
        if anc is None or max(abs(anc[0] - actor.x), abs(anc[1] - actor.y)) > 30:
            continue
        if sq.morale < 35 and game.rng.random() < 0.35:
            sq.rep["shaken"] = game.turn + 90
            sq.order.kind = "hold"
            sq.order.target = anc
            sq.state = "hold"
            sq.arrived = True
            sq.positions = {}
            if sq.leader.active and not sq.leader.is_player and game.rng.random() < 0.5:
                sq.leader.say(game.shout(sq.leader, "retreat") if sq.morale < 20 else "Hold here!", game.turn)
    # a side that loses a commander loses a little of its map
    brain = game.brains.get(actor.side)
    if brain is not None:
        recent = [k for k, c in brain.contacts.items() if c.ref is not None and getattr(c.ref, "is_player", False)]
        for k in recent[:20]:
            brain.contacts.pop(k, None)
