"""Local leaders keep useful rifles in action with real men, dressings and ammunition.

Assignments are individual errands, not replacement squad orders. Knowledge comes from
sight and nearby calls; a runner follows a last-seen position when he loses the recipient.
"""
from __future__ import annotations

import math

from . import medical as MED
from .ammo import hand_over, hand_over_possible, spare_rounds

HANDS = frozenset(("rifleman", "smg_gunner", "engineer", "at_soldier", "lmg_assistant",
                   "hmg_assistant", "tank_crew", "partisan", "volkssturm", "medic"))
BUSY = ("runner", "litter", "escort", "escort_prisoner", "to_aid", "at_aid", "surgery", "helping_v")
WITHDRAWING = ("rout", "retreat", "assault", "banzai", "bound", "flank", "resupply")


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def sees(game, observer, target, radius=24):
    if observer.z != target.z or distance(observer, target) > radius:
        return False
    from .senses import can_detect, los_clear
    if observer.z < 0:
        return los_clear(game, observer.x, observer.y, target.x, target.y)
    return can_detect(game, observer, target)


def witnessed_kill(game, killer, victim):
    """Only a leader who could see both men credits the shooter with effective fire."""
    if killer is None or not hasattr(killer, "body") or killer.side == victim.side or \
            victim.state != "ok" or victim.ai.get("civilian") or not killer.alive:
        return
    for sq in game.squads:
        lead = sq.leader
        if sq.side != killer.side or lead is None or lead is killer or not lead.active or lead.downed:
            continue
        if sees(game, lead, killer, 32) and sees(game, lead, victim, 60):
            records = lead.ai.setdefault("support_effectiveness", {})
            records = {aid: r for aid, r in records.items() if game.turn - r[1] < 600}
            count = records.get(killer.id, (0, game.turn))[0]
            records[killer.id] = (min(4, count + 1), game.turn)
            lead.ai["support_effectiveness"] = records


def effectiveness(game, leader, recipient):
    count, when = leader.ai.get("support_effectiveness", {}).get(recipient.id, (0, -9999))
    return count * max(0., 1 - (game.turn - when) / 600.)


def care_need(patient):
    b = patient.body
    need = MED.needs_care(b)
    # A dressed but damaged limb can still benefit from a corpsman's existing treatment.
    if any(0 < b.hp[p] < b.max[p] * .7 for p in b.hp):
        need = max(need, 5.)
    urgent = b.bleed_rate() >= 3 or b.blood < 3000 or not b.conscious
    return (3 if urgent else 2, need) if need >= 1 else (0, 0.)


