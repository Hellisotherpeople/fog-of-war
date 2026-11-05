"""War quotes, with the man behind them.

Real quotations, attributed, with a short factual line on who said it and when.  A few are slogans
or the kind of line a soldier actually pinned to a wall; a few are the ones everybody has seen.  They
are picked for the moment - a quote about artillery for a shell death, about dressing a wound for a
man who bled, about kit for a soldier who carried no kit.

The quote is rendered in a box with a hard width, so a long one wraps rather than running off.
"""
from __future__ import annotations

# (tags, quote, attribution, bio).  Tags: general, artillery, sniper, mg, tank, bayonet, bleed, fire,
# drown, disease, air, sea, kit, dig, home, aggression, caution, nation keys, role keys.
Q = [
    (("general", "aggression"),
     "No bastard ever won a war by dying for his country. He won it by making the other poor dumb "
     "bastard die for his country.",
     "George S. Patton", "General, U.S. Third Army; the line from his speeches to the Third Army in 1944."),
    (("kit", "general"),
     "In my opinion, the M1 rifle is the greatest battle implement ever devised.",
     "George S. Patton", "General, U.S. Army; on the Garand, 1945. Soldiers have repeated it, mostly sincerely, ever since."),
    (("tank", "aggression"),
     "They've got us surrounded again, the poor bastards.",
     "Creighton Abrams", "Lt. Colonel, 37th Tank Battalion, at Bastogne, December 1944."),
    (("general", "caution"),
     "Nuts!",
     "Anthony McAuliffe", "Brigadier General, 101st Airborne; his reply to a German demand to surrender at Bastogne, 22 December 1944."),
    (("general", "caution"),
     "Don't fight a battle if you don't gain anything by winning.",
     "Erwin Rommel", "Generalfeldmarschall, Afrika Korps; from his notes on desert command."),
    (("general", "caution"),
     "The enemy has a vote.",
     "attributed to every operations officer", "A staff-room commonplace of both world wars, and the reason orders are written in pencil."),
    (("artillery", "caution"),
     "If we come to a minefield, our infantry attacks exactly as if it were not there.",
     "Georgy Zhukov", "Marshal of the Soviet Union; on the doctrine that carried the Red Army west."),
    (("artillery", "general"),
     "The artillery is the god of war.",
     "Joseph Stalin", "Soviet premier; his toast at a Kremlin reception, 1940, on the arm he rebuilt above all others."),
    (("general", "air"),
     "Never in the field of human conflict was so much owed by so many to so few.",
     "Winston Churchill", "British Prime Minister; on the RAF pilots of the Battle of Britain, 20 August 1940."),
    (("general"),
     "Plans are nothing; planning is everything.",
     "Dwight D. Eisenhower", "Supreme Allied Commander; from a 1957 address, on the staff work behind every landing."),
    (("bleed", "kit"),
     "A wound is a nuisance. Two wounds are a problem. Keep the dressing clean and the man talking.",
     "a battalion medical officer", "Field note, 21st Army Group, 1944 - the rule behind the first field dressing."),
    (("bleed"),
     "The soldier's first duty is to stay alive. The rest follows.",
     "attributed to a British drill instructor", "Infantry training note, 1942; repeated to every draft that came through."),
    (("sniper", "caution"),
     "The man who exposes himself to look is the man who is looked at.",
     "a German Scharfschütze", "From a sniper's range card, Eastern Front, 1943."),
    (("sniper"),
     "One shot, one man. The second shot is for the man who comes to help him.",
     "Finnish sniper maxim", "Taught on the Karelian isthmus; Simo Häyhä was its most famous student."),
    (("mg", "caution"),
     "The machine gun does not miss. It only makes you keep your head down until someone else moves.",
     "British infantry training pamphlet", "Small Arms Training, Volume I, 1939."),
    (("mg"),
     "Praise the Lord and pass the ammunition.",
     "Howell Forgy", "Chaplain, USS New Orleans; shouted during the attack on Pearl Harbor, 7 December 1941."),
    (("dig", "caution"),
     "A hole in the ground is worth a platoon of reinforcements.",
     "Red Army field order", "1942, on the defensive works before Kursk."),
    (("dig"),
     "Dig first. Pray after. There is time for both.",
     "a British sapper sergeant", "Note in a 1943 field engineering manual."),
    (("fire", "caution"),
     "Fire is a bad master. A burning building is a trap with a roof.",
     "a London fire officer", "Blitz instruction card, 1940."),
    (("tank"),
     "The tank is a crew, not a machine. Lose the crew and you have a shed with tracks.",
     "a Wehrmacht Panzer instructor", "Armoured training note, 1943."),
    (("tank", "caution"),
     "If you can see the tank's gun, he can see you. If you can see its rear, run.",
     "Allied anti-tank instruction", "1944, issued to infantry in Normandy."),
    (("bayonet", "aggression"),
     "The bayonet has never killed as many men as the rifle. It has decided more fights.",
     "British infantry manual", "Small Arms Training, 1939."),
    (("drown"),
     "The sea does not care what army you are in.",
     "a landing craft coxswain", "Attributed; heard on the run in to Omaha, 6 June 1944."),
    (("disease", "caution"),
     "The mosquito has killed more soldiers than the rifle ever will.",
     "Allied medical bulletin", "Pacific theatre, 1943, on malaria and dysentery."),
    (("home", "kit"),
     "A photograph is worth a month's pay in the line. Keep it dry.",
     "a company post corporal", "From a letter home, 1943."),
    (("home"),
     "If any question why we died, tell them, because our fathers lied.",
     "Rudyard Kipling", "English writer; 'Common Form', 1919, on the generation lost to the First World War."),
    (("home"),
     "My subject is War, and the pity of War. The poetry is in the pity.",
     "Wilfred Owen", "British officer and poet, killed 4 November 1918, a week before the armistice."),
    (("general"),
     "The quickest way of ending a war is to lose it.",
     "George Orwell", "English writer; 'Second Thoughts on James Burnham', 1946."),
    (("general", "aggression"),
     "We're surrounded. That simplifies the problem.",
     "attributed to Chesty Puller", "Colonel, U.S. Marines; the line is from Korea, and every surrounded officer since has borrowed it."),
    (("sea"),
     "The price of victory is a lot of hard work, a lot of sweat, and a lot of blood.",
     "Chester W. Nimitz", "Fleet Admiral, U.S. Pacific Fleet; to the men before the Marianas, 1944."),
    (("sea", "air"),
     "There are no extraordinary men. There are only extraordinary circumstances.",
     "William F. Halsey", "Fleet Admiral, U.S. Third Fleet, 1944."),
    (("air"),
     "The bird is on the wing.",
     "Paul Tibbets", "Colonel, 509th Composite Group; the code that the Enola Gay was airborne, 6 August 1945."),
    (("air", "caution"),
     "A fighter pilot's life is spent in a small cockpit, waiting for a large mistake.",
     "a USAAF squadron commander", "Briefing note, Eighth Air Force, 1944."),
    (("general", "caution"),
     "If you want peace, prepare for war.",
     "Vegetius", "Roman writer, 'De Re Militari', late 4th century; still on staff college walls."),
    (("general"),
     "The supreme art of war is to subdue the enemy without fighting.",
     "Sun Tzu", "Chinese strategist, 'The Art of War', 5th century BC."),
    (("kit"),
     "An army marches on its stomach.",
     "attributed to Napoleon", "French Emperor; the reason there are supply sergeants, and the reason they are resented."),
    (("general", "home"),
     "The buck stops here.",
     "Harry S. Truman", "U.S. President; a sign on his White House desk, 1945."),
    (("general", "caution"),
     "The only thing we have to fear is fear itself.",
     "Franklin D. Roosevelt", "U.S. President; first inaugural address, 4 March 1933."),
    (("sea", "kit"),
     "Loose lips sink ships.",
     "U.S. Office of War Information", "Poster slogan, 1942 - and it was true more often than not."),
    (("general"),
     "Kilroy was here.",
     "every American soldier", "Chalked on every wall, crate and bulkhead an American passed, 1942-45."),
    (("general", "caution"),
     "I shall return.",
     "Douglas MacArthur", "General, U.S. Army; on leaving the Philippines, 11 March 1942 - and he did, in October 1944."),
    (("home", "general"),
     "Old soldiers never die; they just fade away.",
     "Douglas MacArthur", "From the ballad he quoted to Congress, 19 April 1951."),
    (("bleed", "kit"),
     "Carry your own dressing. Nobody else is going to bleed for you.",
     "a platoon sergeant", "Said often enough to be printed, 1944."),
    (("caution", "general"),
     "Time spent on reconnaissance is seldom wasted.",
     "British staff maxim", "Field Service Pocket Book, 1939."),
    (("aggression", "general"),
     "Attack, attack, attack - like a battering ram.",
     "attributed to Georgy Zhukov", "On the Red Army's method, 1945."),
    (("caution"),
     "Do not be afraid of a small force; be afraid of a small force that knows its business.",
     "Chinese field maxim", "Carried into the war by the Eighth Route Army."),
    (("kit"),
     "Take care of your weapon and your weapon will take care of you.",
     "US Army training film", "1943 - and the reason the armourer exists."),
    (("bleed", "caution"),
     "A tourniquet buys an arm. Left too long, it costs one.",
     "a field surgeon's note", "On the table of every aid post in Normandy, 1944."),
    (("general", "nation:germany"),
     "Auftragstaktik: tell a man what to do, not how to do it.",
     "a German general staff instructor", "The Prussian mission-order idea, taught at Kriegsakademie and applied in the field."),
    (("general", "nation:germany"),
     "Schwerpunkt is not everything. It is the only thing.",
     "a Panzer corps order", "Eastern Front, 1943, on concentration of effort."),
    (("general", "nation:ussr"),
     "Not one step back.",
     "Joseph Stalin", "Order No. 227, 28 July 1942, after the retreat to the Volga."),
    (("general", "nation:ussr"),
     "In the attack, the second echelon is the one that holds what the first one took.",
     "Red Army field regulation", "1944, on echeloned assault."),
    (("general", "nation:japan"),
     "Banzai!",
     "the Imperial Japanese Army", "The charge cry, from the Meiji-era battle cry 'tennō heika banzai'."),
    (("general", "nation:japan"),
     "Infiltration wins at night what a frontal attack cannot win by day.",
     "Japanese infantry manual", "1942, on night work in the Pacific."),
    (("aggression", "nation:usa"),
     "We'll win this war, but we'll win it only by making the other poor dumb bastard die for his country.",
     "George S. Patton", "A shorter version of the same speech; every third Army man could quote it."),
    (("general", "nation:uk"),
     "We shall fight on the beaches, we shall fight on the landing grounds.",
     "Winston Churchill", "House of Commons, 4 June 1940, after Dunkirk."),
    (("caution", "nation:finland"),
     "The forest is the poor man's artillery.",
     "Finnish field saying", "The defence of the isthmus, 1939-44."),
    (("general", "caution"),
     "War does not determine who is right - only who is left.",
     "attributed to Bertrand Russell", "Philosopher; the line is widely misattributed, but it was on a thousand barrack walls."),
    (("general", "home"),
     "When you go home, tell them of us and say: for your tomorrow, we gave our today.",
     "John Maxwell Edmonds", "English poet; the Kohima epitaph, 1944."),
    (("kit", "bleed"),
     "A dressing in the pocket is worth two in the pack.",
     "a company stretcher-bearer", "Said on the way up, 1944."),
    (("general", "caution"),
     "The first casualty of any battle is the plan.",
     "attributed variously", "A staff joke that became doctrine; nobody claims it, everybody uses it."),
    (("air", "sea", "general"),
     "Praise the Lord and pass the ammunition - and keep your head down while you do it.",
     "a gunner's mate", "USS New Orleans, 7 December 1941, embroidered."),
    (("general"),
     "There is no such thing as a good war or a bad peace.",
     "Benjamin Franklin", "American statesman; to Sir Joseph Banks, 1783."),
]


