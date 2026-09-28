"""Taking prisoners.

A man who throws down his rifle isn't yet a prisoner.  He still has the grenades on his belt,
the pistol in his boot, and his orders in his tunic.  You search him (it takes most of a
minute, and you have to get close); you tell him to follow, to sit, or to walk back to your
lines; you hand him to a comrade who'll take him back; you bring him in yourself for the
credit and for what intelligence gets out of his paybook.

You can demand a surrender, too - in his language, if you know a word of it.  Men who are
broken, cut off, wounded or outnumbered may take the offer.  Men of some armies almost never
do, and a few will raise their hands and then pull the pin.
"""
from __future__ import annotations

import math

from .constants import cap as _cap, other_side

HANDS_UP = {"germany": "Hände hoch!", "ussr": "Ruki vverkh!", "italy": "Mani in alto!", "japan": "Te o agero!",
            "usa": "Hands up!", "uk": "Hands up!", "france": "Haut les mains!", "finland": "Kädet ylös!",
            "romania": "Mâinile sus!", "hungary": "Fel a kezekkel!", "poland": "Ręce do góry!",
            "china": "Jǔ qǐ shǒu lái!"}
# a surrendered man who isn't searched may still fight: per minute next to you
TREACHERY = {"japan": 0.03}
SEARCH_TIME = 30


def is_prisoner_of(a, p):
    return a.state == "surrendered" and a.ai.get("captor") == p.id


def prisoners_of(game, p):
    return [a for a in game.actors if a.alive and a.state == "surrendered" and a.ai.get("captor") == p.id]


def demand_surrender(game, p):
    """'Hands up!' - in their language.  Wavering men within earshot may take the offer."""
    from .data.nations import NATIONS
    rng = game.rng
    enemy = other_side(p.side)
    words = HANDS_UP.get(game.side_nation(enemy), "Hands up!")
    p.say(words, game.turn, 4)
    game.emit_sound(p.x, p.y, 75, "shout", f"someone shouting '{words}'", p.side, p)
    reach = 18
    friends = sum(1 for a in game.actors if a.side == p.side and a.active and not a.is_player and
                  max(abs(a.x - p.x), abs(a.y - p.y)) <= 10)
    took = 0
    from .data.special import SPECIAL
    for a in game.actors:
        if a.side != enemy or not a.alive or a.state != "ok" or a.vehicle is not None:
            continue
        d = max(abs(a.x - p.x), abs(a.y - p.y))
        if d > reach or not a.body.conscious:
            continue
        doc = NATIONS[a.nation]["doctrine"]
        mates = sum(1 for o in game.actors if o.side == enemy and o.active and o is not a and
                    max(abs(o.x - a.x), abs(o.y - a.y)) <= 6)
        chance = 0.0
        if a.downed:
            chance += 0.45                       # a wounded man on the ground has little choice
        if a.morale < 35:
            chance += 0.25
        if a.suppression > 50:
            chance += 0.2
        if mates == 0:
            chance += 0.2                        # cut off, alone
        if a.weapon is None or (a.weapon.t.kind == "gun" and a.weapon.loaded <= 0 and a.ammo_for(a.weapon) is None):
            chance += 0.25
        chance += 0.03 * friends                 # how many of you there are
        chance -= 0.08 * mates
        chance *= doc.get("surrender", 1.0) * (0.35 ** min(3, getattr(game, "no_quarter", {}).get(enemy, 0)))
        if "fanatic" in SPECIAL.get(a.__dict__.get("unit_type"), {}).get("flags", ()):
            chance *= 0.1
        if d > 10:
            chance *= 0.5                        # did he even hear it
        from .skills import level
        chance *= 0.6 + level(p, "languages") * 0.08   # understood - and meant - in his own tongue
        if chance > 0 and rng.random() < min(0.9, chance):
            a.ai["surrender_at"] = game.turn + rng.randint(1, 4)
            took += 1
        elif chance > 0.05 and rng.random() < 0.3:
            a.say(rng.choice(["Nein!", "Never!", "Go to hell!"] if a.nation != "japan" else ["Bakayarō!"]),
                  game.turn, 3)
    return took


def pending_surrenders(game):
    """Men who've decided: they throw down their weapons a moment after the shout."""
    for a in game.actors:
        t = a.ai.get("surrender_at")
        if t is not None and game.turn >= t:
            a.ai.pop("surrender_at", None)
            if a.alive and a.state == "ok":
                game.surrender(a)


