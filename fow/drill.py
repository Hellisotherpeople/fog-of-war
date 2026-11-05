"""The training range: a safe corner of the war, an instructor, and one thing at a time.

A new soldier learns on a range behind the line before the range is real ground.  The drill walks
through movement, looking, getting down, the weapon, fire, a reload, a dressing and the kit, then
turns the learner loose on a few dummies.  The role trial is the same range seen from the job you
picked - a sniper's far shot, a medic's casualty, a gunner's bursts - with the kit and the rank the
creator gave you.

The overlay is the instructor's voice.  Nothing here changes the simulation; the dummies do not
shoot back unless the learner walks into them.
"""
from __future__ import annotations

import math

from .constants import UI_BG, UI_DIM, UI_FRAME, UI_HI, UI_TEXT, VIEW_W


def _dist(drill, p):
    return math.hypot(p.x - drill.marker[0], p.y - drill.marker[1])


BASIC = (
    ("Walk to the white marker. Arrows or the number pad; hold shift to run.",
     lambda d, g, ps: _dist(d, g.player) <= 2),
    ("Look at the marker: press x, or let the mouse rest on it.",
     lambda d, g, ps: ps.mode == "look"),
    ("Get down. z to crouch, Z to go flat.",
     lambda d, g, ps: g.player.stance > 0),
    ("Take your weapon in hand: i for your kit, then e on it.",
     lambda d, g, ps: g.player.weapon is not None and g.player.weapon.t.kind == "gun"),
    ("Aim at a dummy and fire three rounds. f, then click or Enter on it.",
     lambda d, g, ps: g.stats.get("drill_shots", 0) >= 3),
    ("Reload. r.",
     lambda d, g, ps: g.stats.get("drill_reloads", 0) >= 1),
    ("You're hit in the arm. Put a dressing on it: b.",
     lambda d, g, ps: g.stats.get("drill_bandages", 0) >= 1),
    ("Open your kit and look it over: i. Everything you carry has to go somewhere.",
     lambda d, g, ps: ps.inv_screen is not None),
    ("Open your map: m. A map is how a soldier finds out where he is.",
     lambda d, g, ps: g.__dict__.get("drill_map")),
    ("Last: put five more rounds into a dummy, however you like. Then you're done.",
     lambda d, g, ps: g.stats.get("drill_shots", 0) >= 8),
)

ROLE_STEPS = {
    "sniper": ("The far dummy is yours. Three hits at long range - steady your aim first.", "drill_hits", 3),
    "medic": ("The instructor's taken a splinter in the leg. Go to him and dress it (b beside him).",
              "drill_bandages", 1),
    "lmg_gunner": ("A gunner's job is volume. Ten rounds into the dummies, in bursts.", "drill_shots", 10),
    "hmg_gunner": ("A gunner's job is volume. Ten rounds into the dummies, in bursts.", "drill_shots", 10),
    "engineer": ("Put three rounds into a dummy, then get to the marker and hold it.", "drill_hits", 1),
    "at_soldier": ("Put a round into each dummy - tanks are the real work.", "drill_hits", 2),
    "officer": ("Find the dummies with your glasses, then hit three of them.", "drill_hits", 3),
}


