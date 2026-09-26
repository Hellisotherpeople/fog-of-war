"""Item database: small arms, launchers, grenades, explosives, gear.

Scale notes: one tile ~ 2 m.  Ranges are in tiles and deliberately compressed.
dmg is per projectile against ~60 hp torsos.  disp is base angular error in
degrees.  Costs are in moves (100 moves = 1 second for a normal soldier).
`nations` lists equipment pools (see nations.equip) not nations directly.
"""
from __future__ import annotations

from .defs import ItemType

ITEMS: dict[str, ItemType] = {}

GUN_COLOR = (170, 170, 185)
WOOD_GUN = (175, 135, 90)


def _reg(t: ItemType) -> ItemType:
    if t.id in ITEMS:
        raise KeyError(f"duplicate item id {t.id}")
    ITEMS[t.id] = t
    return t


# ================================================================= ammunition
CALIBERS = {
    # cal id: (name, dmg hint, weight per round kg)
    "3006": (".30-06 Springfield", 0.027),
    "30carb": (".30 Carbine", 0.013),
    "45acp": (".45 ACP", 0.021),
    "9mm": ("9x19mm Parabellum", 0.012),
    "792": ("7.92x57mm Mauser", 0.027),
    "792k": ("7.92x33mm Kurz", 0.017),
    "303": (".303 British", 0.026),
    "762r": ("7.62x54mmR", 0.024),
    "762t": ("7.62x25mm Tokarev", 0.011),
    "38200": (".38/200 revolver", 0.014),
    "455": (".455 Webley", 0.018),
    "65jp": ("6.5x50mm Arisaka", 0.021),
    "77jp": ("7.7x58mm Arisaka", 0.026),
    "8nambu": ("8x22mm Nambu", 0.011),
    "65it": ("6.5x52mm Carcano", 0.021),
    "9glis": ("9mm Glisenti", 0.011),
    "765l": ("7.65mm Longue", 0.010),
    "75fr": ("7.5x54mm MAS", 0.025),
    "8lebel": ("8x50mmR Lebel", 0.027),
    "8x56": ("8x56mmR Mannlicher", 0.027),
    "763m": ("7.63mm Mauser", 0.011),
    "9x25": ("9x25mm Mauser", 0.013),
    "50bmg": (".50 BMG", 0.115),
    "127r": ("12.7x108mm", 0.130),
    "145": ("14.5x114mm", 0.200),
    "55boys": (".55 Boys", 0.120),
    "792ds": ("7.92mm DS (AT)", 0.064),
    "20mm": ("20mm AT rounds", 0.330),
    "12ga": ("12 gauge buckshot", 0.045),
    # rockets and mortar bombs
    "rkt_bazooka": ("2.36in M6 rocket", 1.6),
    "rkt_schreck": ("8.8cm RPzB rocket", 3.3),
    "piat": ("PIAT bomb", 1.2),
    "m50": ("50mm mortar bomb", 0.9),
    "m60": ("60mm mortar bomb", 1.4),
    "m81": ("81/82mm mortar bomb", 3.2),
    "knee": ("50mm Type 89 shell", 0.8),
    "m45": ("45mm Brixia bomb", 0.5),
    "m46": ("46mm wz.36 bomb", 0.7),
    "fuel": ("flamethrower fuel (shots)", 1.0),
}

for _cal, (_nm, _w) in CALIBERS.items():
    big = _cal.startswith(("rkt", "piat", "m5", "m6", "m8", "knee", "m45", "m46"))
    _reg(ItemType(
        f"ammo_{_cal}", _nm if big else f"{_nm} rounds", kind="ammo", cal=_cal,
        weight=_w, volume=_w * 0.6, glyph="=", color=(200, 180, 90) if not big else (160, 160, 110),
        stack=1, desc=f"Ammunition: {_nm}.",
    ))


def ammo_id(cal: str) -> str:
    return f"ammo_{cal}"


# ================================================================= firearms

def gun(id, name, cat, cal, mag, dmg, disp, rng, nations, years=(1900, 1950), *,
        weight=4.0, modes=("single",), burst=1, shot=100, bcost=100, reload=200, jam=0.002,
        heat=0, pen=0, hands=2, freq=10, sound="rifle fire", loud=70, scope=False,
        deploy=False, pellets=1, feed="mag", bayonet=0, desc="", volume=None):
    color = WOOD_GUN if cat in ("rifle", "sniper", "carbine") else GUN_COLOR
    return _reg(ItemType(
        id, name, kind="gun", cat=cat, cal=cal, mag=mag, dmg=dmg, disp=disp, rng=rng,
        nations=tuple(nations), years=years, weight=weight, modes=modes, burst=burst,
        shot_cost=shot, burst_cost=bcost, reload_cost=reload, jam=jam, heat=heat, pen=pen,
        hands=hands, freq=freq, sound=sound, loud=loud, scope=scope, deploy=deploy,
        pellets=pellets, feed=feed, bayonet=bayonet, glyph="(", color=color, desc=desc,
        volume=volume if volume is not None else weight * 0.8,
    ))


# ---------------- United States
gun("m1_garand", "M1 Garand", "rifle", "3006", 8, 42, 0.65, 60, ["usa"], (1937, 1950),
    weight=4.4, shot=65, reload=150, feed="clip", bayonet=18, sound="the crack of a Garand",
    desc="Semi-automatic .30-06 service rifle. The en-bloc clip ejects with a loud ping.")
gun("m1903", "M1903 Springfield", "rifle", "3006", 5, 43, 0.5, 65, ["usa"], (1903, 1945),
    weight=4.0, shot=130, reload=190, feed="stripper", bayonet=18, freq=2,
    sound="the crack of a bolt-action rifle", desc="Accurate bolt-action rifle.")
gun("m1903a4", "M1903A4 Springfield (scoped)", "sniper", "3006", 5, 44, 0.18, 110, ["usa"],
    (1943, 1950), weight=4.5, shot=140, reload=230, scope=True, feed="stripper",
    sound="a sharp rifle crack", desc="Springfield with a Weaver 2.5x scope.")
gun("m1_carbine", "M1 Carbine", "carbine", "30carb", 15, 28, 1.0, 40, ["usa"], (1942, 1950),
    weight=2.6, shot=55, reload=120, jam=0.004, sound="light carbine fire",
    desc="Light semi-automatic carbine for officers and support troops.")
gun("thompson_m1a1", "Thompson M1A1", "smg", "45acp", 30, 26, 2.2, 22, ["usa", "uk", "china"],
    (1942, 1950), weight=4.9, modes=("single", "auto"), burst=5, shot=55, bcost=100, reload=180,
    sound="the chatter of a Tommy gun", loud=65, desc="The 'Chicago typewriter'. Heavy, reliable.")
gun("thompson_1928", "Thompson M1928A1", "smg", "45acp", 20, 26, 2.3, 22,
    ["usa", "uk", "australia", "china", "france"], (1938, 1943), weight=5.0,
    modes=("single", "auto"), burst=5, shot=55, bcost=100, reload=190, sound="Tommy gun fire",
    loud=65, desc="Pre-war Thompson with Cutts compensator.")
gun("m3_grease", "M3 'Grease Gun'", "smg", "45acp", 30, 25, 2.4, 20, ["usa"], (1943.5, 1950),
    weight=3.7, modes=("auto",), burst=4, bcost=100, reload=180, jam=0.004,
    sound="slow, heavy SMG fire", loud=62, desc="Cheap stamped SMG with a slow rate of fire.")
gun("bar", "M1918A2 BAR", "lmg", "3006", 20, 42, 1.25, 55, ["usa"], (1938, 1950), weight=9.0,
    modes=("auto",), burst=4, bcost=100, reload=190, heat=3, sound="the pounding of a BAR",
    loud=75, desc="Browning Automatic Rifle. Squad automatic weapon, bipod-mounted.")
gun("m1919", "M1919A4 Browning", "hmg", "3006", 100, 42, 0.9, 80, ["usa"], (1936, 1950),
    weight=14.0, modes=("auto",), burst=7, bcost=100, reload=420, heat=2, deploy=True,
    feed="belt", sound="Browning machine-gun fire", loud=80,
    desc="Belt-fed .30 cal on a tripod. Must be set up prone to be accurate.")
gun("m1911", "M1911A1", "pistol", "45acp", 7, 24, 2.6, 12,
    ["usa", "uk", "china", "france"], (1911, 1950), weight=1.1, hands=1, shot=50, reload=90,
    sound="a pistol shot", loud=60, desc="The Colt .45 automatic.")
gun("m97_trench", "M1897 Trench Gun", "shotgun", "12ga", 5, 12, 5.0, 10, ["usa"],
    (1917, 1950), weight=3.6, shot=110, reload=260, pellets=9, freq=2, feed="tube",
    sound="a shotgun blast", loud=72, bayonet=18, desc="Pump shotgun loaded with 00 buckshot.")

# ---------------- British Commonwealth
gun("smle", "Lee-Enfield SMLE No.1 Mk III", "rifle", "303", 10, 41, 0.6, 60,
    ["uk", "australia", "india"], (1907, 1950), weight=4.0, shot=100, reload=200, feed="stripper",
    bayonet=18, sound="the crack of a Lee-Enfield",
    desc="Ten-round bolt-action rifle. Fast bolt: the 'mad minute'.")
gun("lee_no4", "Lee-Enfield No.4 Mk I", "rifle", "303", 10, 41, 0.55, 62, ["uk"],
    (1941.5, 1950), weight=4.1, shot=95, reload=200, feed="stripper", bayonet=16,
    sound="the crack of a Lee-Enfield", desc="Simplified wartime Lee-Enfield with spike bayonet.")
gun("lee_no4t", "Lee-Enfield No.4 Mk I (T)", "sniper", "303", 10, 42, 0.2, 105, ["uk"],
    (1942, 1950), weight=5.0, shot=120, reload=230, scope=True, feed="stripper",
    sound="a sharp rifle crack", desc="Sniper conversion with No.32 3.5x scope.")
gun("sten", "Sten Mk II", "smg", "9mm", 32, 22, 2.6, 18, ["uk", "canada", "newzealand", "india"],
    (1941.5, 1950), weight=3.2, modes=("single", "auto"), burst=5, shot=55, bcost=100,
    reload=170, jam=0.018, sound="Sten gun fire", loud=62,
    desc="Crude, cheap SMG. The magazine loves to jam.")
