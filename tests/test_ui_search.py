"""Search must preserve menu actions and the player's information boundaries."""
from unittest.mock import patch

import tcod
import tcod.event as E

from test_smoke import FakeApp
from test_identity_loot_ballistics import scene, corpse_scene
from fow.constants import SCREEN_W, SCREEN_H
from fow.play import Key
from fow.render import Popup, draw_popup
from fow.ui import App, ChoiceMenu, ToggleMenu, TextState, OvermapState, CreatorState, OptionsState


def type_text(state, text):
    for char in text:
        state.on_key(Key(sym=E.KeySym.SPACE) if char == " " else Key(char=char))


def console_text(state):
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    state.render(con)
    return "\n".join("".join(chr(c) for c in con.ch[:, y]) for y in range(SCREEN_H))


def test_choice_filter_typing_navigation_and_original_value():
    app, chosen = FakeApp(), []
    menu = ChoiceMenu(app, "Vehicles", [
        ("Panzer IV", "p4", "Germany", None), ("Tigre II", "kt", "Allemagne, modèle 1944", None),
        ("M4 Sherman", "m4", "USA 1942", None)], chosen.append)
    app.push(menu)
    type_text(menu, "/modele 1944")
    assert menu._indices() == [1] and not chosen
    assert "Tigre II" in console_text(menu) and "M4 Sherman" not in console_text(menu)
    menu.on_key(Key(sym=E.KeySym.DOWN))
    menu.on_key(Key(sym=E.KeySym.RETURN))
    assert chosen == ["kt"] and not app.states


def test_empty_filter_enter_does_nothing_escape_clears_before_closing():
    app, chosen = FakeApp(), []
    menu = ChoiceMenu(app, "Find", [("Radio", 7, "", None)], chosen.append)
    app.push(menu)
    type_text(menu, "/no such item")
    assert "No matches" in console_text(menu)
    menu.on_key(Key(sym=E.KeySym.RETURN))
    assert not chosen and app.states
    menu.on_key(Key(sym=E.KeySym.ESCAPE))
    assert menu._indices() == [0] and app.states
    menu.on_key(Key(sym=E.KeySym.ESCAPE))
    assert not app.states


def test_filtered_mouse_and_toggle_done_keep_original_indices():
    app, chosen = FakeApp(), []
    menu = ChoiceMenu(app, "Find", [(str(i), i, "radio" if i == 12 else "kit", None)
                                    for i in range(30)], chosen.append)
    app.push(menu)
    type_text(menu, "/radio")
    console_text(menu)
    menu.on_click(5, next(iter(menu.item_rows)), 1)
    assert chosen == [12]
    toggle = ToggleMenu(app, "Kit", [("Radio", "radio", ""), ("Shovel", "shovel", "")], [], chosen.append)
    app.push(toggle)
    type_text(toggle, "/shovel")
    toggle.on_key(Key(sym=E.KeySym.RETURN))
    assert toggle.chosen == {"shovel"} and toggle._indices() == [1, 2]
    toggle.on_key(Key(sym=E.KeySym.DOWN))
    toggle.on_key(Key(sym=E.KeySym.RETURN))
    assert chosen[-1] == {"shovel"}


def test_popup_filter_disabled_actions_mouse_mapping_and_digit_dispatch():
    g, play, _ = scene()
    chosen = []
    pop = Popup("Orders", [("Move", "move", None, True), ("105 mm unavailable", "bad", None, False),
                           ("105 mm fire mission", "fire", None, True)], (10, 10))
    play.open_popup(pop, chosen.append)
    play.popup_key(Key(char="/"))
    # Exercise the actual event loop, which used to discard all digits.
    app = App.__new__(App)
    app.states, app._last_kp_period = [play], 0
    App.dispatch(app, E.TextInput(text="105"))
    assert pop.search.query == "105" and pop.sel == 2 and not chosen
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    draw_popup(con, pop)
    x, y, _, _ = pop.rect
    assert pop.item_at(x + 2, y + 1) is None
    assert pop.item_at(x + 2, y + 2) == 2
    play.popup_key(Key(sym=E.KeySym.RETURN))
    assert chosen == ["fire"]
    play.open_popup(Popup("Empty", [("Move", "move", None, True)], (5, 5)), chosen.append)
    type_text(play, "/zzz")
    play.popup_key(Key(sym=E.KeySym.RETURN))
    assert chosen == ["fire"] and play.popups


def test_text_search_preserves_records_and_does_not_close_on_typing_action_keys():
    app = FakeApp()
    lines = ["Supply radio report 14", ("Unrelated casualty report", (200, 200, 200))]
    state = TextState(app, "Log", lines)
    app.push(state)
    type_text(state, "/radio 14")
    assert "Supply radio report" in console_text(state)
    assert "Unrelated casualty" not in console_text(state)
    state.on_key(Key(sym=E.KeySym.RETURN))
    assert app.states and state.lines is lines
    state.on_key(Key(sym=E.KeySym.ESCAPE))
    assert "Unrelated casualty" in console_text(state)


