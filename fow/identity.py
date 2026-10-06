"""Checkpoint conversations: persistent papers, remembered statements and fallible observers."""
from __future__ import annotations

from .skills import level

QUESTIONS = {"name": "Your name?", "trade": "What do you do for a living?",
             "origin": "Where have you come from?", "destination": "Where are you going?",
             "purpose": "What business takes you there?"}
ALTERNATIVES = {
    "name": ("Jean Martin", "Pierre Laurent", "Henri Bernard"),
    "trade": ("farm labourer", "railway worker", "commercial traveller", "electrician"),
    "origin": ("the market quarter", "the farms outside town", "the railway district"),
    "destination": ("the next village", "the town market", "the railway workshops"),
    "purpose": ("visiting a sick relative", "looking for paid work", "delivering parts to a customer"),
}


def legend(game):
    from .agents import cover
    cv = cover(game)
    if cv is None:
        cv = game.__dict__.setdefault("improvised_cover", {})
    if "legend" not in cv:
        cv["legend"] = dict(name=cv.get("name") or "Private Martin", trade=cv.get("trade") or "dispatch rider",
                            purpose=cv.get("story") or "carrying dispatches to the replacement company",
                            origin=game.rng.choice(ALTERNATIVES["origin"]),
                            destination=game.rng.choice(ALTERNATIVES["destination"]))
    return cv["legend"]


def documents(game):
    story = legend(game)
    papers = [i for i in game.player.inv if i.t.tool in ("papers", "cover_papers") and i.functional]
    for it in papers:
        if (it.data or {}).get("identity"):
            continue
        fields = dict(story)
        quality = game.rng.uniform(.55, .98)
        stamp = "clear district seal"
        if game.rng.random() < .25:
            field = game.rng.choice(("origin", "destination", "trade", "stamp"))
            if field == "stamp":
                stamp = "overlapping district seals"
            else:
                fields[field] = game.rng.choice([v for v in ALTERNATIVES[field] if v != story[field]])
        it.data = dict(it.data or {}, identity=fields, paper_quality=quality, stamp=stamp)
    return papers


def notes(game):
    out = ["Legend to maintain:"] + [f"{k.capitalize()}: {v}." for k, v in legend(game).items()]
    papers = documents(game)
    for it in papers:
        out.append(f"{it.t.name}: " + "; ".join(f"{k}: {v}" for k, v in it.data["identity"].items()) + ".")
        out.append(f"Seal: {it.data['stamp']}. Condition {round(it.condition * 100)}%.")
    if not papers:
        out.append("You have no usable identity papers.")
    out.append("Guards can remember answers. A changed route needs an explanation; papers can contain errors.")
    return out


def acuity(guard):
    return .65 * level(guard, "observation") + .35 * level(guard, "languages") + \
        (1.5 if guard.role == "intel" else .6 if guard.role == "mp" else 0.)


def observer(game, check=None):
    check = check or game.__dict__.get("identity_check")
    if not check or check["sector"] != (game.sector.x, game.sector.y):
        return None
    from .senses import los_clear
    p = game.player
    return next((a for a in game.actors if a.id == check["guard"] and a.active and not a.downed and
                 getattr(a, "z", 0) == getattr(p, "z", 0) and
                 max(abs(a.x - p.x), abs(a.y - p.y)) <= 4 and los_clear(game, a.x, a.y, p.x, p.y)), None)


def begin(game, guard):
    if game.__dict__.get("identity_check") or not game.player.ai.get("disguise") or \
            getattr(guard, "z", 0) != getattr(game.player, "z", 0):
        return False
    from .counterintel import state
    papers = documents(game)
    attention = acuity(guard)
    # One stable temperament per sentry; closing a menu never rerolls him.
    if "papers_diligence" not in guard.ai:
        guard.ai["papers_diligence"] = game.rng.uniform(-1.5, 1.)
    attention += guard.ai["papers_diligence"]
    attention += state(game, guard.side)["heat"] / 50
    questions = ["name"]
    if attention >= 3:
        questions += ["purpose"]
    if attention >= 5:
        questions += ["trade", "origin", "destination", "purpose"]
    check = dict(guard=guard.id, sector=(game.sector.x, game.sector.y), attention=attention,
                 questions=questions, step=0, answers={}, evidence=[], score=0, stage="questions",
                 papers=[i.iid for i in papers], started=game.turn)
    game.identity_check = check
    if game.__dict__.get("autopilot"):
        from .succession import set_autopilot
        set_autopilot(game, False)
    if not papers and attention >= 2:
        evidence(check, "You have no usable identity card.", 2)
    for it in papers:
        quality = it.data["paper_quality"] * it.condition
        if attention > quality * 10 + 1:
            evidence(check, "He notices irregular printing or damage to the identity card.", 1)
        if it.data["stamp"] != "clear district seal" and attention >= 5:
            evidence(check, "He points to the overlapping district seals.", 1)
    if level(game.player, "languages") < 4 and attention >= 4:
        evidence(check, "Your accent does not fit a local's papers.", 1)
    game.msg("A sentry stops you: 'Your papers. A few questions.'", "warn")
    return True


