"""Skills: what a man can actually do.

Every soldier has a dozen skills from 0 (never done it) to 10 (as good as anyone gets).  They start
as a roll around his general training - so any man might turn out a fine shot or a natural at
creeping about - and then his job and his unit put a floor under the ones they drilled into him: a
sniper can stalk and shoot, an agent can pass unseen and speak the language, a medic can close a
wound, an engineer knows explosives, a commando can do most of it.  They improve, slowly, with use.

The numbers matter where the skill is used: marksmanship in the aim, gunnery on the guns and the
mortars, stealth in how easily he's noticed, observation in how quickly he notices, melee hand to
hand, first aid over a wound, demolitions with a charge, driving at the wheel, radio when calling
fire, leadership in the men round him, fitness in his wind, languages when he has to pass for a
local or tell the enemy to put his hands up.
"""
from __future__ import annotations

SKILLS = {
    "construction": ("Field engineering", "Digging, surveying, building cover and organizing work parties."),
    "marksmanship": ("Marksmanship", "Rifles, pistols and machine guns: how steady the aim, how fast it's built."),
    "gunnery": ("Gunnery", "Tank and field guns, mortars: laying, ranging, the next round on target."),
    "stealth": ("Stealth", "Moving and lying unseen: fieldcraft, silence, the patience to stay still."),
    "observation": ("Observation", "Seeing the man in the hedge before he sees you."),
    "melee": ("Hand to hand", "Bayonet, knife, rifle butt and fists: the fight at arm's length."),
    "first_aid": ("First aid", "Dressings, tourniquets, morphine - and, with training, much more."),
    "demolitions": ("Demolitions", "Charges, mines and booby traps: setting them fast, and living to do it again."),
    "driving": ("Driving", "Anything with an engine, over any ground."),
    "radio": ("Radio and fire calls", "Using the set, reading the map, calling the guns onto the right field."),
    "leadership": ("Leadership", "Men steadier for having you there, orders carried out faster."),
    "fitness": ("Fitness", "Wind, strength, load: how far and how fast before you're done."),
    "languages": ("Languages", "Passing for a local; telling the enemy to surrender in words he knows."),
}
WORDS = [(1.0, "untrained"), (2.5, "a beginner"), (4.0, "adequate"), (5.5, "competent"), (7.0, "skilled"),
         (8.5, "expert"), (10.1, "a master")]

# what each job's training puts a floor under (and how high)
ROLE_SKILLS = {
    "rifleman": {"marksmanship": 4, "fitness": 4},
    "smg_gunner": {"marksmanship": 3.5, "melee": 4, "fitness": 4},
    "lmg_gunner": {"marksmanship": 5, "fitness": 5},
    "lmg_assistant": {"marksmanship": 3.5, "fitness": 5},
    "hmg_gunner": {"gunnery": 5, "marksmanship": 4},
    "hmg_assistant": {"gunnery": 3.5, "fitness": 5},
    "squad_leader": {"leadership": 5, "marksmanship": 4.5, "radio": 3, "observation": 4},
    "platoon_sergeant": {"leadership": 6, "marksmanship": 5, "observation": 5, "radio": 4},
    "first_sergeant": {"leadership": 6.5, "radio": 4},
    "sergeant_major": {"leadership": 7, "radio": 4},
    "officer": {"leadership": 5.5, "radio": 5.5, "observation": 4},
    "company_commander": {"leadership": 6, "radio": 6},
    "sniper": {"marksmanship": 7.5, "stealth": 7, "observation": 7, "fitness": 5},
    "engineer": {"demolitions": 7, "fitness": 4.5, "construction": 6},
    "seabee": {"construction": 7, "demolitions": 5, "fitness": 5},
    "flamethrower": {"demolitions": 4, "fitness": 5},
    "medic": {"first_aid": 6.5, "fitness": 4},
    "surgeon": {"first_aid": 9.5},
    "radioman": {"radio": 7},
    "mortarman": {"gunnery": 6},
    "artilleryman": {"gunnery": 6, "fitness": 4},
    "at_soldier": {"marksmanship": 4.5, "stealth": 4},
    "tank_crew": {"gunnery": 6, "driving": 6, "radio": 4},
    "agent": {"stealth": 7.5, "languages": 8, "radio": 6, "observation": 6, "melee": 5.5},
    "partisan": {"stealth": 6, "observation": 5, "demolitions": 4, "fitness": 5},
    "pilot": {"observation": 5, "radio": 4},
    "fighter_pilot": {"observation": 6, "radio": 4, "gunnery": 5},
    "bomber_pilot": {"observation": 5, "radio": 5},
    "bombardier": {"gunnery": 6},
    "air_gunner": {"gunnery": 5.5, "observation": 5},
    "sailor": {"fitness": 5},
    "petty_officer": {"leadership": 5, "gunnery": 4},
    "deck_officer": {"leadership": 5, "radio": 5},
    "ship_captain": {"leadership": 7, "radio": 5},
    "motor_sergeant": {"driving": 7},
    "armourer": {"marksmanship": 5},
    "mp": {"melee": 5, "observation": 5},
    "intel": {"languages": 6, "observation": 5, "radio": 5},
    "politruk": {"leadership": 5},
}
# the special units: most of it, and hard
UNIT_SKILLS = {
    "sas": {"stealth": 7, "melee": 6.5, "demolitions": 6.5, "marksmanship": 6.5, "fitness": 7.5, "radio": 5},
    "commando": {"stealth": 6.5, "melee": 7, "demolitions": 6, "marksmanship": 6, "fitness": 7.5},
    "rangers": {"stealth": 5.5, "melee": 6, "demolitions": 5, "marksmanship": 6, "fitness": 8},
    "brandenburg": {"stealth": 7, "languages": 7, "melee": 6, "demolitions": 5.5, "fitness": 6.5},
    "oss": {"stealth": 7, "languages": 6.5, "radio": 7, "demolitions": 6, "melee": 5.5},
    "jedburgh": {"stealth": 7, "languages": 7, "radio": 7.5, "demolitions": 6.5, "leadership": 6},
    "lrdg": {"stealth": 6, "driving": 8, "observation": 7, "radio": 6, "fitness": 6.5},
    "chindits": {"stealth": 6, "fitness": 8, "demolitions": 5, "first_aid": 4},
    "raiders": {"stealth": 6, "melee": 6.5, "fitness": 7.5, "marksmanship": 6},
    "razvedka": {"stealth": 7.5, "observation": 7, "melee": 6.5, "languages": 4},
    "kempeitai": {"observation": 6.5, "languages": 5, "melee": 6},
    "night_witches": {"observation": 6},
    "fallschirmjager": {"marksmanship": 5.5, "fitness": 7, "melee": 5},
    "airborne": {"marksmanship": 5.5, "fitness": 7, "melee": 5},
}
TRAIT_SKILLS = {"crack_shot": {"marksmanship": 2.0}, "shaky": {"marksmanship": -2.0}, "brawler": {"melee": 2.0},
                "camouflaged": {"stealth": 2.0}, "strong": {"fitness": 2.0}, "clumsy": {"stealth": -2.0},
                "veteran": {"marksmanship": 1.0, "observation": 1.0, "stealth": 0.8, "first_aid": 0.8, "melee": 0.5},
                "green": {"marksmanship": -1.0, "observation": -1.0, "stealth": -1.0}}


