"""The secret war: agents, their covers, their missions, their radios, and the aircraft that supplied them.

An agent is a career (data/agents.py: an SOE organiser, a wireless operator, a courier, a Jedburgh, an
OSS saboteur or spy, a Cichociemny, a partisan organiser, an Abwehr man, one of Skorzeny's commandos...)
with a cover identity built for the country he's dropped into - a local name, a trade that explains
him, the papers that trade needs - and a mission drawn from what that career did.

The radio is the heart of it.  A wireless set (a B2 suitcase, a Paraset, an SSTR-1, a Soviet Sever)
talks to London or Moscow in Morse: a report, a request for a drop, a request for a pick-up.  Every
minute on the air is a minute the enemy's direction-finders have to take bearings: enough minutes near
one place and a detector car and a squad of field police come to look (the Funkabwehr in the West, the
NKVD's radio service in the East).  Move between transmissions and they start again.

A drop is real: a special-duties squadron (fires.Squadron) sends an aircraft; it comes over the field at
the time given - at night - and drops only if the reception committee's lights are there (or the S-Phone
talks it in).  The containers land where they land, with what an SOE or partisan load really held, and
must be got away before the enemy comes to see what the aircraft was doing.
"""
from __future__ import annotations

import math

from .constants import other_side
from .data.agents import (CAREERS, CIRCUITS, CONTAINER_LOADS, FEMALE_TRADES, FIELD_NAMES, LOCAL_NAMES, MISSIONS,
                          PAPERS, SPECIAL_DUTIES, TRADES)

DF_ALARM = 1100          # seconds on the air near one place before the detector car is sent
DF_MOVE = 60             # tiles you must move between transmissions for them to start again
TX_TIME = {"report": 600, "drop": 300, "situation": 240}


def _state(game) -> dict:
    return game.__dict__.setdefault("agent", {"df": 0.0, "df_pos": None, "tx": None, "drops": [],
                                             "sent": 0, "hunt": None})


def cover(game):
    return game.__dict__.get("agent", {}).get("cover")


def base_city(p) -> str:
    """Where the traffic goes: London, Moscow, Berlin, Tokyo."""
    return {"ussr": "Moscow", "germany": "Berlin", "japan": "Tokyo", "italy": "Rome", "usa": "London",
            "poland": "London", "hungary": "Budapest", "finland": "Helsinki"}.get(p.nation, "London")


# ============================================================================ careers and covers
def career_for(game, p) -> str:
    """What sort of agent you are: your unit's kind if it says (SOE, OSS, the Cichociemni), else one of your
    nation's careers in service this year."""
    rng = game.rng
    ut = p.__dict__.get("unit_type")
    year = game.year
    cands = [k for k, c in CAREERS.items() if p.nation in c["nations"] and c["years"][0] <= year < c["years"][1]]
    if ut:
        by_unit = [k for k in cands if ut in CAREERS[k]["unit_types"]]
        cands = by_unit or cands
    if not cands:
        cands = [k for k, c in CAREERS.items() if c["years"][0] <= year < c["years"][1]
                 and any(n in c["nations"] for n in _allies_of(game, p))] or ["soe_organiser"]
    # Operation Greif only in the Ardennes
    if game.theatre_id != "bastogne44":
        cands = [k for k in cands if k != "greif"] or cands
    elif p.nation == "germany" and "greif" in cands and rng.random() < 0.7:
        return "greif"
    return rng.choice(cands)


def _allies_of(game, p):
    from .data.theatres import THEATRES
    return [n for n, _w in THEATRES[game.theatre_id]["sides"][p.side]] if game.theatre_id in THEATRES else [p.nation]


def make_cover(game, p, career):
    """A legend: a local name, a trade, a story, papers.  (A Jedburgh or a Greif commando has none: they
    came in uniform - their own, or the enemy's.)"""
    rng = game.rng
    c = CAREERS[career]
    lang = getattr(game.sector, "lang", None) or "fr"
    st = _state(game)
    circuit = rng.choice(CIRCUITS)
    field = rng.choice(FIELD_NAMES[bool(p.female)])
    cv = dict(career=career, circuit=circuit, field=field, lang=lang, service=c["service"])
    if c.get("uniform"):
        cv.update(name=None, trade=None, story=("dropped in uniform" if c["uniform"] is True else
                                                "in an American uniform, with an American's papers"),
                  papers=[])
        st["cover"] = cv
        return cv
    first_m, first_f, last = LOCAL_NAMES.get(lang, LOCAL_NAMES["fr"])
    name = f"{rng.choice(first_f if p.female else first_m)} {rng.choice(last)}".strip()
    trades = (FEMALE_TRADES + TRADES[:3] + TRADES[5:6]) if p.female else TRADES
    trade, story, papers, tools = rng.choice(trades)
    cv.update(name=name, trade=trade, story=story, papers=list(papers), tools=list(tools),
              card=PAPERS.get(lang, "identity card"))
    st["cover"] = cv
    from .entities import Item
    for pid in papers:
        p.add_item(Item(pid))
    for tid in tools:
        p.add_item(Item(tid, 30 if tid == "francs" else 1))
    return cv


MILITARY = {"dogtags", "orders", "brassard", "shovel", "field_orders", "whistle", "helmet"}


def _plain_clothes(game, p, career):
    """Out of everything that says soldier: identity tags, webbing, a service pack, the issue pistol - and what's
    left goes into a jacket's pockets and a civilian's bag."""
    from .entities import Item
    c = CAREERS[career]
    career_guns = {t for t in c["kit"] if _kind(t) == "gun"}
    inv = p.invent
    body = inv.slots.get("body")
    held = p.weapon
    items = [it for it in p.inv if it is not body and it.t.kind != "container"]

    def military(it):
        return (it.tid in MILITARY or it.t.tool in ("dogtags", "orders", "shovel") or
                (it.t.kind == "gun" and career_guns and it.tid not in career_guns) or
                (it.t.kind in ("mag", "clip", "ammo") and career_guns and not _fits_any(it, career_guns)) or
                (it.t.kind == "armor" and it.t.slot == "head"))
    keep = [it for it in items if not military(it)]
    for it in items:
        p.remove_item(it)
    for slot in ("rig", "pack", "head"):
        inv.slots[slot] = None
    rig = Item("coat_pockets")
    inv.slots["rig"] = rig
    rig.where = "rig"
    bag = Item("suitcase" if any(_tool(t) == "wireless" for t in c["kit"]) else "shoulder_bag")
    inv.slots["pack"] = bag
    bag.where = "pack"
    for it in keep:
        if p.add_item(it) is None and game.map is not None:
            game.map.add_item(p.x, p.y, it)
    if held is not None and held in keep:
        p.wield(held)


