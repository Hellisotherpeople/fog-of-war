"""Talking to a man: anyone close enough to hear you (E, or right-click him).

What there is to say depends on who he is to you and the state he's in:
- a comrade: where he's from and who's waiting, how he's holding up (the truth: his wounds, his nerve, his
  ammunition, his feet), what he's seen out there (he points - and you know it too, marked where he means),
  the latest rumour (the war news, as it reaches a foxhole: sometimes wrong), what he makes of the sergeant;
  a smoke, some ammunition, water, covering fire; steadying him when he's shaking; a trade;
- a wounded man: where he's hit, the words that keep him going - and, if he's going, what he wants done;
  what he gives you to take home goes to the chaplain (base.py);
- a prisoner: name, rank and number (the Geneva Convention's due) - and, for a cigarette, or when he's
  frightened enough, where his guns are; sometimes the truth;
- the enemy's wounded: help, and his surrender.
Men who don't share a language with you get gestures: a cigarette held out, a pointed finger, a trade by
holding things up.  Every exchange takes time, and it's what he thinks of you (people.opinion) that
decides what he gives and what he tells you.
"""
from __future__ import annotations

import math

from . import people as PP
from .constants import UI_DIM, UI_TEXT
from .data.phrases import lang
from .render import Popup

GOOD = (180, 220, 150)
WARN = (240, 170, 110)


# ============================================================================ who can you talk to
def near_people(game) -> list:
    p = game.player
    out = []
    for o in game.actors:
        if o is p or not o.alive or o.vehicle is not None and o.vehicle is not p.vehicle:
            continue
        if max(abs(o.x - p.x), abs(o.y - p.y)) > 2:
            continue
        from .senses import player_can_see_actor
        if not player_can_see_actor(game, o):
            continue
        if o.side != p.side and o.state == "ok" and not o.downed and not o.ai.get("civilian"):
            continue                              # (an enemy on his feet: this isn't a conversation)
        out.append(o)
    out.sort(key=lambda o: max(abs(o.x - p.x), abs(o.y - p.y)))
    return out


def talk_key(ps):
    """E: talk to whoever's beside you (a list, if there's more than one)."""
    g = ps.game
    ppl = near_people(g)
    if not ppl:
        g.msg("There's nobody close enough to talk to.", "info")
        return
    if len(ppl) == 1:
        return open_talk(ps, ppl[0])
    opts = [(f"{g.name_of(o)}" + (" (wounded)" if o.downed else " (prisoner)" if o.state == "surrendered" else ""),
             o, None, True) for o in ppl[:12]]
    ps.open_popup(Popup("Talk to", opts, ps._screen_anchor()), lambda o: open_talk(ps, o))


def understands(game, a) -> str:
    """How well you and he understand each other: 'yes', 'some' (broken words), or 'no' (gestures)."""
    p = game.player
    if lang(a.nation) == lang(p.nation):
        return "yes"
    from .skills import level
    mine, his = level(p, "languages"), level(a, "languages")
    best = max(mine, his)
    return "yes" if best >= 7 else "some" if best >= 4 else "no"


def _anchor(ps, who):
    if ps.cam.on_screen(who.x, who.y):
        return ps.cam.to_text(who.x, who.y)
    return ps._screen_anchor()


def _reply(ps, who, text, tone="talk"):
    """He says it: a bubble over him, the line in your log (in English: the story's told in it), and his voice
    if it's English he speaks."""
    g = ps.game
    who.say(text, g.turn, 5, voice=None if lang(who.nation) == "en" else "", tone=tone)
    g.msg(f"{who.last_name}: '{text}'", "shout", (who.x, who.y))


def _did(ps, text, cat="info"):
    ps.game.msg(text, cat)


def _take(g, p, it) -> str:
    """Into your kit if there's room, else your hands, else at your feet.  Where it went, in words."""
    if p.add_item(it) is not None:
        return "kit"
    if p.invent.hands is None:
        p.invent.hands = it
        it.where = "hands"
        return "hands"
    g.map.add_item(p.x, p.y, it)
    return "ground"


