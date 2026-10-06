"""Flying and fighting ships: the screen.

In the air (one second a keypress): arrows turn (shift: hard) and climb/dive, [ ] throttle,
f fire, b bombs/torpedo, Tab changes station (bombers: pilot, bombardier, gunners), t next
target, e bail out, h head for home, z fly on until something happens.

At sea (ten seconds a keypress): arrows put the helm over and ring for speed, f fire the
main battery at the target, g torpedoes, c depth charges, d dive/surface (submarines),
l launch a strike (carriers), t next target, Tab station, o orders to the force, z steam on.
"""
from __future__ import annotations

import math
import textwrap
import time

import tcod.event as E

from .constants import SCREEN_H, SCREEN_W, UI_BG, UI_DIM, UI_HI, UI_TEXT, VIEW_H, VIEW_W
from .skysea import SEC, Plane, Ship, angdiff, bearing, compass
from .skysea_missions import AIR_MISSIONS, SEA_MISSIONS

ARROW8 = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
BIOME_COL = {"sea": ((30, 60, 120), (12, 28, 70), "~"), "farmland": ((150, 160, 90), (70, 85, 40), '"'),
             "bocage": ((80, 130, 60), (40, 70, 30), "#"), "forest": ((40, 100, 50), (18, 50, 24), "♣"),
             "village": ((160, 140, 110), (70, 70, 50), "⌂"), "town": ((170, 160, 150), (70, 70, 70), "▓"),
             "city_ruins": ((140, 130, 120), (60, 55, 50), "▒"), "factory": ((150, 140, 130), (65, 60, 55), "Σ"),
             "steppe": ((170, 170, 100), (85, 85, 45), ","), "desert": ((210, 190, 130), (120, 100, 60), "~"),
             "hills": ((130, 140, 90), (65, 70, 40), "^"), "mountain": ((140, 130, 120), (70, 65, 60), "▲"),
             "abbey": ((150, 140, 120), (70, 65, 55), "Ω"), "marsh": ((90, 130, 100), (35, 60, 50), "≈"),
             "jungle": ((40, 120, 50), (15, 55, 22), "♠"), "volcanic": ((110, 100, 90), (50, 45, 40), "°"),
             "beach": ((220, 200, 150), (120, 105, 70), "░")}


