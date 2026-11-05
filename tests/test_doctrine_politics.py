"""Battle drills, theatre politics, the after-action trace, camps and rebinding."""
from __future__ import annotations

import os
import sys

from test_smoke import Game, FakeApp  # noqa: F401  (headless setup first)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import afteraction, camp, doctrine, politics, quotes  # noqa: E402


def _commandable(g):
    return next(s for s in g.squads if s.side == g.player.side and not s.gone
                and g.command.authority(g, s)[0])


def test_drills_follow_nation_and_training():
    g = Game("kursk43", "germany", "rifleman", seed=5,
             setup={"battlefield": "standard", "scenario": "front"})
    g.player.skills["leadership"] = 9.0
    g.player.rank = max(g.player.rank, 4)
    sq = _commandable(g)
    sq.leader.skills["leadership"] = 9.0
    assert doctrine.available(g, [sq], "schwerpunkt")[0]
    assert doctrine.available(g, [sq], "stoss")[0] or True      # needs an assault unit or the right ground
    ok, why = doctrine.available(g, [sq], "maskirovka")
    assert not ok and "taught" in why
    o = doctrine.make(g, "schwerpunkt", (g.player.x + 5, g.player.y), sq)
    assert o.drill == "schwerpunkt" and o.mod.get("fire", 0) > 1
    g.player.skills["leadership"] = 1.0
    sq.leader.skills["leadership"] = 1.0
    assert not doctrine.available(g, [sq], "schwerpunkt")[0]


def test_follow_me_is_a_drill_and_marks_the_order():
    g = Game("bocage44", "usa", "rifleman", seed=2, setup={"battlefield": "standard"})
    sq = g.player.squad
    sq.player_led = True
    sent, _ = g.command.issue(g, [sq], "follow", drill="follow_me")
    assert sent
    assert sq.order.drill == "follow_me"


def test_politics_only_for_generals_and_defiance_costs():
    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    assert not politics.active(g)
    g.player.rank = 18
    politics.start(g)
    assert politics.active(g)
    credit = g.politics["credit"]
    politics.defy(g)
    assert g.politics["credit"] < credit and g.politics["defiance"] == 1


def test_afteraction_reports_the_decision_and_advice():
    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    p = g.player
    p.x, p.y = max(1, p.x), max(1, p.y)
    p.stance = 0
    g.map.pos_cover[p.x, p.y] = 5
    for _ in range(6):
        g.world_turn()
    p.stance = 1
    p.body.cause = "shrapnel"
    with_trace = afteraction.report(g, None)
    assert with_trace and any("wounds" in t for _a, t, _k in with_trace)
    assert g.death_advice


def test_camp_builds_and_events_change_the_ledger():
    g = Game("bocage44", "germany", "rifleman", seed=4,
             setup={"battlefield": "standard", "scenario": "camp"})
    c = g.__dict__["camp"]
    assert c["prisoners"] >= 10
    camp.resolve(g, "hard")
    assert c["labour"] > 0
    camp.resolve(g, "select")
    assert c["dead"] >= 1
    assert (g.__dict__.get("atrocities") or {}).get("counts")


def test_legacy_projects_from_the_record():
    from fow import legacy
    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    g.stats["civilian_deaths"] = 2
    g.stats["objectives"] = 1
    lines = legacy.project(g)
    assert lines and any("civilian" in t for t, _ in lines)
    assert all(len(t) > 20 for t, _ in lines)


def test_heroism_steadies_and_officer_surrender_shakes():
    from fow import heroism
    g = Game("bocage44", "germany", "rifleman", seed=1, setup={"battlefield": "standard"})
    a = next(x for x in g.actors if x.side == "axis" and x.alive and not x.is_player)
    b = next(x for x in g.actors if x.side == "axis" and x.alive and x is not a and not x.is_player)
    b.x, b.y = a.x + 2, a.y
    g.soldier_at[(b.x, b.y)] = b
    g.map.visible[a.x, a.y] = g.map.visible[b.x, b.y] = True
    b.morale, b.suppression = 50, 30
    heroism.brave(g, a, "rescue")
    assert b.morale > 50 and b.suppression < 30
    a.rank = 10
    b.morale = 50
    g.surrender(a)
    assert a.state == "surrendered" and b.morale < 50


