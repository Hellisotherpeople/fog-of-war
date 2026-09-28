"""Agents, the resistance and their trade: careers, cover identities, missions, the special-duties squadrons.

Everything here was real in kind.  SOE ran circuits named after trades (PROSPER, STOCKBROKER,
WHEELWRIGHT), each an organiser, a courier and a wireless operator - "the pianist" - dropped by
Halifax or landed by Lysander on a moonlit field lit by three torches.  The OSS copied it and sent
three-man Jedburgh teams in uniform after D-Day.  The Poles sent the Cichociemni, "the silent and
unseen", home by parachute.  The Red Army's partisan movement had its own organisers and radio
links to Moscow.  The Abwehr sent men the other way, and in December 1944 Skorzeny's commandos drove
through American lines in American jeeps, in American uniforms, turning signposts round.

A cover identity (a "legend") was a whole life: a name, a trade that explained why you were out on
the roads, papers stamped in the right offices - identity card, work permit, ration card,
demobilisation certificate - and the clothes, the tools and the accent to go with them.
"""
from __future__ import annotations

# ---------------------------------------------------------------- careers
# kit: item ids (count); missions: weighted; uniform: dropped in uniform (no disguise); cover: False for those
CAREERS = {
    "soe_organiser": dict(
        name="SOE circuit organiser", service="Special Operations Executive, F Section", nations=["uk", "france"],
        years=(1941.3, 1945.0), unit_types=["soe"],
        kit={"welrod": 1, "ammo_32acp": 2, "fs_knife": 1, "pe_808": 2, "time_pencil": 4, "signal_torch": 3,
             "francs": 40, "one_time_pad": 1},
        missions={"receive_drop": 4, "sabotage": 4, "eliminate": 1, "steal_plans": 1},
        desc="You run a circuit: the drops, the arms caches, the sabotage teams, the safe houses. "
             "London sends the containers; you decide what they're for."),
    "soe_wireless": dict(
        name="SOE wireless operator", service="Special Operations Executive, F Section", nations=["uk", "france"],
        years=(1941.3, 1945.0), unit_types=["soe"],
        kit={"radio_b2": 1, "colt1903": 1, "ammo_32acp": 1, "one_time_pad": 1, "francs": 20},
        missions={"wireless": 5, "receive_drop": 2},
        desc="The pianist. Every message out of the circuit goes through your suitcase set, on the skeds, in "
             "the one-time code. The Funkabwehr's detector vans listen for you. Six weeks was the average life."),
    "soe_courier": dict(
        name="SOE courier", service="Special Operations Executive, F Section", nations=["uk", "france"],
        years=(1941.3, 1945.0), unit_types=["soe"], female=0.6,
        kit={"colt1903": 1, "ammo_32acp": 1, "francs": 30, "one_time_pad": 1},
        missions={"steal_plans": 3, "rescue_airman": 3, "photograph": 2},
        desc="Messages, money, crystals for the radios and parts of Sten guns, carried across checkpoints in a "
             "shopping basket or a bicycle frame. Many couriers were women: a young woman on a bicycle was "
             "nobody."),
    "jedburgh": dict(
        name="Jedburgh team leader", service="Jedburgh team (SOE / OSS / BCRA)", nations=["uk", "usa", "france"],
        years=(1944.4, 1944.95), unit_types=["jedburgh", "oss", "soe"], uniform=True,
        kit={"m1_carbine": 1, "ammo_30carb": 3, "m1911": 1, "ammo_45acp": 1, "fs_knife": 1,
             "radio_b2": 1, "pe_808": 2, "time_pencil": 4, "signal_torch": 3, "s_phone": 1, "francs": 60},
        missions={"receive_drop": 4, "sabotage": 3, "eliminate": 1},
        desc="Three men dropped in uniform after D-Day - one British or American, one French, one wireless "
             "operator - to arm the Maquis and set it on the German columns moving north."),
    "oss_so": dict(
        name="OSS Special Operations agent", service="Office of Strategic Services, SO Branch", nations=["usa"],
        years=(1943.0, 1945.4), unit_types=["oss"],
        kit={"hdm_pistol": 1, "ammo_22lr": 2, "smatchet": 1, "pe_808": 2, "time_pencil": 4, "limpet": 1,
             "signal_torch": 3, "minox": 1, "francs": 40},
        missions={"sabotage": 4, "receive_drop": 2, "photograph": 2, "eliminate": 1},
        desc="Wild Bill Donovan's saboteurs, armed by the Research and Development Branch with everything "
             "from silenced pistols to explosive flour."),
    "oss_si": dict(
        name="OSS Secret Intelligence agent", service="Office of Strategic Services, SI Branch", nations=["usa"],
        years=(1943.0, 1945.4), unit_types=["oss"],
        kit={"colt1903": 1, "ammo_32acp": 1, "minox": 1, "sstr1": 1, "one_time_pad": 1, "francs": 30},
        missions={"photograph": 4, "wireless": 2, "steal_plans": 2},
        desc="A spy, not a saboteur: count the trains, photograph the gun lines, and get it out."),
    "sis": dict(
        name="SIS agent", service="Secret Intelligence Service (MI6)", nations=["uk", "france", "poland"],
        years=(1939.8, 1945.4), unit_types=["soe"],
        kit={"colt1903": 1, "ammo_32acp": 1, "minox": 1, "paraset": 1, "one_time_pad": 1, "francs": 30},
        missions={"photograph": 3, "wireless": 3, "steal_plans": 2},
        desc="The old service. Networks of railwaymen, café owners and priests counting what passes; a "
             "Paraset under the floorboards."),
    "cichociemni": dict(
        name="Cichociemny", service="Cichociemni, Polish Home Army", nations=["poland"],
        years=(1941.1, 1945.0), unit_types=["cichociemni"],
        kit={"sten_mk2s": 1, "ammo_9mm": 3, "vis": 1, "fs_knife": 1, "pe_808": 2, "time_pencil": 4,
             "signal_torch": 3, "zloty": 30},
        missions={"sabotage": 3, "receive_drop": 3, "eliminate": 2, "rescue_airman": 1},
        desc="'The silent and unseen': 316 Poles trained in Britain and parachuted home to fight with the "
             "Home Army. A third of them died."),
    "nkvd_partisan": dict(
        name="Partisan organiser", service="Central Staff of the Partisan Movement", nations=["ussr"],
        years=(1941.6, 1944.9), unit_types=["razvedka"],
        kit={"ppsh": 1, "ammo_762t": 2, "nr40": 1, "tol_block": 3, "time_pencil": 2, "sever_radio": 1,
             "signal_torch": 3},
        missions={"sabotage": 4, "receive_drop": 3, "eliminate": 2},
        desc="Flown or walked through the lines to turn bands of stragglers and villagers into a partisan "
             "brigade, blowing the railways the Wehrmacht lived on."),
    "gru_radio": dict(
        name="GRU intelligence agent", service="Main Intelligence Directorate (GRU)", nations=["ussr"],
        years=(1941.5, 1945.4), unit_types=["razvedka"],
        kit={"tt33": 1, "ammo_762t": 1, "sever_radio": 1, "one_time_pad": 1, "roubles": 30},
        missions={"wireless": 4, "photograph": 3, "steal_plans": 2},
        desc="Behind the German front with a Sever set, reporting every train, every division, every "
             "airfield."),
    "abwehr": dict(
        name="Abwehr agent", service="Abwehr II (sabotage)", nations=["germany"],
        years=(1939.7, 1944.1), unit_types=["brandenburger"],
        kit={"ppk": 1, "ammo_32acp": 2, "kampfmesser": 1, "tol_block": 2, "time_pencil": 3, "one_time_pad": 1},
        missions={"sabotage": 3, "photograph": 3, "steal_plans": 2},
        desc="Military intelligence's saboteurs: the men who went ahead of the panzers, and the ones who "
             "didn't come back."),
    "greif": dict(
        name="Operation Greif commando", service="Panzerbrigade 150 (Skorzeny)", nations=["germany"],
        years=(1944.9, 1945.1), unit_types=["brandenburger"], uniform="enemy",
        kit={"m1_carbine": 1, "ammo_30carb": 3, "m1911": 1, "ammo_45acp": 1, "tol_block": 2,
             "time_pencil": 2},
        missions={"sabotage": 3, "photograph": 2, "steal_plans": 1},
        desc="December 1944: English-speaking Germans in American uniforms and jeeps, cutting wires, turning "
             "signposts round and spreading panic behind the Ardennes front. Caught, they were shot as spies."),
    "sd_agent": dict(
        name="SD counter-intelligence agent", service="Sicherheitsdienst", nations=["germany"],
        years=(1940.4, 1945.3), unit_types=[],
        kit={"ppk": 1, "ammo_32acp": 2, "minox": 1, "one_time_pad": 1},
        missions={"photograph": 2, "steal_plans": 2, "eliminate": 2},
        desc="The Party's intelligence service. You hunt the resistance - and sometimes pretend to be it."),
    "nakano": dict(
        name="Nakano School intelligence officer", service="Rikugun Nakano Gakkō", nations=["japan"],
        years=(1938.5, 1945.7), unit_types=[],
        kit={"nambu14": 1, "ammo_8nambu": 2, "kampfmesser": 1, "tol_block": 2, "minox": 1},
        missions={"photograph": 3, "sabotage": 2, "steal_plans": 2},
        desc="The Army's school for spies and guerrillas: officers trained to pass as locals, and to fight on "
             "after defeat (Onoda was one)."),
}

