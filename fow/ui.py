"""Application shell: window, event loop, menus and full-screen views."""
from __future__ import annotations

import math
import os
import random
import textwrap
import time
import traceback

import tcod
import tcod.event as E

from .constants import (ALLIES, AXIS, COMPASS, SCREEN_H, SCREEN_W, SIDE_COLOR, SUBTITLE, TITLE, UI_BG,
                        UI_DIM, UI_FRAME, UI_HI, UI_SEL_BG, UI_TEXT, VIEW_W, other_side)
from .data.nations import NATIONS
from .data.roles import PLAYER_ROLE_WEIGHTS, ROLES
from .data.theatres import THEATRES
from .play import Key, PlayState
from .render import draw_center_box

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

SPECIAL_KEYS = {
    E.KeySym.UP, E.KeySym.DOWN, E.KeySym.LEFT, E.KeySym.RIGHT, E.KeySym.RETURN, E.KeySym.KP_ENTER,
    E.KeySym.ESCAPE, E.KeySym.TAB, E.KeySym.BACKSPACE, E.KeySym.HOME, E.KeySym.END, E.KeySym.PAGEUP,
    E.KeySym.PAGEDOWN, E.KeySym.SPACE, E.KeySym.DELETE, E.KeySym.F1, E.KeySym.F2, E.KeySym.F3,
    E.KeySym.F12, E.KeySym.F5, E.KeySym.KP_1, E.KeySym.KP_2, E.KeySym.KP_3, E.KeySym.KP_4, E.KeySym.KP_5,
    E.KeySym.KP_6, E.KeySym.KP_7, E.KeySym.KP_8, E.KeySym.KP_9, E.KeySym.KP_PERIOD, E.KeySym.KP_0,
}

TITLE_ART = [
    "███████  ██████   ██████       ██████  ███████     ██     ██  █████  ██████  ",
    "██      ██    ██ ██           ██    ██ ██          ██     ██ ██   ██ ██   ██ ",
    "█████   ██    ██ ██   ███     ██    ██ █████       ██  █  ██ ███████ ██████  ",
    "██      ██    ██ ██    ██     ██    ██ ██          ██ ███ ██ ██   ██ ██   ██ ",
    "██       ██████   ██████       ██████  ██           ███ ███  ██   ██ ██   ██ ",
]

SCENE = [
    "      ♣♣            §§§§§§§§§§§§           +   +          ≡≡≡≡          ♣     ",
    "   ♣♣♣♣♣  ░░░░░░░░░░░░░░░░░░░░░░░░░░   + + + +  o   ▲  ≡▒▒▒▒≡   ♣♣  ♣♣♣    ",
    "  ♣♣♣♣♣♣♣ ░ @ ░ @ ░  ░ @ ░░░ @ ░ @ ░    +   +     ▲▲▲ ≡▒@▒▒≡  ♣♣♣♣ ♣♣♣♣   ",
]


class MenuState:
    """A vertical list of choices with a description pane."""

    def __init__(self, app, title, options, on_select, subtitle="", on_back=None, width=44):
        self.app = app
        self.title = title
        self.options = options        # (label, value, description, color)
        self.on_select = on_select
        self.subtitle = subtitle
        self.on_back = on_back
        self.sel = 0
        self.width = width
        self.item_rows = {}

    def render(self, con):
        con.clear()
        x0 = 4
        con.print(x0, 2, self.title, fg=UI_HI)
        if self.subtitle:
            for i, line in enumerate(textwrap.wrap(self.subtitle, SCREEN_W - 8)):
                con.print(x0, 3 + i, line, fg=UI_DIM)
        y = 6
        self.item_rows = {}
        top = max(0, self.sel - (SCREEN_H - 12))
        for i, (label, value, desc, col) in enumerate(self.options[top:], start=top):
            if y >= SCREEN_H - 3:
                break
            sel = i == self.sel
            letter = "abcdefghijklmnopqrstuvwxyz"[i] if i < 26 else " "
            bg = UI_SEL_BG if sel else None
            con.print(x0, y, " " * self.width, bg=bg)
            con.print(x0, y, f"{letter}) ", fg=UI_DIM, bg=bg)
            con.print(x0 + 3, y, label[: self.width - 4], fg=col or (UI_HI if sel else UI_TEXT), bg=bg)
            self.item_rows[y] = i
            y += 1
        # description pane
        desc = self.options[self.sel][2] if self.options else ""
        dx = x0 + self.width + 3
        dw = SCREEN_W - dx - 3
        con.draw_frame(dx - 1, 5, dw + 2, SCREEN_H - 9, clear=False, fg=(70, 65, 45))
        yy = 6
        for para in (desc or "").split("\n"):
            for line in textwrap.wrap(para, dw - 1) or [""]:
                if yy >= SCREEN_H - 5:
                    break
                con.print(dx, yy, line, fg=UI_TEXT)
                yy += 1
        con.print(x0, SCREEN_H - 2, "↑↓/letter to choose, Enter to confirm, Esc to go back. Mouse works too.", fg=UI_DIM)

    def on_key(self, key: Key):
        if key.sym in (E.KeySym.UP, E.KeySym.KP_8) or key.char == "k" and False:
            self.sel = (self.sel - 1) % len(self.options)
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
            self.sel = (self.sel + 1) % len(self.options)
        elif key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
            self.on_select(self.options[self.sel][1])
        elif key.sym == E.KeySym.ESCAPE:
            if self.on_back:
                self.on_back()
            else:
                self.app.pop()
        elif key.char and key.char in "abcdefghijklmnopqrstuvwxyz":
            i = "abcdefghijklmnopqrstuvwxyz".index(key.char)
            if i < len(self.options):
                self.sel = i
                self.on_select(self.options[i][1])

    def on_mouse_motion(self, tx, ty):
        if ty in self.item_rows and 4 <= tx < 4 + self.width:
            self.sel = self.item_rows[ty]

    def on_click(self, tx, ty, button):
        if ty in self.item_rows and 4 <= tx < 4 + self.width and button == 1:
            self.sel = self.item_rows[ty]
            self.on_select(self.options[self.sel][1])

    def on_wheel(self, dy):
        self.sel = (self.sel - dy) % len(self.options)


