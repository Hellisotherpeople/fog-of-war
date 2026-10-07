"""The orders book: everything you've been told to do, at once.

Orders reach a soldier from several men at a time, by different routes: a sergeant shouting across a field,
the platoon sergeant grabbing his arm, a runner from company with a scrap of paper, the battalion net on the
radio, the adjutant's written orders, the fire direction centre's numbers.  Each has a man behind it who'll
know whether it was done, a time it must be done by, and what follows either way.

Rewards and punishments are the ones each army really used, and they really happen:
- praise and trust (duty.rep), a line in your record (command.merit), a commendation, a pass to the rear,
  the quartermaster's credit, promotion when the record's good enough, a recommendation for a medal;
- a dressing-down (or, in the Japanese army, a beating); extra duties - fatigues, KP, latrines - served at
  the next base (base.py: they come before anything else there); a fine, docked from your pay; confinement
  to camp (no pass); a charge before the company commander; reduction in rank; for the Red Army, the Special
  Department's attention and, at the end of it, a penal company.

book(game) lists them; the panel shows the first few; T opens the book (ui.OrdersState), where you can
choose a compatible local instruction. The governing order, navigation and Enter share one priority rule.
"""
from __future__ import annotations

import math

# what failure costs, by army, as it escalates: (a first failure, on report (three), the last straw (five))
SANCTION = {
    "usa": ("a chewing-out, and extra duty - KP or the latrines", "company punishment under the 104th Article "
            "of War: fined, and restricted to the area", "reduced in grade"),
    "uk": ("a rocket from the sergeant, and fatigues", "put on a charge: before the company commander - "
           "confined to barracks and a stoppage of pay", "stripped of your stripe"),
    "canada": ("a rocket, and fatigues", "on a charge: CB and a stoppage of pay", "stripped of your stripe"),
    "australia": ("a blast from the sergeant, and fatigues", "on a charge: CB and a fine", "busted"),
    "germany": ("a dressing-down in front of the section, and extra duty", "Arrest - geschärfter Arrest, and "
                "no leave", "reduced in rank"),
    "ussr": ("a dressing-down before the section; the politruk hears of it", "a reprimand in your record, and "
             "the Special Department takes an interest", "reduced in rank - and the penal company next"),
    "japan": ("a beating from the NCO", "confinement and a mark in your record that goes home to your family",
              "reduced in rank"),
    "italy": ("a dressing-down, and extra duty", "consegna: confined, and pay stopped", "reduced in rank"),
    "france": ("a dressing-down, and fatigues", "salle de police: confined, pay stopped", "reduced in rank"),
    "poland": ("a dressing-down, and fatigues", "arrest, and pay stopped", "reduced in rank"),
}
PRAISE = {"usa": "he'll remember it", "uk": "he'll remember it", "germany": "he'll note it",
          "ussr": "a word to the company commander", "japan": "it reflects well on you"}


def sanction(nation, level, rank=None) -> str:
    """What the army does to a man at this level of trouble (a private can't be reduced: filthy jobs and the
    point, instead; a Soviet private goes to the penal company)."""
    if level >= 2 and rank is not None and rank <= 0:
        return ("the penal company" if nation == "ussr" else
                "every filthy job going, and the point on every patrol for the rest of the war")
    return SANCTION.get(nation, SANCTION["uk"])[max(0, min(2, level))]


def _watch(game) -> bool:
    p = game.player
    return p is not None and p.has_tool("watch") is not None


def _clock(game, turn):
    """The time of day - with a watch; without one, nothing to say."""
    if turn is None or not _watch(game):
        return ""
    t = game.now() + __import__("datetime").timedelta(seconds=turn - game.turn)
    return t.strftime("%H:%M")


def _left(game, turn):
    """How long till then: to the minute with a watch, by feel without."""
    if turn is None:
        return ""
    return left_words(game, turn - game.turn)


def left_words(game, d) -> str:
    if d <= 0:
        return "overdue"
    if _watch(game):
        if d < 90:
            return f"{d} s"
        if d < 3600:
            return f"{d // 60} min"
        return f"{d // 3600} h {d % 3600 // 60} min"
    return ("any moment" if d < 120 else "a few minutes" if d < 600 else "within the half hour" if d < 2100 else
            "within the hour" if d < 4500 else "a couple of hours" if d < 3 * 3600 else "hours yet")