gun("owen", "Owen Mk 1", "smg", "9mm", 33, 22, 2.2, 20, ["australia"], (1942, 1950), weight=4.2,
    modes=("single", "auto"), burst=5, shot=55, bcost=100, reload=170, jam=0.001,
    sound="Owen gun fire", loud=62, desc="Ugly, top-fed and nearly impossible to jam.")
gun("bren", "Bren Mk I", "lmg", "303", 30, 41, 0.95, 65, ["uk", "australia", "india"],
    (1938, 1950), weight=10.2, modes=("single", "auto"), burst=4, shot=60, bcost=100, reload=170,
    heat=2, sound="the steady bursts of a Bren", loud=76,
    desc="Accurate top-fed light machine gun.")
gun("vickers", "Vickers Mk I", "hmg", "303", 100, 41, 0.85, 85, ["uk", "australia", "india"],
    (1912, 1950), weight=18.0, modes=("auto",), burst=7, bcost=100, reload=450, heat=1,
    deploy=True, feed="belt", sound="Vickers gun fire", loud=80,
    desc="Water-cooled machine gun. Will fire all day.")
gun("webley", "Webley Mk IV revolver", "pistol", "38200", 6, 20, 2.8, 11,
    ["uk", "australia", "india"], (1932, 1950), weight=1.0, hands=1, shot=55, reload=150,
    feed="tube", sound="a revolver shot", loud=60, desc="Standard British officer's revolver.")
gun("hipower", "Browning Hi-Power (Inglis)", "pistol", "9mm", 13, 20, 2.5, 12,
    ["uk", "china"], (1944, 1950), weight=1.0, hands=1, shot=50, reload=90, freq=4,
    sound="a pistol shot", loud=60, desc="Thirteen-round 9mm pistol.")
gun("boys", "Boys anti-tank rifle", "at_rifle", "55boys", 5, 80, 0.7, 60,
    ["uk", "australia", "india"], (1937, 1943.5), weight=16.0, shot=160, reload=250, pen=21,
    deploy=True, sound="the heavy boom of an anti-tank rifle", loud=85,
    desc="Heavy .55 anti-tank rifle. Bruises the shoulder, not much else by 1942.")

# ---------------- Soviet Union
gun("mosin", "Mosin-Nagant M91/30", "rifle", "762r", 5, 42, 0.6, 60, ["ussr", "finland"],
    (1930, 1950), weight=4.0, shot=130, reload=190, feed="stripper", bayonet=16,
    sound="the crack of a Mosin", desc="Rugged bolt-action rifle. Bayonet is always fixed.")
gun("m44", "Mosin-Nagant M44 carbine", "carbine", "762r", 5, 41, 0.8, 50, ["ussr"],
    (1944, 1950), weight=3.9, shot=120, reload=180, feed="stripper", bayonet=16,
    sound="a sharp carbine report", desc="Short carbine with folding bayonet.")
gun("mosin_pu", "Mosin-Nagant 91/30 PU", "sniper", "762r", 5, 43, 0.2, 110, ["ussr"],
    (1942, 1950), weight=4.8, shot=140, reload=220, scope=True, feed="stripper",
    sound="a sharp rifle crack", desc="Sniper rifle with PU 3.5x scope.")
gun("svt40", "SVT-40", "rifle", "762r", 10, 41, 0.8, 55, ["ussr"], (1940, 1950), weight=3.9,
    shot=70, reload=160, jam=0.008, freq=3, sound="the crack of an SVT",
    desc="Semi-automatic rifle. Temperamental in the mud.")
gun("ppsh", "PPSh-41", "smg", "762t", 71, 20, 2.7, 20, ["ussr"], (1941.5, 1950), weight=5.4,
    modes=("single", "auto"), burst=7, shot=50, bcost=100, reload=260, jam=0.006,
    sound="the buzz of a PPSh", loud=64, desc="71-round drum, 900 rounds a minute. 'Papasha'.")
gun("ppd40", "PPD-40", "smg", "762t", 71, 20, 2.5, 20, ["ussr"], (1940, 1942.5), weight=5.4,
    modes=("single", "auto"), burst=6, shot=50, bcost=100, reload=260, jam=0.004,
    sound="SMG fire", loud=64, desc="Pre-war Degtyaryov SMG with drum magazine.")
gun("pps43", "PPS-43", "smg", "762t", 35, 20, 2.4, 20, ["ussr"], (1943, 1950), weight=3.7,
    modes=("auto",), burst=5, bcost=100, reload=170, jam=0.003, sound="SMG fire", loud=63,
    desc="Stamped-steel SMG designed in besieged Leningrad.")
gun("dp28", "DP-28", "lmg", "762r", 47, 42, 1.3, 60, ["ussr"], (1928, 1950), weight=11.5,
    modes=("auto",), burst=4, bcost=100, reload=230, heat=3, sound="DP machine-gun fire",
    loud=76, desc="Pan-fed light machine gun, 'the record player'.")
gun("maxim1910", "Maxim M1910", "hmg", "762r", 100, 42, 0.9, 85, ["ussr"], (1910, 1950),
    weight=23.0, modes=("auto",), burst=7, bcost=100, reload=460, heat=1, deploy=True,
    feed="belt", sound="Maxim gun fire", loud=80, desc="Water-cooled, wheeled, indestructible.")
gun("tt33", "TT-33 Tokarev", "pistol", "762t", 8, 19, 2.5, 12, ["ussr"], (1933, 1950),
    weight=0.9, hands=1, shot=50, reload=90, sound="a pistol shot", loud=60,
    desc="Soviet service pistol.")
gun("nagant1895", "Nagant M1895 revolver", "pistol", "762t", 7, 16, 2.7, 10, ["ussr"],
    (1895, 1950), weight=0.8, hands=1, shot=60, reload=200, feed="tube", freq=4,
    sound="a revolver shot", loud=55, desc="Gas-seal revolver. Painfully slow to reload.")
gun("ptrd", "PTRD-41", "at_rifle", "145", 1, 95, 0.6, 70, ["ussr"], (1941.8, 1950), weight=17.3,
    shot=100, reload=110, pen=35, deploy=True, feed="single",
    sound="the thunder of an anti-tank rifle", loud=88,
    desc="Single-shot 14.5mm anti-tank rifle. Still bites light armour.")
gun("ptrs", "PTRS-41", "at_rifle", "145", 5, 95, 0.65, 70, ["ussr"], (1942, 1950), weight=20.9,
    shot=100, reload=250, pen=34, deploy=True, freq=4, feed="clip",
    sound="the thunder of an anti-tank rifle", loud=88, desc="Semi-automatic 14.5mm AT rifle.")

# ---------------- Germany
gun("kar98k", "Karabiner 98k", "rifle", "792", 5, 43, 0.55, 62,
    ["germany", "romania", "hungary", "china"], (1935, 1950), weight=4.1, shot=130, reload=190,
    feed="stripper", bayonet=16, sound="the crack of a Kar98k",
    desc="Standard German bolt-action rifle.")
gun("kar98k_zf", "Kar98k with ZF39 scope", "sniper", "792", 5, 44, 0.18, 110, ["germany"],
    (1939, 1950), weight=4.9, shot=140, reload=230, scope=True, feed="stripper",
    sound="a sharp rifle crack", desc="Scoped Kar98k.")
gun("g43", "Gewehr 43", "rifle", "792", 10, 43, 0.75, 58, ["germany"], (1943.5, 1950),
    weight=4.4, shot=70, reload=150, jam=0.006, freq=2, sound="the crack of a G43",
    desc="Semi-automatic rifle with detachable magazine.")
gun("stg44", "StG 44", "assault", "792k", 30, 34, 1.25, 45, ["germany"], (1943.8, 1950),
    weight=5.2, modes=("single", "auto"), burst=4, shot=55, bcost=100, reload=170, jam=0.005,
    freq=4, sound="the rattle of an assault rifle", loud=68,
    desc="Sturmgewehr. Intermediate cartridge, select fire. A new kind of weapon.")
gun("mp40", "MP 40", "smg", "9mm", 32, 22, 2.2, 20, ["germany", "hungary", "romania"],
    (1940, 1950), weight=4.0, modes=("auto",), burst=5, bcost=100, reload=160, jam=0.003,
    sound="MP 40 fire", loud=62, desc="Machinenpistole 40. Slow, controllable, iconic.")
gun("mp38", "MP 38", "smg", "9mm", 32, 22, 2.2, 20, ["germany"], (1938, 1942), weight=4.2,
    modes=("auto",), burst=5, bcost=100, reload=160, jam=0.003, freq=4, sound="MP 38 fire",
    loud=62, desc="Earlier milled-steel MP.")
gun("mg34", "MG 34", "lmg", "792", 50, 43, 1.15, 75, ["germany"], (1936, 1950), weight=12.1,
    modes=("auto",), burst=7, bcost=100, reload=260, heat=3, feed="belt",
    sound="the rip of an MG 34", loud=80,
    desc="General purpose machine gun on a bipod. 50-round belt drum.")
gun("mg42", "MG 42", "lmg", "792", 50, 43, 1.35, 75, ["germany"], (1942.5, 1950), weight=11.6,
    modes=("auto",), burst=10, bcost=100, reload=260, heat=4, feed="belt",
    sound="the tearing buzz of an MG 42", loud=82,
    desc="1,200 rounds a minute. Sounds like canvas ripping. Barrels overheat fast.")
gun("mg42_tripod", "MG 42 (Lafette tripod)", "hmg", "792", 100, 43, 0.9, 90, ["germany"],
    (1942.5, 1950), weight=32.0, modes=("auto",), burst=10, bcost=100, reload=420, heat=3,
    deploy=True, feed="belt", sound="the tearing buzz of an MG 42", loud=82,
    desc="MG 42 on a Lafette tripod with optical sight.")
gun("mg34_tripod", "MG 34 (Lafette tripod)", "hmg", "792", 100, 43, 0.85, 90, ["germany"],
    (1936, 1950), weight=33.0, modes=("auto",), burst=8, bcost=100, reload=420, heat=2,
    deploy=True, feed="belt", sound="the rip of an MG 34", loud=80,
    desc="MG 34 on a sustained-fire tripod.")
gun("p38", "Walther P38", "pistol", "9mm", 8, 20, 2.5, 12, ["germany"], (1939, 1950),
    weight=0.9, hands=1, shot=50, reload=90, sound="a pistol shot", loud=60,
    desc="Double-action service pistol.")
