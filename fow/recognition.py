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
    from .senses import los_clear
    if any(b is not game.player and b.active and not b.downed and b.side == a.side and b.rank > a.rank
           and b.z == a.z and distance(b.pos, a.pos) <= 6 and los_clear(game, *a.pos, *b.pos) for b in game.actors):
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
            c["due"] = game.turn + (0 if at_hq else 30)
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
    if game.turn - ledger["last_review"] >= 60 and channel(game):
        ledger["last_review"] = game.turn
        cmd._battle_awards(game)
    for award in list(ledger["awards"]):
        presentation = channel(game)
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
    ledger["awards"].append(dict(level=level, why=why, due=game.turn + 60, evidence=dict(game.command.battle)))
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
    process(game)
    from .career import consider as field_consider
    return field_consider(game)


def status(game):
    s = state(game)
    if s["pending"]:
        return "Personnel orders: Q to choose advancement once delivered."
    if s["claims"]:
        return "Witness statements are awaiting transmission or review."
    return "Q: field promotions and support choices. Witnessed service and skills improve in the field."