# ---------------------------------------------------------------- missions
MISSIONS = {
    "steal_plans": dict(name="Steal the plans", night=True,
                        brief="Get into their headquarters, take the operation orders, and carry them home."),
    "sabotage": dict(name="Sabotage", night=True,
                     brief="Plant timed charges on the target and be well away before the time pencils run out."),
    "receive_drop": dict(name="Receive a supply drop", night=True,
                         brief="London has confirmed a drop tonight. Meet the reception committee at the dropping "
                               "zone, lay out the lights, bring the aircraft in, and get the containers away "
                               "before the enemy comes to see what the aircraft was."),
    "wireless": dict(name="Get the traffic out", night=False,
                     brief="Your sked is today. Transmit your reports to London from somewhere safe - each "
                           "minute on the air gives the detector vans a better bearing - and then move."),
    "eliminate": dict(name="Eliminate a target", night=True,
                      brief="A man who is killing the network: kill him, quietly if you can, and get out."),
    "rescue_airman": dict(name="An airman on the run", night=False,
                          brief="An Allied airman is hiding in a barn. Find him, give him clothes and papers, and "
                                "get him to the line - or to the pick-up."),
    "photograph": dict(name="Photograph their positions", night=False,
                       brief="Get close enough to their installations to photograph them with the Minox, and "
                             "bring the film home."),
}

