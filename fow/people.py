"""Every soldier a man: where he's from, what he did, who's waiting, what he's like - what he thinks of you,
who his mate is, and what things are worth to him.

life(a) is made the first time anyone asks (seeded by the man, so it's the same man every time) and kept
on him: the home town his letters come from (flavor.py), the girl in his photograph, the trade he'll go
back to.  opinion(a) is what he thinks of you, -100..100, moved by what you do (like()): a cigarette, a
dressing when he was bleeding, carrying him out; asking favours, shooting near him.  buddy() pairs the men
of a section, as armies did (the US 'buddy system', the German Kamerad beside you, the Soviet zemlyak).

worth(a, item) is what a thing is worth to him - in the war's currency, cigarettes - and what he'd take
for what (talk.py for you, social.py when two of them trade): a smoker with none left, a man down to his
last clip, a souvenir hunter and a Luger.  The same rules for everyone.
"""
from __future__ import annotations

import random
import zlib

TRADES = {
    "usa": ["worked the line at the Ford plant", "pumped gas", "farmed with my dad", "clerked at a bank",
            "was at college", "drove a truck", "worked in a steel mill", "was a mechanic", "sold shoes",
            "worked the docks", "was a cowhand", "delivered milk", "was a printer's apprentice"],
    "uk": ["was a miner", "worked on the railways", "was a clerk in the Pru", "was a butcher's boy",
           "worked in a mill", "was a gardener", "was a milkman", "worked in the shipyards", "was a bus conductor"],
    "germany": ["was a baker", "worked on the farm", "was a Gymnasium student", "was a locksmith",
                "worked at Krupp", "was a clerk", "was a carpenter's apprentice", "was a tram driver", "was a miner"],
    "ussr": ["drove a tractor on the kolkhoz", "worked at the tractor works", "was a schoolteacher",
             "was a student", "worked in the mine", "was a lathe operator", "herded cattle", "was a fisherman"],
    "japan": ["farmed rice", "was a fisherman", "worked in a textile mill", "was a student", "was a clerk",
              "was a carpenter", "sold noodles"],
    "italy": ["was a fisherman", "worked the vineyards", "was a barber", "was a mason", "was a student",
              "worked at Fiat"],
    "france": ["was a baker", "farmed", "was a schoolteacher", "worked at Renault"],
    "poland": ["farmed", "was a student in Kraków", "worked in the mine", "was a railwayman"],
    "finland": ["was a lumberjack", "farmed", "was a fisherman"],
}
PARTNER = {"usa": ["Mary", "Dorothy", "Betty", "Helen", "Ruth", "Jean", "Alice", "Marge"],
           "uk": ["Joan", "Margaret", "Peggy", "Doris", "Edna", "Vera"],
           "germany": ["Ilse", "Gerda", "Liesel", "Hilde", "Käthe", "Grete"],
           "ussr": ["Nina", "Valya", "Masha", "Katya", "Galya", "Tanya"],
           "japan": ["Hanako", "Fumiko", "Yoshiko", "Kazuko"], "italy": ["Rosa", "Giulia", "Maria", "Lucia"],
           "france": ["Simone", "Yvette", "Jeanne"], "poland": ["Hanka", "Zosia", "Basia"],
           "finland": ["Aino", "Helmi", "Kerttu"]}
FAITH = {"usa": [("Protestant", 6), ("Catholic", 3), ("Jewish", 1)], "uk": [("C of E", 6), ("Catholic", 2),
                                                                          ("Methodist", 2)],
         "germany": [("Lutheran", 6), ("Catholic", 4)], "ussr": [("none", 6), ("Orthodox, quietly", 3),
                                                                ("Muslim", 1)],
         "japan": [("Shinto and Buddhist", 1)], "italy": [("Catholic", 1)], "france": [("Catholic", 1)],
         "poland": [("Catholic", 1)], "finland": [("Lutheran", 1)]}
