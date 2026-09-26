"""Belligerent nations: names, doctrine, shouts, equipment sources."""
from __future__ import annotations

import random

from ..constants import ALLIES, AXIS

# Doctrine keys:
#   morale     base morale 0-100
#   training   0-10 marksmanship baseline
#   surrender  multiplier on the chance to surrender when broken (0 = never)
#   banzai     broken units charge instead of fleeing
#   aggression how eagerly squads close with the enemy (0-1)
#   cover      how much squads value cover over speed (0-1)
#   arty       likelihood officers call artillery (0-1)
#   smg_ratio  share of riflemen swapped for sub-machine gunners (late war)

NATIONS: dict[str, dict] = {}


def _nation(key, **kw):
    kw["key"] = key
    NATIONS[key] = kw


_nation(
    "usa", name="United States", adj="American", side=ALLIES, army="U.S. Army",
    color=(150, 190, 110),
    first=["James", "John", "Robert", "William", "Charles", "George", "Joseph", "Frank", "Edward",
           "Harold", "Walter", "Raymond", "Donald", "Richard", "Thomas", "Paul", "Eugene", "Carl",
           "Stanley", "Leonard", "Earl", "Howard", "Ralph", "Louis", "Vincent", "Tony", "Salvatore",
           "Abe", "Jack", "Bill", "Roy", "Clarence", "Elmer", "Herman", "Ira", "Dale", "Wesley"],
    last=["Smith", "Johnson", "Miller", "Brown", "Davis", "Wilson", "Anderson", "Taylor", "Moore",
          "Jackson", "Martin", "Thompson", "White", "Harris", "Clark", "Lewis", "Walker", "Hall",
          "Kowalski", "Russo", "O'Brien", "Sullivan", "Murphy", "Schmidt", "Novak", "Rossi",
          "Goldberg", "Hernandez", "Garcia", "Dawson", "Winters", "Malarkey", "Toye", "Guarnere",
          "Lipton", "Nixon", "Speirs", "Hayes", "Kelly", "Baker", "Cooper", "Price", "Reed"],
    doctrine=dict(morale=58, training=5, surrender=1.0, banzai=False, aggression=0.55,
                  cover=0.7, arty=0.9, smg_ratio=0.1),
    shouts=dict(attack=["Move, move, move!", "Go! Go!", "Let's go, boys!", "Fix bayonets!",
                        "Get off the beach!", "Covering fire!"],
                grenade=["Grenade!", "Fire in the hole!"], medic=["Medic!", "Medic! I'm hit!",
                "Somebody help me!", "Ma! Ma!"], reload=["Reloading!", "Changing mags!"],
                contact=["Contact front!", "Krauts!", "Enemy spotted!", "There, in the treeline!"],
                retreat=["Fall back!", "Pull back, pull back!"], surrender=["Don't shoot! I give up!"],
                tank=["Tank! Get the bazooka up here!"], sniper=["Sniper!"], mg=["MG! Get down!"],
                pain=["Aaagh!", "Oh God!", "I'm hit!"]),
    enemy_slang={"germany": "Krauts", "japan": "Japs", "italy": "Eyeties"},
    cigs="Lucky Strike", flask="whiskey", ration="K-ration", currency="dollars",
    equip=[("usa", 1900, 1950)],
)

_nation(
    "uk", name="United Kingdom", adj="British", side=ALLIES, army="British Army",
    color=(170, 160, 100),
    first=["Albert", "Arthur", "Alfred", "Frederick", "Harold", "Henry", "Stanley", "Reginald",
           "Ernest", "Leslie", "Cyril", "Dennis", "Norman", "Ronald", "Kenneth", "Percy", "Sidney",
           "Wilfred", "Horace", "Bernard", "Geoffrey", "Ian", "Alastair", "Hamish", "Dai", "Owen",
           "Patrick", "Michael", "Tommy", "Jack", "George", "William", "Edward", "Charles"],
    last=["Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Evans", "Wilson", "Thomas",
          "Johnson", "Roberts", "Robinson", "Thompson", "Wright", "Walker", "White", "Edwards",
          "Hughes", "Green", "Hall", "Wood", "Harris", "Lewis", "Martin", "Jackson", "Clarke",
          "MacDonald", "Campbell", "Stewart", "Fraser", "O'Connor", "Atkins", "Pritchard",
          "Higgins", "Barker", "Cartwright", "Ashworth", "Fairclough", "Pemberton"],
    doctrine=dict(morale=58, training=6, surrender=1.0, banzai=False, aggression=0.45,
                  cover=0.8, arty=0.95, smg_ratio=0.05),
    shouts=dict(attack=["Up and at 'em!", "Forward, lads!", "Come on, move yourselves!",
                        "Fix bayonets!", "Advance!"],
                grenade=["Grenade!", "Mills bomb, going out!"],
                medic=["Stretcher bearer!", "Medic!", "I've copped it!", "Mum!"],
                reload=["Magazine!", "Changing!"],
                contact=["Enemy front!", "Jerry's in the hedge!", "Movement, half left!"],
                retreat=["Fall back!", "Withdraw!"], surrender=["Don't shoot! Kamerad!"],
                tank=["Tank! Get the PIAT!"], sniper=["Sniper!"], mg=["Spandau! Get down!"],
                pain=["Argh!", "Bloody hell!", "I'm hit!"]),
    enemy_slang={"germany": "Jerry", "italy": "Eyeties", "japan": "Japs"},
    cigs="Player's Navy Cut", flask="rum", ration="compo ration", currency="shillings",
    equip=[("uk", 1900, 1950)],
)