gun("p08", "Luger P08", "pistol", "9mm", 8, 20, 2.4, 12, ["germany"], (1908, 1950), weight=0.9,
    hands=1, shot=50, reload=90, jam=0.005, sound="a pistol shot", loud=60,
    desc="The famous toggle-lock pistol. Every Allied soldier wants one.")
gun("pzb39", "Panzerbüchse 39", "at_rifle", "792ds", 1, 70, 0.6, 60, ["germany"], (1939, 1942),
    weight=12.4, shot=100, reload=110, pen=25, deploy=True, feed="single",
    sound="the bang of an anti-tank rifle", loud=84, desc="7.92mm anti-tank rifle.")
gun("fg42", "FG 42", "assault", "792", 20, 42, 1.4, 55, ["germany"], (1943, 1950), weight=4.9,
    modes=("single", "auto"), burst=4, shot=60, bcost=100, reload=160, jam=0.006, freq=1,
    sound="FG 42 fire", loud=74, desc="Fallschirmjäger rifle. Rare and prized.")

# ---------------- Italy
gun("carcano", "Carcano M91/38", "rifle", "65it", 6, 37, 0.65, 58, ["italy"], (1938, 1950),
    weight=3.4, shot=120, reload=160, feed="clip", bayonet=15,
    sound="the crack of a Carcano", desc="Italian bolt-action rifle, en-bloc clip.")
gun("mab38", "Beretta MAB 38", "smg", "9mm", 40, 23, 2.0, 22, ["italy", "romania"],
    (1938, 1950), weight=4.2, modes=("single", "auto"), burst=5, shot=50, bcost=100,
    reload=160, jam=0.002, freq=5, sound="SMG fire", loud=62,
    desc="Beautifully made and prized by friend and foe.")
gun("breda30", "Breda M30", "lmg", "65it", 20, 37, 1.3, 55, ["italy"], (1930, 1950),
    weight=10.6, modes=("auto",), burst=3, bcost=100, reload=260, jam=0.025, heat=3,
    feed="clip", sound="Breda gun fire", loud=74,
    desc="Fixed-magazine LMG loaded with stripper clips. Needs oiled rounds. Jams.")
gun("breda37", "Breda M37", "hmg", "8x56", 100, 43, 0.95, 85, ["italy"], (1937, 1950),
    weight=19.4, modes=("auto",), burst=6, bcost=100, reload=460, heat=2, deploy=True,
    feed="belt", sound="heavy machine-gun fire", loud=80,
    desc="Tripod MG fed by 20-round trays. Reliable if slow.")
gun("beretta34", "Beretta M1934", "pistol", "9glis", 7, 16, 2.6, 11, ["italy", "romania"],
    (1934, 1950), weight=0.7, hands=1, shot=50, reload=90, sound="a pistol shot", loud=56,
    desc="Compact .380 service pistol.")
gun("solothurn", "Solothurn S-18/1100", "at_rifle", "20mm", 10, 90, 0.7, 65,
    ["italy", "hungary"], (1936, 1943), weight=45.0, shot=120, reload=300, pen=28, deploy=True,
    freq=3, sound="the pounding of a 20mm rifle", loud=88, desc="Enormous 20mm anti-tank rifle.")

# ---------------- Japan
gun("type38", "Arisaka Type 38", "rifle", "65jp", 5, 37, 0.55, 60, ["japan"], (1905, 1950),
    weight=4.1, shot=125, reload=180, feed="stripper", bayonet=18,
    sound="the crack of an Arisaka", desc="Long, accurate, mild-recoiling 6.5mm rifle.")
gun("type99", "Arisaka Type 99", "rifle", "77jp", 5, 42, 0.6, 60, ["japan"], (1939, 1950),
    weight=3.8, shot=130, reload=190, feed="stripper", bayonet=18,
    sound="the crack of an Arisaka", desc="7.7mm successor to the Type 38.")
gun("type97_sniper", "Type 97 sniper rifle", "sniper", "65jp", 5, 38, 0.2, 105, ["japan"],
    (1937, 1950), weight=5.1, shot=130, reload=210, scope=True, feed="stripper",
    sound="a faint rifle crack", loud=58,
    desc="Scoped Type 38. Its low flash and report make the shooter hard to find.")
gun("type100", "Type 100 SMG", "smg", "8nambu", 30, 17, 2.5, 18, ["japan"], (1942, 1950),
    weight=3.9, modes=("auto",), burst=5, bcost=100, reload=170, jam=0.006, freq=2,
    sound="SMG fire", loud=60, desc="Rare Japanese SMG in weak 8mm Nambu.")
gun("type11", "Type 11 LMG", "lmg", "65jp", 30, 37, 1.4, 55, ["japan"], (1922, 1945),
    weight=10.2, modes=("auto",), burst=4, bcost=100, reload=250, jam=0.02, heat=3,
    feed="clip", sound="LMG fire", loud=74, desc="Hopper-fed LMG. Sand gets into everything.")
gun("type96", "Type 96 LMG", "lmg", "65jp", 30, 37, 1.2, 60, ["japan"], (1936, 1950),
    weight=9.0, modes=("auto",), burst=4, bcost=100, reload=190, jam=0.008, heat=3,
    sound="Nambu LMG fire", loud=74, desc="Top-fed LMG, often fitted with a bayonet.")
gun("type99_lmg", "Type 99 LMG", "lmg", "77jp", 30, 42, 1.2, 60, ["japan"], (1939, 1950),
    weight=10.4, modes=("auto",), burst=4, bcost=100, reload=190, jam=0.006, heat=3,
    sound="Nambu LMG fire", loud=75, desc="7.7mm development of the Type 96.")
gun("type92", "Type 92 HMG", "hmg", "77jp", 30, 42, 0.9, 85, ["japan"], (1932, 1950),
    weight=55.0, modes=("auto",), burst=5, bcost=100, reload=200, heat=2, deploy=True,
    feed="clip", sound="the slow knock of a Type 92 'woodpecker'", loud=78,
    desc="Heavy strip-fed machine gun. Its slow rate earned the name 'woodpecker'.")
gun("nambu14", "Nambu Type 14", "pistol", "8nambu", 8, 15, 2.8, 10, ["japan"], (1925, 1950),
    weight=0.9, hands=1, shot=55, reload=100, jam=0.01, sound="a pistol shot", loud=55,
    desc="Officer's pistol. Weak cartridge.")
gun("type97_at", "Type 97 AT rifle", "at_rifle", "20mm", 7, 90, 0.7, 65, ["japan"],
    (1938, 1945), weight=59.0, shot=120, reload=300, pen=30, deploy=True, freq=3,
    sound="the pounding of a 20mm rifle", loud=88, desc="20mm semi-auto anti-tank rifle.")

# ---------------- France (1940)
gun("mas36", "MAS-36", "rifle", "75fr", 5, 41, 0.6, 58, ["france"], (1936, 1950), weight=3.7,
    shot=125, reload=180, feed="stripper", bayonet=16, sound="rifle fire",
    desc="Modern French bolt-action rifle.")
gun("lebel", "Lebel M1886/93", "rifle", "8lebel", 8, 42, 0.6, 58, ["france"], (1893, 1945),
    weight=4.4, shot=130, reload=320, feed="tube", bayonet=18, sound="rifle fire",
    desc="Tube-magazine veteran of the Great War. Very slow to reload.")
gun("mas38", "MAS-38", "smg", "765l", 32, 15, 2.3, 18, ["france"], (1939, 1950), weight=2.9,
    modes=("auto",), burst=5, bcost=100, reload=160, freq=2, sound="SMG fire", loud=58,
    desc="Compact SMG in an underpowered cartridge.")
gun("fm2429", "FM 24/29", "lmg", "75fr", 25, 41, 1.1, 60, ["france"], (1929, 1950), weight=9.8,
    modes=("single", "auto"), burst=4, shot=60, bcost=100, reload=180, heat=3,
    sound="LMG fire", loud=75, desc="Good, reliable French light machine gun.")
gun("hotchkiss1914", "Hotchkiss M1914", "hmg", "8lebel", 100, 42, 0.9, 85, ["france"],
    (1914, 1950), weight=24.0, modes=("auto",), burst=6, bcost=100, reload=420, heat=2,
    deploy=True, feed="clip", sound="Hotchkiss gun fire", loud=80,
    desc="Strip-fed heavy machine gun from the Great War.")
gun("mas1935", "MAS 1935A", "pistol", "765l", 8, 14, 2.5, 11, ["france"], (1935, 1950),
    weight=0.7, hands=1, shot=50, reload=90, sound="a pistol shot", loud=55,
    desc="French service pistol.")

# ---------------- Poland (1939)
gun("wz29", "Karabinek wz. 29", "rifle", "792", 5, 43, 0.6, 60, ["poland"], (1929, 1950),
    weight=4.0, shot=130, reload=190, feed="stripper", bayonet=16, sound="rifle fire",
    desc="Polish Mauser carbine.")
gun("wz28", "rkm wz. 28", "lmg", "792", 20, 43, 1.25, 55, ["poland"], (1928, 1950), weight=9.5,
    modes=("auto",), burst=4, bcost=100, reload=190, heat=3, sound="the pounding of a wz. 28",
    loud=75, desc="Polish licence-built BAR.")
gun("ckm_wz30", "ckm wz. 30", "hmg", "792", 100, 43, 0.9, 85, ["poland"], (1930, 1950),
    weight=21.0, modes=("auto",), burst=7, bcost=100, reload=420, heat=2, deploy=True,
    feed="belt", sound="machine-gun fire", loud=80, desc="Polish Browning M1917 derivative.")
gun("vis", "Vis wz. 35", "pistol", "9mm", 8, 20, 2.3, 12, ["poland"], (1935, 1950), weight=1.0,
    hands=1, shot=50, reload=90, sound="a pistol shot", loud=60,
    desc="One of the finest pistols of the war.")
gun("ur_wz35", "Karabin ppanc. wz. 35 'Ur'", "at_rifle", "792ds", 4, 70, 0.6, 60, ["poland"],
    (1935, 1941), weight=9.5, shot=120, reload=180, pen=30, deploy=True,
    sound="the sharp bang of an anti-tank rifle", loud=84,
    desc="Secret anti-tank rifle, crated as 'surveying equipment' until the war began.")

