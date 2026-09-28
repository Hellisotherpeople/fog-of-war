"""Battles / theatres of war.

Each theatre defines the strategic overmap (a grid of sectors, each a local
battlefield), who fights, when, and the texture of the fighting.

Overmap features:
  ("sea", dir, depth)        rows/cols of open water along an edge (not enterable)
  ("beach", dir)             landing beaches adjacent to the sea edge
  ("river", orient, pos)     a river line across the grid ('v' vertical at column pos, 'h' row)
  ("city", cx, cy, r, biome) a cluster of urban sectors
  ("biome", x, y, biome)     force one sector
  ("pocket", cx, cy, r)      defender holds a pocket surrounded by the attacker
"""
from __future__ import annotations

from ..constants import ALLIES, AXIS

THEATRES: dict[str, dict] = {}


def theatre(id, **kw):
    kw["id"] = id
    kw.setdefault("om_size", (9, 7))
    kw.setdefault("features", [])
    kw.setdefault("special", set())
    kw.setdefault("fort", 1)
    kw.setdefault("front", 0.35)
    kw.setdefault("weather", {"clear": 6, "overcast": 3, "rain": 1})
    kw.setdefault("armor", {ALLIES: 0.4, AXIS: 0.4})
    kw.setdefault("air", {ALLIES: 0.5, AXIS: 0.5})
    kw.setdefault("arty", {ALLIES: 0.6, AXIS: 0.6})
    kw.setdefault("intensity", 1.0)
    kw.setdefault("divisions", {})
    THEATRES[id] = kw