_nation(
    "canada", name="Canada", adj="Canadian", side=ALLIES, army="Canadian Army",
    color=(190, 140, 100),
    first=["Gordon", "Donald", "Lloyd", "Clifford", "Jean", "Pierre", "Marcel", "Gerald",
           "Russell", "Douglas", "Keith", "Murray", "Bruce", "Allan", "Roy", "Lorne", "Wilfrid",
           "Émile", "Lucien", "Roger", "Hector", "Angus", "Ross", "Earl"],
    last=["MacLeod", "Tremblay", "Gagnon", "Roy", "Côté", "Bouchard", "Gauthier", "Morin",
          "Campbell", "MacDonald", "Stewart", "Fraser", "Anderson", "Smith", "Brown", "Wilson",
          "Martin", "Thompson", "Reid", "Ross", "Young", "Dubois", "Lavoie", "Fortin", "Bergeron"],
    doctrine=dict(morale=60, training=6, surrender=1.0, banzai=False, aggression=0.55,
                  cover=0.75, arty=0.95, smg_ratio=0.05),
    shouts=dict(attack=["Let's go, boys!", "Allons-y!", "Forward!", "Move it!"],
                grenade=["Grenade!"], medic=["Stretcher bearer!", "Medic!"],
                reload=["Reloading!"], contact=["Jerry, front!", "Enemy!"],
                retreat=["Fall back!"], surrender=["Don't shoot!"], tank=["Tank! PIAT up!"],
                sniper=["Sniper!"], mg=["MG! Down!"], pain=["Argh!", "Tabarnak!", "I'm hit!"]),
    enemy_slang={"germany": "Jerry"},
    cigs="Sweet Caporal", flask="rum", ration="compo ration", currency="dollars",
    equip=[("uk", 1900, 1950)],
)

_nation(
    "australia", name="Australia", adj="Australian", side=ALLIES, army="Australian Army",
    color=(170, 150, 90),
    first=["Bruce", "Keith", "Cliff", "Reg", "Col", "Bluey", "Norm", "Wal", "Ron", "Les", "Jim",
           "Bill", "Kev", "Des", "Merv", "Stan", "Alf", "Tom", "Ted", "Harry"],
    last=["Kelly", "Ryan", "O'Neill", "Smith", "Jones", "Mitchell", "Campbell", "McKenzie",
          "Walker", "Baxter", "Doyle", "Murray", "Nolan", "Burke", "Hogan", "Brennan", "Lawson"],
    doctrine=dict(morale=64, training=6, surrender=0.8, banzai=False, aggression=0.65,
                  cover=0.7, arty=0.9, smg_ratio=0.12),
    shouts=dict(attack=["Come on, cobbers!", "Get into 'em!", "Forward!"],
                grenade=["Grenade!"], medic=["Stretcher bearer!", "I'm hit, mate!"],
                reload=["Reloading!"], contact=["Enemy, front!"], retreat=["Pull back!"],
                surrender=["Don't shoot!"], tank=["Tank!"], sniper=["Sniper!"],
                mg=["MG! Get down!"], pain=["Strewth!", "Argh!"]),
    enemy_slang={"germany": "Jerry", "japan": "Japs", "italy": "Eyeties"},
    cigs="Capstan", flask="rum", ration="bully beef", currency="shillings",
    equip=[("australia", 1900, 1950), ("uk", 1900, 1950)],
)

