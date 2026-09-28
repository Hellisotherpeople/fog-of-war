#!/usr/bin/env python3
"""Make the animated GIFs in the README, headless, from the real game.

    python tools/make_media.py              every clip, into docs/media/
    python tools/make_media.py carrier gq   just those clips
    python tools/make_media.py --list       what there is

The game runs under SDL's dummy video driver; each frame is rendered exactly as it would be
on screen, read back from the renderer and assembled into a GIF (with ffmpeg's palette tools
if ffmpeg is installed, which makes them much smaller; Pillow otherwise).  Your own
~/.fogofwar/settings.json is never touched: the clips use the default settings.
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_home_"))   # never the player's saves or memorial
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "media")

import fow.settings as FS  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="fow_media_")
FS.SETTINGS_PATH = os.path.join(_TMP, "settings.json")       # leave the player's settings alone

import numpy as np  # noqa: E402
import tcod  # noqa: E402
import tcod.event as E  # noqa: E402
from PIL import Image  # noqa: E402

W, H = 1600, 950          # the window the frames are rendered in
SCALE = 0.6               # and how much they're shrunk for the README


class Recorder:
    """A headless window, the game's own renderer, and a list of frames."""

    def __init__(self, sprites=True, zoom=None):
        from fow.ui import App
        from fow.gfx import Graphics
        self.app = App()
        self.app.settings["sprites"] = sprites
        self.app.settings["sound"] = False
        if zoom is not None:
            self.app.settings["zoom" if sprites else "zoom_ascii"] = zoom
        self.ctx = tcod.context.new(width=W, height=H, tileset=self.app.tileset)
        self.app.context = self.ctx
        self.app.gfx = Graphics(self.ctx, self.app.settings)
        self.frames: list[tuple[Image.Image, int]] = []

    def snap(self, state=None, ms=100):
        st = state if state is not None else self.app.states[-1]
        con = self.app.console
        con.clear()
        st.render(con)
        self.app.gfx.present(con, getattr(st, "layers", None), getattr(st, "overlay", None),
                             getattr(st, "map_offset", None))
        img = Image.fromarray(self.ctx.sdl_renderer.read_pixels()[:, :, :3])
        img = img.resize((int(img.width * SCALE), int(img.height * SCALE)), Image.LANCZOS)
        self.frames.append((img, ms))

    def hold(self, ms):
        """Stretch the last frame."""
        if self.frames:
            img, d = self.frames[-1]
            self.frames[-1] = (img, d + ms)

    def crop(self):
        """Trim the black margins the window leaves round the console (the same box for every frame)."""
        box = None
        for img, _ in self.frames:
            b = img.point(lambda v: 255 if v > 12 else 0).getbbox()
            if b is None:
                continue
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        if box is not None:
            box = (max(0, box[0] - 4), max(0, box[1] - 4), box[2] + 4, box[3] + 4)
            self.frames = [(img.crop(box), d) for img, d in self.frames]

    def save(self, name):
        os.makedirs(OUT, exist_ok=True)
        self.crop()
        path = os.path.join(OUT, name + ".gif")
        if shutil.which("ffmpeg"):
            _ffmpeg_gif(self.frames, path)
        else:
            imgs = [f.convert("P", palette=Image.ADAPTIVE, colors=255) for f, _ in self.frames]
            imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=[d for _, d in self.frames],
                         loop=0, optimize=True, disposal=1)
        kb = os.path.getsize(path) // 1024
        print(f"  {name}.gif: {len(self.frames)} frames, {sum(d for _, d in self.frames) / 1000:.1f} s, {kb} KB")
        self.ctx.close()
        return path