# ============================================================================ the conversation
def open_talk(ps, who, said=None):
    g = ps.game
    p = g.player
    if not who.alive or max(abs(who.x - p.x), abs(who.y - p.y)) > 2:
        return
    from .contacts import met
    met(g, who)
    if who.ai.get("civilian"):
        from .homefront import talk
        return talk(ps, who)
    who.ai["talking"] = g.turn + 30               # (he stops to talk - ai.soldier_act - unless the enemy turns up)
    from .base import TALKERS
    if who.side == p.side and who.active and not who.downed and who.role in TALKERS and said is None:
        from .base import talk
        if talk(ps, who):
            return
    if who.side != p.side:
        return _enemy(ps, who, said)
    if who.downed or who.body.bleed_rate() > 1.5 or not who.body.conscious:
        return _wounded(ps, who, said)
    return _comrade(ps, who, said)


def _head(g, who) -> list:
    lf = PP.life(who)
    nick = f" - '{lf['nick']}'" if lf["nick"] else ""
    return [(f"{who.rank_short} {who.name}{nick}, {who.role_name.lower()}. He {PP.feeling(g, who)}.", UI_DIM)]


def _comrade(ps, who, said):
    g = ps.game
    p = g.player
    lines = _head(g, who)
    if said:
        lines.append((f"'{said}'", UI_TEXT))
    t = g.turn
    op = PP.opinion(g, who)
    fighting = t - getattr(who.squad, "last_contact", -9999) < 30
    opts = []
    if not fighting:
        opts.append(("Where are you from?", "home", None, True))
        if who.ai.get("asked_home"):
            opts.append(("Anyone waiting for you back home?", "family", None, True))
        if who.ai.get("asked_family") and who.find(lambda i: i.t.tool == "photo") is not None:
            opts.append(("Can I see the photograph?", "photo", None, True))
    opts.append(("How are you holding up?", "state", None, True))
    opts.append(("Seen anything out there?", "seen", None, True))
    if not fighting:
        opts.append(("What's the word?", "rumour", None, True))
        ld = who.squad.leader if who.squad is not None else None
        if ld is not None and ld is not who and ld is not p and ld.alive:
            opts.append((f"What do you make of {ld.rank_short} {ld.last_name}?", "leader", None, True))
        fresh = t - who.ai.get("chatted", -9999) > 600
        opts.append(("Pass the time with him" + ("" if fresh else " (you just did)"), "chat", None, fresh))
    if who.morale < 35 or who.suppression > 50:
        opts.append(("Steady. Look at me - we'll get through this.", "steady", GOOD, True))
    w = p.weapon
    if w is not None and w.t.kind == "gun" and w.t.cal:
        opts.append((f"Can you spare some ammunition for my {w.t.name}?", "ammo", None, True))
    if who.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0) is not None:
        opts.append(("Got a smoke?", "smoke", None, True))
    wet = who.find(lambda i: i.t.tool == "canteen" and i.uses > 0) is not None
    opts.append(("Got any water?" + ("" if wet else " (his canteen's dry)"), "water", None, wet))
    if fighting:
        opts.append(("Cover me!", "cover", (240, 220, 140), True))
    opts.append(("Trade..." + ("" if (not fighting or op > 30) else " (not in the middle of this)"), "trade",
                 (220, 200, 140), not fighting or op > 30))
    if p.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0) is not None:
        opts.append(("Offer him a cigarette", "give_smoke", None, True))
    opts.append(("Give him something...", "gift", None, True))
    opts.append(("That's all.", "bye", UI_DIM, True))
    ps.open_popup(Popup(f"{who.last_name}", opts, _anchor(ps, who), lines=lines, width=66),
                  lambda v: _comrade_choice(ps, who, v))


