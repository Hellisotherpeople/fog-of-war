"""Periodic staff briefings over radios, vehicle crews and physical paper couriers.

Packets contain reports already received by HQ, frozen at departure. The same
transport and interruption rules apply to officers of either army.
"""
from copy import deepcopy

from .intelligence import distance, headquarters, merge_map
from .data.ranks import LT2

STAFF = ('adjutant', 'ops_officer', 'intel', 'clerk', 'politruk')


def recipient(a):
    return a.active and not a.downed and not a.ai.get('civilian') and (a.rank >= LT2 or a.role in STAFF)


def channel(game, a):
    from .command import has_radio, vehicle_has_radio
    from .senses import los_clear
    if not a.active or a.downed:
        return None
    if headquarters(game, a):
        return 'HQ map desk'
    if has_radio(a):
        return 'personal radio'
    if a.vehicle is not None and a.vehicle.active and vehicle_has_radio(game, a.vehicle):
        return 'vehicle radio'
    if any(b is not a and b.active and not b.downed and has_radio(b) and
           distance(a.pos, b.pos) <= 3 and los_clear(game, *a.pos, *b.pos)
           for b in game.near(*a.pos, 3, a.side)):
        return 'nearby radioman'
    if any(v.side == a.side and v.active and v.crew > 0 and distance(a.pos, v.pos) <= 3 and
           vehicle_has_radio(game, v) and los_clear(game, *a.pos, *v.pos) for v in game.vehicles):
        return 'nearby vehicle crew'
    return None


def packet(game, side):
    maps = game.strategic.__dict__.get('situation_reports', {}).get(side, {})
    contacts = {c.id: dict(id=c.id, x=c.x, y=c.y, turn=c.turn, kind=c.kind)
                for c in game.brains[side].contacts.values() if not c.sound and 0 <= game.turn - c.turn <= 600}
    return dict(maps=deepcopy(maps), contacts=contacts, posted=game.turn)


def fresh(a, data):
    return any(k not in a.ai.get('map_reports', {}) or r['turn'] > a.ai['map_reports'][k]['turn']
               for k, r in data['maps'].items()) or any(
        k not in a.ai.get('staff_contacts', {}) or r['turn'] > a.ai['staff_contacts'][k]['turn']
        for k, r in data['contacts'].items())


def deliver(game, a, data, via):
    changed = fresh(a, data)
    count = merge_map(a, data['maps'])
    known = a.ai.setdefault('staff_contacts', {})
    for key, r in data['contacts'].items():
        if key not in known or r['turn'] > known[key]['turn']:
            known[key] = deepcopy(r)
    a.ai['staff_contacts'] = {k: r for k, r in known.items() if game.turn - r['turn'] <= 1800}
    a.ai['staff_update'] = dict(at=game.turn, via=via, posted=data['posted'])
    if a is game.player and changed:
        game.msg(f'Situation update via {via}: {count} map report(s), {len(data["contacts"])} reported enemy position(s). '
                 'Your notes retain the original observation times. m: map; C: staff.', 'radio' if 'radio' in via else 'info')


def courier(game, a):
    """Use an available man at a real HQ or with a working set; never spawn a messenger."""
    from .command import has_radio
    from .data.ranks import same_army
    candidates = [b for b in game.actors if b is not a and b is not game.player and b.active and not b.downed
                  and b.vehicle is None and b.side == a.side and same_army(b.nation, a.nation)
                  and b.rank < max(a.rank, LT2) and b.suppression < 20 and game.turn - b.fired_turn > 120
                  and b.role in ('rifleman', 'radioman', 'clerk', 'adjutant')
                  and not any(b.ai.get(k) for k in ('runner', 'situation_dispatch', 'support_job', 'escort', 'escort_prisoner'))
                  and b.squad is not None and b.squad.order.src != 'player'
                  and b.squad.order.kind in ('hold', 'reserve', 'regroup', 'follow')
                  and (headquarters(game, b) or has_radio(b))]
    return min(candidates, key=lambda b: distance(b.pos, a.pos), default=None)


def tick(game):
    recipients = [a for a in game.actors if recipient(a)]
    packets = {}
    for a in recipients:
        a.ai.setdefault('staff_rendezvous', a.pos)  # last signalled / departure position
        if channel(game, a):
            a.ai['staff_rendezvous'] = a.pos
        pending = a.ai.get('staff_pending')
        if pending and game.turn >= pending['due']:
            a.ai.pop('staff_pending')
            via = channel(game, a)
            if via:
                deliver(game, a, pending['data'], via)
        runner_id = a.ai.get('staff_courier')
        if runner_id is not None:
            b = next((b for b in game.actors if b.id == runner_id and b.active and not b.downed
                      and b.ai.get('situation_dispatch', {}).get('recipient') == a.id), None)
            if b is not None and game.turn - b.ai['situation_dispatch']['data']['posted'] < 1800:
                continue
            a.ai.pop('staff_courier', None)
        if a.ai.get('staff_pending') or game.turn < a.ai.get('staff_next', 0):
            continue
        a.ai['staff_next'] = game.turn + (120 if a.rank >= 13 else 180)
        if a.side not in packets:
            packets[a.side] = packet(game, a.side)
        data = packets[a.side]
        if not fresh(a, data):
            continue
        via = channel(game, a)
        if via == 'HQ map desk':
            deliver(game, a, data, via)
        elif via:
            a.ai['staff_pending'] = dict(data=data, due=game.turn + 30)
        elif (b := courier(game, a)) is not None:
            b.ai['situation_dispatch'] = dict(recipient=a.id, data=data, origin=b.pos,
                                             target=a.ai['staff_rendezvous'])
            a.ai['staff_courier'] = b.id


def act(game, a, visible):
    """Walk to the recipient, hand over the packet, then return to the sending post."""
    from .ai import path_step, fix_stance
    from .senses import los_clear
    job = a.ai.get('situation_dispatch')
    if not job or not a.active or a.downed:
        return None
    dest = next((b for b in game.actors if b.id == job.get('recipient') and recipient(b)), None)
    if dest is None or game.turn - job['data']['posted'] >= 1800:
        job['returning'] = True
    if job.get('returning'):
        point = job['origin']
        if distance(a.pos, point) <= 2:
            a.ai.pop('situation_dispatch', None)
            return 100
    else:
        # A courier cannot track a commander who has silently moved elsewhere.
        if distance(a.pos, dest.pos) <= 20 and los_clear(game, *a.pos, *dest.pos):
            job['target'] = dest.pos
        point = job['target']
        if distance(a.pos, dest.pos) <= 2 and a.suppression < 30 and los_clear(game, *a.pos, *dest.pos):
            deliver(game, dest, job['data'], 'runner ' + a.full_name)
            if dest.ai.get('staff_courier') == a.id:
                dest.ai.pop('staff_courier', None)
            job['returning'] = True
            return 100
    if a.suppression >= 30 or any(distance(a.pos, e.pos) <= 8 for e in visible):
        return None  # take cover or fight before carrying on
    cost = path_step(game, a, *point, margin=30)
    if cost:
        fix_stance(game, a, 0)
    return cost or 100


def status(game):
    a = game.player
    last = a.ai.get('staff_update')
    text = (f'Last staff update: {(game.turn - last["at"]) // 60} min ago, via {last["via"]}.' if last else
            'No field staff briefing received yet.')
    if a.ai.get('staff_courier') is not None:
        text += ' A situation runner is on the way.'
    elif a.ai.get('staff_pending'):
        text += ' A signals briefing is being received.'
    elif recipient(a) and not channel(game, a):
        text += ' No nearby working set; updates depend on an available courier.'
    return text
