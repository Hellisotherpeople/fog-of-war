"""Warships and the ships they fought over.

Scale: the sea world uses 100 m tiles (the same as the sky), so a battleship is three
tiles long and a destroyer one.  Speeds in knots; gun ranges in tiles (100 m).

main/sec: (calibre mm, guns, range tiles, reload seconds, penetration mm, damage)
aa: (light guns, heavy guns); torps: (tubes, range tiles, knots); dc: depth charges
air: (fighters, dive bombers, torpedo bombers) aircraft ids by nation are filled in by skysea
"""
from __future__ import annotations

SHIPS: dict[str, dict] = {}


def ship(id, name, cls, nations, years, *, length, speed, hp, belt=0, deck=0, main=None, sec=None, aa=(4, 0),
         torps=None, dc=0, sonar=False, radar=0.0, air=None, crew=200, subspeed=0, freq=10, desc=""):
    SHIPS[id] = dict(id=id, name=name, cls=cls, nations=tuple(nations), years=years, length=length, speed=speed,
                     hp=hp, belt=belt, deck=deck, main=main, sec=sec, aa=aa, torps=torps, dc=dc, sonar=sonar,
                     radar=radar, air=air, crew=crew, subspeed=subspeed, freq=freq, desc=desc)


# ------------------------------------------------------------ United States
ship("fletcher", "Fletcher-class destroyer", "dd", ["usa"], (1942.5, 1950), length=1, speed=36, hp=220,
     main=(127, 5, 120, 4, 60, 70), aa=(10, 0), torps=(10, 90, 45), dc=28, sonar=True, radar=1943, crew=330, freq=20)
ship("benson", "Benson-class destroyer", "dd", ["usa"], (1940, 1946), length=1, speed=35, hp=200,
     main=(127, 4, 120, 4, 60, 70), aa=(6, 0), torps=(10, 90, 45), dc=24, sonar=True, radar=1942.5, crew=250)
ship("buckley", "Buckley-class destroyer escort", "de", ["usa"], (1943.3, 1950), length=1, speed=24, hp=150,
     main=(76, 3, 90, 3, 30, 40), aa=(8, 0), torps=(3, 90, 45), dc=200, sonar=True, radar=1943, crew=200)
ship("atlanta", "Atlanta-class light cruiser", "cl", ["usa"], (1941.9, 1950), length=2, speed=32, hp=450, belt=95,
     main=(127, 16, 130, 4, 60, 70), aa=(16, 0), torps=(8, 90, 45), radar=1942, crew=670)
ship("cleveland", "Cleveland-class light cruiser", "cl", ["usa"], (1942.3, 1950), length=2, speed=32, hp=600,
     belt=127, deck=51, main=(152, 12, 240, 6, 150, 150), sec=(127, 12, 130, 4, 60, 70), aa=(28, 0), radar=1942,
     crew=1250)
ship("baltimore", "Baltimore-class heavy cruiser", "ca", ["usa"], (1943.3, 1950), length=2, speed=33, hp=750,
     belt=152, deck=64, main=(203, 9, 280, 10, 210, 260), sec=(127, 12, 130, 4, 60, 70), aa=(40, 0), radar=1943,
     crew=1700)
ship("northcarolina", "North Carolina-class battleship", "bb", ["usa"], (1941.3, 1950), length=3, speed=28, hp=1600,
     belt=305, deck=140, main=(406, 9, 330, 30, 380, 700), sec=(127, 20, 130, 4, 60, 70), aa=(60, 0), radar=1942,
     crew=2300, freq=4)
ship("iowa", "Iowa-class battleship", "bb", ["usa"], (1943.2, 1950), length=3, speed=33, hp=1900, belt=307, deck=150,
     main=(406, 9, 380, 30, 420, 750), sec=(127, 20, 130, 4, 60, 70), aa=(100, 0), radar=1943, crew=2700, freq=2)
ship("yorktown", "Yorktown-class carrier", "cv", ["usa"], (1937.8, 1945), length=3, speed=32, hp=900, belt=102,
     main=None, sec=(127, 8, 130, 4, 60, 70), aa=(24, 0), radar=1941, air=(24, 36, 15), crew=2200, freq=4)
ship("essex", "Essex-class carrier", "cv", ["usa"], (1942.9, 1950), length=3, speed=33, hp=1100, belt=102, deck=64,
     sec=(127, 12, 130, 4, 60, 70), aa=(60, 0), radar=1943, air=(36, 36, 18), crew=2600, freq=6)