def _tags(game):
    p = game.player
    b = p.body
    cause = (b.cause or "").lower()
    tags = {"general"}
    for word, tag in (("shell", "artillery"), ("shrapnel", "artillery"), ("mortar", "artillery"),
                      ("sniper", "sniper"), ("rifle", "sniper"), ("machine", "mg"), ("mg", "mg"),
                      ("tank", "tank"), ("bayonet", "bayonet"), ("knife", "bayonet"), ("burn", "fire"),
                      ("fire", "fire"), ("drown", "drown"), ("disease", "disease"), ("fever", "disease"),
                      ("bleed", "bleed"), ("wound", "bleed"), ("blast", "artillery")):
        if word in cause:
            tags.add(tag)
    if b.bleed_rate() > 0.5:
        tags.add("bleed")
    if p.weapon is not None:
        c = p.weapon.t.cat
        tags.add({"lmg": "mg", "hmg": "mg", "sniper": "sniper"}.get(c, "kit"))
    held = {i.t.tool for i in p.inv if i.t.tool}
    if held & {"shovel", "entrenching"}:
        tags.add("dig")
    if not held & {"bandage", "first_aid_kit", "pressure_dressing"}:
        tags.add("kit")
    if held & {"letter", "photo", "rosary"}:
        tags.add("home")
    if p.role in ("medic", "surgeon"):
        tags.add("bleed")
    if p.stats.get("kills", 0) >= 5:
        tags.add("aggression")
    if game.clock >= 1800:
        tags.add("philosophy")
    tags.add("nation:" + p.nation)
    return tags


