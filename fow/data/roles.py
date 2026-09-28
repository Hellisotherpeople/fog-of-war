"""Soldier roles, kit generation and squad templates."""
from __future__ import annotations

import random

from .items import HELMETS, ITEMS, ammo_id
from .nations import NATIONS, equip_sources

ROLES = {
    "rifleman": dict(name="Rifleman", desc="The backbone of every army."),
    "squad_leader": dict(name="Squad leader", desc="Leads a squad. Your men look to you."),
    "lmg_gunner": dict(name="Machine gunner", desc="Carries the squad's light machine gun."),
    "lmg_assistant": dict(name="Assistant gunner", desc="Feeds the gun and carries its ammunition."),
    "smg_gunner": dict(name="Assault trooper", desc="Sub-machine gunner for close work."),
    "at_soldier": dict(name="Anti-tank soldier", desc="Hunts tanks at suicidal ranges."),
    "medic": dict(name="Medic", desc="Keeps the wounded alive. Everyone will be shouting for you."),
    "quartermaster": dict(name="Quartermaster", desc="Counts everything twice. Gives nothing away."),
    "intel": dict(name="Intelligence officer", desc="Reads what the dead carried."),
    "surgeon": dict(name="Battalion surgeon", desc="An officer with a scalpel at the aid station. The line brings "
                    "you what's left of its men; you decide who lives."),
    "radioman": dict(name="Radio operator", desc="Carries the radio - and a target on his back."),
    # behind the line: the people who run a base (fow/base.py)
    "adjutant": dict(name="Adjutant", desc="The commander's staff officer: postings, orders, paperwork, and "
                     "who goes where next."),
    "clerk": dict(name="Company clerk", desc="Pay, mail, the morning report and your service record."),
    "mp": dict(name="Military policeman", desc="Traffic, prisoners, stragglers and deserters. Nobody's friend."),
    "armourer": dict(name="Armourer", desc="Keeps the battalion's weapons working."),
    "cook": dict(name="Cook", desc="The field kitchen. Hot food a mile behind the line is worth a medal."),
    "chaplain": dict(name="Chaplain", desc="Unarmed, in the line and at the aid station: the dying, the "
                     "burials, the letters home."),
    "politruk": dict(name="Political officer", desc="The Party's man in the unit: morale, reading, and a notebook of "
                     "who said what."),
    "motor_sergeant": dict(name="Motor sergeant", desc="The motor pool: trucks, jeeps, and the mechanics who "
                           "keep them running."),
    "ops_officer": dict(name="Air operations officer", desc="The airfield's briefings: who flies, where, and "
                        "when."),
    "port_officer": dict(name="Port director", desc="The naval base: berths, boats, and which ship a sailor "
                         "belongs to."),
    "platoon_sergeant": dict(name="Platoon sergeant", desc="The lieutenant's right hand and the platoon's memory. "
                             "When he falls, the platoon is yours."),
    "first_sergeant": dict(name="Company first sergeant", desc="Top kick. The company's senior NCO: ammunition, "
                           "casualties, discipline, and every private's fear."),
    "sergeant_major": dict(name="Battalion sergeant major", desc="The senior soldier of the battalion. Officers "
                           "come and go; you run the place."),
    "officer": dict(name="Platoon officer", desc="Commands the platoon. Can call the guns."),
    "sniper": dict(name="Sniper", desc="Patient, hated, hunted by both sides."),
    "engineer": dict(name="Combat engineer", desc="Demolitions, wire, mines and bunkers."),
    "mortarman": dict(name="Mortarman", desc="Lobs bombs at things you can't see."),
    "artilleryman": dict(name="Artilleryman", desc="Serves a field gun a mile behind the line. Fire missions come "
                         "down the wire; you lay the gun and fire at men you will never see."),
    "hmg_gunner": dict(name="Heavy MG gunner", desc="Crews the tripod machine gun."),
    "hmg_assistant": dict(name="Heavy MG loader", desc="Carries belts and the tripod."),
    "flamethrower": dict(name="Flamethrower operator", desc="Burns out bunkers. Nobody takes you prisoner."),
    "tank_crew": dict(name="Tank crewman", desc="Fights from inside an armoured vehicle."),
    "agent": dict(name="Agent", desc="Civilian clothes, forged papers, a pistol you pray you won't need. "
                  "Behind their lines, you are nobody - until someone looks closely."),
    "pilot": dict(name="Pilot", desc="Flies fighters or bombers. On the ground, a long way from home."),
    "partisan": dict(name="Partisan", desc="No uniform, a captured rifle, the forest for a home. Shot if taken."),
    # the air
    "fighter_pilot": dict(name="Fighter pilot", desc="Alone in a single-seater: sweeps, interceptions, escorts. "
                          "Five victories makes you an ace; most never get one.", service="air"),
    "bomber_pilot": dict(name="Bomber pilot", desc="Holds a bomber steady through flak and fighters while the "
                         "crew does its work. The crew's lives are in your hands.", service="air"),
    "bombardier": dict(name="Bomb aimer", desc="Lies in the nose over the bombsight: 'left, left... steady... "
                       "bombs gone.'", service="air"),
    "air_gunner": dict(name="Air gunner", desc="A turret, two machine guns and a view of the fighters coming in. "
                       "The shortest life expectancy in the air force.", service="air"),
    # the sea
    "sailor": dict(name="Sailor", desc="On a gun mount or a damage-control party. When the ship's hit, you fight "
                   "the fires; when she sinks, you swim.", service="navy"),
    "petty_officer": dict(name="Petty officer", desc="Captain of a gun, chief of a party. The backbone of the "
                          "navy.", service="navy"),
    "deck_officer": dict(name="Watch officer", desc="Officer of the deck: the ship is yours for the watch.",
                         service="navy"),
    "ship_captain": dict(name="Ship's captain", desc="Command at sea: destroyer, cruiser or battleship, by your "
                         "rank. Helm, guns, torpedoes - and every man aboard.", service="navy"),
    "sub_commander": dict(name="Submarine commander", desc="Periscope depth, a firing solution, and then the "
                          "depth charges.", service="navy"),
    "admiral": dict(name="Admiral", desc="A task force or a fleet: carriers, battleships, screens. You launch the "
                    "strikes and signal the line.", service="navy"),
    "volkssturm": dict(name="Volkssturm militiaman", desc="Too old or too young. Given a Panzerfaust."),
    # senior command: the player starts at the head of a formation
    "company_commander": dict(name="Company commander", desc="A captain with three platoons, a radio and "
                              "not enough of anything else.", command=True),
    "battalion_commander": dict(name="Battalion commander", desc="Every squad on this field answers to you. "
                                "So does the mortar platoon, when you can raise it.", command=True),
    "regiment_commander": dict(name="Regimental commander", desc="A colonel. You fight this sector and plan "
                               "the next one on the war map.", command=True),
    "brigade_commander": dict(name="Brigade commander", desc="A one-star. Battalions become pins on a map "
                              "- until the map is the ground you're standing on.", command=True),
    "division_commander": dict(name="Division commander", desc="Two stars. You move regiments across the "
                               "theatre and your staff car is a fine target.", command=True),
    "corps_commander": dict(name="Corps commander", desc="Three stars. Divisions, corps artillery, and the "
                            "front two sectors deep.", command=True),
    "army_commander": dict(name="Army commander", desc="Four stars. You command the whole front. You are "
                           "still one man in a ditch when the shells come.", command=True),
    "army_group_commander": dict(name="Five-star commander", desc="Field marshal, General of the Army, "
                                 "Marshal of the Soviet Union. The theatre is yours. Try not to visit it.",
                                 command=True),
}
# the ranks a man in each job could hold (common 0-18 scale): (lowest, highest)
#   0 private .. 2 corporal, 3-7 sergeants to sergeant major, 8-9 lieutenants, 10 captain, 11 major ...
ROLE_GRADES = {
    "rifleman": (0, 2), "smg_gunner": (0, 3), "lmg_gunner": (1, 3), "lmg_assistant": (0, 2), "at_soldier": (0, 3),
    "medic": (0, 5), "radioman": (0, 4), "sniper": (0, 5), "engineer": (0, 4), "mortarman": (0, 4),
    "artilleryman": (0, 4),
    "hmg_gunner": (1, 4), "hmg_assistant": (0, 2), "flamethrower": (0, 3), "volkssturm": (0, 3),
    "tank_crew": (0, 12), "squad_leader": (2, 4), "platoon_sergeant": (4, 5), "first_sergeant": (6, 6),
    "sergeant_major": (7, 7), "officer": (8, 9), "quartermaster": (3, 10), "intel": (8, 12), "surgeon": (10, 12),
    "agent": (0, 12), "pilot": (3, 14), "partisan": (0, 10),
    "adjutant": (9, 10), "clerk": (2, 3), "mp": (1, 3), "armourer": (3, 4), "cook": (2, 3), "chaplain": (9, 10),
    "politruk": (8, 10),
    "motor_sergeant": (4, 5), "ops_officer": (10, 11), "port_officer": (10, 11),
    "fighter_pilot": (3, 13), "bomber_pilot": (3, 13), "bombardier": (3, 11), "air_gunner": (2, 9),
    "sailor": (0, 2), "petty_officer": (3, 7), "deck_officer": (8, 10), "ship_captain": (11, 14),
    "sub_commander": (10, 12), "admiral": (14, 18),
    "company_commander": (9, 11), "battalion_commander": (11, 12), "regiment_commander": (13, 13),
    "brigade_commander": (14, 14), "division_commander": (14, 15), "corps_commander": (16, 16),
    "army_commander": (17, 17), "army_group_commander": (18, 18),
}

