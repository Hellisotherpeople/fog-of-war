"""The order doesn't arrive as clean as it left.

A chain of command is made of people.  A leader hears the order, looks at the ground, his men and his
ammunition, and answers: 'yes, sir', 'say again', 'we're low - we'll fire and move', or 'not across that'.
A good, trusted leader with latitude improvises a better way and tells you so.  A frightened one may balk,
and needs telling twice.

This is reception, not command: it changes how a player's order lands, never whether the simulation obeys
it.  The order can be shifted by a misheard range, narrowed to a covered line, turned into fire and
movement, or delayed by an argument.  Every officer in the game can be good or bad at this; the player's
own standing and the army's school decide how much latitude they take.
"""
from __future__ import annotations

import math

from .data.phrases import lang, phrase

INDEPENDENT = {"germany": 0.9, "finland": 0.8, "usa": 0.5, "uk": 0.45, "canada": 0.5, "australia": 0.6,
               "newzealand": 0.6, "france": 0.4, "poland": 0.45, "ussr": 0.35, "italy": 0.3,
               "japan": 0.35, "hungary": 0.35, "romania": 0.3, "china": 0.3}
SUGGEST = {
    "usa": ["We're low on rounds - let us fire and move.", "That's open ground. Put us in by bounds.",
            "Give us the hedge line and we'll work up it."],
    "uk": ["We're short. Fire and movement, if you want it done.", "It's open there. Bounds, sir."],
    "germany": ["We're low. Feuer und Bewegung - we'll go by bounds.", "Too much open ground. Let us work round "
                "the flank.", "Give us a fire base and we'll take it."],
    "ussr": ["Rounds are low. We'll go by bounds.", "The open will eat us. Let us go round."],
    "japan": ["We'll go in by bounds and finish with the bayonet.", "Too open. Let us work round."],
    "italy": ["We're short of rounds. Fire and movement, eh?", "It's too open. Let us go round."],
    "france": ["We're low. Feu et mouvement.", "Too open. By bounds."],
    "finland": ["We're low. We'll go round the flank.", "Open ground. Bounds."],
}
BALK = {
    "usa": ["We can't go across that. There's a company of them.", "Not with what we've got. Say it again?"],
    "uk": ["That's too much for us. Insist and we'll try.", "We'll be cut up. Say it again and we'll go."],
    "germany": ["Too strong for us. Say it again and we'll go.", "That's a battalion. Insist, sir."],
    "ussr": ["We haven't the men. Say it again.", "They're too many. Insist and we go."],
    "japan": ["Too many. Say it again and we go.", "We'll go if you insist."],
}


def _skill(game, ld) -> float:
    from .skills import level
    return min(5.0, (getattr(ld, "command_grade", 2) * 0.45) + level(ld, "leadership") * 0.55)


def _near_enemy(game, sq):
    anc = sq.anchor()
    if anc is None:
        return 0
    n = 0
    for a in game.near(anc[0], anc[1], 26):
        if a.side != sq.side and a.alive and a.state == "ok" and not a.downed:
            n += 1
    for v in game.vehicles:
        if v.side != sq.side and v.active and math.hypot(v.x - anc[0], v.y - anc[1]) <= 26:
            n += 2
    return n


def _cover_toward(game, sq):
    """A nearby piece of ground the section can work up to instead of the open."""
    anc = sq.anchor()
    if anc is None:
        return None
    best = None
    m = game.map
    for dx in range(-8, 9):
        for dy in range(-8, 9):
            x, y = anc[0] + dx, anc[1] + dy
            if not m.in_bounds(x, y) or not m.walk[x, y] or m.pos_cover[x, y] < 45:
                continue
            d = abs(dx) + abs(dy)
            if best is None or d < best[0]:
                best = (d, x, y)
    return None if best is None else best[1:]


