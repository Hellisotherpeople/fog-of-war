"""The command screen.

Press C: your roster unfolds from your @ like a map case - every unit in your
chain of command, every unit you've taken under command, and any men nearby you
outrank.  Pick a unit (or a whole platoon) and give it an order; the order goes
by voice, hand signal, radio, relay or runner.  While the roster is open, your
units' last reported positions are marked on the ground in grease pencil.
"""
from __future__ import annotations

import math

from .ai import ROE_NAME
from .command import (ORDER_TEXT, SIGNAL_OK, contact_point, leader_name, squad_has_radio, status_word,
                      strength_text, unit_label)
from .constants import UI_DIM, UI_HI, UI_TEXT, cap
from .render import Popup, put

HEAD = (200, 180, 120)
CHAN_SHORT = {"direct": "here", "voice": "voice", "signal": "signal", "radio": "radio", "relay": "relay",
              "runner": "runner"}
COST = {"direct": 50, "voice": 60, "signal": 60, "radio": 200, "relay": 200, "runner": 120}
TARGETED = ("move", "attack", "assault", "flank", "suppress", "defend", "ambush_at")


def _state_color(sq, stale=False):
    if stale:
        return (140, 135, 120)
    st = status_word(sq)
    if st in ("routing",):
        return (255, 80, 70)
    if st in ("pinned down", "falling back"):
        return (240, 150, 70)
    if st in ("in contact", "assaulting", "suppressing", "charging"):
        return (240, 220, 110)
    return (160, 215, 150)


def _age(sec):
    if sec < 60:
        return f"{sec}s ago"
    return f"{sec // 60}m ago"


def command_units(game):
    """(your chain of command, other men you outrank and know about)."""
    p = game.player
    cmd = game.command
    chain = cmd.chain_squads(game)
    ids = {sq.id for sq in chain}
    others = []
    vr = cmd.voice_range(game)
    radio = cmd.player_radio(game)
    m = game.map
    for sq in game.squads:
        if sq.side != p.side or sq.gone or sq.id in ids or sq is p.squad:
            continue
        ok, _ = cmd.authority(game, sq)
        if not ok:
            continue
        pt = contact_point(sq)
        if pt is None:
            continue
        d = max(abs(pt[0] - p.x), abs(pt[1] - p.y))
        if d <= vr or m.visible[pt[0], pt[1]] or (radio and squad_has_radio(game, sq)):
            others.append((d, sq))
    others.sort(key=lambda e: e[0])
    return chain, [sq for _, sq in others[:10]]


def unit_row(game, sq, indent=0):
    cmd = game.command
    k = cmd.known_of(game, sq)
    stale = k is None or game.turn - k["turn"] > 15
    if k is None:
        state = "no word"
    elif stale:
        state = f"{k['state']} ({_age(game.turn - k['turn'])})"
    else:
        state = status_word(sq)
    ch = cmd.channel(game, sq)
    chan = CHAN_SHORT.get(ch["kind"], "?") if ch else "-"
    name = ("  " * indent + unit_label(sq))[:16]
    ld = leader_name(sq)[:14]
    mine = "*" if sq.order.src == "player" else " "
    return f"{name:<16} {ld:<14} {strength_text(sq):>6} {mine}{state[:19]:<19} {chan}", _state_color(sq, stale)


def _walk(f, depth=0):
    yield f, depth
    for c in f.children:
        yield from _walk(c, depth + 1)


