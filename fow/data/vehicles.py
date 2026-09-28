"""Vehicles, emplaced guns, aircraft and off-map artillery.

Armour values are effective millimetres (slope folded in) for (front, side, rear, top).
Vehicle `speed` is moves per tile on good ground (lower = faster; soldiers walk at 100).
`crush` 0 = none, 1 = fences/wire/brush, 2 = trees/hedges/wood walls, 3 = brick walls.
"""
from __future__ import annotations

from .defs import AircraftType, BatteryType, GunMount, ItemType, VehicleType
from .items import ITEMS

MOUNTS: dict[str, GunMount] = {}
VEHICLES: dict[str, VehicleType] = {}
AIRCRAFT: dict[str, AircraftType] = {}
BATTERIES: dict[str, BatteryType] = {}


def mount(id, name, cal_mm, ap_pen, he_power, rng=90, **kw):
    he_radius = kw.pop("he_radius", max(1, int(round(cal_mm / 28))))
    he_frags = kw.pop("he_frags", int(min(70, cal_mm * 0.6)))
    reload = kw.pop("reload_cost", int(300 + cal_mm * 3.2))
    MOUNTS[id] = GunMount(id, name, cal_mm=cal_mm, ap_pen=ap_pen, he_power=he_power, rng=rng,
                          he_radius=he_radius, he_frags=he_frags, reload_cost=reload,
                          ap_dmg=int(120 + cal_mm * 2.2), **kw)


# ---------------------------------------------------------------- gun mounts
mount("20mm_kwk", "2 cm KwK 30", 20, 25, 20, rng=70, reload_cost=100, he_radius=1, he_frags=6)
mount("20mm_flak", "2 cm FlaK 38", 20, 25, 20, rng=80, reload_cost=100, he_radius=1, he_frags=6, aa=True)
mount("flakvierling", "2 cm Flakvierling 38", 20, 25, 20, rng=80, reload_cost=80, he_radius=1,
      he_frags=6, aa=True)
mount("20mm_jp", "Type 98 20mm", 20, 22, 20, rng=75, reload_cost=100, he_radius=1, he_frags=6, aa=True)
mount("20mm_breda", "Breda 20/65", 20, 22, 20, rng=75, reload_cost=100, he_radius=1, he_frags=6, aa=True)
mount("37mm_pak36", "3.7 cm Pak 36", 37, 35, 45, rng=80, reload_cost=260)
mount("37mm_kwk", "3.7 cm KwK 36", 37, 35, 45, rng=80)
mount("37mm_m6", "37mm M6", 37, 50, 45, rng=80)
mount("37mm_bofors", "37mm Bofors wz. 36", 37, 40, 45, rng=80, reload_cost=260)
mount("37mm_jp", "Type 94 37mm", 37, 35, 45, rng=75, reload_cost=260)
mount("37mm_skoda", "37mm KwK 34(t)", 37, 38, 45, rng=80)
mount("37mm_sa38", "37mm SA38", 37, 30, 40, rng=70)
mount("37mm_61k", "37mm 61-K AA", 37, 45, 50, rng=90, reload_cost=150, aa=True)
mount("40mm_bofors", "40mm Bofors", 40, 45, 55, rng=95, reload_cost=150, aa=True)
mount("40mm_2pdr", "QF 2-pounder", 40, 50, 20, rng=85)
mount("45mm_20k", "45mm 20-K", 45, 45, 55, rng=85)
mount("45mm_m37", "45mm M1937", 45, 45, 55, rng=85, reload_cost=280)
mount("47mm_jp", "Type 1 47mm", 47, 55, 60, rng=85)
mount("47mm_it", "Cannone 47/32", 47, 45, 55, rng=80)
mount("47mm_sa35", "47mm SA35", 47, 55, 60, rng=85)
mount("47mm_sa37", "47mm SA37", 47, 70, 60, rng=90, reload_cost=300)
mount("50mm_kwk38", "5 cm KwK 38", 50, 55, 70, rng=85)
mount("50mm_kwk39", "5 cm KwK 39", 50, 70, 70, rng=90)
mount("50mm_pak38", "5 cm Pak 38", 50, 75, 70, rng=90, reload_cost=300)
mount("57mm_6pdr", "QF 6-pounder", 57, 90, 70, rng=95, reload_cost=320)
mount("57mm_m1", "57mm M1", 57, 90, 70, rng=95, reload_cost=320)
mount("57mm_jp", "Type 97 57mm", 57, 25, 110, rng=70)
mount("57mm_zis2", "57mm ZiS-2", 57, 110, 70, rng=100, reload_cost=320)
mount("75mm_kwk37", "7.5 cm KwK 37 L/24", 75, 40, 150, rng=80)
mount("75mm_kwk40", "7.5 cm KwK 40 L/48", 75, 105, 150, rng=100)
mount("75mm_stuk40", "7.5 cm StuK 40", 75, 105, 150, rng=100)
mount("75mm_kwk42", "7.5 cm KwK 42 L/70", 75, 150, 140, rng=110)
mount("75mm_pak40", "7.5 cm Pak 40", 75, 115, 150, rng=105, reload_cost=380)
mount("75mm_pak39", "7.5 cm Pak 39 L/48", 75, 105, 150, rng=100)
mount("75mm_m3", "75mm M3", 75, 75, 170, rng=95)
mount("75mm_m2", "75mm M2 (hull)", 75, 65, 170, rng=90)
mount("75mm_it", "Obice 75/18", 75, 50, 160, rng=85)
mount("75mm_sa35", "75mm SA35 (hull)", 75, 40, 170, rng=80)
mount("75mm_mle1897", "Canon de 75 mle 1897", 75, 45, 170, rng=95, reload_cost=320)
mount("75mm_wz97", "75mm wz. 1897", 75, 40, 170, rng=90, reload_cost=320)
mount("75mm_resita", "75mm Reșița M1943", 75, 110, 150, rng=100, reload_cost=380)
mount("76mm_f34", "76mm F-34", 76, 70, 160, rng=95)
mount("76mm_zis3", "76mm ZiS-3", 76, 75, 160, rng=100, reload_cost=330)
mount("76mm_m1", "76mm M1", 76, 100, 150, rng=100)
mount("3in_m7", "3-inch M7", 76, 95, 150, rng=100)
mount("3in_m5", "3-inch M5", 76, 100, 150, rng=100, reload_cost=380)
mount("17pdr", "QF 17-pounder", 76, 150, 140, rng=110)
mount("17pdr_towed", "QF 17-pounder", 76, 150, 140, rng=110, reload_cost=380)
mount("85mm_zis", "85mm ZiS-S-53", 85, 110, 180, rng=105)
mount("85mm_d5", "85mm D-5S", 85, 110, 180, rng=105)
mount("88mm_kwk36", "8.8 cm KwK 36", 88, 130, 200, rng=110)
mount("88mm_flak", "8.8 cm FlaK 36", 88, 135, 200, rng=120, reload_cost=380, aa=True)
mount("88mm_kwk43", "8.8 cm KwK 43 L/71", 88, 200, 200, rng=120)
mount("88mm_pak43", "8.8 cm Pak 43", 88, 200, 200, rng=120)
mount("90mm_m3", "90mm M3", 90, 150, 200, rng=110)
mount("95mm_how", "95mm howitzer", 95, 40, 260, rng=85)
mount("105mm_m4", "105mm M4 howitzer", 105, 50, 280, rng=90)
mount("122mm_d25", "122mm D-25T", 122, 160, 380, rng=110, reload_cost=900)
mount("152mm_ml20", "152mm ML-20S", 152, 130, 500, rng=100, reload_cost=1000)
mount("152mm_m10", "152mm M-10T", 152, 90, 500, rng=90, reload_cost=1000)
mount("70mm_type92", "Type 92 battalion gun", 70, 25, 150, rng=80, reload_cost=350)
mount("crocodile", "Crocodile flame projector", 0, 0, 0, rng=36, reload_cost=100, flame=True)
mount("flame_hull", "flame projector", 0, 0, 0, rng=10, reload_cost=100, flame=True)
mount("25mm_hotchkiss", "25mm Hotchkiss", 25, 40, 25, rng=80, reload_cost=180, he_radius=1)
mount("20mm_tks", "20mm FK wz. 38", 20, 30, 20, rng=70, reload_cost=100, he_radius=1)


def veh(id, name, vtype, nations, years, armor, *, hp=None, **kw):
    if hp is None:
        hp = {"tank": 260, "td": 220, "spg": 220, "ltank": 170, "tankette": 90, "halftrack": 150,
              "armcar": 130, "truck": 110, "car": 70, "lc": 120, "amtrac": 140, "atgun": 80,
              "aagun": 70, "fieldgun": 90}.get(vtype, 150)
    glyph = kw.pop("glyph", {"tank": "T", "td": "D", "spg": "D", "ltank": "t", "tankette": "t",
                            "halftrack": "H", "armcar": "A", "truck": "K", "car": "c",
                            "lc": "L", "amtrac": "L", "atgun": "G", "aagun": "Y",
                            "fieldgun": "G"}.get(vtype, "V"))
    static = vtype in ("atgun", "aagun", "fieldgun")
    VEHICLES[id] = VehicleType(id, name, vtype=vtype, nations=tuple(nations), years=years,
                               armor=armor, hp=hp, glyph=glyph, static=static, **kw)


