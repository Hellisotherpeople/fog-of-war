"""Special, elite and exotic units - as rare as they were.

Each: nations, years, where they fought (theatre ids, or None for anywhere), how often an
AI squad is one of them (per squad), the role a player takes, weapons they favoured, kit,
traits and bonuses, doctrine, the name they went by, and the kind of battle they're for.

Doctrine flags:
  fanatic    - rarely surrenders, fights on when others break
  executes   - more likely to shoot prisoners
  penal      - badly armed, driven forward, no retreat
  blocking   - shoots its own side's men who run
  disguise   - trained to pass in enemy or civilian dress
  female     - (the Soviet Union put women in the line: snipers, pilots)
"""
from __future__ import annotations

SPECIAL = {
    # ---------------------------------------------------------------- the Allies
    "sas": dict(name="Special Air Service", nations=["uk"], years=(1941.5, 1946), theatres=None, ai=0.004,
                role="smg_gunner", weapons=["sten", "thompson_m1a1", "thompson_1928", "lee_no4"],
                kit={"satchel": 2, "compass": 1, "map": 1, "morphine": 1}, traits=["veteran"], skill=2, morale=15,
                scenario="raid", unit="{n} SAS, 1st Special Air Service Regiment", flags=[],
                desc="Parachuted or driven hundreds of miles behind the lines to blow up aircraft on the ground."),
    "commando": dict(name="British Commandos", nations=["uk", "canada"], years=(1940.5, 1946), theatres=None,
                     ai=0.006, role="rifleman", weapons=["thompson_1928", "lee_no4", "smle", "sten"],
                     kit={"fs_knife": 1, "satchel": 1}, traits=["veteran"], skill=2, morale=12, scenario="raid",
                     unit="{c} Troop, No. {k} Commando", flags=[],
                     desc="The green beret. Raids on occupied coasts, then the spearhead of every landing."),
    "lrdg": dict(name="Long Range Desert Group", nations=["uk", "newzealand"], years=(1940.5, 1943.5),
                 theatres=["alamein42", "tunisia43"], ai=0.01, role="rifleman", weapons=["smle", "thompson_1928"],
                 kit={"compass": 1, "map": 1, "canteen": 2}, traits=["camouflaged"], skill=1, morale=10,
                 scenario="patrol", unit="{c} Patrol, Long Range Desert Group", flags=[],
                 desc="Navigators of the empty desert, watching the coast road from a thousand miles away."),
    "gurkha": dict(name="Gurkha Rifles", nations=["india"], years=(1939, 1946), theatres=None, ai=0.08,
                   role="rifleman", weapons=["smle", "lee_no4", "thompson_1928"], kit={"kukri": 1},
                   traits=["brave", "tough"], skill=2, morale=20, scenario=None, unit="{c} Coy, 1st/{ko} Gurkha Rifles", k_max=10,
                   flags=[], desc="Nepalese hillmen with the kukri. 'Better to die than be a coward.'"),
    "chindit": dict(name="Chindits", nations=["uk", "india"], years=(1943.1, 1944.8), theatres=["kohima44"],
                    ai=0.03, role="rifleman", weapons=["lee_no4", "sten", "bren"], kit={"ration": 3, "compass": 1},
                    traits=["tough"], skill=1, morale=10, scenario="patrol", unit="{c} Column, 77th Indian Brigade (Chindits)",
                    flags=[], desc="Wingate's long-range penetration columns, supplied from the air deep in the Burmese jungle."),
    "rangers": dict(name="US Army Rangers", nations=["usa"], years=(1942.5, 1946), theatres=None, ai=0.006,
                    role="rifleman", weapons=["m1_garand", "thompson_m1a1", "bar"], kit={"satchel": 1, "trench_knife": 1},
                    traits=["veteran"], skill=2, morale=15, scenario="assault", unit="{c} Company, {ko} Ranger Battalion", k_max=6,
                    flags=[], desc="'Rangers lead the way.' Pointe du Hoc, Cisterna, Omaha Dog Green."),
    "raiders": dict(name="Marine Raiders", nations=["usa"], years=(1942.1, 1944.1),
                    theatres=["guadalcanal42"], ai=0.05, role="smg_gunner", weapons=["thompson_m1a1", "m1_garand", "bar"],
                    kit={"trench_knife": 1}, traits=["veteran"], skill=2, morale=15, scenario="raid",
                    unit="{c} Company, 1st Marine Raider Battalion", flags=[],
                    desc="Edson's Raiders. Tulagi, Edson's Ridge, the long patrol."),
    "oss": dict(name="Office of Strategic Services", nations=["usa"], years=(1942.5, 1946), theatres=None, ai=0.0,
                role="agent", weapons=[], kit={"forged_papers": 1, "silk_map": 1, "scr536": 1}, traits=["camouflaged"],
                skill=2, morale=5, scenario="agent", unit="OSS Special Operations Branch", flags=["disguise"],
                desc="Wild Bill Donovan's spies and saboteurs: Jedburgh teams, agents in occupied Europe."),
    "soe": dict(name="Special Operations Executive", nations=["uk", "france", "poland"], years=(1940.6, 1946),
                theatres=None, ai=0.0, role="agent", weapons=[], kit={"forged_papers": 1, "silk_map": 1}, traits=[],
                skill=2, morale=5, scenario="agent", unit="SOE F Section", flags=["disguise"],
                desc="'Set Europe ablaze.' Wireless operators and saboteurs dropped into occupied countries."),
    "cichociemni": dict(name="Cichociemni", nations=["poland"], years=(1941.1, 1945), theatres=None, ai=0.0,
                        role="agent", weapons=["sten"], kit={"forged_papers": 1, "silk_map": 1}, traits=["veteran"],
                        skill=2, morale=15, scenario="agent", unit="Cichociemni (Silent Unseen), Polish Home Army",
                        flags=["disguise"], desc="Polish paratroopers dropped into their own occupied country to fight with the Home Army."),
    "fssf": dict(name="First Special Service Force", nations=["usa", "canada"], years=(1942.5, 1945),
                 theatres=["cassino44"], ai=0.05, role="rifleman", weapons=["m1_garand", "thompson_m1a1"],
                 kit={"satchel": 1}, traits=["veteran", "tough"], skill=2, morale=15, scenario="raid",
                 unit="{c} Company, First Special Service Force", flags=[],
                 desc="The Devil's Brigade: Americans and Canadians together, mountain and night fighters."),
    "code_talker": dict(name="Navajo Code Talkers", nations=["usa"], years=(1942.4, 1946),
                        theatres=["guadalcanal42", "iwojima45", "okinawa45"], ai=0.0, role="radioman", weapons=[],
                        kit={}, traits=[], skill=0, morale=5, scenario=None, unit="{c} Company, Marine Signal Battalion",
                        flags=[], desc="Marine radiomen speaking a code the Japanese never broke."),
    "penal": dict(name="Shtrafbat (penal battalion)", nations=["ussr"], years=(1942.6, 1946), theatres=None, ai=0.02,
                  role="rifleman", weapons=["mosin"], kit={}, traits=[], skill=-1, morale=-10, scenario="assault",
                  unit="{c} Company, {ko} Separate Penal Battalion", flags=["penal"],
                  desc="Order No. 227: 'Not one step back.' Men sent to atone in blood, first through the minefields."),
    "nkvd": dict(name="NKVD troops", nations=["ussr"], years=(1939, 1946), theatres=None, ai=0.01, role="smg_gunner",
                 weapons=["ppsh", "ppd40"], kit={}, traits=[], skill=1, morale=10, scenario=None,
                 unit="{c} Company, {ko} NKVD Rifle Regiment", flags=["blocking", "executes"],
                 desc="The People's Commissariat's own troops: blocking detachments behind the line."),
    "naval_infantry": dict(name="Soviet Naval Infantry", nations=["ussr"], years=(1941.5, 1946),
                           theatres=["stalingrad42", "moscow41", "karelia44"], ai=0.03, role="smg_gunner",
                           weapons=["ppsh", "svt40", "mosin"], kit={}, traits=["brave"], skill=1, morale=18,
                           scenario=None, unit="{c} Company, {ko} Naval Rifle Brigade", flags=["fanatic"],
                           desc="Sailors ashore in their black peacoats: 'the black death'."),
    "night_witches": dict(name="Night Witches", nations=["ussr"], years=(1942.4, 1946), theatres=None, ai=0.0,
                          role="bomber_pilot", weapons=[], kit={}, traits=["brave"], skill=1, morale=15,
                          scenario="air:attack", aircraft="po2", unit="588th Night Bomber Regiment", flags=["female"],
                          desc="Women flying wood-and-canvas Po-2 biplanes over German lines every night, engines cut."),
    "women_snipers": dict(name="Soviet women snipers", nations=["ussr"], years=(1942.5, 1946), theatres=None, ai=0.0,
                          role="sniper", weapons=["mosin_pu"], kit={}, traits=["crack_shot"], skill=2, morale=10,
                          scenario="sniper", unit="Central Women's Sniper Training School", flags=["female"],
                          desc="Two thousand trained; Lyudmila Pavlichenko alone was credited with 309 kills."),
    "maquis": dict(name="Maquis", nations=["france"], years=(1943, 1945), theatres=None, ai=0.0, role="partisan",
                   weapons=["sten", "lee_no4"], kit={"civvies": 1}, traits=["camouflaged"], skill=0, morale=10,
                   scenario="partisans", unit="Maquis, Forces Françaises de l'Intérieur", flags=["disguise"],
                   desc="The French resistance in the hills, armed by parachute drops."),
    # ---------------------------------------------------------------- the Axis
    "waffen_ss": dict(name="Waffen-SS", nations=["germany"], years=(1939, 1946),
                      theatres=["poland39", "france40", "barbarossa41", "moscow41", "kursk43", "bocage44", "omaha44",
                                "normandy_airborne44", "arnhem44", "bastogne44", "berlin45"], ai=0.04,
                      role="smg_gunner", weapons=["mp40", "stg44", "kar98k", "mg42"], kit={}, traits=["brave"],
                      skill=1, morale=18, scenario=None, service="ss", unit="{c}./SS-Panzergrenadier-Regiment {k}",
                      flags=["fanatic", "executes"],
                      desc="The SS's own army: well equipped, feared, and responsible for massacres of prisoners and civilians."),
    "brandenburger": dict(name="Brandenburgers", nations=["germany"], years=(1939.7, 1944.8), theatres=None,
                          ai=0.003, role="smg_gunner", weapons=["mp40", "kar98k"], kit={"satchel": 1, "forged_papers": 1},
                          traits=["veteran", "camouflaged"], skill=2, morale=12, scenario="raid",
                          unit="{c}. Kompanie, Division Brandenburg", flags=["disguise"],
                          desc="The Abwehr's commandos, often in enemy uniform: bridges, tunnels, headquarters."),
    "fallschirmjager": dict(name="Fallschirmjäger", nations=["germany"], years=(1939, 1946),
                            theatres=["crete41", "cassino44", "normandy_airborne44", "bocage44", "arnhem44"], ai=0.08,
                            role="smg_gunner", weapons=["fg42", "mp40", "kar98k", "mg42"], kit={}, traits=["veteran"],
                            skill=2, morale=15, scenario=None, unit="{c}./Fallschirmjäger-Regiment {k}", flags=[],
                            desc="The Luftwaffe's paratroopers: Crete, then the 'green devils' of Cassino."),
    "gebirgsjager": dict(name="Gebirgsjäger", nations=["germany"], years=(1939, 1946),
                         theatres=["crete41", "karelia44", "cassino44"], ai=0.06, role="rifleman",
                         weapons=["kar98k", "mp40"], kit={}, traits=["tough"], skill=1, morale=10, scenario=None,
                         unit="{c}./Gebirgsjäger-Regiment {k}", flags=[], desc="Mountain troops with the edelweiss badge."),
    "decima": dict(name="Decima Flottiglia MAS", nations=["italy"], years=(1940.5, 1945), theatres=None, ai=0.0,
                   role="engineer", weapons=["mab38"], kit={"satchel": 2}, traits=["brave"], skill=2, morale=15,
                   scenario="raid", unit="Decima Flottiglia MAS", flags=[],
                   desc="Frogmen riding 'pigs' into Alexandria harbour to mine battleships."),
    "alpini": dict(name="Alpini", nations=["italy"], years=(1939, 1946), theatres=None, ai=0.04, role="rifleman",
                   weapons=["carcano", "breda30"], kit={}, traits=["tough"], skill=1, morale=10, scenario=None,
                   unit="{c}ª Compagnia, Battaglione Alpini", flags=[], desc="Mountain troops with the feathered hat."),
    "folgore": dict(name="Folgore paratroopers", nations=["italy"], years=(1941, 1943.5), theatres=["alamein42"],
                    ai=0.2, role="rifleman", weapons=["carcano", "mab38"], kit={}, traits=["brave"], skill=1,
                    morale=20, scenario=None, unit="{c}ª Compagnia, Divisione Folgore", flags=["fanatic"],
                    desc="'They fought like lions' - the paratroopers who held El Alamein's southern flank."),
    "sissi": dict(name="Sissi (long-range patrol)", nations=["finland"], years=(1939, 1946), theatres=None, ai=0.02,
                  role="rifleman", weapons=["mosin", "suomi"], kit={"compass": 1}, traits=["camouflaged", "tough"],
                  skill=2, morale=12, scenario="patrol", unit="Kaukopartio, Päämajan kaukopartio-osasto", flags=[],
                  desc="Finnish long-range patrols on skis, deep behind Soviet lines."),
    "teishin": dict(name="Teishin Shudan", nations=["japan"], years=(1941.9, 1946), theatres=None, ai=0.002,
                    role="smg_gunner", weapons=["type100", "type99"], kit={"satchel": 1}, traits=["brave"], skill=2,
                    morale=20, scenario="raid", unit="1st Raiding Regiment (Teishin Shudan)", flags=["fanatic"],
                    desc="Imperial Army paratroopers: Palembang, Leyte, the suicide raids on airfields."),
    "kamikaze": dict(name="Tokkōtai (special attack)", nations=["japan"], years=(1944.8, 1946), theatres=None, ai=0.0,
                     role="fighter_pilot", weapons=[], kit={}, traits=["brave"], skill=0, morale=25,
                     scenario="air:kamikaze", aircraft="zero", unit="Shinpū Special Attack Corps", flags=["fanatic"],
                     desc="Young pilots with a few weeks' training and a bomb under the wing. There is no return leg."),
}

