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
        return dict(sector=(game.sector.x, game.sector.y), point=a.pos, person=a.id, label=a.full_name)
    from .service import destination
    dest = destination(game, POSTS[kind])
    if dest and dest['sector'] == (game.sector.x, game.sector.y) and distance(game.player.pos, dest['point']) <= 6:
        # Reaching an abandoned post disproves the old map, so seek another post.
        dest = destination(game, POSTS[kind], skip_local=True)
    return dict(dest, person=None, label=NAMES[kind]) if dest else None


def route(game, dest):
    if dest is None:
        return None
    if dest['sector'] == (game.sector.x, game.sector.y):
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
    dest = target(game, 'intel')
    # If intelligence is not reachable on this sheet, a quartermaster can pass papers on.
    if dest is None:
        dest = target(game, 'supply')
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
    dest = p.ai.get('intelligence_order', {}).get('destination') if order else target(g, kind)
    pt = route(g, dest)
    if not dest or not pt:
        return 'consult T; obtain a map or locate a friendly service post', ps.cmd_orders_book
    a = next((a for a in g.actors if a.id == dest.get('person') and a.active and not a.downed), None)
    if a is not None and distance(p.pos, a.pos) <= 2:
        from .senses import los_clear
        if los_clear(g, *p.pos, *a.pos):
            if kind == 'intel' and documents(g):
                from .qmui import hand_over_papers
                return 'hand the papers to ' + a.full_name, lambda: hand_over_papers(ps, a, via_qm=a.role == 'quartermaster')
            if kind == 'supply':
                from .qmui import open_quartermaster
                return 'speak to ' + a.full_name, lambda: open_quartermaster(ps, a)
            from .talk import open_talk
            return 'speak to ' + a.full_name, lambda: open_talk(ps, a)
    from .service import drive_step
    remote = dest['sector'] != (g.sector.x, g.sector.y)
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
    opts.append(('Read the ground: toggle passability overlay', 'going', None, True))
    def choose(kind):
        if kind == 'going':
            return ps.cmd_going()
        if kind == 'intel' and documents(g):
            entry(g)
            from .orders import focus
            if not focus(g, 'intelligence'):
                return ps.cmd_orders_book()
        if kind == 'hq':
            from .debrief import request_report
            from .orders import focus
            request_report(g)
            if not focus(g, 'personnel'):
                return ps.cmd_orders_book()
        label, action = go(ps, kind)
        g.msg(label.capitalize() + '.', 'info')
        action()
    _menu(ps, 'Find help / read the ground', opts, choose)
