"""Every item a particular one: whose it was, where it was made, what's written on it, what's in it.

A rifle has a maker's mark and a serial number, and perhaps initials carved in the butt; a man's identity
tags have his name, number and blood group in his army's format; a letter is from someone in his home town
about things that were really happening there; a newspaper carries the news of that week of the war.
Stamped when a soldier is made (spawn.make_soldier), so the kit on the dead is still theirs.

Item.data["flavor"]: a line shown when you examine it.  Letters, photographs and newspapers get
data["text"]: what you read or see when you use them.
"""
from __future__ import annotations

HOMETOWNS = {
    "usa": ["Dayton, Ohio", "Scranton, Pennsylvania", "Brooklyn", "Mobile, Alabama", "Duluth, Minnesota",
            "Fresno, California", "Lubbock, Texas", "Worcester, Massachusetts", "Paducah, Kentucky", "Tacoma, Washington",
            "Sioux City, Iowa", "Bangor, Maine"],
    "uk": ["Leeds", "Glasgow", "Bethnal Green", "Swansea", "Norwich", "Salford", "Portsmouth", "Belfast", "Carlisle",
           "Coventry"],
    "canada": ["Moose Jaw", "Winnipeg", "Halifax, Nova Scotia", "Trois-Rivières", "Sudbury"],
    "australia": ["Ballarat", "Wagga Wagga", "Fremantle", "Toowoomba", "Launceston"],
    "newzealand": ["Timaru", "Wanganui", "Invercargill", "Nelson"],
    "india": ["a village near Jullundur", "Rawalpindi", "a hill village in Garhwal", "Madras"],
    "germany": ["Dresden", "Hamburg-Altona", "a village near Ulm", "Königsberg", "Essen", "Breslau", "Kiel",
                "a farm in Lower Saxony", "Vienna", "Leipzig"],
    "ussr": ["a kolkhoz near Ryazan", "Gorky", "a village outside Kursk", "Sverdlovsk", "Tambov", "Kazan",
             "Chelyabinsk", "a village near Vologda", "Tashkent", "Kharkov"],
    "japan": ["Kagoshima", "a farming village in Nagano", "Sendai", "Kumamoto", "Osaka", "Hiroshima", "Niigata"],
    "italy": ["Naples", "a village in Calabria", "Bergamo", "Turin", "Palermo", "Florence"],
    "france": ["Lyon", "a village in the Morvan", "Marseille", "Quimper"],
    "poland": ["Lwów", "Kraków", "a village near Lublin", "Warsaw"],
    "finland": ["Viipuri", "Tampere", "a farm in Ostrobothnia"],
    "hungary": ["Debrecen", "Szeged", "Budapest"],
    "romania": ["Iași", "Craiova", "a village in Moldavia"],
    "china": ["a village in Hunan", "Changsha", "Chongqing"],
}
SWEETHEARTS = {"usa": ["Mary", "Dorothy", "Betty", "Helen", "Ruth", "Jean"], "uk": ["Joan", "Margaret", "Peggy", "Doris"],
               "germany": ["Ilse", "Gerda", "Liesel", "Hilde", "Käthe"], "ussr": ["Nina", "Valya", "Masha", "Katya"],
               "japan": ["Hanako", "Fumiko", "Yoshiko", "Kazuko"], "italy": ["Rosa", "Giulia", "Maria", "Lucia"],
               "france": ["Simone", "Yvette", "Jeanne"], "poland": ["Hanka", "Zosia", "Basia"]}
SENDERS = [("Mother", 4), ("your wife", 3), ("your girl", 3), ("your father", 1), ("your sister", 2),
           ("your brother", 1)]
