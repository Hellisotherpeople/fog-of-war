"""Coming back to the ground: landing, parachutes, and the sea."""
from __future__ import annotations

import math

from .constants import other_side
from .skysea import SEC


def to_land(g, sector, frac=None, airfield=False, notes=None):
    """Put the player on the ground in `sector` (its battlefield made or loaded as usual)."""
    from .ai import Order
    from .ai import Squad
    from .spawn import edge_band_point, place
    p = g.player
    if g.map is not None and g.sector is not None and g.sector is not sector and not g.__dict__.get("aboard"):
        g._save_map()
        g.sector.units = g.local_units()
    if p in g.actors:
        g.remove_actor(p)
    p.vehicle = None
    if sector is not g.sector or g.map is None or g.__dict__.get("aboard"):
        g.aboard = None
        g.enter_sector(sector, entry_edge=None)
    m = g.map
    spot = None
    if airfield:
        recs = [r for r in (getattr(m, "gen_positions", None) or []) if r.get("kind") == "airfield" and r.get("side") == p.side]
        if recs:
            spot = (recs[0]["x"], recs[0]["y"])
    if spot is None and frac is not None:
        spot = (int(frac[0] * (m.w - 4)) + 2, int(frac[1] * (m.h - 4)) + 2)
    if spot is None:
        e = g.home_edge(p.side)
        spot = edge_band_point(g, e, g.rng, depth=(4, 12)) if e else (m.w // 2, m.h // 2)
    place(g, p, spot[0], spot[1], 10)
    g.add_actor(p)
    sq = Squad(p.side, p.nation, "rifle", "stragglers")
    sq.members = [p]
    sq.leader = p
    sq.player_led = True
    sq.no_count = True
    sq.order = Order("follow", src="player")
    p.squad = sq
    g.squads.append(sq)
    g.command.organise(g)
    g.update_orders(force=True)
    g.player_fov()


def finish(g, over, state):
    """The flight (or the voyage) is over, one way or another."""
    from . import scenarios as SC
    ss = g.skysea
    p = g.player
    app = state.app
    play = state.play
    g.domain = "land"
    g.skysea = None
    if over == "dead" or not p.alive or p.body.dead:
        if p.alive:
            p.body.dead = True
        g.kill(p, None)
        app.pop()
        play.check_over()
        return
    st = g.strategic
    if isinstance(over, tuple) and over[0] == "landed":
        sec = st.at(*over[1], create=True)
        to_land(g, sec, airfield=True)
        g.msg("You climb down from the cockpit. The ground crew want to know how she flew.", "info")
    elif isinstance(over, tuple) and over[0] == "landed_chute":
        x, y = over[1], over[2]
        sec = st.at(int(math.floor(x / SEC)), int(math.floor(y / SEC)), create=True)
        frac = ((x % SEC) / SEC, (y % SEC) / SEC)
        to_land(g, sec, frac=frac)
        if sec.control != p.side:
            g.mission = dict(kind="evader", stage="evade", sid="evader", start=g.turn,
                             text="Evade capture. Get back to friendly lines - across the front.",
                             home=g.home_edge(p.side) or "S")
            g.noise = 60.0
            g.msg(f"You hit the ground hard in {sec.name}. Enemy country. Bury the chute.", "warn")
        else:
            g.msg(f"You come down in {sec.name}, among your own side. Someone runs over with a flask.", "good")
    elif over == "raft":
        adrift(g, ss)
    app.pop()
    play.recenter()
    play.cam_c = None
    play.check_over()


def adrift(g, ss):
    """Hours in a dinghy: rescue, capture, the shore - or the end."""
    from .pow import start_in_camp
    rng = g.rng
    p = g.player
    side = p.side
    st = g.strategic
    x, y = ss.raft if ss is not None and ss.raft else (0, 0)
    friends = ss is not None and any(s.alive and s.side == side for s in ss.ships)
    enemies = ss is not None and any(s.alive and s.side != side for s in ss.ships)
    for h in range(1, 121):
        g.advance_clock(3600)
        if friends and rng.random() < 0.18:
            coast = _nearest_coast(g, x, y, side) or _nearest_coast(g, x, y, None) or g.sector
            g.msg(f"After {h} hours a destroyer's whaler finds you. They put you ashore at {coast.name}.", "good")
            to_land(g, coast)
            return
        if enemies and rng.random() < 0.06:
            g.msg(f"After {h} hours an enemy ship stops alongside. Rough hands haul you aboard.", "warn")
            g.msg(start_in_camp(g), "warn")
            return
        if rng.random() < 0.025:
            coast = _nearest_coast(g, x, y, None)
            if coast is not None:
                g.msg(f"After {h} hours the current carries you onto a beach at {coast.name}.", "warn")
                to_land(g, coast)
                return
        if h == 36:
            g.msg("No water. Salt sores. The sun.", "hurt")
        if h > 60 and rng.random() < 0.03:
            p.body.dead = True
            p.body.cause = "exposure, adrift at sea"
            g.kill(p, None)
            return
    p.body.dead = True
    p.body.cause = "thirst, adrift at sea"
    g.kill(p, None)


def _nearest_coast(g, x, y, side):
    st = g.strategic
    cx, cy = int(math.floor(x / SEC)), int(math.floor(y / SEC))
    best = None
    for r in range(0, 10):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                c = st.at(cx + dx, cy + dy, create=True)
                if c is None or not c.playable or (side is not None and c.control != side):
                    continue
                if any(n.biome == "sea" for n in st.neighbors(c, create=True)):
                    return c
    return best
