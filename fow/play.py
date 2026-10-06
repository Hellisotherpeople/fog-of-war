"""The in-battle game state: input, commands, targeting, diegetic popups."""
from __future__ import annotations

from .constants import cap

import math
import time

import numpy as np
import tcod
import tcod.event as E

from . import actions as A
from . import tiles as T
from .ai import Order
from .gamemap import octant
from .combat import describe_chance, dispersion, estimate_hit, vehicle_fire_main, vehicle_fire_mg
from .constants import (COMPASS, DIRS8, ENEMY_COLOR, FRIEND_COLOR, UI_DIM, UI_HI, UI_TEXT,
                        VIEW_H, VIEW_W, other_side)
from .data.items import ITEMS
from .data.nations import NATIONS
from .entities import LOC_NAME, Item, riding
from .render import (Camera, Popup, apply_condition_filters, draw_center_box, draw_cursor,
                     draw_effects, draw_entities, draw_line, draw_log, draw_map, draw_overlays,
                     draw_panel, draw_popup, draw_tooltip)
from .senses import player_can_see_actor

MOVE_KEYS = {
    E.KeySym.UP: (0, -1), E.KeySym.DOWN: (0, 1), E.KeySym.LEFT: (-1, 0), E.KeySym.RIGHT: (1, 0),
    E.KeySym.KP_8: (0, -1), E.KeySym.KP_2: (0, 1), E.KeySym.KP_4: (-1, 0), E.KeySym.KP_6: (1, 0),
    E.KeySym.KP_7: (-1, -1), E.KeySym.KP_9: (1, -1), E.KeySym.KP_1: (-1, 1), E.KeySym.KP_3: (1, 1),
    E.KeySym.HOME: (-1, -1), E.KeySym.PAGEUP: (1, -1), E.KeySym.END: (-1, 1), E.KeySym.PAGEDOWN: (1, 1),
}
VI_KEYS = {"h": (-1, 0), "j": (0, 1), "k": (0, -1), "l": (1, 0), "y": (-1, -1), "u": (1, -1),
           "b": (-1, 1), "n": (1, 1)}
# capitals run - except the ones that are commands (Y shout, B bandage): run those ways with Shift+numpad
COMMAND_CAPS = {"Y", "B"}
WAIT_KEYS = {E.KeySym.KP_5, E.KeySym.KP_PERIOD}


def yards(tiles: float) -> str:
    y = tiles * 2.2
    if y < 15:
        return f"{int(round(y))} yards"
    return f"about {int(round(y / 10.0) * 10)} yards"


class Key:
    """Normalised input: either a special key (sym) or a character."""

    def __init__(self, sym=None, char=None, shift=False):
        self.sym = sym
        self.char = char
        self.shift = shift
        self.ctrl = False

    def move(self):
        if self.sym in MOVE_KEYS:
            return MOVE_KEYS[self.sym]
        if self.char and len(self.char) == 1 and self.char.lower() in VI_KEYS and self.char not in COMMAND_CAPS:
            return VI_KEYS[self.char.lower()]
        return None

    def is_run(self):
        return (self.char is not None and self.char.isupper() and self.char.lower() in VI_KEYS) or \
            (self.sym in MOVE_KEYS and self.shift)


def m_tile(g, p):
    return g.map.tile(p.x, p.y).key