def open_command(ps):
    g = ps.game
    cmd = g.command
    p = g.player
    chain, others = command_units(g)
    opts = []
    shown = set()
    ob = g.__dict__.get("oob")
    here_path = set()
    if cmd.billet is not None and ob is not None:
        base = cmd.bases.get(p.side)
        f0 = base
        while f0 is not None:
            here_path.add(id(f0))
            f0 = f0.parent
    if cmd.billet is not None:
        for f, depth in _walk(cmd.billet):
            live = f.live_squads()
            if not live and f.oob_fid is not None and ob is not None and ob.node(f.oob_fid) is not None:
                # a formation of yours somewhere else on the front: its commander and its strength
                par = f.parent
                if depth > 3 and not (par is not None and id(par) in here_path):
                    continue
                s = ob.strength(g, f.oob_fid)
                n = ob.node(f.oob_fid)
                where = ""
                if n.sector is not None and g.strategic.at(*n.sector) is not None:
                    where = f" at {g.strategic.at(*n.sector).name}"
                label = ("  " * depth + f"{f.name}{where} - {f.commander_label()}, {s['men']:,} men"
                         + (f", {s['tanks']} tanks" if s["tanks"] else ""))
                opts.append((label, ("oob", f.oob_fid), (170, 165, 140), True))
                continue
            if not live:
                continue
            here = [sq for sq in f.squads if not sq.gone and (sq.members or sq.vehicles)]
            if f is not cmd.billet or f.children or len(here) > 1:
                nm = f.name if f.oob_fid is not None and f.echelon not in ("platoon", "company") else f.short
                is_base = f is cmd.bases.get(p.side)
                tag = "  (this battlefield)" if is_base and ob is not None else ""
                size = f"{len(live)} unit{'s' if len(live) != 1 else ''}"
                if ob is not None and (f.oob_fid is not None or is_base) and f.echelon not in ("platoon", "company"):
                    fid = f.oob_fid
                    if fid is not None and ob.node(fid) is not None and not is_base:
                        s_ = ob.strength(g, fid)
                        size = f"{s_['men']:,} men" + (f", {s_['tanks']} tanks" if s_["tanks"] else "")
                    else:
                        from .operations import live_strength
                        s_ = live_strength(g, p.side)
                        size = f"{s_['men']:,} men here"
                label = "  " * depth + f"{nm} - {f.commander_label()}, {size}{tag}"
                opts.append((label, ("form", f.id), HEAD, True))
            for sq in here:
                row, col = unit_row(g, sq, depth + 1)
                opts.append((row, ("sq", sq.id), col, True))
                shown.add(sq.id)
    rest = [sq for sq in chain if sq.id not in shown]
    if rest:
        own = [sq for sq in rest if sq is cmd.billet_squad]
        att = [sq for sq in rest if sq is not cmd.billet_squad]
        for sq in own:
            row, col = unit_row(g, sq)
            opts.insert(0, (row, ("sq", sq.id), col, True))
        if att:
            opts.append(("Attached to you", None, HEAD, False))
            for sq in att:
                row, col = unit_row(g, sq, 1)
                opts.append((row, ("sq", sq.id), col, True))
    if others:
        opts.append(("Men here you outrank", None, HEAD, False))
        for sq in others:
            row, col = unit_row(g, sq, 1)
            opts.append((row, ("sq", sq.id), col, True))
    if not opts:
        opts.append(("Nobody here answers to you.", None, UI_DIM, False))
    vr = cmd.voice_range(g)
    lines = [(f"{p.rank_full} {p.name}" + (f" - {cmd.billet_title(g)}" if cmd.billet_title(g) else ""), UI_HI),
             (f"In this noise a shout carries about {int(vr * 2.2 / 5) * 5} yards. Radio: "
              + ("at hand." if cmd.player_radio(g) else "none."), UI_DIM),
             (f"{'unit':<16} {'leader':<14} {'men':>6}  {'last word':<19} reach", (120, 115, 100))]
    if cmd.pending:
        lines.insert(2, (f"{len(cmd.pending)} order{'s' if len(cmd.pending) != 1 else ''} on the way.", (200, 190, 150)))
    pop = Popup("Command", opts, ps._screen_anchor(), width=76, lines=lines,
                footer="Enter: give orders   * = your orders   Esc: close")
    ps.cmd_show = True
    ps.open_popup(pop, lambda v: _pick(ps, v), cancel=lambda: _close(ps))


def _close(ps):
    ps.cmd_show = False


def _find_formation(game, fid):
    for root in game.command.roots.values():
        for f in root.walk():
            if f.id == fid:
                return f
    return None