ship("casablanca", "Casablanca-class escort carrier", "cve", ["usa"], (1943.5, 1950), length=2, speed=19, hp=380,
     sec=(127, 1, 130, 4, 60, 70), aa=(24, 0), radar=1943, air=(16, 0, 12), crew=860)
ship("gato", "Gato-class submarine", "ss", ["usa"], (1941.9, 1950), length=1, speed=20, subspeed=9, hp=120,
     main=(76, 1, 60, 5, 20, 30), torps=(10, 80, 46), crew=60, freq=6)
ship("elco_pt", "Elco PT boat", "pt", ["usa"], (1941, 1950), length=1, speed=41, hp=40, main=(20, 2, 20, 1, 5, 12),
     torps=(4, 70, 28), crew=12, freq=6)
ship("liberty", "Liberty ship", "ap", ["usa", "uk"], (1941.9, 1950), length=2, speed=11, hp=300, aa=(4, 0), crew=45,
     freq=8)
ship("lst", "LST (tank landing ship)", "lst", ["usa", "uk"], (1942.8, 1950), length=2, speed=12, hp=250, aa=(8, 0),
     crew=110)

# ------------------------------------------------------------ Britain and the Commonwealth
ship("j_class", "J-class destroyer", "dd", ["uk", "australia", "canada", "newzealand", "india", "poland"],
     (1939.5, 1950), length=1, speed=36, hp=190, main=(120, 6, 110, 5, 50, 60), aa=(6, 0), torps=(10, 90, 36), dc=45,
     sonar=True, radar=1941.5, crew=220, freq=18)
ship("flower", "Flower-class corvette", "de", ["uk", "canada", "australia", "newzealand", "india", "france"],
     (1940.3, 1950), length=1, speed=16, hp=110, main=(102, 1, 90, 5, 30, 40), aa=(3, 0), dc=70, sonar=True,
     radar=1941.5, crew=85, freq=14)
ship("dido", "Dido-class cruiser", "cl", ["uk"], (1940.4, 1950), length=2, speed=32, hp=420, belt=76,
     main=(133, 10, 140, 5, 70, 80), aa=(16, 0), torps=(6, 90, 36), radar=1941, crew=480)
ship("county", "County-class heavy cruiser", "ca", ["uk", "australia"], (1928, 1950), length=2, speed=31, hp=620,
     belt=110, main=(203, 8, 270, 12, 190, 250), sec=(102, 8, 100, 4, 30, 40), aa=(16, 0), radar=1941.5, crew=780)
ship("kgv", "King George V-class battleship", "bb", ["uk"], (1940.9, 1950), length=3, speed=28, hp=1700, belt=374,
     deck=150, main=(356, 10, 320, 30, 360, 620), sec=(133, 16, 140, 5, 70, 80), aa=(50, 0), radar=1941, crew=1600,
     freq=4)
ship("illustrious", "Illustrious-class carrier", "cv", ["uk"], (1940.4, 1950), length=3, speed=30, hp=1000, belt=114,
     deck=76, sec=(114, 16, 110, 4, 40, 50), aa=(40, 0), radar=1941, air=(15, 0, 21), crew=1200, freq=4)
ship("t_class", "T-class submarine", "ss", ["uk"], (1938, 1950), length=1, speed=15, subspeed=9, hp=110,
     main=(102, 1, 60, 5, 20, 30), torps=(11, 80, 45), crew=60, freq=5)
ship("mtb", "Vosper motor torpedo boat", "pt", ["uk"], (1939, 1950), length=1, speed=40, hp=35,
     main=(20, 2, 20, 1, 5, 12), torps=(2, 70, 40), crew=12)

# ------------------------------------------------------------ Germany
ship("zerstorer36", "Type 1936 destroyer", "dd", ["germany"], (1939, 1950), length=1, speed=38, hp=210,
     main=(128, 5, 130, 5, 60, 75), aa=(8, 0), torps=(8, 90, 44), dc=30, sonar=True, crew=330, freq=14)
ship("hipper", "Admiral Hipper-class cruiser", "ca", ["germany"], (1939.1, 1950), length=2, speed=32, hp=700,
     belt=80, deck=50, main=(203, 8, 300, 10, 210, 260), sec=(105, 12, 140, 4, 40, 50), aa=(24, 0),
     torps=(12, 90, 44), radar=1940, crew=1400, freq=4)
ship("scharnhorst", "Scharnhorst-class battleship", "bb", ["germany"], (1939.0, 1944), length=3, speed=31, hp=1500,
     belt=350, deck=105, main=(283, 9, 380, 17, 300, 460), sec=(150, 12, 220, 6, 150, 150), aa=(36, 0), radar=1940,
     crew=1970, freq=3)