def _comrade_choice(ps, who, v):
    g = ps.game
    p = g.player
    lf = PP.life(who)
    rng = g.rng
    op = PP.opinion(g, who)
    if v == "bye":
        return
    say = None
    cost = 400
    if v == "home":
        who.ai["asked_home"] = True
        say = f"{lf['town']}. I {lf['trade']}, before all this."
        if lf["age"] <= 19:
            say += " Lied about my age to get in."
        PP.like(g, who, 1)
    elif v == "family":
        who.ai["asked_family"] = True
        fam, partner, kids = lf["family"], lf["partner"], lf["kids"]
        if fam == "married":
            say = f"My wife, {partner}." + (f" We've got {'a boy' if kids == 1 else f'{kids} kids'}." if kids else "")
        elif fam == "engaged":
            say = f"{partner}. We're getting married when I get back."
        elif fam == "a girl":
            say = f"There's a girl. {partner}. She writes, most weeks."
        elif fam == "his mother":
            say = "My mother. Just her, since Dad died."
        else:
            say = "Nobody, really. Maybe that's easier."
        say += f" When this is over I'm going to {lf['hope']}."
        PP.like(g, who, 2)
    elif v == "photo":
        ph = who.find(lambda i: i.t.tool == "photo")
        text = (ph.data or {}).get("text") if ph is not None else None
        _did(ps, f"{who.last_name} digs out a photograph and holds it out. {text or 'A creased snapshot.'}")
        say = "Don't get it dirty."
        PP.like(g, who, 3, "looked at my photograph")
    elif v == "state":
        say = _state_words(g, who)
    elif v == "seen":
        say = _seen_words(ps, who)
    elif v == "rumour":
        say = _rumour(g, who)
    elif v == "leader":
        say = _leader_words(g, who)
    elif v == "chat":
        who.ai["chatted"] = g.turn
        from .data.banter import BANTER
        opener, reply = rng.choice(BANTER.get("en"))
        _did(ps, f"You: '{opener}'")
        say = reply
        PP.like(g, who, 3)
        p.morale = min(100.0, p.morale + 2)
        who.morale = min(100.0, who.morale + 2)
        cost = 900
    elif v == "steady":
        from .skills import level
        gain = 6 + level(p, "leadership") * 1.2 + max(0.0, op / 20)
        who.morale = min(100.0, who.morale + gain)
        who.suppression = max(0.0, who.suppression - 15)
        say = "Yeah. Yeah. Okay." if gain > 10 else "Easy for you to say."
        PP.like(g, who, 3, "talked me down when I was shaking")
        cost = 200
    elif v == "ammo":
        return _ask_ammo(ps, who)
    elif v == "smoke":
        cig = who.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0)
        if cig is not None and (op > -10 or not lf["smoker"]):
            cig.uses -= 1
            if cig.uses <= 0:
                who.remove_item(cig)
            p.morale = min(100.0, p.morale + 6)
            say = rng.choice(["Here.", "Keep it.", "Last but one. Here."])
            PP.like(g, who, -1)
            _did(ps, f"{who.last_name} shakes one out for you and lights it off his own.", "good")
        else:
            say = "Get your own."
    elif v == "water":
        cw = who.find(lambda i: i.t.tool == "canteen" and i.uses > 0)
        if cw is not None and (op > -20 or cw.uses > 3):
            cw.uses -= 1
            if getattr(p.body, "temp", 37.0) > 37.0:
                p.body.temp = max(37.0, p.body.temp - 0.4)        # (it cools a man who's overheating)
            say = "Go easy. That's all I've got till the jeep comes up."
            PP.like(g, who, -1)
        else:
            say = "It's nearly empty. Sorry."
    elif v == "cover":
        if op > -15 or (who.squad is not None and p.rank > who.rank):
            who.ai["cover_for"] = g.turn + 40
            say = rng.choice(["Go! I've got you!", "Covering! Go!", "Go - I'm on 'em!"])
            _reply(ps, who, say, "shout")
            return ps.act(100)
        say = "Cover yourself."
    elif v == "trade":
        return trade(ps, who)
    elif v == "give_smoke":
        cig = p.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0)
        if cig is not None:
            cig.uses -= 1
            if cig.uses <= 0:
                p.remove_item(cig)
            who.morale = min(100.0, who.morale + 8)
            PP.like(g, who, 8 if lf["smoker"] else 3, "gave me a smoke")
            g.duty.rep += 0.3
            say = rng.choice(["Thanks, pal.", "God bless you.", "Lifesaver."])
            cost = 200
    elif v == "gift":
        return gift(ps, who)
    if say:
        _reply(ps, who, say)
    ps.act(cost)
    if v not in ("cover",):
        open_talk(ps, who, said=say)