class MainMenuState(MenuState):
    def __init__(self, app):
        opts = [("Quick start (everything random)", "quick",
                 "Thrown into a random battle of the war, on a random side, in a random role. "
                 "The war does not care whether you are ready.", None),
                ("New game", "new", "The character and battle creator: side, battle, nation, battle type (front line, "
                                    "tank battle, night patrol, commando raid, agent behind the lines, partisans...), "
                                    "role, rank up to five stars, name, traits, weapon and kit. Leave any of it to chance.",
                 None)]
        from .game import SAVE_DIR
        if os.path.exists(os.path.join(SAVE_DIR, "save.pkl")):
            opts.insert(0, ("Continue", "continue", "Return to your war.", UI_HI))
        opts += [("How to play", "help", "Keys, mouse and a few hard-won lessons.", None),
                 ("Options", "options", "The sound mixer, display, safe mode, battlefield size, autosave.", None),
                 ("Memorial", "memorial", "The fallen.", None),
                 ("Quit", "quit", "Go home.", None)]
        super().__init__(app, "", opts, self.choose)

    def render(self, con):
        con.clear()
        for i, line in enumerate(TITLE_ART):
            con.print((SCREEN_W - len(line)) // 2, 3 + i, line, fg=(200, 170, 90))
        con.print((SCREEN_W - len(SUBTITLE)) // 2, 9, SUBTITLE, fg=UI_DIM)
        for i, line in enumerate(SCENE):
            x = (SCREEN_W - len(line)) // 2
            for j, ch in enumerate(line):
                col = {"♣": (50, 120, 50), "§": (150, 150, 150), "░": (120, 100, 60), "@": (220, 200, 140),
                       "+": (170, 170, 160), "≡": (200, 180, 120), "▒": (90, 90, 90), "▲": (130, 120, 110),
                       "o": (110, 90, 70)}.get(ch, (60, 60, 60))
                con.print(x + j, 11 + i, ch, fg=col)
        y = 16
        self.item_rows = {}
        for i, (label, value, desc, col) in enumerate(self.options):
            sel = i == self.sel
            x = (SCREEN_W - 40) // 2
            con.print(x, y, " " * 40, bg=UI_SEL_BG if sel else None)
            con.print(x + 2, y, f"{'abcdefghij'[i]})  {label}", fg=col or (UI_HI if sel else UI_TEXT),
                      bg=UI_SEL_BG if sel else None)
            self.item_rows[y] = i
            y += 2
        desc = self.options[self.sel][2]
        for i, line in enumerate(textwrap.wrap(desc, 70)):
            con.print((SCREEN_W - 70) // 2, y + 1 + i, line, fg=UI_DIM)
        con.print(2, SCREEN_H - 2, "A turn-based war simulator in the spirit of Cataclysm: DDA. Built on libtcod.",
                  fg=(80, 75, 60))

    def on_mouse_motion(self, tx, ty):
        if ty in self.item_rows:
            self.sel = self.item_rows[ty]

    def on_click(self, tx, ty, button):
        if ty in self.item_rows and button == 1:
            self.sel = self.item_rows[ty]
            self.choose(self.options[self.sel][1])

    def on_key(self, key):
        if key.sym == E.KeySym.ESCAPE:
            self.app.quit()
            return
        super().on_key(key)

    def choose(self, v):
        app = self.app
        if v == "quit":
            app.quit()
        elif v == "help":
            app.push(HelpState(app, play=self.play))
        elif v == "memorial":
            app.push(MemorialState(app))
        elif v == "options":
            app.push(OptionsState(app))
        elif v == "continue":
            from .game import Game
            try:
                g = Game.load()
            except Exception as e:
                app.push(TextState(app, "Could not load", [f"The save could not be read: {e}"]))
                return
            app.push(PlayState(app, g))
        elif v == "quick":
            rng = random.Random()
            th = rng.choice(list(THEATRES))
            side = rng.choice((ALLIES, AXIS))
            nations = THEATRES[th]["sides"][side]
            nat = rng.choices([n for n, _ in nations], [w for _, w in nations])[0]
            r = rng.random()
            service = "air" if r < 0.08 else "navy" if r < 0.13 else "army"
            app.start_game(th, nat, None, dict(scenario="random", service=service))
        elif v == "new":
            app.push(CreatorState(app))


# ====================================================================== the character & scenario creator

KIT_CHOICES = [("binoculars", 1), ("map", 1), ("staff_map", 1), ("compass", 1), ("watch", 1), ("flaregun", 1),
               ("medkit", 1), ("morphine", 3), ("bandage", 4), ("plasma", 1), ("satchel", 2), ("wirecutters", 1),
               ("shovel", 1), ("canteen", 1), ("ration", 2), ("cigarettes", 3), ("mine_detector", 1),
               ("forged_papers", 1), ("civvies", 1), ("scr536", 1), ("flask", 1)]


class ChoiceMenu(MenuState):
    """Pick one value for a creator field."""

    def __init__(self, app, title, options, on_pick, subtitle=""):
        super().__init__(app, title, options, self._pick, subtitle=subtitle, width=56)
        self.on_pick = on_pick

    def _pick(self, v):
        self.app.pop()
        self.on_pick(v)


class ToggleMenu(MenuState):
    """Tick things on and off (traits, extra kit); Enter on 'Done' to finish."""

    def __init__(self, app, title, items, chosen, on_done, subtitle=""):
        self.items = items                    # (label, value, desc)
        self.chosen = set(chosen)
        self.on_done = on_done
        super().__init__(app, title, [], self._toggle, subtitle=subtitle, width=56)
        self._rebuild()

    def _rebuild(self):
        opts = [(("[x] " if v in self.chosen else "[ ] ") + lab, v, d, UI_HI if v in self.chosen else None)
                for lab, v, d in self.items]
        opts.append(("Done", "__done__", "Finished.", (220, 200, 120)))
        self.options = opts

    def _toggle(self, v):
        if v == "__done__":
            self.app.pop()
            self.on_done(self.chosen)
            return
        self.chosen ^= {v}
        self._rebuild()


class CreatorState:
    """Every choice in one place: who you are, where, when, what kind of fight, and with what."""

    ROWS = [("side", "Side"), ("theatre", "Battle"), ("nation", "Nation"), ("service", "Service"),
            ("scenario", "Battle type"),
            ("role", "Role"), ("unit", "Unit"), ("rank", "Rank"), ("name", "Name"), ("traits", "Traits"),
            ("weapon", "Weapon"),
            ("kit", "Extra kit"), ("fair", "Opening"), ("start", "")]

    def __init__(self, app):
        self.app = app
        self.v = dict(side="random", theatre="random", nation="random", service="army", scenario="random",
                      role="default", unit=None,
                      rank=None, name="", traits=None, weapon=None, kit={}, fair=False)
        self.sel = 0
        self.rows = {}

    # -------------------------------------------------------- the lists
    def _side(self):
        return self.v["side"] if self.v["side"] != "random" else None

    def _theatre(self):
        return self.v["theatre"] if self.v["theatre"] != "random" else None

    def _nation(self):
        return self.v["nation"] if self.v["nation"] != "random" else None

    def options(self, key):
        from .scenarios import SCENARIOS, eligible
        v = self.v
        if key == "side":
            return [("Leave it to chance", "random", "Conscription doesn't ask either.")] + \
                [("The Allies", ALLIES, "The United Nations at war."), ("The Axis", AXIS, "Germany and her allies.")]
        if key == "theatre":
            out = [("Leave it to chance", "random", "Somewhere, sometime, in the war.")]
            for tid, th in sorted(THEATRES.items(), key=lambda kv: kv[1]["date"]):
                out.append((f"{th['date'][0]}  {th['battle']}", tid, f"{th['name']}: {th['battle']}\n\n{th['desc']}"))
            return out
        if key == "nation":
            out = [("Leave it to chance (weighted by who fought there)", "random", "")]
            th = THEATRES.get(self._theatre()) if self._theatre() else None
            sides = [self._side()] if self._side() else [ALLIES, AXIS]
            seen = set()
            for sd in sides:
                pool = th["sides"][sd] if th else [(n, 1) for n in NATIONS if NATIONS[n]["side"] == sd]
                for n, w in pool:
                    if n not in seen:
                        seen.add(n)
                        out.append((NATIONS[n]["name"], n, NATIONS[n]["army"]))
            return out
        if key == "service":
            return [("Army (and marines)", "army", "The war on the ground."),
                    ("Air force (or naval aviation)", "air", "Fighters, bombers, dive and torpedo bombers: dogfights, "
                     "interceptions, escorts, ground attack, strategic bombing, reconnaissance."),
                    ("Navy", "navy", "Destroyers to battleships, carriers and submarines: surface actions, carrier "
                     "battles, convoys, submarine patrols, shore bombardment.")]
        if key == "scenario" and v.get("service") in ("air", "navy"):
            from .skysea_missions import AIR_MISSIONS, SEA_MISSIONS
            pool = AIR_MISSIONS if v["service"] == "air" else SEA_MISSIONS
            pre = "air:" if v["service"] == "air" else "sea:"
            return [("Leave it to chance (by your role)", "random", "")] + \
                [(t.split(":")[0], pre + k, t) for k, t in pool.items()]
        if key == "scenario":
            out = [("Leave it to chance", "random", "The war picks.")]
            th = THEATRES.get(self._theatre()) if self._theatre() else None
            for sid, sc in SCENARIOS.items():
                ok = th is None or self._side() is None or eligible(sid, th, self._side())
                out.append((sc["name"] + ("" if ok else "  (not possible here)"), sid, sc["desc"]))
            return out
        if key == "role":
            out = [("As the army (or the battle type) assigns", "default", ""),
                   ("Random", "random", "")]
            from .data.roles import COMMAND_ROLE_LIST
            from .data.roles import ROLE_GRADES
            from .data.ranks import rank_title
            n = self._nation() or "usa"
            from .data.roles import SERVICE_ROLES
            sv = v.get("service", "army")
            if sv in SERVICE_ROLES:
                order = list(SERVICE_ROLES[sv])
            else:
                order = list(PLAYER_ROLE_WEIGHTS) + ["platoon_sergeant", "first_sergeant", "sergeant_major", "agent",
                                                     "pilot", "partisan", "quartermaster", "intel", "surgeon"] + \
                    COMMAND_ROLE_LIST
            for r in order:
                lo, hi = ROLE_GRADES.get(r, (0, 18))
                rk = rank_title(n, lo, False, sv) + ("" if lo == hi else f" to {rank_title(n, hi, False, sv)}")
                out.append((ROLES[r]["name"], r, f"{ROLES[r]['desc']}\n\nRanks: {rk}."))
            return out
        if key == "unit":
            from .data.special import SPECIAL, eligible
            th = THEATRES.get(self._theatre()) if self._theatre() else None
            year = th["date"][0] + (th["date"][1] - 1) / 12 if th else None
            out = [("As the army decides (now and then, something special)", None, "Most men served in ordinary "
                    "line units. A few found themselves in something else."),
                   ("An ordinary line unit", "regular", "")]
            nats = [self._nation()] if self._nation() else [n for n in NATIONS]
            for sid, d in SPECIAL.items():
                ok = any(eligible(sid, n, year if year else d["years"][0], th["id"] if th else (d["theatres"] or [None])[0],
                                  v.get("service", "army")) for n in nats)
                if ok:
                    out.append((d["name"], sid, d["desc"] + ("\n\nRare." if d.get("ai", 0) < 0.01 else "")))
            return out
        if key == "rank":
            from .data.ranks import rank_title, stars
            from .data.roles import ROLE_GRADES
            n = self._nation() or "usa"
            out = [("As the role implies", None, "The usual rank for the job.")]
            role = v["role"]
            if role in ("default", "random"):
                return out + [("(choose a role first)", None, "Ranks depend on the job: a squad leader is a "
                                                              "corporal or sergeant, a platoon officer a lieutenant.")]
            lo, hi = ROLE_GRADES.get(role, (0, 18))
            sv = v.get("service", "army")
            for gr in range(lo, hi + 1):
                st = stars(gr)
                kind = "enlisted" if gr <= 1 else ("petty officer" if sv == "navy" else "NCO") if gr <= 7 else \
                    "officer" if gr <= 13 else ("flag officer" if sv == "navy" else "air officer" if sv == "air"
                                                else "general officer")
                out.append((f"{rank_title(n, gr, False, sv)}" + (f"  {'★' * len(st)}" if st else "") + f"  ({kind})",
                            gr, R_COMMAND.get(gr, "") if sv == "army" else ""))
            return out
        if key == "weapon":
            from .data.items import ITEMS
            from .data.nations import equip_sources
            th = THEATRES.get(self._theatre()) if self._theatre() else None
            year = th["date"][0] + (th["date"][1] - 1) / 12 if th else 1944
            n = self._nation()
            srcs = equip_sources(n, year) if n else []
            out = [("As issued for the role", None, "")]
            guns = [t for t in ITEMS.values() if t.kind == "gun" and t.get("years", (1900, 1950))[0] <= year <
                    t.get("years", (1900, 1950))[1]]
            guns.sort(key=lambda t: (0 if not srcs or any(s in (t.get("nations") or ()) for s in srcs) else 1,
                                     t.cat, t.name))
            for t in guns:
                own = not srcs or any(s in (t.get("nations") or ()) for s in srcs)
                out.append((t.name + ("" if own else "  (captured)"), t.id, getattr(t, "desc", "") or t.cat))
            return out
        return []

    def _value_label(self, key):
        if key == "start":
            return ">>> START <<<"
        v = self.v[key]
        if key == "name":
            return v or "(random)"
        if key == "traits":
            from .spawn import TRAITS
            return "random" if v is None else (", ".join(TRAITS[t] for t in sorted(v)) or "none")
        if key == "kit":
            from .data.items import ITEMS
            return ", ".join(ITEMS[t].name for t in v) or "nothing extra"
        if key == "fair":
            return "a fair start" if v else "whatever the war deals (wounded, jammed, lost...)"
        if key == "start":
            return ">>> START <<<"
        for lab, val, _ in self.options(key):
            if val == v:
                return lab
        return str(v)

    # -------------------------------------------------------- drawing
    def render(self, con):
        con.clear()
        x0 = 4
        con.print(x0, 2, "Character and battle", fg=UI_HI)
        con.print(x0, 3, "Choose anything - or leave it to chance. Enter picks from a list, arrows cycle, type a name.",
                  fg=UI_DIM)
        y = 6
        self.rows = {}
        for i, (key, label) in enumerate(self.ROWS):
            sel = i == self.sel
            bg = UI_SEL_BG if sel else None
            con.print(x0, y, " " * 70, bg=bg)
            if key == "start":
                con.print(x0 + 20, y, self._value_label(key), fg=(240, 210, 120), bg=bg)
            else:
                con.print(x0, y, f"{label:<12}", fg=UI_DIM, bg=bg)
                con.print(x0 + 13, y, self._value_label(key)[:56], fg=UI_HI if sel else UI_TEXT, bg=bg)
            self.rows[y] = i
            y += 2
        # description of what's under the cursor
        key = self.ROWS[self.sel][0]
        desc = ""
        if key in ("theatre", "scenario", "role", "nation", "weapon", "unit", "service"):
            for lab, val, d in self.options(key):
                if val == self.v[key]:
                    desc = d
        dx = x0 + 74
        dw = SCREEN_W - dx - 3
        con.draw_frame(dx - 1, 5, dw + 2, SCREEN_H - 9, clear=False, fg=(70, 65, 45))
        yy = 6
        for para in (desc or "").split("\n"):
            for line in textwrap.wrap(para, dw - 1) or [""]:
                if yy >= SCREEN_H - 5:
                    break
                con.print(dx, yy, line, fg=UI_TEXT)
                yy += 1
        con.print(x0, SCREEN_H - 2, "↑↓ choose a line  ←→ cycle  Enter pick  Esc back", fg=UI_DIM)

    # -------------------------------------------------------- input
    def _cycle(self, key, d):
        if key == "fair":
            self.v["fair"] = not self.v["fair"]
            return
        opts = self.options(key)
        if not opts:
            return
        vals = [o[1] for o in opts]
        i = vals.index(self.v[key]) if self.v[key] in vals else 0
        self.v[key] = vals[(i + d) % len(vals)]
        self._fixup(key)

    def _fixup(self, key):
        """Keep the choices consistent: a nation from the chosen side and battle, a rank that fits the job."""
        if key == "service":
            self.v["scenario"] = "random"
            self.v["role"] = "default"
            self.v["rank"] = None
        if key == "role" and self.v["rank"] is not None:
            from .data.roles import ROLE_GRADES
            lo, hi = ROLE_GRADES.get(self.v["role"], (0, 18))
            if self.v["role"] in ("default", "random") or not (lo <= self.v["rank"] <= hi):
                self.v["rank"] = None
        if key in ("side", "theatre"):
            n = self._nation()
            vals = [o[1] for o in self.options("nation")]
            if n and n not in vals:
                self.v["nation"] = "random"
        if key == "nation" and self._nation():
            sd = NATIONS[self._nation()]["side"]
            if self._side() != sd:
                self.v["side"] = sd

    def _open(self, key):
        app = self.app
        if key == "start":
            return self.start()
        if key == "fair":
            self.v["fair"] = not self.v["fair"]
            return
        if key == "name":
            return
        if key == "traits":
            from .spawn import TRAITS
            items = [(TRAITS[t], t, "") for t in TRAITS]
            return app.push(ToggleMenu(app, "Traits", items, self.v["traits"] or [],
                                       lambda ch: self.v.__setitem__("traits", sorted(ch))))
        if key == "kit":
            from .data.items import ITEMS
            items = [(f"{ITEMS[t].name}" + (f" x{n}" if n > 1 else ""), t, getattr(ITEMS[t], "desc", ""))
                     for t, n in KIT_CHOICES if t in ITEMS]
            return app.push(ToggleMenu(app, "Extra kit", items, list(self.v["kit"]),
                                       lambda ch: self.v.__setitem__("kit", {t: dict(KIT_CHOICES)[t] for t in ch})))
        label = dict(self.ROWS)[key]

        def pick(v, key=key):
            self.v[key] = v
            self._fixup(key)
        app.push(ChoiceMenu(app, label, [(lab, val, d, None) for lab, val, d in self.options(key)], pick))

    def on_key(self, key):
        k = self.ROWS[self.sel][0]
        if key.sym in (E.KeySym.UP, E.KeySym.KP_8):
            self.sel = (self.sel - 1) % len(self.ROWS)
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2, E.KeySym.TAB):
            self.sel = (self.sel + 1) % len(self.ROWS)
        elif key.sym in (E.KeySym.LEFT, E.KeySym.KP_4):
            self._cycle(k, -1)
        elif key.sym in (E.KeySym.RIGHT, E.KeySym.KP_6):
            self._cycle(k, 1)
        elif key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER):
            self._open(k)
        elif key.sym == E.KeySym.ESCAPE:
            self.app.pop()
        elif key.sym == E.KeySym.BACKSPACE and k == "name":
            self.v["name"] = self.v["name"][:-1]
        elif key.sym == E.KeySym.SPACE and k == "name":
            if self.v["name"] and len(self.v["name"]) < 30:
                self.v["name"] += " "
        elif key.sym == E.KeySym.SPACE:
            self._open(k)
        elif key.char and k == "name":
            if len(self.v["name"]) < 30:
                self.v["name"] += key.char
        elif key.char == " " and k != "name":
            self._open(k)

    def on_mouse_motion(self, tx, ty):
        if ty in self.rows:
            self.sel = self.rows[ty]

    def on_click(self, tx, ty, button):
        if ty in self.rows and button == 1:
            self.sel = self.rows[ty]
            self._open(self.ROWS[self.sel][0])

    # -------------------------------------------------------- go
    def start(self):
        rng = random.Random()
        v = self.v
        side = self._side() or (NATIONS[self._nation()]["side"] if self._nation() else rng.choice((ALLIES, AXIS)))
        nat = self._nation()
        th = self._theatre()
        if th is None:
            # a random battle - but one this nation fought, on this side
            fought = [t for t, d in THEATRES.items() if nat is None or any(n == nat for n, _ in d["sides"][side])]
            th = rng.choice(fought or list(THEATRES))
        if nat is None or nat not in [n for n, _ in THEATRES[th]["sides"][side]]:
            pool = THEATRES[th]["sides"][side]
            nat = rng.choices([n for n, _ in pool], [w for _, w in pool])[0]
        from .data.roles import SERVICE_ROLES
        if v["role"] == "default":
            role = None
        elif v["role"] == "random":
            sv = v["service"]
            role = rng.choice(SERVICE_ROLES[sv] if sv in SERVICE_ROLES else list(PLAYER_ROLE_WEIGHTS))
        else:
            role = v["role"]
        setup = dict(scenario=v["scenario"], service=v["service"], rank=v["rank"], name=v["name"] or None,
                     traits=v["traits"], unit=v["unit"],
                     weapon=v["weapon"], kit=dict(v["kit"]), fair=v["fair"], role_random=v["role"] == "random")
        self.app.start_game(th, nat, role, setup)


R_COMMAND = {0: "The lowest of the low.", 1: "A private who's lasted.", 2: "Leads a fire team.", 3: "Leads a squad.",
             4: "A senior squad leader.", 5: "Second in command of a platoon.",
             6: "The company's senior NCO.", 7: "The battalion's senior NCO.",
             8: "Leads a platoon.", 9: "Leads a platoon (and wishes it were a company).",
             10: "Commands a company.", 11: "A battalion's second in command, or on the staff.",
             12: "Commands a battalion.",
             13: "Commands a regiment.", 14: "Commands a brigade.", 15: "Commands a division.", 16: "Commands a corps.",
             17: "Commands an army.", 18: "Commands an army group - or a whole front."}


class BriefingState:
    def __init__(self, app, game):
        self.app = app
        self.game = game

    def render(self, con):
        con.clear()
        lines = []
        for l in self.game.briefing:
            if not l:
                lines.append(("", None))
                continue
            for i, w in enumerate(textwrap.wrap(l, SCREEN_W - 16)):
                col = UI_HI if l is self.game.briefing[0] else UI_TEXT
                lines.append((w, col))
        draw_center_box(con, "Briefing", lines, width=SCREEN_W - 10, footer="Enter: begin   ?: how to play")

    def on_key(self, key):
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE, E.KeySym.ESCAPE):
            self.app.replace(PlayState(self.app, self.game))
        elif key.char == "?":
            self.app.push(HelpState(self.app))

    def on_click(self, tx, ty, b):
        self.app.replace(PlayState(self.app, self.game))


