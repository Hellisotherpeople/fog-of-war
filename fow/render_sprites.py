"""Sprite-mode battlefield rendering: builds the stack of layer consoles."""
from __future__ import annotations

import math

from .figures import look

import numpy as np
import tcod

from . import tiles as T
from .constants import ENEMY_COLOR, FRIEND_COLOR, PLAYER_COLOR
from .render import ITEM_PRIORITY
from .senses import daylight, player_can_see_actor
from .sprites import vehicle_camo, vehicle_class

SQUAD_RING = (140, 255, 230)
N_LAYERS = 8   # terrain, decals, rings, hulls, units, top (turrets/aircraft), effects, filter


def _layer(vw, vh, opaque=False):
    c = tcod.console.Console(vw, vh, order="F")
    c.rgba["ch"] = 0
    c.rgba["fg"] = (255, 255, 255, 255)
    c.rgba["bg"] = (0, 0, 0, 255 if opaque else 0)
    return c


def item_kind(it) -> str:
    t = it.t
    if t.kind == "corpse":
        return "corpse"
    if t.kind == "gun":
        return {"pistol": "pistol", "smg": "smg", "lmg": "mg", "hmg": "mg", "at_launcher": "tube",
                "at_disposable": "tube", "mortar": "tube", "flamer": "tube"}.get(t.cat, "rifle")
    if t.kind in ("grenade", "explosive"):
        return "live" if it.data and it.data.get("live") is not None else "grenade"
    if t.kind == "ammo":
        return "ammo"
    if t.kind == "medical":
        return "medical"
    if t.kind == "armor":
        return "helmet"
    if t.tool == "ammo_crate":
        return "crate"
    return "tool"


