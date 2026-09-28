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
choose which one Enter gets on with.
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


def sanction(nation, level) -> str:
    return SANCTION.get(nation, SANCTION["uk"])[max(0, min(2, level))]


def _watch(game) -> bool:
    p = game.player
    return p is not None and p.has_tool("watch") is not None


def _clock(game, turn):
    """The time of day - with a watch; without one, nothing to say."""
    if turn is None or not _watch(game):
        return ""
    t = game.now() + __import__("datetime").timedelta(seconds=max(0, turn - game.turn))
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
    """The orders you hold: [dict(key, who, how, text, issued, due, reward, penalty, urgent, point)], the
    most pressing first."""
    from .duty import REWARD, STRICT, TASK_TEXT
    p = game.player
    out = []
    if p is None:
        return out
    nat = p.nation
    duty = getattr(game, "duty", None)
    strikes = duty.strikes if duty is not None else 0
    next_level = 0 if strikes < 2 else 1 if strikes < 4 else 2
    # the mission (a briefing: raids, patrols, agents, the navy's and the air force's jobs)
    from .scenarios import mission_line
    ml = mission_line(game)
    ms = game.__dict__.get("mission") or {}
    if ml:
        who = {"agent": "your briefing officer, before you went in", "raid": "the raid commander's briefing",
               "patrol": "the company commander's briefing"}.get(ms.get("kind"), "your briefing")
        out.append(dict(key="mission", who=who, how="briefing", text=ml, issued=ms.get("start"), due=None,
                        reward="a line in your record, and a medal recommendation if it's done well",
                        penalty="the mission fails - and the men who sent you will know why", urgent=False,
                        point=None))
    # the men who command you, in the field
    for t in (duty._tasks() if duty is not None else []):
        r = REWARD.get(t["kind"], 2)
        how = "shouted" if t["kind"] in ("down", "help", "fire", "come", "gun", "ammo") else "told you"
        out.append(dict(key=f"duty:{t.get('uid')}", uid=t.get("uid"),
                        who=f"{t['by_name']}" + (f", {t['by_role'].lower()}" if t.get("by_role") else ""),
                        how=how, text=TASK_TEXT[t["kind"]], issued=t["issued"], due=t["deadline"],
                        reward=("his trust" if r < 3 else "his trust, and a line in your record") +
                        f" ({PRAISE.get(nat, 'he will remember it')})",
                        penalty=f"a strike against you: {sanction(t.get('by_nation', nat), next_level)}",
                        urgent=t["kind"] in ("down", "help", "fire", "come"), point=duty.task_point(game, t)))
    # a fire mission for your gun or tube
    if game.support is not None and game.map is not None:
        f = game.support.fires
        pm = f.player_mission(game)
        if pm is not None:
            b, m = pm
            out.append(dict(key="fire", who="the section chief" if b.kind != "mortar" else "the platoon sergeant",
                            how="the fire direction centre's numbers", text=f.order_text(game), issued=m.get("start"),
                            due=m.get("deadline"), reward="your standing with the battery, and a line in your record",
                            penalty="he fires your rounds himself - and you're on report", urgent=True, point=None))
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
                        penalty=f"a strike against you: {sanction(nat, next_level)}", urgent=False, point=None))
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
            game.sector is not None and not ml:
        o = sq.order
        text = game.__dict__.get("_squad_order_text")
        if text:
            out.append(dict(key="squad", who=f"{sq.leader.full_name}, your {sq.leader.role_name.lower()}",
                            how=_route(game, sq.leader), text=text, issued=o.issued, due=None,
                            reward="the section's opinion of you; merit for ground taken",
                            penalty="leave the fight and it's desertion", urgent=False, point=None))
    cmd = game.command
    if cmd.billet is not None and not ml:
        text = game.__dict__.get("_command_order_text")
        if text:
            out.append(dict(key="command", who="battalion" if cmd.billet.echelon in ("platoon", "company")
                            else "higher headquarters", how="the battalion net" if p.has_tool("radio") else "a runner",
                            text=text, issued=None, due=None, reward="merit for every objective held, and promotion",
                            penalty="relieved of your command if it goes badly enough", urgent=False, point=None))
    # the medevac, if you called one
    from .medevac import order_line
    mv = order_line(game)
    if mv:
        out.insert(0, dict(key="medevac", who="the battalion aid post", how="the radio", text=mv, issued=None,
                           due=None, reward="a hospital bed", penalty="-", urgent=True, point=None))
    out.sort(key=lambda o: (not o["urgent"], o["due"] if o["due"] is not None else 10 ** 12))
    return out


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
    """Make one of your orders the one Enter gets on with."""
    duty = getattr(game, "duty", None)
    if key.startswith("duty:") and duty is not None:
        duty.focus = int(key.split(":")[1])
    game.__dict__["order_focus"] = key


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