def evidence(check, text, weight):
    if text not in check["evidence"]:
        check["evidence"].append(text)
        check["score"] += weight


def choices(game, check):
    field = check["questions"][check["step"]]
    values = [legend(game)[field]]
    values += [it.data["identity"][field] for it in documents(game)]
    values += list(ALTERNATIVES[field])
    values = list(dict.fromkeys(values))
    # No correct-answer marker or predictable first slot.
    import random
    random.Random(check["guard"] * 37 + check["step"]).shuffle(values)
    return field, values[:6]


def answer(game, value):
    check = game.__dict__.get("identity_check")
    guard = observer(game, check)
    if check is None or guard is None:
        game.identity_check = None
        return
    from .counterintel import state
    field = check["questions"][check["step"]]
    attention = check["attention"]
    previous = check["answers"].get(field)
    name = check["answers"].get("name", value if field == "name" else legend(game)["name"])
    memory = guard.ai.setdefault("identities", {}).get(name, {})
    # Security specialists compare the district's recorded checks; ordinary sentries remember their own.
    if guard.role in ("mp", "intel") or guard.ai.get("security"):
        memory = dict(state(game, guard.side).setdefault("identities", {}).get(name, {}), **memory)
    if attention >= 2 and (previous is not None and previous != value):
        evidence(check, f"You changed your answer about {field} during this conversation.", 3)
    if attention >= 4 and field in memory and memory[field] != value:
        evidence(check, f"The earlier checkpoint record gives a different {field}.", 2)
    for it in documents(game):
        if attention >= 3 and it.data["identity"].get(field) != value:
            evidence(check, f"Your {field} does not match the {it.t.name}.", 2)
    check["answers"][field] = value
    check["step"] += 1
    if check["step"] == len(check["questions"]):
        if check["score"] >= 2:
            check["stage"] = "explain"
        else:
            finish(game, True)


def finish(game, passed):
    check = game.__dict__.get("identity_check")
    if not check:
        return
    guard = observer(game, check)
    p = game.player
    if guard is not None:
        name = check["answers"].get("name", legend(game)["name"])
        guard.ai.setdefault("identities", {}).setdefault(name, {}).update(check["answers"])
        from .counterintel import state
        # A routine sentry doesn't telepathically circulate every answer; security keeps a register.
        if guard.ai.get("security") or guard.role in ("mp", "intel"):
            state(game, guard.side).setdefault("identities", {}).setdefault(name, {}).update(check["answers"])
        guard.ai["cleared_identity_until"] = game.turn + 600 if passed else game.turn
    p.ai["suspicion"] = 0
    p.ai["papers_checked"] = game.turn
    game.identity_check = None
    if passed:
        game.msg("He hands the papers back. 'All right. Move along.'", "info")
        from .skills import use
        use(game, p, "languages", 2)
    else:
        blow_cover(game, "You refuse the check and he raises the alarm.")


def blow_cover(game, reason):
    from .constants import other_side
    from . import counterintel as CI
    p = game.player
    p.ai.update(disguise=False, suspicion=0)
    game.identity_check = None
    game._enemy_arr = {}
    enemy = other_side(p.side)
    CI.state(game, enemy)["wanted"] = True
    CI.report(game, enemy, p.pos, 50, "a blown cover identity")
    game.brains[enemy].report(p, game.turn)
    game.msg(reason + " Your cover is blown!", "death")


def explain(game, choice):
    check = game.identity_check
    if choice == "clerical":
        supported = any("match" in e or "seals" in e or "printing" in e for e in check["evidence"])
    elif choice == "route":
        supported = any("destination" in e or "purpose" in e for e in check["evidence"])
    else:
        supported = False
    # Explaining a single discrepancy can work; a rehearsed excuse cannot erase repeated contradictions.
    allowance = 2 if supported and level(game.player, "languages") + 1 >= check["attention"] else 0
    if check["score"] - allowance < 2:
        finish(game, True)
    else:
        check["stage"] = "search"


