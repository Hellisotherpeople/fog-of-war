"""Useful destinations from visible people and marked friendly service posts."""
from .intelligence import distance, headquarters

ROLES = {'intel': ('intel',), 'supply': ('quartermaster',), 'medical': ('surgeon', 'medic'),
         'repairs': ('motor_sergeant', 'mechanic', 'armourer'), 'hq': ('adjutant', 'clerk', 'ops_officer', 'intel')}
POSTS = {'intel': ('hq', 'intel'), 'supply': ('depot',), 'medical': ('aid',),
         'repairs': ('motor_pool', 'factory'), 'hq': ('hq',)}
NAMES = {'intel': 'intelligence officer', 'supply': 'quartermaster', 'medical': 'medical staff',
         'repairs': 'fitters', 'hq': 'HQ personnel desk'}


def documents(game):
    from .logistics import DOCS
    return [it for it in game.player.inv if it.tid in DOCS and (it.data or {}).get('side') != game.player.side]


def people(game, kind):
    p = game.player
    from .senses import player_can_see_actor
    facilities = [r for r in getattr(game.map, 'gen_positions', []) if r.get('kind') in POSTS[kind]
                  and r.get('side') == p.side and not r.get('destroyed')]
    # A staffed post on a known map is a legitimate place to ask for its specialist.
    known_post = p.has_tool('map') is not None or headquarters(game)
    out = [a for a in game.actors if a is not p and a.side == p.side and a.active and not a.downed
           and a.role in ROLES.get(kind, ()) and (kind != 'hq' or headquarters(game, a)) and
           (player_can_see_actor(game, a) or known_post and a.squad is not None and
            getattr(a.squad, 'no_count', False) and any(distance(a.pos, (r['x'], r['y'])) <= 10 for r in facilities))]
    return sorted(out, key=lambda a: distance(p.pos, a.pos))