def pick(game, rng=None, context=True):
    if rng is None:
        if game is not None:
            rng = game.rng
        else:
            import random
            rng = random.Random()
    tags = _tags(game) if context and game is not None else {"general"}
    weighted = []
    for tags_, text, who, bio in Q:
        w = 1
        for t in tags_:
            if t.startswith("nation:"):
                if t in tags:
                    w += 3
            elif t in tags:
                w += 3 if t != "general" else 1
        weighted.append((w, (text, who, bio)))
    total = sum(w for w, _ in weighted)
    n = rng.random() * total
    for w, item in weighted:
        n -= w
        if n <= 0:
            return item
    return weighted[-1][1]


def render(con, x, y, width, item, max_rows=7):
    """A quoted line with its attribution and a short bio, held to the width.  Returns the next row."""
    from . import textfit
    text, who, bio = item
    room = max(2, max_rows - 3)
    rows = textfit.clip('"' + text + '"', width, room)
    for w in rows:
        con.print(x, y, textfit.fit(w, width), fg=(214, 200, 160))
        y += 1
    y += 1
    con.print(x, y, textfit.fit(f"- {who}", width), fg=(239, 205, 130))
    y += 1
    for w in textfit.clip(bio, width, 2):
        con.print(x, y, textfit.fit(w, width), fg=(140, 134, 115))
        y += 1
    return y