class GameOverState:
    def __init__(self, app, game):
        self.app = app
        self.game = game
        from .game import Game
        Game.delete_save()

    def render(self, con):
        con.clear()
        g = self.game
        p = g.player
        lines = []
        for w in textwrap.wrap(g.death_text or "The war goes on without you.", 84):
            lines.append((w, (230, 200, 160)))
        lines.append(("", None))
        lines.append((f"{g.theatre['name']}: {g.theatre['battle']}", UI_DIM))
        mins = g.clock // 60
        lines.append((f"You lasted {mins // 60}h {mins % 60:02d}m.", UI_TEXT))
        lines.append((f"Enemy killed by your hand: {g.stats['kills']}.   Vehicles destroyed: {g.stats['vehicles_killed']}.", UI_TEXT))
        lines.append((f"Times wounded: {g.stats['wounds']}.   Shots fired: {p.stats['shots']}, hits: {p.stats['hits']}.", UI_TEXT))
        lines.append((f"Sectors fought over: {len(g.sector_log)}.   Objectives taken with your squad: {g.stats['objectives']}.", UI_TEXT))
        if g.stats["desertions"]:
            lines.append(("You left your post under fire.", (220, 120, 80)))
        lines.append(("", None))
        if p.inv or True:
            keep = [i.name for i in p.inv if i.t.tool in ("letter", "photo", "rosary", "dogtags", "coin", "bible", "harmonica")]
            if keep:
                lines.append(("On the body: " + ", ".join(keep) + ".", UI_DIM))
        lines.append(("", None))
        lines.append(("Your name has been added to the memorial.", UI_DIM))
        draw_center_box(con, "In memoriam" if "Killed" in (g.death_text or "") else "The end", lines, width=92,
                        footer="Enter: return to the main menu")

    def on_key(self, key):
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.ESCAPE, E.KeySym.SPACE):
            self.app.reset_to_menu()

    def on_click(self, tx, ty, b):
        self.app.reset_to_menu()


class TextState:
    def __init__(self, app, title, lines):
        self.app = app
        self.title = title
        self.lines = lines
        self.scroll = 0

    def render(self, con):
        con.clear()
        out = []
        for l in self.lines:
            if isinstance(l, tuple):
                out.append(l)
            else:
                for w in textwrap.wrap(l, SCREEN_W - 12) or [""]:
                    out.append((w, UI_TEXT))
        vis = out[self.scroll:self.scroll + SCREEN_H - 6]
        draw_center_box(con, self.title, vis, width=SCREEN_W - 6, footer="Esc to close, ↑↓ scroll", top=1)

    def on_key(self, key):
        if key.sym in (E.KeySym.ESCAPE, E.KeySym.RETURN, E.KeySym.KP_ENTER) or key.char in ("q", "?"):
            self.app.pop()
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2, E.KeySym.PAGEDOWN):
            self.scroll += 1 if key.sym != E.KeySym.PAGEDOWN else 20
        elif key.sym in (E.KeySym.UP, E.KeySym.KP_8, E.KeySym.PAGEUP):
            self.scroll = max(0, self.scroll - (1 if key.sym != E.KeySym.PAGEUP else 20))

    def on_wheel(self, dy):
        self.scroll = max(0, self.scroll - dy)

    def on_click(self, tx, ty, b):
        self.app.pop()


class OrdersState:
    """The orders book: every order you hold, written up as you'd keep it in a field notebook - who gave it, how
    it reached you, when, by when, what's in it for you and what happens if you don't.  Enter makes one the order
    you get on with (and Enter on the map then does it)."""
    PAPER = (58, 52, 38)
    INK = (225, 210, 170)
    FAINT = (160, 145, 110)
    LEFT = 34

    def __init__(self, app, play):
        from .orders import book
        self.app = app
        self.play = play
        self.orders = book(play.game)
        self.sel = 0

    def render(self, con):
        from .orders import _clock, _left
        con.clear()
        g = self.play.game
        W, H = SCREEN_W, SCREEN_H
        con.draw_rect(1, 1, W - 2, H - 2, ord(" "), bg=self.PAPER)
        con.print(3, 2, f"ORDERS - {g.now().strftime('%H:%M, %d %B %Y')}", fg=self.INK, bg=self.PAPER)
        con.print(3, 3, "(the ones you hold; Enter: get on with this one; Esc: close)", fg=self.FAINT, bg=self.PAPER)
        if not self.orders:
            con.print(3, 6, "Nothing. For once, nobody wants anything of you.", fg=self.INK, bg=self.PAPER)
            return
        y = 5
        for k, o in enumerate(self.orders):
            who = o["who"].split(",")[0]
            due = _left(g, o["due"]) if o["due"] is not None else ""
            mark = "!" if o["urgent"] else "-"
            fg = (250, 200, 120) if o["urgent"] else self.INK
            bg = (95, 82, 55) if k == self.sel else self.PAPER
            con.print(3, y, f"{mark} {who}"[:self.LEFT - 4], fg=fg, bg=bg)
            if due:
                con.print(self.LEFT - len(due) - 1, y, due, fg=self.FAINT, bg=bg)
            y += 2
            if y > H - 4:
                break
        o = self.orders[self.sel % len(self.orders)]
        x = self.LEFT + 2
        wdt = W - x - 4
        y = 5
        con.draw_rect(self.LEFT, 5, 1, H - 8, ord("│"), fg=self.FAINT, bg=self.PAPER)

        def put(label, text, col=None):
            nonlocal y
            if not text:
                return
            con.print(x, y, label, fg=self.FAINT, bg=self.PAPER)
            for line in textwrap.wrap(str(text), wdt - 12) or [""]:
                con.print(x + 12, y, line, fg=col or self.INK, bg=self.PAPER)
                y += 1
            y += 1
        put("From", o["who"])
        put("How", o["how"])
        put("Given", _clock(g, o["issued"]) if o.get("issued") is not None and o["issued"] <= g.turn else "")
        if o["due"] is not None:
            put("By", f"{_clock(g, o['due'])} ({_left(g, o['due'])})", (250, 200, 120) if o["due"] - g.turn < 120
                else None)
        put("Order", o["text"], (240, 230, 190))
        put("If done", o["reward"], (180, 220, 150))
        put("If not", o["penalty"], (240, 160, 130))
        foc = g.__dict__.get("order_focus")
        if foc == o["key"]:
            con.print(x, y, "This is the order you're getting on with.", fg=(180, 220, 150), bg=self.PAPER)

    def on_key(self, key):
        from .orders import focus
        if key.sym == E.KeySym.ESCAPE or key.char in ("T", "q"):
            self.app.pop()
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2) or key.char == "j":
            self.sel = (self.sel + 1) % max(1, len(self.orders))
        elif key.sym in (E.KeySym.UP, E.KeySym.KP_8) or key.char == "k":
            self.sel = (self.sel - 1) % max(1, len(self.orders))
        elif key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER) and self.orders:
            o = self.orders[self.sel % len(self.orders)]
            focus(self.play.game, o["key"])
            self.play.game.msg(f"You'll see to it: {o['text']}", "info")
            self.play.game.update_orders(force=True)
            self.app.pop()

    def on_click(self, tx, ty, b):
        if ty >= 5 and tx < self.LEFT:
            k = (ty - 5) // 2
            if 0 <= k < len(self.orders):
                self.sel = k
                return
        self.app.pop()


class HelpState:
    """How to play: the sections down the left, the keys (bold, on keycaps) and what they do on the right.
    Opened from play it starts at "Right now" - the keys for where you are this moment.  / searches everything."""
    LEFT = 24                    # the section list
    KEYW = 21                    # the keycap column

    def __init__(self, app, section=None, play=None):
        from .helpdata import SECTIONS
        self.app = app
        self.play = play
        now = None
        if play is not None:
            try:
                now = play.help_now()
            except Exception:
                now = None
        self.sections = ([("Right now", now)] if now else []) + list(SECTIONS)
        self.sel = 0
        if section:
            want = section.lower()
            alias = {"aboard": "aboard ship", "chart": "chart & cockpit", "looking": "looking around",
                     "kit": "your kit", "information": "looking around", "the chart": "chart & cockpit"}
            want = alias.get(want, want)
            for i, (t, _r) in enumerate(self.sections):
                if t.lower().startswith(want):
                    self.sel = i
                    break
        self.scroll = 0
        self.query = ""
        self.typing = False
        self._lines = []
        self._list_rows = {}

    # ---------------------------------------------------------------- what's on the right
    def _rows(self):
        from .helpdata import search
        if self.query.strip():
            now = self.sections[0][1] if self.sections and self.sections[0][0] == "Right now" else None
            return search(self.query, now) or [("t", f"Nothing mentions '{self.query}'.")]
        return self.sections[self.sel][1]

    @staticmethod
    def _merged(rows):
        from .helpdata import merged
        return merged(rows)

    def _inline(self, x, text, fg):
        """A line with {key} marks in it: the keys in bold, the rest plain."""
        import re
        from .fonts import bold
        segs = []
        pos = 0
        cx = x
        for mt in re.finditer(r"\{([^}]*)\}", text):
            if mt.start() > pos:
                seg = text[pos:mt.start()]
                segs.append((cx, seg, fg, None))
                cx += len(seg)
            k = mt.group(1)
            segs.append((cx, bold(k), (255, 232, 150), None))
            cx += len(k)
            pos = mt.end()
        if pos < len(text):
            segs.append((cx, text[pos:], fg, None))
        return segs

    @staticmethod
    def _wrap(text, width):
        """Word-wrap, keeping a {key} mark (even {move keys}) whole and counting it as the key alone."""
        import re
        words = re.findall(r"\{[^}]*\}\S*|\S+", text)
        lines, cur, n = [], [], 0
        for w_ in words:
            wl = len(w_.replace("{", "").replace("}", ""))
            if cur and n + 1 + wl > width:
                lines.append(" ".join(cur))
                cur, n = [], 0
            cur.append(w_)
            n += wl + (1 if len(cur) > 1 else 0)
        if cur:
            lines.append(" ".join(cur))
        return lines or [""]

    def _layout(self, width):
        """The rows as screen lines: each a list of (x, text, fg, bg)."""
        from .fonts import bold
        out = []
        kw = self.KEYW
        dw = max(20, width - kw - 1)
        cap_fg, cap_bg = (255, 232, 150), (58, 60, 74)
        prev = None
        for r in self._merged(self._rows()):
            kind = r[0]
            if kind == "h":
                if out:
                    out.append([])
                out.append([(0, bold(r[1].upper()), UI_HI, None)])
                prev = kind
                continue
            if prev is not None and (kind == "t") != (prev == "t") and prev != "h" and out and out[-1]:
                out.append([])                        # a breath between a list of keys and a paragraph
            prev = kind
            if kind == "t":
                for ln in self._wrap(r[1], width):
                    out.append(self._inline(0, ln, (190, 185, 165)))
                continue
            if kind == "l":
                desc = self._wrap(r[2], dw)
                for i, d in enumerate(desc):
                    segs = [(0, bold(r[1]), (205, 200, 170), None)] if i == 0 else []
                    out.append(segs + self._inline(kw + 1, d, UI_TEXT))
                continue
            keys = [k for k in r[1].split("|") if k] if r[1] else []
            desc = self._wrap(r[2], dw)
            # keycaps, wrapping inside their column
            cap_lines = [[]]
            x = 0
            for k in keys:
                w = len(k) + 2
                if x and x + w > kw:
                    cap_lines.append([])
                    x = 0
                cap_lines[-1].append((x, bold(f" {k} "), cap_fg, cap_bg))
                x += w + 1
            n = max(len(cap_lines), len(desc))
            for i in range(n):
                segs = list(cap_lines[i]) if i < len(cap_lines) else []
                if i < len(desc):
                    segs += self._inline(kw + 1, desc[i], UI_TEXT)
                out.append(segs)
        return out

    # ---------------------------------------------------------------- drawing
    def render(self, con):
        from .fonts import bold
        con.clear()
        x0, y0 = 1, 0
        w, h = SCREEN_W - 2, SCREEN_H
        con.draw_frame(x0, y0, w, h, clear=True, fg=UI_FRAME, bg=UI_BG)
        con.print(x0 + 2, y0, f" {bold('HOW TO PLAY')} ", fg=UI_HI, bg=UI_BG)
        # the search box
        sb = f" / search: {self.query}{'_' if self.typing else ''} " if (self.typing or self.query) else \
            " / to search every key "
        con.print(x0 + w - len(sb) - 2, y0, sb, fg=(255, 232, 150) if self.typing or self.query else UI_DIM,
                  bg=(40, 42, 52) if self.typing else UI_BG)
        # sections
        lx, ly = x0 + 2, y0 + 2
        self._list_rows = {}
        for i, (t, _r) in enumerate(self.sections):
            y = ly + i
            if y >= y0 + h - 4:
                break
            on = i == self.sel and not self.query.strip()
            label = f"{'►' if on else ' '} {t}"
            con.print(lx, y, label.ljust(self.LEFT - 2), fg=(255, 240, 190) if on else
                      ((170, 210, 160) if t == "Right now" else UI_TEXT), bg=(52, 50, 38) if on else UI_BG)
            self._list_rows[y] = i
        foot = ["↑↓  section", "PgUp PgDn  scroll", "/  search", "Esc  close"]
        for j, f_ in enumerate(foot):
            con.print(lx, y0 + h - 2 - len(foot) + j, f_, fg=UI_DIM, bg=UI_BG)
        for y in range(y0 + 1, y0 + h - 1):
            con.print(x0 + self.LEFT + 1, y, "│", fg=UI_FRAME, bg=UI_BG)
        # the section
        rx = x0 + self.LEFT + 3
        rw = w - self.LEFT - 6
        title = f"Search: {self.query}" if self.query.strip() else self.sections[self.sel][0]
        con.print(rx, y0 + 2, bold(title.upper()), fg=UI_HI, bg=UI_BG)
        lines = self._layout(rw)
        self._lines = lines
        top = y0 + 4
        rows = h - 6
        self.scroll = max(0, min(self.scroll, max(0, len(lines) - rows)))
        for i, segs in enumerate(lines[self.scroll:self.scroll + rows]):
            for dx, text, fg, bg in segs:
                con.print(rx + dx, top + i, text, fg=fg, bg=bg if bg is not None else UI_BG)
        if self.scroll > 0:
            con.print(rx + rw - 8, y0 + 3, "▲ more", fg=UI_DIM, bg=UI_BG)
        if self.scroll + rows < len(lines):
            con.print(rx + rw - 8, y0 + h - 2, "▼ more", fg=UI_DIM, bg=UI_BG)

    # ---------------------------------------------------------------- keys and the mouse
    def _page(self):
        return max(1, SCREEN_H - 8)

    def on_key(self, key):
        n = len(self.sections)
        if self.typing:
            if key.sym == E.KeySym.ESCAPE:
                self.typing = False
                self.query = ""
            elif key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER):
                self.typing = False
            elif key.sym == E.KeySym.BACKSPACE:
                self.query = self.query[:-1]
            elif key.sym == E.KeySym.SPACE:
                self.query += " "
            elif key.char and key.char.isprintable():
                self.query += key.char
            self.scroll = 0
            return
        c = key.char
        if key.sym == E.KeySym.ESCAPE or c in ("q", "?") or key.sym == E.KeySym.F1:
            if self.query and key.sym == E.KeySym.ESCAPE:
                self.query = ""
                return
            self.app.pop()
            return
        if c == "/":
            self.typing = True
            self.query = ""
            return
        if key.sym in (E.KeySym.UP, E.KeySym.KP_8):
            self.sel = (self.sel - 1) % n
            self.scroll = 0
            self.query = ""
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
            self.sel = (self.sel + 1) % n
            self.scroll = 0
            self.query = ""
        elif key.sym == E.KeySym.TAB:
            self.sel = (self.sel + (-1 if getattr(key, "shift", False) else 1)) % n
            self.scroll = 0
            self.query = ""
        elif key.sym in (E.KeySym.PAGEDOWN, E.KeySym.KP_3):
            self.scroll += self._page()
        elif key.sym in (E.KeySym.PAGEUP, E.KeySym.KP_9):
            self.scroll = max(0, self.scroll - self._page())
        elif key.sym == E.KeySym.HOME:
            self.sel, self.scroll = 0, 0
        elif key.sym == E.KeySym.END:
            self.sel, self.scroll = n - 1, 0
        elif c and c.isalpha():
            # a letter: the next section beginning with it
            for k in range(1, n + 1):
                j = (self.sel + k) % n
                if self.sections[j][0].lower().startswith(c.lower()):
                    self.sel, self.scroll, self.query = j, 0, ""
                    break

    def on_wheel(self, dy, *a, **kw):
        self.scroll = max(0, self.scroll - dy * 3)

    def on_click(self, tx, ty, b):
        if tx < 1 + self.LEFT and ty in self._list_rows:
            self.sel = self._list_rows[ty]
            self.scroll = 0
            self.query = ""
        elif b == 3:
            self.app.pop()