ship("bismarck", "Bismarck-class battleship", "bb", ["germany"], (1940.6, 1945), length=3, speed=30, hp=1900,
     belt=320, deck=120, main=(380, 8, 360, 26, 380, 650), sec=(150, 12, 220, 6, 150, 150), aa=(46, 0), radar=1940,
     crew=2100, freq=2)
ship("u7c", "Type VIIC U-boat", "ss", ["germany"], (1940.8, 1950), length=1, speed=17, subspeed=7, hp=100,
     main=(88, 1, 60, 5, 20, 30), aa=(1, 0), torps=(5, 75, 44), crew=50, freq=20)
ship("u9c", "Type IXC U-boat", "ss", ["germany"], (1941, 1950), length=1, speed=18, subspeed=7, hp=110,
     main=(105, 1, 60, 5, 30, 35), aa=(1, 0), torps=(6, 75, 44), crew=48, freq=10)
ship("sboot", "S-boot", "pt", ["germany"], (1939, 1950), length=1, speed=43, hp=40, main=(20, 1, 20, 1, 5, 12),
     torps=(2, 70, 44), crew=24, freq=8)

# ------------------------------------------------------------ Japan
ship("kagero", "Kagero-class destroyer", "dd", ["japan"], (1939.9, 1950), length=1, speed=35, hp=210,
     main=(127, 6, 120, 5, 60, 70), aa=(6, 0), torps=(8, 200, 48), dc=16, sonar=True, radar=1944, crew=240, freq=20)
ship("fubuki", "Fubuki-class destroyer", "dd", ["japan"], (1928, 1950), length=1, speed=38, hp=190,
     main=(127, 6, 120, 5, 60, 70), aa=(4, 0), torps=(9, 200, 48), dc=18, sonar=True, crew=220, freq=14)
ship("myoko", "Myōkō-class heavy cruiser", "ca", ["japan"], (1929, 1950), length=2, speed=35, hp=720, belt=102,
     deck=35, main=(203, 10, 290, 10, 210, 260), sec=(127, 8, 130, 4, 60, 70), aa=(16, 0), torps=(16, 200, 48),
     crew=890, freq=6)
ship("kongo", "Kongō-class battleship", "bb", ["japan"], (1914, 1945), length=3, speed=30, hp=1300, belt=203,
     deck=100, main=(356, 8, 320, 30, 330, 600), sec=(152, 14, 220, 6, 150, 150), aa=(40, 0), radar=1943.5,
     crew=1400, freq=4)
ship("yamato", "Yamato-class battleship", "bb", ["japan"], (1941.95, 1945.3), length=3, speed=27, hp=2400,
     belt=410, deck=200, main=(460, 9, 420, 40, 500, 900), sec=(155, 12, 250, 6, 170, 160), aa=(90, 0), radar=1943,
     crew=2500, freq=1)
ship("shokaku", "Shōkaku-class carrier", "cv", ["japan"], (1941.6, 1945), length=3, speed=34, hp=950, belt=46,
     sec=(127, 16, 130, 4, 60, 70), aa=(36, 0), air=(18, 27, 27), crew=1660, freq=4)
ship("i_boat", "I-class submarine", "ss", ["japan"], (1937, 1950), length=1, speed=23, subspeed=8, hp=130,
     main=(140, 1, 70, 6, 40, 45), torps=(17, 200, 48), crew=94, freq=6)
ship("maru", "transport maru", "ap", ["japan"], (1930, 1950), length=2, speed=12, hp=260, aa=(2, 0), crew=50, freq=8)

# ------------------------------------------------------------ Italy, the USSR, France
ship("soldati", "Soldati-class destroyer", "dd", ["italy"], (1938, 1950), length=1, speed=38, hp=180,
     main=(120, 5, 110, 5, 50, 60), aa=(8, 0), torps=(6, 90, 44), dc=20, sonar=True, crew=215, freq=14)
ship("zara", "Zara-class cruiser", "ca", ["italy"], (1931, 1950), length=2, speed=32, hp=700, belt=150, deck=70,
     main=(203, 8, 290, 12, 210, 260), sec=(100, 16, 100, 4, 30, 40), aa=(16, 0), crew=840, freq=4)
ship("littorio", "Littorio-class battleship", "bb", ["italy"], (1940.4, 1950), length=3, speed=30, hp=1700, belt=350,
     deck=150, main=(381, 9, 390, 30, 380, 650), sec=(152, 12, 220, 6, 150, 150), aa=(40, 0), crew=1830, freq=3)
