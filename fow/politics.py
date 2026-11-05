"""The war above the war map: heads of state, their staffs, and what they want from you.

At general rank the player is no longer only a soldier; he is a name in someone else's plan.  A
five-star commander can set theatre direction, pull priorities of supply and air onto his front, move
formations, relieve a failing commander - and can tell the head of state that the plan is wrong.
Compliance earns political credit; refusal spends it, and the head of state has a temper and a
memory.

The politics are deliberately coarse and historical in shape, not a spreadsheet of court intrigue:
Stalin's Stavka and Hitler's Führer headquarters interfere hard and often; the American and British
chiefs of staff are more patient; the Japanese Imperial Headquarters speaks in the Emperor's name.
No effect is a free buff.  A directive that presses the attack costs supply and lives; standing fast
loses ground; defying the direction costs credit and, if repeated, the command.
"""
from __future__ import annotations

from .data.nations import NATIONS
from .data.ranks import GENERAL, LT_GEN

HEADS = {
    "germany": ("the Führer", "Hitler", "Führer headquarters", 0.75),
    "ussr": ("Stavka", "Stalin", "the Kremlin", 0.8),
    "usa": ("the Chief of Staff", "General Marshall", "Washington", 0.5),
    "uk": ("the Prime Minister", "Churchill", "the War Cabinet", 0.55),
    "japan": ("Imperial General Headquarters", "the Emperor's staff", "Tokyo", 0.7),
    "italy": ("the Duce", "Mussolini", "Palazzo Venezia", 0.65),
    "finland": ("the Commander-in-Chief", "Mannerheim", "Mikkeli", 0.45),
    "france": ("the government", "the Third Republic", "Algiers", 0.5),
}

DIRECTIVES = {
    "press": ("Press the attack", "Every commander on the front leans into the next objective. Supply and "
              "casualties rise.", "attack"),
    "hold": ("Stand fast", "Nobody gives ground without orders. The line stiffens; opportunities go by.",
             "defend"),
    "supply": ("Priority of supply", "Stores, spares and ammunition come to this front first.", None),
    "air": ("Air priority", "The squadrons and the gun line look to your requests before the rest.", None),
    "armour": ("Armour to this front", "Tanks and anti-tank guns are diverted to your sector.", None),
}


def active(game):
    p = game.player
    return (p is not None and p.alive and p.rank >= GENERAL and game.__dict__.get("domain", "land") == "land"
            and game.__dict__.get("politics") is not None)


def start(game):
    if game.player.rank < LT_GEN:
        return
    p = game.player
    head = HEADS.get(p.nation)
    if head is None:
        return
    game.politics = dict(side=p.side, nation=p.nation, credit=50.0, patience=head[3] * 100,
                         stance=None, supply=0, air=0, defiance=0, demands=[], last=game.turn,
                         sacked=False)


def _head(game):
    return HEADS.get(game.politics.get("nation")) if game.__dict__.get("politics") else None


def _word(game):
    h = _head(game)
    return h[0] if h else "headquarters"


def tick(game):
    pol = game.__dict__.get("politics")
    if pol is None or not active(game):
        return
    t = game.turn
    if t % 600 != 0:
        return
    pol["patience"] = min(100.0, pol["patience"] + 2)
    for d in list(pol["demands"]):
        ob = next((o for o in game.map.objectives if o.name == d["name"]), None)
        if ob is not None and ob.owner == pol["side"]:
            pol["demands"].remove(d)
            pol["credit"] = min(100.0, pol["credit"] + 20)
            game.msg(f"{_word(game).capitalize()} is satisfied: {d['name']} is taken.", "good")
        elif game.turn > d["due"]:
            pol["demands"].remove(d)
            pol["credit"] = max(0.0, pol["credit"] - 15)
            pol["patience"] = max(0.0, pol["patience"] - 20)
            game.msg(f"{_word(game).capitalize()} notes that {d['name']} was not taken.", "warn")
    # the direction wears off: headquarters wants a new statement of intent every so often
    if pol["stance"] and t - pol.get("stance_set", t) > 900:
        pol["stance"] = None
        game.msg(f"{_word(game).capitalize()} has stopped looking for a new push from you.", "info")
    if pol["supply"]:
        from .sustain import stores
        s = stores(game.sector, pol["side"])
        for k in ("ammo", "materials", "fuel", "medical"):
            s[k] = s.get(k, 0) + 6
        pol["supply"] -= 1
    if pol["air"]:
        pol["air"] -= 1
    # a demand now and then
    if t - pol["last"] > 900 and len(pol["demands"]) < 2 and game.command.is_top_commander(game):
        obj = next((o for o in game.map.objectives if o.owner != pol["side"]), None)
        if obj is not None:
            pol["demands"].append(dict(kind="take", name=obj.name, sector=(game.sector.x, game.sector.y),
                                       due=t + 1800))
            game.msg(f"{_word(game).capitalize()} wants {obj.name} taken. (Command screen)"
                     if obj.name else "", "radio")
            pol["last"] = t