_nation(
    "newzealand", name="New Zealand", adj="New Zealander", side=ALLIES, army="2nd NZEF",
    color=(160, 160, 110),
    first=["Charles", "Keith", "Arthur", "Tamati", "Wiremu", "Hemi", "Rangi", "Nelson", "Jack",
           "Colin", "Lindsay", "Ngarimu", "Moana", "Te Rata", "Ian", "Rex"],
    last=["Upham", "Ngarimu", "Hinton", "Elliott", "Kippenberger", "Tait", "Parata", "Walker",
          "Morrison", "Harrison", "Rewi", "Tamihana", "Paora", "Wilson", "MacKay"],
    doctrine=dict(morale=66, training=6, surrender=0.8, banzai=False, aggression=0.7,
                  cover=0.7, arty=0.9, smg_ratio=0.1),
    shouts=dict(attack=["Ake ake kia kaha!", "Forward!", "Into them!"], grenade=["Grenade!"],
                medic=["Stretcher bearer!"], reload=["Reloading!"], contact=["Enemy!"],
                retreat=["Fall back!"], surrender=["Don't shoot!"], tank=["Tank!"],
                sniper=["Sniper!"], mg=["MG!"], pain=["Argh!"]),
    enemy_slang={"germany": "Jerry"},
    cigs="Capstan", flask="rum", ration="bully beef", currency="shillings",
    equip=[("uk", 1900, 1950)],
)

_nation(
    "india", name="British India", adj="Indian", side=ALLIES, army="British Indian Army",
    color=(180, 150, 80),
    first=["Kamal", "Gian", "Lalbahadur", "Bhanbhagta", "Tul", "Ganju", "Karamjeet", "Umrao",
           "Nand", "Parkash", "Abdul", "Gurbachan", "Rajendra", "Sher", "Ali", "Ram", "Harka"],
    last=["Singh", "Thapa", "Gurung", "Rai", "Limbu", "Khan", "Pun", "Ram", "Chand", "Lama",
          "Magar", "Hafiz", "Sharma", "Bahadur"],
    doctrine=dict(morale=64, training=6, surrender=0.8, banzai=False, aggression=0.6,
                  cover=0.75, arty=0.9, smg_ratio=0.08),
    shouts=dict(attack=["Ayo Gorkhali!", "Bole So Nihal!", "Forward!"], grenade=["Grenade!"],
                medic=["Stretcher!"], reload=["Reloading!"], contact=["Dushman!"],
                retreat=["Fall back!"], surrender=["Don't shoot!"], tank=["Tank!"],
                sniper=["Sniper!"], mg=["Machine gun!"], pain=["Aaah!"]),
    enemy_slang={"japan": "Japs"},
    cigs="Capstan", flask="rum", ration="atta and dal", currency="rupees",
    equip=[("india", 1900, 1950), ("uk", 1900, 1950)],
)

_nation(
    "ussr", name="Soviet Union", adj="Soviet", side=ALLIES, army="Red Army",
    color=(200, 110, 90),
    first=["Ivan", "Nikolai", "Aleksandr", "Sergei", "Vasily", "Mikhail", "Pyotr", "Dmitri",
           "Yakov", "Grigori", "Alexei", "Boris", "Fyodor", "Pavel", "Andrei", "Viktor", "Semyon",
           "Stepan", "Timur", "Rustam", "Taras", "Oleksandr", "Mykola", "Arkady", "Leonid",
           "Lyudmila", "Roza", "Nina", "Maria"],
    last=["Ivanov", "Smirnov", "Kuznetsov", "Popov", "Sokolov", "Lebedev", "Kozlov", "Novikov",
          "Morozov", "Petrov", "Volkov", "Solovyov", "Vasiliev", "Zaytsev", "Pavlov", "Chuikov",
          "Shevchenko", "Kovalenko", "Bondarenko", "Tkachenko", "Nurmagambetov", "Aliyev",
          "Gelashvili", "Abramov", "Yegorov", "Kantaria", "Pavlichenko", "Shanina", "Orlov"],
    doctrine=dict(morale=55, training=4, surrender=0.7, banzai=False, aggression=0.75,
                  cover=0.5, arty=0.85, smg_ratio=0.3),
    shouts=dict(attack=["Urraaa!", "Za Rodinu!", "Vperyod!", "Ni shagu nazad!"],
                grenade=["Granata!", "Lozhis'!"], medic=["Sanitar!", "Pomogite!", "Mama!"],
                reload=["Perezaryazhayu!"], contact=["Fritzy!", "Nemtsy!", "Vrag vperedi!"],
                retreat=["Otkhodim!", "Nazad!"], surrender=["Ne strelyay! Sdayus'!"],
                tank=["Tank! Protivotankovoye!"], sniper=["Snayper!"], mg=["Pulemyot! Lozhis'!"],
                pain=["Aaa!", "Blyad'!", "Ranen!"]),
    enemy_slang={"germany": "Fritzes", "finland": "Finns", "romania": "Romanians",
                 "hungary": "Magyars", "japan": "samurai"},
    cigs="Belomorkanal papirosy", flask="vodka", ration="sukhari", currency="roubles",
    equip=[("ussr", 1900, 1950)],
)

