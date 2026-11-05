"""Battle drills: the vocabulary an army, a unit and a leader actually have.

An order is not a menu item that everyone gets.  What a section can be told depends on whose army
taught it, what it was trained for, and how good the man giving it is.  A German sergeant with a
trained eye can name a Schwerpunkt; a Soviet lieutenant can mask a position with dummies; a British
corporal is taught to bite and hold.  A replacement private with an untrained voice gets "follow me"
and "watch there".

None of it is magic.  A drill only changes weights the simulation already uses - how much cover the
men seek, how closely they keep together, where the leader puts his fire - and it keeps the real
costs: a Schwerpunkt leaves the flanks thin, infiltration is slow through the wrong ground, maskirovka
takes men and time, and a fire ambush gives away its position the moment it speaks.

The drills also carry the side's language.  What is said is in the phrases table, keyed by nation.
"""
from __future__ import annotations

from .data.ranks import CORPORAL, SERGEANT, STAFF_SGT, COALITION

# grade, leadership skill, and the ground the drill needs.  These are teaching standards, not the
# rank table: a good corporal with a section that knows him has more to offer than a fresh one.
DRILLS = {
    # ------------------------------------------------------------------ every army
    "follow_me": dict(
        label="Follow me", verb="Follow me", nation=None, grade=0, lead=0.0, kind="follow",
        blurb="Keep on my heels, whatever the ground. The simplest order there is.",
        mods=dict(spread=0.5), phrase="follow_me", target=False, contrast=False),
    "cover_me": dict(
        label="Cover me while I move", verb="Cover me", nation=None, grade=0, lead=2.0, kind="hold",
        blurb="Hold and put fire on what the section knows. You move; they watch you cross.",
        mods=dict(watch=True, cover_me=True), phrase="cover_me", target=False),
    "watch": dict(
        label="Watch that ground", verb="Watch", nation=None, grade=0, lead=2.0, kind="hold",
        blurb="Hold here, eyes on that ground, hold fire. Call what you see.",
        mods=dict(watch=True, roe="hold"), phrase="o_watch", target=True, radius=14),
    "consolidate": dict(
        label="Consolidate", verb="Consolidate", nation=None, grade=0, lead=3.0, kind="hold",
        blurb="Stop. Reorganise, redistribute ammunition, dress wounds, and get down.",
        mods=dict(consolidate=True, dig_on_arrival=True), phrase="o_consolidate", target=False),
    "probe": dict(
        label="Probe the position", verb="Probe", nation=None, grade=0, lead=4.0, kind="attack",
        blurb="A small party tests it. They go in far enough to draw fire, not to take it.",
        mods=dict(probe=True), phrase="o_probe", target=True, radius=6),
    "break_contact": dict(
        label="Break contact", verb="Break contact", nation=None, grade=1, lead=3.5, kind="retreat",
        blurb="Come away by bounds, smoke between you and him, and rally behind cover.",
        mods=dict(bounds=True, smoke=True), phrase="o_break", target=False),
    # ------------------------------------------------------------------ German
    "auftragstaktik": dict(
        label="Auftragstaktik: mission and ground", verb="Auftrag", nation=("germany",), grade=0, lead=5.0,
        kind="move", blurb="Give the objective and the area; the leader chooses the way. Loose rein, own judgement.",
        mods=dict(initiative=True, spread=1.6), phrase="o_auftrag", target=True, radius=16),
    "feuerueberfall": dict(
        label="Feuerüberfall: fire ambush", verb="Feuerüberfall", nation=("germany",), grade=0, lead=4.5,
        kind="ambush", blurb="All weapons on one kill zone. Hold everything; one volley, then break.",
        mods=dict(volley=True, fire=1.3), phrase="o_feuerueberfall", target=True, radius=10),
    "schwerpunkt": dict(
        label="Schwerpunkt: point of main effort", verb="Schwerpunkt", nation=("germany",), grade=2, lead=6.0,
        kind="attack", blurb="Name the decisive point. Every gun bends toward it; the flanks go thin.",
        mods=dict(schwerpunkt=True, fire=1.2, spread=0.8, exposure=0.85, morale=3.0),
        phrase="o_schwerpunkt", target=True, radius=7),
    "stoss": dict(
        label="Stosstrupp: storm party", verb="Stosstrupp", nation=("germany",), grade=1, lead=6.5,
        kind="assault", blurb="Two small parties, close in along dead ground, bypass the strongpoint.",
        mods=dict(storm=True, exposure=1.35, fire=0.85), phrase="o_stoss", target=True, radius=5,
        ground=("cover", "night"), unit=("fallschirmjager", "brandenburg", "commando", "rangers")),
    # ------------------------------------------------------------------ Soviet
    "maskirovka": dict(
        label="Maskirovka: dummy positions", verb="Maskirovka", nation=("ussr",), grade=2, lead=4.5,
        kind="defend", blurb="Dummies out front to draw his fire; the men dig where the dummies are not.",
        mods=dict(decoy=True, dig_on_arrival=True), phrase="o_maskirovka", target=True, radius=8,
        needs="construction"),
    "deep_echelon": dict(
        label="Deep echelon: first and second", verb="Eshalonami", nation=("ussr",), grade=2, lead=5.5,
        kind="attack", blurb="First echelon goes in; the second follows and consolidates the ground.",
        mods=dict(echelon=True), phrase="o_echelon", target=True, radius=7),
    "main_attack": dict(
        label="Main attack", verb="Glavnyy udar", nation=("ussr",), grade=2, lead=5.0, kind="attack",
        blurb="All of it, here, now, with everything the section has.",
        mods=dict(fire=1.15, morale=2.0), phrase="o_main_attack", target=True, radius=6),
    # ------------------------------------------------------------------ American and Commonwealth
    "recon_by_fire": dict(
        label="Reconnaissance by fire", verb="Recon by fire", nation=("usa", "uk", "canada", "australia",
                                                                      "newzealand", "india"), grade=0, lead=4.0,
        kind="suppress", blurb="Fire into the likely cover and make him answer. It gives the position away.",
        mods=dict(recon_fire=True), phrase="o_recon_fire", target=True, radius=10),
    "fire_and_movement": dict(
        label="Fire and movement", verb="Fire and movement", nation=("usa", "uk", "canada", "australia",
                                                                    "newzealand", "india"), grade=0, lead=3.0,
        kind="attack", blurb="Teams by bounds: one moves, one keeps fire on him.",
        mods=dict(bounds=True), phrase="o_fire_move", target=True, radius=6),
    "bite_and_hold": dict(
        label="Bite and hold", verb="Bite and hold", nation=("uk", "canada", "australia", "newzealand", "india"),
        grade=1, lead=4.5, kind="attack",
        blurb="A limited objective, taken and dug in at once. No pursuit.",
        mods=dict(hold_on_arrival=True, dig_on_arrival=True, fire=1.1), phrase="o_bite_hold", target=True,
        radius=4),
    # ------------------------------------------------------------------ others
    "infiltration": dict(
        label="Infiltration", verb="Shin'nyū", nation=("japan",), grade=0, lead=4.5, kind="attack",
        blurb="Small parties through the gaps, in the dark and the dead ground; avoid the strongpoints.",
        mods=dict(infiltrate=True, exposure=1.4), phrase="o_infiltration", target=True, radius=8,
        ground=("night", "cover")),
    "banzai": dict(
        label="Banzai charge", verb="Banzai", nation=("japan",), grade=1, lead=4.0, kind="assault",
        blurb="Fix bayonets and go at them. The section will not stop for fire.",
        mods=dict(banzai=True, fire=0.8), phrase="o_banzai", target=True, radius=5),
    "motti": dict(
        label="Motti: close the ring", verb="Motti", nation=("finland",), grade=2, lead=5.5, kind="attack",
        blurb="Take the two flanks and close the ring; the pocket is the prize.",
        mods=dict(ring=True), phrase="o_motti", target=True, radius=8, squads=2),
}

