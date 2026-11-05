"""The first hour: kit, the zeroing range, the section, and a first patrol.

Nothing here is a popup lesson.  There is a quartermaster with a stores table, a board to zero on, a
sergeant who wants you to report, and a track across the field.  The war is a long way off until it
is not.
"""
from __future__ import annotations

from . import tiles as T


def setup(game, notes):
    from .spawn import edge_band_point, make_soldier, place
    p = game.player
    m = game.map
    rng = game.rng
    home = game.home_edge(p.side)
    # clear the immediate enemy so the first twenty minutes belong to the training
    for a in list(game.actors):
        if a.side != p.side and a.alive and max(abs(a.x - p.x), abs(a.y - p.y)) < 55:
            game.remove_actor(a)
    # the stores table behind the section, with the quartermaster
    dx, dy = {"N": (0, 3), "S": (0, -3), "W": (3, 0), "E": (-3, 0)}.get(home or "N", (0, 3))
    sx, sy = max(1, min(m.w - 2, p.x + dx)), max(1, min(m.h - 2, p.y + dy))
    for ox in range(-2, 3):
        for oy in range(-1, 2):
            x, y = sx + ox, sy + oy
            if m.in_bounds(x, y) and m.walk[x, y]:
                m.set(x, y, "crates" if (ox + oy) % 3 else "floor_wood")
    m.refresh()
    qm = make_soldier(game, p.nation, "quartermaster")
    place(game, qm, sx, sy + 1)
    nco = make_soldier(game, p.nation, "squad_leader", rank=max(3, p.rank + 2))
    place(game, nco, p.x + (1 if home in ("N", "S") else 0), p.y + (1 if home in ("W", "E") else 0))
    nco.ai["enlist_nco"] = True
    # the zeroing board, and the track out
    bx, by = p.x + (12 if home in ("W", "N") else -12), p.y - 4
    bx, by = max(2, min(m.w - 3, bx)), max(2, min(m.h - 3, by))
    for ox in range(-1, 2):
        for oy in range(-1, 2):
            if m.in_bounds(bx + ox, by + oy):
                m.set(bx + ox, by + oy, "crates")
    m.refresh()
    px, py = max(2, min(m.w - 3, bx + (8 if bx > p.x else -8))), by
    game.mission = dict(kind="enlist", stage="issue", text="Draw your kit from the stores table, then report to "
                        f"the sergeant ({nco.rank_short} {nco.last_name}).", nco=nco.id, board=(bx, by),
                        range_at=(px, py), zero_marks=p.stats.get("shots", 0), patrol=(px, py),
                        stage_at=game.turn, contact=0, done_at=None)
    notes[:] = ["Nothing shoots at you yet. Read the panel: the mission is one small thing at a time.",
                "Arrows or click to move. c crouches, p goes prone. i opens your kit.",
                "Walk into the stores table and press g (or ,) to pick things up."]
    # a rifle to draw: issue the section's stores on the ground
    from .entities import Item
    rifle = p.weapon.tid if p.weapon is not None else "m1_garand"
    from .data.items import ITEMS, ammo_id
    if rifle not in ITEMS:
        rifle = next((i for i in ("m1_garand", "lee_enfield", "kar98k", "mosin") if i in ITEMS), None)
    ammo = ammo_id(ITEMS[rifle].cal) if rifle and ITEMS[rifle].cal else None
    stores = [(iid, n) for iid, n in ((rifle, 1), (ammo, 40), ("bandage", 3), ("canteen", 1), ("ration", 2)) if iid]
    for iid, n in stores:
        for ox in range(-1, 2):
            for oy in range(-1, 2):
                x, y = sx + ox, sy + oy
                if m.in_bounds(x, y) and (x, y) != (sx, sy):
                    it = Item(iid, n)
                    m.add_item(x, y, it)
                    break
            break


def _near(game, p, point, r=2):
    return point is not None and max(abs(p.x - point[0]), abs(p.y - point[1])) <= r


def tick(game, ms, done):
    p = game.player
    if p is None or not p.alive:
        return
    stage = ms.get("stage")
    t = game.turn
    if stage == "issue":
        # a weapon in hand and something to eat: that is the whole test
        if p.weapon is not None and t - ms.get("stage_at", t) > 20:
            ms.update(stage="range", stage_at=t,
                      text=f"Five rounds at the board ({ms['board'][0]},{ms['board'][1]}) to zero your rifle.",
                      zero_marks=p.stats.get("shots", 0))
            game.msg("The quartermaster: 'Sign for it. Now the board - five rounds, and don't lean on the table.' "
                     "(w to take the rifle out; aim with f and Tab; fire with f)", "info")
            game.update_orders(force=True)
        elif t - ms.get("stage_at", t) > 40 and p.weapon is None:
            game.msg("The quartermaster nods at the stores: 'Rifle, rounds. Take them.' (g to pick up, w to hold)",
                     "info")
            ms["stage_at"] = t
    elif stage == "range":
        if p.stats.get("shots", 0) - ms.get("zero_marks", 0) >= 5:
            nco = next((a for a in game.actors if a.id == ms.get("nco")), None)
            if nco is not None:
                ms.update(stage="report", stage_at=t,
                          text=f"Report to {nco.rank_short} {nco.last_name}. Walk up to him (he is by the stores).")
                game.msg("'Groups good enough,' the sergeant says. 'Now come and tell me so, properly.'", "info")
                game.update_orders(force=True)
    elif stage == "report":
        nco = next((a for a in game.actors if a.id == ms.get("nco")), None)
        if nco is None:
            ms.update(stage="patrol", stage_at=t, text="Follow the section out on patrol.")
            return
        if max(abs(p.x - nco.x), abs(p.y - nco.y)) <= 2:
            if t - ms.get("stage_at", t) > 15:
                ms.update(stage="patrol", stage_at=t, patrol=(nco.x + 14, nco.y),
                          text="Walk the section's line out along the hedge. Keep low, watch the far side.")
                game.msg("The sergeant: 'Right. Section - along the hedge, ten paces. Watch your front, and if it "
                         "goes quiet, that's when to worry.'", "info")
                game.update_orders(force=True)
        elif t - ms.get("stage_at", t) > 60:
            game.msg("The sergeant is by the stores, waiting. Walk up to him.", "info")
            ms["stage_at"] = t
    elif stage == "patrol":
        if _near(game, p, ms.get("patrol"), 3):
            ms.update(stage="contact", stage_at=t,
                      text="Hold the line of the hedge. First contact is likely soon.")
            game.msg("'Down here,' the sergeant says. 'This is the line. Watch the far treeline.'", "info")
            game.update_orders(force=True)
    elif stage == "contact":
        if ms.get("done_at") is None and t - ms.get("stage_at", t) > 30:
            ms["done_at"] = t + 120
            from .spawn import spawn_units
            from .scenarios import other_side
            from collections import Counter
            enemy = other_side(p.side)
            try:
                spawn_units(game, enemy, Counter({"inf": 4}), game.home_edge(enemy), True, [], wave=True)
            except Exception:
                pass
            game.msg("Movement in the treeline. They're coming through the fields.", "warn")
            ms["text"] = "First contact: hold the hedge, watch the gaps, and don't bunch."
        if ms.get("done_at") is not None and t >= ms["done_at"]:
            done("You have drawn your kit, zeroed your rifle, found your place in the section, walked the line and "
                 "stood your first contact.", 4)