_nation(
    "france", name="France", adj="French", side=ALLIES, army="Armée de Terre",
    color=(120, 150, 200),
    first=["Jean", "Pierre", "Louis", "Henri", "Marcel", "André", "René", "Georges", "Paul",
           "Robert", "Maurice", "Lucien", "Roger", "Fernand", "Émile", "Raymond", "Gaston",
           "Jacques", "Ahmed", "Mamadou", "Moussa", "Abdelkader"],
    last=["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand",
          "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David",
          "Bertrand", "Roux", "Vincent", "Fournier", "Morel", "Girard", "Diallo", "Traoré",
          "Benali", "Leclerc"],
    doctrine=dict(morale=50, training=5, surrender=1.3, banzai=False, aggression=0.4,
                  cover=0.8, arty=0.8, smg_ratio=0.0),
    shouts=dict(attack=["En avant!", "Allez, allez!", "À l'attaque!", "Baïonnette au canon!"],
                grenade=["Grenade!"], medic=["Brancardier!", "Infirmier!", "Maman!"],
                reload=["Je recharge!"], contact=["Les Boches!", "Ennemi en vue!"],
                retreat=["Repliez-vous!", "Sauve qui peut!"], surrender=["Ne tirez pas!"],
                tank=["Char! Char ennemi!"], sniper=["Tireur!"], mg=["Mitrailleuse!"],
                pain=["Aïe!", "Merde!", "Je suis touché!"]),
    enemy_slang={"germany": "Boches", "italy": "Ritals"},
    cigs="Gauloises", flask="pinard", ration="singe", currency="francs",
    equip=[("france", 1900, 1941), ("usa", 1942, 1950)],
)

_nation(
    "poland", name="Poland", adj="Polish", side=ALLIES, army="Wojsko Polskie",
    color=(220, 120, 130),
    first=["Jan", "Stanisław", "Józef", "Tadeusz", "Władysław", "Kazimierz", "Zbigniew",
           "Marian", "Witold", "Jerzy", "Andrzej", "Henryk", "Bolesław", "Stefan", "Franciszek",
           "Czesław", "Wojciech", "Mieczysław", "Zdzisław", "Wacław"],
    last=["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk", "Kamiński", "Lewandowski",
          "Zieliński", "Szymański", "Woźniak", "Dąbrowski", "Kozłowski", "Jankowski",
          "Mazur", "Kwiatkowski", "Krawczyk", "Piotrowski", "Grabowski", "Pilecki", "Sosabowski"],
    doctrine=dict(morale=66, training=5, surrender=0.7, banzai=False, aggression=0.65,
                  cover=0.65, arty=0.8, smg_ratio=0.05),
    shouts=dict(attack=["Naprzód!", "Hurra!", "Za Polskę!", "Do ataku!"],
                grenade=["Granat!"], medic=["Sanitariusz!", "Ratunku!", "Mamo!"],
                reload=["Przeładowuję!"], contact=["Szwaby!", "Nieprzyjaciel!"],
                retreat=["Odwrót!"], surrender=["Nie strzelać!"], tank=["Czołg!"],
                sniper=["Snajper!"], mg=["Karabin maszynowy!"], pain=["Aaa!", "Cholera!"]),
    enemy_slang={"germany": "Szwaby", "ussr": "Sowieci"},
    cigs="Sport", flask="wódka", ration="suchary", currency="złoty",
    equip=[("poland", 1900, 1940), ("uk", 1940, 1945.2), ("ussr", 1945.2, 1950)],
)

_nation(
    "china", name="Republic of China", adj="Chinese", side=ALLIES,
    army="National Revolutionary Army", color=(120, 150, 190),
    first=["Wei", "Jun", "Ming", "Hao", "Lei", "Chen", "Jian", "Qiang", "Yong", "Bo", "Tao",
           "Feng", "Guang", "Hong", "Zhi", "Xiang", "Cheng", "Liang", "De", "Shan"],
    last=["Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou", "Xu",
          "Sun", "Ma", "Zhu", "Hu", "Guo", "He", "Gao", "Lin", "Luo", "Xie", "Xue"],
    doctrine=dict(morale=52, training=3, surrender=0.6, banzai=False, aggression=0.6,
                  cover=0.7, arty=0.4, smg_ratio=0.08),
    shouts=dict(attack=["Chōng a!", "Shā!", "Forward!"], grenade=["Shǒuliúdàn!"],
                medic=["Wèishēngbīng!", "Jiù mìng!"], reload=["Huàn dànjiā!"],
                contact=["Rìběn guǐzi!", "Enemy!"], retreat=["Chèntuì!"],
                surrender=["Bié kāi qiāng!"], tank=["Tǎnkè!"], sniper=["Jūjī shǒu!"],
                mg=["Jīqiāng!"], pain=["Āiyō!", "Aaa!"]),
    enemy_slang={"japan": "guizi"},
    cigs="Ruby Queen", flask="baijiu", ration="rice", currency="fabi",
    equip=[("china", 1900, 1950)],
)