# the basic vocabulary every army has, and the drills, in the order a leader thinks of them
BASIC = ("follow_me", "cover_me", "watch", "consolidate", "probe", "break_contact")

GROUND_WORD = {"cover": "ground with cover", "night": "dark or dead ground"}


def _nation(nation):
    """The doctrine family: Commonwealth armies drill together, the rest stand alone."""
    return "cw" if COALITION.get(nation) == "cw" else nation


def drill_nations(d):
    if d["nation"] is None:
        return None
    return {"cw" if n in ("uk", "canada", "australia", "newzealand", "india") else n for n in d["nation"]}


def leader_skill(game, sq):
    """What the man giving the order and the man taking it can between them be expected to know."""
    from .skills import level
    p = game.player
    mine = level(p, "leadership")
    theirs = level(sq.leader, "leadership") if sq.leader is not None and sq.leader.active else 0.0
    # a section that knows its leader adds a little; the player's own voice carries
    return max(mine, theirs * 0.85) + (0.7 if sq.player_led else 0.0)


def grade(game, sq):
    """The authority behind the order: yours, or the section leader's if he is a real one."""
    p = game.player
    theirs = sq.leader.command_grade if sq.leader is not None and sq.leader.active else 0
    return max(p.command_grade, theirs)


def teachable(game, sq, key):
    """(ok, reason).  Unavailable drills are still listed with their reason, so the player learns the ladder."""
    d = DRILLS[key]
    n = _nation(sq.nation)
    fam = drill_nations(d)
    if fam is not None and n not in fam:
        return False, f"Not taught in the {sq.nation} army."
    if d.get("nounit"):
        return False, "Not for this unit."
    if d.get("unit") and (p_unit := game.player.__dict__.get("unit_type")) not in d["unit"] and \
            (sq.__dict__.get("unit_type") not in d["unit"]):
        return False, "Needs a trained assault unit or specialist."
    if grade(game, sq) < d["grade"]:
        from .data.ranks import COMMAND_LEVEL
        return False, f"Needs a {COMMAND_LEVEL.get(d['grade'], 'higher')} commander to put his name to it."
    skill = leader_skill(game, sq)
    if skill < d["lead"]:
        from .skills import word
        return False, f"Too much for a leader who is {word(skill)}. Practice the simpler drills."
    if d.get("squads") and len(d.get("_squads", ())) < d["squads"]:
        return False, "Needs two units to take the flanks."
    if d.get("needs") == "construction":
        if not any(a.active and not a.downed and (a.has_tool("shovel") or a.has_tool("repair"))
                   for a in sq.members):
            return False, "No entrenching tools in the section."
    g = d.get("ground")
    if g:
        m = game.map
        anc = sq.anchor()
        if anc is not None:
            near_cover = any(m.in_bounds(anc[0] + dx, anc[1] + dy) and
                             (m.pos_cover[anc[0] + dx, anc[1] + dy] >= 40 or m.conceal[anc[0] + dx, anc[1] + dy] >= 40)
                             for dx, dy in ((0, 0), (2, 0), (-2, 0), (0, 2), (0, -2), (3, 3), (-3, -3)))
            night = game.is_night()
            if "night" in g and not night and "cover" in g and not near_cover:
                return False, "Needs darkness or dead ground."
            if "night" in g and not night and "cover" not in g:
                return False, "Needs darkness."
            if "cover" in g and not near_cover and "night" not in g:
                return False, "Needs dead ground close by."
    return True, ""