def _kind(tid):
    from .data.items import ITEMS
    return ITEMS[tid].kind if tid in ITEMS else None


def _tool(tid):
    from .data.items import ITEMS
    return ITEMS[tid].tool if tid in ITEMS else None


def _fits_any(it, guns):
    from .data.items import ITEMS
    for g in guns:
        t = ITEMS.get(g)
        if t is not None and t.cal and it.t.cal == t.cal:
            return True
    return False


def equip(game, p, career):
    """The kit the career went in with (on top of the agent's papers and clothes)."""
    from .data.items import ITEMS
    from .entities import Item
    c = CAREERS[career]
    if not c.get("uniform"):
        _plain_clothes(game, p, career)
    elif any(_kind(t) == "gun" for t in c["kit"]):
        for it in list(p.inv):
            if it.t.kind == "gun" or it.t.kind in ("mag", "clip", "ammo"):
                p.remove_item(it)
    for tid, n in c["kit"].items():
        if tid not in ITEMS:
            continue
        t = ITEMS[tid]
        if t.kind == "gun":
            it = Item(tid)
            if getattr(t, "magtype", None) and it.loaded == 0:
                it.loaded = t.mag
            if p.weapon is None:
                p.add_item(it)
                p.wield(it)
            else:
                p.add_item(it)
        elif t.kind == "ammo":
            p.add_item(Item(tid, 12 * n))
        else:
            if t.stackable or tid in ("francs", "zloty", "roubles"):
                p.add_item(Item(tid, n))
            else:
                for _ in range(n):
                    p.add_item(Item(tid))
    if c.get("uniform"):
        body = p.invent.slots.get("body")
        if body is not None and body.tid == "civvies":
            p.invent.slots["body"] = None
        p.ai.pop("disguise", None)


def cover_lines(game) -> list[str]:
    """For the cover page (@): who you are, and who you're supposed to be."""
    cv = cover(game)
    if cv is None:
        return []
    from .data.agents import RESISTANCE
    c = CAREERS.get(cv["career"]) or RESISTANCE[cv["career"]]
    out = [f"You: {c['name']} - {cv['service']}.", f"Circuit {cv['circuit']}; your field name is {cv['field']}."]
    if cv.get("name"):
        out += [f"Your cover: {cv['name']}, {cv['trade']} - {cv['story']}.",
                f"Papers: {cv['card']}" + (", " + ", ".join(_paper_name(x) for x in cv["papers"]) if cv["papers"]
                                           else "") + "."]
    else:
        out.append(f"No cover: {cv['story']}.")
    out.append(c["desc"])
    ms = game.__dict__.get("mission") or {}
    if ms.get("kind") == "agent" and ms.get("task"):
        out.append(f"Mission: {MISSIONS[ms['task']]['name']}. {ms.get('text', '')}")
    st = _state(game)
    if st.get("sent"):
        out.append(f"Messages sent this mission: {st['sent']}.")
    return out


def _paper_name(pid):
    from .data.items import ITEMS
    return ITEMS[pid].name if pid in ITEMS else pid


def papers_bonus(game, p) -> float:
    """At a papers check: a cover with the right documents for its trade, and the language, help."""
    from .skills import level
    cv = cover(game)
    b = 0.0
    if cv is not None and cv.get("name"):
        have = {i.tid for i in p.inv}
        b += 0.04 * sum(1 for x in cv.get("papers", ()) if x in have)
        b += 0.03 * sum(1 for x in cv.get("tools", ()) if x in have)
    b += (level(p, "languages") - 5) * 0.03
    return b


def bribe(game, p) -> bool:
    """When the papers don't satisfy him: money, if you have enough, and he's that kind of man."""
    money = next((i for i in p.inv if i.t.tool == "money" and i.count >= 20), None)
    if money is None or game.rng.random() > 0.45:
        return False
    take = min(money.count, game.rng.randint(20, 60))
    p.remove_item(money, take) if take < money.count else p.remove_item(money)
    game.msg(f"You fold {take} notes into your papers. He looks at them for a long moment, pockets them, and "
             f"hands the papers back.", "info")
    return True


# ============================================================================ missions
def setup(game, notes, strip_friends, sid="agent"):
    """The agent's start: career, cover, kit, the mission and its map."""
    from .spawn import edge_band_point, place
    rng = game.rng
    p = game.player
    side = p.side
    enemy = other_side(side)
    strip_friends([])
    if p.squad is not None:
        p.squad.members = [p]
        p.squad.leader = p
        p.squad.player_led = True
    career = career_for(game, p)
    c = CAREERS[career]
    make_cover(game, p, career)
    equip(game, p, career)
    task = rng.choices(list(c["missions"]), list(c["missions"].values()))[0]
    home = game.home_edge(side) or "S"
    x, y = edge_band_point(game, _far_from_enemy(game, enemy), rng, depth=(2, 8))
    game.remove_actor(p)
    place(game, p, x, y, 5)
    if not c.get("uniform"):
        p.ai["disguise"] = True
    elif c["uniform"] == "enemy":
        p.ai["disguise"] = True                          # (an American uniform: the disguise tick allows it)
        p.ai["enemy_uniform"] = True
    ms = dict(kind="agent", task=task, stage="go", home=home, career=career, sid=sid,
              award_for={"steal_plans": "theft of the enemy's plans", "sabotage": "sabotage operation",
                         "receive_drop": "reception of a supply drop", "wireless": "wireless work behind the lines",
                         "eliminate": "operation behind the lines", "rescue_airman": "rescue of an Allied airman",
                         "photograph": "photographic reconnaissance"}.get(task, "work behind the lines"))
    game.mission = ms
    fn = {"steal_plans": _setup_steal, "sabotage": _setup_sabotage, "receive_drop": _setup_drop,
          "wireless": _setup_wireless, "eliminate": _setup_eliminate, "rescue_airman": _setup_airman,
          "photograph": _setup_photograph}[task]
    fn(game, ms, notes)
    if MISSIONS[task]["night"]:
        from .scenarios import _set_night
        _set_night(game)
    cv = cover(game)
    who = (f"You are {cv['name']}, {cv['trade']} - {cv['story']}." if cv.get("name") else
           f"You came in {cv['story']}.")
    notes.insert(0, f"{c['name']}, circuit {cv['circuit']} ('{cv['field']}'). {who}")
    return ms