def book(game) -> list:
    """Received instructions, with authority, governing/active status and reasons; governing order first."""
    from .duty import REWARD, STRICT, TASK_TEXT
    p = game.player
    out = []
    if p is None:
        return out
    nat = p.nation
    duty = getattr(game, "duty", None)
    if duty is not None and (game.renegade or duty.arrest or duty.disgraced):
        from .conduct import status
        out.append(dict(key='conduct', who='Your comrades', how='their reaction to your actions',
                        text=status(game), issued=None, due=None, point=None, authority=0,
                        reward='cooperation restored, followed by an HQ debrief',
                        penalty='further deliberate attacks renew hostility', urgent=True))
    strikes = duty.strikes if duty is not None else 0
    next_level = 0 if strikes < 2 else 1 if strikes < 4 else 2
    # the mission (a briefing: raids, patrols, agents, the navy's and the air force's jobs)
    from .scenarios import mission_line, mission_point
    ml = mission_line(game)
    ms = game.__dict__.get("mission") or {}
    if ml:
        point = mission_point(game)
        if point and ms.get("kind") == "agent" and ms.get("stage") in ("find", "kill", "photo", "send"):
            from .senses import direction_word
            dx, dy = point[0] - p.x, point[1] - p.y
            distance = int(round(math.hypot(dx, dy) * 2.2 / 10) * 10)
            ml += f" Lead: {point[2]}; {direction_word(dx, dy)}, about {distance} yards."
        who = {"agent": "operations headquarters, your briefing officer", "raid": "the raid commander's briefing",
               "patrol": "the company commander's briefing"}.get(ms.get("kind"),
                   "battalion's briefing" if ms.get("authority", mission_authority(ms)) >= 12 else "company's briefing")
        out.append(dict(key="mission", who=who, how="briefing", text=ml, issued=ms.get("start"), due=None,
                        reward="a line in your record, and a medal recommendation if it's done well",
                        penalty="the mission fails - and the men who sent you will know why", urgent=False,
                        point=point, authority=ms.get("authority", mission_authority(ms))))
    from .service import entry as service_entry
    service = service_entry(game)
    if service:
        out.append(service)
    from .debrief import entry as debrief_entry
    personnel = debrief_entry(game)
    if personnel:
        out.append(personnel)
    from .contacts import entry as intelligence_entry
    intelligence = intelligence_entry(game)
    if intelligence:
        out.append(intelligence)
    from .contacts import entries as contact_entries
    out.extend(contact_entries(game))
    # the men who command you, in the field
    for t in (duty._tasks() if duty is not None else []):
        r = REWARD.get(t["kind"], 2)
        how = "shouted" if t["kind"] in ("down", "help", "fire", "come", "gun", "ammo") else "told you"
        returning = (t["kind"] == "scout" and t.get("leg") == "back") or \
            (t["kind"] == "fetch" and p.ai.get("resupplied_turn", -1) >= t["issued"])
        text = f"Report back to {t['by_name']} with what you brought back." if returning else TASK_TEXT[t["kind"]]
        out.append(dict(key=f"duty:{t.get('uid')}", uid=t.get("uid"),
                        who=f"{t['by_name']}" + (f", {t['by_role'].lower()}" if t.get("by_role") else ""),
                        how=how, text=text, issued=t["issued"], due=t["deadline"],
                        reward=("his trust" if r < 3 else "his trust, and a line in your record") +
                        f" ({PRAISE.get(nat, 'he will remember it')})",
                        penalty=f"a strike against you: {sanction(t.get('by_nation', nat), next_level, p.rank)}",
                        urgent=t["kind"] in ("down", "help", "fire", "come"), point=duty.task_point(game, t),
                        authority=t.get("authority", issuer_rank(game, t)), task=t))
    # a fire mission for your gun or tube
    if game.support is not None and game.map is not None:
        f = game.support.fires
        pm = f.player_mission(game)
        if pm is not None:
            b, m = pm
            out.append(dict(key="fire", who="the section chief" if b.kind != "mortar" else "the platoon sergeant",
                            how="the fire direction centre's numbers", text=f.order_text(game), issued=m.get("start"),
                            due=m.get("deadline"), reward="your standing with the battery, and a line in your record",
                            penalty="he fires your rounds himself - and you're on report", urgent=True, point=None,
                            authority=9))
    # the adjutant's written orders
    from . import base as BASE
    bo = game.__dict__.get("base_order")
    if bo:
        rw = bo.get("reward") or {}
        bits = []
        if rw.get("credit"):
            bits.append(f"{rw['credit']} credit with the quartermaster")
        if rw.get("merit", 0) >= 3:
            bits.append("a line in your record")
        elif rw.get("merit"):
            bits.append("a note in your record")
        if rw.get("rep"):
            bits.append("the adjutant's good opinion")
        out.append(dict(key="base", who=f"{bo['by']['name']}, {bo['by'].get('role', 'adjutant')}"
                                        f"{', ' + bo['by']['base'] if bo['by'].get('base') else ''}",
                        how="written orders" if bo["kind"] != "guard" else "detailed at the guardroom",
                        text=BASE.order_line(game), issued=bo.get("issued"), due=bo.get("deadline"),
                        reward=", ".join(bits) or "the adjutant's good opinion",
                        penalty=f"a strike against you: {sanction(nat, next_level, p.rank)}", urgent=False,
                        point=BASE.order_point(game), authority=bo.get("authority", bo["by"].get("rank", 10))))
    # a sailor ashore
    if game.__dict__.get("ship_ashore"):
        ctx = game.ship_ashore
        out.append(dict(key="liberty", who=f"the officer of the deck, {ctx['ship_name']}", how="liberty card",
                        text="Back aboard by 0500 - the port director has the boat.", issued=ctx.get("left"),
                        due=ctx.get("back_by"), reward="another liberty, next time in port",
                        penalty="adrift: captain's mast in the morning; miss her sailing and you're a deserter",
                        urgent=False, point=None))
    elif game.__dict__.get("awol"):
        out.append(dict(key="awol", who="the military police", how="a warrant", issued=None, due=None,
                        text="You're absent without leave. Report yourself to the adjutant or the port director.",
                        reward="a stoppage of pay, not the stockade", penalty="arrest: the stockade, then company "
                        "punishment", urgent=True, point=None))
    # your unit's orders, as your leader gives them
    sq = p.squad
    if sq is not None and not sq.player_led and sq.leader is not None and not sq.leader.is_player and \
            game.sector is not None:
        o = sq.order
        from .ai import order_target
        text = o.describe(game)
        if text:
            out.append(dict(key="squad", who=f"{sq.leader.full_name}, your {sq.leader.role_name.lower()}",
                            how=_route(game, sq.leader), text=text, issued=o.issued, due=None,
                            reward="the section's opinion of you; merit for ground taken",
                            penalty="leave the fight without authority and it's desertion", urgent=False,
                            point=order_target(game, sq), authority=sq.leader.rank))
    cmd = game.command
    if cmd.billet is not None or (sq is not None and sq.player_led):
        objs = [o for o in game.map.objectives if o.owner != p.side] if game.map is not None else []
        ob = min(objs, key=lambda o: abs(o.x - p.x) + abs(o.y - p.y)) if objs else None
        text = f"Take {ob.name}." if ob is not None else None
        if text:
            out.append(dict(key="command", who="battalion" if cmd.billet is not None else "company",
                            how="the battalion net" if p.has_tool("radio") else "a runner",
                            text=text, issued=None, due=None, reward="a reported contribution to the operation",
                            penalty="relieved of your command if it goes badly enough", urgent=False,
                            point=(ob.x, ob.y), authority=12 if cmd.billet is not None else 10))
    field = game.__dict__.get("field_order")
    if field and field.get("sector") == (game.sector.x, game.sector.y):
        edge = field.get("edge")
        pt = exit_point(game, edge) if edge else field.get("point")
        out.append(dict(key="field", who=field["who"], how="headquarters orders", text=field["text"],
                        issued=field["issued"], due=None, reward="carry out headquarters' instructions", penalty="-",
                        urgent=True, point=pt, authority=field["authority"], reason=field["reason"]))
    # the medevac, if you called one
    from .medevac import order_line
    mv = order_line(game)
    if mv:
        out.insert(0, dict(key="medevac", who="the battalion aid post", how="the radio", text=mv, issued=None,
                           due=None, reward="a hospital bed", penalty="-", urgent=True, point=None))
    return _prioritize(game, out)


