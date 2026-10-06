"""Everything around you, in a list (V) - as in Cataclysm's "list all items and monsters".

Only what you've actually got: the men and vehicles you can see, the sounds you've just heard
(placed where you think they came from, which is a guess), and whatever is lying on the ground
in sight.  Nearest first.  Choosing one puts the look cursor on it; the description is the same
one you'd get by looking.
"""
from __future__ import annotations

import math

from .constants import ENEMY_COLOR, FRIEND_COLOR, PANEL_W, SCREEN_H, SCREEN_W, UI_BG, UI_DIM, UI_HI, UI_TEXT
from .data.nations import NATIONS
from .senses import direction_word, player_can_see_actor

TABS = ("Soldiers", "Items")
SHIP_DIRS = {"E": "fwd", "W": "aft", "N": "port", "S": "stbd", "NE": "p.bow", "SE": "s.bow", "NW": "p.qtr",
             "SW": "s.qtr"}
NEUTRAL = (200, 190, 150)
HEARD = (170, 170, 200)
AMMO_PRIMARY = (130, 225, 150)
AMMO_SECONDARY = (115, 185, 255)
AMMO_BOTH = (225, 175, 255)


def ammo_match(player, item):
    """Check actual feed compatibility, including empty magazines; calibre alone isn't enough."""
    from .ammo import compatible
    slots = player.invent.slots
    matches = list(dict.fromkeys("secondary" if slot == "holster" else slot
                   for slot in ("primary", "secondary", "holster")
                   if slots.get(slot) is not None and slots[slot].t.kind == "gun" and compatible(item, slots[slot])))
    return ("P/S", AMMO_BOTH) if len(matches) == 2 else \
        ("P", AMMO_PRIMARY) if matches == ["primary"] else \
        ("S", AMMO_SECONDARY) if matches else ("", NEUTRAL)


def _dir(game, dx, dy):
    w = direction_word(dx, dy)
    if game.__dict__.get("domain") == "aboard":
        return SHIP_DIRS.get(w, w)            # aboard, directions are the ship's: forward, aft, port, starboard
    return w


def _yd(d):
    y = d * 2.2
    return f"{int(round(y))}y" if y < 15 else f"{int(round(y / 10.0) * 10)}y"


def _who(game, a, d):
    """What you'd call him from here: a name if he's one of yours, otherwise what he looks like."""
    p = game.player
    if a.ai.get("civilian"):
        return a.ai.get("occupation", "civilian")
    if a.side == p.side and a.squad is not None and a.squad is p.squad:
        return a.name.split()[-1] if a.name else a.role_name
    nat = NATIONS.get(a.nation, {}).get("adj", "")
    if d > 60 and not game.player_binoculars:
        return f"{nat} soldier"                # too far to tell an MG gunner from a rifleman
    return f"{nat} {a.role_name.lower()}"


def _state(a):
    if a.state == "surrendered":
        return "hands up"
    if a.downed:
        return "down"
    if a.suppression > 50:
        return "pinned"
    return ""                                  # crouched or prone: the look tooltip says so


