"""Evidence, recommendations, vacancies and delivered personnel orders.

This is an abstraction of personnel administration, not a universal historical
promotion schedule. Skill is learned in action; official credit travels separately.
"""
from __future__ import annotations

from .data import ranks as R
from .intelligence import distance, headquarters, radio_link


def state(game):
    return game.command.__dict__.setdefault("personnel", dict(claims=[], credited=0., spent=0.,
        last_promotion=game.turn, pending=None, awards=[], last_review=game.turn))


def claim(game, kind, weight, why, position=None, *, restore_trust=True):
    p = game.player
    from .senses import los_clear
    pos = position or p.pos
    witnesses = []
    for a in game.actors:
        if a is p or a.side != p.side or not a.active or a.downed or a.ai.get("civilian"):
            continue
        # Seeing the result alone is not witnessing who performed the deed.
        if distance(a.pos, p.pos) <= 25 and distance(a.pos, pos) <= game.view_range_cache and \
                los_clear(game, a.x, a.y, p.x, p.y) and los_clear(game, a.x, a.y, *pos):
            witnesses.append(a.id)
    if p.vehicle is not None and p.vehicle.active and p.vehicle.crew > 1:
        witnesses.append(("crew", p.vehicle.id))
    if not witnesses:
        return False
    ledger = state(game)
    ledger["claims"].append(dict(kind=kind, weight=weight, why=why, witnesses=witnesses,
                                  turn=game.turn, reported=None, sector=(game.sector.x, game.sector.y)))
    from .conduct import valor
    if restore_trust:
        valor(game, kind, weight)
    return True


def channel(game, a=None):
    a = a or game.player
    if headquarters(game, a):
        return "headquarters"
    if radio_link(game, a):
        return "radio"
    if any(b is not game.player and b.active and not b.downed and b.side == a.side and b.rank > a.rank
           and distance(b.pos, a.pos) <= 6 for b in game.actors):
        return "your superior"
    return None


def process(game):
    ledger = state(game)
    cmd = game.command
    for c in list(ledger["claims"]):
        if c["reported"] is None:
            a = next((a for a in game.actors if a.id in c["witnesses"] and a.side == game.player.side and a.active and not a.downed
                      and channel(game, a)), None)
            crew = next((v for v in game.vehicles if ("crew", v.id) in c["witnesses"] and v.side == game.player.side and v.active
                         and v.crew > 1 and (headquarters(game, v) or radio_link(game, v) or
                         any(b is not game.player and b.active and not b.downed and b.side == v.side and b.rank >= R.SERGEANT
                             and distance(b.pos, v.pos) <= 6 for b in game.actors))), None)
            if a is None and crew is None:
                # Unsent evidence dies with its witnesses; missing men can still return.
                if game.turn - c["turn"] > 7 * 86400:
                    ledger["claims"].remove(c)
                continue
            c["reported"] = game.turn
            at_hq = headquarters(game, a) if a is not None else headquarters(game, crew)
            c["due"] = game.turn + (300 if at_hq else 1800)
            c["by"] = a.full_name if a is not None else f"the crew of {crew.vt.name}"
        if game.turn < c["due"]:
            continue
        ledger["credited"] += c["weight"]
        reviewed = ledger.setdefault("reviewed", {})
        reviewed[c["kind"]] = reviewed.get(c["kind"], 0) + 1
        cmd.merit += c["weight"]
        game.duty.rep = min(100., game.duty.rep + c["weight"])
        if c["kind"] == "wounds" and cmd._medal(game, 0) not in cmd.medals:
            recommend_award(game, 0, "for medically reported wounds received in action")
        if c["kind"] in cmd.battle:
            cmd.battle[c["kind"]] += 1
        cmd.__dict__.setdefault("record", []).append(
            f"{game.datetime_str()}: report by {c['by']} - {c['why']}.")
        ledger["claims"].remove(c)
    if game.turn - ledger["last_review"] >= 3600 and channel(game):
        ledger["last_review"] = game.turn
        cmd._battle_awards(game)
    for award in list(ledger["awards"]):
        from .debrief import settled
        presentation = settled(game) if game.__dict__.get('domain', 'land') == 'land' else channel(game)
        if game.turn >= award["due"] and presentation:
            current = cmd.battle
            cmd.battle = award["evidence"]
            try:
                cmd._award(game, award["level"], award["why"])
            finally:
                cmd.battle = current
            ledger["awards"].remove(award)