def _pick(ps, v):
    g = ps.game
    if v is None:
        return
    kind, ident = v
    if kind == "oob":
        # a formation elsewhere on the front: its orders go through the general staff
        from .opsui import OperationsState
        ops = g.ops
        os_ = OperationsState(ps.app, g, ps)
        ob = g.oob
        want = None
        for n in ob.chain(ident):
            if n.fid in ops.divs:
                want = n.fid
                break
        if want is None:
            want = next((n.fid for n in ob.walk(ident) if n.fid in ops.divs), None)
        divs = os_._divs()
        for i, (did, d) in enumerate(divs):
            if did == want:
                os_.sel = i
        ps.cmd_show = False
        ps.app.push(os_)
        return
    if kind == "sq":
        sq = next((s for s in g.squads if s.id == ident and not s.gone), None)
        if sq is None:
            return open_command(ps)
        return unit_menu(ps, [sq], sq.name)
    f = _find_formation(g, ident)
    if f is None:
        return open_command(ps)
    sqs = [sq for sq in f.live_squads() if not (sq is g.player.squad and sq.player_led)]
    if not sqs:
        g.msg("There's nobody left in it to order.", "info")
        return open_command(ps)
    unit_menu(ps, sqs, f.title() if f.echelon == "platoon" else f.name, formation=f)


def unit_menu(ps, squads, title, formation=None):
    g = ps.game
    cmd = g.command
    p = g.player
    single = len(squads) == 1
    sq0 = squads[0]
    chans = {sq.id: cmd.channel(g, sq) for sq in squads}
    reach = [sq for sq in squads if chans[sq.id] is not None]
    auth = [sq for sq in squads if cmd.authority(g, sq)[0]]
    lines = []
    if single:
        ok, why = cmd.authority(g, sq0)
        o = sq0.order
        lines.append((f"{leader_name(sq0)} - {strength_text(sq0)} - {status_word(sq0)}", UI_TEXT))
        lines.append((f"Orders: {o.describe(g)} ({'yours' if o.src == 'player' else 'from above'}), "
                      f"{ROE_NAME.get(o.roe, o.roe)}", UI_DIM))
        ch = chans[sq0.id]
        if not ok:
            lines.append((why, (240, 150, 90)))
        elif ch is None:
            lines.append(("No way to reach them: out of earshot, no radio, nobody to send.", (240, 150, 90)))
        else:
            lines.append((f"Reach: {ch['note']} - about {max(1, ch['delay'])} s", (170, 200, 150)))
    else:
        lines.append((f"{len(squads)} units. {len(reach)} can be reached now.", UI_TEXT))
        byk = {}
        for sq in reach:
            k = chans[sq.id]["kind"]
            byk[k] = byk.get(k, 0) + 1
        if byk:
            lines.append((", ".join(f"{n} by {k}" for k, n in byk.items()), UI_DIM))

    def can(kind):
        if not auth:
            return False
        for sq in auth:
            ch = chans[sq.id]
            if ch is None:
                continue
            if ch["kind"] == "signal" and kind not in SIGNAL_OK:
                continue
            return True
        return False

    has_veh = any(v.active and v.vt.seats > 0 for sq in squads for v in sq.vehicles)
    mounted = any(v.active and v.passengers for sq in squads for v in sq.vehicles)
    near_transport = any(v.side == p.side and v.active and v.vt.seats > 0 and len(v.passengers) < v.vt.seats
                         for v in g.vehicles)
    opts = [("Move to...", "move", None, can("move")),
            ("Attack...", "attack", (240, 170, 90), can("attack")),
            ("Assault - go in now!", "assault", (250, 140, 80), can("assault")),
            ("Flank...", "flank", None, can("flank")),
            ("Suppress...", "suppress", None, can("suppress")),
            ("Defend...", "defend", None, can("defend")),
            ("Hold where you are", "hold", None, can("hold")),
            ("Dig in", "dig", None, can("dig")),
            ("Ambush here - hold fire until they're close", "ambush", None, can("ambush")),
            ("Ambush at...", "ambush_at", None, can("ambush")),
            ("Come to me", "come", None, can("come")),
            ("Regroup on your leader", "regroup", None, can("regroup")),
            ("Fall back!", "retreat", None, can("retreat"))]
    if mounted:
        opts.append(("Dismount", "dismount", None, can("dismount")))
    elif has_veh or near_transport:
        opts.append(("Mount up", "mount", None, can("mount")))
    from .command import ammo_points
    if ammo_points(g, p.side):
        opts.append(("Resupply at the nearest ammunition dump", "resupply", None, can("resupply")))
    opts.append(("Tasks... (scavenge, the wounded, prisoners, a hand for the tanks)", "tasks", (220, 200, 140),
                 can("task")))
    roe = sq0.order.roe if single else None
    for r, label in (("free", "Fire at will"), ("return", "Return fire only"), ("hold", "Hold your fire")):
        mark = " (now)" if roe == r else ""
        opts.append((f"{label}{mark}", f"roe_{r}", (180, 200, 230), can("roe")))
    opts.append(("Report!", "report", None, can("report")))
    if any(sq.order.src == "player" for sq in squads) or any(sq.id in cmd.attached for sq in squads):
        opts.append(("Carry on - use your own judgement", "release", UI_DIM, can("release")))
    if any(not cmd.in_chain(g, sq) for sq in auth):
        opts.append(("Take them under your command", "attach", HEAD, can("attach")))
    pt = contact_point(sq0)
    anchor = ps._screen_anchor()
    if pt is not None and ps.cam.on_screen(*pt):
        anchor = ps.cam.to_text(*pt)
    pop = Popup(title[:60], opts, anchor, lines=lines, width=66, footer="Esc: back to the roster")
    ps.cmd_show = True
    label = (formation.short if formation is not None else unit_label(sq0)) if not single or formation else None
    ps.open_popup(pop, lambda v: _order(ps, squads, v, label), cancel=lambda: open_command(ps))