def gather(game):
    """{tab: [entry]} - entry: dict(x, y, label, right, color, d, group)."""
    p = game.player
    m = game.map
    ox, oy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
    men = []
    for a in game.actors:
        if a is p or not a.alive or a.vehicle is not None or not m.in_bounds(a.x, a.y):
            continue
        if not m.visible[a.x, a.y] or not player_can_see_actor(game, a):
            continue
        d = math.hypot(a.x - ox, a.y - oy)
        friend = a.side == p.side
        if a.ai.get("civilian"):
            group, col = "Civilians", NEUTRAL
        elif a.state == "surrendered" and not friend:
            group, col = "Prisoners and the surrendering", NEUTRAL
        else:
            group, col = ("Friendly", FRIEND_COLOR) if friend else ("Enemy", ENEMY_COLOR)
        st = _state(a)
        job = a.ai.get("support_job")
        label = _who(game, a, d) + (f" ({st})" if st else "")
        if friend and not st and job and job["target"] == p.id and job["until"] > game.turn:
            label = ("Ammo for you: " if job["kind"] == "ammo" else "Aid for you: ") + a.last_name
        men.append(dict(x=a.x, y=a.y, label=label,
                        right=f"{_yd(d)} {_dir(game, a.x - ox, a.y - oy)}", color=col, d=d, group=group,
                        enemy=not friend and a.state != "surrendered" and not a.ai.get("civilian")))
    for v in game.vehicles:
        if v.dead and not v.burning:
            continue
        if not m.in_bounds(v.x, v.y) or not (m.visible[v.x, v.y] or p.vehicle is v) or p.vehicle is v:
            continue
        d = math.hypot(v.x - ox, v.y - oy)
        friend = v.side == p.side
        name = v.vt.name if (friend or d < 60 or game.player_binoculars) else "a vehicle"
        if v.dead:
            name += " (burning)"
        men.append(dict(x=v.x, y=v.y, label=name, right=f"{_yd(d)} {_dir(game, v.x - ox, v.y - oy)}",
                        color=FRIEND_COLOR if friend else ENEMY_COLOR, d=d,
                        group="Friendly" if friend else "Enemy", enemy=not friend and not v.dead))
    if p.body.deaf <= 0:
        seen = set()
        for s in game.sound_marks:
            if not m.in_bounds(s.x, s.y) or m.visible[s.x, s.y] or (s.x // 4, s.y // 4, s.kind) in seen:
                continue
            seen.add((s.x // 4, s.y // 4, s.kind))
            d = math.hypot(s.x - ox, s.y - oy)
            what = {"brrrt": "MG fire", "rat-tat": "SMG fire", "crack": "a shot", "BOOM": "a big blast",
                    "bang": "a blast"}.get(s.text) or \
                {"gunfire": "gunfire", "explosion": "a blast", "shell": "a shell", "footsteps": "movement",
                 "engine": "an engine", "scream": "a scream", "shout": "a shout"}.get(s.kind, s.kind)
            men.append(dict(x=s.x, y=s.y, label=what, right=f"~{_yd(d)} {_dir(game, s.x - ox, s.y - oy)}",
                            color=HEARD, d=d, group="Heard, not seen", heard=s.text))
    order = {"Enemy": 0, "Prisoners and the surrendering": 1, "Friendly": 2, "Heard, not seen": 3}
    men.sort(key=lambda e: (order.get(e["group"], 9), e["d"]))
    items = []
    for (x, y), pile in m.items.items():
        if not pile or not m.visible[x, y]:
            continue
        d = math.hypot(x - ox, y - oy)
        if d > 60:
            continue                             # a rifle in the grass at 130 yards is just grass
        names = []
        item_colors = []
        matches = set()
        first_match = None
        for it in pile:
            if it.t.kind == "corpse" and it.data:
                ours = it.data.get("side") == p.side
                nat = NATIONS.get(it.data.get("nation"), {}).get("adj", "")
                n = f"dead {nat}" + ("" if not ours else " (ours)")
                from .entities import visible_body_items
                for kit, loc in visible_body_items(it, d):
                    tag, color = ammo_match(p, kit)
                    label = (f"[{tag}] " if tag else "") + kit.name
                    source = f"{n}: {loc}"
                    items.append(dict(x=x, y=y, label=label, right=f"{_yd(d)} {_dir(game, x - ox, y - oy)}",
                                      color=color, d=d, group="On bodies", body=it,
                                      names=[label, source, "Enter: approach and open this body's kit."],
                                      item_colors=[color, UI_DIM, UI_DIM]))
                if d <= 8 and not it.data.get("searched"):
                    n += " (pockets / closed pack unsearched)"
            else:
                n = it.name
            tag, col = ammo_match(p, it)
            if tag:
                matches.update(tag.split("/"))
                n = f"[{tag}] {n}"
                if first_match is None:
                    first_match = n
            if it.data and it.data.get("live") is not None:
                n = "LIVE " + n
                col = (255, 90, 70)
            names.append(n)
            item_colors.append(col)
        label = (first_match or names[0]) + (f" +{len(names) - 1}" if len(names) > 1 else "")
        danger = any(it.data and it.data.get("live") is not None for it in pile)
        col = AMMO_BOTH if len(matches) == 2 else AMMO_PRIMARY if "P" in matches else \
            AMMO_SECONDARY if matches else NEUTRAL
        items.append(dict(x=x, y=y, label=label, right=f"{_yd(d)} {_dir(game, x - ox, y - oy)}",
                          color=(255, 90, 70) if danger else col, d=d,
                          group="Here" if d < 1 else "On the ground", names=names, item_colors=item_colors))
    for entry in items:
        if entry["d"] < 1:
            entry["right"] = "here"
    items.sort(key=lambda e: (e["d"], e["group"]))
    return {"Soldiers": men, "Items": items}


def heard_lines(e):
    """The tooltip for a sound: you didn't see it, so all you can say is what and roughly where."""
    return [(f"'{e['heard']}' - {e['label']}", HEARD),
            ("somewhere about here - a guess from the sound", UI_DIM)]


def draw(con, ps):
    """The list, over the right-hand panel."""
    st = ps.nearby
    g = ps.game
    x0 = SCREEN_W - PANEL_W
    w = PANEL_W
    con.draw_rect(x0, 0, w, SCREEN_H, ord(" "), bg=UI_BG)
    from . import icons
    icons.erase(x0, 0, w, SCREEN_H)               # (the panel's pictures: the list is over them)
    tab = TABS[st["tab"]]
    entries = st["lists"][tab]
    head = "  ".join(f"[{t}]" if t == tab else t for t in TABS)
    con.print(x0 + 1, 0, head[:w - 2], fg=UI_HI, bg=UI_BG)
    if tab == "Items":
        for offset, row, label, col in ((1, 1, "P primary", AMMO_PRIMARY), (12, 1, "S secondary", AMMO_SECONDARY),
                                        (1, 2, "P/S both", AMMO_BOTH)):
            con.print(x0 + offset, row, label[:max(0, w - offset - 1)], fg=col, bg=UI_BG)
    else:
        con.print(x0 + 1, 1, ("binoculars up" if g.player_binoculars else "by eye")[:w - 2], fg=UI_DIM, bg=UI_BG)
    if not entries:
        con.print(x0 + 1, 3, "Nothing." if tab == "Items" else "Nobody in sight.", fg=UI_DIM, bg=UI_BG)
    rows = SCREEN_H - 8
    sel = st["sel"]
    top = max(0, min(sel - rows // 2, len(entries) - rows))
    y = 3
    last_group = None
    for i in range(top, len(entries)):
        e = entries[i]
        if y >= SCREEN_H - 4:
            break
        if e["group"] != last_group:
            con.print(x0 + 1, y, e["group"][:w - 2], fg=UI_DIM, bg=UI_BG)
            last_group = e["group"]
            y += 1
            if y >= SCREEN_H - 4:
                break
        right = e["right"]
        room = w - 3 - len(right)
        label = e["label"] if len(e["label"]) <= room else e["label"][:room - 1] + "…"
        bg = (70, 60, 30) if i == sel else UI_BG
        con.print(x0 + 1, y, " " * (w - 2), bg=bg)
        con.print(x0 + 1, y, label, fg=e["color"], bg=bg)
        con.print(x0 + w - 1 - len(right), y, right, fg=UI_TEXT if i == sel else UI_DIM, bg=bg)
        y += 1
    if entries and len(entries) > rows:
        con.print(x0 + 1, SCREEN_H - 4, f"{sel + 1} of {len(entries)}", fg=UI_DIM, bg=UI_BG)
    keys = ["↑↓ pick   Tab " + TABS[1 - st["tab"]].lower()]
    keys.append("f/Enter fire, or go to" if tab == "Soldiers" else "Enter go and pick up")
    keys.append("/ find  x look  b binocs  Esc")
    for i, k in enumerate(keys):
        con.print(x0 + 1, SCREEN_H - 3 + i, k[:w - 2], fg=UI_DIM, bg=UI_BG)