def word(v: float) -> str:
    for top, w in WORDS:
        if v < top:
            return w
    return WORDS[-1][1]


def roll(rng, a):
    """A new man's skills: a roll around his general training for each, then his job's and his unit's floors
    (reached with a little spread of their own), then his traits."""
    base = getattr(a, "skill", 5.0)
    s = {}
    for k in SKILLS:
        s[k] = rng.gauss(base * 0.55, 1.6)
    for table in (ROLE_SKILLS.get(a.role, {}), UNIT_SKILLS.get(a.__dict__.get("unit_type") or "", {})):
        for k, floor in table.items():
            s[k] = max(s[k], floor + rng.gauss(0, 0.8))
    for t in getattr(a, "traits", ()) or ():
        for k, d in TRAIT_SKILLS.get(t, {}).items():
            s[k] += d
    # a native speaker's languages are the enemy's - here: the tongues he'd need behind the lines
    for k in s:
        s[k] = round(max(0.0, min(10.0, s[k])), 1)
    a.skills = s
    return s


def level(a, k) -> float:
    """His skill (a save from before skills: worked out from his training)."""
    s = a.__dict__.get("skills") if hasattr(a, "__dict__") else None
    if s is None:
        base = getattr(a, "skill", 5.0)
        floor = ROLE_SKILLS.get(getattr(a, "role", ""), {}).get(k, 0)
        return max(base * 0.6, floor)
    return s.get(k, 3.0)


def use(game, a, k, amount=1.0):
    """Practice: a little better each time, less so the better he is.  The player hears when it tells."""
    s = a.__dict__.get("skills")
    if s is None:
        return
    old = s.get(k, 3.0)
    if old >= 10:
        return
    gain = 0.004 * amount * (11 - old) / 6
    new = min(10.0, old + gain)
    s[k] = new
    if a.is_player and word(new) != word(old):
        game.msg(f"Your {SKILLS[k][0].lower()} has come on: you're {word(new)} now.", "good")


# ---------------------------------------------------------------- what they do (small helpers the systems use)
def stealth_mult(a) -> float:
    """On the chance of being noticed: 1.25 for a clumsy novice, about 0.95 at competent, 0.65 for a master."""
    return max(0.6, 1.25 - level(a, "stealth") * 0.06)


def observe_mult(a) -> float:
    """On how quickly he notices things: 0.8 untrained, 1.0 competent, 1.3 for a master."""
    return 0.8 + level(a, "observation") * 0.05


def fitness_mult(a) -> float:
    """On how fast he tires: 1.2 unfit, 1.0 competent, 0.75 for the fittest."""
    return max(0.72, 1.25 - level(a, "fitness") * 0.05)