# what home wrote about, by army: the war as it was at home
HOME_NEWS = {
    "usa": ["We saved the tin foil and the grease for the drive, and I bought another war bond.",
            "Gas is on the A-card now, three gallons a week, so we walk to church.",
            "The Hendersons' boy was reported missing in the Pacific. His mother won't take the flag down.",
            "Dad's working a double shift at the plant. They make parts for bombers now.",
            "The Dodgers lost again. Your brother says it's because you're not there to cheer."],
    "uk": ["The windows went again in the last raid but we're all right. Mrs Finch's house is gone.",
           "Two ounces of tea a week and I make it last. The Woolton pie was dreadful.",
           "The Americans have come to the village. They've got everything, and they give the children gum.",
           "Your father's on fire-watching three nights a week and his Home Guard the other nights.",
           "Our Jean has joined the ATS and is on the guns somewhere on the coast."],
    "germany": ["The raids are every night now. We sleep in the cellar with our coats on.",
                "The coal ration is short again; Mother burns the old chairs.",
                "Frau Müller's son has fallen in the East. The notice was in the paper, with the Iron Cross.",
                "They've taken Karl for the Volkssturm, at fifty-eight, with his bad leg.",
                "The children were sent to the country with the school. We miss them terribly."],
    "ussr": ["We were evacuated beyond the Volga; I work in the factory now, twelve hours, making shells.",
             "The kolkhoz harvest is all women and old men. We did it anyway.",
             "We had no word of Petya since the summer. Write if you hear anything.",
             "The Germans burned the village when they left. We live in the dugout by the river.",
             "Your little sister joined the Komsomol and knits mittens for the front."],
    "japan": ["We pray for you at the shrine every morning. Please do not worry about us.",
              "The rice ration is smaller, but we grow sweet potatoes in the school yard.",
              "The neighbourhood association made another senninbari; I stood on the corner for three days.",
              "Your father says to serve the Emperor bravely and not to shame the family.",
              "The air raid drills are every week now, with buckets of water and bamboo spears."],
    "italy": ["There's no bread, and the Germans take what there is. Your mother cries at night.",
              "We heard the King has dismissed him. Nobody knows what will happen now.",
              "Tonino has gone to the mountains with the others. Don't tell anyone.",
              "The bombers came over Naples again; the port is burning."],
    "france": ["We have had no news of your father since they took him to Germany for the STO.",
               "The Germans requisitioned the horses. We pull the plough ourselves."],
    "poland": ["They took the Nowaks away in a lorry at night. We don't speak of it.",
               "We keep your room ready. God keep you."],
}
GENERIC_NEWS = ["We are all well, thank God, though there is little to eat.", "The house is cold; we manage.",
                "Your grandmother asks after you every day.", "The soldiers took the chickens again."]
GENERIC_PHOTO = ["A family in their best clothes, stiff before the camera.", "A young woman at a garden gate.",
                 "An old couple on a bench in front of a house."]
