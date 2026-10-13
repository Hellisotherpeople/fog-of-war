"""Briefing locations must never move or multiply persistent installations."""
from copy import deepcopy
import hashlib
import pickle
import zlib

import pytest

from test_smoke import Game
from test_streaming import reframe, world
from fow import streaming
from fow.gamemap import GameMap


def sites(m):
    return [(r['kind'], r['x'], r['y'], r.get('rect'), r.get('destroyed'))
            for r in m.gen_positions]


@pytest.mark.parametrize('kind', ['agent', 'raid'])
def test_mission_target_never_mutates_its_canonical_site(kind):
    g = Game('tunisia43', 'usa', seed=73,
             setup={'battlefield': 'standard', 'reality_radius': 120})
    m = g.map
    rec = next(r for r in m.gen_positions if r.get('rect'))
    key = (g.sector.x, g.sector.y)
    target = (key[0]*m.w+rec['x'], key[1]*m.h+rec['y'])
    expected = deepcopy(sites(m))
    # Agent theft/sabotage and commando raids originally retain this same dict.
    g.mission = dict(kind=kind, task='sabotage', rec=rec)
    st = streaming.ensure(g)
    for dx in (0, 24, 24, -24, -24, 24, -24):
        if dx:
            reframe(g, st, dx=dx)
        brief = g.mission['rec']
        assert st.world_pos(brief['x'], brief['y']) == target
        assert sites(st.preload(g, key)) == expected
        st.checkpoint(g)
        assert sites(st.preload(g, key)) == expected


def test_load_repairs_displaced_copies_without_changing_target_or_valid_sites(tmp_path):
    g, ps, st = world()
    key, cm = next((k, m) for k, m in st.maps.items()
                   if not isinstance(m, bytes) and m.gen_positions)
    rec = cm.gen_positions[0]
    expected = deepcopy(sites(cm))
    live_expected = deepcopy(sites(g.map))
    bad = deepcopy(rec)
    streaming.records(bad, st.w*3, st.h*3)
    # Simulate an old mission's alias and thousands of its displaced exports.
    cm.gen_positions.extend(deepcopy(bad) for _ in range(2048))
    cm.gen_positions.append(bad)
    g.mission = dict(kind='agent', task='sabotage', rec=bad)
    target = deepcopy(bad)
    shifted = deepcopy(bad)
    streaming.records(shifted, key[0]*st.w-st.origin[0], key[1]*st.h-st.origin[1])
    shifted['_world_sector'] = key
    g.map.gen_positions.extend(deepcopy(shifted) for _ in range(2048))
    path = str(tmp_path / 'legacy.pkl')
    g.save(path)
    digest = hashlib.sha256((tmp_path / 'legacy.pkl').read_bytes()).digest()
    loaded = Game.load(path)
    land = loaded.landscape
    assert sites(land.maps[key]) == expected
    assert sites(loaded.map) == live_expected
    assert loaded.mission['rec'] == target
    assert hashlib.sha256((tmp_path / 'legacy.pkl').read_bytes()).digest() == digest
    # The repair is idempotent, and later exports don't repopulate the duplicates.
    land.repair_records(loaded)
    land.checkpoint(loaded)
    assert sites(land.maps[key]) == expected
    loaded.save(str(tmp_path / 'repaired.pkl'))
    again = Game.load(str(tmp_path / 'repaired.pkl'))
    assert sites(again.map) == live_expected
    assert sites(again.landscape.maps[key]) == expected
    assert again.mission['rec'] == target


def test_compressed_legacy_cells_are_repaired_when_preloaded():
    m = GameMap(30, 20)
    # Rectangles may cross cell boundaries; their anchor is the ownership key.
    intact = dict(kind='aid', x=2, y=3, rect=(-2, -1, 8, 8))
    destroyed = dict(kind='hq', x=20, y=15, destroyed=True)
    m.gen_positions = [intact, destroyed, dict(kind='hq', x=32, y=3)]
    st = streaming.Landscape.__new__(streaming.Landscape)
    st.maps = {(0, 0): zlib.compress(pickle.dumps(m))}
    loaded = st.preload(None, (0, 0))
    assert loaded.gen_positions == [intact, destroyed]
    assert st.preload(None, (0, 0)) is loaded