def present(ps):
    """Called between simulation turns, never from inside an actor's AI update."""
    g = ps.game
    check = g.__dict__.get("identity_check")
    if not check or ps.popups or ps.inv_screen is not None or g.game_over or not g.player.body.conscious or \
            ps.__dict__.get("_resolving_identity") or \
            (ps.__dict__.get("wait") or {}).get("kind") == "forced":
        return False
    guard = observer(g, check)
    if guard is None or not g.player.ai.get("disguise"):
        g.identity_check = None
        return False
    ps.stop_auto()
    from .render import Popup
    from .constants import UI_TEXT, UI_DIM
    import textwrap
    tell = "He barely glances up." if check["attention"] < 3 else "He reads the papers carefully." if check["attention"] < 6 else \
        "He compares the documents and writes down each answer."
    lines = [(tell, UI_DIM)]
    lines += [(line, UI_TEXT) for e in check["evidence"][-3:] for line in textwrap.wrap(e, 64)]
    if check["stage"] == "questions":
        field, values = choices(g, check)
        repeated = field in check["answers"]
        lines.append((("Again: " if repeated else "") + QUESTIONS[field], UI_TEXT))
        opts = [(v, ("answer", v), None, True) for v in values]
    elif check["stage"] == "explain":
        lines.append(("'These details don't agree. Explain that.'", UI_TEXT))
        opts = [("The issuing clerk made an error.", ("explain", "clerical"), None, True),
                ("My destination changed after the permit was issued.", ("explain", "route"), None, True),
                ("I've already told you everything.", ("explain", "insist"), None, True)]
    else:
        lines.append(("'Put your bag down. I need to search it.'", UI_TEXT))
        opts = [("Submit to a search", ("search", None), None, True)]
    money = g.player.find(lambda i: i.functional and i.t.tool == "money" and i.count >= 20)
    if money is not None and check["stage"] != "questions":
        opts.append(("Offer twenty notes with the papers", ("bribe", None), None, True))
    opts += [("Review your legend and documents", ("notes", None), None, True),
             ("Refuse the check and break away", ("leave", None), None, True)]

    def choose(value):
        if g.__dict__.get("identity_check") is not check:
            return
        if observer(g, check) is None:
            g.identity_check = None
            return
        action, val = value
        if action == "notes":
            from .ui import TextState
            ps.app.push(TextState(ps.app, "Cover and papers - Esc returns to the check", notes(g)))
            return
        if action == "answer":
            answer(g, val)
        elif action == "explain":
            explain(g, val)
        elif action == "bribe":
            money = g.player.find(lambda i: i.functional and i.t.tool == "money" and i.count >= 20)
            if "takes_bribes" not in guard.ai:
                guard.ai["takes_bribes"] = g.rng.random() < (.12 if guard.role == "intel" else .4)
            corrupt = guard.ai["takes_bribes"]
            if money is not None and corrupt and check["score"] < 5:
                g.player.remove_item(money, 20)
                g.msg("He folds the notes away with a glance down the road.", "info")
                finish(g, True)
            else:
                evidence(check, "He refuses the money and calls another sentry over.", 2)
                check["stage"] = "search"
        elif action == "search":
            ps._resolving_identity = True
            try:
                ps.act(800)
            finally:
                ps._resolving_identity = False
            if g.game_over or not g.player.body.conscious or g.__dict__.get("identity_check") is not check:
                return
            contraband = [i for i in g.player.inv if i.functional and
                          (i.t.kind in ("gun", "explosive", "grenade") or i.t.tool in ("wireless", "code"))]
            if contraband or check["score"] >= 5:
                blow_cover(g, "The search finds " + (contraband[0].t.name if contraband else "irreconcilable identity details") + ".")
                # Use the existing surrender/captivity rules. The player chooses whether to comply.
                ps.open_popup(Popup("'Hands up!'", [("Surrender", True, None, True), ("Resist / escape", False, None, True)],
                                    ps._screen_anchor()), lambda surrender: ps._yell("surrender") if surrender else None)
            else:
                finish(g, True)
            return
        else:
            finish(g, False)
        ps.act(300 if action != "search" else 800)
        present(ps)

    ps.open_popup(Popup("Papers check", opts, ps._screen_anchor(), lines=lines, width=70), choose)
    # Esc only closes the view; the pending check remains, with the same answers and evidence.
    return True