LETTER_END = {
    "usa": ["Come home safe. All my love.", "Keep your head down, son.", "Write when you can. We read every word."],
    "uk": ["Keep your chin up, love.", "Come home to us.", "All my love, and mind you keep warm."],
    "germany": ["Komm gesund nach Hause.", "Mit tausend Grüßen und Küssen.", "Gott schütze dich."],
    "ussr": ["Smash the fascists and come home.", "We wait for you.", "Kisses, a thousand times."],
    "japan": ["Take care of your body.", "Serve with honour. We wait for you."],
    "italy": ["Torna presto.", "Ti bacio, tua mamma."],
}
PHOTOS = {
    "usa": ["A girl in a summer dress on the steps of a bakery, squinting into the sun.",
            "A family in their Sunday best on a porch: a mother, a father, three kids and a dog.",
            "Two boys in baseball uniforms, arms round each other's shoulders.",
            "A baby in a christening gown. On the back: 'Your son, 3 months'."],
    "uk": ["A young woman in a WAAF uniform, laughing.", "A terrace of houses; a family at the door.",
           "A wedding group outside a chapel, all hats and borrowed suits."],
    "germany": ["A young woman with plaited hair beside a bicycle.", "A family at a café table in the Tiergarten.",
                "A group of men in uniform at a Christmas tree, 1939, all smiling.",
                "A little girl on a rocking horse. On the back: 'Deine Liesel'."],
    "ussr": ["A young woman in a headscarf, very serious.", "A family by a stove, the grandmother in the middle.",
             "A boy in a Pioneer's red kerchief."],
    "japan": ["A formal portrait: his mother and father, kneeling.", "A young woman in a kimono beneath a cherry tree.",
              "A group of schoolboys in caps outside a wooden school."],
    "italy": ["A woman holding a baby on a whitewashed doorstep.", "A family at a long table under a vine."],
}
# makers: (gun id, [marks])
MAKERS = {
    "m1_garand": ["Springfield Armory", "Winchester Repeating Arms"],
    "m1_carbine": ["Inland Div. General Motors", "Winchester", "Underwood", "Rock-Ola", "Quality Hardware",
                   "I.B.M. Corp.", "Saginaw S.G.", "National Postal Meter", "Standard Products"],
    "m1903": ["Springfield Armory", "Remington", "Smith-Corona"], "m1903a4": ["Remington"],
    "thompson_1928": ["Auto-Ordnance, Bridgeport", "Savage Arms"], "thompson_m1a1": ["Auto-Ordnance", "Savage Arms"],
    "m3_grease": ["Guide Lamp Div. General Motors"],
    "m1911": ["Colt", "Remington Rand", "Ithaca", "Union Switch & Signal"],
    "bar": ["New England Small Arms", "I.B.M. Corp.", "Winchester"],
    "kar98k": ["byf (Mauser, Oberndorf)", "ar (Mauser, Borsigwalde)", "bnz (Steyr)", "dot (Brno)"],
    "mp40": ["ayf (Erma, Erfurt)", "bnz (Steyr)", "fxo (Haenel, Suhl)"],
    "p38": ["ac (Walther)", "byf (Mauser)", "cyq (Spreewerk)"],
    "mosin": ["Izhevsk (the arrow in a triangle)", "Tula (the star)"],
    "lee_no4": ["ROF Fazakerley", "ROF Maltby", "Long Branch", "Savage - U.S. PROPERTY"],
    "smle": ["BSA", "LSA", "Enfield", "Lithgow", "Ishapore"],
    "sten": ["Lines Bros. (the toymakers)", "BSA", "ROF Fazakerley", "Long Branch"],
    "bren": ["Enfield", "Inglis, Toronto", "Lithgow"],
    "type99": ["Nagoya Arsenal", "Kokura Arsenal", "Tokyo Arsenal (Koishikawa)"],
    "type38": ["Kokura Arsenal", "Tokyo Arsenal (Koishikawa)", "Nagoya Arsenal"],
    "carcano": ["Terni", "Gardone", "FNA Brescia"],
}
MARKINGS = ["the bluing worn silver at the edges", "the woodwork dark with years of oil", "brand new, still stiff",
            "a crack in the stock bound with wire", "a sling of webbing mended with string",
            "the front sight filed down a touch", "a spot of rust nobody could shift"]
CARVINGS = ["initials carved in the butt: '{init}'", "a name scratched on the receiver: '{name}'",
            "a small cross cut into the stock", "a line of notches cut in the stock",
            "'{town}' burned into the stock with a hot nail"]


def _initials(owner):
    parts = owner.name.split()
    return ".".join(p[0] for p in parts if p) + "." if parts else "?"