# ====================================================================== where: proposed targets
TARGET_TITLE = {"move": "Advance to where?", "attack": "Attack what?", "assault": "Assault what?",
                "flank": "Flank what?", "suppress": "Suppress what?", "defend": "Defend where?",
                "ambush": "Ambush where?"}
KIND_WORD = {"hmg": "heavy machine gun", "mg": "machine gun", "atgun": "anti-tank gun", "tank": "tank",
             "vehicle": "vehicle", "sniper": "sniper", "mortar": "mortar", "officer": "officer",
             "infantry": "enemy rifleman", "soldier": "enemy soldier"}


def proposals(game, kind, squads, origin) -> list:
    """Where an order could go, best first: the next objective, the enemy positions your side knows about,
    the other objectives.  [(label, (x, y), colour)]."""
    from .senses import direction_word
    p = game.player
    side = p.side
    m = game.map
    ox, oy = origin

    def dist(x, y):
        return math.hypot(x - ox, y - oy)

    def where(x, y):
        d = dist(x, y)
        return "right here" if d < 4 else f"{direction_word(x - ox, y - oy)}, about {int(round(d * 2.2 / 10.0) * 10)} yards"

    def state(o):
        return "ours" if o.owner == side else "no one's" if o.owner is None else "enemy-held"
    objs = list(m.objectives)
    theirs = sorted([o for o in objs if o.owner != side], key=lambda o: dist(o.x, o.y))
    ours = sorted([o for o in objs if o.owner == side], key=lambda o: dist(o.x, o.y))
    # the next objective: the one higher command has given this unit, or the nearest that isn't ours
    nxt = None
    sq0 = squads[0] if squads else None
    oi = getattr(getattr(sq0, "order", None), "obj", None)
    if oi is not None and 0 <= oi < len(objs) and objs[oi].owner != side:
        nxt = objs[oi]
    elif theirs:
        nxt = theirs[0]
    brain = game.brains[side]
    contacts = [c for c in brain.live_contacts(180, False) if c.kind != "sound"]
    strong = sorted([c for c in contacts if c.kind in ("hmg", "mg", "atgun", "tank", "sniper", "mortar")],
                    key=lambda c: dist(c.x, c.y))
    others = sorted([c for c in contacts if c not in strong], key=lambda c: dist(c.x, c.y))
    clusters = brain.clusters(radius=6, min_size=2, max_age=180)
    out = []

    def add(label, x, y, col=None):
        if not m.in_bounds(x, y) or any(abs(x - q[1][0]) + abs(y - q[1][1]) < 4 for q in out):
            return
        out.append((label[:1].upper() + label[1:], (int(x), int(y)), col))

    def seen(c):
        a = game.turn - c.turn
        return "just now" if a < 20 else f"{a // 60 or 1} min ago" if a < 3600 else "a while ago"
    hot, cool, obj_col = (250, 170, 110), (230, 210, 150), (180, 220, 160)
    if kind in ("move", "attack", "assault", "flank", "ambush") and nxt is not None:
        add(f"{nxt.name}: the next objective ({state(nxt)}), {where(nxt.x, nxt.y)}", nxt.x, nxt.y, obj_col)
    if kind in ("flank", "attack", "assault", "suppress"):
        for c in strong[:5]:
            add(f"The {KIND_WORD.get(c.kind, c.kind)}, {where(c.x, c.y)} (seen {seen(c)})", c.x, c.y, hot)
        for _w, cx, cy, grp in clusters[:3]:
            add(f"A group of about {len(grp)} enemy, {where(cx, cy)}", cx, cy, hot)
        for c in others[:2]:
            add(f"An {KIND_WORD.get(c.kind, 'enemy soldier')}, {where(c.x, c.y)} (seen {seen(c)})", c.x, c.y, cool)
    if kind == "suppress" and nxt is not None:
        add(f"{nxt.name}: the next objective ({state(nxt)}), {where(nxt.x, nxt.y)}", nxt.x, nxt.y, obj_col)
    if kind in ("defend", "move"):
        for o in ours[:4]:
            add(f"{o.name} ({state(o)}), {where(o.x, o.y)}", o.x, o.y, obj_col)
    for o in theirs + ours:
        add(f"{o.name} ({state(o)}), {where(o.x, o.y)}", o.x, o.y, None)
    if kind == "defend" and sq0 is not None:
        a = contact_point(sq0)
        if a is not None:
            add("Where they are now", a[0], a[1], None)
    return out[:10]


