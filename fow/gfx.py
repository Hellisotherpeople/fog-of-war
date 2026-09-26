"""Layered rendering on the SDL renderer.

Layers, bottom to top:
  1. the UI console (text: side panel, log)
  2. map layers clipped to the map area - sprites (terrain, decals/items, units,
     effects, filters) or, in ASCII mode, the map drawn as text in a zoomed font
  3. an overlay text console with transparent background (popups, tooltips, bubbles, cursor)

Text is rasterised at exactly the cell size the window allows, so it stays crisp
at any window size and on HiDPI displays.  Zooming changes the size of a map cell;
the map's sprite or font atlas is rebuilt at exactly that size (it takes a few ms),
so the map is crisp at every zoom level while the interface stays the same size.
"""
from __future__ import annotations

import math

import tcod
import tcod.render
import tcod.sdl.render

from . import fonts
from .constants import SCREEN_H, SCREEN_W, VIEW_H, VIEW_W

ZOOM_MIN = {"sprites": 0.45, "ascii": 0.5}
ZOOM_MAX = {"sprites": 4.0, "ascii": 3.0}
ZOOM_STEP = 1.15


class Graphics:
    def __init__(self, ctx, settings):
        self.ctx = ctx
        self.renderer = ctx.sdl_renderer
        self.settings = settings
        self.out_size = None
        self.cell = (10, 16)
        self.origin = (0, 0)
        self.text_ts = None
        self.text_atlas = None
        self._renders = {}
        self.sprite_px = 0
        self.sprite_bank = None
        self.sprite_atlas = None
        self.map_cell = (10, 16)        # pixels per map cell on screen
        self.map_font_atlas = None
        self._map_font_key = None
        self._font_key = None
        self._sprite_key = None
        self.check_resize(force=True)

    # ------------------------------------------------------------ layout
    def check_resize(self, force=False) -> bool:
        out = tuple(self.renderer.output_size)
        if out == self.out_size and not force:
            return False
        self.out_size = out
        self._layout()
        return True

    def _layout(self):
        W, H = self.out_size
        cw = max(6, W // SCREEN_W)
        ch = max(10, H // SCREEN_H)
        # keep text proportions pleasant
        ch = min(ch, int(cw * 2.25))
        cw = min(cw, int(ch * 0.62))
        self.cell = (cw, ch)
        self.origin = ((W - cw * SCREEN_W) // 2, (H - ch * SCREEN_H) // 2)
        key = (self.settings["font"], cw, ch)
        if key != self._font_key:
            self._font_key = key
            self.text_ts = fonts.make_tileset(self.settings["font"], cw, ch)
            self.text_atlas = tcod.render.SDLTilesetAtlas(self.renderer, self.text_ts)
            self._renders = {k: v for k, v in self._renders.items() if k[1] != "text"}
        self._sprite_layout()

    def _sprite_layout(self):
        """(Re)build whatever the map is drawn with, at the current zoom."""
        cw, ch = self.cell
        s = max(6, int(round(ch * self.zoom_value("sprites"))))
        self.sprite_px = s
        if self.settings.get("sprites"):
            if self._sprite_key != s:
                from .sprites import SpriteBank
                if self.sprite_bank is None:
                    self.sprite_bank = SpriteBank()
                ts = self.sprite_bank.build(s)
                self.sprite_atlas = tcod.render.SDLTilesetAtlas(self.renderer, ts)
                self._sprite_key = s
                self._renders = {k: v for k, v in self._renders.items() if k[1] != "sprite"}
            self.map_cell = (s, s)
        else:
            z = self.zoom_value("ascii")
            mw, mh = max(3, int(round(cw * z))), max(5, int(round(ch * z)))
            key = (self.settings["font"], mw, mh)
            if key != self._map_font_key:
                self._map_font_key = key
                ts = self.text_ts if (mw, mh) == (cw, ch) else fonts.make_tileset(self.settings["font"], mw, mh)
                self.map_font_atlas = tcod.render.SDLTilesetAtlas(self.renderer, ts)
                self._renders = {k: v for k, v in self._renders.items() if k[1] != "mapfont"}
            self.map_cell = (mw, mh)

    def _zoom_key(self, mode=None):
        mode = mode or ("sprites" if self.settings.get("sprites") else "ascii")
        return mode, ("zoom" if mode == "sprites" else "zoom_ascii")

    def zoom_value(self, mode=None) -> float:
        mode, key = self._zoom_key(mode)
        return float(self.settings.get(key, 1.4 if mode == "sprites" else 1.0))

    def set_zoom(self, z):
        mode, key = self._zoom_key()
        self.settings[key] = max(ZOOM_MIN[mode], min(ZOOM_MAX[mode], z))
        self.settings.save()
        self._sprite_layout()

    def zoom_step(self, steps: int):
        """Zoom in (positive) or out (negative) a notch.  Returns the new zoom."""
        self.set_zoom(self.zoom_value() * ZOOM_STEP ** steps)
        return self.zoom_value()

    def sprites_on(self) -> bool:
        return bool(self.settings.get("sprites")) and self.sprite_atlas is not None

    def enable_sprites(self, on: bool):
        self.settings["sprites"] = on
        self.settings.save()
        if on:
            self._sprite_key = None
        self._sprite_layout()

    def map_view_size(self) -> tuple[int, int]:
        """How many map tiles fit in the map area at the current zoom (a partial cell counts)."""
        cw, ch = self.cell
        mw, mh = self.map_cell
        return max(8, -(-(VIEW_W * cw) // mw)), max(6, -(-(VIEW_H * ch) // mh))

    def map_scale(self) -> tuple[float, float]:
        """UI text cells per map cell."""
        cw, ch = self.cell
        mw, mh = self.map_cell
        return mw / cw, mh / ch

    def map_cell_to_text(self, sx: float, sy: float) -> tuple[int, int]:
        """Map-view cell -> UI text cell (for anchoring popups and bubbles)."""
        tx, ty = self.map_scale()
        return int((sx + 0.5) * tx), int((sy + 0.5) * ty)

    def text_to_map_cell(self, tx: float, ty: float) -> tuple[int, int]:
        sx, sy = self.map_scale()
        return math.floor(tx / sx), math.floor(ty / sy)

    def pixel_to_cell(self, x: float, y: float) -> tuple[float, float]:
        try:
            px, py = self.renderer.coordinates_from_window((x, y))
        except Exception:
            px, py = x, y
        ox, oy = self.origin
        cw, ch = self.cell
        return (px - ox) / cw, (py - oy) / ch

    # ------------------------------------------------------------ drawing
    def _render(self, name, kind, console):
        key = (name, kind, console.width, console.height)
        r = self._renders.get(key)
        if r is None:
            atlas = {"text": self.text_atlas, "sprite": self.sprite_atlas, "mapfont": self.map_font_atlas}[kind]
            r = tcod.render.SDLConsoleRender(atlas)
            self._renders[key] = r
        return r.render(console)

    def present(self, ui, layers=None, overlay=None, map_offset=None):
        """Draw the UI, then the map layers (shifted by a sub-cell pixel offset for smooth scrolling)."""
        r = self.renderer
        self.check_resize()
        r.draw_color = (0, 0, 0, 255)
        r.clear()
        ox, oy = self.origin
        cw, ch = self.cell
        tex = self._render("ui", "text", ui)
        r.copy(tex, dest=(ox, oy, ui.width * cw, ui.height * ch))
        if layers:
            kind = "sprite" if self.sprites_on() else "mapfont"
            mw, mh = self.map_cell
            dx, dy = (int(round(map_offset[0])), int(round(map_offset[1]))) if map_offset else (0, 0)
            clip = (ox, oy, VIEW_W * cw, VIEW_H * ch)
            r.clip_rect = clip
            for i, con in enumerate(layers):
                if con is None:
                    continue
                tex = self._render(f"layer{i}", kind, con)
                r.copy(tex, dest=(ox - dx, oy - dy, con.width * mw, con.height * mh))
            r.clip_rect = None
        if overlay is not None:
            tex = self._render("overlay", "text", overlay)
            r.copy(tex, dest=(ox, oy, overlay.width * cw, overlay.height * ch))
        r.present()