def test_inventory_search_keeps_unsearched_pockets_hidden_and_only_focuses_item():
    g, play, _ = scene()
    body, mag, secret = corpse_scene(g)
    play.cmd_inventory(focus_body=body)
    inv, turn = play.inv_screen, g.turn
    inv.on_key(Key(char="/"))
    menu = play.app.states[-1]
    assert not any(value[1] is secret for _, value, _, _ in menu.options)
    assert any(value[1] is mag for _, value, _, _ in menu.options)
    play.app.pop()
    body.data["searched"] = True
    inv.on_key(Key(char="/"))
    menu = play.app.states[-1]
    type_text(menu, secret.name + " searching")
    menu.on_key(Key(sym=E.KeySym.RETURN))
    console_text(inv)
    assert inv.cells[inv.cursor]["item"] is secret
    assert g.turn == turn and inv.loot.inv.contains(secret)
    assert inv.held is None


def test_map_search_includes_only_known_locations_and_never_issues_order():
    g, play, _ = scene()
    g.map.gen_positions = []
    state = OvermapState(play.app, g)
    state.has_map, state.map_range = False, 0
    known = g.sector
    known.visited = True
    before = list(g.command.strategic_orders)
    state.on_key(Key(char="/"))
    menu = play.app.states[-1]
    assert menu.options
    assert all(state._knows(*xy) for _, xy, _, _ in menu.options)
    assert len(menu.options) < len(g.strategic.cells)
    menu.on_key(Key(sym=E.KeySym.RETURN))
    assert g.strategic.cells[state.cx, state.cy].visited
    assert g.command.strategic_orders == before


def test_command_finder_opens_requested_screen_and_preserves_busy_gate():
    g, play, _ = scene()
    turn = g.turn
    play.on_key(Key(char="/"))
    menu = play.app.states[-1]
    type_text(menu, "inventory")
    assert g.turn == turn and play.inv_screen is None
    menu.on_key(Key(sym=E.KeySym.RETURN))
    assert play.inv_screen is not None and g.turn == turn
    play.inv_screen = None
    with patch.object(play, "realtime_busy", return_value=True), patch.object(play, "cmd_reload") as reload:
        play.on_key(Key(char="/"))
        menu = play.app.states[-1]
        type_text(menu, "reload")
        menu.on_key(Key(sym=E.KeySym.RETURN))
        reload.assert_not_called()


def test_text_input_follows_search_dialog_opened_in_same_event():
    g, play, _ = scene()
    app = App.__new__(App)
    app.states, app._last_kp_period = play.app.states, 0
    with patch.object(play, "begin_target") as fire:
        App.dispatch(app, E.TextInput(text="/fire"))
    fire.assert_not_called()
    assert app.states[-1].search.query == "fire"


def test_creator_search_opens_field_and_settings_search_scrolls_to_result():
    app = FakeApp()
    creator = CreatorState(app)
    app.push(creator)
    creator.on_key(Key(char="/"))
    menu = app.states[-1]
    type_text(menu, "vehicle use")
    menu.on_key(Key(sym=E.KeySym.RETURN))
    assert isinstance(app.states[-1], ChoiceMenu)
    assert any("Captured" in o[0] for o in app.states[-1].options)
    from fow.settings import Settings
    app.settings = Settings()
    state = OptionsState(app)
    app.push(state)
    state.on_key(Key(char="/"))
    menu = app.states[-1]
    target = next(i for i in range(len(state.items) - 2, -1, -1) if state.items[i][2] != "head")
    menu._pick(target)
    console_text(state)
    assert target in state.rows.values()


def test_record_search_accepts_action_letters_and_digits_without_closing():
    from fow.ui import StatusState
    g, play, _ = scene()
    state = StatusState(play.app, g)
    play.app.push(state)
    state.on_key(Key(char="/"))
    type_text(state, "q")
    assert play.app.states[-1] is state and state.search.query == "q"
    state.on_key(Key(sym=E.KeySym.DELETE))
    app = App.__new__(App)
    app.states, app._last_kp_period = [state], 0
    App.dispatch(app, E.TextInput(text="1944"))
    assert state.search.query == "1944"
    state.on_key(Key(sym=E.KeySym.BACKSPACE))
    assert state.search.query == "194"
    state.on_key(Key(sym=E.KeySym.ESCAPE))
    assert not state.search.query and play.app.states[-1] is state
    state.on_key(Key(sym=E.KeySym.ESCAPE))
    assert play.app.states[-1] is play


def test_log_search_matches_across_wrapped_lines_and_keeps_whole_message():
    from fow.ui import LogState
    g, play, _ = scene()
    message = "Workshop " + "report " * 30 + "radio repaired."
    g.msg(message, "info")
    state = LogState(play.app, g)
    type_text(state, "/workshop repaired")
    rendered = console_text(state)
    assert "Workshop" in rendered and "radio repaired" in rendered


def test_nearby_search_selects_existing_entry_without_travel_or_targeting():
    g, play, _ = scene()
    body, _, _ = corpse_scene(g)
    play.cmd_nearby()
    before = g.player.pos, g.turn
    play.on_key(Key(char="/"))
    menu = play.app.states[-1]
    type_text(menu, "mp 40")
    assert menu._indices()
    menu.on_key(Key(sym=E.KeySym.RETURN))
    assert "MP 40" in play._nearby_entry()["label"]
    assert (g.player.pos, g.turn) == before and play.mode == "nearby"