def choose_target(ps, kind, squads, cb, start, label=None, cmd=False):
    """Where the order goes: a short list of proposals (Enter takes the first - the next objective), or pick a
    spot on the map yourself (and Tab there steps through the same proposals)."""
    g = ps.game
    props = proposals(g, kind, squads, start)
    mode_data = {"cb": cb, "cmd": cmd, "label": label or ORDER_TEXT.get(kind, kind),
                 "props": [q[1] for q in props]}
    if not props:
        ps.enter_mode("order_target", start, mode_data)
        return
    opts = [(q[0], q[1], q[2], True) for q in props] + [("Pick a spot on the map...", "pick", UI_DIM, True)]

    def chosen(v):
        if v == "pick":
            mode_data["prop_i"] = 0                  # the cursor starts on the first; Tab goes on to the next
            ps.enter_mode("order_target", props[0][1], mode_data)
        else:
            cb(v)
    ps.open_popup(Popup(TARGET_TITLE.get(kind, "Where?"), opts, ps._screen_anchor(), width=74,
                        lines=[("Enter takes the first. Or pick a spot yourself (Tab there steps through these).",
                                UI_DIM)]),
                  chosen, cancel=(lambda: open_command(ps)) if cmd else None)


def _order(ps, squads, what, label=None):
    g = ps.game
    if what == "tasks":
        from . import tasks as TK
        pt = contact_point(squads[0]) or (g.player.x, g.player.y)
        opts = TK.menu_options(g, squads[0], pt)
        ps.open_popup(Popup("Tasks", opts, ps._screen_anchor(), width=78,
                            lines=[("Sent the way any order goes: voice, signal, radio, relay or runner.", UI_DIM)]),
                      lambda k: _send(ps, squads, "task_stop" if k == "stop" else f"task_{k}", None, label=label),
                      cancel=lambda: open_command(ps))
        return
    if what in TARGETED:
        p = g.player
        pt = contact_point(squads[0]) if len(squads) == 1 else None
        start = pt if pt is not None else (p.x, p.y)
        kind = "ambush" if what == "ambush_at" else what
        ps.cmd_show = True
        choose_target(ps, kind, squads, lambda pos: _send(ps, squads, kind, pos, label=label), start,
                      ORDER_TEXT.get(kind, kind), cmd=True)
        return
    roe = None
    kind = what
    if what.startswith("roe_"):
        kind = "roe"
        roe = what[4:]
    _send(ps, squads, kind, None, roe, label)


