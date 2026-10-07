"""Friendly-fire evidence and restoration of battlefield trust.

An aim point is not a conviction. We need an identifiable friendly target,
an unambiguous attack and surviving witnesses. Accidents have physical costs,
but neither casualty counts nor the absence of enemies establish intent.
"""
from __future__ import annotations

from contextlib import contextmanager

from .intelligence import distance
from .senses import los_clear


def fresh():
    return dict(version=1, warned=None, last_attack=-999999, valor=0., restored=0,
                last_rebuke=-999999, allegations=[])


def state(game):
    duty = game.duty
    if 'conduct' not in duty.__dict__:
        migrate(game)
    return duty.conduct


def migrate(game):
    """Old counters did not record intent; don't preserve an unsupported conviction."""
    duty = game.duty
    if 'conduct' in duty.__dict__:
        return
    duty.conduct = fresh()
    incidents, deaths, accidents = duty.ff_incidents, duty.murders, duty.ff_accidents
    if incidents or accidents:
        duty.conduct['legacy_unclassified'] = dict(incidents=incidents, deaths=deaths, accidents=accidents)
        duty.rep = min(100., duty.rep + 15 * incidents + 25 * deaths + 2 * accidents)
        duty.strikes = max(0, duty.strikes - int(accidents >= 4) - int(accidents >= 7))
        duty.ff_incidents = duty.murders = 0
        if incidents:
            duty.arrest = None
            duty.disgraced = False
            game.renegade = False
            _restore_command(game)
        game.msg('Earlier friendly-fire accusations lacked evidence of intent. '
                 'Those accusations no longer make your side hostile.', 'info')


def _observers(game, source, point):
    p = game.player
    radius = min(25, game.view_range_cache)
    return [a.id for a in game.actors if a is not p and a.side == p.side and a.active and not a.downed
            and not a.ai.get('civilian') and distance(a.pos, source.pos) <= radius
            and distance(a.pos, point) <= radius
            and los_clear(game, a.x, a.y, source.x, source.y) and los_clear(game, a.x, a.y, *point)]


def current(game):
    return game.__dict__.get('_conduct_attack')


@contextmanager
def attack(game, source, point=None, target=None, *, controlled=False, evidence=None, collateral=False):
    """One trigger pull, burst, shell or melee exchange, including secondary damage.

    Saved shells/grenades keep this firing-time evidence, never a later aim point.
    AI vehicle fire is not a deliberate attack by its passenger or driver.
    """
    previous = current(game)
    p = game.player
    mine = source is not None and p is not None and (source is p or source is p.vehicle)
    if collateral and previous is not None and previous['source'] == getattr(source, 'id', None):
        yield previous
        return
    event = evidence
    if event is None and mine:
        point = point or source.pos
        target = target or game.soldier_at.get(point) or game.vehicle_at.get(point)
        controlled = controlled or source is p
        friendly = (target is not None and target is not p and target is not p.vehicle
                    and (target.side == p.side or target.ai.get('civilian'))
                    and getattr(target, 'alive', not getattr(target, 'dead', False)))
        # Err toward mistaken identification during close fighting. The test uses
        # the situation at firing time, not whether the enemy survived the shell.
        contested = any(distance(e.pos, point) <= 8 and game.can_see(*e.pos)
                        for e in game.enemies_of(p.side) if e is not p)
        deliberate = (controlled and not collateral and friendly and game.can_see(*target.pos)
                      and distance(source.pos, target.pos) <= game.view_range_cache and not contested)
        event = dict(source=source.id, responsible=p.id, turn=game.turn, point=point, deliberate=bool(deliberate),
                     witnesses=_observers(game, source, point) if deliberate else [], hits={}, handled=False)
    game._conduct_attack = event
    try:
        yield event
    finally:
        game._conduct_attack = previous
        if event is not None and event['hits'] and not event['handled']:
            _resolve(game, event)


def hit(game, victim, killed=False, attacker=None):
    event = current(game)
    if event is not None and event['source'] == getattr(attacker, 'id', None):
        event['hits'][victim.id] = dict(killed=killed or event['hits'].get(victim.id, {}).get('killed', False),
                                       point=victim.pos, civilian=bool(victim.ai.get('civilian')))
        if event['deliberate']:
            victim.ai['deliberate_friendly_wound'] = game.turn
        return
    # Unattributed collateral, tracks, fire and old saved explosives cannot prove intent.
    _accident(game)


def _accident(game):
    s = state(game)
    if s.get('accident_turn') == game.turn:
        return
    s['accident_turn'] = game.turn
    game.duty.ff_accidents += 1
    if game.turn - s['last_rebuke'] >= 30:
        s['last_rebuke'] = game.turn
        game.msg('Friendly casualty! Check your fire and help the wounded.', 'warn')


