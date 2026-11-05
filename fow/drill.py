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


def _cover(drill, g):
    """Cover under the man or in any direction of him - standing on the bags counts."""
    p = g.player
    m = g.map
    best = float(m.pos_cover[p.x, p.y])
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        best = max(best, float(m.cover_toward(p.x, p.y, p.x + dx, p.y + dy)))
    return best


def _crawled(drill, g):
    p = g.player
    if drill.__dict__.get("crawl_from") is None:
        drill.crawl_from = (p.x, p.y)
        return False
    if max(abs(p.x - drill.crawl_from[0]), abs(p.y - drill.crawl_from[1])) >= 2:
        drill.crawl_from = None
        return True
    return False


def _reached_line(drill, g):
    p = g.player
    return any(max(abs(a.x - p.x), abs(a.y - p.y)) <= 4 for a in g.actors if a.ai.get("drill_target"))


def _dummies_down(drill, g):
    return sum(1 for a in g.actors if a.ai.get("drill_target") and
               (not a.alive or sum(a.body.hp.values()) < sum(a.body.max.values())))


BASIC = (
    ("Get down behind the sandbags. z to crouch, Z to go flat.",
     lambda d, g, ps: g.player.stance > 0 and _cover(d, g) >= 30),
    ("Look over them without standing up: q to lean out.",
     lambda d, g, ps: getattr(g.player, "peek", None)),
    ("Walk to the white marker ahead. Arrows or the number pad; hold shift to run.",
     lambda d, g, ps: _dist(d, g.player) <= 2),
    ("Look at the marker: press x, or let the mouse rest on it.",
     lambda d, g, ps: ps.mode == "look"),
    ("Take your weapon in hand: i for your kit, then e on it.",
     lambda d, g, ps: g.player.weapon is not None and g.player.weapon.t.kind == "gun"),
    ("Aim at a dummy and fire three rounds. f, then click or Enter on it.",
     lambda d, g, ps: g.stats.get("drill_shots", 0) >= 3),
    ("Reload. r.",
     lambda d, g, ps: g.stats.get("drill_reloads", 0) >= 1),
    ("Crawl to the next firing point without standing: stay flat, then move a step.",
     lambda d, g, ps: g.player.stance == 2 and _crawled(d, g)),
    ("You're hit in the arm. Put a dressing on it: b.",
     lambda d, g, ps: g.stats.get("drill_bandages", 0) >= 1),
    ("The instructor's hit beside the marker. Go to him, get down, and dress him: b.",
     lambda d, g, ps: g.stats.get("drill_buddy", 0) >= 1),
    ("Pop smoke to cross the open: t, then click the marker.",
     lambda d, g, ps: g.stats.get("drill_smokes", 0) >= 1),
    ("Open your kit and look it over: i. Everything you carry has to go somewhere.",
     lambda d, g, ps: ps.inv_screen is not None),
    ("Open your map: m. A map is how a soldier finds out where he is.",
     lambda d, g, ps: g.__dict__.get("drill_map")),
    ("Last: put a round into each dummy, then walk to their line. Move, use cover, shoot as you go.",
     lambda d, g, ps: _dummies_down(d, g) >= 3 or _reached_line(d, g)),
)

def _casualties(game):
    return [a for a in game.actors if a.ai.get("drill_casualty") and a.alive]


def _dressed(game):
    cs = _casualties(game)
    return bool(cs) and all(bool(a.body.wounds) and all(w.bandaged for w in a.body.wounds) for a in cs)


def _carried(game):
    return game.player.carrying is not None


def _put_down(game, drill):
    if game.player.carrying is not None:
        drill.__dict__["carried"] = True
        from .actions import put_down
        put_down(game, game.player)
    return drill.__dict__.get("carried", False)


def _wire_count(game, drill):
    from . import tiles as T
    m = game.map
    mx, my = drill.marker
    return sum(1 for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)
               if m.in_bounds(mx + dx, my + dy) and T.DEFS[int(m.t[mx + dx, my + dy])].key == "wire")


def _wire_cut(game, drill):
    return _wire_count(game, drill) < drill.__dict__.get("wire0", 99)


def _charged(game, drill):
    return game.player.ai.get("last_charge", -1) >= drill.__dict__.get("charge_at", 0)


def _broken_vehicle(game):
    return next((v for v in game.vehicles if v.ai.get("drill_vehicle") and not v.dead), None)