class Drill:
    def __init__(self, game, mode, marker, instructor=None):
        self.mode = mode if mode in ("basic", "role") else "basic"
        self.marker = marker
        self.instructor = instructor
        self.step = 0
        self.done = False
        self.said = game.turn - 1
        self.started = game.turn
        self.steps = self._steps(game)
        game.stats.setdefault("drill_shots", 0)
        game.stats.setdefault("drill_reloads", 0)
        game.stats.setdefault("drill_bandages", 0)
        game.stats.setdefault("drill_hits", 0)

    def _steps(self, game):
        steps = list(BASIC)
        if self.mode == "role":
            role = game.player.role
            text, counter, n = ROLE_STEPS.get(role, ("Put three rounds into a dummy.", "drill_hits", 3))
            if counter == "drill_bandages":
                steps.insert(2, (text, lambda d, g, ps: g.stats.get("drill_bandages", 0) >= n))
            else:
                steps.insert(5, (text, lambda d, g, ps, c=counter, n=n: g.stats.get(c, 0) >= n))
        # the last stock step becomes the finish
        steps[-1] = (steps[-1][0], steps[-1][1])
        return steps

    # ------------------------------------------------------------------ running
    def key(self, play, key):
        if self.done:
            return
        k = key.char
        if k in ("x", ";"):
            pass
        if k == "i" or k == "Escape":
            return

    def update(self, play):
        if self.done or self.step >= len(self.steps) or play.popups:
            return
        game = play.game
        if game.player.stance > 0 and self.step in (2, 3):
            pass
        text, check = self.steps[self.step]
        try:
            if not check(self, game, play):
                return
        except (AttributeError, IndexError, TypeError):
            return
        self.step += 1
        if self.step >= len(self.steps):
            self.finish(play)
            return
        game.msg(f"INSTRUCTOR: {self.steps[self.step][0]}", "info")
        self._stage(play, self.step)

    def _stage(self, play, n):
        """Things the range does when a lesson is reached."""
        g = play.game
        text = self.steps[n][0]
        if n == 6 or (text.startswith("You're hit")):
            if not g.player.body.wounds:
                g.player.body.damage(g.rng, "l_arm", 5, "cut")
                g.msg("A splinter opens your forearm. It bleeds.", "hurt")
        if text.startswith("The instructor's taken"):
            if self.instructor is not None and not self.instructor.body.wounds:
                self.instructor.body.damage(g.rng, "l_leg", 5, "cut")

    def skip(self, play):
        """F10: no more lessons, but leave the range as it is."""
        if not self.done:
            self.finish(play)

    def finish(self, play):
        self.done = True
        from .render import Popup
        mins = max(0.2, (play.game.turn - self.started) / 60.0)
        lines = [("You've done the basic drills." if self.mode == "basic" else
                  f"That's the {play.game.player.role_name} trial.", UI_HI),
                 (f"About {mins:.1f} minutes. You hit {play.game.stats.get('drill_hits', 0)} times.", UI_TEXT),
                 ("The dummies won't shoot back. Nothing here does, unless you walk into them.", UI_DIM)]
        opts = [("Back to the menu", "menu", None, True), ("Stay on the range", "keep", None, True)]
        play.open_popup(Popup("Drill complete", opts, play._screen_anchor(), lines=lines, width=58),
                        lambda v: self._leave(play, v))

    def _leave(self, play, v):
        if v == "menu":
            play.app.pop()

    # ------------------------------------------------------------------ drawing
    def draw(self, con, play):
        if self.done and not play.popups:
            top = play.top_console(con)
            top.print(2, 1, " DRILL COMPLETE ", fg=UI_HI, bg=(40, 50, 35))
            return
        if self.step >= len(self.steps) or play.popups:
            return
        top = play.top_console(con)
        text = self.steps[self.step][0]
        title = ("DRILL: BASIC TRAINING" if self.mode == "basic" else "DRILL: YOUR ROLE")
        import textwrap
        lines = textwrap.wrap(text, 56)
        h = len(lines) + 3
        x, y = 2, 1
        top.draw_frame(x, y, 60, h, clear=True, fg=(150, 135, 90), bg=(20, 20, 16))
        top.print(x + 1, y, f" {title}  ({self.step + 1}/{len(self.steps)}) ", fg=(240, 220, 150), bg=(20, 20, 16))
        for i, line in enumerate(lines):
            top.print(x + 2, y + 1 + i, line, fg=UI_TEXT, bg=(20, 20, 16))
        top.print(x + 1, y + h - 1, " x look  i kit  m map  z down  f fire  r reload  b dressing ", fg=UI_DIM,
                  bg=(20, 20, 16))
        # the marker: there, and pointed to from the edge when it isn't
        cam = play.cam
        mx, my = self.marker
        if cam.on_screen(mx, my):
            tx, ty = cam.to_text(mx, my)
            lit = (play.game.turn // 2) % 2
            top.print(tx, ty, "X", fg=(255, 252, 235) if lit else (225, 218, 190),
                      bg=(95, 90, 55) if lit else (60, 56, 42))
        else:
            sx, sy = cam.to_screen(mx, my)
            cx = min(max(sx, 0), cam.vw - 1)
            cy = min(max(sy, 0), cam.vh - 1)
            tx, ty = cam.to_text(cam.x0 + cx, cam.y0 + cy)
            tx = min(max(tx, 1), 58)
            ty = min(max(ty, 1), 20)
            arrow = ("►" if sx >= cam.vw else "◄") if abs(sx - cam.vw / 2) > abs(sy - cam.vh / 2) else \
                ("▼" if sy >= cam.vh else "▲")
            top.print(tx, ty, arrow, fg=(255, 248, 200), bg=(60, 55, 40))
        # the dummies
        for a in play.game.actors:
            if a.ai.get("drill_target") and a.alive and play.cam.on_screen(a.x, a.y):
                tx, ty = play.cam.to_text(a.x, a.y)
                top.print(tx, ty - 1, "▼", fg=(240, 140, 110))
        d = _dist(self, play.game.player)
        if d > 2:
            top.print(x + 59, y, f" {int(d):>2}yd ", fg=UI_DIM, bg=(20, 20, 16))