# ---------------------------------------------------------------- what he says
def _state_words(g, a) -> str:
    """How he really is: his wounds, his nerve, his breath, the cold, his ammunition, his canteen."""
    b = a.body
    bits = []
    if b.wounds:
        open_ = [w for w in b.wounds if not (w.bandaged or w.tourniquet)]
        if open_:
            bits.append("I'm still bleeding, if you hadn't noticed.")
        else:
            from .body import PART_NAME
            bits.append(f"My {PART_NAME.get(b.wounds[0].part, 'arm')}'s stiff where they patched it.")
    m = a.morale
    bits.append("I'm all right. Really." if m > 65 else "I'm holding up." if m > 45 else
                "Honestly? I don't know how much more of this I've got in me." if m > 25 else
                "I can't stop my hands shaking. Look at them.")
    if getattr(a, "stamina", 100) < 35 or getattr(a, "fatigue", 0) > 60:
        bits.append("I could sleep for a week.")
    from . import thermal
    t = getattr(a.body, "temp", 37.0)
    if t < 36.4:
        bits.append("And I'm freezing.")
    elif t > 38.0:
        bits.append("This heat's killing me.")
    w = a.weapon
    if w is not None and w.t.kind == "gun" and w.t.cal:
        spare = sum(1 for i in a.inv if i.t.kind in ("mag", "clip", "ammo") and i.t.cal == w.t.cal)
        bits.append("I'm down to what's in the gun." if spare == 0 else "Down to my last clip." if spare == 1 else
                    "Got a few clips left." if spare <= 4 else "Plenty of ammo, anyway.")
    cw = a.find(lambda i: i.t.tool == "canteen")
    if cw is not None and cw.uses <= 0:
        bits.append("My canteen's dry.")
    return " ".join(bits[:4])


def _seen_words(ps, a) -> str:
    """What he's seen of the enemy lately - and he points, so you know it too (marked where he means)."""
    g = ps.game
    p = g.player
    t = g.turn
    seen = []
    for eid, (x, y, turn, e) in list(a.known.items()):
        if t - turn > 180 or e is None:
            continue
        if getattr(e, "vt", None) is not None:
            if e.dead or e.abandoned:
                continue
        elif not e.alive or e.state != "ok":
            continue
        seen.append((turn, x, y, e))
    if not seen:
        return "Nothing. Which is what worries me."
    seen.sort(key=lambda s: -s[0])
    from .brain import contact_kind
    from .senses import direction_word
    words = []
    for turn, x, y, e in seen[:3]:
        kind = contact_kind(e)
        what = {"tank": "a tank", "atgun": "an anti-tank gun", "vehicle": "a vehicle", "mg": "an MG", "hmg": "a heavy MG",
                "sniper": "a sniper", "mortar": "a mortar", "officer": "an officer"}.get(kind, "a couple of them")
        yd = int(round(math.hypot(x - p.x, y - p.y) * 2.2 / 25.0) * 25) or 25
        ago = "just now" if t - turn < 20 else "a minute back" if t - turn < 90 else "a while back"
        known = p.has_tool("compass") or p.has_tool("map")
        where = f"{direction_word(x - p.x, y - p.y)}, maybe {yd} yards" if known else "over there - that way"
        words.append(f"{what}, {where}, {ago}")
        g.add_sound_mark(x, y, {"tank": "TANK?", "atgun": "AT?", "mg": "MG?", "hmg": "MG?", "sniper": "SNIPER?"}.get(
            kind, "them?"), 240, "intel")
    return "I saw " + "; ".join(words) + ". He points."