ship("gnevny", "Gnevny-class destroyer", "dd", ["ussr"], (1938, 1950), length=1, speed=38, hp=180,
     main=(130, 4, 130, 5, 60, 70), aa=(4, 0), torps=(6, 90, 44), dc=25, sonar=True, crew=200, freq=10)
ship("kirov", "Kirov-class cruiser", "cl", ["ussr"], (1938, 1950), length=2, speed=35, hp=580, belt=50,
     main=(180, 9, 280, 8, 150, 180), sec=(100, 6, 100, 4, 30, 40), aa=(10, 0), crew=870, freq=3)
ship("shch", "Shch-class submarine", "ss", ["ussr"], (1933, 1950), length=1, speed=12, subspeed=8, hp=90,
     main=(45, 1, 40, 3, 10, 15), torps=(6, 70, 44), crew=38, freq=5)
ship("lefantasque", "Le Fantasque-class destroyer", "dd", ["france"], (1935, 1950), length=1, speed=40, hp=200,
     main=(138, 5, 140, 6, 70, 80), aa=(4, 0), torps=(9, 90, 43), dc=16, sonar=True, crew=230, freq=8)


# Escorts and auxiliaries make the supply war visible alongside the capital ships.
ship("cannon", "Cannon-class destroyer escort", "de", ["usa", "france"], (1943.7, 1950),
     length=1, speed=21, hp=150, main=(76, 3, 90, 3, 30, 40), aa=(8, 0), torps=(3, 90, 45),
     dc=120, sonar=True, radar=1943.7, crew=216)
ship("evarts", "Evarts-class destroyer escort", "de", ["usa", "uk"], (1943.1, 1950),
     length=1, speed=19, hp=130, main=(76, 3, 90, 3, 30, 40), aa=(6, 0), dc=100, sonar=True,
     radar=1943.1, crew=156)
ship("independence", "Independence-class light carrier", "cve", ["usa"], (1943.1, 1950),
     length=2, speed=31, hp=590, belt=127, aa=(26, 0), radar=1943.1, air=(24, 0, 9), crew=1560, freq=5)
ship("sangamon", "Sangamon-class escort carrier", "cve", ["usa"], (1942.7, 1950),
     length=2, speed=18, hp=460, sec=(127, 2, 120, 5, 60, 65), aa=(20, 0), radar=1942.7,
     air=(18, 0, 12), crew=1080)
ship("cimarron", "Cimarron-class fleet oiler", "ap", ["usa"], (1939.2, 1950),
     length=2, speed=18, hp=400, main=(127, 4, 100, 7, 50, 60), aa=(8, 0), crew=304,
     desc="Fleet oiler. Transfers fuel alongside in calm water at low speed.")
ship("vestal", "Vestal repair ship", "ap", ["usa"], (1913, 1950),
     length=2, speed=16, hp=340, aa=(6, 0), crew=465, freq=3,
     desc="A floating workshop and stores ship. Supports damaged escorts and transports.")
ship("river_frigate", "River-class frigate", "de", ["uk", "canada", "australia"], (1942.4, 1950),
     length=1, speed=20, hp=170, main=(102, 2, 100, 5, 35, 45), aa=(8, 0), dc=150,
     sonar=True, radar=1942.4, crew=140)
ship("matsu", "Matsu-class escort destroyer", "dd", ["japan"], (1944.3, 1950),
     length=1, speed=28, hp=150, main=(127, 3, 110, 5, 50, 60), aa=(24, 0), torps=(4, 160, 48),
     dc=36, sonar=True, radar=1944.3, crew=211)
SHIPS["cimarron"]["cargo"] = dict(fuel=600.)
SHIPS["vestal"]["cargo"] = dict(parts=250., medical=100.)


def available(nation, year, cls=None):
    out = []
    for s in SHIPS.values():
        if nation not in s["nations"]:
            continue
        y0, y1 = s["years"]
        if not (y0 <= year < y1):
            continue
        if cls is not None and s["cls"] not in (cls if isinstance(cls, (tuple, list)) else (cls,)):
            continue
        out.append(s)
    return out


CLASS_NAME = {"dd": "destroyer", "de": "escort", "cl": "light cruiser", "ca": "heavy cruiser", "bb": "battleship",
              "cv": "fleet carrier", "cve": "escort carrier", "ss": "submarine", "pt": "torpedo boat",
              "ap": "transport", "lst": "landing ship"}
