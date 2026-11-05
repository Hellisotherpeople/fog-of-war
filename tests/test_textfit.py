"""Hand-drawn text never runs past its column."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fow import afteraction, quotes, textfit  # noqa: E402


def test_wrap_and_fit_are_hard_limits():
    assert all(len(r) <= 12 for r in textfit.wrap("a " * 40, 12))
    assert len(textfit.fit("x" * 80, 12)) <= 12
    rows = textfit.clip("word " * 200, 20, 3)
    assert len(rows) == 3 and all(len(r) <= 20 for r in rows)
    assert rows[-1].endswith("…")


def test_quote_never_writes_past_its_width():
    import tcod
    con = tcod.console.Console(120, 50, order="F")
    con.draw_rect(0, 0, 120, 50, ord("Z"))
    item = ("x" * 400, "General " + "Verylongname " * 4, "A long biography. " * 12)
    y = quotes.render(con, 4, 5, 49, item, max_rows=9)
    for row in range(5, y):
        assert all(chr(con.ch[x, row]) == "Z" for x in range(53, 70)), row
    assert any(int(con.ch[x, row]) != ord("Z") for row in range(5, y) for x in range(4, 53))


def test_timeline_stamp_does_not_run_into_the_text():
    import tcod
    con = tcod.console.Console(120, 50, order="F")
    lines = [(125, "You got up in the open with the enemy in sight. " * 3, "fact")]
    con.draw_rect(0, 0, 120, 50, ord("Z"))
    afteraction.render(con, 4, 5, 49, lines)
    # the explanation starts in the fixed column and nothing is written past the width
    for row in range(5, con.height):
        if chr(con.ch[4, row]) != "Z":
            assert all(chr(con.ch[x, row]) == "Z" for x in range(53, 60)), row
    assert "".join(chr(con.ch[x, 5]) for x in range(4, 15)).strip().endswith("before")


def test_death_screen_stays_in_its_columns():
    import tcod
    from fow.game import Game
    from fow.ui import GameOverState

    class App:
        settings = {}
        def reset_to_menu(self):
            pass

    g = Game("bocage44", "usa", "rifleman", seed=1, setup={"battlefield": "standard"})
    g.death_text = "Killed by shell fragments. " * 4
    g.death_advice = ["A very long piece of advice about getting flat and crawling to the nearest cover when the shells start."]
    g.death_timeline = [(120, "You got up in the open with the enemy in sight and stayed up to reload.", "fact"),
                        (3, "Rounds came in.", "fact")]
    con = tcod.console.Console(120, 50, order="F")
    con.draw_rect(0, 0, 120, 50, ord("Z"))
    st = GameOverState(App(), g)
    st.render(con)
    for x in range(53, 57):
        assert all(chr(con.ch[x, y]) == " " for y in range(4, 45)), x
    st.page = 1
    st.render(con)
    for x in range(111, 115):
        assert all(chr(con.ch[x, y]) == " " for y in range(4, 44)), x