# ------------------------------------------------ USA
veh("m4", "M4 Sherman", "tank", ["usa", "uk", "ussr", "france"], (1942.8, 1950), (80, 38, 38, 19),
    speed=55, crush=3, crew=5, main="75mm_m3", mgs=("m1919", "m1919"), ap=30, he=60, freq=14,
    smoke=2, desc="The ubiquitous Sherman. Reliable, fast, and prone to brewing up.")
veh("m4a3e8", "M4A3E8 Sherman 'Easy Eight'", "tank", ["usa"], (1944.7, 1950), (90, 38, 38, 19),
    speed=50, crush=3, crew=5, main="76mm_m1", mgs=("m1919", "m1919"), ap=35, he=40, freq=6,
    smoke=2, desc="76mm Sherman on HVSS suspension.")
veh("m4_105", "M4 Sherman (105mm)", "tank", ["usa"], (1944, 1950), (80, 38, 38, 19),
    speed=58, crush=3, crew=5, main="105mm_m4", mgs=("m1919",), ap=10, he=60, freq=2)
veh("m3_stuart", "M3 Stuart", "ltank", ["usa", "uk", "australia", "china"], (1941.9, 1944),
    (45, 25, 25, 12), speed=40, crush=2, crew=4, main="37mm_m6", mgs=("m1919", "m1919"), ap=40,
    he=40, desc="Light tank. The British called it 'Honey'.")
veh("m5_stuart", "M5 Stuart", "ltank", ["usa", "uk"], (1942.9, 1950), (50, 28, 25, 12), speed=38,
    crush=2, crew=4, main="37mm_m6", mgs=("m1919", "m1919"), ap=40, he=50)
veh("m24", "M24 Chaffee", "ltank", ["usa"], (1944.9, 1950), (38, 25, 19, 12), speed=38, crush=2,
    crew=5, main="75mm_m3", mgs=("m1919", "m1919"), ap=20, he=40, freq=4)
veh("m3_lee", "M3 Lee/Grant", "tank", ["usa", "uk", "australia"], (1942, 1944), (51, 38, 38, 13),
    speed=55, crush=3, crew=6, main="75mm_m2", mgs=("m1919",), ap=30, he=40, freq=5)
veh("m10", "M10 Wolverine", "td", ["usa", "france"], (1942.9, 1950), (60, 25, 19, 0), speed=55,
    crush=3, crew=5, main="3in_m7", mgs=("m2hb",), ap=40, he=20, open_top=True,
    desc="Tank destroyer with an open-topped turret.")
veh("m18", "M18 Hellcat", "td", ["usa"], (1944.5, 1950), (25, 13, 13, 0), speed=32, crush=2,
    crew=5, main="76mm_m1", mgs=("m2hb",), ap=40, he=20, open_top=True, freq=4,
    desc="The fastest tracked vehicle of the war. Paper armour.")
veh("m36", "M36 Jackson", "td", ["usa"], (1944.7, 1950), (76, 25, 19, 0), speed=55, crush=3,
    crew=5, main="90mm_m3", mgs=("m2hb",), ap=35, he=15, open_top=True, freq=3)
veh("m3_ht", "M3 half-track", "halftrack", ["usa", "uk", "ussr", "france"], (1941, 1950),
    (12, 6, 6, 0), speed=45, crush=1, crew=2, seats=10, mgs=("m2hb",), open_top=True,
    desc="Armoured half-track for an infantry squad.")
veh("m16_mgmc", "M16 MGMC 'Meat Chopper'", "halftrack", ["usa"], (1943.5, 1950), (12, 6, 6, 0),
    speed=45, crush=1, crew=4, mgs=("m2hb", "m2hb", "m2hb", "m2hb"), open_top=True, aa=True,
    freq=2, desc="Quad .50 anti-aircraft half-track. Devastating against infantry.")
veh("m8_greyhound", "M8 Greyhound", "armcar", ["usa", "france"], (1943, 1950), (19, 10, 10, 0),
    speed=35, crush=1, crew=4, main="37mm_m6", mgs=("m1919",), ap=30, he=30, open_top=True)
veh("jeep", "Willys MB jeep", "car", ["usa", "uk", "ussr", "france", "china"], (1941.5, 1950),
    (0, 0, 0, 0), speed=30, crush=0, crew=1, seats=3, mgs=("m1919",), open_top=True,
    desc="Quarter-ton utility truck.")
veh("gmc", "GMC CCKW truck", "truck", ["usa", "france"], (1941, 1950), (0, 0, 0, 0), speed=40,
    crush=1, crew=1, seats=12, open_top=True, desc="The 'Jimmy' deuce-and-a-half.")
veh("lcvp", "LCVP 'Higgins boat'", "lc", ["usa", "uk", "canada"], (1942, 1950), (10, 3, 3, 0),
    speed=40, crew=3, seats=30, mgs=("m1919",), open_top=True, water="water",
    desc="Plywood landing craft with a steel ramp. Thirty men and a prayer.")
veh("lvt", "LVT-2 Water Buffalo", "amtrac", ["usa"], (1943, 1950), (12, 6, 6, 0), speed=60,
    crush=1, crew=3, seats=18, mgs=("m2hb", "m1919"), open_top=True, water="amphib",
    desc="Amphibious tractor. Crawls over coral reefs.")
veh("m1_57mm", "57mm M1 anti-tank gun", "atgun", ["usa"], (1943, 1950), (10, 0, 0, 0),
    speed=400, crew=4, main="57mm_m1", ap=40, he=20, turret=False)
veh("m5_3in", "3-inch M5 anti-tank gun", "atgun", ["usa"], (1943.5, 1950), (10, 0, 0, 0),
    speed=500, crew=5, main="3in_m5", ap=40, he=20, turret=False, freq=4)
veh("oerlikon", "20mm Oerlikon", "aagun", ["usa", "uk", "canada", "australia", "newzealand", "india", "france"],
    (1940, 1950), (4, 0, 0, 0), speed=200, crew=2, main="20mm_flak", ap=20, he=240, aa=True, freq=0,
    desc="The ship's light AA gun: shoulder it, lean into it, and hose the sky.")
veh("pompom", "2-pdr 'pom-pom'", "aagun", ["uk", "canada", "australia"], (1930, 1950), (6, 0, 0, 0), speed=600,
    crew=4, main="40mm_bofors", ap=10, he=200, aa=True, freq=0, desc="The Royal Navy's eight-barrelled pom-pom.")
veh("type96_25", "Type 96 25mm AA", "aagun", ["japan"], (1936, 1950), (6, 0, 0, 0), speed=600, crew=4,
    main="20mm_jp", ap=15, he=240, aa=True, freq=0, desc="The Imperial Navy's triple 25mm: slow to train, and "
                                                         "the magazines hold fifteen rounds.")
veh("flak_c38", "3.7 cm SK C/30", "aagun", ["germany"], (1935, 1950), (6, 0, 0, 0), speed=600, crew=4,
    main="40mm_bofors", ap=10, he=160, aa=True, freq=0, desc="The Kriegsmarine's twin 37mm - single shots, "
                                                           "hand-loaded.")
veh("bofors_us", "40mm Bofors", "aagun", ["usa", "uk", "poland", "australia", "india"],
    (1939, 1950), (6, 0, 0, 0), speed=500, crew=5, main="40mm_bofors", ap=10, he=80,
    aa=True, turret=True)

# ------------------------------------------------ Britain / Commonwealth
veh("matilda", "Matilda II", "tank", ["uk", "australia", "ussr"], (1940, 1943.5), (78, 65, 55, 20),
    speed=90, crush=3, crew=4, main="40mm_2pdr", mgs=("besa",), ap=60, he=0,
    desc="'Queen of the Desert'. Slow but armoured like a pillbox.")
veh("valentine", "Valentine", "tank", ["uk", "ussr", "newzealand"], (1941, 1945), (65, 60, 60, 15),
    speed=70, crush=3, crew=3, main="40mm_2pdr", mgs=("besa",), ap=60, he=0)
veh("crusader", "Crusader III", "tank", ["uk", "australia"], (1941.5, 1943.5), (51, 28, 28, 12),
    speed=45, crush=2, crew=3, main="57mm_6pdr", mgs=("besa",), ap=50, he=10)
veh("churchill", "Churchill VII", "tank", ["uk", "canada"], (1942.5, 1950), (120, 76, 50, 20),
    speed=85, crush=3, crew=5, main="75mm_m3", mgs=("besa", "besa"), ap=30, he=50,
    desc="Slow, heavily armoured infantry tank. Climbs anything.")
veh("churchill_croc", "Churchill Crocodile", "tank", ["uk"], (1944.4, 1950), (120, 76, 50, 20),
    speed=90, crush=3, crew=5, main="crocodile", mgs=("besa",), ap=0, he=0, freq=2,
    desc="Churchill towing a fuel trailer. Its flame projector reaches 80 yards.")
veh("cromwell", "Cromwell IV", "tank", ["uk"], (1944, 1950), (76, 32, 32, 14), speed=40, crush=3,
    crew=5, main="75mm_m3", mgs=("besa", "besa"), ap=30, he=40)
