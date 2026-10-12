"""Nearby work must preserve capture rules and the surgeon's patient priority/tie order."""
from copy import deepcopy
from unittest.mock import patch

from test_command_realism import scene, soldier
from fow import ai, commander
from fow.body import Wound


def test_capture_query_matches_full_roster_after_movement_and_casualties():
    g = scene()
    o = g.map.objectives[0]
    o.x,o.y,o.radius,o.owner,o.hold_time = 30,25,6,None,0
    for x,y,nation in ((31,25,'usa'),(36,25,'usa'),(37,25,'germany'),(34,29,'germany')):
        soldier(g,x,y,nation=nation)
    g.actor_array()
    # Change position and eligibility after the spatial index already exists.
    a = g.actors[-1]
    a.x,a.y = 55,25
    g.note_move(a)
    g.actors[1].body.dead = True
    reference = deepcopy(g)
    with patch.object(reference,'near',return_value=reference.actors):
        commander.update_objectives(reference,5)
    commander.update_objectives(g,5)
    assert [(o.owner,o.contested,o.hold_time) for o in g.map.objectives] == [
        (o.owner,o.contested,o.hold_time) for o in reference.map.objectives]
    assert g.map.objectives[0].hold_time == 5 and not g.map.objectives[0].contested


def test_surgeon_preserves_priority_and_original_roster_tie_breaking():
    g = scene()
    surgeon = g.player
    first = soldier(g,11,10)
    tied = soldier(g,10,11)
    distant = soldier(g,60,10)
    for patient,bleed in ((first,3),(tied,3),(distant,20)):
        patient.body.wounds.append(Wound('l_arm',bleed,'bullet'))
    with patch('fow.medical.at_aid_post',return_value=True), \
         patch('fow.medical.can_help',return_value=True), \
         patch('fow.medical.needs_surgery',return_value=False), \
         patch('fow.medical.first_aid',side_effect=lambda game,who,patient:patient.id):
        with patch.object(g,'near',return_value=g.actors):
            reference = ai.surgeon_act(g,surgeon,[])
        assert ai.surgeon_act(g,surgeon,[]) == reference == first.id
