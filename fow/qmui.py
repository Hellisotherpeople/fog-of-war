"""The quartermaster's counter and the intelligence officer's tent.

Menus pop out from the man you're talking to.  Credit is the quartermaster's ledger:
what the army owes you for what you've brought in.  Cigarettes are the other currency.
"""
from __future__ import annotations

from . import logistics as L
from .constants import UI_DIM, UI_HI, UI_TEXT
from .render import Popup

CATS = [("Weapons", ("gun",)), ("Ammunition", ("mag", "clip", "ammo")), ("Grenades and explosives", ("grenade", "explosive")),
        ("Medical", ("medical",)), ("Equipment", ("tool", "armor", "container", "melee"))]


def credit(game) -> int:
    return int(getattr(game.command, "credit", 0))


def add_credit(game, n):
    game.command.credit = getattr(game.command, "credit", 0) + n


def _anchor(ps, npc):
    if ps.cam.on_screen(npc.x, npc.y):
        return ps.cam.to_text(npc.x, npc.y)
    return ps._screen_anchor()


def open_quartermaster(ps, qm):
    g = ps.game
    p = g.player
    cigs = sum(i.count for i in p.inv if i.t.tool == "cigarettes")
    stock, mult, supply = L.stock(g, p.side)
    supply_word = "well stocked" if supply >= 0.7 else "short of most things" if supply >= 0.35 else \
        "nearly empty - we're cut off"
    lines = [(f"{qm.rank_short} {qm.last_name}, quartermaster. The depot is {supply_word}.", UI_TEXT),
             (f"Your credit: {credit(g)}   Cigarettes: {cigs} pack{'s' if cigs != 1 else ''}", (220, 200, 140))]
    from .sustain import stores
    lines.append(("Stores: " + ", ".join(f"{k} {int(v)}" for k, v in stores(g.sector, p.side).items()), UI_DIM))
    opts = [("Turn in what I'm carrying...", "turnin", None, True),
            ("Draw equipment...", "draw", None, True)]
    if cigs:
        opts.append((f"Pay in cigarettes ({L.CIG_CREDIT} credit a pack)", "cigs", None, True))
    if any(i.tid in L.DOCS for i in p.inv):
        opts.append(("Hand over enemy papers (he'll pass them to intelligence)", "papers", None, True))
    ps.open_popup(Popup("Quartermaster", opts, _anchor(ps, qm), lines=lines, width=64),
                  lambda v: _qm_choice(ps, qm, v))


def _qm_choice(ps, qm, what):
    if what == "turnin":
        return _turn_in_menu(ps, qm)
    if what == "draw":
        return _draw_menu(ps, qm)
    if what == "cigs":
        g = ps.game
        p = g.player
        n = 0
        for it in [i for i in p.inv if i.t.tool == "cigarettes"]:
            n += it.count
            p.remove_item(it)
        add_credit(g, n * L.CIG_CREDIT)
        g.msg(f"{qm.last_name} pockets {n} pack{'s' if n != 1 else ''} without a word and writes you up "
              f"{n * L.CIG_CREDIT} credit.", "info")
        ps.act(60)
        return open_quartermaster(ps, qm)
    if what == "papers":
        return hand_over_papers(ps, qm, via_qm=True)


def _turn_in_menu(ps, qm):
    g = ps.game
    p = g.player
    opts = []
    for it in p.inv:
        if it is p.weapon or it.tid in L.DOCS or it.tid in ("orders", "dogtags", "dispatches"):
            continue
        if it.t.kind in ("corpse",) or any(it is p.invent.slots.get(s) for s in ("rig", "pack", "head", "body")):
            continue
        v = L.value(it, p.nation)
        if v <= 0:
            continue
        tag = " (souvenir)" if L.souvenir(it, p.nation) else ""
        opts.append((f"{it.name}{tag} - {v} credit", it, (220, 200, 140) if tag else None, True))
    if not opts:
        g.msg("You've nothing he's interested in.", "info")
        return open_quartermaster(ps, qm)
    opts.sort(key=lambda o: -L.value(o[1], p.nation))
    lines = [("Captured kit goes to salvage and intelligence. The rear echelon pays well for souvenirs.", UI_DIM)]
    ps.open_popup(Popup("Turn in", opts[:40], _anchor(ps, qm), lines=lines, width=64),
                  lambda it: _turn_in(ps, qm, it), cancel=lambda: open_quartermaster(ps, qm))


def _turn_in(ps, qm, it):
    g = ps.game
    p = g.player
    v = L.value(it, p.nation)
    p.remove_item(it)
    add_credit(g, v)
    if L.souvenir(it, p.nation):
        g.msg(f"'A real {it.t.name}? Some supply clerk'll give his right arm for that.' +{v} credit.", "good")
    else:
        g.msg(f"You hand over the {it.name}. +{v} credit.", "info")
    ps.act(40)
    _turn_in_menu(ps, qm)


def _draw_menu(ps, qm):
    g = ps.game
    opts = [(name, kinds, None, True) for name, kinds in CATS]
    ps.open_popup(Popup(f"Draw (credit {credit(g)})", opts, _anchor(ps, qm)),
                  lambda kinds: _draw_list(ps, qm, kinds), cancel=lambda: open_quartermaster(ps, qm))