def available(game, squads, key):
    """Checked against the first real unit and the count of units given."""
    live = [s for s in squads if not s.gone]
    if not live:
        return False, "No unit."
    if key not in DRILLS:
        return False, "Unknown drill."
    d = dict(DRILLS[key])
    if d.get("squads"):
        d["_squads"] = live
        # teachable reads DRILLS, so pass the count through a temp key on the module
        DRILLS[key]["_squads"] = live
    try:
        return teachable(game, live[0], key)
    finally:
        DRILLS[key].pop("_squads", None)


def menu(game, squads):
    """[(label, key, enabled, reason)] - every drill this army teaches, available or not."""
    out = []
    n = _nation(squads[0].nation) if squads else None
    for key in BASIC + tuple(k for k, d in DRILLS.items() if k not in BASIC):
        d = DRILLS[key]
        fam = drill_nations(d)
        if fam is not None and n not in fam:
            continue
        ok, why = available(game, squads, key)
        out.append((d["label"], key, ok, why))
    return out


def phrase_key(key):
    return DRILLS[key].get("phrase", "o_move")


def target_label(key):
    d = DRILLS[key]
    return d["verb"] if d.get("contrast") is False else d["verb"]


def make(game, key, target, sq, roe=None):
    """The order a drill actually issues.  The base kind does the work; the modifiers are the drill."""
    from .ai import Order
    d = DRILLS[key]
    kind = d["kind"]
    radius = d.get("radius", 6)
    o = Order(kind, target=tuple(target) if target is not None else None, radius=radius,
              issued=game.turn, src="player", roe=roe or (sq.order.roe if sq is not None else "free"))
    o.mod = dict(d.get("mods", {}))
    o.drill = key
    if o.mod.get("roe"):
        o.roe = o.mod["roe"]
    if kind == "ambush":
        o.roe = "hold"
    if key == "auftragstaktik":
        o.radius = 16
    return o