# ---------------- China
gun("hanyang88", "Hanyang 88", "rifle", "792", 5, 42, 0.8, 55, ["china"], (1904, 1950),
    weight=4.1, shot=140, reload=210, feed="clip", bayonet=16, jam=0.004,
    sound="rifle fire", desc="Chinese-made Gewehr 88. Old, worn, everywhere.")
gun("chiang", "Zhongzheng Type 24", "rifle", "792", 5, 43, 0.6, 60, ["china"], (1935, 1950),
    weight=4.1, shot=130, reload=190, feed="stripper", bayonet=16, sound="rifle fire",
    desc="The 'Chiang Kai-shek rifle', a Mauser Standardmodell copy.")
gun("zb26", "ZB vz. 26", "lmg", "792", 20, 43, 1.1, 60, ["china", "romania"], (1926, 1950),
    weight=9.6, modes=("auto",), burst=4, bcost=100, reload=170, heat=3, jam=0.001,
    sound="ZB machine-gun fire", loud=75, desc="Czech LMG. Legendary reliability.")
gun("c96", "Mauser C96 'Broomhandle'", "pistol", "763m", 10, 18, 2.6, 16, ["china"],
    (1896, 1950), weight=1.3, hands=1, modes=("single", "auto"), burst=4, shot=50, bcost=100,
    reload=150, feed="stripper", sound="the rattle of a machine pistol", loud=62,
    desc="Select-fire 'box cannon' with stripper clips.")
gun("type24_maxim", "Type 24 Maxim", "hmg", "792", 100, 43, 0.9, 85, ["china"], (1935, 1950),
    weight=40.0, modes=("auto",), burst=7, bcost=100, reload=460, heat=1, deploy=True,
    feed="belt", sound="Maxim gun fire", loud=80, desc="Chinese-built MG 08.")

# ---------------- Finland
gun("m39", "Mosin-Nagant M/39", "rifle", "762r", 5, 43, 0.45, 65, ["finland"], (1939, 1950),
    weight=4.3, shot=125, reload=190, feed="stripper", bayonet=16,
    sound="the crack of a Mosin", desc="Finnish-refined Mosin. Superb accuracy.")
gun("suomi", "Suomi KP/-31", "smg", "9mm", 50, 22, 1.8, 24, ["finland"], (1931, 1950),
    weight=6.2, modes=("auto",), burst=6, bcost=100, reload=200, jam=0.002,
    sound="Suomi SMG fire", loud=63, desc="Heavy, accurate, 50-round 'coffin' magazine.")
gun("lahti_saloranta", "Lahti-Saloranta M/26", "lmg", "762r", 20, 42, 1.2, 60, ["finland"],
    (1926, 1950), weight=9.3, modes=("single", "auto"), burst=4, shot=60, bcost=100,
    reload=190, jam=0.015, heat=3, sound="LMG fire", loud=75,
    desc="Accurate but finicky Finnish LMG. Captured DPs are preferred.")
gun("maxim_m32", "Maxim M/32-33", "hmg", "762r", 100, 42, 0.85, 85, ["finland"], (1932, 1950),
    weight=24.0, modes=("auto",), burst=7, bcost=100, reload=440, heat=1, deploy=True,
    feed="belt", sound="Maxim gun fire", loud=80, desc="Finnish-improved Maxim.")
gun("lahti_l35", "Lahti L-35", "pistol", "9mm", 8, 20, 2.3, 12, ["finland"], (1935, 1950),
    weight=1.2, hands=1, shot=50, reload=90, sound="a pistol shot", loud=60,
    desc="Robust pistol built for arctic cold.")
gun("lahti_l39", "Lahti L-39 'Norsupyssy'", "at_rifle", "20mm", 10, 90, 0.6, 65, ["finland"],
    (1940, 1950), weight=49.0, shot=110, reload=280, pen=30, deploy=True, freq=4,
    sound="the pounding of a 20mm rifle", loud=88, desc="The 'elephant gun'. 20mm semi-auto.")

# ---------------- Hungary / Romania
gun("35m", "Mannlicher 35M", "rifle", "8x56", 5, 43, 0.6, 58, ["hungary"], (1935, 1950),
    weight=4.0, shot=120, reload=170, feed="clip", bayonet=16, sound="rifle fire",
    desc="Hungarian clip-fed rifle.")
gun("kiraly", "39M Király", "smg", "9x25", 40, 25, 1.8, 26, ["hungary"], (1941, 1950),
    weight=3.7, modes=("single", "auto"), burst=5, shot=50, bcost=100, reload=170,
    sound="SMG fire", loud=65, desc="Long-barrelled SMG in the potent 9mm Mauser Export.")
gun("solothurn31m", "31M Solothurn", "lmg", "8x56", 25, 43, 1.2, 60, ["hungary"], (1931, 1950),
    weight=10.0, modes=("auto",), burst=4, bcost=100, reload=190, heat=3, sound="LMG fire",
    loud=75, desc="Swiss-designed light machine gun.")
gun("schwarzlose", "07/31M Schwarzlose", "hmg", "8x56", 100, 43, 0.95, 80, ["hungary"],
    (1907, 1950), weight=41.0, modes=("auto",), burst=6, bcost=100, reload=440, heat=2,
    deploy=True, feed="belt", sound="heavy machine-gun fire", loud=80,
    desc="Old Austro-Hungarian delayed-blowback MG.")
gun("frommer37m", "37M Frommer", "pistol", "9glis", 7, 16, 2.5, 11, ["hungary"], (1937, 1950),
    weight=0.8, hands=1, shot=50, reload=90, sound="a pistol shot", loud=56,
    desc="Hungarian service pistol.")
gun("vz24", "ZB vz. 24", "rifle", "792", 5, 43, 0.6, 60, ["romania", "china"], (1924, 1950),
    weight=4.2, shot=130, reload=190, feed="stripper", bayonet=16, sound="rifle fire",
    desc="Czech Mauser, the standard Romanian rifle.")
gun("orita", "Orița M1941", "smg", "9mm", 32, 22, 2.0, 22, ["romania"], (1942, 1950),
    weight=3.5, modes=("single", "auto"), burst=5, shot=50, bcost=100, reload=160, freq=6,
    sound="SMG fire", loud=62, desc="Romanian SMG with a long barrel and good sights.")

# ================================================================= launchers / flamers / mortars

def launcher(id, name, cat, pen, blast, rng, nations, years, *, cal=None, weight=6.0,
             reload=250, disp=1.6, min_rng=3, backblast=True, freq=10, blast_r=1,
             frags=6, sound="the whoosh of a rocket", desc="", shot=150):
    return _reg(ItemType(
        id, name, kind="gun", cat=cat, cal=cal, mag=1, pen=pen, blast=blast, blast_r=blast_r,
        frags=frags, frag_dmg=18, rng=rng, disp=disp, nations=tuple(nations), years=years,
        weight=weight, reload_cost=reload, shot_cost=shot, min_rng=min_rng, backblast=backblast,
        freq=freq, sound=sound, loud=80, feed="single", glyph="(", color=(120, 140, 90),
        dmg=60, desc=desc, volume=weight,
    ))


launcher("bazooka", "M1A1 Bazooka", "at_launcher", 100, 45, 32, ["usa", "uk", "china", "france"],
         (1942.9, 1950), cal="rkt_bazooka", weight=6.8, reload=260,
         desc="2.36-inch rocket launcher. Needs a loader for speed. Mind the backblast.")
launcher("panzerschreck", "RPzB 54 Panzerschreck", "at_launcher", 200, 70, 30, ["germany", "hungary"],
         (1943.9, 1950), cal="rkt_schreck", weight=11.0, reload=280,
         desc="The 'stovepipe'. 88mm rocket that kills any tank it hits.")
launcher("piat", "PIAT", "at_launcher", 100, 55, 22, ["uk", "australia", "india"],
         (1943, 1950), cal="piat", weight=14.5, reload=320, backblast=False, disp=1.9,
         sound="the thunk of a PIAT", desc="Spring-loaded spigot launcher. Cocking it is agony.")
launcher("pzf30k", "Panzerfaust 30 klein", "at_disposable", 140, 55, 14, ["germany"],
         (1943.6, 1944.8), weight=3.2, disp=2.2, min_rng=2,
         desc="Single-shot disposable anti-tank weapon. Short range.")
launcher("pzf60", "Panzerfaust 60", "at_disposable", 200, 65, 24, ["germany", "hungary"],
         (1944.6, 1950), weight=6.1, disp=2.0, min_rng=2,
         desc="Single-shot disposable. 'Achtung! Feuerstrahl!' printed on the tube.")
launcher("pzf100", "Panzerfaust 100", "at_disposable", 200, 65, 34, ["germany"],
         (1944.9, 1950), weight=6.8, disp=1.9, min_rng=2, desc="Longer-ranged Panzerfaust.")

_reg(ItemType("m2_flamer", "M2-2 flamethrower", kind="gun", cat="flamer", cal="fuel", mag=10,
              dmg=30, rng=8, disp=4.0, nations=("usa",), years=(1943.5, 1950), weight=31.0,
              volume=30, reload_cost=900, shot_cost=100, sound="the roar of a flamethrower",
              loud=60, glyph="(", color=(200, 120, 60), fire=3, feed="tank",
              desc="Napalm-thickened fuel. The tanks on your back are a target."))
_reg(ItemType("flammenwerfer41", "Flammenwerfer 41", kind="gun", cat="flamer", cal="fuel", mag=8,
              dmg=30, rng=7, disp=4.0, nations=("germany",), years=(1941, 1950), weight=22.0,
              volume=24, reload_cost=900, shot_cost=100, sound="the roar of a flamethrower",
              loud=60, glyph="(", color=(200, 120, 60), fire=3, feed="tank",
              desc="German man-portable flamethrower."))
_reg(ItemType("roks2", "ROKS-2 flamethrower", kind="gun", cat="flamer", cal="fuel", mag=8,
              dmg=30, rng=7, disp=4.0, nations=("ussr",), years=(1940, 1950), weight=23.0,
              volume=24, reload_cost=900, shot_cost=100, sound="the roar of a flamethrower",
              loud=60, glyph="(", color=(200, 120, 60), fire=3, feed="tank",
              desc="Soviet flamethrower disguised as a rifle and pack."))