_nation(
    "germany", name="Germany", adj="German", side=AXIS, army="Wehrmacht",
    color=(160, 160, 160),
    first=["Hans", "Karl", "Heinrich", "Friedrich", "Wilhelm", "Otto", "Ernst", "Walter",
           "Hermann", "Kurt", "Werner", "Helmut", "Günther", "Franz", "Josef", "Paul", "Fritz",
           "Rudolf", "Gerhard", "Klaus", "Dieter", "Horst", "Heinz", "Erich", "Willi", "Alfred",
           "Johann", "Ludwig", "Max", "Georg", "Bernhard", "Siegfried"],
    last=["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker",
          "Schulz", "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter", "Klein", "Wolf",
          "Schröder", "Neumann", "Schwarz", "Zimmermann", "Braun", "Krüger", "Hofmann",
          "Hartmann", "Lange", "Werner", "Krause", "Lehmann", "Köhler", "Huber", "Kaiser",
          "Fuchs", "Peters", "Lang", "Scholz", "Möller", "Weiß", "Jung", "Hahn", "Vogel"],
    doctrine=dict(morale=62, training=6, surrender=0.8, banzai=False, aggression=0.55,
                  cover=0.85, arty=0.8, smg_ratio=0.15),
    shouts=dict(attack=["Vorwärts!", "Los, los, los!", "Angriff!", "Hurra!", "Marsch, marsch!"],
                grenade=["Handgranate!", "Vorsicht, Granate!", "Deckung!"],
                medic=["Sanitäter!", "Sani! Sani!", "Hilfe!", "Mutti!"],
                reload=["Nachladen!", "Magazin!"],
                contact=["Feind in Sicht!", "Da! Amis!", "Achtung, Feind!", "Iwan kommt!"],
                retreat=["Rückzug!", "Zurück, zurück!", "Absetzen!"],
                surrender=["Nicht schießen! Kamerad!", "Hände hoch, ich ergebe mich!"],
                tank=["Panzer! Panzerschreck nach vorn!", "Feindpanzer!"],
                sniper=["Scharfschütze!"], mg=["MG! Volle Deckung!"],
                pain=["Aaah!", "Verdammt!", "Ich bin getroffen!", "Scheiße!"]),
    enemy_slang={"usa": "Amis", "uk": "Tommies", "canada": "Tommies", "ussr": "Iwan",
                 "france": "Franzmänner", "poland": "Polacken", "australia": "Tommies",
                 "newzealand": "Tommies"},
    cigs="Juno", flask="schnapps", ration="Knäckebrot", currency="Reichsmark",
    equip=[("germany", 1900, 1950)],
)

_nation(
    "italy", name="Italy", adj="Italian", side=AXIS, army="Regio Esercito",
    color=(150, 170, 120),
    first=["Giuseppe", "Giovanni", "Antonio", "Mario", "Francesco", "Luigi", "Angelo",
           "Vincenzo", "Pietro", "Salvatore", "Carlo", "Franco", "Domenico", "Bruno", "Paolo",
           "Michele", "Giorgio", "Aldo", "Enzo", "Sergio", "Luciano", "Renato", "Alberto"],
    last=["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci",
          "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Mancini", "Costa",
          "Giordano", "Rizzo", "Lombardi", "Moretti", "Barbieri", "Fontana", "Santoro"],
    doctrine=dict(morale=45, training=4, surrender=1.5, banzai=False, aggression=0.4,
                  cover=0.8, arty=0.7, smg_ratio=0.05),
    shouts=dict(attack=["Avanti!", "Savoia!", "All'attacco!", "Forza, ragazzi!"],
                grenade=["Bomba a mano!", "Granata!"], medic=["Portaferiti!", "Aiuto!", "Mamma!"],
                reload=["Ricarico!"], contact=["Nemico in vista!", "Gli inglesi!"],
                retreat=["Ritirata!", "Indietro!"], surrender=["Non sparate! Mi arrendo!"],
                tank=["Carro armato!"], sniper=["Cecchino!"], mg=["Mitragliatrice! A terra!"],
                pain=["Ahi!", "Madonna!", "Sono ferito!"]),
    enemy_slang={"uk": "gli inglesi", "usa": "gli americani", "australia": "gli australiani",
                 "newzealand": "i neozelandesi"},
    cigs="Macedonia", flask="grappa", ration="galletta", currency="lire",
    equip=[("italy", 1900, 1950)],
)

