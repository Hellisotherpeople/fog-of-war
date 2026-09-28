"""The kit screen: equipment slots, webbing pouches, pack, pockets - and whatever you're searching.

It unfolds from your @ (with a line back to you).  Items are blocks on grids.
Move them with Enter or the mouse (drag and drop), rotate with r, and so on.
Everything you do costs time; the battle doesn't wait.
"""
from __future__ import annotations

import math
import textwrap

import tcod.event as E

from .ammo import fill_magazine, reload as ammo_reload, unload
from .constants import UI_BG, UI_DIM, UI_FRAME, UI_HI, UI_SEL_BG, UI_TEXT, VIEW_H, VIEW_W
from .data.nations import NATIONS
from .entities import Item
from .inventory import ACCESS, SLOT_NAME, SLOTS, Grid, Inventory, container_grids, item_size

CW, CH = 4, 2          # text cells per grid cell

KIND_COL = {"gun": (70, 80, 55), "mag": (115, 100, 55), "clip": (120, 105, 60), "ammo": (110, 95, 50),
            "grenade": (65, 85, 55), "explosive": (120, 80, 40), "medical": (150, 145, 135),
            "tool": (80, 80, 85), "melee": (90, 85, 80), "armor": (75, 85, 65), "container": (100, 90, 65),
            "corpse": (90, 30, 30)}


SHORT = {"bandage": "Band", "morphine": "Morph", "tourniquet": "Tqt", "sulfa": "Sulfa", "medkit": "Medic bag",
         "plasma": "Plasma", "canteen": "Water", "ration": "Food", "cigarettes": "Cigs", "flask": "Flask",
         "letter": "Letter", "photo": "Photo", "dogtags": "Tags", "rosary": "Rosary", "lucky_coin": "Coin",
         "cards": "Cards", "bible": "Bible", "harmonica": "Harp", "watch": "Watch", "compass": "Comp",
         "map": "Map", "orders": "Orders", "whistle": "Whstl", "binoculars": "Binos", "wirecutters": "Cutters",
         "flaregun": "Flare", "shovel": "Shovel", "bayonet": "Bayo", "radio": "Radio", "radio_scr300": "Radio"}


def label_for(it) -> str:
    t = it.t
    if it.tid in SHORT:
        return SHORT[it.tid]
    if t.kind == "clip":
        return f"Clip {t.cal}"
    if t.kind == "mag":
        return {"clip": "Clip", "belt": "Belt"}.get(it.tid.split("_")[0], "Mag")
    if t.kind == "grenade":
        return {"smoke": "Smoke", "wp": "WP", "at": "AT gren", "molotov": "Molotov",
                "gammon": "Gammon", "stick": "Stick"}.get(t.gtype, "Gren")
    if t.kind == "ammo":
        return t.cal
    n = t.get("short") or t.name
    for a, b in (("-round ", "rd "), ("magazine", "mag"), ("stripper clip", "clip"), (" grenade", ""),
                 ("fragmentation", "frag"), ("field dressing", "dressing"), ("syrette", ""), ("en-bloc ", ""),
                 ("(drum)", "drum"), ("(box)", "box")):
        n = n.replace(a, b)
    if "(" in n:
        n = n.split("(")[0].strip()
    return n