_reg(ItemType("type93_flamer", "Type 93 flamethrower", kind="gun", cat="flamer", cal="fuel",
              mag=8, dmg=30, rng=7, disp=4.0, nations=("japan",), years=(1933, 1950),
              weight=25.0, volume=24, reload_cost=900, shot_cost=100,
              sound="the roar of a flamethrower", loud=60, glyph="(", color=(200, 120, 60),
              fire=3, feed="tank", desc="Japanese flamethrower."))
_reg(ItemType("lanciafiamme", "Lanciafiamme M35", kind="gun", cat="flamer", cal="fuel", mag=7,
              dmg=28, rng=6, disp=4.0, nations=("italy",), years=(1935, 1950), weight=27.0,
              volume=24, reload_cost=900, shot_cost=100, sound="the roar of a flamethrower",
              loud=60, glyph="(", color=(200, 120, 60), fire=3, feed="tank",
              desc="Italian flamethrower."))


def mortar(id, name, cal, power, radius, frags, rng, nations, years, *, weight=12.0, min_rng=8,
           freq=10, desc="", disp=4.0):
    return _reg(ItemType(
        id, name, kind="gun", cat="mortar", cal=cal, mag=1, blast=power, blast_r=radius,
        frags=frags, frag_dmg=22, rng=rng, min_rng=min_rng, nations=tuple(nations),
        years=years, weight=weight, volume=weight, reload_cost=120, shot_cost=200, disp=disp,
        sound="the hollow cough of a mortar", loud=70, feed="single", glyph="(",
        color=(110, 120, 90), freq=freq, desc=desc,
    ))


mortar("m2_mortar", "M2 60mm mortar", "m60", 85, 3, 34, 90, ["usa", "china", "france"],
       (1940, 1950), weight=19.0, desc="Company mortar. Indirect fire at anything you can see.")
mortar("2in_mortar", "Ordnance ML 2-inch mortar", "m50", 70, 3, 26, 70,
       ["uk", "australia", "india"], (1938, 1950), weight=4.8, min_rng=6,
       desc="Platoon mortar. Light, short-ranged; lobs HE or smoke.")
mortar("50rm38", "50-RM 38", "m50", 65, 3, 26, 40, ["ussr"], (1938, 1943), weight=12.0,
       min_rng=6, desc="Soviet company mortar.")
mortar("legrw36", "5 cm leGrW 36", "m50", 60, 2, 22, 45, ["germany"], (1936, 1943),
       weight=14.0, min_rng=6, desc="Over-engineered light mortar.")
mortar("type89", "Type 89 grenade discharger", "knee", 55, 2, 22, 45, ["japan"], (1929, 1950),
       weight=4.7, min_rng=5, disp=5.0,
       desc="The 'knee mortar'. Fire it braced on the ground - never on your thigh.")
mortar("brixia", "Brixia M35", "m45", 40, 2, 14, 40, ["italy"], (1935, 1950), weight=15.5,
       min_rng=5, desc="Complicated, tiny 45mm mortar.")
mortar("wz36", "granatnik wz. 36", "m46", 50, 2, 18, 40, ["poland"], (1936, 1950), weight=8.0,
       min_rng=5, desc="Polish 46mm light mortar.")
# the battalion mortars: heavier, longer-ranged - and, once the light ones were given up, the only ones
mortar("grw34", "8 cm GrW 34", "m81", 110, 4, 44, 120, ["germany", "hungary", "romania", "finland"], (1934, 1950),
       weight=19.0, min_rng=10, freq=6, desc="The German battalion mortar. The tube alone is 18 kg; "
       "the baseplate and bipod go on two other men's backs.")
mortar("82bm37", "82-BM-37", "m81", 105, 4, 42, 110, ["ussr", "china"], (1937, 1950), weight=19.0, min_rng=10,
       freq=6, desc="Soviet 82mm battalion mortar. After 1943 it did the company mortar's job too.")
mortar("m1_81mm", "M1 81mm mortar", "m81", 110, 4, 44, 120, ["usa", "france", "china"], (1940, 1950),
       weight=20.0, min_rng=10, freq=3, desc="The battalion's heavy mortar.")
mortar("3in_mortar", "Ordnance SBML 3-inch mortar", "m81", 105, 4, 42, 110,
       ["uk", "canada", "australia", "newzealand", "india", "poland"], (1936, 1950), weight=20.0, min_rng=10,
       freq=4, desc="British battalion mortar.")
mortar("type97_81", "Type 97 81mm mortar", "m81", 105, 4, 42, 110, ["japan"], (1937, 1950), weight=21.0,
       min_rng=10, freq=2, desc="Japanese infantry mortar.")
mortar("brandt27", "Mortier Brandt 81 mm Mle 27/31", "m81", 105, 4, 42, 110, ["france", "poland", "china"],
       (1931, 1950), weight=20.0, min_rng=10, freq=5, desc="The French design half the world's 81mm mortars came from.")
mortar("m81_14", "Mortaio da 81/14 M35", "m81", 105, 4, 42, 110, ["italy"], (1935, 1950), weight=20.0,
       min_rng=10, freq=4, desc="Italian 81mm mortar.")

# ================================================================= grenades & explosives

def grenade(id, name, gtype, nations, years, *, fuse=4, power=55, radius=3, frags=24,
            frag_dmg=20, dud=0.02, throw=0, weight=0.6, pen=0, smoke=0, fire=0, freq=10,
            desc="", color=(150, 160, 110)):
    return _reg(ItemType(
        id, name, kind="grenade", gtype=gtype, nations=tuple(nations), years=years, fuse=fuse,
        blast=power, blast_r=radius, frags=frags, frag_dmg=frag_dmg, dud=dud, throw=throw,
        weight=weight, volume=0.3, pen=pen, smoke=smoke, fire=fire, freq=freq, glyph="*",
        color=color, desc=desc, stack=1,
    ))


grenade("mk2", "Mk 2 fragmentation grenade", "frag", ["usa", "china", "france"], (1918, 1950),
        fuse=4, power=55, radius=3, frags=28, desc="The 'pineapple'. Pull pin, release spoon.")
grenade("m15_wp", "M15 white phosphorus grenade", "wp", ["usa"], (1943, 1950), fuse=4,
        power=25, radius=2, frags=6, smoke=40, fire=2, weight=0.9, freq=3,
        desc="'Willie Pete'. Burning phosphorus and a thick white cloud.", color=(220, 220, 220))
grenade("m18_smoke", "M18 smoke grenade", "smoke", ["usa"], (1943, 1950), fuse=2, power=0,
        radius=0, frags=0, smoke=50, weight=0.5, freq=4, desc="Coloured smoke canister.",
        color=(150, 200, 150))
grenade("mills", "No. 36 Mills bomb", "frag", ["uk", "australia", "india"], (1915, 1950), fuse=4,
        power=55, radius=3, frags=30, desc="Segmented British fragmentation grenade.")
grenade("no77", "No. 77 WP grenade", "wp", ["uk"], (1943, 1950), fuse=3, power=20, radius=2,
        frags=4, smoke=40, fire=2, freq=3, desc="Phosphorus smoke grenade.",
        color=(220, 220, 220))
grenade("gammon", "No. 82 Gammon bomb", "gammon", ["uk"], (1943, 1950), fuse=1, power=110,
        radius=3, frags=10, pen=25, weight=1.0, freq=2,
        desc="A cloth bag of plastic explosive. Detonates on impact.")
grenade("rgd33", "RGD-33 stick grenade", "stick", ["ussr"], (1933, 1950), fuse=4, power=50,
        radius=3, frags=22, throw=2, desc="Soviet stick grenade. Awkward to arm.")
grenade("f1", "F-1 'limonka'", "frag", ["ussr"], (1939, 1950), fuse=4, power=50, radius=3,
        frags=40, frag_dmg=18, desc="Defensive grenade. Fragments fly much further than you can throw.")
grenade("rg42", "RG-42", "frag", ["ussr"], (1942, 1950), fuse=4, power=55, radius=3, frags=26,
        desc="Cheap tin-can grenade.")
grenade("rpg43", "RPG-43 AT grenade", "at", ["ussr"], (1943, 1950), fuse=1, power=80, radius=2,
        frags=6, pen=75, weight=1.2, throw=-3, freq=3,
        desc="Shaped-charge anti-tank grenade with a drogue.")
grenade("molotov", "Molotov cocktail", "molotov", ["ussr", "finland", "poland", "china", "japan"],
        (1939, 1950), fuse=1, power=0, radius=2, frags=0, fire=3, weight=0.8, freq=4,
        desc="A bottle of fuel with a rag. Named by the Finns for Molotov.",
        color=(200, 140, 70))
grenade("stielhandgranate", "Stielhandgranate 24", "stick", ["germany", "hungary", "romania", "china"],
        (1924, 1950), fuse=5, power=65, radius=3, frags=12, throw=3,
        desc="The 'potato masher'. Blast grenade; throws far. Unscrew the cap, pull the cord.")
grenade("eihandgranate", "Eihandgranate 39", "frag", ["germany"], (1939, 1950), fuse=4,
        power=45, radius=3, frags=18, desc="Small egg grenade.")
grenade("nebel39", "Nebelhandgranate 39", "smoke", ["germany"], (1939, 1950), fuse=3, power=0,
        radius=0, frags=0, smoke=45, throw=3, freq=3, desc="Smoke stick grenade.",
        color=(150, 150, 150))
grenade("srcm35", "SRCM Mod. 35", "frag", ["italy"], (1935, 1950), fuse=1, power=35, radius=2,
        frags=10, frag_dmg=15, dud=0.12, weight=0.2,
        desc="The 'red devil'. Impact-fused, weak, and dangerous to pick up if it didn't go off.",
        color=(200, 60, 60))
grenade("type97", "Type 97 grenade", "frag", ["japan"], (1937, 1950), fuse=5, power=50,
        radius=3, frags=24, dud=0.15,
        desc="Strike the fuse on your helmet, then throw. Fuse times are erratic.")
grenade("type99_gr", "Type 99 grenade", "frag", ["japan"], (1939, 1950), fuse=5, power=45,
        radius=3, frags=20, dud=0.12, desc="Smaller Japanese grenade.")
grenade("f1_fr", "F1 grenade (French)", "frag", ["france"], (1915, 1950), fuse=4, power=50,
        radius=3, frags=26, dud=0.05, desc="French defensive grenade.")
grenade("wz33", "granat wz. 33", "frag", ["poland"], (1933, 1950), fuse=4, power=50, radius=3,
        frags=26, desc="Polish defensive grenade.")
