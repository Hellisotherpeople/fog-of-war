"""What goes on between men that nobody orders: the noise of a fight, and the life of a quiet hour.

In a fight (every two seconds, squad by squad):
- the wounded cry out - where they're hit, how badly, the blood, the legs that won't carry them, and at
  the end their mothers; it goes on until a medic gets to them or they go quiet, and it wears on everyone
  in earshot (morale), friend or enemy;
- a man's buddy shouts his name when he goes down, and again when he's dead - and he takes it hard;
- men call their moves ("Moving!" "Covering!"), their troubles ("I'm out!" "Where's it coming from?!"),
  the shells ("Incoming!"), their kills; the frightened panic, and a steadier mate talks them down; NCOs
  keep them firing, spread them out and get them up.
When it's quiet (no contact for two minutes and more):
- smokers light up and pass the cigarettes round (at night the glow can be seen), men trade what they
  have for what they want (people.worth: real items change hands), show the photograph, read the letter,
  pray, hum a song from home; the NCO makes them change their socks;
- a man whose buddy was killed goes to the body when he can, and takes one of the tags; a souvenir hunter
  goes through the enemy dead for a Luger or a watch.
Everything's in the speaker's language (data/chatter.py) and heard by whoever's near - the enemy too.
"""
from __future__ import annotations

from .data.chatter import C, PART, SONGS, UNIVERSAL
from .data.phrases import lang
from .people import buddy, call_name, deal, life, name_of_item, spoken, tradeable, worth


def line(game, a, key, **fmt) -> str | None:
    """A line of `key` in his language, filled in (or None if his language has nothing for it)."""
    lg = lang(a.nation)
    lst = C.get(key, {}).get(lg) or UNIVERSAL.get(key)
    if not lst:
        return None
    text = game.rng.choice(lst)
    if "{part}" in text:
        fmt.setdefault("part", PART.get(lg, PART["en"]).get(fmt.pop("where", "torso"), "leg"))
    try:
        return text.format(**fmt)
    except (KeyError, IndexError):
        return None


def say(game, a, key, tone=None, dur=3, gap=4, loud=0, **fmt) -> bool:
    """He says it - if he hasn't just said something (gap turns), and there's a line for it.  loud: a sound
    others hear (screams carry)."""
    t = game.turn
    if t - a.ai.get("said", -99) < gap or not a.alive:
        return False
    text = line(game, a, key, **fmt)
    if not text:
        return False
    a.ai["said"] = t
    a.say(text, t, dur, tone=tone)
    if loud:
        game.emit_sound(a.x, a.y, loud, "scream" if tone == "scream" else "shout", text, a.side, a)
    return True


def _near(a, b, r) -> bool:
    return max(abs(a.x - b.x), abs(a.y - b.y)) <= r


# ============================================================================ hit
def wounded(game, a, attacker, res):
    """He's just been hit: the cry - and his buddy's."""
    if not a.alive or a.is_player and not res.get("dmg", 0) > 25:
        return
    rng = game.rng
    b = a.body
    part = res.get("part", "torso")
    dmg = res.get("dmg", 0)
    if res.get("knocked_out") or not b.conscious:
        pass
    elif dmg < 14:
        say(game, a, "hit_light", "shout", gap=2, loud=45)
    else:
        if res.get("disabled") and part in ("l_leg", "r_leg"):
            key = "legs"
        elif part == "torso" and dmg > 22:
            key = rng.choice(["gut", "chest", "hit_bad"])
        elif part == "head" and rng.random() < 0.4:
            key = "eyes"
        else:
            key = rng.choice(["part", "hit_bad", "hit_bad"])
        say(game, a, key, "scream", dur=3, gap=0, loud=60, where=part)
    a.ai["cry_next"] = game.turn + rng.randint(4, 9)
    # his mate
    if a.is_player:
        return
    bd = buddy(game, a)
    if bd is not None and bd.active and not bd.downed and _near(a, bd, 18) and not bd.is_player:
        if say(game, bd, "buddy_down", "shout", gap=2, loud=50, name=call_name(a)):
            bd.morale = max(0.0, bd.morale - 4)
            bd.ai["help_buddy"] = (a.id, game.turn)         # (ai.buddy_aid_act: he goes to him first)


