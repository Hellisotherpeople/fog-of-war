"""Keep seeded simulation tests independent of collection order and earlier games."""
import itertools

import pytest


@pytest.fixture(autouse=True)
def isolated_entity_ids(monkeypatch):
    # IDs choose bounding teams and stagger AI duties. Leaking counters from a previous
    # test changes the next test's battle even when its random seed is unchanged.
    # Multiple games inside one test still share counters, as they do in the application.
    from fow import entities
    from fow.ai import Squad
    from fow.skysea import Plane, Ship

    monkeypatch.setattr(entities, '_ids', itertools.count(1))
    for cls in (Squad, Plane, Ship):
        monkeypatch.setattr(cls, '_next', 1)
