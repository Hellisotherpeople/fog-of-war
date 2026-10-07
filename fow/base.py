"""Friendly bases: the men behind the line, and what a soldier can get done there.

A headquarters has its adjutant (orders, postings, leave), a clerk (pay, mail, your record) and
military police at the gate; a depot its quartermaster, armourer and field kitchen; an aid station
its surgeon and chaplain; a motor pool its motor sergeant; an airfield its operations officer; a
naval base its port director.  They are real men at real posts: they stand where they work, they
carry what rear-echelon men carried, they can be killed, and they're only there while the base is.

Walk into one of them to talk (or right-click).  The adjutant's orders are real jobs in the real
war - carry dispatches to another headquarters, go up and rejoin a company in the line, patrol
into enemy ground and report, stand a guard, report aboard a ship or to an airfield - and they
show in your orders like any other, with Enter to get on with it.
"""
from __future__ import annotations

import math
from collections import deque

from .constants import UI_DIM, UI_HI, UI_TEXT
from .data.nations import NATIONS
from .render import Popup

EDGE_VEC = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}

# who works where (the quartermaster, intelligence officer and aid-station staff come from mapgen's spots)
STAFF_AT = {
    "hq": ["adjutant", "clerk", "mp"],
    "depot": ["armourer", "cook"],
    "aid": ["chaplain"],
    "motor_pool": ["motor_sergeant"],
    "airfield": ["ops_officer", "cook"],
    "naval_base": ["port_officer", "clerk", "mp", "cook"],
}
TALKERS = {"adjutant", "clerk", "mp", "armourer", "cook", "chaplain", "politruk", "motor_sergeant", "ops_officer",
           "port_officer", "quartermaster", "intel", "surgeon"}
GRADE = {"adjutant": 10, "clerk": 3, "mp": 2, "armourer": 4, "cook": 3, "chaplain": 10, "politruk": 9,
         "motor_sergeant": 5,
         "ops_officer": 11, "port_officer": 11}
DAY = 86400
HOUR = 3600

# a month's pay in 1944 dollars, by grade (the others are converted - roughly - in their own money)
PAY = [50, 54, 66, 78, 96, 114, 138, 138, 150, 166, 200, 250, 291, 333, 500, 667, 733, 800, 900]
MONEY = {"usa": ("$", 1.0), "uk": ("£", 0.25), "canada": ("$", 1.1), "australia": ("£", 0.3),
         "newzealand": ("£", 0.3), "india": ("rupees ", 3.3), "germany": ("RM ", 2.5), "italy": ("lire ", 19.0),
         "ussr": ("roubles ", 5.3), "japan": ("yen ", 4.3), "france": ("francs ", 50.0), "poland": ("złoty ", 5.0),
         "finland": ("marks ", 49.0), "hungary": ("pengő ", 3.4), "romania": ("lei ", 140.0),
         "china": ("yuan ", 20.0)}
DRINK = {"usa": "coffee", "canada": "coffee", "uk": "tea", "australia": "tea", "newzealand": "tea", "india": "chai",
         "germany": "ersatz coffee", "italy": "surrogato", "ussr": "tea from the samovar", "japan": "green tea",
         "finland": "coffee (real, somehow)", "france": "coffee", "poland": "tea", "hungary": "coffee",
         "romania": "ţuică and coffee", "china": "tea"}
HOME = {"usa": ["Ohio", "Brooklyn", "Texas", "Iowa", "Pittsburgh", "Georgia", "Chicago", "Oregon", "Maine"],
        "uk": ["Leeds", "Glasgow", "Bristol", "Manchester", "Swansea", "a village in Kent", "Belfast"],
        "canada": ["Winnipeg", "Halifax", "Saskatoon", "Quebec", "Toronto"],
        "australia": ["Bendigo", "Perth", "Brisbane", "a station out past Dubbo"],
        "newzealand": ["Dunedin", "Wellington", "a farm near Taupo"],
        "india": ["Nepal", "the Punjab", "Rajputana", "Madras"],
        "germany": ["Hamburg", "Bavaria", "Dresden", "the Ruhr", "Königsberg", "a village in the Eifel"],
        "italy": ["Naples", "Turin", "Sicily", "Bologna"], "ussr": ["Kharkov", "Gorky", "a kolkhoz near Ryazan",
                                                                   "Tashkent", "Sverdlovsk"],
        "japan": ["Hiroshima", "Sendai", "a village in Nagano", "Osaka"], "finland": ["Viipuri", "Tampere"],
        "france": ["Lyon", "Brittany"], "poland": ["Lwów", "Kraków"], "hungary": ["Debrecen"],
        "romania": ["Iaşi"], "china": ["Hunan", "Sichuan"]}
LETTER = ["The {who} writes from {home}: the {news}. 'Keep your head down and come home.'",
          "A letter from {home}, three weeks old. The {who} says the {news}. There's a pressed flower in it.",
          "The {who} writes that the {news}, and asks if you're eating. You read it twice.",
          "From {home}: the {news}. The {who} has underlined 'we are all so proud of you' twice."]
WHO = ["your mother", "your wife", "your girl", "your father", "your sister", "your kid brother"]
NEWS = ["harvest was good", "old dog died", "roof finally got fixed", "rationing's worse", "baby is walking",
        "neighbour's boy was posted missing", "factory's on double shifts", "river flooded again",
        "church bells were taken for the war", "prices are terrible", "garden's full of vegetables"]


TITLE = {"mp": {"germany": "Feldgendarmerie", "uk": "Royal Military Police", "japan": "Kempeitai",
                "ussr": "the komendatura", "italy": "Carabinieri", "usa": "military police"},
         "chaplain": {"uk": "padre", "canada": "padre", "australia": "padre", "newzealand": "padre",
                      "germany": "Kriegspfarrer", "italy": "cappellano", "usa": "chaplain", "poland": "kapelan"},
         "politruk": {"ussr": "political officer"}}


def staff_title(a) -> str:
    return TITLE.get(a.role, {}).get(a.nation, a.role_name.lower())


def _he(a) -> str:
    return "she" if getattr(a, "female", False) else "he"


def staff_roles(kind, nation):
    """Who works at this kind of installation in this army (the Red Army had political officers, not chaplains;
    the Japanese army had no chaplains to speak of)."""
    out = []
    for r in STAFF_AT.get(kind, []):
        if r == "chaplain" and nation == "ussr":
            r = "politruk"
        elif r == "chaplain" and nation in ("japan", "china"):
            continue
        out.append(r)
    return out


def is_staff(a) -> bool:
    return a is not None and a.role in TALKERS and a.active


# ============================================================================ the staff
def spawn_staff(game, rec):
    """The people who run this installation, at their places in it."""
    from .spawn import free_tile_near, make_soldier, pick_nation, place
    from .ai import Order, Squad
    if not STAFF_AT.get(rec.get("kind")) or not rec.get("side"):
        return
    side = rec["side"]
    nat = pick_nation(game, side)
    roles = staff_roles(rec.get("kind"), nat)
    x0, y0, sw, sh = rec.get("rect", (rec["x"] - 5, rec["y"] - 5, 10, 10))
    rng = game.rng
    cx, cy = x0 + sw // 2, y0 + sh // 2
    hints = rec.get("staff_at") or {}
    for i, role in enumerate(roles):
        if role in hints:
            hx, hy = hints[role]
            pt = free_tile_near(game, int(hx), int(hy), 4)
        elif role == "mp":
            # at the gate: the middle of the side facing home
            e = game.home_edge(side)
            gx, gy = {"N": (cx, y0), "S": (cx, y0 + sh - 1), "W": (x0, cy), "E": (x0 + sw - 1, cy)}.get(e, (cx, cy))
            pt = free_tile_near(game, gx, gy, 4)
        else:
            ang = (i + rng.random() * 0.5) * 2.4
            pt = free_tile_near(game, int(cx + math.cos(ang) * sw * 0.25), int(cy + math.sin(ang) * sh * 0.25), 5)
        if pt is None:
            continue
        sq = Squad(side, nat, "staff", rec.get("name", "the base").replace("the ", "").capitalize())
        sq.no_count = True
        sq.order = Order("hold", target=pt, radius=2)
        sq.arrived = True
        a = make_soldier(game, nat, role, rank=GRADE.get(role, 3))
        a.squad = sq
        a.ai["post"] = pt
        a.ai["base"] = rec.get("name", "the base")
        a.ai["base_kind"] = rec.get("kind")
        sq.members.append(a)
        place(game, a, pt[0], pt[1], 2)
        sq.leader = a
        sq.initial = 1
        game.squads.append(sq)