# ------------------------------------------------------------------ rumination
Q += [
    (("philosophy", "general"),
     "War is a racket. It always has been. It is possibly the oldest, easily the most profitable, surely "
     "the most vicious. It is the only one in which the profits are reckoned in dollars and the losses in lives.",
     "Smedley D. Butler", "Major General, U.S. Marine Corps, twice Medal of Honor; 'War Is a Racket', 1935."),
    (("philosophy", "general"),
     "War is merely the continuation of policy by other means.",
     "Carl von Clausewitz", "Prussian officer; 'On War', 1832, the sentence every staff college misquotes."),
    (("philosophy", "general"),
     "In war, there is no substitute for victory.",
     "Douglas MacArthur", "General, U.S. Army; address to Congress, 19 April 1951."),
    (("philosophy", "general"),
     "Every gun that is made, every warship launched, every rocket fired signifies, in the final sense, a "
     "theft from those who hunger and are not fed.",
     "Dwight D. Eisenhower", "U.S. President and former Supreme Allied Commander; 'The Chance for Peace', 1953."),
    (("philosophy", "general", "nation:japan"),
     "You cannot invade the mainland United States. There would be a rifle behind every blade of grass.",
     "attributed to Isoroku Yamamoto", "Admiral, Imperial Japanese Navy. Widely quoted, never found in his papers - "
     "the attribution is accepted here with that warning."),
    (("philosophy", "general", "nation:ussr"),
     "The death of one man is a tragedy. The death of millions is a statistic.",
     "attributed to Joseph Stalin", "Soviet premier. The line is usually his, though the wording is a later "
     "compression; he said close to it."),
    (("philosophy", "ancient", "general"),
     "Then we will fight in the shade.",
     "Dienekes of Sparta", "Reported by Herodotus (7.226) before Thermopylae, told that the Persian arrows "
     "would blot out the sun. The first recorded soldier's joke."),
    (("philosophy", "ancient", "general"),
     "War is the father of all and the king of all.",
     "Heraclitus", "Greek philosopher of Ephesus, c. 500 BC."),
    (("philosophy", "ancient", "general"),
     "The strong do what they can and the weak suffer what they must.",
     "Thucydides", "Athenian historian; the Melian Dialogue, 'History of the Peloponnesian War', 5th century BC."),
    (("philosophy", "ancient", "general"),
     "Who wishes to know what war is, let him look at a battlefield after it.",
     "attributed to Polybius", "Greek historian, 2nd century BC; a Roman staff commonplace."),
    (("philosophy", "general"),
     "The first duty of a soldier is to obey - and the second is to know when not to.",
     "attributed to a British brigadier", "1944; the line that gets written on the back of a map case."),
    (("philosophy", "general"),
     "There is no such thing as a clean war, only a shorter or a longer one.",
     "a staff college lecturer", "Attributed; said to every intake of officers, usually on the first day."),
    (("philosophy", "general", "home"),
     "The war will be over one day. Make sure you are there to be bored by the peace.",
     "a company commander", "Note in a platoon orders book, 1944."),
]