TEMPERS = ("cheerful", "grim", "nervous", "pious", "joker", "quiet", "cynical", "hard", "homesick", "keen")
HOPES = {"usa": ["open a garage", "go to college on the GI Bill", "marry {partner}", "buy a farm", "see the Dodgers win",
                 "never see another hedgerow"],
         "uk": ["get married", "have a pint in the local", "get his old job back", "emigrate to Canada"],
         "germany": ["see his children", "rebuild the bakery", "get out of the East alive", "marry {partner}"],
         "ussr": ["see Berlin", "go home to the village", "study engineering", "find his family"],
         "japan": ["see his mother again", "return to the village"], "italy": ["go home", "open a trattoria"]}


def _rng(a):
    return random.Random(zlib.crc32(f"{a.id}:{a.name}:{a.nation}".encode()))


def life(a) -> dict:
    """Who he is when he isn't a soldier (made once, kept on him)."""
    lf = a.__dict__.get("life")
    if lf is not None:
        return lf
    from .flavor import HOMETOWNS
    rng = _rng(a)
    nat = a.nation
    rank = getattr(a, "rank", 0)
    age = int(rng.triangular(18, 34, 21)) + max(0, rank - 3) * 2 + (6 if a.role in ("officer", "surgeon", "chaplain")
                                                                   else 0)
    age = min(58, age)
    town = rng.choice(HOMETOWNS.get(nat) or ["home"])
    married = rng.random() < min(0.75, max(0.08, (age - 19) / 16))
    partner = rng.choice(PARTNER.get(nat) or PARTNER["usa"])
    kids = rng.choice([0, 0, 1, 1, 2, 3]) if married and age > 22 else 0
    fam = "married" if married else rng.choice(["a girl", "a girl", "engaged", "nobody", "nobody", "his mother"])
    temper = rng.choice(TEMPERS)
    if a.role in ("chaplain",):
        temper = "pious"
    if a.role in ("politruk",):
        temper = "keen"
    faith = rng.choices([f for f, _ in FAITH.get(nat, [("", 1)])], [w for _, w in FAITH.get(nat, [("", 1)])])[0]
    hope = rng.choice(HOPES.get(nat) or ["go home"]).format(partner=partner)
    lf = {
        "age": age, "town": town, "trade": rng.choice(TRADES.get(nat) or TRADES["usa"]),
        "family": fam, "partner": partner if fam in ("married", "engaged", "a girl") else "",
        "kids": kids, "temper": temper, "faith": faith, "hope": hope,
        "smoker": rng.random() < 0.78, "drinker": rng.random() < 0.35,
        "souvenirs": rng.random() < {"usa": 0.55, "uk": 0.3, "ussr": 0.45, "canada": 0.35}.get(nat, 0.12),
        "nick": _nick(a, rng, age, town, temper),
    }
    a.life = lf
    return lf


def _nick(a, rng, age, town, temper):
    if a.nation not in ("usa", "uk", "canada", "australia", "newzealand") or rng.random() < 0.6:
        return ""
    if a.role == "medic":
        return "Doc"
    if "Texas" in town:
        return "Tex"
    if town == "Brooklyn":
        return "Brooklyn"
    if age >= 30:
        return "Pops"
    if age <= 18:
        return "Kid"
    return {"pious": "Deacon", "joker": "Lucky", "hard": "Moose", "quiet": "Mouse", "cynical": "Smiley"}.get(temper, "")


def call_name(a) -> str:
    """What his mates shout: the nickname, or the surname."""
    nick = life(a)["nick"]
    return nick or a.last_name


# ============================================================================ what he thinks of you
def opinion(game, a) -> float:
    op = a.ai.get("op")
    if op is not None:
        return op
    p = game.player
    if p is None:
        return 0.0
    if a.side != p.side:
        op = -10.0 if a.state == "surrendered" else -35.0
    else:
        op = 0.0
        if a.squad is not None and a.squad is p.squad:
            op = 8.0 + max(-15.0, min(15.0, getattr(game.duty, "rep", 0) / 2))
    op += {"cheerful": 6, "grim": -4, "cynical": -3, "keen": 2}.get(life(a)["temper"], 0)
    a.ai["op"] = op
    return op


def like(game, a, delta, why=None):
    """He thinks better (or worse) of you - and remembers why."""
    a.ai["op"] = max(-100.0, min(100.0, opinion(game, a) + delta))
    if why:
        mem = a.ai.setdefault("mem", [])
        if why not in mem:
            mem.append(why)
            del mem[:-6]