SS_LADDER = [("SS-Schütze", "SS-Schtz."), ("SS-Oberschütze", "SS-OSchtz."), ("SS-Sturmmann", "SS-Strm."),
             ("SS-Rottenführer", "SS-Rttf."), ("SS-Unterscharführer", "SS-Uscha."), ("SS-Scharführer", "SS-Scha."),
             ("SS-Oberscharführer", "SS-Oscha."), ("SS-Hauptscharführer", "SS-Hscha."), ("SS-Untersturmführer", "SS-Ustuf."),
             ("SS-Obersturmführer", "SS-Ostuf."), ("SS-Hauptsturmführer", "SS-Hstuf."), ("SS-Sturmbannführer", "SS-Stubaf."),
             ("SS-Obersturmbannführer", "SS-Ostubaf."), ("SS-Standartenführer", "SS-Staf."), ("SS-Brigadeführer", "SS-Brigf."),
             ("SS-Gruppenführer", "SS-Gruf."), ("SS-Obergruppenführer", "SS-Ogruf."), ("SS-Oberst-Gruppenführer", "SS-Obstgruf."),
             ("Reichsführer-SS", "RFSS")]


def eligible(sid, nation, year, theatre_id=None, service="army"):
    d = SPECIAL[sid]
    if nation not in d["nations"] or not (d["years"][0] <= year < d["years"][1]):
        return False
    if d["theatres"] is not None and theatre_id not in d["theatres"]:
        return False
    sc = d.get("scenario") or ""
    if service == "air" and not sc.startswith("air:"):
        return False
    if service != "air" and sc.startswith("air:"):
        return False
    if service == "navy":
        return False
    return True


def for_player(nation, year, theatre_id, service="army"):
    return [k for k in SPECIAL if eligible(k, nation, year, theatre_id, service)]
