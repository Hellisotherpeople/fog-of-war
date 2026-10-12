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
    from .career import grades
    p, s = game.player, R.state(game)
    choices = grades(game)
    if not choices:
        return None, 'You hold the highest campaign rank.'
    required = game.command.promotion_need(p.rank)
    if s['credited'] - s['spent'] < required:
        return None, f'Next advancement needs {required:g} reviewed service; {s["credited"] - s["spent"]:.1f} banked.'
    return dict(grade=choices[0], title='field appointment', **{'from': p.rank}), ''


def apply_career(game):
    return R.consider(game)


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
    if not eligible(game) or not requests(game):
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
            game.msg('Only one refit can be reserved for an active vehicle.', 'info')
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
        text += f'Load at a friendly HQ: {duration // 60:g} minutes. Components still need repair work; hull damage needs a workshop.'
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
    R.consider(game)
    maybe_report(game)


def maybe_report(game):
    # The player's notebook can remember to report an action without magically telling HQ.
    s = R.state(game)
    # A desk visit is useful for evidence that has no reporting channel. Radio
    # recognition and field promotion never generate a mandatory trip back.
    changed = sum(c['weight'] for c in s['claims'] if c.get('reported') is None) >= 3 and not R.channel(game)
    if changed and s.get('debrief_started') is None and game.turn - s.get('last_debrief', -3600) >= 600:
        request_report(game, automatic=True)


def menu(ps):
    from .career import menu as field_menu
    return field_menu(ps)