grenade("m32_fin", "Model 32 stick grenade", "stick", ["finland"], (1932, 1950), fuse=5,
        power=55, radius=3, frags=14, throw=2, desc="Finnish stick grenade.")
grenade("36m", "36M grenade", "frag", ["hungary", "romania"], (1936, 1950), fuse=4, power=45,
        radius=3, frags=18, desc="Hungarian egg grenade.")
grenade("chinese_stick", "Chinese stick grenade", "stick", ["china"], (1930, 1950), fuse=5,
        power=45, radius=3, frags=10, throw=2, dud=0.1,
        desc="Locally made stick grenade. Quality varies.")


def explosive(id, name, charge, nations, years, *, fuse=10, power=250, radius=4, frags=12,
              pen=0, weight=5.0, freq=10, desc=""):
    return _reg(ItemType(
        id, name, kind="explosive", charge=charge, nations=tuple(nations), years=years,
        fuse=fuse, blast=power, blast_r=radius, frags=frags, frag_dmg=25, pen=pen, weight=weight,
        volume=weight * 0.8, freq=freq, glyph="*", color=(210, 170, 90), desc=desc,
    ))


_ALL = ["usa", "uk", "ussr", "germany", "italy", "japan", "france", "poland", "china", "finland",
        "hungary", "romania", "australia", "india"]
explosive("satchel", "satchel charge", "satchel", _ALL, (1930, 1950), fuse=10, power=320,
          radius=4, frags=8, pen=60, weight=6.0,
          desc="Several kilos of TNT with a pull-igniter. Place it and run.")
explosive("geballte", "Geballte Ladung", "bundle", ["germany"], (1939, 1950), fuse=5, power=200,
          radius=3, frags=14, pen=40, weight=3.5, freq=5,
          desc="Six grenade heads wired around a seventh. Thrown onto engine decks.")
explosive("haft_hl", "Hafthohlladung 3", "magnetic", ["germany"], (1942.9, 1944.6), fuse=5,
          power=90, radius=2, frags=4, pen=140, weight=3.0, freq=3,
          desc="Magnetic hollow charge. Walk up to the tank and slap it on.")
explosive("type99_mine", "Type 99 magnetic mine", "magnetic", ["japan"], (1939, 1950), fuse=6,
          power=90, radius=2, frags=6, pen=40, weight=1.3, freq=4,
          desc="Hakobakurai. Clamped to a tank by hand.")
explosive("bangalore", "Bangalore torpedo", "bangalore", ["usa", "uk", "india", "australia"],
          (1914, 1950), fuse=8, power=140, radius=2, frags=10, weight=13.0, freq=4,
          desc="A pipe of explosive for blowing gaps in wire.")
explosive("sticky", "No. 74 'sticky bomb'", "magnetic", ["uk", "australia"], (1940, 1943),
          fuse=5, power=80, radius=2, frags=4, pen=50, weight=1.0, freq=3,
          desc="A glass sphere of nitroglycerine coated in glue. Unpopular.")

# ================================================================= melee

def melee(id, name, dmg, nations, years=(1900, 1950), *, cost=100, weight=0.5, hands=1,
          freq=10, desc="", tool=""):
    return _reg(ItemType(
        id, name, kind="melee", dmg=dmg, nations=tuple(nations), years=years, cost=cost,
        weight=weight, volume=weight, hands=hands, freq=freq, glyph="/", color=(180, 180, 180),
        desc=desc, tool=tool,
    ))


melee("bayonet", "bayonet", 16, _ALL + ["canada", "newzealand"],
      desc="A blade for the end of your rifle, or your hand.")
melee("trench_knife", "M3 trench knife", 15, ["usa"], (1943, 1950), weight=0.3)
melee("fs_knife", "Fairbairn-Sykes knife", 15, ["uk"], (1941, 1950), weight=0.3, freq=3)
melee("kukri", "kukri", 26, ["india"], weight=0.7, desc="The Gurkha's heavy curved knife.")
melee("katana", "shin-guntō", 38, ["japan"], weight=1.3, hands=2, freq=0,
      desc="An officer's sword, often a family blade in a military mounting.")
melee("dadao", "dadao", 32, ["china"], weight=1.8, hands=2, freq=2,
      desc="A heavy broadsword carried by the 'Big Sword' units.")
melee("szabla", "szabla wz. 34", 28, ["poland"], weight=1.4, freq=0,
      desc="Polish cavalry sabre.")
melee("puukko", "puukko", 14, ["finland"], weight=0.2, desc="Finnish belt knife.")
melee("shovel", "entrenching tool", 18, _ALL + ["canada", "newzealand"], weight=1.2,
      tool="shovel", desc="For digging foxholes, and sharpened for everything else.")

# ================================================================= gear

def gear(id, name, kind, *, weight=0.2, volume=0.2, glyph=";", color=(170, 170, 150), desc="",
         **kw):
    return _reg(ItemType(id, name, kind=kind, weight=weight, volume=volume, glyph=glyph,
                         color=color, desc=desc, **kw))


# medical
gear("bandage", "field dressing", "medical", med="bandage", power=1, weight=0.1, volume=0.1,
     glyph="+", color=(230, 230, 230), desc="A compress bandage. Stops bleeding on one wound.")
gear("morphine", "morphine syrette", "medical", med="morphine", power=60, weight=0.05,
     volume=0.05, glyph="+", color=(200, 200, 250),
     desc="Squeeze into a muscle. Kills pain. Too many will kill you.")
gear("tourniquet", "tourniquet", "medical", med="tourniquet", power=1, weight=0.1, volume=0.1,
     glyph="+", color=(220, 150, 150), desc="Stops all bleeding in a limb. Costs the limb eventually.")
gear("sulfa", "sulfanilamide powder", "medical", med="sulfa", power=1, weight=0.05, volume=0.05,
     glyph="+", color=(240, 240, 200), desc="Sprinkle on wounds. Slows bleeding a little.")
gear("medkit", "medic's bag", "medical", med="kit", power=8, uses=8, weight=3.0, volume=4.0,
     glyph="+", color=(250, 250, 250),
     desc="Dressings, splints, morphine and plasma. Treats several casualties.")
gear("surgical_kit", "surgical instruments", "medical", med="surgery", power=1, uses=12, weight=4.0, volume=4.0,
     glyph="+", color=(220, 220, 235), size=(2, 2),
     desc="Scalpels, clamps, retractors, sutures, ether. An aid station in a canvas roll.")
gear("plasma", "blood plasma kit", "medical", med="plasma", power=1200, weight=0.8, volume=1.0,
     glyph="+", color=(230, 200, 150), desc="Dried plasma. Restores lost blood volume.")
# tools & navigation
gear("wirecutters", "wire cutters", "tool", tool="wirecutters", weight=0.7, volume=0.4,
     desc="Cut a path through barbed wire.")
gear("binoculars", "binoculars", "tool", tool="binoculars", weight=0.9, volume=0.8,
     desc="Look further and identify what you're looking at.")
gear("radio_scr300", "SCR-300 radio", "tool", tool="radio", weight=17.0, volume=15,
     glyph="&", desc="Backpack radio. Talk to battalion and the guns.")
gear("radio", "field radio", "tool", tool="radio", weight=14.0, volume=14, glyph="&",
     desc="A heavy field radio set. Your link to the artillery.")
gear("scr536", "SCR-536 'handie-talkie'", "tool", tool="handradio", weight=2.3, volume=1.5, size=(1, 2),
     glyph="&", desc="A handheld radio. A mile on a good day. Platoon to company - not to the guns.")
gear("ws38", "Wireless Set No. 38", "tool", tool="handradio", weight=9.5, volume=6, size=(2, 2), glyph="&",
     desc="A platoon man-pack set. Temperamental, but better than shouting.")
gear("feldfu", "Feldfunksprecher", "tool", tool="handradio", weight=5.5, volume=4, size=(2, 2), glyph="&",
     desc="A small infantry radio for company nets.")
gear("flaregun", "flare pistol", "tool", tool="flaregun", weight=1.0, volume=0.6, uses=4,
     desc="Fires illumination flares.")
gear("compass", "compass", "tool", tool="compass", weight=0.1, volume=0.05,
     desc="Tells you which way is north.")
gear("watch", "wristwatch", "tool", tool="watch", weight=0.05, volume=0.02,
     desc="Tells you the time.")
gear("map", "sector map", "tool", tool="map", weight=0.05, volume=0.05, glyph="?",
     color=(225, 215, 180),
     desc="A folded map of the sector with the front marked in grease pencil.")
gear("orders", "written orders", "tool", tool="orders", weight=0.01, volume=0.01, glyph="?",
     color=(225, 215, 180), desc="Your orders, scribbled in pencil.")
# enemy papers, by the rank of the man who carried them
# shipboard gear (shipboard.py)
gear("ammo_load", "load of ready ammunition", "tool", tool="ammo_load", weight=18.0, volume=8.0, size=(2, 2),
     glyph="■", color=(200, 180, 90), desc="Magazines or clips for a mount, in a canvas carrier. Heavy.")
gear("fire_hose", "fire hose", "tool", tool="hose", weight=9.0, volume=6.0, size=(2, 2), glyph="~",
     color=(220, 80, 70), desc="A charged hose and an all-purpose nozzle: fog, jet or foam.")
gear("shoring", "shoring timber", "tool", tool="shoring", weight=14.0, volume=8.0, size=(1, 3), glyph="/",
     color=(180, 140, 90), desc="Four-by-four timbers, wedges and a maul.")
gear("life_ring_item", "life ring", "tool", tool="life_ring", weight=2.5, volume=4.0, size=(2, 2), glyph="o",
     color=(240, 150, 60), desc="Cork and canvas, and a line.")
gear("paybook", "paybook", "tool", tool="document", weight=0.05, volume=0.05, glyph="?", color=(200, 190, 150),
     desc="A soldier's pay book: name, unit, next of kin. Intelligence wants these.")
gear("notebook", "NCO's notebook", "tool", tool="document", weight=0.05, volume=0.05, glyph="?", color=(200, 190, 150),
     desc="Names, rations, positions sketched in pencil.")
gear("field_orders", "field orders", "tool", tool="document", weight=0.05, volume=0.05, glyph="?",
     color=(230, 210, 160), desc="An officer's orders for the day: objectives, times, fire plans.")
gear("marked_map", "marked map", "tool", tool="document", weight=0.2, volume=0.2, glyph="?", color=(230, 210, 160),
     desc="A map with the enemy's own positions and boundaries in grease pencil.")