SERVICE_ROLES = {
    "air": ["fighter_pilot", "bomber_pilot", "bombardier", "air_gunner"],
    "navy": ["sailor", "petty_officer", "deck_officer", "ship_captain", "sub_commander", "admiral"],
}


def service_of(role) -> str:
    for sv, rs in SERVICE_ROLES.items():
        if role in rs:
            return sv
    return "army"


COMMAND_ROLE_LIST = ["company_commander", "battalion_commander", "regiment_commander", "brigade_commander",
                     "division_commander", "corps_commander", "army_commander", "army_group_commander"]

PLAYER_ROLE_WEIGHTS = {
    "rifleman": 34, "lmg_gunner": 7, "lmg_assistant": 5, "smg_gunner": 7, "squad_leader": 6,
    "officer": 3, "medic": 5, "radioman": 4, "at_soldier": 6, "sniper": 4, "engineer": 4,
    "mortarman": 3, "hmg_gunner": 3, "flamethrower": 2, "tank_crew": 7, "artilleryman": 2,
}

SQUAD_SIZE = {"usa": 10, "uk": 8, "canada": 8, "australia": 8, "newzealand": 8, "india": 8,
              "ussr": 8, "france": 9, "poland": 9, "china": 9, "germany": 8, "italy": 8,
              "japan": 10, "finland": 8, "hungary": 8, "romania": 8}

