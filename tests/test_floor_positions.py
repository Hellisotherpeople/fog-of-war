"""Upper-floor position stores survive duplicates and window drops."""
from __future__ import annotations

from fow.game import Game


def make():
    g = Game("bocage44", "usa", seed=4, setup={"battlefield": "standard"})
    return g


def test_store_falls_back_to_the_other_man_on_the_tile():
    g = make()
    p = g.player
    mate = next(a for a in g.actors if a is not p)
    mate.x, mate.y, mate.z = p.x, p.y, 3
    g.set_actor_at(mate)
    assert g.actor_at(p.x, p.y, 3) is mate
    g.pop_actor_at(mate)
    assert g.actor_at(p.x, p.y, 3) is None


def test_store_leaves_the_remaining_duplicate():
    from fow.entities import Actor
    g = make()
    p = g.player
    a = Actor("usa", "rifleman", 3, "Smith", p.x, p.y)
    b = Actor("usa", "rifleman", 3, "Jones", p.x, p.y)
    g.actors += [a, b]
    for who in (a, b):
        who.x, who.y, who.z = p.x, p.y, 2
    g.set_actor_at(b)                      # last placed wins the single store slot
    assert g.actor_at(p.x, p.y, 2) is b
    g.pop_actor_at(b)
    assert g.actor_at(p.x, p.y, 2) is a


def test_carried_man_is_put_back_in_the_store():
    from fow import actions as A
    g = make()
    p = g.player
    patient = next(a for a in g.actors if a is not p and a.side == p.side)
    patient.x, patient.y, patient.z = p.x + 1, p.y, 1
    p.carrying = patient
    patient.ai["carried_by"] = p.id
    g.pop_actor_at(patient, patient.x, patient.y, 1)
    A.put_down(g, p)
    assert patient.ai.get("carried_by") is None
    assert g.actor_at(patient.x, patient.y, patient.z) is patient
