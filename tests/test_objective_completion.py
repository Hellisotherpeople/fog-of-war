"""A section recognizes secured ground locally, without inventing a report or a capture."""
import pickle
from unittest.mock import patch

import pytest

from test_command_realism import scene, soldier, move, unradio
from fow import ai, commander, intelligence, intent, orders
from fow.constants import other_side
from fow.gamemap import Objective


def cemetery():
    g = scene()
    ob = Objective("the cemetery", 30, 30, radius=10)
    ob.owner = g.player.side
    g.map.objectives = [ob]
    g.map.__dict__.pop("objective_reports", None)
    move(g, g.player, (30, 34))
    leader = soldier(g, 24, 37, role="rifleman")
    sq = leader.squad
    sq.members.append(g.player)
    g.player.squad = sq
    g.player.rank = 1
    sq.initial = 2
    g.squads = [sq]
    for a in sq.members:
        unradio(a)
    sq.order = ai.Order("attack", obj=0, radius=10, issued=g.turn-300, roe="return")
    sq.arrived, sq.state = True, "hold"
    sq.rep["intent"] = dict(mission="seize", target=ob.pos, freedom="free", risk="normal",
                            source="ai", issued=g.turn-300, strength=2, next=g.turn+15, completed=False)
    g.attacker = sq.side
    return g, sq, ob


def test_section_recognizes_capture_outside_five_tiles_without_radio_or_duplicate_credit():
    g, sq, ob = cemetery()
    assert intelligence.distance(sq.leader.pos, ob.pos) == 7
    assert intelligence.objective_owner(g, sq.side, 0) is None
    before = g.stats["objectives"], g.command.merit, list(g.command.medals)
    # Also repairs already-saved stale orders on the ordinary squad update.
    g = pickle.loads(pickle.dumps(g))
    sq = g.player.squad
    ai.squad_update(g, sq)
    assert sq.order.kind == "defend" and sq.order.obj == 0 and sq.arrived
    assert sq.order.roe == "return" and sq.rep["intent"]["completed"]
    assert [(o["key"], o["text"]) for o in orders.book(g)] == [("squad", "Hold the cemetery")]
    assert intelligence.objective_owner(g, sq.side, 0) is None
    for _ in range(3):
        intent.update(g, sq)
        commander.commander_update(g, sq.side)
    assert sq.order.kind == "defend"
    assert sum("Your section has secured the cemetery" in m.text for m in g.messages) == 1
    assert (g.stats["objectives"], g.command.merit, list(g.command.medals)) == before


@pytest.mark.parametrize("blocked", ["enemy", "contested", "unconscious", "unseen", "distant"])
def test_unsecured_or_unobserved_ground_does_not_complete(blocked):
    g, sq, ob = cemetery()
    if blocked == "enemy":
        ob.owner = other_side(sq.side)
    elif blocked == "contested":
        ob.contested = True
    elif blocked == "unconscious":
        for a in sq.members:
            a.body.unconscious = 20
    elif blocked == "unseen":
        move(g, g.player, (27, 30))
        move(g, sq.leader, (23, 30))
        g.map.fill(29, 1, 30, 55, "wall_brick")
        g.map.refresh()
    else:
        move(g, g.player, (5, 5))
        move(g, sq.leader, (6, 5))
    intent.update(g, sq)
    assert sq.order.kind == "attack" and not sq.rep["intent"]["completed"]
    assert not any("Your section has secured" in m.text for m in g.messages)


def test_capture_still_requires_real_uncontested_hold_and_is_credited_once():
    g, sq, ob = cemetery()
    ob.owner = other_side(sq.side)
    before = g.stats["objectives"]
    for _ in range(3):
        g.turn += 5
        commander.update_objectives(g, 5)
        intent.update(g, sq)
        assert ob.owner != sq.side and not sq.rep["intent"]["completed"]
    g.turn += 5
    commander.update_objectives(g, 5)
    intent.update(g, sq)
    assert ob.owner == sq.side and sq.order.kind == "defend"
    assert g.stats["objectives"] == before + 1
    commander.update_objectives(g, 5)
    intent.update(g, sq)
    assert g.stats["objectives"] == before + 1


def test_live_enemy_blocks_completion_between_capture_updates():
    g, sq, ob = cemetery()
    enemy = soldier(g, *ob.pos, nation="germany", role="rifleman")
    assert not ob.contested  # the next five-second capture check has not run yet
    intent.update(g, sq)
    assert sq.order.kind == "attack" and not sq.rep["intent"]["completed"]
    enemy.body.unconscious = 20
    intent.update(g, sq)
    assert sq.order.kind == "defend" and sq.rep["intent"]["completed"]


def test_commander_does_not_reissue_take_for_locally_held_ground():
    g, sq, ob = cemetery()
    next_ob = Objective("the station", 60, 50)
    next_ob.owner = other_side(sq.side)
    g.map.objectives.append(next_ob)
    with patch("fow.command.low_on_ammo", return_value=False):
        commander.commander_update(g, sq.side)
        assert sq.order.kind == "defend" and sq.order.obj == 0
        g.turn += 20
        commander.commander_update(g, sq.side)
        assert sq.order.kind == "defend" and sq.order.obj == 0
        g.turn += 60
        commander.commander_update(g, sq.side)
        assert sq.order.kind == "attack" and sq.order.obj == 1
    assert intelligence.objective_owner(g, sq.side, 0) is None


def test_coordinate_seize_uses_actual_objective_control_and_its_area():
    g, sq, ob = cemetery()
    sq.order = ai.Order("attack", target=ob.pos, issued=g.turn, src="player")
    sq.rep["intent"].update(next=g.turn, source="player")
    ob.owner = other_side(sq.side)
    # Standing at the center without contacts is not itself a completed capture.
    move(g, sq.leader, ob.pos)
    with patch("fow.intent.low_on_ammo", return_value=False):
        intent.update(g, sq)
        assert not sq.rep["intent"]["completed"]
        move(g, sq.leader, (24, 37))
        ob.owner = sq.side
        g.turn += 15
        intent.update(g, sq)
    assert sq.rep["intent"]["completed"] and sq.order.kind == "defend"
    assert sq.order.obj == 0 and sq.order.radius == ob.radius and sq.order.src == "player"


def test_objective_reports_survive_reframing_without_revealing_unreported_changes():
    from test_streaming import world, reframe
    g, _, landscape = world(radius=96)
    g.turn = 1000
    ob = min(g.map.objectives, key=lambda o: intelligence.distance(o.pos, g.player.pos))
    side, world_pos = g.player.side, ob._world_pos
    ob.owner = side
    i = g.map.objectives.index(ob)
    move(g, g.player, ob.pos)
    with patch("fow.intelligence.radio_link", return_value=True):
        assert intelligence.objective_owner(g, side, i, [g.player]) == side
    ob.owner = other_side(side)  # subsequent change has not been reported
    reframe(g, landscape)
    g = pickle.loads(pickle.dumps(g))
    i = next(i for i, o in enumerate(g.map.objectives) if o._world_pos == world_pos)
    assert intelligence.objective_owner(g, side, i, []) == side
    assert g.map.objectives[i].owner == other_side(side)