gear("op_orders", "operation orders", "tool", tool="document", weight=0.2, volume=0.2, glyph="?",
     color=(250, 220, 150), desc="A battalion's plan of attack, in full. Worth a man's life to get back.")
gear("whistle", "whistle", "tool", tool="whistle", weight=0.02, volume=0.01,
     desc="Blow it to signal your squad to advance.")
gear("wire_spool", "barbed wire coil", "tool", tool="wire", weight=8.0, volume=6.0,
     desc="Unroll to string an obstacle.")
gear("sandbags", "empty sandbags", "tool", tool="sandbags", weight=1.0, volume=1.0, uses=6,
     desc="Fill and stack for cover.")
gear("mine_detector", "mine detector", "tool", tool="detector", weight=8.0, volume=6.0,
     desc="SCR-625 style detector. Slowly sweeps for mines.")
# personal / flavour
gear("canteen", "canteen", "tool", tool="canteen", weight=1.0, volume=1.0, uses=6,
     desc="Water. A sip steadies the nerves.")
gear("cigarettes", "pack of cigarettes", "tool", tool="cigarettes", weight=0.03, volume=0.03,
     uses=20, desc="Smoke one to calm down. Currency for everything.")
gear("flask", "hip flask", "tool", tool="flask", weight=0.3, volume=0.2, uses=4,
     desc="Dulls pain and fear. Also your aim.")
gear("ration", "field ration", "tool", tool="ration", weight=0.5, volume=0.5, desc="Food.")
gear("letter", "letter from home", "tool", tool="letter", weight=0.01, volume=0.01, glyph="?",
     color=(225, 215, 180), desc="Worn soft from rereading.")
gear("photo", "photograph", "tool", tool="photo", weight=0.01, volume=0.01, glyph="?",
     color=(225, 215, 180), desc="A creased photograph.")
gear("dogtags", "identity tags", "tool", tool="dogtags", weight=0.02, volume=0.01,
     desc="Stamped with a name and number.")
gear("harmonica", "harmonica", "tool", tool="harmonica", weight=0.1, volume=0.05,
     desc="Play something. It might be the last thing you do.")
gear("rosary", "rosary", "tool", tool="rosary", weight=0.02, volume=0.01,
     desc="Beads worn smooth.")
gear("lucky_coin", "lucky coin", "tool", tool="coin", weight=0.01, volume=0.01,
     desc="It hasn't failed you yet.")
gear("cards", "deck of cards", "tool", tool="cards", weight=0.1, volume=0.05,
     desc="Missing the queen of hearts.")
gear("bible", "pocket bible", "tool", tool="bible", weight=0.2, volume=0.1,
     desc="Steel-covered. Some swear it stops bullets.")
gear("ammo_crate", "ammunition crate", "tool", tool="ammo_crate", weight=25.0, volume=30,
     glyph="&", color=(130, 110, 60), uses=10,
     desc="A crate of mixed small-arms ammunition. Resupply here.")
# armour
gear("helmet_m1", "M1 helmet", "armor", slot="head", prot_bullet=0.12, prot_frag=0.55,
     weight=1.3, volume=1.5, glyph="[", color=(120, 130, 80), desc="The 'steel pot'.")
gear("helmet_brodie", "Brodie Mk II helmet", "armor", slot="head", prot_bullet=0.1,
     prot_frag=0.55, weight=1.0, volume=1.5, glyph="[", color=(120, 120, 80),
     desc="Tin hat. Good against shrapnel falling from above.")
gear("helmet_mk3", "Mk III 'turtle' helmet", "armor", slot="head", prot_bullet=0.12,
     prot_frag=0.6, weight=1.2, volume=1.5, glyph="[", color=(120, 120, 80),
     desc="Deeper-sided British helmet.")
gear("stahlhelm", "Stahlhelm M40", "armor", slot="head", prot_bullet=0.12, prot_frag=0.6,
     weight=1.2, volume=1.5, glyph="[", color=(110, 115, 105), desc="German steel helmet.")
gear("ssh40", "SSh-40 helmet", "armor", slot="head", prot_bullet=0.12, prot_frag=0.55,
     weight=1.2, volume=1.5, glyph="[", color=(90, 110, 70), desc="Soviet steel helmet.")
gear("type90", "Type 90 helmet", "armor", slot="head", prot_bullet=0.08, prot_frag=0.45,
     weight=1.0, volume=1.5, glyph="[", color=(130, 120, 80), desc="Japanese steel helmet.")
gear("adrian", "Adrian M26 helmet", "armor", slot="head", prot_bullet=0.06, prot_frag=0.4,
     weight=0.8, volume=1.5, glyph="[", color=(90, 110, 140), desc="French crested helmet.")
gear("m33_it", "M33 helmet", "armor", slot="head", prot_bullet=0.1, prot_frag=0.5, weight=1.1,
     volume=1.5, glyph="[", color=(120, 120, 90), desc="Italian steel helmet.")
gear("wz31", "wz. 31 helmet", "armor", slot="head", prot_bullet=0.1, prot_frag=0.5, weight=1.2,
     volume=1.5, glyph="[", color=(100, 110, 80), desc="Polish steel helmet.")
gear("tanker_helmet", "tanker's helmet", "armor", slot="head", prot_bullet=0.0, prot_frag=0.15,
     weight=0.5, volume=1.0, glyph="[", color=(90, 80, 60), desc="Padded crew helmet.")
gear("soft_cap", "field cap", "armor", slot="head", prot_bullet=0.0, prot_frag=0.0, weight=0.1,
     volume=0.2, glyph="[", color=(130, 120, 90), desc="Offers no protection whatsoever.")
gear("peaked_cap", "peaked service cap", "armor", slot="head", prot_bullet=0.0, prot_frag=0.0, weight=0.2,
     volume=0.4, glyph="[", color=(150, 130, 90), desc="An officer's cap. Snipers like it too.")
gear("staff_map", "staff map case", "tool", tool="map", weight=0.8, volume=0.6, glyph="?", color=(210, 200, 160),
     desc="Situation maps in grease pencil: every unit, every boundary, every phase line.")
gear("civvies", "civilian clothes", "armor", slot="body", weight=1.2, volume=2.0, glyph="[",
     color=(130, 110, 90), desc="A worn jacket, a cap, a farmer's boots. At a distance, nobody.")
gear("flight_jacket", "flying jacket", "armor", slot="body", warmth=2, weight=1.8, volume=2.5, glyph="[",
     color=(110, 80, 50), desc="Sheepskin-lined leather. Warm, and it marks you out as an airman.")
gear("forged_papers", "identity papers", "tool", tool="papers", weight=0.05, volume=0.05, glyph="?",
     color=(220, 210, 180), desc="A work permit and an identity card in a name that isn't yours. Good forgeries; "
     "a careful man could still tell.")
gear("silk_map", "silk escape map", "tool", tool="map", weight=0.02, volume=0.02, glyph="?",
     color=(200, 190, 220), desc="Printed on silk so it won't rustle or rot. Sewn into your jacket lining.")
gear("winter_coat", "winter greatcoat", "armor", slot="body", warmth=3, weight=3.0, volume=4.0,
     glyph="[", color=(150, 150, 140), desc="Heavy wool coat. Keeps the cold out.")
# camouflage over the uniform: worth a great deal where it matches the ground, little where it doesn't
gear("ghillie", "ghillie suit", "armor", slot="body", warmth=1, weight=3.0, volume=3.5, glyph="[",
     color=(95, 110, 60), camo=dict(veg=0.42, urban=0.9, snow=1.1, open=0.8),
     desc="Hessian strips and scrim sewn to a smock, with grass and twigs stuck in it. In long grass or a hedge "
          "bottom you are part of the ground.")
gear("maskhalat", "maskhalat oversuit", "armor", slot="body", warmth=1, weight=1.2, volume=1.5, glyph="[",
     color=(110, 120, 70), camo=dict(veg=0.55, urban=0.85, snow=1.1, open=0.85),
     desc="The Red Army sniper's amoeba-pattern camouflage suit, hood and all.")
gear("tarnjacke", "camouflage smock", "armor", slot="body", warmth=1, weight=1.0, volume=1.2, glyph="[",
     color=(105, 115, 70), camo=dict(veg=0.72, urban=0.9, snow=1.1, open=0.9),
     desc="A splinter- or dot-pattern camouflage smock.")
gear("foliage_cape", "foliage cape", "armor", slot="body", warmth=0, weight=1.2, volume=2.0, glyph="[",
     color=(70, 110, 55), camo=dict(veg=0.5, urban=1.0, snow=1.2, open=0.9),
     desc="A net cape with leaves and palm fronds woven into it - the Japanese sniper's, in a tree.")
gear("snow_smock", "snow smock", "armor", slot="body", warmth=1, weight=0.8, volume=1.0, camo=dict(snow=0.5, veg=1.1,
                                                                                                urban=1.0, open=1.0),
     glyph="[", color=(230, 230, 230), desc="White camouflage over-smock.")
gear("mae_west", "life preserver", "armor", slot="body", weight=0.5, volume=0.5, glyph="[",
     color=(200, 180, 80), desc="Inflatable belt. Might keep your head above water.")

HELMETS = {
    "usa": "helmet_m1", "uk": "helmet_brodie", "canada": "helmet_brodie",
    "australia": "helmet_brodie", "newzealand": "helmet_brodie", "india": "helmet_brodie",
    "ussr": "ssh40", "france": "adrian", "poland": "wz31", "china": "stahlhelm",
    "germany": "stahlhelm", "italy": "m33_it", "japan": "type90", "finland": "stahlhelm",
    "hungary": "stahlhelm", "romania": "stahlhelm",
}

# corpse template (instances carry a name)
gear("corpse", "corpse", "corpse", weight=75.0, volume=80, glyph="%", color=(160, 30, 30),
     desc="A body.")


# ================================================================= magazines, clips and belts
# Generated from the guns so compatibility falls out of calibre and capacity:
# a Sten takes MP 40 magazines, MG 34 and MG 42 share belts, any 7.92mm Mauser takes Mauser clips.

MAG_EMPTY_WEIGHT = {"pistol": 0.1, "smg": 0.25, "assault": 0.3, "rifle": 0.2, "carbine": 0.15, "lmg": 0.35,
                    "sniper": 0.2, "shotgun": 0.1}


