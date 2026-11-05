"""Command friction, renown, the lull, the manual, packs, fronts, saves and accessibility."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_home_"))
os.environ["FOW_DEBUG"] = "1"

from test_smoke import Game  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import consolidate, friction, manual, packs, renown, sleep, weather_director  # noqa: E402
from fow.ai import Order  # noqa: E402


def _quiet(g):
    for a in list(g.actors):
        if a.side != g.player.side and a.alive:
            a.body.dead = True
            g.kill(a, None)
    g.seen_enemies = lambda within=35: False


def test_a_good_trusted_leader_finds_a_better_way():
    g = Game("bocage44", "germany", "squad_leader", seed=51, setup={"battlefield": "standard"})
    _quiet(g)
    sq = next(q for q in g.squads if q.side == g.player.side and q.leader is not None and q.leader is not g.player)
    ld = sq.leader
    ld.skills["leadership"] = 9.0
    ld.rank = max(ld.rank, 5)
    ld.ai["op"] = 80
    sq.morale = 70
    for m in sq.members:
        for i in list(m.inv):
            if i.t.kind in ("mag", "ammo", "clip"):
                i.loaded = 0
                i.count = 0
    got = None
    for _ in range(40):
        job = dict(kind="attack", channel="radio", order=Order("attack", target=(g.player.x + 10, g.player.y),
                                                               issued=g.turn, src="player"))
        friction.receive(g, sq, job)
        if job.get("improvised"):
            got = job
            break
    assert got is not None
    assert got["order"].mod.get("fire", 0) > 0 and got.get("friction")


def test_renown_rises_and_makes_you_a_target():
    g = Game("bocage44", "usa", "rifleman", seed=52, setup={"battlefield": "standard"})
    p = g.player
    t0 = renown.threat(g, p)
    for _ in range(10):
        renown.event(g, "kill")
    assert renown.state(g)["score"] >= 10 and renown.threat(g, p) > t0


def test_the_lull_sets_chores_and_ends():
    g = Game("bocage44", "usa", "rifleman", seed=53, setup={"battlefield": "standard"})
    _quiet(g)
    sq = g.player.squad
    consolidate.begin(g, sq)
    assert sq.rep.get("consolidate")
    assert any(m.ai.get("after") for m in sq.members)
    consolidate.end(g, sq)
    assert sq.rep.get("consolidate") is None
    assert sq.rep.get("consolidated") is not None


def test_manual_page_unlocks_on_the_trigger():
    g = Game("bocage44", "usa", "rifleman", seed=54, setup={"battlefield": "standard"})
    manual.unlock(g, "vehicle")
    assert "armour" in manual.unlocked(g)
    manual.unlock(g, "vehicle")
    assert manual.unlocked(g).count("armour") == 1


def test_a_pack_adds_a_theatre_and_a_quote(tmp_path, monkeypatch):
    monkeypatch.setattr(packs, "SHIPPED", tmp_path)
    monkeypatch.setattr(packs, "USER", tmp_path)
    import json
    (tmp_path / "p.json").write_text(json.dumps({
        "name": "T",
        "theatres": {"packland45": {"name": "Packland", "battle": "A field", "date": [1945, 1, 1, 6, 0],
                                    "climate": "winter",
                                    "sides": {"allies": [["usa", 1]], "axis": [["germany", 1]]}}},
        "quotes": [[["general"], "A quote.", "Someone", "A bio."]],
    }), encoding="utf-8")
    errs = packs.load_all(force=True)
    assert not errs
    from fow.data.theatres import THEATRES
    from fow.quotes import Q
    assert "packland45" in THEATRES and Q[-1][0][0] == "general"
    THEATRES.pop("packland45", None)               # (later tests iterate every theatre)


def test_storm_warning_and_stand_to():
    g = Game("bocage44", "usa", "rifleman", seed=55, setup={"battlefield": "standard"})
    _quiet(g)
    g.weather_director_seen = True
    g.weather = "storm"
    from fow.weather import state as wstate
    wstate(g)["next"] = g.turn + 300
    g.turn += 100
    weather_director.tick(g)
    p = g.player
    assert sleep.begin(g, p)
    weather_director.stand_to(g, 5)
    assert not sleep.asleep(p)


def test_save_falls_back_to_the_backup(tmp_path):
    g = Game("bocage44", "usa", "rifleman", seed=56, setup={"battlefield": "standard"})
    path = str(tmp_path / "save.pkl")
    g.save(path)
    g.save(path)
    assert os.path.exists(path + ".bak")
    with open(path, "wb") as f:
        f.write(b"not a save")                 # break the head copy
    g2 = Game.load(path)
    assert g2.player is not None and g2.save_version


def test_high_contrast_and_screen_reader_do_not_crash():
    import tcod
    from fow.contrast import apply
    con = tcod.console.Console(20, 5, order="F")
    con.print(1, 1, "hello", fg=(120, 90, 70), bg=(20, 20, 10))
    apply(con)
    assert int(con.rgb["fg"][1, 1, 0]) >= 120
    from fow import screenreader
    screenreader.say("test")
    screenreader.status(Game("bocage44", "usa", "rifleman", seed=57, setup={"battlefield": "standard"}))
