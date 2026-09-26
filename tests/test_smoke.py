"""Smoke tests: every battle starts and runs, every service starts, saves load, the war at sea goes on.

    python -m pytest tests            (pip install pytest)
    python tests/test_smoke.py        (no pytest needed)

These are not unit tests of numbers; they're "does the whole thing hold together" runs of the real
game, headless.  FOW_DEBUG=1 makes an exception inside any soldier's AI fail the test instead of
being swallowed.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["FOW_DEBUG"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fow.settings as FS  # noqa: E402
FS.SETTINGS_PATH = os.path.join(tempfile.mkdtemp(prefix="fow_test_"), "settings.json")

from fow.data.theatres import THEATRES  # noqa: E402
from fow.game import Game  # noqa: E402


class FakeApp:
    """Just enough of the application for a PlayState to live in."""

    def __init__(self):
        self.settings = {"safe_mode": False}
        self.states = []
        self.show_numbers = False
        self.audio = None
        self.gfx = None

    def push(self, s):
        self.states.append(s)

    def pop(self):
        self.states.pop()


def _turns(g, n):
    for _ in range(n):
        g.player.moves = 0
        g.world_turn()


def test_every_theatre_starts_and_runs():
    for th, t in THEATRES.items():
        for side in ("allies", "axis"):
            nat = t["sides"][side][0][0]
            g = Game(th, nat, seed=11, setup={"battlefield": "standard"})
            _turns(g, 15)
            assert g.player is not None and g.actors, (th, nat)


def test_services_start():
    cases = [("guadalcanal42", "usa", "fighter_pilot", "air", "random"),
             ("bocage44", "uk", "bomber_pilot", "air", "air:strategic"),
             ("guadalcanal42", "japan", "admiral", "navy", "sea:carrier"),
             ("omaha44", "usa", "sailor", "navy", "random"),
             ("okinawa45", "usa", "sub_commander", "navy", "random"),
             ("crete41", "germany", "bombardier", "air", "random")]
    for th, nat, role, sv, sc in cases:
        g = Game(th, nat, role=role, seed=4, setup=dict(service=sv, scenario=sc, battlefield="standard"))
        _turns(g, 20)
        assert g.player.role == role, (th, role, g.player.role)


def test_save_and_load_aboard():
    d = tempfile.mkdtemp(prefix="fow_save_")
    for role, sc, sv, th in (("sailor", "sea:carrier", "navy", "okinawa45"),
                             ("bombardier", "air:strategic", "air", "bocage44")):
        g = Game(th, "usa", role=role, seed=7, setup={"battlefield": "standard", "service": sv, "scenario": sc})
        _turns(g, 30)
        path = os.path.join(d, role + ".pkl")
        g.save(path)
        g2 = Game.load(path)
        _turns(g2, 30)
        assert g2.domain == "aboard" and g2.aboard["kind"] == ("ship" if sv == "navy" else "plane")


def test_ship_is_full_size():
    from fow import aboard as AB
    g = Game("okinawa45", "usa", role="sailor", seed=7,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:carrier"})
    ship = AB.ship_of(g)
    if ship.cls in ("cv", "cve"):
        assert "hangar" in g.aboard["decks"] and "flight" in g.aboard["decks"]
    fr = g.aboard["frame"]
    assert fr.L * 2 >= 100            # two metres a tile: nothing aboard is a toy


def test_carrier_battle_goes_somewhere():
    """With nobody conning her, the captain must take her into the fight - not steam off for ever."""
    from fow import aboard as AB, shipboard as SB
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("okinawa45", "usa", role="sailor", seed=7,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:carrier"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    ss, me = g.skysea, AB.ship_of(g)
    hp0 = {s.id: s.hp for s in ss.ships if s.side != me.side}
    for _ in range(4 * 360):                       # four hours in 10-second steps
        SB.fast_step(g, 10)
        g.aboard["task"] = None
        if ss.over or not me.alive:
            break
    enemy = [s for s in ss.ships if s.side != me.side]
    assert any(s.hp < hp0[s.id] for s in enemy), "four hours and not a scratch on the enemy"
    near = min(math.hypot(s.x - me.x, s.y - me.y) for s in enemy)
    assert near < 400, f"the carrier wandered {near:.0f} tiles from the enemy"


def test_fast_forward_stops_for_the_watch():
    from fow import shipboard as SB
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("okinawa45", "usa", role="sailor", seed=3,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:convoy"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    t0 = g.turn
    stopped = False
    for _ in range(2000):
        if SB.fast_step(g, 30):
            stopped = True
            break
    assert stopped and g.turn > t0


if __name__ == "__main__":
    import time
    tests = [(k, v) for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    bad = 0
    for name, fn in tests:
        t0 = time.perf_counter()
        try:
            fn()
            print(f"ok    {name}  ({time.perf_counter() - t0:.1f}s)")
        except Exception:
            import traceback
            bad += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
    sys.exit(1 if bad else 0)