def recommend_award(game, level, why, posthumous=False):
    ledger = state(game)
    name = game.command._medal(game, level)
    if level > 0 and f"{name} (second award)" in game.command.medals:
        return None  # do not generate endless presentation errands for a completed citation
    if posthumous:
        # Only reports already received by headquarters can support a posthumous citation.
        return game.command._award(game, level, why, True) if ledger["credited"] > 0 else None
    if any(a["level"] == level for a in ledger["awards"]):
        return None
    ledger["awards"].append(dict(level=level, why=why, due=game.turn + 86400, evidence=dict(game.command.battle)))
    return "recommendation submitted"


def vacancy(game):
    cmd, p = game.command, game.player
    from .command import ECHELON_GRADE
    appointment = state(game).get("appointment")
    if appointment and appointment["from"] == p.rank:
        return appointment["grade"], appointment["title"]
    f = cmd.billet
    if f is not None and f.acting and f.commander is p:
        ceiling = ECHELON_GRADE.get(f.echelon, p.rank)
        if ceiling > p.rank:
            return ceiling, f.title()
    sq = cmd.billet_squad
    if sq is not None and sq.leader is p and p.rank < R.SERGEANT:
        return R.SERGEANT, sq.name
    # A junior private's first class classification is not a command appointment.
    if p.rank == R.PRIVATE:
        return R.PFC, "first class soldier"
    return None


def consider(game, why=""):
    p, cmd = game.player, game.command
    ledger = state(game)
    process(game)
    if not p.alive or p.rank >= R.MARSHAL or game.duty.disgraced or game.duty.rep < -20 or game.renegade:
        return False
    pending = ledger["pending"]
    slot = vacancy(game)
    if pending:
        if slot is None or pending["from"] != p.rank or slot[0] < pending["to"]:
            ledger["pending"] = None
            return False
        if game.turn < pending["due"] or not channel(game):
            return False
        p.rank = pending["to"]
        # Exceptional service is banked, not thrown away after one stripe.
        ledger["spent"] += cmd.promotion_need(pending["from"])
        ledger["last_promotion"] = game.turn
        ledger["pending"] = None
        appointment = ledger.pop("appointment", None)
        if appointment:
            ledger["career_post"] = appointment["title"]
        cmd.merit_at_promotion = cmd.merit
        cmd.promotions.append((game.datetime_str(), p.rank))
        game.msg(f"Personnel orders reach you by {channel(game)}: {p.rank_full}, assigned to {pending['billet']}.", "good")
        if cmd.billet is not None and p.rank >= slot[0]:
            cmd.billet.acting = False
        cmd._after_promotion(game)
        return True
    minimum = 86400 if p.rank < R.LT2 else 7 * 86400
    if not slot or game.turn - ledger["last_promotion"] < minimum or not channel(game):
        return False
    if ledger["credited"] - ledger["spent"] < cmd.promotion_need(p.rank):
        return False
    # A commission is an appointment to an officer vacancy, not a random jump past stripes.
    new = R.LT2 if R.STAFF_SGT <= p.rank < R.LT2 and slot[0] >= R.LT2 else p.rank + 1
    ledger["pending"] = dict(to=new, **{"from": p.rank}, billet=slot[1],
                              due=game.turn + (21600 if new >= R.LT2 else 3600))
    return False


def status(game):
    s = state(game)
    if s["pending"]:
        return "A personnel recommendation is awaiting review and delivery."
    if s["claims"]:
        return "Witness statements are awaiting transmission or review."
    return "Report at HQ for recognition, support allocations and career appointments. Skills improve in the field."