class PlayState:
    def __init__(self, app, game):
        self.app = app
        self.game = game
        game.__dict__["_prefs"] = getattr(app, "settings", None) or {}
        self._autosaved = time.time()
        self._rt_last = time.monotonic()
        self._rt_elapsed = 0.0
        self.cam = Camera()
        self.mode = "normal"
        self.cursor = None
        self.popups: list[Popup] = []
        self.anim = 0
        self.anim_next = 0.0
        self.anim_groups = []
        self._desert_warned = None
        self.hover = None
        self.travel_path = None
        self.travel_dest = None
        self.auto_wait = 0
        self.wait = None              # a wait you chose (z, Z): what you're waiting for, and since when
        self.running = None
        self.pending = None           # callback when a target is picked
        self.target_list = []
        self.target_idx = 0
        self.flash_red = False
        self.last_hp_turn = -1
        self.cook = 0
        self.log_scroll = 0
        self.interrupt_state = None
        self.layers = None
        self.overlay = None
        self._cam_locked = False
        self.view_center = None         # None: the camera follows you; else the world point it's parked on
        self.cam_c = None               # where the view is centred now (float world coords) - glides to cam_target
        self.cam_target = None
        self._cam_t = time.monotonic()
        self.cam_moving = False
        self.map_offset = (0.0, 0.0)    # sub-cell pixel shift of the map layers (smooth scrolling, shake)
        self.shake = 0.0
        self.minimap = bool((getattr(app, "settings", None) or {}).get("minimap", False))  # F5: the sector in a corner
        self._mini = None
        self._view_pos = None           # where you were when the view was parked
        self._drag = None               # middle-button pan in progress
        self.hover_t = 0.0              # when the mouse came to rest on the hovered tile
        self.hover_quiet = False        # a key was pressed since the mouse last moved
        self.inv_screen = None
        self.cmd_show = False
        self.mark_interrupt()
        if game.turn == 0:
            game.msg("(? for help. Your body, kit and orders are on the right. Right-click the map for options.)", "system")

    # ================================================================== rendering
    CURSOR_MODES = ("target", "throw", "order_target", "radio_target", "flare_target", "look", "place",
                    "travel_pick", "nearby")

    def sprites(self):
        gfx = getattr(self.app, "gfx", None)
        return gfx is not None and gfx.sprites_on()

    def render(self, con):
        g = self.game
        p = g.player
        if g.__dict__.get("domain", "land") in ("air", "sea") and g.__dict__.get("skysea") is not None and \
                not getattr(self, "_skysea_pushed", False):
            from .skyseaui import SkySeaState
            self._skysea_pushed = True
            self.app.push(SkySeaState(self.app, g, self))
            if g.map is None:
                return                        # (the sky view draws itself from the next frame)
        elif g.__dict__.get("domain", "land") in ("land", "aboard"):
            if g.__dict__.get("domain") == "aboard":
                from . import aboard as AB
                if AB.ended(g) and not g.game_over:
                    return self._leave_ship()
                st_ = (g.aboard or {}).pop("push_station", None)
                if st_:
                    AB.take_station(self, st_)
            else:
                self._skysea_pushed = False
        if g.map is None:
            # in the air or at sea with no ground under him (the sky view draws itself): nothing to draw here
            con.clear()
            self.layers = self.overlay = None
            return
        gfx = getattr(self.app, "gfx", None)
        sprites = self.sprites()
        g.__dict__["_realtime_label"] = self.realtime_label()
        try:
            g.__dict__["_order_hint"] = self.order_hint()
        except Exception:
            g.__dict__["_order_hint"] = None
        try:
            g.__dict__["_ctx_hint"] = self.context_hint() if self.app.settings.get("hints", True) else None
        except Exception:
            g.__dict__["_ctx_hint"] = None
        con.clear()
        self.layers = None
        self.overlay = None
        if not p.body.conscious and not g.game_over:
            con.draw_rect(0, 0, VIEW_W, VIEW_H, ord(" "), bg=(0, 0, 0))
            t = ["...", "Voices, far away.", "Someone is shouting your name.", "Cold. So cold."]
            con.print(VIEW_W // 2 - 10, VIEW_H // 2, t[(g.turn // 20) % len(t)], fg=(120, 60, 60))
            draw_panel(con, g)
            draw_log(con, g)
            return
        layered = gfx is not None          # the real window: the map is its own (zoomable) layer
        if layered:
            vw, vh = gfx.map_view_size()
            self.cam.configure(vw + 1, vh + 1, *gfx.map_scale())   # a spare column/row for smooth scrolling
            self._update_camera(g, gfx)
        else:
            self.cam.configure(VIEW_W, VIEW_H)
            self.map_offset = (0.0, 0.0)
            if self.mode in self.CURSOR_MODES and self.cursor:
                if not self._cam_locked:
                    self._place_cam(g)
                    self._cam_locked = True
                self.cam.ensure_visible(g, *self.cursor)
            else:
                self._cam_locked = False
                self._place_cam(g)
        self._mapcon = None
        if sprites:
            from .render_sprites import draw_sprite_layers
            self.layers = draw_sprite_layers(gfx.sprite_bank, g, self.cam, 4 - self.anim if self.anim else 0, self)
            top = tcod.console.Console(con.width, con.height, order="F")
            top.rgba["bg"] = (0, 0, 0, 0)
            top.rgba["fg"] = (255, 255, 255, 255)
            self.overlay = top
        else:
            mapcon = con
            if layered:
                mapcon = tcod.console.Console(vw + 1, vh + 1, order="F")   # (the camera's spare row and column)
            draw_map(mapcon, g, self.cam, self.anim, going=self.going_on())
            draw_entities(mapcon, g, self.cam, self.anim)
            if self.anim > 0:
                draw_effects(mapcon, g, self.cam, 4 - self.anim)
            apply_condition_filters(mapcon, g, self.flash_red)
            if layered:
                self.layers = [mapcon]
                top = tcod.console.Console(con.width, con.height, order="F")
                top.rgba["bg"] = (0, 0, 0, 0)
                top.rgba["fg"] = (255, 255, 255, 255)
                self.overlay = top
                self._mapcon = mapcon
            else:
                top = con
        draw_overlays(top, g, self.cam, self, sprites)
        from .render import draw_player_pointer
        draw_player_pointer(top, g, self.cam)
        if self.minimap and self.inv_screen is None:
            self._draw_minimap(top)
        zn = getattr(self, "_zoom_note", None)
        if zn is not None and time.monotonic() - zn[0] < 1.2:
            txt = f" zoom {int(round(zn[1] * 100))}% "
            top.print(VIEW_W - len(txt) - 1, VIEW_H - 1, txt, fg=(20, 20, 20), bg=(200, 190, 140))
            self.cam_moving = True          # keep drawing until the note fades
        if self.cmd_show and not self.popups and self.mode != "order_target":
            self.cmd_show = False
        # modes
        if self.inv_screen is not None:
            self.inv_screen.render(top)
        elif self.mode in self.CURSOR_MODES and self.cursor:
            self._render_cursor(top, sprites)
        elif self.hover and not self.popups:
            self._render_hover(top)
        if self.cmd_show:
            from .cmdui import draw_markers
            draw_markers(top, self)
        elif self.inv_screen is None:
            from .cmdui import draw_recent_orders
            draw_recent_orders(top, self)
        for pop in self.popups:
            draw_popup(top, pop)
        draw_panel(con, g)
        if self.mode == "nearby" and getattr(self, "nearby", None):
            from .nearby import draw as draw_nearby
            draw_nearby(con, self)
        draw_log(con, g, self.log_scroll)
        if self.overlay is not None:
            self._finish_overlay()
        if self.mode != "normal":
            hint = {"target": "FIRE: move cursor, Tab next target, f/Enter fire, a aim longer, A aim & fire, Esc cancel",
                    "throw": f"THROW: pick the spot, t/Enter throw, c cook ({self.cook}s), Esc cancel",
                    "look": "LOOK: move cursor, Esc done",
                    "nearby": "AROUND YOU: everything you can see and hear, nearest first (the list is on the right)",
                    "order_target": f"ORDER ({(self.pending or {}).get('label', 'squad')}): pick the spot"
                                    f"{', Tab the suggested places' if (self.pending or {}).get('props') else ''}, "
                                    f"Enter confirm, Esc cancel",
                    "radio_target": "FIRE MISSION: pick the target, Enter confirm, Esc cancel",
                    "flare_target": "FLARE: pick where to fire it, Enter confirm",
                    "place": "PLACE: choose an adjacent tile (direction key)",
                    "peek": "PEEK: lean out which way? (direction key, Esc cancel)",
                    "travel_pick": ""}.get(self.mode, "")
            if hint:
                top.print(0, 0, f" {hint} ", fg=(20, 20, 20), bg=(220, 200, 120))
                if self.overlay is not None:
                    self.overlay.rgba["bg"][: len(hint) + 2, 0, 3] = 255
        elif self.__dict__.get("wait") is not None and self.auto_wait > 0 and not self.wait.get("quick"):
            hint = self.wait_banner()
            top.print(0, 0, f" {hint} ", fg=(20, 20, 20), bg=(170, 200, 230))
            if self.overlay is not None:
                self.overlay.rgba["bg"][: len(hint) + 2, 0, 3] = 255

    # ------------------------------------------------------------ the camera
    def _view_tiles(self, gfx):
        sx, sy = gfx.map_scale()
        return VIEW_W / sx, VIEW_H / sy

    def _player_center(self, g):
        p = g.player
        x, y = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        return x + 0.5, y + 0.5

    def _clamp_center(self, g, cx, cy, wv, hv):
        from .render import EDGE_M
        m = g.map
        e = EDGE_M if g.sector is not None and getattr(g, "pow", None) is None else 0
        lo_x, hi_x = wv / 2 - e, m.w - wv / 2 + e
        lo_y, hi_y = hv / 2 - e, m.h - hv / 2 + e
        cx = (lo_x + hi_x) / 2 if lo_x > hi_x else max(lo_x, min(hi_x, cx))
        cy = (lo_y + hi_y) / 2 if lo_y > hi_y else max(lo_y, min(hi_y, cy))
        return cx, cy

    def _update_camera(self, g, gfx):
        """Where the view should be, and a smooth glide there.

        Following you, it keeps you centred (or, with auto-centre off, only scrolls when you near the
        edge).  Zoomed, dragged or panned somewhere else, it stays there until you move.  In look and
        aim modes it keeps the cursor in view.  Big jumps (a new sector, Home) are instant."""
        wv, hv = self._view_tiles(gfx)
        pc = self._player_center(g)
        auto = (getattr(self.app, "settings", None) or {}).get("auto_center", True)
        pos = (g.player.vehicle.x, g.player.vehicle.y) if g.player.vehicle is not None else (g.player.x, g.player.y)
        moved = pos != self._view_pos
        if moved:
            self._view_pos = pos
        if self.cam_c is None:
            self.cam_c = list(pc)
        tgt = list(self.cam_target or self.cam_c)
        if self.mode in self.CURSOR_MODES and self.cursor:
            # keep the cursor in view with a margin, sliding only as far as needed
            mx, my = min(5.0, wv / 4), min(4.0, hv / 4)
            cx, cy = self.cursor[0] + 0.5, self.cursor[1] + 0.5
            if cx < tgt[0] - wv / 2 + mx:
                tgt[0] = cx - mx + wv / 2
            elif cx > tgt[0] + wv / 2 - mx:
                tgt[0] = cx + mx - wv / 2
            if cy < tgt[1] - hv / 2 + my:
                tgt[1] = cy - my + hv / 2
            elif cy > tgt[1] + hv / 2 - my:
                tgt[1] = cy + my - hv / 2
        elif self.view_center is not None and not (moved and (auto or not self._on_view(pc, wv, hv, 1.0))):
            tgt = list(self.view_center)
        else:
            self.view_center = None
            if auto:
                tgt = list(pc)
            else:
                # deadzone: scroll only when you get near the edge of the view
                mx, my = wv * 0.3, hv * 0.3
                if pc[0] < tgt[0] - mx:
                    tgt[0] = pc[0] + mx
                elif pc[0] > tgt[0] + mx:
                    tgt[0] = pc[0] - mx
                if pc[1] < tgt[1] - my:
                    tgt[1] = pc[1] + my
                elif pc[1] > tgt[1] + my:
                    tgt[1] = pc[1] - my
        # the mouse at the edge of the battlefield scrolls it (if you like that)
        now = time.monotonic()
        dt = min(0.25, now - self._cam_t)
        self._cam_t = now
        if (getattr(self.app, "settings", None) or {}).get("edge_scroll") and self._drag is None and not self.popups:
            mxt, myt = getattr(self, "mouse_txt", (-1, -1))
            if 0 <= mxt < VIEW_W and 0 <= myt < VIEW_H:
                ex = -1 if mxt < 1.5 else 1 if mxt > VIEW_W - 1.5 else 0
                ey = -1 if myt < 1.0 else 1 if myt > VIEW_H - 1.0 else 0
                if ex or ey:
                    base = list(self.view_center or tgt)
                    base[0] += ex * wv * 0.9 * dt
                    base[1] += ey * hv * 0.9 * dt
                    self.view_center = tuple(base)
                    tgt = list(base)
        tgt = list(self._clamp_center(g, tgt[0], tgt[1], wv, hv))
        self.cam_target = tgt
        # glide
        dx, dy = tgt[0] - self.cam_c[0], tgt[1] - self.cam_c[1]
        if abs(dx) > wv * 0.9 or abs(dy) > hv * 0.9 or self._drag is not None:
            self.cam_c = list(tgt)
        else:
            k = 1.0 - math.exp(-dt * 14.0)
            self.cam_c[0] += dx * k
            self.cam_c[1] += dy * k
            if abs(tgt[0] - self.cam_c[0]) < 0.02 and abs(tgt[1] - self.cam_c[1]) < 0.02:
                self.cam_c = list(tgt)
        self.cam_moving = self.cam_c != tgt
        # screen shake from blasts close by
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 2.5)
        self.cam.set_float(self.cam_c[0] - wv / 2, self.cam_c[1] - hv / 2)
        fx, fy = self.cam.frac()
        mw, mh = gfx.map_cell
        sh = 0.0
        if self.shake > 0 and (getattr(self.app, "settings", None) or {}).get("shake", True):
            import random as _r
            sh = self.shake * mw * 0.35
            self.map_offset = (fx * mw + _r.uniform(-sh, sh), fy * mh + _r.uniform(-sh, sh))
        else:
            self.map_offset = (fx * mw, fy * mh)

    def _on_view(self, pc, wv, hv, margin):
        c = self.cam_c
        return abs(pc[0] - c[0]) <= wv / 2 - margin and abs(pc[1] - c[1]) <= hv / 2 - margin

    # ------------------------------------------------------------ the minimap (F5)
    MINI_W, MINI_H = 40, 16

    def _mini_rect(self):
        return VIEW_W - self.MINI_W - 1, 1, self.MINI_W, self.MINI_H

    def _draw_minimap(self, con):
        """The whole battlefield in a corner: ground you've seen, your men, what you can see of theirs, and
        the part you're looking at."""
        g = self.game
        m = g.map
        x0, y0, W, H = self._mini_rect()
        key = (id(m), g.turn // 30, int(m.explored.sum()) // 50)
        if self._mini is None or self._mini[0] != key:
            bw, bh = -(-m.w // W), -(-m.h // H)
            pw, ph = bw * W, bh * H
            bg = np.zeros((pw, ph, 3), np.float32)
            bg[:m.w, :m.h] = T.BG[m.t] * 1.1 + T.FG[m.t] * 0.15
            ex = np.zeros((pw, ph), np.float32)
            ex[:m.w, :m.h] = m.explored
            cols = (bg * ex[..., None]).reshape(W, bw, H, bh, 3).sum(axis=(1, 3))
            n = ex.reshape(W, bw, H, bh).sum(axis=(1, 3))
            cols = np.where(n[..., None] > 0, cols / np.maximum(n, 1)[..., None], 0)
            seen = n / (bw * bh)
            cols = cols * (0.35 + 0.65 * np.clip(seen, 0, 1))[..., None]
            self._mini = (key, np.clip(cols, 0, 255).astype(np.uint8), bw, bh)
        _, cols, bw, bh = self._mini
        con.draw_frame(x0 - 1, y0 - 1, W + 2, H + 2, clear=False, fg=(120, 110, 80), bg=(8, 8, 8))
        con.rgb["bg"][x0:x0 + W, y0:y0 + H] = cols
        con.rgb["ch"][x0:x0 + W, y0:y0 + H] = ord(" ")
        p = g.player
        for a in g.actors:
            if not a.alive or a.vehicle is not None:
                continue
            if not (a.side == p.side and p.squad is not None and a.squad is p.squad) and \
                    not player_can_see_actor(g, a):
                continue
            cx, cy = x0 + a.x // bw, y0 + a.y // bh
            if x0 <= cx < x0 + W and y0 <= cy < y0 + H:
                ch, col = ("·", (120, 190, 255)) if a.side == p.side else ("x", (255, 90, 70))
                con.print(cx, cy, ch, fg=col, bg=tuple(int(c) for c in cols[cx - x0, cy - y0]))
        for v in g.vehicles:
            if v.dead or (p.vehicle is not v and not m.visible[v.x, v.y]):
                continue
            cx, cy = x0 + v.x // bw, y0 + v.y // bh
            if x0 <= cx < x0 + W and y0 <= cy < y0 + H:
                con.print(cx, cy, "▪", fg=(120, 190, 255) if v.side == p.side else (255, 90, 70),
                          bg=tuple(int(c) for c in cols[cx - x0, cy - y0]))
        for i, o in enumerate(m.objectives if p.has_tool("map") is not None else ()):
            cx, cy = x0 + o.x // bw, y0 + o.y // bh
            if x0 <= cx < x0 + W and y0 <= cy < y0 + H:
                con.print(cx, cy, "ABCDEFGH"[i % 8], fg=(250, 220, 120), bg=tuple(int(c) for c in cols[cx - x0, cy - y0]))
        px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        con.print(x0 + px // bw, y0 + py // bh, "@", fg=(255, 255, 120), bg=(40, 40, 10))
        # the part of the field on screen
        cam = self.cam
        fx0 = cam.fx0 if cam.fx0 is not None else cam.x0
        fy0 = cam.fy0 if cam.fy0 is not None else cam.y0
        gfx = getattr(self.app, "gfx", None)
        wv, hv = self._view_tiles(gfx) if gfx is not None else (VIEW_W, VIEW_H)
        rx0, ry0 = int(max(0, fx0) // bw), int(max(0, fy0) // bh)
        rx1, ry1 = int(min(m.w - 1, fx0 + wv) // bw), int(min(m.h - 1, fy0 + hv) // bh)
        for xx in range(rx0, rx1 + 1):
            for yy in (ry0, ry1):
                if 0 <= xx < W and 0 <= yy < H:
                    con.rgb["fg"][x0 + xx, y0 + yy] = (230, 230, 230)
                    if con.rgb["ch"][x0 + xx, y0 + yy] == ord(" "):
                        con.rgb["ch"][x0 + xx, y0 + yy] = ord("─")
        for yy in range(ry0, ry1 + 1):
            for xx in (rx0, rx1):
                if 0 <= xx < W and 0 <= yy < H:
                    con.rgb["fg"][x0 + xx, y0 + yy] = (230, 230, 230)
                    if con.rgb["ch"][x0 + xx, y0 + yy] in (ord(" "), ord("─")):
                        con.rgb["ch"][x0 + xx, y0 + yy] = ord("│")
        con.print(x0, y0 + H, " F5 hides. Click to look there. ", fg=(150, 140, 110), bg=(8, 8, 8))

    def _minimap_click(self, tx, ty):
        if not self.minimap:
            return False
        x0, y0, W, H = self._mini_rect()
        if not (x0 <= tx < x0 + W and y0 <= ty < y0 + H):
            return False
        m = self.game.map
        bw, bh = -(-m.w // W), -(-m.h // H)
        self.view_center = ((tx - x0 + 0.5) * bw, (ty - y0 + 0.5) * bh)
        p = self.game.player
        self._view_pos = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        return True

    def pan(self, dx_tiles, dy_tiles):
        """Look elsewhere without moving: the view stays there until you move (or press Home)."""
        c = list(self.view_center or self.cam_target or self.cam_c or self._player_center(self.game))
        self.view_center = (c[0] + dx_tiles, c[1] + dy_tiles)

    def _place_cam(self, g):
        """Follow you - or stay where you zoomed or dragged the view, until you walk off its edge."""
        if self.view_center is None:
            self.cam.focus(g)
            return
        cx, cy = self.view_center
        self.cam.x0 = int(round(cx - self.cam.vw / 2))
        self.cam.y0 = int(round(cy - self.cam.vh / 2))
        self.cam._clamp(g)
        p = g.player
        pos = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        if pos != self._view_pos and self._drag is None:
            # you've moved: if you've left the view it comes back to you; near its edge, it scrolls
            self._view_pos = pos
            if (getattr(self.app, "settings", None) or {}).get("auto_center", True) or not self.cam.on_screen(*pos):
                self.view_center = None
                self.cam.focus(g)
                return
            self.cam.ensure_visible(g, pos[0], pos[1], margin=3)
            self.view_center = (self.cam.x0 + self.cam.vw / 2, self.cam.y0 + self.cam.vh / 2)

    def park_view(self):
        """Leave the camera where it is now (after looking around, zooming or dragging)."""
        p = self.game.player
        if self.cam_c is not None:
            self.view_center = tuple(self.cam_target or self.cam_c)
        else:
            self.view_center = (self.cam.x0 + self.cam.vw / 2, self.cam.y0 + self.cam.vh / 2)
        self._view_pos = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)

    def recenter(self):
        self.view_center = None
        self._cam_locked = False
        self.cam_target = list(self._player_center(self.game))

    def _finish_overlay(self):
        """Printing leaves background alpha at 0: make drawn cells opaque (text-only cells half so)."""
        o = self.overlay.rgba
        painted = o["bg"][..., :3].astype(np.int32).sum(axis=-1) > 0
        text = (o["ch"] != 0) & (o["ch"] != 32)
        o["bg"][..., 3] = np.where(painted, 255, np.where(text, 150, 0)).astype(np.uint8)

    def top_console(self, con):
        """Where on-map UI (menus over the battlefield) must be drawn."""
        return self.overlay if self.overlay is not None else con

    def _screen_anchor(self):
        g = self.game
        p = g.player
        x, y = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        return self.cam.to_text(x, y)

    def _render_cursor(self, con, sprites=False):
        g = self.game
        p = g.player
        cx, cy = self.cursor
        ox, oy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        if not sprites:
            mc = self._mapcon if getattr(self, "_mapcon", None) is not None else con
            if self.mode in ("target", "throw", "flare_target", "radio_target", "order_target"):
                draw_line(mc, g, self.cam, ox, oy, cx, cy)
            draw_cursor(mc, self.cam, cx, cy)
        lines, title = self.describe_tile(cx, cy, targeting=self.mode == "target")
        if self.mode == "nearby":
            e = self._nearby_entry()
            if e is not None and e.get("heard") is not None:
                from .nearby import heard_lines
                lines, title = heard_lines(e), "Heard, not seen"
            elif e is not None and e.get("names"):
                lines, title = list(zip(e["names"], e["item_colors"])), "Items here"
        if self.mode == "throw" and self.popups == []:
            it = self.pending and self.pending.get("item")
            if it:
                rng = A.throw_range(p, it)
                d = math.hypot(cx - p.x, cy - p.y)
                lines.append((f"{yards(d)} - {'in reach' if d <= rng else 'too far, it will fall short'}",
                              (180, 220, 150) if d <= rng else (240, 140, 80)))
        if lines and self.cam.on_screen(cx, cy):
            box = draw_tooltip(con, self.cam.to_text(cx, cy), lines, title)
            if self.mode == "target":
                self._sight_picture(con, cx, cy, box)

    def _sight_picture(self, con, cx, cy, box):
        """Through your sights, beside the words: the man, what shows of him over his cover, and the spread of
        your rounds - the circle the chance of a hit comes to (in its band, as the words have it, unless the
        numbers are on)."""
        from . import icons
        from .combat import estimate_hit
        g = self.game
        p = g.player
        w = p.weapon
        e = g.soldier_at.get((cx, cy))
        if not icons.on() or e is None or e is p or w is None or w.t.kind != "gun" or not g.map.visible[cx, cy] \
                or not player_can_see_actor(g, e):
            return
        pr = estimate_hit(g, p, w, e)
        if not self.app.show_numbers:
            pr = next(v for lo, v in ((0.75, 0.85), (0.5, 0.62), (0.3, 0.4), (0.15, 0.22), (0.05, 0.1), (-1, 0.03))
                      if pr > lo)
        m = g.map
        cov = int(max(m.cover_toward(e.x, e.y, p.x, p.y), m.pos_cover[e.x, e.y]))
        from .senses import daylight
        scope = w.t.cat == "sniper" or bool(w.t.get("scope"))
        x, y, bw, bh = box
        sw, sh = 14, 8
        sx = x + bw - sw
        sy = y + bh if y + bh + sh <= VIEW_H else max(0, y - sh)
        con.draw_frame(sx, sy, sw, sh, clear=True, fg=(110, 100, 70), bg=(16, 15, 12))
        icons.pic(sx + 1, sy + 1, sw - 2, sh - 2, f"sight|{2 if e.downed else e.stance}|{cov // 10 * 10}|"
                  f"{int(pr * 100)}|{1 if scope else 0}|{round(daylight(g), 1)}", "over")

    HOVER_DWELL = 0.3

    def hover_looking(self) -> bool:
        """The mouse has come to rest on the battlefield: that's a look."""
        return (self.hover is not None and not self.hover_quiet and not self.popups and self.mode == "normal"
                and self._drag is None and time.monotonic() - self.hover_t >= self.HOVER_DWELL)

    def _render_hover(self, con):
        x, y = self.hover
        g = self.game
        if not self.cam.on_screen(x, y) or self.hover_quiet:
            return
        if not g.map.in_bounds(x, y):
            if self.hover_looking():
                lines, title = self._describe_beyond(x, y)
                if lines:
                    draw_tooltip(con, self.cam.to_text(x, y), lines, title)
            return
        if self.hover_looking():
            if not self.sprites():
                mc = self._mapcon if getattr(self, "_mapcon", None) is not None else con
                draw_cursor(mc, self.cam, x, y)
            lines, title = self.describe_tile(x, y)
            if lines:
                draw_tooltip(con, self.cam.to_text(x, y), lines, title)
            return
        if not g.map.explored[x, y]:
            return
        lines, title = self.describe_tile(x, y, brief=True)
        if lines and (title or len(lines) > 1):
            draw_tooltip(con, self.cam.to_text(x, y), lines, title)

    def _describe_beyond(self, x, y):
        """Looking across the edge into the next sector."""
        g = self.game
        m = g.map
        ex, ey = max(0, min(m.w - 1, x)), max(0, min(m.h - 1, y))
        if not m.explored[ex, ey]:
            return [], None
        ndx = -1 if x < 0 else 1 if x >= m.w else 0
        ndy = -1 if y < 0 else 1 if y >= m.h else 0
        n = g.strategic.at(g.sector.x + ndx, g.sector.y + ndy)
        if n is None:
            return [], None
        from .strategic import BIOME_NAME
        from .constants import COMPASS as _C
        lines = [(f"The next stretch of ground, to the {_C.get((ndx, ndy), '')}: "
                  f"{BIOME_NAME.get(n.biome, n.biome)}.", UI_TEXT)]
        if g.player.has_tool("map") or n.visited:
            held = "ours" if n.control == g.player.side else "the enemy's" if n.control else "nobody's"
            lines.append((f"{n.name} - {held}, by the map.", UI_DIM))
        at = g.strategic.attack_on(n.x, n.y) if hasattr(g.strategic, "attack_on") else None
        if at is not None:
            who = "our attack" if at["side"] == g.player.side else "an enemy attack"
            lines.append((f"Smoke, gun flashes, the rattle of fire: {who} is going in over there.", (250, 190, 120)))
        lines.append(("Walk off the edge to go there.", UI_DIM))
        return lines, None

    def describe_tile(self, x, y, targeting=False, brief=False):
        g = self.game
        m = g.map
        p = g.player
        lines = []
        title = None
        if not m.in_bounds(x, y):
            return lines, title
        vis = m.visible[x, y]
        if not m.explored[x, y]:
            return [("You haven't seen that ground.", UI_DIM)], None
        a = g.soldier_at.get((x, y))
        v = g.vehicle_at.get((x, y))
        ox, oy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        d = math.hypot(x - ox, y - oy)
        if a is not None and vis and player_can_see_actor(g, a):
            if a is p:
                title = "You"
            else:
                friend = a.side == p.side
                far = d > 60 and not g.player_binoculars
                title = (a.full_name if friend and a.squad is p.squad else
                         f"{NATIONS[a.nation]['adj']} {'soldier' if far else a.role_name.lower()}")
                col = FRIEND_COLOR if friend else ENEMY_COLOR
                st = {0: "standing", 1: "crouching", 2: "prone"}[a.stance]
                if a.state == "surrendered":
                    st = "hands raised"
                elif a.downed:
                    st = "down, wounded"
                where = m.describe(x, y)
                lines.append((f"{st} in {where}", col))
                if a.weapon is not None and (d < 25 or g.player_binoculars):
                    lines.append((f"armed with {'a ' if not a.weapon.t.name[0] in 'AEIOU' else 'an '}{a.weapon.t.name}", UI_TEXT))
                job = a.ai.get("support_job")
                if friend and job and job["target"] == p.id and job["until"] > g.turn:
                    lines.append(("Bringing ammunition to you." if job["kind"] == "ammo" else
                                  "On the way to give you first aid.", (150, 225, 170)))
                if a.has_tool("brassard") and (d < 40 or g.player_binoculars):
                    lines.append(("a Red Cross armband" + ("" if a.weapon is not None and a.weapon.t.kind == "gun"
                                                           else " - and no weapon"), (230, 120, 120)))
                worst = min(a.body.hp[k] / a.body.max[k] for k in a.body.hp)
                if worst < 0.95 and d < 20:
                    lines.append(("wounded" if worst > 0.4 else "badly wounded", (240, 140, 80)))
                if a.suppression > 50 and not friend:
                    lines.append(("keeping his head down", UI_DIM))
                if getattr(a, "z", 0) > 0:
                    from .actions import floor_word
                    lines.append((f"up on {floor_word(g, a)}", (230, 200, 140)))
                cond = []
                if a.moved_turn >= g.turn - 1 and a.ai.get("pace_now") in ("run", "sprint"):
                    cond.append(a.ai["pace_now"] + "ing" if a.ai["pace_now"] == "sprint" else "running")
                if getattr(a, "stamina", 100) < 20:
                    cond.append("gasping for breath")
                elif getattr(a, "fatigue", 0) > 70:
                    cond.append("worn out")
                t = getattr(a.body, "temp", 37.0)
                if t < 34.5:
                    cond.append("blue with cold")
                elif t < 35.8:
                    cond.append("shivering")
                elif t > 39.3:
                    cond.append("reeling in the heat")
                if getattr(a.body, "wet", 0) > 60:
                    cond.append("soaked")
                if cond and d < 30:
                    lines.append((", ".join(cond), (190, 200, 220)))
                if targeting and not friend and p.weapon is not None and p.weapon.t.kind == "gun":
                    pr = estimate_hit(g, p, p.weapon, a)
                    word, wcol = describe_chance(pr)
                    lines.append((f"{yards(d)}: {word}", wcol))
                    if self.app.show_numbers:
                        lines.append((f"~{int(pr * 100)}% per shot", UI_DIM))
                    lines += self._aim_lines(p.weapon, a, x, y)
                    cov = m.cover_toward(x, y, p.x, p.y)
                    if cov >= 70:
                        lines.append(("behind good cover", (230, 170, 90)))
                    elif cov >= 35:
                        lines.append(("partly covered", (220, 200, 110)))
        elif v is not None and (vis or p.vehicle is v):
            friend = v.side == p.side
            far = d > 70 and not g.player_binoculars and p.vehicle is not v
            kind = {"tank": "tank", "ltank": "light tank", "td": "tank destroyer", "spg": "self-propelled gun",
                    "halftrack": "half-track", "truck": "truck", "car": "car", "armcar": "armoured car",
                    "atgun": "gun", "aagun": "anti-aircraft gun", "fieldgun": "field gun"}.get(v.vt.vtype, "vehicle")
            title = ("Friendly " if friend else "Enemy ") + (kind if far else v.vt.name)
            lines += self._vehicle_state_lines(v, friend, d)
            if friend and not v.dead and d <= 8:
                from . import maintenance as MT
                wl = MT.work_left(v)
                if wl is not None:
                    lines.append((f"the crew are at work on {MT.REPAIR_WORD[wl[0]]} (about {wl[1]} min)", (220, 200, 140)))
                needs = MT.needs_words(v)
                if needs:
                    lines.append(("needs " + ", ".join(needs), (230, 170, 110)))
                if MT.is_supply_truck(v):
                    lines.append((f"ammunition truck: {v.ai.get('cargo', 0)} rounds aboard", (200, 220, 150)))
                if p.vehicle is None and v.near(p.x, p.y) <= 1:
                    lines.append(("e: get in   right-click: more", UI_DIM))
            if targeting and not friend:
                rel = (__import__("fow.gamemap", fromlist=["octant"]).octant(ox - v.x, oy - v.y) - v.facing) % 8
                face = "its front" if rel in (0, 1, 7) else "its side" if rel in (2, 6) else "its rear"
                lines.append((f"{yards(d)}, you're looking at {face}", UI_TEXT))
                w = p.weapon
                if p.vehicle is None and w is not None and w.t.kind == "gun":
                    from .ai import can_hurt_vehicle
                    if not can_hurt_vehicle(p, v):
                        lines.append(("Your rounds will just bounce off.", (240, 140, 80)))
                    elif w.t.cat not in ("at_launcher", "at_disposable", "at_rifle") and max(v.vt.armor) <= 12:
                        lines.append(("Thin skin: your rounds will go through it.", (200, 220, 150)))
        else:
            title = None
            tile = m.tile(x, y) if vis else T.DEFS[int(m.memory()[x, y])]       # (remembered: as it was)
            desc = m.describe(x, y) if vis else tile.name + " (remembered)"
            if tile.key.startswith("ac_"):
                from .parked import describe as ac_describe
                desc = ac_describe(m, x, y) or desc
            lines.append((desc[0].upper() + desc[1:], UI_TEXT if vis else UI_DIM))
            from .going import words as going_words
            gw = going_words(g, x, y, self.app.show_numbers, tid=None if vis else tile.id)
            if gw is not None and not brief:
                lines.append(gw)
            tdesc = tile.desc
            if tdesc and not brief:
                import textwrap
                lines += [(ln, UI_DIM) for ln in textwrap.wrap(tdesc, 58)[:4]]
            from .relief import words as height_words
            hw = height_words(g, x, y)
            if hw:
                lines.append((hw[0].upper() + hw[1:] + ".", UI_DIM))
        if vis:
            items = m.items_at(x, y)
            if items:
                names = []
                for it in items[:4]:
                    n = it.name
                    if it.data and it.data.get("live") is not None:
                        n = "LIVE " + n
                    names.append(n)
                lines.append(("Here: " + ", ".join(names) + ("..." if len(items) > 4 else ""), (200, 190, 150)))
            mn = m.mines.get((x, y))
            if mn is not None and p.side in mn.known:
                lines.append(("A mine is buried here.", (255, 80, 80)))
        if targeting and not lines:
            lines.append((yards(d), UI_TEXT))
        return lines, title

    # ================================================================== animation / ticking
    def realtime_enabled(self):
        return bool((getattr(self.app, "settings", None) or {}).get("realtime"))

    def reset_realtime_clock(self):
        self._rt_last = time.monotonic()
        self._rt_elapsed = 0.0

    def realtime_paused(self):
        states = getattr(self.app, "states", [])
        return (not getattr(self.app, "focused", True) or bool(states and states[-1] is not self) or
                bool(self.popups) or self.inv_screen is not None or self.mode == "nearby" or
                bool(self.game.__dict__.get("succession_pending")) or self.game.game_over)

    def realtime_busy(self):
        return self.realtime_enabled() and self.game.player.moves <= 0

    def realtime_label(self):
        if not self.realtime_enabled():
            return None
        pace = (getattr(self.app, "settings", None) or {}).get("realtime_pace", "deliberate")
        speed = {"normal": "1x", "deliberate": "0.5x", "slow": "0.25x"}.get(pace, "0.5x")
        if self.realtime_paused():
            return f"REAL TIME {speed} - PAUSED"
        p = self.game.player
        if p.moves <= 0:
            left = max(1, math.ceil((1 - p.moves) / max(1, p.speed())))
            return f"REAL TIME {speed} - busy {left}s"
        return f"REAL TIME {speed} - ready (F6)"

    def _realtime_tick(self, now=None):
        """One shared clock; no catch-up burst after menus, focus loss or a stalled frame."""
        now = time.monotonic() if now is None else now
        last = self._rt_last
        self._rt_last = now
        if self.realtime_paused():
            self._rt_elapsed = 0.0
            return False
        pace = (getattr(self.app, "settings", None) or {}).get("realtime_pace", "deliberate")
        interval = {"normal": 1.0, "deliberate": 2.0, "slow": 4.0}.get(pace, 2.0)
        elapsed = max(0.0, now - last)
        if elapsed > max(5.0, interval * 2):
            self._rt_elapsed = 0.0
            return False
        self._rt_elapsed += elapsed
        if self._rt_elapsed < interval:
            return False
        self._rt_elapsed %= interval          # at most one simulation second per frame, never a burst
        g = self.game
        before = sum(g.player.body.hp.values())
        g.world_turn()
        g.player_fov()
        self.flash_red = sum(g.player.body.hp.values()) < before
        if g.effects:
            self._start_anim()
        self.check_over()
        self._maybe_autosave()
        return True

    def cmd_realtime(self):
        st = getattr(self.app, "settings", None)
        if st is None:
            return
        self.stop_auto()
        st["realtime"] = not st.get("realtime", False)
        if hasattr(st, "save"):
            st.save()
        self.reset_realtime_clock()
        chart_open = any(state.__class__.__name__ == "SkySeaState" for state in getattr(self.app, "states", []))
        if not st["realtime"] and not chart_open and self.game.map is not None and self.game.player.moves <= 0:
            self.game.player_done()           # switching clocks cannot erase an action's remaining cost
            self.check_over()
        self.game.msg("Real time on: everyone shares the clock. Menus pause it. F6: turn based." if st["realtime"]
                      else "Turn based time. F6: real time.", "system")

    def wants_tick(self):
        g = self.game
        if g.__dict__.get("identity_check") and not g.game_over and g.player.body.conscious and \
                not self.popups and self.inv_screen is None:
            return True                               # closing the view does not dismiss a sentry's questions
        if self.realtime_enabled() and not g.game_over and g.map is not None:
            return True
        if g.__dict__.get("autopilot") and not g.game_over and g.map is not None:
            return True                               # (your soldier's getting on with it: the world must turn)
        return self.anim > 0 or self.travel_path or self.auto_wait > 0 or self.running or \
            self.__dict__.get("digging") or self.__dict__.get("ff_until") or \
            (not self.game.player.body.conscious and not self.game.game_over) or self.cam_moving or \
            self.shake > 0 or self._edge_scrolling()

    def _edge_scrolling(self):
        if not (getattr(self.app, "settings", None) or {}).get("edge_scroll"):
            return False
        mx, my = getattr(self, "mouse_txt", (-1, -1))
        return 0 <= mx < VIEW_W and 0 <= my < VIEW_H and (mx < 1.5 or mx > VIEW_W - 1.5 or my < 1 or
                                                          my > VIEW_H - 1)

    def _anim_speed(self):
        st = getattr(self.app, "settings", None) or {}
        return st.get("anim_speed", "fast")

    def _start_anim(self):
        """Play back the shots and blasts since you last acted.  Slowed down, they play second by
        second in the order they happened; fast, all at once."""
        g = self.game
        self.anim_groups = []
        if self._anim_speed() in ("slow", "very slow"):
            by = {}
            for e in g.effects:
                by.setdefault(e.get("t", 0), []).append(e)
            groups = [by[k] for k in sorted(by)]
            if len(groups) > 12:                     # a long wait: don't replay a minute of war
                n = -(-len(groups) // 12)
                groups = [sum(groups[i:i + n], []) for i in range(0, len(groups), n)]
            g.effects = groups[0]
            self.anim_groups = groups[1:]
        self.anim = 4
        self.anim_next = 0

    def tick(self):
        g = self.game
        from .identity import present as papers_check
        if papers_check(self):
            return
        now = time.time()
        if g.map is None:
            return
        if self.realtime_enabled() and not getattr(self.app, "focused", True):
            self.reset_realtime_clock()
            return
        timed = self.realtime_enabled() and not self.auto_wait and not self.__dict__.get("ff_until")
        if timed:
            self._realtime_tick()
            if self.realtime_paused() or g.player.moves <= 0 or not g.player.body.conscious or \
                    g.__dict__.get("autopilot") or g.game_over:
                return
        else:
            self.reset_realtime_clock()
        if now < self.anim_next:
            return
        if self.anim > 0:
            from .settings import ANIM_FRAME
            self.anim -= 1
            self.anim_next = now + ANIM_FRAME.get(self._anim_speed(), 0.035)
            if self.anim == 0:
                if getattr(self, "anim_groups", None):
                    g.effects = self.anim_groups.pop(0)
                    self.anim = 4
                    return
                g.effects = []
                self.flash_red = False
            return
        p = g.player
        if g.__dict__.get("succession_pending"):
            if not self.popups:
                self._succession_menu()
            return
        if self.auto_wait > 0 and (self.__dict__.get("wait") or {}).get("kind") == "forced":
            self._wait_tick()
            self.anim_next = now + 0.005
            return
        if g.__dict__.get("autopilot") and not g.game_over:
            from .succession import set_autopilot
            if p.state != "ok" or not p.alive or g.__dict__.get("domain", "land") != "land":
                set_autopilot(g, False)
            else:
                # your soldier acts on his own, as every other man does - second by second; with nobody in
                # sight, as many seconds a frame as the machine can simulate (Options: quiet time goes quickly)
                deadline = time.perf_counter() + (self.WAIT_BUDGET if self._fast_quiet() else 0.0)
                while True:
                    g.world_turn()
                    g.player_fov()
                    self.check_over()
                    if g.game_over or not g.__dict__.get("autopilot") or time.perf_counter() >= deadline or \
                            not self._fast_quiet():
                        break
                    self._skip_replay()
                if g.effects:
                    self._start_anim()
                self.anim_next = now + 0.03
                return
        if not p.body.conscious and not g.game_over:
            for _ in range(5):
                if p.body.conscious or g.game_over:
                    break
                g.world_turn()
            g.player_fov()
            self.anim_next = now + 0.05
            self.check_over()
            return
        if self.travel_path:
            deadline = time.perf_counter() + (self.WAIT_BUDGET if self._fast_quiet() else 0.0)
            while True:
                self._travel_step(now)
                sts = getattr(self.app, "states", None)
                if not self.travel_path or g.game_over or time.perf_counter() >= deadline or \
                        not self._fast_quiet() or self.popups or (sts and sts[-1] is not self):
                    return
                self._skip_replay()
        if self.running:
            if self.interrupted():
                self.stop_auto()
                return
            dx, dy = self.running
            m = g.map
            nx, ny = p.x + dx, p.y + dy
            mn = m.mines.get((nx, ny)) if m.in_bounds(nx, ny) else None
            if not m.in_bounds(nx, ny) or not m.walk[nx, ny] or (nx, ny) in g.soldier_at or \
                    (mn is not None and p.side in mn.known):
                self.stop_auto()
                return
            if not self.do_move(dx, dy, auto=True):
                self.stop_auto()
            self.anim_next = now + 0.02
            return
        if self.__dict__.get("ff_until"):
            self._ff_tick()
            self.anim_next = now + 0.01
            return
        if self.__dict__.get("digging"):
            if self.interrupted():
                self.stop_auto("You stop digging.")
                return
            c = A.dig(g, p)
            if c is None:
                self.digging = False
                return
            self.act(c)
            if T.DEFS[int(g.map.t[p.x, p.y])].key in ("foxhole", "trench_snow"):
                self.digging = False
            self.anim_next = now + 0.01
            return
        if self.auto_wait > 0:
            self._wait_tick()
            self.anim_next = now + 0.005

    def _travel_step(self, now):
        """One step of a walk-to (the route replanned where what you guessed at turns out otherwise)."""
        g = self.game
        p = g.player
        if self.travel_path:
            following = self.__dict__.get("_following_order")
            if following is not None:
                from .orders import execution_signature
                if following != execution_signature(g):
                    self.stop_auto("Your orders have changed. Enter follows the current instruction.")
                    return
            if self.interrupted():
                self.stop_auto("You stop.")
                return
            m = g.map
            nx0, ny0 = self.travel_path[0]
            shut = not m.walk[nx0, ny0] and not T.DOOR[m.t[nx0, ny0]] and m.explored[nx0, ny0]
            known = int(m.explored.sum())
            if shut or (known != self.__dict__.get("travel_known", known) and
                        any(m.explored[q] for q in self.__dict__.get("travel_blind", ()))):
                # what you guessed at, you've now seen: plan again from here
                if not self._replan_route():
                    self.stop_auto("There's no way through that you can find.")
                    return
                self.travel_known = known
                if not self.travel_path:
                    self.travel_dest = None
                    then = self.__dict__.get("travel_then")
                    self.travel_then = None
                    if then is not None:
                        then()
                    return
            nx, ny = self.travel_path.pop(0)
            dx, dy = nx - p.x, ny - p.y
            if (g.soldier_at.get((nx, ny)) is not None and g.soldier_at[(nx, ny)].side != p.side and
                    not g.soldier_at[(nx, ny)].ai.get("civilian")):
                self.stop_auto()
                return
            if max(abs(dx), abs(dy)) != 1 or (nx, ny) in g.vehicle_at:
                # off the route (a door that took a moment to open, a man in the way, a vehicle parked
                # across it): find the way again from here
                if not self._replan_route() or not self.travel_path:
                    self.stop_auto()
                    return
                nx, ny = self.travel_path.pop(0)
                dx, dy = nx - p.x, ny - p.y
                if max(abs(dx), abs(dy)) != 1:
                    self.stop_auto()
                    return
            before = (p.x, p.y)
            ok = self.do_move(dx, dy, auto=True)
            if not ok:
                self.stop_auto()
            elif (p.x, p.y) == before and (p.x, p.y) != (nx, ny) and self.travel_path is not None:
                # you didn't get there (you opened the door): the same step again, next
                self.travel_path.insert(0, (nx, ny))
                self.travel_retry = self.__dict__.get("travel_retry", 0) + 1
                if self.travel_retry > 4 and not self._replan_route():
                    self.stop_auto()
            else:
                self.travel_retry = 0
            if not self.travel_path:
                self.travel_dest = None
                then = self.__dict__.get("travel_then")
                self.travel_then = None
                if ok and then is not None:
                    then()
            self.anim_next = now + 0.02

    # ------------------------------------------------------------ time going by (z, Z; walking; autopilot)
    WAIT_BUDGET = 0.1         # seconds of simulation between frames when time is going quickly

    def _fast_quiet(self) -> bool:
        """Nobody in sight, nothing coming at you: the seconds may go by as fast as they can be simulated."""
        st = getattr(self.app, "settings", None) or {}
        if st.get("realtime") or not st.get("fast_quiet", True):
            return False
        g = self.game
        p = g.player
        if p.suppression > 5 or g.turn - p.hit_turn < 20 or not p.body.conscious:
            return False
        if any(a.side != p.side and not a.ai.get("civilian") and a.alive and player_can_see_actor(g, a) for a in g.actors):
            return False
        return not any(v.side != p.side and v.active and g.map.in_bounds(v.x, v.y) and g.map.visible[v.x, v.y]
                       for v in g.vehicles)

    def _skip_replay(self):
        """Seconds that went by quickly aren't played back one by one: the shots and bursts far off, and the
        shouting, happened - they're in the log - but aren't replayed or voiced."""
        g = self.game
        self.anim = 0
        self.anim_groups = []
        g.effects = []
        self.shake = 0.0
        ev = g.__dict__.get("audio_events")
        if ev:
            g.audio_events = [e for e in ev if e[0] != "voice"]

    def _orders_sig(self):
        """What orders you hold, and when each was given: a new one changes it."""
        from .orders import book
        try:
            return frozenset((e.get("key"), e.get("issued")) for e in book(self.game))
        except Exception:
            return frozenset()

    def begin_wait(self, kind, secs, quick=False):
        """Wait (z: a minute; Z: the menu): second by second, every second simulated, as fast as the machine
        can manage, stopping for anything that matters."""
        g = self.game
        self.stop_auto()
        self.wait = dict(kind=kind, start=g.turn, secs=int(secs), t0=time.perf_counter(), sig=self._orders_sig(),
                         quick=quick)
        self.auto_wait = int(secs)
        self.mark_interrupt()
        if not quick:
            g.msg({"event": "You settle down to wait. (any key stops)",
                   "dawn": "You settle down to wait for the light. (any key stops)",
                   "dark": "You settle down to wait for dark. (any key stops)",
                   "orders": "You wait for orders. (any key stops)"}.get(kind, "You wait. (any key stops)"), "info")
        else:
            g.msg("You wait, watching.", "info")

    def _wait_tick(self):
        g = self.game
        p = g.player
        deadline = time.perf_counter() + self.WAIT_BUDGET
        w0 = self.wait
        forced = w0 is not None and w0["kind"] == "forced"
        while self.auto_wait > 0:
            if w0 is not None:
                self.auto_wait = max(0, w0["start"] + w0["secs"] - g.turn)       # (the clock decides, not the count)
                if self.auto_wait <= 0:
                    break
            self.auto_wait -= 1
            if forced:
                # One simulation second, even if wounded, asleep, or stunned. Drawing and
                # replaying every shot is what makes long waits expensive.
                p.moves = 0
                g.world_turn()
                self.check_over()
            else:
                self.act(100)
            sts = getattr(self.app, "states", None)
            if g.game_over or g.__dict__.get("succession_pending") or (sts and sts[-1] is not self) or \
                    (not forced and (not p.body.conscious or self.popups)):
                self.auto_wait = 0
                self.wait = None
                return
            why = self._wait_stop()
            if why is not None:
                self._end_wait(why)
                return
            if self.auto_wait <= 0 or time.perf_counter() >= deadline:
                break
            self._skip_replay()
        if forced:
            self._skip_replay()
            g.player_fov()
        if self.auto_wait <= 0:
            self._end_wait("")

    def _wait_stop(self):
        """Why the wait ends now: a message (\"\" for 'what you waited for'), or None to go on."""
        g = self.game
        if (self.wait or {}).get("kind") == "forced":
            return None
        if self.interrupted():
            return "Something catches your attention."
        w = self.wait
        if w is None:
            return None
        if w["kind"] == "dawn" and not g.is_night():
            return "It's getting light."
        if w["kind"] == "dark" and g.is_night():
            return "It's dark."
        if (g.turn - w["start"]) % 5 == 0 and self._orders_sig() != w["sig"]:
            return "New orders." if w["kind"] != "orders" else ""
        return None

    def _end_wait(self, why):
        g = self.game
        w = self.wait
        self.wait = None
        self.auto_wait = 0
        if w is None:
            if why:
                g.msg(why, "info")
            return
        span = g.turn - w["start"]
        if w.get("quick") and not why:
            return                              # (a minute, as asked: nothing to say)
        text = self.span_words(span)
        g.msg(f"{why} {text}".strip() if why else text, "info")
        g.update_orders(force=True)

    def span_words(self, secs) -> str:
        """How long that was - to the minute with a watch; without one, a feeling."""
        if self.game.player.has_tool("watch") is not None:
            h, mnt = secs // 3600, (secs % 3600) // 60
            if not h and not mnt:
                return f"{secs} seconds go by."
            if not h:
                return f"{mnt} minute{'s' if mnt != 1 else ''} go{'es' if mnt == 1 else ''} by."
            return f"{h} hour{'s' if h != 1 else ''} {mnt} minute{'s' if mnt != 1 else ''} go by."
        return ("A moment passes." if secs < 90 else "A few minutes pass." if secs < 600 else
                "Time passes." if secs < 2400 else "A long while passes." if secs < 7200 else "Hours pass.")

    def wait_banner(self) -> str:
        """WAITING, what for, how long so far (with a watch), and how much faster than life it's going."""
        g = self.game
        w = self.wait
        what = {"event": "until something happens", "dawn": "for first light", "dark": "for dark",
                "orders": "for orders", "forced": "through events"}.get(w["kind"], "")
        gone = g.turn - w["start"]
        bits = ["WAITING" + (f" {what}" if what else "")]
        if g.player.has_tool("watch") is not None:
            h, mnt = gone // 3600, (gone % 3600) // 60
            if w["kind"] in ("time", "forced"):
                th, tm = w["secs"] // 3600, (w["secs"] % 3600) // 60
                bits.append(f"{h}:{mnt:02d} of {th}:{tm:02d}")
            else:
                bits.append(f"{h}:{mnt:02d} gone")
        wall = time.perf_counter() - w["t0"]
        if wall > 0.5 and gone > 5:
            bits.append(f"time x{gone / wall:.0f}")
        bits.append("any key stops")
        return "  -  ".join(bits)

    def cmd_wait(self):
        """Z: how long to wait - to the minute with a watch; without one, by feel and by the sky."""
        g = self.game
        p = g.player
        watch = p.has_tool("watch") is not None
        opts = [("Until something happens (up to three hours)", ("event", 3 * 3600), None, True)]
        spans = ((("5 minutes", 300), ("15 minutes", 900), ("30 minutes", 1800), ("An hour", 3600),
                  ("Three hours", 3 * 3600)) if watch else
                 (("A few minutes", 300), ("A while", 1200), ("A good while", 3600), ("Hours", 3 * 3600)))
        opts += [(lab, ("time", secs), None, True) for lab, secs in spans]
        if g.is_night():
            opts.append(("Until first light", ("dawn", 16 * 3600), None, True))
        else:
            opts.append(("Until dark", ("dark", 18 * 3600), None, True))
        opts.append(("Until there are new orders", ("orders", 6 * 3600), None, True))
        opts.append(("Pass time regardless of events...", "forced", None, True))
        if g.__dict__.get("domain") == "aboard" and (g.aboard or {}).get("kind") == "ship" and self._quiet_aboard():
            opts.append(("Ship's routine: until needed", "ship", None, True))
        self.open_popup(Popup("Wait", opts, self._screen_anchor(),
                              footer="ordinary waits stop for danger; any key cancels"), self._choose_wait)

    def _choose_wait(self, choice):
        if choice == "forced":
            spans = (("15 minutes", 900), ("An hour", 3600), ("Six hours", 21600),
                     ("Twelve hours", 43200), ("A day", 86400))
            self.open_popup(Popup("Pass time through events", [(label, seconds, None, True)
                            for label, seconds in spans], self._screen_anchor(),
                            footer="Combat, wounds and orders continue. Stops at death or any key."),
                            lambda seconds: seconds and self.begin_wait("forced", seconds))
        elif choice == "ship":
            self.fast_forward()
        elif choice:
            self.begin_wait(*choice)

    def mark_interrupt(self):
        g = self.game
        p = g.player
        seen = {a.id for a in g.actors if a.side != p.side and not a.ai.get("civilian") and a.alive and player_can_see_actor(g, a)}
        seen |= {v.id for v in g.vehicles if v.side != p.side and v.active and g.map.visible[v.x, v.y]}
        self.interrupt_state = dict(seen=seen, hit=p.hit_turn, sup=p.suppression, msgs=g.msg_total,
                                    blood=p.body.blood)

    def interrupted(self) -> bool:
        g = self.game
        p = g.player
        st = self.interrupt_state or {}
        seen = {a.id for a in g.actors if a.side != p.side and not a.ai.get("civilian") and a.alive and player_can_see_actor(g, a)}
        seen |= {v.id for v in g.vehicles if v.side != p.side and v.active and g.map.visible[v.x, v.y]}
        if seen - st.get("seen", set()):
            g.msg("You spot movement!" if len(seen) else "", "warn")
            return True
        if p.hit_turn > st.get("hit", -99):
            return True
        if p.suppression > st.get("sup", 0) + 12:
            return True
        # important messages
        new = g.msg_total - st.get("msgs", g.msg_total)
        if new > 0:
            for mm in list(g.messages)[-min(new, len(g.messages)):]:
                if mm.cat in ("death", "hurt", "warn"):
                    return True
        return False

    def stop_auto(self, msg=None):
        self._following_order = None
        self.travel_path = None
        self.travel_dest = None
        self.travel_then = None
        self.running = None
        self.auto_wait = 0
        self.digging = False
        w = self.__dict__.get("wait")
        if w is not None:
            self.wait = None
            if not w.get("quick") and self.game.turn > w["start"]:
                self.game.msg("You stop waiting. " + self.span_words(self.game.turn - w["start"]), "info")
        if msg:
            self.game.msg(msg, "info")

    # ================================================================== core action plumbing
    def act(self, cost):
        """Spend moves and let the world run."""
        g = self.game
        p = g.player
        if cost is None or cost <= 0:
            return False
        if g.__dict__.get("autopilot"):
            g.msg("Your soldier's on autopilot. (A to take over)", "info")
            return False
        self.flash_red = False
        self.log_scroll = 0
        hp_before = sum(p.body.hp.values())
        p.moves -= cost
        if not self.realtime_enabled() or self.realtime_paused() or self.__dict__.get("_rt_modal_action") or \
                self.wait is not None or self.auto_wait > 0:
            g.player_done()                   # a menu action still charges its full simulation time
            self.reset_realtime_clock()
        if sum(p.body.hp.values()) < hp_before:
            self.flash_red = True
        if g.effects:
            px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
            near = [e for e in g.effects if e.get("kind") == "explosion" and e.get("r", 0) >= 1]
            if near:
                d = min(math.hypot(e["x"] - px, e["y"] - py) for e in near)
                if d < 16:
                    self.shake = min(1.0, self.shake + (1 - d / 16) * (0.5 + 0.1 * max(e.get("r", 1) for e in near)))
            self._start_anim()
        p.aim_turns = p.aim_turns if cost == 100 and self.mode == "target" else p.aim_turns
        g.player_binoculars = False
        self.check_over()
        self._maybe_autosave()
        from .identity import present as papers_check
        papers_check(self)
        return True

    def _maybe_autosave(self):
        st = getattr(self.app, "settings", None) or {}
        g = self.game
        if not st.get("autosave", True) or g.game_over or time.time() - self.__dict__.get("_autosaved", 0) < 300:
            return
        if self.travel_path or self.running or self.auto_wait:
            return                       # not in the middle of something
        self._autosaved = time.time()
        try:
            g.save()
        except Exception:
            pass

    def check_over(self):
        g = self.game
        pw = getattr(g, "pow", None)
        if pw is not None and pw.get("stage") == "camp" and not g.game_over and g.player.alive:
            from .ui import POWState
            if not isinstance(self.app.states[-1], POWState):
                self.stop_auto()
                self.popups = []
                self.app.push(POWState(self.app, g, self))
            return
        if g.game_over:
            self.stop_auto()
            self.popups = []
            self.mode = "normal"
            from .ui import GameOverState
            self.app.replace(GameOverState(self.app, g))

    # ================================================================== input
    def on_key(self, key: Key):
        g = self.game
        p = g.player
        if g.map is None:
            return                                    # (between worlds: the sky view or the camp is coming)
        if key.sym == E.KeySym.F6 and not self.popups and self.inv_screen is None:
            return self.cmd_realtime()
        if self.anim > 0:
            self.anim = 0
            self.anim_groups = []
            g.effects = []
            self.flash_red = False
        if self.travel_path or self.running or self.auto_wait or self.__dict__.get("digging") or \
                self.__dict__.get("ff_until"):
            if self.__dict__.get("ff_until"):
                self.ff_until = None
                if g.__dict__.get("aboard"):
                    g.aboard["sleeping"] = False
                g.msg("You stir.", "info")
            self.stop_auto()
            return
        if g.__dict__.get("succession_pending") and self.popups:
            return self.popup_key(key)             # (who carries on: the dead man can still choose)
        if self.realtime_busy() and key.sym != E.KeySym.ESCAPE:
            inspecting = not self.popups and self.inv_screen is None and (key.char in ("?", "m", "x", ";", "T", "@", "P", "+", "-", "=") or \
                key.sym in (E.KeySym.F1, E.KeySym.HOME, E.KeySym.F5) or \
                (self.mode in ("look", "target") and key.move() is not None))
            if not inspecting:
                return                      # the existing action must finish before another starts
        if not p.body.conscious:
            if key.sym == E.KeySym.ESCAPE and not self.popups:
                from .ui import EscMenuState
                self.app.push(EscMenuState(self.app, self))     # (out cold, you can still save and quit)
            return
        if g.__dict__.get("autopilot") and not self.popups and self.inv_screen is None and self.mode == "normal":
            # on autopilot: A or Esc takes him back; looking, the map, the books and the help still work
            if key.char == "A" or key.sym == E.KeySym.ESCAPE:
                return self.cmd_autopilot()
            if key.char not in ("?", "m", "x", ";", "T", "@", "P", "V", "G", "C", "+", "-", "=", "X") and \
                    key.sym not in (E.KeySym.F1, E.KeySym.F2, E.KeySym.F3, E.KeySym.F4, E.KeySym.F5, E.KeySym.HOME):
                g.msg("Your soldier's on autopilot. (A to take over)", "info")
                return
        if self.inv_screen is not None:
            return self.inv_screen.on_key(key)
        if self.popups:
            return self.popup_key(key)
        if self.mode != "normal":
            return self.mode_key(key)
        self.mark_interrupt()
        self.hover_quiet = True
        if key.sym == E.KeySym.HOME:
            return self.recenter()
        if key.sym == E.KeySym.F5:
            self.minimap = not self.minimap
            return
        if key.sym == E.KeySym.F1:
            return self.cmd_help()
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER):
            return self.cmd_do_order()
        if g.__dict__.get("domain") == "aboard" and (g.aboard or {}).get("kind") == "ship":
            from . import aboard as AB
            if key.char in ("<", ">"):
                return AB.climb(self, "up" if key.char == "<" else "down")
            if key.char == "z" and self._quiet_aboard():
                return self.fast_forward()
        elif key.char in ("<", ">") and p.vehicle is None:
            # the stairs, or the cellar trapdoor
            c = A.climb(g, p, 1 if key.char == "<" else -1)
            if c is None:
                g.msg("There are no stairs here." if m_tile(g, p) not in ("stairs", "trapdoor") else
                      "That's as far as these go.", "info")
                return
            g.player_fov()
            return self.act(c)
        if getattr(key, "ctrl", False) and key.move():
            gfx = getattr(self.app, "gfx", None)
            wv, hv = self._view_tiles(gfx) if gfx is not None else (VIEW_W, VIEW_H)
            dx, dy = key.move()
            return self.pan(dx * wv * 0.25, dy * hv * 0.25)
        mv = key.move()
        if mv:
            if key.is_run():
                if self.safe_mode_blocks(("run",) + tuple(mv)):
                    return
                self.running = mv
                return
            return self.do_move(*mv)
        if key.sym in WAIT_KEYS or key.char == ".":
            return self.act(100)
        if key.sym == E.KeySym.ESCAPE:
            from .ui import EscMenuState
            self.app.push(EscMenuState(self.app, self))
            return
        c = key.char
        if c is None:
            if key.sym == E.KeySym.TAB:
                return self.begin_target()
            return
        handler = {
            "f": self.begin_target, "F": self.cycle_mode, "r": self.cmd_reload, "t": self.cmd_throw,
            "c": self.cmd_crouch, "p": self.cmd_prone, "i": self.cmd_inventory, "g": self.cmd_pickup,
            ",": self.cmd_pickup, "d": self.cmd_drop, "w": self.cmd_wield, "a": self.cmd_apply,
            "B": self.cmd_bandage, "x": self.cmd_look, ";": self.cmd_look, "m": self.cmd_overmap,
            "P": self.cmd_log, "?": self.cmd_help, "e": self.cmd_vehicle, "o": self.cmd_door,
            "O": self.cmd_orders, "D": self.cmd_dig, "R": self.cmd_radio, "z": self.cmd_rest,
            "C": self.cmd_command, "q": self.cmd_peek,
            "Z": self.cmd_wait, "S": self.cmd_resupply, "@": self.cmd_charsheet, "Y": self.cmd_yell,
            "v": self.cmd_vehicle_mg, "s": lambda: self.act(100), "V": self.cmd_nearby,
            "+": lambda: self.zoom(1), "=": lambda: self.zoom(1), "-": lambda: self.zoom(-1),
            "G": self.cmd_staff, "W": self.cmd_pace, "!": self.cmd_safe_mode, "'": self.cmd_ignore_danger,
            "T": self.cmd_orders_book, "A": self.cmd_autopilot, "E": self.cmd_talk, "X": self.cmd_going,
        }.get(c)
        if handler:
            return handler()

    def _map_at(self, ftx, fty):
        """Text-cell float coords -> world tile (or None outside the map view)."""
        if ftx < 0 or fty < 0 or ftx >= VIEW_W or fty >= VIEW_H:
            return None
        gfx = getattr(self.app, "gfx", None)
        if gfx is not None and self.cam.fx0 is not None:
            return self.cam.world_at(ftx, fty)
        if gfx is not None:
            cx, cy = gfx.text_to_map_cell(ftx, fty)
        else:
            cx, cy = math.floor(ftx), math.floor(fty)
        if not (0 <= cx < self.cam.vw and 0 <= cy < self.cam.vh):
            return None
        return self.cam.to_map(cx, cy)

    def on_mouse_motion(self, ftx, fty):
        self.mouse_txt = (ftx, fty)
        tx, ty = math.floor(ftx), math.floor(fty)
        if self.inv_screen is not None:
            return self.inv_screen.on_mouse_motion(tx, ty)
        if self._drag is not None:
            # dragging the battlefield with the middle button
            sx, sy, cx0, cy0 = self._drag
            gfx = getattr(self.app, "gfx", None)
            kx, ky = gfx.map_scale() if gfx is not None else (1.0, 1.0)
            self.view_center = (cx0 - (ftx - sx) / kx, cy0 - (fty - sy) / ky)
            p = self.game.player
            self._view_pos = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
            self._cam_locked = False
            return
        mp = self._map_at(ftx, fty)
        self.hover_quiet = False
        if mp is not None:
            if mp != self.hover:
                self.hover_t = time.monotonic()
            self.hover = mp
            if self.mode in ("target", "throw", "look", "order_target", "radio_target", "flare_target"):
                m = self.game.map
                self.cursor = (max(0, min(m.w - 1, mp[0])), max(0, min(m.h - 1, mp[1])))
        else:
            self.hover = None
        if self.popups:
            it = self.popups[-1].item_at(tx, ty)
            if it is not None:
                self.popups[-1].sel = it

    def on_click(self, ftx, fty, button):
        g = self.game
        if g.map is None:
            return
        if self.realtime_busy() and button != 2:
            return
        if button == 2 and self.inv_screen is None and not self.popups and 0 <= ftx < VIEW_W and 0 <= fty < VIEW_H:
            c = self.view_center or (tuple(self.cam_c) if self.cam_c else
                                     (self.cam.x0 + self.cam.vw / 2, self.cam.y0 + self.cam.vh / 2))
            self._drag = (ftx, fty, c[0], c[1])
            return
        if button not in (1, 3) or ftx < 0 or fty < 0:
            return
        tx, ty = math.floor(ftx), math.floor(fty)
        if g.__dict__.get("succession_pending") and self.popups:
            pop = self.popups[-1]
            it = pop.item_at(tx, ty)
            if it is not None and button == 1:
                pop.sel = it
                return self.popup_select()
            return
        if not g.player.body.conscious or g.map is None:
            return                               # (out cold: no walking, firing or menus by mouse either)
        if self.inv_screen is not None:
            return self.inv_screen.on_click(tx, ty, button)
        if self.travel_path or self.running or self.auto_wait or self.__dict__.get("digging") or \
                self.__dict__.get("ff_until"):
            if self.__dict__.get("ff_until"):
                self.ff_until = None
                if g.__dict__.get("aboard"):
                    g.aboard["sleeping"] = False
            self.stop_auto()
            return
        if not self.popups and button == 1 and self._minimap_click(tx, ty):
            return
        if g.__dict__.get("autopilot") and not self.popups and self.inv_screen is None:
            g.msg("Your soldier's on autopilot. (A to take over)", "info")       # (looking and the minimap still work)
            return
        if self.popups:
            pop = self.popups[-1]
            it = pop.item_at(tx, ty)
            if it is not None and button == 1:
                pop.sel = it
                return self.popup_select()
            x, y, w, h = pop.rect
            if not (x <= tx < x + w and y <= ty < y + h):
                self.popups.pop()
            return
        mp = self._map_at(ftx, fty)
        if mp is None:
            return
        mx, my = mp
        if not g.map.in_bounds(mx, my):
            # the ground next door: walk to the edge nearest it
            mx = max(0, min(g.map.w - 1, mx))
            my = max(0, min(g.map.h - 1, my))
            if button == 1 and self.mode == "normal":
                self.start_travel(mx, my)
            return
        if button == 3:
            self.mode = "normal"
            self.cursor = None
            return self.context_menu(mx, my, tx, ty)
        if self.mode != "normal":
            self.cursor = (mx, my)
            return self.mode_confirm()
        # left click: walk there (or hit what's adjacent)
        p = g.player
        if max(abs(mx - p.x), abs(my - p.y)) == 1:
            return self.do_move(mx - p.x, my - p.y)
        self.start_travel(mx, my)

    def on_release(self, ftx, fty, button):
        if button == 2:
            self._drag = None
        if self.inv_screen is not None:
            self.inv_screen.on_release(math.floor(ftx), math.floor(fty), button)

    def on_wheel(self, dy, dx=0, shift=False):
        if self.inv_screen is not None:
            return
        if self.popups:
            self.popups[-1].move(-dy)
            return
        mx, my = getattr(self, "mouse_txt", (0, 0))
        if 0 <= mx < VIEW_W and 0 <= my < VIEW_H:
            gfx = getattr(self.app, "gfx", None)
            wv, hv = self._view_tiles(gfx) if gfx is not None else (VIEW_W, VIEW_H)
            if dx or shift:
                # two fingers sideways (or shift + wheel): pan
                self.pan(-dx * wv * 0.06 if dx else 0, (-dy * hv * 0.08) if shift and dy else 0)
                return
            self.zoom(1 if dy > 0 else -1)      # wheel over the battlefield zooms, toward the mouse
        else:
            self.log_scroll = max(0, self.log_scroll + dy)

    # ================================================================== movement
    def do_move(self, dx, dy, auto=False):
        g = self.game
        p = g.player
        m = g.map
        if p.vehicle is not None:
            return self.drive(dx, dy)
        if p.ai.get("carried_by") is not None:
            g.msg("You're being carried. Hang on.", "info")
            return self.act(100)
        nx, ny = p.x + dx, p.y + dy
        if not m.in_bounds(nx, ny):
            edge = "N" if ny < 0 else "S" if ny >= m.h else "W" if nx < 0 else "E"
            if not auto:
                self.prompt_travel(edge)
            return False
        other = g.soldier_at.get((nx, ny))
        if p.ai.get("grapple") is not None:
            from .melee import attack, grappling
            gr = grappling(g, p)
            if gr is not None:
                # locked together: at him is the fight, anywhere else is tearing free
                return self.act(attack(g, p, gr, None if other is gr else "break"))
        if other is not None and other.side != p.side and other.state == "ok" and not other.ai.get("civilian"):
            return self.act(A.melee(g, p, other))
        if other is not None and not auto and other.side == p.side and other.state == "ok" and not other.downed:
            from .base import TALKERS, talk
            if other.role in TALKERS and talk(self, other):
                return False                  # walking up to a man at his post is talking to him
        if not auto and self.safe_mode_blocks((dx, dy)):
            return False
        v = g.vehicle_at.get((nx, ny))
        if v is not None:
            if not auto:
                g.msg(f"{cap(g.name_of_vehicle(v))} is in the way." if v.side == p.side or v.dead
                      else f"You'd need something heavier than your boots for that {v.vt.name}.", "info")
            return False
        if m.tile(nx, ny).key == "wire" and p.has_tool("wirecutters") and not auto:
            return self.act(A.cut_wire(g, p, nx, ny))
        if not m.walk[nx, ny] and not T.DOOR[m.t[nx, ny]]:
            if not auto:
                d = m.tile(nx, ny)
                if d.window:
                    if self.__dict__.get("_window_bump") == (nx, ny, g.turn):
                        m.set(nx, ny, "window_broken", refresh=True)
                        g.emit_sound(nx, ny, 55, "glass", "breaking glass", p.side, p)
                        g.msg("You smash the window out with your rifle butt and knock the glass from the frame.",
                              "info")
                        self._window_bump = None
                        return self.act(250)
                    self._window_bump = (nx, ny, g.turn)
                    g.msg("A window. Push again to smash it out and climb through (it'll be heard).", "info")
                elif d.water >= 2:
                    pass
                else:
                    g.msg(f"There's {d.name} in the way.", "info")
            return False
        mn = m.mines.get((nx, ny))
        if mn is not None and p.side in mn.known and not auto:
            g.msg("There's a mine there. You know - you watched them bury it.", "warn")
            return False
        cost = A.move(g, p, dx, dy)
        if cost is None:
            return False
        if T.WATER[m.t[p.x, p.y]] >= 2 and p.carried_weight() > 15:
            g.msg("You're in deep water with a full kit.", "warn")
        self.act(cost)
        # something here?
        items = m.items_at(p.x, p.y)
        if items and not auto:
            names = ", ".join(i.name for i in items[:3])
            g.msg(f"Here: {names}{'...' if len(items) > 3 else ''}.", "info")
        return True

    def drive(self, dx, dy):
        g = self.game
        p = g.player
        v = p.vehicle
        if not v.player_crewed:
            g.msg("You're a passenger. Press e to get out (or to take an empty seat).", "info")
            return False
        from . import crew as C
        from .gamemap import octant
        seat = C.player_seat(v)
        if seat == "gunner" and v.vt.turret and v.vt.main:
            # at the gun, the direction keys traverse the turret (by hand, slowly, if the power's gone)
            from . import vdamage as VD
            tr = VD.traverse(v)
            want = octant(dx, dy)
            if tr == "jammed":
                g.msg("The turret's jammed: the hull has to swing to bring the gun round.", "warn")
                return False
            if tr == "hand" and want != v.turret:
                diff = (want - v.turret) % 8
                v.turret = (v.turret + (1 if diff <= 4 else -1)) % 8
                g.msg("You crank the traverse handwheel round, turn after turn.", "info")
                return self.act(VD.HAND_TRAVERSE)
            v.turret = want
            return self.act(50)
        ok, why = C.can(v, "drive")
        if not ok:
            g.msg(why + " (e to change seats)", "info")
            return False
        if not v.mobile:
            g.msg(f"The {v.vt.name} won't move: {v.status_text()}.", "warn")
            return False
        if seat == "commander":
            # you talk the driver through it; he does the driving
            d = octant(dx, dy)
            if v.ai.get("cmd_dir") != d or g.turn - v.ai.get("cmd_dir_turn", -99) > 30:
                v.ai["cmd_dir"] = d
                v.ai["cmd_dir_turn"] = g.turn
                rel = (d - v.facing) % 8
                word = {0: "Driver, advance!", 1: "Driver, half left!", 7: "Driver, half right!", 2: "Driver, left!",
                        6: "Driver, right!", 4: "Driver, reverse!", 3: "Driver, hard left!", 5: "Driver, hard right!"}[rel]
                p.say(word, g.turn, 2)
        # driving off the edge of the map: on to the next sector, vehicle and all
        m = g.map
        ahead = v.cells(v.x + dx, v.y + dy, octant(dx, dy))
        off = [(cx, cy) for cx, cy in ahead if not m.in_bounds(cx, cy)]
        if off:
            cx, cy = off[0]
            edge = "W" if cx < 0 else "E" if cx >= m.w else "N" if cy < 0 else "S"
            return self.prompt_travel(edge)
        cost = g.try_move_vehicle(v, dx, dy)
        if cost is None:
            # no room to go that way: swing the hull toward it, if there's room for that
            if g.turn_vehicle(v, octant(dx, dy)):
                return self.act(150)
            g.msg(f"There's no room to get the {v.vt.name} through there.", "info")
            return False
        p.x, p.y = v.x, v.y
        if seat == "commander":
            cost = int(cost * 1.15)           # a word, a pause, then the driver acts
        elif seat == "driver":
            from .skills import level, use
            cost = int(cost * max(0.85, 1.2 - level(p, "driving") * 0.04))
            if g.rng.random() < 0.05:
                use(g, p, "driving", 1.0)
        if v.ai.get("captured"):
            from .familiar import vehicle_learn, vehicle_level
            cost = int(cost * (1 + (1 - vehicle_level(v)) * 0.6))    # grinding unfamiliar gears
            vehicle_learn(v, 0.004)
        return self.act(max(40, cost))

    def _crew_fire(self, v, x, y, mg):
        """Fire from your seat - or, from the commander's, tell a gunner what to shoot."""
        from . import crew as C
        g = self.game
        p = g.player
        seat = C.player_seat(v)
        ok, why = C.can(v, "mg" if mg else "main")
        if not ok:
            g.msg(why + " (e to change seats)", "info")
            return
        tgt = g.vehicle_at.get((x, y)) or g.soldier_at.get((x, y))
        if tgt is not None and getattr(tgt, "side", None) == p.side and getattr(tgt, "vt", None) is None:
            g.msg("That's one of ours!", "warn")
            return
        if seat == "commander":
            if tgt is None:
                g.msg("Your gunner can't see anything there to lay on. (pick a target)", "info")
                return
            v.ai["designated"] = tgt.id
            v.ai["designated_turn"] = g.turn
            v.ai.pop("hold_fire", None)
            what = C.target_word(tgt)
            clock = C.clock_word(v, tgt.x, tgt.y)
            if mg:
                p.say(f"Machine guns - {what}, {clock}! Fire!", g.turn, 3)
            else:
                rnd = "AP" if getattr(tgt, "vt", None) is not None and v.ap > 0 else "HE" if v.he > 0 else "AP"
                if v.ammo_choice != rnd.lower():
                    v.ammo_choice = rnd.lower()
                p.say(f"Gunner - {rnd}, {what}, {clock}! Fire!", g.turn, 3)
            return self.act(50)
        if mg:
            idxs = C.mgs_for(v, seat)
            idxs = [i for i in idxs if C.mg_arc_ok(v, i, x, y)]
            if not idxs:
                g.msg("Your gun won't bear - it points where the hull points.", "info")
                return
            if C.player_seat(v) == "gunner" and v.vt.turret:
                from . import vdamage as VD
                tr = VD.traverse(v)
                want = octant(x - v.x, y - v.y)
                diff = (want - v.turret) % 8
                if tr == "power":
                    v.turret = want
                elif diff not in (0, 1, 7):
                    if tr == "hand":
                        v.turret = (v.turret + (1 if diff <= 4 else -1)) % 8
                        g.msg("No power to the traverse: you crank the turret round by hand. (v again when it bears)",
                              "info")
                        return self.act(VD.HAND_TRAVERSE)
                    g.msg("The turret ring's jammed - the coax only fires where the gun points.", "warn")
                    return
            if not vehicle_fire_mg(g, v, x, y, tgt, idxs=idxs):
                from .vdamage import mg_ok
                g.msg("Your machine gun's knocked out." if not any(mg_ok(v, i) for i in idxs) else
                      "The machine gun is silent - no belts left." if v.mg_ammo <= 0 else "The machine gun is silent.",
                      "warn")
                return
            return self.act(100)
        if v.reload > 0:
            g.msg("The gun isn't loaded yet!" + ("" if C.is_manned(v, "loader") else " (nobody's loading - it's all you)"),
                  "warn")
            return
        from . import vdamage as VD
        tr = VD.traverse(v)
        if v.vt.turret and not v.static and tr == "hand":
            want = octant(x - v.x, y - v.y)
            diff = (want - v.turret) % 8
            if diff not in (0, 1, 7):
                v.turret = (v.turret + (1 if diff <= 4 else -1)) % 8
                g.msg("No power to the traverse: you crank the turret round by hand. (f again when it bears)", "info")
                return self.act(VD.HAND_TRAVERSE)
        if not v.vt.turret or v.static or tr == "jammed":
            want = octant(x - v.x, y - v.y)
            gun = v.turret if tr == "jammed" else v.facing
            if (want - gun) % 8 not in (0, 1, 7):
                if C.is_manned(v, "driver") and not v.static:
                    if not VD.can_move(v):
                        g.msg("The gun won't bear, and she can't pivot to bring it round.", "warn")
                        return
                    p.say("Driver, swing us round!", g.turn, 2)
                    if g.turn_vehicle(v, v.facing + (1 if (want - gun) % 8 <= 4 else -1)) and tr != "jammed":
                        v.turret = v.facing
                    return self.act(150)
                if v.static:
                    g.turn_vehicle(v, v.facing + (1 if (want - v.facing) % 8 <= 4 else -1))
                    v.turret = v.facing
                    return self.act(250)
                g.msg("The gun won't traverse that far, and nobody's driving to swing the hull.", "info")
                return
        if not vehicle_fire_main(g, v, x, y, tgt, v.ammo_choice):
            g.msg("The gun's knocked out." if not v.gun_ok else
                  "No rounds left in the racks." if v.ap + v.he <= 0 and not (v.mount and v.mount.flame) else
                  "The main gun can't fire.", "warn")
            return
        return self.act(100)

    def _go_to_vehicle(self, v, then=None):
        """Walk to the nearest open ground beside a vehicle, and `then` on arrival (if it's still there)."""
        g = self.game
        p = g.player
        m = g.map
        if v.near(p.x, p.y) <= 1:
            return then() if then is not None else None
        cells = set(v.cells())
        best = None
        for cx, cy in cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    x, y = cx + dx, cy + dy
                    if (x, y) in cells or not m.in_bounds(x, y) or not m.walk[x, y] or m.water[x, y] >= 2:
                        continue
                    if g.vehicle_at.get((x, y)) is not None or g.soldier_at.get((x, y)) not in (None, p):
                        continue
                    d = max(abs(x - p.x), abs(y - p.y))
                    if best is None or d < best[0]:
                        best = (d, x, y)
        if best is None:
            g.msg(f"There's no getting near the {v.vt.name}.", "info")
            return False

        def arrive():
            if then is not None and not v.dead and v.near(p.x, p.y) <= 1:
                then()
        return self.start_travel(best[1], best[2], then=arrive)

    def start_travel(self, tx, ty, then=None, stop_short=0):
        """Walk there (click, or an order): `then` is done on arrival; `stop_short` stops beside it.

        The route is planned on what you know: ground you've seen as it is, ground you haven't as if you
        could cross it.  As you go and see more - a hedge where you hoped for a gap, a stream - the route is
        planned again from where you are, until you're there or every way you can think of is shut."""
        if self.game.__dict__.get("autopilot"):
            self.game.msg("Your soldier's on autopilot. (A to take over)", "info")
            return
        g = self.game
        p = g.player
        m = g.map
        self._following_order = None
        self.travel_then = None
        if not m.in_bounds(tx, ty):
            return False
        if p.vehicle is not None:
            return False
        if max(abs(tx - p.x), abs(ty - p.y)) <= stop_short:
            if then is not None:
                then()
            return True
        plan = self._plan_route(tx, ty, stop_short)
        if plan is None:
            g.msg("You can't see a way there from here." if m.explored[tx, ty] else
                  "There's no way there that you can think of from here.", "info")
            return False
        pts, (tx, ty) = plan
        if not pts:
            if then is not None:
                then()
            return bool(then)
        if self.safe_mode_blocks(("travel", tx, ty)):
            return False
        self.travel_replans = 0
        self._set_route(pts, tx, ty, stop_short)
        self.travel_then = then
        self.mark_interrupt()
        return True

    def _set_route(self, pts, tx, ty, stop_short):
        m = self.game.map
        self.travel_path = pts
        self.travel_dest = (tx, ty)
        self.travel_short = stop_short
        self.travel_known = int(m.explored.sum())
        self.travel_blind = [q for q in pts if not m.explored[q]]    # the steps planned on guesswork
        self.__dict__.setdefault("travel_replans", 0)

    def _route_costs(self, tx, ty, stop_short):
        """Step costs on what you know: seen ground as it is, unseen ground assumed passable (a little
        dearer, so a known way is preferred when there is one)."""
        g = self.game
        p = g.player
        m = g.map
        cost = np.maximum(1, T.COST[m.t] // 50).astype(np.int32)
        cost[~m.walk] = 0
        cost[T.DOOR[m.t] == 1] = 3
        # deep water: never a route you'd choose - unless you're already in it (off a landing craft), when
        # the way out is a swim
        cost[m.water >= 2] = 10 if m.water[p.x, p.y] >= 2 else 0
        cost[~m.explored] = 3                           # ground you haven't seen: you'll find out
        for (x, y), veh in g.vehicle_at.items():
            if m.visible[x, y] and veh is not p.vehicle:
                cost[x, y] = 0                          # a lorry parked across the lane: round it
        for (x, y), mn in m.mines.items():
            if p.side in mn.known:
                cost[x, y] = 0
        if stop_short:
            cost[tx, ty] = max(1, int(cost[tx, ty]))    # the man you're going to is standing on it
        return cost

    def _plan_route(self, tx, ty, stop_short=0):
        """(steps, destination) from where you stand, or None if you can't think of a way.  A destination
        you now know can't be stood on (a wall, a hedge, deep water) becomes the nearest spot to it that can."""
        g = self.game
        p = g.player
        m = g.map
        cost = self._route_costs(tx, ty, stop_short)
        if cost[tx, ty] == 0:
            best = None
            for r in range(1, 6):
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        x, y = tx + dx, ty + dy
                        if max(abs(dx), abs(dy)) == r and m.in_bounds(x, y) and cost[x, y] > 0:
                            d = math.hypot(dx, dy) + math.hypot(x - p.x, y - p.y) * 0.01
                            if best is None or d < best[0]:
                                best = (d, x, y)
                if best is not None:
                    break
            if best is None:
                return None
            tx, ty = best[1], best[2]
        try:
            path = tcod.path.path2d(cost, start_points=[(p.x, p.y)], end_points=[(tx, ty)],
                                    cardinal=2, diagonal=3)
        except Exception:
            return None
        pts = [(int(x), int(y)) for x, y in path][1:]
        if not pts and max(abs(tx - p.x), abs(ty - p.y)) > stop_short:
            return None
        if stop_short:
            pts = pts[:max(0, len(pts) - stop_short)]
        return pts, (tx, ty)

    def _replan_route(self) -> bool:
        """New ground seen on the way (or the next step turns out shut): plan again from here.  False if
        there's no way left."""
        g = self.game
        if self.travel_dest is None:
            return False
        self.travel_replans = self.__dict__.get("travel_replans", 0) + 1
        if self.travel_replans > 600:
            return False
        tx, ty = self.travel_dest
        plan = self._plan_route(tx, ty, self.__dict__.get("travel_short", 0))
        if plan is None or not plan[0]:
            return plan is not None
        pts, (tx, ty) = plan
        self._set_route(pts, tx, ty, self.__dict__.get("travel_short", 0))
        return True

    def prompt_travel(self, edge):
        """Walking (or driving) off the edge of the ground you're on: straight on into the next."""
        g = self.game
        if not g.can_travel(edge):
            g.msg("There's nothing that way but open water.", "info")
            return
        p = g.player
        from .orders import authorized_departure
        if not authorized_departure(g, edge) and p.squad is not None and not p.squad.player_led and \
                p.squad.order.kind in ("attack", "defend"):
            # a step away from your squad in the middle of a fight is desertion: say so once
            if self._desert_warned != (edge, g.turn // 30):
                self._desert_warned = (edge, g.turn // 30)
                g.msg("Your squad is still fighting here. Keep going and you're deserting.", "warn")
                return
        self._travel_chosen(edge)

    # ================================================================== safe mode (as in CDDA)
    def dangers(self):
        """What you can see or feel that makes a step dangerous: [(kind, key, thing, distance)]."""
        g = self.game
        p = g.player
        px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        out = []
        for a in g.actors:
            if a.side != p.side and not a.ai.get("civilian") and a.alive and a.state == "ok" and not a.downed and player_can_see_actor(g, a):
                out.append(("enemy", ("a", a.id), a, max(abs(a.x - px), abs(a.y - py))))
        for v in g.vehicles:
            if v.side != p.side and v.active and g.map.in_bounds(v.x, v.y) and g.map.visible[v.x, v.y]:
                out.append(("enemy", ("v", v.id), v, max(abs(v.x - px), abs(v.y - py))))
        t = g.turn
        if p.hit_turn >= t - 5:
            out.append(("fire", ("hit", p.hit_turn), None, 0))
        elif g.__dict__.get("last_near_miss", -99) >= t - 5 or p.suppression > 25:
            out.append(("fire", ("shot at", g.__dict__.get("last_near_miss", t) // 10), None, 0))
        for sh in getattr(g, "shells", ()) or ():
            tx, ty = getattr(sh, "x", None), getattr(sh, "y", None)
            if isinstance(sh, dict):
                tx, ty = sh.get("x"), sh.get("y")
            if tx is not None and max(abs(tx - px), abs(ty - py)) < 14:
                out.append(("fire", ("shells", t // 20), None, 0))
                break
        return out

    def _danger_new(self, found):
        """The dangers you haven't already been warned about (or that have got a lot closer since)."""
        ack = self.__dict__.get("safe_ack") or {}
        new = []
        for kind, key, thing, d in found:
            d0 = ack.get(key, (None,))[0]
            if d0 is None or (kind == "enemy" and ((d <= 3 < d0) or (d <= 6 < d0) or (d0 - d >= 4 and d < d0 * 0.6))):
                new.append((kind, key, thing, d))
        return new

    def _danger_ack(self, found, touch_only=False):
        ack = self.__dict__.setdefault("safe_ack", {})
        t = self.game.turn
        for kind, key, thing, d in found:
            old = ack.get(key)
            # a fresh warning sets the distance you were told about; otherwise just "still there"
            ack[key] = (d if touch_only is False or old is None else old[0], t)
        # a man out of sight for a minute is forgotten: if he shows up again, you hear about it again
        for k in [k for k, v in ack.items() if v[1] < t - 60]:
            del ack[k]

    def safe_mode_blocks(self, what) -> bool:
        """CDDA's safe mode: with the enemy in sight (or bullets about), the first step is a warning;
        take the step again and you've been told.  ' ignores what you can see now; ! turns it off."""
        st = getattr(self.app, "settings", None) or {}
        g = self.game
        p = g.player
        found = self.dangers()
        if not st.get("safe_mode", True):
            return False
        new = self._danger_new(found)
        if not new:
            self._danger_ack(found, touch_only=True)
            return False
        warned = self.__dict__.get("safe_warned")
        if warned is not None and warned[0] == what and g.turn - warned[1] <= 2:
            self._danger_ack(found)             # you heard; you go anyway
            self.safe_warned = None
            return False
        self.safe_warned = (what, g.turn)
        self.stop_auto()
        g.msg(self._danger_text(new) + "  Again to move anyway;  ' ignore;  ! safe mode off.", "warn")
        return True

    def _danger_text(self, new):
        g = self.game
        p = g.player
        px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        fire = [n for n in new if n[0] == "fire"]
        foes = sorted((n for n in new if n[0] == "enemy"), key=lambda n: n[3])
        bits = []
        if fire:
            k = fire[0][1][0]
            bits.append({"hit": "You've been hit!", "shot at": "You're under fire!",
                         "shells": "Shells are coming down close!"}.get(k, "Danger!"))
        if foes:
            kind, key, e, d = foes[0]
            from .constants import COMPASS
            dx, dy = e.x - px, e.y - py
            ang = math.atan2(dy, dx)
            o = int(round(ang / (math.pi / 4))) % 8
            vec = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)][o]
            where = COMPASS.get(vec, "")
            if getattr(e, "vt", None) is not None:
                what = f"an enemy {e.vt.name}"
            else:
                what = f"{'an' if NATIONS[e.nation]['adj'][0] in 'AEIOU' else 'a'} {NATIONS[e.nation]['adj']} " \
                       f"{e.role_name.lower()}"
            more = f" (and {len(foes) - 1} more)" if len(foes) > 1 else ""
            bits.append(f"Enemy in sight: {what}, {yards(d)} to the {where}{more}.")
        return " ".join(bits)

    def cmd_safe_mode(self):
        st = getattr(self.app, "settings", None)
        if st is None:
            return
        st["safe_mode"] = not st.get("safe_mode", True)
        try:
            st.save()
        except Exception:
            pass
        self.game.msg("Safe mode " + ("on: you'll be warned before stepping out under the enemy's eyes."
                                      if st["safe_mode"] else "off. Watch yourself."), "info")

    def cmd_going(self):
        """Read the ground: tint what you can't get through red, and slow going amber (X)."""
        st = getattr(self.app, "settings", None)
        if st is None:
            return
        st["going"] = not st.get("going", False)
        try:
            st.save()
        except Exception:
            pass
        who = "the vehicle" if self.game.player.vehicle is not None else "you"
        self.game.msg("You read the ground: red is no way through for " + who + ", amber is slow going - the "
                      "deeper, the slower. (X again to stop)" if st["going"] else "You stop reading the ground.",
                      "info")

    def going_on(self) -> bool:
        st = getattr(self.app, "settings", None)
        return bool(st is not None and st.get("going", False))

    def cmd_ignore_danger(self):
        found = self.dangers()
        self._danger_ack(found)
        self.safe_warned = None
        n = sum(1 for f in found if f[0] == "enemy")
        self.game.msg(f"You note {'them' if n != 1 else 'it'} and carry on." if found else "Nothing in sight.", "info")

    # ================================================================== doing what you're told
    def _order_plan(self):
        """(what Enter will do, the function that does it) for your current order - or None."""
        g = self.game
        p = g.player
        if g.__dict__.get("domain") == "aboard" and (g.aboard or {}).get("kind") == "ship":
            from . import shipboard as SB
            return SB.plan(self)
        from .orders import active, navigation
        current = active(g)
        foc = current["key"] if current is not None else None
        if foc in ("mission", "field") and p.vehicle is None:
            pt = navigation(g)
            if pt is None:
                return ("carry out the briefing here (T: details; no single destination)", self.cmd_orders_book)
            ms = g.__dict__.get("mission") or {}
            edge = None
            if foc == "field":
                edge = g.field_order.get("edge")
            elif pt[2].startswith("Return toward"):
                edge = ms.get("home") or g.home_edge(p.side)
            elif pt[2] == "Return to the mission sector":
                from .base import _next_edge
                sector = ms.get("_start_sector", g.sector)
                edge = _next_edge(g, (sector.x, sector.y))
            close = max(abs(pt[0] - p.x), abs(pt[1] - p.y)) <= (1 if edge else 3)
            if edge:
                return (pt[2].lower(), lambda: self._travel_chosen(edge) if close else
                        self.start_travel(pt[0], pt[1], then=lambda: self._travel_chosen(edge), stop_short=1))
            if not close:
                instruction = pt[2].lower()
                if not instruction.startswith(("take ", "hold ")):
                    instruction = "move to the " + instruction
                return (instruction, lambda: self.start_travel(pt[0], pt[1], stop_short=1))
            return ("hold at the mission position; T shows the remaining task", self.cmd_orders_book)
        chosen_other = (foc or "fire") != "fire"      # (you picked another order in the book: that one first)
        if g.support is not None and not chosen_other:
            f = g.support.fires
            pm = f.player_mission(g)
            if pm is not None:
                d = pm[1]["data"]
                what = "drop a bomb down the tube" if pm[0].kind == "mortar" else "lay the gun and fire"
                return (f"{what}: azimuth {d['az']:04d}, elevation {d['qe']:04d}, charge {d['charge']}",
                        lambda: self._fire_mission_round())
        if foc == "base" and g.__dict__.get("base_order") and p.vehicle is None:
            from . import base as BASE
            plan = BASE.order_plan(self)               # (you chose the adjutant's orders in the book)
            if plan is not None:
                return plan
        if p.vehicle is not None:
            bo = g.__dict__.get("base_order")
            if bo and bo.get("kind") == "supply_run" and bo.get("truck") == p.vehicle.id:
                from . import base as BASE
                return BASE.order_plan(self)
            # riding in the back: the order is to get out and get on with it; crewing it: your seat is your job
            if p in p.vehicle.passengers:
                v = p.vehicle
                return ("climb out", lambda: self._vehicle_choice(v, ("exit", None)))
            return None
        d = getattr(g, "duty", None)
        t = current.get("task") if current is not None else None
        near = lambda a: max(abs(a.x - p.x), abs(a.y - p.y)) <= 1   # noqa: E731

        def again(fn, a, reach=1):
            """On arrival: do it if he's still within reach; if he's moved on, after him (a few tries)."""
            def go():
                if max(abs(a.x - p.x), abs(a.y - p.y)) <= reach:
                    return fn()
                k = self.__dict__.get("_order_retry", 0)
                if k < 6:
                    self.cmd_do_order(retry=k + 1)
            return go
        if t is not None:
            k = t["kind"]
            tgt = t.get("target")
            who = d._actor(g, tgt) if isinstance(tgt, int) else None
            by = d._actor(g, t["by"])
            name = g.name_of(who) if who is not None else ""
            if k == "help" and who is not None:
                act = lambda: self._patch_menu(who) if near(who) else None   # noqa: E731
                return (f"go to {name} and patch him up" if not near(who) else f"patch up {name}",
                        lambda: self.start_travel(who.x, who.y, then=again(lambda: self._patch_menu(who), who),
                                                  stop_short=1) if not near(who) else act())
            if k == "ammo" and who is not None:
                close = max(abs(who.x - p.x), abs(who.y - p.y)) <= 2        # near enough to toss it to him
                give = lambda: self._give(who, "give_ammo")   # noqa: E731
                return (f"take the ammunition over to {name}" if not close else f"hand {name} the ammunition",
                        lambda: self.start_travel(who.x, who.y, then=again(give, who, 2), stop_short=1)
                        if not close else give())
            if k == "gun" and isinstance(tgt, tuple):
                it = t.get("item")

                def take():
                    if it is not None and it in g.map.items_at(p.x, p.y):
                        self._pickup(it)
                        if it in p.inv:
                            self.item_action(it, "wield")
                return ("go to the gun and take it up", lambda: self.start_travel(tgt[0], tgt[1], then=take))
            if k == "down":
                return ("get down", self.cmd_prone if p.stance != 2 else (lambda: None))
            if k == "come" and who is not None:
                return (f"go to {name}", lambda: self.start_travel(who.x, who.y, stop_short=2))
            if k == "fire" and isinstance(tgt, tuple):
                def aim():
                    self.begin_target()
                    if self.mode == "target":
                        self.cursor = tgt
                return ("aim at where he pointed", aim)
            if k == "dig":
                return ("dig in here" if p.has_tool("shovel") else "(you've nothing to dig with)", self.cmd_dig)
            if k == "runner" and who is not None:
                return (f"run the message to {name}", lambda: self.start_travel(who.x, who.y, stop_short=1))
            if k == "fetch" and isinstance(tgt, tuple):
                if p.ai.get("resupplied_turn", -1) >= t["issued"] and by is not None:
                    return (f"bring the ammunition back to {g.name_of(by)}",
                            lambda: self.start_travel(by.x, by.y, stop_short=2))
                def back():
                    self.cmd_resupply()
                    if by is not None:
                        self.start_travel(by.x, by.y, stop_short=2)
                return ("go to the ammunition point, draw ammunition, and bring it back",
                        lambda: self.start_travel(tgt[0], tgt[1], then=back, stop_short=1))
            if k == "scout" and isinstance(tgt, tuple):
                if t.get("leg") == "out":
                    return ("creep out to where he pointed", lambda: self.start_travel(tgt[0], tgt[1]))
                if by is not None:
                    return (f"go back and report to {g.name_of(by)}", lambda: self.start_travel(by.x, by.y,
                                                                                               stop_short=2))
            if k in ("track", "shells"):
                from . import maintenance as MT
                v = next((v for v in g.vehicles if v.id == t.get("vid")), None)
                if v is not None and not v.dead:
                    if k == "track":
                        help_ = lambda: MT.help_with(self, v)   # noqa: E731
                        if v.near(p.x, p.y) <= 1:
                            return (f"work on the {v.vt.name}'s track with the crew", help_)
                        return (f"go to the {v.vt.name} and help with the track", lambda: self._go_to_vehicle(v, help_))
                    crate = (p.invent.hands is not None and p.invent.hands.tid == "shell_crate") or \
                        any(i.tid == "shell_crate" for i in p.inv)
                    if crate:
                        up = lambda: MT.hand_up(self, v)   # noqa: E731
                        if v.near(p.x, p.y) <= 1:
                            return (f"hand the shells up into the {v.vt.name}", up)
                        return (f"carry the crate to the {v.vt.name} and hand it up", lambda: self._go_to_vehicle(v, up))
                    trucks = [tr for tr in g.vehicles if tr.side == p.side and MT.is_supply_truck(tr)]
                    if trucks:
                        tr = min(trucks, key=lambda tr: abs(tr.x - p.x) + abs(tr.y - p.y))

                        def fetch():
                            MT.take_crate(self, tr)
                            if p.invent.hands is not None and p.invent.hands.tid == "shell_crate":
                                self._go_to_vehicle(v, lambda: MT.hand_up(self, v))
                        return ("get a crate of shells off the truck and take it to the tank",
                                (lambda: fetch()) if tr.near(p.x, p.y) <= 1 else
                                (lambda: self._go_to_vehicle(tr, fetch)))
                    return ("(there's no ammunition truck up here to carry shells from)", lambda: None)
            if k == "escort":
                from .prisoners import prisoners_of
                brain = g.brains[p.side]
                if prisoners_of(g, p) and brain.home is not None:
                    edge = g.home_edge(p.side)
                    x, y = g._edge_exit_point(edge, (p.x, p.y), 6) if edge else (p.x, p.y)
                    return ("walk your prisoners back toward our lines", lambda: self.start_travel(x, y))
        from . import base as BASE
        if g.__dict__.get("ship_ashore"):
            pd = BASE.staff_here(g, "port_officer")
            if pd:
                who = min(pd, key=lambda a: abs(a.x - p.x) + abs(a.y - p.y))
                return ("go to the port director for the boat back",
                        lambda: self.start_travel(who.x, who.y, then=lambda: BASE.talk(self, who), stop_short=1))
        if g.__dict__.get("awol") or (BASE._straggler(g) and not g.__dict__.get("base_order")):
            adj = BASE.staff_here(g, "adjutant") or (BASE.staff_here(g, "port_officer") if g.__dict__.get("awol")
                                                     else [])
            if adj:
                who = min(adj, key=lambda a: abs(a.x - p.x) + abs(a.y - p.y))
                return (f"report to the {who.role_name.lower()}",
                        lambda: self.start_travel(who.x, who.y, then=lambda: BASE.talk(self, who), stop_short=1))
        plan = BASE.order_plan(self) if foc == "base" else None
        if plan is not None:
            return plan
        tp = g.order_target_for_player()
        if tp is not None and max(abs(tp[0] - p.x), abs(tp[1] - p.y)) > 3:
            return ("move toward your objective", lambda: self.start_travel(tp[0], tp[1], stop_short=1))
        return None

    def _vehicle_state_lines(self, v, friend, d):
        """What you know of a vehicle's state: ours, everything its crew would shout down to you (yours, to
        the round); the enemy's, only what shows from outside - a track lying off, smoke, holes, a head
        out of the hatch."""
        from . import vdamage as VD
        from . import crew as C
        g = self.game
        p = g.player
        out = []
        if v.dead:
            return [("destroyed", (200, 120, 100))]
        close = d < 45 or g.player_binoculars
        # ours: what the crew would shout down to you - within shouting distance, over the radio, or aboard
        told = p.vehicle is v or d <= 10 or (p.has_tool("radio") is not None and v.squad is not None and
                                             v.squad is p.squad)
        if friend and not told:
            seen = VD.visible_damage(v) if close or v.burning else (["burning"] if v.burning else [])
            return [(", ".join(seen) if seen else ("no damage that shows" if close else "too far to tell"),
                     (230, 150, 110) if seen else FRIEND_COLOR)]
        if friend:
            dmg = VD.damage_list(v)
            r = v.hp / v.vt.hp
            hull = "hull badly holed" if r < 0.35 else "hull damaged" if r < 0.75 else None
            words = (["burning"] if v.burning else []) + dmg + ([hull] if hull else [])
            if v.abandoned:
                words.insert(0, "abandoned")
            out.append((", ".join(words) if words else "no damage", (230, 150, 110) if words else FRIEND_COLOR))
            if not v.abandoned and v.vt.crew:
                men = C.manned(v)
                empty = [C.name(v.vt, st).lower() for st in (v.ai.get("seat_out") or {})]
                crew = f"crew {v.crew} of {v.vt.crew}" + (f" - the {', the '.join(empty)} hit" if empty else "")
                hs = VD.hatch_user(v)
                if hs is not None and hs in men | ({v.player_station} if v.player_crewed else set()):
                    crew += ", buttoned up" if v.buttoned else ", commander head out"
                out.append((crew, UI_TEXT))
            if p.vehicle is v and (v.vt.ap or v.vt.he):
                out.append((f"{v.ap} AP, {v.he} HE aboard; machine-gun belts: {v.mg_ammo} rounds", UI_DIM))
            from .rear import describe as convoy_load
            load = convoy_load(v)
            if load:
                out.append((load[0].upper() + load[1:], (200, 190, 150)))
        else:
            if v.vt.id == "ambulance" and close:
                out.append(("red crosses on its sides and roof", (230, 120, 110)))
            seen = VD.visible_damage(v) if close or v.burning else (["burning"] if v.burning else [])
            if seen:
                out.append((", ".join(seen), ENEMY_COLOR))
            elif close:
                out.append(("no damage you can see", ENEMY_COLOR))
            if close and not v.abandoned and VD.hatch_user(v) is not None and not v.buttoned and v.crew > 0:
                out.append(("the commander's head is out of the hatch", (230, 200, 120)))
        return out

    def context_hint(self):
        """The keys that matter right where you're standing: a line under the orders (Options: Hints)."""
        g = self.game
        p = g.player
        m = g.map
        v = p.vehicle
        if v is not None:
            if v.player_crewed:
                from . import crew as C
                from .vdamage import hatch_user
                seat = C.player_seat(v)
                hatch = ""
                if seat == hatch_user(v):
                    hatch = " Hatch shut (e to open)." if v.buttoned else " Head out of the hatch (e to button up)."
                elif (seat in ("gunner", "driver") or seat.startswith("mg")) and not v.vt.open_top and \
                        not v.vt.static and v.vt.vtype not in ("truck", "car", "lc") and max(v.vt.armor) > 12:
                    hatch = " You see only through your sight."
                return f"{C.name(v.vt, seat)}: {C.seat_help(v, seat)}{hatch} e: seats, get out."
            if riding(p):
                return "Riding on the hull: e to jump down. (There's no firing from up there: get off to fight.)"
            return "A passenger: e to get out (or take an empty seat)."
        if p.carrying is not None:
            return f"Carrying {g.name_of(p.carrying)}: walk them to cover or a medic; B puts them down."
        if p.invent.hands is not None:
            h = p.invent.hands
            if h.tid == "shell_crate":
                return "A crate of shells in your arms: right-click a tank beside you to hand it up. d drops it."
            return f"{h.name} in your hands: i to put it away, d to drop it."
        from .base import TALKERS
        from . import maintenance as MT
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not dx and not dy:
                    continue
                x, y = p.x + dx, p.y + dy
                veh = g.vehicle_at.get((x, y))
                if veh is not None and not veh.dead and (veh.side == p.side or veh.abandoned or veh.crew == 0):
                    extra = []
                    if veh.side == p.side and MT.repairs(veh):
                        extra.append("help fix it")
                    if MT.is_supply_truck(veh):
                        extra.append("take shells")
                    rider = not veh.vt.seats and p.role != "tank_crew" and veh.crew >= veh.vt.crew and not veh.abandoned
                    return (f"The {veh.vt.name}: e {'climb on and ride' if rider else 'get in'}"
                            + (f"; right-click: {', '.join(extra)}" if extra else "; right-click for more") + ".")
                a = g.soldier_at.get((x, y))
                if a is not None and a is not p and a.side == p.side and a.state == "ok" and a.active:
                    if a.role in TALKERS or a.role in ("quartermaster", "intel"):
                        return f"The {a.role_name.lower()}: walk into {a.him} or right-click to talk."
                    if a.downed or a.body.bleed_rate() > 0.1:
                        return f"{g.name_of(a)} is hurt: right-click {a.him} to patch {a.him} up."
                if m.in_bounds(x, y) and T.DOOR[m.t[x, y]]:
                    return "A door: walk through it to open it; o shuts an open door beside you."
        if m.items_at(p.x, p.y):
            return "Something here: g picks it up (i for the kit screen)."
        return None

    def order_hint(self):
        plan = self._order_plan()
        return f"Enter: {plan[0]}" if plan else None

    def _fire_mission_round(self):
        g = self.game
        g.player.ai["mission_fired"] = g.turn        # (where the rounds land is the observer's call: duty._justified)
        c = g.support.fires.fire_player_round(self)
        if c:
            self.act(c)

    def cmd_do_order(self, retry=0):
        """Enter: set about your orders - walk there, and do it when you arrive (he may have moved: after him)."""
        g = self.game
        plan = self._order_plan()
        if plan is None:
            if not retry:
                g.msg("You've no particular orders to carry out right now.", "info")
            return
        if not retry:
            g.msg(f"You {plan[0]}.", "info")
        self._order_retry = retry
        from .orders import execution_signature
        signature = execution_signature(g)
        plan[1]()
        if self.travel_path:
            self._following_order = signature

    def _leave_ship(self):
        """The voyage is over - home to port, or into the sea."""
        from . import aboard as AB
        from .skysea_exit import _nearest_coast, adrift, to_land
        g = self.game
        ss = g.skysea
        over = ss.over if ss is not None else None
        ship = AB.ship_of(g)
        p = g.player
        g.domain = "land"
        g.aboard = None
        g.skysea = None
        if over == "dead" or not p.alive:
            p.body.dead = True
            if not getattr(p, "_killed", False):
                g.kill(p, None)                  # (player_died runs from there - once: one death, one life)
            elif not g.game_over and g.player is p:
                g.player_died(None)
            if not g.game_over and g.player is not p:
                # someone carries on - a man of her crew, picked up and put ashore
                x, y = (ship.x, ship.y) if ship is not None else (ss.cx * 30, ss.cy * 30) if ss is not None else (0, 0)
                coast = _nearest_coast(g, x, y, g.player.side) or g.sector
                g.map = None
                to_land(g, coast)
                self.recenter()
            return self.check_over()
        if isinstance(over, tuple) and over[0] == "landed":
            g.map = None
            to_land(g, g.strategic.at(*over[1], create=True), airfield=True)
            g.msg("She's down. You climb out onto the hardstand with the rest of the crew.", "info")
            self.recenter()
            return self.check_over()
        if over == "raft":
            g.map = None
            adrift(g, ss)
            if g.map is None and p.alive and not g.__dict__.get("pow"):
                to_land(g, g.sector)            # (never left without ground under him)
        else:
            x, y = (ship.x, ship.y) if ship is not None else (ss.cx * 30, ss.cy * 30)
            coast = _nearest_coast(g, x, y, p.side) or g.sector
            g.map = None
            to_land(g, coast)
            g.msg(f"{ship.name if ship else 'The ship'} puts in. You go ashore at {coast.name}.", "info")
        self.recenter()
        self.cam_c = None
        self.check_over()

    # ================================================================== time going by, aboard
    def _quiet_aboard(self):
        from . import shipboard as SB
        return SB.quiet(self.game)

    def fast_forward(self, sleep=False):
        """Z aboard: the hours go by in big steps until something happens (or you're woken)."""
        from . import shipboard as SB
        g = self.game
        if not SB.quiet(g) and not sleep:
            g.msg("Not now - there's something going on.", "info")
            return
        g.aboard["sleeping"] = sleep
        cond = g.aboard["condition"]
        self.ff_until = g.turn + (8 * 3600 if sleep else (6 * 3600 if cond in ("III", "port") else 3600))
        self.ff_start = g.turn
        self.mark_interrupt()
        g.msg("You turn in." if sleep else ("The ship steams on. (any key stops)" if cond == "III" else
                                            "She swings at anchor; the work goes on. (any key stops)"
                                            if cond == "port" else "You stand by at your station. (any key stops)"),
              "info")

    def _ff_tick(self):
        from . import shipboard as SB
        g = self.game
        stop = False
        for _ in range(4):
            if SB.fast_step(g, 30) or g.turn >= self.ff_until or g.game_over:
                stop = True
                break
        if stop:
            span = g.turn - self.ff_start
            g.aboard["sleeping"] = False
            self.ff_until = None
            g.msg(self.span_words(span), "info")
            if g.player.stance == 2 and T.DEFS[int(g.map.t[g.player.x, g.player.y])].key == "bunk":
                g.msg("Someone shakes you awake.", "info")
            g.update_orders(force=True)
            g.player_fov()

    def after_travel(self):
        self.recenter()
        self.cam.focus(self.game)

    def _travel_chosen(self, edge):
        if edge:
            g = self.game
            from .orders import authorized_departure
            authorized = authorized_departure(g, edge)
            if not authorized and g.player.squad and not g.player.squad.player_led and \
                    g.player.squad.order.kind in ("attack", "defend"):
                g.stats["desertions"] += 1
            g.travel(edge)
            self.recenter()
            self.cam.focus(g)

    # ================================================================== popups
    def open_popup(self, pop: Popup, callback, cancel=None):
        pop.data["cb"] = callback
        pop.data["cancel"] = cancel
        self.popups.append(pop)

    def popup_key(self, key: Key):
        pop = self.popups[-1]
        if key.sym == E.KeySym.ESCAPE:
            self.popups.pop()
            cb = pop.data.get("cancel")
            if cb:
                cb()
            return
        if key.sym in (E.KeySym.UP, E.KeySym.KP_8):
            pop.move(-1)
            return
        if key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
            pop.move(1)
            return
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
            return self.popup_select()
        if key.char:
            if pop.kind == "yesno":
                if key.char in "yY":
                    pop.sel = 0
                    return self.popup_select()
                if key.char in "nN":
                    self.popups.pop()
                    return
            idx = pop.index_of_letter(key.char)
            if idx is not None:
                pop.sel = idx
                return self.popup_select()

    def popup_select(self):
        pop = self.popups[-1]
        if not pop.options:
            self.popups.pop()
            return
        label, value, col, enabled = pop.options[pop.sel]
        if not enabled:
            return
        cb = pop.data.get("cb")
        keep = pop.data.get("keep", False)
        if not keep:
            self.popups.remove(pop)
        if cb:
            self._rt_modal_action = True
            try:
                cb(value)
            finally:
                self._rt_modal_action = False
                self.reset_realtime_clock()

    # ================================================================== targeting modes
    def enter_mode(self, mode, cursor, pending=None):
        self.mode = mode
        self.cursor = cursor
        self.pending = pending or {}

    def mode_key(self, key: Key):
        g = self.game
        if key.sym == E.KeySym.F1 or key.char == "?":
            return self.cmd_help()                  # (the mode stays: help opens on the section for it)
        if self.mode == "nearby":
            return self._nearby_key(key)
        mv = key.move()
        if getattr(key, "ctrl", False) and mv:
            gfx = getattr(self.app, "gfx", None)
            wv, hv = self._view_tiles(gfx) if gfx is not None else (VIEW_W, VIEW_H)
            return self.pan(mv[0] * wv * 0.25, mv[1] * hv * 0.25)
        if key.sym == E.KeySym.F5:
            self.minimap = not self.minimap
            return
        if key.char in ("+", "="):
            return self.zoom(1)
        if key.char == "-":
            return self.zoom(-1)
        if key.sym == E.KeySym.HOME:
            self.recenter()
            if self.cursor is not None:
                p = g.player
                self.cursor = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
            return
        if key.sym == E.KeySym.ESCAPE:
            if self.mode == "look":
                self.park_view()          # the view stays where you were looking (Home to come back)
            self.mode = "normal"
            self.cursor = None
            self.pending = None
            return
        if self.mode in ("place", "peek") and mv:
            p = g.player
            self.cursor = (p.x + mv[0], p.y + mv[1])
            return self.mode_confirm()
        if mv:
            step = 5 if key.is_run() else 1
            cx, cy = self.cursor
            self.cursor = (max(0, min(g.map.w - 1, cx + mv[0] * step)), max(0, min(g.map.h - 1, cy + mv[1] * step)))
            return
        if key.sym == E.KeySym.TAB and self.mode == "target":
            self.cycle_target(-1 if key.shift else 1)
            return
        if key.sym == E.KeySym.TAB and self.mode == "order_target" and (self.pending or {}).get("props"):
            # step the cursor through the proposed places (the objectives, the enemy positions you know of)
            props = self.pending["props"]
            i = self.pending.get("prop_i", -1) + (-1 if key.shift else 1)
            self.pending["prop_i"] = i % len(props)
            self.cursor = tuple(props[i % len(props)])
            return
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER) or key.char in ("f", "t") and self.mode in ("target", "throw") \
                or key.char == "." and self.mode != "look":
            return self.mode_confirm()
        if key.char == "a" and self.mode == "target":
            return self.aim()
        if key.char == "A" and self.mode == "target":
            return self.aim(then_fire=True)
        if key.char == "c" and self.mode == "throw":
            self.cook = (self.cook + 1) % 4
            g.msg(f"You'll hold it {self.cook} second{'s' if self.cook != 1 else ''} before throwing." if self.cook
                  else "You'll throw it straight away.", "info")
            return
        if key.char in ("x", ";") and self.mode == "look":
            self.park_view()
            self.mode = "normal"
            self.cursor = None

    def mode_confirm(self):
        g = self.game
        mode = self.mode
        cursor = self.cursor
        pend = self.pending or {}
        self.mode = "normal"
        self.cursor = None
        self.pending = None
        if cursor is None:
            return
        if mode == "target":
            return self.fire_at(*cursor, pend)
        if mode == "throw":
            it = pend.get("item")
            if it is not None and it in g.player.inv:
                cook = self.cook
                self.cook = 0
                return self.act(A.throw(g, g.player, it, cursor[0], cursor[1], cook))
        if mode == "peek":
            p = g.player
            dx, dy = cursor[0] - p.x, cursor[1] - p.y
            c = A.peek(g, p, dx, dy) if max(abs(dx), abs(dy)) == 1 else None
            if c is None:
                g.msg("There's nothing to lean out into that way - it's solid.", "info")
                return
            from .senses import direction_word
            m = g.map
            what = "out of the window" if T.WINDOW[m.t[cursor[0], cursor[1]]] else \
                "over the top" if not m.walk[cursor[0], cursor[1]] else f"round to the {direction_word(dx, dy)}"
            g.msg(f"You lean {what}, keeping most of yourself behind cover. (q or moving: back in)", "info")
            return self.act(c)
        if mode == "place":
            it = pend.get("item")
            p = g.player
            if it is not None and it in p.inv and max(abs(cursor[0] - p.x), abs(cursor[1] - p.y)) == 1:
                return self.act(A.place_charge(g, p, it, cursor[0], cursor[1]))
            g.msg("You can only place a charge right next to you.", "info")
            return
        if mode == "order_target":
            cb = pend.get("cb")
            if cb:
                cb(cursor)
        if mode == "radio_target":
            cb = pend.get("cb")
            if cb:
                cb(cursor)
        if mode == "flare_target":
            return self.act(A.fire_flare(g, g.player, cursor[0], cursor[1]))
        if mode == "look":
            # Enter while looking: walk there (finding a way through what you haven't seen)
            self.mode = "normal"
            self.cursor = None
            return self.start_travel(cursor[0], cursor[1])

    def visible_targets(self):
        g = self.game
        p = g.player
        ox, oy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        ts = [a for a in g.actors if a.side != p.side and not a.ai.get("civilian") and a.alive and a.state == "ok" and a.vehicle is None
              and player_can_see_actor(g, a)]
        ts += [v for v in g.vehicles if v.side != p.side and not v.dead and g.map.visible[v.x, v.y]]
        ts.sort(key=lambda e: (e.x - ox) ** 2 + (e.y - oy) ** 2)
        return ts

    def captive_blocks(self, what="that"):
        """A prisoner under guard doesn't get to pick up a rifle; out of his sight, it's an escape."""
        g = self.game
        p = g.player
        if p.state != "captive":
            return False
        pw = g.__dict__.get("pow") or {}
        guard = next((a for a in g.actors if a.id == pw.get("guard") and a.active), None)
        if guard is not None and max(abs(guard.x - p.x), abs(guard.y - p.y)) <= 10 and \
                g.map.visible[guard.x, guard.y]:
            g.msg("The guard's rifle is on you. Not now.", "warn")
            return True
        # nobody watching: this is the escape
        p.state = "ok"
        g.pow = None
        g.msg("You're armed again - and a prisoner no longer, if you can get away with it.", "warn")
        return False

    def begin_target(self, mg=False):
        g = self.game
        p = g.player
        if self.captive_blocks():
            return
        if p.vehicle is not None and p.vehicle.vt.aa and p.vehicle.player_crewed:
            from . import aboard as AB
            tg = AB.aa_targets(g, p.vehicle)
            if tg:
                opts = []
                for ac, d in tg[:8]:
                    how = {"dive": "diving", "strafe": "strafing", "bomb": "bombing", "torpedo": "torpedo run",
                           "kamikaze": "COMING STRAIGHT IN"}.get(getattr(ac, "kind", ac.mode), ac.mode)
                    opts.append((f"{ac.at.name} - {how}, {int(d * 2)} m", ac, (250, 170, 120), True))
                self.open_popup(Popup("Fire at", opts, self._screen_anchor()),
                                lambda ac: self.act(AB.fire_aa(g, p, p.vehicle, ac)) if ac is not None else None)
                return
        if not mg and g.support is not None and g.support.fires.player_mission(g) is not None and \
                not self.visible_targets():
            return self._fire_mission_round()          # nothing to shoot at here: f fires the mission
        if p.vehicle is not None:
            v = p.vehicle
            if not v.player_crewed:
                g.msg("You can't fire from here.", "info")
                return
            from . import crew as C
            ok, why = C.can(v, "mg" if mg else "main")
            if not ok:
                g.msg(why + " (e to change seats)", "info")
                return
        else:
            w = p.weapon
            if w is None or w.t.kind != "gun":
                g.msg("You have nothing to shoot with. (w to wield something)", "info")
                return
            if w.jammed:
                g.msg(f"Your {w.t.name} is jammed! (r to clear it)", "warn")
                return
            if w.loaded <= 0 and w.t.cat not in ("mortar",):
                if p.ammo_for(w) is not None:
                    return self.cmd_reload()
                g.msg(f"Your {w.t.name} is empty and you have nothing to load it with.", "warn")
                return
        self.target_list = self.visible_targets()
        self.target_idx = 0
        if self.target_list:
            t = self.target_list[0]
            cur = (t.x, t.y)
        else:
            ox, oy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
            cur = (ox, oy)
        self.enter_mode("target", cur, {"mg": mg})

    def cycle_target(self, d):
        if not self.target_list:
            self.target_list = self.visible_targets()
        if not self.target_list:
            return
        self.target_idx = (self.target_idx + d) % len(self.target_list)
        t = self.target_list[self.target_idx]
        self.cursor = (t.x, t.y)

    def _aim_lines(self, w, tgt, x, y):
        """How good your aim is on him, what another moment would buy, and what it costs."""
        from .combat import AIM_WORD, aim_level, aim_time, max_aim
        g = self.game
        p = g.player
        out = []
        lvl = aim_level(p, x, y)
        mx = max_aim(p, w.t)
        spd = max(1, p.speed())
        shot = (w.t.burst_cost if w.mode_name == "auto" else w.t.shot_cost) / spd
        if lvl < mx:
            keep = (p.aim_target, p.aim_turns)
            p.aim_target, p.aim_turns = (x, y), lvl + 1
            nxt = estimate_hit(g, p, w, tgt)
            p.aim_target, p.aim_turns = (x, y), mx
            best = estimate_hit(g, p, w, tgt)
            p.aim_target, p.aim_turns = keep
            t1 = aim_time(p, w.t) / spd
            num = self.app.show_numbers
            out.append((f"{AIM_WORD[lvl].capitalize()} - f fires ({shot:.1f}s)", (200, 210, 170)))
            out.append((f"a: {AIM_WORD[lvl + 1]}" + (f" ~{int(nxt * 100)}%" if num else "") + f" (+{t1:.1f}s)",
                        UI_DIM))
            if mx > lvl + 1:
                out.append((f"A: {AIM_WORD[mx]}, then fire" + (f" ~{int(best * 100)}%" if num else "")
                            + f" ({t1 * (mx - lvl) + shot:.1f}s)", UI_DIM))
        else:
            out.append((f"{AIM_WORD[lvl].capitalize()} - the best you'll get. f fires ({shot:.1f}s)", (170, 230, 150)))
        if p.recoil > 0.35:
            out.append(("The muzzle's still coming down from the last shot.", (230, 170, 90)))
        return out

    def aim(self, then_fire=False):
        """Take another moment over the sights (or all you need, then fire)."""
        from .combat import AIM_WORD, aim_level, aim_time, max_aim
        g = self.game
        p = g.player
        if self.cursor is None:
            return
        w = p.weapon
        if p.vehicle is not None or w is None or w.t.kind != "gun":
            return
        cur = self.cursor
        mx = max_aim(p, w.t)
        tgt = g.soldier_at.get(cur) or g.vehicle_at.get(cur)
        while True:
            lvl = aim_level(p, *cur)
            if lvl >= mx:
                if not then_fire:
                    g.msg("You have the best aim you'll get.", "info")
                break
            p.aim_target, p.aim_turns = cur, lvl + 1
            hp0 = sum(p.body.hp.values())
            sup0 = p.suppression
            self.act(aim_time(p, w.t))
            if not p.alive or not p.body.conscious:
                return
            self.mode, self.cursor = "target", cur
            if tgt is not None and getattr(tgt, "vt", None) is None:
                if not tgt.alive or (tgt.x, tgt.y) != cur:
                    if tgt.alive and max(abs(tgt.x - cur[0]), abs(tgt.y - cur[1])) <= 1:
                        cur = (tgt.x, tgt.y)           # follow him the step he took
                        self.cursor = cur
                    else:
                        g.msg("He's gone from your sights.", "warn")
                        return
            if sum(p.body.hp.values()) < hp0 or p.suppression > sup0 + 25:
                g.msg("You flinch - the sight picture's gone.", "warn")
                return
            if not then_fire:
                g.msg({1: "You bring the sights onto him.", 2: "You settle your breathing and take careful aim.",
                       3: "You let half a breath out and hold it.", 4: "The crosshairs sit dead still."}
                      .get(p.aim_turns, "You aim."), "info")
                return
        if then_fire:
            self.mode, self.cursor = "normal", None
            return self.fire_at(cur[0], cur[1], self.pending or {})

    def fire_at(self, x, y, pend):
        g = self.game
        p = g.player
        if p.vehicle is not None:
            v = p.vehicle
            if (x, y) in v.cells():
                return
            return self._crew_fire(v, x, y, bool(pend.get("mg")))
        w = p.weapon
        if (x, y) == (p.x, p.y):
            return
        tgt = g.soldier_at.get((x, y)) or g.vehicle_at.get((x, y))
        if tgt is not None and getattr(tgt, "side", None) == p.side and getattr(tgt, "vt", None) is None:
            g.msg("That's one of ours!", "warn")
            return
        if w.t.cat == "mortar":
            d = math.hypot(x - p.x, y - p.y)
            if d < w.t.min_rng:
                g.msg("Too close for the mortar - you'd drop it on yourself.", "warn")
                return
            if d > w.t.rng:
                g.msg("Out of the mortar's range.", "warn")
                return
            if p.ammo_for(w) is None:
                g.msg("No bombs left.", "warn")
                return
        cost = A.fire(g, p, x, y, tgt)
        if cost:
            if w.t.cat in ("lmg", "hmg") and p.stance != 2 and not p.deployed:
                g.msg("Firing the gun from the hip, you spray rounds everywhere.", "info")
            return self.act(cost)

    # ================================================================== commands
    def zoom(self, steps, at_mouse=True):
        """Zoom about a point: the tile under the mouse (if it's over the battlefield), else the look/aim
        cursor, else the middle of the view.  That tile stays where it is on screen."""
        gfx = getattr(self.app, "gfx", None)
        if gfx is None:
            return
        cam = self.cam
        tx0, ty0 = gfx.map_scale()
        mx, my = getattr(self, "mouse_txt", (-1, -1))
        fx0 = cam.fx0 if cam.fx0 is not None else cam.x0
        fy0 = cam.fy0 if cam.fy0 is not None else cam.y0
        if at_mouse and 0 <= mx < VIEW_W and 0 <= my < VIEW_H:
            ftx, fty = mx, my
        elif self.mode in self.CURSOR_MODES and self.cursor and cam.on_screen(*self.cursor):
            ftx = (self.cursor[0] - fx0 + 0.5) * tx0
            fty = (self.cursor[1] - fy0 + 0.5) * ty0
        else:
            ftx, fty = VIEW_W / 2, VIEW_H / 2
        wx, wy = fx0 + ftx / tx0, fy0 + fty / ty0          # the world point under the anchor
        gfx.zoom_step(steps)
        tx1, ty1 = gfx.map_scale()
        wv, hv = VIEW_W / tx1, VIEW_H / ty1
        c = (wx - ftx / tx1 + wv / 2, wy - fty / ty1 + hv / 2)
        self.view_center = c
        self.cam_c = list(c)                                 # a zoom doesn't glide: the point stays put
        self.cam_target = list(c)
        p = self.game.player
        self._view_pos = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        self._cam_locked = False
        self._zoom_note = (time.monotonic(), gfx.zoom_value())

    def cycle_mode(self):
        g = self.game
        p = g.player
        if p.vehicle is not None and p.vehicle.player_crewed:
            from . import crew as C
            v = p.vehicle
            ok, why = C.can(v, "ammo")
            if not ok:
                g.msg(why, "info")
                return
            v.ammo_choice = "he" if v.ammo_choice == "ap" else "ap"
            rnd = "HE" if v.ammo_choice == "he" else "AP"
            g.msg(f"'{rnd}, load!'" if C.player_seat(v) != "loader" else f"You heave an {rnd} round into the rack.",
                  "info")
            return
        m = A.cycle_mode(p)
        if m:
            g.msg(f"You switch to {m}.", "info")

    def cmd_reload(self):
        g = self.game
        p = g.player
        if p.vehicle is not None and p.vehicle.player_crewed:
            from . import crew as C
            v = p.vehicle
            if C.player_seat(v) == "loader" or (C.player_seat(v) == "gunner" and not C.is_manned(v, "loader")):
                if not v.gun_ok:
                    g.msg("The gun's knocked out - there's nothing to load.", "warn")
                    return
                if v.ap + v.he <= 0 and not (v.mount and v.mount.flame):
                    g.msg("The racks are empty. Not a round left.", "warn")
                    return
                if v.reload <= 0:
                    g.msg("The gun's loaded.", "info")
                    return
                v.reload = max(0, v.reload - 120)
                g.msg("You ram the round home. 'Up!'" if v.reload <= 0 else "You wrestle the next round out of the rack.",
                      "info")
                return self.act(100)
            g.msg("That's the loader's job.", "info")
            return
        w = p.weapon
        if w is None or w.t.kind != "gun":
            g.msg("Nothing to reload.", "info")
            return
        if w.jammed:
            return self.act(A.unjam(g, p))
        if w.t.cat in ("at_disposable",):
            g.msg("It's a single-shot tube. Throw it away when it's spent.", "info")
            return
        if w.loaded >= w.t.mag:
            if not w.known_rounds:
                w.known_rounds = True
                g.msg(f"You check: {w.loaded} rounds.", "info")
                return self.act(100)
            g.msg("It's fully loaded.", "info")
            return
        c = A.reload(g, p)
        if c is None:
            g.msg(f"You have no ammunition for your {w.t.name}.", "warn")
            return
        g.msg(f"You reload the {w.t.name}.", "info")
        self.act(c)

    def cmd_crouch(self):
        g = self.game
        p = g.player
        if p.vehicle is not None:
            g.msg("You're inside the " + p.vehicle.vt.name + ".", "info")
            return
        c = A.set_stance(g, p, 0 if p.stance == 1 else 1)
        if c:
            g.msg({0: "You stand up.", 1: "You crouch.", 2: "You drop prone."}[p.stance], "info")
            self.act(c)

    def cmd_prone(self):
        g = self.game
        p = g.player
        if p.vehicle is not None:
            g.msg("You're inside the " + p.vehicle.vt.name + ".", "info")
            return
        if p.stance != 2 and g.map.water[p.x, p.y] >= 1:
            g.msg("Lie down in the water and you'll drown.", "info")
            return
        c = A.set_stance(g, p, 1 if p.stance == 2 else 2)
        if c:
            g.msg({0: "You stand up.", 1: "You get up into a crouch.", 2: "You hit the dirt."}[p.stance], "info")
            self.act(c)

    def cmd_peek(self):
        g = self.game
        p = g.player
        if p.vehicle is not None:
            g.msg("You can't lean out of a vehicle.", "info")
            return
        if getattr(p, "peek", None):
            A.unpeek(g, p)
            g.msg("You pull back into cover.", "info")
            return self.act(30)
        self.enter_mode("peek", (p.x, p.y))

    def _wounded_near(self):
        """Comrades within reach who need patching up, the worst first."""
        g = self.game
        out = []
        for a in self._adjacent_friends():
            b = a.body
            need = b.bleed_rate() * 10 + (40 if a.downed else 0) + max(0, b.effective_pain() - 60) / 2
            if need > 1 or b.worst_wound() is not None:
                out.append((need, a))
        out.sort(key=lambda e: -e[0])
        return [a for _, a in out]

    def _hurt_words(self, a):
        b = a.body
        w = b.worst_wound()
        where = w.part.replace("l_", "left ").replace("r_", "right ") if w is not None else ""
        bleed = b.bleed_rate()
        how = "bleeding out" if bleed > 5 else "bleeding badly" if bleed > 1.5 else "bleeding" if bleed > 0.3 else \
            "down" if a.downed else "hurt"
        return f"{how}{', ' + where if where else ''}"

    def cmd_bandage(self):
        g = self.game
        p = g.player
        if p.carrying is not None:
            opts = [(f"Put {g.name_of(p.carrying)} down", "down", None, True)]
            from . import medical as MED
            if MED.at_aid_post(g, p):
                opts.insert(0, (f"Lay him on a cot here", "cot", (200, 220, 160), True))
            self.open_popup(Popup("Carrying", opts, self._screen_anchor()), self._carry_choice)
            return
        others = self._wounded_near()
        if others:
            mine = p.body.worst_wound() is not None or p.body.bleed_rate() > 0
            opts = []
            if mine:
                opts.append((f"Yourself ({self._hurt_words(p)})", p, (240, 200, 120), True))
            for a in others:
                opts.append((f"{g.name_of(a)} - {self._hurt_words(a)}", a, (240, 120, 100) if a.downed else None, True))
            self.open_popup(Popup("Patch up who?", opts, self._screen_anchor()), self._patch_menu)
            return
        self._patch_up(p)

    def _prisoner(self, who, what):
        """A prisoner of yours: search him, tell him what to do, patch him up, hand him on."""
        g = self.game
        p = g.player
        from . import prisoners as PW
        if what == "take_wounded":
            g.surrender(who)
            if who.state != "surrendered":
                return
            who.ai["captor"] = p.id
            g.duty.good["prisoner"] += 1
            g.msg(f"{cap(g.name_of(who))} lets go of his rifle. He's yours - and he can't walk.", "good")
            return self.act(80)
        if what == "patch_enemy":
            return self._patch_menu(who)
        if what == "prisoner":
            searched = who.ai.get("searched")
            opts = []
            if not searched:
                opts.append(("Search and disarm him (most of a minute)", "search", (200, 220, 150), True))
            order = who.ai.get("pw_order", "follow")
            opts += [("Follow me" + (" (now)" if order == "follow" else ""), "follow", None, True),
                     ("Sit down and wait here" + (" (now)" if order == "stay" else ""), "stay", None, True),
                     ("Walk back to our lines on your own", "rear", None, True)]
            near = [o for o in g.actors if o.side == p.side and o.active and not o.is_player and
                    max(abs(o.x - p.x), abs(o.y - p.y)) <= 6]
            opts.append(("Hand him over to a comrade to take back", "handover", None, bool(near)))
            if who.downed:
                opts.append(("Carry him", "carry", None, p.carrying is None))
            lines = [(f"{'Searched' if searched else 'Not searched yet - watch his hands'}. "
                      f"{'Wounded. ' if who.body.worst_wound() is not None else ''}"
                      f"Bring him within sight of our rear, or to a command post, aid post or depot.", UI_DIM)]
            self.open_popup(Popup(f"Prisoner: {g.name_of(who)}", opts, self._screen_anchor(), lines=lines),
                            lambda v: self._prisoner_order(who, v))

    def _prisoner_order(self, who, v):
        g = self.game
        p = g.player
        from . import prisoners as PW
        if v is None or not who.alive or who.state != "surrendered":
            return
        if v == "search":
            cost, text = PW.search(g, p, who)
            g.msg(text, "info")
            if p.stance == 0:
                p.stance = 1
            return self.act(cost * 100) if cost else None       # seconds of kneeling beside him
        if v in ("follow", "stay", "rear"):
            who.ai["pw_order"] = v
            who.say({"follow": "Ja, ja...", "stay": "...", "rear": "..."}.get(v, "...") if who.nation == "germany" else "",
                    g.turn, 2)
            g.msg({"follow": "You wave him along behind you.", "stay": "You push him down: 'Sit. Stay.'",
                   "rear": "You point him back toward our lines and give him a shove. He goes - for now."}[v], "info")
            return self.act(50)
        if v == "handover":
            o = PW.hand_over(g, p, who)
            if o is None:
                g.msg("There's nobody near enough to hand him to.", "info")
                return
            o.say({"usa": "I got him.", "uk": "Right, come on, you."}.get(o.nation, ""), g.turn, 2)
            g.msg(f"You hand {g.name_of(who)} over to {o.rank_short} {o.last_name}, who marches him off to the rear.",
                  "info")
            return self.act(80)
        if v == "carry":
            c = A.pick_up(g, p, who)
            if c:
                g.msg(f"You haul {g.name_of(who)} over your shoulder.", "info")
                return self.act(c)

    def _give(self, who, what):
        g = self.game
        p = g.player
        if what == "take_prisoner":
            who.ai["captor"] = p.id
            who.ai.setdefault("pw_order", "follow")
            g.duty.good["prisoner"] += 1
            g.duty.rep += 2
            g.command.merit += 1
            g.msg(f"You take {g.name_of(who)} prisoner. He'll follow you - search him, and bring him back to our "
                  f"lines. (right-click him for more)", "good")
            return self.act(80)
        if what == "give_ammo":
            from .ammo import hand_over
            n = hand_over(g, p, who, who.weapon)
            g.msg(f"You pass {g.name_of(who)} {n} lot{'s' if n != 1 else ''} of ammunition." if n else
                  "You've nothing that fits his weapon.", "good" if n else "info")
            return self.act(120) if n else None
        if what == "give_dressing":
            src = p.find(lambda i: i.tid == "bandage") or p.medical("bandage")
            if src is None:
                return
            if src.tid != "bandage" and src.t.kind == "medical" and src.uses > 1:
                from .entities import Item as _Item
                src.uses -= 1
                it = _Item("bandage")
            else:
                it = p.remove_item(src, 1)
            if who.add_item(it) is None:
                g.map.add_item(who.x, who.y, it)
            g.msg(f"You give {g.name_of(who)} a field dressing.", "info")
            g.duty.rep += 0.5
            return self.act(60)
        if what == "give_grenade":
            gr = p.grenades()[0]
            it = p.remove_item(gr, 1)
            if who.add_item(it) is None:
                g.map.add_item(who.x, who.y, it)
            g.msg(f"You hand {g.name_of(who)} a {it.t.name}.", "info")
            g.duty.rep += 0.5
            return self.act(60)
        if what == "give_smoke":
            cig = p.find(lambda i: i.t.tool == "cigarettes")
            p.remove_item(cig, 1)
            who.morale = min(100.0, who.morale + 10)
            g.duty.rep += 1
            who.say(g.rng.choice(["Thanks, pal.", "God bless you.", "Lifesaver."]) if who.nation in (
                "usa", "uk", "canada", "australia", "newzealand") else "", g.turn, tone="talk")
            g.msg(f"You light a cigarette for {g.name_of(who)}. His hands stop shaking a little.", "info")
            return self.act(90)

    def _carry_choice(self, what):
        from . import medical as MED
        g = self.game
        p = g.player
        c = p.carrying
        if c is None:
            return
        if what == "cot":
            spot = MED.cot_near(g, p.x, p.y, 6)
            A.put_down(g, p, spot)
            c.ai["at_aid"] = g.turn
            c.ai["to_aid"] = g.turn
            g.msg(f"You lay {g.name_of(c)} on a cot. The orderlies take over.", "good")
            g.command.merit += 1.0
            if hasattr(g, "duty"):
                g.duty.good_deed(g, "rescue", c)
        else:
            A.put_down(g, p)
            g.msg(f"You set {g.name_of(c)} down.", "info")
        self.act(100)

    def _patch_menu(self, who):
        """What you can do for him depends on what you know."""
        from . import medical as MED
        g = self.game
        p = g.player
        if who is p:
            return self._patch_up(p)
        s = MED.skill(p)
        opts = []
        if MED.can_help(g, p, who):
            opts.append((f"Treat him ({MED.skill_name(s)})", "treat", None, True))
        if s >= MED.SURGEON and MED.at_aid_post(g, p) and MED.needs_surgery(who.body):
            t = MED.surgery_time(who.body)
            opts.append((f"Operate (about {max(10, t // 60)} minutes)", "operate", (230, 200, 140), True))
        if who.downed and p.carrying is None and p.vehicle is None:
            opts.append(("Carry him out (to the aid station, or to cover)", "carry", None, True))
        if who.body.wounds or who.body.effective_pain() > 50:
            # a dressing lying there, the dead man's morphine: what's within reach will do as well as your own
            for i, pos, h in self.within_reach():
                if i.t.kind == "medical" and max(abs(pos[0] - who.x), abs(pos[1] - who.y)) <= 2:
                    opts.append((f"Use the {i.name} {'on the dead man' if h is not None else 'lying there'} on him",
                                 ("near", i, pos, h), (240, 200, 120), True))
                    if len(opts) > 8:
                        break
        if not opts:
            g.msg("You've nothing on you that would help him.", "warn")
            return
        if len(opts) == 1 and opts[0][1] == "treat":
            return self._patch_up(who)
        self.open_popup(Popup(g.name_of(who), opts, self._screen_anchor()), lambda v: self._patch_do(who, v))

    def _patch_do(self, who, what):
        from . import medical as MED
        g = self.game
        p = g.player
        if isinstance(what, tuple) and what[0] == "near":
            _k, it, pos, h = what
            return self.use_where_it_lies(it, pos, h, "other", who)
        if what == "treat":
            return self._patch_up(who)
        if what == "carry":
            c = A.pick_up(g, p, who)
            if c is None:
                g.msg("You can't get a grip on him from here.", "info")
                return
            post = MED.nearest_aid(g, p)
            if post is not None:
                from .senses import direction_word
                g.msg(f"The aid station is {direction_word(post[0] - p.x, post[1] - p.y)} of you. (B to put him down)",
                      "info")
            return self.act(c)
        if what == "operate":
            t = MED.begin_surgery(g, p, who)
            if t is None:
                return
            g.msg("You scrub your hands in a basin of pink water and open him up. (moving or any key stops you)",
                  "info")
            self.auto_wait = t
            self.mark_interrupt()
            return self.act(100)

    def _patch_up(self, who):
        from . import medical as MED
        g = self.game
        p = g.player
        if who is not p:
            c = MED.first_aid(g, p, who)
            if c is None:
                g.msg("You've nothing on you that would help.", "warn")
                return
            if who.alive and g.rng.random() < 0.5:
                who.say(g.rng.choice(["Thanks...", "Christ, that hurts.", "Am I gonna make it?", "Don't leave me."])
                        if p.nation in ("usa", "uk", "canada", "australia", "newzealand") else "", g.turn, tone="talk")
            g.command.merit += 0.5
            if hasattr(g, "duty"):
                g.duty.good_deed(g, "patched", who)
            return self.act(c)
        c = MED.first_aid(g, p, p) if MED.skill(p) >= MED.MEDIC else None
        if c is not None:
            return self.act(c)
        c = A.treat(g, p, p)
        if c is None:
            if p.body.arms_ok() == 0:
                g.msg("Neither arm will do what you tell it. You can't treat yourself - shout for a medic (Y).",
                      "warn")
            elif p.body.worst_wound() is None and p.body.effective_pain() < 70:
                g.msg("You don't need patching up. Not yet.", "info")
            else:
                g.msg("You have nothing to treat yourself with.", "warn")
            return
        self.act(c)

    def cmd_pace(self):
        """Creep, walk, run, sprint."""
        from .pace import PACES, allowed, effective
        g = self.game
        p = g.player
        if p.vehicle is not None:
            g.msg("Your pace is the vehicle's. (Get out to walk.)", "info")
            return
        cur = getattr(p, "pace", "walk")
        nxt = PACES[(PACES.index(cur) + 1) % len(PACES)] if cur in PACES else "walk"
        p.pace = nxt
        real = effective(p, nxt, g.turn)
        if real != nxt:
            why = "you're lying down" if p.stance == 2 else "crouched, the best you can do is a run" if p.stance == 1 \
                else "your legs won't have it" if allowed(p, g.turn) != "sprint" else "you've no breath for it"
            g.msg(f"You'll {nxt} when you can - {why}.", "info")
        else:
            g.msg({"walk": "You slow to a walk.", "run": "You break into a run.",
                   "sprint": "You'll sprint - flat out, for as long as your lungs last.",
                   "sneak": "You creep: slow, quiet, placing each foot, using every fold of the ground."}[nxt],
                  "info")

    def cmd_staff(self):
        """The general staff: divisions, corps, the reserve."""
        g = self.game
        if g.command.strategic_reach(g) <= 0:
            g.msg("You don't command on that scale. (Colonels and above.)", "info")
            return
        from .opsui import OperationsState
        self.app.push(OperationsState(self.app, g, self))

    def wait_at_hq(self, turns):
        self.game.msg("You settle in at headquarters with the maps and the telephones.", "info")
        self.auto_wait = int(turns)
        self.mark_interrupt()

    def cmd_look(self):
        p = self.game.player
        self.enter_mode("look", (p.x, p.y))

    # ------------------------------------------------------------ V: everything around you
    def cmd_nearby(self, keep=None):
        """A list of everything you can see and hear, nearest first (Cataclysm's V)."""
        from . import nearby as NB
        g = self.game
        p = g.player
        lists = NB.gather(g)
        tab = keep[0] if keep else (0 if lists["Soldiers"] or not lists["Items"] else 1)
        self.nearby = dict(tab=tab, sel=0, lists=lists)
        if keep:
            ents = lists[NB.TABS[tab]]
            self.nearby["sel"] = next((i for i, e in enumerate(ents) if (e["x"], e["y"]) == keep[1]),
                                      min(keep[2], max(0, len(ents) - 1)))
        self.enter_mode("nearby", (p.x, p.y))
        self._nearby_cursor()

    def _nearby_entry(self):
        from .nearby import TABS
        st = self.nearby
        ents = st["lists"][TABS[st["tab"]]]
        return ents[st["sel"]] if ents and 0 <= st["sel"] < len(ents) else None

    def _nearby_cursor(self):
        e = self._nearby_entry()
        p = self.game.player
        self.cursor = (e["x"], e["y"]) if e else (p.x, p.y)
        if e and self.cam_c is not None:
            self.view_center = None                     # let the view follow the cursor to it

    def _nearby_key(self, key):
        from .nearby import TABS
        g = self.game
        p = g.player
        st = self.nearby
        ents = st["lists"][TABS[st["tab"]]]
        mv = key.move()
        c = key.char
        if key.sym == E.KeySym.ESCAPE or c in ("V", "q"):
            self.park_view()
            self.mode = "normal"
            self.cursor = None
            return
        if key.sym == E.KeySym.TAB or (mv and mv[1] == 0 and mv[0]):
            st["tab"] = 1 - st["tab"]
            st["sel"] = 0
            return self._nearby_cursor()
        if mv and mv[0] == 0 and ents:
            st["sel"] = (st["sel"] + mv[1] * (5 if key.is_run() else 1)) % len(ents)
            return self._nearby_cursor()
        if key.sym in (E.KeySym.PAGEUP, E.KeySym.PAGEDOWN) and ents:
            st["sel"] = max(0, min(len(ents) - 1, st["sel"] + (10 if key.sym == E.KeySym.PAGEDOWN else -10)))
            return self._nearby_cursor()
        e = self._nearby_entry()
        if c == "b":
            if not p.has_tool("binoculars"):
                g.msg("You don't have binoculars.", "info")
                return
            g.player_binoculars = not g.player_binoculars
            g.msg("You raise your binoculars." if g.player_binoculars else "You lower your binoculars.", "info")
            return self.cmd_nearby(keep=(st["tab"], (e["x"], e["y"]) if e else None, st["sel"]))
        if e is None:
            return
        if c in ("x", ";"):
            self.enter_mode("look", (e["x"], e["y"]))
            return
        enter = key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER)
        if st["tab"] == 0 and enter and e.get("heard") is not None:
            self.enter_mode("look", (e["x"], e["y"]))      # nothing to walk to: look where it came from
            return
        if st["tab"] == 0 and (c == "f" or (enter and e.get("enemy"))):
            self.mode = "normal"
            self.begin_target()
            if self.mode == "target":
                self.cursor = (e["x"], e["y"])
                for i, t in enumerate(self.target_list or []):
                    if (t.x, t.y) == (e["x"], e["y"]):
                        self.target_idx = i
            return
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER):
            self.mode = "normal"
            self.cursor = None
            self.recenter()
            if st["tab"] == 1:
                body = e.get("body")
                def collect():
                    if body is not None and body in g.map.items_at(e["x"], e["y"]):
                        self.cmd_inventory(focus_body=body)
                    else:
                        self.cmd_pickup()
                if (e["x"], e["y"]) == (p.x, p.y):
                    return collect()
                if not self.start_travel(e["x"], e["y"], then=collect):
                    g.msg("You can't see a way there.", "info")
                return
            if not self.start_travel(e["x"], e["y"], stop_short=1):
                g.msg("You can't see a way there.", "info")
            return

    def cmd_binoculars(self):
        g = self.game
        p = g.player
        if not p.has_tool("binoculars"):
            g.msg("You don't have binoculars.", "info")
            return
        g.player_binoculars = True
        g.msg("You raise your binoculars.", "info")
        self.enter_mode("look", (p.x, p.y))

    def cmd_rest(self):
        """z: wait a minute, watching (Z for longer)."""
        self.begin_wait("time", 60, quick=True)

    def cmd_overmap(self):
        from .ui import OvermapState
        self.app.push(OvermapState(self.app, self.game))

    def cmd_log(self):
        from .ui import LogState
        self.app.push(LogState(self.app, self.game))

    def cmd_help(self):
        """F1 / ?: how to play - opened at "Right now", the keys for where you are this moment."""
        from .ui import HelpState
        self.app.push(HelpState(self.app, play=self))

    def help_now(self):
        """The keys that matter where you are, for the help's first section: your seat, your orders, what's
        beside you, the mode you're in."""
        from . import crew as C
        from . import maintenance as MT
        from .base import TALKERS
        g = self.game
        p = g.player
        rows = []
        v = p.vehicle
        m = g.map
        # where you are
        if g.__dict__.get("domain") == "aboard":
            where = "Aboard your aircraft." if (g.aboard or {}).get("kind") == "plane" else "Aboard ship."
        elif v is not None:
            seat = C.player_seat(v)
            where = (f"In the {v.vt.name}: the {C.name(v.vt, seat).lower()}'s seat" if seat else
                     f"Riding on the {v.vt.name}'s hull" if riding(p) else f"A passenger in the {v.vt.name}")
            from .vdamage import damage_list, hatch_user
            if seat and seat == hatch_user(v):
                where += ", hatch shut" if v.buttoned else ", head out of the hatch"
            dmg = damage_list(v)
            where += "." + (f" Damage: {', '.join(dmg)}." if dmg else "")
        else:
            where = {0: "On your feet", 1: "Crouching", 2: "Lying flat"}.get(p.stance, "On foot") + \
                (", leaning out of cover." if getattr(p, "peek", None) else ".")
        rows.append(("t", where))
        # the mode you're in
        modes = {
            "target": [("f|t|Enter", "fire"), ("Tab|Shift+Tab", "next / previous target"),
                       ("a|A", "aim longer / aim fully and fire"), ("Esc", "stop aiming")],
            "throw": [("t|f|Enter", "throw"), ("c", f"cook it (now {self.cook} s)"), ("Esc", "don't")],
            "look": [("move keys", "move the cursor"), ("x|Esc", "done")],
            "nearby": [("up|down", "pick one"), ("Tab", "soldiers / items"), ("f|Enter", "fire / go to it"),
                       ("x|b", "look / binoculars"), ("Esc", "close")],
            "order_target": [("move keys", "pick the spot"), ("Enter", "order it"), ("Esc", "cancel")],
            "radio_target": [("move keys", "pick the target"), ("Enter", "call it in"), ("Esc", "cancel")],
            "flare_target": [("move keys", "pick the spot"), ("Enter", "fire the flare"), ("Esc", "cancel")],
            "peek": [("move keys", "which way to lean"), ("Esc", "don't")],
        }
        if self.mode in modes:
            rows.append(("h", "What you're doing"))
            rows += [("k", k, d) for k, d in modes[self.mode]]
        # your orders
        rows.append(("h", "Your orders"))
        plan = None
        try:
            plan = self._order_plan()
        except Exception:
            pass
        rows.append(("k", "Enter", plan[0] if plan else "(nothing to carry out just now)"))
        if g.support is not None and g.support.fires.player_mission(g) is not None:
            rows.append(("k", "f", "fire the mission's rounds (with nothing in sight to shoot at)"))
        # your seat
        if v is not None:
            rows.append(("h", "Your seat"))
            seat = C.player_seat(v)
            from .vdamage import hatch_user
            vt = v.vt
            gun = []
            if vt.main:
                gun.append(("f", "fire the main gun at what you can see" +
                            (" (the crew swing the trail round for you)" if vt.static else "")))
                if vt.ap and vt.he:
                    gun.append(("F", "AP or HE"))
                if vt.turret and not vt.static:
                    gun.append(("move keys", "traverse the turret"))
            if C.mgs_for(v, "gunner"):
                gun.append(("v", "the machine gun" if not vt.main else "the coaxial machine gun"))
            seat_keys = {
                "driver": [("move keys", "drive (off the map edge: on into the next sector)")],
                "gunner": gun,
                "loader": [("r", "hurry the next round"), ("F", "change the round")],
                "commander": [("move keys", "tell the driver where to go"), ("f", "give the gunner a target"),
                              ("v", "give the machine gunners a target")],
            }
            if seat is None:
                rows.append(("k", "e", "jump down" if riding(p) else "get out, or take an empty seat"))
            else:
                rows += [("k", k, d) for k, d in seat_keys.get(seat, [("v", "fire your machine gun")] if
                                                                 seat.startswith("mg") else [])]
                menu = ["get out", "change seats"]
                if seat == hatch_user(v):
                    menu.append("open your hatch" if v.buttoned else "button up")
                if seat == "commander":
                    menu.append("crew orders")
                rows.append(("k", "e", "the menu: " + ", ".join(menu)))
        # what's beside you
        near = []
        if v is None and m is not None:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    x, y = p.x + dx, p.y + dy
                    veh = g.vehicle_at.get((x, y))
                    if veh is not None and not veh.dead and veh not in [n[1] for n in near if n[0] == "veh"]:
                        near.append(("veh", veh))
                    a = g.soldier_at.get((x, y))
                    if a is not None and a is not p and a.side == p.side and a.alive:
                        near.append(("man", a))
            head = len(rows)
            for kind, o in near:
                if kind == "veh" and (o.side == p.side or o.abandoned or o.crew == 0):
                    extra = []
                    if o.side == p.side and MT.repairs(o):
                        extra.append("help fix it")
                    if MT.is_supply_truck(o):
                        extra.append("take a crate of shells")
                    rows.append(("k", "e", f"get into the {o.vt.name}"))
                    rows.append(("k", "right-click", f"the {o.vt.name}: " + (", ".join(extra) or "everything else")))
                elif kind == "man":
                    if o.role in TALKERS or o.role in ("quartermaster", "intel"):
                        rows.append(("k", "walk into", f"the {o.role_name.lower()}: talk to {o.him}"))
                    elif o.downed or o.body.bleed_rate() > 0.1:
                        rows.append(("k", "B|right-click", f"patch up {g.name_of(o)}"))
            if m.items_at(p.x, p.y):
                rows.append(("k", "g", "pick up what's here"))
            if p.carrying is not None:
                rows.append(("k", "B", f"put {g.name_of(p.carrying)} down"))
            if p.invent.hands is not None:
                rows.append(("k", "d|i", f"drop the {p.invent.hands.name} / put it away"))
            if len(rows) > head:
                rows.insert(head, ("h", "Beside you"))
        # danger
        enemies = g.seen_enemies()
        if enemies and v is None:
            rows.append(("h", "The enemy's in sight"))
            rows += [("k", "f|Tab", "aim and fire"), ("k", "c|p", "get low - prone behind cover is best"),
                     ("k", "q", "lean out of cover to shoot, and back"), ("k", "!|'", "safe mode off / ignore what you see")]
        if v is None and m is not None:
            t = m.tile(p.x, p.y).key
            if t == "stairs" or t == "trapdoor" or getattr(p, "z", 0):
                from .actions import floor_word
                rows.append(("h", f"On {floor_word(g, p)}" if getattr(p, "z", 0) else "Stairs"))
                if t == "stairs":
                    rows.append(("k", "<|>", "up a floor (see and shoot over the hedges) / down again"))
                if t == "trapdoor":
                    rows.append(("k", ">|<", "down into the cellar (shelter from the shells) / up again"))
                if getattr(p, "z", 0) > 0 and t != "stairs":
                    rows.append(("l", "the stairs", "are the only way down: walk back to them"))
        rows.append(("h", "Always"))
        rows += [("k", "V", "everything around you in a list"), ("k", "x", "look"), ("k", "i", "your kit"),
                 ("k", "@", "yourself: your body in detail"), ("k", "Esc", "the menu")]
        return rows

    def cmd_charsheet(self):
        from .ui import StatusState
        self.app.push(StatusState(self.app, self.game))

    def cmd_dig(self):
        g = self.game
        p = g.player
        if p.vehicle is not None:
            g.msg("Not from in there. Get out first.", "info")
            return
        c = A.dig(g, p)
        if c is None:
            if not p.has_tool("shovel"):
                g.msg("You have nothing to dig with.", "info")
            else:
                g.msg("You can't dig here.", "info")
            return
        if not self.__dict__.get("digging"):
            left = max(1, (60 - p.dig_progress) // (2 if g.map.climate != "winter" else 1))
            g.msg(f"You start digging in - about {left} seconds of work, if they let you. (any key stops)", "info")
        self.digging = True
        self.mark_interrupt()
        self.act(c)

    def cmd_resupply(self):
        g = self.game
        c = A.resupply(g, g.player)
        if c is None:
            carried = p = g.player
            if carried.find(lambda i: i.tid == "ammo_crate") is not None:
                g.msg("Put the crate down (d) and open it first.", "info")
            else:
                g.msg("There's no ammunition dump or crate within reach.", "info")
            return
        self.act(c)

    def cmd_door(self):
        g = self.game
        p = g.player
        m = g.map
        for dx, dy in DIRS8:
            x, y = p.x + dx, p.y + dy
            if m.in_bounds(x, y) and m.tile(x, y).key == "door_open" and (x, y) not in g.soldier_at:
                m.set(x, y, "door", refresh=True)
                g.msg("You close the door.", "info")
                return self.act(100)
        g.msg("No open door nearby.", "info")

    def cmd_vehicle(self):
        g = self.game
        p = g.player
        if p.vehicle is None and g.__dict__.get("domain") == "aboard":
            from . import aboard as AB
            r = AB.use_here(self)
            if r is not None or g.map.t[p.x, p.y] in (T.ID["hatch"], T.ID["ladder_up"], T.ID["ladder"]):
                return r
        if p.vehicle is not None:
            return self._vehicle_menu(p.vehicle)
        near = [v for v in g.vehicles if not v.dead and v.near(p.x, p.y) <= 1]
        if not near and self._parked_plane_near():
            return self._take_off_menu()
        if not near:
            g.msg("There's no vehicle or gun next to you.", "info")
            return
        if len(near) > 1:
            opts = []
            for v in near:
                why = self._why_not_enter(v)
                opts.append((f"{v.vt.name}" + (f" - {why}" if why else ""), v, None, why is None))
            self.open_popup(Popup("Get into which?", opts, self._screen_anchor()), self._enter_vehicle)
            return
        return self._enter_vehicle(near[0])

    def _why_not_enter(self, v):
        p = self.game.player
        if v.dead:
            return "wrecked"
        if v.side != p.side and not (v.abandoned or v.crew == 0):
            return "enemy crew inside"
        from .maintenance import riders_capacity
        cap = riders_capacity(v)
        if not (p.role == "tank_crew" or v.crew == 0 or v.abandoned) and len(v.passengers) >= cap:
            return "no room" if cap else "no room inside, and nowhere to hold on"
        if p.role == "tank_crew" and v.crew >= v.vt.crew and len(v.passengers) >= v.vt.seats:
            return "fully crewed"
        return None

    def _enter_vehicle(self, v):
        g = self.game
        p = g.player
        if v is None:
            return
        if p.carrying is not None:
            g.msg(f"Put {g.name_of(p.carrying)} down first (B).", "info")
            return
        if p.ai.get("carried_by") is not None:
            g.msg("You're on a stretcher. You're not getting into anything.", "info")
            return
        why = self._why_not_enter(v)
        c = A.enter_vehicle(g, p, v)
        if c is None:
            g.msg(f"You can't get into the {v.vt.name}" + (f": {why}." if why else "."), "warn")
            return
        if v.player_crewed:
            from . import crew as C
            seat = C.player_seat(v)
            g.msg(f"You take the {C.name(v.vt, seat).lower()}'s seat in the {v.vt.name}. {C.seat_help(v, seat)} "
                  f"(e: seats and exit)", "good")
        elif riding(p):
            g.msg(f"You climb up onto the {v.vt.name}'s engine deck and grab a handhold. It's warm, it's fast - and "
                  f"everything that shoots at it shoots at you. (e: get off)", "info")
        else:
            g.msg(f"You clamber into the {v.vt.name}. (e: get out)", "info")
        self.act(c)

    def _vehicle_menu(self, v):
        """Get out, change seats, or - from the commander's seat - tell the crew how to fight."""
        from . import crew as C
        g = self.game
        p = g.player
        seat = C.player_seat(v)
        opts = [((f"Jump down off the {v.vt.name}" if riding(p) else f"Climb out of the {v.vt.name}"),
                 ("exit", None), None, True)]
        man = C.manned(v)
        for st in C.stations(v.vt):
            if st == seat:
                continue
            who = "manned - you'll swap" if st in man else "empty"
            if seat is None:
                if st in man or v.crew >= v.vt.crew:
                    continue
                opts.append((f"Take the {C.name(v.vt, st).lower()}'s seat ({who})", ("seat", st), None, True))
            else:
                opts.append((f"Move to the {C.name(v.vt, st).lower()}'s seat ({who})", ("seat", st), None, True))
        from .vdamage import hatch_user
        if seat is not None and seat == hatch_user(v):
            opts.insert(1, ("Button up: hatch shut, eyes to the periscopes" if not v.buttoned else
                            "Open your hatch and put your head out: you'll see, and be seen", ("hatch", None),
                            (180, 200, 230), True))
        if v.ai.get("captured") and not v.ai.get("marked"):
            opts.append(("Paint our markings on it (a few minutes, outside)", ("paint", None), None, True))
        if seat == "commander":
            hold = v.ai.get("hold_fire")
            opts.append(("Crew: fire at will" if hold else "Crew: hold fire", ("hold", not hold), None, True))
            if v.ai.get("designated") is not None:
                opts.append(("Crew: cease fire on that target", ("undesignate", None), None, True))
            if v.vt.turret and v.vt.main:
                opts.append(("Gunner: traverse to the front", ("front", None), None, True))
        from .vdamage import damage_list
        lines = [(f"You are the {C.name(v.vt, seat).lower()}." if seat else "You're riding as a passenger.", UI_TEXT),
                 ("Crew: " + "  ".join(f"{C.SHORT.get(s, s)}{'*' if s == seat else '' if s in man else '-'}"
                                       for s in C.stations(v.vt)), UI_DIM)]
        dmg = damage_list(v)
        if dmg:
            lines.append(("Damage: " + ", ".join(dmg), (230, 150, 110)))
        self.open_popup(Popup(v.vt.name, opts, self._screen_anchor(), lines=lines, width=58),
                        lambda ch: self._vehicle_choice(v, ch))

    def _vehicle_choice(self, v, ch):
        from . import crew as C
        g = self.game
        p = g.player
        what, arg = ch
        if what == "exit":
            c = A.exit_vehicle(g, p)
            if c is None:
                g.msg("You can't get out here.", "warn")
                return
            g.msg(f"You climb out of the {v.vt.name}.", "info")
            return self.act(c)
        if what == "seat":
            if C.player_seat(v) is None:
                # a passenger takes an empty crew seat: the half-track's MG, the gun nobody's firing
                if p in v.passengers:
                    v.passengers.remove(p)
                v.crew += 1
                v.crew_actors.append(p)
                v.player_crewed = True
                v.abandoned = False
            swapped = arg in C.manned(v)
            v.player_station = arg
            g.msg(f"You squeeze into the {C.name(v.vt, arg).lower()}'s seat"
                  + (" and he takes yours" if swapped else "") + f". {C.seat_help(v, arg)}", "info")
            return self.act(150)
        if what == "paint":
            from .data.nations import NATIONS
            mark = {"usa": "big white stars", "uk": "white stars and red-white-blue roundels",
                    "ussr": "red stars and a slogan", "germany": "black crosses and a swastika flag over the deck",
                    "japan": "rising suns", "italy": "white crosses", "france": "tricolour roundels"}.get(
                p.nation, f"{NATIONS.get(p.nation, {}).get('adj', 'our')} markings")
            g.msg(f"You climb out with a tin of paint and daub {mark} on the {v.vt.name}, big enough to see a mile off.",
                  "info")
            self.act(9000)
            if p.alive:
                v.ai["marked"] = True
                g.brains[p.side].contacts.pop(v.id, None)
                g.msg("Done. Your own side should know it now - mostly.", "good")
            return
        if what == "hatch":
            v.buttoned = not v.buttoned
            g.msg("You drop down and pull the hatch shut. The world shrinks to the periscopes." if v.buttoned else
                  "You push the hatch open and stand up in the cupola. You can see - and anyone can see your head.",
                  "info")
            g.player_fov()
            return self.act(100)
        if what == "hold":
            v.ai["hold_fire"] = arg
            if arg:
                v.ai.pop("designated", None)
            p.say("Hold fire! Wait for my word." if arg else "Fire at will!", g.turn, 2)
            return self.act(20)
        if what == "undesignate":
            v.ai.pop("designated", None)
            p.say("Cease fire on that one.", g.turn, 2)
            return self.act(20)
        if what == "front":
            from . import vdamage as VD
            tr = VD.traverse(v)
            if tr == "jammed":
                g.msg("The turret ring's jammed: she won't traverse. Swing the hull to bring the gun round.", "warn")
                return
            steps = min((v.turret - v.facing) % 8, (v.facing - v.turret) % 8)
            v.turret = v.facing
            p.say("Gunner, traverse front.", g.turn, 2)
            if tr == "hand" and steps:
                g.msg("No power to the traverse: the gunner cranks her round by hand.", "info")
                return self.act(VD.HAND_TRAVERSE * steps)
            return self.act(30)

    def _parked_plane_near(self):
        g = self.game
        p = g.player
        from .parked import ids as ac_ids
        planes = ac_ids() | {T.ID["plane_parked"]}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = p.x + dx, p.y + dy
                if g.map.in_bounds(x, y) and int(g.map.t[x, y]) in planes:
                    return g.sector.control == p.side
        return False

    def _take_off_menu(self):
        """An aircraft on the flight line - and whatever the operations room has for you."""
        from .skysea_missions import AIR_MISSIONS, eligible_air
        g = self.game
        p = g.player
        flier = p.__dict__.get("service") == "air" or p.role in ("pilot", "fighter_pilot", "bomber_pilot")
        opts = [(AIR_MISSIONS[k].split(":")[0], k, None, True) for k in AIR_MISSIONS if eligible_air(g, k)]
        if not opts:
            g.msg("There's nothing here you could fly.", "info")
            return
        lines = [("The operations room has work for anyone who can fly." if flier else
                  "You've never flown anything. The ground crew stare at you.", UI_DIM if flier else (240, 150, 90))]
        self.open_popup(Popup("Take off", opts, self._screen_anchor(), lines=lines, width=60),
                        lambda k: self._take_off(k, flier))

    def _take_off(self, kind, flier):
        from .skysea_missions import launch_air
        g = self.game
        p = g.player
        ss = launch_air(g, kind)
        if ss is None:
            g.msg("There's nothing here you could fly for that.", "info")
            return
        if not flier:
            ss.player_plane.crew[0]["skill"] = 1.0
            if g.rng.random() < 0.35:
                ss.player_plane.hp["wing_l"] = 20
                g.msg("You bounce down the runway, wrench it into the air, and clip a tree. It flies. Just.", "warn")
        g.msg(f"You climb into the {ss.player_plane.name} and take off. {ss.mission['text']}", "good")

    def _to_the_fleet(self):
        from .skysea_missions import SEA_MISSIONS, eligible_sea, put_to_sea
        g = self.game
        opts = [(SEA_MISSIONS[k].split(":")[0], k, None, True) for k in SEA_MISSIONS if eligible_sea(g, k)]
        if not opts:
            g.msg("No ship of ours is anywhere near.", "info")
            return

        def go(k):
            ss = put_to_sea(g, k, station="aa gun" if g.player.rank < 8 else "bridge")
            if ss is not None:
                from . import aboard as AB
                g.msg(f"A boat takes you out to {ss.player_ship.name}. {ss.mission['text']}", "good")
                AB.board_ship(g, ss.player_ship)
                ss.station = "deck"
                self.recenter()
        self.open_popup(Popup("Out to the fleet", opts, self._screen_anchor(), width=60), go)

    def cmd_vehicle_mg(self):
        p = self.game.player
        if p.vehicle is not None and p.vehicle.player_crewed:
            self.begin_target(mg=True)
        else:
            self.game.msg("v fires a vehicle's machine gun - you're not crewing one.", "info")

    def cmd_yell(self):
        g = self.game
        p = g.player
        from .constants import other_side as _os
        enemy = _os(p.side)
        seen = [a for a in g.actors if a.side == enemy and a.alive and a.state == "ok" and
                max(abs(a.x - p.x), abs(a.y - p.y)) <= 12 and player_can_see_actor(g, a)]
        from .prisoners import HANDS_UP
        words = HANDS_UP.get(g.side_nation(enemy), "Hands up!")
        opts = [("Medic!", "medic", None, True), ("Need ammunition!", "ammo", None, True),
                ("Grenade!", "grenade", None, True),
                ("Covering fire!", "cover", None, True),
                (f"'{words}' (demand their surrender)", "demand", (200, 220, 150), bool(seen)),
                ("Don't shoot! (surrender)" + ("" if seen else " - nobody to surrender to"), "surrender",
                 (240, 120, 80), bool(seen))]
        self.open_popup(Popup("Shout", opts, self._screen_anchor()), self._yell)

    def _yell(self, what):
        g = self.game
        p = g.player
        if what == "demand":
            from .prisoners import demand_surrender
            n = demand_surrender(g, p)
            g.msg("You shout for them to give up." + (" Somebody out there is thinking about it." if n else ""), "info")
            return self.act(100)
        if what == "surrender":
            from .pow import begin_captivity
            g.msg("You throw down your weapon and raise your hands.", "warn")
            p.say(g.shout(p, "surrender"), g.turn, 4)
            res = begin_captivity(g)
            if res == "shot":
                p.body.cause = "a bullet through the head after surrendering"
                g.msg("He looks at you for a long moment. Then he raises his rifle.", "death")
                g.kill(p, None)                       # (a body like any other: the kit, the tile, succession)
                if g.game_over:
                    g.death_text = (f"{p.rank_full} {p.name}, {p.unit}. Shot after surrendering near "
                                    f"{g.sector.name}, {g.datetime_str(exact=True)}.")
                self.check_over()
                return
            g.player_orders = "You're a prisoner. Keep up with the guard - or run, and take your chances."
            return self.act(100)
        text = {"medic": g.shout(p, "medic"), "ammo": "Need ammunition!",
                "grenade": g.shout(p, "grenade"), "cover": "Covering fire!"}[what]
        p.say(text, g.turn, voice=self._native_order("suppress") if what == "cover" else None,
              tone="scream" if what == "medic" else None)
        g.msg(f"You shout: '{text}'", "shout")
        g.emit_sound(p.x, p.y, 55, "scream", text, p.side, p)
        if what == "cover" and p.squad:
            for m in p.squad.members:
                if m is not p and m.active:
                    m.suppression = max(0, m.suppression - 10)
                    m.ai["cover_for"] = g.turn + 20       # (they fire on what they know of the enemy)
        if what == "medic":
            p.ai["medic_call"] = g.turn
        elif what == "ammo":
            p.ai["ammo_call"] = g.turn
        self.act(50)

    # ---------------------------------------------------------------- inventory
    def _item_color(self, it):
        return it.t.color if it.t.kind not in ("ammo",) else (190, 175, 110)

    def cmd_inventory(self, focus_body=None):
        from .invui import InventoryScreen, loot_sources_at
        g = self.game
        p = g.player
        if p.vehicle is not None:
            g.msg("There's no room to go through your kit in here.", "info")
            return
        srcs = loot_sources_at(g, p.x, p.y, reach=1)
        if p.state == "captive":
            pw = g.__dict__.get("pow") or {}
            guard = next((a for a in g.actors if a.id == pw.get("guard") and a.active), None)
            if guard is not None and max(abs(guard.x - p.x), abs(guard.y - p.y)) <= 10:
                srcs = []                        # under the guard's eye you keep your hands to yourself
        self.inv_screen = InventoryScreen(self, srcs)
        if focus_body is not None:
            for k, pane in enumerate(srcs):
                if pane.inv is not None and pane.inv is focus_body.data.get("inv"):
                    self.inv_screen.src_idx = k
        if self.app.audio is not None:
            self.app.audio.ui("rustle")

    def _tool_verb(self, tool):
        return {"shovel": "Dig in here", "wirecutters": "Cut wire", "binoculars": "Look through them",
                "radio": "Get on the radio", "flaregun": "Fire a flare", "compass": "Check your bearings",
                "watch": "Check the time", "map": "Study the map", "orders": "Read your orders",
                "canteen": "Take a drink", "flask": "Take a swig", "cigarettes": "Light one up",
                "ration": "Eat something", "letter": "Read the letter", "photo": "Look at the photograph",
                "harmonica": "Play something", "rosary": "Pray", "bible": "Read a verse", "coin": "Flip it",
                "cards": "Shuffle the deck", "whistle": "Blow the whistle", "ammo_crate": "Resupply",
                "sandbags": "Fill and stack them", "wire": "String the wire", "detector": "Sweep for mines",
                "wireless": "Set up the wireless", "camera": "Take a photograph", "torch": "Lay out the lights",
                "sphone": "Talk to the aircraft", "time_pencil": "Check the time pencils", "money": "Count it",
                "cover_papers": "Go over your cover", "papers": "Go over your cover", "code": "Check the pad",
                "film": "Look at it", "trade": "Handle it"}.get(tool, "Use it")

    def _adjacent_friends(self):
        g = self.game
        p = g.player
        out = []
        for dx, dy in DIRS8:
            a = g.soldier_at.get((p.x + dx, p.y + dy))
            if a is not None and a.side == p.side and a.alive:
                out.append(a)
        return out

    def item_action(self, it, act):
        g = self.game
        p = g.player
        t = it.t
        if act == "wield":
            c = A.wield(g, p, it)
            if c is None:
                g.msg("Your hands are full, and there's nowhere to put what you're holding.", "info")
                return
            g.msg(f"You take the {t.name} in hand.", "info")
            return self.act(c)
        if act == "reload":
            return self.cmd_reload()
        if act == "count":
            it.known_rounds = True
            g.msg(f"You count {it.loaded} rounds.", "info")
            return self.act(100)
        if act == "unload":
            from .ammo import unload
            spill = unload(p, it)
            if spill is not None:
                g.map.add_item(p.x, p.y, spill)
            g.msg(f"You unload the {t.name}.", "info")
            return self.act(t.reload_cost // 2)
        if act == "mode":
            return self.cycle_mode()
        if act == "throw":
            self.cook = 0
            return self.enter_mode("throw", self._guess_throw_target(it), {"item": it})
        if act == "place":
            g.msg("Which way? (direction key)", "info")
            return self.enter_mode("place", (p.x, p.y), {"item": it})
        if act == "self":
            c = A.treat(g, p, p, it)
            if c is None:
                g.msg("That won't help right now.", "info")
                return
            return self.act(c)
        if act == "other":
            friends = self._adjacent_friends()
            if len(friends) == 1:
                return self._treat_other(friends[0], it)
            opts = [(f"{g.name_of(a)}", a, None, True) for a in friends]
            self.open_popup(Popup("Treat who?", opts, self._screen_anchor()), lambda a: self._treat_other(a, it))
            return
        if act == "use":
            return self.use_tool(it)
        if act == "wear":
            p.remove_item(it)
            p.helmet = it
            g.msg(f"You put on the {t.name}.", "info")
            from .actions import _enemy_helmet_warning
            _enemy_helmet_warning(g, p, it)
            return self.act(150)
        if act == "unwear":
            p.invent.slots["head"] = None
            placed = False
            for grid, loc in p.invent._grid_order(it, "pack"):
                spot = grid.find_spot(it)
                if spot is not None:
                    grid.place(it, *spot)
                    it.where = loc
                    placed = True
                    break
            if placed:
                g.msg(f"You take off the {t.name} and stow it.", "info")
            else:
                it.where = "ground"
                g.map.add_item(p.x, p.y, it)
                g.msg(f"You take off the {t.name}. There's no room for it, so you set it down.", "info")
            return self.act(100)
        if act == "examine":
            return self.examine(it)
        if act in ("drop", "drop1"):
            c = A.drop(g, p, it, 1 if act == "drop1" else None)
            g.msg(f"You drop the {t.name}.", "info")
            return self.act(c)

    def _treat_other(self, a, it):
        g = self.game
        c = A.treat(g, g.player, a, it)
        if c is None:
            g.msg("That won't help them right now.", "info")
            return
        self.act(c)

    def _guess_throw_target(self, it):
        ts = self.visible_targets()
        p = self.game.player
        rng = A.throw_range(p, it)
        for t in ts:
            if math.hypot(t.x - p.x, t.y - p.y) <= rng + 2:
                return (t.x, t.y)
        return (p.x, p.y)

    def examine(self, it):
        lines = self.examine_lines(it)
        self.open_popup(Popup(it.name, [("Close", None, None, True)], self._screen_anchor(), lines=lines,
                              width=58), lambda v: None)

    def examine_lines(self, it):
        """What you see when you look an item over: what it is, its story, and this one's particulars."""
        t = it.t
        lines = []
        import textwrap
        for l in textwrap.wrap(t.desc or "Nothing remarkable.", 52):
            lines.append((l, UI_TEXT))
        from .data.lore import LORE
        lore = LORE.get(t.id)
        if lore:
            lines.append(("", None))
            for l in textwrap.wrap(lore, 52):
                lines.append((l, (190, 180, 150)))
        fl = (it.data or {}).get("flavor")
        if fl:
            lines.append(("", None))
            for l in textwrap.wrap(("This one: " + fl) if t.kind == "gun" else fl, 52):
                lines.append((l, UI_HI))
        owner = (it.data or {}).get("owner")
        if owner and owner != self.game.player.name and t.kind != "corpse":
            lines.append((f"It was {owner}'s.", UI_DIM))
        if t.kind == "gun" and t.cat not in ("mortar",):
            lines.append(("", None))
            lines.append((f"Effective to {yards(t.rng)}.", UI_DIM))
            if t.mag > 1:
                cal = ITEMS['ammo_' + t.cal].name.replace(" rounds", "") if t.cal and 'ammo_' + t.cal in ITEMS else "?"
                lines.append((f"Holds {t.mag} rounds of {cal}.", UI_DIM))
            if "auto" in t.modes:
                lines.append(("Fires automatic bursts.", UI_DIM))
            if t.pen >= 20:
                lines.append(("Can punch through armour.", UI_DIM))
        if t.kind == "grenade":
            lines.append((f"Fuse about {t.fuse} seconds." if t.fuse > 1 else "Explodes on impact.", UI_DIM))
        if t.kind == "corpse" and it.data:
            d = it.data
            lines = [(f"{d.get('name', 'Unknown')}", UI_HI),
                     (f"{NATIONS[d['nation']]['adj']} {d.get('role', 'soldier').replace('_', ' ')}", UI_TEXT),
                     (f"Killed by {d.get('cause') or 'unknown causes'}.", UI_DIM)]
        lines.append((f"Weight {it.weight:.1f} kg.", UI_DIM))
        from .equipment import description
        for line in description(it):
            lines.extend((s, UI_DIM) for s in textwrap.wrap(line, 52))
        return lines

    def _personal_use(self, it):
        """A soldier's own things, used."""
        g = self.game
        if not it.functional:
            g.msg("It's broken and cannot be used.", "warn")
            return
        p = g.player
        t = it.t
        tool = t.tool
        rng = g.rng

        def used_one():
            it.uses -= 1
            if it.uses <= 0:
                p.remove_item(it)
        if tool == "stimulant":
            used_one()
            last = p.ai.get("stim_turn", -10 ** 9)
            p.ai["stim_turn"] = g.turn
            p.stamina = 100.0
            p.fatigue = max(0.0, getattr(p, "fatigue", 0) - 45)
            if g.turn - last < 3600:
                p.morale = max(0, p.morale - 6)
                p.suppression = min(100, p.suppression + 10)
                g.msg(f"Another {t.name.split()[-1]}. Your heart hammers and your hands won't keep still; the "
                      f"world has hard edges.", "warn")
            else:
                p.morale = min(100, p.morale + 6)
                g.msg("Twenty minutes later the tiredness is simply gone. Everything is very clear and very "
                      "important.", "info")
            return self.act(100)
        if tool == "chocolate":
            p.remove_item(it) if it.count <= 1 else p.remove_item(it, 1)
            p.morale = min(100, p.morale + 4)
            p.stamina = min(100.0, p.stamina + 10)
            g.msg(f"You eat the {t.name}. Sugar, and for a moment, somewhere else.", "info")
            return self.act(200)
        if tool == "gum":
            used_one()
            p.morale = min(100, p.morale + 1)
            p.suppression = max(0, p.suppression - 5)
            g.msg("You chew. It gives your jaw something to do besides clench.", "info")
            return self.act(30)
        if tool == "lighter":
            cig = p.find(lambda i: i.t.tool == "cigarettes")
            if cig is not None:
                return self.use_tool(cig)
            g.msg(f"You flick the {t.name}. It lights first time. Nothing to smoke.", "info")
            return self.act(20)
        if tool in ("charm", "flag", "medal", "ring"):
            mine = (it.data or {}).get("owner") in (None, p.name)
            if tool == "flag" and not mine:
                g.msg("You unfold the flag: a dead man's names, his family's wishes in ink. You fold it again.", "think")
            elif tool == "ring" and not mine:
                g.msg("Someone's wedding ring. " + ((it.data or {}).get("flavor") or "No inscription."), "think")
            elif tool == "medal" and not mine:
                g.msg("A souvenir now. You wonder what he did for it.", "think")
            else:
                p.morale = min(100, p.morale + 5)
                g.msg({"charm": "You touch it through your tunic. Still there.",
                       "flag": "You unfold it and read the names from home.",
                       "medal": "You look at it for a while. It doesn't say what it was really like.",
                       "ring": "You turn it on your finger. Home."}[tool], "think")
            return self.act(100)
        if tool == "shave":
            p.morale = min(100, p.morale + 3)
            g.msg("You shave in a mess tin of cold water. You look like a man again - an old one.", "info")
            return self.act(600)
        if tool == "sewing":
            g.msg("You sew a button back on and darn the worst of your socks.", "info")
            return self.act(600)
        g.msg(t.desc, "info")

    def use_tool(self, it):
        if not it.functional:
            self.game.msg("It's broken and cannot be used.", "warn")
            return
        g = self.game
        p = g.player
        tool = it.t.tool
        rng = g.rng
        if tool in ("antiseptic", "splint", "blanket", "gun_oil", "fuel", "repair", "spares"):
            from .sustain import use
            return use(self, it)
        if tool == "ci_log":
            from .counterintel import open_log
            return open_log(self)
        if tool == "shovel":
            return self.cmd_dig()
        if tool == "wirecutters":
            for dx, dy in DIRS8:
                x, y = p.x + dx, p.y + dy
                if g.map.in_bounds(x, y) and g.map.tile(x, y).key == "wire":
                    g.msg("You snip through the wire.", "info")
                    return self.act(A.cut_wire(g, p, x, y))
            g.msg("There's no wire within reach.", "info")
            return
        if tool == "binoculars":
            return self.cmd_binoculars()
        if tool == "radio":
            return self.cmd_radio()
        if tool in ("wireless", "sphone", "torch", "camera", "time_pencil", "code", "film", "money", "cover_papers",
                    "papers", "trade"):
            from . import agents as AG
            return AG.use_tool(self, it)
        if tool == "flaregun":
            if it.uses <= 0:
                g.msg("You're out of flares.", "warn")
                return
            return self.enter_mode("flare_target", (p.x, p.y))
        if tool == "compass":
            g.msg("North is up. Your squad's objective lies " + self._objective_hint() + ".", "info")
            return self.act(50)
        if tool == "watch":
            g.msg(f"It's {g.now().strftime('%H:%M')} on {g.now().strftime('%d %B %Y')}.", "info")
            return self.act(20)
        if tool == "map":
            return self.cmd_overmap()
        if tool == "orders":
            txt = (it.data or {}).get("text") or g.player_orders or "The pencil is smudged beyond reading."
            g.msg(f"Your orders: {txt}", "radio")
            return self.act(50)
        if tool in ("canteen", "flask"):
            g.msg("You take a drink." if tool == "canteen" else "The spirit burns going down. Better.", "info")
            return self.act(A.drink(g, p, it))
        if tool == "cigarettes":
            it.uses -= 1
            p.morale = min(100, p.morale + 6)
            p.suppression = max(0, p.suppression - 15)
            g.msg(f"You light a {NATIONS[p.nation]['cigs']}. Your hands stop shaking, a little.", "info")
            if it.uses <= 0:
                p.remove_item(it)
            if g.is_night():
                g.map.lights.append([p.x, p.y, 1, g.turn + 30])
            return self.act(300)
        if tool == "ration":
            needs = p.ai.setdefault("needs", dict(hunger=0., thirst=0., infection=0.))
            needs["hunger"] *= 1 - it.condition
            from .actions import _consume
            _consume(p, it)
            p.morale = min(100, p.morale + 3)
            g.msg(f"You wolf down a {NATIONS[p.nation]['ration']}.", "info")
            return self.act(400)
        if tool == "letter" and it.data and it.data.get("text"):
            g.msg(it.data["text"], "think")
            p.morale = min(100, p.morale + 5)
            return self.act(300)
        if tool == "photo" and it.data and it.data.get("text"):
            g.msg(it.data["text"], "think")
            p.morale = min(100, p.morale + 5)
            return self.act(200)
        if tool in ("newspaper", "document") and it.data and it.data.get("text"):
            g.msg(it.data["text"], "think")
            return self.act(300)
        if tool == "newspaper":
            from .flavor import headline
            g.msg(headline(g, it.tid), "think")
            return self.act(300)
        if tool in ("stimulant", "chocolate", "gum", "lighter", "charm", "flag", "medal", "shave", "sewing", "ring"):
            return self._personal_use(it)
        if tool in ("letter", "photo"):
            lines = {"letter": ["'...and the baby has your eyes. Come home to us.'", "'Mother says to keep your head down.'",
                                "'I'll wait for you. However long it takes.'", "'The harvest was good this year. We miss you.'"],
                     "photo": ["A girl squinting into the sun.", "Your family, stiff in their Sunday best.",
                               "Your brother, in uniform. You haven't heard from him in months."]}[tool]
            g.msg(rng.choice(lines), "think")
            p.morale = min(100, p.morale + 5)
            return self.act(200)
        if tool == "harmonica":
            p.morale = min(100, p.morale + 5)
            g.msg("You play a few bars. Men nearby go quiet.", "think")
            g.emit_sound(p.x, p.y, 40, "music", "a harmonica", p.side, p)
            for a in g.actors:
                if a.side == p.side and a.alive and abs(a.x - p.x) + abs(a.y - p.y) < 10:
                    a.morale = min(100, a.morale + 3)
            return self.act(300)
        if tool in ("rosary", "bible"):
            p.morale = min(100, p.morale + 5)
            g.msg("You pray. It helps, or it doesn't. You pray anyway.", "think")
            return self.act(200)
        if tool == "coin":
            g.msg("Heads." if rng.random() < 0.5 else "Tails.", "think")
            return self.act(30)
        if tool == "cards":
            g.msg("The queen of hearts is still missing.", "think")
            return self.act(50)
        if tool == "whistle":
            g.emit_sound(p.x, p.y, 60, "whistle", "a whistle blast", p.side, p)
            g.msg("You blow the whistle!", "shout")
            if p.squad is not None and p.squad.player_led:
                p.squad.order = Order("attack", target=self._facing_point(), issued=g.turn)
                p.squad.state = "assault"
                p.squad.state_turn = g.turn
                g.msg("Your men rise and go forward!", "good")
            return self.act(50)
        if tool == "ammo_crate":
            return self.cmd_resupply()
        if tool == "detector":
            found = 0
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    mn = g.map.mines.get((p.x + dx, p.y + dy))
                    if mn is not None and p.side not in mn.known and rng.random() <= it.condition:
                        mn.known.add(p.side)
                        found += 1
            g.msg(f"The detector whines{': ' + str(found) + ' mines found!' if found else '. Nothing.'}", "warn" if found else "info")
            return self.act(400)
        if tool == "sandbags":
            for dx, dy in DIRS8:
                x, y = p.x + dx, p.y + dy
                if g.map.in_bounds(x, y) and g.map.walk[x, y] and (x, y) not in g.soldier_at and T.DIG[g.map.t[x, y]]:
                    g.map.set(x, y, "sandbags", refresh=True)
                    it.uses -= 1
                    if it.uses <= 0:
                        p.remove_item(it)
                    g.msg("You fill and stack sandbags.", "info")
                    return self.act(900)
            g.msg("Nowhere to stack them here.", "info")
            return
        if tool == "wire":
            for dx, dy in DIRS8:
                x, y = p.x + dx, p.y + dy
                if g.map.in_bounds(x, y) and g.map.walk[x, y] and (x, y) not in g.soldier_at:
                    g.map.set(x, y, "wire", refresh=True)
                    p.remove_item(it)
                    g.msg("You string the wire.", "info")
                    return self.act(1200)
            g.msg("There's nowhere clear next to you to string it.", "info")
            return
        if tool == "handradio":
            if self._can_radio():
                return self.cmd_radio()
            g.msg("Static. Nobody on this net answers.", "info")
            return self.act(50)
        if tool == "document":
            from .prisoners import read
            g.msg(read(g, p, it), "info")
            return self.act(150)
        if tool == "papers":
            g.msg("Your papers - the name on them isn't yours. Keep them close; don't be searched.", "info")
            return
        g.msg(f"You turn the {it.name} over in your hands. There's nothing to do with it here.", "info")

    def _objective_hint(self):
        g = self.game
        p = g.player
        t = g.order_target_for_player()
        if t is None:
            return "nowhere in particular"
        from .senses import direction_word
        d = math.hypot(t[0] - p.x, t[1] - p.y)
        return f"to the {direction_word(t[0] - p.x, t[1] - p.y)}, {yards(d)}"

    def _facing_point(self):
        g = self.game
        p = g.player
        t = g.order_target_for_player()
        return t or (p.x, p.y)

    def cmd_throw(self):
        g = self.game
        p = g.player
        if self.captive_blocks():
            return
        v = p.vehicle
        if v is not None and not v.vt.open_top and (v.buttoned or not v.player_crewed):
            g.msg("Not through closed hatches. (Open up first - e - or get out.)", "info")
            return
        gr = [i for i in p.inv if i.t.kind in ("grenade",)] + [i for i in p.inv if i.t.kind == "explosive"]
        if not gr:
            g.msg("You have nothing to throw.", "info")
            return
        if len(gr) == 1:
            it = gr[0]
            self.cook = 0
            return self.enter_mode("throw", self._guess_throw_target(it), {"item": it})
        opts = [(i.name, i, self._item_color(i), True) for i in gr]

        def chosen(it):
            self.cook = 0
            self.enter_mode("throw", self._guess_throw_target(it), {"item": it})
        self.open_popup(Popup("Throw what?", opts, self._screen_anchor()), chosen)

    def cmd_pickup(self):
        g = self.game
        p = g.player
        if self.captive_blocks():
            return
        if p.vehicle is not None:
            g.msg("You'd have to climb out first.", "info")
            return
        here = g.map.items_at(p.x, p.y)
        items = [i for i in here if i.t.kind != "corpse"]
        bodies = [i for i in here if i.t.kind == "corpse" and i.data and i.data.get("inv") is not None]
        near = [(x, y) for x in range(p.x - 1, p.x + 2) for y in range(p.y - 1, p.y + 2)
                if (x, y) != (p.x, p.y) and g.map.in_bounds(x, y) and g.map.items_at(x, y)]
        if not items and not bodies:
            if near:
                return self.cmd_inventory()            # nothing underfoot, but within reach
            g.msg("There's nothing here you can take.", "info")
            return
        if len(items) == 1 and not bodies:
            return self._pickup(items[0])
        # CDDA-style: what's lying here, one line each - and the bodies to go through
        opts = [(i.name + (" (LIVE!)" if i.data and i.data.get("live") is not None else ""), i, self._item_color(i), True)
                for i in items]
        if len(items) > 1:
            opts.append(("Everything loose", "all", UI_HI, True))
        for b in bodies:
            opts.append((f"Search {b.data.get('name', 'the body')}", ("search", b), (200, 150, 140), True))
        if near:
            opts.append(("Sort through everything within reach (kit screen)", ("kit", None), UI_DIM, True))
        self.open_popup(Popup("Here", opts, self._screen_anchor()), self._pickup)

    def _pickup(self, it):
        g = self.game
        p = g.player
        if isinstance(it, tuple):
            kind, body = it
            if kind == "search" and body is not None:
                g.msg(f"You {'crawl up to' if p.stance == 2 else 'kneel by'} {body.data.get('name', 'the body')} "
                      f"and go through his pockets.", "info")
                self.cmd_inventory(focus_body=body)
            else:
                self.cmd_inventory()
            return
        if it == "all":
            total = 0
            left = []
            for i in [i for i in g.map.items_at(p.x, p.y) if i.t.kind != "corpse"]:
                c = A.pickup(g, p, i)
                if c is None:
                    left.append(i.name)
                total += c or 0
            g.msg("You gather up everything you can carry." + (f" No room for: {', '.join(left[:3])}"
                                                               f"{'...' if len(left) > 3 else ''}." if left else ""),
                  "info")
            return self.act(min(600, total))
        c = A.pickup(g, p, it)
        if c is None:
            return self._no_room(it)
        if not (it.data and it.data.get("live") is not None):
            g.msg(f"You pick up the {it.name}" + (" - flat on your belly, it takes a while." if p.stance == 2 else "."),
                  "info")
        return self.act(int(c * (1.4 if p.stance == 2 else 1.0)))

    def _no_room(self, it, x=None, y=None):
        """No room for it: say why, and offer the trades a soldier would make."""
        g = self.game
        p = g.player
        x = p.x if x is None else x
        y = p.y if y is None else y
        t = it.t
        opts = []
        if t.kind in ("gun", "melee"):
            slot = "holster" if t.kind == "gun" and t.cat == "pistol" else "primary"
            cur = p.invent.slots.get(slot) or p.invent.slots.get("secondary") if slot == "primary" else \
                p.invent.slots.get(slot)
            if cur is not None:
                opts.append((f"Drop your {cur.name} and take the {it.name}", ("swap", it, cur, x, y), UI_HI, True))
            if p.invent.hands is None:
                opts.append((f"Carry it in your hands (nothing else in them)", ("hands", it, None, x, y), None, True))
        else:
            opts.append(("Open your kit and make room (i)", ("kit", it, None, x, y), None, True))
        if not opts:
            g.msg(f"You have no room for the {it.name}.", "warn")
            return
        opts.append(("Leave it", None, UI_DIM, True))
        g.msg(f"You have no room for the {it.name}.", "warn")
        self.open_popup(Popup(f"No room for the {it.name}", opts, self._screen_anchor()), self._trade)

    def _trade(self, v):
        if not v:
            return
        g = self.game
        p = g.player
        kind, it, cur, x, y = v
        m = g.map
        if kind == "kit":
            return self.cmd_inventory()
        if it not in m.items_at(x, y):
            return
        if kind == "hands":
            m.remove_item(x, y, it)
            p.invent.hands = it
            it.where = "carried"
            if it.t.kind in ("gun", "melee"):
                p.wield(it)
            g.msg(f"You pick up the {it.name} and carry it in your hands.", "info")
            return self.act(100)
        if kind == "swap":
            cost = A.drop(g, p, cur)
            c = A.pickup(g, p, it, x, y)
            if c is None:
                A.pickup(g, p, cur)                  # it still doesn't go: take your own back
                g.msg(f"Even without the {cur.name} there's no room for the {it.name}.", "warn")
                return self.act(cost)
            if it.t.kind == "gun":
                A.wield(g, p, it)
                from .familiar import first_look
                first_look(g, p, it.t)
            g.msg(f"You put down your {cur.name} and take up the {it.name}.", "info")
            return self.act(cost + c + 60)

    def cmd_drop(self):
        g = self.game
        p = g.player
        its = list(p.inv)
        if not its:
            g.msg("You've nothing to drop.", "info")
            return
        opts = [(i.name, i, self._item_color(i), True) for i in its]
        self.open_popup(Popup("Drop what?", opts, self._screen_anchor()),
                        lambda it: self.item_action(it, "drop"))

    def cmd_wield(self):
        g = self.game
        p = g.player
        if self.captive_blocks():
            return
        its = [i for i in p.inv if i.t.kind in ("gun", "melee") and i is not p.weapon]
        if not its and p.weapon is None:
            g.msg("You have nothing to fight with.", "info")
            return
        opts = [(f"{i.name}  ({LOC_NAME.get(p.loc(i), '')})", i, self._item_color(i), True) for i in its]
        if p.weapon is not None:
            opts.append(("Put away what you're holding", "none", UI_DIM, True))
        self.open_popup(Popup("Take up", opts, self._screen_anchor()), self._wield)

    def _wield(self, it):
        g = self.game
        p = g.player
        if it == "none":
            p.weapon = None
            return self.act(80)
        return self.item_action(it, "wield")

    # what can be used where it lies, without picking it up first: dressings, syrettes, food, water, a smoke, a
    # letter to read (the rest - a rifle, a radio - you take up)
    IN_PLACE = {"canteen", "flask", "cigarettes", "ration", "chocolate", "stimulant", "gum", "letter", "photo",
                "newspaper", "document", "watch", "compass"}

    def usable_here(self, it) -> bool:
        return it.t.kind == "medical" or (it.t.kind == "tool" and it.t.tool in self.IN_PLACE)

    def within_reach(self) -> list:
        """What's lying where you can reach it - your tile and the eight round it, loose or on the dead:
        [(item, (x, y), holder)] (entities.things_at)."""
        from .entities import things_at
        g = self.game
        p = g.player
        out = []
        if p.vehicle is not None:
            return out
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = p.x + dx, p.y + dy
                if g.map.in_bounds(x, y):
                    out += [(it, (x, y), h) for it, h in things_at(g.map, x, y)]
        return out

    def use_where_it_lies(self, it, pos, holder, act="use", target=None):
        """Use a thing where it lies: in your hand for the moment it takes (a little longer - you bend for it,
        or go through his pockets), and whatever's left of it back where it was."""
        from .entities import return_thing, take_thing
        g = self.game
        p = g.player
        m = g.map
        take_thing(m, pos[0], pos[1], it, holder)
        inv = p.invent
        was = inv.hands
        inv.hands, it.where = it, "hands"
        try:
            if act == "self":
                c = A.treat(g, p, p, it)
                if c is None:
                    g.msg("That won't help right now.", "info")
                else:
                    self.act(c + 60)
            elif act == "other" and target is not None:
                c = A.treat(g, p, target, it)
                if c is None:
                    g.msg("That won't help him right now.", "info")
                else:
                    self.act(c + 60)
            else:
                self.use_tool(it)
                self.act(60)
        finally:
            left = inv.hands is it
            inv.hands = was
            if left:
                return_thing(m, pos[0], pos[1], it, holder)

    def cmd_apply(self):
        g = self.game
        p = g.player
        its = [i for i in p.inv if i.t.kind in ("medical", "explosive") or
               (i.t.kind == "tool" and i.t.tool not in ("pack", "dogtags"))]
        if p.weapon is not None and p.weapon.t.tool == "shovel":
            its.append(p.weapon)
        near = [(i, pos, h) for i, pos, h in self.within_reach() if self.usable_here(i)]
        if not its and not near:
            g.msg("You have nothing to use.", "info")
            return
        opts = [(f"{i.name}" + (" (place it beside you)" if i.t.kind == "explosive" else ""), ("own", i),
                 self._item_color(i), True) for i in its]
        for i, pos, h in near[:12]:
            opts.append((f"{i.name} ({'on the dead man' if h is not None else 'on the ground'})", ("near", i, pos, h),
                         self._item_color(i), True))

        def pick(v):
            if v[0] == "own":
                it = v[1]
                return self.item_action(it, {"medical": "self", "explosive": "place"}.get(it.t.kind, "use"))
            _k, it, pos, h = v
            return self.use_where_it_lies(it, pos, h, "self" if it.t.kind == "medical" else "use")
        self.open_popup(Popup("Use", opts, self._screen_anchor()), pick)

    # ---------------------------------------------------------------- context menu (right click)
    def context_menu(self, mx, my, sx, sy):
        g = self.game
        p = g.player
        m = g.map
        opts = [("Look", "look", None, True)]
        who = g.soldier_at.get((mx, my))
        if who is not None and who is not p and who in self._wounded_near():
            opts.insert(0, (f"Patch up {g.name_of(who)}", "patch", (240, 200, 120), True))
        adj = who is not None and who is not p and max(abs(mx - p.x), abs(my - p.y)) <= 1
        if adj and who.side == p.side and who.active:
            from .ammo import hand_over_possible
            w = who.weapon
            if w is not None and w.t.kind == "gun" and w.t.cal and hand_over_possible(p, w):
                opts.append((f"Give {who.him} ammunition for {who.his} {w.t.name}", "give_ammo", (200, 220, 150), True))
            if p.medical("bandage") is not None:
                opts.append((f"Give {who.him} a field dressing", "give_dressing", None, True))
            if p.grenades():
                opts.append((f"Give {who.him} a grenade", "give_grenade", None, True))
            if p.find(lambda i: i.t.tool == "cigarettes") is not None:
                opts.append((f"Offer {who.him} a cigarette", "give_smoke", None, True))
        if adj and who.side == p.side and who.active and who.role in ("adjutant", "clerk", "mp", "armourer", "cook",
                                                                        "chaplain", "politruk", "motor_sergeant",
                                                                        "ops_officer",
                                                                        "port_officer", "surgeon"):
            opts.insert(0, (f"Talk to the {who.role_name.lower()}", "talk", (220, 200, 140), True))
        if adj and who.side == p.side and who.active and who.role == "quartermaster":
            opts.insert(0, ("Trade with the quartermaster", "qm", (220, 200, 140), True))
        if adj and who.side == p.side and who.active and who.role == "intel":
            opts.insert(0, ("Report to the intelligence officer", "intel", (220, 200, 140), True))
        if adj and who.side != p.side and who.state == "surrendered" and who.ai.get("captor") != p.id:
            opts.insert(0, ("Take him prisoner", "take_prisoner", (200, 220, 150), True))
        if adj and who.side != p.side and who.state == "surrendered" and who.ai.get("captor") == p.id:
            opts.insert(0, ("Your prisoner...", "prisoner", (200, 220, 150), True))
        if adj and who.side != p.side and not who.ai.get("civilian") and who.state == "ok" and who.downed and who.body.conscious:
            opts.insert(0, ("Take the wounded man prisoner", "take_wounded", (200, 220, 150), True))
        if adj and who.side != p.side and not who.ai.get("civilian") and who.state == "ok" and p.vehicle is None and player_can_see_actor(g, who):
            # hand to hand: each move and the odds as you'd judge them (melee.py)
            from . import melee as ML
            for k, mv in enumerate(ML.moves_for(g, p, who)):
                opts.insert(k, (f"{ML.MOVES[mv]['name']} ({ML.odds_word(ML.odds(g, p, who, mv))})",
                                ("melee", mv), (240, 150, 120), True))
        if adj and who.side != p.side and who.state == "surrendered" and who.body.worst_wound() is not None and \
                (p.medical("bandage") is not None or p.medical("tourniquet") is not None):
            opts.append(("Patch him up (he's a prisoner)", "patch_enemy", None, True))
        if who is not None and who is not p and max(abs(mx - p.x), abs(my - p.y)) <= 2 and who.alive and \
                (who.side == p.side or who.ai.get("civilian") or who.state == "surrendered" or who.downed) and player_can_see_actor(g, who):
            opts.insert(0, (f"Talk to {who.him}" + (" (E)" if adj else ""), "chat", (220, 210, 170), True))
        if who is not None and who is not p and (who.side == p.side or who.state == "surrendered") and \
                player_can_see_actor(g, who):
            opts.append(("His chain of command", "chain", None, True))
        if max(abs(mx - p.x), abs(my - p.y)) == 1 and p.vehicle is None and m.in_bounds(mx, my) and m.see[mx, my]:
            opts.append(("Lean out this way (peek)", "peek", None, True))
        if m.in_bounds(mx, my) and m.water[mx, my] >= 1 and max(abs(mx - p.x), abs(my - p.y)) <= 3 and \
                g.sector.sea_edge is not None:
            opts.append(("Signal a boat to take you out to the fleet", "fleet", (140, 190, 255), True))
        if m.in_bounds(mx, my) and (mx, my) != (p.x, p.y) and (not m.explored[mx, my] or (
                (m.walk[mx, my] or T.DOOR[m.t[mx, my]]) and m.water[mx, my] < 2 and (mx, my) not in g.vehicle_at)):
            opts.append(("Go there" + ("" if m.explored[mx, my] else " (find a way)"), "go", None, True))
        if p.weapon is not None and p.weapon.t.kind == "gun" or p.vehicle is not None:
            opts.append(("Fire at it", "fire", None, True))
        if any(i.t.kind == "grenade" for i in p.inv):
            opts.append(("Throw a grenade there", "throw", None, True))
        if self._can_radio():
            opts.append(("Call artillery on it", "arty", (240, 170, 90), True))
        fg = p.has_tool("flaregun")
        if fg is not None:
            opts.append(("Fire a flare over it" + ("" if fg.uses > 0 else " (no cartridges left)"), "flare", None,
                         fg.uses > 0))
        if p.squad is not None and p.squad.player_led:
            opts.append(("Order the squad there", "order_move", None, True))
            opts.append(("Order an assault on it", "order_attack", None, True))
        # a vehicle: getting in (or onto it), out of it, and keeping it going
        veh = g.vehicle_at.get((mx, my))
        if veh is not None and not veh.dead:
            from . import maintenance as MT
            if p.vehicle is veh:
                opts.insert(0, ("Jump down off it" if riding(p) else f"Get out of the {veh.vt.name}",
                                "veh_exit", (200, 220, 150), True))
            elif p.vehicle is None and veh.near(p.x, p.y) <= 1 and (veh.side == p.side or veh.abandoned or veh.crew == 0):
                why = self._why_not_enter(veh)
                inside = veh.vt.seats or p.role == "tank_crew" or veh.crew < veh.vt.crew or veh.abandoned
                label = f"Get in the {veh.vt.name}" if inside else f"Climb onto the {veh.vt.name}'s hull and ride"
                opts.insert(0, (label + (f" ({why})" if why else ""), "veh_enter", (200, 220, 150), why is None))
                if veh.side == p.side:
                    jobs = MT.repairs(veh)
                    if jobs:
                        opts.insert(1, (f"Help fix {MT.REPAIR_WORD[jobs[0]]}", "veh_help", (220, 200, 140), True))
                    carrying = (p.invent.hands is not None and p.invent.hands.tid == "shell_crate") or \
                        any(i.tid == "shell_crate" for i in p.inv)
                    if MT.shells_short(veh) > 0 and carrying:
                        opts.insert(1, ("Hand up the shells", "veh_shells", (220, 200, 140), True))
                    if MT.is_supply_truck(veh):
                        opts.insert(1, (f"Take a crate of shells ({veh.ai.get('cargo', 0)} rounds on the truck)",
                                        "veh_crate", (220, 200, 140), p.invent.hands is None))
        # our own men and machines: nothing on the list to shoot them with (you still can - aim with f)
        mine = (veh is not None and not veh.dead and veh.side == p.side) or \
            (who is not None and who is not p and who.side == p.side and who.state == "ok")
        if mine or veh is not None:
            opts = [o for o in opts if not (o[1] == "peek" or mine and o[1] in ("fire", "throw", "arty", "flare"))]
        self.open_popup(Popup("", opts, (sx, sy)), lambda v: self._context(v, mx, my))

    def _context(self, v, x, y):
        g = self.game
        if isinstance(v, tuple) and v[0] == "melee":
            who = g.soldier_at.get((x, y))
            if who is not None and who.alive and max(abs(x - g.player.x), abs(y - g.player.y)) <= 1:
                return self.act(A.melee(g, g.player, who, v[1]))
            return
        if v == "fleet":
            return self._to_the_fleet()
        if v in ("veh_enter", "veh_exit", "veh_help", "veh_shells", "veh_crate"):
            from . import maintenance as MT
            veh = g.vehicle_at.get((x, y)) or g.player.vehicle
            if veh is None:
                return
            if v == "veh_enter":
                return self._enter_vehicle(veh)
            if v == "veh_exit":
                return self._vehicle_choice(veh, ("exit", None))
            if v == "veh_help":
                return MT.help_with(self, veh)
            if v == "veh_shells":
                return MT.hand_up(self, veh)
            return MT.take_crate(self, veh)
        if v == "chain":
            who = g.soldier_at.get((x, y))
            if who is not None:
                from .ui import ChainState
                self.app.push(ChainState(self.app, g, who))
            return
        if v == "talk":
            who = g.soldier_at.get((x, y))
            if who is not None:
                from .base import talk
                talk(self, who)
            return
        if v == "chat":
            who = g.soldier_at.get((x, y))
            if who is not None:
                from .talk import open_talk
                open_talk(self, who)
            return
        if v in ("qm", "intel"):
            who = g.soldier_at.get((x, y))
            if who is not None:
                from .qmui import open_intel, open_quartermaster
                return open_quartermaster(self, who) if v == "qm" else open_intel(self, who)
        if v in ("prisoner", "take_wounded", "patch_enemy"):
            who = g.soldier_at.get((x, y))
            if who is not None:
                return self._prisoner(who, v)
        if v in ("give_ammo", "give_dressing", "give_grenade", "give_smoke", "take_prisoner"):
            who = g.soldier_at.get((x, y))
            if who is not None:
                return self._give(who, v)
        if v == "patch":
            who = g.soldier_at.get((x, y))
            if who is not None:
                self._patch_menu(who)
        elif v == "peek":
            self.enter_mode("peek", (x, y))
            self.mode_confirm()
        elif v == "look":
            self.enter_mode("look", (x, y))
        elif v == "go":
            self.start_travel(x, y)
        elif v == "fire":
            self.begin_target()
            if self.mode == "target":
                self.cursor = (x, y)
                self.mode_confirm()
        elif v == "throw":
            gr = [i for i in g.player.inv if i.t.kind == "grenade"]
            if gr:
                self.act(A.throw(g, g.player, gr[0], x, y, 0))
        elif v == "arty":
            self._fire_mission((x, y))
        elif v == "flare":
            c = A.fire_flare(g, g.player, x, y)
            if c is None:
                g.msg("Click. The flare pistol's empty.", "info")
            self.act(c)
        elif v == "order_move":
            self._order_move((x, y))
        elif v == "order_attack":
            self._order_attack((x, y))

    # ---------------------------------------------------------------- squad orders
    def cmd_command(self):
        from .cmdui import open_command
        open_command(self)

    def cmd_orders(self):
        g = self.game
        p = g.player
        sq = p.squad
        if sq is None or not sq.player_led:
            from .cmdui import command_units
            chain, others = command_units(g)
            if chain or others:
                return self.cmd_command()
            g.msg("You're not in command of anyone. (C shows who you could order.)", "info")
            return
        roe = sq.order.roe
        opts = [("Follow me!", "follow", None, True), ("Hold here - take cover!", "hold", None, True),
                ("Advance to...", "move", None, True), ("Assault...", "attack", (240, 170, 90), True),
                ("Flank...", "flank", None, True), ("Suppress...", "suppress", None, True),
                ("Dig in", "dig", None, True), ("Ambush - down, and hold your fire", "ambush", None, True),
                ("Fall back!", "retreat", None, True),
                ("Fire at will" + (" (now)" if roe == "free" else ""), "roe_free", (180, 200, 230), True),
                ("Return fire only" + (" (now)" if roe == "return" else ""), "roe_return", (180, 200, 230), True),
                ("Hold your fire" + (" (now)" if roe == "hold" else ""), "roe_hold", (180, 200, 230), True)]
        opts.append(("Tasks... (scavenge, the wounded, prisoners, a hand for the tanks)", "tasks", (220, 200, 140),
                     True))
        from .cmdui import command_units
        chain, others = command_units(g)
        if [x for x in chain if x is not sq] or others:
            opts.append(("Command other units... (C)", "command", (200, 180, 120), True))
        self.open_popup(Popup("Orders", opts, self._screen_anchor()), self._order)

    def _order(self, what):
        g = self.game
        p = g.player
        sq = p.squad
        if what == "follow":
            sq.order = Order("follow", issued=g.turn)
            sq.arrived = False
            sq.player_led = True
            sq.leader = p
            text = "On me! Follow me!"
        elif what == "hold":
            sq.order = Order("hold", target=(p.x, p.y), radius=6, issued=g.turn)
            sq.arrived = True
            sq.positions = {}
            sq.player_led = True
            text = "Hold here! Get into cover!"
        elif what == "dig":
            sq.order = Order("dig", target=(p.x, p.y), radius=6, issued=g.turn)
            sq.arrived = True
            sq.positions = {}
            sq.player_led = True
            text = "Dig in, boys. We're staying."
        elif what == "retreat":
            sq.order = Order("retreat", issued=g.turn)
            text = "Fall back! Fall back!"
        elif what == "tasks":
            from . import tasks as TK
            self.open_popup(Popup("Tasks for the squad", TK.menu_options(g, sq, (p.x, p.y)), self._screen_anchor(),
                                  width=78, lines=[("Men go when there's no enemy close, and stop to fight when "
                                                    "there is.", UI_DIM)]),
                            lambda k: self._task(k))
            return
        elif what in ("move", "attack"):
            from .cmdui import choose_target
            cb = self._order_move if what == "move" else self._order_attack
            return choose_target(self, what, [sq], cb, (p.x, p.y), "squad")
        elif what == "command":
            return self.cmd_command()
        elif what in ("flank", "suppress"):
            from .cmdui import _send, choose_target
            return choose_target(self, what, [sq], lambda pos: _send(self, [sq], what, pos), (p.x, p.y), what)
        elif what == "ambush":
            g.command.issue(g, [sq], "ambush", None, say=False)
            text = "Get down. Nobody fires till I do."
        elif what.startswith("roe_"):
            r = what[4:]
            sq.order.roe = r
            text = {"free": "Fire at will!", "return": "Only fire if they fire on us!",
                    "hold": "Hold your fire! Nobody shoots!"}[r]
        else:
            return
        p.say(text, g.turn, voice=self._native_order(what))
        g.msg(f"You shout: '{text}'", "shout")
        g.emit_sound(p.x, p.y, 55, "shout", text, p.side, p)
        self.act(50)

    def _task(self, kind):
        """A job for your own squad: they hear you, and get on with it."""
        from . import tasks as TK
        g = self.game
        p = g.player
        sq = p.squad
        if kind == "stop":
            TK.finish(g, sq, "stopped")
            text = "Leave that! Back to your places!"
        else:
            TK.assign(g, sq, kind, by=p)
            text = {"ammo": "Go round the dead - get their ammunition!", "medical": "Get their dressings and morphine!",
                    "weapons": "Grab any grenades you can find!", "papers": "Search their dead - bring me any papers!",
                    "casevac": "Get the wounded back to the aid post!",
                    "prisoners": "Search that lot and march them back!",
                    "repair": "Rifles down, lads - give the tankers a hand!"}[kind]
        p.say(text, g.turn)
        g.msg(f"You shout: '{text}'", "shout")
        g.emit_sound(p.x, p.y, 55, "shout", text, p.side, p)
        self.act(50)

    def _native_order(self, what):
        """What a non-English-speaking leader actually shouts for this order (None: the text as shown)."""
        from .data.phrases import ORDER_PHRASE, lang, phrase
        p = self.game.player
        if lang(p.nation) == "en":
            return None
        if what in ("attack", "assault"):
            return self.game.shout(p, "attack")
        key = ORDER_PHRASE.get(what)
        return phrase(self.game.rng, p.nation, key) if key else ""

    def _order_move(self, pos):
        g = self.game
        p = g.player
        sq = p.squad
        sq.order = Order("move", target=pos, radius=4, issued=g.turn)
        sq.arrived = False
        sq.player_led = True
        text = "Move up! Go, go!"
        p.say(text, g.turn, voice=self._native_order("move"))
        g.msg(f"You point and shout: '{text}'", "shout")
        self._squad_follow_order(sq)
        self.act(50)

    def _order_attack(self, pos):
        g = self.game
        p = g.player
        sq = p.squad
        sq.order = Order("attack", target=pos, radius=4, issued=g.turn)
        sq.arrived = False
        sq.state = "assault"
        sq.state_turn = g.turn
        text = g.shout(p, "attack")
        p.say(text, g.turn)
        g.msg(f"You shout: '{text}'", "shout")
        if p.has_tool("whistle"):
            g.emit_sound(p.x, p.y, 60, "whistle", "a whistle blast", p.side, p)
        self._squad_follow_order(sq)
        self.act(50)

    def _squad_follow_order(self, sq):
        # the squad executes the order itself; you stay in command
        sq.player_led = True

    # ---------------------------------------------------------------- radio
    def _can_radio(self):
        g = self.game
        p = g.player
        if p.has_tool("radio"):
            return True
        v = p.vehicle
        from .vdamage import has_radio
        if v is not None and has_radio(g, v):
            return True                          # the vehicle's own set (most had one; early Soviet tanks mostly didn't)
        if (p.role in ("officer", "squad_leader") or p.rank >= 8) and p.squad is not None:
            for a in p.squad.members:
                if a is not p and a.active and a.has_tool("radio") and abs(a.x - p.x) + abs(a.y - p.y) <= 3:
                    return True
        return False

    def cmd_autopilot(self):
        """A: hand your soldier to his training - the same AI as every man on the field - and back."""
        from .succession import autopilot_on, set_autopilot
        g = self.game
        if g.player.state != "ok" or g.game_over:
            return
        if not autopilot_on(g) and g.__dict__.get("domain", "land") != "land":
            g.msg("Aboard, your job is your station and your orders: Enter gets on with them, Z lets the watch go "
                  "by. (There's no autopilot at sea or in the air.)", "info")
            return
        self.stop_auto()
        set_autopilot(g, not autopilot_on(g))

    def _succession_menu(self):
        """You died, and chose to choose: who carries on."""
        from . import succession as SU
        g = self.game
        cands = SU.pending(g)
        if not cands:
            g.__dict__.pop("succession_pending", None)
            g.game_over = True
            self.check_over()
            return
        dead = g.player
        opts = []
        for a in cands[:12]:
            d = int(math.hypot(a.x - dead.x, a.y - dead.y) * 2.2)
            side = "" if a.side == dead.side else " (the other side)"
            same = ", your squad" if a.squad is dead.squad else ""
            opts.append((f"{a.rank_short} {a.name}, {a.role_name.lower()}{same} - {d} yd{side}", a, None, True))
        self.open_popup(Popup("Who carries on?", opts, self._screen_anchor(),
                              lines=[(f"{dead.rank_full} {dead.name} is dead. The war goes on.", UI_DIM)]),
                        lambda a: (SU.choose(g, a), self.recenter()))

    def cmd_talk(self):
        """E: talk to whoever's beside you (talk.py)."""
        from .talk import talk_key
        talk_key(self)

    def cmd_orders_book(self):
        """T: every order you hold - who, how, by when, and what follows either way."""
        from .ui import OrdersState
        self.game.update_orders(force=True)
        self.app.push(OrdersState(self.app, self))

    def cmd_radio(self):
        g = self.game
        p = g.player
        from . import agents as AG
        if AG.has_wireless(p) and not self._can_radio():
            return AG.open_wireless(self)            # an agent's set talks to London, not to the guns
        if not self._can_radio():
            from .medevac import _radio_near, can_call
            if _radio_near(g, p):
                # not yours to call the guns on - but a wounded man can ask the radioman for the stretchers
                ok, why = can_call(g)
                self.open_popup(Popup("The radioman's set", [(
                    "Ask him to call for stretcher-bearers" + (f" ({why})" if not ok else ""), "medevac",
                    (240, 170, 170), ok)], self._screen_anchor()), self._radio)
                return
            g.msg("You have no radio, and no radioman at your side.", "info")
            return
        opts = [("Fire mission (HE)", "he", None, True), ("Smoke screen", "smoke", None, True)]
        if (p.role == "officer" or p.rank >= 12) and g.support.air_level.get(p.side, 0) > 0.3:
            opts.append(("Request air support", "air", None, True))
        if p.vehicle is not None or p.role in ("tank_crew", "officer") or p.rank >= 8:
            cd = g.__dict__.get("_truck_call", -9999)
            opts.append(("Request an ammunition truck (and fitters)", "truck", None, g.turn - cd > 1200))
        from .medevac import can_call
        ok, why = can_call(g)
        opts.append(("Request medical evacuation - stretcher-bearers" + (f" ({why})" if not ok else ""), "medevac",
                     (240, 170, 170), ok))
        opts.append(("Ask for a situation report", "sitrep", None, True))
        if AG.has_wireless(p):
            opts.append(("The wireless set: Morse to base (reports, drops)", "wireless", (220, 200, 140), True))
        self.open_popup(Popup("Radio", opts, self._screen_anchor(),
                              lines=[(g.support.fires.summary(g, p.side), UI_DIM)]),
                        self._radio)

    def _radio(self, what):
        g = self.game
        p = g.player
        if what == "he":
            self.enter_mode("radio_target", (p.x, p.y), {"cb": self._fire_mission})
        elif what == "smoke":
            self.enter_mode("radio_target", (p.x, p.y), {"cb": self._smoke_mission})
        elif what == "air":
            self.enter_mode("radio_target", (p.x, p.y), {"cb": self._air_mission})
        elif what == "truck":
            from .maintenance import call_truck
            near = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
            g.msg(f"You: 'Request ammunition and fitters at grid {near[0]:03d}{near[1]:03d}, over.'", "radio")
            r = call_truck(g, p.side, target=near, why="asked")
            if r and r.startswith("An ammunition"):
                g.__dict__["_truck_call"] = g.turn
            elif r:
                g.msg(f"Radio: '{r}'", "radio")
            self.act(200)
        elif what == "medevac":
            from .medevac import call
            call(self)
        elif what == "wireless":
            from . import agents as AG
            AG.open_wireless(self)
        elif what == "sitrep":
            st = g.strategic.overview()
            mine = st["allies" if p.side == "allies" else "axis"]
            theirs = st["axis" if p.side == "allies" else "allies"]
            g.msg(f"Radio: 'We hold {mine} sectors, the enemy {theirs}. Objectives here: "
                  + ", ".join(f"{o.name} ({'ours' if o.owner == p.side else 'theirs' if o.owner else 'contested'})"
                              for o in g.map.objectives) + ".'", "radio")
            self.act(200)

    def _fire_mission(self, pos):
        g = self.game
        p = g.player
        x, y = pos
        if not g.map.explored[x, y]:
            g.msg("You can't call fire on ground you haven't seen.", "warn")
            return
        danger = math.hypot(x - p.x, y - p.y) < 12
        g.msg(f"You: 'Fire mission, over. Grid {x:03d}{y:03d}. Infantry in the open.{' DANGER CLOSE!' if danger else ''}'", "radio")
        ok = g.support.request_fire(p.side, x, y, caller=p)
        if ok:
            g.stats["fire_missions"] += 1
        self.act(300)

    def _smoke_mission(self, pos):
        g = self.game
        p = g.player
        x, y = pos
        g.msg(f"You: 'Fire mission, over. Grid {x:03d}{y:03d}. Smoke - I say again, smoke.'", "radio")
        if g.support.request_fire(p.side, x, y, caller=p, smoke=True):
            g.msg("Radio: 'Smoke on the way.'", "radio")
        self.act(300)

    def _air_mission(self, pos):
        g = self.game
        p = g.player
        g.msg("You: 'Request air on the marked position, over.'", "radio")
        if g.support.launch_sortie(p.side, target=pos):
            g.msg("Radio: 'Wilco. Mark with smoke.'", "radio")
        self.act(300)