def stamp(game, it, owner=None, nation=None):
    """Give this item its particulars (idempotent: a stamped item keeps its story)."""
    if it.data and it.data.get("flavor"):
        return
    rng = game.rng
    t = it.t
    nat = getattr(owner, "nation", None) or nation or (t.nations[0] if t.nations else "usa")
    lf = None
    if owner is not None and hasattr(owner, "ai"):
        from .people import life
        lf = life(owner)                        # (his own town, his own girl: every letter from the same place)
    town = lf["town"] if lf else rng.choice(HOMETOWNS.get(nat) or ["home"])
    line = None
    text = None
    if t.kind == "gun" and t.cat not in ("mortar", "at_disposable"):
        maker = MAKERS.get(t.id)
        serial = rng.randint(10000, 3999999) if nat == "usa" else rng.randint(1000, 99999)
        bits = [f"{rng.choice(maker)}, serial {serial:,}" if maker else f"serial {serial:,}"]
        if t.id in ("kar98k", "mp40", "p38", "g43", "mg42", "mg34", "stg44"):
            bits.append(f"'{str(int(game.year) - rng.randint(0, 3))[-2:]}' and the Waffenamt eagle")
        if t.id in ("type99", "type38"):
            bits.append("the chrysanthemum on the receiver")
        bits.append(rng.choice(MARKINGS))
        if owner is not None and rng.random() < 0.18:
            bits.append(rng.choice(CARVINGS).format(init=_initials(owner), name=owner.name.split()[-1], town=town.split(",")[0]))
        line = "; ".join(bits) + "."
    elif t.tool == "dogtags" and owner is not None:
        line = _tags(game, owner)
    elif t.tool == "letter":
        who = rng.choices([s for s, _w in SENDERS], [w for _s, w in SENDERS])[0]
        if lf is not None:
            fam = lf["family"]
            if who == "your wife" and fam != "married":
                who = "Mother"
            elif who == "your girl" and fam not in ("a girl", "engaged"):
                who = "your sister"
            if who in ("your wife", "your girl") and lf["partner"]:
                who = f"{lf['partner']}" + (", your wife" if who == "your wife" else "")
        news = HOME_NEWS.get(nat) or GENERIC_NEWS
        a, b = rng.sample(news, 2) if len(news) > 1 else (news[0], news[0])
        end = rng.choice(LETTER_END.get(nat) or ["God keep you."])
        text = f"A letter from {who}, {town}. '...{a} {b} {end}'"
        line = f"From {who}, {town}. Read soft."
    elif t.tool == "photo" and t.id == "photo":
        text = rng.choice(PHOTOS.get(nat) or GENERIC_PHOTO)
        line = text
    elif t.tool in ("watch", "lighter", "ring") and owner is not None and rng.random() < 0.4:
        first = owner.name.split()[0]
        line = rng.choice([f"Engraved: 'To {first}, from Mother, Christmas {int(game.year) - rng.randint(1, 4)}'.",
                           f"Engraved on the back: '{_initials(owner)} - {town.split(',')[0]}'.",
                           "Engraved: 'Come home to me.'", f"Engraved: '{first} & {rng.choice(SWEETHEARTS.get(nat, SWEETHEARTS['usa']))}'."])
    elif t.tool == "newspaper":
        text = headline(game, t.id)
        line = text
    elif t.tool == "document" and t.id == "diary" and owner is not None:
        text = _diary(game, owner)
        line = "The last entries are the ones that matter."
    if line is None and text is None:
        return
    it.data = dict(it.data or {})
    if line:
        it.data["flavor"] = line
    if text:
        it.data["text"] = text
    if owner is not None:
        it.data.setdefault("owner", owner.name)


def _tags(game, a):
    rng = game.rng
    blood = rng.choices(["O", "A", "B", "AB"], [45, 40, 11, 4])[0]
    nat = a.nation
    if nat == "usa":
        rel = rng.choices(["P", "C", "H", ""], [60, 32, 4, 4])[0]
        num = f"{rng.randint(31, 39)} {rng.randint(100, 999)} {rng.randint(100, 999)}"
        return f"{a.name.upper()} / {num} / T{str(int(game.year) - 1)[-2:]} {str(int(game.year))[-2:]} {blood} {rel}".strip()
    if nat in ("uk", "canada", "australia", "newzealand", "india"):
        rel = rng.choice(["C of E", "RC", "METH", "PRES", "C of S"])
        return f"Two fibre discs, red and green: {a.name.split()[-1].upper()} {a.name[0]} / {rng.randint(1000000, 9999999)} / {rel}"
    if nat == "germany":
        return (f"An oval zinc Erkennungsmarke, perforated to snap in half: '{rng.randint(1, 14)}./I.R. "
                f"{rng.randint(1, 600)}  {rng.randint(1, 900)}  {blood}'. Half stays with the body, half goes to the "
                f"company.")
    return f"{a.name}, {rng.randint(10000, 99999)}"


def _diary(game, a):
    rng = game.rng
    lines = {"japan": ["We have not eaten rice for eleven days. The men dig for roots.",
                       "The enemy's shells never stop. At night their flares make it day.",
                       "Lieutenant Tanaka died of fever. We burned a finger for his family.",
                       "Tonight we attack. I have written to Mother. Long live the Emperor."],
             "germany": ["The Ivans came again at dawn, singing. We had forty rounds a man.",
                         "Mail at last. Nothing from Hilde.", "The Amis have everything - aircraft, guns, petrol.",
                         "Only nine of the company left who came out from home."],
             "usa": ["Rain, mud, K-rations. Can't remember being dry.", "Lost Eddie today. Just like that.",
                     "The old men of the company are the ones who've been here three weeks."],
             "ussr": ["Took the village back. Nothing left of it but chimneys.",
                      "Wrote to Mother. Told her I'm in the reserve and safe."]}.get(a.nation) or \
        ["Another day of waiting.", "They say we move tonight."]
    return "A diary, in pencil: '" + " ... ".join(rng.sample(lines, min(2, len(lines)))) + "'"