def mission_authority(ms):
    """Common rank grades; old saves retain the authority implied by their briefing."""
    return 13 if ms.get("kind") == "agent" else 12 if ms.get("kind") in ("take", "hold", "rearguard") else 10


def issuer_rank(game, task):
    if "by_rank" in task:
        return task["by_rank"]
    who = next((a for a in game.actors if a.id == task.get("by")), None)
    return who.rank if who is not None else 3


def _supports(game, order, primary):
    """Local execution of a mission is allowed; a different destination is not a new mission."""
    if order['key'] == 'conduct':
        return True  # ceasing friendly fire and aiding comrades always supports duty
    if order["key"] in ("personnel", "intelligence") or order["key"].startswith("contact:"):
        from .debrief import release_allowed
        return release_allowed(game)
    if order["key"] == "service" and game.player.ai.get("service_order", {}).get("kind") == "repair":
        # A senior commander can release his own vehicle to the workshops in a quiet sector.
        return game.player.rank >= primary["authority"] and game.turn - game.player.fired_turn > 120
    t = order.get("task")
    if t:
        if t["kind"] == "down":
            return True
        pt = order.get("point")
        if t["kind"] in ("help", "ammo") and pt:
            return max(abs(pt[0] - game.player.x), abs(pt[1] - game.player.y)) <= 3
    if primary["key"] != "mission":
        return False
    ms = game.__dict__.get("mission") or {}
    k = ms.get("kind")
    if ms.get("stage") in ("return", "exfil", "home", "withdraw", "away", "out"):
        return False
    if order["key"] in ("squad", "command"):
        sq = game.player.squad
        if k not in ("take", "hold", "rearguard") or not order["point"]:
            return False
        if order["key"] == "squad" and sq.order.kind not in (("attack", "assault", "move") if k == "take" else
                                                            ("defend", "hold", "dig")):
            return False
        return any(max(abs(ob.x - order["point"][0]), abs(ob.y - order["point"][1])) <= ob.radius
                   for ob in game.map.objectives if k != "take" or ob.owner != game.player.side)
    if t:
        if t["kind"] == "dig" and k in ("hold", "rearguard"):
            pt = primary.get("point")
            return pt is not None and max(abs(pt[0] - game.player.x), abs(pt[1] - game.player.y)) <= 8
    return False