def ring_points(point, squads):
    """Motti: the flanks, not the centre.  Two units go round the pocket from opposite sides."""
    import math
    x, y = point
    out = []
    n = max(1, len(squads))
    for i in range(n):
        ang = (2 * math.pi * i / n) + math.pi / 4
        # a quarter of the way round a 30-yard ring: the flanks, with the pocket still between them
        out.append((int(round(x + math.cos(ang) * 12)), int(round(y + math.sin(ang) * 12))))
    return out


def decoys(game, sq, point):
    """Maskirovka: contacts that aren't there any more (or yet).  The enemy brain shoots at them."""
    from .brain import Contact
    brain = game.brains.get("axis" if sq.side == "allies" else "allies")
    if brain is None:
        return 0
    made = 0
    x, y = point
    for dx, dy in ((4, 2), (-4, 2), (0, 5), (6, -3)):
        xx, yy = x + dx, y + dy
        if not game.map.in_bounds(xx, yy):
            continue
        key = -(100000 + sq.id * 10 + made)
        c = Contact(key, xx, yy, game.turn, "mg", None, sound=False)
        c.decoy = game.turn + 900
        brain.contacts[key] = c
        made += 1
    return made


def tick(game):
    """A decoy is a few men with shovels and a helmet on a stick: it fades when they're found out."""
    for side in ("allies", "axis"):
        brain = game.brains.get(side)
        if brain is None:
            continue
        for k in [k for k, c in brain.contacts.items()
                  if getattr(c, "decoy", 0) and game.turn > c.decoy]:
            brain.contacts.pop(k, None)


# ============================================================================ what the other side is taught
def ai_choice(game, sq, kind):
    """An NPC leader's own training: the drill he reaches for, or None for a plain order.

    Skill gates it, the army decides the menu, and the roll keeps it from being a script.  It only
    chooses among things that section could already do - the same mechanics the player uses.
    """
    ld = sq.leader
    if ld is None or not ld.active or ld.downed:
        return None
    from .skills import level
    skill = level(ld, "leadership")
    n = _nation(sq.nation)
    r = game.rng.random()
    if kind == "attack":
        if n == "germany" and skill >= 5.5:
            return "schwerpunkt" if r < 0.18 else "stoss" if r < 0.30 else None
        if n == "ussr" and skill >= 5.0:
            return "main_attack" if r < 0.22 else "deep_echelon" if r < 0.34 else None
        if n == "japan" and skill >= 4.5:
            return "infiltration" if game.is_night() and r < 0.35 else "banzai" if r < 0.22 else None
        if n in ("usa", "cw") and skill >= 4.0:
            return "fire_and_movement" if r < 0.30 else None
        if n == "cw" and skill >= 4.5 and r < 0.20:
            return "bite_and_hold"
    elif kind == "defend":
        if n == "ussr" and skill >= 4.5 and r < 0.12:
            return "maskirovka"
        if n == "germany" and skill >= 4.5 and game.turn - sq.last_contact < 120 and r < 0.12:
            return "feuerueberfall"
    return None


def ai_order(game, sq, kind, obj, radius):
    """A commander's order, with a national drill when this leader would really reach for one."""
    from .ai import Order
    key = ai_choice(game, sq, kind)
    if key is None:
        o = Order(kind, obj=obj, radius=radius, issued=game.turn)
        return o
    o = make(game, key, None, sq)
    o.kind = kind
    o.obj = obj
    o.radius = radius
    o.src = "ai"
    return o