# ---------------------------------------------------------------- the news, as the papers told it
# (year, month, day, sides that printed it, the headline)
NEWS = [
    (1939, 9, 1, ("axis",), "The Führer to the Reichstag: 'Since 5.45 we have been returning fire.'"),
    (1939, 9, 3, ("allies",), "BRITAIN AND FRANCE AT WAR WITH GERMANY."),
    (1940, 6, 4, ("allies",), "THE MIRACLE OF DUNKIRK: 335,000 MEN HOME FROM THE BEACHES."),
    (1940, 6, 14, ("axis",), "German troops enter Paris."),
    (1940, 9, 15, ("allies",), "RAF'S GREATEST DAY: 185 RAIDERS DOWN."),
    (1941, 6, 22, ("allies", "ussr"), "Molotov on the radio: 'Our cause is just. The enemy will be beaten. Victory "
                                      "will be ours.'"),
    (1941, 12, 7, ("allies",), "JAPS BOMB PEARL HARBOR - U.S. AT WAR."),
    (1941, 12, 8, ("axis",), "Imperial Headquarters: a state of war in the western Pacific; a great victory at "
                             "Hawaii."),
    (1941, 12, 13, ("ussr",), "The German plan to encircle and take Moscow has failed."),
    (1942, 2, 15, ("axis",), "Singapore has fallen."),
    (1942, 6, 7, ("allies",), "JAP FLEET SMASHED AT MIDWAY."),
    (1942, 11, 4, ("allies",), "ROMMEL IN FULL RETREAT - EIGHTH ARMY BREAKS THROUGH AT ALAMEIN."),
    (1942, 11, 8, ("allies",), "AMERICAN TROOPS LAND IN NORTH AFRICA."),
    (1943, 2, 3, ("axis",), "The battle for Stalingrad is over. They died so that Germany might live."),
    (1943, 2, 2, ("ussr", "allies"), "The encircled German forces at Stalingrad have surrendered."),
    (1943, 7, 10, ("allies",), "ALLIES INVADE SICILY."),
    (1943, 9, 8, ("allies",), "ITALY SURRENDERS."),
    (1944, 6, 4, ("allies",), "FIFTH ARMY ENTERS ROME."),
    (1944, 6, 6, ("allies",), "ALLIES LAND IN FRANCE - 'THE TIDE HAS TURNED'."),
    (1944, 6, 7, ("axis",), "The long-awaited invasion has begun: the enemy is being thrown back into the sea."),
    (1944, 8, 25, ("allies",), "PARIS LIBERATED."),
    (1944, 12, 20, ("axis",), "Our offensive in the West: the Americans in headlong flight."),
    (1944, 12, 27, ("allies",), "PATTON RELIEVES BASTOGNE - 'NUTS!'"),
    (1945, 4, 13, ("allies",), "PRESIDENT ROOSEVELT IS DEAD."),
    (1945, 5, 2, ("ussr",), "The Red Banner over the Reichstag. Berlin has fallen."),
    (1945, 5, 8, ("allies", "ussr"), "VICTORY IN EUROPE."),
]


def headline(game, tid):
    """The latest real headline this paper (by its side) would have printed by today."""
    import datetime
    now = game.now().date() if hasattr(game.now(), "date") else game.now()
    side = {"stars_and_stripes": "allies", "yank": "allies", "signal_mag": "axis", "krasnaya_zvezda": "ussr"}.get(tid, "allies")
    best = None
    for y, m, d, sides, text in NEWS:
        if side in sides and datetime.date(y, m, d) <= now:
            best = (datetime.date(y, m, d), text)
    name = {"stars_and_stripes": "Stars and Stripes", "yank": "Yank", "signal_mag": "Signal",
            "krasnaya_zvezda": "Krasnaya Zvezda"}.get(tid, "The paper")
    if best is None:
        return f"{name}: nothing but the war news, days old."
    return f"{name}, {best[0].strftime('%d %B %Y').lstrip('0')}: {best[1]}"