class MemorialState(TextState):
    def __init__(self, app):
        from .game import SAVE_DIR
        path = os.path.join(SAVE_DIR, "memorial.txt")
        lines = []
        try:
            with open(path, encoding="utf-8") as f:
                lines = [l.rstrip("\n") for l in f.readlines()][-200:]
        except OSError:
            lines = ["No names yet."]
        super().__init__(app, "Memorial", lines or ["No names yet."])


class LogState(TextState):
    def __init__(self, app, game):
        from .constants import MSG_COLORS
        lines = []
        for m in list(game.messages):
            t = m.text + (f" (x{m.count})" if m.count > 1 else "")
            for w in textwrap.wrap(t, SCREEN_W - 12):
                lines.append((w, MSG_COLORS.get(m.cat, UI_TEXT)))
        super().__init__(app, "What happened", lines)
        self.scroll = max(0, len(lines) - (SCREEN_H - 6))


def chain_text(game, a):
    """A soldier's chain of command, squad to head of state, as you know it."""
    from .hierarchy import Hierarchy
    h = game.__dict__.get("hierarchy")
    if h is None:
        h = game.hierarchy = Hierarchy()
    out = []
    for post, who in h.chain_lines(game, a):
        col = (240, 220, 140) if who == "you" else UI_DIM if who in ("commander unknown", "no leader",
                                                                     "no commander") else UI_TEXT
        out.append((f"  {post:<52} {who}", col))
    return out


class ChainState(TextState):
    def __init__(self, app, game, a):
        mine = a.side == game.player.side
        lines = [(f"{a.rank_full} {a.name}", UI_HI), (a.unit or "", UI_DIM), ("", None)]
        lines += chain_text(game, a)
        if not mine:
            lines += [("", None), ("What intelligence knows of their commanders. Bring in papers and prisoners.",
                                   UI_DIM)]
        super().__init__(app, "Chain of command", lines)


class StatusState:
    """Yourself, in detail: the body part by part, blood, pain, heat and cold, breath, load and nerves -
    and (Tab) your service record."""

    DOLL = ["    .-.    ", "   ( H )   ", "    '-'    ", "  .-TTT-.  ", " L| TTT |R ", " L| TTT |R ",
            "  '-TTT-'  ", "   l| |r   ", "   l| |r   ", "   l| |r   "]

    def __init__(self, app, game):
        self.app = app
        self.game = game
        self.page = 0
        self.record = CharState(app, game)

    @property
    def PAGES(self):
        from .agents import cover
        return ("health", "skills", "record") + (("cover",) if cover(self.game) else ())

    def render(self, con):
        name = self.PAGES[self.page % len(self.PAGES)]
        if name == "record":
            self.record.render(con)
            con.print(2, SCREEN_H - 2, "Tab: next page   Shift+Tab: back   Esc: close", fg=UI_DIM)
            return
        if name == "skills":
            return self._render_skills(con)
        if name == "cover":
            return self._render_cover(con)
        con.clear()
        g = self.game
        p = g.player
        b = p.body
        nums = self.app.show_numbers
        from .body import BLOOD_MAX, PART_NAME, PARTS
        con.print(2, 1, f"{p.rank_full} {p.name}", fg=UI_HI)
        con.print(2, 2, "HEALTH   (Tab: skills, then service record)", fg=UI_DIM)
        # the body, part by part
        y = 4
        con.print(2, y, "The body", fg=UI_HI)
        y += 1
        partcol = {}
        for part in PARTS:
            word, col = b.part_status(part)
            partcol[part] = col
            r = max(0.0, b.hp[part] / b.max[part])
            bar = "█" * int(round(r * 12)) + "·" * (12 - int(round(r * 12)))
            bleed = b.part_bleeding(part)
            con.print(4, y, f"{PART_NAME[part]:<10}", fg=UI_TEXT)
            con.print(15, y, bar, fg=col)
            con.print(28, y, word + (f" ({b.hp[part]}/{b.max[part]})" if nums else ""), fg=col)
            if bleed:
                con.print(50, y, bleed, fg=(255, 80, 80) if "bleed" in bleed or "gush" in bleed else (200, 190, 150))
            y += 1
        # the doll, coloured
        keymap = {"H": "head", "T": "torso", "L": "l_arm", "R": "r_arm", "l": "l_leg", "r": "r_leg"}
        for i, row in enumerate(self.DOLL):
            for j, ch in enumerate(row):
                if ch in keymap:
                    con.print(66 + j, 4 + i, "█", fg=partcol[keymap[ch]])
                elif ch != " ":
                    con.print(66 + j, 4 + i, ch, fg=(120, 120, 110))
        y += 1
        wounds = [w for w in b.wounds]
        con.print(2, y, f"Wounds ({len(wounds)})" if wounds else "No open wounds.", fg=UI_HI if wounds else UI_DIM)
        y += 1
        for w in wounds[:7]:
            state = "tourniquet on" if w.tourniquet else "dressed" if w.bandaged else \
                ("bleeding hard" if w.bleed >= 3 else "bleeding" if w.bleed > 0.2 else "oozing")
            con.print(4, y, f"{w.kind} wound, {PART_NAME.get(w.part, w.part)}: {state}"
                      + (f" ({w.bleed:.1f} ml/s)" if nums and not (w.bandaged or w.tourniquet) else ""),
                      fg=(240, 120, 100) if state.startswith("bleed") else UI_TEXT)
            y += 1
        from .medical import needs_surgery
        try:
            if needs_surgery(p):
                con.print(4, y, "You need a surgeon.", fg=(240, 150, 90))
                y += 1
        except Exception:
            pass
        y += 1
        # blood, pain, drugs
        frac = b.blood / BLOOD_MAX
        bw = "full" if frac > 0.92 else "lost some blood" if frac > 0.8 else "lost a lot of blood" if frac > 0.66 else \
            "bled nearly white" if frac > 0.55 else "dying of blood loss"
        con.print(2, y, "Blood: " + bw + (f" ({int(b.blood)} ml)" if nums else ""),
                  fg=(150, 210, 150) if frac > 0.9 else (240, 170, 90) if frac > 0.7 else (255, 80, 70))
        y += 1
        pain = b.effective_pain()
        pw = "none" if pain < 5 else "aching" if pain < 20 else "hurting" if pain < 50 else "terrible" if pain < 100 \
            else "blinding"
        con.print(2, y, f"Pain: {pw}" + (f" ({int(pain)})" if nums else "")
                  + ("   morphine in you" if b.morphine > 0.5 else "") + ("   drunk" if b.alcohol > 1.5 else
                                                                         "   a drink in you" if b.alcohol > 0.4 else ""),
                  fg=(150, 210, 150) if pain < 20 else (240, 170, 90) if pain < 90 else (255, 80, 70))
        y += 1
        extras = []
        if b.deaf > 0:
            extras.append("deafened - ears ringing")
        if b.stunned > 0:
            extras.append("stunned")
        if b.unconscious > 0:
            extras.append("drifting in and out")
        if extras:
            con.print(2, y, ", ".join(extras), fg=(230, 180, 100))
            y += 1
        # right column: heat, breath, load, nerves
        x = 84
        yy = 4
        con.print(x, yy, "Heat and cold", fg=UI_HI)
        yy += 1
        from . import thermal
        tw, tc = thermal.words(p)
        con.print(x + 2, yy, tw + (f" ({getattr(b, 'temp', 37.0):.1f}°C core)" if nums else ""), fg=tc)
        yy += 1
        air = thermal.ambient(g)
        feel = thermal.feels_like(g, p)
        aw = "bitter" if air < -15 else "freezing" if air < 0 else "cold" if air < 8 else "cool" if air < 15 else \
            "mild" if air < 24 else "warm" if air < 30 else "hot" if air < 37 else "scorching"
        con.print(x + 2, yy, f"The air: {aw}" + (f" ({int(air)}°C, feels {int(feel)}°C where you are)" if nums else ""),
                  fg=UI_TEXT)
        yy += 1
        wet = getattr(b, "wet", 0.0)
        con.print(x + 2, yy, "Soaked through" if wet > 70 else "Wet" if wet > 30 else "Damp" if wet > 5 else "Dry",
                  fg=(150, 190, 240) if wet > 30 else UI_TEXT)
        yy += 1
        ins = thermal.insulation(p)
        con.print(x + 2, yy, "Clothes: " + ("thin" if ins < 1.2 else "a uniform" if ins < 1.8 else "warm" if ins < 3
                                            else "very warm") + (f" ({ins:.1f})" if nums else ""), fg=UI_TEXT)
        yy += 1
        if getattr(b, "frost", 0) > 20:
            con.print(x + 2, yy, "Frostbite: " + ("numb fingers and toes" if b.frost < 60 else "black toes"),
                      fg=(170, 190, 255))
            yy += 1
        yy += 1
        con.print(x, yy, "Breath and legs", fg=UI_HI)
        yy += 1
        st = getattr(p, "stamina", 100.0)
        bw2 = p.breath_word() or "Breathing easily"
        con.print(x + 2, yy, bw2 + (f" ({int(st)})" if nums else ""), fg=UI_TEXT if st > 40 else (240, 170, 90))
        yy += 1
        spd = p.speed(g.turn)
        con.print(x + 2, yy, f"Speed {spd}", fg=UI_TEXT)
        yy += 1
        for label, v in (("wounds", b.speed_mult()), ("load", p.encumbrance(g.turn)),
                         ("breath", 0.6 + 0.4 * min(1.0, st / 30.0)), ("cold/heat", thermal.speed_mult(p))):
            if v < 0.99:
                con.print(x + 4, yy, f"- {label}: x{v:.2f}", fg=UI_DIM)
                yy += 1
        yy += 1
        con.print(x, yy, "Load", fg=UI_HI)
        yy += 1
        wkg = p.carried_weight()
        con.print(x + 2, yy, f"{wkg:.1f} kg carried" + ("  - too much" if wkg > 26 else ""),
                  fg=(240, 170, 90) if wkg > 26 else UI_TEXT)
        yy += 2
        con.print(x, yy, "Nerves", fg=UI_HI)
        yy += 1
        mw = "steady" if p.morale > 70 else "holding" if p.morale > 45 else "shaken" if p.morale > 25 else "at breaking point"
        con.print(x + 2, yy, f"Morale: {mw}" + (f" ({int(p.morale)})" if nums else ""), fg=UI_TEXT)
        yy += 1
        sw = "none" if p.suppression < 10 else "under fire" if p.suppression < 40 else "heavy fire" if p.suppression < 70 \
            else "pinned"
        con.print(x + 2, yy, f"Suppression: {sw}", fg=UI_TEXT)
        yy += 1
        from .spawn import TRAITS
        if p.traits:
            yy += 1
            con.print(x, yy, "Traits: " + ", ".join(TRAITS.get(t, t) for t in sorted(p.traits))[:SCREEN_W - x - 10],
                      fg=UI_DIM)
        feel_lines = b.feel()
        yy = max(y, yy) + 2
        for t, col in feel_lines[:3]:
            con.print(2, yy, t, fg=col)
            yy += 1
        con.print(2, SCREEN_H - 2, "Tab: skills   Esc: close" +
                  ("" if nums else "   (numbers can be turned on in Options)"), fg=UI_DIM)

    def _render_skills(self, con):
        """What you can do: each skill in words (and a bar), what your training guaranteed, your traits."""
        from .fonts import bold
        from .skills import ROLE_SKILLS, SKILLS, UNIT_SKILLS, level, word
        from .spawn import TRAITS
        con.clear()
        g = self.game
        p = g.player
        nums = self.app.show_numbers
        con.print(2, 1, f"{p.rank_full} {p.name}", fg=UI_HI)
        con.print(2, 2, "SKILLS   (Tab: service record   Shift+Tab: health)", fg=UI_DIM)
        drilled = set(ROLE_SKILLS.get(p.role, {})) | set(UNIT_SKILLS.get(p.__dict__.get("unit_type") or "", {}))
        y = 4
        for k, (name, desc) in SKILLS.items():
            v = level(p, k)
            n = int(round(v))
            col = (140, 140, 130) if v < 2.5 else UI_TEXT if v < 5.5 else (190, 220, 150) if v < 7.5 else (255, 225, 130)
            con.print(4, y, bold(name), fg=col)
            con.print(28, y, "█" * n + "·" * (10 - n), fg=col)
            con.print(40, y, word(v) + (f" ({v:.1f})" if nums else ""), fg=col)
            if k in drilled:
                con.print(58, y, "drilled in training", fg=(170, 200, 150))
            con.print(6, y + 1, desc, fg=UI_DIM)
            y += 3
        traits = [TRAITS.get(t, t) for t in sorted(p.traits)]
        con.print(2, y, "Traits: " + (", ".join(traits) if traits else "none to speak of"), fg=UI_TEXT)
        con.print(2, y + 1, "Skills come on slowly with use: shooting at real targets, creeping past the enemy, "
                            "closing wounds, laying the guns...", fg=UI_DIM)
        con.print(2, SCREEN_H - 2, "Tab: service record   Shift+Tab: health   Esc: close", fg=UI_DIM)

    def _render_cover(self, con):
        """An agent's page: the career, the circuit, the legend and its papers, the mission."""
        from .agents import cover_lines
        import textwrap
        con.clear()
        p = self.game.player
        con.print(2, 1, f"{p.rank_full} {p.name}", fg=UI_HI)
        con.print(2, 2, "COVER   (Tab: health   Shift+Tab: service record)", fg=UI_DIM)
        y = 4
        for i, line in enumerate(cover_lines(self.game)):
            for w in textwrap.wrap(line, SCREEN_W - 8):
                con.print(4, y, w, fg=UI_TEXT if i else UI_HI)
                y += 1
            y += 1
        con.print(2, SCREEN_H - 2, "Tab: health   Shift+Tab: service record   Esc: close", fg=UI_DIM)

    def on_key(self, key):
        if key.sym == E.KeySym.TAB or key.sym in (E.KeySym.LEFT, E.KeySym.RIGHT):
            back = getattr(key, "shift", False) or key.sym == E.KeySym.LEFT
            self.page = (self.page + (-1 if back else 1)) % len(self.PAGES)
        elif self.PAGES[self.page % len(self.PAGES)] == "record" and key.sym not in (E.KeySym.ESCAPE,) and \
                key.char not in ("@", "q"):
            self.record.on_key(key)
        else:
            self.app.pop()

    def on_wheel(self, dy):
        if self.PAGES[self.page % len(self.PAGES)] == "record" and hasattr(self.record, "on_wheel"):
            self.record.on_wheel(dy)