def feeling(game, a) -> str:
    op = opinion(game, a)
    return "would die for you" if op > 60 else "likes you" if op > 25 else "gets on with you" if op > 5 else \
        "doesn't know you" if op > -10 else "doesn't like you" if op > -40 else "hates you"


# ============================================================================ his mate
def buddy(game, a):
    """His buddy in the section (the man he looks out for, and who looks out for him), or None."""
    bid = a.ai.get("buddy")
    sq = a.squad
    if bid is None and sq is not None and not a.is_player:
        men = sorted((m for m in sq.members if m.alive and not m.is_player and m.ai.get("buddy") is None),
                     key=lambda m: m.id)
        for i in range(0, len(men) - 1, 2):
            men[i].ai["buddy"], men[i + 1].ai["buddy"] = men[i + 1].id, men[i].id
        bid = a.ai.get("buddy")
    if bid is None:
        return None
    return game.actor_by_id(bid) if hasattr(game, "actor_by_id") else next((o for o in game.actors if o.id == bid), None)


# ============================================================================ what things are worth to him
# base worth, in cigarettes: what a thing fetched between soldiers
BASE = {"cigarettes": 20, "chocolate": 6, "ration": 5, "flask": 18, "watch": 60, "lighter": 12, "medal": 25,
        "flag": 45, "money": 0.05, "cards": 4, "harmonica": 10, "gum": 2, "stimulant": 8, "canteen": 6,
        "binoculars": 70, "compass": 20, "torch": 6, "wirecutters": 5, "map": 15, "whistle": 3, "shave": 4,
        "sewing": 3, "camera": 80, "newspaper": 1}
PERSONAL = {"letter", "photo", "dogtags", "document", "rosary", "ring", "charm", "orders", "dispatches", "papers",
            "cover_papers", "code", "film", "brassard", "bible"}
KIND = {"grenade": 6, "medical": 8, "mag": 5, "clip": 3, "ammo": 3, "melee": 10, "armor": 6, "explosive": 8,
        "container": 5, "gun": 30}
SOUVENIR_GUNS = {"p08", "p38", "ppk", "type14", "type94", "tt33", "m1911", "welrod", "hi_power"}


def personal(it) -> bool:
    return it.t.kind == "tool" and it.t.tool in PERSONAL


def tradeable(a, it) -> bool:
    """His to part with: not what he's holding, wearing or fighting with, not his letters and his tags."""
    inv = a.invent
    if it is a.weapon or it in inv.slots.values() or personal(it) or it.t.kind == "corpse":
        return False
    if it.data and it.data.get("live") is not None:
        return False
    return True


def worth(game, a, it, giving=False) -> float:
    """What this is worth to him, in cigarettes.  giving: what he'd want for it (a little more, always)."""
    t = it.t
    lf = life(a)
    tool = t.tool if t.kind == "tool" else None
    if personal(it):
        return 1e6 if giving else 0.0
    v = BASE.get(tool, KIND.get(t.kind, 4)) if tool else KIND.get(t.kind, 4)
    if tool == "money":
        v = BASE["money"] * max(1, it.count)
    if tool == "cigarettes":
        v = BASE["cigarettes"] * max(1, it.uses) / 20
        if lf["smoker"]:
            v *= 2.5 if a.find(lambda i: i.t.tool == "cigarettes" and i is not it) is None else 1.4
        else:
            v *= 0.9                        # (still worth something: everyone else smokes)
    if tool == "flask" and lf["drinker"]:
        v *= 2.2
    if t.kind in ("mag", "clip", "ammo"):
        w = a.weapon
        fits = w is not None and w.t.kind == "gun" and t.cal and t.cal == w.t.cal
        if fits:
            spare = sum(1 for i in a.inv if i.t.kind in ("mag", "clip", "ammo") and i.t.cal == t.cal and i is not it)
            v *= 4.0 if spare <= 1 else 2.0 if spare <= 3 else 1.0
        else:
            v *= 0.3
    if t.kind == "grenade":
        v *= 1.5 if game.turn - getattr(a.squad, "last_contact", -9999) < 600 else 1.0
    if t.kind == "medical":
        v *= 2.0 if a.body.wounds else 1.2
    # souvenirs: the enemy's pistols, medals, flags, swords, watches - what men went through pockets for
    enemy_made = bool(t.nations) and a.nation not in t.nations
    if lf["souvenirs"] and enemy_made and (t.id in SOUVENIR_GUNS or tool in ("medal", "flag", "watch") or
                                           t.id in ("katana", "dadao", "kampfmesser")):
        v *= 3.0 if not (a.nation == "ussr" and tool == "watch") else 5.0
    elif t.kind == "gun" and t is not getattr(a.weapon, "t", None):
        v *= 0.4 if t.weight > 3 else 0.8             # (another rifle is only weight)
    if giving:
        v *= 1.15 + (0.35 if lf["temper"] in ("hard", "cynical") else 0.0)
    return max(0.1, v)