veh("firefly", "Sherman Firefly", "tank", ["uk", "canada", "poland"], (1944.4, 1950),
    (80, 38, 38, 19), speed=55, crush=3, crew=4, main="17pdr", mgs=("m1919",), ap=45, he=20,
    freq=5, desc="Sherman with the 17-pounder. Tiger crews prioritized it.")
veh("sherman_v", "Sherman V", "tank", ["uk", "canada", "poland", "newzealand", "india"],
    (1942.8, 1950), (80, 38, 38, 19), speed=55, crush=3, crew=5, main="75mm_m3",
    mgs=("m1919", "m1919"), ap=30, he=60, freq=12)
veh("achilles", "Achilles (17pdr M10)", "td", ["uk", "canada", "poland"], (1944.5, 1950),
    (60, 25, 19, 0), speed=55, crush=3, crew=5, main="17pdr", mgs=("m2hb",), ap=40, he=10,
    open_top=True, freq=3)
veh("carrier", "Universal Carrier", "halftrack", ["uk", "canada", "australia", "newzealand",
    "india", "poland"], (1938, 1950), (10, 7, 7, 0), speed=40, crush=1, crew=2, seats=3,
    mgs=("bren",), open_top=True, desc="The Bren gun carrier. Does everything.")
veh("humber", "Humber armoured car", "armcar", ["uk", "india"], (1941, 1950), (15, 10, 10, 8),
    speed=40, crush=1, crew=3, main=None, mgs=("besa_hvy", "besa"), freq=5)
veh("bedford", "Bedford QL truck", "truck", ["uk", "canada", "australia", "newzealand", "india",
    "poland"], (1941, 1950), (0, 0, 0, 0), speed=40, crush=1, crew=1, seats=12, open_top=True)
veh("2pdr_gun", "QF 2-pounder anti-tank gun", "atgun", ["uk", "australia", "india"],
    (1938, 1943), (10, 0, 0, 0), speed=400, crew=4, main="40mm_2pdr", ap=50, he=0, turret=False)
veh("6pdr_gun", "QF 6-pounder anti-tank gun", "atgun", ["uk", "canada", "australia",
    "newzealand", "india", "poland"], (1942, 1950), (10, 0, 0, 0), speed=450, crew=5,
    main="57mm_6pdr", ap=40, he=20, turret=False)
veh("17pdr_gun", "QF 17-pounder anti-tank gun", "atgun", ["uk", "canada", "poland"],
    (1943, 1950), (10, 0, 0, 0), speed=600, crew=6, main="17pdr_towed", ap=40, he=10,
    turret=False, freq=5)

# ------------------------------------------------ Soviet Union
veh("t26", "T-26", "ltank", ["ussr", "china", "finland"], (1933, 1942), (15, 15, 15, 6), speed=60,
    crush=2, crew=3, main="45mm_20k", mgs=("dt",), ap=40, he=40)
veh("bt7", "BT-7", "ltank", ["ussr"], (1935, 1942), (22, 13, 13, 10), speed=35, crush=2, crew=3,
    main="45mm_20k", mgs=("dt",), ap=40, he=40)
veh("t60", "T-60", "tankette", ["ussr"], (1941.7, 1944), (35, 25, 25, 10), speed=50, crush=1,
    crew=2, main="20mm_kwk", mgs=("dt",), ap=60, he=40, freq=5)
veh("t70", "T-70", "ltank", ["ussr"], (1942.5, 1945), (45, 35, 35, 10), speed=48, crush=2,
    crew=2, main="45mm_20k", mgs=("dt",), ap=40, he=40, freq=6)
veh("t34_76", "T-34/76", "tank", ["ussr", "finland"], (1941, 1945), (75, 45, 40, 16), speed=45,
    crush=3, crew=4, main="76mm_f34", mgs=("dt", "dt"), ap=30, he=50, freq=20,
    desc="Sloped armour, wide tracks, a shock to the Germans in 1941.")
veh("t34_85", "T-34-85", "tank", ["ussr", "poland"], (1944, 1950), (90, 45, 40, 18), speed=45,
    crush=3, crew=5, main="85mm_zis", mgs=("dt", "dt"), ap=30, he=30, freq=20)
veh("kv1", "KV-1", "tank", ["ussr"], (1941, 1944), (95, 75, 70, 30), speed=75, crush=3, crew=5,
    main="76mm_f34", mgs=("dt", "dt"), ap=30, he=60, freq=6,
    desc="Heavy tank almost immune to German guns in 1941.")
veh("kv2", "KV-2", "tank", ["ussr"], (1941, 1942), (95, 75, 70, 30), speed=110, crush=3, crew=6,
    main="152mm_m10", mgs=("dt",), ap=6, he=30, freq=2,
    desc="A 152mm howitzer in a turret the size of a house.")
veh("is2", "IS-2", "tank", ["ussr", "poland"], (1944, 1950), (120, 90, 60, 30), speed=65, crush=3,
    crew=4, main="122mm_d25", mgs=("dt", "dshk"), ap=10, he=18, freq=4,
    desc="Breakthrough heavy tank. Its 122mm gun is slow but crushing.")
veh("su76", "SU-76M", "spg", ["ussr", "poland"], (1943, 1950), (35, 15, 15, 0), speed=45, crush=2,
    crew=4, main="76mm_zis3", ap=20, he=40, open_top=True, turret=False,
    desc="Light self-propelled gun. 'Bitch' to her crews.")
veh("su85", "SU-85", "td", ["ussr"], (1943.7, 1945), (75, 45, 40, 16), speed=45, crush=3, crew=4,
    main="85mm_d5", ap=30, he=20, turret=False, freq=5)
veh("su152", "SU-152 'Zveroboy'", "spg", ["ussr"], (1943.4, 1945), (75, 60, 60, 20), speed=70,
    crush=3, crew=5, main="152mm_ml20", ap=8, he=12, turret=False, freq=3,
    desc="'Beast killer'. A 152mm gun-howitzer on a KV hull.")
veh("ba64", "BA-64 armoured car", "armcar", ["ussr", "poland"], (1942, 1950), (15, 10, 10, 6),
    speed=35, crush=0, crew=2, mgs=("dt",), open_top=True)
veh("zis5", "ZiS-5 truck", "truck", ["ussr"], (1933, 1950), (0, 0, 0, 0), speed=45, crush=1,
    crew=1, seats=12, open_top=True)
veh("45mm_gun", "45mm M1937 anti-tank gun", "atgun", ["ussr", "china", "finland"], (1937, 1950),
    (10, 0, 0, 0), speed=350, crew=4, main="45mm_m37", ap=40, he=30, turret=False,
    desc="The 'Sorokopyatka'. Farewell, Motherland, its crews called it.")
veh("zis3_gun", "76mm ZiS-3 divisional gun", "atgun", ["ussr", "poland"], (1942, 1950),
    (10, 0, 0, 0), speed=450, crew=5, main="76mm_zis3", ap=30, he=40, turret=False)
veh("zis2_gun", "57mm ZiS-2 anti-tank gun", "atgun", ["ussr"], (1943, 1950), (10, 0, 0, 0),
    speed=450, crew=5, main="57mm_zis2", ap=40, he=20, turret=False, freq=5)
veh("61k", "37mm 61-K AA gun", "aagun", ["ussr"], (1939, 1950), (6, 0, 0, 0), speed=500,
    crew=5, main="37mm_61k", ap=10, he=80, aa=True)

# ------------------------------------------------ Germany
veh("pz1", "Panzer I", "tankette", ["germany", "china"], (1934, 1941.5), (13, 13, 13, 6), speed=50,
    crush=1, crew=2, main=None, mgs=("mg34", "mg34"), freq=4)
veh("pz2", "Panzer II", "ltank", ["germany"], (1936, 1943), (30, 15, 15, 10), speed=45, crush=2,
    crew=3, main="20mm_kwk", mgs=("mg34",), ap=80, he=100)
veh("pz38t", "Panzer 38(t)", "ltank", ["germany", "hungary", "romania"], (1939, 1942.5),
    (30, 15, 15, 8), speed=48, crush=2, crew=4, main="37mm_skoda", mgs=("mg34", "mg34"), ap=50,
    he=40)
veh("pz3", "Panzer III Ausf. J", "tank", ["germany"], (1939, 1944), (50, 30, 30, 12), speed=50,
    crush=3, crew=5, main="50mm_kwk39", mgs=("mg34", "mg34"), ap=45, he=45, freq=10)
veh("pz3n", "Panzer III Ausf. N", "tank", ["germany"], (1942.5, 1944), (70, 30, 30, 12),
    speed=50, crush=3, crew=5, main="75mm_kwk37", mgs=("mg34", "mg34"), ap=20, he=50, freq=3)
veh("pz4d", "Panzer IV Ausf. D", "tank", ["germany"], (1939, 1942.3), (30, 20, 20, 10),
    speed=50, crush=3, crew=5, main="75mm_kwk37", mgs=("mg34", "mg34"), ap=25, he=55)
veh("pz4", "Panzer IV Ausf. H", "tank", ["germany", "hungary", "romania", "finland"],
    (1942.3, 1950), (80, 30, 20, 12), speed=50, crush=3, crew=5, main="75mm_kwk40",
    mgs=("mg34", "mg34"), ap=40, he=40, freq=20, desc="The workhorse of the Panzerwaffe.")
