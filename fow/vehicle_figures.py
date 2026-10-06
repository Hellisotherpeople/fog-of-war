"""Visible occupants of vehicles and gun positions; no extra simulated soldiers.

Crew strength represents the unnamed crew. Named crewmen (including the player)
replace those figures, while passengers come only from the actual passenger list.
Positions are fractions of a map tile, attached to the hull or rotating turret.
"""
from __future__ import annotations

import math
from typing import NamedTuple

from .footprint import rect_center


class Occupant(NamedTuple):
    x: float
    y: float
    facing: int
    pose: str
    appearance: tuple
    scale: float


def appearance(nation, climate, actor=None, tanker=False):
    from .sprites import UNIFORM
    from .figures import HELMET_STYLE
    helmet = "cap" if tanker else UNIFORM.get(nation, UNIFORM["usa"])[2]
    coat = "none"
    skin = 0
    if actor is not None:
        nation = actor.nation
        head = actor.invent.slots.get("head")
        helmet = HELMET_STYLE.get(head.tid if head else None, helmet)
        body = actor.invent.slots.get("body")
        coat = "smock" if body and body.tid == "snow_smock" else "none"
        tanker = actor.role == "tank_crew"
        skin = actor.id % 4
    return nation, climate, helmet, coat, tanker, skin


