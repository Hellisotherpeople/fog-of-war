"""Demolition orders name real, persistent equipment and verify its destruction."""
from __future__ import annotations

import math

from . import tiles as T


def origin(game):
    land = game.__dict__.get('landscape')
    if land is not None and land.frame is game.map:
        return land.origin
    return game.sector.x * game.map_w, game.sector.y * game.map_h


def tile_at(game, world):
    ox, oy = origin(game)
    x, y = world[0] - ox, world[1] - oy
    if game.map.in_bounds(x, y):
        return int(game.map.t[x, y])
    land = game.__dict__.get('landscape')
    if land is None or land.frame is not game.map:
        return None
    key = world[0] // land.w, world[1] // land.h
    if key not in land.maps:
        return None                       # missing terrain is never destruction evidence
    m = land.preload(game, key)
    return int(m.t[world[0] % land.w, world[1] % land.h])


def prepare(game, ms):
    if 'demolition' in ms:
        return ms['demolition']
    if ms.get('kind') != 'raid' and not (ms.get('kind') == 'agent' and ms.get('task') == 'sabotage'):
        return None
    ox, oy = origin(game)
    plan = dict(tiles=[], vehicles=[], need=0, lost_before=0, label='briefed equipment')
    if ms.get('target') == 'rail':
        x, y = ms['tx'], ms['ty']
        positions = ms.get('rail_tiles')
        if positions is None:
            positions = [(rx, ry) for rx in range(x-4, x+5) for ry in range(y-4, y+5)
                         if game.map.in_bounds(rx, ry) and game.map.t[rx, ry] == T.ID['rail']]
            ms['rail_tiles'] = positions
        plan['tiles'] = [dict(world=(x+ox, y+oy), tile=T.ID['rail']) for x, y in positions]
        plan.update(need=min(2, len(positions)), label='rail sections')
    elif ms.get('rec'):
        rec = ms['rec']
        x, y, w, h = rec['rect']
        # Bind only when the real target area is available, never a clipped corner.
        if not (game.map.in_bounds(x, y) and game.map.in_bounds(x+w-1, y+h-1)):
            return None
        tiles = [(rx, ry, int(game.map.t[rx, ry])) for rx in range(x, x+w) for ry in range(y, y+h)]
        if rec['kind'] == 'hq':
            targets = [(rx, ry, tid) for rx, ry, tid in tiles if tid in (T.ID['radio_set'], T.ID['antenna'])]
            plan.update(need=1 if targets else 0, label='command-post communications', disable_hq=True)
        else:
            targets = [(rx, ry, tid) for rx, ry, tid in tiles if tid in T.EXPLODE]
            # Old orders recorded the original number of stores. Retain evidence
            # of those already destroyed rather than resetting their progress.
            baseline = max(len(targets), ms.get('base', 0))
            plan.update(need=math.ceil(baseline * (.6 if ms['kind'] == 'raid' else .5)),
                        lost_before=baseline-len(targets), label='ammunition, fuel or aircraft stores')
        plan['tiles'] = [dict(world=(rx+ox, ry+oy), tile=tid) for rx, ry, tid in targets]
        if not plan['need']:
            guns = [v for v in game.vehicles if not v.dead and v.side == rec.get('side') and v.static
                    and x <= v.x < x+w and y <= v.y < y+h]
            plan['vehicles'] = [dict(id=v.id, world=(v.x+ox, v.y+oy)) for v in guns]
            plan.update(need=len(guns) if ms['kind'] == 'raid' else min(1, len(guns)), label='guns',
                        capture_counts=ms['kind'] == 'raid')
            plan.pop('disable_hq', None)
        plan.update(site_world=(rec['x']+ox, rec['y']+oy), kind=rec['kind'], side=rec.get('side'))
    ms['demolition'] = plan
    return plan


def assign(game, ms):
    """New orders skip empty or ruined sites rather than assigning an impossible task."""
    from .scenarios import _explosive_count
    plan = prepare(game, ms)
    if (plan and plan['need']) or ms.get('target') == 'rail':
        return plan
    for rec in game.map.gen_positions:
        if rec.get('side') == game.player.side or rec.get('side') is None or rec.get('kind') not in (
                'depot', 'motor_pool', 'artillery', 'airfield', 'aa', 'hq') or not rec.get('rect') or rec.get('destroyed'):
            continue
        ms.update(rec=rec, base=_explosive_count(game.map, rec))
        ms.pop('demolition', None)
        plan = prepare(game, ms)
        if plan and plan['need']:
            break
    return plan


def destroyed(game, plan):
    from .mission_evidence import entity
    n = plan['lost_before']
    for target in plan['tiles']:
        current = tile_at(game, target['world'])
        n += current is not None and current != target['tile']
    for target in plan['vehicles']:
        v = entity(game, target['id'], vehicles=True)
        n += v is not None and (v.dead or plan.get('capture_counts') and v.side == game.player.side)
    return n


def achieved(game, ms):
    plan = prepare(game, ms)
    return bool(plan and plan['need'] and destroyed(game, plan) >= plan['need'])


def instruction(plan):
    if not plan or not plan['need']:
        return 'No intact demolition target has been identified.'
    if plan.get('disable_hq'):
        return "Disable the command post's communications: destroy its radio equipment or mast."
    if plan.get('capture_counts'):
        return f"Destroy or capture the {plan['need']} marked guns."
    return f"Destroy at least {plan['need']} marked {plan['label']}."


def point(game, ms):
    from .mission_evidence import entity
    plan = prepare(game, ms)
    if not plan or not plan['need']:
        return None
    positions = [t['world'] for t in plan['tiles'] if tile_at(game, t['world']) in (None, t['tile'])]
    positions += [t['world'] for t in plan['vehicles']
                  if (v := entity(game, t['id'], vehicles=True)) is None or not (
                      v.dead or plan.get('capture_counts') and v.side == game.player.side)]
    if not positions:
        return None
    ox, oy = origin(game)
    p = game.player
    wx, wy = min(positions, key=lambda pt: abs(pt[0]-ox-p.x)+abs(pt[1]-oy-p.y))
    return wx-ox, wy-oy, instruction(plan)


def disable_hq(game, ms):
    """A wrecked communications post can no longer receive reports or provide services."""
    plan = prepare(game, ms)
    if not plan or not plan.get('disable_hq') or plan.get('disabled'):
        return
    wx, wy = plan['site_world']
    ox, oy = origin(game)
    land = game.__dict__.get('landscape')
    maps = [(game.map, (ox, oy))]
    key = wx//game.map_w, wy//game.map_h
    if land is not None and key in land.maps:
        maps.append((land.preload(game, key), (key[0]*land.w, key[1]*land.h)))
    for m, (mx, my) in maps:
        for rec in m.gen_positions:
            if rec.get('kind') == 'hq' and (rec['x']+mx, rec['y']+my) == (wx, wy):
                rec['destroyed'] = True
    ms['rec']['destroyed'] = True
    sector = game.strategic.at(*key, create=True)
    # Another headquarters in the same strategic cell remains usable.
    m, (mx, my) = maps[-1]
    other = any(r.get('kind') == 'hq' and r.get('side') == plan['side'] and not r.get('destroyed')
                and ((r['x']+mx)//game.map_w, (r['y']+my)//game.map_h) == key for r in m.gen_positions)
    if not other:
        for install in sector.installations:
            if install[:2] == ['hq', plan['side']]:
                install[2] = False
    plan['disabled'] = True