def _rumour(g, a) -> str:
    """The latest, as it gets to a foxhole: the war's real news - or a latrine rumour."""
    rng = g.rng
    st = g.strategic
    news = [n for n in (st.news or [])[-12:] if len(n) < 160]
    if news and rng.random() < 0.7:
        n = rng.choice(news)
        return f"Word is: {n[0].lower() + n[1:] if n[:1].isupper() and not n[:2].isupper() else n} Came down from " \
               f"battalion, so it's probably half true."
    latrine = {"en": ["They say we're being relieved by the end of the week.", "Somebody says Hitler's dead. Somebody always says that.",
                      "Heard the cooks are bringing up hot chow tonight. Heard it last week too.",
                      "Supposedly there's a whole Panzer division in front of us. Or a platoon. Depends who you ask.",
                      "Word is the whole regiment's going back to England to refit. Yeah, right."]}
    return rng.choice(latrine["en"])


def _leader_words(g, a) -> str:
    from .skills import level
    ld = a.squad.leader
    lv = level(ld, "leadership")
    temper = PP.life(a)["temper"]
    if temper == "cynical":
        return "They're all the same. He'll do what they tell him and we'll do the dying."
    if lv >= 6.5:
        return f"{ld.last_name}? Best there is. If anybody gets us out of this, he will."
    if lv >= 4:
        return f"{ld.last_name}'s all right. Knows his job. Doesn't take chances he doesn't have to."
    return f"{ld.last_name}'s going to get us all killed. Keep that to yourself."


def _ask_ammo(ps, who):
    g = ps.game
    p = g.player
    op = PP.opinion(g, who)
    from .ammo import hand_over
    w = p.weapon
    spare = [i for i in who.inv if i.t.kind in ("mag", "clip", "ammo") and i.t.cal == w.t.cal]
    his = who.weapon
    same = his is not None and his.t.kind == "gun" and his.t.cal == w.t.cal
    if not spare:
        _reply(ps, who, "Nothing that fits that." if not same else "I'm as dry as you are.")
    elif same and len(spare) <= 2 and op < 40:
        _reply(ps, who, "I've got two clips and I'm keeping them. Sorry.")
    elif op < -20:
        _reply(ps, who, "Ask somebody who likes you.")
    else:
        n = hand_over(g, who, p, w, max_items=1 if same else 2)
        PP.like(g, who, -1)
        _reply(ps, who, "Here. Don't waste it." if n else "Hang on - no, that's the last.")
    ps.act(200)
    open_talk(ps, who)


# ============================================================================ the wounded
def _wounded(ps, who, said):
    g = ps.game
    b = who.body
    lines = _head(g, who)
    if said:
        lines.append((f"'{said}'", UI_TEXT))
    opts = []
    if b.conscious:
        opts.append(("Where are you hit?", "where", None, True))
        opts.append(("Hang on - you're going to make it.", "hang_on", GOOD, True))
        if b.blood < 3300 or b.hp["torso"] / b.max["torso"] < 0.35:
            opts.append(("Is there anything you want me to do?", "last", WARN, True))
    else:
        lines.append(("He doesn't answer. His eyes are half open.", UI_DIM))
    opts.append(("See to his wounds...", "patch", (240, 200, 120), True))
    opts.append(("Leave him for the medics.", "bye", UI_DIM, True))
    ps.open_popup(Popup(f"{who.last_name} (wounded)", opts, _anchor(ps, who), lines=lines, width=66),
                  lambda v: _wounded_choice(ps, who, v))


def _wounded_choice(ps, who, v):
    g = ps.game
    b = who.body
    rng = g.rng
    if v == "bye":
        return
    if v == "patch":
        return ps._patch_menu(who)
    say = None
    if v == "where":
        from .body import PART_NAME
        bits = []
        for w in b.wounds[:3]:
            st = "the tourniquet's on" if w.tourniquet else "it's dressed" if w.bandaged else \
                "it won't stop" if w.bleed > 2.5 else "it's bleeding"
            bits.append(f"my {PART_NAME.get(w.part, w.part)} - {st}")
        say = ("It's " + ", and ".join(bits) + ".") if bits else "I don't know. Everywhere. I can't tell."
    elif v == "hang_on":
        who.morale = min(100.0, who.morale + 10)
        PP.like(g, who, 5, "stayed with me when I was hit")
        say = rng.choice(["Don't leave me. Please don't leave me.", "Okay... okay.", "Is it bad? Don't lie to me.",
                          "Tell the medic to hurry."])
    elif v == "last":
        return _last_words(ps, who)
    if say:
        _reply(ps, who, say, "talk")
    ps.act(300)
    open_talk(ps, who, said=say)


