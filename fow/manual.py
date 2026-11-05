"""The field manual, in the pages you've earned.

Nobody reads a manual front to back in a ditch.  Pages come up when the thing happens: the first time
you're shot at and get down, the first tank, the first man you watch bleed out.  Each is a short page in
the army's voice, with a diagram, a do and a don't.  They stay in the book after that, readable with K.

Nothing here is a tutorial prompt.  A page only appears if the ground has already taught the lesson once.
"""
from __future__ import annotations

PAGES = {
    "cover": dict(title="Cover and the ground", unlock="always",
                  lines=["A ditch is worth more than a good rifle. Get into the ground, or behind it.",
                         "Stay below the top of what's in front of you. A helmet over the parapet is a target.",
                         "One man in one place is a target; two men ten yards apart are a problem."],
                  do="down, behind, apart", dont="up, together, in the open",
                  art=["   |      |      |", "  _|_    _|_    _|_", " (o)    (o)    (o)",
                       "  |      |      |"]),
    "dead_ground": dict(title="Dead ground", unlock="shelled",
                        lines=["Ground can't be shot if it can't be seen. A fold, a bank and the far side of a "
                               "hedge are dead ground.",
                               "Move through it, not across the fields. It's slower and you live."],
                        do="use the fold", dont="cross the crest",
                        art=["      o", "     /|\\", "  ___/ \\___", "  dead   dead"]),
    "fire_move": dict(title="Fire and movement", unlock="contact",
                      lines=["One part fires; the other moves. Then swap.",
                             "Never both at once. The moving half goes by bounds, and gets down before the next."],
                      do="bound, cover, bound", dont="both up together",
                      art=["  >->     o", "  __      __", "  fire   move"]),
    "armour": dict(title="Enemy armour", unlock="vehicle",
                   lines=["A tank is blind shut down and deaf with the engine on. Get off its line, then behind "
                          "or beside it.",
                          "Infantry riding a tank are its eyes. Shoot them first; a tank alone is a work party."],
                   do="get round it", dont="lie in front of the gun",
                   art=["  [####]", "  ______/", "  ^ dead angle"]),
    "shells": dict(title="Splinters and shells", unlock="shelled",
                   lines=["Flat, in a scrape, face down, mouth open. A standing man catches everything.",
                          "Don't all go into one hole. A near miss on a crowded slit trench is a section."],
                   do="flat and apart", dont="stand and stare",
                   art=["  *  *  *", "  _  _  _", " (o)(o)(o)"]),
    "stretcher": dict(title="Stretchers", unlock="medevac",
                      lines=["A stretcher takes four. Don't drag a man by the arm if there are backs to spare.",
                             "Dress him where he lies first; bleeding is what kills before the stretcher comes."],
                      do="dress, then carry", dont="carry an open wound",
                      art=["  o---o", "  | + |", "  o---o"]),
    "wire": dict(title="Wire", unlock="wire",
                 lines=["Cut low and from the side, never kneeling on it. Cut enough, not neat.",
                        "A gap is a choke point. Get through fast and spread out."],
                 do="cut low, go fast", dont="stand in the gap",
                 art=["  x x x", "  | | |", "  v v v"]),
    "water": dict(title="Water, feet and salt", unlock="thirst",
                  lines=["Fill the canteen at every chance. A man without water is rationed to what he can carry.",
                         "Change socks when you can. Trench foot takes a section out of the line as surely as fire."],
                  do="fill and dry", dont="drink it all at once",
                  art=["  ~~~", "  [ ]", "  ^ ^"]),
    "stand_to": dict(title="Stand-to", unlock="night",
                     lines=["First and last light are when the attack comes. Everyone up, weapons ready, at the "
                            "parapet, before the light changes.",
                            "Stand-to is not a rest. It is the ten minutes that decides the day."],
                     do="up before dawn", dont="sleep through the grey",
                     art=["  o o o", "  | | |", "  ======"]),
    "prisoners": dict(title="Prisoners", unlock="prisoner",
                      lines=["Hands up doesn't mean empty. Search him from behind, gun out of reach, before anything.",
                             "Send them back in twos with a guard. A prisoner alone behind you is a problem."],
                      do="search, then send", dont="turn your back",
                      art=["  o_/", "  /|", "  / \\"]),
}
ORDER = ("cover", "fire_move", "dead_ground", "shells", "armour", "stretcher", "wire", "water", "stand_to",
         "prisoners")
TRIGGERS = {"contact": "fire_move", "shelled": "shells", "vehicle": "armour", "medevac": "stretcher",
            "thirst": "water", "night": "stand_to", "prisoner": "prisoners", "wire": "wire", "cover": "cover"}


def unlocked(game) -> list[str]:
    got = game.__dict__.setdefault("manual", [])
    if "cover" not in got:
        got.append("cover")
    return [k for k in ORDER if k in got]


def unlock(game, trigger, why=None) -> None:
    key = TRIGGERS.get(trigger, trigger)
    got = game.__dict__.setdefault("manual", [])
    if key in got or key not in PAGES:
        return
    got.append(key)
    p = PAGES[key]
    game.msg(f"FIELD MANUAL: {p['title']}. (K to read it)", "info")
    from . import diary
    diary.entry(game, "manual", f"Learned the page on {p['title'].lower()}"
                                + (f" the hard way: {why}" if why else "") + ".")


def check(game) -> None:
    """Unlock pages from what has happened to the player."""
    p = game.player
    if p is None or not p.alive:
        return
    st = p.stats
    if game.seen_enemies(30) and game.turn:
        unlock(game, "contact")
    if p.suppression > 25 or getattr(p, "hit_turn", -999) >= 0:
        unlock(game, "cover")
    if getattr(p, "hit_turn", -999) >= 0 or game.__dict__.get("shells"):
        unlock(game, "shells")
        unlock(game, "dead_ground")
    if game.stats.get("vehicles_killed", 0) >= 1:
        unlock(game, "vehicle")
    if game.__dict__.get("medevac") is not None:
        unlock(game, "medevac")
    if st.get("shots", 0) >= 20:
        unlock(game, "fire_move")
    if p.has_tool("wirecutters"):
        unlock(game, "wire")
    if p.ai.get("needs", {}).get("thirst", 0) > 55:
        unlock(game, "thirst")
    if game.is_night():
        unlock(game, "night")
    if any(a.state == "surrendered" for a in game.near(p.x, p.y, 12)):
        unlock(game, "prisoner")
    if game.turn > 120:
        unlock(game, "dead_ground")