def intact(game, rec) -> bool:
    """Is this installation still there (and still theirs)?"""
    s = game.sector
    return any(k == rec.get("kind") and sd == rec.get("side") and ok for k, sd, ok in s.installations) or \
        rec.get("kind") in ("aid",) and rec.get("name") == "the battalion aid post"


def staff_here(game, role=None, side=None):
    side = side or game.player.side
    return [a for a in game.actors if a.alive and a.side == side and a.role in TALKERS and a.active
            and (role is None or a.role == role)]


def _state(game) -> dict:
    return game.__dict__.setdefault("base_state", {"cd": {}, "paid": None, "mail": None, "leave": -10 ** 9})


def _ready(game, key, every) -> bool:
    return game.turn >= _state(game)["cd"].get(key, -10 ** 9) + every


def _used(game, key):
    _state(game)["cd"][key] = game.turn


def _anchor(ps, npc):
    if ps.cam.on_screen(npc.x, npc.y):
        return ps.cam.to_text(npc.x, npc.y)
    return ps._screen_anchor()


def _name(a) -> str:
    return f"{a.rank_short} {a.last_name}"


def _time_passes(ps, secs, note=None):
    """It takes as long as it takes: the world goes on (and can interrupt you)."""
    if note:
        ps.game.msg(note, "info")
    ps.auto_wait = max(ps.auto_wait, int(secs))
    ps.mark_interrupt()


# ============================================================================ talking
def talk(ps, who) -> bool:
    """Walked into (or right-clicked) a man at his post: his menu.  False if he has nothing to say."""
    g = ps.game
    p = g.player
    if who.side != p.side or not who.active:
        return False
    from .contacts import met
    met(g, who)
    role = who.role
    # dispatches for this headquarters are handed to the first officer you find there
    if _deliverable(g, who):
        return deliver_dispatches(ps, who)
    if role == "quartermaster":
        from .qmui import open_quartermaster
        open_quartermaster(ps, who)
        return True
    if role == "intel":
        from .qmui import open_intel
        open_intel(ps, who)
        return True
    fn = MENUS.get(role)
    if fn is None:
        return False
    fn(ps, who)
    return True


def _menu(ps, who, title, lines, opts, handler, width=64):
    # a greyed line says why, if it doesn't already (mostly: you had one not long ago)
    opts = [(lab if ok or "(" in lab else f"{lab} (not yet)", v, col, ok) for lab, v, col, ok in opts]
    ps.open_popup(Popup(title, opts, _anchor(ps, who), lines=lines, width=width), handler)


# ---------------------------------------------------------------- the adjutant
def _adjutant(ps, who):
    g = ps.game
    p = g.player
    bo = g.__dict__.get("base_order")
    lines = [(f"{_name(who)}, adjutant, {who.ai.get('base', 'headquarters')} - {g.sector.name}.", UI_TEXT)]
    opts = []
    owed = _state(g).get("fatigues", 0)
    if owed:
        lines.append((f"You've {owed} hours of extra duty on the board against your name.", (240, 180, 120)))
        opts.append((f"Serve your extra duty ({owed} hours: fatigues)", "fatigues", (240, 180, 120), True))
    if bo and _done(g, bo) and bo.get("report_to_any", True):
        opts.append(("Report: orders carried out", "report", (180, 230, 150), True))
    if bo and not _done(g, bo):
        lines.append((f"Your orders: {bo['text']}", (220, 200, 140)))
        opts.append(("Ask to be taken off your orders", "cancel", None, True))
    else:
        opts.append(("Ask for orders", "orders", None, not bo or _done(g, bo)))
    if _straggler(g):
        opts.insert(0, ("Report in - you've lost your unit", "report_in", (200, 220, 150), True))
    if g.__dict__.get("awol"):
        opts.insert(0, ("Report yourself absent without leave", "turnin", (240, 180, 120), True))
    opts.append(("What's the situation?", "situation", None, True))
    opts.append(("After-action debrief, decorations and support (Q)", "debrief", None, True))
    rep = g.duty.rep
    fatigue = getattr(p, "fatigue", 0)
    leave_ok = rep >= 8 and g.turn - _state(g)["leave"] > 7 * DAY and not bo
    can_ask = leave_ok or (fatigue > 70 and not bo)
    opts.append(("Ask for a pass to the rear" + ("" if can_ask else " (not now)"), "leave", None, can_ask))
    _menu(ps, who, "Adjutant", lines, opts, lambda v: _adjutant_choice(ps, who, v))


def _adjutant_choice(ps, who, v):
    g = ps.game
    if v == "debrief":
        from .debrief import menu
        return menu(ps)
    if v == "fatigues":
        h = _state(g).pop("fatigues", 0)
        return _time_passes(ps, h * HOUR, f"{who.last_name} hands you over to the sergeant of the guard. {h} hours "
                                         f"of digging latrines, peeling potatoes and whitewashing stones.")
    if v == "orders" and _state(g).get("fatigues"):
        g.msg(f"{who.last_name}: 'Extra duty first. Then we'll talk about orders.'", "info")
        return
    if v == "report":
        return complete(ps, who)
    if v == "cancel":
        g.__dict__["base_order"] = None
        g.duty.rep -= 3
        g.msg(f"{who.last_name} crosses your name off {who.his} board with a look. 'Fine. Get out.'", "warn")
        g.update_orders(force=True)
        return
    if v == "orders":
        offers = offer_orders(g, who)
        if not offers:
            g.msg(f"{who.last_name}: 'Nothing for you right now. Get some rest while you can.'", "info")
            return
        lines = [(f"{who.last_name} runs a finger down {who.his} board.", UI_DIM)]
        opts = [(o["menu"], i, None, True) for i, o in enumerate(offers)]
        return ps.open_popup(Popup("Orders", opts, _anchor(ps, who), lines=lines, width=78),
                             lambda i: give_order(ps, who, offers[i]))
    if v == "report_in":
        return report_in(ps, who)
    if v == "turnin":
        return turn_yourself_in(ps, who)
    if v == "situation":
        return _situation(ps, who)
    if v == "leave":
        if g.__dict__.get("base_order") and not _done(g, g.base_order):
            g.msg(f"{who.last_name}: 'A pass? You've got orders. Carry them out first.'", "info")
            return
        return _leave(ps, who)


def _straggler(game) -> bool:
    sq = game.player.squad
    return sq is None or (sq.player_led and len([m for m in sq.members if m.alive]) <= 1 and
                          game.command.billet is None)


def report_in(ps, who):
    """A lost man reports to headquarters: he's put with a squad in this sector, or sent to one."""
    g = ps.game
    p = g.player
    sq = _best_squad_here(g)
    if sq is not None:
        _join(g, sq)
        ldr = sq.leader
        g.msg(f"{who.last_name}: 'You're with {sq.name} now. {('Report to ' + _name(ldr)) if ldr else 'Go find them'}.'",
              "radio")
        g.duty.rep += 1
        ps.act(300)
        return
    tgt = _front_sector(g)
    if tgt is None:
        g.msg(f"{who.last_name}: 'Stay here. Something will turn up.'", "info")
        return
    give_order(ps, who, _order_rejoin(g, who, tgt))


def _best_squad_here(game):
    p = game.player
    best = None
    for sq in game.squads:
        if sq.side != p.side or getattr(sq, "no_count", False) or sq.player_led or sq.kind in ("staff", "rear", "aid", "atgun") or \
                not sq.members or sq.vehicles:
            continue
        if sq.nation != p.nation and not (game.command and p.rank >= 14):
            continue
        n = len([m for m in sq.members if m.alive])
        if n == 0:
            continue
        if best is None or n < best[0]:
            best = (n, sq)
    return best[1] if best else None


def _join(game, sq):
    p = game.player
    old = p.squad
    if old is not None and p in old.members:
        old.members.remove(p)
        if not old.members and old in game.squads:
            game.squads.remove(old)
    p.squad = sq
    sq.members.append(p)
    try:
        from .ai import assign_positions
        assign_positions(game, sq)
    except Exception:
        pass
    try:
        game.command.organise(game)
    except Exception:
        pass
    game.update_orders(force=True)


def _situation(ps, who):
    g = ps.game
    st = g.strategic
    p = g.player
    ours = sum(1 for s in st.sectors() if s.control == p.side)
    theirs = sum(1 for s in st.sectors() if s.control and s.control != p.side)
    near = []
    s0 = g.sector
    for s in st.sectors():
        d = abs(s.x - s0.x) + abs(s.y - s0.y)
        if 0 < d <= 3 and s.control and s.control != p.side:
            near.append((d, s))
    near.sort(key=lambda t: t[0])
    front = ", ".join(s.name for _, s in near[:3]) or "nowhere near here"
    atk = [a for a in getattr(st, "attacks", []) or [] if isinstance(a, dict)]
    g.msg(f"{who.last_name}: 'We hold {ours} sectors to their {theirs}. The nearest enemy ground is {front}."
          + (f" There are {len(atk)} attacks going in along the front." if atk else "") + "'", "radio")
    ps.act(200)