def _last_words(ps, who):
    """He knows.  What he wants done - and what he gives you to take home (the chaplain will see it gets there)."""
    g = ps.game
    p = g.player
    lf = PP.life(who)
    to = f"{lf['partner']}" if lf["partner"] else "my mother"
    keep = who.find(lambda i: i.t.tool in ("letter", "photo", "ring", "watch", "rosary") and not (i.data or {}).get("for"))
    if keep is not None:
        who.remove_item(keep)
        keep.data = dict(keep.data or {})
        keep.data["for"] = f"{to}, in {lf['town']}"
        keep.data["from_dead"] = who.name
        where = _take(g, p, keep)
        say = f"Take this. Give it to {to}. Tell her... tell her it didn't hurt."
        _did(ps, f"{who.last_name} presses {PP.name_of_item(keep)} into your hand" +
             (" - you've nowhere to put it, and it goes down at your feet" if where == "ground" else "") +
             f". (Take it to a chaplain: he'll see it reaches {lf['town']}.)", "warn")
    else:
        say = f"Tell {to}... tell her I was thinking about her."
    PP.like(g, who, 10, "was with me at the end")
    who.morale = min(100.0, who.morale + 15)
    _reply(ps, who, say, "talk")
    ps.act(600)


# ============================================================================ the enemy: prisoners and wounded
def _enemy(ps, who, said):
    g = ps.game
    und = understands(g, who)
    lines = [(f"{g.name_of(who)}" + (" - your prisoner" if who.ai.get("captor") == g.player.id else ""), UI_DIM)]
    if said:
        lines.append((f"'{said}'", UI_TEXT))
    if und == "no":
        lines.append(("You don't share a word of each other's language. Hands, then.", UI_DIM))
    elif und == "some":
        lines.append(("A few words in common, and a lot of pointing.", UI_DIM))
    opts = []
    if und != "no" and who.state == "surrendered":
        opts.append(("Name, rank and unit?", "name", None, True))
        opts.append(("Where are your guns? Where are your men?", "intel", None, True))
        opts.append(("Lean on him", "lean", WARN, True))
    if who.state == "ok" and who.downed:
        opts.append(("Give up - we'll patch you up.", "offer", GOOD, True))
    if g.player.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0) is not None:
        opts.append(("Offer him a cigarette", "cig", None, True))
    if g.player.find(lambda i: i.t.tool == "canteen" and i.uses > 0) is not None:
        opts.append(("Give him water", "water", None, True))
    opts.append(("Trade...", "trade", (220, 200, 140), who.state == "surrendered"))
    opts.append(("That's all.", "bye", UI_DIM, True))
    ps.open_popup(Popup(g.name_of(who)[:1].upper() + g.name_of(who)[1:], opts, _anchor(ps, who), lines=lines, width=66),
                  lambda v: _enemy_choice(ps, who, v, und))