def _prioritize(game, out):
    if not out:
        return out
    from .data.ranks import COMMAND_LEVEL
    for o in out:
        o.setdefault("authority", 8 if o["key"] in ("medevac", "liberty", "awol") else 3)
        o["authority_name"] = ("unit discipline" if o['key'] == 'conduct' else
                               "service visit" if o["key"].startswith("contact:") else
                               "reporting procedure" if o["key"] in ("personnel", "intelligence") else
                               COMMAND_LEVEL.get(o["authority"], "section"))
    mission = next((o for o in out if o["key"] == "mission"), None)
    directives = [o for o in out if o["key"] in ("mission", "base", "field")]
    primary = mission
    if primary is None and directives:
        primary = max(directives, key=lambda o: (o["authority"], o["issued"] or 0))
    if primary is not None:
        # Only an actual received order can supersede the briefing, never the generic side AI's target.
        for o in sorted(out, key=lambda o: o["issued"] or 0):
            if o["key"] in ("squad", "command", "medevac", "liberty", "awol"):
                continue
            if o["authority"] >= primary["authority"] and (o["issued"] or 0) > (primary["issued"] or 0):
                primary = o
    else:
        tasks = [o for o in out if o["key"] not in ("squad", "command")]
        primary = min(tasks or out, key=lambda o: (-o["authority"], not o["urgent"], o["due"] or 10 ** 12))
    protected = bool(directives)
    for o in out:
        o["governing"] = o is primary
        o["deferred"] = protected and o is not primary and not _supports(game, o, primary)
        o["status"] = "Governing" if o is primary else "Deferred" if o["deferred"] else "Supporting"
        if o["deferred"]:
            o["reason"] = f"{primary['who']} has priority. This order cannot redirect you." + \
                (" Its deadline is paused." if o["due"] is not None else "")
        elif o is primary and mission is not None and o is not mission:
            o["reason"] = o.get("reason") or "Newer orders from an equal or higher authority take precedence."
        elif o is primary:
            o["reason"] = o.get("reason") or "This order governs the arrow and Enter. Local directions must support it."
        else:
            o["reason"] = "A local instruction you can follow without replacing the governing order."
    chosen = next((o for o in out if o["key"] == game.__dict__.get("order_focus") and not o["deferred"]), primary)
    for o in out:
        o["active"] = o is chosen
    out.sort(key=lambda o: (not o["governing"], o["deferred"], not o["active"], not o["urgent"],
                            o["due"] or 10 ** 12))
    return out