def _resolve(game, event):
    event['handled'] = True
    if event.get('responsible', game.player.id) != game.player.id:
        return  # succession does not transfer culpability for a predecessor's rounds
    s = state(game)
    witnesses = [a for a in game.actors if a.id in event['witnesses'] and a.active and not a.downed
                 and a.side == game.player.side
                 and any(distance(a.pos, h['point']) <= game.view_range_cache
                         and los_clear(game, a.x, a.y, *h['point']) for h in event['hits'].values())]
    if not event['deliberate'] or not witnesses:
        _accident(game)
        return
    duty = game.duty
    witness = max(witnesses, key=lambda a: a.rank)
    deaths = sum(h['killed'] for h in event['hits'].values())
    duty.ff_incidents += 1
    duty.murders += sum(h['killed'] and not h['civilian'] for h in event['hits'].values())
    s['civilian_killings'] = s.get('civilian_killings', 0) + sum(
        h['killed'] and h['civilian'] for h in event['hits'].values())
    duty.rep -= 15 + (25 if deaths else 0)
    s['last_attack'], s['valor'] = game.turn, 0.
    s['allegations'].append(dict(turn=game.turn, deaths=deaths, by=witness.full_name))
    del s['allegations'][:-40]
    # Multiple fragments or simultaneous shells cannot manufacture disobedience
    # to a warning that had not yet been delivered when they were fired.
    if s['warned'] is not None and 0 < event['turn'] - s['warned'] <= 120:
        duty.turn_on_player(game, witness)
    else:
        duty._say(game, witness, 'ff_rebuke', 'Cease fire! Those are civilians!' if any(
            h['civilian'] for h in event['hits'].values()) else 'Cease fire! You are aiming at our own men!')
        if deaths and not duty.arrest:
            duty.arrest = dict(turn=game.turn, by=witness.id)
            game.msg('A witnessed attack is on report. Cease fire and put away your weapon '
                     '(d; leave the vehicle with e), or help against the enemy to regain trust.', 'warn')
    s['warned'] = game.turn
    game.update_orders(force=True)


def valor(game, kind, weight):
    """Fast local reconciliation from newly witnessed service, not an amnesty."""
    duty, s = game.duty, state(game)
    event = current(game)
    if event is not None and event['deliberate']:
        return
    if not (game.renegade or duty.arrest or duty.disgraced or duty.rep < 0):
        return
    if game.turn <= s['last_attack']:
        return                       # the same attack cannot both offend and rehabilitate
    gain = (3 if weight >= .6 else 1) if kind == 'kills' else 3 if kind == 'objectives' else \
           min(3, weight) if kind == 'assistance' else 0
    if gain <= 0:
        return
    s['valor'] += gain
    duty.rep = min(100., duty.rep + gain * 10)
    if s['valor'] < 3:
        game.msg(f'Your comrades witnessed your help against the enemy. '
                 f'Trust returning: {s["valor"]:g}/3.', 'good')
        game.update_orders(force=True)
        return
    game.renegade = False
    duty.arrest = None
    duty.disgraced = False
    duty.rep = max(0., duty.rep)
    s['warned'] = None
    s['valor'] = 0.
    s['restored'] += 1
    _restore_command(game)
    game.command.__dict__.setdefault('record', []).append(
        f'{game.datetime_str()}: witnessed battlefield service restored the unit\'s trust; '
        'earlier disciplinary reports remain on record.')
    game.msg('Your comrades have seen you fight for them. They stand down and cooperate again. '
             'Report to HQ for your debrief; earlier misconduct remains on record.', 'good')
    from .debrief import request_report
    request_report(game, automatic=True)
    game.update_orders(force=True)


def _restore_command(game):
    game._enemy_arr = {}
    game.__dict__.pop('_enemy_idx', None)
    p = game.player
    if p.squad is not None and p.squad.leader is p:
        p.squad.player_led = True
    suspended = state(game).pop('suspended_command', None)
    if suspended:
        formation, squad = suspended
        if formation is not None and formation.commander is p and game.command.billet is None:
            game.command.billet = formation
        if squad is not None and squad.leader is p and game.command.billet_squad is None:
            game.command.billet_squad = squad
    brain = game.brains[p.side]
    brain.contacts.pop(p.id, None)
    brain.urgent = True
    game.__dict__.get('intel_pending', {}).pop((p.side, p.id), None)
    for sq in game.squads:
        if sq.side == p.side:
            sq.rep.get('local_contacts', {}).pop(p.id, None)
    for a in [*game.actors, *game.vehicles]:
        if a.side == p.side:
            a.visible = [e for e in a.visible if e is not p]
            a.vis_turn = -999999
            a.ai.get('staff_contacts', {}).pop(p.id, None)


def status(game):
    s = state(game)
    return (f'Cease friendly fire. Three witnessed enemy kills, a vehicle knockout or a rescue under fire '
            f'can restore trust. Progress: {s["valor"]:g}/3. Then report to HQ.')