PERSONAL = ["letter", "photo", "rosary", "harmonica", "lucky_coin", "cards", "bible"]


def _available(nation: str, year: float, kind: tuple, cats: tuple) -> list:
    srcs = equip_sources(nation, year)
    out = []
    for src in srcs:
        for t in ITEMS.values():
            if t.kind not in kind or (cats and t.cat not in cats) or t.freq <= 0:
                continue
            if src not in t.nations:
                continue
            y0, y1 = t.years
            if not (y0 <= year < y1):
                continue
            out.append(t)
        if out:
            return out
    return out


def pick(rng: random.Random, nation: str, year: float, cats, kind=("gun",)) -> str | None:
    if isinstance(cats, str):
        cats = (cats,)
    for cat in cats:
        pool = _available(nation, year, kind, (cat,))
        if pool:
            weights = [t.freq for t in pool]
            return rng.choices(pool, weights)[0].id
    return None


def pick_grenade(rng, nation, year, gtypes=("frag", "stick")) -> str | None:
    srcs = equip_sources(nation, year)
    for src in srcs:
        pool = [t for t in ITEMS.values() if t.kind == "grenade" and t.gtype in gtypes
                and src in t.nations and t.years[0] <= year < t.years[1] and t.freq > 0]
        if pool:
            return rng.choices(pool, [t.freq for t in pool])[0].id
    return None


def pick_explosive(rng, nation, year, charges) -> str | None:
    srcs = equip_sources(nation, year) + [nation]
    for src in srcs:
        pool = [t for t in ITEMS.values() if t.kind == "explosive" and t.charge in charges
                and src in t.nations and t.years[0] <= year < t.years[1] and t.freq > 0]
        if pool:
            return rng.choices(pool, [t.freq for t in pool])[0].id
    return None


from .items_personal import IDS as _PERSONAL_IDS  # noqa: E402


def _personal(rng, nation, year, tools):
    """One of this army's own things of these kinds (items_personal): their rations, their drink, their charms."""
    pool = [t for t in ITEMS.values() if t.kind == "tool" and t.tool in tools and t.freq == 0 and nation in t.nations
            and t.years[0] <= year < t.years[1] and t.id in _PERSONAL_IDS]
    return rng.choice(pool).id if pool else None


def _mags(item_id: str, n: float) -> tuple[str, int] | None:
    t = ITEMS[item_id]
    if not t.cal:
        return None
    per = max(1, t.mag)
    return ammo_id(t.cal), int(per * n)


COMMONWEALTH = ("uk", "canada", "australia", "newzealand", "india")
# where the Japanese were the enemy, and the red cross protected nobody
PACIFIC_THEATRES = {"guadalcanal42", "iwojima45", "okinawa45", "kohima44"}
# the knife a man might carry besides whatever he was issued: (item, chance)
BELT_KNIFE = {"germany": ("kampfmesser", 0.25), "ussr": ("nr40", 0.12), "finland": ("puukko", 0.8),
              "india": ("kukri", 0.3), "uk": ("clasp_knife", 0.5), "canada": ("clasp_knife", 0.5),
              "australia": ("clasp_knife", 0.5), "newzealand": ("clasp_knife", 0.5)}


