#!/usr/bin/env python3
"""Exercise real movement, combat, streaming and save/load with state checks.

Run from the repository root, for example:
  .venv/bin/python tools/audit_world.py --theatre bocage44 --seed 73
  .venv/bin/python tools/audit_world.py --save ~/.fogofwar/save.pkl --steps 240

The save argument is copied before loading. All saves and memorial writes go to
a new temporary directory. This is a logic stress test, not a speed benchmark.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


def check(game):
    ids = [v.id for v in game.vehicles] + [a.id for a in game.actors]
    assert len(ids) == len(set(ids)), ('duplicate entity ID', game.turn)
    owners = {}
    for actor in game.actors:
        assert 0 <= actor.body.blood <= 5000, ('blood', actor.id, actor.body.blood)
        for item in actor.inv:
            assert item.count > 0, ('empty carried stack', actor.id, item.tid)
            assert item.iid not in owners, ('shared item', item.iid, owners.get(item.iid), actor.id)
            owners[item.iid] = actor.id
            if item.t.kind == 'gun':
                assert 0 <= item.loaded <= max(1, item.t.mag), ('loaded rounds', item.tid, item.loaded)
    for squad in game.squads:
        order = squad.order
        if order.obj is not None:
            assert 0 <= order.obj < len(game.map.objectives), ('objective index', squad.id)
            if order.world_objective is not None:
                assert order.world_objective is game.map.objectives[order.obj], ('objective identity', squad.id)
    landscape = game.__dict__.get('landscape')
    if landscape is not None:
        for key, m in landscape.maps.items():
            if not isinstance(m, bytes):
                assert all(m.in_bounds(r['x'], r['y']) for r in m.gen_positions), ('displaced site', key)
        if landscape.frame is game.map:
            for rec in game.map.gen_positions:
                wx, wy = landscape.world_pos(rec['x'], rec['y'])
                owner = wx//landscape.w, wy//landscape.h
                assert rec.get('_world_sector', owner) == owner, ('site ownership', rec)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--theatre', default='bocage44')
    parser.add_argument('--seed', type=int, default=73)
    parser.add_argument('--steps', type=int, default=360)
    parser.add_argument('--radius', type=int, default=160)
    parser.add_argument('--save', type=Path)
    args = parser.parse_args()
    if args.steps < 1:
        parser.error('--steps must be positive')
    scratch = Path(tempfile.mkdtemp(prefix='fow-audit-'))
    os.environ['FOW_HOME'] = str(scratch)
    os.environ['SDL_VIDEODRIVER'] = os.environ['SDL_AUDIODRIVER'] = 'dummy'
    os.environ['FOW_DEBUG'] = '1'
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fow.game import Game
    from fow.streaming import ensure
    from fow.ai import path_step
    from fow.data.theatres import THEATRES
    if args.save:
        source = scratch / 'source.pkl'
        shutil.copy2(args.save.expanduser(), source)
        game = Game.load(str(source))
    else:
        nation = THEATRES[args.theatre]['sides']['allies'][0][0]
        game = Game(args.theatre, nation, seed=args.seed,
                    setup={'battlefield': 'standard', 'reality_radius': args.radius})
    landscape = ensure(game)
    if landscape is None:
        parser.error('This harness requires a seamless land battle')
    first_turn = game.turn
    start = landscape.world_pos(*game.player.pos)
    save_path = str(scratch / 'roundtrip.pkl')
    origins = {landscape.origin}
    checks = actions = roundtrips = 0
    for step in range(args.steps):
        if game.game_over:
            break
        dx, dy = ((1, 0), (0, 1), (-1, 0), (0, -1))[(step // 80) % 4]
        target = (start[0] + dx * 90 - landscape.origin[0],
                  start[1] + dy * 90 - landscape.origin[1])
        cost = path_step(game, game.player, *target) if game.player.body.conscious and not game.player.downed else None
        game.player.moves -= cost or 100
        game.player_done()
        actions += 1
        landscape = game.landscape
        origins.add(landscape.origin)
        if step % 10 == 0:
            check(game)
            checks += 1
        if step in (100, 220):
            game.save(save_path)
            game = Game.load(save_path)
            landscape = game.landscape
            roundtrips += 1
            check(game)
            checks += 1
    check(game)
    print(json.dumps(dict(theatre=game.theatre_id, seed=game.seed,
                          source='save copy' if args.save else 'new game', actions=actions,
                          turns=game.turn-first_turn, checks=checks+1, roundtrips=roundtrips,
                          frames=len(origins), actors=len(game.actors), game_over=game.game_over,
                          scratch=str(scratch))), flush=True)


if __name__ == '__main__':
    main()