def search(game, p, a):
    """Search and disarm a prisoner: weapons and ammunition in a pile, papers to you."""
    from .entities import Item
    if a.ai.get("searched"):
        return 0, "You've already searched him."
    taken = []
    papers = []
    for it in list(a.inv):
        t = it.t
        if t.kind in ("gun", "grenade", "explosive", "melee", "mag", "clip", "ammo") or t.tool in ("binoculars",):
            a.remove_item(it)
            game.map.add_item(a.x, a.y, it)
            taken.append(it.name)
        elif t.tool in ("document", "orders", "map"):
            a.remove_item(it)
            it.data = dict(it.data or {}, owner=a.name, unit=getattr(a, "unit", ""), nation=a.nation, rank=a.rank_short)
            papers.append(it)
    a.weapon = None
    a.ai["searched"] = True
    for it in papers:
        if p.add_item(it) is None:
            game.map.add_item(p.x, p.y, it)
    if not any(i.tid == "paybook" for i in papers):
        pb = Item("paybook")
        pb.data = dict(owner=a.name, unit=getattr(a, "unit", ""), nation=a.nation, rank=a.rank_short)
        if p.add_item(pb) is None:
            game.map.add_item(p.x, p.y, pb)
        papers.append(pb)
    bits = []
    if taken:
        bits.append(f"You pull {', '.join(taken[:3])}{' and more' if len(taken) > 3 else ''} off him and "
                    f"throw them down")
    else:
        bits.append("You pat him down: nothing on him but his clothes")
    if papers:
        bits.append(f"You pocket his {', '.join(sorted({x.name for x in papers}))}")
    return SEARCH_TIME + 4 * len(taken), ". ".join(bits) + "."


def treachery_tick(game):
    """Once a minute: an unsearched prisoner with a weapon still on him, next to you, makes his move."""
    p = game.player
    if p is None or not p.alive:
        return
    rng = game.rng
    for a in game.actors:
        if a.state != "surrendered" or a.ai.get("searched") or not a.alive or not a.body.conscious or a.downed:
            continue
        if max(abs(a.x - p.x), abs(a.y - p.y)) > 3:
            continue
        rate = TREACHERY.get(a.nation, 0.0015)
        armed = any(i.t.kind in ("grenade", "gun") for i in a.inv)
        if not armed or rng.random() > rate:
            continue
        a.state = "ok"
        a.ai.pop("captor", None)
        g = next((i for i in a.inv if i.t.kind == "grenade"), None)
        if g is not None:
            game.msg(f"{_cap(game.name_of(a))} pulls a grenade from under his tunic!", "death")
            from .actions import throw
            try:
                throw(game, a, g, p.x, p.y)
            except Exception:
                pass
        else:
            gun = next(i for i in a.inv if i.t.kind == "gun")
            a.wield(gun)
            game.msg(f"{_cap(game.name_of(a))} has a pistol out of his boot!", "death")
        game.duty.__dict__.setdefault("treachery_seen", 0)
        game.duty.treachery_seen += 1
        return


def hand_over(game, p, a):
    """Give a prisoner to the nearest comrade to take back; you get on with the war."""
    near = [o for o in game.actors if o.side == p.side and o.active and not o.is_player and not o.downed and
            o.vehicle is None and max(abs(o.x - p.x), abs(o.y - p.y)) <= 6 and not o.ai.get("escort_prisoner")]
    if not near:
        return None
    o = min(near, key=lambda o: (o.role in ("officer", "radioman", "medic", "lmg_gunner", "hmg_gunner"),
                                 max(abs(o.x - p.x), abs(o.y - p.y))))
    o.ai["escort_prisoner"] = a.id
    a.ai["captor"] = o.id
    a.ai["credit"] = p.id
    a.ai["pw_order"] = "follow"
    return o


def bring_along(game, p):
    """Prisoners who come with you across the edge of the map."""
    return [a for a in prisoners_of(game, p) if a.body.conscious and not a.downed and
            max(abs(a.x - p.x), abs(a.y - p.y)) <= 15 and a.ai.get("pw_order", "follow") == "follow"]


def read(game, p, it):
    """A paybook or orders taken from a prisoner (or a body): what can you make of it?"""
    d = it.data or {}
    from .data.nations import NATIONS
    unit = d.get("unit") or ""
    owner = d.get("owner")
    if not owner:
        return "It's smudged and torn; you can't make much of it."
    nat = d.get("nation")
    reads = nat == p.nation or (nat in ("uk", "usa", "canada", "australia", "newzealand") and
                                p.nation in ("uk", "usa", "canada", "australia", "newzealand")) or \
        "linguist" in getattr(p, "traits", ()) or p.role in ("officer", "intel", "agent")
    if not reads:
        return (f"{NATIONS.get(nat, {}).get('adj', 'Foreign')} writing. A name - {owner} - and numbers. "
                f"Intelligence will want it.")
    h = game.__dict__.get("hierarchy")
    n = h.learn_enemy(game, unit_text=unit) if h is not None and unit else 0
    return (f"{d.get('rank', '')} {owner}: {unit or 'unit not given'}."
            + (" You know now who commands them." if n else ""))


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)