def _draw_list(ps, qm, kinds):
    g = ps.game
    p = g.player
    stock, mult, supply = L.stock(g, p.side)
    opts = []
    my_cals = {i.t.cal for i in p.inv if i.t.kind == "gun" and i.t.cal}
    for t in stock:
        if t.kind not in kinds:
            continue
        if t.kind in ("mag", "clip", "ammo") and t.cal not in my_cals:
            continue                    # only what fits your guns
        ok, why = L.rank_ok(p, t)
        pr = L.price(t, mult)
        label = f"{t.name} - {pr}" + ("" if ok else f"   ({why})")
        opts.append((label, t, None if ok and pr <= credit(g) else (120, 115, 100), ok and pr <= credit(g)))
    if not opts:
        g.msg("'Nothing of that on the shelves for you.'", "info")
        return _draw_menu(ps, qm)
    opts.sort(key=lambda o: (not o[3], o[0]))
    lines = [(f"Credit {credit(g)}. Prices {'as marked' if mult <= 1 else 'steep - supplies are short'}.", UI_DIM)]
    ps.open_popup(Popup("Draw", opts[:48], _anchor(ps, qm), lines=lines, width=66),
                  lambda t: _draw(ps, qm, t, kinds), cancel=lambda: _draw_menu(ps, qm))


def _draw(ps, qm, t, kinds):
    from .entities import Item
    g = ps.game
    p = g.player
    stock, mult, supply = L.stock(g, p.side)
    pr = L.price(t, mult)
    if t not in stock:
        g.msg("'None left in store. Wait for the next delivery.'", "info")
        return _draw_list(ps, qm, kinds)
    if pr > credit(g):
        g.msg("'Come back when you've something to trade.'", "info")
        return _draw_list(ps, qm, kinds)
    n = 1
    if t.kind == "ammo":
        n = 30
    elif t.kind == "medical" and t.med == "bandage":
        n = 2
    it = Item(t.id, n)
    if p.add_item(it) is None:
        g.msg("You've no room to carry it.", "warn")
        return _draw_list(ps, qm, kinds)
    add_credit(g, -pr)
    from .sustain import take, category
    take(g.sector, p.side, category(t), 1)
    g.msg(f"You sign for a {it.name}. (-{pr} credit)", "info")
    ps.act(60)
    _draw_list(ps, qm, kinds)


def hand_over_papers(ps, officer, via_qm=False):
    """Intelligence reads what the enemy dead carried.  The more senior the man, the more it's worth."""
    g = ps.game
    p = g.player
    from .intelligence import distance
    from .senses import los_clear
    if not officer.active or officer.downed or officer.side != p.side or officer.role not in ('intel', 'quartermaster') or \
            distance(p.pos, officer.pos) > 3 or not los_clear(g, *p.pos, *officer.pos):
        g.msg('You need a living friendly intelligence officer or quartermaster within speaking distance.', 'info')
        return
    from .contacts import documents
    docs = documents(g)
    if not docs:
        g.msg("'Bring me papers off their officers. Maps, orders, anything with writing on it.'", "info")
        return
    total_c = 0
    total_m = 0.0
    for it in sorted(docs, key=lambda i: -L.DOCS[i.tid][0]):
        c, mrt, info = L.turn_in_papers(g, p, it)
        if via_qm:
            c = int(c * 0.7)
        p.remove_item(it)
        total_c += c
        total_m += mrt
        what = "; ".join(info) if info else "tells us little"
        g.msg(f"The {it.name} {what}.", "radio" if L.DOCS[it.tid][0] >= 3 else "info")
    add_credit(g, total_c)
    g.command.merit += total_m
    from .recognition import state
    ledger = state(g)
    ledger['credited'] += total_m  # physical papers handed to the receiving officer are corroboration
    ledger.setdefault('reviewed', {})['intelligence'] = ledger.get('reviewed', {}).get('intelligence', 0) + len(docs)
    g.duty.rep += min(10, total_m * 1.5)
    g.msg(f"{officer.rank_short} {officer.last_name}: 'Good work.' (+{total_c} credit)", "good")
    from .contacts import entry
    entry(g)
    g.update_orders(force=True)
    ps.act(120)


def open_intel(ps, officer):
    g = ps.game
    p = g.player
    from .contacts import documents
    docs = documents(g)
    lines = [(f"{officer.rank_short} {officer.last_name}, intelligence.", UI_TEXT)]
    opts = [(f"Hand over {len(docs)} lot{'s' if len(docs) != 1 else ''} of enemy papers", "papers", None, bool(docs)),
            ("Ask what's known of the enemy", "brief", None, True),
            ("Counterintelligence reports and security patrols", "security", None, True)]
    def choose(v):
        if v == "papers":
            hand_over_papers(ps, officer)
        elif v == "brief":
            _brief(ps, officer)
        elif v == "security":
            from .counterintel import open_log
            open_log(ps)
    ps.open_popup(Popup("Intelligence", opts, _anchor(ps, officer), lines=lines, width=60),
                  choose)


def _brief(ps, officer):
    g = ps.game
    p = g.player
    brain = g.brains[p.side]
    n = len(brain.live_contacts(120, False))
    kinds = {}
    for c in brain.live_contacts(120, False):
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    desc = ", ".join(f"{v} {k}" for k, v in kinds.items()) or "nothing firm"
    g.msg(f"{officer.last_name}: 'We know of {n} enemy positions here: {desc}. Bring me their papers and I'll tell "
          f"you more.'", "radio")
    ps.act(60)
