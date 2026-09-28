#!/usr/bin/env python3
"""A monkey at the keyboard: plays the real game headless by pressing random keys, to shake out crashes.

    python tools/fuzz.py                       every theatre, 1 seed, 300 steps
    python tools/fuzz.py bocage44,kursk43 3 500
    python tools/fuzz.py all 1 300 allies cmd  as officers up to five stars (exercises the command UI)

Arguments: theatres (comma list or "all"), seeds per theatre, steps per game, side (allies/axis),
and "cmd" for command roles.  Prints one line per game; a crash prints CRASH and the traceback.
FOW_DEBUG=1 is set, so an exception inside one soldier's AI is raised instead of swallowed.
"""
import os
import random
import sys
import tempfile
import time
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_home_"))   # never the player's saves or memorial
os.environ["FOW_DEBUG"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fow.settings as FS  # noqa: E402
FS.SETTINGS_PATH = os.path.join(tempfile.mkdtemp(prefix="fow_fuzz_"), "settings.json")   # not yours

from fow.ui import App  # noqa: E402
from fow.play import PlayState, Key  # noqa: E402
from fow.game import Game  # noqa: E402
from fow.data.theatres import THEATRES  # noqa: E402
from fow.constants import ALLIES, AXIS  # noqa: E402
import tcod.event as E  # noqa: E402

ROLE_POOL = None

def draw(app, ps):
    """Render a frame the way the real window does (sprite layers or ASCII, then the compositor)."""
    app.console.clear()
    ps.render(app.console)
    if app.gfx is not None:
        app.gfx.present(app.console, getattr(ps, "layers", None), getattr(ps, "overlay", None),
                        getattr(ps, "map_offset", None))


def run(th, nat, seed, steps, app, verbose=False):
    if app.gfx is not None:
        app.gfx.enable_sprites(seed % 2 == 0)             # half the games in sprites, half in ASCII (as F2 does)
    role = random.Random(seed * 3 + len(th)).choice(ROLE_POOL) if ROLE_POOL else None
    app.settings["succession"] = ("off", "on", "choose")[seed % 3]     # carrying on as someone else, a third each
    app.settings["succession_rule"] = random.Random(seed).choice(("squad", "unit", "nearest", "role", "rank",
                                                                   "random", "killer"))
    g = Game(th, nat, role=role, seed=seed)
    ps = PlayState(app, g)
    app.states = [ps]
    rng = random.Random(seed)
    t0 = time.perf_counter()
    for step in range(steps):
        if g.game_over or app.states[-1] is not ps:
            break
        ps.anim = 0
        n = 0
        while ps.wants_tick() and n < 80 and not g.game_over:
            ps.anim_next = 0
            ps.tick(); n += 1
        if g.game_over: break
        r = rng.random()
        def key(c=None, sym=None, shift=False): ps.on_key(Key(char=c, sym=sym, shift=shift))
        if ps.inv_screen is not None:
            inv = ps.inv_screen
            rr = rng.random()
            if rr < 0.08:
                key(sym=E.KeySym.ESCAPE)
            elif rr < 0.45:
                key(sym=rng.choice((E.KeySym.UP, E.KeySym.DOWN, E.KeySym.LEFT, E.KeySym.RIGHT)))
            elif rr < 0.6:
                key(sym=E.KeySym.RETURN)
            elif rr < 0.65:
                key(sym=E.KeySym.TAB)
            elif rr < 0.85:
                key(c=rng.choice('rel ucdx[]q'))
            else:
                x, y = rng.randint(0, 93), rng.randint(0, 41)
                ps.on_mouse_motion(x, y) if hasattr(ps, 'on_mouse_motion') else None
                ps.on_click(x, y, rng.choice((1, 1, 3)))
                ps.on_release(x + rng.randint(-5, 5), y + rng.randint(-3, 3), 1)
            if step % 10 == 0:
                draw(app, ps)
            continue
        if ps.popups:
            pop = ps.popups[-1]
            if rng.random() < 0.8 and pop.options:
                en = [i for i,o in enumerate(pop.options) if o[3]]
                if en:
                    pop.sel = rng.choice(en)
                    # avoid surrender
                    if pop.options[pop.sel][1] in ('surrender','abandon'): key(sym=E.KeySym.ESCAPE); continue
                    key(sym=E.KeySym.RETURN)
            else:
                key(sym=E.KeySym.ESCAPE)
            continue
        if ps.mode != 'normal':
            if rng.random() < 0.3:
                key(c=rng.choice('hjklyubn'))
            if ps.mode == 'place':
                key(c=rng.choice('hjklyubn'))
            elif rng.random() < 0.7:
                key(sym=E.KeySym.RETURN)
            else:
                key(sym=E.KeySym.ESCAPE)
            continue
        if r < 0.30:
            key(c=rng.choice('hjklyubn'))
        elif r < 0.40:
            key(c='f')
        elif r < 0.45:
            key(c='.')
        elif r < 0.48:
            key(c='r')
        elif r < 0.51:
            key(c=rng.choice('cp'))
        elif r < 0.56:
            key(c='i')
        elif r < 0.58:
            key(c='t')
        elif r < 0.60:
            key(c='g')
        elif r < 0.62:
            key(c='a')
        elif r < 0.64:
            key(c='B')
        elif r < 0.66:
            key(c='O')
        elif r < 0.68:
            key(c='R')
        elif r < 0.70:
            key(c='e')
        elif r < 0.71:
            key(c='z')
        elif r < 0.72:
            key(c='S')
        elif r < 0.74:
            key(c='D')
        elif r < 0.75:
            key(c='w')
        elif r < 0.76:
            key(c='d')
        elif r < 0.78:
            key(c='x'); key(sym=E.KeySym.ESCAPE)
        elif r < 0.80:
            key(c='F')
        elif r < 0.83:
            # click somewhere on screen
            ps.on_click(rng.randint(0, 93), rng.randint(0, 41), rng.choice((1, 1, 3)))
        elif r < 0.85:
            key(c=rng.choice('HJKLYUBN'))
        elif r < 0.86:
            key(c='v')
        elif r < 0.87:
            key(c='o')
        elif r < 0.92:
            key(c=rng.choice('CCO'))
        elif r < 0.95:
            key(c=rng.choice('qqBY+-'))
        elif r < 0.965:
            key(sym=E.KeySym.RETURN)                   # carry out your orders
        elif r < 0.98 and g.map is not None:
            # right-click the nearest vehicle, or someone nearby: the context menus
            p = g.player
            near = [(v.x, v.y) for v in g.vehicles if not v.dead and abs(v.x - p.x) + abs(v.y - p.y) < 12] + \
                [(a.x, a.y) for a in g.actors if a.alive and a is not p and abs(a.x - p.x) + abs(a.y - p.y) < 4]
            if near:
                x, y = rng.choice(near)
                ps.context_menu(x, y, 10, 10)
        elif r < 0.985:
            key(c='V')
        elif r < 0.99:
            key(c='T')                                 # the orders book: look, choose one, close it
            if app.states[-1] is not ps:
                book = app.states[-1]
                for _ in range(rng.randint(0, 3)):
                    book.on_key(Key(sym=E.KeySym.DOWN))
                app.console.clear()
                book.render(app.console)
                book.on_key(Key(sym=rng.choice((E.KeySym.RETURN, E.KeySym.ESCAPE))))
                if app.states[-1] is book:
                    app.pop()
        elif r < 0.993:
            key(c='A')                                 # autopilot on / off
        elif r < 0.996:
            key(c='E')                                 # talk to whoever's beside you (the menus: popups above)
        elif r < 0.998:
            key(c='X')                                 # read the ground (the going tint) on / off
        else:
            key(c='.')
        if step % 25 == 0:
            draw(app, ps)
    dt = time.perf_counter() - t0
    p = g.player
    return dict(th=th, nat=nat, seed=seed, rank=p.rank_short, orders=g.command.battle.get('orders'), turns=g.turn, over=g.game_over, death=(g.death_text or '')[:110], secs=round(dt,1), role=p.role, kills=g.stats['kills'], sectors=len(g.sector_log))

if len(sys.argv) > 5 and sys.argv[5] == 'cmd':
    ROLE_POOL = ['officer', 'squad_leader', 'company_commander', 'battalion_commander', 'regiment_commander',
                 'brigade_commander', 'division_commander', 'corps_commander', 'army_commander', 'army_group_commander']
app = App()
# a real (headless) renderer, so drawing bugs show up too
try:
    import tcod
    from fow.gfx import Graphics
    _ctx = tcod.context.new(width=1440, height=900, tileset=app.tileset)
    app.context = _ctx
    app.gfx = Graphics(_ctx, app.settings)
except Exception as ex:
    print("(no renderer:", ex, ")")
ths = sys.argv[1].split(',') if len(sys.argv) > 1 and sys.argv[1] != 'all' else list(THEATRES)
seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 1
steps = int(sys.argv[3]) if len(sys.argv) > 3 else 300
for th in ths:
    for s in range(seeds):
        side = random.Random(s).choice((ALLIES, AXIS)) if len(sys.argv) < 5 else sys.argv[4]
        nats = THEATRES[th]['sides'][side]
        nat = random.Random(s+7).choice(nats)[0]
        try:
            res = run(th, nat, 1000 + s, steps, app)
            print(res, flush=True)
        except Exception:
            print("CRASH", th, nat, s)
            traceback.print_exc()
            break