veh("stug3", "StuG III Ausf. G", "td", ["germany", "finland", "romania"], (1942.5, 1950),
    (80, 30, 30, 10), speed=50, crush=3, crew=4, main="75mm_stuk40", mgs=("mg34",), ap=40, he=35,
    turret=False, freq=14, desc="Assault gun. Low, cheap, and deadly in ambush.")
veh("stug3b", "StuG III Ausf. B", "spg", ["germany"], (1940, 1942.5), (50, 30, 30, 10), speed=50,
    crush=3, crew=4, main="75mm_kwk37", ap=20, he=50, turret=False)
veh("tiger", "Tiger I", "tank", ["germany"], (1942.7, 1950), (110, 80, 80, 25), speed=70, crush=3,
    crew=5, main="88mm_kwk36", mgs=("mg34", "mg34"), ap=45, he=45, freq=3, smoke=2,
    desc="The 88mm on a heavily armoured hull. Every Allied tanker's nightmare.")
veh("panther", "Panther Ausf. G", "tank", ["germany"], (1943.5, 1950), (140, 50, 40, 16),
    speed=50, crush=3, crew=5, main="75mm_kwk42", mgs=("mg34", "mg34"), ap=45, he=35, freq=7,
    smoke=2, desc="Sloped frontal armour, a long 75mm, and a fragile final drive.")
veh("kingtiger", "Tiger II", "tank", ["germany"], (1944.5, 1950), (185, 80, 80, 40), speed=80,
    crush=3, crew=5, main="88mm_kwk43", mgs=("mg34", "mg34"), ap=45, he=35, freq=1,
    desc="Königstiger. Nearly invulnerable from the front. Drinks fuel it doesn't have.")
veh("marder3", "Marder III", "td", ["germany"], (1942.3, 1945), (50, 15, 10, 0), speed=50,
    crush=2, crew=4, main="75mm_pak40", mgs=("mg34",), ap=30, he=10, turret=False,
    open_top=True, freq=5)
veh("hetzer", "Jagdpanzer 38(t) Hetzer", "td", ["germany", "hungary"], (1944.3, 1950),
    (110, 20, 20, 8), speed=55, crush=2, crew=4, main="75mm_pak39", mgs=("mg34",), ap=30, he=15,
    turret=False, freq=6)
veh("jagdpanther", "Jagdpanther", "td", ["germany"], (1944.5, 1950), (140, 50, 40, 25), speed=55,
    crush=3, crew=5, main="88mm_kwk43", mgs=("mg34",), ap=40, he=15, turret=False, freq=1)
veh("elefant", "Elefant", "td", ["germany"], (1943.5, 1945), (200, 80, 80, 30), speed=110,
    crush=3, crew=6, main="88mm_pak43", ap=40, he=10, turret=False, freq=1,
    desc="Tank destroyer. No machine gun at Kursk - infantry swarmed it.")
veh("sdkfz251", "Sd.Kfz. 251 half-track", "halftrack", ["germany", "hungary", "romania"],
    (1939, 1950), (14, 8, 8, 0), speed=45, crush=1, crew=2, seats=10, mgs=("mg34", "mg42"),
    open_top=True, desc="'Hanomag' armoured personnel carrier.")
veh("sdkfz222", "Sd.Kfz. 222", "armcar", ["germany"], (1937, 1950), (14, 8, 8, 0), speed=35,
    crush=0, crew=3, main="20mm_kwk", mgs=("mg34",), ap=40, he=100, open_top=True)
veh("puma", "Sd.Kfz. 234/2 Puma", "armcar", ["germany"], (1944, 1950), (30, 10, 10, 10),
    speed=32, crush=1, crew=4, main="50mm_kwk39", mgs=("mg42",), ap=30, he=25, freq=3)
veh("kubel", "Kübelwagen", "car", ["germany", "hungary", "romania"], (1940, 1950), (0, 0, 0, 0),
    speed=32, crush=0, crew=1, seats=3, mgs=("mg34",), open_top=True)
veh("opel_blitz", "Opel Blitz truck", "truck", ["germany", "hungary", "romania"], (1937, 1950),
    (0, 0, 0, 0), speed=40, crush=1, crew=1, seats=12, open_top=True)
veh("pak36_gun", "3.7 cm Pak 36", "atgun", ["germany", "china", "romania", "hungary"],
    (1936, 1943), (8, 0, 0, 0), speed=300, crew=4, main="37mm_pak36", ap=50, he=30,
    turret=False, desc="The 'door knocker'. Useless against T-34s.")
veh("pak38_gun", "5 cm Pak 38", "atgun", ["germany", "romania", "hungary"], (1941, 1945),
    (8, 0, 0, 0), speed=400, crew=5, main="50mm_pak38", ap=40, he=30, turret=False)
veh("pak40_gun", "7.5 cm Pak 40", "atgun", ["germany", "romania", "hungary", "finland"],
    (1942, 1950), (8, 0, 0, 0), speed=600, crew=5, main="75mm_pak40", ap=40, he=30,
    turret=False, freq=14, desc="The standard German anti-tank gun of the late war.")
veh("flak88", "8.8 cm FlaK 36", "aagun", ["germany", "finland", "hungary"], (1936, 1950),
    (10, 0, 0, 0), speed=900, crew=8, main="88mm_flak", ap=30, he=40, aa=True, freq=4,
    desc="The 'eighty-eight'. Anti-aircraft gun turned tank killer.")
veh("flak38", "2 cm FlaK 38", "aagun", ["germany", "hungary", "romania", "finland"],
    (1939, 1950), (6, 0, 0, 0), speed=350, crew=4, main="20mm_flak", ap=20, he=160, aa=True,
    desc="Light flak. Chews up infantry and aircraft alike.")
veh("flakvierling", "2 cm Flakvierling 38", "aagun", ["germany"], (1941, 1950), (6, 0, 0, 0),
    speed=500, crew=6, main="flakvierling", ap=20, he=240, aa=True, freq=3)

# ------------------------------------------------ Italy
veh("l3_35", "L3/35 tankette", "tankette", ["italy"], (1935, 1943), (14, 8, 8, 6), speed=45,
    crush=1, crew=2, mgs=("breda38", "breda38"), freq=6)
veh("l6_40", "L6/40", "ltank", ["italy"], (1941, 1943.8), (30, 15, 15, 6), speed=45, crush=1,
    crew=2, main="20mm_breda", mgs=("breda38",), ap=40, he=100, freq=4)
veh("m11_39", "M11/39", "tank", ["italy"], (1940, 1941.5), (30, 15, 15, 8), speed=70, crush=2,
    crew=3, main="37mm_skoda", mgs=("breda38", "breda38"), ap=40, he=40, freq=3)
veh("m13_40", "M13/40", "tank", ["italy"], (1940.8, 1943.8), (42, 25, 25, 10), speed=65,
    crush=2, crew=4, main="47mm_it", mgs=("breda38", "breda38", "breda38"), ap=40, he=40,
    freq=12, desc="Italy's main tank. Riveted plates crack under fire.")
veh("m14_41", "M14/41", "tank", ["italy"], (1941.5, 1943.8), (42, 25, 25, 10), speed=60,
    crush=2, crew=4, main="47mm_it", mgs=("breda38", "breda38"), ap=40, he=40, freq=8)
veh("semovente", "Semovente 75/18", "spg", ["italy"], (1941.9, 1943.8), (50, 25, 25, 10),
    speed=60, crush=2, crew=3, main="75mm_it", mgs=("breda38",), ap=20, he=40, turret=False,
    freq=5, desc="Assault gun. Italy's most effective armoured vehicle.")
veh("ab41", "AB 41 armoured car", "armcar", ["italy"], (1941, 1943.8), (15, 9, 9, 6), speed=32,
    crush=0, crew=4, main="20mm_breda", mgs=("breda38",), ap=40, he=100)
veh("fiat626", "Fiat 626 truck", "truck", ["italy"], (1939, 1950), (0, 0, 0, 0), speed=45,
    crush=1, crew=1, seats=12, open_top=True)
veh("47_32_gun", "Cannone da 47/32", "atgun", ["italy"], (1935, 1950), (6, 0, 0, 0), speed=280,
    crew=4, main="47mm_it", ap=40, he=30, turret=False)
veh("breda20", "Breda 20/65", "aagun", ["italy"], (1935, 1950), (6, 0, 0, 0), speed=350,
    crew=4, main="20mm_breda", ap=20, he=160, aa=True)

# ------------------------------------------------ Japan
veh("type94_tk", "Type 94 tankette", "tankette", ["japan"], (1934, 1945), (12, 12, 10, 6),
    speed=45, crush=1, crew=2, mgs=("type91",), freq=4)
veh("ha_go", "Type 95 Ha-Go", "ltank", ["japan"], (1935, 1950), (12, 12, 10, 9), speed=40,
    crush=1, crew=3, main="37mm_jp", mgs=("type97_tmg", "type97_tmg"), ap=40, he=40, freq=12,
    desc="Light tank. Its armour stops rifle rounds and little else.")