def died(game, a, killer):
    """He's dead: his buddy - and the man who shot him."""
    rng = game.rng
    bd = buddy(game, a)
    if bd is not None and bd.alive and bd.active and not bd.is_player:
        near = _near(a, bd, 25)
        if near and say(game, bd, "buddy_dead", "scream" if rng.random() < 0.5 else "shout", dur=4, gap=0, loud=55,
                        name=call_name(a)):
            pass
        bd.morale = max(0.0, bd.morale - (18 if near else 8))
        bd.ai["mourn"] = (a.id, a.x, a.y, call_name(a), game.turn)
    if killer is not None and getattr(killer, "vt", None) is None and hasattr(killer, "ai") and killer.alive and \
            not killer.is_player and rng.random() < 0.35:
        say(game, killer, "got_him", "shout", gap=3)


# ============================================================================ every two seconds
def tick(game):
    t = game.turn
    rng = game.rng
    p = game.player
    for a in game.actors:
        if "replies" in a.ai:
            replies(game, a)
        if a.is_player or not a.alive or a.state != "ok" or a.vehicle is not None:
            continue
        b = a.body
        if not b.conscious:
            continue
        hurt = a.downed or b.bleed_rate() > 0.6 or b.effective_pain() > 60
        if hurt and t >= a.ai.get("cry_next", 0):
            _cry(game, a)
    for sq in game.squads:
        if sq.gone or not sq.members:
            continue
        if t - sq.last_contact < 12:
            if (t // 2) % 2 == sq.id % 2:
                _fight_talk(game, sq)
        elif t - sq.last_contact > 120 and (t // 2) % 5 == sq.id % 5 and rng.random() < 0.3:
            _quiet_life(game, sq)
    return p


def _cry(game, a):
    """A wounded man, until someone gets to him or he goes quiet."""
    rng = game.rng
    b = a.body
    t = game.turn
    pain = b.effective_pain()
    treated = all(w.bandaged or w.tourniquet for w in b.wounds) if b.wounds else True
    worst = min(b.hp[k] / b.max[k] for k in b.hp)
    if b.blood < 3100 or (b.hp["torso"] / b.max["torso"] < 0.3):
        key, tone, loud = ("dying", "talk", 30) if rng.random() < 0.7 else ("shock", "talk", 20)
        nxt = rng.randint(10, 22)
    elif b.bleed_rate() > 2.0 and not treated:
        key, tone, loud, nxt = "bleeding", "scream", 55, rng.randint(5, 11)
    elif a.downed and (b.hp["l_leg"] <= 0 or b.hp["r_leg"] <= 0):
        key, tone, loud, nxt = rng.choice(["legs", "hit_bad", "scream"]), "scream", 55, rng.randint(6, 12)
    elif pain > 90:
        key, tone, loud, nxt = rng.choice(["scream", "hit_bad", "part"]), "scream", 60, rng.randint(5, 10)
    elif pain > 40 or not treated:
        key, tone, loud, nxt = rng.choice(["moan", "hit_bad"]), "scream" if pain > 60 else "talk", 35, rng.randint(9, 18)
    else:
        a.ai["cry_next"] = t + 30
        return
    if b.morphine > 20:
        nxt *= 2                                      # (the morphine: quieter, further off)
        loud = max(15, loud - 20)
    where = max(b.hp, key=lambda k: -(b.hp[k] / b.max[k]))
    a.ai["cry_next"] = t + nxt
    if not say(game, a, key, tone, dur=3, gap=0, loud=loud, where=where):
        return
    # it wears on everyone who hears it
    near = game.near(a.x, a.y, 25, a.side)
    for o in near:
        if o is not a and o.active and _near(a, o, 8):
            o.morale = max(0.0, o.morale - (0.6 if worst < 0.3 else 0.3))
    # the medic answers; a mate beside him says something
    for o in near:
        if not o.active or o.downed or o is a or o.is_player:
            continue
        if o.role == "medic":
            if say(game, o, "medic_coming", "shout", gap=12):
                break
        elif _near(a, o, 1) and rng.random() < 0.35:
            say(game, o, "comfort", "talk", gap=8)
            break


def _fight_talk(game, sq):
    """The noise a section makes in a fight: a man or two says something about what's happening to him."""
    rng = game.rng
    t = game.turn
    men = [m for m in sq.members if m.active and not m.downed and not m.is_player and m.vehicle is None]
    if not men:
        return
    lead = sq.leader if sq.leader is not None and sq.leader.active and not sq.leader.is_player else None
    said = 0
    for m in rng.sample(men, min(len(men), 4)):
        if said >= 2 or t - m.ai.get("said", -99) < 6:
            continue
        w = m.weapon
        key = None
        if w is not None and w.t.kind == "gun" and w.loaded <= 0 and m.ammo_for(w) is None and \
                w.t.cat not in ("mortar", "at_disposable"):
            key = "out_of_ammo"
        elif t - m.ai.get("near_shell", -99) <= 2:
            key = "shelling"
        elif m.morale < 20 and m.suppression > 55:
            key = "panic"
        elif m.suppression > 45 and not m.visible and rng.random() < 0.5:
            key = "under_fire"
        elif sq.state == "bound" and m.moved_turn >= t - 1 and m.id % 2 == sq.phase and rng.random() < 0.4:
            key = "moving"
        elif sq.state == "bound" and m.id % 2 != sq.phase and m.fired_turn >= t - 2 and rng.random() < 0.35:
            key = "covering"
        if key is None:
            continue
        if say(game, m, key, "shout", gap=6):
            said += 1
            if key == "panic":
                _steady(game, m, men)
    if lead is not None and said < 2 and t - lead.ai.get("said", -99) >= 8 and rng.random() < 0.45:
        pinned = sum(1 for m in men if m.suppression > 50)
        prone = sum(1 for m in men if m.stance == 2 and m.moved_turn < t - 4)
        bunched = sum(1 for m in men for o in men if m is not o and _near(m, o, 1)) // 2
        if pinned >= max(2, len(men) // 2) and sq.state in ("engaged", "hold", "bound"):
            say(game, lead, "nco_fire", "shout", gap=8)
        elif bunched >= 3:
            say(game, lead, "nco_spread", "shout", gap=8)
        elif sq.state in ("advance", "bound", "assault") and prone >= max(2, len(men) // 2):
            say(game, lead, "nco_up", "shout", gap=8)


def _steady(game, frightened, men):
    """A steadier man beside him talks him down (a little of his nerve, lent)."""
    for o in men:
        if o is not frightened and o.morale > 45 and _near(o, frightened, 2):
            from .skills import level
            if say(game, o, "steady", "talk", gap=6):
                frightened.morale = min(100.0, frightened.morale + 5 + level(o, "leadership"))
            return


# ============================================================================ a quiet hour
def _quiet_life(game, sq):
    rng = game.rng
    men = [m for m in sq.members if m.active and not m.downed and not m.is_player and m.vehicle is None]
    if not men:
        return
    a = rng.choice(men)
    mates = [m for m in men if m is not a and _near(a, m, 3)]
    lf = life(a)
    options = []
    cig = a.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0)
    if lf["smoker"] and cig is not None:
        options += ["smoke"] * 3
    if mates:
        options += ["trade"] * 3
    if a.find(lambda i: i.t.tool == "photo") is not None and mates:
        options.append("photo")
    if a.find(lambda i: i.t.tool == "letter") is not None:
        options.append("letter")
    if lf["temper"] == "pious" or lf["faith"] not in ("none", "") and rng.random() < 0.2:
        options.append("pray")
    if lf["temper"] in ("cheerful", "homesick", "quiet") and SONGS.get(a.nation):
        options.append("hum")
    if a is sq.leader:
        options.append("feet")
    if a.ai.get("mourn") is not None:
        options += ["mourn"] * 3
    if lf["souvenirs"]:
        options.append("souvenir")
    if not options:
        return
    what = rng.choice(options)
    getattr(_Q, what)(game, a, mates, cig)


class _Q:
    """The things men do when it's quiet (each: game, the man, the mates beside him, his cigarettes)."""

    @staticmethod
    def smoke(game, a, mates, cig):
        t = game.turn
        a.morale = min(100.0, a.morale + 3)
        cig.uses -= 1
        if cig.uses <= 0:
            a.remove_item(cig)
        m = game.map
        if game.is_dark:
            m.lights.append((a.x, a.y, 1, t + 8))         # the glow of a cigarette: it can be seen
        want = [o for o in mates if life(o)["smoker"] and o.find(lambda i: i.t.tool == "cigarettes") is None]
        if want and cig.uses > 0:
            o = want[0]
            if say(game, a, "offer_smoke", "talk", gap=3):
                cig.uses -= 1
                o.morale = min(100.0, o.morale + 5)
                o.ai["replies"] = ("thanks", t + 3)
                _seen(game, a, f"{game.name_of(a)} shares a cigarette with {game.name_of(o)}.")

    @staticmethod
    def trade(game, a, mates, cig):
        """He's got something a mate wants, and the mate's got something he wants: real things change hands."""
        rng = game.rng
        for o in rng.sample(mates, len(mates)):
            mine = [i for i in a.inv if tradeable(a, i)][:12]
            theirs = [i for i in o.inv if tradeable(o, i)][:12]
            best = None
            for x in mine:
                for y in theirs:
                    if x.tid == y.tid or not deal(game, a, x, y, 20) or not deal(game, o, y, x, 20):
                        continue
                    gain = worth(game, a, y) - worth(game, a, x) + worth(game, o, x) - worth(game, o, y)
                    if best is None or gain > best[0]:
                        best = (gain, x, y)
            if best is None:
                continue
            _, x, y = best
            lg = lang(a.nation)
            if not say(game, a, "trade_offer", "talk", gap=3, give=spoken(x, lg), want=spoken(y, lg)):
                return
            if _swap(a, x, o, y):
                o.ai["replies"] = ("trade_yes", game.turn + 3)
                _seen(game, a, f"{game.name_of(a)} swaps {name_of_item(x)} with {game.name_of(o)} for "
                               f"{name_of_item(y)}.")
            return

    @staticmethod
    def photo(game, a, mates, cig):
        lf = life(a)
        sweet = lf["partner"] or "girl"
        say(game, a, "photo", "talk", gap=3, sweet=sweet)
        for o in mates[:1]:
            o.morale = min(100.0, o.morale + 1)

    @staticmethod
    def letter(game, a, mates, cig):
        good = game.rng.random() < 0.7
        if say(game, a, "letter_good" if good else "letter_bad", "talk", gap=3):
            a.morale = max(0.0, min(100.0, a.morale + (4 if good else -8)))

    @staticmethod
    def pray(game, a, mates, cig):
        if say(game, a, "pray", "talk", gap=3):
            a.morale = min(100.0, a.morale + 3)

    @staticmethod
    def hum(game, a, mates, cig):
        song = game.rng.choice(SONGS[a.nation])
        for o in mates:
            o.morale = min(100.0, o.morale + 1)
        a.morale = min(100.0, a.morale + 1)
        a.say("♪ ...", game.turn, 4, voice="")
        _seen(game, a, f"{game.name_of(a)} hums {song} under {a.his} breath.")

    @staticmethod
    def feet(game, a, mates, cig):
        say(game, a, "feet", "talk", gap=3)

    @staticmethod
    def mourn(game, a, mates, cig):
        mid, x, y, name, when = a.ai["mourn"]
        if game.turn - when > 3600 or max(abs(a.x - x), abs(a.y - y)) > 30:
            a.ai.pop("mourn", None)
            return
        a.ai["errand"] = ("mourn", x, y, game.turn + 240)

    @staticmethod
    def souvenir(game, a, mates, cig):
        m = game.map
        from .entities import things_at
        best = None
        for (x, y) in [k for k in m.items if max(abs(k[0] - a.x), abs(k[1] - a.y)) <= 12][:60]:
            for it, _h in things_at(m, x, y):
                v = worth(game, a, it)
                if v >= 40 and (best is None or v > best[0]):
                    best = (v, x, y)
        if best is not None:
            a.ai["errand"] = ("souvenir", best[1], best[2], game.turn + 180)


def _swap(a, x, b, y) -> bool:
    """Hand x (his) over for y (the other man's), if they both have room - else neither moves.  (Held apart
    from stacks while it happens: an item merged into another stack can't be taken back out whole.)"""
    marks = []
    for it in (x, y):
        if not it.data:
            it.data = {"_swap": 1}
            marks.append(it)
    try:
        ax = a.remove_item(x)
        by = b.remove_item(y)
        if a.add_item(by) is None:
            a.add_item(ax)
            b.add_item(by)
            return False
        if b.add_item(ax) is None:
            a.remove_item(by)
            a.add_item(ax)
            b.add_item(by)
            return False
        return True
    finally:
        for it in marks:
            it.data = None


def _seen(game, a, text):
    """In the log, if you're there to see it."""
    p = game.player
    if p is not None and game.map.visible[a.x, a.y] and max(abs(a.x - p.x), abs(a.y - p.y)) <= 12:
        game.msg(text, "think", (a.x, a.y))


def replies(game, a):
    """The other half of an exchange a moment later (a thanks, a 'deal')."""
    r = a.ai.get("replies")
    if r is not None and game.turn >= r[1]:
        a.ai.pop("replies", None)
        say(game, a, r[0], "talk", gap=0)


# ============================================================================ errands: going to the dead
def errand_act(game, a) -> int | None:
    """In a quiet moment: to his buddy's body, or to the enemy dead for a souvenir.  None if there's nothing
    to do, or it's no longer quiet."""
    er = a.ai.get("errand")
    if er is None:
        return None
    kind, x, y, until = er
    sq = a.squad
    if game.turn > until or (sq is not None and game.turn - sq.last_contact < 60) or a.visible:
        a.ai.pop("errand", None)
        return None
    from . import actions as A
    from .ai import path_step
    if max(abs(a.x - x), abs(a.y - y)) > 1:
        return path_step(game, a, x, y, margin=12) or None
    a.ai.pop("errand", None)
    m = game.map
    if kind == "mourn":
        mid, _x, _y, name, _w = a.ai.pop("mourn", (None, 0, 0, "", 0))
        if a.stance == 0:
            A.set_stance(game, a, 1)
        say(game, a, "mourn", "talk", dur=4, gap=0, name=name)
        a.morale = min(100.0, a.morale + 6)
        from .entities import return_thing, take_thing, things_at
        found = next(((i, h) for i, h in things_at(m, x, y) if i.t.tool == "dogtags"), None)
        tags = found[0] if found else None
        if found is not None:
            take_thing(m, x, y, *found)
            if a.add_item(tags) is None:
                return_thing(m, x, y, *found)
        _seen(game, a, f"{game.name_of(a)} kneels by {name} for a moment" +
              (", and takes one of the tags." if tags is not None else "."))
        return 300
    if kind == "souvenir":
        from .entities import return_thing, take_thing, things_at
        best, bv, holder = None, 39.0, None
        for it, h in things_at(m, x, y):
            v = worth(game, a, it)
            if v > bv:
                best, bv, holder = it, v, h
        if best is not None:
            take_thing(m, x, y, best, holder)
            if a.add_item(best) is None:
                return_thing(m, x, y, best, holder)
                return 100
            say(game, a, "souvenir", "talk", gap=0)
            _seen(game, a, f"{game.name_of(a)} goes through the dead man's pockets and comes up with "
                           f"{name_of_item(best)}.")
        return 200
    return None