def _enemy_choice(ps, who, v, und):
    g = ps.game
    p = g.player
    rng = g.rng
    lf = PP.life(who)
    op = PP.opinion(g, who)
    if v == "bye":
        return
    say = None
    if v == "name":
        say = f"{who.rank_full} {who.name}." + (f" {who.unit}." if op > 20 or lf["temper"] in ("nervous",) else
                                               " That's all I have to tell you.")
    elif v in ("intel", "lean"):
        if v == "lean":
            who.morale = max(0.0, who.morale - 15)
            PP.like(g, who, -15)
        talks = (0.15 + max(0.0, op) / 150 + (0.25 if who.morale < 25 else 0) +
                 {"nervous": 0.25, "homesick": 0.1, "keen": -0.35, "hard": -0.2}.get(lf["temper"], 0)
                 + (0.2 if v == "lean" else 0) - (0.2 if und == "some" else 0))
        if rng.random() < talks:
            say = _prisoner_intel(ps, who, lie=rng.random() < (0.25 + (0.25 if v == "lean" else 0)))
        else:
            say = rng.choice(["Nothing. I'll tell you nothing.",
                              "I don't know. I'm a private, I know nothing." if who.rank <= 1 else
                              "I don't know. They tell us nothing.",
                              "Name, rank and number. That's all."])
    elif v == "offer":
        from .data.nations import NATIONS
        doc = NATIONS[who.nation]["doctrine"]
        ch = (0.45 + (0.25 if who.morale < 35 else 0.0) + max(0.0, op) / 100) * doc.get("surrender", 1.0)
        if rng.random() < min(0.9, ch):
            g.surrender(who)
            _did(ps, "He lets go of his rifle. He's yours.", "good")
            PP.like(g, who, 15)
            return ps.act(200)
        say = rng.choice(["Nein!", "Nyet!", "No!"])
    elif v == "cig":
        cig = p.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0)
        if cig is not None:
            cig.uses -= 1
            if cig.uses <= 0:
                p.remove_item(cig)
            PP.like(g, who, 15, "gave me a cigarette")
            who.morale = min(100.0, who.morale + 8)
            g.duty.rep += 0.2
            _did(ps, "He takes it with a shaking hand. You light it for him.", "info")
            say = {"germany": "Danke.", "ussr": "Spasibo.", "japan": "...", "italy": "Grazie.", "france": "Merci."}.get(
                who.nation, "...")
    elif v == "water":
        cw = p.find(lambda i: i.t.tool == "canteen" and i.uses > 0)
        if cw is not None:
            cw.uses -= 1
            PP.like(g, who, 10, "gave me water")
            say = {"germany": "Danke... danke.", "ussr": "Spasibo...", "italy": "Grazie..."}.get(who.nation, "...")
    elif v == "trade":
        return trade(ps, who)
    if say:
        _reply(ps, who, say, "talk")
    ps.act(300)
    if who.alive:
        open_talk(ps, who, said=say)


def _prisoner_intel(ps, who, lie=False) -> str:
    """He tells you where his side's men and guns are - the truth, or a story (you can't tell which)."""
    g = ps.game
    p = g.player
    rng = g.rng
    his = [sq for sq in g.squads if sq.side == who.side and not sq.gone and sq.anchor() is not None and
           sq.kind in ("mg", "mortar", "atgun", "tank", "hq", "rifle", "assault", "sniper")]
    his.sort(key=lambda sq: {"mg": 0, "atgun": 0, "mortar": 1, "tank": 1, "hq": 2}.get(sq.kind, 3))
    if not his:
        return "They've all gone. You got the last of us."
    sq = his[0] if rng.random() < 0.6 else rng.choice(his)
    x, y = sq.anchor()
    what = {"mg": "a machine gun", "atgun": "an anti-tank gun", "mortar": "the mortars", "tank": "tanks",
            "hq": "the company command post", "sniper": "a sniper"}.get(sq.kind, "a platoon")
    if lie:
        x = max(0, min(g.map.w - 1, x + rng.randint(-40, 40)))
        y = max(0, min(g.map.h - 1, y + rng.randint(-40, 40)))
    from .senses import direction_word
    mtr = int(round(math.hypot(x - p.x, y - p.y) * 2.0 / 50.0) * 50) or 50     # (two metres a tile)
    g.add_sound_mark(x, y, "HE SAYS", 240, "intel")
    return f"There's {what} - {direction_word(x - p.x, y - p.y)}, {mtr} metres. That's all I know. (He points.)"