def draw_sprite_layers(bank, game, cam, frame=0, ui=None):
    m = game.map
    p = game.player
    vw, vh = cam.vw, cam.vh
    x0, y0 = cam.x0, cam.y0
    from .render import beyond_parts, view_window
    sx0, sy0, ox, oy, w, h = view_window(m, cam, vw, vh)
    S = (slice(sx0, sx0 + w), slice(sy0, sy0 + h))       # this map's part of the view...
    D = (slice(ox, ox + w), slice(oy, oy + h))           # ...and where it goes on screen
    L = [_layer(vw, vh, opaque=True)] + [_layer(vw, vh) for _ in range(N_LAYERS - 1)]
    terr, deco, rings, hulls, units, top, fx, filt = L

    # ---------------------------------------------------------------- the ground next door
    d = daylight(game)
    for dest, bt, bvar, seen, lit, far in beyond_parts(game, cam, vw, vh):
        ch = (0xE000 + bt * 4 + (bvar % 4)).astype(np.uint32)
        ch[~seen] = 0
        terr.rgba["ch"][dest] = ch
        f = np.where(lit, 128, 88) * (1 - np.clip(far / (22 * 2.2), 0, 0.4)) * (0.55 + 0.45 * d)
        terr.rgba["fg"][dest] = np.stack([f * 0.88, f * 0.94, f * 1.12, np.full_like(f, 255)], axis=-1) \
            .clip(0, 255).astype(np.uint8)

    marks = game.__dict__.get("front_marks") or ()
    if marks:
        night = game.is_night()
        for mk in marks:
            if cam.on_screen(mk["x"], mk["y"]):
                top.rgba["ch"][mk["x"] - x0, mk["y"] - y0] = bank.effect("smoke", 0)
                top.rgba["fg"][mk["x"] - x0, mk["y"] - y0] = (240, 140, 70, 200) if night else (190, 186, 180, 170)

    # ---------------------------------------------------------------- terrain + light
    t = m.t[S]
    var = m.var[S]
    vis = m.visible[S]
    exp = m.explored[S]
    terr.rgba["ch"][D] = 0xE000 + t * 4 + (var % 4)
    base = 0.42 + 0.58 * d
    if game.weather == "fog":
        base *= 0.9
    light = np.full((w, h), base, np.float32)
    from .relief import shade
    sh = shade(m)
    if sh is not None:
        light = np.minimum(light * sh[S], 1.0)  # the lie of the land (relief.py)
    if d < 0.95 and game.lit is not None:
        light = np.where(game.lit[S], np.maximum(light, 0.95), light)
    tint = np.zeros((w, h, 3), np.float32)
    tint[...] = 255
    tint *= light[..., None]
    if d < 0.6:
        tint[..., 2] = np.minimum(255, tint[..., 2] * 1.15 + 10)       # moonlight
    mem = exp & ~vis
    tint[mem] = (70, 74, 88)
    terr.rgba["fg"][ox:ox + w, oy:oy + h, :3] = np.clip(tint, 0, 255).astype(np.uint8)
    terr.rgba["ch"][D][~exp] = 0
    light_rgb = np.full((vw, vh, 3), 255, np.float32)
    light_rgb[D] = tint

    def tint_at(sx, sy):
        if 0 <= sx < vw and 0 <= sy < vh:
            return tuple(int(v) for v in light_rgb[sx, sy]) + (255,)
        return (255, 255, 255, 255)

    # ---------------------------------------------------------------- reading the ground (X)
    if ui is not None and getattr(ui, "going_on", lambda: False)():
        from .going import tint
        gcol, ga = tint(game, S[0], S[1])
        ga = np.where(exp, ga, 0.0)
        deco.rgba["bg"][ox:ox + w, oy:oy + h, :3] = gcol.astype(np.uint8)
        deco.rgba["bg"][ox:ox + w, oy:oy + h, 3] = np.clip(ga * 235, 0, 255).astype(np.uint8)

    # ---------------------------------------------------------------- decals
    blood = m.blood[S]
    scorch = m.scorch[S]
    bmask = (blood > 20) & exp
    cp_blood = bank.effect("blood")
    cp_scorch = bank.effect("scorch")
    deco.rgba["ch"][D][scorch.astype(bool) & exp] = cp_scorch
    deco.rgba["ch"][D][bmask] = cp_blood
    alpha = np.clip(blood.astype(np.int32) + 40, 0, 255).astype(np.uint8)
    deco.rgba["fg"][ox:ox + w, oy:oy + h, 3][bmask] = alpha[bmask]
    # fire and smoke
    fire = m.fire[S]
    fmask_in = (fire > 0) & vis
    fmask = np.zeros((vw, vh), bool)
    fmask[D] = fmask_in
    if fmask_in.any():
        deco.rgba["ch"][D][fmask_in] = bank.effect("fire", (game.turn + frame) % 3)
    smoke = m.smoke[S]
    smask = (smoke > 0.25) & exp
    if smask.any():
        top.rgba["ch"][D][smask] = bank.effect("smoke", 0)
        top.rgba["fg"][ox:ox + w, oy:oy + h, 3][smask] = np.clip(smoke * 90, 40, 235).astype(np.uint8)[smask]
    # items
    for (x, y), items in m.items.items():
        if not items or not cam.on_screen(x, y) or not m.visible[x, y]:
            continue
        sx, sy = x - x0, y - y0
        if 0 <= sx < vw and 0 <= sy < vh and fmask[sx, sy]:
            continue
        topi = min(items, key=lambda i: ITEM_PRIORITY.get(i.t.kind, 9))
        kind = item_kind(topi)
        if kind == "live" and (frame // 2) % 2:
            kind = "grenade"
        side_col = None
        if kind == "corpse" and topi.data:
            from .sprites import UNIFORM
            side_col = UNIFORM.get(topi.data.get("nation"), ((110, 105, 80),))[0]
        deco.rgba["ch"][sx, sy] = bank.item(kind, side_col)
        deco.rgba["fg"][sx, sy] = tint_at(sx, sy)
    # known mines
    cp_mine = bank.ring("mine")
    for (x, y), mn in m.mines.items():
        if p.side in mn.known and cam.on_screen(x, y) and m.visible[x, y]:
            deco.rgba["ch"][x - x0, y - y0] = cp_mine
            deco.rgba["fg"][x - x0, y - y0] = (230, 70, 60, 255)

    # ---------------------------------------------------------------- aircraft parked on the ground (parked.py)
    parked = m.__dict__.get("parked")
    if parked:
        from .parked import ids as ac_ids
        acs = ac_ids()
        body_id = T.ID["ac_body"]
        for rec in parked:
            rx, ry, rw, rh = rec["x"], rec["y"], rec["w"], rec["h"]
            if rx + rw < x0 or rx > x0 + vw or ry + rh < y0 or ry > y0 + vh:
                continue
            box = m.t[max(0, rx):rx + rw, max(0, ry):ry + rh]
            if not (box == body_id).any():
                continue                                  # burnt out: the wreck tiles show what's left
            gcp = 0xE000 + int(rec.get("ground", T.ID["grass"])) * 4
            for dx, dy, cp in bank.parked_pieces(rec["model"], rec.get("scheme", rec["nation"]), rec["nation"],
                                                 rec["facing"], rec.get("folded", False)):
                wx, wy = rx + dx, ry + dy
                sx, sy = wx - x0, wy - y0
                if not (0 <= sx < vw and 0 <= sy < vh) or not m.in_bounds(wx, wy) or not m.explored[wx, wy]:
                    continue
                tid = int(m.t[wx, wy])
                if tid in acs:
                    terr.rgba["ch"][sx, sy] = gcp + int(m.var[wx, wy]) % 4      # the ground it stands on
                elif not T.WALK[tid] or T.DEFS[tid].key == "ac_wreck":
                    continue                              # a wreck, or something built there since
                hulls.rgba["ch"][sx, sy] = cp
                hulls.rgba["fg"][sx, sy] = tint_at(sx, sy)

    winter = m.climate == "winter"
    # ---------------------------------------------------------------- vehicles (as big as they are)
    vw, vh = cam.vw, cam.vh

    def lay(layer, pieces, px, py):
        for dx, dy, cp in pieces:
            qx, qy = px + dx - x0, py + dy - y0
            if 0 <= qx < vw and 0 <= qy < vh:
                layer.rgba["ch"][qx, qy] = cp
                layer.rgba["fg"][qx, qy] = tint_at(qx, qy)

    for v in game.vehicles:
        if v.dead:
            continue
        cells = v.cells()
        if not any(cam.on_screen(cx, cy) for cx, cy in cells):
            continue
        if p.vehicle is not v and not any(m.in_bounds(cx, cy) and m.visible[cx, cy] for cx, cy in cells):
            continue
        vc = vehicle_class(v.vt)
        camo = vehicle_camo(v.nation, game.year, m.climate)
        if p.vehicle is v:
            rc = PLAYER_COLOR
        elif v.side == p.side:
            rc = FRIEND_COLOR
        else:
            rc = ENEMY_COLOR
        if v.abandoned or v.crew <= 0:
            rc = tuple(int(c * 0.45) for c in rc)
        vlen, vwid = v.size
        hf = v.body_facing if v.static else v.facing
        gun_face = v.facing if v.static else hf
        if cam.on_screen(v.x, v.y):
            rings.rgba["ch"][v.x - x0, v.y - y0] = bank.ring("bracket")
            rings.rgba["fg"][v.x - x0, v.y - y0] = rc + (200,)
        lay(hulls, bank.vehicle_pieces(vc, camo, vlen, vwid, hf if not v.static else gun_face, 0, "hull",
                                       v.burning > 0), v.x, v.y)
        if vc in ("tank", "heavy", "ltank", "armcar", "tankette") and v.vt.turret:
            lay(top, bank.vehicle_pieces(vc, camo, vlen, vwid, hf, v.turret, "turret"), v.x, v.y)
        if v.burning and (frame + game.turn) % 2 == 0:
            for k, (cx, cy) in enumerate(cells):
                if k % 2 == (game.turn + frame) % 2 and cam.on_screen(cx, cy):
                    fx.rgba["ch"][cx - x0, cy - y0] = bank.effect("fire", (game.turn + frame + k) % 3)

    # ---------------------------------------------------------------- soldiers
    for a in game.actors:
        if not a.alive or a.vehicle is not None or not cam.on_screen(a.x, a.y):
            continue
        if not player_can_see_actor(game, a):
            continue
        sx, sy = a.x - x0, a.y - y0
        if a.state == "surrendered":
            state = "surrendered"
        elif a.downed:
            state = "downed"
        else:
            state = "ok"
        cached = a.ai.get("_look")
        if cached is None or cached[0] != game.turn:
            cached = (game.turn, look(a, game))
            a.ai["_look"] = cached
        units.rgba["ch"][sx, sy] = bank.figure(cached[1])
        units.rgba["fg"][sx, sy] = tint_at(sx, sy)
        if a is p:
            rc = PLAYER_COLOR
        elif a.side == p.side:
            rc = SQUAD_RING if (p.squad is not None and a.squad is p.squad) else FRIEND_COLOR
        else:
            rc = ENEMY_COLOR
        leader = a.squad is not None and a.squad.leader is a and a.side == p.side
        rings.rgba["ch"][sx, sy] = bank.ring("player" if a is p else "leader" if leader else "ring")
        rings.rgba["fg"][sx, sy] = rc + (255,)

    # ---------------------------------------------------------------- aircraft
    for ac in game.support.aircraft:
        x, y = int(ac.x), int(ac.y)
        o = int(round(math.atan2(-ac.dy, ac.dx) / (math.pi / 2))) % 4
        if cam.on_screen(x, y):
            top.rgba["ch"][x - x0, y - y0] = bank.aircraft(ac.nation, o)
        shx, shy = x + 2, y + 3
        if cam.on_screen(shx, shy):
            rings.rgba["ch"][shx - x0, shy - y0] = bank.aircraft(ac.nation, o, shadow=True)

    # ---------------------------------------------------------------- effects
    if ui is not None and ui.anim > 0:
        f = 4 - ui.anim
        for e in game.effects:
            k = e["kind"]
            if k == "tracer":
                pts = tcod.los.bresenham((e["x0"], e["y0"]), (e["x1"], e["y1"]))
                n = len(pts)
                if n < 2:
                    continue
                head = int(min(n - 1, (f + 1) * max(3, n // 3)))
                tail = max(1, head - (3 if not e["mg"] else 5))
                cp = bank.effect("rocket" if e.get("rocket") else "tracer")
                for i in range(tail, head + 1):
                    x, y = int(pts[i][0]), int(pts[i][1])
                    if cam.on_screen(x, y) and m.in_bounds(x, y) and m.visible[x, y]:
                        fx.rgba["ch"][x - x0, y - y0] = cp
            elif k == "flash" and f <= 1:
                if cam.on_screen(e["x"], e["y"]) and m.in_bounds(e["x"], e["y"]):
                    fx.rgba["ch"][e["x"] - x0, e["y"] - y0] = bank.effect("flash")
            elif k == "explosion":
                r = e["r"]
                cx, cy = e["x"], e["y"]
                rr = min(r, f + 1) if r else 0
                for dx in range(-rr, rr + 1):
                    for dy in range(-rr, rr + 1):
                        dd = math.hypot(dx, dy)
                        if dd > rr + 0.3:
                            continue
                        x, y = cx + dx, cy + dy
                        if cam.on_screen(x, y) and m.in_bounds(x, y) and m.visible[x, y]:
                            fx.rgba["ch"][x - x0, y - y0] = bank.effect("explosion", min(3, int(dd) + f // 2))
            elif k == "splash":
                if cam.on_screen(e["x"], e["y"]) and m.in_bounds(e["x"], e["y"]):
                    fx.rgba["ch"][e["x"] - x0, e["y"] - y0] = bank.effect("splash")
            elif k == "flame":
                for i, (x, y) in enumerate(e["pts"][: f * 3 + 3]):
                    if cam.on_screen(x, y):
                        fx.rgba["ch"][x - x0, y - y0] = bank.effect("flame")
            elif k == "throw":
                pts = tcod.los.bresenham((e["x0"], e["y0"]), (e["x1"], e["y1"]))
                n = len(pts)
                i = min(n - 1, int((f + 1) * n / 3))
                x, y = int(pts[i][0]), int(pts[i][1])
                if cam.on_screen(x, y):
                    fx.rgba["ch"][x - x0, y - y0] = bank.item("grenade")

    # ---------------------------------------------------------------- cursor, target line, destination
    if ui is not None:
        if ui.mode != "normal" and ui.cursor is not None:
            cx, cy = ui.cursor
            if ui.mode in ("target", "throw", "radio_target", "order_target", "flare_target"):
                ox, oy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
                pts = tcod.los.bresenham((ox, oy), (cx, cy))
                blocked = False
                for i in range(1, len(pts) - 1):
                    x, y = int(pts[i][0]), int(pts[i][1])
                    if not m.in_bounds(x, y):
                        break
                    if not m.see[x, y]:
                        blocked = True
                    if cam.on_screen(x, y):
                        fx.rgba["ch"][x - x0, y - y0] = bank.ring("dot")
                        fx.rgba["fg"][x - x0, y - y0] = (230, 70, 60, 200) if blocked else (240, 230, 120, 170)
            if cam.on_screen(cx, cy):
                fx.rgba["ch"][cx - x0, cy - y0] = bank.ring("cursor")
                fx.rgba["fg"][cx - x0, cy - y0] = (255, 255, 255, 255)
        dest = getattr(ui, "travel_dest", None)
        if dest is not None and cam.on_screen(*dest):
            fx.rgba["ch"][dest[0] - x0, dest[1] - y0] = bank.ring("bracket")
            fx.rgba["fg"][dest[0] - x0, dest[1] - y0] = (255, 255, 120, 220)
        hv = getattr(ui, "hover", None)
        if hv is not None and ui.mode == "normal" and cam.on_screen(*hv) and not ui.popups \
                and not getattr(ui, "hover_quiet", False):
            if getattr(ui, "hover_looking", lambda: False)():
                fx.rgba["ch"][hv[0] - x0, hv[1] - y0] = bank.ring("cursor")
                fx.rgba["fg"][hv[0] - x0, hv[1] - y0] = (255, 255, 255, 200)
            fx.rgba["ch"][hv[0] - x0, hv[1] - y0] = fx.rgba["ch"][hv[0] - x0, hv[1] - y0] or bank.ring("bracket")
            if fx.rgba["ch"][hv[0] - x0, hv[1] - y0] == bank.ring("bracket"):
                fx.rgba["fg"][hv[0] - x0, hv[1] - y0] = (255, 255, 255, 110)

    # ---------------------------------------------------------------- condition filter
    apply_filter(filt, game, ui)
    return L


def apply_filter(filt, game, ui):
    p = game.player
    vw, vh = filt.width, filt.height
    a = np.zeros((vw, vh), np.float32)
    col = np.zeros((vw, vh, 3), np.float32)
    sup = p.suppression / 100.0
    if sup > 0.2:
        xs = (np.arange(vw) - vw / 2) / (vw / 2)
        ys = (np.arange(vh) - vh / 2) / (vh / 2)
        r = np.sqrt(xs[:, None] ** 2 + ys[None, :] ** 2)
        inner = 1.05 - sup * 0.8
        a = np.maximum(a, np.clip((r - inner) * 2.2 * sup, 0, 0.85))
    lost = max(0.0, (4600 - p.body.blood) / 2200)
    if lost > 0:
        g = min(0.6, lost * 0.7)
        a2 = np.full((vw, vh), g, np.float32)
        col = col * (a[..., None] / np.maximum(a + a2, 1e-6)[..., None]) + \
            np.array([90, 90, 90], np.float32) * (a2 / np.maximum(a + a2, 1e-6))[..., None]
        a = np.clip(a + a2 * (1 - a), 0, 1)
    if ui is not None and getattr(ui, "flash_red", False):
        a = np.clip(a + 0.3, 0, 1)
        col = col * 0.4 + np.array([150, 0, 0], np.float32) * 0.6
    if a.max() > 0:
        filt.rgba["bg"][..., :3] = np.clip(col, 0, 255).astype(np.uint8)
        filt.rgba["bg"][..., 3] = np.clip(a * 255, 0, 255).astype(np.uint8)