class CharState(TextState):
    def __init__(self, app, game):
        from .spawn import TRAITS
        p = game.player
        n = NATIONS[p.nation]
        cmd = game.command
        lines = [(f"{p.rank_full} {p.name}", UI_HI),
                 (f"{n['adj']} {n['army']}", UI_TEXT),
                 (p.unit, UI_DIM),
                 (f"{p.role_name}", UI_TEXT),
                 ("", None)]
        if cmd.billet is not None or cmd.billet_squad is not None:
            lines.append((f"Command: {cmd.billet_title(game)}", (220, 200, 140)))
            lines.append((f"  {len(cmd.chain_squads(game))} units answer to you on this field.", UI_DIM))
        if cmd.medals:
            lines.append(("Decorations: " + ", ".join(cmd.medals), (240, 210, 110)))
        for entry in (cmd.__dict__.get("record") or [])[-8:]:
            lines.append(("  " + entry, (220, 190, 150) if "report" in entry or "penal" in entry else (190, 210, 160)))
        if cmd.promotions:
            from .data.ranks import rank_title
            lines.append(("Promotions: " + "; ".join(f"{rank_title(p.nation, gr, False)} ({when})"
                                                     for when, gr in cmd.promotions), UI_TEXT))
        need = cmd.promotion_need(p.rank)
        earned = cmd.merit - cmd.merit_at_promotion
        feel = "Nobody has noticed you yet." if earned < need * 0.3 else \
            "Your name has come up at headquarters." if earned < need * 0.8 else "There's talk of a promotion."
        lines += [(feel, UI_DIM)]
        duty = getattr(game, "duty", None)
        if duty is not None:
            from .duty import standing_word
            lines.append((standing_word(duty.rep), (200, 190, 150)))
            bits = []
            gd = duty.good
            if gd.get("patched"):
                bits.append(f"patched up {gd['patched']} comrades")
            if gd.get("rescue"):
                bits.append(f"carried {gd['rescue']} out")
            if gd.get("prisoner"):
                bits.append(f"took {gd['prisoner']} prisoners ({gd.get('delivered', 0)} brought in)")
            if duty.done:
                bits.append(f"{duty.done} orders carried out")
            if duty.failed:
                bits.append(f"{duty.failed} ignored")
            if bits:
                lines.append(("You have " + ", ".join(bits) + ".", UI_DIM))
            if duty.murders or duty.pow_shot:
                lines.append((f"Blood on your hands: {duty.murders} of your own, {duty.pow_shot} prisoners.",
                              (220, 90, 80)))
        lines.append(("", None))
        lines.append(("Your chain of command (as far as you know):", UI_HI))
        lines += chain_text(game, p)
        lines.append(("", None))
        lines += [("Traits: " + (", ".join(TRAITS[t] for t in sorted(p.traits)) or "none to speak of"), UI_TEXT),
                  ("", None),
                  (f"Kills: {p.kills}   Shots fired: {p.stats['shots']}   Hits: {p.stats['hits']}", UI_TEXT),
                  (f"Grenades thrown: {p.stats['grenades']}   Wounds dressed: {p.stats['bandaged']}", UI_TEXT),
                  (f"Distance covered: {int(p.stats['distance'] * 2.2)} yards", UI_TEXT),
                  (f"Time in action: {game.clock // 60} minutes", UI_TEXT),
                  ("", None),
                  ("Where you've been:", UI_HI)]
        lines += [(f"  {l}", UI_DIM) for l in game.sector_log[-10:]]
        super().__init__(app, "Yourself", lines)


def _bar(v, n=10):
    k = int(round(max(0.0, min(1.0, v)) * n))
    return "█" * k + "░" * (n - k) + f" {int(round(v * 100)):3d}%"


def _voice_engine_desc() -> str:
    from . import neural_voice as NV
    base = ("natural: Piper, a neural voice that runs on your own machine - it fetches one voice per language "
            "(60-80 MB each, into ~/.fogofwar/piper) the first time a battle needs it, and the system voice speaks "
            "until it's here, and for Japanese and Chinese.  system: macOS say or espeak - instant, robotic.")
    if not NV.available():
        base += "  (Piper isn't installed: pip install -r requirements-voices.txt - until then it's the system voice.)"
    return base


