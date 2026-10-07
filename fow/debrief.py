"""HQ debriefs, career appointments and finite support allocations.

Rank is a career; exceptional combat service can also support the soldier's current
job. Thresholds and staff appointments are campaign abstractions, not regulations.
"""
from __future__ import annotations

from . import recognition as R
from .data import ranks as GR
from .intelligence import distance, headquarters


def eligible(game):
    return (game.player.alive and not game.renegade and not game.duty.disgraced
            and game.duty.rep >= -20 and game.__dict__.get('domain', 'land') == 'land')


def requests(game):
    s = R.state(game)
    return max(0, s.get('support_earned', 0) - s.get('support_used', 0))


def entitlements(game):
    """One accounting source; rereading a citation never grants it again."""
    from .awards import records
    merit = int(R.state(game)['credited'] // 12)
    awards = sum(a['level'] for a in records(game.command, game.player.nation)
                 if not a.get('posthumous'))
    promotions = sum(1 if rank < GR.LT2 else 2 if rank < GR.COLONEL else 3
                     for _, rank in game.command.promotions)
    return merit + awards + promotions


def request_report(game, automatic=False):
    if not eligible(game):
        return False
    s = R.state(game)
    if not s.get('report_order'):
        s['report_order'] = dict(issued=game.turn, automatic=automatic)
        game.msg('Report to a friendly HQ for an after-action debrief, recognition and support. '
                 'T marks the route; current operational orders still take precedence.', 'info')
    return True


def entry(game):
    s = R.state(game)
    maybe_report(game)
    ticket = s.get('report_order')
    if not ticket or game.__dict__.get('domain', 'land') != 'land':
        return None
    from .contacts import assigned_target
    dest = assigned_target(game, ticket, 'hq')
    point = None
    if dest:
        if dest['sector'] == (game.sector.x, game.sector.y):
            point = (*dest['point'], dest['label'])
        else:
            from .base import _next_edge
            from .orders import exit_point
            edge = _next_edge(game, dest['sector'])
            if edge:
                point = (*exit_point(game, edge), 'Route to HQ at ' + game.strategic.at(*dest['sector']).name)
    return dict(key='personnel', who='HQ debrief and decorations', how='your service notebook',
                text='Report your actions at HQ. Bring surviving witnesses or your crew. '
                     + ('Report to ' + dest['label'] + '; follow the marked route.' if dest else
                        'No staffed HQ is located: obtain a map or find a friendly command post.'),
                issued=ticket['issued'], due=None, reward='reviewed service, decorations, career opportunities and unit support',
                penalty='no penalty for postponing; evidence and recognition remain pending', urgent=False,
                point=point, authority=0)


def plan(ps):
    from .service import drive_step
    g, p = ps.game, ps.game.player
    order = entry(g)
    if settled(g):
        return 'report to the HQ personnel desk', lambda: menu(ps)
    if not order or not order['point']:
        return 'consult T for the HQ destination', ps.cmd_orders_book
    dest = R.state(g)['report_order']['destination']
    point = order['point']
    remote = dest['sector'] != (g.sector.x, g.sector.y)
    if p.vehicle is not None and distance(p.pos, point[:2]) > 2:
        return 'drive toward ' + point[2], lambda: drive_step(ps, point[:2])
    if remote:
        from .base import _next_edge
        edge = _next_edge(g, dest['sector'])
        return point[2], lambda: ps._travel_chosen(edge) if distance(p.pos, point[:2]) <= 2 else \
            ps.start_travel(*point[:2], then=lambda: ps._travel_chosen(edge), stop_short=1)
    return 'proceed to ' + point[2], lambda: ps.start_travel(*point[:2], stop_short=2)


def release_allowed(game):
    """Routine reporting supports duty in a quiet, secured sector, not an unfinished mission."""
    p = game.player
    from .base import _done
    base_order = game.__dict__.get('base_order')
    return (game.sector.control == p.side and game.turn - p.fired_turn > 300 and p.suppression < 10
            and not (game.__dict__.get('mission') or game.__dict__.get('field_order'))
            and (not base_order or _done(game, base_order)))


def settled(game):
    if not eligible(game) or not headquarters(game) or game.player.suppression >= 10 or game.turn - game.player.fired_turn <= 120:
        return False
    from .contacts import people
    from .senses import los_clear
    return any(distance(game.player.pos, a.pos) <= 3 and los_clear(game, *game.player.pos, *a.pos)
               for a in people(game, 'hq'))


def review(game):
    if not settled(game):
        game.msg('Report within speaking distance of the adjutant or personnel staff at a quiet, functioning friendly HQ.', 'info')
        return False
    s = R.state(game)
    R.process(game)
    if s.get('debrief_started') is None:
        s['debrief_started'] = game.turn
        s['debrief_work'] = 0
        game.msg('The adjutant takes your account and checks the available witness statements. '
                 'Remain at HQ for five minutes; fighting or leaving interrupts the interview.', 'info')
    return True


def finish_review(game):
    s = R.state(game)
    R.process(game)
    game.command._battle_awards(game)
    R.consider(game)
    new = max(0, entitlements(game) - s.get('support_earned', 0))
    s['support_earned'] = s.get('support_earned', 0) + new
    s['last_debrief_credit'] = s['credited']
    s['last_debrief_awards'] = len(game.command.medals)
    s['last_debrief_promotions'] = len(game.command.promotions)
    s['last_debrief'] = game.turn
    s.pop('debrief_started', None)
    s.pop('report_order', None)
    if game.__dict__.get('order_focus') == 'personnel':
        game.order_focus = None
    from .intelligence import copy_map
    copy_map(game)
    text = f'HQ records your service. {new} additional support allocation(s) authorized; {requests(game)} available.'
    if s['claims']:
        text += ' Some statements still need surviving witnesses or review.'
    if s['awards']:
        text += ' Decoration recommendations have gone forward; approval is still pending.'
    game.msg(text + ' You may keep your present job or apply for advancement at the desk.', 'good')
    game.command.__dict__.setdefault('record', []).append(game.datetime_str() + ': after-action debrief; ' + text)
    game.update_orders(force=True)


def career_offer(game):
    p, s = game.player, R.state(game)
    if p.rank >= GR.MARSHAL:
        return None, 'You hold the highest campaign rank.'
    if s.get('pending') or s.get('appointment'):
        return None, 'Your appointment is already under review.'
    if 'last_debrief' not in s:
        return None, 'Complete an HQ debrief first.'
    required = game.command.promotion_need(p.rank)
    if s['credited'] - s['spent'] < required:
        return None, f'Next appointment needs {required:g} reviewed service; {s["credited"] - s["spent"]:.1f} banked.'
    minimum = 86400 if p.rank < GR.LT2 else 7 * 86400
    left = minimum - (game.turn - s['last_promotion'])
    if left > 0:
        return None, f'Continue serving: next appointment review in about {max(1, (left + 3599) // 3600)} hours.'
    grade = GR.LT2 if GR.STAFF_SGT <= p.rank < GR.LT2 else p.rank + 1
    from .skills import level
    needed = min(6.5, 3 + grade * .2) if grade >= GR.LT2 else 0
    if level(p, 'leadership') < needed:
        return None, f'Leadership training needed for this appointment ({needed:.1f}); the HQ course remains available.'
    title = ('junior NCO appointment' if grade <= GR.SERGEANT else 'senior NCO appointment' if grade < GR.LT2 else
             'junior officer appointment' if grade <= GR.LT else 'unit command / staff appointment' if grade < GR.BRIGADIER else
             'higher command / general staff appointment')
    return dict(grade=grade, title=title, **{'from': p.rank}), ''


def apply_career(game):
    if not settled(game):
        return False
    offer, why = career_offer(game)
    if offer is None:
        game.msg(why, 'info')
        return False
    R.state(game)['appointment'] = offer
    R.consider(game)
    game.msg('HQ endorses your application for ' + offer['title'] + '. Personnel approval and delivery are still required. '
             'Your remaining service record is retained for later advancement.', 'good')
    return True


def support_units(game):
    p = game.player
    from .data.ranks import same_army
    return [sq for sq in game.squads if sq is not p.squad and sq.side == p.side and same_army(sq.nation, p.nation)
            and sq.kind in ('rifle', 'inf', 'engineer', 'mg', 'mortar', 'at', 'tank', 'sniper') and not sq.gone
            and sq.id not in game.command.attached and not getattr(sq, 'no_count', False)
            and sq.order.kind in ('hold', 'reserve', 'regroup') and sq.order.src != 'player'
            and game.turn - sq.last_contact > 300
            and any(a.active and not a.downed and distance(a.pos, p.pos) <= 40 for a in sq.members)]


def allocate(game, kind, squad=None):
    if not settled(game) or not requests(game):
        return False
    s, p = R.state(game), game.player
    if kind == 'kit':
        from .qmui import add_credit
        add_credit(game, 120)
        p.ai['hq_equipment'] = True
        text = 'HQ authorizes 120 requisition credit and signals/observation kit for your duty. Draw available equipment at a quartermaster.'
    elif kind == 'support':
        if squad not in support_units(game):
            game.msg('That unit is no longer available for attachment.', 'info')
            return False
        from .ai import Order
        game.command.attached.add(squad.id)
        squad.order = Order('follow', target=p.pos, issued=game.turn, src='player')
        squad.rep['hq_attachment'] = game.turn
        text = f'HQ attaches {squad.name} to your mission. Its own leader remains in command; C gives it instructions.'
    elif kind == 'refit':
        v = p.vehicle
        if v is None or not v.active or v.ai.get('hq_refit'):
            game.msg('Bring your vehicle to HQ; only one refit can be in progress.', 'info')
            return False
        from .maintenance import shells_short, mg_short
        from .sustain import stores, take
        stock = stores(game.sector, p.side)
        shells = min(shells_short(v), int(stock['ammo'] * 4))
        belts = min(mg_short(v), int(max(0, stock['ammo'] - shells / 4) * 250))
        fuel = min(max(0, 100 - v.ai.get('fuel', 100)), stock['fuel'] * 5)
        parts = min(max(0, 8 - v.ai.get('field_parts', 0)), stock['parts'])
        if shells + belts + fuel + parts <= 0:
            game.msg('No needed stores can be issued. Your allocation remains available.', 'info')
            return False
        take(game.sector, p.side, 'ammo', shells / 4 + belts / 250)
        take(game.sector, p.side, 'fuel', fuel / 5)
        take(game.sector, p.side, 'parts', parts)
        duration = 300 * v.vt.get('supply_load', 1)
        v.ai['hq_refit'] = dict(shells=shells, belts=belts, fuel=fuel, parts=parts, work=0, duration=duration,
                                sector=(game.sector.x, game.sector.y))
        text = f'Stores reserved: {shells} shells, {belts} MG rounds, fuel {fuel:.0f}, spares {parts:g}. '
        text += f'Remain at HQ for {duration // 60:g} minutes to load. Components still need repair work; hull damage needs a workshop.'
    else:
        return False
    s['support_used'] = s.get('support_used', 0) + 1
    game.msg(text, 'good')
    return True


def tick(game):
    if not eligible(game):
        return
    s = R.state(game)
    dt = min(30, max(0, game.turn - s.get('desk_tick', game.turn)))
    s['desk_tick'] = game.turn
    if s.get('debrief_started') is not None and settled(game):
        s['debrief_work'] = s.get('debrief_work', 0) + dt
        if s['debrief_work'] >= 300:
            finish_review(game)
    if s.get('training') and settled(game):
        s['training']['work'] += dt
        if s['training']['work'] >= 3600:
            p = game.player
            p.skills['leadership'] = min(6.7, p.skills.get('leadership', 0) + .5)
            s.pop('training')
            game.msg('You complete an hour of staff exercises and command instruction. Your leadership improves.', 'good')
    from .maintenance import quiet, _load_rounds, full_load
    from .sustain import deliver
    for v in game.vehicles:
        job = v.ai.get('hq_refit')
        if not job or not v.active or not headquarters(game, v) or not quiet(game, v):
            continue
        if job['sector'] != (game.sector.x, game.sector.y):
            continue
        job['work'] += dt
        if job['work'] < job.get('duration', 300):
            continue
        before = v.ap + v.he
        _load_rounds(v, job['shells'])
        belts = min(job['belts'], max(0, full_load(v)[2] - v.mg_ammo))
        fuel = min(job['fuel'], max(0, 100 - v.ai.get('fuel', 100)))
        v.mg_ammo += belts
        v.ai['fuel'] = v.ai.get('fuel', 100) + fuel
        v.ai['field_parts'] = v.ai.get('field_parts', 0) + job['parts']
        deliver(game.sector, v.side, 'ammo', (job['shells'] - (v.ap + v.he - before)) / 4 + (job['belts'] - belts) / 250)
        deliver(game.sector, v.side, 'fuel', (job['fuel'] - fuel) / 5)
        v.ai.pop('hq_refit')
        game.msg(f'The {v.vt.name} has taken aboard its authorized ammunition, fuel and field spares.', 'good')
    maybe_report(game)


def maybe_report(game):
    # The player's notebook can remember to report an action without magically telling HQ.
    s = R.state(game)
    changed = (sum(c['weight'] for c in s['claims']) + s['credited'] - s.get('last_debrief_credit', 0) >= 3
               or len(game.command.medals) > s.get('last_debrief_awards', 0)
               or len(game.command.promotions) > s.get('last_debrief_promotions', 0)
               or any(a['due'] <= game.turn for a in s['awards']))
    if changed and s.get('debrief_started') is None and game.turn - s.get('last_debrief', -3600) >= 600:
        request_report(game, automatic=True)


def menu(ps):
    from .command_work_ui import _menu
    from .constants import UI_DIM, UI_TEXT
    g, p = ps.game, ps.game.player
    if not settled(g):
        request_report(g)
        g.msg('The HQ report route is in T. Your present operational orders still govern until you can be released.', 'info')
        return ps.cmd_orders_book()
    s = R.state(g)
    offer, why = career_offer(g)
    from .data.ranks import rank_title
    title = 'Apply for ' + rank_title(p.nation, offer['grade'], False) if offer else 'Career appointment: not yet eligible'
    lines = [(f'Reviewed service: {s["credited"]:.1f}; banked toward advancement: {s["credited"] - s["spent"]:.1f}. '
              f'Authorized support requests: {requests(g)}.', UI_TEXT),
             ('You can keep your crew position. Decorations, unit support and career advancement are separate decisions.', UI_DIM)]
    if not offer:
        lines.append((why, UI_DIM))
    if s.get('pending'):
        lines.append((f'Personnel decision pending: about {max(0, (s["pending"]["due"] - g.turn + 59) // 60)} minutes.', UI_DIM))
    if s.get('awards'):
        lines.append((f'{len(s["awards"])} decoration recommendation(s) awaiting approval.', UI_DIM))
    if s.get('debrief_started') is not None:
        lines.append((f'Debrief: {s.get("debrief_work", 0):.0f}/300 seconds at HQ.', UI_TEXT))
    if s.get('training'):
        lines.append((f'Leadership course: {s["training"]["work"]:.0f}/3600 seconds at HQ.', UI_TEXT))
    opts = [('Submit / review my after-action report', 'review', None, s.get('debrief_started') is None),
            (title, 'career', None, offer is not None),
            ('Leadership course: one hour at HQ (+0.5; up to staff competence)', 'train', None,
             not s.get('training') and p.skills.get('leadership', 0) < 6.7),
            ('Wait at HQ for ten minutes (interruptible)', 'wait', None, True),
            ('Equipment requisition authority — 1 support request', 'kit', None, requests(g) > 0),
            ('Vehicle ammunition, fuel and field spares — 1 request', 'refit', None,
             requests(g) > 0 and p.vehicle is not None and not p.vehicle.ai.get('hq_refit')),
            ('Attach an available local support unit — 1 request', 'support', None, requests(g) > 0),
            ('Keep my present job / return to duty', 'done', None, True)]
    def pick(kind):
        if kind == 'review':
            review(g)
        elif kind == 'career':
            apply_career(g)
        elif kind == 'train':
            if settled(g) and not s.get('training') and p.skills.get('leadership', 0) < 6.7:
                s['training'] = dict(work=0)
                g.msg('The staff course begins. Remain at HQ for an hour; leaving or fighting pauses instruction.', 'info')
        elif kind == 'wait':
            return ps.begin_wait('time', 600)
        elif kind == 'support':
            units = support_units(g)
            return _menu(ps, 'Available units — retain their leaders',
                         [(sq.name, sq, None, True) for sq in units] or [('None available; retain your allocation', None, UI_DIM, False)],
                         lambda sq: allocate(g, 'support', sq) if sq else None)
        elif kind != 'done':
            allocate(g, kind)
    _menu(ps, 'HQ — service review and support', opts, pick, lines)