class Pane:
    """A view of an inventory-like source (yours, a body's, or the ground)."""

    def __init__(self, title, inv: Inventory | None = None, ground=None, owner=None):
        self.title = title
        self.inv = inv
        self.ground = ground        # (x, y) for a ground pile
        self.owner = owner          # Actor for your own kit
        self.rect = (0, 0, 0, 0)
        self.page = 0               # PgUp / PgDn when there's more than fits
        self.more = False

    def ground_grid(self, game):
        """A virtual grid packing the loose items on a tile."""
        x, y = self.ground
        items = [i for i in game.map.items_at(x, y) if i.t.kind != "corpse"]
        # as deep as the pile needs (shown twelve rows at a time)
        need = sum(max(1, it.dims(False)[0] * it.dims(False)[1]) for it in items)
        g = Grid(8, max(12, 12 * (-(-need // 70)) + 12), "ground")
        for it in items:
            spot = g.find_spot(it)
            if spot is None:
                continue
            gx, gy, rot = spot
            w, h = it.dims(rot)
            for i in range(gx, gx + w):
                for j in range(gy, gy + h):
                    g.cells[i][j] = it
            g.items.append(it)
        return g


class InventoryScreen:
    def __init__(self, play, loot_sources=None):
        self.play = play
        self.game = play.game
        p = self.game.player
        self.own = Pane("Your kit", p.invent, owner=p)
        self.sources = loot_sources or []     # list of Pane
        self.src_idx = 0
        self.focus = 0                        # 0 own, 1 loot
        self.cells = []                       # hit targets built each frame
        self.cursor = 0
        self.held = None                      # (item, origin pane)
        self.held_rot = False
        self.drag = False
        self.info = ""
        self.menu = None
        self.ground_layout = {}

    # ================================================================== helpers
    @property
    def loot(self):
        return self.sources[self.src_idx] if self.sources else None

    def spend(self, cost):
        if cost and cost > 0:
            self.play.act(cost)

    def say(self, text):
        self.info = text

    # ================================================================== drawing
    def render(self, con):
        game = self.game
        p = game.player
        self.cells = []
        loot = self.loot
        own_w = 66 if loot is None else 56
        loot_w = VIEW_W - own_w - 1 if loot is not None else 0
        total = own_w + loot_w
        ax, ay = self.play._screen_anchor()
        x0 = max(0, min(VIEW_W - total, ax + 3 if ax + 3 + total <= VIEW_W else ax - 3 - total))
        if total > VIEW_W - 2:
            x0 = 1
        y0 = 1
        h = VIEW_H - 2
        # connector to the soldier
        if 0 <= ax < VIEW_W and 0 <= ay < VIEW_H and not (x0 <= ax < x0 + total):
            edge = x0 if x0 > ax else x0 + total - 1
            step = 1 if edge > ax else -1
            for cx in range(ax + step, edge, step):
                con.print(cx, ay, "─", fg=UI_FRAME)
        self._draw_pane(con, self.own, x0, y0, own_w, h, focused=self.focus == 0)
        if loot is not None:
            self._draw_pane(con, loot, x0 + own_w, y0, loot_w, h, focused=self.focus == 1)
        # held item follows the cursor
        if self.held is not None and self.cells:
            c = self.cells[self.cursor % len(self.cells)]
            it = self.held[0]
            w, hh = it.dims(self.held_rot)
            rx, ry = c["rect"][0], c["rect"][1]
            ok = self._can_drop(c)
            col = (60, 110, 60) if ok else (130, 50, 50)
            for i in range(w * CW):
                for j in range(hh * CH):
                    if 0 <= rx + i < VIEW_W and 0 <= ry + j < VIEW_H:
                        con.print(rx + i, ry + j, " ", bg=col)
            con.print(rx, ry, label_for(it)[: w * CW], fg=(255, 255, 230), bg=col)
        if self.menu is not None:
            from .render import draw_popup
            draw_popup(con, self.menu)

    def _draw_pane(self, con, pane, x0, y0, w, h, focused):
        game = self.game
        con.draw_frame(x0, y0, w, h, clear=True, fg=UI_HI if focused else UI_FRAME, bg=UI_BG)
        title = pane.title
        if pane is self.own:
            p = game.player
            wt = p.carried_weight()
            burden = "light" if wt < 18 else "a fair load" if wt < 26 else "heavy" if wt < 34 else "crushing"
            con.print(x0 + 2, y0, f" {title} ", fg=UI_HI, bg=UI_BG)
            tag = f" {wt:.1f} kg, {burden} "
            con.print(x0 + w - len(tag) - 2, y0, tag, fg=UI_DIM, bg=UI_BG)
        else:
            con.print(x0 + 2, y0, f" {title[: w - 6]} ", fg=UI_HI, bg=UI_BG)
            if len(self.sources) > 1:
                # every pile and body within reach, as tabs: [ and ] (or a click) to switch
                tx = x0 + 2
                for k, src in enumerate(self.sources):
                    lab = f" {getattr(src, 'tab', src.title)[:18]} "
                    if tx + len(lab) > x0 + w - 2:
                        con.print(tx, y0 + 1, "…", fg=UI_DIM, bg=UI_BG)
                        break
                    cur = k == self.src_idx
                    con.print(tx, y0 + 1, lab, fg=UI_HI if cur else UI_DIM, bg=UI_SEL_BG if cur else UI_BG)
                    self.cells.append(dict(kind="tab", pane=pane, idx=k, item=None, rect=(tx, y0 + 1, len(lab), 1)))
                    tx += len(lab) + 1
                con.print(x0 + w - 16, y0 + h - 1, " [ ] other piles ", fg=UI_DIM, bg=UI_BG)
        pane.rect = (x0, y0, w, h)
        if pane.ground is not None:
            self._draw_ground(con, pane, x0 + 2, y0 + 2)
        else:
            self._draw_kit(con, pane, x0, y0, w, h)
        # footer help / info
        if pane is self.own:
            info = self.info or self._hover_text()
            lines = textwrap.wrap(info, w - 4)[:3]
            for i, line in enumerate(lines):
                con.print(x0 + 2, y0 + h - 5 + i, line, fg=UI_TEXT, bg=UI_BG)
            con.print(x0 + 2, y0 + h - 2, "Enter pick/drop  r rotate  e use/equip  l load  u unload  c count  d drop  x look"[: w - 4],
                      fg=UI_DIM, bg=UI_BG)
            if self.sources:
                con.print(x0 + 2, y0 + h - 1, " Tab: switch side  q: quick move ", fg=UI_DIM, bg=UI_BG)

    def _hover_text(self):
        if not self.cells:
            return ""
        c = self.cells[self.cursor % len(self.cells)]
        it = c.get("item")
        if it is None:
            if c["kind"] == "slot":
                return f"{SLOT_NAME[c['slot']]}: empty."
            return ""
        t = it.t
        bits = [it.name]
        if t.kind == "gun":
            bits.append(f"[{it.ammo_estimate()}]")
        if t.kind == "mag":
            bits.append(f"[{it.rounds_text()}]")
        bits.append(f"{it.weight:.1f} kg")
        return " ".join(bits) + ". " + (t.desc[:110] if t.desc else "")

    def _kit_blocks(self, pane):
        """(label, [(grid, loc)]) groups for a kit."""
        inv = pane.inv
        blocks = []
        rig = inv.slots["rig"]
        if rig is not None:
            blocks.append((rig.name, [(g, "rig") for g in container_grids(rig)]))
        blocks.append(("Pockets", [(g, "pockets") for g in inv.pockets] +
                       ([(g, "pockets") for g in container_grids(inv.slots["body"])]
                        if inv.slots["body"] is not None and inv.slots["body"].t.get("grids") else [])))
        pack = inv.slots["pack"]
        if pack is not None and pack.t.get("grids"):
            blocks.append((pack.name, [(g, "pack") for g in container_grids(pack)]))
        return blocks

    def _draw_kit(self, con, pane, x0, y0, w, h):
        inv = pane.inv
        # equipment column
        sx = x0 + 2
        sy = y0 + 2
        slot_w = 24 if w > 50 else w - 4
        for s in SLOTS:
            it = inv.slots[s]
            name = SLOT_NAME[s].split(" (")[0]
            con.print(sx, sy, f"{name[:9]:9}", fg=UI_DIM, bg=UI_BG)
            box_x = sx + 10
            txt = it.name if it is not None else "-"
            if it is not None and it.t.kind == "gun" and it.t.cat not in ("melee",):
                txt = f"{it.t.name} [{it.ammo_estimate()}]"
            hands = pane is self.own and it is not None and it is self.game.player.weapon
            col = (255, 240, 170) if hands else (UI_TEXT if it is not None else UI_DIM)
            con.print(box_x, sy, txt[: slot_w - 10 + (0 if w > 50 else 10)], fg=col,
                      bg=(40, 36, 26) if it is not None else UI_BG)
            if hands:
                con.print(box_x - 1, sy, "»", fg=(255, 220, 120), bg=UI_BG)
            self.cells.append(dict(kind="slot", slot=s, pane=pane, item=it,
                                   rect=(box_x, sy, max(4, slot_w - 10), 1)))
            sy += 2 if w > 50 else 1
        if pane is self.own and inv.hands is not None:
            con.print(sx, sy, "Hands", fg=UI_DIM, bg=UI_BG)
            con.print(sx + 10, sy, inv.hands.name[:20], fg=(255, 240, 170), bg=(40, 36, 26))
            self.cells.append(dict(kind="hands", pane=pane, item=inv.hands, rect=(sx + 10, sy, 12, 1)))
            sy += 2
        # grids
        gx0 = x0 + 2 + (slot_w + 2 if w > 50 else 0)
        gy = y0 + 2 if w > 50 else sy + 1
        maxw = x0 + w - 2
        blocks = self._kit_blocks(pane)
        pane.page = min(pane.page, max(0, len(blocks) - 1))
        pane.more = False
        if pane.page:
            con.print(gx0, gy, f"(PgUp: the first {pane.page} section{'s' if pane.page > 1 else ''})", fg=UI_DIM,
                      bg=UI_BG)
            gy += 1
        for bi, (label, grids) in enumerate(blocks[pane.page:]):
            if gy >= y0 + h - 7:
                pane.more = True
                break
            con.print(gx0, gy, label[: maxw - gx0], fg=UI_FRAME, bg=UI_BG)
            gy += 1
            cx = gx0
            row_h = 0
            for g, loc in grids:
                gw, gh = g.w * CW, g.h * CH
                if cx + gw > maxw:
                    cx = gx0
                    gy += row_h + 1
                    row_h = 0
                if gy + gh >= y0 + h - 5:
                    pane.more = True
                    break
                self._draw_grid(con, pane, g, cx, gy)
                cx += gw + 1
                row_h = max(row_h, gh)
            gy += row_h + 1
        if pane.more:
            con.print(gx0, y0 + h - 6 if pane is not self.own else y0 + h - 7, " ▼ more below - PgDn ",
                      fg=(220, 200, 140), bg=UI_BG)

    def _draw_grid(self, con, pane, g, x, y):
        # empty cells
        for i in range(g.w):
            for j in range(g.h):
                if g.cells[i][j] is None:
                    bx, by = x + i * CW, y + j * CH
                    for dx in range(CW):
                        for dy in range(CH):
                            con.print(bx + dx, by + dy, "·" if (dx, dy) == (1, 0) else " ", fg=(60, 56, 44), bg=(24, 22, 17))
                self.cells.append(dict(kind="grid", pane=pane, grid=g, x=i, y=j, item=g.cells[i][j],
                                       rect=(x + i * CW, y + j * CH, CW, CH)))
        # items
        for it in g.items:
            if it.gpos is None or it.grid is not g:
                continue
            ix, iy = it.gpos
            w, h = it.dims()
            self._draw_item_block(con, it, x + ix * CW, y + iy * CH, w * CW, h * CH)

    def _draw_item_block(self, con, it, x, y, w, h):
        base = KIND_COL.get(it.t.kind, (80, 80, 80))
        sel = self.cells and self.cells[self.cursor % len(self.cells)].get("item") is it
        bg = tuple(min(255, int(c * 1.5)) for c in base) if sel else base
        for dx in range(w):
            for dy in range(h):
                con.print(x + dx, y + dy, " ", bg=bg)
        lab = label_for(it)
        lines = textwrap.wrap(lab, max(1, w)) or [lab]
        for k, line in enumerate(lines[: max(1, h - (1 if h > 1 else 0))]):
            con.print(x, y + k, line[:w], fg=(240, 235, 215), bg=bg)
        tag = ""
        t = it.t
        if t.kind == "mag":
            tag = it.rounds_text()
        elif t.kind == "gun" and t.mag > 1:
            tag = it.ammo_estimate()
        elif it.count > 1:
            tag = f"x{it.count}"
        if it.data and it.data.get("live") is not None:
            tag = "LIVE!"
        if tag:
            con.print(x + max(0, w - len(tag)), y + h - 1, tag[:w], fg=(255, 230, 140), bg=bg)

    def _draw_ground(self, con, pane, x, y):
        g = pane.ground_grid(self.game)
        self.ground_layout[id(pane)] = g
        used = max((j for i in range(g.w) for j in range(g.h) if g.cells[i][j] is not None), default=0) + 1
        pages = max(1, -(-used // 12))
        pane.page = min(pane.page, pages - 1)
        j0 = pane.page * 12
        pane.more = pages > 1
        for i in range(g.w):
            for j in range(j0, j0 + 12):
                self.cells.append(dict(kind="ground", pane=pane, grid=g, x=i, y=j, item=g.cells[i][j],
                                       rect=(x + i * CW, y + (j - j0) * CH, CW, CH)))
                if g.cells[i][j] is None:
                    con.print(x + i * CW + 1, y + (j - j0) * CH, "·", fg=(60, 56, 44), bg=(24, 22, 17))
        seen = set()
        for i in range(g.w):
            for j in range(j0, j0 + 12):
                it = g.cells[i][j]
                if it is None or id(it) in seen:
                    continue
                seen.add(id(it))
                w, h = it.dims(False)
                if not (i + w <= g.w and all(g.cells[i + a][j] is it for a in range(w))):
                    w, h = it.dims(True)
                h = min(h, j0 + 12 - j)
                self._draw_item_block(con, it, x + i * CW, y + (j - j0) * CH, w * CW, h * CH)
        if pages > 1:
            con.print(x, y + 12 * CH, f" page {pane.page + 1}/{pages} - PgUp/PgDn ", fg=UI_DIM, bg=UI_BG)

    # ================================================================== input
    def on_key(self, key):
        p = self.game.player
        if self.menu is not None:
            return self._menu_key(key)
        # letters are actions on this screen (l load, u unload...): only arrows and the numpad move
        mv = key.move() if key.char is None or not key.char.isalpha() else None
        if key.sym == E.KeySym.ESCAPE:
            if self.held is not None:
                self.held = None
                self.say("")
                return
            self.play.inv_screen = None
            return
        if key.sym == E.KeySym.TAB and self.sources:
            self.focus = 1 - self.focus
            self._jump_to_focus()
            return
        if key.sym in (E.KeySym.PAGEDOWN, E.KeySym.PAGEUP):
            pane = self.own if self.focus == 0 or self.loot is None else self.loot
            if key.sym == E.KeySym.PAGEDOWN and pane.more:
                pane.page += 1
            elif key.sym == E.KeySym.PAGEUP and pane.page > 0:
                pane.page -= 1
            return
        if mv:
            self._move_cursor(*mv)
            return
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
            return self._activate()
        c = key.char
        if c is None:
            return
        cell = self.cells[self.cursor % len(self.cells)] if self.cells else None
        it = cell.get("item") if cell else None
        if c == "r" and self.held is not None:
            self.held_rot = not self.held_rot
            return
        if c == "[" and self.sources:
            self.src_idx = (self.src_idx - 1) % len(self.sources)
            return
        if c == "]" and self.sources:
            self.src_idx = (self.src_idx + 1) % len(self.sources)
            return
        if c == "i":
            self.play.inv_screen = None
            return
        if self.held is not None and c in ("e", "l", "u", "c", "d", "q"):
            self.say("Put down what you're holding first (Enter), or Esc to put it back.")
            return
        if it is None:
            return
        if c == "e":
            return self.use(it, cell)
        if c == "l":
            return self.load(it)
        if c == "u":
            return self.do_unload(it)
        if c == "c":
            return self.count(it)
        if c == "d":
            return self.drop(it, cell)
        if c == "x":
            self.say(f"{it.name}: {it.t.desc}")
            return
        if c == "q":
            return self.quick_move(it, cell)

    def _jump_to_focus(self):
        want = self.own if self.focus == 0 else self.loot
        for k, c in enumerate(self.cells):
            if c["pane"] is want and c["kind"] != "tab":
                self.cursor = k
                return

    def _move_cursor(self, dx, dy):
        if not self.cells:
            return
        cur = self.cells[self.cursor % len(self.cells)]
        cx = cur["rect"][0] + cur["rect"][2] / 2
        cy = cur["rect"][1] + cur["rect"][3] / 2
        best = None
        bs = 1e9
        for k, c in enumerate(self.cells):
            if c is cur:
                continue
            x = c["rect"][0] + c["rect"][2] / 2
            y = c["rect"][1] + c["rect"][3] / 2
            ddx, ddy = x - cx, y - cy
            along = ddx * dx + ddy * dy * 2
            if along <= 0.1:
                continue
            perp = abs(ddx * dy) + abs(ddy * dx) * 2
            s = along + perp * 2.5
            if s < bs:
                bs, best = s, k
        if best is not None:
            self.cursor = best
            self.focus = 0 if self.cells[best]["pane"] is self.own else 1

    def on_mouse_motion(self, tx, ty):
        k = self._cell_at(tx, ty)
        if k is not None:
            self.cursor = k
            self.focus = 0 if self.cells[k]["pane"] is self.own else 1
        if self.menu is not None:
            it = self.menu.item_at(tx, ty)
            if it is not None:
                self.menu.sel = it

    def _cell_at(self, tx, ty):
        for k, c in enumerate(self.cells):
            x, y, w, h = c["rect"]
            if x <= tx < x + w and y <= ty < y + h:
                return k
        return None

    def on_click(self, tx, ty, button):
        if self.menu is not None:
            it = self.menu.item_at(tx, ty)
            if it is not None and button == 1:
                self.menu.sel = it
                return self._menu_select()
            self.menu = None
            return
        k = self._cell_at(tx, ty)
        if k is None:
            # clicking outside the panes closes the screen
            inside = any(p.rect[0] <= tx < p.rect[0] + p.rect[2] and p.rect[1] <= ty < p.rect[1] + p.rect[3]
                         for p in [self.own] + ([self.loot] if self.loot else []))
            if not inside and self.held is None:
                self.play.inv_screen = None
            return
        self.cursor = k
        cell = self.cells[k]
        if cell["kind"] == "tab":
            self.src_idx = cell["idx"]
            return
        if button == 3:
            if cell.get("item") is not None and self.held is None:
                self.open_menu(cell["item"], cell)
            return
        if self.held is None and cell.get("item") is not None:
            self._pick(cell)
            self.drag = True
        elif self.held is not None:
            self._drop_held(cell)

    def on_release(self, tx, ty, button):
        if self.drag and self.held is not None:
            k = self._cell_at(tx, ty)
            if k is not None and self.cells[k].get("item") is not self.held[0]:
                self.cursor = k
                self._drop_held(self.cells[k])
        self.drag = False

    # ================================================================== moving things
    def _activate(self):
        if not self.cells:
            return
        cell = self.cells[self.cursor % len(self.cells)]
        if cell["kind"] == "tab":
            self.src_idx = cell["idx"]
            return
        if self.held is None:
            if cell.get("item") is not None:
                self._pick(cell)
        else:
            self._drop_held(cell)

    def _pick(self, cell):
        it = cell["item"]
        self.held = (it, cell["pane"], cell)
        self.held_rot = it.rot if cell["kind"] == "grid" else False
        self.say(f"Holding {it.name}. Choose where it goes (r to rotate, Esc to put it back).")

    def _can_drop(self, cell):
        if self.held is None:
            return False
        it = self.held[0]
        k = cell["kind"]
        if k == "grid":
            if it.t.kind == "container" or it.tid == "backpack":
                if any(cell["grid"] is g for g in container_grids(it)):
                    return False                  # not inside itself
            return cell["grid"].fits(it, cell["x"], cell["y"], self.held_rot, ignore=it)
        if k == "slot":
            inv = cell["pane"].inv
            return inv._slot_ok(it, cell["slot"]) and inv.slots[cell["slot"]] in (None, it)
        if k == "ground":
            return True
        return False

    def _remove_from_origin(self, it, pane):
        game = self.game
        if pane.ground is not None:
            x, y = pane.ground
            game.map.remove_item(x, y, it)
            return 90
        cost = ACCESS.get(pane.inv.location(it), 100) // 2 + 30
        pane.inv.remove(it)
        if pane is self.own and game.player.weapon is it:
            game.player.weapon = None
        return cost

    def _drop_held(self, cell):
        game = self.game
        p = game.player
        it, origin, ocell = self.held
        # it must still be where it was picked up (or the drop would make a second copy of it)
        still = (it in game.map.items_at(*origin.ground)) if origin.ground is not None else \
            (origin.inv is not None and origin.inv.contains(it))
        if not still:
            self.held = None
            self.say("It isn't there any more.")
            return
        if not self._can_drop(cell):
            self.say("It doesn't fit there.")
            return
        target = cell["pane"]
        cost = 0
        if cell["kind"] == "ground":
            if origin.ground is not None and tuple(origin.ground) == tuple(target.ground):
                self.held = None                   # the same pile: nothing to do
                return
            cost += self._remove_from_origin(it, origin)   # (a pile beside it, a body, or your kit)
            x, y = target.ground
            game.map.add_item(x, y, it)
            it.grid = None
            cost += 40
        elif cell["kind"] == "grid":
            if origin is target and target.inv is not None and it.grid is not None:
                ok = target.inv.move(it, cell["grid"], cell["x"], cell["y"], self.held_rot)
                if not ok:
                    self.say("It doesn't fit there.")
                    return
                cost += 40 + ACCESS.get(target.inv.location(it), 80) // 3
            else:
                cost += self._remove_from_origin(it, origin)
                cell["grid"].place(it, cell["x"], cell["y"], self.held_rot)
                it.where = target.inv.location(it)
                cost += 40
        elif cell["kind"] == "slot":
            cost += self._remove_from_origin(it, origin)
            target.inv.slots[cell["slot"]] = it
            it.grid = None
            it.where = cell["slot"]
            cost += 60 if cell["slot"] not in ("head", "body", "rig", "pack") else 250
            me = self.game.player
            if target.inv is me.invent:
                if cell["slot"] == "head":
                    from .actions import _enemy_helmet_warning
                    _enemy_helmet_warning(self.game, me, it)
                elif it.t.kind == "gun":
                    from .familiar import first_look
                    first_look(self.game, me, it.t)
        self.held = None
        live = it.data and it.data.get("live") is not None
        if live and origin.ground is not None and target is not origin:
            game.pick_live(it, p)                  # in your hand (or pouch) now - and still ticking
        elif live and target.ground is not None and origin.ground is None:
            game.drop_live(it, *target.ground)
        self.say(f"You move the {it.name}." + (" It's still live!" if live else ""))
        self.spend(cost)

    def quick_move(self, it, cell):
        """Move an item straight to the other side (loot <-> kit)."""
        game = self.game
        p = game.player
        src = cell["pane"]
        if src is self.own:
            dst = self.loot
            if dst is None:
                return self.drop(it, cell)
            cost = self._remove_from_origin(it, src)
            if dst.ground is not None:
                game.map.add_item(dst.ground[0], dst.ground[1], it)
            elif dst.inv.add(it) is None:
                if p.add_item(it) is None:
                    game.map.add_item(p.x, p.y, it)       # (never into thin air: at worst, at your feet)
                self.say("No room on the other side.")
                return
        else:
            if src.ground is not None:
                from .actions import pickup
                c = pickup(game, p, it, *src.ground)
                if c is None:
                    if it.t.kind in ("gun", "melee"):
                        # the trade (drop yours, take his) is a decision: make it outside the kit screen
                        self.play.inv_screen = None
                        return self.play._no_room(it, *src.ground)
                    self.say("No room for that. Make some: drop or move something (d), or wear it (e).")
                    return
                self.say(f"You take the {it.name}.")
                return self.spend(c)
            src.inv.remove(it)
            if p.add_item(it) is None:
                if src.inv.add(it) is None:
                    game.map.add_item(p.x, p.y, it)
                self.say("No room for that.")
                return
            cost = 120
        self.say(f"You move the {it.name}.")
        self.spend(cost)

    def drop(self, it, cell):
        game = self.game
        p = game.player
        pane = cell["pane"]
        if pane.ground is not None:
            return
        cost = self._remove_from_origin(it, pane)
        game.map.add_item(p.x, p.y, it)
        self.say(f"You drop the {it.name}.")
        self.spend(cost)

    # ================================================================== using things
    def use(self, it, cell):
        game = self.game
        p = game.player
        t = it.t
        pane = cell["pane"]
        if pane is not self.own:
            return self.quick_move(it, cell)
        if t.kind in ("gun", "melee"):
            from .actions import wield
            c = wield(game, p, it)
            if c is None:
                self.say("Your hands are full.")
                return
            self.say(f"You take the {t.name} in hand.")
            return self.spend(c)
        if t.kind in ("armor", "container") or it.tid == "backpack":
            slot = p.invent.best_slot(it)
            if slot is None:
                self.say("You're already wearing something there.")
                return
            p.invent.remove(it)
            p.invent.slots[slot] = it
            self.say(f"You put on the {t.name}.")
            return self.spend(300)
        if t.kind == "mag":
            return self.load(it)
        # hand off to the normal item actions (medical, tools, food...)
        self.play.inv_screen = None
        self.play.item_action(it, "self" if t.kind == "medical" else "use")

    def load(self, it):
        game = self.game
        p = game.player
        t = it.t
        if t.kind == "gun":
            c = ammo_reload(game, p, it)
            if c is None:
                self.say("You have nothing to load it with.")
                return
            self.say(f"You reload the {t.name}.")
            return self.spend(c)
        if t.kind == "mag":
            if it.loaded >= t.mag:
                self.say("It's full.")
                return
            n = fill_magazine(p, it)
            if n == 0:
                self.say(f"You have no loose {t.cal} rounds to fill it with.")
                return
            self.say(f"You thumb {n} rounds into the magazine.")
            return self.spend(min(1500, 50 * n))
        self.say("That doesn't take ammunition.")

    def do_unload(self, it):
        game = self.game
        p = game.player
        t = it.t
        if t.kind == "gun":
            spill = unload(p, it)
            if spill is not None:
                game.map.add_item(p.x, p.y, spill)
            self.say(f"You unload the {t.name}.")
            return self.spend(120)
        if t.kind == "mag" and it.loaded > 0:
            from .data.items import ammo_id
            rounds = Item(ammo_id(t.cal), it.loaded)
            it.loaded = 0
            if p.add_item(rounds) is None:
                game.map.add_item(p.x, p.y, rounds)
            self.say("You strip the rounds out of the magazine.")
            return self.spend(40 * max(1, rounds.count // 3))
        self.say("Nothing to unload.")

    def count(self, it):
        t = it.t
        if t.kind in ("mag", "gun"):
            it.known_rounds = True
            self.say(f"You count them: {it.loaded} round{'s' if it.loaded != 1 else ''}.")
            return self.spend(150 if t.kind == "mag" else 100)
        self.say(f"{it.name}.")

    # ================================================================== context menu
    def open_menu(self, it, cell):
        from .render import Popup
        t = it.t
        opts = []
        mine = cell["pane"] is self.own
        if not mine:
            opts.append(("Take it", "take", None, True))
        if t.kind in ("gun", "melee") and mine:
            opts.append(("Take in hand", "use", None, True))
        if t.kind == "gun" and t.mag > 1:
            opts.append(("Reload", "load", None, True))
            opts.append(("Unload", "unload", None, True))
            opts.append(("Check the rounds", "count", None, True))
        if t.kind == "mag":
            opts.append(("Fill from loose rounds", "load", None, True))
            opts.append(("Empty it", "unload", None, True))
            opts.append(("Count the rounds", "count", None, True))
        if t.kind in ("medical", "tool") and mine:
            opts.append(("Use", "use", None, True))
        if t.kind in ("armor", "container") and mine and cell["kind"] != "slot":
            opts.append(("Wear it", "use", None, True))
        if cell["kind"] == "grid":
            opts.append(("Move it", "move", None, True))
        if mine:
            opts.append(("Drop it", "drop", None, True))
        opts.append(("Look it over", "look", None, True))
        x, y, w, h = cell["rect"]
        self.menu = Popup(it.name, opts, (x + w - 1, y))
        self.menu.data["item"] = it
        self.menu.data["cell"] = cell

    def _menu_key(self, key):
        m = self.menu
        if key.sym == E.KeySym.ESCAPE:
            self.menu = None
            return
        if key.sym in (E.KeySym.UP, E.KeySym.KP_8):
            m.move(-1)
            return
        if key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
            m.move(1)
            return
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
            return self._menu_select()
        if key.char:
            idx = m.index_of_letter(key.char)
            if idx is not None:
                m.sel = idx
                return self._menu_select()

    def _menu_select(self):
        m = self.menu
        self.menu = None
        act = m.options[m.sel][1]
        it = m.data["item"]
        cell = m.data["cell"]
        if act == "take":
            return self.quick_move(it, cell)
        if act == "use":
            return self.use(it, cell)
        if act == "load":
            return self.load(it)
        if act == "unload":
            return self.do_unload(it)
        if act == "count":
            return self.count(it)
        if act == "drop":
            return self.drop(it, cell)
        if act == "move":
            return self._pick(cell)
        if act == "look":
            self.say(f"{it.name}: {it.t.desc}")


def loot_sources_at(game, x, y, reach=0):
    """Loose items and bodies on a tile (and the tiles within reach), as panes: what's underfoot first."""
    from .constants import COMPASS
    panes = []
    m = game.map
    spots = [(x, y)] + [(x + dx, y + dy) for dy in range(-reach, reach + 1) for dx in range(-reach, reach + 1)
                        if (dx or dy) and m.in_bounds(x + dx, y + dy)]
    for sx, sy in spots:
        where = "" if (sx, sy) == (x, y) else f" ({COMPASS.get((sx - x, sy - y), '')})"
        loose = [i for i in m.items_at(sx, sy) if i.t.kind != "corpse"]
        if loose:
            p = Pane(f"On the ground{where}", ground=(sx, sy))
            p.tab = f"Ground{where} ({len(loose)})"
            panes.append(p)
        for it in m.items_at(sx, sy):
            if it.t.kind == "corpse" and it.data and it.data.get("inv") is not None:
                d = it.data
                p = Pane(f"Searching {d.get('name', 'a body')}{where}", d["inv"])
                p.tab = f"{d.get('name', 'body').split()[-1]}{where}"
                panes.append(p)
    return panes
