"""Special weapons used the way they were, and the picture-first look."""
from __future__ import annotations

import time

import tcod
import tcod.event as E

from test_smoke import FakeApp
from fow import actions as A
from fow import ai
from fow import tiles as T
from fow.constants import SCREEN_H, SCREEN_W
from fow.entities import Item, Vehicle
from fow.game import Game
from fow.play import Key, PlayState


def make(nation="usa"):
    from fow import icons
    icons.ENABLED = True
    icons.SHOW = True
    g = Game("bocage44", nation, role="rifleman", seed=4, setup={"battlefield": "standard"})
    g.map.explored[:] = True
    g.map.visible[:] = True
    return g


def clear_line(g, x0, x1, y):
    for x in range(min(x0, x1), max(x0, x1) + 1):
        for dy in (-1, 0, 1):
            g.map.set(x, y + dy, "grass")
    g.map.refresh()


def test_rifle_grenade_is_launched_from_a_rifle():
    g = make()
    p = g.player
    rifle = Item("m1_garand")
    p.wield(rifle)
    it = Item("no68")
    p.add_item(it)
    clear_line(g, p.x, p.x + 15, p.y)
    before = p.ammo_count(rifle)
    cost = A.throw(g, p, it, p.x + 15, p.y)
    assert cost
    assert any(e["kind"] == "tracer" and e.get("rocket") for e in g.effects)
    assert p.ammo_count(rifle) == before            # a grenade cup, not a bullet
    # it came to rest well out from the muzzle, not at the player's feet
    blasts = [e for e in g.effects if e["kind"] == "explosion"]
    assert blasts and max(abs(e["x"] - p.x) for e in blasts) >= 4


def test_rifle_grenade_too_close_does_not_arm():
    g = make()
    p = g.player
    p.wield(Item("m1_garand"))
    it = Item("no68")
    p.add_item(it)
    clear_line(g, p.x, p.x + 2, p.y)
    A.throw(g, p, it, p.x + 1, p.y)
    piles = [g.map.items_at(x, y) for x in range(p.x, p.x + 3) for y in (p.y - 1, p.y, p.y + 1)]
    landed = next((i for pile in piles for i in pile if i.tid == "no68"), None)
    assert landed is not None and (landed.data or {}).get("dud")
    assert not any(e["kind"] == "explosion" for e in g.effects)


def test_unlaunched_rifle_grenade_falls_short():
    g = make()
    p = g.player
    p.wield(Item("m1_garand"))
    a = Item("no68")
    b = Item("no68")
    far = A.throw_range(p, a)
    p.weapon = None
    near = A.throw_range(p, b)
    assert near < far


def test_assault_charge_goes_on_a_tank_alongside():
    g = make()
    p = g.player
    mate = next(m for m in p.squad.members if m is not p and m.alive)
    for old in list(mate.inv):
        mate.remove_item(old)
    charge = Item("haft_hl")
    assert mate.add_item(charge) is not None
    tank = Vehicle("pz4", "germany", "germany", mate.x + 1, mate.y)
    g.vehicles.append(tank)
    g.vehicle_at[(tank.x, tank.y)] = tank
    cost = ai.assault_tank(g, mate, [tank])
    assert cost
    assert any(e["item"].tid == "haft_hl" for e in g.explosives)
    assert (g.explosives[-1]["item"].data or {}).get("on_vehicle") == tank.id


def test_look_gives_a_face_and_holds_the_words_back():
    g = make()
    app = FakeApp()
    app.settings["tell"] = "both"
    app.settings["tell_dwell"] = 60          # the words are not due for a minute
    ps = PlayState(app, g)
    app.push(ps)
    mate = next(m for m in g.player.squad.members if m is not g.player and m.alive)
    mate.body.hp["head"] = mate.body.max["head"] * 0.5
    ps.enter_mode("look", (mate.x, mate.y))
    pics = ps._look_pics(mate.x, mate.y, True, 2)
    assert pics and pics[0][0].startswith("face|")
    assert "blood" in pics[0][0]
    lines, title = ps.describe_tile(mate.x, mate.y)
    assert len(lines) > 1
    short, _t = ps.essential(lines, title)
    assert len(short) < len(lines)


def test_pictures_mode_drops_the_prose_words_mode_keeps_it():
    g = make()
    app = FakeApp()
    ps = PlayState(app, g)
    app.push(ps)
    app.settings["tell"] = "pictures"
    assert not ps.look_words_due(time.monotonic() - 10)
    app.settings["tell"] = "words"
    assert ps.look_words_due(time.monotonic())


def test_ground_look_has_a_picture_and_mark_warning_survives():
    g = make()
    app = FakeApp()
    ps = PlayState(app, g)
    app.push(ps)
    p = g.player
    spot = next((x, y) for x in range(p.x - 2, p.x + 3) for y in range(p.y - 2, p.y + 3)
                if (x, y) != (p.x, p.y) and g.soldier_at.get((x, y)) is None
                and g.vehicle_at.get((x, y)) is None and not g.map.items_at(x, y))
    pics = ps._look_pics(spot[0], spot[1], True, 0)
    assert pics and pics[0][0].startswith("ground|")
    lines = [("Here: Mk 2 fragmentation grenade", (200, 190, 150)), ("Some long prose about grass.", (1, 1, 1))]
    short, _t = ps.essential(lines, None)
    assert short and short[0][0].startswith("Here:")


def test_title_menu_never_runs_into_the_quote():
    from fow.ui import MainMenuState
    app = FakeApp()
    st = MainMenuState(app)
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    st.render(con)
    rows = list(st.item_rows)
    assert rows, "the menu is drawn"
    for y in rows:
        # the menu column is 52 wide from x=6; the quote box's left border is at 63 and nothing meets it
        assert "".join(chr(c) for c in con.ch[6:58, y]).strip()
        assert all(chr(c) == " " for c in con.ch[58:63, y])


def test_a_sprite_painted_while_the_preloader_moves_on_reaches_the_live_atlas():
    from fow.sprites import SpriteBank
    b = SpriteBank()
    small = b.build(8)
    live = b.build(14)                       # the game's own size
    before = b.next_cp
    cp = b.soldier("usa", "rifleman", 0)     # painted after both atlases exist
    assert cp == before
    assert small[cp] is not None and live[cp] is not None
