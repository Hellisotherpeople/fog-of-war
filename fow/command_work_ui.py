"""Appointments, intent and engineer tasks in the existing command popup."""
import textwrap
from .constants import UI_DIM, UI_HI, UI_TEXT
from .render import Popup


def _menu(ps, title, options, callback, lines=()):
    wrapped = [(line, color) for text, color in lines for line in (textwrap.wrap(text, 73) or [""])]
    ps.open_popup(Popup(title, options, ps._screen_anchor(), width=78, lines=wrapped[:25]), callback)


def send(ps, squads, kind, payload):
    from .cmdui import _send
    _send(ps, squads, kind, payload)


def guidance(ps, squads):
    from .intent import MISSIONS, FREEDOM, profile
    doc = profile(squads[0].nation)

    def mission_selected(mission):
        def freedom_selected(freedom):
            def risk_selected(risk):
                from .cmdui import choose_target
                choose_target(ps, "defend", squads, lambda pos: send(ps, squads, "mission",
                    dict(mission=mission, freedom=freedom, risk=risk, target=pos)), ps.game.player.pos,
                    label="Mission objective / centre of assigned area", cmd=True)
            _menu(ps, "Losses and commitment", [
                ("Preserve strength: reorganize at 15% losses", "cautious", None, True),
                ("Normal commitment: reorganize at 30% losses", "normal", None, True),
                ("Press the mission: reorganize at 50% losses", "press", None, True)], risk_selected)
        _menu(ps, "Freedom of action", [(f"{label} ({radius * 2} yards)" +
                 (" - normal doctrine" if key == doc[2] else ""), key, None, True)
                for key, (radius, label) in FREEDOM.items()], freedom_selected,
              [("These are mission boundaries; broken men can still run or refuse.", UI_DIM)])
    _menu(ps, "Standing mission", [(name, key, None, True) for key, name in MISSIONS.items()], mission_selected,
          [(f"Doctrine: {doc[0]}", UI_HI),
           ("Leaders choose local action, replenish ammunition and consolidate on arrival.", UI_DIM),
           ("The mission travels by the same means as an ordinary order.", UI_DIM)])


def appointment(ps, squads, formation=None):
    from .intent import appointable
    g = ps.game
    candidates = [a for a in g.actors if appointable(g, a) and g.command.authority(g, a.squad)[0]
                  and (g.can_see(a.x, a.y) or g.command.known_of(g, a.squad))]
    candidates.sort(key=lambda a: (-a.rank, -a.skills.get("leadership", 0)))
    opts = [(f"{a.full_name} - {a.role_name}, {a.squad.short or a.squad.name}", a.id, None, True)
            for a in candidates]
    if not opts:
        opts = [("No available subordinate officer or NCO", None, UI_DIM, False)]
    def chosen(aid):
        if aid is not None:
            send(ps, [squads[0]], "appointment", dict(actor=aid, formation=formation.id if formation else None))
    _menu(ps, "Appoint an acting commander", opts, chosen,
          [("You must outrank both the appointee and the commander being replaced.", UI_DIM),
           ("The appointment changes the billet; it does not confer a new rank.", UI_DIM)])


def reassign(ps, squads):
    from .intent import formations
    g = ps.game
    opts = [(f"{f.title()} - {f.commander_label()}", f.id, None, True) for f in formations(g)
            if f.side == g.player.side and f.commander_grade() < g.player.rank and f.live_squads()
            and all(g.command.authority(g, s)[0] for s in f.live_squads())
            and f.echelon in ("platoon", "company", "battalion")]
    _menu(ps, "Place under another command", opts or [("No eligible command", None, UI_DIM, False)],
          lambda fid: send(ps, squads, "reassign", dict(formation=fid)) if fid is not None else None)


def construction(ps, squads):
    from .fieldworks import WORKS, engineer, tools
    opts = []
    for k, (name, tile, work, materials, skilled, install) in WORKS.items():
        fit = any(a.active and not a.downed and tools(a) and (not skilled or engineer(a))
                  for sq in squads for a in sq.members)
        opts.append((f"{name} - {work / 3600:g} man-hours, {materials} crates", k, None, fit))
    def chosen(kind):
        from .cmdui import choose_target
        workers = next(sq for sq in squads if any(a.active and not a.downed and tools(a) and
                       (not WORKS[kind][4] or engineer(a)) for a in sq.members))
        choose_target(ps, "defend", squads, lambda pos: send(ps, [workers], "build", dict(kind=kind, point=pos)),
                      ps.game.player.pos, label="Mark the construction site", cmd=True)
    _menu(ps, "Engineer works", opts, chosen,
          [("One selected unit forms the work party. Engineers collect and carry the stores.", UI_DIM),
           ("Combat interrupts work. Completion creates terrain and functioning installations.", UI_DIM)])


def staff(ps):
    from .fieldworks import projects, WORKS
    from .sustain import stores
    from .recognition import status
    from .intelligence import headquarters
    g = ps.game
    lines = [(status(g), UI_DIM)]
    from .dispatches import status as dispatch_status
    lines.append((dispatch_status(g), UI_TEXT))
    if headquarters(g):
        lines += [("Local stores: " + ", ".join(f"{k} {v:.0f}" for k, v in stores(g.sector, g.player.side).items()), UI_TEXT)]
        hf = g.sector.__dict__.get("homefront", {})
        if hf:
            lines.append((f"Civilian ration provision: {hf.get('relief', 1):.0%}; "
                          f"shortage: {hf.get('shortage_hours', 0):.1f} hours. "
                          "Food, workforce and power determine workshop output.", UI_DIM))
    for p in projects(g):
        if p["side"] == g.player.side:
            spec = WORKS[p["kind"]]
            lines.append((f"{spec[0]} at {p['point']}: {p['status']}, {min(100, p['work'] / spec[2] * 100):.0f}%", UI_TEXT))
    if len(lines) == 1:
        lines.append(("No work parties assigned here. Select an engineer unit to start works.", UI_DIM))
    opts = [("HQ debrief, decorations and career / support requests (Q)", "debrief", None, True),
            ("Request ammunition, spares and engineer stores", "truck", None, g.command.player_radio(g) or bool(headquarters(g))),
            ("Orders and workshop destinations (T)", "orders", None, True)]
    def pick(k):
        if k == "debrief":
            from .debrief import menu
            menu(ps)
        elif k == "orders":
            ps.cmd_orders_book()
        elif k == "truck":
            from .maintenance import call_truck
            answer = call_truck(g, g.player.side, g.player.pos, why="supply request")
            if answer:
                g.msg(answer, "info")
            ps.act(300)
    _menu(ps, "Staff, supply and engineer works", opts, pick, lines)