def _ffmpeg_gif(frames, path):
    d = tempfile.mkdtemp(prefix="fow_frames_", dir=_TMP)
    lines = []
    for i, (img, ms) in enumerate(frames):
        f = os.path.join(d, f"{i:04d}.png")
        img.save(f)
        lines.append(f"file '{f}'\nduration {ms / 1000:.3f}")
    lines.append(f"file '{os.path.join(d, f'{len(frames) - 1:04d}.png')}'")
    lst = os.path.join(d, "list.txt")
    with open(lst, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    pal = os.path.join(d, "palette.png")
    q = ["-hide_banner", "-loglevel", "error", "-y"]
    subprocess.run(["ffmpeg", *q, "-f", "concat", "-safe", "0", "-i", lst,
                    "-vf", "palettegen=max_colors=192:stats_mode=diff", pal], check=True)
    subprocess.run(["ffmpeg", *q, "-f", "concat", "-safe", "0", "-i", lst, "-i", pal,
                    "-lavfi", "paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                    "-loop", "0", path], check=True)
    shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------ helpers
def _play(rec, game):
    from fow.play import PlayState
    ps = PlayState(rec.app, game)
    rec.app.states = [ps]
    return ps


def _immortal(p):
    """The camera must not die before the clip ends."""
    p.body.hp = {k: 9999 for k in p.body.hp}
    p.body.max = dict(p.body.hp)


def _turn(g, n=1):
    for _ in range(n):
        g.player.moves = 0
        g.world_turn()


def _lift_fog():
    """For the battle clips only: show the whole fight, not just what one man can see."""
    import fow.render as R
    import fow.render_sprites as RS
    import fow.senses as SEN
    for mod in (R, RS, SEN):
        mod.player_can_see_actor = lambda game, a: True


def _hotspot(g, turns=40):
    """Where the fighting is: the densest knot of shots and blasts over the next few turns."""
    pts = []
    for _ in range(turns):
        _turn(g)
        for e in g.effects:
            if e.get("kind") == "tracer":
                pts.append((e["x0"], e["y0"]))           # where the men firing are
            elif "x" in e:
                pts.append((e["x"], e["y"]))
        g.effects = []
    if not pts:
        xs = [a.x for a in g.actors if a.alive]
        ys = [a.y for a in g.actors if a.alive]
        pts = list(zip(xs, ys))
    a = np.array(pts)
    best = max(pts, key=lambda c: int(np.sum((np.abs(a[:, 0] - c[0]) < 14) & (np.abs(a[:, 1] - c[1]) < 9))))
    return best


def _daylight(g):
    """Mid-morning: the clips are for showing, and a dawn attack is mostly darkness."""
    h = g.now().hour + g.now().minute / 60
    if not 9 <= h <= 16:
        g.clock += int(((10 - h) % 24) * 3600)


def _pin_camera(ps, x, y):
    """Hold the view on (x, y) - the camera normally glides after the player in real time."""
    ps._pin = (x + 0.5, y + 0.5)
    ps.view_center = ps._pin
    ps.cam_c = list(ps._pin)


def _follow(ps):
    """Snap the view onto the player (no real-time glide in a headless loop)."""
    ps.recenter()
    ps.cam_c = None


def _battle(rec, g, ps, frames, reveal=True, turns_per_frame=1, ms=110):
    rec.snap(ps, ms)
    rec.frames.pop()                         # the first render moves the view to the player: settle it
    for _ in range(frames):
        _turn(g, turns_per_frame)
        g.player_fov()
        if reveal:
            g.map.visible[:] = True
            g.map.explored[:] = True
        if getattr(ps, "_pin", None):
            ps.view_center = ps._pin
            ps.cam_c = list(ps._pin)
        rec.snap(ps, ms)
        g.effects = []


# ------------------------------------------------------------------ the clips
def clip_battle():
    """Sprites: an infantry fight in the Normandy bocage, fog of war lifted for the camera."""
    from fow.game import Game
    rec = Recorder(sprites=True, zoom=2.2)
    g = Game("bocage44", "usa", seed=3, setup={"battlefield": "standard"})
    _daylight(g)
    ps = _play(rec, g)
    _immortal(g.player)
    _turn(g, 50)
    hx, hy = _hotspot(g, 30)
    _lift_fog()
    _pin_camera(ps, hx, hy)
    _battle(rec, g, ps, 70)
    rec.save("battle")


def clip_tanks():
    """Sprites: Kursk, July 1943 - armour and infantry fighting for a village crossroads."""
    from fow.game import Game
    rec = Recorder(sprites=True, zoom=1.7)
    g = Game("kursk43", "ussr", seed=5, setup={"battlefield": "standard"})
    _daylight(g)
    ps = _play(rec, g)
    _immortal(g.player)
    _turn(g, 60)
    vs = [v for v in g.vehicles if not v.dead]
    if vs:
        vx = np.array([v.x for v in vs])
        vy = np.array([v.y for v in vs])
        hx, hy = max(((v.x, v.y) for v in vs),
                     key=lambda c: int(np.sum((np.abs(vx - c[0]) < 16) & (np.abs(vy - c[1]) < 10))))
    else:
        hx, hy = _hotspot(g, 20)
    _lift_fog()
    _pin_camera(ps, hx, hy)
    _battle(rec, g, ps, 70)
    rec.save("tanks")


def clip_ascii():
    """The same game in ASCII: street fighting in Stalingrad."""
    from fow.game import Game
    rec = Recorder(sprites=False, zoom=1.3)
    g = Game("stalingrad42", "ussr", seed=4, setup={"battlefield": "standard"})
    _daylight(g)
    ps = _play(rec, g)
    _immortal(g.player)
    _turn(g, 50)
    hx, hy = _hotspot(g, 30)
    _lift_fog()
    _pin_camera(ps, hx, hy)
    _battle(rec, g, ps, 60)
    rec.save("ascii")


def clip_carrier():
    """One sailor at an AA mount on a carrier's flight deck, a Japanese strike coming in."""
    from fow.game import Game
    from fow.skysea import Plane
    from fow import aboard as AB, shipboard as SB
    rec = Recorder(sprites=True, zoom=1.25)
    g = Game("okinawa45", "usa", role="sailor", seed=7,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:carrier"})
    ps = _play(rec, g)
    _immortal(g.player)
    ss = g.skysea
    me = AB.ship_of(g)
    SB.general_quarters(g, me)
    _turn(g, 40)
    bn, bx, by, bk = g.aboard["battle_station"]
    if bn != g.aboard["deck"]:
        AB.change_deck(g, bn, bx, by)
    for i, (at, role) in enumerate((("d3a", "dive"), ("d3a", "dive"), ("b5n", "torpedo"), ("zero", "kamikaze"),
                                    ("d3a", "dive"))):
        ang = math.radians(30 + i * 22)
        pl = Plane(at, "axis", "japan", me.x + math.sin(ang) * 22, me.y - math.cos(ang) * 22, 0,
                   2500 if role == "dive" else 500)
        pl.ai = dict(role=role, target=-me.id, wp=(me.x, me.y))
        if role == "kamikaze":
            pl.bombs = [[250, 3, 1]]
        ss.planes.append(pl)
    _turn(g, 8)
    fr = g.aboard["frame"]
    rec.snap(ps, 110)
    rec.frames.pop()                         # the first render moves the view to the player: settle it
    _pin_camera(ps, int(fr.x0 + fr.L * 0.55), int(fr.cy))     # the middle of the flight deck
    for _ in range(80):
        _turn(g)
        g.player_fov()
        g.map.visible[:] = True                 # the whole flight deck, not just the man's own sightlines
        g.map.explored[:] = True
        ps.view_center = ps._pin
        ps.cam_c = list(ps._pin)
        rec.snap(ps, 110)
        g.effects = []
    rec.save("carrier")


def clip_gq():
    """General quarters on a destroyer: the alarm, and Enter takes you through the ship to your gun."""
    from fow.game import Game
    from fow.play import Key
    from fow import aboard as AB, shipboard as SB
    rec = Recorder(sprites=True, zoom=1.9)
    g = Game("okinawa45", "usa", role="sailor", seed=3,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:convoy"})
    ps = _play(rec, g)
    _immortal(g.player)
    ab = g.aboard
    # below in the berthing compartment, off watch, when the alarm goes
    low, spot = ab["deck"], None
    for name in reversed(ab["order"]):
        d = AB.deck(g, name)
        room = next((r for r in d.rooms if r["kind"] == "berthing"), None)
        if room is not None:
            x0, y0, x1, y1 = room["rect"]
            free = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if d.map.is_walkable(x, y)]
            if free:
                low, spot = name, free[len(free) // 2]
                break
    if spot is None:
        spot = (g.player.x, g.player.y)
    AB.change_deck(g, low, spot[0], spot[1])
    _turn(g, 5)
    g.player_fov()
    _follow(ps)
    rec.snap(ps, 900)
    SB.general_quarters(g, AB.ship_of(g))
    g.update_orders(force=True)
    for _ in range(4):
        _turn(g)
        g.player_fov()
        rec.snap(ps, 250)
    ps.on_key(Key(sym=E.KeySym.RETURN))
    for _ in range(400):
        if not ps.wants_tick():
            break
        ps.anim_next = 0
        ps.anim = 0
        ps.tick()
        g.player_fov()
        _follow(ps)
        rec.snap(ps, 90)
        g.effects = []
    for _ in range(6):
        _turn(g)
        g.player_fov()
        rec.snap(ps, 200)
    rec.hold(1500)
    rec.save("gq")


def clip_bomber():
    """Inside a B-17 on a daylight raid: the crew at their guns, flak outside."""
    from fow.game import Game
    from fow import aboard as AB
    rec = Recorder(sprites=True, zoom=2.0)
    g = Game("bocage44", "usa", role="bombardier", seed=4,
             setup={"battlefield": "standard", "service": "air", "scenario": "air:strategic"})
    ps = _play(rec, g)
    _immortal(g.player)
    ss = g.skysea
    pl = AB.plane_of(g)
    m = ss.mission or {}
    # fly on until the target's close and the flak's up
    for i in range(1500):
        _turn(g)
        g.effects = []
        tx, ty = m.get("target_pt", (pl.x, pl.y))
        in_flak = any(f["side"] != pl.side and math.hypot(f["x"] - pl.x, f["y"] - pl.y) < f["r"] for f in ss.flak)
        if math.hypot(tx - pl.x, ty - pl.y) < 45 or in_flak or pl.state != "flying" or g.domain != "aboard":
            break
    for _ in range(80):
        if g.domain != "aboard" or pl.state != "flying" or g.player.body.dead:
            break
        _turn(g)
        g.player_fov()
        g.map.visible[:] = True                 # the sky all round, not just what the windows show
        g.map.explored[:] = True
        meta = g.aboard["meta"]
        _pin_camera(ps, int(meta["x0"] + meta["L"] * 0.5), int(meta["cy"]))   # the whole aircraft
        if not rec.frames:
            rec.snap(ps, 120)
            rec.frames.pop()                 # the first render moves the view to the player: settle it
            _pin_camera(ps, int(meta["x0"] + meta["L"] * 0.5), int(meta["cy"]))
        rec.snap(ps, 120)
        g.effects = []
    rec.save("bomber")


def clip_general():
    """Five stars: the general staff (G), the command tree (C) and the war map (m)."""
    from fow.game import Game
    from fow.play import Key
    from fow.ui import OvermapState
    rec = Recorder(sprites=True)
    g = Game("bocage44", "usa", role="army_group_commander", seed=5)
    ps = _play(rec, g)
    _turn(g, 30)
    g.player_fov()
    ps.on_key(Key(char="G"))
    st = rec.app.states[-1]
    rec.snap(st, 1800)
    for _ in range(5):
        st.on_key(Key(sym=E.KeySym.DOWN))
        rec.snap(st, 450)
    rec.hold(1200)
    rec.app.states = [ps]
    ps.on_key(Key(char="C"))                       # the command tree: every formation under you
    top = rec.app.states[-1]
    rec.snap(top, 1800)
    for _ in range(8):
        top.on_key(Key(sym=E.KeySym.DOWN)) if top is not ps else ps.on_key(Key(sym=E.KeySym.DOWN))
        rec.snap(top, 380)
    rec.hold(1200)
    rec.app.states = [ps]
    ps.popups.clear()
    om = OvermapState(rec.app, g)
    rec.app.states.append(om)
    rec.snap(om, 1800)
    for k in "llllkkkhh":
        om.on_key(Key(char=k))
        rec.snap(om, 280)
    rec.hold(1500)
    rec.save("general")


def clip_kit():
    """The kit: a Tarkov-style grid, looting a body, and the health screen."""
    from fow.game import Game
    from fow.play import Key
    from fow.ui import StatusState
    rec = Recorder(sprites=True)
    g = Game("bocage44", "germany", role="lmg_gunner", seed=8)
    ps = _play(rec, g)
    _turn(g, 10)
    g.player_fov()
    ps.cmd_inventory()
    rec.snap(ps, 2600)
    ps.inv_screen = None
    p = g.player
    e = next(a for a in g.actors if a.side != p.side and a.alive and a.vehicle is None)
    g.remove_from_map(e)
    e.x, e.y = p.x, p.y
    e.body.dead = True
    e.body.cause = "a burst from your MG 42"
    g.actors.append(e)
    g.kill(e, p)
    g.player_fov()
    ps.cmd_pickup()
    pop = ps.popups[-1] if getattr(ps, "popups", None) else None
    if pop is not None:
        # "Here": the body is one of the choices - search it
        idx = next((i for i, o in enumerate(pop.options) if "Search" in str(o[0])), None)
        if idx is not None:
            pop.sel = idx
            ps.on_key(Key(sym=E.KeySym.RETURN))
    if ps.inv_screen is not None:
        ps.inv_screen.focus = 1
    rec.snap(ps, 2600)
    ps.inv_screen = None
    p.body.damage(g.rng, "l_arm", 14, "gunshot")
    _turn(g, 30)
    st = StatusState(rec.app, g)
    rec.snap(st, 2600)
    rec.save("kit")


def clip_creator():
    """The character and battle creator."""
    from fow.ui import CreatorState
    rec = Recorder(sprites=True)
    c = CreatorState(rec.app)
    rec.app.states = [c]
    looks = [dict(side="allies", theatre="bocage44", nation="uk", scenario="raid", role="engineer", rank=3,
                  name="Jack Hardy", traits=["strong"]),
             dict(side="axis", theatre="stalingrad42", nation="germany", scenario="front", role="sniper", rank=2,
                  name="Karl Weber", traits=["crack_shot"]),
             dict(side="allies", theatre="okinawa45", nation="usa", service="navy", scenario="sea:carrier",
                  role="sailor", rank=1, name="Frank O'Brien", traits=[]),
             dict(side="allies", theatre="kursk43", nation="ussr", service="army", scenario="armour",
                  role="tank_crew", rank=5, name="Nikolai Orlov", traits=["brave"])]
    for i, v in enumerate(looks):
        try:
            c.v.update(v)
            c.sel = 3 + i
            rec.snap(c, 1700)
        except Exception as ex:                      # a combination the creator won't show: skip it
            print("   (creator look skipped:", ex, ")")
    rec.save("creator")


def clip_gunline():
    """Sprites: the gun line - an American howitzer battery firing a mission, and the enemy's answer."""
    from fow.game import Game
    rec = Recorder(sprites=True, zoom=2.6)
    g = Game("bocage44", "usa", seed=6, setup={"battlefield": "standard", "scenario": "gunline"})
    _daylight(g)
    g.update_view_range()
    ps = _play(rec, g)
    _immortal(g.player)
    f = g.support.fires
    b = f.player_battery(g)
    guns = [v for v in g.vehicles if v.id in b.vids] or [g.player]
    cx = sum(v.x for v in guns) // len(guns)
    cy = sum(v.y for v in guns) // len(guns)
    cx = max(26, min(g.map.w - 27, cx))                  # keep the view over the map, not the void past its edge
    cy = max(15, min(g.map.h - 16, cy))
    _turn(g, 5)
    g.player_fov()
    _pin_camera(ps, cx, cy)
    f._call_from_front(g, b)
    if b.mission is not None:
        b.mission["start"] = g.turn + 2
    rec.snap(ps, 110)
    rec.frames.pop()
    _lift_fog()
    for i in range(80):
        if f.player_mission(g) is not None and i % 3 == 0 and i < 38:
            ps._order_plan()[1]()
        else:
            _turn(g, 2)
        if i == 38 and g.player.vehicle is not None:
            from fow import actions as A
            A.exit_vehicle(g, g.player)             # (off the gun and into a slit trench before the reply comes)
        g.player_fov()
        g.map.visible[:] = True
        g.map.explored[:] = True
        ps.view_center = ps._pin
        ps.cam_c = list(ps._pin)
        rec.snap(ps, 120)
        g.effects = []
        if i == 40:
            enemy = "axis"
            g._counter_battery = [(g.turn, enemy, b.pos[0], b.pos[1], False)]
    rec.save("gunline")


def clip_help():
    """The help: "Right now" from a tank commander's seat, the keys in bold, and a search."""
    from fow.game import Game
    from fow.play import Key
    from fow.ui import HelpState
    rec = Recorder(sprites=True)
    g = Game("kursk43", "ussr", role="tank_crew", seed=3, setup={"battlefield": "standard", "scenario": "armour"})
    ps = _play(rec, g)
    _turn(g, 3)
    h = HelpState(rec.app, play=ps)
    rec.app.states = [ps, h]
    rec.snap(h, 3200)
    h.on_key(Key(char="v"))
    rec.snap(h, 3200)
    h.on_key(Key(char="/"))
    for c in "fire mission":
        h.on_key(Key(char=c) if c != " " else Key(sym=E.KeySym.SPACE))
        rec.snap(h, 90)
    rec.hold(3000)
    rec.save("help")


def clip_title():
    """The title screen, as a still."""
    from fow.ui import MainMenuState
    rec = Recorder(sprites=True)
    m = MainMenuState(rec.app)
    rec.app.states = [m]
    rec.snap(m, 1000)
    rec.crop()
    img = rec.frames[-1][0]
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, "title.png"), optimize=True)
    print("  title.png")
    rec.ctx.close()


CLIPS = {"title": clip_title, "battle": clip_battle, "tanks": clip_tanks, "ascii": clip_ascii,
         "carrier": clip_carrier, "gq": clip_gq, "bomber": clip_bomber, "general": clip_general, "kit": clip_kit,
         "creator": clip_creator, "gunline": clip_gunline, "help": clip_help}


def main(argv):
    if "--list" in argv:
        for k, f in CLIPS.items():
            print(f"{k:9} {f.__doc__.strip().splitlines()[0]}")
        return
    names = [a for a in argv if not a.startswith("-")] or list(CLIPS)
    try:
        if "--one" in argv:
            CLIPS[names[0]]()
            return
        # each clip in its own process: some lift the fog of war for the camera, and that mustn't leak
        procs = []
        jobs = int(os.environ.get("JOBS", "3"))
        for n in names:
            print(n + ":", CLIPS[n].__doc__.strip().splitlines()[0], flush=True)
            procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "--one", n]))
            while sum(p.poll() is None for p in procs) >= jobs:
                procs[[p.poll() is None for p in procs].index(True)].wait()
        bad = [n for n, p in zip(names, procs) if p.wait() != 0]
        if bad:
            print("failed:", ", ".join(bad))
            sys.exit(1)
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1:])