def deal(game, a, give, get, favour=0.0) -> bool:
    """Would he hand over `give` (his) for `get` (the other man's)?  favour: how much he thinks of the other
    man (-100..100), which makes a friend generous and a stranger careful."""
    if not tradeable(a, give):
        return False
    return worth(game, a, get) * (1 + favour / 250) >= worth(game, a, give, giving=True)


def wants(game, a, n=3) -> list[str]:
    """The kinds of thing he'd trade for, most wanted first (words, for when he's asked)."""
    lf = life(a)
    out = []
    if lf["smoker"] and a.find(lambda i: i.t.tool == "cigarettes") is None:
        out.append("smokes")
    w = a.weapon
    if w is not None and w.t.kind == "gun" and w.t.cal:
        spare = sum(1 for i in a.inv if i.t.kind in ("mag", "clip", "ammo") and i.t.cal == w.t.cal)
        if spare <= 2:
            out.append(f"ammunition for his {w.t.name}")
    if a.body.wounds and a.medical("bandage") is None:
        out.append("a field dressing")
    if lf["drinker"] and a.find(lambda i: i.t.tool == "flask") is None:
        out.append("something to drink")
    if lf["souvenirs"]:
        out.append("a Luger, a watch or a flag" if a.nation != "ussr" else "a watch - any watch")
    if not out:
        out.append("chocolate")
    return out[:n]


def name_of_item(it) -> str:
    """For the log: 'a pack of Lucky Strikes', 'a Walther P38'."""
    t = it.t
    nm = t.name
    if t.tool == "cigarettes":
        nm = nm.replace("pack of ", "").replace("Pack of ", "")
        return f"a pack of {nm}" if it.uses >= 15 else f"some {nm}"
    if t.kind in ("mag", "clip", "ammo"):
        return "a clip" if t.kind == "clip" or "clip" in t.id else "a magazine" if t.kind == "mag" else "some rounds"
    if "(" in nm:
        nm = nm.split("(")[0].strip()
    return nm if t.kind == "tool" and nm[:1].isupper() and " " not in nm else f"a {nm}" if nm[:1].lower() not in \
        "aeiou" else f"an {nm}"


def spoken(it, lg) -> str:
    """What a man calls it, in his own language (data/chatter.NOUN)."""
    from .data.chatter import NOUN
    t = it.t
    tool = t.tool if t.kind == "tool" else None
    cat = {"cigarettes": "smokes", "ration": "food", "chocolate": "sweet", "flask": "drink", "watch": "watch",
           "lighter": "lighter", "money": "money", "medal": "medal", "flag": "flag", "binoculars": "binoculars",
           "canteen": "water"}.get(tool)
    if cat is None:
        cat = {"mag": "ammo", "clip": "ammo", "ammo": "ammo", "grenade": "grenade", "melee": "knife"}.get(t.kind)
    if cat is None and t.kind == "medical":
        cat = "morphine" if t.id == "morphine" else "dressing"
    if cat is None and t.kind == "gun" and t.cat == "pistol":
        cat = "pistol"
    if tool == "ration" and t.id in ("chocolate", "d_ration", "schokakola"):
        cat = "sweet"
    words = NOUN.get(lg) or NOUN["en"]
    if cat is None and lg == "en":
        return name_of_item(it)
    return words.get(cat or "thing", words["thing"])