def _far_from_enemy(game, enemy):
    e = game.home_edge(enemy)
    return {"N": "S", "S": "N", "E": "W", "W": "E"}.get(e, "S")


def _where(game, x, y):
    from .senses import direction_word
    p = game.player
    d = int(round(math.hypot(x - p.x, y - p.y) * 2.2 / 50.0) * 50)
    return f"{direction_word(x - p.x, y - p.y)}, about {max(50, d)} yards"


def _setup_steal(game, ms, notes):
    from .entities import Item
    from .scenarios import _enemy_installation
    enemy = other_side(game.player.side)
    rec = _enemy_installation(game, enemy, "hq") or _enemy_installation(game, enemy)
    doc = Item("op_orders")
    doc.data = dict(side=enemy, unit=f"{game.side_nation(enemy)} headquarters", level=5)
    if rec is not None:
        game.map.add_item(rec["x"], rec["y"], doc)
    ms.update(rec=rec, doc=doc.iid, stage="steal",
              text=f"Steal the operation orders from their headquarters ({_rec_where(game, rec)}) and carry them "
                   f"back to our lines.")
    notes.append("Walk like a local. No rifle where they can see it; don't loiter near sentries; don't run.")


def _rec_where(game, rec):
    return _where(game, rec["x"], rec["y"]) if rec else "somewhere on this map"


def _setup_sabotage(game, ms, notes):
    """A target that matters: a depot, a motor pool, the guns, an airfield - or the railway."""
    from .scenarios import _enemy_installation, _explosive_count
    enemy = other_side(game.player.side)
    m = game.map
    from . import tiles as T
    rail = T.ID.get("rail")
    rails = [] if rail is None else list(zip(*((m.t == rail).nonzero())))
    rec = None
    if rails and game.rng.random() < 0.6:
        x, y = rails[game.rng.randrange(len(rails))]
        ms.update(target="rail", tx=int(x), ty=int(y), stage="plant",
                  text=f"Cut the railway ({_where(game, x, y)}): charges under the rails, time pencils set, and "
                       f"be gone before they go off.")
    else:
        for kind in ("depot", "motor_pool", "artillery", "airfield", "aa", "hq"):
            rec = _enemy_installation(game, enemy, kind)
            if rec is not None:
                break
        base = _explosive_count(m, rec)
        ms.update(target="rec", rec=rec, base=base, stage="plant",
                  text=f"Blow up the enemy {rec['kind'].replace('_', ' ') if rec else 'depot'} "
                       f"({_rec_where(game, rec)}) with timed charges - and be well away when they go.")
    notes.append("Squeeze the time pencil, pull the strip, walk away. Ten minutes, give or take - they run fast in "
                 "the heat and slow in the cold.")


def _setup_drop(game, ms, notes):
    """The dropping zone: an open field; a reception committee of the local resistance waiting in the hedge."""
    rng = game.rng
    p = game.player
    dz = _open_field(game, p.x, p.y)
    ms.update(dz=dz, stage="dz",
              text=f"Get to the dropping zone ({_where(game, *dz)}), lay out the lights when you hear the aircraft, "
                   f"and get the containers away before the enemy arrives.")
    if ms.get("band"):
        _state(game)["committee"] = p.squad.id           # the band is the reception committee
        from .entities import Item
        for a in p.squad.members[:4]:
            a.add_item(Item("signal_torch"))
    else:
        _reception_committee(game, dz)
    when = game.turn + rng.randint(1500, 2400)
    schedule_drop(game, dz, when, confirmed=True)
    notes.append("London confirmed on the BBC: \"Les sanglots longs des violons...\" The aircraft comes whether "
                 "you're there or not - but it won't drop without the lights.")


def _setup_wireless(game, ms, notes):
    need = game.rng.randint(2, 3)
    ms.update(stage="send", need=need,
              text=f"Transmit your {need} messages to {base_city(game.player)} (a to use the set, or R), then get off "
                   f"this map. Move "
                   f"between transmissions - the detector cars are listening.")
    notes.append("Twenty minutes on the air in one place and they'll have you. The aerial goes up in an attic "
                 "or a hedge; the set goes back in the suitcase the moment you're done.")


def _setup_eliminate(game, ms, notes):
    """A man killing the network: an SD officer, a Gestapo informer, a collaborator - with a guard or two."""
    from .scenarios import _enemy_installation
    from .spawn import make_soldier, place, free_tile_near
    from .ai import Order, Squad
    rng = game.rng
    p = game.player
    enemy = other_side(p.side)
    nat = game.side_nation(enemy)
    rec = _enemy_installation(game, enemy, "hq") or _enemy_installation(game, enemy)
    m = game.map
    if rec is not None:
        x, y = rec["x"], rec["y"]
    else:
        x, y = m.w // 2 + rng.randint(-20, 20), m.h // 2 + rng.randint(-15, 15)
    pt = free_tile_near(game, x, y, 8) or (x, y)
    sq = Squad(enemy, nat, "staff", "the target")
    sq.no_count = True
    sq.order = Order("hold", target=pt, radius=3)
    sq.arrived = True
    who = {"germany": ("SD officer", "officer", 10), "japan": ("Kempeitai officer", "officer", 9),
           "italy": ("OVRA agent", "officer", 8), "ussr": ("NKVD officer", "officer", 9)}.get(nat, ("officer", "officer", 9))
    t = make_soldier(game, nat, who[1], rank=who[2])
    t.ai["mark"] = True
    t.squad = sq
    sq.members.append(t)
    place(game, t, pt[0], pt[1], 2)
    for _ in range(rng.randint(1, 2)):
        g2 = make_soldier(game, nat, "mp" if nat == "germany" else "rifleman")
        g2.squad = sq
        sq.members.append(g2)
        place(game, g2, pt[0], pt[1], 4)
    sq.leader = t
    sq.initial = len(sq.members)
    game.squads.append(sq)
    ms.update(stage="kill", mark=t.id, mark_name=t.name,
              text=f"Kill the {who[0]} {t.last_name} ({_where(game, *pt)}), then get clear.")
    notes.append(f"{t.last_name} has broken two circuits this year. Quietly, if it can be done quietly.")