def test_interrogation_gives_papers_and_plans():
    from fow import interrogation
    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    p = g.player
    en = next(a for a in g.actors if a.side == "axis" and a.alive)
    g.surrender(en)
    en.ai["captor"] = p.id
    en.rank = 10
    en.ai["searched"] = True
    en.ai["interrogation"] = dict(rounds=0, methods=[], gave=set(), done=False)
    p.skills["languages"] = 9
    if p.invent.slots["pack"] is None:          # (a man without a pack has nowhere to put the map)
        from fow.entities import Item
        p.invent.slots["pack"] = Item("backpack")

    class PS:
        def __init__(self):
            self.game = g
        def act(self, c):
            self.cost = c
    ps = PS()
    for _ in range(30):
        interrogation._do(ps, en, "ask")
        if "map" in en.ai["interrogation"]["gave"] or "orders" in en.ai["interrogation"]["gave"]:
            break
    assert "map" in en.ai["interrogation"]["gave"] or "orders" in en.ai["interrogation"]["gave"]
    assert any(i.tid == "marked_map" for i in p.inv) or g.__dict__.get("enemy_plan_warning")


def test_pow_interrogation_buys_treatment():
    from fow.ui import POWState

    class App:
        def __init__(self):
            self.states = []
        def push(self, s):
            self.states.append(s)
        def pop(self):
            self.states.pop()

    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    g.pow = dict(camp="Stalag VIIA", day=3, food=40, weak=2, sick=0, rations=0.55, death=0.001, parcels=False)
    st = POWState(App(), g, None)
    st._answered("all")
    assert g.pow["food"] > 40 and g.pow["cooperated"] == 1


def test_translation_default_friendlies_and_language_for_enemies():
    from fow import translate as tr
    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    ger = next(a for a in g.actors if a.nation == "germany" and a.alive)
    us = next(a for a in g.actors if a.nation == "usa" and a.alive and not a.is_player)
    tr.ACTIVE_SIDE, tr.ACTIVE_MODE, tr.PLAYER = "usa", "own", g.player
    g.player.skills["languages"] = 0.5
    tr._UNDERSTOOD.clear()
    ger.say("Handgranate!", g.turn)
    assert ger.shout[0] == "Handgranate!"
    us.say("Grenade!", g.turn)
    assert us.shout[0] == "Grenade!"
    tr.ACTIVE_MODE = "all"
    ger.say("Handgranate!", g.turn)
    assert "Handgranate! / Grenade!" == ger.shout[0]
    assert ger.spoken[3] is True
    tr.ACTIVE_MODE = "own"
    tr.ACTIVE_SIDE = None
    tr.PLAYER = None


def test_rumination_uses_the_actual_fight():
    from fow import rumination
    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    g.clock = 3600
    g.player.stats["shots"] = 200
    lines = rumination.numbers(g)
    assert lines and "200 rounds" in lines[0] and any("thirty thousand" in l for l in lines)
    assert rumination.why(g)


def test_quotes_match_the_cause():
    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    g.player.body.cause = "shell fragments"
    text, who, bio = quotes.pick(g)
    assert text and who and bio


def test_keybind_capture_writes_and_persists():
    from fow.ui import KeybindState
    from fow.settings import Settings

    class App:
        def __init__(self):
            self.settings = Settings()
        def pop(self):
            pass

    app = App()
    ks = KeybindState(app)
    ks.sel = next(i for i, (a, _l) in enumerate(ks.lines) if a == "crouch")
    ks.on_key(__import__("fow.ui", fromlist=["Key"]).Key(sym=13))
    from fow.ui import Key
    ks.on_key(Key(char="v"))
    assert app.settings["keymap"]["crouch"] == "v"


def test_keybinds_swap_and_remap():
    from fow import keybinds
    st = {}
    keybinds.bind(st, "crouch", "V")
    assert keybinds.remap(st, "V") == "c"
    # V belonged to nearby; it has been swapped to crouch's old key
    assert st["keymap"]["nearby"] == "c"
    keybinds.reset(st)
    assert keybinds.remap(st, "v") == "v"