def build_kit(rng: random.Random, nation: str, year: float, role: str, *, para: bool = False,
              winter: bool = False, player: bool = False, pacific: bool = False) -> dict:
    """Return {'wield': id, 'sling': id|None, 'items': [(id, count)], 'helmet': id}.

    Nobody goes to war with nothing: every man has at least what his army really gave a man in his
    job - a rifle, a pistol, a knife - except where the job itself was to go unarmed (see medics)."""
    doc = NATIONS[nation]["doctrine"]
    items: list[tuple[str, int]] = []
    wield = None
    sling = None

    def add(iid, n=1):
        if iid and n > 0:
            items.append((iid, n))

    def add_ammo(gun_id, mags):
        if gun_id:
            m = _mags(gun_id, mags)
            if m:
                add(*m)

    def service_rifle():
        # late war Germany hands out some assault rifles, everyone gets SMGs by doctrine
        if nation == "germany" and year >= 1944.5 and rng.random() < 0.15:
            g = pick(rng, nation, year, ("assault", "rifle"))
        elif rng.random() < doc.get("smg_ratio", 0):
            g = pick(rng, nation, year, ("smg", "rifle"))
        else:
            g = pick(rng, nation, year, ("rifle", "carbine", "smg"))
        return g

    grenades = 0
    if role == "rifleman":
        wield = service_rifle()
        add_ammo(wield, rng.uniform(5, 9))
        grenades = rng.randint(1, 3)
        if nation == "germany" and year >= 1944.3 and rng.random() < 0.35:
            add(pick(rng, nation, year, "at_disposable"))
    elif role == "volkssturm":
        wield = pick(rng, nation, year, ("rifle",)) if rng.random() < 0.6 else None
        add_ammo(wield, rng.uniform(1, 3))
        pf = pick(rng, nation, year, "at_disposable")
        if pf:
            add(pf, rng.randint(1, 2))
            if not wield:
                wield = pf
        grenades = rng.randint(0, 1)
    elif role == "smg_gunner":
        wield = pick(rng, nation, year, ("smg", "assault", "rifle"))
        add_ammo(wield, rng.uniform(4, 7))
        grenades = rng.randint(2, 4)
    elif role in ("platoon_sergeant", "first_sergeant", "sergeant_major"):
        wield = pick(rng, nation, year, ("smg", "carbine", "rifle"))
        add_ammo(wield, rng.uniform(3, 5))
        add("whistle")
        add("watch")
        add("binoculars" if role != "platoon_sergeant" or rng.random() < 0.5 else None)
        add("map" if role != "platoon_sergeant" else None)
        grenades = rng.randint(1, 3)
    elif role == "squad_leader":
        if nation in ("japan",) or (nation in ("france", "poland") and year < 1941):
            wield = pick(rng, nation, year, ("rifle",))
        elif nation == "germany" and year >= 1944 and rng.random() < 0.3:
            wield = pick(rng, nation, year, ("assault", "smg"))
        elif rng.random() < 0.75:
            wield = pick(rng, nation, year, ("smg", "rifle"))
        else:
            wield = pick(rng, nation, year, ("rifle", "carbine"))
        add_ammo(wield, rng.uniform(4, 7))
        grenades = rng.randint(2, 3)
        add("binoculars" if rng.random() < 0.5 else None)
        add("whistle")
        add("compass")
        add("watch")
        add("map" if rng.random() < 0.7 else None)
    elif role == "lmg_gunner":
        wield = pick(rng, nation, year, ("lmg", "smg"))
        add_ammo(wield, rng.uniform(3, 5))
        pistol = pick(rng, nation, year, "pistol")
        if pistol and rng.random() < 0.7:
            add(pistol)
            add_ammo(pistol, 2)
        grenades = rng.randint(0, 1)
    elif role == "lmg_assistant":
        wield = service_rifle()
        add_ammo(wield, rng.uniform(3, 5))
        lmg = pick(rng, nation, year, "lmg")
        add_ammo(lmg, rng.uniform(4, 7))
        pistol = pick(rng, nation, year, "pistol")
        if pistol and rng.random() < 0.3:
            add(pistol)
            add_ammo(pistol, 2)
        grenades = rng.randint(1, 2)
    elif role == "hmg_gunner":
        wield = pick(rng, nation, year, ("hmg", "lmg"))
        add_ammo(wield, rng.uniform(2, 3))
        pistol = pick(rng, nation, year, "pistol")
        add(pistol)
        add_ammo(pistol, 2)
    elif role == "hmg_assistant":
        wield = service_rifle()
        add_ammo(wield, rng.uniform(3, 5))
        hmg = pick(rng, nation, year, "hmg")
        add_ammo(hmg, rng.uniform(3, 5))
        grenades = rng.randint(0, 2)
    elif role == "at_soldier":
        at = pick(rng, nation, year, ("at_launcher", "at_disposable", "at_rifle"))
        if at:
            wield = at
            t = ITEMS[at]
            if t.cat == "at_launcher":
                add(ammo_id(t.cal), rng.randint(3, 5))
            elif t.cat == "at_rifle":
                add_ammo(at, rng.uniform(3, 6))
            else:
                add(at, rng.randint(0, 2))
            side = pick(rng, nation, year, ("pistol",)) if t.weight > 10 else \
                pick(rng, nation, year, ("carbine", "rifle"))
            if side:
                if ITEMS[side].cat == "pistol":
                    add(side)
                else:
                    sling = side
                add_ammo(side, 2)
        else:
            wield = service_rifle()
            add_ammo(wield, 5)
        atg = pick_grenade(rng, nation, year, ("at", "gammon", "molotov"))
        if atg:
            add(atg, rng.randint(1, 2))
        mag = pick_explosive(rng, nation, year, ("magnetic", "bundle"))
        if mag and rng.random() < 0.4:
            add(mag)
        grenades = rng.randint(0, 2)
    elif role == "medic":
        # Arms and the red cross.  In Europe and Africa, American and Commonwealth medics went unarmed
        # and trusted the armband (a few carried a pistol anyway).  Against the Japanese, who didn't
        # respect it, they took it off and carried carbines and pistols.  A German Sanitäter was allowed
        # a pistol to defend himself and his wounded; Soviet medics mostly went armed like everyone else.
        western = nation == "usa" or nation in COMMONWEALTH
        pistol = pick(rng, nation, year, "pistol")
        if western and not pacific:
            add("brassard")
            add("clasp_knife" if nation in COMMONWEALTH else None)     # issued to everyone, RAMC too
            if pistol and rng.random() < (0.2 if nation == "usa" else 0.1):
                add(pistol)                            # unofficially, in a pocket
                add_ammo(pistol, 1)
        elif western:
            wield = pick(rng, nation, year, ("carbine", "rifle")) if rng.random() < 0.6 else pistol
            add_ammo(wield, 3)
            if nation == "usa" and year >= 1942.9:
                add("kabar" if rng.random() < 0.5 else None)
        elif nation == "germany":
            add("brassard")
            if pistol and rng.random() < 0.7:
                add(pistol)
                add_ammo(pistol, 1)
        elif nation == "ussr":
            r = rng.random()
            if r < 0.5:
                wield = service_rifle()
                add_ammo(wield, 3)
            elif pistol:
                add(pistol)
                add_ammo(pistol, 2)
            add("brassard" if rng.random() < 0.5 else None)
        elif nation == "japan":
            add("brassard")
            add("bayonet")                             # every Japanese soldier had one on his belt
            if pistol and rng.random() < 0.3:
                add(pistol)
                add_ammo(pistol, 1)
        else:
            add("brassard")
            if pistol and rng.random() < 0.6:
                add(pistol)
                add_ammo(pistol, 1)
            else:
                add("bayonet")
        add("medkit")
        add("bandage", rng.randint(4, 8))
        add("morphine", rng.randint(3, 6))
        add("plasma", rng.randint(0, 2))
        add("tourniquet", 2)
    elif role == "radioman":
        wield = pick(rng, nation, year, ("carbine", "smg", "rifle"))
        add_ammo(wield, rng.uniform(3, 5))
        add("radio_scr300" if "usa" in equip_sources(nation, year) else "radio")
        add("watch")
        grenades = rng.randint(0, 2)
    elif role == "officer":
        if nation == "japan":
            wield = "katana"
            add(pick(rng, nation, year, "pistol"))
            add_ammo("nambu14", 3)
        else:
            wield = pick(rng, nation, year, ("smg", "carbine", "rifle")) if rng.random() < 0.6 \
                else pick(rng, nation, year, ("carbine", "rifle"))
            add_ammo(wield, rng.uniform(3, 5))
            p = pick(rng, nation, year, "pistol")
            add(p)
            add_ammo(p, 2)
        add("binoculars")
        add("map")
        add("compass")
        add("watch")
        add("whistle")
        add("flaregun" if rng.random() < 0.4 else None)
        grenades = rng.randint(1, 2)
    elif role in COMMAND_ROLE_LIST:
        general = COMMAND_ROLE_LIST.index(role) >= 3
        if nation == "japan" and not general:
            wield = "katana"
            add(pick(rng, nation, year, "pistol"))
            add_ammo("nambu14", 2)
        elif general:
            wield = pick(rng, nation, year, "pistol")
            add_ammo(wield, 2)
        else:
            wield = pick(rng, nation, year, ("carbine", "smg", "rifle")) if rng.random() < 0.5 \
                else pick(rng, nation, year, "pistol")
            add_ammo(wield, rng.uniform(2, 4))
            if ITEMS.get(wield) is not None and ITEMS[wield].cat != "pistol":
                p = pick(rng, nation, year, "pistol")
                add(p)
                add_ammo(p, 2)
        add("binoculars")
        add("staff_map" if general or rng.random() < 0.5 else "map")
        add("compass")
        add("watch")
        if not general:
            add("whistle")
            grenades = rng.randint(0, 1)
    elif role == "agent":
        p = pick(rng, nation, year, "pistol")
        wield = None
        add(p)
        add_ammo(p, 1)
        add("forged_papers")
        add("silk_map")
        add("compass")
        add("watch")
        add("cigarettes", 3)
        add("civvies")
    elif role in ("fighter_pilot", "bomber_pilot"):
        p = pick(rng, nation, year, "pistol")
        wield = p
        add_ammo(p, 1)
        add("flight_jacket")
        add("silk_map")
        add("compass")
        add("watch")
    elif role in ("bombardier", "air_gunner"):
        # aircrew flew with a pistol for when they came down: the Americans a .45, the Luftwaffe a
        # Walther or a Sauer; RAF bomber crews often didn't bother
        wield = None
        if nation not in COMMONWEALTH or rng.random() < 0.4:
            p = pick(rng, nation, year, "pistol")
            add(p)
            add_ammo(p, 1)
        add("flight_jacket")
        add("silk_map" if rng.random() < 0.6 else None)
        add("ration")
    elif role in ("sailor", "petty_officer"):
        # small arms live in the ship's armoury; a sailor carries a knife for the lines
        wield = None
        add("rigging_knife")
        add("mae_west")
        add("cigarettes")
    elif role in ("deck_officer", "ship_captain", "sub_commander", "admiral"):
        p = pick(rng, nation, year, "pistol")
        wield = p
        add_ammo(p, 1)
        add("mae_west")
        add("binoculars")
        add("watch")
    elif role == "pilot":
        p = pick(rng, nation, year, "pistol")
        wield = p
        add_ammo(p, 1)
        add("flight_jacket")
        add("silk_map")
        add("compass")
        add("watch")
        add("ration")
    elif role == "partisan":
        # whatever they could get: their own army's rifle, or a dead enemy's
        wield = pick(rng, nation, year, ("rifle", "carbine", "smg")) if rng.random() < 0.7 else service_rifle()
        add_ammo(wield, rng.uniform(2, 4))
        grenades = rng.randint(0, 2)
        add(pick_grenade(rng, nation, year, ("molotov",)) if rng.random() < 0.4 else None, 2)
        add("civvies")
    elif role == "surgeon":
        p = pick(rng, nation, year, "pistol")
        wield = p
        add_ammo(p, 1)
        add("medkit", 2)
        add("surgical_kit")
        add("plasma", 3)
        add("morphine", 6)
        add("bandage", 6)
        add("tourniquet", 2)
        add("watch")
    elif role == "sniper":
        wield = pick(rng, nation, year, ("sniper", "rifle"))
        add_ammo(wield, rng.uniform(6, 10))
        p = pick(rng, nation, year, "pistol")
        if p and rng.random() < 0.5:
            add(p)
            add_ammo(p, 2)
        add("binoculars" if rng.random() < 0.5 else None)
        grenades = rng.randint(0, 1)
        # the sniper's camouflage: what his army gave him (or what he made himself)
        if not winter:
            camo = {"uk": "ghillie", "canada": "ghillie", "australia": "ghillie", "newzealand": "ghillie",
                    "usa": "ghillie" if rng.random() < 0.5 else None, "ussr": "maskhalat", "germany": "tarnjacke",
                    "japan": "foliage_cape", "finland": "maskhalat", "italy": None}.get(nation)
            if camo and rng.random() < 0.8:
                add(camo)
        else:
            add("snow_smock")
    elif role == "engineer":
        wield = pick(rng, nation, year, ("smg", "rifle")) if rng.random() < 0.4 else service_rifle()
        add_ammo(wield, rng.uniform(3, 6))
        add(pick_explosive(rng, nation, year, ("satchel",)), rng.randint(1, 2))
        add("wirecutters")
        b = pick_explosive(rng, nation, year, ("bangalore",))
        if b and rng.random() < 0.25:
            add(b)
        add("mine_detector" if rng.random() < 0.1 else None)
        grenades = rng.randint(2, 4)
    elif role == "mortarman":
        m = pick(rng, nation, year, "mortar")
        if m:
            wield = m
            add(ammo_id(ITEMS[m].cal), rng.randint(3, 6) if ITEMS[m].cal == "m81" else rng.randint(6, 12))
            p = pick(rng, nation, year, "pistol")
            add(p)
            add_ammo(p, 2)
        else:
            wield = service_rifle()
            add_ammo(wield, 5)
    elif role == "flamethrower":
        f = pick(rng, nation, year, "flamer")
        if f:
            wield = f
            p = pick(rng, nation, year, "pistol")
            add(p)
            add_ammo(p, 2)
        else:
            wield = service_rifle()
            add_ammo(wield, 5)
            add(pick_grenade(rng, nation, year, ("molotov",)), 3)
    elif role == "chaplain":
        # chaplains were non-combatants and went unarmed (the Geneva Conventions protected them too)
        add("watch")
    elif role in ("adjutant", "ops_officer", "port_officer", "politruk"):
        p = pick(rng, nation, year, "pistol")
        add(p)
        add_ammo(p, 1)
        add("watch")
        add("map")
    elif role == "artilleryman":
        # a gunner's rifle stays in the gun pit: carbines for the Americans, rifles for everyone else
        wield = pick(rng, nation, year, ("carbine", "rifle")) if nation in ("usa",) else service_rifle()
        add_ammo(wield, 2)
        add("watch" if rng.random() < 0.3 else None)
    elif role in ("clerk", "cook", "armourer", "motor_sergeant"):
        # rear-echelon men had a carbine or a rifle somewhere near them
        wield = pick(rng, nation, year, ("carbine", "rifle")) if rng.random() < 0.6 else \
            pick(rng, nation, year, ("smg", "rifle"))
        add_ammo(wield, 2)
        add("watch" if role in ("clerk", "motor_sergeant") else None)
    elif role == "mp":
        wield = pick(rng, nation, year, ("smg", "carbine", "rifle"))
        add_ammo(wield, 3)
        p = pick(rng, nation, year, "pistol")
        add(p)
        add_ammo(p, 1)
        add("whistle")
    elif role == "tank_crew":
        if rng.random() < 0.5:
            wield = pick(rng, nation, year, ("smg", "pistol"))
        else:
            wield = pick(rng, nation, year, ("pistol", "smg"))
        add_ammo(wield, rng.uniform(2, 4))
    else:
        wield = service_rifle()
        add_ammo(wield, 6)

    # the belt knife: Marines' Ka-Bars in the Pacific, German boot knives, the Finns' puukko, the army
    # clasp knife every Commonwealth soldier was issued
    if role not in ("agent", "sailor", "petty_officer", "medic") and role not in COMMAND_ROLE_LIST[3:]:
        kn = ("kabar", 0.5) if nation == "usa" and pacific and year >= 1942.9 else \
            ("trench_knife", 0.15) if nation == "usa" and year >= 1943 else BELT_KNIFE.get(nation)
        if kn and rng.random() < kn[1]:
            add(kn[0])
    # and nobody is left with nothing: a pistol for a man whose job gave him one, else a bayonet
    armed = wield is not None or any(ITEMS[i].kind in ("gun", "melee") for i, _ in items if i in ITEMS)
    if not armed and role not in ("medic", "chaplain"):
        if role in ("tank_crew", "radioman", "mortarman", "flamethrower", "hmg_gunner") or \
                role in COMMAND_ROLE_LIST or role.endswith(("pilot", "officer", "captain", "commander")):
            p = pick(rng, nation, year, "pistol")
            add(p)
            add_ammo(p, 1)
        else:
            add("bayonet")

    # grenades
    if grenades:
        g = pick_grenade(rng, nation, year)
        add(g, grenades)
    if role in ("rifleman", "smg_gunner", "squad_leader", "engineer") and rng.random() < 0.15:
        add(pick_grenade(rng, nation, year, ("smoke", "wp")))

    # common kit
    add("bandage", 1 + (rng.random() < 0.5))
    if "usa" in equip_sources(nation, year) and rng.random() < 0.7:
        add("sulfa")
    if para or rng.random() < 0.15:
        add("morphine")
    if role not in ("tank_crew", "medic") and rng.random() < 0.65:
        add("shovel")
    add("canteen" if rng.random() < 0.85 else None)
    add((_personal(rng, nation, year, ("ration", "chocolate")) or "ration") if rng.random() < 0.6 else None)
    add((_personal(rng, nation, year, ("cigarettes",)) if rng.random() < 0.3 else None) or
        ("cigarettes" if rng.random() < 0.6 else None))
    add((_personal(rng, nation, year, ("flask",)) or "flask") if rng.random() < 0.12 else None)
    add(_personal(rng, nation, year, ("stimulant",)) if rng.random() < (0.15 if nation == "germany" and year < 1942
                                                                          else 0.04) else None)
    if role not in ("squad_leader", "officer", "radioman") and role not in COMMAND_ROLE_LIST and rng.random() < 0.25:
        add("watch")
    add("dogtags" if nation in ("usa", "uk", "canada", "australia", "newzealand", "germany") else None)
    for _ in range(rng.choice((0, 1, 1, 2, 2, 3))):
        add(_personal(rng, nation, year, ("charm", "flag", "medal", "rosary", "photo", "ring", "watch", "newspaper",
                                           "document", "shave", "sewing", "gum", "lighter"))
            if rng.random() < 0.55 else rng.choice(PERSONAL))
    if role not in ("tank_crew",) and rng.random() < 0.7:
        add("backpack")
    if para:
        g = pick_grenade(rng, nation, year)
        add(g, rng.randint(1, 3))
        add("compass")
        if "uk" in equip_sources(nation, year) and rng.random() < 0.4:
            add("gammon")
        if nation == "germany":
            # Fallschirmjäger jumped with pistols and grenades; long arms came in canisters
            if rng.random() < 0.35 and ITEMS[wield].cat in ("rifle", "lmg", "smg") if wield else False:
                add(wield)
                add_ammo(wield, 0)
                wield = pick(rng, nation, year, "pistol")
                add_ammo(wield, 3)
    if winter:
        coat = 0.12 if nation in ("germany", "italy", "hungary", "romania") and year < 1942.4 else 0.5
        add("winter_coat" if nation in ("ussr", "finland") or rng.random() < coat else None)
        if nation in ("ussr", "finland") and rng.random() < 0.5:
            add("snow_smock")
    helmet = "tanker_helmet" if role == "tank_crew" else HELMETS.get(nation, "soft_cap")
    if role in ("agent", "partisan", "sailor", "petty_officer", "deck_officer", "ship_captain", "sub_commander",
                "admiral"):
        helmet = "soft_cap" if role not in ("ship_captain", "admiral") else "peaked_cap"
    elif role in ("pilot", "fighter_pilot", "bomber_pilot", "bombardier", "air_gunner"):
        helmet = None
    if role in COMMAND_ROLE_LIST[3:] and rng.random() < 0.5:
        helmet = "peaked_cap"
    if nation == "china" and rng.random() < 0.5:
        helmet = "soft_cap"
    if role == "volkssturm":
        helmet = "soft_cap" if rng.random() < 0.6 else helmet
    return dict(wield=wield, sling=sling, items=[i for i in items if i[0]], helmet=helmet)