def _leave(ps, who):
    """A pass to the rear: a day or three of sleep, hot food, clean clothes - and the war goes on."""
    g = ps.game
    p = g.player
    days = g.rng.choice((1, 1, 2, 3))
    _state(g)["leave"] = g.turn
    g.msg(f"{who.last_name} signs a pass. {days * 24} hours. You ride back on a supply truck, sleep in a bed, "
          f"eat, bathe, and ride forward again.", "good")
    g._skip_time(days * DAY)
    p.fatigue = 0.0
    p.stamina = 100.0
    p.morale = max(p.morale, 90.0)
    b = p.body
    for k in b.hp:
        b.hp[k] = min(b.max[k], b.hp[k] + b.max[k] * 0.25 * days)
    if hasattr(b, "temp"):
        b.temp = 37.0
    if hasattr(b, "wet"):
        b.wet = 0.0
    g.msg("Back at the front, the war has moved on without you.", "info")
    g.update_orders(force=True)


# ---------------------------------------------------------------- the clerk
def _clerk(ps, who):
    g = ps.game
    p = g.player
    owed_days = _days_owed(g)
    lines = [(f"{_name(who)}, clerk. Typewriter, carbon paper, a mug of cold {DRINK.get(who.nation, 'coffee')}.",
              UI_TEXT)]
    opts = [(f"Draw your pay ({owed_days} days owed)", "pay", None, owed_days >= 1),
            ("Any mail for me?", "mail", None, True),
            ("My service record - am I up for anything?", "record", None, True),
            ("Write a letter home", "write", None, _ready(g, "write", DAY // 2))]
    _menu(ps, who, "Clerk", lines, opts, lambda v: _clerk_choice(ps, who, v))


def _days_owed(game) -> int:
    st = _state(game)
    if st["paid"] is None:
        st["paid"] = game.turn - (game.now().day - 1) * DAY      # last paid on the first of the month
    return int((game.turn - st["paid"]) // DAY)


def _clerk_choice(ps, who, v):
    g = ps.game
    p = g.player
    if v == "pay":
        days = _days_owed(g)
        fine = min(days, _state(g).pop("fine_days", 0))
        if fine:
            g.msg(f"{who.last_name} runs a finger down the sheet: {fine} days stopped, by order.", "warn")
        days -= fine
        usd = PAY[max(0, min(len(PAY) - 1, p.rank))] * days / 30.0
        sym, rate = MONEY.get(p.nation, ("$", 1.0))
        cr = max(1, int(usd * 0.4))
        from .qmui import add_credit
        add_credit(g, cr)
        _state(g)["paid"] = g.turn
        g.msg(f"{who.last_name} counts it out: {sym}{int(usd * rate):,}, {days} days' pay, less allotments. "
              f"(The quartermaster will take it: +{cr} credit.)", "good")
        return ps.act(300)
    if v == "mail":
        st = _state(g)
        if st["mail"] is not None and g.turn - st["mail"] < 2 * DAY:
            g.msg(f"{who.last_name}: 'Nothing since last time. The mail's slow as ever.'", "info")
            return ps.act(100)
        st["mail"] = g.turn
        rng = g.rng
        n = rng.choice((0, 1, 1, 1, 2, 3))
        if n == 0:
            g.msg(f"{who.last_name} goes through the sack twice. 'Sorry, pal. Nothing.'", "info")
            p.morale = max(0, p.morale - 2)
            return ps.act(200)
        from .entities import Item
        for _ in range(n):
            it = Item("letter")
            home = rng.choice(HOME.get(p.nation, HOME["usa"]))
            it.data = dict(text=rng.choice(LETTER).format(who=rng.choice(WHO), home=home, news=rng.choice(NEWS)))
            if p.add_item(it) is None:
                g.map.add_item(p.x, p.y, it)
        g.msg(f"{who.last_name} hands you {n} letter{'s' if n != 1 else ''}. (a to read)", "good")
        p.morale = min(100, p.morale + 4 * n)
        return ps.act(200)
    if v == "record":
        c = g.command
        before = p.rank
        try:
            c.consider_promotion(g, why="the colonel signs the papers")
        except Exception:
            pass
        med = ", ".join(c.medals[-3:]) if getattr(c, "medals", None) else "none yet"
        if p.rank > before:
            g.msg(f"{who.last_name}: 'Your promotion came through - here, sign.' You're now {p.rank_full}.", "good")
        else:
            need = max(0, int(c.promotion_need(p.rank) - (c.merit - c.merit_at_promotion))) \
                if hasattr(c, "promotion_need") else 0
            word = "soon, if you keep it up" if need < 5 else "not yet" if need < 15 else "not for a long while"
            g.msg(f"{who.last_name} leafs through your file. Decorations: {med}. Promotion: {word}.", "info")
        return ps.act(200)
    if v == "write":
        _used(g, "write")
        p.morale = min(100, p.morale + 5)
        return _time_passes(ps, 600, "You borrow a pencil and write home. You leave out most of it.")


# ---------------------------------------------------------------- military police
def _mp(ps, who):
    g = ps.game
    p = g.player
    if g.__dict__.get("awol") or g.__dict__.get("wanted") or getattr(g.duty, "arrest", False):
        return _arrest(ps, who)
    lines = [(f"{_name(who)}, {staff_title(who)}. {_he(who).capitalize()} looks at your face, then your boots, then "
              f"your papers.", UI_TEXT)]
    opts = [("Where can I find...", "where", None, True)]
    _menu(ps, who, "Military police", lines, opts, lambda v: _directions(ps, who))


def _directions(ps, who):
    g = ps.game
    p = g.player
    from .senses import direction_word
    out = []
    for a in staff_here(g):
        if a is who:
            continue
        d = math.hypot(a.x - p.x, a.y - p.y)
        out.append((d, f"the {a.role_name.lower()} {int(round(d * 2.2 / 10) * 10)} yards {direction_word(a.x - p.x, a.y - p.y)}"))
    out.sort()
    if not out:
        g.msg(f"{who.last_name}: 'There's nobody here but me, Mac.'", "info")
    else:
        g.msg(f"{who.last_name}: '" + "; ".join(t for _, t in out[:6]) + ".'", "info")
        for a in staff_here(g):
            if a is not who:
                g.add_sound_mark(a.x, a.y, "·" + a.role_name.split()[0].lower(), 12, "shout")
    ps.act(100)


def turn_yourself_in(ps, who):
    """Better to walk in than be dragged in: a stoppage of pay and a black mark, not the stockade."""
    g = ps.game
    g.__dict__["awol"] = False
    g.duty.rep -= 3
    _state(g)["paid"] = g.turn
    g.msg(f"{who.last_name} writes it up. 'Missed movement. You'll lose a week's pay - and you're lucky it isn't "
          f"worse. We'll find you another berth.'", "warn")
    g.update_orders(force=True)
    ps.act(300)


def _arrest(ps, who):
    g = ps.game
    p = g.player
    g.msg(f"{who.last_name}: 'You're {p.name}? You're under arrest.' The cuffs go on.", "death")
    g.duty.rep -= 6
    g.duty.strikes += 1
    g.__dict__["awol"] = False
    g.__dict__["wanted"] = None
    try:
        g.duty.arrest = False
    except Exception:
        pass
    g._skip_time(DAY)
    g.msg("A day in the stockade, then a company punishment: extra duties, pay stopped. The adjutant has "
          "something for you.", "warn")
    _state(g)["paid"] = g.turn                   # stopped pay
    g.update_orders(force=True)


# ---------------------------------------------------------------- the armourer
def _armourer(ps, who):
    g = ps.game
    p = g.player
    w = p.weapon
    gun = w is not None and w.t.kind == "gun"
    own = gun and p.nation in (w.t.get("nations") or ()) or (gun and any(src in (w.t.get("nations") or ())
                                                                         for src in _sources(g)))
    lines = [(f"{_name(who)}, armourer. Oil, rags, a vice, and a crate of parts from things that got hit.", UI_TEXT)]
    ammo_ok = bool(gun and own and _ready(g, "ammo", HOUR * 6))
    ammo_why = "" if ammo_ok else " (you've no gun)" if not gun else " (he's nothing for a captured gun)" if not own \
        else " (you drew some not long ago)"
    opts = [(f"Strip, clean and check your {w.t.name}" if gun else "Strip and clean your weapon (you've no gun)",
             "clean", None, bool(gun and w.functional)),
            ("Draw ammunition for it" + ammo_why, "ammo", None, ammo_ok),
            ("Swap your captured weapon for an issue one" + ("" if (gun and not own) else " (yours is issue)"),
             "swap", None, bool(gun and not own))]
    from .equipment import repairable
    opts += [(f"Repair {i.name} ({round(i.condition * 100)}%; parts and workshop time)", ("repair", i), None, True)
             for i in p.inv if repairable(i) and 0 < i.condition < .999]
    _menu(ps, who, "Armourer", lines, opts, lambda v: _armourer_choice(ps, who, v))


def _sources(game):
    from .data.nations import equip_sources
    return equip_sources(game.player.nation, game.year)


def _armourer_choice(ps, who, v):
    g = ps.game
    p = g.player
    w = p.weapon
    if isinstance(v, tuple) and v[0] == "repair":
        it = v[1]
        if it not in p.inv or not (0 < it.condition < 1):
            return
        from .sustain import take
        deficit = 1 - it.condition
        if not take(g.sector, p.side, "parts", max(1., deficit * 5)):
            g.msg("The armourer has no spare parts for this repair.", "warn")
            return
        it.condition = 1.
        it.jammed = False
        g.msg(f"{who.last_name} repairs the {it.t.name} with parts from the stores.", "good")
        return _time_passes(ps, int(600 + 1800 * deficit))
    if v == "clean" and w is not None:
        w.jammed = False
        w.heat = 0
        w.data = dict(w.data or {}, clean=g.turn)
        g.msg(f"{who.last_name} strips your {w.t.name}, tuts, replaces a worn spring and hands it back cleaner than "
              f"it's been in weeks. (It'll jam less for a while.)", "good")
        return _time_passes(ps, 900)
    if v == "ammo" and w is not None:
        from .ammo import give_loads
        _used(g, "ammo")
        give_loads(p, w, 3)
        g.msg(f"{who.last_name} slides three loads for your {w.t.name} across the bench and writes it in a book.",
              "good")
        return ps.act(200)
    if v == "swap" and w is not None:
        from .data.roles import build_kit
        from .spawn import apply_kit
        kit = build_kit(g.rng, p.nation, g.year, "rifleman")
        nid = kit.get("wield")
        if not nid:
            g.msg(f"{who.last_name}: 'Nothing on the rack for you.'", "info")
            return
        from .entities import Item
        from .ammo import give_loads
        from .data.items import ITEMS
        p.remove_item(w)
        new = Item(nid)
        p.wield(new)
        give_loads(p, new, 4)
        g.msg(f"{who.last_name} takes the {w.t.name} ('souvenir hunters'll pay for that') and issues you a "
              f"{ITEMS[nid].name} with four loads.", "good")
        return ps.act(300)


# ---------------------------------------------------------------- the cook
def _cook(ps, who):
    g = ps.game
    drink = DRINK.get(who.nation, "coffee")
    lines = [(f"{_name(who)}, cook. Steam, a dixie of something, a ladle.", UI_TEXT)]
    opts = [("A hot meal", "meal", None, _ready(g, "meal", HOUR * 5)),
            (f"A mug of {drink}", "drink", None, _ready(g, "drink", HOUR)),
            ("Rations for the road", "rations", None, _ready(g, "rations", HOUR * 12))]
    _menu(ps, who, "Field kitchen", lines, opts, lambda v: _cook_choice(ps, who, v))


def _cook_choice(ps, who, v):
    g = ps.game
    p = g.player
    if v == "meal":
        _used(g, "meal")
        p.morale = min(100, p.morale + 12)
        p.fatigue = max(0.0, getattr(p, "fatigue", 0) - 12)
        p.stamina = 100.0
        if hasattr(p.body, "temp"):
            p.body.temp = max(p.body.temp, min(37.0, p.body.temp + 0.6))
        food = {"usa": "stew and canned peaches", "uk": "bully beef hash and duff", "germany": "Eintopf from the "
                "Gulaschkanone", "ussr": "kasha and a chunk of black bread", "japan": "rice and pickled plums",
                "italy": "pasta e fagioli", "finland": "pea soup", "france": "a stew with actual wine in it"}
        g.msg(f"{who.last_name} fills your mess tin: {food.get(p.nation, 'something hot')}. You eat standing up. "
              f"It's the best thing you've ever tasted.", "good")
        return _time_passes(ps, 600)
    if v == "drink":
        _used(g, "drink")
        p.morale = min(100, p.morale + 4)
        p.fatigue = max(0.0, getattr(p, "fatigue", 0) - 3)
        g.msg(f"A mug of {DRINK.get(who.nation, 'coffee')}, scalding.", "info")
        return _time_passes(ps, 240)
    if v == "rations":
        _used(g, "rations")
        from .entities import Item
        for _ in range(2):
            it = Item("ration")
            if p.add_item(it) is None:
                g.map.add_item(p.x, p.y, it)
        for it in p.inv:
            if it.t.tool == "canteen" or it.tid == "canteen":
                it.uses = it.t.uses or it.uses
        g.msg(f"{who.last_name} hands over two ration packs and fills your canteen.", "info")
        return ps.act(150)


# ---------------------------------------------------------------- the chaplain
def _chaplain(ps, who):
    g = ps.game
    p = g.player
    tags = [i for i in p.inv if i.t.tool == "dogtags" and i.data and (i.data.get("name") or i.data.get("owner"))]
    keeps = [i for i in p.inv if i.data and i.data.get("for")]
    lines = [(f"{_name(who)}, {staff_title(who)}. A stole in {who.his} pocket, mud to the knees. "
              f"{_he(who).capitalize()}'s buried a lot of men.", UI_TEXT)]
    opts = [(f"Talk with {who.him}", "talk", None, _ready(g, "chaplain", HOUR * 12)),
            (f"Give {who.him} the tags of {len(tags)} dead {'man' if len(tags) == 1 else 'men'}" if tags else
             "Give over a dead man's tags", "tags", None, bool(tags)),
            (f"Ask {who.him} to write to a dead friend's family", "write", None, _ready(g, "condolence", DAY))]
    if keeps:
        opts.insert(1, (f"Give {who.him} what a dying man asked you to send home ({len(keeps)})", "keeps",
                        (220, 200, 140), True))
    _menu(ps, who, "Chaplain", lines, opts, lambda v: _chaplain_choice(ps, who, v, tags))


def _chaplain_choice(ps, who, v, tags):
    g = ps.game
    p = g.player
    if v == "talk":
        _used(g, "chaplain")
        lift = 15 if p.morale < 40 else 8
        p.morale = min(100, p.morale + lift)
        p.suppression = 0
        g.msg(f"You sit on an ammunition box and {who.last_name} lets you talk, and doesn't say much. It helps.", "good")
        return _time_passes(ps, 900)
    if v == "keeps":
        keeps = [i for i in p.inv if i.data and i.data.get("for")]
        for it in keeps:
            p.remove_item(it)
        g.duty.rep += 3 * len(keeps)
        g.command.merit += len(keeps)
        p.morale = min(100, p.morale + 6)
        rec = g.command.__dict__.setdefault("record", [])
        for it in keeps[:3]:
            rec.append(f"{g.datetime_str()}: carried {it.data.get('from_dead', 'a dying man')}'s last things home.")
        where = keeps[0].data.get("for", "his family")
        g.msg(f"{who.last_name} wraps {'them' if len(keeps) > 1 else 'it'} in a field-service envelope and writes the "
              f"address: {where}. 'It'll get there. You did right by him.'", "good")
        return ps.act(300)
    if v == "tags":
        names = [t.data.get("name") or t.data.get("owner") for t in tags]
        for t in tags:
            p.remove_item(t)
        g.duty.rep += 2 * len(tags)
        p.morale = min(100, p.morale + 3)
        g.msg(f"{who.last_name} takes the tags - {', '.join(names[:3])}{'...' if len(names) > 3 else ''} - and "
              f"writes the names in {who.his} book. 'They'll be buried properly. Their people will know.'", "info")
        return ps.act(300)
    if v == "write":
        _used(g, "condolence")
        g.duty.rep += 1
        p.morale = min(100, p.morale + 4)
        return _time_passes(ps, 600, f"You tell {who.last_name} what the man was like. It goes down on paper in a "
                                     f"careful hand.")


# ---------------------------------------------------------------- the political officer
def _politruk(ps, who):
    g = ps.game
    p = g.player
    lines = [(f"{_name(who)}, political officer. A copy of Krasnaya Zvezda, a notebook, and eyes that miss nothing.",
              UI_TEXT)]
    opts = [("Listen to the political talk", "talk", None, _ready(g, "politruk", HOUR * 12)),
            ("Ask to join the Party", "party", None, not _state(g).get("party"))]
    _menu(ps, who, "Political officer", lines, opts, lambda v: _politruk_choice(ps, who, v))


def _politruk_choice(ps, who, v):
    g = ps.game
    p = g.player
    if v == "talk":
        _used(g, "politruk")
        p.morale = min(100, p.morale + 7)
        g.duty.rep += 1
        return _time_passes(ps, 900, f"{who.last_name} reads the latest from the Sovinformburo - cities liberated, the "
                                     f"fascists in retreat - and the men around you straighten up a little.")
    if v == "party":
        _state(g)["party"] = True
        g.duty.rep += 5
        p.morale = min(100, p.morale + 4)
        g.msg(f"You write it out on a page of {who.last_name}'s notebook: 'If I die, consider me a communist.' "
              f"{_he(who).capitalize()} tucks it away.", "info")
        return ps.act(300)


# ---------------------------------------------------------------- the motor pool
def _motor(ps, who):
    g = ps.game
    p = g.player
    bo = g.__dict__.get("base_order")
    need = bool(bo and bo.get("sector") and tuple(bo["sector"]) != (g.sector.x, g.sector.y))
    lines = [(f"{_name(who)}, motor sergeant. Grease to the elbows. Behind {who.him}, engines in pieces.", UI_TEXT)]
    ok = (p.rank >= 3 or need) and _ready(g, "vehicle", DAY // 2)
    opts = [("Draw a vehicle" + ("" if ok else f" ({_he(who)} laughs)"), "vehicle", None, ok)]
    from .maintenance import repairs
    near = [v for v in g.vehicles if not v.dead and v.side == p.side and abs(v.x - p.x) + abs(v.y - p.y) < 6
            and (v.hp < v.vt.hp or repairs(v))]
    if near:
        opts.append((f"Get the {near[0].vt.name} fixed", "repair", None, True))
    run = supply_run_order(g, who)
    if run is not None and not bo:
        opts.append((run["menu"], "supply_run", None, True))
    _menu(ps, who, "Motor pool", lines, opts, lambda v: _motor_choice(ps, who, v, near))


def _armour_sector(game):
    """The nearest sector of ours (not this one) with tanks in it, the front first: where shells are wanted."""
    st = game.strategic
    p = game.player
    s0 = game.sector
    best = None
    for s in st.sectors():
        if not s.playable or s.control != p.side:
            continue
        d = abs(s.x - s0.x) + abs(s.y - s0.y)
        if d == 0 or d > 4:
            continue
        u = s.units[p.side]
        if u.get("tank", 0) + u.get("td", 0) <= 0:
            continue
        try:
            front = st.is_front(s, p.side)
        except Exception:
            front = False
        key = (0 if front else 1, d)
        if best is None or key < best[0]:
            best = (key, s)
    return best[1] if best else None


def supply_run_order(game, who):
    """An ammunition truck to drive up to the tanks, or None."""
    s = _armour_sector(game)
    if s is None:
        return None
    d = abs(s.x - game.sector.x) + abs(s.y - game.sector.y)
    return dict(kind="supply_run", sector=(s.x, s.y), need=40,
                text=f"Drive an ammunition truck up to the tanks in {s.name}, and see them loaded.",
                menu=f"Supply run: an ammunition truck to the tanks in {s.name} ({d} sector{'s' if d != 1 else ''})",
                reward=dict(merit=2 + d, rep=3, credit=10 + 5 * d), hours=2 + 2 * d, by=_issuer(game, who),
                report_to_any=False)


def _truck_for(ps, who, o):
    """The motor sergeant signs out a loaded truck.  Returns it, or None if there isn't one."""
    from . import maintenance as MT
    from .data.vehicles import VEHICLES
    from .entities import Vehicle
    from .spawn import pick_vehicle, spot_and_facing
    g = ps.game
    p = g.player
    vid = pick_vehicle(g.rng, p.nation, g.year, "truck")
    if vid is None:
        g.msg(f"{who.last_name}: 'Not a truck left that runs.'", "info")
        return None
    pt, f = spot_and_facing(g, p.x, p.y, VEHICLES[vid], 6, g.rng.randint(0, 7))
    if pt is None:
        g.msg(f"{who.last_name}: 'No room to bring it round.'", "info")
        return None
    t = Vehicle(vid, p.side, p.nation, pt[0], pt[1], f)
    t.crew = 0
    t.abandoned = False
    t.ai.update(issued_to=p.id, cargo=MT.TRUCK_CARGO, delivered=0, fitters=True, player_run=True)
    g.add_vehicle(t)
    return t


def _motor_choice(ps, who, v, near):
    g = ps.game
    p = g.player
    if v == "vehicle":
        from .spawn import pick_vehicle, spot_and_facing
        from .data.vehicles import VEHICLES
        from .entities import Vehicle
        vid = pick_vehicle(g.rng, p.nation, g.year, "car") or pick_vehicle(g.rng, p.nation, g.year, "truck")
        if vid is None:
            g.msg(f"{who.last_name}: 'Nothing that runs.'", "info")
            return
        pt, f = spot_and_facing(g, p.x, p.y, VEHICLES[vid], 6, g.rng.randint(0, 7))
        if pt is None:
            g.msg(f"{who.last_name}: 'No room to bring it round.'", "info")
            return
        v = Vehicle(vid, p.side, p.nation, pt[0], pt[1], f)
        v.crew = 0
        v.abandoned = False
        v.ai["issued_to"] = p.id
        g.add_vehicle(v)
        _used(g, "vehicle")
        g.msg(f"{who.last_name} signs out a {VEHICLES[vid].name}. 'Bring it back with the same number of holes.' "
              f"(e to get in)", "good")
        return ps.act(300)
    if v == "supply_run":
        o = supply_run_order(g, who)
        if o is None or g.__dict__.get("base_order"):
            return
        t = _truck_for(ps, who, o)
        if t is None:
            return
        o["truck"] = t.id
        g.msg(f"{who.last_name} signs out a {t.vt.name}, {MT_ROUNDS()} rounds of tank ammunition roped down in the back "
              f"and two fitters on the tailboard. (e beside it to get in and drive)", "good")
        return give_order(ps, who, o)
    if v == "repair" and near:
        veh = near[0]
        for part in veh.parts:
            veh.parts[part] = 2                     # every part mended or replaced
        veh.hp = veh.vt.hp
        g.msg(f"{who.last_name}'s mechanics swarm over the {veh.vt.name}.", "info")
        return _time_passes(ps, 1800)


# ---------------------------------------------------------------- the airfield
def _ops(ps, who):
    g = ps.game
    p = g.player
    from .data.roles import service_of
    air = service_of(p.role) == "air"
    lines = [(f"{_name(who)}, operations. A map with strings and pins, a board of aircraft and crews.", UI_TEXT)]
    opts = [("Flying orders" + ("" if air else " (for aircrew)"), "fly", None, air)]
    _menu(ps, who, "Air operations", lines, opts, lambda v: _ops_choice(ps, who, v))


def _ops_choice(ps, who, v):
    g = ps.game
    if v == "fly":
        g.msg(f"{who.last_name}: 'You're on. Briefing in ten minutes, then get out to your aircraft.'", "radio")
        return ps._take_off_menu()
    if v == "transfer":
        g.msg(f"{who.last_name}: 'Aircrew are trained men, not volunteers off the street. Put in through your "
              f"adjutant.'", "info")


# ---------------------------------------------------------------- the naval base
def _port(ps, who):
    from . import naval as NV
    g = ps.game
    p = g.player
    from .data.roles import service_of
    ctx = NV.ship_ashore(g)
    lines = [(f"{_name(who)}, port director. A chart of the anchorage, the berths chalked on a board.", UI_TEXT)]
    opts = []
    if ctx is not None:
        opts.append((f"Liberty boat back to {ctx['ship_name']}", "back", (140, 190, 255), True))
    if g.__dict__.get("awol"):
        opts.insert(0, ("Report yourself: you missed your ship", "turnin", (240, 180, 120), True))
    navy = service_of(p.role) == "navy"
    awol = bool(g.__dict__.get("awol"))
    opts.append(("Ask for a ship" + (" (report yourself first)" if awol else ""), "ship", None,
                 navy and ctx is None and not awol))
    if not navy:
        opts.append(("Passage out to the fleet", "fleet", None, True))
    _menu(ps, who, "Naval base", lines, opts, lambda v: _port_choice(ps, who, v))


def _port_choice(ps, who, v):
    from . import naval as NV
    g = ps.game
    if v == "back":
        return NV.return_aboard(ps)
    if v == "turnin":
        return turn_yourself_in(ps, who)
    if v in ("ship", "fleet"):
        if g.__dict__.get("awol"):
            turn_yourself_in(ps, who)          # asking the port director for a berth is reporting in
        g.msg(f"{who.last_name}: 'There's a boat going out now. Here are your orders.'", "radio")
        return ps._to_the_fleet()


# ---------------------------------------------------------------- the surgeon
def _surgeon(ps, who):
    g = ps.game
    p = g.player
    worst = p.body.worst_wound() if hasattr(p.body, "worst_wound") else None
    if worst is None:
        g.msg(f"{who.last_name} looks you up and down. 'You're fine. Out of my way.'", "info")
        return
    g.msg(f"{who.last_name}: 'Sit down there. Let's have a look at you.'", "info")
    _time_passes(ps, 300)


MENUS = {"adjutant": _adjutant, "clerk": _clerk, "mp": _mp, "armourer": _armourer, "cook": _cook,
         "chaplain": _chaplain, "politruk": _politruk, "motor_sergeant": _motor, "ops_officer": _ops, "port_officer": _port,
         "surgeon": _surgeon}


# ============================================================================ the adjutant's orders
def MT_ROUNDS():
    from .maintenance import TRUCK_CARGO
    return TRUCK_CARGO


def _hq_sectors(game, side, max_d=6, exclude_here=True):
    st = game.strategic
    s0 = game.sector
    out = []
    for s in st.sectors():
        if not s.playable or s.control != side:
            continue
        d = abs(s.x - s0.x) + abs(s.y - s0.y)
        if d > max_d or (exclude_here and d == 0):
            continue
        if s.installs(side, "hq"):
            out.append((d, s))
    out.sort(key=lambda t: t[0])
    return [s for _, s in out]


def _front_sector(game):
    st = game.strategic
    p = game.player
    s0 = game.sector
    best = None
    for s in st.sectors():
        if not s.playable or s.control != p.side:
            continue
        try:
            front = st.is_front(s, p.side)
        except Exception:
            front = False
        if not front:
            continue
        d = abs(s.x - s0.x) + abs(s.y - s0.y)
        if best is None or d < best[0]:
            best = (d, s)
    return best[1] if best else None


def _patrol_target(game):
    st = game.strategic
    p = game.player
    s0 = game.sector
    best = None
    for s in st.sectors():
        if not s.playable or s.control is None or s.control == p.side:
            continue
        d = abs(s.x - s0.x) + abs(s.y - s0.y)
        if d > 5:
            continue
        if not any((n := st.at(s.x + dx, s.y + dy)) is not None and n.control == p.side
                   for dx, dy in EDGE_VEC.values()):
            continue
        if best is None or d < best[0]:
            best = (d, s)
    return best[1] if best else None


def _issuer(game, who):
    return dict(name=_name(who), role=who.role, rank=max(10, who.rank),
                sector=(game.sector.x, game.sector.y), base=who.ai.get("base"))


def _order_rejoin(game, who, s):
    return dict(kind="rejoin", sector=(s.x, s.y), text=f"Go up and join the company holding {s.name}.",
                menu=f"Rejoin the line: a company in {s.name} is short of men", reward=dict(merit=1, rep=2),
                hours=6, by=_issuer(game, who), report_to_any=False)


def offer_orders(game, who):
    """What the adjutant has on his board for a man of your rank and service, here and now."""
    from .data.roles import service_of
    p = game.player
    sv = service_of(p.role)
    rng = game.rng
    out = []
    if sv == "navy":
        from . import naval as NV
        port = NV.nearest_port(game)
        if port is not None and NV.ship_ashore(game) is None:      # (on liberty you've a ship already)
            out.append(dict(kind="report_port", sector=(port.x, port.y),
                            text=f"Report to the port director at the naval base, {port.name}, for a ship.",
                            menu=f"Report to the naval base at {port.name} for a ship", reward=dict(merit=0, rep=1),
                            hours=12, by=_issuer(game, who), report_to_any=False))
    if sv == "air":
        af = [s for s in _all_with(game, "airfield")]
        if af:
            s = af[0]
            out.append(dict(kind="report_airfield", sector=(s.x, s.y),
                            text=f"Report to the operations officer at the airfield, {s.name}.",
                            menu=f"Report to the airfield at {s.name} for flying duties", reward=dict(merit=0, rep=1),
                            hours=12, by=_issuer(game, who), report_to_any=False))
    hqs = _hq_sectors(game, p.side)
    if hqs:
        s = hqs[min(len(hqs) - 1, rng.randint(0, 2))]
        d = abs(s.x - game.sector.x) + abs(s.y - game.sector.y)
        out.append(dict(kind="dispatch", sector=(s.x, s.y),
                        text=f"Carry dispatches to the headquarters in {s.name} and hand them to an officer there.",
                        menu=f"Carry dispatches to headquarters in {s.name} ({d} sector{'s' if d != 1 else ''})",
                        reward=dict(merit=2 + d, rep=3, credit=10 + 5 * d), hours=2 + 2 * d, by=_issuer(game, who),
                        report_to_any=False))
    tgt = _patrol_target(game)
    if tgt is not None and p.rank >= 1:
        out.append(dict(kind="patrol", sector=(tgt.x, tgt.y), stage="out",
                        text=f"Patrol into {tgt.name}, see what's there, and come back and report.",
                        menu=f"Patrol into enemy ground at {tgt.name} and report back",
                        reward=dict(merit=5, rep=4, credit=15), hours=6, by=_issuer(game, who)))
    fs = _front_sector(game)
    if fs is not None and (fs.x, fs.y) != (game.sector.x, game.sector.y) and sv == "army":
        out.append(_order_rejoin(game, who, fs))
    # the tanks up the road want shells, and there's a truck to take them
    if sv == "army" and (staff_here(game, "motor_sergeant") or who.role == "motor_sergeant"):
        run = supply_run_order(game, who)
        if run is not None:
            out.append(run)
    # a guard at this base: the thing there's always someone needed for
    post = _guard_post(game, who)
    if post is not None:
        mins = rng.choice((20, 30, 40))
        out.append(dict(kind="guard", sector=(game.sector.x, game.sector.y), post=post, secs=mins * 60,
                        text=f"Stand guard at {who.ai.get('base', 'the base')} for {mins} minutes.",
                        menu=f"Guard duty here: {mins} minutes on the gate", reward=dict(merit=1, rep=2),
                        hours=2, by=_issuer(game, who)))
    return out[:4]


def _all_with(game, kind):
    p = game.player
    s0 = game.sector
    out = [(abs(s.x - s0.x) + abs(s.y - s0.y), s) for s in game.strategic.sectors()
           if s.playable and s.control == p.side and s.installs(p.side, kind)]
    out.sort(key=lambda t: t[0])
    return [s for _, s in out]


def _guard_post(game, who):
    from .spawn import free_tile_near
    mp = [a for a in staff_here(game, "mp") if a.ai.get("base") == who.ai.get("base")]
    if mp:
        pt = free_tile_near(game, mp[0].x + 1, mp[0].y, 3)
        return pt
    return free_tile_near(game, who.x + 3, who.y, 4)


def give_order(ps, who, o):
    g = ps.game
    o = dict(o)
    o["issued"] = g.turn
    o["_priority_checked"] = g.turn
    o["deadline"] = g.turn + int(o.get("hours", 4) * HOUR)
    o.setdefault("stage", "go")
    if o["kind"] == "dispatch":
        from .entities import Item
        it = Item("dispatches")
        it.data = dict(to=o["sector"], by=o["by"]["name"])
        if g.player.add_item(it) is None:
            g.map.add_item(g.player.x, g.player.y, it)
    if o["kind"] == "guard":
        o["start"] = None
        o["away"] = 0
    if o["kind"] == "supply_run" and o.get("truck") is None:
        t = _truck_for(ps, who, o)
        if t is None:
            return
        o["truck"] = t.id
        g.msg(f"A {t.vt.name} is brought round for you, loaded with shells. (e beside it to get in and drive)", "info")
    g.__dict__["base_order"] = o
    g.msg(f"{who.last_name}: '{o['text']}'", "radio")
    g.update_orders(force=True)
    ps.act(150)


def _done(game, o) -> bool:
    return o.get("stage") == "done"


def order_line(game):
    o = game.__dict__.get("base_order")
    if not o:
        return None
    if _done(game, o):
        return f"Report back to {o['by']['name']} at {o['by'].get('base') or 'headquarters'}: done."
    from .orders import left_words
    left = max(0, o["deadline"] - game.turn)
    when = left_words(game, left)
    if o["kind"] == "patrol" and o.get("stage") == "back":
        return f"Get back and report what you saw in {_sector_name(game, o.get('scouted_name') or o['sector'])}. " \
               f"({when} left)"
    if o["kind"] == "guard" and o.get("start") is not None:
        rest = max(0, o["start"] + o["secs"] - game.turn)
        return f"On guard at {o['by'].get('base')}: {left_words(game, rest)} to go. Stay at your post."
    return f"{o['text']} ({when}{'' if when in ('overdue', 'any moment', 'hours yet') else ' left'})"


def _sector_name(game, key):
    s = game.strategic.at(*key)
    return s.name if s is not None else "there"


def update(game):
    """Every few seconds: how the adjutant's orders are going."""
    o = game.__dict__.get("base_order")
    if not o or _done(game, o):
        return
    from .orders import deferred, pause_deadline
    blocked = deferred(game, "base")
    pause_deadline(game, o, blocked)
    if blocked:
        return
    p = game.player
    here = (game.sector.x, game.sector.y)
    tgt = tuple(o.get("sector") or here)
    k = o["kind"]
    if game.turn > o["deadline"]:
        game.msg(f"You've run out of time on {o['by']['name']}'s orders. He'll have words.", "warn")
        game.duty.rep -= 4
        game.duty.strikes += 1
        game.__dict__["base_order"] = None
        game.update_orders(force=True)
        return
    if k == "rejoin" and here == tgt:
        sq = _best_squad_here(game)
        if sq is not None:
            _join(game, sq)
            game.msg(f"You find {sq.name} in the line and report to {_name(sq.leader) if sq.leader else 'the sergeant'}. "
                     f"'About time. Get in a hole.'", "radio")
        _reward(game, o)
        game.__dict__["base_order"] = None
        game.update_orders(force=True)
        return
    if k == "patrol":
        if o["stage"] == "out" and here == tgt:
            o.setdefault("arrived", game.turn)
            seen = any(a.side != p.side and a.alive and p in getattr(a, "visible", ()) or
                       (a.side != p.side and a.alive and a in getattr(p, "visible", ()))
                       for a in game.actors)
            if seen or game.turn - o["arrived"] > 180:
                o["stage"] = "back"
                o["scouted_name"] = tgt
                o["sector"] = o["by"]["sector"]
                s = game.strategic.at(*tgt)
                if s is not None:
                    s.__dict__["scouted"] = game.turn
                game.msg("You've seen enough. Now get back and report it.", "info")
                game.update_orders(force=True)
        return
    if k == "supply_run":
        return _supply_run_update(game, o, here == tgt)
    if k == "guard" and here == tgt:
        post = tuple(o["post"])
        d = max(abs(p.x - post[0]), abs(p.y - post[1]))
        if o.get("start") is None:
            if d <= 2:
                o["start"] = game.turn
                game.msg("You take up your post. (z or Enter to stand your guard)", "info")
                game.update_orders(force=True)
            return
        if d > 4:
            o["away"] += 10
            if o["away"] > 90:
                game.msg("The sergeant of the guard finds your post empty.", "warn")
                game.duty.rep -= 5
                game.duty.strikes += 1
                game.__dict__["base_order"] = None
                game.update_orders(force=True)
                return
        if game.turn >= o["start"] + o["secs"]:
            o["stage"] = "done"
            game.msg("Your relief comes. Go and tell the adjutant.", "info")
            game.update_orders(force=True)


def excused(game, why):
    """You've been taken out of it through no doing of your own - carried off wounded, captured: the orders
    you had lapse, and a ship you were ashore from sails without you, which nobody calls desertion."""
    o = game.__dict__.get("base_order")
    if o:
        game.__dict__["base_order"] = None
        game.msg(f"({o['by']['name']}'s orders go to somebody else.)", "info")
    duty = getattr(game, "duty", None)
    if duty is not None and getattr(duty, "task", None) is not None:
        duty.task = None
    ctx = game.__dict__.get("ship_ashore")
    if ctx:
        game.__dict__["ship_ashore"] = None
        game.__dict__["lost_ship"] = ctx.get("ship_name")


def back_in_service(game, how):
    """Back from hospital or a prison camp: a sailor or an airman is sent to report to his own service, not
    handed a rifle."""
    from .data.roles import service_of
    p = game.player
    sv = service_of(p.role)
    by = dict(name="the replacement depot", role="clerk", sector=(game.sector.x, game.sector.y),
              base="the replacement depot")
    o = None
    if sv == "navy":
        from . import naval as NV
        port = NV.nearest_port(game)
        if port is not None:
            o = dict(kind="report_port", sector=(port.x, port.y), by=by, report_to_any=False,
                     text=f"Report to the port director at the naval base, {port.name}, for a ship.",
                     reward=dict(merit=0, rep=1), hours=48)
    elif sv == "air":
        af = _all_with(game, "airfield")
        if af:
            o = dict(kind="report_airfield", sector=(af[0].x, af[0].y), by=by, report_to_any=False,
                     text=f"Report to the operations officer at the airfield, {af[0].name}.",
                     reward=dict(merit=0, rep=1), hours=48)
    if o is None:
        return False
    o["issued"] = game.turn
    o["deadline"] = game.turn + int(o["hours"] * HOUR)
    o["stage"] = "go"
    game.__dict__["base_order"] = o
    game.msg(f"Your papers say: {o['text']}", "radio")
    game.update_orders(force=True)
    return True


def left_behind(game, riding):
    """You're crossing into the next sector without the vehicle the motor pool signed out to you: it doesn't
    wait there for you (the motor pool sends a driver for it) - and a supply run without its truck is over."""
    p = game.player
    o = game.__dict__.get("base_order")
    if o and o["kind"] == "supply_run" and not _done(game, o):
        t = _supply_truck(game, o)
        if t is not None and t is not riding:
            game.msg(f"You've left the {t.vt.name} and its shells behind. The motor pool sends a driver for it, and "
                     f"the supply run goes to somebody else. {o['by']['name']} will hear about it.", "warn")
            game.duty.rep -= 2
            game.__dict__["base_order"] = None
            game.update_orders(force=True)
    for v in game.vehicles:
        if v.ai.get("issued_to") == p.id and v is not riding and not v.dead and not v.ai.get("player_run"):
            v.ai.pop("issued_to", None)
            game.msg(f"You leave the {v.vt.name} you signed out; the motor pool will collect it.", "info")


def _supply_truck(game, o):
    return next((v for v in game.vehicles if v.id == o.get("truck") and not v.dead), None)


def _supply_run_update(game, o, arrived):
    from . import maintenance as MT
    p = game.player
    t = _supply_truck(game, o)
    if not arrived:
        return
    if t is None:
        if not o.get("told_no_truck"):
            o["told_no_truck"] = True
            game.msg("You're here - but the shells aren't. The truck is wherever you left it.", "warn")
        return
    tanks = [v for v in game.vehicles if v.side == p.side and v is not t and not v.dead and not v.abandoned
             and v.vt.vtype in ("tank", "td", "spg") and (v.vt.ap or v.vt.he)]
    if not o.get("primed"):
        o["primed"] = True
        o["arrived_turn"] = game.turn
        # they've been in action - it's why you were sent: the racks are half empty
        for v in tanks:
            if v.player_crewed or MT.shells_short(v) > 0:
                continue
            ap, he, _ = MT.full_load(v)
            v.ap = int(ap * game.rng.uniform(0.25, 0.6))
            v.he = int(he * game.rng.uniform(0.25, 0.6))
        if tanks:
            game.msg("The tanks are here somewhere, laagered up and nearly out. Get the truck to them.", "info")
            game.update_orders(force=True)
    got = t.ai.get("delivered", 0)
    full_up = got >= 10 and not any(MT.shells_short(v) > 0 and abs(v.x - t.x) + abs(v.y - t.y) <= 30 for v in tanks)
    if got >= o.get("need", 40) or (t.ai.get("cargo", 0) <= 0 and got > 0) or full_up:
        game.msg(f"The last of the rounds go up into the turrets. A tank commander leans down: 'Just in time. Tell "
                 f"your sergeant thanks.'", "radio")
        _reward(game, o)
        game.__dict__["base_order"] = None
        game.update_orders(force=True)
        return
    if not tanks and game.turn - o.get("arrived_turn", game.turn) > 60 and t.near(p.x, p.y) <= 2:
        game.msg("The tanks have moved on. An officer has your load dumped at the ammunition point instead.", "info")
        o["reward"] = {k: v // 2 for k, v in o.get("reward", {}).items()}
        t.ai["cargo"] = 0
        _reward(game, o)
        game.__dict__["base_order"] = None
        game.update_orders(force=True)


def _reward(game, o, who=None):
    r = o.get("reward", {})
    game.command.merit += r.get("merit", 0)
    game.duty.rep += r.get("rep", 0)
    if r.get("credit"):
        from .qmui import add_credit
        add_credit(game, r["credit"])
    bits = []
    if r.get("credit"):
        bits.append(f"+{r['credit']} credit")
    if r.get("merit", 0) >= 3:
        bits.append("a line in your record")
        from .orders import reward_record
        reward_record(game, f"{o['by']['name']}: orders carried out - {o.get('menu') or o.get('text', '')}")
    game.msg("Well done." + (f" ({', '.join(bits)})" if bits else ""), "good")
    try:
        game.command.consider_promotion(game, why="orders well carried out")
    except Exception:
        pass


def complete(ps, who):
    g = ps.game
    o = g.__dict__.get("base_order")
    if not o:
        return
    g.msg(f"{who.last_name} ticks your name off the board. 'Good.'", "radio")
    _reward(g, o, who)
    g.__dict__["base_order"] = None
    g.update_orders(force=True)
    ps.act(150)


def _deliverable(game, who) -> bool:
    o = game.__dict__.get("base_order")
    if not o or _done(game, o):
        return False
    here = (game.sector.x, game.sector.y)
    if tuple(o.get("sector") or ()) != here:
        return False
    if o["kind"] == "dispatch":
        return _takes_dispatches(who) or (who.role == "clerk" and not _officers_here(game))
    if o["kind"] == "patrol" and o.get("stage") == "back":
        return who.role in ("adjutant", "intel")
    if o["kind"] == "report_port":
        return who.role == "port_officer"
    if o["kind"] == "report_airfield":
        return who.role == "ops_officer"
    return False


def deliver_dispatches(ps, who):
    g = ps.game
    p = g.player
    o = g.__dict__.get("base_order")
    k = o["kind"]
    if k == "dispatch":
        it = next((i for i in p.inv if i.tid == "dispatches"), None)
        if it is None:
            g.msg(f"{who.last_name}: 'Dispatches? You've lost them? God help you.'", "warn")
            g.duty.rep -= 6
            g.__dict__["base_order"] = None
            g.update_orders(force=True)
            return True
        p.remove_item(it)
        g.msg(f"{who.last_name} breaks the seal, reads, and looks up. 'Right. Thank you.'", "radio")
    elif k == "patrol":
        g.msg(f"You tell {who.last_name} what you saw in {_sector_name(g, o.get('scouted_name') or o['sector'])}. "
              f"{_he(who).capitalize()} marks {who.his} map.", "radio")
    elif k == "report_port":
        g.msg(f"{who.last_name} checks a list. 'There's a berth for you. The boat leaves now.'", "radio")
        _reward(g, o, who)
        g.__dict__["base_order"] = None
        g.update_orders(force=True)
        ps._to_the_fleet()
        return True
    elif k == "report_airfield":
        _reward(g, o, who)
        g.__dict__["base_order"] = None
        g.update_orders(force=True)
        return _ops(ps, who) or True
    _reward(g, o, who)
    g.__dict__["base_order"] = None
    g.update_orders(force=True)
    ps.act(200)
    return True


# ---------------------------------------------------------------- where the orders point, and Enter
def _next_edge(game, target):
    """Which edge of this sector to leave by for `target`: through our own ground if we can."""
    st = game.strategic
    s0 = game.sector
    start = (s0.x, s0.y)
    goal = tuple(target)
    if start == goal:
        return None
    prev = {start: None}
    q = deque([start])
    while q:
        k = q.popleft()
        if k == goal:
            break
        if abs(k[0] - start[0]) + abs(k[1] - start[1]) > 14:
            continue
        for e, (dx, dy) in EDGE_VEC.items():
            nk = (k[0] + dx, k[1] + dy)
            if nk in prev:
                continue
            c = st.at(*nk, create=True)
            if c is None or not c.playable:
                continue
            if nk != goal and c.control not in (game.player.side, None):
                continue
            prev[nk] = (k, e)
            q.append(nk)
    if goal not in prev:
        dx, dy = goal[0] - start[0], goal[1] - start[1]
        return ("E" if dx > 0 else "W") if abs(dx) >= abs(dy) else ("S" if dy > 0 else "N")
    k = goal
    first = None
    while prev[k] is not None:
        k0, e = prev[k]
        first = e
        k = k0
    return first


def order_point(game):
    """(x, y, label) for the arrow and the grease-pencil X."""
    o = game.__dict__.get("base_order")
    if not o:
        return None
    p = game.player
    here = (game.sector.x, game.sector.y)
    tgt = tuple(o.get("sector") or here)
    if _done(game, o):
        tgt = tuple(o["by"]["sector"])
    if tgt != here:
        e = _next_edge(game, tgt)
        if e is None:
            return None
        from .orders import exit_point
        x, y = exit_point(game, e)
        return x, y, f"to {_sector_name(game, tgt)}"
    if o["kind"] == "guard" and not _done(game, o):
        x, y = o["post"]
        return x, y, "your post"
    if o["kind"] == "supply_run":
        t = _supply_truck(game, o)
        if t is not None and p.vehicle is not t:
            return t.x, t.y, "the truck"
        c = _thirsty_tank(game)
        if c is not None:
            return c.x, c.y, "the tanks"
        return None
    who = _who_to_see(game, o)
    if who is not None:
        return who.x, who.y, f"{who.role_name.lower()}"
    return None


def _thirsty_tank(game):
    from . import maintenance as MT
    p = game.player
    c = [v for v in game.vehicles if v.side == p.side and not v.dead and not v.abandoned
         and v.vt.vtype in ("tank", "td", "spg") and MT.shells_short(v) > 0]
    return min(c, key=lambda v: abs(v.x - p.x) + abs(v.y - p.y)) if c else None


def _takes_dispatches(a) -> bool:
    """Who can sign for dispatches: the staff officers - or, with them gone, any line officer (not the doctor,
    not the padre)."""
    return a.alive and a.active and a.rank >= 8 and (a.role in ("adjutant", "intel", "ops_officer", "port_officer") or
                                                     a.role not in ("surgeon", "chaplain", "politruk", "medic"))


def _officers_here(game):
    return [a for a in game.actors if a.side == game.player.side and not a.is_player and _takes_dispatches(a)]


def _who_to_see(game, o):
    if _done(game, o) or (o["kind"] == "patrol" and o.get("stage") == "back"):
        cands = staff_here(game, "adjutant") or staff_here(game, "intel")
    elif o["kind"] == "dispatch":
        cands = staff_here(game, "adjutant") or staff_here(game, "intel") or _officers_here(game) or \
            staff_here(game, "clerk")                    # (the clerk signs, and passes them up)
    elif o["kind"] == "report_port":
        cands = staff_here(game, "port_officer")
    elif o["kind"] == "report_airfield":
        cands = staff_here(game, "ops_officer")
    else:
        return None
    p = game.player
    return min(cands, key=lambda a: abs(a.x - p.x) + abs(a.y - p.y)) if cands else None


def order_plan(ps):
    """(what Enter does, how) for the adjutant's orders, or None."""
    g = ps.game
    o = g.__dict__.get("base_order")
    if not o:
        return None
    p = g.player
    here = (g.sector.x, g.sector.y)
    tgt = tuple(o.get("sector") or here)
    if _done(g, o):
        tgt = tuple(o["by"]["sector"])
    if o["kind"] == "supply_run" and not _done(g, o):
        t = _supply_truck(g, o)
        if t is not None and p.vehicle is None:
            return (f"go to the {t.vt.name} and get in",
                    lambda: ps._go_to_vehicle(t, lambda: ps._enter_vehicle(t)))
        if t is not None and p.vehicle is t:
            where = f"to {_sector_name(g, tgt)}, {_next_edge(g, tgt)} edge" if tgt != here else "up to the tanks"
            return (f"drive it {where} yourself: follow the arrow", lambda: None)
    if tgt != here:
        e = _next_edge(g, tgt)
        if e is None:
            return None
        from .orders import exit_point
        x, y = exit_point(g, e)
        return (f"head for {_sector_name(g, tgt)} ({e})",
                lambda: ps.start_travel(x, y, then=lambda: ps._travel_chosen(e)))
    if o["kind"] == "guard" and not _done(g, o):
        post = tuple(o["post"])
        if max(abs(p.x - post[0]), abs(p.y - post[1])) > 2:
            return "go to your post", lambda: ps.start_travel(post[0], post[1], stop_short=0)
        rest = max(60, (o.get("start") or g.turn) + o["secs"] - g.turn)
        return "stand your guard", lambda: _time_passes(ps, rest, "You stand your guard.")
    who = _who_to_see(g, o)
    if who is not None:
        return (f"go to the {who.role_name.lower()}",
                lambda: ps.start_travel(who.x, who.y, then=lambda: talk(ps, who), stop_short=1))
    return None