def _send(ps, squads, kind, pos, roe=None, label=None):
    g = ps.game
    cmd = g.command
    sent, fails = cmd.issue(g, squads, kind, pos, roe=roe, label=label)
    ps.cmd_show = False
    for sq, why in fails[:3]:
        g.msg(f"{cap(unit_label(sq))}: {why}", "warn")
    if len(fails) > 3:
        g.msg(f"...and {len(fails) - 3} more units couldn't be reached.", "warn")
    if not sent:
        return
    kinds = [cmd.channel(g, sq, kind) for sq in sent]
    cost = max((COST.get(c["kind"], 100) for c in kinds if c), default=60)
    ps.act(cost)


# ====================================================================== grease pencil on the map

def draw_markers(con, ps):
    """Where your units last reported, and where you've sent them."""
    g = ps.game
    cmd = g.command
    cam = ps.cam
    p = g.player
    chain, others = command_units(g)
    t = g.turn
    for sq in chain + others:
        k = cmd.known_of(g, sq)
        if k is None:
            continue
        x, y = k["x"], k["y"]
        stale = t - k["turn"] > 15
        col = _state_color(sq, stale) if sq in chain else (150, 170, 200)
        o = sq.order
        tgt = o.target if o.src == "player" and o.target is not None and o.kind not in ("follow",) else None
        if tgt is not None and sq in chain:
            _dotted(con, cam, x, y, tgt[0], tgt[1], (200, 190, 120))
            if cam.on_screen(*tgt):
                tx, ty = cam.to_text(*tgt)
                sym = ORDER_SYM.get(o.kind, "+")
                put(con, tx, ty, sym, (240, 220, 120), (40, 35, 20))
        if not cam.on_screen(x, y):
            continue
        tx, ty = cam.to_text(x, y)
        label = unit_label(sq).replace(" Sqd", "").replace(" Sec", "")[:12]
        if stale:
            label += "?"
        bx = tx + 1
        if bx + len(label) + 2 >= int(cam.vw * cam.tx):
            bx = tx - len(label) - 2
        bx = max(0, int(bx))
        if 0 <= ty < con.height:
            con.print(bx, ty, f"[{label}]", fg=(20, 20, 20), bg=col)
    for job in cmd.pending:
        sq = next((s for s in g.squads if s.id == job["sq"]), None)
        if sq is None:
            continue
        k = cmd.known_of(g, sq)
        if k is not None and cam.on_screen(k["x"], k["y"]):
            tx, ty = cam.to_text(k["x"], k["y"])
            put(con, tx, ty - 1, "»" if job["channel"] == "runner" else "~", (250, 240, 200))


ORDER_SYM = {"attack": "X", "assault": "X", "suppress": "*", "flank": ">", "defend": "O", "ambush": "!",
             "move": "+", "hold": "o", "dig": "o", "resupply": "$"}


def draw_recent_orders(con, ps, window=120):
    """Orders you've given lately stay pencilled on the map: from where the unit was to where it's going."""
    g = ps.game
    cmd = g.command
    cam = ps.cam
    t = g.turn
    for sq in cmd.chain_squads(g):
        o = sq.order
        if sq.player_led or o.src != "player" or o.target is None or t - o.issued > window:
            continue
        k = cmd.known_of(g, sq)
        if k is None:
            continue
        _dotted(con, cam, k["x"], k["y"], o.target[0], o.target[1], (200, 185, 110))
        if cam.on_screen(*o.target):
            tx, ty = cam.to_text(*o.target)
            put(con, tx, ty, ORDER_SYM.get(o.kind, "+"), (240, 220, 120), (40, 35, 20))
    # still on their way
    for job in cmd.pending:
        o = job.get("order")
        if o is None or o.target is None:
            continue
        sq = next((s for s in g.squads if s.id == job["sq"]), None)
        k = cmd.known_of(g, sq) if sq is not None else None
        if k is None:
            continue
        _dotted(con, cam, k["x"], k["y"], o.target[0], o.target[1], (150, 145, 120))


def _dotted(con, cam, x0, y0, x1, y1, col):
    d = max(abs(x1 - x0), abs(y1 - y0))
    if d < 2:
        return
    for i in range(1, d, 2):
        x = x0 + (x1 - x0) * i / d
        y = y0 + (y1 - y0) * i / d
        xi, yi = int(round(x)), int(round(y))
        if cam.on_screen(xi, yi):
            tx, ty = cam.to_text(xi, yi)
            put(con, tx, ty, "·", col)