def low_ammo(actor):
    w = actor.weapon
    if w is None or not w.functional or w.t.kind != "gun" or not w.t.cal or \
            w.t.cat in ("at_disposable", "flamer"):
        return False
    return w.loaded <= max(1, w.t.mag // 2) and spare_rounds(actor, w) < max(1, w.t.mag)


def claimed(game, recipient, kind, except_actor=None):
    # Medics consider many casualties. Index the few actual errands once per turn, not
    # every soldier for every candidate. Revalidate each entry as men get hit or diverted.
    cache = game.__dict__.get("_support_claims")
    if cache is None or cache[0] != game.turn:
        by_target = {}
        for a in game.actors:
            job = a.ai.get("support_job")
            if job:
                by_target.setdefault((job["target"], job["kind"]), []).append(a)
        cache = game._support_claims = (game.turn, by_target)
    return any((job := a.ai.get("support_job")) and a is not except_actor and a.active and
               not a.downed and a.vehicle is None and
               a.suppression < 65 and a.morale >= 20 and
               job["target"] == recipient.id and
               job["kind"] == kind and job["until"] > game.turn and
               job["sector"] == (game.sector.x, game.sector.y)
               for a in cache[1].get((recipient.id, kind), ()))


def available(a, sq):
    return a is not sq.leader and not a.is_player and a.active and not a.downed and \
        a.vehicle is None and a.carrying is None and a.role in HANDS and \
        a.body.bleed_rate() < .5 and a.body.arms_ok() > 0 and a.suppression < 55 and a.morale >= 25 and \
        not a.ai.get("support_job") and not a.ai.get("help_buddy") and not a.ai.get("patient") and \
        not any(a.ai.get(k) is not None for k in BUSY)


def eligible_patient(game, a, side):
    return a.alive and a.state == "ok" and a.side == side and a.vehicle is None and \
        not a.ai.get("civilian") and not a.ai.get("disguise") and not a.ai.get("carried_by") and \
        not a.ai.get("surgery") and not (a.is_player and getattr(game, "renegade", False))


def dispatch(game, sq):
    """At most one runner per squad and one assignment of each kind per recipient."""
    lead = sq.leader
    if lead is None or lead.is_player or not lead.active or lead.downed or lead.vehicle is not None or \
            lead.suppression >= 65 or sq.state in WITHDRAWING or sq.order.kind in WITHDRAWING or \
            sq.order.kind == "ambush" or sq.__dict__.get("task") is not None:
        return
    if game.turn - sq.__dict__.get("support_checked", -999) < 6:
        return
    sq.support_checked = game.turn
    for member in sq.members:
        job = member.ai.get("support_job")
        if job and (job["until"] <= game.turn or job["sector"] != (game.sector.x, game.sector.y)):
            member.ai.pop("support_job", None)
    if any(m.ai.get("support_job") and m.active and not m.downed for m in sq.members):
        return
    helpers = [a for a in sq.members if available(a, sq) and sees(game, lead, a, 16)]
    if not helpers:
        return
    candidates = []
    for recipient in game.near(lead.x, lead.y, 24, sq.side):
        if not eligible_patient(game, recipient, sq.side) or not sees(game, lead, recipient):
            continue
        credit = effectiveness(game, lead, recipient)
        d = distance(lead, recipient)
        tier, need = care_need(recipient)
        recent = recipient.ai.get("support_received", {})
        if tier and (tier == 3 or game.turn - recent.get("aid", -999) >= 20) and not claimed(game, recipient, "aid"):
            candidates.append(((tier, need + credit * 4 - d * .4), recipient, "aid", credit))
        # Nearby men can notice empty pouches; further away, firing dry or a call is the cue.
        cue = d <= 8 or game.turn - recipient.fired_turn < 20 or game.turn - recipient.ai.get("ammo_call", -999) < 30
        if recipient.active and low_ammo(recipient) and cue and game.turn - recent.get("ammo", -999) >= 40 and \
                not claimed(game, recipient, "ammo"):
            candidates.append(((1, (10 if recipient.weapon.loaded == 0 else 0) + credit * 6 - d * .4),
                               recipient, "ammo", credit))
    for _, recipient, kind, credit in sorted(candidates, key=lambda c: c[0], reverse=True):
        suitable = [a for a in helpers if a is not recipient and distance(a, recipient) <= 28 and
                    not (a.ai.get("support_retry", {}).get((recipient.id, kind), -1) > game.turn) and
                    (MED.can_help(game, a, recipient) if kind == "aid" else
                     a.role != "medic" and hand_over_possible(a, recipient.weapon))]
        if not suitable:
            continue
        helper = min(suitable, key=lambda a: distance(a, recipient) -
                     (6 if kind == "aid" and MED.skill(a) >= MED.MEDIC else 0))
        helper.ai["support_job"] = dict(target=recipient.id, leader=lead.id, kind=kind,
                                         sector=(game.sector.x, game.sector.y), until=game.turn + 90,
                                         last_pos=recipient.pos, last_seen=game.turn,
                                         triage=care_need(recipient)[0],
                                         gun=recipient.weapon.iid if kind == "ammo" else None)
        game._support_claims = None
        helper.ai.pop("path", None)
        task = f"dress {recipient.last_name}'s wounds" if kind == "aid" else f"take {recipient.last_name} ammunition"
        words = f"{helper.last_name}, {task}!" + (" Keep that rifle in action!" if credit else "")
        lead.say(words, game.turn, 4)
        game.emit_sound(lead.x, lead.y, 45, "shout", words, lead.side, lead)
        if recipient.is_player:
            action = "give you first aid" if kind == "aid" else f"bring ammunition for your {recipient.weapon.t.name}"
            game.msg(f"{lead.rank_short} {lead.last_name} sends {helper.rank_short} {helper.last_name} to {action}." +
                     ((" She's" if lead.female else " He's") + " seen your fire taking effect." if credit else ""), "good")
        return


def _cancel(game, helper, reason=None):
    job = helper.ai.pop("support_job", None)
    game._support_claims = None
    helper.ai.pop("path", None)
    if reason and job:
        retry = {k: t for k, t in helper.ai.get("support_retry", {}).items() if t > game.turn}
        retry[(job["target"], job["kind"])] = game.turn + 30
        helper.ai["support_retry"] = retry
    if reason and job and game.player and job["target"] == game.player.id and sees(game, game.player, helper):
        game.msg(f"{helper.rank_short} {helper.last_name} {reason}.", "warn")


def act(game, helper, enemies):
    job = helper.ai.get("support_job")
    if not job:
        return None
    sq = helper.squad
    target = next((a for a in game.actors if a.id == job["target"]), None)
    if job["until"] <= game.turn or job["sector"] != (game.sector.x, game.sector.y) or \
            sq is None or sq.state in WITHDRAWING or sq.order.kind in WITHDRAWING or \
            sq.order.kind == "ambush" or sq.__dict__.get("task") is not None or \
            target is None or not eligible_patient(game, target, helper.side) or target.z != helper.z or \
            helper.carrying is not None or any(helper.ai.get(k) is not None for k in BUSY):
        _cancel(game, helper)
        return None
    if helper.suppression >= 65 or helper.morale < 20 or any(distance(helper, e) <= 8 for e in enemies):
        return None                           # fight or take cover now; resume the errand when possible
    visible = sees(game, helper, target, 30)
    if visible:
        job.update(last_pos=target.pos, last_seen=game.turn, triage=care_need(target)[0])
    elif game.turn - job["last_seen"] > 20 or distance_to(helper, job["last_pos"]) <= 1.5:
        _cancel(game, helper, "loses sight of you and returns to his squad")
        return None
    if job["kind"] == "aid":
        # A suddenly critical casualty overrides a routine dressing, regardless of combat reputation.
        tier = job.get("triage", 2)
        if any(o is not target and o is not helper and eligible_patient(game, o, helper.side) and
               care_need(o)[0] > tier and MED.can_help(game, helper, o) and sees(game, helper, o, 8)
               for o in game.near(helper.x, helper.y, 8, helper.side)):
            _cancel(game, helper, "turns to a more urgent casualty")
            return None
        if visible and not MED.can_help(game, helper, target):
            _cancel(game, helper)
            return None
    elif visible and (not low_ammo(target) or target.weapon.iid != job["gun"] or
                      not hand_over_possible(helper, target.weapon)):
        _cancel(game, helper)
        return None
    from . import ai as AI
    if visible and distance(helper, target) <= 1.5:
        if job["kind"] == "aid":
            cost = MED.first_aid(game, helper, target)
            if cost:
                target.ai.setdefault("support_received", {})["aid"] = game.turn
                if MED.can_help(game, helper, target):
                    return cost
            _cancel(game, helper)
            return cost
        ground_before = len(game.map.items_at(target.x, target.y))
        n = hand_over(game, helper, target, target.weapon)
        if n:
            target.ai.setdefault("support_received", {})["ammo"] = game.turn
            helper.ai["ammo_cd"] = game.turn
            if target.is_player:
                dropped = len(game.map.items_at(target.x, target.y)) > ground_before
                game.msg(f"{helper.rank_short} {helper.last_name} brings ammunition for your {target.weapon.t.name}." +
                         (" There's no room for some of it; it's at your feet." if dropped else ""), "good")
        _cancel(game, helper)
        return 120 if n else None
    # Ordinary pathfinding accounts for fire, terrain and occupancy. No tracking through walls.
    cost = AI.path_step(game, helper, *job["last_pos"])
    if cost:
        job.pop("stuck", None)
        return cost
    job["stuck"] = job.get("stuck", 0) + 1
    if job["stuck"] >= 3:
        _cancel(game, helper, "cannot find a route to you")
    return 100


def distance_to(actor, point):
    return math.hypot(actor.x - point[0], actor.y - point[1])
