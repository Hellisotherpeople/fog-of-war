"""Field personnel orders: real delivery, immediate choices, banked service.

The campaign compresses personnel administration, never the evidence or the
supply chain. A promotion changes rank only when the player accepts its duties.
"""
from . import recognition as R
from .data import ranks as GR


def eligible(game):
    p = game.player
    return p.alive and not game.game_over and not game.renegade and not game.duty.disgraced and game.duty.rep >= -20


def options(game):
    from .data.rank_profiles import choices
    return choices(game.player, game.year)


def grades(game):
    return list(dict.fromkeys(r.grade for r in options(game)))


def sync_support(game):
    from .debrief import entitlements
    s = R.state(game)
    s['support_earned'] = max(s.get('support_earned', 0), entitlements(game))


def delivered(game, via):
    s = R.state(game)
    pending = s.get('pending')
    if not pending or pending['from'] != game.player.rank or pending.get('delivered') is not None:
        return False
    pending.update(delivered=game.turn, via=via)
    s['show_promotion'] = True
    game.msg(f'Personnel orders via {via}: advancement is available. Q: choose your rank, duties and support.', 'good')
    return True


def consider(game):
    s, p = R.state(game), game.player
    if not eligible(game):
        return False
    sync_support(game)
    pending = s.get('pending')
    if pending and (pending['from'] != p.rank or pending.get('from_id', p.__dict__.get('rank_id')) != p.__dict__.get('rank_id')):
        s['pending'] = pending = None
    if not pending:
        if not grades(game) or s['credited'] - s['spent'] < game.command.promotion_need(p.rank):
            return False
        s['pending'] = pending = dict(**{'from': p.rank}, from_id=p.__dict__.get('rank_id'), to=grades(game)[0], due=game.turn)
    if pending.get('delivered') is not None:
        return True
    # Legacy recommendations no longer carry a hours/days-long desk timer.
    via = R.channel(game)
    if via:
        return delivered(game, via)
    runner = next((a for a in game.actors if a.ai.get('personnel_dispatch') and a.active and not a.downed), None)
    if runner is None:
        from .dispatches import courier
        runner = courier(game, p)
        if runner is not None:
            runner.ai['personnel_dispatch'] = dict(target=p.pos, origin=runner.pos, issued=game.turn)
    return False


def runner_act(game, a, visible):
    from .ai import path_step, fix_stance
    from .intelligence import distance
    from .senses import los_clear
    job, p = a.ai['personnel_dispatch'], game.player
    if not eligible(game) or not R.state(game).get('pending') or R.state(game)['pending'].get('delivered') is not None:
        job['returning'] = True
    if job.get('returning'):
        if distance(a.pos, job['origin']) <= 2:
            a.ai.pop('personnel_dispatch', None)
            return 100
        point = job['origin']
    else:
        if a.z == p.z and distance(a.pos, p.pos) <= 20 and los_clear(game, *a.pos, *p.pos):
            job['target'] = p.pos
        if a.z == p.z and distance(a.pos, p.pos) <= 2 and a.suppression < 30 and los_clear(game, *a.pos, *p.pos):
            delivered(game, 'runner ' + a.full_name)
            job['returning'] = True
            return 100
        point = job['target']
    if a.suppression >= 30 or any(distance(a.pos, e.pos) <= 8 for e in visible):
        return None
    cost = path_step(game, a, *point, margin=30)
    if cost:
        fix_stance(game, a, 0)
    return cost or 100


def accept(game, grade, duties='keep'):
    """Revalidate the presented choice; accepting twice cannot spend/grant twice."""
    s, p, cmd = R.state(game), game.player, game.command
    pending = s.get('pending')
    chosen = next((r for r in options(game) if r.key == grade or r.grade == grade), None)
    if not eligible(game) or not pending or pending.get('delivered') is None or pending['from'] != p.rank or \
            pending.get('from_id', p.__dict__.get('rank_id')) != p.__dict__.get('rank_id') or \
            chosen is None or duties not in ('keep', 'command') or (duties == 'command' and
            (chosen.command_grade < GR.CORPORAL or game.__dict__.get('domain','land') != 'land')):
        return False
    cost = cmd.promotion_need(p.rank)
    if s['credited'] - s['spent'] < cost:
        return False
    from .data.rank_profiles import assign
    assign(p, chosen)
    grade = chosen.grade
    s.update(spent=s['spent'] + cost, last_promotion=game.turn, pending=None, show_promotion=False,
             career_post='current specialist duties' if duties == 'keep' else
             chosen.appointment or GR.COMMAND_LEVEL.get(grade, 'soldier'))
    s.pop('appointment', None)
    cmd.merit_at_promotion = cmd.merit
    cmd.promotions.append((game.datetime_str(), grade))
    s.setdefault('rank_history', []).append(dict(at=game.datetime_str(), key=chosen.key, title=chosen.title, duties=duties))
    if duties == 'command':
        _command_appointment(game)
    sync_support(game)
    game.msg(f'You accept promotion to {p.rank_full}: {s["career_post"]}. Your remaining service is banked. '
             'Choose support now or retain the allocation in Q.', 'good')
    game.update_orders(force=True)
    return True


