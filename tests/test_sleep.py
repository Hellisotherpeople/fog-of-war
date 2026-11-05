"""Sleep is a real state: depth, quality, debt, and the things that wake a man."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_home_"))
os.environ["FOW_DEBUG"] = "1"

from test_smoke import Game, FakeApp  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import jobs, pace, sleep  # noqa: E402
from fow.play import Key, PlayState  # noqa: E402
from fow import tiles as T  # noqa: E402


def _quiet(g):
    for a in list(g.actors):
        if a.side != g.player.side and a.alive:
            a.body.dead = True
            g.kill(a, None)
    g.seen_enemies = lambda within=35: False


def test_n_lies_down_the_world_runs_and_n_gets_up():
    fa = FakeApp()
    fa.settings["fast_quiet"] = True
    g = Game("bocage44", "usa", "rifleman", seed=11, setup={"battlefield": "standard"})
    _quiet(g)
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    p.fatigue = 80
    t0, f0 = g.turn, p.fatigue
    ps.on_key(Key(char="N"))
    assert sleep.asleep(p)
    for _ in range(40):
        ps.anim = ps.anim_next = 0
        ps.tick()
        if g.turn > t0 + 60:
            break
    assert g.turn > t0 + 5 and p.fatigue < f0
    ps.on_key(Key(char="N"))
    assert not sleep.asleep(p)


def test_moving_wakes_you_and_moves():
    import tcod
    fa = FakeApp()
    g = Game("bocage44", "usa", "rifleman", seed=17, setup={"battlefield": "standard"})
    _quiet(g)
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    assert sleep.begin(g, p)
    ps.on_key(Key(sym=tcod.event.KeySym.UP))
    assert not sleep.asleep(p)


def test_an_enemy_close_wakes_you():
    g = Game("bocage44", "usa", "rifleman", seed=12, setup={"battlefield": "standard"})
    p = g.player
    assert sleep.begin(g, p)
    enemy = next(a for a in g.actors if a.side != p.side and a.alive and a.vehicle is None)
    from fow.spawn import place
    place(g, enemy, p.x + 4, p.y, 1)
    for _ in range(3):
        g.world_turn()
        if not sleep.asleep(p):
            break
    assert not sleep.asleep(p)


def test_fire_close_wakes_you():
    g = Game("bocage44", "usa", "rifleman", seed=13, setup={"battlefield": "standard"})
    p = g.player
    assert sleep.begin(g, p)
    p.suppression = 60
    g.world_turn()
    assert not sleep.asleep(p)


def test_a_bed_is_better_than_wet_grass():
    g = Game("bocage44", "usa", "rifleman", seed=14, setup={"battlefield": "standard"})
    p = g.player
    p.stance = 2
    q_open = sleep.quality(g, p)
    g.map.t[p.x, p.y] = T.ID["bed"]
    q_bed = sleep.quality(g, p)
    assert q_bed > q_open


def test_sleep_debt_slows_you_and_ruins_your_aim():
    g = Game("bocage44", "usa", "rifleman", seed=15, setup={"battlefield": "standard"})
    p = g.player
    p.ai["sleep_debt"] = 0
    s0, a0 = pace.speed_mult(p), pace.aim_penalty(g, p)
    p.ai["sleep_debt"] = 95
    assert pace.speed_mult(p) < s0 and pace.aim_penalty(g, p) > a0


def test_autopilot_gets_his_head_down_at_night():
    g = Game("bocage44", "usa", "rifleman", seed=16, setup={"battlefield": "standard"})
    _quiet(g)
    g.is_night = lambda: True
    p = g.player
    p.fatigue = 92
    g.map.pos_cover[p.x, p.y] = 60
    c = jobs._survival(g, p, [], 999)
    assert c and sleep.asleep(p) and g.__dict__["player_job"]["kind"] == "sleep"