class OptionsState:
    """Every setting in one place, grouped, each with a word on what it does.  ←/→ change a value,
    Enter toggles or cycles it, Esc goes back."""

    def __init__(self, app, play=None):
        self.app = app
        self.play = play
        self.sel = 1
        self.rows = {}
        self.items = []
        self._build()

    # (label, key, kind, description, extra)
    def _spec(self):
        app = self.app
        st = app.settings
        sizes = ("standard", "large", "huge")
        return [
            ("SOUND", None, "head", "", None),
            ("Sound", "sound", "toggle", "All sound on or off (F3).", None),
            ("Master volume", "volume", "slider", "Everything together.", None),
            ("Weapons and explosions", "vol_weapons", "slider",
             "Rifles, machine guns, shells, grenades, ricochets - near and far.", None),
            ("Battle ambience, wind and rain", "vol_ambience", "slider",
             "The distant war (louder with a battle next door), the wind and the rain. Turn it down if it drowns "
             "out the fighting you're actually in.", None),
            ("Voices", "vol_voices", "slider", "Shouts, orders and the radio, in each army's language.", None),
            ("Spoken voices", "voices", "toggle", "Voices at all: off saves the time it takes to render them.", None),
            ("Voice engine", "voice_engine", "cycle", _voice_engine_desc(), ("neural", "system")),
            ("Footsteps, engines and the rest", "vol_effects", "slider",
             "Footsteps, engines and tracks, doors, digging, the ringing in your ears after a blast.", None),
            ("Interface", "vol_ui", "slider", "The rustle of your kit and the clicks of the menus.", None),
            ("Sounds written in the log", "sound_log", "cycle",
             "all: every sound you hear is written down.  near: only what's close.  off: none (you still hear "
             "them, and the guesses still appear on the map).", ("all", "near", "off")),
            ("DISPLAY", None, "head", "", None),
            ("Graphics", "sprites", "toggle", "Sprites or ASCII (F2).", None),
            ("Font", "font", "cycle", "DejaVu Sans Mono or the classic bitmap font (F4).", ("ttf", "bitmap")),
            ("Animations", "anim_speed", "cycle", "How long shots and blasts stay on screen: slow ones play "
             "second by second in the order they happened.", ("fast", "normal", "slow", "very slow")),
            ("Screen shake", "shake", "toggle", "The view jolts when shells land close.", None),
            ("Centre on me when I move", "auto_center", "toggle", "The view glides back to you when you move.", None),
            ("Scroll at the screen edge", "edge_scroll", "toggle", "The mouse at the edge of the battlefield "
             "scrolls it.", None),
            ("Minimap open at the start", "minimap", "toggle", "F5 shows or hides it in play.", None),
            ("Hit chances as numbers", "show_numbers", "toggle", "Percentages instead of words when aiming.", None),
            ("PLAY", None, "head", "", None),
            ("Key hints", "hints", "toggle", "A line under your orders with the keys for what's beside you: a "
             "vehicle, a door, a wounded man, someone to talk to, your seat in a tank. F1 or ? for all the keys.",
             None),
            ("Safe mode", "safe_mode", "toggle", "With the enemy in sight or rounds coming in, a step stops with a "
             "warning; step again to go anyway. (! in play; ' ignores what you can see.)", None),
            ("Battlefield size (new games)", "battlefield", "cycle",
             "standard: 180 x 120 tiles.  large: 270 x 180, about twice the men on each side (the default).  "
             "huge: 360 x 240, three times the men - slow on most machines. Takes effect when you start a new "
             "game.", sizes),
            ("Autosave", "autosave", "toggle", "Save every five minutes of real time, as well as when you quit. "
             "There's still only one life - unless succession is on.", None),
            ("WHEN YOU DIE", None, "head", "", None),
            ("Succession", "succession", "cycle", "off: death is the end.  on: the battle goes on and you're someone "
             "else, chosen by the rule below - the same field, the same men, the dead where they fell.  choose: a "
             "list of who could carry on, and you pick.", ("off", "on", "choose")),
            ("Who carries on", "succession_rule", "cycle", "squad: a man of your squad (then your unit, then anyone "
             "near).  unit: your company or battery.  nearest: whoever's nearest.  role: the nearest man in your job. "
             " rank: the most senior man near.  random: anyone on the field.  killer: the man who killed you.",
             ("squad", "unit", "nearest", "role", "rank", "random", "killer")),
            ("Which side", "succession_side", "cycle", "own: always your own side (the killer rule still crosses "
             "over).  any: nearest and random may be a man of either side.", ("own", "any")),
            ("Lives", "succession_lives", "cycle", "How many deaths before it really is the end (0: none - the war "
             "goes on as long as anyone's alive).", (0, 3, 5, 10, 25)),
            ("Back", "__back__", "action", "", None),
        ]

    def _value(self, key, kind):
        app = self.app
        st = app.settings
        from .settings import DEFAULTS
        if key == "show_numbers":
            return bool(app.show_numbers)
        return st.get(key, DEFAULTS.get(key))

    def _build(self):
        self.items = self._spec()

    def _label(self, it):
        lab, key, kind, desc, extra = it
        if kind == "head":
            return lab
        v = self._value(key, kind)
        if kind == "toggle":
            if key == "sprites":
                return f"{lab}: {'sprites' if v else 'ASCII'}"
            return f"{lab}: {'on' if v else 'off'}"
        if kind == "slider":
            return f"{lab:34} {_bar(float(v if v is not None else 1.0))}"
        if kind == "slider2":
            lo, hi = extra
            f = (float(v or 1.0) - lo) / (hi - lo)
            return f"{lab:34} {'█' * int(round(f * 10)) + '░' * (10 - int(round(f * 10)))} {float(v or 1.0):.1f}x"
        if kind == "cycle":
            shown = {"ttf": "DejaVu Sans Mono", "bitmap": "classic bitmap", "neural": "natural (Piper)",
                     "system": "system (instant, robotic)"}.get(v, v)
            return f"{lab}: {shown}"
        return lab

    def render(self, con):
        if self.play is not None:
            self.play.render(con)
            con = self.play.top_console(con)
        w = 74
        h = min(SCREEN_H - 2, len(self.items) + 8)
        x = (VIEW_W - w) // 2 if self.play is not None and VIEW_W > w else (SCREEN_W - w) // 2
        y = max(0, (SCREEN_H - h) // 2)
        con.draw_frame(x, y, w, h, clear=True, fg=UI_FRAME, bg=UI_BG)
        con.print(x + 2, y, " Options ", fg=UI_HI, bg=UI_BG)
        self.rows = {}
        yy = y + 1
        for i, it in enumerate(self.items):
            if yy >= y + h - 5:
                break
            lab = self._label(it)
            if it[2] == "head":
                con.print(x + 2, yy, lab, fg=(200, 180, 120), bg=UI_BG)
            else:
                sel = i == self.sel
                con.print(x + 2, yy, " " * (w - 4), bg=UI_SEL_BG if sel else UI_BG)
                con.print(x + 4, yy, lab[: w - 6], fg=UI_HI if sel else UI_TEXT, bg=UI_SEL_BG if sel else UI_BG)
                self.rows[yy] = i
            yy += 1
        desc = self.items[self.sel][3]
        for j, line in enumerate(textwrap.wrap(desc, w - 6)[:3]):
            con.print(x + 3, y + h - 5 + j, line, fg=UI_DIM, bg=UI_BG)
        con.print(x + 3, y + h - 2, "↑↓ choose   ←→ change   Enter toggle   Esc back"[: w - 6], fg=UI_DIM, bg=UI_BG)
        if self.play is not None and getattr(self.play, "overlay", None) is not None:
            self.play._finish_overlay()

    @property
    def layers(self):
        return self.play.layers if self.play is not None else None

    @property
    def overlay(self):
        return self.play.overlay if self.play is not None else None

    def _move(self, d):
        n = len(self.items)
        for _ in range(n):
            self.sel = (self.sel + d) % n
            if self.items[self.sel][2] != "head":
                return

    def on_key(self, key):
        if key.sym == E.KeySym.ESCAPE:
            self.app.pop()
        elif key.sym in (E.KeySym.UP, E.KeySym.KP_8):
            self._move(-1)
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
            self._move(1)
        elif key.sym in (E.KeySym.LEFT, E.KeySym.KP_4):
            self.change(-1)
        elif key.sym in (E.KeySym.RIGHT, E.KeySym.KP_6):
            self.change(1)
        elif key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
            self.change(1, enter=True)

    def on_mouse_motion(self, tx, ty):
        if ty in self.rows:
            self.sel = self.rows[ty]

    def on_click(self, tx, ty, b):
        if ty in self.rows:
            self.sel = self.rows[ty]
            self.change(-1 if b == 3 else 1, enter=True)

    def change(self, d, enter=False):
        app = self.app
        st = app.settings
        lab, key, kind, desc, extra = self.items[self.sel]
        if kind == "action":
            if key == "__back__":
                app.pop()
            return
        if kind == "toggle":
            if key == "sound":
                app.toggle_sound()
            elif key == "sprites":
                app.toggle_sprites()
            elif key == "show_numbers":
                app.show_numbers = not app.show_numbers
            else:
                from .settings import DEFAULTS
                st[key] = not st.get(key, DEFAULTS.get(key))
                if key == "minimap" and self.play is not None:
                    self.play.minimap = st[key]
        elif kind == "slider":
            v = float(st.get(key, 0.8))
            st[key] = round(max(0.0, min(1.0, v + 0.1 * d)), 2)
            if key == "volume" and app.audio is not None:
                app.audio.apply_volume()
            if app.audio is not None and key == "vol_ui":
                try:
                    app.audio.ui("rustle")          # hear what you've set
                except Exception:
                    pass
        elif kind == "slider2":
            lo, hi = extra
            v = float(st.get(key, 1.0))
            st[key] = round(max(lo, min(hi, v + 0.1 * d)), 1)
            if app.gfx is not None:
                app.gfx.check_resize(force=True)
        elif kind == "cycle":
            opts = list(extra)
            cur = st.get(key, opts[0])
            i = opts.index(cur) if cur in opts else 0
            st[key] = opts[(i + (d if not enter else 1)) % len(opts)]
            if key == "font" and app.gfx is not None:
                app.gfx.check_resize(force=True)
        try:
            st.save()
        except Exception:
            pass


class EscMenuState:
    def __init__(self, app, play):
        self.app = app
        self.play = play
        self.sel = 0
        self.opts = []
        self._build()

    def _build(self):
        app = self.app
        st = app.settings
        self.opts = [("Resume", "resume"), ("Save and quit to menu", "save"), ("How to play", "help"),
                     ("Options: sound mixer, display, safe mode...", "options"),
                     ("Graphics: " + ("sprites" if st.get("sprites") else "ASCII") + "   (F2)", "sprites"),
                     ("Sound: " + ("on" if st.get("sound") else "off") + "   (F3)", "sound"),
                     ("Take your own life" if not getattr(self, "_confirm_end", False) else
                      "Take your own life - are you sure? (choose again)", "abandon")]
        self.rows = {}

    @property
    def layers(self):
        return self.play.layers

    @property
    def overlay(self):
        return self.play.overlay

    def render(self, con):
        self.play.render(con)
        top = self.play.top_console(con)
        self._draw_box(top)
        if top is not con:
            self.play._finish_overlay()

    def _draw_box(self, con):
        w = 50
        h = len(self.opts) * 2 + 3
        x = (SCREEN_W - w) // 2
        y = (SCREEN_H - h) // 2
        con.draw_frame(x, y, w, h, clear=True, fg=UI_FRAME, bg=UI_BG)
        con.print(x + 2, y, " Menu ", fg=UI_HI, bg=UI_BG)
        self.rows = {}
        for i, (label, v) in enumerate(self.opts):
            yy = y + 2 + i * 2
            sel = i == self.sel
            con.print(x + 2, yy, " " * (w - 4), bg=UI_SEL_BG if sel else UI_BG)
            con.print(x + 3, yy, label, fg=UI_HI if sel else UI_TEXT, bg=UI_SEL_BG if sel else UI_BG)
            self.rows[yy] = i

    def on_key(self, key):
        if key.sym == E.KeySym.ESCAPE:
            self.app.pop()
        elif key.sym in (E.KeySym.UP, E.KeySym.KP_8):
            self.sel = (self.sel - 1) % len(self.opts)
        elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
            self.sel = (self.sel + 1) % len(self.opts)
        elif key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
            self.choose(self.opts[self.sel][1])

    def on_mouse_motion(self, tx, ty):
        if ty in self.rows:
            self.sel = self.rows[ty]

    def on_click(self, tx, ty, b):
        if ty in self.rows:
            self.sel = self.rows[ty]
            self.choose(self.opts[self.sel][1])

    def choose(self, v):
        app = self.app
        if v == "resume":
            app.pop()
        elif v == "save":
            try:
                self.play.game.save()
            except Exception as e:
                app.pop()
                self.play.game.msg(f"Save failed: {e}", "warn")
                return
            app.reset_to_menu()
        elif v == "help":
            app.push(HelpState(app))
        elif v == "options":
            app.push(OptionsState(app, self.play))
        elif v == "numbers":
            app.show_numbers = not app.show_numbers
            self._build()
        elif v == "sprites":
            app.toggle_sprites()
            self._build()
        elif v == "voices":
            app.settings["voices"] = not app.settings.get("voices", True)
            app.settings.save()
            self._build()
        elif v in ("center", "edge", "shake", "safe"):
            k = {"center": "auto_center", "edge": "edge_scroll", "shake": "shake", "safe": "safe_mode"}[v]
            app.settings[k] = not app.settings.get(k, v != "edge")
            app.settings.save()
            self._build()
        elif v == "anim":
            from .settings import ANIM_SPEEDS
            cur = app.settings.get("anim_speed", "fast")
            app.settings["anim_speed"] = ANIM_SPEEDS[(ANIM_SPEEDS.index(cur) + 1) % len(ANIM_SPEEDS)] \
                if cur in ANIM_SPEEDS else "normal"
            app.settings.save()
            self._build()
        elif v == "sound":
            app.toggle_sound()
            self._build()
        elif v == "font":
            app.toggle_font()
            self._build()
        elif v == "abandon":
            if not getattr(self, "_confirm_end", False):
                self._confirm_end = True
                self._build()
                return
            from .game import Game
            g = self.play.game
            p = g.player
            p.body.dead = True
            p.body.cause = "his own hand"
            g.game_over = True
            g.death_text = (f"{p.rank_full} {p.name}, {p.unit}. Took {p.his} own life near {g.sector.name}, "
                            f"{g.datetime_str(exact=True)}.")
            g.msg("It's over.", "death")
            g.write_memorial()
            Game.delete_save()
            app.pop()
            self.play.check_over()


class POWState:
    """Days in the camp, while the war goes on."""

    def __init__(self, app, game, play):
        self.app = app
        self.game = game
        self.play = play
        self.log = [("You arrive at the " + game.pow["camp"] + (f" near {game.pow['sector_name']}"
                                                              if game.pow.get("sector_name") else "") + ".", UI_HI)]
        self.done = None

    def render(self, con):
        con.clear()
        g = self.game
        pw = g.pow
        if pw is None:
            return
        con.print(3, 1, f"PRISONER OF WAR - {pw['camp'].upper()}", fg=UI_HI)
        p = g.player
        con.print(3, 3, f"{p.rank_full} {p.name}   Day {pw['day']} of captivity   {g.datetime_str()}", fg=UI_TEXT)
        food = pw["food"]
        fw = "well fed" if food > 70 else "hungry" if food > 40 else "starving" if food > 15 else "wasting away"
        health = "sick" if pw["sick"] > 0 else "weak" if pw["weak"] > 6 else "holding up"
        con.print(3, 4, f"You are {fw} and {health}.", fg=(220, 190, 140) if food < 40 or pw["sick"] else UI_TEXT)
        rows = []
        for text, col in self.log[-(SCREEN_H - 12):]:
            for line in textwrap.wrap(text, SCREEN_W - 8):
                rows.append((line, col))
        for i, (line, col) in enumerate(rows[-(SCREEN_H - 11):]):
            con.print(4, 6 + i, line, fg=col or UI_DIM)
        foot = "Enter: another day   w: a week   e: try to escape   Esc: menu"
        if self.done:
            foot = "Enter to continue."
        con.print(3, SCREEN_H - 2, foot, fg=UI_DIM)

    def _days(self, n):
        from .pow import camp_day
        g = self.game
        for _ in range(n):
            ev = camp_day(g)
            for e in ev:
                if e.startswith("__dead__"):
                    cause = e.split(":", 1)[1]
                    p = g.player
                    g.game_over = True
                    g.death_text = (f"{p.rank_full} {p.name}, {p.unit}. Died of {cause} in the {g.pow['camp']}, "
                                    f"{g.datetime_str(exact=True)}, after {g.pow['day']} days in captivity.")
                    g.write_memorial()
                    self.log.append((f"Day {g.pow['day']}: you die of {cause}.", (230, 90, 80)))
                    self.done = "dead"
                    return
                if e == "__liberated__":
                    self.log.append(("Tanks at the wire - ours. The guards are gone. You're free.", (160, 230, 150)))
                    self.done = "liberated"
                    return
                self.log.append((f"Day {g.pow['day']}: {e}", None))

    def on_key(self, key):
        g = self.game
        if self.done:
            if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
                return self._finish()
            return
        if key.sym == E.KeySym.ESCAPE:
            self.app.push(EscMenuState(self.app, self.play))
            return
        if key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER, E.KeySym.SPACE):
            self._days(1)
        elif key.char == "w":
            self._days(7)
        elif key.char == "e":
            from .pow import try_escape
            r = try_escape(g)
            if r == "escaped":
                self.log.append(("Under the wire at night, three days in a ditch, then friendly voices.", (160, 230, 150)))
                self.done = "escaped"
            elif r == "shot":
                p = g.player
                g.game_over = True
                g.death_text = (f"{p.rank_full} {p.name}, {p.unit}. Shot while escaping from the {g.pow['camp']}, "
                                f"{g.datetime_str(exact=True)}.")
                g.write_memorial()
                self.log.append(("A searchlight. A shout. The machine gun in the tower.", (230, 90, 80)))
                self.done = "dead"
            else:
                self.log.append(("Caught at the wire. Two weeks in the cooler on bread and water.", (230, 170, 90)))
                self._days(3)

    def _finish(self):
        from .pow import return_to_war
        g = self.game
        if self.done == "dead":
            self.app.pop()
            self.play.check_over()
            return
        if return_to_war(g, self.done):
            g.msg("You're back with your own side - thin, filthy, and alive. The quartermaster will find you a rifle.",
                  "good")
        self.app.pop()

    def on_click(self, tx, ty, b):
        self.on_key(Key(sym=E.KeySym.RETURN))