class SkySeaState:
    def __init__(self, app, game, play):
        self.app = app
        self.game = game
        self.play = play
        self.zoom = 1                      # tiles per text column
        self._terrain = {}
        self.note = ""
        self.auto = 0
        self.orders_menu = False
        self._rt_last = time.monotonic()
        self._rt_elapsed = 0.0

    @property
    def ss(self):
        return self.game.skysea

    @property
    def _rt_action_until(self):
        return self.ss.__dict__.get("player_action_until", 0) if self.ss is not None else 0

    @_rt_action_until.setter
    def _rt_action_until(self, value):
        if self.ss is not None:
            self.ss.player_action_until = value

    # ------------------------------------------------------------ what you're looking from
    def _eye(self):
        ss = self.ss
        if ss.player_plane is not None:
            return ss.player_plane.x, ss.player_plane.y
        if ss.player_ship is not None:
            return ss.player_ship.x, ss.player_ship.y
        if ss.chute is not None:
            return ss.chute[0], ss.chute[1]
        if ss.raft is not None:
            return ss.raft
        return ss.cx * SEC, ss.cy * SEC

    def _cell_world(self, i, j, ex, ey):
        z = self.zoom
        return ex + (i - VIEW_W / 2) * z, ey + (j - VIEW_H / 2) * z * 1.7

    def _world_cell(self, x, y, ex, ey):
        z = self.zoom
        return int(round((x - ex) / z + VIEW_W / 2)), int(round((y - ey) / (z * 1.7) + VIEW_H / 2))

    def _ground(self, wx, wy):
        key = (int(math.floor(wx)), int(math.floor(wy)))
        t = self._terrain.get(key)
        if t is not None:
            return t
        ss = self.ss
        c = ss.sector_at(wx, wy)
        biome = c.biome if c is not None else "sea"
        fg, bg, gl = BIOME_COL.get(biome, BIOME_COL["farmland"])
        h = (key[0] * 73856093 ^ key[1] * 19349663) & 0xFFFF
        jit = (h % 17 - 8) * 1.5
        bg = tuple(max(0, min(255, int(v + jit))) for v in bg)
        ch = gl if h % 5 == 0 else " "
        if biome == "sea" and h % 7 != 0:
            ch = " "
        lx, ly = key[0] % SEC, key[1] % SEC
        if c is not None and c.playable and (lx in (0, SEC - 1) or ly in (0, SEC - 1)):
            # the front: where held ground meets held ground
            st = ss.game.strategic
            nx = c.x + (-1 if lx == 0 else 1 if lx == SEC - 1 else 0)
            ny = c.y + (-1 if ly == 0 else 1 if ly == SEC - 1 else 0)
            n = st.at(nx, ny)
            if n is not None and n.playable and n.control and c.control and n.control != c.control and h % 3 == 0:
                ch, fg = "·", (230, 140, 60)
        if c is not None and c.playable and lx == SEC // 2 and ly == SEC // 2:
            inst = [k for k, sd, ok in c.installations if ok]
            if inst:
                ch = {"airfield": "═", "depot": "■", "aa": "ᴬ", "hq": "H", "artillery": "Ⓐ", "aid": "+",
                      "motor_pool": "M", "fortress": "#", "naval_base": "N"}.get(inst[0], "■")
                fg = (230, 220, 160)
        t = self._terrain[key] = (ch, fg, bg)
        if len(self._terrain) > 60000:
            self._terrain.clear()
        return t

    def _clouds(self, wx, wy):
        from .world import noise
        return noise(wx, wy, 991 + int(self.ss.t // 600), 0.06) > 0.35

    # ------------------------------------------------------------ drawing
    def render(self, con):
        con.clear()
        ss = self.ss
        g = self.game
        if ss is None:
            return
        ex, ey = self._eye()
        me = ss.player_plane
        ship = ss.player_ship
        alt = me.alt if me is not None else (ss.chute[2] if ss.chute else 0)
        cloud_band = 1500 <= alt <= 3200
        above = alt > 3200
        night = g.is_night()
        dim = 0.45 if night else 1.0
        rgb = con.rgb
        for i in range(VIEW_W):
            for j in range(VIEW_H):
                wx, wy = self._cell_world(i, j, ex, ey)
                ch, fg, bg = self._ground(wx, wy)
                if (above or cloud_band) and self._clouds(wx, wy):
                    ch, fg, bg = ("░", (220, 220, 225), (150, 150, 160)) if above else ("▒", (200, 200, 205), (120, 120, 130))
                rgb["ch"][i, j] = ord(ch)
                rgb["fg"][i, j] = tuple(int(v * dim) for v in fg)
                rgb["bg"][i, j] = tuple(int(v * dim) for v in bg)
        side = g.player.side

        def put(x, y, ch, col, bg=None):
            i, j = self._world_cell(x, y, ex, ey)
            if 0 <= i < VIEW_W and 0 <= j < VIEW_H:
                con.print(i, j, ch, fg=col, bg=bg)
        # ground targets you know of
        for g2 in ss.ground:
            if not g2["dead"] and g2["id"] in ss.contacts:
                put(g2["x"], g2["y"], "x", (255, 110, 90))
            elif g2["dead"]:
                put(g2["x"], g2["y"], "*", (120, 80, 60))
        # ships
        for s in ss.ships:
            if not s.alive:
                continue
            if s.side != side and -s.id not in ss.contacts:
                continue
            col = (255, 240, 120) if s.player else (130, 190, 255) if s.side == side else (255, 100, 80)
            if s.cls == "ss" and s.depth > 0:
                put(s.x, s.y, "¦" if s.depth == 1 else "·", col)
                continue
            for k, (cx, cy) in enumerate(s.cells()):
                put(cx, cy, "▬" if k < len(s.cells()) - 1 else ARROW8[int(((s.hdg + 22.5) % 360) // 45)], col)
            if s.fires:
                put(s.x + 0.3, s.y, "▲", (255, 140, 40))
        # planes
        for p in ss.planes:
            if not p.alive:
                continue
            if p.side != side and p.id not in ss.contacts:
                continue
            col = (255, 250, 110) if p.player else (140, 200, 255) if p.side == side else (255, 90, 70)
            if p.fire:
                col = (255, 160, 60)
            put(p.x, p.y, ARROW8[int(((p.hdg + 22.5) % 360) // 45)], col)
            if ss.target == p.id:
                i, j = self._world_cell(p.x, p.y, ex, ey)
                if 0 <= i - 1 and i + 1 < VIEW_W and 0 <= j < VIEW_H:
                    con.print(i - 1, j, "[", fg=(255, 255, 255))
                    con.print(i + 1, j, "]", fg=(255, 255, 255))
        for tp in ss.torps:
            put(tp["x"], tp["y"], "·", (140, 230, 255))
        for e in ss.effects:
            ch, col = {"flak": ("*", (180, 180, 180)), "tracer": ("·", (255, 230, 120)), "splash": ("o", (200, 220, 255)),
                       "hit": ("*", (255, 160, 60)), "explosion": ("☼", (255, 150, 40)), "blast": ("*", (255, 120, 40)),
                       "muzzle": ("°", (255, 240, 180)), "dc": ("Ø", (200, 230, 255))}.get(e["kind"], ("*", (255, 255, 255)))
            put(e["x"], e["y"], ch, col)
        if ss.chute is not None:
            put(ss.chute[0], ss.chute[1], "⌂", (240, 240, 240))
        if ss.raft is not None:
            put(ss.raft[0], ss.raft[1], "o", (255, 200, 80))
        # mission marker
        m = ss.mission or {}
        tp = m.get("target_pt") or (m.get("shore")[:2] if m.get("shore") else None)
        if tp and m.get("stage") not in ("done",):
            i, j = self._world_cell(tp[0], tp[1], ex, ey)
            if 0 <= i < VIEW_W and 0 <= j < VIEW_H:
                con.print(i, j, "X", fg=(245, 215, 110))
        self._hud(con)
        from .render import draw_log, draw_popup
        draw_log(con, g)
        # menus opened from here (the admiral's signals) live on the play state: draw them over the chart
        for pop in getattr(self.play, "popups", []) or []:
            draw_popup(con, pop)
        hint = self._hint()
        con.print(0, 0, f" {hint} "[:VIEW_W], fg=(20, 20, 20), bg=(200, 190, 140))

    def _hint(self):
        ss = self.ss
        if ss.player_plane is not None:
            out = "e/Esc back to the fuselage (bail out at the hatch)" if getattr(self, "aboard", False) else "e bail out"
            if ss.station == "pilot":
                return f"←→ turn (shift hard)  ↑↓ climb/dive  [ ] throttle  f fire  b bombs  t target  Tab station  {out}  z fly on  +/- zoom"
            if ss.station == "bombardier":
                return "BOMBARDIER: b release over the target  t target  Tab station  z fly on  +/- zoom"
            return f"{ss.station.upper()}: t pick a fighter, f fire  Tab station  z fly on  +/- zoom"
        if ss.player_ship is not None:
            return "←→ helm  ↑↓ speed  f fire  g torpedoes  c depth charges  d dive  l air strike  t target  o orders  Tab station  z steam on"
        if ss.chute is not None:
            return "Under the canopy. Space: drift down."
        return "Adrift. Space: wait."

    def _hud(self, con):
        ss = self.ss
        g = self.game
        x = VIEW_W + 1
        w = SCREEN_W - x - 1
        con.draw_rect(VIEW_W, 0, SCREEN_W - VIEW_W, SCREEN_H, ord(" "), bg=UI_BG)
        y = 0
        p = g.player

        def line(t, col=UI_TEXT):
            nonlocal y
            for s in textwrap.wrap(t, w) or [""]:
                if y < SCREEN_H - 1:
                    con.print(x, y, s, fg=col, bg=UI_BG)
                    y += 1
        line(f"{p.rank_full} {p.name}", UI_HI)
        if self.play.realtime_enabled():
            pace = self.app.settings.get("realtime_pace", "deliberate")
            speed = {"normal": "1x", "deliberate": "0.5x", "slow": "0.25x"}.get(pace, "0.5x")
            left = max(0, self._rt_action_until - ss.t)
            paused = bool(self.play.popups) or not getattr(self.app, "focused", True)
            state = "PAUSED" if paused else f"busy {left:.0f}s" if left else "ready"
            line(f"REAL TIME {speed} - {state} (F6)", (140, 205, 210))
        me = ss.player_plane
        ship = ss.player_ship
        if me is not None:
            line(f"{me.name} - {ss.station}", (220, 200, 140))
            vs = "↑" if me.pitch > 0 else "↓" if me.pitch < 0 else "-"
            line(f"{int(me.kmh)} km/h   {int(me.alt)} m {vs}")
            line(f"Heading {int(me.hdg):03d}° {compass(me.hdg)}   throttle {int(me.throttle * 100)}%")
            line(f"Fuel {int(me.fuel)}%   ammunition {max(0, me.ammo)}", (240, 120, 90) if me.fuel < 25 else UI_TEXT)
            if me.bombs:
                line("Bombs: " + ", ".join(f"{c} x {pw}kg" for pw, r, c in me.bombs))
            if me.torpedo:
                line("Torpedo: armed (drop below 90 m, under 330 km/h)")
            y += 1
            line("Airframe", UI_DIM)
            for k in ("wing_l", "wing_r", "tail", "cockpit", "fuel"):
                v = me.hp[k]
                col = (150, 220, 140) if v > 70 else (240, 200, 90) if v > 30 else (255, 90, 70)
                line(f"  {k.replace('_l', ' (left)').replace('_r', ' (right)'):14} {int(v)}%", col)
            for i, v in enumerate(me.hp["engine"]):
                col = (150, 220, 140) if v > 70 else (240, 200, 90) if v > 30 else (255, 90, 70)
                line(f"  engine {i + 1:<7} {'DEAD' if v <= 0 else str(int(v)) + '%'}", col)
            if me.fire:
                line("  ON FIRE!", (255, 120, 40))
            crew = [c for c in me.crew]
            if len(crew) > 1:
                line(f"Crew {sum(1 for c in crew if c['alive'])}/{len(crew)}: " +
                     ", ".join(c["station"] + ("" if c["alive"] else " (dead)") for c in crew), UI_DIM)
            line(f"Victories: {me.kills}", (240, 210, 110))
        elif ship is not None:
            from .data.ships import CLASS_NAME
            line(f"{ship.name} ({ship.st['name']})", (220, 200, 140))
            line(f"Station: {ss.station}")
            line(f"{ship.kn:.0f} kn (ordered {ship.order_kn:.0f})   heading {int(ship.hdg):03d}° (to {int(ship.order_hdg):03d}°)")
            hp = ship.hp / ship.st["hp"] * 100
            line(f"Hull {int(hp)}%   flooding {int(ship.flood)}%   fires {ship.fires}",
                 (150, 220, 140) if hp > 60 else (240, 200, 90) if hp > 30 else (255, 90, 70))
            if ship.st["main"]:
                ready = "ready" if ss.t >= ship.main_ready else f"reloading {int(ship.main_ready - ss.t)}s"
                line(f"Main battery {ship.st['main'][1] - ship.turret_out}x{ship.st['main'][0]}mm: {ready}")
            if ship.st["torps"]:
                line(f"Torpedoes: {ship.torps}")
            if ship.st["dc"]:
                line(f"Depth charges: {ship.dc}")
            if ship.cls == "ss":
                line(f"{['SURFACED', 'PERISCOPE DEPTH', 'DEEP'][ship.depth]}   battery {int(ship.battery)}%")
            if ship.air is not None:
                line(f"Air group: {ship.air[0]} fighters, {ship.air[1]} dive bombers, {ship.air[2]} torpedo bombers")
            force = [s for s in ss.ships if s.alive and s.side == p.side and s is not ship]
            if force:
                line(f"With you: {len(force)} ships", UI_DIM)
        elif ss.chute is not None:
            line(f"Under a parachute, {int(ss.chute[2])} m up.", (220, 200, 140))
        elif ss.raft is not None:
            line("In a life raft.", (220, 200, 140))
        y += 1
        # target
        tgt = ss.entity(ss.target) if ss.target else None
        ex, ey = self._eye()
        if tgt is not None:
            if isinstance(tgt, Plane) and tgt.alive:
                d = math.hypot(tgt.x - ex, tgt.y - ey) / 10
                line(f"Target: {tgt.name}", (255, 150, 120))
                line(f"  {d:.1f} km, bearing {int(bearing(ex, ey, tgt.x, tgt.y)):03d}°, "
                     f"{'+' if tgt.alt >= (me.alt if me else 0) else ''}{int(tgt.alt - (me.alt if me else 0))} m")
            elif isinstance(tgt, Ship) and tgt.alive:
                from .data.ships import CLASS_NAME
                d = math.hypot(tgt.x - ex, tgt.y - ey) / 10
                line(f"Target: {CLASS_NAME.get(tgt.cls, 'ship')}", (255, 150, 120))
                line(f"  {d:.1f} km, bearing {int(bearing(ex, ey, tgt.x, tgt.y)):03d}°, "
                     f"ranging {int(ss.player_ship.ranging.get(tgt.id, 0) * 100) if ss.player_ship else 0}%")
            elif isinstance(tgt, dict) and not tgt.get("dead"):
                d = math.hypot(tgt["x"] - ex, tgt["y"] - ey) / 10
                line(f"Target: {tgt['name']}", (255, 150, 120))
                line(f"  {d:.1f} km, bearing {int(bearing(ex, ey, tgt['x'], tgt['y'])):03d}°")
        # mission
        m = ss.mission or {}
        if m:
            y += 1
            line("MISSION", UI_HI)
            line(m.get("text", ""), UI_TEXT)
            pt = m.get("target_pt") if m.get("stage") in ("outbound", "search") else m.get("base_pt") or m.get("home")
            if pt:
                d = math.hypot(pt[0] - ex, pt[1] - ey) / 10
                line(f"{'Target' if m.get('stage') in ('outbound', 'search') else 'Home'}: {d:.1f} km, "
                     f"bearing {int(bearing(ex, ey, pt[0], pt[1])):03d}° {compass(bearing(ex, ey, pt[0], pt[1]))}",
                     (245, 215, 110))
        if self.note:
            y += 1
            line(self.note, (250, 220, 150))
        # contacts
        y += 1
        line("Contacts", UI_DIM)
        n = 0
        for e in ss.planes:
            if e.alive and e.id in ss.contacts and n < 6:
                d = math.hypot(e.x - ex, e.y - ey) / 10
                line(f"  {e.name[:18]:18} {d:4.1f}km {compass(bearing(ex, ey, e.x, e.y)):>3} {int(e.alt)}m", (255, 130, 110))
                n += 1
        for s in ss.ships:
            if s.alive and -s.id in ss.contacts and n < 10:
                from .data.ships import CLASS_NAME
                d = math.hypot(s.x - ex, s.y - ey) / 10
                line(f"  {CLASS_NAME.get(s.cls, 'ship')[:18]:18} {d:4.1f}km {compass(bearing(ex, ey, s.x, s.y)):>3}",
                     (255, 130, 110))
                n += 1

    # ------------------------------------------------------------ input
    def wants_tick(self):
        return self.auto > 0 or self.play.realtime_enabled()

    def reset_realtime_clock(self):
        self._rt_last = time.monotonic()
        self._rt_elapsed = 0.0

    def _realtime_tick(self, now=None):
        now = time.monotonic() if now is None else now
        elapsed = max(0., now - self._rt_last)
        self._rt_last = now
        if not getattr(self.app, "focused", True) or self.play.popups or self.ss is None or \
                (self.app.states and self.app.states[-1] is not self):
            self._rt_elapsed = 0.0
            return False
        pace = self.app.settings.get("realtime_pace", "deliberate")
        interval = {"normal": 1., "deliberate": 2., "slow": 4.}.get(pace, 2.)
        if elapsed > max(5., interval * 2):
            self._rt_elapsed = 0.
            return False
        self._rt_elapsed += elapsed
        if self._rt_elapsed < interval:
            return False
        self._rt_elapsed %= interval
        self._advance(seconds=1)
        return True

    def tick(self):
        if self.play.realtime_enabled() and not self.auto:
            self._realtime_tick()
            return
        self.reset_realtime_clock()
        if self.play.realtime_enabled() and not getattr(self.app, "focused", True):
            return
        if self.auto > 0:
            before = (set(self.ss.contacts), self._hurt_level())
            self.auto -= 1
            self._advance()
            if self.ss is None or self.game.__dict__.get("skysea") is None or \
                    (self.app.states and self.app.states[-1] is not self):
                self.auto = 0                    # the flight ended under us
                return
            if set(self.ss.contacts) - before[0] or self._hurt_level() < before[1] or self.ss.over:
                self.auto = 0
                self.note = "Something's happening."

    def _hurt_level(self):
        ss = self.ss
        if ss.player_plane is not None:
            p = ss.player_plane
            return sum(p.hp["engine"]) + p.hp["wing_l"] + p.hp["wing_r"] + p.hp["tail"] + p.hp["fuel"]
        if ss.player_ship is not None:
            return ss.player_ship.hp
        return 0

    def _advance(self, seconds=None):
        ss = self.ss
        dt = seconds if seconds is not None else 1 if (ss.player_plane is not None or ss.chute is not None) else 10
        if getattr(self, "aboard", False):
            # at the chart table aboard: the ship's life goes on around you, second by second
            from .aboard import advance
            if seconds is None:
                advance(self.play, dt)
            else:
                # A clock tick is exactly one second, independent of the sailor's action-point balance.
                for _ in range(int(dt)):
                    self.game.world_turn()
                    if ss.over or self.game.game_over:
                        break
                self.game.player_fov()
                self.play.check_over()
            for n in ss.news[-2:]:
                self.game.msg(n, "radio")
            ss.news = []
            if ss.over or self.game.game_over:
                if self.app.states and self.app.states[-1] is self:
                    self.app.pop()               # (not if the game-over screen has already replaced us)
                self.play._skysea_pushed = False
            return
        ss.step(dt)
        for n in ss.news[-2:]:
            self.game.msg(n, "radio")
        ss.news = []
        self._check_end()

    def _cycle_target(self):
        ss = self.ss
        ex, ey = self._eye()
        cands = [e for e in ss.planes if e.alive and e.id in ss.contacts]
        cands += [s for s in ss.ships if s.alive and -s.id in ss.contacts]
        cands += [g2 for g2 in ss.ground if not g2["dead"] and g2["id"] in ss.contacts]

        def pos(e):
            return (e["x"], e["y"]) if isinstance(e, dict) else (e.x, e.y)
        cands.sort(key=lambda e: math.hypot(pos(e)[0] - ex, pos(e)[1] - ey))
        if not cands:
            self.note = "Nothing in sight."
            return
        ids = [(e["id"] if isinstance(e, dict) else (-e.id if isinstance(e, Ship) else e.id)) for e in cands]
        i = (ids.index(ss.target) + 1) % len(ids) if ss.target in ids else 0
        ss.target = ids[i]
        if ss.player_ship is not None and isinstance(cands[i], Ship):
            ss.player_ship.target = cands[i].id

    def on_key(self, key):
        ss = self.ss
        if ss is None:
            return self.app.pop()
        if key.sym == E.KeySym.F6:
            self.auto = 0
            self.play.cmd_realtime()
            self.reset_realtime_clock()
            if not self.play.realtime_enabled() and self._rt_action_until > ss.t:
                self._advance(seconds=int(math.ceil(self._rt_action_until - ss.t)))
            return
        if getattr(self.play, "popups", None):
            return self.play.popup_key(key)
        self.note = ""
        self.auto = 0
        c = key.char
        if getattr(self, "aboard", False) and (key.sym == E.KeySym.ESCAPE or c in ("e", "q")):
            # step back from the chart onto the deck (the captain's AI - or the officer of the watch - has her)
            ss.station = "deck"
            self.play._skysea_pushed = False
            self.game.msg("You step back from the plot.", "info")
            return self.app.pop()
        if key.sym == E.KeySym.ESCAPE:
            from .ui import EscMenuState
            self.app.push(EscMenuState(self.app, self.play))
            return
        if c in ("+", "="):
            self.zoom = max(1, self.zoom // 2)
            return
        if c == "-":
            self.zoom = min(16, self.zoom * 2)
            return
        if c == "?":
            from .ui import TextState
            from .ui import HelpState
            return self.app.push(HelpState(self.app, "chart"))
        if c == "m":
            from .ui import OvermapState
            return self.app.push(OvermapState(self.app, self.game))
        if c == "t":
            return self._cycle_target()
        if c == "z":
            self.auto = 120 if ss.player_plane is not None else 90
            return
        if self._rt_action_until > ss.t:
            if self.play.realtime_enabled():
                self.note = "Still carrying out the last action."
                return
            self._advance(seconds=int(math.ceil(self._rt_action_until - ss.t)))
            if self.ss is not ss or ss.over:
                return
        me = ss.player_plane
        ship = ss.player_ship
        acted = True
        if me is not None:
            acted = self._air_key(key, me)
        elif ship is not None:
            acted = self._sea_key(key, ship)
        elif key.sym in (E.KeySym.SPACE,) or c == ".":
            acted = True
        else:
            acted = False
        if acted:
            if self.play.realtime_enabled():
                self._rt_action_until = ss.t + (1 if me is not None or ss.chute is not None else 10)
            else:
                self._advance()

    def _air_key(self, key, me):
        ss = self.ss
        c = key.char
        mv = None
        if key.sym in (E.KeySym.LEFT, E.KeySym.KP_4) or c in ("a",):
            mv = "left"
        elif key.sym in (E.KeySym.RIGHT, E.KeySym.KP_6) or c in ("d",):
            mv = "right"
        if c == "e":
            # anyone aboard can go over the side
            r = ss.bail_out(me)
            if r:
                self.note = r
                return False
            return True
        if key.sym == E.KeySym.TAB:
            st = [x["station"] for x in me.crew if x["alive"]]
            if len(st) > 1:
                i = (st.index(ss.station) + 1) % len(st) if ss.station in st else 0
                ss.station = st[i]
                self.note = f"You take the {ss.station}'s position."
            return False
        if ss.station == "pilot":
            if mv:
                tr = me.turn_rate() * (1.8 if key.shift else 1.0)
                me.hdg = (me.hdg + (-tr if mv == "left" else tr)) % 360
                if key.shift:
                    me.kmh -= 25                   # a hard turn bleeds speed
                me.pitch = 0
            elif key.sym in (E.KeySym.UP, E.KeySym.KP_8) or c == "w":
                me.pitch = 1
            elif key.sym in (E.KeySym.DOWN, E.KeySym.KP_2) or c == "s":
                me.pitch = -1
            elif c == "[":
                me.throttle = max(0.1, me.throttle - 0.15)
                return False
            elif c == "]":
                me.throttle = min(1.0, me.throttle + 0.15)
                return False
            elif c == "f":
                tgt = ss.entity(ss.target) if ss.target else None
                h = ss.fire_guns(me, tgt if isinstance(tgt, Plane) else None)
                self.note = "Hits!" if h else "Your burst goes wide." if me.ammo > 0 else "Out of ammunition."
            elif c == "b":
                ss.drop(me)
            elif c == "e":
                r = ss.bail_out(me)
                if r:
                    self.note = r
                    return False
            elif c == "h":
                bp = (ss.mission or {}).get("base_pt") or me.home
                if bp:
                    me.hdg = bearing(me.x, me.y, bp[0], bp[1])
                    self.note = "You swing onto the heading for home."
            elif key.sym in (E.KeySym.SPACE, E.KeySym.KP_5) or c == ".":
                me.pitch = 0
            else:
                return False
            return True
        if ss.station == "bombardier":
            if c == "b":
                ss.drop(me)
                return True
            if key.sym in (E.KeySym.SPACE,) or c == ".":
                return True
            if mv:
                # 'left, left... steady': a correction on the run, not a new course
                off = me.ai.get("bomb_trim", 0) + (-3 if mv == "left" else 3)
                me.ai["bomb_trim"] = max(-30, min(30, off))
                me.hdg = (me.hdg + (-3 if mv == "left" else 3)) % 360
                return True
            return False
        # a gunner
        if c == "f":
            tgt = ss.entity(ss.target) if ss.target else None
            self.note = ss.gunner_fire(me, ss.station, tgt)
            return True
        if key.sym in (E.KeySym.SPACE,) or c == ".":
            return True
        return False

    def _sea_key(self, key, ship):
        ss = self.ss
        c = key.char
        rank = self.game.player.rank
        bridge = ss.station in ("bridge", "captain")
        if ss.station == "plot":
            # a seaman at the plot: he can look, zoom and let time pass - the orders aren't his to give
            if key.sym == E.KeySym.TAB or (c and c in "tfbhrgoaAc") or key.sym in (
                    E.KeySym.LEFT, E.KeySym.RIGHT, E.KeySym.UP, E.KeySym.DOWN):
                self.note = "Not your ship to command. (Esc to step back)"
                return False
            return key.sym in (E.KeySym.SPACE, E.KeySym.KP_5) or c == "."     # watching the plot: time goes by
        if key.sym == E.KeySym.TAB:
            opts = ["bridge", "main battery", "aa gun", "damage control"]
            i = (opts.index(ss.station) + 1) % len(opts) if ss.station in opts else 0
            ss.station = opts[i]
            self.note = f"You go to the {ss.station}."
            return False
        if bridge:
            if key.sym in (E.KeySym.LEFT, E.KeySym.KP_4):
                ship.order_hdg = (ship.order_hdg - 15) % 360
                self.note = f"'Port fifteen. Come to {int(ship.order_hdg):03d}.'"
                return True
            if key.sym in (E.KeySym.RIGHT, E.KeySym.KP_6):
                ship.order_hdg = (ship.order_hdg + 15) % 360
                self.note = f"'Starboard fifteen. Come to {int(ship.order_hdg):03d}.'"
                return True
            steps = [0, 0.33, 0.66, 0.85, 1.0]
            cur = min(range(len(steps)), key=lambda i: abs(steps[i] * ship.st["speed"] - ship.order_kn))
            if key.sym in (E.KeySym.UP, E.KeySym.KP_8):
                ship.order_kn = steps[min(4, cur + 1)] * ship.st["speed"]
                self.note = ["'All stop.'", "'Ahead one third.'", "'Ahead two thirds.'", "'Ahead full.'",
                             "'Ahead flank!'"][min(4, cur + 1)]
                return True
            if key.sym in (E.KeySym.DOWN, E.KeySym.KP_2):
                ship.order_kn = steps[max(0, cur - 1)] * ship.st["speed"]
                self.note = ["'All stop.'", "'Ahead one third.'", "'Ahead two thirds.'", "'Ahead full.'",
                             "'Ahead flank!'"][max(0, cur - 1)]
                return True
        tgt = ss.entity(-ship.target) if ship.target else None
        if c == "f" and ss.station in ("bridge", "main battery", "captain"):
            m = ss.mission or {}
            if m.get("shore") and (tgt is None or not tgt.alive):
                return self._bombard(ship, m)
            if not isinstance(tgt, Ship) or not tgt.alive:
                self.note = "No target. (t to pick one)"
                return False
            gun = ship.st["main"] or ship.st["sec"]
            if gun is None:
                self.note = "No guns to speak of."
                return False
            if ss.t < ship.main_ready:
                self.note = f"Reloading - {int(ship.main_ready - ss.t)} seconds."
                return True
            d = math.hypot(tgt.x - ship.x, tgt.y - ship.y)
            if d > gun[2]:
                self.note = f"Out of range ({d / 10:.1f} km; the guns reach {gun[2] / 10:.1f})."
                return False
            ss.salvo(ship, tgt, gun)
            self.note = f"'Shoot!' - a salvo on its way, {int(d / 7)} seconds' flight."
            return True
        if c == "g" and bridge:
            if not isinstance(tgt, Ship) or not tgt.alive:
                self.note = "No target for the torpedoes."
                return False
            self.note = ss.fire_torpedoes(ship, tgt, spread=4 if ship.cls != "ss" else 3)
            return True
        if c == "c" and bridge:
            subs = [s for s in ss.ships if s.alive and s.side != ship.side and s.cls == "ss"]
            if not subs:
                self.note = "No submarine contact."
                return False
            sub = min(subs, key=lambda s: math.hypot(s.x - ship.x, s.y - ship.y))
            self.note = ss.depth_charges(ship, sub)
            return True
        if c == "d" and bridge and ship.cls == "ss":
            ship.depth = (ship.depth + 1) % 3
            self.note = ["'Surface!'", "'Periscope depth.'", "'Take her deep!'"][ship.depth]
            return True
        if c == "l" and bridge and ship.air is not None:
            if not isinstance(tgt, Ship) or not tgt.alive:
                self.note = "Pick a target for the strike first (t)."
                return False
            self.note = ss.launch_strike(ship, tgt)
            return True
        if c == "o" and bridge:
            if rank >= 13 or self.game.player.role in ("admiral", "ship_captain"):
                return self._fleet_order(ship)
            self.note = "Signalling the force is for the senior officer present - not you."
            return False
        if ss.station == "aa gun" and c == "f":
            planes = [p for p in ss.planes if p.alive and p.side != ship.side and math.hypot(p.x - ship.x, p.y - ship.y) < 9]
            if not planes:
                self.note = "Nothing overhead."
                return False
            p2 = min(planes, key=lambda p: math.hypot(p.x - ship.x, p.y - ship.y))
            if ss.rng().random() < 0.12 + self.game.player.skill * 0.01:
                ss._plane_hit(p2, 45, None, aspect=90)
                self.note = f"Your tracers walk into the {p2.name}!"
            else:
                self.note = "You hose the sky with tracer."
            return True
        if ss.station == "damage control" and c in ("f", " ") or (ss.station == "damage control" and
                                                                    key.sym == E.KeySym.SPACE):
            if ship.fires:
                ship.fires -= 1
                self.note = "You drag a hose into the smoke. The fire is out."
            elif ship.flood > 0:
                ship.flood = max(0.0, ship.flood - 8)
                self.note = "You shore up the bulkhead with timbers. The water slows."
            else:
                self.note = "Nothing to fight."
            return True
        if key.sym in (E.KeySym.SPACE, E.KeySym.KP_5) or c == ".":
            return True
        return False

    def _bombard(self, ship, m):
        ok, note = self.ss.shore_salvo(ship, m)
        self.note = note
        return ok

    def _fleet_order(self, ship):
        ss = self.ss
        force = [s for s in ss.ships if s.alive and s.side == ship.side and s is not ship]
        if not force:
            self.note = "You have no other ships."
            return False
        from .render import Popup
        opts = [("All ships: follow me in line", "follow", None, True), ("All ships: engage my target", "engage", None, True),
                ("Destroyers: attack with torpedoes", "torps", None, True), ("All ships: act independently", "free", None, True)]
        opts += [(f"{s.name}: stop for replenishment alongside", s, None, True) for s in force if s.st.get("cargo")]

        def pick(v):
            if not v:
                return
            if isinstance(v, Ship):
                v.ai["holding_for_replenishment"] = True
                v.order_kn = 0.
                self.note = f"{v.name} is stopping. Close within 300 metres at six knots or less; calm water required."
                self.game.msg(self.note, "radio")
                return
            tgt = ss.entity(-ship.target) if ship.target else None
            if v in ("engage", "torps") and tgt is None:
                self.note = "Pick a target first (t) - the signal needs one."
                return
            n = 0
            for i, s in enumerate(force):
                s.ai.pop("holding_for_replenishment", None)
                if v == "follow":
                    s.ai.update(role="line", leader=ship.id, offset=(0, 2 + 2 * i))
                    n += 1
                elif v == "engage":
                    s.target = tgt.id
                    n += 1
                elif v == "torps" and s.cls in ("dd", "pt"):
                    s.ai.update(role="strike", leader=None, wp=(tgt.x, tgt.y))
                    s.target = tgt.id
                    n += 1
                elif v == "free":
                    s.ai.update(role="screen", leader=None)
                    n += 1
            if not n:
                self.note = "No ship of yours can do that - there are no destroyers with you."
                return
            self.note = {"follow": "Signal: form line astern.", "engage": "Signal: concentrate fire on the enemy.",
                         "torps": "Signal: destroyers, attack!", "free": "Signal: engage at will."}[v]
        self.play.open_popup(Popup("Signal to the force", opts, (VIEW_W // 2, VIEW_H // 2)), pick)
        self.app.pop() if False else None
        return False

    # ------------------------------------------------------------ coming back to earth
    def _check_end(self):
        ss = self.ss
        g = self.game
        if not ss.over:
            return
        over = ss.over
        from .skysea_exit import finish
        finish(g, over, self)


HELP_TEXT = [
    ("ABOARD (a ship's helm or plot, a bomber's station): Esc, e or q steps back onto the deck / into the", UI_HI),
    ("  fuselage - the ship's life goes on around you either way. From a bomber you bail out at the hatch.", None),
    ("", None),
    ("IN THE AIR (each key is a second)", UI_HI),
    ("  ← → or a d  turn (shift+arrow: hard turn - it bleeds speed)     ↑ or w climb   ↓ or s dive", None),
    ("  space or .  fly straight (bombardier and gunners: wait)     bombardier: ← → correct the aim, b release", None),
    ("  [ ]  throttle     f fire the guns along your nose     b bombs away / drop the torpedo", None),
    ("  t    pick a target     Tab  change station (bombers: pilot, bombardier, the gunners)", None),
    ("  h    turn for home     e  bail out (above 120 m)     z  fly on until something happens", None),
    ("  Level bombing: the bombs fall forward - the X is the target; release when it's under you.", None),
    ("  Dive bombing: dive steeply at the target and release low.  Torpedoes: below 90 m, under 330 km/h.", None),
    ("  Landing: back over your airfield, low (<150 m) and slow (<320 km/h).", None),
    ("", None),
    ("AT SEA (each key is ten seconds)", UI_HI),
    ("  ← →  helm fifteen degrees     ↑ ↓  ring for more or less speed     t  pick a target", None),
    ("  f    fire the main battery (salvos walk onto the target)     g  torpedoes     c  depth charges", None),
    ("  d    dive / periscope / surface (submarines)     l  launch an air strike (carriers)", None),
    ("  o    signal your force (captains and admirals)     Tab  bridge, main battery, AA gun, damage control", None),
    ("  z    steam on until something happens     +/-  zoom     m  war map     space or .  wait ten seconds", None),
    ("  At the plot (not an officer): you watch; t, zoom, space and z work, the orders aren't yours.", None),
    ("  Damage control: f or space to fight the fire or the flooding.", None),
    ("", None),
    ("  ? this help     Esc the menu (or back onto the deck)     F2 sprites/ASCII   F3 sound   F4 font", None),
]