_nation(
    "japan", name="Japan", adj="Japanese", side=AXIS, army="Imperial Japanese Army",
    color=(200, 180, 110),
    first=["Hiroshi", "Takeshi", "Kenji", "Isamu", "Minoru", "Saburo", "Ichiro", "Jiro",
           "Shigeru", "Tadashi", "Masao", "Yoshio", "Kiyoshi", "Tsutomu", "Akira", "Haruo",
           "Noboru", "Katsumi", "Hideo", "Toshio", "Hiroo", "Kunio", "Shoichi", "Yasuo"],
    last=["Satō", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Itō", "Yamamoto", "Nakamura",
          "Kobayashi", "Katō", "Yoshida", "Yamada", "Sasaki", "Yamaguchi", "Matsumoto", "Inoue",
          "Kimura", "Hayashi", "Shimizu", "Onoda", "Kuribayashi", "Nishi", "Ushijima", "Mori"],
    doctrine=dict(morale=75, training=5, surrender=0.05, banzai=True, aggression=0.75,
                  cover=0.75, arty=0.5, smg_ratio=0.0),
    shouts=dict(attack=["Tennōheika banzai!", "Totsugeki!", "Susume!", "Banzai!"],
                grenade=["Shuryūdan!", "Fusero!"], medic=["Eisei-hei!", "Okāsan!"],
                reload=["Sōten!"], contact=["Teki da!", "Beihei!", "Teki shūrai!"],
                retreat=["Tettai!"], surrender=["Utsu na!"], tank=["Sensha da!"],
                sniper=["Sogekihei!"], mg=["Kikanjū! Fusero!"],
                pain=["Guaah!", "Itai!", "Yarareta!"]),
    enemy_slang={"usa": "Yankees", "uk": "Eikoku-hei", "china": "Shina-hei",
                 "australia": "Gōshū-hei", "india": "Indo-hei"},
    cigs="Kinshi", flask="sake", ration="rice ball", currency="yen",
    equip=[("japan", 1900, 1950)],
)

_nation(
    "finland", name="Finland", adj="Finnish", side=AXIS, army="Suomen Puolustusvoimat",
    color=(180, 190, 200),
    first=["Simo", "Aarne", "Eino", "Toivo", "Väinö", "Lauri", "Onni", "Viljo", "Tauno",
           "Arvo", "Veikko", "Kalle", "Matti", "Antti", "Pekka", "Heikki", "Urho", "Reino"],
    last=["Häyhä", "Juutilainen", "Korhonen", "Virtanen", "Mäkinen", "Nieminen", "Mäkelä",
          "Hämäläinen", "Laine", "Heikkinen", "Koskinen", "Järvinen", "Lehtonen", "Saarinen",
          "Salminen", "Rokka", "Hietanen", "Lahtinen", "Koskela", "Rahikainen"],
    doctrine=dict(morale=70, training=7, surrender=0.6, banzai=False, aggression=0.6,
                  cover=0.85, arty=0.75, smg_ratio=0.25),
    shouts=dict(attack=["Eteenpäin!", "Hyökkää!", "Hurraa!"], grenade=["Kranaatti!", "Maahan!"],
                medic=["Lääkintämies!", "Apua!", "Äiti!"], reload=["Lataan!"],
                contact=["Ryssiä!", "Vihollinen!"], retreat=["Perääntykää!"],
                surrender=["Älä ammu!"], tank=["Panssarivaunu!"], sniper=["Tarkka-ampuja!"],
                mg=["Konekivääri!"], pain=["Perkele!", "Aah!"]),
    enemy_slang={"ussr": "ryssät"},
    cigs="Työmies", flask="kossu", ration="näkkileipä", currency="markka",
    equip=[("finland", 1900, 1950)],
)

_nation(
    "hungary", name="Hungary", adj="Hungarian", side=AXIS, army="Magyar Királyi Honvédség",
    color=(170, 160, 120),
    first=["László", "István", "József", "János", "Ferenc", "Sándor", "Gyula", "Imre", "Béla",
           "Lajos", "Károly", "Mihály", "Zoltán", "Tibor", "Miklós", "Géza", "Dezső"],
    last=["Nagy", "Kovács", "Tóth", "Szabó", "Horváth", "Varga", "Kiss", "Molnár", "Németh",
          "Farkas", "Balogh", "Papp", "Takács", "Juhász", "Lakatos", "Mészáros", "Oláh", "Simon"],
    doctrine=dict(morale=50, training=5, surrender=1.1, banzai=False, aggression=0.45,
                  cover=0.8, arty=0.65, smg_ratio=0.1),
    shouts=dict(attack=["Előre!", "Rajta!", "Hajrá!"], grenade=["Kézigránát!"],
                medic=["Szanitéc!", "Segítség!", "Anyám!"], reload=["Töltök!"],
                contact=["Ellenség!", "Oroszok!"], retreat=["Vissza!"], surrender=["Ne lőjetek!"],
                tank=["Tank!"], sniper=["Mesterlövész!"], mg=["Géppuska!"], pain=["Jaj!", "Aaah!"]),
    enemy_slang={"ussr": "Russkies"},
    cigs="Levente", flask="pálinka", ration="kenyér", currency="pengő",
    equip=[("hungary", 1900, 1950), ("germany", 1944, 1950)],
)