# ============================================================================ trading, and giving
def trade(ps, who):
    """What of his do you want - then what will you give for it (you can see in his face what he thinks)."""
    g = ps.game
    his = [i for i in who.inv if PP.tradeable(who, i)]
    lines = [(f"He'd want: {', '.join(PP.wants(g, who))}.", UI_DIM)]
    if not his:
        _reply(ps, who, "I've got nothing I'd part with.")
        return open_talk(ps, who)
    opts = [(PP.name_of_item(i), i, None, True) for i in his[:18]]
    opts.append(("Never mind.", None, UI_DIM, True))
    ps.open_popup(Popup(f"Trade with {who.last_name}: what do you want?", opts, _anchor(ps, who), lines=lines, width=66),
                  lambda it: _trade_offer(ps, who, it) if it is not None else open_talk(ps, who))


def _trade_offer(ps, who, want):
    g = ps.game
    p = g.player
    mine = [i for i in p.inv if PP.tradeable(p, i)]
    if not mine:
        g.msg("You've nothing he'd take.", "info")
        return open_talk(ps, who)
    fav = PP.opinion(g, who)
    opts = []
    for i in mine[:18]:
        ok = PP.deal(g, who, want, i, fav)
        cue = "he'd take it" if ok else "he shakes his head"
        opts.append((f"{PP.name_of_item(i)} - {cue}", i, GOOD if ok else UI_DIM, True))
    opts.append(("Never mind.", None, UI_DIM, True))
    ps.open_popup(Popup(f"For his {PP.name_of_item(want)}, you offer:", opts, _anchor(ps, who), width=70),
                  lambda it: _trade_close(ps, who, want, it) if it is not None else open_talk(ps, who))


def _trade_close(ps, who, want, give):
    g = ps.game
    p = g.player
    fav = PP.opinion(g, who)
    from .entities import Item
    # one for one: a packet for a packet (the menu names one of each), not the whole stack
    w1 = want if want.count <= 1 else Item(want.tid, 1)
    g1 = give if give.count <= 1 else Item(give.tid, 1)
    if not PP.deal(g, who, w1, g1, fav):
        from .social import line
        _reply(ps, who, "Not a chance." if lang(who.nation) == "en" else (line(g, who, "trade_no") or "No."))
        ps.act(200)
        return open_talk(ps, who)
    got = who.remove_item(want, 1 if want.count > 1 else None)
    gave = p.remove_item(give, 1 if give.count > 1 else None)
    if who.add_item(gave) is None:
        g.map.add_item(who.x, who.y, gave)           # (he'll sort out where it goes)
    where = _take(g, p, got)
    PP.like(g, who, 2)
    _reply(ps, who, g.rng.choice(["Deal.", "Done.", "You drive a hard bargain.", "Pleasure."]))
    g.msg(f"You swap {PP.name_of_item(give)} for {who.last_name}'s {PP.name_of_item(want)}" +
          {"hands": " - no room for it, so you carry it", "ground": " - and put it down: you've no room"}.get(where, "")
          + ".", "good")
    ps.act(500)
    open_talk(ps, who)


def gift(ps, who):
    g = ps.game
    p = g.player
    mine = [i for i in p.inv if PP.tradeable(p, i)]
    if not mine:
        g.msg("You've nothing to give.", "info")
        return open_talk(ps, who)
    opts = [(PP.name_of_item(i), i, None, True) for i in mine[:18]] + [("Never mind.", None, UI_DIM, True)]
    ps.open_popup(Popup(f"Give {who.last_name}:", opts, _anchor(ps, who), width=60),
                  lambda it: _gift(ps, who, it) if it is not None else open_talk(ps, who))


def _gift(ps, who, it):
    g = ps.game
    p = g.player
    got = p.remove_item(it, 1 if it.count > 1 else None)
    v = PP.worth(g, who, got)
    if who.add_item(got) is None:
        p.add_item(got)
        g.msg("He's got no room for it.", "info")
        return open_talk(ps, who)
    PP.like(g, who, min(20.0, 1 + v / 4), f"gave me {PP.name_of_item(got)}")
    _reply(ps, who, "For me? Thanks." if v > 5 else "Uh. Thanks, I guess.")
    ps.act(150)
    open_talk(ps, who)
