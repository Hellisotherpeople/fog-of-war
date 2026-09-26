"""The general staff: your divisions, their strength, their orders - and the reserve.

G from the battlefield (or o on the war map).  Pick a division; attack, hold, move,
pull it into reserve, or send it reinforcements.  Wait at headquarters and let the
reports come in.
"""
from __future__ import annotations

import textwrap

import tcod.event as E

from .constants import SCREEN_H, SCREEN_W, UI_DIM, UI_HI, UI_SEL_BG, UI_TEXT
from . import oob as OB
from .operations import strength


class OperationsState:
    def __init__(self, app, game, play=None):
        self.app = app
        self.game = game
        self.play = play
        self.sel = 0
        self.note = ""
        self.picking = None          # ("attack"|"move"|"commit", [sectors]) while choosing a target
        self.pick_sel = 0
        game.ops.organise(game)

    def _divs(self):
        ops = self.game.ops
        return sorted(ops.divs.items(), key=lambda kv: (kv[1].get("corps") or 0, min(kv[1]["sectors"])))

    def render(self, con):
        con.clear()
        g = self.game
        ops = g.ops
        cmd = g.command
        p = g.player
        st = g.strategic
        tot = ops.totals(g)
        title = cmd.billet_title(g) or f"{p.rank_full} {p.name}"
        con.print(2, 1, f"GENERAL STAFF - {title}", fg=UI_HI)
        ncorps = len(ops.corps)
        ech = next((d.get("echelon", "division") for d in ops.divs.values()), "division")
        gech = next((c.get("echelon", "corps") for c in ops.corps.values()), "corps")
        plural = lambda w, n: w if n == 1 else (w if w.endswith(("corps", "s")) else w + "s")  # noqa: E731
        con.print(2, 2, f"{len(ops.divs)} {plural(ech, len(ops.divs))}"
                  + (f" in {ncorps} {plural(gech, ncorps)}" if ncorps else "") +
                  f":  {tot['men']:,} men   {tot['tanks']:,} tanks   {tot['guns']:,} guns"
                  f"      Chief of staff: {ops.chief}", fg=UI_TEXT)
        rs = strength(ops.reserve, g.player_nation)
        con.print(2, 3, f"Army reserve: {rs['men']:,} men, {rs['tanks']} tanks, {rs['guns']} guns"
                  + (f"   ({len(ops.arriving)} group{'s' if len(ops.arriving) != 1 else ''} on the road)"
                     if ops.arriving else ""), fg=(200, 190, 150))
        y = 5
        con.print(2, y, f"{ech.title():34} {'Sectors':26} {'Men':>7} {'Tanks':>5} {'Guns':>5}  Supply  Orders",
                  fg=UI_DIM)
        y += 1
        divs = self._divs()
        self.sel = min(self.sel, max(0, len(divs) - 1))
        # the rows (group headings and formations), scrolled to keep the selection in view
        rows = []
        last_corps = None
        for i, (did, d) in enumerate(divs):
            if d.get("corps") and d["corps"] != last_corps and d["corps"] in ops.corps:
                last_corps = d["corps"]
                rows.append(("head", ops.corps[d["corps"]]["name"]))
            rows.append(("div", i))
        room = SCREEN_H - 15 - y
        at = next((k for k, r in enumerate(rows) if r == ("div", self.sel)), 0)
        top = max(0, min(at - room // 2, len(rows) - room))
        if top > 0:
            con.print(SCREEN_W - 14, y - 1, f"↑ {top} more", fg=UI_DIM)
        if top + room < len(rows):
            con.print(SCREEN_W - 14, y + room, f"↓ {len(rows) - top - room} more", fg=UI_DIM)
        shown = rows[top:top + room]
        for kind, v in shown:
            if kind == "head":
                con.print(2, y, v, fg=(180, 170, 130))
                y += 1
                continue
            i = v
            did, d = divs[i]
            s = ops.div_strength(g, did)
            names = ", ".join(st.at(*k).name for k in sorted(d["sectors"]) if st.at(*k))[:26]
            sup = min((st.supply_of(p.side, st.at(*k)) for k in d["sectors"] if st.at(*k)), default=1.0)
            supw = "good" if sup >= 0.7 else "short" if sup >= 0.35 else "CUT OFF" if sup <= 0 else "poor"
            sel = i == self.sel
            bg = UI_SEL_BG if sel else None
            con.print(2, y, " " * (SCREEN_W - 4), bg=bg)
            status = d["status"]
            if d["order"] == "attack" and d["target"]:
                at = st.attack_on(*d["target"]) if hasattr(st, "attack_on") else None
                if at is not None and at["side"] == p.side:
                    status += " - fighting"
            if any(st.attack_on(*k) and st.attack_on(*k)["side"] != p.side for k in d["sectors"]
                   if hasattr(st, "attack_on")):
                status += " - UNDER ATTACK"
            if (g.sector.x, g.sector.y) in d["sectors"]:
                status += " (you are here)"
            con.print(2, y, f"{d['name'][:34]:34} {names:26} {s['men']:7,} {s['tanks']:5} {s['guns']:5}  "
                            f"{supw:6}  {status}"[:SCREEN_W - 4],
                      fg=UI_HI if sel else ((240, 120, 100) if supw == "CUT OFF" else UI_TEXT), bg=bg)
            y += 1
        if not divs:
            con.print(4, y, "Nothing on the war map answers to you at this rank. (Colonels and above command here.)",
                      fg=UI_DIM)
        # the commander of the selected formation
        ob = g.__dict__.get("oob")
        if divs and ob is not None and ob.node(divs[self.sel][0]) is not None:
            n = ob.node(divs[self.sel][0])
            rank, name, hist = ob.commander(g, n)
            subs = [ob.node(c) for c in n.children if ob.node(c) is not None]
            con.print(2, SCREEN_H - 13, (f"{n.name}: commanded by {rank} {name}"
                      + ("" if not hist else " (as history has it)")
                      + (f".  {len(subs)} {OB.level_name(ob.nation, subs[0].echelon)}"
                         f"{'s' if len(subs) != 1 else ''} under it." if subs else ""))[:SCREEN_W - 4],
                      fg=(200, 190, 150))
        # picking a target
        yy = SCREEN_H - 11
        if self.picking:
            kind, cands = self.picking
            con.print(2, yy, {"attack": "Attack which sector?", "move": "Move to which sector?",
                              "commit": "Send the reserve to which sector?",
                              "visit": "Go forward to where?"}[kind] + "  (↑↓, Enter, Esc)",
                      fg=(250, 200, 140))
            for j, c in enumerate(cands[:6]):
                sel = j == self.pick_sel
                own = c.control == p.side
                from .strategic import power
                k = st.__dict__.get("scale", 1.0)
                pw = power(c.units[c.control]) / k if c.control else 0
                est = "" if own else f"  enemy {'weak' if pw < 6 else 'strong' if pw > 15 else 'moderate'} (estimate)"
                if kind == "visit":
                    at = st.attack_on(c.x, c.y)
                    est = ("  - the fighting" if at is not None else "") + ("  (enemy ground)" if not own else "")
                con.print(4, yy + 1 + j, f"{c.name} - {c.biome}{est}", fg=UI_HI if sel else UI_TEXT,
                          bg=UI_SEL_BG if sel else None)
        else:
            keys = ["a  attack", "h  hold / dig in", "m  move", "r  into reserve", "c  commit reserve here",
                    "v  go and see", "w  wait at HQ", "Esc  close"]
            con.print(2, yy, "   ".join(keys), fg=(200, 190, 150))
            for j, line in enumerate(textwrap.wrap(self.note, SCREEN_W - 6)[:2]):
                con.print(2, yy + 1 + j, line, fg=(250, 220, 150))
        # the last reports
        rep = [m.text for m in g.messages if m.text.startswith("Situation report")][-2:]
        yy = SCREEN_H - 5
        for t in rep:
            for line in textwrap.wrap(t, SCREEN_W - 6)[:2]:
                if yy < SCREEN_H - 1:
                    con.print(2, yy, line, fg=UI_DIM)
                    yy += 1

    def _cands(self, kind, did):
        g = self.game
        st = g.strategic
        d = g.ops.divs[did]
        out = []
        if kind == "visit":
            # the division's own sectors (the jump-off line) and, if an attack's on, the fighting itself
            here = (g.sector.x, g.sector.y)
            for k in sorted(d["sectors"]):
                c = st.at(*k)
                if c is not None and k != here:
                    out.append(c)
            if d["order"] == "attack" and d["target"]:
                c = st.at(*d["target"])
                if c is not None and st.attack_on(c.x, c.y) is not None:
                    out.insert(0, c)
            for k in d["sectors"]:
                c = st.at(*k)
                if c is not None and st.attack_on(c.x, c.y) is not None and c not in out[:1]:
                    out.insert(0, c)
            return out
        seen = set()
        for k in d["sectors"]:
            c0 = st.at(*k)
            if c0 is None:
                continue
            for n in st.neighbors(c0, create=True):
                if (n.x, n.y) in seen or not n.playable:
                    continue
                if kind == "attack" and n.control != g.player_side:
                    out.append(n)
                    seen.add((n.x, n.y))
                elif kind in ("move", "commit") and n.control == g.player_side:
                    out.append(n)
                    seen.add((n.x, n.y))
        if kind == "commit":
            out = [st.at(*k) for k in d["sectors"] if st.at(*k)] + out
        return out

    def on_key(self, key):
        g = self.game
        c = key.char
        divs = self._divs()
        if self.picking:
            kind, cands = self.picking
            if key.sym in (E.KeySym.UP, E.KeySym.KP_8):
                self.pick_sel = (self.pick_sel - 1) % max(1, len(cands))
            elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
                self.pick_sel = (self.pick_sel + 1) % max(1, len(cands))
            elif key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER) and cands:
                tgt = cands[self.pick_sel]
                did = divs[self.sel][0]
                if kind == "commit":
                    self.note = g.ops.commit(g, (tgt.x, tgt.y))
                elif kind == "visit":
                    self.picking = None
                    self.note = g.go_forward((tgt.x, tgt.y))
                    g.msg(self.note, "info")
                    if (g.sector.x, g.sector.y) == (tgt.x, tgt.y):
                        self.app.pop()
                        if self.play is not None:
                            self.play.after_travel() if hasattr(self.play, "after_travel") else None
                    return
                else:
                    self.note = g.ops.order(g, did, kind, (tgt.x, tgt.y))
                g.msg(f"Orders: {self.note}", "radio")
                self.picking = None
            elif key.sym == E.KeySym.ESCAPE:
                self.picking = None
            return
        if key.sym in (E.KeySym.UP, E.KeySym.KP_8):
            self.sel = (self.sel - 1) % max(1, len(divs))
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
            self.sel = (self.sel + 1) % max(1, len(divs))
        elif key.sym == E.KeySym.ESCAPE or c in ("G", "q"):
            self.app.pop()
        elif divs and c in ("a", "m", "c", "v"):
            kind = {"a": "attack", "m": "move", "c": "commit", "v": "visit"}[c]
            cands = self._cands(kind, divs[self.sel][0])
            if not cands:
                self.note = {"attack": "No enemy ground next to that division.",
                             "move": "Nowhere of ours to move to from there.",
                             "commit": "Nowhere to send them.",
                             "visit": "You're already with that division."}[kind]
                return
            self.picking = (kind, cands)
            self.pick_sel = 0
        elif divs and c == "h":
            self.note = g.ops.order(g, divs[self.sel][0], "hold")
            g.msg(f"Orders: {self.note}", "radio")
        elif divs and c == "r":
            self.note = g.ops.order(g, divs[self.sel][0], "reserve")
            g.msg(f"Orders: {self.note}", "radio")
        elif c == "w" and self.play is not None:
            from .render import Popup
            self.app.pop()
            opts = [("Ten minutes", 600, None, True), ("Half an hour", 1800, None, True),
                    ("An hour", 3600, None, True), ("Until something happens", 7200, None, True)]
            self.play.open_popup(Popup("Wait at headquarters", opts, self.play._screen_anchor()),
                                 lambda n: self.play.wait_at_hq(n))