_nation(
    "romania", name="Romania", adj="Romanian", side=AXIS, army="Armata Română",
    color=(180, 170, 110),
    first=["Ion", "Gheorghe", "Vasile", "Constantin", "Nicolae", "Dumitru", "Mihai", "Petre",
           "Ilie", "Florin", "Marin", "Alexandru", "Costel", "Gavril", "Radu", "Toma"],
    last=["Popescu", "Ionescu", "Popa", "Dumitru", "Stan", "Stoica", "Gheorghe", "Matei",
          "Ciobanu", "Rusu", "Munteanu", "Constantin", "Dinu", "Lazăr", "Moldovan", "Neagu"],
    doctrine=dict(morale=46, training=4, surrender=1.3, banzai=False, aggression=0.45,
                  cover=0.75, arty=0.6, smg_ratio=0.05),
    shouts=dict(attack=["Înainte!", "Ura!", "La atac!"], grenade=["Grenadă!"],
                medic=["Sanitar!", "Ajutor!", "Mamă!"], reload=["Reîncarc!"],
                contact=["Inamicul!", "Rușii!"], retreat=["Retragerea!"],
                surrender=["Nu trageți!"], tank=["Tanc!"], sniper=["Lunetist!"],
                mg=["Mitralieră!"], pain=["Au!", "Aaah!"]),
    enemy_slang={"ussr": "Russkies"},
    cigs="Mărășești", flask="țuică", ration="mămăligă", currency="lei",
    equip=[("romania", 1900, 1950), ("germany", 1943, 1950)],
)


# ---------------------------------------------------------------- helpers

def side_nations(side: str) -> list[str]:
    return [k for k, v in NATIONS.items() if v["side"] == side]


def equip_sources(nation: str, year: float) -> list[str]:
    """Equipment pools usable by a nation in a given year, most specific first."""
    srcs = [s for s, y0, y1 in NATIONS[nation]["equip"] if y0 <= year < y1]
    return srcs or [NATIONS[nation]["equip"][0][0]]


def random_name(rng: random.Random, nation: str, male: bool = False) -> str:
    from ..entities import FEMALE_NAMES
    n = NATIONS[nation]
    first = rng.choice(n["first"])
    for _ in range(8):
        if not (male and first in FEMALE_NAMES):
            break
        first = rng.choice(n["first"])
    last = rng.choice(n["last"])
    if first in FEMALE_NAMES and nation == "ussr":
        last = feminine_surname(last)
    return f"{first} {last}"


def feminine_surname(last: str) -> str:
    """Russian surnames agree with the bearer: Ivanov, Ivanova; Kovalevsky, Kovalevskaya."""
    if last.endswith(("ov", "ev", "yov", "in", "yn")):
        return last + "a"
    if last.endswith("sky"):
        return last[:-1] + "aya"
    if last.endswith("iy"):
        return last[:-2] + "aya"
    return last


def rank_name(nation: str, rank: int, short: bool = True, service: str = "army") -> str:
    """Rank title for a grade on the common 0-18 scale (see data/ranks.py), in a service's own ranks."""
    from .ranks import rank_title
    return rank_title(nation, rank, short, service)


def officer_rank(nation: str) -> int:
    """Grade of the first commissioned rank."""
    from .ranks import LT2
    return LT2


def nco_rank(nation: str) -> int:
    """Grade a squad leader of this army normally held."""
    from .ranks import SQUAD_LEADER_GRADE, SERGEANT
    return SQUAD_LEADER_GRADE.get(nation, SERGEANT)


_ORD = {1: "st", 2: "nd", 3: "rd"}


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{_ORD.get(n % 10, 'th')}"