def _setup_airman(game, ms, notes):
    """A bomber crewman who came down last night, hiding in a barn."""
    from .spawn import make_soldier, place, free_tile_near
    from .ai import Order, Squad
    rng = game.rng
    p = game.player
    m = game.map
    nat = {"germany": "uk", "japan": "usa", "italy": "uk", "ussr": "ussr"}.get(p.nation, p.nation)
    if p.side != "allies":
        nat = game.side_nation(p.side)
    x = rng.randint(m.w // 4, 3 * m.w // 4)
    y = rng.randint(m.h // 4, 3 * m.h // 4)
    pt = free_tile_near(game, x, y, 12) or (x, y)
    sq = Squad(p.side, nat, "rifle", "evader")
    sq.no_count = True
    sq.order = Order("hold", target=pt, radius=1)
    sq.arrived = True
    a = make_soldier(game, nat, "air_gunner")
    a.ai["hiding"] = True
    a.squad = sq
    sq.members.append(a)
    sq.leader = a
    sq.initial = 1
    place(game, a, pt[0], pt[1], 1)
    game.squads.append(sq)
    ms.update(stage="find", airman=a.id,
              text=f"Find the airman hiding {_where(game, *pt)}, and get him out with you - off the map toward "
                   f"our lines, or to friendly ground.")
    notes.append("He speaks no French and walks like an American. Keep him close and keep him quiet.")


def _setup_photograph(game, ms, notes):
    from .entities import Item
    p = game.player
    enemy = other_side(p.side)
    recs = [r for r in (getattr(game.map, "gen_positions", None) or []) if r.get("side") == enemy and r.get("rect")]
    need = max(1, min(3, len(recs))) if recs else 0
    if not p.find(lambda i: i.t.tool == "camera"):
        p.add_item(Item("minox"))
    ms.update(stage="photo", need=need or 2, shot=[],
              text=f"Photograph {need or 2} of their positions with the Minox (a, looking at them, within 25 yards) "
                   f"and bring the film home.")
    notes.append("A foot and a half from a page, steady hands. From the hedge across the road, luck.")


# ============================================================================ progress
def update(game, ms, done, friendly_ground, here):
    """Every few seconds (scenarios.update): has the mission moved on?"""
    p = game.player
    task = ms["task"]
    if task == "sabotage":
        _update_sabotage(game, ms, done, friendly_ground, here)
    elif task == "receive_drop":
        _update_drop(game, ms, done, here)
    elif task == "wireless":
        if ms["stage"] == "send" and _state(game)["sent"] >= ms["need"]:
            ms["stage"] = "away"
            ms["text"] = "The traffic's out. Now pack the set and get off this map before the cars come."
            game.update_orders(force=True)
        elif ms["stage"] == "away" and not here:
            done(f"You're clear. {base_city(p)} has your messages; somewhere a staff officer is moving pins on a map.", 8)
    elif task == "eliminate":
        mark = next((a for a in game.actors if a.id == ms["mark"]), None)
        if ms["stage"] == "kill" and (mark is None or not mark.alive):
            ms["stage"] = "away"
            ms["text"] = "It's done. Get clear - off this map."
            game.msg("The man is dead. The network breathes again, for a while.", "good")
            game.update_orders(force=True)
        elif ms["stage"] == "away" and not here:
            done("You get clear. By morning the posters are up: a reward, and a list of hostages.", 9)
    elif task == "rescue_airman":
        a = next((o for o in game.actors if o.id == ms.get("airman")), None)
        if ms["stage"] == "find":
            if a is not None and a.alive and max(abs(a.x - p.x), abs(a.y - p.y)) <= 1:
                _collect_airman(game, a)
                ms["stage"] = "out"
                ms["text"] = "Get him out: off the map toward our lines, or onto friendly ground."
                game.update_orders(force=True)
            elif a is None or not a.alive:
                ms["stage"] = "failed"
                game.msg("The airman is dead. You couldn't reach him in time.", "death")
        elif ms["stage"] == "out":
            if a is not None and a.alive and (not here or friendly_ground):
                done("He shakes your hand at the line and says something you don't understand. He'll fly again.", 9)
            elif a is None or not a.alive:
                ms["stage"] = "failed"
                game.msg("The airman is dead.", "death")
    elif task == "photograph":
        has = p.find(lambda i: i.tid == "film") is not None
        if ms["stage"] == "photo" and len(ms["shot"]) >= ms["need"]:
            from .entities import Item
            if not has:
                p.add_item(Item("film"))
            ms["stage"] = "home"
            ms["text"] = "The film's in your pocket. Now get it home - off this map toward our lines."
            game.update_orders(force=True)
        elif ms["stage"] == "home" and has and (not here or friendly_ground):
            done("The film goes by Lysander to London. Three days later a photo interpreter circles something on a "
                 "print and picks up a telephone.", 9)


def _update_sabotage(game, ms, done, friendly_ground, here):
    from .scenarios import _explosive_count
    m = game.map
    if ms["stage"] == "plant":
        if ms["target"] == "rail" and here:
            from . import tiles as T
            x, y = ms["tx"], ms["ty"]
            cut = sum(1 for dx in range(-4, 5) for dy in range(-4, 5)
                      if m.in_bounds(x + dx, y + dy) and m.t[x + dx, y + dy] != T.ID["rail"] and
                      m.tile(x + dx, y + dy).key in ("crater", "rubble", "rubble_light", "dirt"))
            if cut >= 2 or ms.get("rail_hit"):
                ms["stage"] = "away"
        elif ms["target"] == "rec" and here and ms.get("rec"):
            left = _explosive_count(m, ms["rec"])
            if ms["base"] and left <= ms["base"] * 0.5:
                ms["stage"] = "away"
        if ms["stage"] == "away":
            ms["text"] = "It's gone up. Get clear before they cordon the district."
            game.msg("The explosions roll across the countryside. Somewhere a siren starts.", "good")
            game.update_orders(force=True)
    elif ms["stage"] == "away" and (not here or friendly_ground):
        done("You're clear. The line will be closed for days; the reprisals will last longer.", 9)


def rail_blast(game, x, y):
    """A charge went off on or beside the railway (called from the explosion): a length of track gone."""
    ms = game.__dict__.get("mission") or {}
    if ms.get("kind") == "agent" and ms.get("task") == "sabotage" and ms.get("target") == "rail":
        if abs(x - ms["tx"]) + abs(y - ms["ty"]) <= 30:
            ms["rail_hit"] = True


def _collect_airman(game, a):
    from .entities import Item
    p = game.player
    a.ai.pop("hiding", None)
    if a.squad is not None and a in a.squad.members:
        a.squad.members.remove(a)
        a.squad.gone = not a.squad.members
    a.squad = p.squad
    p.squad.members.append(a)
    p.squad.player_led = True
    body = a.invent.slots.get("body")
    if body is None or body.tid != "civvies":
        c = Item("civvies")
        a.invent.slots["body"] = c
        c.where = "body"
    a.add_item(Item("forged_papers"))
    game.msg(f"A voice from the straw: 'Don't shoot - American!' {a.first_name if hasattr(a, 'first_name') else a.name}"
             f", a waist gunner, sprained ankle. You give him the clothes and the papers. He follows you.", "good")


def _update_drop(game, ms, done, here):
    st = _state(game)
    drop = next((d for d in st["drops"] if d.get("mission")), None)
    if ms["stage"] == "dz" and drop is not None and drop["state"] == "dropped":
        ms["stage"] = "collect"
        ms["text"] = "Containers down. Get them away - your committee will gather them; keep the enemy off."
        rc = _committee(game)
        if rc is not None:
            from .tasks import assign
            assign(game, rc, "drop", by=game.player)
            rc.task["drop"] = drop["id"]
            rc.task["until"] = game.turn + 3600
        game.update_orders(force=True)
    elif ms["stage"] == "dz" and drop is not None and drop["state"] in ("no_lights", "lost"):
        ms["stage"] = "failed"
        ms["text"] = f"No drop. {base_city(game.player)} will try again in the next moon."
        game.msg("The drop's failed.", "warn")
        game.update_orders(force=True)
    elif ms["stage"] == "collect" and drop is not None:
        left = _drop_left(game, drop)
        if left <= max(1, drop["n_items"] * 0.3):
            done("By dawn the containers are in a barn under the hay: Stens, plastic, grenades. Enough for a "
                 "company of the Maquis - and for the next month's sabotage.", 9)


def _drop_left(game, drop):
    m = game.map
    n = 0
    x0, y0 = drop["dz"]
    for (x, y), items in list(getattr(m, "items", {}).items()):
        if abs(x - x0) <= 40 and abs(y - y0) <= 40:
            n += sum(1 for it in items if (it.data or {}).get("drop") == drop["id"])
    return n


# ============================================================================ the resistance on the ground
def _reception_committee(game, dz):
    """Four or five of the local resistance, in the hedge by the field, with torches."""
    from .ai import Order
    from .entities import Item
    from .spawn import make_squad
    p = game.player
    nat = p.nation if p.nation in ("france", "poland", "ussr") else {"uk": "france", "usa": "france"}.get(
        p.nation, game.side_nation(p.side))
    try:
        sq = make_squad(game, p.side, nat, "rifle", dz[0] + 4, dz[1] + 4, name="reception committee")
    except Exception:
        return None
    sq.no_count = True
    sq.order = Order("hold", target=dz, radius=6, issued=game.turn, src="player")
    sq.__dict__["committee"] = True
    for a in sq.members[5:]:
        game.remove_actor(a)
    sq.members = sq.members[:5]
    for a in sq.members:
        c = Item("civvies")
        a.invent.slots["body"] = c
        c.where = "body"
        a.add_item(Item("signal_torch"))
    game.__dict__.setdefault("agent", _state(game))["committee"] = sq.id
    return sq


def _committee(game):
    sid = _state(game).get("committee")
    return next((q for q in game.squads if q.id == sid and q.members), None)


def _open_field(game, x, y):
    """The nearest good dropping zone: open, flat, walkable ground a few hundred yards across."""
    from . import tiles as T
    m = game.map
    best = None
    rng = game.rng
    for _ in range(80):
        cx = max(8, min(m.w - 9, x + rng.randint(-60, 60)))
        cy = max(8, min(m.h - 9, y + rng.randint(-40, 40)))
        sub = m.walk[cx - 6:cx + 7, cy - 6:cy + 7]
        open_ = sub.mean() if sub.size else 0
        trees = sum(1 for dx in range(-6, 7, 3) for dy in range(-6, 7, 3)
                    if not T.SEE[m.t[cx + dx, cy + dy]])
        score = open_ - trees * 0.05 - math.hypot(cx - x, cy - y) / 400
        if best is None or score > best[0]:
            best = (score, cx, cy)
    return (best[1], best[2]) if best else (x, y)


# ============================================================================ the radio
def has_wireless(p):
    return p.find(lambda i: i.t.tool == "wireless") is not None


def radio_options(game) -> list:
    """The wireless set's menu: (label, key, colour, enabled)."""
    p = game.player
    st = _state(game)
    ms = game.__dict__.get("mission") or {}
    busy = st["tx"] is not None
    out = []
    night_word = "tonight" if game.is_night() else "after dark"
    out.append((f"Send a report to {base_city(p)}"
                f" ({TX_TIME['report'] // 60} min on the air)", "report", (220, 200, 140), not busy))
    out.append((f"Request a supply drop here, {night_word} ({TX_TIME['drop'] // 60} min)", "drop", (200, 220, 150),
                not busy and not any(d["state"] == "waiting" for d in st["drops"])))
    if ms.get("kind") == "agent":
        out.append(("Listen for traffic (the skeds, the BBC messages)", "listen", None, True))
    if busy:
        out.append(("Stop transmitting - pack the set", "stop", (240, 170, 120), True))
    return out


def radio_choice(ps, what):
    g = ps.game
    p = g.player
    st = _state(g)
    if what == "stop":
        st["tx"] = None
        g.msg("You pull the aerial down and pack the set into its suitcase.", "info")
        return ps.act(200)
    if what == "listen":
        drops = [d for d in st["drops"] if d["state"] == "waiting"]
        if drops:
            d = drops[0]
            mins = max(0, (d["at"] - g.turn) // 60)
            g.msg(f"The BBC, after the news: personal messages. '{d['phrase']}' - yours. The aircraft will be over the "
                  f"field in about {mins} minutes.", "radio")
        else:
            g.msg("Static, a dance band, the news in French from London. Nothing for you.", "radio")
        return ps.act(300)
    if what == "drop":
        if not _field_ok(g, p.x, p.y):
            g.msg(f"{base_city(p)} won't drop into trees, buildings or water: find an open field first.", "warn")
            return
    secs = TX_TIME[what]
    st["tx"] = dict(what=what, left=secs, pos=(p.x, p.y), start=g.turn)
    g.msg(f"You string the aerial, put on the headphones and start tapping out your call sign. "
          f"({secs // 60} minutes; any key stops.)", "info")
    ps.auto_wait = max(ps.auto_wait, secs)
    ps.mark_interrupt()


def _field_ok(game, x, y):
    from . import tiles as T
    m = game.map
    n = t = 0
    for dx in range(-4, 5, 2):
        for dy in range(-4, 5, 2):
            if m.in_bounds(x + dx, y + dy):
                t += 1
                k = int(m.t[x + dx, y + dy])
                n += bool(m.walk[x + dx, y + dy] and T.SEE[k] and not T.FLOOR[k] and m.water[x + dx, y + dy] == 0)
    return t and n / t >= 0.75


def tick(game):
    """Every turn: a transmission going out (and the enemy listening), the drops, the hunt."""
    st = game.__dict__.get("agent")
    if not st:
        return
    p = game.player
    tx = st.get("tx")
    if tx is not None:
        if (p.x, p.y) != tx["pos"] or p.fired_turn >= game.turn - 1 or not p.alive or p.downed:
            st["tx"] = None
            game.msg("You break off - the message is only half sent.", "warn")
        else:
            tx["left"] -= 1
            _df(game, 1.0, tx["pos"])
            if tx["left"] <= 0:
                st["tx"] = None
                _sent(game, tx["what"])
    if game.turn % 5 == 0:
        for d in st["drops"]:
            _drop_tick(game, d)
        _hunt_tick(game)
        st["df"] = max(0.0, st["df"] - 1.0)             # (the bearings go stale)


def transmitting(game) -> bool:
    return bool((game.__dict__.get("agent") or {}).get("tx"))


def _df(game, secs, pos):
    st = _state(game)
    if st["df_pos"] is not None and math.hypot(pos[0] - st["df_pos"][0], pos[1] - st["df_pos"][1]) > DF_MOVE:
        st["df"] *= 0.4                                  # a new place: they start their bearings again
    st["df_pos"] = pos
    st["df"] += secs
    if st["df"] >= DF_ALARM and st.get("hunt") is None:
        _send_detector(game, pos)


def _sent(game, what):
    p = game.player
    st = _state(game)
    home = base_city(p)
    if what == "report":
        st["sent"] += 1
        seen = len([c for c in game.brains[p.side].contacts.values() if getattr(c, "kind", None) != "sound"])
        what = (f"{seen} enemy position{'s' if seen != 1 else ''} and units you've seen" if seen else
                "the circuit's news: arrests, the state of the drop zones, what's moving on the roads")
        game.msg(f"{home} acknowledges: 'QSL.' Your message is out - {what}, in five-letter groups.", "radio")
        try:
            game.command.merit += 0.5 + min(2.0, seen * 0.1)
        except Exception:
            pass
    elif what == "drop":
        when = game.turn + game.rng.randint(1200, 2400)
        if not game.is_night():
            when = max(when, game.turn + _secs_to_dark(game) + game.rng.randint(600, 1800))
        schedule_drop(game, (p.x, p.y), when)
        d = st["drops"][-1]
        mins = (d["at"] - game.turn) // 60
        game.msg(f"{home}: 'Drop approved. Listen for the message: \"{d['phrase']}\".' The aircraft will be over this "
                 f"field in about {mins} minutes. Lights in a line into the wind, the letter {d['letter']} "
                 f"flashed at the end.", "radio")


def _secs_to_dark(game):
    h = game.hour_float()
    dark = 21.5
    return int(((dark - h) % 24) * 3600)


# ============================================================================ the detector cars
def _send_detector(game, pos):
    """They've a good bearing: a car with a loop aerial and a squad of field police come to look."""
    from .ai import Order
    from .spawn import edge_band_point, make_squad, pick_vehicle, spot_and_facing
    from .data.vehicles import VEHICLES
    from .entities import Vehicle
    p = game.player
    enemy = other_side(p.side)
    nat = game.side_nation(enemy)
    e = game.home_edge(enemy) or {"N": "S", "S": "N", "E": "W", "W": "E"}.get(game.home_edge(p.side) or "S", "N")
    rng = game.rng
    x, y = edge_band_point(game, e, rng, depth=(1, 4))
    try:
        sq = make_squad(game, enemy, nat, "rifle", x, y, name={"germany": "Funkabwehr detachment",
                                                               "japan": "Kempeitai detachment",
                                                               "ussr": "NKVD radio-intercept group"}.get(nat, "police"))
    except Exception:
        return
    sq.no_count = True
    for a in sq.members[5:]:
        game.remove_actor(a)
    sq.members = sq.members[:5]
    sq.order = Order("attack", target=pos, radius=12, issued=game.turn)
    vid = pick_vehicle(rng, nat, game.year, "car")
    if vid is not None:
        pt, f = spot_and_facing(game, x, y, VEHICLES[vid], 8, 0)
        if pt is not None:
            v = Vehicle(vid, enemy, nat, pt[0], pt[1], f)
            v.ai["df_van"] = True
            game.add_vehicle(v)
            v.squad = sq
            sq.vehicles.append(v)
    game.squads.append(sq)
    game.brains[enemy].report(None, game.turn, sound=True, x=pos[0], y=pos[1])
    _state(game)["hunt"] = dict(squad=sq.id, pos=pos, turn=game.turn)
    game.emit_sound(x, y, 55, "engine", "a car engine, idling somewhere along the road", enemy, None)


def _hunt_tick(game):
    st = _state(game)
    h = st.get("hunt")
    if h is None:
        return
    sq = next((q for q in game.squads if q.id == h["squad"]), None)
    if sq is None or not any(a.active for a in sq.members) or game.turn - h["turn"] > 3600:
        st["hunt"] = None
        st["df"] = 0.0
        return
    for v in sq.vehicles:
        if not v.dead and game.can_see(v.x, v.y) and not h.get("seen"):
            h["seen"] = True
            game.msg("A black car crawls along the road with a loop aerial turning on its roof. The detector car.",
                     "warn")


# ============================================================================ drops
PHRASES = ["Les sanglots longs des violons", "Jean a de longues moustaches", "Il fait chaud à Suez",
           "Les dés sont sur le tapis", "La girafe a un long cou", "Le chat a neuf vies", "Yvette aime les grosses "
           "carottes", "Le lapin a bu un apéritif", "Nous nous roulerons sur le gazon", "L'arc-en-ciel est jaune"]


def schedule_drop(game, dz, when, confirmed=False):
    """A drop for the field at dz: the special-duties squadron's aircraft will be over it at `when`."""
    rng = game.rng
    p = game.player
    st = _state(game)
    q = _special_duties(game, p.side, p.nation)
    d = dict(id=len(st["drops"]) + 1, dz=tuple(dz), at=when, state="waiting", squadron=q.id if q else None,
             letter=rng.choice("BDFGKLMNPRSTVWXZ"), phrase=rng.choice(PHRASES), lights=False, n_items=0,
             mission=confirmed)
    st["drops"].append(d)
    return d


def _special_duties(game, side, nation):
    """The squadron that flies the drops (a real one, on the war map, with aircraft and a hangar)."""
    from .data.vehicles import AIRCRAFT
    f = game.support.fires
    spec = SPECIAL_DUTIES.get(nation) or SPECIAL_DUTIES["uk"]
    aid, name, _n = spec
    if aid not in AIRCRAFT:
        return None
    q = next((q for q in f.squadrons if q.side == side and q.atype == aid), None)
    if q is None:
        from .fires import Squadron
        q = Squadron(f._id(), side, nation, aid, f._rear_point(game, side), 12, name)
        f.squadrons.append(q)
    return q


def lights_up(game, d) -> bool:
    """Are the lights out on the field when the aircraft comes over: the player with torches at the DZ, or the
    reception committee with theirs.  (The S-Phone, from anywhere near, talks the pilot in.)"""
    p = game.player
    x, y = d["dz"]
    near = p.alive and not p.downed and max(abs(p.x - x), abs(p.y - y)) <= 8
    torches = sum(i.count for i in p.inv if i.t.tool == "torch")
    if near and (torches >= 1 or p.find(lambda i: i.t.tool == "sphone") is not None):
        return True
    rc = _committee(game)
    if rc is not None:
        return sum(1 for a in rc.members if a.active and not a.downed and not a.is_player and
                   max(abs(a.x - x), abs(a.y - y)) <= 10) >= 2
    return False


def _drop_tick(game, d):
    """The aircraft on its way; over the field; home."""
    if d["state"] != "waiting" or game.turn < d["at"] - 60:
        return
    f = game.support.fires
    q = next((s for s in f.squadrons if s.id == d["squadron"]), None)
    if q is None or q.ready(game.turn) <= 0:
        d["state"] = "lost"
        game.msg("The aircraft doesn't come. Later you'll learn why: weather over the Channel, or a night fighter.",
                 "warn")
        return
    from .support import Aircraft
    at = q.at
    m = game.map
    tx, ty = d["dz"]
    ex, ey, _dist = f.bearing_point(game, q.sec, None)
    ang = math.atan2(ty - ey, tx - ex)
    sx, sy = tx - math.cos(ang) * m.w * 0.8, ty - math.sin(ang) * m.h * 0.8
    ac = Aircraft(at, game.player.side, q.nation, sx, sy, tx, ty, "drop")
    ac.squadron = q.id
    ac.drop_id = d["id"]
    game.support.aircraft.append(ac)
    f.sortie_out(game, q, 1)
    d["state"] = "flying"
    game.msg(f"Engines, low, from the {_bearing_word(ang)}: a {at.name} - {q.name.split(',')[0]}.", "radio")
    game.emit_sound(game.player.x, game.player.y, 60, "aircraft", f"the drone of a {at.name}, low", q.side, None)


def _bearing_word(ang):
    from .senses import direction_word
    return direction_word(-math.cos(ang), -math.sin(ang))


def drop_now(game, ac):
    """Over the field (called from Support.attack): lights - containers; no lights - it circles, and goes home."""
    st = _state(game)
    d = next((x for x in st["drops"] if x["id"] == getattr(ac, "drop_id", None)), None)
    if d is None:
        return
    p = game.player
    rng = game.rng
    if not lights_up(game, d):
        d["state"] = "no_lights"
        game.msg("The aircraft circles twice over the dark field, finds no lights, and turns for home.", "warn")
        return
    sphone = p.find(lambda i: i.t.tool == "sphone") is not None and max(abs(p.x - d["dz"][0]),
                                                                          abs(p.y - d["dz"][1])) <= 40
    if sphone:
        game.msg("On the S-Phone, a Yorkshire voice: 'Hello, reception. I see your lights. Running in now.'", "radio")
    spread = 6 if sphone else 14
    n = SPECIAL_DUTIES.get(p.nation, SPECIAL_DUTIES["uk"])[2]
    n = rng.randint(max(4, n - 6), n)
    items = 0
    m = game.map
    for k in range(n):
        along = rng.uniform(-spread * 1.5, spread * 1.5)
        x = int(round(d["dz"][0] + ac.dx * along + rng.gauss(0, spread * 0.4)))
        y = int(round(d["dz"][1] + ac.dy * along + rng.gauss(0, spread * 0.4)))
        x = max(1, min(m.w - 2, x))
        y = max(1, min(m.h - 2, y))
        for it in _container_load(game, p.nation):
            it.data = dict(it.data or {}, drop=d["id"])
            m.add_item(x, y, it)
            items += 1
    d["state"] = "dropped"
    d["n_items"] = items
    game.msg(f"Parachutes blossom white against the sky - {n} containers swinging down onto the field.", "good")
    # the enemy heard the aircraft too, and will come to see what it was doing
    enemy = other_side(p.side)
    game.brains[enemy].report(None, game.turn + rng.randint(60, 240), sound=True, x=d["dz"][0], y=d["dz"][1])
    game.noise = min(100.0, getattr(game, "noise", 0) + 25)


def _container_load(game, nation):
    """One container's contents, as that army's drops really held (Stens for the SOE, PPShs for partisans)."""
    from .data.items import ITEMS
    from .entities import Item
    rng = game.rng
    load = rng.choice(CONTAINER_LOADS)
    swap = {}
    if nation == "ussr":
        swap = {"sten": "ppsh", "mag_9mm_32_smg": "mag_762t_71_smg", "ammo_9mm": "ammo_762t", "bren": "dp28",
                "mag_303_30_lmg": "mag_762r_47_lmg", "lee_no4": "mosin", "ammo_303": "ammo_762r",
                "pe_808": "tol_block", "mills": "rgd33", "gammon": "rgd33", "liberator": "tt33",
                "ammo_45acp": "ammo_762t", "m1911": "tt33", "francs": "roubles", "chocolate": "ration"}
    elif nation == "germany":
        swap = {"sten": "mp40", "mag_9mm_32_smg": "mag_9mm_32_smg", "bren": "mg42", "lee_no4": "kar98k",
                "ammo_303": "ammo_792", "pe_808": "tol_block", "mills": "stielhandgranate", "gammon": "stielhandgranate",
                "liberator": "p38", "m1911": "p38", "ammo_45acp": "ammo_9mm", "francs": "francs"}
    elif nation == "poland":
        swap = {"francs": "zloty"}
    out = []
    for tid, (lo, hi) in load:
        tid = swap.get(tid, tid)
        if tid not in ITEMS:
            continue
        n = rng.randint(lo, hi)
        t = ITEMS[tid]
        if t.kind == "ammo" or t.stackable:
            out.append(Item(tid, n))
        else:
            for _ in range(min(n, 8)):
                it = Item(tid)
                if t.kind == "mag":
                    it.loaded = t.mag
                out.append(it)
    return out


# ============================================================================ using the kit
def open_wireless(ps):
    from .render import Popup
    g = ps.game
    st = _state(g)
    lines = []
    if st["df"] > DF_ALARM * 0.5:
        lines.append(("You've been on the air a long time near here. Move before you send again.", (240, 170, 120)))
    ps.open_popup(Popup("The wireless set (Morse, to base)", radio_options(g), ps._screen_anchor(), lines=lines),
                  lambda v: radio_choice(ps, v))


def use_tool(ps, it):
    """The secret war's kit, used (play.item_action dispatches here)."""
    g = ps.game
    p = g.player
    tool = it.t.tool
    st = _state(g)
    if tool == "wireless":
        return open_wireless(ps)
    if tool == "camera":
        return photograph(ps)
    if tool == "torch":
        d = next((d for d in st["drops"] if d["state"] == "waiting"), None)
        if d is not None and max(abs(p.x - d["dz"][0]), abs(p.y - d["dz"][1])) <= 8:
            d["lights"] = True
            g.msg(f"You pace out the line into the wind and bed the torches in the grass, the last one ready to flash "
                  f"'{d['letter']}'. They go on when you hear the engines.", "info")
            return ps.act(600)
        g.msg("A torch with a red filter. For a dropping zone - in a line into the wind, the letter flashed at the end.",
              "info")
        return
    if tool == "sphone":
        g.msg("The S-Phone: when the aircraft comes over the field, you talk the pilot in. Have it on you at the "
              "dropping zone.", "info")
        return
    if tool == "time_pencil":
        n = sum(i.count for i in p.inv if i.t.tool == "time_pencil")
        g.msg(f"{n} time pencil{'s' if n != 1 else ''}, ten-minute bands. Place a charge (a) and one goes in "
              f"it by itself.", "info")
        return
    if tool == "money":
        n = sum(i.count for i in p.inv if i.t.tool == "money")
        g.msg(f"You count {n} notes, and put them back where they won't be found.", "info")
        return ps.act(100)
    if tool == "cover_papers" or tool == "papers":
        cv = cover(g)
        if cv and cv.get("name"):
            g.msg(f"{cv['name']}, {cv['trade']}. You go over the story again: {cv['story']}.", "info")
        else:
            g.msg(it.t.desc, "info")
        return ps.act(100)
    if tool == "code":
        g.msg("The one-time pad: a sheet a message, burned afterwards. Your reports go out in it.", "info")
        return
    if tool == "film":
        g.msg("Exposed film. Keep it dark, keep it dry, get it home.", "info")
        return
    g.msg(it.t.desc, "info")


def photograph(ps):
    """The Minox: their installations near enough (25 yards) and in sight."""
    g = ps.game
    p = g.player
    enemy = other_side(p.side)
    ms = g.__dict__.get("mission") or {}
    got = []
    m = g.map
    for r in getattr(m, "gen_positions", None) or []:
        if r.get("side") != enemy or not r.get("rect"):
            continue
        x0, y0, w, h = r["rect"]
        nx, ny = max(x0, min(p.x, x0 + w - 1)), max(y0, min(p.y, y0 + h - 1))
        if math.hypot(nx - p.x, ny - p.y) <= 12 and m.in_bounds(nx, ny) and m.visible[nx, ny]:
            got.append(r)
    if not got:
        vs = [v for v in g.vehicles if v.side == enemy and not v.dead and g.can_see(v.x, v.y) and
              math.hypot(v.x - p.x, v.y - p.y) <= 12]
        if vs:
            g.msg(f"Click. The {vs[0].vt.name}, its markings and whatever's parked round it.", "info")
            return ps.act(150)
        g.msg("Nothing worth a frame within twenty-five yards that you can see.", "info")
        return
    for r in got:
        key = f"{r.get('kind')}@{r['x']},{r['y']}"
        what = (r.get("name") or r.get("kind", "position")).replace("_", " ")
        if ms.get("task") == "photograph" and key not in ms.get("shot", []):
            ms["shot"].append(key)
            g.msg(f"Click. Click. Click. The {what}: its layout, its guns, its vehicles. "
                  f"({len(ms['shot'])} of {ms['need']})", "good")
        else:
            g.msg(f"Click. The {what}.", "info")
    from .skills import use
    use(g, p, "observation", 2)
    return ps.act(300)


# ============================================================================ the resistance, as a band
def band_mission(game, notes) -> bool:
    """A partisan detachment's job: a career from the resistance of this country, and its mission.  False if it's
    the classic ambush on the road (scenarios.py does that)."""
    from .data.agents import RESISTANCE
    rng = game.rng
    p = game.player
    year = game.year
    cands = [k for k, c in RESISTANCE.items() if p.nation in c["nations"] and c["years"][0] <= year < c["years"][1]]
    if not cands:
        return False
    career = rng.choice(cands)
    c = RESISTANCE[career]
    st = _state(game)
    lang = getattr(game.sector, "lang", None) or "fr"
    st["cover"] = dict(career=career, circuit=rng.choice(CIRCUITS), field=rng.choice(FIELD_NAMES[bool(p.female)]),
                       lang=lang, service=c["service"], name=None, story="living rough with the band, in the woods",
                       papers=[], resistance=True)
    task = rng.choices(list(c["missions"]), list(c["missions"].values()))[0]
    notes.insert(0, f"{c['name']} - {c['service']}. {c['desc']}")
    if task == "ambush":
        return False
    home = game.home_edge(p.side) or "S"
    ms = dict(kind="agent", task=task, stage="go", home=home, career=career, sid="partisans", band=True,
              award_for={"sabotage": "sabotage operation", "receive_drop": "reception of a supply drop",
                         "eliminate": "operation behind the lines",
                         "rescue_airman": "rescue of an Allied airman"}.get(task, "work behind the lines"))
    game.mission = ms
    from .entities import Item
    if task == "sabotage":
        for a in p.squad.members:
            a.add_item(Item("tol_block" if p.nation in ("ussr", "china") else "pe_808"))
            if a is p or rng.random() < 0.5:
                a.add_item(Item("time_pencil", 2))
    {"sabotage": _setup_sabotage, "receive_drop": _setup_drop, "eliminate": _setup_eliminate,
     "rescue_airman": _setup_airman}[task](game, ms, notes)
    if MISSIONS[task]["night"]:
        from .scenarios import _set_night
        _set_night(game)
    return True