def _repaired(game, drill):
    from .maintenance import repairs
    v = _broken_vehicle(game)
    return v is None or "track" not in repairs(v)


def _inside(game, drill):
    return game.player.vehicle is not None and game.stats.get("drill_shots", 0) >= 5


def _radioed(game, drill):
    return game.stats.get("drill_radio", 0) >= 1 and _dist(drill, game.player) <= 3


def _glasses(game, drill):
    return bool(game.player_binoculars) and game.stats.get("drill_hits", 0) >= 3


ROLE_TRIALS = {
    "sniper": [("The far dummy is yours. Three hits at long range - steady your aim first.",
                lambda d, g, ps: g.stats.get("drill_hits", 0) >= 3, None)],
    "medic": [("Two men are hit by the marker. Get to the first and dress him: stand beside him and press b.",
               lambda d, g, ps: g.stats.get("drill_bandages", 0) >= 1, "casualties"),
              ("He's stable. Pick him up and carry him back to the bags: E beside him, then Carry him.",
               lambda d, g, ps: g.player.carrying is not None, None),
              ("Put him down behind the bags (B), and dress the second man.", _dressed, None)],
    "engineer": [("There's wire round the marker and a bunker beyond it. You have cutters: walk into the wire.",
                  lambda d, g, ps: _wire_cut(g, d), "wire"),
                 ("The gap's open. Put a charge on the bunker: a on the satchel, then on the bunker.",
                  lambda d, g, ps: _charged(g, d), "charge")],
    "motor_sergeant": [("The half-track by the marker has thrown a track. Go to it and get it back on - stand "
                        "beside the hull with the tools.", lambda d, g, ps: _repaired(g, d), "track_job")],
    "tank_crew": [("There's a carrier at the marker. Get in (e), take the gun, and put five rounds into the dummies.",
                   _inside, "carrier")],
    "radioman": [("The set is yours. Take it to the marker and raise battalion on it: R.",
                  lambda d, g, ps: _radioed(g, d), "radio")],
    "officer": [("Find the dummies through your glasses: V opens the nearby list, b raises the glasses.",
                 lambda d, g, ps: bool(g.player_binoculars), "glasses"),
                ("Now hit three of them.", lambda d, g, ps: g.stats.get("drill_hits", 0) >= 3, None)],
    "lmg_gunner": [("A gunner's job is volume. Ten rounds into the dummies, in bursts.",
                    lambda d, g, ps: g.stats.get("drill_shots", 0) >= 10, None)],
    "hmg_gunner": [("A gunner's job is volume. Ten rounds into the dummies, in bursts.",
                    lambda d, g, ps: g.stats.get("drill_shots", 0) >= 10, None)],
    "at_soldier": [("Put a round into each dummy - tanks are the real work.",
                    lambda d, g, ps: g.stats.get("drill_hits", 0) >= 2, None)],
    "flamethrower": [("Burn them out. Five bursts at the dummies.",
                      lambda d, g, ps: g.stats.get("drill_shots", 0) >= 5, None)],
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
        game.stats.setdefault("drill_buddy", 0)
        game.stats.setdefault("drill_smokes", 0)

    def _steps(self, game):
        steps = list(BASIC)
        self.__dict__["role_stage"] = {}
        if self.mode == "role":
            trial = ROLE_TRIALS.get(game.player.role) or [
                ("Put three rounds into a dummy.", lambda d, g, ps: g.stats.get("drill_hits", 0) >= 3, None)]
            at = 5
            for i, (text, check, stage) in enumerate(trial):
                steps.insert(at + i, (text, lambda d, g, ps, c=check: c(d, g, ps)))
                if stage:
                    self.__dict__["role_stage"][at + i] = stage
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

    def _prop(self, play, stage):
        """The trade's own kit and props on the range."""
        g = play.game
        p = g.player
        mx, my = self.marker
        from .entities import Item
        from .spawn import free_tile_near, make_soldier, place

        def give(tid):
            it = Item(tid)
            if p.add_item(it) is not None:
                return
            if p.invent.add(it, prefer="pack"):
                return
            if p.invent.slots.get("pack") is None:
                p.invent.slots["pack"] = Item("backpack")
                p.invent.add(it, prefer="pack")
            else:
                g.map.add_item(p.x, p.y, it)

        if stage == "casualties":
            for i in range(2):
                a = make_soldier(g, p.nation, "rifleman")
                a.side = p.side
                spot = free_tile_near(g, mx + i * 2 - 1, my, 2) or (mx, my)
                place(g, a, spot[0], spot[1], 1)
                a.ai["drill_target"] = True
                a.ai["drill_casualty"] = True
                a.body.damage(g.rng, "l_leg", 12, "cut")
                a.body.hp["l_leg"] = 0
                a.weapon = None
            for _ in range(6):
                give("bandage")
        elif stage == "wire":
            from . import tiles as T
            for dx, dy in ((-1, 0), (0, -1), (1, 0), (0, 1)):
                x, y = mx + dx, my + dy
                if g.map.in_bounds(x, y):
                    g.map.t[x, y] = T.ID["wire"]
            self.__dict__["wire0"] = _wire_count(g, self)
            give("wirecutters")
        elif stage == "charge":
            give("satchel")
            give("time_pencil")
            self.__dict__["charge_at"] = g.turn
        elif stage in ("track_job", "carrier"):
            from .ai import Order
            from .spawn import make_vehicle_squad
            x, y = free_tile_near(g, mx + 4, my, 4) or (mx + 4, my)
            sq = make_vehicle_squad(g, p.side, p.nation, "halftrack", x, y, 1,
                                    Order("hold", target=(x, y), radius=3, issued=g.turn))
            if sq is not None and sq.vehicles:
                v = sq.vehicles[0]
                v.ai["drill_vehicle"] = True
                if stage == "track_job":
                    from . import vdamage
                    v.parts["tracks"] = vdamage.OUT
                    v.crew = max(2, v.crew)
        elif stage == "radio":
            give("radio_scr300")
        elif stage == "glasses":
            give("binoculars")

    def _stage(self, play, n):
        """Things the range does when a lesson is reached."""
        g = play.game
        text = self.steps[n][0]
        if self.__dict__.get("role_stage", {}).get(n):
            self._prop(play, self.__dict__["role_stage"][n])
        if text.startswith("You're hit"):
            if not g.player.body.wounds:
                g.player.body.damage(g.rng, "l_arm", 5, "cut")
                g.msg("A splinter opens your forearm. It bleeds.", "hurt")
        if text.startswith("The instructor's hit"):
            if self.instructor is not None and not self.instructor.body.wounds:
                self.instructor.body.damage(g.rng, "l_leg", 6, "cut")
                self.instructor.say("Medic! My leg!", g.turn)
        if text.startswith("Pop smoke"):
            from .data.items import ITEMS
            from .entities import Item
            key = "nebel39" if g.player.nation == "germany" else next(
                (k for k, t in ITEMS.items() if t.gtype == "smoke" and g.player.nation in t.nations), "m18_smoke")
            for _ in range(2):
                g.player.invent.add(Item(key), prefer="pockets")

    def skip(self, play):
        """F10: no more lessons, but leave the range as it is."""
        if not self.done:
            self.finish(play)

    def finish(self, play):
        self.done = True
        from .render import Popup
        mins = max(0.2, (play.game.turn - self.started) / 60.0)
        hits = play.game.stats.get("drill_hits", 0)
        g = play.game
        if mins < 1.2 and hits >= 8:
            remark = ("Fast and tidy. Don't get cocky - the range doesn't shoot back.")
        elif g.stats.get("drill_buddy"):
            remark = ("You stopped for the man beside you. That's worth more than the grouping.")
        elif hits < 4:
            remark = ("Slow. The Army will knock the rest out of you, or the enemy will.")
        else:
            remark = ("You'll do. Keep your head down and your magazine full.")
        lines = [("BASIC TRAINING COMPLETE" if self.mode == "basic" else
                  f"{g.player.role_name.upper()} TRIAL COMPLETE", UI_HI),
                 (f"{mins:.1f} minutes. {hits} hits. {g.stats.get('drill_bandages', 0)} dressing(s), "
                  f"{g.stats.get('drill_smokes', 0)} smoke.", UI_TEXT),
                 ("", None), (f"INSTRUCTOR: {remark}", (240, 220, 150)),
                 ("The dummies won't shoot back. Nothing here does, unless you walk into them.", UI_DIM),
                 ("", None), ("In the line: get down, fire from cover, reload behind it.", (200, 210, 180))]
        opts = [("Pass out: back to the menu", "menu", None, True), ("Stay on the range", "keep", None, True)]
        play.open_popup(Popup("Drill complete", opts, play._screen_anchor(), lines=lines, width=62),
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