def governing(game):
    return next((o for o in book(game) if o["governing"]), None)


def active(game):
    return next((o for o in book(game) if o["active"]), None)


def summary(game, entries=None):
    entries = book(game) if entries is None else entries
    primary = next((o for o in entries if o["governing"]), None)
    if primary is None:
        return None
    text = f"ORDERS ({primary['authority_name']}): {primary['text']}"
    chosen = next((o for o in entries if o["active"]), None)
    if chosen is not None and chosen["key"] != primary["key"]:
        text += f" Local action: {chosen['text']}"
    return text


def navigation(game):
    o = active(game)
    if o is None or o["point"] is None:
        return None
    pt = o["point"]
    label = pt[2] if len(pt) > 2 else o["text"].split("!")[0].split(".")[0]
    return int(pt[0]), int(pt[1]), label


def execution_signature(game):
    """The instruction a walk started under; moving men and clocks are not new orders."""
    o = active(game)
    if o is None:
        return None
    key = o["key"]
    detail = o["text"]
    if key == "base":
        bo = game.base_order
        detail = (bo.get("kind"), bo.get("stage"), bo.get("sector"))
    elif key == "mission":
        point = o["point"]
        detail = ((game.__dict__.get("mission") or {}).get("stage"),
                  point[2] if point is not None and len(point) > 2 else None)
    elif key == "service":
        dest = game.player.ai.get("service_order", {}).get("destination") or {}
        detail = (detail, dest.get("sector"), dest.get("point"))
    elif key.startswith('contact:'):
        dest = game.player.ai.get('contact_orders', {}).get(key.split(':')[1], {}).get('destination') or {}
        detail = (detail, dest.get('sector'), dest.get('person') or dest.get('point'))
    return key, o["issued"], detail


def exit_point(game, edge):
    """Keep a sector's chosen exit fixed while approaching it, including in a vehicle."""
    import random
    p, m = game.player, game.map
    key = (game.sector.x, game.sector.y, edge, p.vehicle.vid if p.vehicle is not None else None)
    exits = m.__dict__.setdefault('order_exits', {})
    saved = exits.get(key)
    if saved:
        x, y = saved['point']
        # Occupants, including our own tank, do not invalidate the destination.
        # Only a terrain change which blocks the marked spot warrants a new exit.
        if saved['version'] == m.walk_version or m.in_bounds(x, y) and m.walk[x, y] and m.water[x, y] < 2:
            saved['version'] = m.walk_version
            return x, y
    point = game._edge_exit_point(edge, p.pos, 6, rng=random.Random(p.x * 73856093 ^ p.y * 19349663))
    exits[key] = dict(point=point, version=m.walk_version)
    return point


def authorized_departure(game, edge):
    chosen = active(game)
    if chosen and chosen['key'].startswith('contact:') and not chosen['deferred']:
        from .base import _next_edge
        dest = game.player.ai.get('contact_orders', {}).get(chosen['key'].split(':')[1], {}).get('destination')
        return bool(dest and edge == _next_edge(game, dest['sector']))
    if chosen and chosen["key"] in ("personnel", "intelligence") and not chosen["deferred"]:
        from .recognition import state
        from .base import _next_edge
        dest = (state(game).get("report_order", {}) if chosen["key"] == "personnel" else
                game.player.ai.get("intelligence_order", {})).get("destination")
        return bool(dest and edge == _next_edge(game, dest["sector"]))
    primary = governing(game)
    if primary is None:
        return False
    if primary["key"] == "service":
        ticket = game.player.ai.get("service_order", {})
        dest = ticket.get("destination")
        from .base import _next_edge
        return bool(dest and edge == _next_edge(game, dest["sector"]))
    if primary["key"] == "field":
        return edge == game.field_order.get("edge")
    if primary["key"] == "base":
        from .base import _next_edge, _done
        bo = game.base_order
        target = bo["by"]["sector"] if _done(game, bo) else bo.get("sector")
        return target is not None and edge == _next_edge(game, tuple(target))
    if primary["key"] == "mission":
        ms = game.mission
        if ms.get("stage") in ("return", "exfil", "home", "withdraw", "away", "out") or \
                ms.get("kind") in ("evader", "breakout"):
            return edge == (ms.get("home") or game.home_edge(game.player.side))
        if game.sector is not ms.get("_start_sector", game.sector):
            from .base import _next_edge
            start = ms["_start_sector"]
            return edge == _next_edge(game, (start.x, start.y))
        return ms.get("kind") in ("agent", "raid", "patrol", "sniper", "partisans")
    return False