def _cal_name(cal):
    return CALIBERS.get(cal, (cal, 0.02))[0]


def _round_weight(cal):
    return CALIBERS.get(cal, (cal, 0.02))[1]


def _register_mags():
    for g in list(ITEMS.values()):
        if g.kind != "gun" or not g.cal or g.cat in ("mortar", "flamer", "at_launcher", "at_disposable"):
            continue
        rw = _round_weight(g.cal)
        if g.feed in ("mag", "clip", "belt") and g.mag > 1:
            if g.feed == "clip":
                mid = f"clip_{g.cal}_{g.mag}"
                name = f"{g.mag}-round en-bloc clip"
                size = (1, 1)
                empty = 0.02
                kind = "mag"
            elif g.feed == "belt":
                mid = f"belt_{g.cal}_{g.mag}"
                name = f"{g.mag}-round belt" + (" (drum)" if g.mag <= 50 else " (box)")
                size = (2, 2)
                empty = 0.5 if g.mag <= 50 else 1.4
                kind = "mag"
            else:
                mid = f"mag_{g.cal}_{g.mag}_{g.cat}"
                drum = g.mag >= 45
                name = f"{g.mag}-round {'drum' if drum and g.cat != 'lmg' else 'pan' if drum else 'magazine'}"
                size = (1, 1) if g.cat == "pistol" else ((2, 2) if drum else (1, 2))
                empty = MAG_EMPTY_WEIGHT.get(g.cat, 0.25) * (3 if drum else 1)
                kind = "mag"
            if mid not in ITEMS:
                _reg(ItemType(mid, f"{name} ({_cal_name(g.cal)})", kind=kind, cal=g.cal, mag=g.mag,
                              weight=empty, round_weight=rw, size=size, glyph="=", color=(170, 160, 120),
                              compat=[g.id], desc=f"Holds {g.mag} rounds of {_cal_name(g.cal)}."))
            else:
                ITEMS[mid].compat.append(g.id)
            g.magtype = mid
        elif g.feed == "stripper":
            n = 10 if g.cal == "763m" else 5
            sid = f"strip_{g.cal}_{n}"
            if sid not in ITEMS:
                _reg(ItemType(sid, f"stripper clip ({n} x {_cal_name(g.cal)})", kind="clip", cal=g.cal, mag=n,
                              weight=0.01, round_weight=rw, size=(1, 1), stack_max=3, glyph="=",
                              color=(190, 170, 110), compat=[g.id],
                              desc=f"{n} rounds on a stripper clip. Push them down into the magazine."))
            else:
                ITEMS[sid].compat.append(g.id)
            g.stripper = sid


_register_mags()
for _mt in ITEMS.values():
    if _mt.kind in ("mag", "clip"):
        names = sorted({ITEMS[c].name for c in _mt.compat})
        _mt.desc += " Fits: " + ", ".join(names[:6]) + ("..." if len(names) > 6 else "") + "."


# ================================================================= webbing, packs, coats

def container(id, name, slot, grids, *, weight=1.0, nations=(), desc="", fold=(3, 2), color=(150, 140, 100)):
    return _reg(ItemType(id, name, kind="container", slot=slot, grids=tuple(grids), weight=weight, nations=tuple(nations),
                         desc=desc, fold=fold, glyph="[", color=color, volume=weight))


P1 = (1, 1, "pouch", None)
P2 = (1, 2, "pouch", None)
P4 = (2, 2, "pouch", None)
GR = (1, 1, "grenade loop", ("grenade",))
STICK = (1, 2, "belt", ("grenade",))

# rigs
container("us_m1923", "M1923 cartridge belt", "rig", [P1] * 10 + [GR] * 2, weight=0.9,
          desc="Ten pockets, each holding one en-bloc clip. Suspenders for grenades.")
container("us_bar_belt", "M1937 BAR belt", "rig", [P2] * 6 + [P1], weight=1.1, desc="Six pockets for BAR magazines.")
container("us_smg_belt", "M1936 belt with SMG pouches", "rig", [P2] * 4 + [P1] * 3 + [GR] * 2, weight=0.9,
          desc="Web pouches for sub-machine gun magazines.")
container("us_carbine_belt", "M1936 belt with carbine pouches", "rig", [P2] * 3 + [P1] * 4, weight=0.7)
container("us_mg_belt", "M1936 pistol belt", "rig", [P1] * 3 + [P4], weight=0.8,
          desc="Pistol magazine pouch, first aid pouch, a place for an ammunition box.")
container("uk_37", "1937 pattern webbing", "rig", [P4, P4, P1, P1, GR], weight=1.3,
          desc="Two basic pouches that take Bren magazines, grenades or anything else.")
container("de_koppel", "Koppel with K98 pouches", "rig", [P1] * 6 + [STICK] * 2, weight=1.1,
          desc="Six pouch compartments of three stripper clips each. A stick grenade shoved into the belt.")
container("de_mp", "MP 40 magazine pouches", "rig", [P2] * 6 + [P1] * 2 + [STICK], weight=1.0,
          desc="Two canvas pouches, three magazines each.")
container("de_mg", "MG gunner's belt", "rig", [P1] * 3 + [P4], weight=0.9, desc="Pistol pouch, tool pouch, belt drum.")
container("su_pouches", "ammunition pouches", "rig", [P1] * 4 + [P1] * 2, weight=0.7,
          desc="Leather pouches for Mosin clips and a grenade bag.")
container("su_drum", "PPSh drum pouches", "rig", [P4, P4, P1, P1], weight=0.8, desc="Canvas pouches for drum magazines.")
container("su_smg", "PPS magazine pouches", "rig", [P2] * 3 + [P1] * 2, weight=0.6)
container("jp_type30", "Type 30 cartridge boxes", "rig", [P1] * 5 + [GR] * 2, weight=1.0,
          desc="Two front cartridge boxes and a larger rear box.")
container("it_giberne", "giberne M1907", "rig", [P1] * 4 + [GR], weight=0.7, desc="Two leather pouches.")
container("fr_cartouchieres", "cartouchières M1916", "rig", [P1] * 6, weight=0.9)
container("bandolier", "cloth bandolier", "rig", [P1] * 6, weight=0.5, desc="Cloth pockets slung across the chest.")
container("medic_bags", "medical pouches", "rig", [P4, P4, P1, P1], weight=1.2, desc="Aid pouches on a yoke.")
container("crew_belt", "crew belt", "rig", [P1, P1, P2], weight=0.5, desc="A pistol holster and a couple of pouches.")
container("lmg_belt", "LMG pouches", "rig", [P2] * 4 + [P4] + [P1] * 2, weight=1.2,
          desc="Pouches for light machine gun magazines or pans.")
# packs
container("backpack", "pack", "pack", [(4, 3, "main", None)], weight=1.2, fold=(3, 3), desc="A field pack.")
container("us_haversack", "M1928 haversack", "pack", [(4, 3, "main", None)], weight=1.4, fold=(3, 3))
container("us_musette", "M1936 musette bag", "pack", [(3, 3, "main", None)], weight=0.9, fold=(3, 2))
container("uk_small_pack", "1937 small pack", "pack", [(4, 3, "main", None)], weight=1.1, fold=(3, 2))
container("de_tornister", "Tornister 39", "pack", [(5, 3, "main", None)], weight=1.8, fold=(3, 3))
container("de_aframe", "A-frame assault pack", "pack", [(3, 3, "main", None)], weight=1.0, fold=(3, 2))
container("su_veshmeshok", "veshmeshok", "pack", [(5, 4, "sack", None)], weight=0.7, fold=(3, 2),
          desc="A duffel sack with a drawstring. Holds everything, organises nothing.")
container("jp_haversack", "Type 99 haversack", "pack", [(4, 3, "main", None)], weight=1.2, fold=(3, 2))
container("it_zaino", "zaino affardellato", "pack", [(4, 4, "main", None)], weight=1.5, fold=(3, 3))
container("fr_musette", "musette M1935", "pack", [(3, 3, "main", None)], weight=0.9, fold=(3, 2))
container("sack", "rough sack", "pack", [(4, 3, "sack", None)], weight=0.6, fold=(3, 2))
# the winter coat has pockets
ITEMS["winter_coat"].grids = ((1, 2, "coat pocket", None), (1, 2, "coat pocket", None))

RIGS = {
    # nation -> {role class: rig id}
    "usa": {"rifle": "us_m1923", "smg": "us_smg_belt", "lmg": "us_bar_belt", "carbine": "us_carbine_belt",
            "mg": "us_mg_belt", "medic": "medic_bags", "crew": "crew_belt"},
    "uk": {"rifle": "uk_37", "smg": "uk_37", "lmg": "uk_37", "carbine": "uk_37", "mg": "uk_37",
           "medic": "medic_bags", "crew": "crew_belt"},
    "germany": {"rifle": "de_koppel", "smg": "de_mp", "lmg": "de_mg", "carbine": "de_koppel", "mg": "de_mg",
                "medic": "medic_bags", "crew": "crew_belt"},
    "ussr": {"rifle": "su_pouches", "smg": "su_drum", "lmg": "lmg_belt", "carbine": "su_pouches", "mg": "lmg_belt",
             "medic": "medic_bags", "crew": "crew_belt"},
    "japan": {"rifle": "jp_type30", "smg": "jp_type30", "lmg": "lmg_belt", "carbine": "jp_type30", "mg": "lmg_belt",
              "medic": "medic_bags", "crew": "crew_belt"},
    "italy": {"rifle": "it_giberne", "smg": "it_giberne", "lmg": "lmg_belt", "carbine": "it_giberne",
              "mg": "lmg_belt", "medic": "medic_bags", "crew": "crew_belt"},
    "france": {"rifle": "fr_cartouchieres", "smg": "fr_cartouchieres", "lmg": "lmg_belt", "carbine": "fr_cartouchieres",
               "mg": "lmg_belt", "medic": "medic_bags", "crew": "crew_belt"},
}
PACKS = {"usa": "us_haversack", "uk": "uk_small_pack", "canada": "uk_small_pack", "australia": "uk_small_pack",
         "newzealand": "uk_small_pack", "india": "uk_small_pack", "germany": "de_tornister", "ussr": "su_veshmeshok",
         "japan": "jp_haversack", "italy": "it_zaino", "france": "fr_musette", "poland": "sack", "china": "sack",
         "finland": "su_veshmeshok", "hungary": "de_tornister", "romania": "de_tornister"}
