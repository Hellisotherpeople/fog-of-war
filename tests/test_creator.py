"""Explicit roles and national ranks must remain playable in the creator."""
from unittest.mock import patch

import pytest
import tcod

from test_smoke import FakeApp
from fow.constants import SCREEN_W, SCREEN_H
from fow.ui import CreatorState


@pytest.mark.parametrize('theatre', ['random', 'bocage44'])
def test_five_star_creator_renders_selects_rank_and_starts(theatre):
    app = FakeApp()
    creator = CreatorState(app)
    creator.v.update(nation='usa', theatre=theatre, role='army_group_commander')
    app.push(creator)
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order='F')
    creator.render(con)
    creator._open('rank')
    app.states[-1]._pick('line:18')
    creator.render(con)
    assert creator.v['rank'] == 'line:18' and app.states == [creator]
    with patch.object(app, 'start_game', create=True) as start:
        creator.start()
    assert start.call_args.args[2] == 'army_group_commander'
    assert start.call_args.args[3]['rank'] == 'line:18'


def test_changing_roles_preserves_compatible_rank_and_clears_incompatible_rank():
    creator = CreatorState(FakeApp())
    creator.v.update(nation='usa', role='officer', rank='line:9')
    creator.v['role'] = 'adjutant'
    creator._fixup('role')
    assert creator.v['rank'] == 'line:9'
    creator.v['role'] = 'army_group_commander'
    creator._fixup('role')
    assert creator.v['rank'] is None


@pytest.mark.parametrize('theatre,allowed,excluded', [
    ('france40', 'warrant:pre1941', 'warrant:junior'),
    ('bocage44', 'warrant:junior', 'warrant:pre1941'),
    ('random', 'warrant:junior', 'warrant:pre1941'),
])
def test_rank_choices_follow_battle_date(theatre, allowed, excluded):
    creator = CreatorState(FakeApp())
    creator.v.update(nation='usa', theatre=theatre, role='agent')
    ranks = {value for _, value, _ in creator.options('rank')}
    assert allowed in ranks and excluded not in ranks


def test_changing_battle_clears_a_rank_that_did_not_exist_then():
    creator = CreatorState(FakeApp())
    creator.v.update(nation='usa', theatre='bocage44', role='agent', rank='warrant:junior')
    creator.v['theatre'] = 'france40'
    creator._fixup('theatre')
    assert creator.v['rank'] is None