def deferred(game, key):
    return any(o["key"] == key and o["deferred"] for o in book(game))


def pause_deadline(game, task, blocked):
    """Pause deadlines while higher orders prevent compliance, including the last paused interval."""
    last = task.get("_priority_checked", game.turn)
    if blocked or task.get("_priority_paused"):
        elapsed = max(0, game.turn - last)
        task["deadline"] += elapsed
        if task.get("kind") == "guard" and task.get("start") is not None:
            task["start"] += elapsed  # higher duty does not count as time served on the guard post
    task["_priority_checked"] = game.turn
    task["_priority_paused"] = blocked


def recall(game, authority, who, reason):
    """An explicit battlefield recall, with the authority and circumstances preserved in the book."""
    primary = governing(game)
    if primary and (authority < primary["authority"] or game.turn <= (primary["issued"] or 0)):
        game.msg(f"{who} orders a withdrawal, but your higher mission orders still stand.", "radio")
        return False
    edge = game.home_edge(game.player.side)
    game.field_order = dict(authority=authority, who=who, reason=reason, issued=game.turn, edge=edge,
                            sector=(game.sector.x, game.sector.y), text=f"Withdraw toward friendly lines. {reason}")
    ms = game.__dict__.get("mission")
    if ms and primary and primary["key"] == "mission":
        ms["stage"] = "cancelled"
        ms["cancelled_by"] = who
        ms["cancel_reason"] = reason
    game.order_focus = None
    game.update_orders(force=True)
    return True


def _route(game, who) -> str:
    p = game.player
    d = max(abs(who.x - p.x), abs(who.y - p.y))
    if d <= game.command.voice_range(game):
        return "shouted" if d > 4 else "told you"
    return "by runner" if not p.has_tool("radio") and not p.has_tool("handradio") else "on the radio"


def lines(game, n=3) -> list:
    """The first few, short, for the panel: (text, urgent)."""
    out = []
    for o in book(game)[:n]:
        who = o["who"].split(",")[0]
        due = _left(game, o["due"]) if o["due"] is not None else ""
        t = o["text"] or ""
        out.append((f"{who}: {t}" + (f" ({due})" if due else ""), o["urgent"]))
    return out


def focus(game, key):
    """Select an executable order, without silently overriding higher authority."""
    o = next((o for o in book(game) if o["key"] == key), None)
    if o is None or o["deferred"]:
        return False
    duty = getattr(game, "duty", None)
    if key.startswith("duty:") and duty is not None:
        duty.focus = int(key.split(":")[1])
    game.__dict__["order_focus"] = key
    return True


# ============================================================================ the consequences, carried out
def punish(game, level, who):
    """A failure's consequence (duty._escalate calls this at each level): what the army did, done."""
    from . import base as BASE
    p = game.player
    nat = p.nation
    st = BASE._state(game)
    words = sanction(nat, level)
    if level == 0:
        if nat == "japan":
            p.morale = max(0, p.morale - 8)
        st["fatigues"] = st.get("fatigues", 0) + 2                   # served at the next base
    elif level == 1:
        st["fine_days"] = st.get("fine_days", 0) + 7
        st["leave"] = max(st.get("leave", -10 ** 9), game.turn + 7 * 86400)    # no pass for a fortnight
        st["fatigues"] = st.get("fatigues", 0) + 4
        game.command.merit -= 3
        rec = game.command.__dict__.setdefault("record", [])
        rec.append(f"{game.datetime_str()}: on report ({who}) - {words}.")
    return words


def reward_record(game, text):
    """A commendation in your record (the service record shows it)."""
    rec = game.command.__dict__.setdefault("record", [])
    rec.append(f"{game.datetime_str()}: {text}")