veh("chi_ha", "Type 97 Chi-Ha", "tank", ["japan"], (1938, 1950), (25, 25, 20, 10), speed=55,
    crush=2, crew=4, main="57mm_jp", mgs=("type97_tmg", "type97_tmg"), ap=20, he=60, freq=10)
veh("shinhoto", "Type 97 Shinhoto Chi-Ha", "tank", ["japan"], (1942, 1950), (25, 25, 20, 10),
    speed=55, crush=2, crew=4, main="47mm_jp", mgs=("type97_tmg", "type97_tmg"), ap=40, he=40,
    freq=8)
veh("type94_truck", "Type 94 truck", "truck", ["japan"], (1934, 1950), (0, 0, 0, 0), speed=45,
    crush=1, crew=1, seats=12, open_top=True)
veh("type1_47", "Type 1 47mm anti-tank gun", "atgun", ["japan"], (1942, 1950), (6, 0, 0, 0),
    speed=350, crew=5, main="47mm_jp", ap=40, he=30, turret=False)
veh("type94_37", "Type 94 37mm gun", "atgun", ["japan"], (1936, 1950), (6, 0, 0, 0), speed=300,
    crew=4, main="37mm_jp", ap=40, he=30, turret=False)
veh("type92_bg", "Type 92 battalion gun", "fieldgun", ["japan"], (1932, 1950), (6, 0, 0, 0),
    speed=300, crew=5, main="70mm_type92", ap=10, he=40, turret=False)
veh("type98_aa", "Type 98 20mm AA gun", "aagun", ["japan"], (1938, 1950), (6, 0, 0, 0),
    speed=350, crew=4, main="20mm_jp", ap=20, he=160, aa=True)

# ------------------------------------------------ France 1940
veh("char_b1", "Char B1 bis", "tank", ["france"], (1937, 1941), (60, 60, 55, 25), speed=80,
    crush=3, crew=4, main="47mm_sa35", mgs=("reibel", "reibel"), ap=50, he=40, freq=6,
    desc="Heavy tank with a hull 75mm howitzer. The commander also loads and aims the turret gun.")
veh("somua", "Somua S35", "tank", ["france"], (1936, 1941), (47, 40, 40, 20), speed=50, crush=3,
    crew=3, main="47mm_sa35", mgs=("reibel",), ap=50, he=40, freq=8)
veh("r35", "Renault R35", "ltank", ["france", "poland", "romania"], (1936, 1942),
    (43, 40, 40, 15), speed=70, crush=2, crew=2, main="37mm_sa38", mgs=("reibel",), ap=40, he=40,
    freq=12)
veh("h39", "Hotchkiss H39", "ltank", ["france"], (1939, 1941), (45, 40, 40, 15), speed=55,
    crush=2, crew=2, main="37mm_sa38", mgs=("reibel",), ap=40, he=40, freq=8)
veh("panhard178", "Panhard 178", "armcar", ["france"], (1937, 1941), (20, 15, 15, 8), speed=32,
    crush=0, crew=4, main="25mm_hotchkiss", mgs=("reibel",), ap=40, he=30)
veh("laffly", "Laffly truck", "truck", ["france"], (1936, 1941), (0, 0, 0, 0), speed=45, crush=1,
    crew=1, seats=10, open_top=True)
veh("25mm_gun", "25mm Hotchkiss anti-tank gun", "atgun", ["france"], (1934, 1941),
    (6, 0, 0, 0), speed=250, crew=3, main="25mm_hotchkiss", ap=50, he=20, turret=False)
veh("47mm_gun", "47mm SA37 anti-tank gun", "atgun", ["france"], (1937, 1941), (8, 0, 0, 0),
    speed=400, crew=5, main="47mm_sa37", ap=40, he=20, turret=False)
veh("75mm_gun", "Canon de 75 mle 1897", "fieldgun", ["france", "poland"], (1897, 1945),
    (6, 0, 0, 0), speed=450, crew=6, main="75mm_mle1897", ap=20, he=60, turret=False,
    desc="The legendary French 75.")

# ------------------------------------------------ Poland 1939
veh("7tp", "7TP", "ltank", ["poland"], (1935, 1940), (17, 17, 10, 8), speed=50, crush=2, crew=3,
    main="37mm_bofors", mgs=("ckm_wz30_t",), ap=40, he=40, freq=8,
    desc="Polish light tank; outgunned most Panzers of 1939.")
veh("tks", "TKS tankette", "tankette", ["poland"], (1934, 1940), (10, 8, 8, 5), speed=40,
    crush=1, crew=2, mgs=("ckm_wz30_t",), freq=10)
veh("tks20", "TKS with 20mm", "tankette", ["poland"], (1939, 1940), (10, 8, 8, 5), speed=40,
    crush=1, crew=2, main="20mm_tks", ap=40, he=20, freq=2)
veh("wz34", "wz. 34 armoured car", "armcar", ["poland"], (1934, 1940), (8, 6, 6, 4), speed=40,
    crush=0, crew=2, mgs=("ckm_wz30_t",))
veh("pf621", "Polski Fiat 621 truck", "truck", ["poland"], (1935, 1940), (0, 0, 0, 0), speed=45,
    crush=1, crew=1, seats=10, open_top=True)
veh("bofors37_gun", "37mm Bofors wz. 36", "atgun", ["poland"], (1936, 1940), (6, 0, 0, 0),
    speed=280, crew=4, main="37mm_bofors", ap=50, he=20, turret=False,
    desc="Excellent little anti-tank gun that shredded early Panzers.")

# ------------------------------------------------ Finland / Hungary / Romania
veh("toldi", "38M Toldi", "ltank", ["hungary"], (1940, 1944), (20, 13, 13, 6), speed=45, crush=1,
    crew=3, main="20mm_breda", mgs=("solothurn31m",), ap=40, he=100)
veh("turan", "40M Turán I", "tank", ["hungary"], (1942, 1945), (50, 25, 25, 10), speed=55,
    crush=2, crew=5, main="47mm_sa37", mgs=("schwarzlose_t", "schwarzlose_t"), ap=40, he=40,
    freq=10)
veh("zrinyi", "Zrínyi II", "spg", ["hungary"], (1943.5, 1945), (75, 25, 25, 10), speed=60,
    crush=2, crew=4, main="105mm_m4", ap=10, he=40, turret=False, freq=3)
veh("csaba", "39M Csaba", "armcar", ["hungary"], (1940, 1945), (13, 7, 7, 6), speed=35, crush=0,
    crew=4, main="20mm_breda", mgs=("solothurn31m",), ap=40, he=60)
veh("r2", "R-2 (LT vz. 35)", "ltank", ["romania"], (1938, 1944), (25, 16, 16, 8), speed=55,
    crush=2, crew=4, main="37mm_skoda", mgs=("zb53_t",), ap=40, he=40)
veh("tacam", "TACAM T-60", "td", ["romania"], (1943.5, 1945), (35, 15, 15, 0), speed=55, crush=2,
    crew=3, main="76mm_f34", ap=30, he=20, turret=False, open_top=True, freq=3)
veh("resita_gun", "75mm Reșița M1943", "atgun", ["romania"], (1943.5, 1950), (8, 0, 0, 0),
    speed=600, crew=5, main="75mm_resita", ap=40, he=30, turret=False, freq=6)
veh("bt42", "BT-42", "spg", ["finland"], (1942, 1945), (22, 13, 13, 10), speed=40, crush=2,
    crew=3, main="95mm_how", ap=10, he=40, freq=2, desc="Finnish howitzer conversion of a BT-7.")
veh("37mm_fin", "37 PstK/36", "atgun", ["finland"], (1936, 1950), (6, 0, 0, 0), speed=280,
    crew=4, main="37mm_bofors", ap=50, he=20, turret=False)

# ------------------------------------------------ field artillery (installations)
mount("105mm_m2a1", "105mm M2A1 howitzer", 105, 45, 260, rng=90, reload_cost=500)
mount("25pdr", "QF 25-pounder", 88, 70, 220, rng=95, reload_cost=450)
mount("lefh18", "10.5 cm leFH 18", 105, 45, 260, rng=90, reload_cost=500)
mount("m30_how", "122mm M-30 howitzer", 122, 50, 320, rng=90, reload_cost=600)
mount("it_75_27", "Cannone da 75/27", 75, 40, 160, rng=90, reload_cost=380)
mount("type91_how", "Type 91 105mm howitzer", 105, 40, 250, rng=90, reload_cost=500)
mount("wz14_how", "100mm wz. 14/19 howitzer", 100, 35, 230, rng=85, reload_cost=480)
veh("m2a1_how", "105mm M2A1 howitzer", "fieldgun", ["usa", "france", "china"], (1941, 1950),
    (6, 0, 0, 0), speed=900, crew=6, main="105mm_m2a1", ap=4, he=60, turret=False, freq=0)
veh("25pdr_gun", "QF 25-pounder gun-howitzer", "fieldgun", ["uk", "canada", "australia",
    "newzealand", "india", "poland"], (1939, 1950), (8, 0, 0, 0), speed=800, crew=6, main="25pdr",
    ap=12, he=60, turret=False, freq=0, desc="The 25-pounder. Also a fine anti-tank gun in a pinch.")