# ---------------------------------------------------------------- squads

def squad_template(rng: random.Random, nation: str, year: float, kind: str) -> list[str]:
    size = SQUAD_SIZE.get(nation, 8)
    doc = NATIONS[nation]["doctrine"]
    if kind == "rifle":
        roles = ["squad_leader", "lmg_gunner", "lmg_assistant"]
        roles += ["rifleman"] * (size - 3 + rng.randint(-2, 1))
        if rng.random() < doc.get("smg_ratio", 0) * 1.5:
            roles.append("smg_gunner")
        if rng.random() < 0.35:
            roles.append("at_soldier")
        if rng.random() < 0.2:
            roles.append("medic")
        return roles
    if kind == "assault":
        return ["squad_leader"] + ["smg_gunner"] * rng.randint(4, 6) + ["engineer", "rifleman"]
    if kind == "mg":
        return ["hmg_gunner", "hmg_assistant"] + ["rifleman"] * rng.randint(1, 2)
    if kind == "mortar":
        return ["mortarman", "mortarman"] + ["rifleman"] * rng.randint(0, 1)
    if kind == "at":
        return ["at_soldier", "at_soldier", "rifleman"]
    if kind == "hq":
        return ["officer", "radioman", "medic", "rifleman"]
    if kind == "sniper":
        return ["sniper"] + (["rifleman"] if rng.random() < 0.4 else [])
    if kind == "engineer":
        roles = ["squad_leader"] + ["engineer"] * rng.randint(3, 5) + ["rifleman"]
        if rng.random() < 0.4:
            roles.append("flamethrower")
        return roles
    if kind == "volkssturm":
        return ["squad_leader"] + ["volkssturm"] * rng.randint(5, 8)
    if kind == "recon":
        # a patrol: a few men, light, quiet
        return ["squad_leader"] + rng.sample(["rifleman", "rifleman", "smg_gunner", "sniper"], rng.randint(2, 3))
    if kind == "raid":
        # a trench raid or fighting patrol: close-quarter weapons, grenades, a sapper
        return ["squad_leader"] + ["smg_gunner"] * rng.randint(2, 4) + ["engineer"] + ["rifleman"] * rng.randint(1, 2)
    if kind == "commando":
        return ["squad_leader"] + ["smg_gunner"] * rng.randint(2, 3) + ["engineer", "engineer"] + \
            (["sniper"] if rng.random() < 0.5 else ["rifleman"])
    if kind == "partisan":
        return ["squad_leader"] + ["rifleman"] * rng.randint(3, 6) + (["smg_gunner"] if rng.random() < 0.6 else []) + \
            (["lmg_gunner"] if rng.random() < 0.3 else [])
    return ["rifleman"] * size