def menu(ps):
    from .render import Popup
    g = ps.game
    pol = g.politics
    h = _head(g)
    lines = [(f"{h[0].capitalize()} - {h[2]}. Political credit: {pol['credit']:.0f}. Patience: "
              f"{pol['patience']:.0f}.", (220, 200, 150)),
             (f"Defiances: {pol['defiance']}.", (200, 190, 160))]
    if pol["stance"]:
        lines.append(("Standing direction: " + DIRECTIVES[pol["stance"]][0], (240, 220, 150)))
    for d in pol["demands"]:
        left = max(0, d["due"] - g.turn)
        lines.append((f"Demand: {d['name']}. {left // 60} minutes left.", (240, 170, 120)))
    opts = []
    for k, (label, desc, _s) in DIRECTIVES.items():
        mark = " (in force)" if pol["stance"] == k and k in ("press", "hold") else ""
        cost = {"press": 40, "hold": 40, "supply": 12, "air": 12, "armour": 30}.get(k, 10)
        opts.append((f"{label}{mark} - costs about {cost}", k, (230, 215, 160) if pol["credit"] >= cost else
                     (140, 135, 120), pol["credit"] >= cost))
    opts += [("Relieve a commander...", "relieve", None, True),
             ("Tell headquarters the plan is wrong", "defy", (245, 190, 120), pol["credit"] >= 15),
             ("Back", "back", None, True)]
    from .textfit import wrap as _wrap
    flat = [(w, c) for text, c in lines for w in _wrap(text, 76)]
    ps.open_popup(Popup("Theatre direction", opts, ps._screen_anchor(), width=80, lines=flat),
                  lambda v: _pick(ps, v), cancel=lambda: None)


def _pick(ps, v):
    g = ps.game
    pol = g.politics
    if v == "back" or v is None:
        return
    if v == "relieve":
        return relieve(ps)
    if v == "defy":
        return defy(g)
    label, desc, kind = DIRECTIVES[v]
    cost = {"press": 40, "hold": 40, "supply": 12, "air": 12, "armour": 30}.get(v, 10)
    if pol["credit"] < cost:
        g.msg(f"{_word(g).capitalize()} wants more than your credit is worth.", "warn")
        return
    pol["credit"] -= cost
    if v in ("press", "hold"):
        pol["stance"] = v
        pol["stance_set"] = g.turn
    elif v == "supply":
        pol["supply"] = 3
    elif v == "air":
        pol["air"] = 4
    elif v == "armour":
        pol["armour"] = 2
        from .strategic import BIOME_NAME  # noqa: F401
        for s in g.strategic.sectors():
            if s.control == g.player.side:
                s.units[g.player.side]["tank"] += 1
                break
    g.msg(f"{_word(g).capitalize()} records the direction: {label.lower()}.", "good")
    g.command.__dict__.setdefault("record", []).append(g.datetime_str() + ": theatre direction - " + label)


def defy(game):
    """Telling the head of state the plan is wrong: it may be right, and it still costs."""
    pol = game.politics
    if pol["credit"] < 15:
        game.msg("You have too little credit to be heard.", "warn")
        return
    pol["credit"] -= 15
    pol["defiance"] += 1
    pol["stance"] = None
    game.msg(f"You tell {_word(game)} the direction is wrong. It is on the record now.", "warn")
    roll = game.rng.random()
    if roll < 0.25 + pol["defiance"] * 0.12 and pol["patience"] < 45:
        # sacked: the player keeps the rank but loses the theatre billet for a while
        pol["sacked"] = game.turn + 900
        game.msg(f"{_word(game).capitalize()} has relieved you of the front for a while. "
                 f"Your regiments go on without you.", "death")
        game.msg("(You will be back. Probably.)", "info")


def relieved(game):
    pol = game.__dict__.get("politics")
    return bool(pol and pol.get("sacked", 0) > game.turn)


def relieve(ps):
    """Take a failing formation commander out of his own plan."""
    from .render import Popup
    g = ps.game
    opts = []
    for root in g.command.roots.values():
        for f in root.walk():
            if f.commander is None or f.commander is g.player:
                continue
            if f.side != g.player.side or not f.live_squads():
                continue
            if f.commander_grade() >= g.player.rank:
                continue
            opts.append((f"{f.title()} - {f.commander_label()}", f.id, None, True))
    opts = opts[:12] or [("No command of yours to change", None, False)]
    ps.open_popup(Popup("Relieve a commander", opts, ps._screen_anchor(), width=76,
                        lines=[("The formation gets its next senior officer. It costs political credit.", "info")]),
                  lambda fid: _do_relieve(g, fid), cancel=lambda: None)


def _do_relieve(game, fid):
    if fid is None:
        return
    pol = game.politics
    if pol["credit"] < 8:
        game.msg("Not enough credit to spend on a sacking.", "warn")
        return
    for root in game.command.roots.values():
        for f in root.walk():
            if f.id != fid:
                continue
            cs = [m for sq in f.squads for m in sq.members
                  if m.active and not m.downed and m.command_grade < game.player.rank]
            if not cs:
                game.msg("There is nobody in it senior enough to take over.", "warn")
                return
            f.commander = max(cs, key=lambda m: (m.command_grade, m.skill))
            f.acting = True
            pol["credit"] -= 8
            game.msg(f"{f.commander_label()} takes the {f.title()}.", "info")
            return