veh("lefh18_gun", "10.5 cm leFH 18", "fieldgun", ["germany", "hungary", "romania", "finland"],
    (1935, 1950), (6, 0, 0, 0), speed=900, crew=6, main="lefh18", ap=4, he=60, turret=False, freq=0)
veh("m30_gun", "122mm M-30 howitzer", "fieldgun", ["ussr", "poland", "finland"], (1939, 1950),
    (6, 0, 0, 0), speed=1000, crew=8, main="m30_how", ap=2, he=50, turret=False, freq=0)
veh("it75_gun", "Cannone da 75/27", "fieldgun", ["italy"], (1911, 1950), (6, 0, 0, 0),
    speed=700, crew=6, main="it_75_27", ap=6, he=60, turret=False, freq=0)
veh("type91_gun", "Type 91 105mm howitzer", "fieldgun", ["japan"], (1931, 1950), (6, 0, 0, 0),
    speed=900, crew=6, main="type91_how", ap=4, he=60, turret=False, freq=0)
veh("wz14_gun", "100mm wz. 14/19 howitzer", "fieldgun", ["poland"], (1919, 1941), (6, 0, 0, 0),
    speed=900, crew=6, main="wz14_how", ap=4, he=60, turret=False, freq=0)
# the medium guns and the rocket launchers of the batteries (fires.py puts each battery's own pieces down)
mount("155mm_m1", "155mm M1 howitzer", 155, 60, 400, rng=95, reload_cost=900)
mount("sfh18", "15 cm sFH 18", 150, 60, 410, rng=95, reload_cost=900)
mount("ml20", "152mm ML-20 gun-howitzer", 152, 70, 420, rng=100, reload_cost=950)
mount("55in", "BL 5.5-inch medium gun", 140, 60, 340, rng=100, reload_cost=800)
mount("zis3_div", "76mm ZiS-3 divisional gun", 76, 70, 160, rng=95, reload_cost=350)
mount("type38_75", "Type 38 75mm field gun", 75, 40, 150, rng=85, reload_cost=380)
mount("it_100_17", "Obice da 100/17", 100, 35, 220, rng=85, reload_cost=480)
mount("fr_155gpf", "Canon de 155 GPF", 155, 60, 380, rng=100, reload_cost=950)
mount("bm13", "BM-13 rocket rails", 132, 20, 210, rng=100, reload_cost=3000)
mount("nbw41", "15 cm Nebelwerfer 41", 150, 20, 280, rng=90, reload_cost=2400)
veh("m1_155", "155mm M1 howitzer", "fieldgun", ["usa"], (1942, 1950), (6, 0, 0, 0), speed=1200, crew=11,
    main="155mm_m1", ap=2, he=40, turret=False, freq=0)
veh("sfh18_gun", "15 cm sFH 18", "fieldgun", ["germany"], (1935, 1950), (6, 0, 0, 0), speed=1200, crew=7,
    main="sfh18", ap=2, he=40, turret=False, freq=0)
veh("ml20_gun", "152mm ML-20 gun-howitzer", "fieldgun", ["ussr"], (1939, 1950), (6, 0, 0, 0), speed=1200,
    crew=9, main="ml20", ap=2, he=40, turret=False, freq=0)
veh("55in_gun", "BL 5.5-inch medium gun", "fieldgun", ["uk", "canada", "newzealand", "poland"], (1942, 1950),
    (6, 0, 0, 0), speed=1200, crew=10, main="55in", ap=2, he=40, turret=False, freq=0)
veh("zis3_div_gun", "76mm ZiS-3 divisional gun", "fieldgun", ["ussr", "poland"], (1939, 1950), (6, 0, 0, 0),
    speed=700, crew=6, main="zis3_div", ap=10, he=60, turret=False, freq=0)
veh("type38_gun", "Type 38 75mm field gun", "fieldgun", ["japan"], (1905, 1950), (6, 0, 0, 0), speed=700,
    crew=6, main="type38_75", ap=6, he=60, turret=False, freq=0)
veh("it100_gun", "Obice da 100/17", "fieldgun", ["italy"], (1914, 1950), (6, 0, 0, 0), speed=900, crew=6,
    main="it_100_17", ap=2, he=50, turret=False, freq=0)
veh("gpf155_gun", "Canon de 155 GPF", "fieldgun", ["france"], (1917, 1950), (6, 0, 0, 0), speed=1300, crew=8,
    main="fr_155gpf", ap=2, he=40, turret=False, freq=0)
veh("katyusha", "BM-13 Katyusha", "truck", ["ussr", "poland"], (1941.6, 1950), (4, 0, 0, 0), speed=45, crush=1,
    crew=5, main="bm13", ap=0, he=16, turret=False, freq=0,
    desc="Sixteen 132mm rockets on rails on the back of a lorry. 'Stalin's organ.'")
veh("nebelwerfer", "15 cm Nebelwerfer 41", "fieldgun", ["germany"], (1941, 1950), (4, 0, 0, 0), speed=900,
    crew=4, main="nbw41", ap=0, he=12, turret=False, freq=0, desc="Six rocket tubes on a wheeled carriage.")

veh("ambulance", "field ambulance", "truck", ["usa", "uk", "ussr", "germany", "italy", "japan",
    "france", "poland", "china", "finland", "hungary", "romania", "canada", "australia",
    "newzealand", "india"], (1930, 1950), (0, 0, 0, 0), speed=45, crush=1, crew=1, seats=6,
    open_top=False, freq=0, desc="A red cross painted on the canvas. It helps, sometimes.")

# vehicle machine guns: aliases to infantry items with tweaks
VEHICLE_MG_ALIASES = {
    "m2hb": ("m1919", dict(dmg=70, pen=18, name="M2 Browning .50", sound="heavy .50 cal fire")),
    "besa": ("vickers", dict(name="BESA 7.92mm")),
    "besa_hvy": ("vickers", dict(dmg=65, pen=15, name="BESA 15mm")),
    "dt": ("dp28", dict(name="DT machine gun")),
    "dshk": ("maxim1910", dict(dmg=70, pen=18, name="DShK 12.7mm", sound="heavy DShK fire")),
    "breda38": ("breda37", dict(name="Breda M38")),
    "type91": ("type11", dict(name="Type 91 MG")),
    "type97_tmg": ("type96", dict(name="Type 97 MG")),
    "reibel": ("fm2429", dict(name="MAC 31 Reibel")),
    "ckm_wz30_t": ("ckm_wz30", dict(name="ckm wz. 30")),
    "schwarzlose_t": ("schwarzlose", dict(name="34/40M MG")),
    "zb53_t": ("zb26", dict(name="ZB-53")),
}

# ---------------------------------------------------------------- aircraft
# guns: tuple of (damage, range tiles, rounds per pass); bombs: (power, radius, count)
# rockets: (pen, power, count)

def plane(id, name, role, nations, years, **kw):
    AIRCRAFT[id] = AircraftType(id, name, role=role, nations=tuple(nations), years=years, **kw)


plane("p47", "P-47 Thunderbolt", "fighterbomber", ["usa", "france"], (1943.3, 1950), speed=9,
      hp=110, guns=((70, 12, 40),), bombs=((520, 7, 2),), rockets=((0, 180, 6),), freq=14,
      sound="the roar of a radial engine")
plane("p51", "P-51 Mustang", "fighter", ["usa"], (1943.9, 1950), speed=10, hp=70,
      guns=((70, 12, 30),), bombs=((360, 6, 2),), freq=8)
plane("p38", "P-38 Lightning", "fighterbomber", ["usa"], (1942.5, 1950), speed=10, hp=90,
      guns=((70, 12, 30), (110, 10, 6)), bombs=((520, 7, 2),), freq=5)
plane("p40", "P-40 Warhawk", "fighterbomber", ["usa", "uk", "australia", "china"],
      (1941, 1945), speed=8, hp=70, guns=((70, 11, 30),), bombs=((360, 6, 1),), freq=8)
plane("f4u", "F4U Corsair", "fighterbomber", ["usa", "newzealand"], (1943, 1950), speed=10,
      hp=90, guns=((70, 12, 36),), bombs=((520, 7, 2),), rockets=((0, 180, 8),), freq=10,
      sound="the whistle of a gull-winged fighter")
plane("sbd", "SBD Dauntless", "divebomber", ["usa"], (1941, 1945), speed=7, hp=70,
      guns=((70, 10, 10),), bombs=((600, 7, 1),), freq=6)
plane("b25", "B-25 Mitchell", "bomber", ["usa", "uk", "ussr", "china"], (1942, 1950), speed=7,
      hp=180, guns=((70, 10, 20),), bombs=((360, 6, 6),), freq=5)
plane("b17", "B-17 Flying Fortress", "heavybomber", ["usa"], (1942.5, 1950), speed=6, hp=300,
      guns=(), bombs=((360, 6, 12),), freq=3, sound="the drone of four-engine bombers")
plane("typhoon", "Hawker Typhoon", "fighterbomber", ["uk", "canada"], (1943.5, 1950), speed=9,
      hp=90, guns=((95, 11, 16),), rockets=((80, 220, 8),), bombs=((520, 7, 2),), freq=12,
      sound="the howl of a Sabre engine")