# ---------------------------------------------------------------- cover identities (legends)
# by the language of the country you're in (world.py sector.lang): occupation, why you're on the roads,
# the extra papers and the tools of the trade
TRADES = [
    ("farm labourer", "hired by the day at the farms round here", ["work_permit"], []),
    ("railway worker", "a platelayer on this stretch of line - the Ausweis lets you walk the track", ["rail_pass"],
     ["spanner"]),
    ("commercial traveller", "selling agricultural machinery parts to the farms of the district", ["travel_permit"],
     []),
    ("doctor", "the country doctor, called out at any hour - the curfew pass is genuine", ["curfew_pass"],
     ["doctors_bag"]),
    ("priest", "the curate from the next parish, visiting the sick", ["curfew_pass"], ["breviary"]),
    ("schoolteacher", "on your way to your sister's, the school being shut", [], []),
    ("electrician", "an engineer from the power company, checking the lines", ["work_permit"], ["spanner"]),
    ("demobilised soldier", "discharged in 1940, looking for work", ["demob_papers"], []),
    ("black marketeer", "selling butter and eggs to anyone who pays", [], ["francs"]),
    ("forced labourer on leave", "back from a factory in the Reich on a fortnight's leave", ["work_permit"], []),
]
FEMALE_TRADES = [
    ("nurse", "a district nurse on her rounds", ["curfew_pass"], ["doctors_bag"]),
    ("shop girl", "going to her aunt's in the next town", [], []),
    ("secretary", "a typist at the prefecture, on her day off", ["work_permit"], []),
]
LOCAL_NAMES = {
    "fr": (["Jean", "Pierre", "Marcel", "André", "Louis", "Henri", "Georges", "Robert", "Lucien", "René"],
           ["Marie", "Jeanne", "Odette", "Yvonne", "Simone", "Denise", "Madeleine", "Paulette"],
           ["Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Lefèvre", "Girard", "Roux", "Fournier", "Morel"]),
    "be": (["Jan", "Pieter", "Joseph", "Albert", "Marcel", "Léon"], ["Maria", "Anna", "Josée", "Andrée"],
           ["Peeters", "Janssens", "Maes", "Jacobs", "Dubois", "Lambert", "Claes"]),
    "nl": (["Jan", "Willem", "Cornelis", "Hendrik", "Pieter", "Gerrit"], ["Johanna", "Maria", "Truus", "Hannie"],
           ["de Jong", "Jansen", "de Vries", "van den Berg", "Bakker", "Visser", "Smit"]),
    "pl": (["Jan", "Stanisław", "Józef", "Tadeusz", "Władysław", "Kazimierz"], ["Maria", "Halina", "Irena", "Zofia"],
           ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kamiński", "Lewandowski"]),
    "ru": (["Ivan", "Pyotr", "Nikolai", "Vasily", "Mikhail", "Grigory"], ["Anna", "Maria", "Olga", "Nina"],
           ["Ivanov", "Petrov", "Sidorov", "Kuznetsov", "Smirnov", "Popov"]),
    "uk": (["Mykola", "Ivan", "Petro", "Vasyl", "Taras", "Stepan"], ["Oksana", "Halyna", "Mariya", "Olena"],
           ["Kovalenko", "Bondarenko", "Shevchenko", "Tkachenko", "Kravchenko", "Melnyk"]),
    "it": (["Giuseppe", "Giovanni", "Antonio", "Mario", "Luigi", "Francesco"], ["Maria", "Anna", "Giuseppina", "Rosa"],
           ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano"]),
    "gr": (["Giorgos", "Nikos", "Manolis", "Yannis", "Kostas", "Andreas"], ["Maria", "Eleni", "Katerina", "Sofia"],
           ["Papadakis", "Kourakis", "Manousakis", "Xylouris", "Vlachos", "Petrakis"]),
    "de": (["Hans", "Karl", "Heinz", "Walter", "Kurt", "Otto"], ["Anna", "Gertrud", "Ilse", "Hildegard"],
           ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Becker"]),
    "fi": (["Matti", "Juho", "Eino", "Toivo", "Väinö"], ["Aino", "Helmi", "Lyyli"],
           ["Korhonen", "Virtanen", "Mäkinen", "Nieminen"]),
    "zh": (["Wang", "Li", "Zhang", "Liu", "Chen"], ["Mei", "Lan", "Hua"], ["Wei", "Jun", "Ming", "Hong"]),
    "en": (["John", "William", "George", "Thomas"], ["Mary", "Margaret", "Joan"], ["Smith", "Jones", "Brown"]),
    "ja": (["Tarō", "Ichirō", "Kenji", "Seitoku", "Kamado", "Chōei"], ["Tsuru", "Kama", "Ushi", "Nabe"],
           ["Higa", "Kinjō", "Ōshiro", "Miyagi", "Shimabukuro", "Chinen", "Tamashiro"]),
    "ar": (["Mohammed", "Ahmed", "Ali", "Hassan", "Omar", "Mahmoud"], ["Fatima", "Aisha", "Zeinab"],
           ["el-Masri", "Hassan", "Abdel Aziz", "Ibrahim", "Suleiman", "el-Obeidi"]),
    "in": (["Zhapu", "Visier", "Neikhriehu", "Kevi", "Angami"], ["Khrienuo", "Vikhono"],
           ["Angami", "Sema", "Lotha", "Ao", "Chakhesang"]),
    "my": (["Maung Ba", "Maung Tin", "Ko Hla", "U Thein"], ["Ma Mya", "Daw Khin"], ["", "", ""]),
    "mel": (["Jacob", "John", "Peter", "Daniel"], ["Mary", "Ruth"], ["Vouza", "Kuma", "Tome", "Bera"]),
}
PAPERS = {  # the documents on a cover, by country
    "fr": "carte d'identité",
    "be": "carte d'identité",
    "nl": "persoonsbewijs",
    "pl": "Kennkarte",
    "ru": "passport stamped by the German Ortskommandantur",
    "uk": "passport stamped by the German Ortskommandantur",
    "it": "carta d'identità",
    "gr": "identity card from the German Kommandantur",
    "de": "Kennkarte",
}
# SOE circuits went by trades; agents by a field name
CIRCUITS = ["STOCKBROKER", "WHEELWRIGHT", "FARMER", "SCIENTIST", "JOCKEY", "MONK", "HECKLER", "ACROBAT", "MINISTER",
            "PIMENTO", "SALESMAN", "DIGGER", "FIREMAN", "FREELANCE", "HEADMASTER", "PEDLAR", "ROVER", "SHIPWRIGHT",
            "SILVERSMITH", "TINKER", "WRESTLER", "CLERGYMAN", "DONKEYMAN", "GARDENER", "MARKSMAN", "PLANE"]
FIELD_NAMES = {True: ["Madeleine", "Louise", "Denise", "Paulette", "Hélène", "Odile", "Christine", "Marie"],
               False: ["Hilaire", "Alphonse", "Prosper", "Gilbert", "César", "Aristide", "Valentin", "Anatole",
                       "Fabien", "Gaspard", "Hector", "Urbain"]}

# ---------------------------------------------------------------- the aircraft that brought them
# the special-duties squadrons: (nation, aircraft id, name, the containers it carried)
SPECIAL_DUTIES = {
    "uk": ("halifax_sd", "No. 138 (Special Duties) Squadron RAF, Tempsford", 15),
    "france": ("halifax_sd", "No. 138 (Special Duties) Squadron RAF, Tempsford", 15),
    "poland": ("halifax_sd", "No. 1586 (Polish Special Duties) Flight", 12),
    "usa": ("b24_cb", "36th Bombardment Squadron, 801st BG 'Carpetbaggers'", 12),
    "ussr": ("li2", "101st Long-Range Aviation Regiment", 10),
    "germany": ("ju52", "Kampfgeschwader 200", 8),
    "japan": ("ki57", "Special transport chūtai", 6),
    "italy": ("sm79", "Squadriglia speciale", 6),
}
# what came down in a container: (item id, count range) - an SOE "C-type" load was sten guns, their
# magazines, grenades, plastic explosive, detonators, and whatever London thought of that week
CONTAINER_LOADS = [
    [("sten", (4, 6)), ("mag_9mm_32_smg", (12, 20)), ("ammo_9mm", (60, 120))],
    [("bren", (1, 1)), ("mag_303_30_lmg", (6, 10)), ("lee_no4", (2, 3)), ("ammo_303", (60, 100))],
    [("pe_808", (4, 8)), ("time_pencil", (8, 16)), ("mills", (6, 12)), ("gammon", (2, 4))],
    [("bandage", (10, 20)), ("morphine", (4, 8)), ("sulfa", (4, 8)), ("cigarettes", (10, 20)), ("chocolate", (4, 8))],
    [("liberator", (6, 10)), ("ammo_45acp", (30, 60)), ("m1911", (1, 2))],
    [("ration", (4, 8)), ("francs", (100, 400)), ("one_time_pad", (1, 2))],
]

# ---------------------------------------------------------------- the resistance (the partisans' own careers)
# missions include "ambush" (scenarios.py: the convoy on the road); the rest are the agents' missions, done as a band
RESISTANCE = {
    "maquis": dict(name="Maquisard", service="Forces Françaises de l'Intérieur (Armée Secrète)", nations=["france"],
                   years=(1943.0, 1944.95),
                   missions={"ambush": 4, "receive_drop": 3, "sabotage": 3, "rescue_airman": 1, "eliminate": 1},
                   desc="Young men who took to the hills rather than be sent to work in Germany, armed by parachute "
                        "and led - when they were lucky - by someone who knew what he was doing."),
    "ftp": dict(name="FTP partisan", service="Francs-Tireurs et Partisans (communist)", nations=["france"],
                years=(1941.5, 1944.95), missions={"sabotage": 3, "eliminate": 3, "ambush": 2},
                desc="The Communist Party's fighting arm: small groups, trains derailed, German officers shot in the "
                     "street - and hostages shot in reprisal."),
    "home_army": dict(name="Home Army soldier", service="Armia Krajowa (Home Army)", nations=["poland"],
                      years=(1939.7, 1945.0), missions={"sabotage": 3, "receive_drop": 2, "eliminate": 2, "ambush": 2},
                      desc="The underground army of the Polish state: a third of a million sworn soldiers, its own "
                           "courts, its own schools - and, in the forests, its partisan units."),
    "soviet_partisan": dict(name="Soviet partisan", service="Partisan brigade (Central Staff of the Partisan "
                            "Movement)", nations=["ussr"], years=(1941.6, 1944.9),
                            missions={"ambush": 3, "sabotage": 4, "receive_drop": 2, "eliminate": 1},
                            desc="Stragglers from the 1941 encirclements, villagers, Party men and escaped prisoners, "
                                 "in the forests and marshes. In the 'Rail War' of August 1943 they blew the track in "
                                 "tens of thousands of places in one night."),
    "chinese_guerrilla": dict(name="Guerrilla", service="Eighth Route Army guerrillas", nations=["china"],
                              years=(1937.5, 1945.7), missions={"ambush": 4, "sabotage": 3, "eliminate": 1},
                              desc="Behind the Japanese lines in the villages of the north: cut the roads and "
                                   "railways by night, farm by day."),
}