theatre(
    "poland39", name="Invasion of Poland", battle="Battle of the Bzura",
    date=(1939, 9, 12, 5, 30), climate="summer",
    desc="The Wehrmacht's first Blitzkrieg. Polish armies trapped west of Warsaw turn and strike "
         "south across the Bzura river into the flank of the German 8th Army.",
    sides={ALLIES: [("poland", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="W", front=0.4,
    biomes=[("farmland", 5), ("village", 3), ("forest", 2), ("marsh", 1)],
    features=[("river", "h", 3)],
    air={ALLIES: 0.15, AXIS: 0.85}, arty={ALLIES: 0.45, AXIS: 0.7}, armor={ALLIES: 0.15, AXIS: 0.5},
    fort=1,
    places=["Kutno", "Łęczyca", "Piątek", "Sochaczew", "Brochów", "Stryków", "Łowicz",
            "Walewice", "Bielawy", "Głowno", "Ozorków", "Kampinos forest", "Witonia"],
    divisions={"poland": ["14th Infantry Division", "25th Infantry Division",
                          "Podolska Cavalry Brigade"],
               "germany": ["30. Infanterie-Division", "24. Infanterie-Division",
                           "1. Panzer-Division", "SS-Leibstandarte"]},
)

theatre(
    "france40", name="Battle of France", battle="Crossing of the Meuse at Sedan",
    date=(1940, 5, 13, 15, 0), climate="summer",
    desc="After slipping through the 'impassable' Ardennes, German infantry assault across the "
         "Meuse under a storm of Stuka attacks. French reservists wait in their bunkers.",
    sides={ALLIES: [("france", 0.85), ("uk", 0.15)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="E", front=0.3,
    biomes=[("farmland", 4), ("forest", 3), ("village", 3), ("town", 1)],
    features=[("river", "v", 3)],
    air={ALLIES: 0.25, AXIS: 0.9}, arty={ALLIES: 0.7, AXIS: 0.55}, armor={ALLIES: 0.35, AXIS: 0.55},
    fort=2,
    places=["Sedan", "Wadelincourt", "Frénois", "Glaire", "Bellevue", "Donchery", "Marfée heights",
            "Chéhéry", "Bulson", "Stonne", "Floing", "Iges", "Torcy"],
    divisions={"france": ["55e Division d'Infanterie", "71e Division d'Infanterie",
                          "3e Division Cuirassée"],
               "germany": ["1. Panzer-Division", "Infanterie-Regiment Großdeutschland",
                           "10. Panzer-Division"]},
)

theatre(
    "crete41", name="Battle of Crete", battle="Maleme airfield and Hill 107",
    date=(1941, 5, 20, 8, 0), climate="mediterranean",
    desc="Operation Mercury: the largest airborne assault yet attempted. Fallschirmjäger drop "
         "straight onto New Zealand positions around Maleme. Many die in the air.",
    sides={ALLIES: [("newzealand", 0.45), ("uk", 0.3), ("australia", 0.25)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="N", front=0.0,
    biomes=[("hills", 4), ("village", 2), ("farmland", 3)],
    features=[("sea", "N", 1)],
    special={"paradrop_axis"},
    air={ALLIES: 0.05, AXIS: 0.95}, arty={ALLIES: 0.35, AXIS: 0.3}, armor={ALLIES: 0.1, AXIS: 0.0},
    fort=1,
    places=["Maleme", "Hill 107", "Pirgos", "Tavronitis bridge", "Galatas", "Prison Valley",
            "Kondomari", "Platanias", "Modhion", "Vlakheronitissa", "Canea road"],
    divisions={"germany": ["Luftlande-Sturm-Regiment", "7. Flieger-Division",
                           "5. Gebirgs-Division"],
               "newzealand": ["22nd Battalion", "23rd Battalion", "28th (Maori) Battalion"]},
)

theatre(
    "barbarossa41", name="Operation Barbarossa", battle="The Smolensk pocket",
    date=(1941, 7, 20, 4, 0), climate="summer",
    desc="Four weeks into the invasion. Panzer groups have encircled whole Soviet armies around "
         "Smolensk, and the trapped divisions fight savagely to break out.",
    sides={ALLIES: [("ussr", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="W", front=0.4,
    biomes=[("farmland", 4), ("forest", 3), ("village", 3), ("marsh", 1), ("steppe", 1)],
    features=[("river", "v", 5)],
    air={ALLIES: 0.2, AXIS: 0.8}, arty={ALLIES: 0.6, AXIS: 0.65}, armor={ALLIES: 0.45, AXIS: 0.5},
    fort=1,
    places=["Smolensk", "Yelnya", "Dukhovshchina", "Yartsevo", "Solovyovo crossing", "Vop river",
            "Dorogobuzh", "Krasny", "Rudnya", "Katyn woods", "Gnezdovo"],
    divisions={"ussr": ["16th Army", "20th Army", "1st Moscow Motor Rifle Division"],
               "germany": ["17. Panzer-Division", "29. Infanterie-Division (mot.)",
                           "7. Panzer-Division"]},
)

theatre(
    "moscow41", name="Battle of Moscow", battle="The winter counteroffensive",
    date=(1941, 12, 6, 9, 0), climate="winter",
    desc="Thirty below zero. The German drive on Moscow has frozen in place, and fresh Siberian "
         "divisions in white smocks come out of the forests.",
    sides={ALLIES: [("ussr", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=ALLIES, attacker_from="E", front=0.3,
    biomes=[("forest", 4), ("village", 3), ("farmland", 3)],
    weather={"clear": 3, "overcast": 3, "snow": 4},
    air={ALLIES: 0.55, AXIS: 0.45}, arty={ALLIES: 0.65, AXIS: 0.45}, armor={ALLIES: 0.4, AXIS: 0.3},
    fort=1,
    places=["Krasnaya Polyana", "Khimki", "Kryukovo", "Istra", "Solnechnogorsk", "Klin",
            "Volokolamsk road", "Dubosekovo", "Yakhroma", "Naro-Fominsk"],
    divisions={"ussr": ["78th Rifle Division (Siberian)", "1st Guards Cavalry Corps",
                        "316th Rifle Division (Panfilov)"],
               "germany": ["2. Panzer-Division", "SS-Division Das Reich", "106. Infanterie-Division"]},
)

theatre(
    "alamein42", name="North Africa", battle="Second Battle of El Alamein",
    date=(1942, 10, 23, 21, 40), climate="desert",
    desc="At 21:40 nearly 900 guns open fire at once. Infantry and sappers walk forward through "
         "the minefields of Rommel's 'Devil's Gardens' by moonlight.",
    sides={ALLIES: [("uk", 0.45), ("australia", 0.2), ("newzealand", 0.2), ("india", 0.15)],
           AXIS: [("germany", 0.45), ("italy", 0.55)]},
    attacker=ALLIES, attacker_from="E", front=0.3,
    biomes=[("desert", 8), ("hills", 1)],
    weather={"clear": 9, "sandstorm": 1},
    air={ALLIES: 0.8, AXIS: 0.2}, arty={ALLIES: 1.0, AXIS: 0.5}, armor={ALLIES: 0.6, AXIS: 0.5},
    fort=3, special={"minefields"},
    places=["Tel el Eisa", "Kidney Ridge", "Miteiriya Ridge", "Outpost Snipe", "Tel el Aqqaqir",
            "Point 29", "Ruweisat Ridge", "Deir el Shein", "Himeimat", "Qattara depression"],
    divisions={"uk": ["51st Highland Division", "7th Armoured Division", "1st Armoured Division"],
               "germany": ["15. Panzer-Division", "164. leichte Afrika-Division", "Fallschirmjäger-Brigade Ramcke"],
               "italy": ["Divisione Folgore", "Divisione Ariete", "Divisione Trento"]},
)

theatre(
    "stalingrad42", name="Stalingrad", battle="The factory district",
    date=(1942, 10, 14, 6, 0), climate="autumn",
    desc="Rattenkrieg. The Sixth Army's final assault on the tractor works and the Barrikady. "
         "Soviet troops cling to the rubble with the Volga at their backs. Not one step back.",
    sides={ALLIES: [("ussr", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="W", front=0.45,
    biomes=[("city_ruins", 5), ("factory", 4)],
    features=[("river", "v", 8)],
    air={ALLIES: 0.25, AXIS: 0.8}, arty={ALLIES: 0.8, AXIS: 0.75}, armor={ALLIES: 0.15, AXIS: 0.35},
    fort=2, special={"urban"}, intensity=1.3,
    places=["Tractor Factory", "Barrikady Gun Factory", "Red October Steelworks", "Mamayev Kurgan",
            "Pavlov's House", "Grain Elevator", "Central Station", "Orlovka", "Spartakovka",
            "Workers' Settlement", "Chemical Plant 'Lazur'", "Tennis Racket", "Volga crossing"],
    divisions={"ussr": ["62nd Army", "13th Guards Rifle Division", "284th Rifle Division",
                        "37th Guards Rifle Division"],
               "germany": ["14. Panzer-Division", "305. Infanterie-Division", "389. Infanterie-Division"]},
)

theatre(
    "uranus42", name="Stalingrad", battle="Operation Uranus - the Romanian front",
    date=(1942, 11, 19, 7, 30), climate="winter",
    desc="Freezing fog on the Don steppe. At 07:30 thirty-five hundred Soviet guns open up on the "
         "thinly spread Romanian Third Army guarding the Sixth Army's flank.",
    sides={ALLIES: [("ussr", 1.0)], AXIS: [("romania", 0.8), ("germany", 0.2)]},
    attacker=ALLIES, attacker_from="N", front=0.3,
    biomes=[("steppe", 6), ("village", 2), ("farmland", 2)],
    weather={"fog": 4, "overcast": 3, "snow": 3},
    air={ALLIES: 0.5, AXIS: 0.3}, arty={ALLIES: 0.95, AXIS: 0.4}, armor={ALLIES: 0.6, AXIS: 0.15},
    fort=1,
    places=["Kletskaya", "Serafimovich", "Raspopinskaya", "Bolshoy", "Kalach", "Gromki",
            "Blinov", "Perelazovsky", "Golubinsky", "Don bridgehead"],
    divisions={"romania": ["5th Infantry Division", "1st Armoured Division 'Romania Mare'",
                           "15th Infantry Division"],
               "ussr": ["5th Tank Army", "21st Army", "4th Tank Corps"]},
)

theatre(
    "guadalcanal42", name="Guadalcanal", battle="Edson's Ridge",
    date=(1942, 9, 13, 21, 0), climate="tropical",
    desc="Night on the ridge south of Henderson Field. Kawaguchi's brigade comes out of the jungle "
         "in waves, screaming, against a thin line of Marine raiders and paratroopers.",
    sides={ALLIES: [("usa", 1.0)], AXIS: [("japan", 1.0)]},
    attacker=AXIS, attacker_from="S", front=0.4,
    biomes=[("jungle", 6), ("hills", 2), ("farmland", 1)],
    features=[("sea", "N", 1), ("beach", "N")],
    weather={"clear": 4, "overcast": 3, "rain": 4},
    air={ALLIES: 0.6, AXIS: 0.4}, arty={ALLIES: 0.7, AXIS: 0.3}, armor={ALLIES: 0.1, AXIS: 0.1},
    fort=1, special={"night"},
    places=["Edson's Ridge", "Henderson Field", "Lunga Point", "Matanikau river", "Alligator Creek",
            "Hill 80", "Hill 123", "Kukum", "Tenaru", "Point Cruz", "Mount Austen"],
    divisions={"usa": ["1st Marine Raider Battalion", "1st Parachute Battalion", "5th Marines"],
               "japan": ["Kawaguchi Detachment", "124th Infantry Regiment", "Ichiki Detachment"]},
)

theatre(
    "tunisia43", name="Tunisia", battle="Kasserine Pass",
    date=(1943, 2, 19, 7, 0), climate="desert",
    desc="Rommel's veterans hit green American troops in the Atlas passes. The US Army's first "
         "big battle against the Germans goes very badly.",
    sides={ALLIES: [("usa", 0.85), ("uk", 0.15)], AXIS: [("germany", 0.8), ("italy", 0.2)]},
    attacker=AXIS, attacker_from="E", front=0.35,
    biomes=[("desert", 4), ("hills", 4), ("village", 1)],
    air={ALLIES: 0.45, AXIS: 0.55}, arty={ALLIES: 0.55, AXIS: 0.6}, armor={ALLIES: 0.5, AXIS: 0.6},
    fort=1,
    places=["Kasserine Pass", "Sidi Bou Zid", "Djebel Chambi", "Thala", "Djebel Semmama",
            "Hatab river", "Sbiba", "Feriana", "Faïd Pass", "Djebel Lessouda"],
    divisions={"usa": ["1st Armored Division", "26th Infantry Regiment", "19th Engineers"],
               "germany": ["10. Panzer-Division", "21. Panzer-Division", "Deutsches Afrikakorps"],
               "italy": ["Divisione Centauro"]},
)

theatre(
    "kursk43", name="Kursk", battle="Ponyri and the northern face",
    date=(1943, 7, 5, 4, 30), climate="summer",
    desc="Operation Citadel. The Germans throw their new Tigers, Panthers and Elefants at the most "
         "heavily fortified line in history: trench belts, minefields and dug-in anti-tank guns.",
    sides={ALLIES: [("ussr", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="S", front=0.35,
    biomes=[("steppe", 5), ("farmland", 3), ("village", 2)],
    air={ALLIES: 0.5, AXIS: 0.55}, arty={ALLIES: 0.9, AXIS: 0.8}, armor={ALLIES: 0.75, AXIS: 0.85},
    fort=3, special={"minefields"}, intensity=1.3,
    places=["Ponyri station", "Hill 253.5", "Olkhovatka", "Teploye", "Maloarkhangelsk",
            "Prokhorovka", "Oboyan road", "Snova river", "Gnilets", "Samodurovka", "Hill 274"],
    divisions={"ussr": ["307th Rifle Division", "13th Army", "2nd Tank Army",
                        "5th Guards Tank Army"],
               "germany": ["9. Armee", "292. Infanterie-Division", "schwere Panzerjäger-Abteilung 654",
                           "SS-Panzergrenadier-Division Totenkopf"]},
)

theatre(
    "sicily43", name="Sicily", battle="Operation Husky - Gela",
    date=(1943, 7, 10, 4, 0), climate="mediterranean",
    desc="Allied troops come ashore on Sicily. Italian coastal divisions and the Hermann Göring "
         "Panzer Division counterattack toward the beaches.",
    sides={ALLIES: [("usa", 0.6), ("uk", 0.3), ("canada", 0.1)],
           AXIS: [("italy", 0.6), ("germany", 0.4)]},
    attacker=ALLIES, attacker_from="S", front=0.0,
    biomes=[("hills", 3), ("farmland", 3), ("village", 2), ("town", 1)],
    features=[("sea", "S", 1), ("beach", "S")],
    air={ALLIES: 0.8, AXIS: 0.3}, arty={ALLIES: 0.75, AXIS: 0.5}, armor={ALLIES: 0.35, AXIS: 0.45},
    fort=1, special={"landing"},
    places=["Gela", "Piano Lupo", "Biazzo Ridge", "Ponte Olivo airfield", "Niscemi", "Licata",
            "Scoglitti", "Vittoria", "Butera", "Priolo", "Primosole bridge"],
    divisions={"usa": ["1st Infantry Division", "82nd Airborne Division", "45th Infantry Division"],
               "italy": ["Divisione Livorno", "18ª Brigata Costiera"],
               "germany": ["Fallschirm-Panzer-Division Hermann Göring"]},
)

theatre(
    "cassino44", name="Italy", battle="Monte Cassino",
    date=(1944, 5, 17, 5, 0), climate="mediterranean",
    desc="The fourth battle. Polish II Corps assaults the ridges around the bombed-out abbey, held "
         "by German paratroopers who have turned the rubble into a fortress.",
    sides={ALLIES: [("poland", 0.4), ("uk", 0.2), ("newzealand", 0.1), ("india", 0.15),
                    ("usa", 0.05), ("france", 0.1)],
           AXIS: [("germany", 1.0)]},
    attacker=ALLIES, attacker_from="S", front=0.35,
    biomes=[("mountain", 5), ("city_ruins", 1), ("hills", 2)],
    features=[("river", "h", 5), ("biome", 4, 2, "abbey")],
    air={ALLIES: 0.85, AXIS: 0.1}, arty={ALLIES: 0.95, AXIS: 0.65}, armor={ALLIES: 0.25, AXIS: 0.15},
    fort=3,
    places=["Monte Cassino abbey", "Point 593", "Snakeshead Ridge", "Phantom Ridge", "Castle Hill",
            "Cassino town", "Hangman's Hill", "Rapido river", "Colle Sant'Angelo", "Albaneta farm",
            "Liri valley", "Piedimonte"],
    divisions={"poland": ["3rd Carpathian Rifle Division", "5th Kresowa Infantry Division"],
               "germany": ["1. Fallschirmjäger-Division"],
               "newzealand": ["2nd New Zealand Division"], "india": ["4th Indian Division"]},
)

theatre(
    "normandy_airborne44", name="D-Day", battle="Sainte-Mère-Église (airborne drop)",
    date=(1944, 6, 6, 1, 30), climate="summer",
    desc="Night. Thirteen thousand paratroopers jump into flak and cloud over the Cotentin. "
         "Pilots scatter them across the countryside. Many land in flooded fields - and drown.",
    sides={ALLIES: [("usa", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=ALLIES, attacker_from="E", front=0.0,
    biomes=[("bocage", 5), ("village", 2), ("marsh", 2), ("farmland", 1)],
    features=[("biome", 4, 3, "town")],
    air={ALLIES: 0.9, AXIS: 0.05}, arty={ALLIES: 0.3, AXIS: 0.55}, armor={ALLIES: 0.0, AXIS: 0.2},
    fort=1, special={"paradrop_allies", "night"},
    places=["Sainte-Mère-Église", "La Fière causeway", "Chef-du-Pont", "Brécourt Manor",
            "Sainte-Marie-du-Mont", "Carentan", "Neuville-au-Plain", "Hiesville", "Pouppeville",
            "Merderet marshes", "Dead Man's Corner", "Le Grand Chemin"],
    divisions={"usa": ["82nd Airborne Division", "101st Airborne Division"],
               "germany": ["91. Luftlande-Division", "709. Infanterie-Division",
                           "Fallschirmjäger-Regiment 6"]},
)

theatre(
    "omaha44", name="D-Day", battle="Omaha Beach",
    date=(1944, 6, 6, 6, 30), climate="summer",
    desc="H-Hour. The bombers missed, the DD tanks sank, and the landing craft are coming in on "
         "the wrong beaches under intact bunkers of the Atlantic Wall. Bloody Omaha.",
    sides={ALLIES: [("usa", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=ALLIES, attacker_from="N", front=0.0,
    biomes=[("bocage", 4), ("village", 2), ("farmland", 2)],
    features=[("sea", "N", 1), ("beach", "N")],
    weather={"overcast": 7, "clear": 2, "rain": 1},
    air={ALLIES: 0.9, AXIS: 0.05}, arty={ALLIES: 0.75, AXIS: 0.6}, armor={ALLIES: 0.2, AXIS: 0.1},
    fort=3, special={"landing"}, intensity=1.4,
    places=["Dog Green", "Easy Red", "Fox Green", "Charlie", "Vierville draw", "Les Moulins",
            "Colleville-sur-Mer", "Saint-Laurent-sur-Mer", "WN 62", "Pointe du Hoc",
            "Le Ruquet draw", "Formigny", "Trévières"],
    divisions={"usa": ["29th Infantry Division", "1st Infantry Division", "2nd Ranger Battalion"],
               "germany": ["352. Infanterie-Division", "716. Infanterie-Division"]},
)

theatre(
    "bocage44", name="Normandy", battle="The bocage south of Saint-Lô",
    date=(1944, 7, 11, 6, 0), climate="summer",
    desc="Hedgerow hell. Every field is a fortress walled by earth banks and thick hedges. "
         "Advances are measured in fields, casualties in companies.",
    sides={ALLIES: [("usa", 0.5), ("uk", 0.3), ("canada", 0.2)], AXIS: [("germany", 1.0)]},
    attacker=ALLIES, attacker_from="N", front=0.3,
    biomes=[("bocage", 6), ("village", 2), ("town", 1), ("farmland", 1)],
    air={ALLIES: 0.85, AXIS: 0.1}, arty={ALLIES: 0.9, AXIS: 0.55}, armor={ALLIES: 0.6, AXIS: 0.5},
    fort=1,
    places=["Hill 192", "Saint-Lô", "Hill 112", "Carpiquet", "Villers-Bocage", "Tilly-sur-Seulles",
            "Martinville ridge", "Hauts-Vents", "Le Mesnil-Rouxelin", "Pont-Hébert",
            "Saint-Jean-de-Daye", "Épron"],
    divisions={"usa": ["29th Infantry Division", "2nd Armored Division", "30th Infantry Division"],
               "uk": ["43rd (Wessex) Division", "7th Armoured Division", "15th (Scottish) Division"],
               "canada": ["3rd Canadian Infantry Division"],
               "germany": ["Panzer-Lehr-Division", "12. SS-Panzer-Division Hitlerjugend",
                           "3. Fallschirmjäger-Division", "2. SS-Panzer-Division Das Reich"]},
)

theatre(
    "arnhem44", name="Operation Market Garden", battle="Arnhem and Oosterbeek",
    date=(1944, 9, 19, 7, 0), climate="autumn",
    desc="A bridge too far. British paratroopers hold the north end of the Arnhem road bridge and a "
         "shrinking perimeter at Oosterbeek, while SS panzer units close in.",
    sides={ALLIES: [("uk", 0.8), ("poland", 0.2)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="E", front=0.4,
    biomes=[("town", 4), ("forest", 3), ("farmland", 2)],
    features=[("river", "h", 5), ("pocket", 4, 3, 1)],
    air={ALLIES: 0.4, AXIS: 0.3}, arty={ALLIES: 0.35, AXIS: 0.7}, armor={ALLIES: 0.0, AXIS: 0.55},
    fort=0, special={"paradrop_allies"},
    places=["Arnhem road bridge", "Oosterbeek", "Hartenstein Hotel", "Utrechtseweg",
            "St. Elisabeth hospital", "Wolfheze", "Ginkel Heath", "Heveadorp ferry",
            "Den Brink", "Westerbouwing", "Driel"],
    divisions={"uk": ["1st Airborne Division", "2nd Parachute Battalion", "1st Airlanding Brigade"],
               "poland": ["1st Independent Parachute Brigade"],
               "germany": ["9. SS-Panzer-Division Hohenstaufen", "10. SS-Panzer-Division Frundsberg",
                           "Kampfgruppe Spindler"]},
)

theatre(
    "hurtgen44", name="Western Front", battle="Hürtgen Forest",
    date=(1944, 11, 16, 8, 0), climate="autumn",
    desc="Dark firs, mud, mines and tree bursts. The longest battle the US Army ever fought on "
         "German soil grinds on through the Hürtgenwald.",
    sides={ALLIES: [("usa", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=ALLIES, attacker_from="W", front=0.35,
    biomes=[("forest", 7), ("village", 2)],
    weather={"overcast": 4, "rain": 4, "fog": 2},
    air={ALLIES: 0.5, AXIS: 0.1}, arty={ALLIES: 0.85, AXIS: 0.65}, armor={ALLIES: 0.25, AXIS: 0.2},
    fort=2, special={"minefields"},
    places=["Vossenack", "Kommerscheidt", "Schmidt", "Hürtgen", "Kleinhau", "Grosshau",
            "Kall trail", "Germeter", "Brandenberg", "Bergstein", "Castle Hill 400"],
    divisions={"usa": ["28th Infantry Division", "4th Infantry Division", "9th Infantry Division"],
               "germany": ["275. Infanterie-Division", "89. Infanterie-Division", "116. Panzer-Division"]},
)

theatre(
    "bastogne44", name="Battle of the Bulge", battle="The siege of Bastogne",
    date=(1944, 12, 21, 8, 0), climate="winter",
    desc="Surrounded in the snow. The 101st Airborne holds the crossroads town of Bastogne with "
         "little ammunition and no winter clothing. 'Nuts!'",
    sides={ALLIES: [("usa", 1.0)], AXIS: [("germany", 1.0)]},
    attacker=AXIS, attacker_from="E", front=0.5,
    biomes=[("forest", 5), ("village", 2), ("farmland", 2)],
    features=[("pocket", 4, 3, 1), ("biome", 4, 3, "town")],
    weather={"overcast": 3, "snow": 4, "fog": 3},
    air={ALLIES: 0.3, AXIS: 0.2}, arty={ALLIES: 0.45, AXIS: 0.7}, armor={ALLIES: 0.3, AXIS: 0.6},
    fort=1,
    places=["Bastogne", "Foy", "Noville", "Bois Jacques", "Champs", "Mande-Saint-Étienne",
            "Marvie", "Senonchamps", "Longchamps", "Recogne", "Bizory"],
    divisions={"usa": ["101st Airborne Division", "10th Armored Division (Team SNAFU)"],
               "germany": ["26. Volksgrenadier-Division", "Panzer-Lehr-Division",
                           "15. Panzergrenadier-Division"]},
)

theatre(
    "iwojima45", name="Pacific", battle="Iwo Jima",
    date=(1945, 2, 19, 9, 0), climate="volcanic",
    desc="Eight square miles of volcanic ash. Kuribayashi's 21,000 men wait underground in "
         "sixteen miles of tunnels. They will not surrender.",
    sides={ALLIES: [("usa", 1.0)], AXIS: [("japan", 1.0)]},
    attacker=ALLIES, attacker_from="S", front=0.0,
    biomes=[("volcanic", 7), ("hills", 1)],
    features=[("sea", "S", 1), ("beach", "S"), ("biome", 1, 5, "mountain")],
    air={ALLIES: 0.95, AXIS: 0.05}, arty={ALLIES: 0.95, AXIS: 0.7}, armor={ALLIES: 0.4, AXIS: 0.1},
    fort=3, special={"landing"}, intensity=1.3,
    places=["Mount Suribachi", "Airfield No. 1", "Airfield No. 2", "The Meat Grinder",
            "Hill 382", "Turkey Knob", "The Amphitheater", "Cushman's Pocket", "Motoyama",
            "Green Beach", "Red Beach", "Yellow Beach", "Blue Beach"],
    divisions={"usa": ["4th Marine Division", "5th Marine Division", "3rd Marine Division"],
               "japan": ["109th Division", "145th Infantry Regiment"]},
)

theatre(
    "berlin45", name="Battle of Berlin", battle="The Reichstag",
    date=(1945, 4, 29, 6, 0), climate="summer",
    desc="The end. Soviet assault groups fight block by block toward the Reichstag. The defenders "
         "are SS remnants, Volkssturm old men and Hitler Youth with Panzerfausts.",
    sides={ALLIES: [("ussr", 0.9), ("poland", 0.1)], AXIS: [("germany", 1.0)]},
    attacker=ALLIES, attacker_from="E", front=0.4,
    biomes=[("city_ruins", 6), ("town", 2)],
    features=[("river", "v", 4)],
    air={ALLIES: 0.95, AXIS: 0.05}, arty={ALLIES: 1.0, AXIS: 0.35}, armor={ALLIES: 0.6, AXIS: 0.2},
    fort=2, special={"urban", "volkssturm"}, intensity=1.3,
    places=["Reichstag", "Moltke bridge", "Königsplatz", "Kroll Opera House", "Tiergarten",
            "Zoo flak tower", "Potsdamer Platz", "Anhalter Bahnhof", "Wilhelmstraße",
            "Spree bank", "Ministry of the Interior ('Himmler's House')"],
    divisions={"ussr": ["150th Rifle Division", "171st Rifle Division", "8th Guards Army"],
               "poland": ["1st Tadeusz Kościuszko Infantry Division"],
               "germany": ["SS-Division Nordland", "Volkssturm-Bataillon", "Hitlerjugend",
                           "Division Müncheberg"]},
)

theatre(
    "changsha41", name="Second Sino-Japanese War", battle="Second Battle of Changsha",
    date=(1941, 9, 20, 6, 0), climate="summer",
    desc="The Japanese 11th Army drives south on Changsha across rice paddies and river lines. "
         "Xue Yue's armies trade space for time and strike the flanks.",
    sides={ALLIES: [("china", 1.0)], AXIS: [("japan", 1.0)]},
    attacker=AXIS, attacker_from="N", front=0.35,
    biomes=[("farmland", 3), ("marsh", 3), ("village", 3), ("hills", 2), ("forest", 1)],
    features=[("river", "h", 4)],
    air={ALLIES: 0.1, AXIS: 0.8}, arty={ALLIES: 0.3, AXIS: 0.65}, armor={ALLIES: 0.0, AXIS: 0.2},
    fort=1,
    places=["Changsha", "Xinqiang river", "Miluo river", "Laodao river", "Yongan", "Jinjing",
            "Fulinpu", "Qiaotou", "Huangsha street", "Yuelu mountain"],
    divisions={"china": ["74th Army", "10th Army", "Hunan provincial militia"],
               "japan": ["3rd Division", "4th Division", "6th Division"]},
)

theatre(
    "kohima44", name="Burma", battle="Kohima - the tennis court",
    date=(1944, 4, 18, 6, 0), climate="tropical",
    desc="The Stalingrad of the East. Around the District Commissioner's bungalow the lines are a "
         "tennis court's width apart. Grenades are thrown across the net.",
    sides={ALLIES: [("uk", 0.5), ("india", 0.5)], AXIS: [("japan", 1.0)]},
    attacker=AXIS, attacker_from="E", front=0.4,
    biomes=[("jungle", 4), ("hills", 3), ("village", 2)],
    features=[("biome", 4, 3, "town")],
    weather={"clear": 3, "overcast": 3, "rain": 4},
    air={ALLIES: 0.7, AXIS: 0.2}, arty={ALLIES: 0.6, AXIS: 0.35}, armor={ALLIES: 0.1, AXIS: 0.0},
    fort=2,
    places=["Garrison Hill", "the tennis court", "DC's bungalow", "Kuki Piquet", "FSD Ridge",
            "Jail Hill", "Naga Village", "Aradura Spur", "GPT Ridge", "Treasury Hill"],
    divisions={"uk": ["4th Bn Royal West Kent Regiment", "2nd Division"],
               "india": ["Assam Regiment", "161st Indian Brigade"],
               "japan": ["31st Division", "58th Infantry Regiment"]},
)

theatre(
    "karelia44", name="Continuation War", battle="Tali-Ihantala",
    date=(1944, 6, 25, 5, 0), climate="summer",
    desc="The largest battle in Nordic history. The Soviet summer offensive smashes into the "
         "Finnish line between the lakes; the Finns, with German Panzerfausts, hold.",
    sides={ALLIES: [("ussr", 1.0)], AXIS: [("finland", 1.0)]},
    attacker=ALLIES, attacker_from="S", front=0.3,
    biomes=[("forest", 5), ("marsh", 2), ("village", 1), ("farmland", 1)],
    air={ALLIES: 0.75, AXIS: 0.35}, arty={ALLIES: 0.9, AXIS: 0.75}, armor={ALLIES: 0.6, AXIS: 0.2},
    fort=2,
    places=["Tali", "Ihantala", "Portinhoikka", "Leitimojärvi", "Repola", "Kärstilänjärvi",
            "Juustila", "Viipuri road", "Konkkala", "Noskua"],
    divisions={"finland": ["Panssaridivisioona", "6. Divisioona", "18. Divisioona"],
               "ussr": ["21st Army", "30th Guards Rifle Corps"]},
)

theatre(
    "don43", name="Eastern Front", battle="The Don - Ostrogozhsk-Rossosh",
    date=(1943, 1, 13, 8, 0), climate="winter",
    desc="Forty below on the Don. The Hungarian Second Army, badly armed and frozen, faces a "
         "Soviet offensive with obsolete anti-tank guns and no winter oil.",
    sides={ALLIES: [("ussr", 1.0)], AXIS: [("hungary", 0.85), ("germany", 0.15)]},
    attacker=ALLIES, attacker_from="E", front=0.3,
    biomes=[("steppe", 5), ("village", 2), ("forest", 1), ("farmland", 2)],
    features=[("river", "v", 6)],
    weather={"clear": 3, "overcast": 3, "snow": 4},
    air={ALLIES: 0.5, AXIS: 0.2}, arty={ALLIES: 0.85, AXIS: 0.4}, armor={ALLIES: 0.5, AXIS: 0.2},
    fort=1,
    places=["Uryv", "Storozhevoye", "Korotoyak", "Ostrogozhsk", "Rossosh", "Alekseyevka",
            "Svoboda", "Don ice", "Shchuchye", "Kantemirovka"],
    divisions={"hungary": ["7th Light Division", "1st Armoured Field Division", "10th Light Division"],
               "ussr": ["40th Army", "3rd Tank Army"]},
)

theatre(
    "okinawa45", name="Pacific", battle="Okinawa - the Shuri Line",
    date=(1945, 5, 11, 6, 0), climate="tropical",
    desc="The typhoon of steel. Sugar Loaf Hill changes hands eleven times in a week, in rain "
         "and mud and the smell of the dead.",
    sides={ALLIES: [("usa", 1.0)], AXIS: [("japan", 1.0)]},
    attacker=ALLIES, attacker_from="N", front=0.35,
    biomes=[("hills", 4), ("village", 2), ("farmland", 2), ("jungle", 1)],
    features=[("biome", 4, 4, "city_ruins")],
    weather={"overcast": 3, "rain": 6, "clear": 1},
    air={ALLIES: 0.9, AXIS: 0.2}, arty={ALLIES: 0.95, AXIS: 0.6}, armor={ALLIES: 0.45, AXIS: 0.05},
    fort=3,
    places=["Sugar Loaf Hill", "Half Moon Hill", "Horseshoe Ridge", "Shuri Castle", "Conical Hill",
            "Kakazu Ridge", "Dakeshi", "Wana Draw", "Naha", "Chocolate Drop"],
    divisions={"usa": ["6th Marine Division", "1st Marine Division", "96th Infantry Division"],
               "japan": ["32nd Army", "62nd Division", "24th Division"]},
)


def theatre_year(t: dict) -> float:
    y, m, d = t["date"][:3]
    return y + (m - 1) / 12 + (d - 1) / 365


def theatres_for_side(side: str) -> list[dict]:
    return list(THEATRES.values())


# Where the sun is: (latitude, longitude east, the clock's hours ahead of GMT) for each battle.  The clock is
# the one its start time is given in - German summer time, Moscow time, British double summer time, Tokyo
# time - so a dawn attack starts at the dawn it really started at.
SUN = {
    "poland39": (52.2, 19.8, 1), "france40": (49.7, 4.9, 2), "crete41": (35.5, 23.8, 2),
    "barbarossa41": (54.8, 32.0, 2), "moscow41": (55.7, 37.6, 3), "alamein42": (30.8, 28.9, 2),
    "stalingrad42": (48.7, 44.5, 3), "uranus42": (49.6, 42.7, 3), "guadalcanal42": (-9.45, 160.0, 11),
    "tunisia43": (35.2, 8.7, 1), "kursk43": (52.3, 36.3, 3), "sicily43": (37.1, 14.25, 2),
    "cassino44": (41.5, 13.8, 2), "normandy_airborne44": (49.4, -1.3, 2), "omaha44": (49.4, -0.9, 2),
    "bocage44": (49.1, -1.1, 2), "arnhem44": (52.0, 5.9, 2), "hurtgen44": (50.7, 6.4, 1),
    "bastogne44": (50.0, 5.7, 1), "iwojima45": (24.8, 141.3, 10), "berlin45": (52.5, 13.4, 2),
    "changsha41": (28.2, 113.0, 8), "kohima44": (25.7, 94.1, 6.5), "karelia44": (60.8, 28.8, 3),
    "don43": (50.9, 39.1, 3), "okinawa45": (26.2, 127.7, 9),
}
for _k, _v in SUN.items():
    if _k in THEATRES:
        THEATRES[_k]["sun"] = _v