def occupants(v, climate="summer", turn=0):
    """A bounded, hashable drawing description derived from the current vehicle state."""
    if v.dead:
        return ()
    from . import crew
    from .sprites import vehicle_class
    from .vdamage import hatch_user
    vc, vt = vehicle_class(v.vt), v.vt
    length, width = v.size
    hull = v.body_facing % 8
    cx, cy = rect_center(length, width, hull)
    out = []

    def place(x, y, pose, actor=None, frame=None, heading=None, scale=.6, tanker=False):
        frame = hull if frame is None else frame % 8
        ang = -frame * math.pi / 4
        dx, dy = x * math.cos(ang) - y * math.sin(ang), x * math.sin(ang) + y * math.cos(ang)
        if actor is not None and actor.downed:
            pose = "slumped"
        out.append(Occupant(round(cx + dx, 4), round(cy + dy, 4),
                            frame if heading is None else (frame + heading) % 8, pose,
                            appearance(v.nation, climate, actor, tanker), scale))

    count = max(0, int(v.crew)) if not v.abandoned else 0
    stations = [s for s in crew.stations(vt) if s in crew.manned(v)][:count] if count else []
    stations += [f"assistant{i}" for i in range(count - len(stations))]
    named = [a for a in v.crew_actors if a.alive and a.vehicle is v]
    player = next((a for a in named if a.is_player), None)
    remaining = iter(a for a in named if a is not player)
    members = {seat: player if player is not None and v.player_crewed and v.player_station == seat
               else next(remaining, None) for seat in stations}
    # Soft-skinned trucks use a canvas-covered load bed in this tileset. Armour's
    # open_top flag also describes vulnerability; it does not remove a drawn roof.
    exposed = vt.static or (vt.open_top and vc not in ("truck", "ambulance", "wagon"))
    if vt.static:
        # Gunner at the sights; loader on the other side of the breech; the rest
        # pass ammunition along the trails. All centres stay in the gun footprint.
        positions = [(-.06, -.32), (-.12, .32), (-.4, .02), (-.4, -.36),
                     (-.4, .36), (.3, -.38), (.3, .38), (-.2, -.38), (-.2, .38), (-.2, -.09), (-.2, .13)]
        if vc == "aagun":
            positions[0:3] = [(-.04, -.3), (-.1, .3), (-.36, .02)]
        for i, seat in enumerate(stations[:len(positions)]):
            x, y = positions[i]
            loading = v.reload > 0 and (seat == "loader" or seat.startswith("assistant"))
            pose = "load" if loading and (turn // 2) % 2 else "work"
            place(x * length, y * width, pose, members[seat],
                  frame=v.facing if seat in ("gunner", "loader") else hull,
                  heading=0 if x < -.2 else (6 if y < 0 else 2),
                  scale=(.7 if count > 8 else .78) if min(length, width) > 1 else .64)
    elif exposed:
        for i, seat in enumerate(stations):
            actor = members[seat]
            if vc == "aa_halftrack":
                if seat == "driver":
                    place(.11 * length, -.21 * width, "drive", actor, scale=.52)
                elif seat == "gunner":
                    place(-.1 * length, 0, "work", actor, frame=v.turret, scale=.48)
                else:
                    place(-.36 * length, (-.22 if i % 2 == 0 else .22) * width,
                          "load" if v.reload > 0 and (turn // 2) % 2 else "seated", actor, scale=.48)
            elif vc in ("halftrack", "car", "motorcycle"):
                x = (.11 if vc == "halftrack" else .21) * length
                y = -.21 * width if seat == "driver" else .2 * width
                if i > 1:
                    x, y = -.28 * length, 0
                place(x, y, "drive" if seat == "driver" else "seated", actor, scale=.52)
            elif vc in ("lc", "amtrac"):
                place(-.42 * length, (-.3 + .3 * i) * width, "drive" if seat == "driver" else "seated",
                      actor, scale=.57)
            else:  # open fighting compartment / open turret, with the driver below the glacis
                if seat == "driver" or (vc == "open_td" and seat.startswith("assistant")) or \
                        (vc == "armcar" and seat == "loader"):
                    continue
                pos = {"gunner": (.06, -.14), "loader": (-.1, .14), "commander": (-.2, -.03)}
                x, y = pos.get(seat, (-.25, .2))
                pose = "load" if seat == "loader" and v.reload > 0 and (turn // 2) % 2 else "work"
                place(x * length, y * width, pose, actor, frame=v.turret if vt.turret else hull,
                      scale=.5 if vc == "armcar" else .6)
    elif vc == "wagon" and stations:
        place(.06 * length, 0, "drive", members[stations[0]], scale=.6)
    elif not v.buttoned:
        seat = hatch_user(v)
        if seat in members:
            place(-.03 * length, -.13 * width, "hatch", members[seat],
                  frame=v.turret if vt.turret else hull, scale=.55, tanker=True)

    passengers = [a for a in v.passengers if a.alive and a.vehicle is v]
    riders = not vt.seats and vt.vtype in ("tank", "td", "spg")
    if passengers and (exposed or riders):
        rows = max(1, math.ceil(max(len(passengers), vt.seats if not riders else 6) / 2))
        for i, actor in enumerate(passengers):
            row, side = i // 2, -1 if i % 2 == 0 else 1
            if riders:
                # Engine-deck riders stay behind the turret, including on closed tanks.
                x = -.4 * length + row * .16 * length
                y = side * .29 * width
                scale = .6
            elif vc == "car":
                x = .2 * length if i == 0 else -.2 * length
                y = .22 * width if i == 0 else side * .22 * width
                scale = .52
            else:
                start, end = (-.3, .32) if vc in ("lc", "amtrac") else (-.37, -.02)
                x = (start + (end - start) * row / max(1, rows - 1)) * length
                y = side * .24 * width
                scale = .48 if width == 1 else .57
            place(x, y, "seated", actor, heading=2 if side > 0 else 6, scale=scale)
    return tuple(out)


def paint_person(spec):
    """Helmet, face, shoulders, hands and the task in front of him, at tile master scale."""
    from .sprites import Canvas, M, UNIFORM, _helmet, shade, mix
    from .figures import CREW, DESERT, TROPICAL, SKINS, SKIN_DEFAULT
    from PIL import Image
    nation, climate, helmet, coat, tanker, skin_index = spec.appearance
    uniform, helm, _, web = UNIFORM.get(nation, UNIFORM["usa"])
    if climate == "desert" and nation in DESERT:
        uniform = DESERT[nation][0]
    elif climate in ("tropical", "jungle") and nation in TROPICAL:
        uniform = TROPICAL[nation][0]
    if tanker:
        uniform = CREW.get(nation, uniform)
    if coat == "smock":
        uniform = mix(uniform, (230, 233, 235), .8)
    skin = SKINS.get(nation, SKIN_DEFAULT)[skin_index % len(SKINS.get(nation, SKIN_DEFAULT))]
    edge = (25, 24, 22, 255)
    c = Canvas()
    pose = spec.pose
    if pose == "hatch":
        c.ellipse((12, 15, 49, 51), fill=(25, 27, 22, 255), outline=(165, 163, 137, 255), width=3)
    else:
        c.shadow((9, 14, 53, 55), 105, 2)
        c.ellipse((9, 19, 25, 30), fill=(49, 40, 33, 255), outline=edge)
        c.ellipse((9, 36, 25, 47), fill=(49, 40, 33, 255), outline=edge)
    c.ellipse((19, 12, 43, 52), fill=uniform + (255,), outline=edge, width=2)
    c.line([(23, 18), (32, 43)], fill=web + (255,), width=3)
    c.line([(23, 46), (32, 22)], fill=web + (255,), width=3)
    if pose != "hatch":
        reach = 53 if pose in ("work", "load", "drive") else 44
        c.line([(32, 17), (reach - 7, 17), (reach, 25)], fill=uniform + (255,), width=7)
        c.line([(32, 47), (reach - 7, 47), (reach, 39)], fill=uniform + (255,), width=7)
        c.ellipse((reach - 3, 22, reach + 3, 28), fill=skin + (255,), outline=edge)
        c.ellipse((reach - 3, 36, reach + 3, 42), fill=skin + (255,), outline=edge)
        if pose == "load":
            c.rect((43, 23, 54, 42), fill=(169, 137, 68, 255), outline=edge)
            c.poly([(43, 23), (54, 23), (49, 15)], fill=(93, 98, 73, 255), outline=edge)
        elif pose == "drive":
            c.ellipse((44, 23, 58, 41), outline=(28, 28, 27, 255), width=3)
    hx, hy = (28, 38) if pose == "slumped" else (35, 32)
    c.ellipse((hx + 2, hy - 8, hx + 13, hy + 8), fill=skin + (255,), outline=edge)
    if helmet == "bare":
        c.ellipse((hx - 10, hy - 9, hx + 7, hy + 9), fill=(77, 59, 43, 255), outline=edge, width=2)
    else:
        _helmet(c, "cap" if helmet in ("tanker", "peaked") else helmet, helm, hx, hy, 11)
    img = c.img.resize((round(M * spec.scale), round(M * spec.scale)), Image.Resampling.LANCZOS)
    return img.rotate(spec.facing * 45, resample=Image.Resampling.BICUBIC, expand=True)


def paint_pieces(figures):
    """Composite occupants before slicing: several people can share a transport's tile."""
    import numpy as np
    from PIL import Image
    from .sprites import M
    if not figures:
        return {}
    # Two tiles of padding cover the shoulders at diagonal facings without clipping.
    left = math.floor(min(s.x for s in figures)) - 1
    top = math.floor(min(s.y for s in figures)) - 1
    right = math.ceil(max(s.x for s in figures)) + 2
    bottom = math.ceil(max(s.y for s in figures)) + 2
    canvas = Image.new("RGBA", ((right - left) * M, (bottom - top) * M))
    for spec in sorted(figures, key=lambda s: s.y):
        person = paint_person(spec)
        px = round((spec.x - left + .5) * M - person.width / 2)
        py = round((spec.y - top + .5) * M - person.height / 2)
        canvas.alpha_composite(person, (px, py))
    out = {}
    for dx in range(left, right):
        for dy in range(top, bottom):
            x, y = (dx - left) * M, (dy - top) * M
            tile = np.asarray(canvas.crop((x, y, x + M, y + M)), dtype=np.uint8)
            if tile[..., 3].max() >= 12:
                out[(dx, dy)] = tile.copy()
    return out