def target(game, kind):
    candidates = people(game, kind)
    if candidates:
        a = candidates[0]
        dest = dict(sector=(game.sector.x, game.sector.y), point=a.pos, person=a.id, label=a.full_name)
        landscape = game.__dict__.get('landscape')
        if landscape is not None and landscape.frame is game.map:
            dest['world'] = landscape.world_pos(*a.pos)
            dest['sector'] = (dest['world'][0]//landscape.w, dest['world'][1]//landscape.h)
        return dest
    from .service import destination
    dest = destination(game, POSTS[kind])
    return dict(dest, person=None, label=NAMES[kind]) if dest else None


def _staff_at(game, kind, point, radius=12):
    """The specialists actually at a post, seen or not: the post is known, so are its people."""
    return [a for a in game.actors if a is not game.player and a.side == game.player.side and a.active
            and not a.downed and a.role in ROLES.get(kind, ()) and distance(a.pos, point) <= radius]


def _lose(game, ticket):
    ticket['destination_lost'] = 'The assigned staff are missing, incapacitated or their post is no longer operating. Select another visit in X.'
    game.msg(ticket['destination_lost'], 'warn')
    return None


def assigned_target(game, ticket, kind):
    """A visit keeps its post/person; casualties do not create another appointment.

    Walking up to a post, its people are often out of sight behind its walls: that is not a
    lost appointment. Only a post that no longer operates, or staff who are no longer there
    when the player arrives and can see the place, ends it.
    """
    from .service import resolve, destination_available
    if ticket.get('destination') is None and not ticket.get('destination_lost'):
        ticket['destination'] = target(game, kind)
    dest = resolve(game, ticket.get('destination'))
    if not dest or ticket.get('destination_lost'):
        return None
    if not dest.get('world') and tuple(dest['sector']) != (game.sector.x,game.sector.y):
        if dest.get('person') is not None or destination_available(game,dest,POSTS[kind]):
            return dest
    landscape = game.__dict__.get('landscape')
    framed = landscape is not None and landscape.frame is game.map
    point = dest.get('point')
    if point is not None and not game.map.in_bounds(*point):
        return dest              # still beyond the simulated frame: keep walking
    post = dest.get('post') or (point if dest.get('person') is None else None)
    if post is not None and dest.get('kind') is not None and not destination_available(game, dict(dest, point=post), POSTS[kind]):
        return _lose(game, ticket)

    def follow(person):
        dest.update(point=person.pos, label=person.full_name)
        if framed:
            dest['world'] = landscape.world_pos(*person.pos)
            dest['sector'] = (dest['world'][0]//landscape.w, dest['world'][1]//landscape.h)
        return dest
    known = people(game, kind)
    person = next((a for a in known if a.id == dest.get('person')), None)
    if person is not None:
        return follow(person)
    if post is not None:
        seen = [a for a in known if distance(a.pos, post) <= 12]
        if seen:
            person = min(seen, key=lambda a: distance(a.pos, game.player.pos))
            dest.update(person=person.id, post=post)
            return follow(person)
        # Out of sight behind the post's walls is still at the post; never a tracking beacon.
        if _staff_at(game, kind, post) or distance(game.player.pos, post) > 6 or not game.can_see(*post):
            dest['point'] = post
            return dest
        return _lose(game, ticket)
    if point and (distance(game.player.pos, point) > 6 and not game.can_see(*point)):
        return dest  # last known location, never a live tracking beacon
    return _lose(game, ticket)


def request(game, kind):
    """An X destination is a saved order, with the same arrow and Enter action as T."""
    service_ticket = game.player.ai.get('service_order')
    if service_ticket and service_ticket.get('destination_lost') and kind == (
            'hq' if service_ticket['kind'] == 'conference' else 'repairs'):
        for key in ('destination', 'destination_lost', 'loss_reported'):
            service_ticket.pop(key, None)
    if kind == 'hq':
        from .debrief import request_report
        from .recognition import state
        personnel = state(game)
        if (personnel.get('report_order') or {}).get('destination_lost'):
            personnel.pop('report_order', None)
        return 'personnel' if request_report(game) else None
    if kind == 'intel' and documents(game):
        game.player.ai.pop('intelligence_order', None)
        entry(game)
        return 'intelligence'
    if kind not in ROLES:
        return None
    game.player.ai.setdefault('contact_orders', {})[kind] = dict(issued=game.turn, destination=target(game, kind))
    return 'contact:' + kind


def entries(game):
    if game.__dict__.get('domain', 'land') != 'land':
        return []
    out = []
    for kind, ticket in game.player.ai.get('contact_orders', {}).items():
        dest = assigned_target(game, ticket, kind)
        text = ticket.get('destination_lost') or ('Speak to ' + dest['label'] + ' (' + NAMES[kind] + '). Follow the marked route.' if dest else
                'Locate ' + NAMES[kind] + ': no suitable person or service post is known yet.')
        out.append(dict(key='contact:' + kind, who='Visit ' + NAMES[kind], how='your selected service visit',
                        text=text, issued=ticket['issued'], due=None, reward='access to the staff and services you need',
                        penalty='no penalty for postponing this visit', urgent=False, point=route(game, dest), authority=0))
    return out


def complete(game, kind):
    game.player.ai.get('contact_orders', {}).pop(kind, None)
    if game.__dict__.get('order_focus') == 'contact:' + kind:
        game.order_focus = None


def met(game, person):
    """Visits also finish through normal talk/right-click interactions, not only Enter."""
    visits = game.player.ai.get('contact_orders', {})
    if not visits or not person.active or person.downed or person.side != game.player.side or \
            distance(game.player.pos, person.pos) > 2:
        return
    from .senses import los_clear
    if not los_clear(game, *game.player.pos, *person.pos):
        return
    changed = False
    for kind, ticket in list(visits.items()):
        dest = ticket.get('destination') or {}
        at_post = (dest.get('person') is None and tuple(dest.get('sector', ())) == (game.sector.x, game.sector.y)
                   and (dest.get('point') is None or distance(person.pos, dest['point']) <= 12))
        if person.role in ROLES[kind] and (dest.get('person') == person.id or at_post):
            complete(game, kind)
            changed = True
    if changed:
        game.update_orders(force=True)


def interact(ps, kind, person):
    from .senses import los_clear
    g, p = ps.game, ps.game.player
    if not person.active or person.downed or person.side != p.side or person.role not in ROLES[kind] or \
            distance(p.pos, person.pos) > 2 or not los_clear(g, *p.pos, *person.pos):
        g.msg('The contact is no longer within speaking distance. T keeps the destination marked.', 'info')
        return
    complete(g, kind)
    g.update_orders(force=True)
    if kind == 'intel':
        from .qmui import hand_over_papers, open_intel
        return hand_over_papers(ps, person, via_qm=person.role == 'quartermaster') if documents(g) else open_intel(ps, person)
    if kind == 'supply':
        from .qmui import open_quartermaster
        return open_quartermaster(ps, person)
    from .talk import open_talk
    return open_talk(ps, person)


def route(game, dest):
    if dest is None:
        return None
    from .service import resolve
    resolve(game, dest)
    if dest['sector'] == (game.sector.x, game.sector.y) or dest.get('world') and game.map.in_bounds(*dest['point']):
        return (*dest['point'], dest.get('label', dest.get('kind', 'service post')))
    from .base import _next_edge
    from .orders import exit_point
    edge = _next_edge(game, dest['sector'])
    if edge:
        return (*exit_point(game, edge), 'Route to ' + dest.get('label', 'service post') +
                ' at ' + game.strategic.at(*dest['sector']).name)
    return None


def entry(game):
    if game.__dict__.get('domain', 'land') != 'land':
        return None
    carried = documents(game)
    p = game.player
    if not carried:
        p.ai.pop('intelligence_order', None)
        if game.__dict__.get('order_focus') == 'intelligence':
            game.order_focus = None
        return None
    ticket = p.ai.setdefault('intelligence_order', dict(issued=game.turn))
    dest = assigned_target(game, ticket, 'intel')
    # If intelligence is not reachable on this sheet, a quartermaster can pass papers on.
    if dest is None and not ticket.get('destination_lost'):
        dest = target(game, 'supply')
    if dest is not None:
        ticket['destination'] = dest
    return dict(key='intelligence', who='Captured intelligence hand-in', how='your service notebook',
                text=f'Deliver {len(carried)} lot(s) of captured papers to ' +
                     (dest['label'] if dest else 'intelligence; no contact is on your map yet') + '.',
                issued=ticket['issued'], due=None, reward='intelligence, requisition credit and reviewed service toward promotion',
                penalty='no penalty for delaying; keep the papers safe', urgent=False, point=route(game, dest), authority=0)


def go(ps, kind='intel'):
    g, p = ps.game, ps.game.player
    if kind == 'hq':
        from .debrief import request_report, plan
        request_report(g)
        from .orders import focus
        focus(g, 'personnel')
        return plan(ps)
    order = entry(g) if kind == 'intel' else None
    ticket = p.ai.get('contact_orders', {}).get(kind)
    dest = p.ai.get('intelligence_order', {}).get('destination') if order else \
        assigned_target(g, ticket, kind) if ticket else target(g, kind)
    pt = route(g, dest)
    if not dest or not pt:
        return 'consult T; obtain a map or locate a friendly service post', ps.cmd_orders_book
    a = next((a for a in g.actors if a.id == dest.get('person') and a.active and not a.downed), None)
    if a is not None and distance(p.pos, a.pos) <= 2:
        from .senses import los_clear
        if los_clear(g, *p.pos, *a.pos):
            if kind == 'intel' and documents(g) and a.role == 'quartermaster':
                from .qmui import hand_over_papers
                return 'hand the papers to ' + a.full_name, lambda: hand_over_papers(ps, a, via_qm=True)
            return 'speak to ' + a.full_name, lambda: interact(ps, kind, a)
    from .service import drive_step
    remote = dest['sector'] != (g.sector.x, g.sector.y) and not (dest.get('world') and g.map.in_bounds(*dest['point']))
    if p.vehicle is not None and distance(p.pos, pt[:2]) > 2:
        return 'drive toward ' + pt[2], lambda: drive_step(ps, pt[:2])
    if remote:
        from .base import _next_edge
        edge = _next_edge(g, dest['sector'])
        return pt[2], lambda: ps._travel_chosen(edge) if distance(p.pos, pt[:2]) <= 2 else \
            ps.start_travel(*pt[:2], then=lambda: ps._travel_chosen(edge), stop_short=1)
    if a is None and distance(p.pos, pt[:2]) <= 6:
        return 'look for surviving staff at this post', lambda: g.msg('No suitable staff are here. Use X to find another post.', 'info')
    return 'go to ' + pt[2], lambda: ps.start_travel(*pt[:2], stop_short=2)


def menu(ps):
    from .command_work_ui import _menu
    g = ps.game
    opts = []
    for kind, label in NAMES.items():
        dest = target(g, kind)
        suffix = (' — ' + dest['label'] if dest.get('person') else ' — marked service post') if dest else ' — not located'
        opts.append(('Find nearest ' + label + suffix, kind, None, True))
    if g.player.ai.get('contact_orders'):
        opts.append(('Clear my service visit orders', 'clear', None, True))
    opts.append(('Read the ground: toggle passability overlay', 'going', None, True))
    def choose(kind):
        if kind == 'going':
            return ps.cmd_going()
        if kind == 'clear':
            for k in list(g.player.ai.get('contact_orders', {})):
                complete(g, k)
            g.update_orders(force=True)
            return
        key = request(g, kind)
        from .orders import focus
        if not key or not focus(g, key):
            return ps.cmd_orders_book()
        g.update_orders(force=True)
        label, action = go(ps, kind)
        g.msg(label.capitalize() + '.', 'info')
        action()
    from .constants import UI_DIM
    _menu(ps, 'Find help / read the ground', opts, choose,
          [('Selecting a person or post adds a visit to T. The arrow and Enter follow it when duty permits.', UI_DIM)])
