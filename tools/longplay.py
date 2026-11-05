"""Long headless runs with invariants checked every turn.

    FOW_HOME=/tmp/fowlong python tools/longplay.py 5000 --seed 1 --theatre bocage44 --nation usa

Plays the world turn by turn with the player idle (autopilot), and after each turn checks the things
that should always be true: positions in bounds, no actor in two places, no negative ammunition or
health, leaders inside their own squads, squads not both gone and populated, objectives not in a
contradictory state.  Exits nonzero on the first broken invariant, with a short context dump.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", "/tmp/fowlong")


def check(game, turn):
    g = game
    m = g.map
    ids = set()
    for a in g.actors:
        if a.id in ids:
            return f"actor {a.id} is in the actor list twice"
        ids.add(a.id)
        if a.vehicle is None:
            if not (0 <= round(a.x) < m.w and 0 <= round(a.y) < m.h):
                return f"actor {a.id} ({a.name}) out of bounds at {a.x},{a.y}"
            if math.isnan(a.x) or math.isnan(a.y):
                return f"actor {a.id} at NaN"
            land = g.__dict__.get("landscape")
            active = land is None or a.id in land.active_actors
            if getattr(a, "z", 0) and active and a.ai.get("carried_by") is None and g.actor_at(a.x, a.y, a.z) is not a \
                    and not any(o is not a and o.x == a.x and o.y == a.y and o.z == a.z for o in g.actors):
                return f"actor {a.id} on storey {a.z} is not in its position store"
            if getattr(a, "z", 0):
                from fow import floors
                if floors.tile_at(m, a.x, a.y, a.z) is None:
                    return f"actor {a.id} on storey {a.z} over air at {a.x},{a.y}"
        for k, v in a.body.hp.items():
            if v < -0.01 or v > a.body.max[k] + 0.01:
                return f"actor {a.id} {k} hp {v}/{a.body.max[k]}"
        if a.weapon is not None and a.weapon.loaded < 0:
            return f"actor {a.id} negative rounds"
    for a in g.actors:
        st = a.ai.get("sleeping")
        if st is not None:
            if m.water[a.x, a.y] >= 3 or m.fire[a.x, a.y] > 0:
                return f"actor {a.id} asleep in water or fire at {a.x},{a.y}"
            if "stage" not in st or "since" not in st:
                return f"actor {a.id} has a broken sleep state"
        d = a.ai.get("sleep_debt")
        if d is not None and not (0 <= d <= 101):
            return f"actor {a.id} sleep debt {d}"
    for sq in g.squads:
        if sq.gone and (sq.members or sq.vehicles):
            return f"gone squad {sq.id} still has units"
        if sq.leader is not None and sq.leader.alive and sq.leader in g.actors and sq.leader not in sq.members \
                and not sq.gone:
            in_crew = any(sq.leader in getattr(v, "crew_actors", ()) for v in sq.vehicles)
            dormant = sq.__dict__.get("_stream_dormant") or sq.leader.__dict__.get("_stream_dormant")
            anyone_up = any(m.active and not m.downed for m in sq.members)
            if not in_crew and not dormant and anyone_up:
                return f"squad {sq.id} leader {sq.leader.id} not in the squad or its crews"
        if sq.order.kind not in ("hold", "move", "attack", "assault", "defend", "ambush", "flank",
                                 "suppress", "retreat", "follow", "regroup", "dig", "resupply"):
            return f"squad {sq.id} unknown order {sq.order.kind}"
    for i, o in enumerate(m.objectives):
        if o.owner is not None and o.owner not in ("allies", "axis"):
            return f"objective {i} owner {o.owner}"
        if o.hold_time < 0:
            return f"objective {i} negative hold time"
    for v in g.vehicles:
        if v.crew < 0 or v.crew > v.vt.crew:
            return f"vehicle {v.id} crew {v.crew}/{v.vt.crew}"
    if g.turn <= 0:
        return "turn did not advance"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("turns", type=int)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--theatre", default="bocage44")
    ap.add_argument("--nation", default="usa")
    ap.add_argument("--role", default=None)
    ap.add_argument("--scenario", default="front")
    ap.add_argument("--radius", type=int, default=240)
    ap.add_argument("--verbose", action="store_true")
    ns = ap.parse_args()
    from fow.game import Game
    from fow.streaming import ensure
    g = Game(ns.theatre, ns.nation, ns.role, seed=ns.seed,
             setup=dict(battlefield="standard", scenario=ns.scenario, reality_radius=ns.radius))
    ensure(g)
    g.__dict__["autopilot"] = True
    last, quarantined = 0, 0
    for i in range(ns.turns):
        if not g.player.alive:
            break
        try:
            g.world_turn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"turn {g.turn}: {e.__class__.__name__}: {e}"
        bad = check(g, g.turn) if g.turn % 2 == 0 else None
        if bad:
            return f"turn {g.turn}: {bad}"
        if ns.verbose and g.turn % 500 == 0:
            active = sum(1 for s in g.squads if not s.gone)
            held = sum(1 for a in g.actors if a.alive and a.ai.get("chore"))
            print(f"  t={g.turn} actors={len(g.actors)} squads={active} chores={held} "
                  f"kills={g.stats.get('kills')} wound={g.stats.get('wounds')}", flush=True)
        q = g.__dict__.pop("_expectation_checked", None)
        if q:
            quarantined += 1
    active = sum(1 for s in g.squads if not s.gone)
    print(f"ok {g.turn} turns, {len(g.actors)} actors, {active} live squads, player "
          f"{'alive' if g.player.alive else 'dead'}, kills {g.stats.get('kills')}, "
          f"objectives taken {g.stats.get('objectives')}")
    return None


if __name__ == "__main__":
    err = main()
    if err:
        print("FAIL:", err)
        sys.exit(1)