def unit_designation(rng: random.Random, nation: str, divisions: list[str] | None = None) -> str:
    """A plausible company/battalion/regiment/division string."""
    div = rng.choice(divisions) if divisions else None
    bn = rng.randint(1, 3)
    coy = (bn - 1) * 4 + rng.randint(1, 4)       # companies are numbered through the regiment, four a battalion
    rgt = rng.randint(2, 999)
    if nation == "usa":
        letter = "ABCDEFGHIKLM"[coy - 1]
        d = div or ""
        if "Airborne" in d:
            unit = f"{ordinal(rng.choice([501, 502, 504, 505, 506, 507, 508, 517]))} Parachute Infantry Regiment"
        elif "Armored" in d:
            return f"Co. {letter[:1] if coy <= 3 else 'A'}, {ordinal(rng.randint(10, 70))} Armored Infantry Battalion, {d}"
        elif "Marine" in d:
            unit = f"{ordinal(rng.randint(1, 29))} Marines"
        else:
            unit = f"{ordinal(rgt)} Infantry Regiment"
        return f"Co. {letter}, {ordinal(bn)} Bn, {unit}, {div or ordinal(rng.randint(1, 106)) + ' Infantry Division'}"
    if nation in ("uk", "canada", "australia", "newzealand", "india"):
        letter = "ABCD"[coy % 4]
        regts = {"uk": ["Royal Warwickshire Regiment", "East Yorkshire Regiment",
                        "Durham Light Infantry", "Black Watch", "Royal Ulster Rifles",
                        "Parachute Regiment", "Hampshire Regiment", "Green Howards",
                        "King's Own Scottish Borderers", "Rifle Brigade"],
                 "canada": ["Royal Winnipeg Rifles", "Queen's Own Rifles", "Régiment de la Chaudière",
                            "North Nova Scotia Highlanders", "Regina Rifles", "Black Watch of Canada"],
                 "australia": ["2/13th Battalion", "2/17th Battalion", "2/24th Battalion",
                               "39th Battalion", "2/48th Battalion"],
                 "newzealand": ["28th (Maori) Battalion", "23rd Battalion", "26th Battalion",
                                "20th Battalion"],
                 "india": ["1st Gurkha Rifles", "4th Indian Division", "2nd Punjab Regiment",
                           "1st/7th Rajput", "4th/7th Rajput", "Assam Regiment"]}[nation]
        return f"{letter} Company, {ordinal(bn)} Bn, {rng.choice(regts)}, {div or 'infantry brigade'}"
    if nation == "germany":
        # the regiment has to belong to the kind of division it's in
        d = div or ""
        kind = ("SS-Panzergrenadier-Regiment", rng.randint(1, 40)) if "SS" in d else \
            ("Fallschirmjäger-Regiment", rng.randint(1, 26)) if "Fallschirm" in d else \
            ("Gebirgsjäger-Regiment", rng.randint(85, 143)) if "Gebirgs" in d else \
            ("Panzergrenadier-Regiment", rng.randint(1, 156)) if "Panzer" in d else ("Grenadier-Regiment", rgt)
        return (f"{coy}. Kompanie, {'I II III'.split()[bn - 1]}. Bataillon, "
                f"{kind[0]} {kind[1]}, {div or str(rng.randint(1, 716)) + '. Infanterie-Division'}")
    if nation == "ussr":
        return (f"{ordinal(coy)} Company, {ordinal(bn)} Battalion, {ordinal(rgt)} Rifle Regiment, "
                f"{div or ordinal(rng.randint(1, 400)) + ' Rifle Division'}")
    if nation == "japan":
        return (f"{ordinal(coy)} Company, {ordinal(bn)} Battalion, {ordinal(rng.randint(1, 250))} "
                f"Infantry Regiment, {div or ordinal(rng.randint(1, 116)) + ' Division'}")
    if nation == "italy":
        return (f"{coy}ª Compagnia, {bn}° Battaglione, {rgt}° Reggimento Fanteria, "
                f"{div or 'Divisione ' + rng.choice(['Ariete', 'Folgore', 'Pavia', 'Brescia', 'Trento', 'Livorno'])}")
    if nation == "france":
        dv = div or "division d'infanterie"
        return f"{coy}e Compagnie, {bn}e Bataillon, {rgt}e Régiment d'Infanterie, {dv}"
    if nation == "poland":
        return f"{coy}. kompania, {bn}. batalion, {rng.randint(1, 86)}. pułk piechoty, {div or 'dywizja piechoty'}"
    if nation == "china":
        return f"{ordinal(coy)} Company, {ordinal(bn)} Battalion, {ordinal(rgt)} Regiment, {div or ordinal(rng.randint(1, 200)) + ' Division'}"
    if nation == "finland":
        return f"{coy}. komppania, JR {rng.randint(1, 61)}, {div or str(rng.randint(1, 18)) + '. Divisioona'}"
    if nation == "hungary":
        return f"{coy}. század, {rng.randint(1, 50)}. gyalogezred, {div or 'Second Hungarian Army'}"
    if nation == "romania":
        return f"Compania {coy}, Regimentul {rng.randint(1, 96)} Infanterie, {div or 'Third Romanian Army'}"
    return f"{ordinal(coy)} Company"