plane("spitfire", "Supermarine Spitfire", "fighter", ["uk", "canada", "poland", "australia"],
      (1939, 1950), speed=10, hp=60, guns=((50, 11, 30), (95, 11, 8)), freq=8)
plane("hurricane", "Hawker Hurricane", "fighterbomber", ["uk", "poland", "india"],
      (1939, 1944), speed=8, hp=70, guns=((50, 11, 36),), bombs=((250, 5, 2),), freq=8)
plane("beaufighter", "Bristol Beaufighter", "fighterbomber", ["uk", "australia"], (1941, 1950),
      speed=8, hp=110, guns=((95, 11, 20),), rockets=((80, 220, 8),), freq=4)
plane("blenheim", "Bristol Blenheim", "bomber", ["uk", "australia", "finland"], (1939, 1943),
      speed=6, hp=120, guns=((40, 8, 10),), bombs=((250, 5, 4),), freq=4)
plane("lancaster", "Avro Lancaster", "heavybomber", ["uk", "canada"], (1942.2, 1950), speed=6,
      hp=280, guns=(), bombs=((700, 8, 10),), freq=2, sound="the drone of heavy bombers")
plane("il2", "Il-2 Sturmovik", "attacker", ["ussr", "poland"], (1941.5, 1950), speed=7, hp=160,
      guns=((95, 11, 20), (50, 10, 30)), rockets=((50, 200, 8),), bombs=((250, 5, 4),),
      cannon_pen=35, freq=16, sound="the growl of a Sturmovik")
plane("yak9", "Yak-9", "fighter", ["ussr", "poland"], (1942.8, 1950), speed=10, hp=60,
      guns=((95, 11, 12), (60, 11, 20)), freq=8)
plane("i16", "Polikarpov I-16", "fighter", ["ussr", "china"], (1935, 1943), speed=8, hp=50,
      guns=((45, 10, 30),), bombs=((250, 5, 2),), freq=6)
plane("pe2", "Pe-2", "divebomber", ["ussr"], (1941, 1950), speed=8, hp=120,
      guns=((50, 10, 10),), bombs=((500, 7, 2),), freq=6)
plane("po2", "Po-2 'Night Witch'", "nightbomber", ["ussr"], (1941, 1950), speed=3, hp=30,
      guns=(), bombs=((250, 5, 2),), night=True, freq=6,
      sound="the rattle of a biplane engine, cutting out")
plane("bf109", "Bf 109", "fighter", ["germany", "finland", "hungary", "romania", "italy"],
      (1937, 1950), speed=10, hp=60, guns=((50, 11, 24), (95, 11, 10)),
      bombs=((250, 5, 1),), freq=10, sound="the scream of a Daimler-Benz engine")
plane("fw190", "Fw 190 F-8", "fighterbomber", ["germany"], (1942, 1950), speed=10, hp=85,
      guns=((50, 11, 24), (95, 11, 16)), bombs=((520, 7, 1),), freq=8)
plane("ju87", "Ju 87 Stuka", "divebomber", ["germany", "italy", "hungary", "romania"],
      (1937, 1944.8), speed=6, hp=80, guns=((50, 10, 16),), bombs=((1100, 9, 1), (250, 5, 4)),
      siren=True, freq=12, sound="the wail of a Jericho trumpet")
plane("ju87g", "Ju 87G 'Kanonenvogel'", "attacker", ["germany"], (1943, 1950), speed=6, hp=80,
      guns=((180, 11, 12),), cannon_pen=80, freq=2, sound="the drone of a Stuka")
plane("hs129", "Hs 129", "attacker", ["germany"], (1942.5, 1945), speed=7, hp=110,
      guns=((140, 11, 12), (50, 10, 20)), cannon_pen=60, freq=4)
plane("ju88", "Ju 88", "bomber", ["germany", "finland", "hungary", "romania"], (1939, 1950),
      speed=8, hp=150, guns=((50, 10, 10),), bombs=((500, 7, 4),), freq=6)
plane("he111", "He 111", "bomber", ["germany"], (1937, 1950), speed=6, hp=170,
      guns=((50, 10, 10),), bombs=((360, 6, 8),), freq=5, sound="the throb of bombers")
plane("me262", "Me 262", "fighterbomber", ["germany"], (1944.7, 1950), speed=15, hp=80,
      guns=((140, 11, 16),), bombs=((520, 7, 2),), freq=1,
      sound="an unearthly jet scream")
plane("mc202", "Macchi C.202 Folgore", "fighter", ["italy"], (1941.5, 1950), speed=10, hp=60,
      guns=((70, 11, 20), (45, 10, 20)), freq=10)
plane("cr42", "Fiat CR.42 Falco", "fighterbomber", ["italy", "hungary"], (1939, 1943.8), speed=6,
      hp=45, guns=((70, 10, 20),), bombs=((250, 5, 2),), freq=5,
      sound="the clatter of a biplane")
plane("sm79", "SM.79 Sparviero", "bomber", ["italy"], (1937, 1943.8), speed=7, hp=150,
      guns=((50, 10, 10),), bombs=((360, 6, 5),), freq=5)
plane("zero", "A6M Zero", "fighterbomber", ["japan"], (1940.5, 1950), speed=10, hp=45,
      guns=((95, 11, 12), (45, 10, 30)), bombs=((250, 5, 2),), freq=12)
plane("ki43", "Ki-43 Hayabusa", "fighter", ["japan"], (1941.5, 1950), speed=9, hp=40,
      guns=((70, 11, 20),), bombs=((250, 5, 2),), freq=8)
plane("d3a", "D3A 'Val'", "divebomber", ["japan"], (1940, 1945), speed=7, hp=60,
      guns=((45, 10, 16),), bombs=((600, 7, 1), (250, 5, 2)), freq=7)
plane("ki51", "Ki-51 'Sonia'", "attacker", ["japan"], (1940, 1950), speed=6, hp=55,
      guns=((70, 10, 20),), bombs=((250, 5, 4),), freq=5)
plane("g4m", "G4M 'Betty'", "bomber", ["japan"], (1941, 1950), speed=8, hp=90,
      guns=((45, 10, 10),), bombs=((360, 6, 6),), freq=4)
plane("ms406", "Morane-Saulnier MS.406", "fighter", ["france"], (1938, 1941), speed=8, hp=50,
      guns=((95, 10, 8), (45, 10, 20)), freq=8)
plane("d520", "Dewoitine D.520", "fighter", ["france"], (1940, 1941), speed=9, hp=55,
      guns=((95, 10, 10), (45, 10, 24)), freq=4)
plane("br693", "Breguet 693", "attacker", ["france"], (1940, 1941), speed=7, hp=70,
      guns=((95, 10, 10),), bombs=((250, 5, 4),), freq=4)
plane("pzl11", "PZL P.11", "fighter", ["poland"], (1934, 1940), speed=7, hp=45,
      guns=((45, 10, 30),), freq=8)
plane("karas", "PZL.23 Karaś", "bomber", ["poland"], (1936, 1940), speed=6, hp=70,
      guns=((45, 9, 10),), bombs=((250, 5, 4),), freq=6)
plane("buffalo", "Brewster Buffalo", "fighter", ["finland"], (1940, 1945), speed=8, hp=60,
      guns=((70, 11, 24),), freq=6, sound="a stubby fighter droning overhead")
plane("iar80", "IAR 80", "fighter", ["romania"], (1941, 1950), speed=9, hp=55,
      guns=((45, 10, 30),), bombs=((250, 5, 2),), freq=6)
plane("re2000", "Reggiane Re.2000 Héja", "fighter", ["hungary"], (1941, 1950), speed=9, hp=55,
      guns=((70, 10, 24),), freq=6)

# carrier aircraft, torpedo bombers, heavy and medium bombers, heavy fighters
plane("f4f", "F4F Wildcat", "fighter", ["usa", "uk"], (1940, 1945), speed=9, hp=70, guns=((70, 12, 30),), freq=6)
plane("f6f", "F6F Hellcat", "fighter", ["usa", "uk"], (1943.1, 1950), speed=10, hp=90, guns=((70, 12, 36),),
      rockets=((0, 180, 6),), freq=8)
plane("tbf", "TBF Avenger", "torpedo", ["usa", "uk", "newzealand"], (1942.4, 1950), speed=7, hp=110,
      guns=((70, 10, 10),), bombs=((600, 7, 1),), freq=6)
plane("sb2c", "SB2C Helldiver", "divebomber", ["usa"], (1943.8, 1950), speed=8, hp=90, guns=((95, 11, 10),),
      bombs=((600, 7, 1),), freq=6)
plane("b24", "B-24 Liberator", "heavybomber", ["usa"], (1942, 1950), speed=6, hp=290, guns=(), bombs=((360, 6, 12),),
      freq=3, sound="the drone of four-engine bombers")
plane("swordfish", "Fairey Swordfish", "torpedo", ["uk"], (1936, 1945), speed=4, hp=60, guns=((50, 10, 10),),
      bombs=((600, 7, 1),), freq=4, sound="the clatter of a biplane")
plane("wellington", "Vickers Wellington", "bomber", ["uk", "canada", "poland"], (1939, 1945), speed=6, hp=170,
      guns=((50, 10, 20),), bombs=((360, 6, 6),), freq=4)