def receive(game, sq, job) -> bool:
    """React to an incoming player order, mutating it where a good leader would. False: refused."""
    from .people import opinion
    ld = None
    for m in sq.members:
        if m is sq.leader:
            ld = m
            break
    if ld is None or ld.is_player:
        return True
    kind = job.get("kind")
    if kind not in ("move", "attack", "assault", "flank", "defend", "hold", "ambush", "retreat", "regroup", "rally",
                    "follow", "suppress"):
        return True
    rng = game.rng
    p = game.player
    ch = job.get("channel")
    anc = sq.anchor()
    if anc is None:
        return True
    px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
    dist = max(abs(anc[0] - px), abs(anc[1] - py))
    competence = _skill(game, ld)
    trust = max(-1.0, min(1.0, opinion(game, ld) / 100.0))
    indep = INDEPENDENT.get(ld.nation, 0.4)
    strain = max(0.0, (1 - sq.morale / 100) * 0.6 + ld.suppression / 150)
    noise = game.noise / 100.0
    # 1. it comes through wrong
    garb = 0.02 + (0.10 if ch in ("radio", "signal", "runner") else 0.0) + noise * 0.10 + \
        (0.10 if dist > 30 else 0.0)
    if kind in ("move", "attack", "assault", "flank") and job.get("order") is not None and \
            job["order"].target is not None and rng.random() < garb:
        ox, oy = job["order"].target
        d = rng.randint(3, 8)
        ang = rng.random() * math.tau
        tx = int(ox + math.cos(ang) * d * 1.6)
        ty = int(oy + math.sin(ang) * d * 1.6)
        if game.map.in_bounds(tx, ty):
            job["order"].target = (tx, ty)
            job["order"].obj = None
            job["friction"] = rng.choice(["Say again? ...Right. On it.", "You're breaking up. We'll go.",
                                          "Repeat the reference. ...We think we have it."])
            job["misheard"] = True
    # 2. not across that
    fat = _near_enemy(game, sq)
    suicidal = kind in ("attack", "assault") and fat > max(4, sq.strength() * 2.4) and \
        sq.morale < 50 and not job.get("_insisted")
    cmd = getattr(game, "command", None)
    last = (cmd.refused.get(sq.id, -999) if cmd is not None else -999)
    if suicidal and game.turn - last > 120 and \
            rng.random() < 0.45 + strain * 0.3 - competence * 0.06 and trust < 0.35:
        job["friction"] = phrase(rng, ld.nation, "balk") if lang(ld.nation) != "en" else \
            rng.choice(BALK.get(ld.nation, BALK["usa"]))
        job["refused"] = True
        if cmd is not None:
            cmd.refused[sq.id] = game.turn
        return False
    # 3. a better way, from a good and trusted leader with rope
    if "friction" not in job and rng.random() < 0.18 + competence * 0.06 + indep * 0.10 + max(0, trust) * 0.08:
        from .command import low_on_ammo
        changed = False
        if kind in ("attack", "assault") and low_on_ammo(sq):
            job["order"].kind = "attack"
            job["order"].mod = dict(getattr(job["order"], "mod", None) or {}, fire=1.25, exposure=1.1,
                                    spread=1.1)
            job["order"].roe = "return"
            changed = True
        if kind in ("attack", "assault") and job["order"].target is not None:
            tx, ty = job["order"].target
            if game.map.in_bounds(tx, ty) and game.map.pos_cover[tx, ty] < 25:
                cover = _cover_toward(game, sq)
                if cover is not None and rng.random() < 0.55:
                    job["order"].mod = dict(getattr(job["order"], "mod", None) or {}, spread=1.2,
                                            exposure=0.9)
                    job["order"].radius = max(4, job["order"].radius - 2)
                    changed = True
        if changed:
            job["friction"] = phrase(rng, ld.nation, "suggest") if lang(ld.nation) != "en" else \
                rng.choice(SUGGEST.get(ld.nation, SUGGEST["usa"]))
            job["improvised"] = True
        return True
    # 4. a question, when it's vague and they're not sure of you
    if "friction" not in job and kind in ("attack", "assault") and job["order"].target is None and \
            rng.random() < 0.3 + (1 - trust) * 0.2:
        job["friction"] = rng.choice(["Where, exactly? ...Right, we have it.", "Which side of the hedge?",
                                      "Confirm the reference?"])
    return True


def reply_key(game, job) -> str | None:
    """Whether the reception replaced the ordinary acknowledgement."""
    return job.get("friction")
