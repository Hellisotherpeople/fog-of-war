"""The battlefield map in your hand: ground you've walked, your section's marks on it, and the places
you've been told about.

Only what the soldier knows is on the sheet.  Unexplored ground stays blank, and an enemy appears at
the moment you can see him and no sooner.  The pencil is yours: 1 to 5 write a danger, a rally point,
a firing position, a cache or a casualty, and 0 rubs one out.
"""
from __future__ import annotations

import tcod.event as E

from . import marks as MK
from . import tiles as T
from .constants import SCREEN_H, SCREEN_W, UI_DIM, UI_HI, UI_SEL_BG, UI_TEXT
from .senses import player_can_see_actor


class MapState:
    """A full-screen sheet of the ground in hand."""

    title = "Battlefield map"

    def __init__(self, app, game, play=None):
        self.app = app
        self.game = game
        self.play = play
        p = game.player
        self.cx, self.cy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        self.vx0 = self.vy0 = None
        self.note = ""
        self.inspect = None

    # ---------------------------------------------------------------- view
    def _view_size(self):
        return max(10, SCREEN_W - 33), max(6, SCREEN_H - 7)

    def _scroll(self, vw, vh):
        m = self.game.map
        self.cx = max(0, min(m.w - 1, self.cx))
        self.cy = max(0, min(m.h - 1, self.cy))
        if self.vx0 is None:
            self.vx0, self.vy0 = self.cx - vw // 2, self.cy - vh // 2
        if self.cx < self.vx0 + 2:
            self.vx0 = self.cx - 2
        elif self.cx > self.vx0 + vw - 3:
            self.vx0 = self.cx - vw + 3
        if self.cy < self.vy0 + 1:
            self.vy0 = self.cy - 1
        elif self.cy > self.vy0 + vh - 2:
            self.vy0 = self.cy - vh + 2
        self.vx0 = max(0, min(m.w - vw, self.vx0))
        self.vy0 = max(0, min(m.h - vh, self.vy0))

    def render(self, con):
        con.clear()
        g = self.game
        m = g.map
        p = g.player
        ox, oy = 2, 2
        vw, vh = self._view_size()
        self._scroll(vw, vh)
        con.print(2, 0, f"BATTLEFIELD MAP - {m.name} ({g.time_feel()}, {g.weather})", fg=UI_HI)
        sheet = "with a map sheet" if p.has_tool("map") is not None else "from what you remember of the walk"
        px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        dx, dy = self.cx - px, self.cy - py
        if not dx and not dy:
            where = "you are here"
        else:
            from .play import yards
            from .senses import direction_word
            where = f"{direction_word(dx, dy)}, {yards(max(abs(dx), abs(dy)))}"
        con.print(2, 1, f"Grid {self.cx}, {self.cy} - {where}; pencilled {sheet}.", fg=UI_DIM)
        # ground
        for vy in range(vh):
            y = self.vy0 + vy
            if y >= m.h:
                break
            for vx in range(vw):
                x = self.vx0 + vx
                if x >= m.w:
                    break
                if not m.explored[x, y]:
                    con.print(ox + vx, oy + vy, " ", fg=(40, 40, 40), bg=(10, 10, 10))
                    continue
                t = int(m.t[x, y])
                ch = chr(int(T.GLYPHS[t, int(m.var[x, y]) % T.MAXV]))
                bg = tuple(int(c) for c in T.BG[t]) if not m.visible[x, y] else \
                    tuple(int(min(255, int(c) * 1.25)) for c in T.BG[t])
                if x % 10 == 0 or y % 10 == 0:
                    bg = tuple(min(255, c + 16) for c in bg)          # the grid, for reporting a place
                con.print(ox + vx, oy + vy, ch, fg=tuple(int(c) for c in T.FG[t]), bg=bg)
        # things on it
        for a in g.actors:
            if not a.alive:
                continue
            own = a is p or (a.side == p.side and p.squad is not None and a.squad is p.squad)
            if not own and not player_can_see_actor(g, a):
                continue
            x, y = a.x, a.y
            if not (self.vx0 <= x < self.vx0 + vw and self.vy0 <= y < self.vy0 + vh):
                continue
            con.print(ox + x - self.vx0, oy + y - self.vy0, "@" if a is p else "·",
                      fg=(255, 245, 140) if a is p else (130, 190, 255) if a.side == p.side else (255, 95, 75))
        for v in g.vehicles:
            if v.dead:
                continue
            x, y = v.x, v.y
            if not (self.vx0 <= x < self.vx0 + vw and self.vy0 <= y < self.vy0 + vh):
                continue
            if v.side != p.side and not m.visible[x, y] and p.vehicle is not v:
                continue
            con.print(ox + x - self.vx0, oy + y - self.vy0, "▮",
                      fg=(120, 190, 255) if v.side == p.side else (255, 95, 75))
        if p.has_tool("map") is not None:
            for i, o in enumerate(m.objectives):
                if not (self.vx0 <= o.x < self.vx0 + vw and self.vy0 <= o.y < self.vy0 + vh):
                    continue
                con.print(ox + o.x - self.vx0, oy + o.y - self.vy0, "ABCDEFGH"[i % 8], fg=(250, 220, 120))
        for x, y, mk in MK.on_map(g, p.side):
            if not (self.vx0 <= x < self.vx0 + vw and self.vy0 <= y < self.vy0 + vh):
                continue
            ch = MK.KINDS[mk["kind"]][0]
            con.print(ox + x - self.vx0, oy + y - self.vy0, ch, fg=MK.color(mk, g.turn))
        for x, y, rec, col in MK.sightings(g):
            if not (self.vx0 <= x < self.vx0 + vw and self.vy0 <= y < self.vy0 + vh):
                continue
            con.print(ox + x - self.vx0, oy + y - self.vy0, "▮" if rec.get("v") else "×", fg=col)
        # cursor
        if self.vx0 <= self.cx < self.vx0 + vw and self.vy0 <= self.cy < self.vy0 + vh:
            t = int(m.t[self.cx, self.cy])
            ch = chr(int(T.GLYPHS[t, int(m.var[self.cx, self.cy]) % T.MAXV])) if m.explored[self.cx, self.cy] else " "
            con.print(ox + self.cx - self.vx0, oy + self.cy - self.vy0, ch, fg=(20, 20, 20), bg=(245, 225, 120))
        # the mark list, nearest first
        sx = SCREEN_W - 30
        con.print(sx, 1, "YOUR MARKS", fg=UI_HI)
        rows = sorted(MK.on_map(g, p.side),
                      key=lambda t: max(abs(t[0] - px), abs(t[1] - py)))
        if not rows:
            con.print(sx, 2, "None yet. 1-5 write one.", fg=UI_DIM)
        for i, (x, y, mk) in enumerate(rows[: SCREEN_H - 7]):
            d = max(abs(x - px), abs(y - py))
            glyph, name, _c = MK.KINDS[mk["kind"]]
            label = f"{name} '{mk['note']}'" if mk.get("note") else name
            con.print(sx, 2 + i, f"{glyph} {label[:14]}  {d * 2}m ({x},{y})"[:29], fg=MK.color(mk, g.turn))
        # the edge of the sheet
        con.print(1, SCREEN_H - 4, MK.LINE + "  × / ▮ last seen", fg=UI_DIM)
        con.print(1, SCREEN_H - 3, "0 rub out   Enter walk there   o send the section   r rally here   "
                  "e note   f fire mission   s smoke   n marks   x look   / find   Esc close", fg=UI_DIM)
        if self.inspect is not None and self.play is not None:
            lines, _title = self.play.describe_tile(self.inspect[0], self.inspect[1], brief=True)
            y = SCREEN_H - 3 - min(6, len(lines)) - 1
            for ln, col in lines[-6:]:
                con.print(2, y, ln[:SCREEN_W - 4], fg=col)
                y += 1
        if self.note:
            con.print(2, SCREEN_H - 5, self.note[:SCREEN_W - 4], fg=(240, 190, 120))

    # ---------------------------------------------------------------- input
    def _speak(self):
        """For a screen reader: the cursor's ground and the marks on it, nothing more."""
        if not (getattr(self.app, "settings", None) or {}).get("screen_reader"):
            return
        from . import screenreader
        p = self.game.player
        px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        dx, dy = self.cx - px, self.cy - py
        from .senses import direction_word
        where = "here" if not dx and not dy else direction_word(dx, dy)
        lines, _t = (self.play.describe_tile(self.cx, self.cy, brief=True) if self.play is not None
                     else ([], None))
        marks = ", ".join(mk["kind"] for mk in MK.at(self.game, self.cx, self.cy))
        spoken = "; ".join(t for t, _c in lines[:2])
        screenreader.say(f"{where}, {self.cx}, {self.cy}. {spoken}" + (f" Marks: {marks}." if marks else ""))

    def _mark(self, kind):
        mk = MK.place(self.game, self.cx, self.cy, kind)
        if mk is None:
            self.note = "Nothing there to write on - you haven't seen it."
            return
        self.note = f"Marked: {MK.KINDS[kind][1]}."

    def _search(self):
        g = self.game
        m = g.map
        from .ui import search_choices
        out = []
        for label, x, y in m.labels:
            if m.in_bounds(x, y) and m.explored[x, y]:
                out.append((label, (x, y), "on the ground", UI_TEXT))
        for i, o in enumerate(m.objectives):
            out.append((f"Objective {'ABCDEFGH'[i % 8]}", (o.x, o.y), "objective", (250, 220, 120)))
        for x, y, mk in MK.on_map(g, g.player.side):
            out.append((MK.KINDS[mk["kind"]][1].title(), (x, y), "your mark", MK.KINDS[mk["kind"]][2]))

        def pick(xy):
            self.cx, self.cy = xy
            self.inspect = xy
        return search_choices(self.app, "Find on the map", out, pick)

    def on_key(self, key):
        c = key.char
        mv = key.move()
        if key.sym == E.KeySym.F1 or c == "?":
            return self.play.cmd_help() if self.play is not None else None
        if c == "/":
            return self._search()
        if c in MK.KEY:
            return self._mark(MK.KEY[c])
        if c == "0":
            n = MK.clear_at(self.game, self.cx, self.cy)
            self.note = f"Rubbed out {n} mark{'s' if n != 1 else ''}." if n else "Nothing marked there."
            return
        if c == "e":
            note = MK.cycle_note(self.game, self.cx, self.cy)
            self.note = f"Note: {note}" if note else "Nothing marked there."
            return
        if c in ("n", "N"):
            p = self.game.player
            rows = sorted(MK.on_map(self.game, p.side),
                          key=lambda t: max(abs(t[0] - p.x), abs(t[1] - p.y)))
            if rows:
                i = next((i for i, (x, y, _m) in enumerate(rows) if (x, y) == (self.cx, self.cy)), -1)
                i = (i + (-1 if c == "N" else 1)) % len(rows)
                self.cx, self.cy = rows[i][0], rows[i][1]
                self._speak()
            return
        if key.sym == E.KeySym.HOME or c == "@":
            p = self.game.player
            self.cx, self.cy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
            return self._speak()
        if mv:
            k = 5 if key.is_run() else 1
            self.cx += mv[0] * k
            self.cy += mv[1] * k
            self.inspect = None
            return self._speak()
        if key.sym == E.KeySym.PAGEUP:
            self.cy -= 10
            return self._speak()
        if key.sym == E.KeySym.PAGEDOWN:
            self.cy += 10
            return self._speak()
        if key.sym == E.KeySym.TAB:
            props = [q for q in self._proposals()]
            if props:
                i = (self.__dict__.get("prop_i", -1) + (1 if key.shift else -1)) % len(props)
                self.prop_i = i
                self.cx, self.cy = props[i][1]
                self._speak()
            return
        if c == "x" or c == ";":
            self.inspect = (self.cx, self.cy)
            return
        if c == "o" and self.play is not None:
            self.app.pop()
            return self.play._order_move((self.cx, self.cy))
        if c == "r" and self.play is not None:
            self.app.pop()
            return self.play._order_rally((self.cx, self.cy))
        if c in ("f", "s") and self.play is not None:
            if not self.play._can_radio():
                self.note = "You have no radio."
                return
            self.app.pop()
            cb = self.play._fire_mission if c == "f" else self.play._smoke_mission
            return self.play.enter_mode("radio_target", (self.cx, self.cy), {"cb": cb})
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER):
            self.app.pop()
            if self.play is not None and not self.play.start_travel(self.cx, self.cy):
                self.game.msg("You can't see a way there.", "info")
            return
        if key.sym == E.KeySym.ESCAPE or c in ("M", "m", "q"):
            self.app.pop()

    def _proposals(self):
        """The obvious places: objectives, then your rally points."""
        m = self.game.map
        out = [(f"Objective {'ABCDEFGH'[i % 8]}", (o.x, o.y)) for i, o in enumerate(m.objectives)]
        out += [("Rally point", (x, y)) for x, y, mk in MK.on_map(self.game, self.game.player.side)
                if mk["kind"] == "rally"]
        return out

    def on_click(self, tx, ty, b):
        if tx >= SCREEN_W - 30:
            p = self.game.player
            rows = sorted(MK.on_map(self.game, p.side),
                          key=lambda t: max(abs(t[0] - p.x), abs(t[1] - p.y)))
            i = ty - 2
            if 0 <= i < len(rows) and b == 1:
                self.cx, self.cy = rows[i][0], rows[i][1]
                self._speak()
            return
        ox, oy = 2, 2
        vw, vh = self._view_size()
        x, y = self.vx0 + tx - ox, self.vy0 + ty - oy
        if 0 <= tx - ox < vw and 0 <= ty - oy < vh:
            same = (x, y) == (self.cx, self.cy)
            self.cx, self.cy = x, y
            self._speak()
            if b == 3:
                self.inspect = (x, y)
            elif same:
                self.app.pop()
                if self.play is not None:
                    self.play.start_travel(x, y)
            return
        if b == 1:
            self.app.pop()


def open_map(app, game, play):
    app.push(MapState(app, game, play))