plane("b5n", "B5N 'Kate'", "torpedo", ["japan"], (1937, 1945), speed=6, hp=60, guns=((45, 10, 10),),
      bombs=((600, 7, 1),), freq=6)
plane("bf110", "Bf 110", "fighter", ["germany"], (1939, 1950), speed=9, hp=110, guns=((50, 11, 20), (95, 11, 10)),
      bombs=((250, 5, 2),), freq=4)
plane("do17", "Do 17", "bomber", ["germany"], (1937, 1943), speed=7, hp=130, guns=((50, 10, 10),),
      bombs=((250, 5, 6),), freq=3)
plane("la5", "La-5", "fighter", ["ussr"], (1942.6, 1950), speed=10, hp=65, guns=((95, 11, 16),), freq=8)
plane("il4", "Il-4", "bomber", ["ussr"], (1938, 1950), speed=7, hp=140, guns=((50, 10, 10),), bombs=((500, 7, 4),),
      freq=4)
plane("ki84", "Ki-84 Hayate", "fighter", ["japan"], (1944.3, 1950), speed=11, hp=55, guns=((95, 11, 16),), freq=5)

# ---------------------------------------------------------------- off-map artillery

def battery(id, name, nations, years, **kw):
    BATTERIES[id] = BatteryType(id, name, nations=tuple(nations), years=years, **kw)


battery("us_105", "105mm M2A1 howitzers", ["usa", "france"], (1941, 1950), power=240, radius=5,
        frags=60, salvo=12, spread=7, delay=45, cal="105mm", freq=14)
battery("us_155", "155mm M1 howitzers", ["usa"], (1942, 1950), power=380, radius=6, frags=80,
        salvo=8, spread=8, delay=60, cal="155mm", freq=6)
battery("us_81", "81mm mortar section", ["usa", "france", "china"], (1939, 1950), power=120,
        radius=4, frags=40, salvo=12, spread=6, delay=25, cal="81mm", freq=10,
        sound="the whisper of falling mortar bombs")
battery("us_naval", "naval gunfire (destroyer 5-inch)", ["usa", "uk", "canada"], (1942, 1950),
        power=280, radius=5, frags=60, salvo=10, spread=8, delay=50, naval=True, cal="5-inch",
        freq=0)
battery("us_bb", "naval gunfire (battleship 14-inch)", ["usa", "uk"], (1942, 1950), power=1100,
        radius=9, frags=100, salvo=3, spread=10, delay=70, naval=True, cal="14-inch", freq=0,
        sound="a freight train tearing through the sky")
battery("uk_25pdr", "25-pounder field guns", ["uk", "canada", "australia", "newzealand",
        "india", "poland"], (1939, 1950), power=220, radius=5, frags=55, salvo=16, spread=7,
        delay=40, cal="25-pdr", freq=16)
battery("uk_55", "5.5-inch medium guns", ["uk", "canada", "newzealand", "poland"], (1942, 1950),
        power=330, radius=6, frags=70, salvo=8, spread=8, delay=60, cal="5.5-inch", freq=5)
battery("uk_3in", "3-inch mortar section", ["uk", "canada", "australia", "newzealand", "india",
        "poland"], (1939, 1950), power=120, radius=4, frags=40, salvo=12, spread=6, delay=25,
        cal="3-inch mortar", freq=10, sound="the whisper of falling mortar bombs")
battery("su_76", "76mm divisional guns", ["ussr", "poland"], (1939, 1950), power=150, radius=4,
        frags=45, salvo=16, spread=7, delay=35, cal="76mm", freq=10)
battery("su_122", "122mm M-30 howitzers", ["ussr", "poland"], (1939, 1950), power=300, radius=5,
        frags=70, salvo=12, spread=8, delay=50, cal="122mm", freq=10)
battery("su_152", "152mm ML-20 gun-howitzers", ["ussr"], (1939, 1950), power=420, radius=6,
        frags=80, salvo=6, spread=9, delay=70, cal="152mm", freq=4)
battery("su_katyusha", "BM-13 Katyusha rocket launchers", ["ussr", "poland"], (1941.6, 1950),
        power=210, radius=5, frags=50, salvo=32, spread=14, delay=60, rocket=True, cal="132mm rocket",
        freq=8, sound="a howling organ chorus of rockets")
battery("su_120", "120mm regimental mortars", ["ussr", "finland"], (1939, 1950), power=200,
        radius=5, frags=50, salvo=10, spread=7, delay=35, cal="120mm mortar", freq=8,
        sound="the whisper of falling mortar bombs")
battery("de_105", "10.5 cm leFH 18 howitzers", ["germany", "hungary", "romania", "finland"],
        (1935, 1950), power=240, radius=5, frags=60, salvo=12, spread=7, delay=45, cal="105mm",
        freq=14)
battery("de_150", "15 cm sFH 18 howitzers", ["germany"], (1935, 1950), power=400, radius=6,
        frags=80, salvo=6, spread=8, delay=65, cal="150mm", freq=5)
battery("de_81", "8 cm GrW 34 mortars", ["germany", "hungary", "romania"], (1934, 1950),
        power=125, radius=4, frags=40, salvo=12, spread=6, delay=25, cal="81mm mortar", freq=12,
        sound="the whisper of falling mortar bombs")
battery("de_nebelwerfer", "15 cm Nebelwerfer 41", ["germany"], (1941, 1950), power=280, radius=5,
        frags=60, salvo=18, spread=12, delay=55, rocket=True, cal="150mm rocket", freq=6,
        sound="the moaning shriek of Nebelwerfer rockets - 'Moaning Minnies'")
battery("it_75", "75/27 field guns", ["italy"], (1911, 1950), power=150, radius=4, frags=45,
        salvo=12, spread=8, delay=45, cal="75mm", freq=12)
battery("it_100", "100/17 howitzers", ["italy"], (1914, 1950), power=220, radius=5, frags=55,
        salvo=8, spread=8, delay=55, cal="100mm", freq=6)
battery("it_81", "81mm mortars", ["italy"], (1935, 1950), power=120, radius=4, frags=40,
        salvo=10, spread=6, delay=25, cal="81mm mortar", freq=8,
        sound="the whisper of falling mortar bombs")
battery("jp_75", "Type 38 75mm field guns", ["japan"], (1905, 1950), power=150, radius=4,
        frags=45, salvo=10, spread=8, delay=45, cal="75mm", freq=10)
battery("jp_105", "Type 91 105mm howitzers", ["japan"], (1931, 1950), power=240, radius=5,
        frags=60, salvo=8, spread=8, delay=55, cal="105mm", freq=6)
battery("jp_81", "Type 97 81mm mortars", ["japan"], (1937, 1950), power=120, radius=4, frags=40,
        salvo=10, spread=6, delay=25, cal="81mm mortar", freq=10,
        sound="the whisper of falling mortar bombs")
battery("jp_320", "320mm spigot mortar", ["japan"], (1944, 1950), power=950, radius=9,
        frags=60, salvo=2, spread=12, delay=80, rocket=True, cal="320mm", freq=2,
        sound="something enormous and tumbling - a 'flying ashcan'")
battery("fr_75", "75mm mle 1897 field guns", ["france", "poland"], (1897, 1950), power=150,
        radius=4, frags=45, salvo=16, spread=7, delay=35, cal="75mm", freq=14)
battery("fr_155", "155mm GPF guns", ["france"], (1917, 1950), power=380, radius=6, frags=80,
        salvo=6, spread=9, delay=65, cal="155mm", freq=5)
battery("pl_100", "100mm wz. 14/19 howitzers", ["poland"], (1919, 1950), power=220, radius=5,
        frags=55, salvo=8, spread=8, delay=50, cal="100mm", freq=8)
battery("cn_75", "75mm mountain guns", ["china"], (1920, 1950), power=130, radius=4, frags=40,
        salvo=6, spread=9, delay=55, cal="75mm", freq=8)
battery("cn_82", "82mm mortars", ["china"], (1930, 1950), power=115, radius=4, frags=35,
        salvo=8, spread=7, delay=30, cal="82mm mortar", freq=10,
        sound="the whisper of falling mortar bombs")
battery("fi_122", "122 H/10 howitzers", ["finland"], (1930, 1950), power=300, radius=5,
        frags=70, salvo=8, spread=7, delay=45, cal="122mm", freq=8)
battery("fi_81", "81 Krh/32 mortars", ["finland"], (1932, 1950), power=120, radius=4, frags=40,
        salvo=10, spread=5, delay=20, cal="81mm mortar", freq=10,
        sound="the whisper of falling mortar bombs")
battery("hu_105", "10.5 cm 37M howitzers", ["hungary", "romania"], (1937, 1950), power=240,
        radius=5, frags=60, salvo=8, spread=8, delay=50, cal="105mm", freq=8)


def _register_vehicle_mgs():
    for alias, (base, over) in VEHICLE_MG_ALIASES.items():
        b = ITEMS[base]
        attrs = {k: v for k, v in vars(b).items() if k not in ("id", "name")}
        attrs.update({k: v for k, v in over.items() if k != "name"})
        attrs["freq"] = 0
        attrs["nations"] = ()
        ITEMS[alias] = ItemType(alias, over.get("name", b.name), **attrs)


_register_vehicle_mgs()