def _command_appointment(game):
    p, cmd = game.player, game.command
    if p.rank < GR.LT2:
        if p.rank >= GR.CORPORAL and p.squad is not None:
            from .ai import Order
            p.squad.leader = p
            p.squad.player_led = True
            p.squad.order = Order('follow', issued=game.turn, src='player')
            cmd.billet_squad = p.squad
        # Senior NCOs command their soldiers without being turned into officers.
        return
    from .command import ROLE_ECHELON, ECHELON_GRADE
    echelon = max((e for e, rank in ECHELON_GRADE.items() if rank <= p.rank), key=ECHELON_GRADE.get)
    p.role = next((role for role, e in ROLE_ECHELON.items() if e == echelon), 'officer')
    from . import oob
    oob.update(game)
    cmd._assign_billet(game)
    if echelon in ('platoon', 'company') and p.squad is not None:
        f = p.squad.formation
        while f is not None and f.echelon != echelon:
            f = f.parent
        if f is not None:
            f.commander, f.offmap, f.acting = p, None, False
            cmd.billet = f
    cmd._after_promotion(game)


def present(ps):
    g = ps.game
    s = R.state(g)
    if not s.get('show_promotion') or not eligible(g) or not g.player.body.conscious or ps.popups or \
            ps.inv_screen is not None or ps.mode != 'normal':
        return False
    s['show_promotion'] = False
    ps.stop_auto()
    ps.reset_realtime_clock()
    menu(ps)
    return True


def menu(ps):
    from .command_work_ui import _menu
    from .constants import UI_TEXT, UI_DIM
    g, p = ps.game, ps.game.player
    consider(g)
    s = R.state(g)
    pending = s.get('pending')
    if not pending or pending.get('delivered') is None:
        return rewards(ps)
    s['show_promotion'] = False
    options = []
    from .data.rank_profiles import choices
    for rank in choices(p, g.year):
        path = 'commission' if p.rank < GR.LT2 <= rank.grade else rank.category
        options.append((rank.title + ' — ' + path, rank.key, None, True))
    options.append(('Decide later; keep these orders in Q', None, None, True))
    def pick(grade):
        if grade is None:
            return
        from .data.rank_profiles import choices
        chosen = next((r for r in choices(p, g.year) if r.key == grade), None)
        if chosen is None:
            return
        def duty(choice):
            if choice and accept(g, grade, choice):
                rewards(ps)
        _menu(ps, 'Promotion — choose your duties', [
            ('Keep my current job and crew position', 'keep', None, True),
            ('Take land command: ' + (chosen.appointment or GR.COMMAND_LEVEL.get(chosen.command_grade, 'specialist duties')), 'command', None,
             chosen.command_grade >= GR.CORPORAL and g.__dict__.get('domain','land') == 'land'),
            ('Back to promotion choices', None, None, True)],
            lambda choice: duty(choice) if choice else menu(ps),
            [(f'{p.rank_full} → {chosen.title}. '
              f'Uses {g.command.promotion_need(p.rank):g} reviewed service; no time waiting at base.', UI_TEXT),
             ('Land command assigns an existing formation. Aboard ship or aircraft, keep your crew position; command stations remain part of ship and air operations.', UI_DIM)])
    _menu(ps, 'Field promotion — orders received', options, pick,
          [(f'Delivered via {pending.get("via", "personnel orders")}. '
            f'Reviewed service available: {s["credited"] - s["spent"]:.1f}.', UI_TEXT),
           ('Choose a national rank or specialist appointment. A warrant is distinct from a line commission; keeping senior soldier duties is always possible.', UI_DIM)])


def rewards(ps):
    from .command_work_ui import _menu
    from .constants import UI_DIM, UI_TEXT
    from . import debrief as D
    g = ps.game
    sync_support(g)
    count = D.requests(g)
    def pick(kind):
        if kind == 'support':
            units = D.support_units(g)
            return _menu(ps, 'Available support units', [(sq.name, sq, None, True) for sq in units] or
                         [('No local unit available; retain allocation', None, UI_DIM, False)],
                         lambda sq: D.allocate(g, 'support', sq) if sq else None)
        if kind:
            D.allocate(g, kind)
    _menu(ps, 'Field service — support choices', [
        ('Equipment authority: 120 requisition credit — 1 allocation', 'kit', None, count > 0),
        ('Attach an available local support unit — 1 allocation', 'support', None, count > 0),
        ('Reserve vehicle ammunition, fuel and spares — 1 allocation', 'refit', None, count > 0 and g.player.vehicle is not None),
        ('Keep allocations for later / return to duty', None, None, True)], pick,
        [(f'{count} support allocation(s) available. Unspent allocations remain yours.', UI_TEXT),
         ('Equipment is drawn from a quartermaster. Vehicle stores are reserved now and loaded at a friendly HQ. '
          'Attached soldiers keep their own leaders.', UI_DIM)])