class OvermapState:
    CW, CH = 9, 5

    def __init__(self, app, game):
        self.app = app
        self.game = game
        s = game.sector
        self.cx, self.cy = s.x, s.y
        mp = game.player.has_tool("map")
        self.has_map = mp is not None
        # a map sheet covers so much ground; a staff map (and a general's staff) a great deal more
        self.map_range = 0 if mp is None else 14 if (getattr(mp, "tid", "") == "staff_map" or game.player.rank >= 11) else 7
        self.vx0 = self.vy0 = None
        self.compact = False        # z: the wide view - a glyph a sector
        self.radio = game.player_near_radio(game.player.side)
        self.reach = game.command.strategic_reach(game)
        self.mode = None            # None / "attack" / "move": choosing where to
        self.src = None
        self.note = ""

    def _orders(self):
        return self.game.command.strategic_orders

    def render(self, con):
        con.clear()
        g = self.game
        st = g.strategic
        p = g.player
        ox, oy = 2, 3
        title = f"{g.theatre['name']} - {g.theatre['battle']}"
        if self.reach:
            title = "WAR MAP - " + title
        con.print(2, 1, title, fg=UI_HI)
        if not self.has_map:
            con.print(2, 2, "You have no map. You know only the ground you've walked.", fg=(220, 160, 100))
        here = g.sector
        vw, vh = self._view_size()
        self._scroll(vw, vh)
        if self.compact:
            self._render_compact(con, ox, oy, vw, vh)
        cells = []
        if self.compact:
            vw = vh = 0                 # the detailed cells are skipped
        for vx in range(self.vx0, self.vx0 + vw):
            for vy in range(self.vy0, self.vy0 + vh):
                s = st.at(vx, vy, create=self._knows(vx, vy))
                if s is None:
                    x = ox + (vx - self.vx0) * self.CW
                    y = oy + (vy - self.vy0) * self.CH
                    con.draw_rect(x, y, self.CW - 1, self.CH - 1, ord(" "), bg=(16, 16, 16))
                    con.print(x + self.CW // 2 - 1, y + 1, "?", fg=(55, 55, 55), bg=(16, 16, 16))
                    if (vx, vy) == (self.cx, self.cy):
                        con.draw_frame(x - 1, y - 1, self.CW + 1, self.CH + 1, clear=False, fg=UI_HI)
                    continue
                cells.append(s)
        for s in cells:
            x = ox + (s.x - self.vx0) * self.CW
            y = oy + (s.y - self.vy0) * self.CH
            known = s.visited or self._knows(s.x, s.y)
            if s.biome == "sea":
                bg = (15, 30, 70)
            elif not known:
                bg = (20, 20, 20)
            elif s.control == ALLIES:
                bg = (30, 45, 80)
            elif s.control == AXIS:
                bg = (80, 30, 25)
            else:
                bg = (50, 50, 50)
            in_reach = self.reach and s.control == p.side and s.biome != "sea" and \
                abs(s.x - here.x) + abs(s.y - here.y) <= self.reach
            if in_reach:
                bg = tuple(min(255, c + 22) for c in bg)
            con.draw_rect(x, y, self.CW - 1, self.CH - 1, ord(" "), bg=bg)
            from .strategic import BIOME_GLYPH, power
            if known or s.biome == "sea":
                gl = BIOME_GLYPH.get(s.biome, "?")
                for i in range(self.CW - 1):
                    if (i + s.y) % 3 == 0:
                        con.print(x + i, y + self.CH - 2, gl, fg=(110, 110, 100), bg=bg)
                nm = s.name[: self.CW - 2]
                con.print(x + 1, y, nm, fg=(220, 210, 180), bg=bg)
                if self.has_map and s.biome != "sea":
                    # grease-pencil estimates of strength
                    pa, pb = power(s.units[p.side]), power(s.units[other_side(p.side)])
                    own = "▮" * min(4, int(pa / 5 + 0.99)) if pa else ""
                    con.print(x + 1, y + 1, own, fg=SIDE_COLOR[p.side], bg=bg)
                    if self.radio or s.visited or abs(s.x - g.sector.x) + abs(s.y - g.sector.y) <= 1 or self.reach:
                        import random as _r
                        pb *= _r.Random(hash((s.x, s.y, st.ticks, other_side(p.side)))).uniform(0.6, 1.5)
                        enemy = "▮" * min(4, int(pb / 5 + 0.99)) if pb >= 0.5 else ""
                        con.print(x + self.CW - 1 - len(enemy) - 1, y + 1, enemy, fg=SIDE_COLOR[other_side(p.side)], bg=bg)
                    inst = [k for k, side, ok in s.installations if ok and side == p.side]
                    if inst:
                        sym = "".join({"depot": "D", "artillery": "A", "aa": "F", "hq": "H", "aid": "+",
                                       "motor_pool": "M", "airfield": "W", "fortress": "#",
                                       "naval_base": "N"}.get(k, "?")
                                      for k in inst)
                        con.print(x + 1, y + 2, sym[: self.CW - 2], fg=(200, 220, 160), bg=bg)
                    if s.fort:
                        con.print(x + self.CW - 3, y + 2, "##"[: s.fort], fg=(230, 150, 120) if s.control != p.side
                                  else (150, 190, 240), bg=bg)
            else:
                con.print(x + self.CW // 2 - 1, y + 1, "?", fg=(70, 70, 70), bg=bg)
            if s is g.sector:
                con.print(x + self.CW // 2 - 1, y + 2, "@", fg=(255, 255, 160), bg=bg)
            # within your command
            if in_reach:
                con.print(x, y + self.CH - 2, "·", fg=(240, 220, 130), bg=bg)
                con.print(x + self.CW - 2, y + self.CH - 2, "·", fg=(240, 220, 130), bg=bg)
            if (s.x, s.y) == (self.cx, self.cy):
                con.draw_frame(x - 1, y - 1, self.CW + 1, self.CH + 1, clear=False,
                               fg=(250, 150, 110) if self.mode == "attack" else (140, 190, 250) if self.mode == "move"
                               else UI_HI)
        # standing orders in grease pencil
        for o in self._orders():
            sx, sy = o["src"]
            if not (self.vx0 <= sx < self.vx0 + vw and self.vy0 <= sy < self.vy0 + vh):
                continue
            x = ox + (sx - self.vx0) * self.CW
            y = oy + (sy - self.vy0) * self.CH
            if o["kind"] in ("attack", "move") and o.get("dst"):
                dx, dy = o["dst"][0] - sx, o["dst"][1] - sy
                col = (255, 120, 90) if o["kind"] == "attack" else (140, 190, 255)
                gl = {(1, 0): "►", (-1, 0): "◄", (0, 1): "▼", (0, -1): "▲"}.get((dx, dy), "*")
                bx = x + (self.CW - 1) // 2 + dx * (self.CW // 2)
                by = y + (self.CH - 1) // 2 + dy * (self.CH // 2 + 0)
                con.print(bx, by, gl, fg=col)
            elif o["kind"] == "hold":
                con.print(x + self.CW - 3, y + self.CH - 2, "DUG", fg=(150, 190, 240))
            elif o["kind"] == "arty":
                con.print(x + 1, y + self.CH - 2, "ART!", fg=(250, 210, 110))
            elif o["kind"] == "air":
                con.print(x + 1, y + self.CH - 3, "AIR!", fg=(200, 220, 255))
        # info pane
        s = st.at(self.cx, self.cy, create=self._knows(self.cx, self.cy))
        vw, vh = self._view_size()
        ix = ox + vw * self._cw() + 2
        iw = SCREEN_W - ix - 2
        from .strategic import BIOME_NAME, UNIT_NAME
        from .world import COUNTRY
        lines = []
        known = s is not None and (s.visited or self._knows(s.x, s.y))
        dx, dy = self.cx - here.x, self.cy - here.y
        km = 3 * math.hypot(dx, dy)
        where = "where you are" if (dx, dy) == (0, 0) else \
            f"{km:.0f} km {COMPASS.get((int(math.copysign(1, dx)) if abs(dx) * 2 >= abs(dy) and dx else 0, int(math.copysign(1, dy)) if abs(dy) * 2 >= abs(dx) and dy else 0), '')} of you"
        if known:
            lines.append((s.name, UI_HI))
            lines.append((BIOME_NAME.get(s.biome, s.biome).capitalize()
                          + (f", {COUNTRY[s.lang]}" if getattr(s, "lang", None) in COUNTRY and s.biome != "sea" else ""),
                          UI_TEXT))
            lines.append((where, UI_DIM))
            if s.biome != "sea":
                ctl = "Allied" if s.control == ALLIES else "Axis" if s.control == AXIS else "no-man's land"
                lines.append((f"Held by: {ctl}", SIDE_COLOR.get(s.control, UI_TEXT)))
                if self.has_map:
                    u = s.units[p.side]
                    parts = [f"{n} {UNIT_NAME.get(k, k)}" for k, n in u.items() if n > 0]
                    lines.append(("Our forces:" + ("" if parts else " none"), SIDE_COLOR[p.side]))
                    for part in parts[:6]:
                        lines.append((f"  {part}", UI_DIM))
                    if self.radio or s.visited or self.reach:
                        lines += self._enemy_estimate(s)
                    else:
                        lines.append(("Enemy strength: unknown", UI_DIM))
                    inst = [(k, side) for k, side, ok in s.installations if ok and (side == p.side or s.visited)]
                    if inst:
                        lines.append(("Installations:", UI_TEXT))
                        for k, side in inst:
                            lines.append((f"  {'our' if side == p.side else 'enemy'} {k.replace('_', ' ')}", UI_DIM))
                    if s.fort:
                        lines.append((f"Fortified ({s.fort}/3)", (230, 150, 120)))
        else:
            lines.append(("Unknown ground", UI_DIM))
            lines.append((where, UI_DIM))
            if not self.has_map:
                lines.append(("Without a map you know only the ground you've walked.", UI_DIM))
            else:
                lines.append(("Off the edge of your map sheet.", UI_DIM))
        if self.reach and s is not None:
            lines.append(("", None))
            mine = [o for o in self._orders() if tuple(o["src"]) == (s.x, s.y)]
            for o in mine:
                what = {"attack": "attack", "move": "move up to", "hold": "dig in", "arty": "artillery priority",
                        "air": "air priority"}[o["kind"]]
                dst = st.at(*o["dst"]).name if o.get("dst") else ""
                lines.append((f"Orders: {what} {dst}".strip(), (240, 210, 120)))
            ok, why = self.game.command.can_order_sector(self.game, s)
            if self.mode:
                lines.append(("Pick the " + ("enemy sector to attack" if self.mode == "attack" else
                                             "sector to move to") + ", Enter to confirm, Esc to cancel.",
                              (250, 200, 140)))
            elif ok:
                for t in ("o  general staff: divisions and the reserve", "a  attack a neighbour", "r  move reserves",
                          "d  dig in and hold",
                          "p  artillery priority", "f  air priority" if p.rank >= 15 else "",
                          "x  cancel orders here"):
                    if t:
                        lines.append((t, (200, 190, 150)))
            elif s.control == p.side:
                lines.append((why, UI_DIM))
            if self.note:
                lines.append((self.note, (250, 220, 150)))
        yy = 3
        for t, col in lines:
            for w in textwrap.wrap(t, iw) or [""]:
                if yy >= SCREEN_H - 9:
                    break
                con.print(ix, yy, w, fg=col or UI_TEXT)
                yy += 1
        leg = ["@ you   ▮ strength", "D depot  A artillery", "F flak  H HQ  + aid", "M motor pool  W airfield",
               "# fortress  N naval base" + ("   bright: in your reach" if self.reach else "")]
        for i, l in enumerate(leg):
            con.print(ix, SCREEN_H - 8 + i, l, fg=UI_DIM)
        foot = ("Arrows (shift: faster) to look around, z " + ("detail" if self.compact else "wide view")
                + ", Home back to you, Esc to close. The world goes on as far as you walk.")
        if self.reach:
            foot = ("Orders go out with the next situation report (about every ten minutes). "
                    "Arrows to inspect, Esc to close.")
        con.print(2, SCREEN_H - 2, foot, fg=UI_DIM)
        if self.has_map or self.radio:
            ov = st.overview()
            con.print(2, SCREEN_H - 3, f"The front: Allies hold {ov['allies']} sectors, the Axis {ov['axis']}.",
                      fg=UI_TEXT)

    def _enemy_estimate(self, s):
        """What intelligence says about the enemy here: never the true, current count."""
        import random as _r
        from .strategic import UNIT_NAME, power
        g = self.game
        st = g.strategic
        enemy = other_side(g.player.side)
        u = s.units[enemy]
        col = SIDE_COLOR[enemy]
        rng = _r.Random(hash((s.x, s.y, st.ticks, enemy)))
        near = abs(s.x - g.sector.x) + abs(s.y - g.sector.y) <= 1
        if near:
            # patrols and observers next door: rounded, and often wrong
            out = [("Enemy forces (estimated):", col)]
            for k, n in u.items():
                if n <= 0:
                    continue
                est = max(1, int(round(n * rng.uniform(0.6, 1.5))))
                word = f"~{est}" if est > 2 else ("a few" if est > 1 else "some")
                out.append((f"  {word} {UNIT_NAME.get(k, k)}", UI_DIM))
            if len(out) == 1:
                out.append(("  nothing seen", UI_DIM))
            return out[:7]
        pw = power(u) * rng.uniform(0.6, 1.5)
        word = "none reported" if pw < 0.5 else "weak" if pw < 6 else "moderate" if pw < 15 else \
            "strong" if pw < 30 else "very strong"
        out = [(f"Enemy strength: {word} (intelligence estimate)", col)]
        if (u.get("tank", 0) + u.get("td", 0)) and rng.random() < 0.8:
            out.append(("  armour reported", UI_DIM))
        return out

    def _confirm(self):
        g = self.game
        st = g.strategic
        dst = st.at(self.cx, self.cy)
        src = self.src
        cmd = g.command
        mode = self.mode
        self.mode = None
        if src is None or dst is None:
            return
        if abs(dst.x - src.x) + abs(dst.y - src.y) != 1:
            self.note = "Only a neighbouring sector."
        elif mode == "attack":
            if dst.control == g.player_side or not dst.playable:
                self.note = "That's not an enemy sector."
            else:
                cmd.add_strategic_order(g, "attack", (src.x, src.y), (dst.x, dst.y))
                self.note = f"{src.name} will attack {dst.name}."
                g.msg(f"You order the attack from {src.name} on {dst.name}.", "radio")
        elif mode == "move":
            if dst.control != g.player_side or not dst.playable:
                self.note = "Reserves only move through our own ground."
            elif src is g.sector:
                self.note = "The troops here are in the fight: command them on the ground (C)."
            else:
                cmd.add_strategic_order(g, "move", (src.x, src.y), (dst.x, dst.y))
                self.note = f"Half of {src.name}'s forces will move to {dst.name}."
                g.msg(f"You order forces from {src.name} up to {dst.name}.", "radio")
        self.cx, self.cy = src.x, src.y

    def on_key(self, key):
        g = self.game
        st = g.strategic
        c = key.char
        if self.mode and key.sym in (E.KeySym.RETURN, E.KeySym.KP_ENTER):
            return self._confirm()
        if self.mode and key.sym == E.KeySym.ESCAPE:
            self.mode = None
            if self.src is not None:
                self.cx, self.cy = self.src.x, self.src.y
            return
        if self.reach and not self.mode and c in ("a", "r", "d", "p", "f", "x"):
            s = st.at(self.cx, self.cy)
            if s is None:
                self.note = "You know nothing of that ground."
                return
            ok, why = g.command.can_order_sector(g, s)
            if not ok:
                self.note = why
                return
            cmd = g.command
            if c == "a":
                self.mode, self.src = "attack", s
                self.note = ""
            elif c == "r":
                self.mode, self.src = "move", s
                self.note = ""
            elif c == "d":
                cmd.add_strategic_order(g, "hold", (s.x, s.y))
                self.note = f"{s.name} will dig in and hold."
            elif c == "p":
                cmd.strategic_orders = [o for o in cmd.strategic_orders if o["kind"] != "arty"]
                cmd.add_strategic_order(g, "arty", (s.x, s.y))
                self.note = f"The guns will fire for {s.name} first."
            elif c == "f":
                if g.player.rank < 15:
                    self.note = "Air priority is decided above your level."
                    return
                cmd.strategic_orders = [o for o in cmd.strategic_orders if o["kind"] != "air"]
                cmd.add_strategic_order(g, "air", (s.x, s.y))
                self.note = f"The air forces will support {s.name}."
            elif c == "x":
                cmd.strategic_orders = [o for o in cmd.strategic_orders if tuple(o["src"]) != (s.x, s.y)]
                self.note = "Orders cancelled."
            return
        mv = key.move() if key.sym != E.KeySym.HOME else None     # (Home is "back to you" here, not north-west)
        if mv:
            k = 5 if key.is_run() else 1
            self.cx += mv[0] * k
            self.cy += mv[1] * k
        elif key.sym == E.KeySym.HOME or c == "@":
            self.cx, self.cy = g.sector.x, g.sector.y
        elif c == "o" and self.reach:
            from .opsui import OperationsState
            play = next((st for st in reversed(self.app.states) if isinstance(st, PlayState)), None)
            self.app.push(OperationsState(self.app, g, play))
        elif c == "z":
            self.compact = not self.compact
            self.vx0 = self.vy0 = None
        elif key.sym in (E.KeySym.ESCAPE, E.KeySym.RETURN) or c in ("m", "q"):
            self.app.pop()

    def _knows(self, x, y) -> bool:
        """On your map sheet (or ground you've walked)."""
        c = self.game.strategic.cells.get((x, y))
        if c is not None and c.visited:
            return True
        h = self.game.sector
        return self.has_map and max(abs(x - h.x), abs(y - h.y)) <= self.map_range

    def _cw(self):
        return 3 if self.compact else self.CW

    def _ch(self):
        return 2 if self.compact else self.CH

    def _view_size(self):
        return max(5, (SCREEN_W - 40) // self._cw()), max(4, (SCREEN_H - 7) // self._ch())

    def _render_compact(self, con, ox, oy, vw, vh):
        """The wide view: each sector a coloured glyph, the front a seam of red against blue."""
        from .strategic import BIOME_GLYPH
        g = self.game
        st = g.strategic
        for vx in range(self.vx0, self.vx0 + vw):
            for vy in range(self.vy0, self.vy0 + vh):
                x = ox + (vx - self.vx0) * 3
                y = oy + (vy - self.vy0) * 2
                s = st.at(vx, vy, create=self._knows(vx, vy))
                known = s is not None and (s.visited or self._knows(vx, vy))
                if not known:
                    bg, gl, fg = (16, 16, 16), "·", (50, 50, 50)
                elif s.biome == "sea":
                    bg, gl, fg = (15, 30, 70), "≈", (60, 90, 160)
                else:
                    bg = (30, 45, 80) if s.control == ALLIES else (80, 30, 25) if s.control == AXIS else (50, 50, 50)
                    gl, fg = BIOME_GLYPH.get(s.biome, "?"), (150, 150, 130)
                    if s.installations and any(i[2] and i[1] == g.player.side for i in s.installations):
                        fg = (200, 220, 160)
                con.draw_rect(x, y, 2, 1, ord(" "), bg=bg)
                con.print(x, y, gl, fg=fg, bg=bg)
                if s is g.sector:
                    con.print(x + 1, y, "@", fg=(255, 255, 160), bg=bg)
                if (vx, vy) == (self.cx, self.cy):
                    con.print(x - 1, y, "[", fg=UI_HI)
                    con.print(x + 2, y, "]", fg=UI_HI)

    def _scroll(self, vw, vh):
        """Keep the cursor in view (a sector's margin), centring on it the first time."""
        if self.vx0 is None:
            self.vx0, self.vy0 = self.cx - vw // 2, self.cy - vh // 2
        if self.cx < self.vx0 + 1:
            self.vx0 = self.cx - 1
        elif self.cx > self.vx0 + vw - 2:
            self.vx0 = self.cx - vw + 2
        if self.cy < self.vy0 + 1:
            self.vy0 = self.cy - 1
        elif self.cy > self.vy0 + vh - 2:
            self.vy0 = self.cy - vh + 2

    def on_click(self, tx, ty, b):
        vw, vh = self._view_size()
        x = (tx - 2) // self._cw()
        y = (ty - 3) // self._ch()
        if 0 <= x < vw and 0 <= y < vh and tx >= 2 and ty >= 3 and self.vx0 is not None:
            self.cx, self.cy = self.vx0 + x, self.vy0 + y
            if self.mode:
                self._confirm()
        elif not self.mode:
            self.app.pop()


class GeneratingState:
    def __init__(self, app, theatre, nation, role, setup=None):
        self.app = app
        self.args = (theatre, nation, role)
        self.setup = setup
        self.done = False

    def render(self, con):
        con.clear()
        th = THEATRES[self.args[0]]
        msg = f"{th['name']}, {th['date'][0]}. Moving up to the line..."
        con.print((SCREEN_W - len(msg)) // 2, SCREEN_H // 2, msg, fg=UI_TEXT)

    def wants_tick(self):
        return True

    def tick(self):
        if self.done:
            return
        self.done = True
        from .game import Game
        try:
            g = Game(*self.args, setup=self.setup)
        except Exception:
            tb = traceback.format_exc()
            self.app.replace(TextState(self.app, "Something broke", tb.splitlines()))
            return
        self.app.replace(BriefingState(self.app, g))

    def on_key(self, key):
        pass


# ====================================================================== the app

class App:
    def __init__(self, font=None):
        from .settings import Settings
        self.settings = Settings()
        if font:
            self.settings["font"] = "bitmap"
        self.console = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
        self.states = [MainMenuState(self)]
        self.running = True
        self.context = None
        self.gfx = None
        self.audio = None
        self._last_kp_period = 0.0
        # offscreen rendering (tests/screenshots) still needs a tileset
        from . import fonts
        self.tileset = fonts.make_tileset(self.settings["font"], 10, 20) if self.settings["font"] == "ttf" \
            else fonts.bitmap_tileset()

    @property
    def show_numbers(self):
        return self.settings.get("show_numbers", False)

    @show_numbers.setter
    def show_numbers(self, v):
        self.settings["show_numbers"] = bool(v)
        self.settings.save()

    def push(self, st):
        self.states.append(st)

    def pop(self):
        if self.states:
            self.states.pop()
        if not self.states:
            self.running = False

    def replace(self, st):
        if self.states:
            self.states.pop()
        self.states.append(st)

    def reset_to_menu(self):
        self.states = [MainMenuState(self)]

    def quit(self):
        self.running = False

    def start_game(self, theatre, nation, role, setup=None):
        setup = dict(setup or {})
        setup.setdefault("battlefield", self.settings.get("battlefield", "large"))
        self.push(GeneratingState(self, theatre, nation, role, setup))

    def current_game(self):
        for st in reversed(self.states):
            if isinstance(st, PlayState):
                return st.game
        return None

    # ---------------------------------------------------------------- toggles
    def toggle_sprites(self):
        if self.gfx is None:
            return
        on = not self.settings.get("sprites")
        try:
            self.gfx.enable_sprites(on)
        except Exception:
            self.settings["sprites"] = False
            on = False
        g = self.current_game()
        if g is not None:
            g.msg(f"Graphics: {'sprites' if on else 'ASCII'} (F2)", "system")

    def toggle_sound(self):
        on = self.settings.toggle("sound")
        if self.audio is not None:
            self.audio.set_enabled(on)
        g = self.current_game()
        if g is not None:
            g.msg(f"Sound {'on' if on else 'off'} (F3)", "system")

    def toggle_font(self):
        self.settings["font"] = "bitmap" if self.settings["font"] == "ttf" else "ttf"
        self.settings.save()
        if self.gfx is not None:
            self.gfx.check_resize(force=True)

    # ---------------------------------------------------------------- main loop
    def _window_size(self):
        w, h = 1440, 900
        try:
            import tcod.sdl.video as V
            disp = V.get_displays()[0] if hasattr(V, "get_displays") else None
            bounds = getattr(disp, "usable_bounds", None) or getattr(disp, "bounds", None) if disp else None
            if bounds:
                bw, bh = bounds[2], bounds[3]
                w = min(1600, int(bw * 0.92))
                h = min(1000, int(bh * 0.9))
        except Exception:
            pass
        return w, h

    def run(self):
        w, h = self._window_size()
        flags = tcod.context.SDL_WINDOW_RESIZABLE
        hidpi = getattr(tcod.context, "SDL_WINDOW_ALLOW_HIGHDPI", 0)
        with tcod.context.new(width=w, height=h, tileset=self.tileset, title=f"{TITLE} - {SUBTITLE}",
                              vsync=True, sdl_window_flags=flags | hidpi) as ctx:
            self.context = ctx
            try:
                ctx.sdl_window.start_text_input()
            except Exception:
                pass
            from .gfx import Graphics
            self.gfx = Graphics(ctx, self.settings)
            try:
                from .audio import Audio
                self.audio = Audio(self.settings)
            except Exception:
                self.audio = None
            while self.running and self.states:
                st = self.states[-1]
                try:
                    st.render(self.console)
                    layers = getattr(st, "layers", None)
                    overlay = getattr(st, "overlay", None)
                except Exception:
                    tb = traceback.format_exc()
                    self.console.clear()
                    for i, line in enumerate(tb.splitlines()[-40:]):
                        self.console.print(0, i, line[:SCREEN_W], fg=(255, 120, 120))
                    layers = overlay = None
                    self._log_error(tb)
                self.gfx.present(self.console, layers, overlay, getattr(st, "map_offset", None))
                if self.audio is not None:
                    g = self.current_game()
                    try:
                        self.audio.update(g)
                    except Exception:
                        self._log_error(traceback.format_exc())
                ticking = hasattr(st, "wants_tick") and st.wants_tick()
                pending_audio = self.audio is not None and self.audio.busy()
                timeout = 0.015 if ticking else (0.03 if pending_audio else 0.25)
                for event in E.wait(timeout):
                    self.dispatch(event)
                    if not self.running:
                        break
                if self.states and hasattr(self.states[-1], "tick") and self.states[-1].wants_tick():
                    try:
                        self.states[-1].tick()
                    except Exception:
                        tb = traceback.format_exc()
                        self._log_error(tb)
                        g = self.current_game()
                        if g is not None:
                            g.msg("An error occurred (see ~/.fogofwar/error.log). The war goes on.", "system")
                        top = self.states[-1]
                        if hasattr(top, "stop_auto"):
                            top.stop_auto()
                        if os.environ.get("FOW_DEBUG"):
                            raise
            if self.audio is not None:
                self.audio.close()
        g = self.current_game()
        if g is not None and not g.game_over:
            try:
                g.save()
            except Exception:
                pass

    def _log_error(self, tb):
        try:
            from .game import SAVE_DIR
            os.makedirs(SAVE_DIR, exist_ok=True)
            with open(os.path.join(SAVE_DIR, "error.log"), "a") as f:
                f.write(tb + "\n")
        except OSError:
            pass

    def _cell(self, event):
        x, y = event.position
        if self.gfx is not None:
            return self.gfx.pixel_to_cell(x, y)
        return float(x), float(y)

    def dispatch(self, event):
        if not self.states:
            return
        st = self.states[-1]
        if isinstance(event, E.Quit):
            g = self.current_game()
            if g is not None and not g.game_over:
                try:
                    g.save()
                except Exception:
                    pass
            self.running = False
            return
        try:
            if isinstance(event, E.KeyDown):
                if event.sym == E.KeySym.F2:
                    return self.toggle_sprites()
                if event.sym == E.KeySym.F3:
                    return self.toggle_sound()
                if event.sym == E.KeySym.F4:
                    return self.toggle_font()
                if event.sym == E.KeySym.KP_PERIOD:
                    self._last_kp_period = time.time()
                if event.sym in SPECIAL_KEYS:
                    shift = bool(event.mod & E.Modifier.SHIFT)
                    k = Key(sym=event.sym, shift=shift)
                    k.ctrl = bool(event.mod & (E.Modifier.CTRL | E.Modifier.GUI | E.Modifier.ALT))
                    st.on_key(k)
            elif isinstance(event, E.TextInput):
                for ch in event.text:
                    if ch.isdigit() or ch == " ":
                        continue
                    if ch == "." and time.time() - self._last_kp_period < 0.2:
                        continue
                    st.on_key(Key(char=ch))
            elif isinstance(event, E.MouseMotion):
                if hasattr(st, "on_mouse_motion"):
                    x, y = self._cell(event)
                    if not isinstance(st, PlayState):
                        x, y = math.floor(x), math.floor(y)
                    st.on_mouse_motion(x, y)
            elif isinstance(event, E.MouseButtonDown):
                if hasattr(st, "on_click"):
                    x, y = self._cell(event)
                    if x >= 0 and y >= 0:
                        if not isinstance(st, PlayState):
                            x, y = math.floor(x), math.floor(y)
                        st.on_click(x, y, int(event.button))
            elif isinstance(event, E.MouseButtonUp):
                if hasattr(st, "on_release"):
                    x, y = self._cell(event)
                    st.on_release(x, y, int(event.button))
            elif isinstance(event, E.MouseWheel):
                if hasattr(st, "on_wheel"):
                    if isinstance(st, PlayState):
                        mods = E.get_modifier_state() if hasattr(E, "get_modifier_state") else 0
                        st.on_wheel(int(event.y), dx=int(event.x), shift=bool(mods & E.Modifier.SHIFT))
                    else:
                        st.on_wheel(int(event.y))
        except Exception:
            tb = traceback.format_exc()
            g = self.current_game()
            if g is not None:
                g.msg("An error occurred (see ~/.fogofwar/error.log). The war goes on.", "system")
            self._log_error(tb)
            if os.environ.get("FOW_DEBUG"):
                raise
