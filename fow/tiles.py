"""Terrain tile definitions and numpy lookup tables.

Every tile type has physical properties used by movement, sight, ballistics,
explosions, fire and sound.  The map stores tile indices; all per-tile
queries are vectorised through the lookup arrays below.
"""
from __future__ import annotations

import numpy as np


class TileDef:
    __slots__ = ("id", "key", "name", "glyphs", "fg", "bg", "walk", "see", "cost", "cover",
                 "tall", "hp", "armor", "into", "burnt", "flam", "water", "pos_cover", "conceal",
                 "dig", "crush", "floor", "door", "sound", "desc", "window", "vcost", "hard")

    def __init__(self, key, name, glyphs, fg, bg, *, walk=True, see=True, cost=100, cover=0,
                 tall=False, hp=0, armor=0, into=None, burnt=None, flam=0, water=0, pos_cover=0,
                 conceal=0, dig=False, crush=0, floor=False, door=0, sound=0, desc="",
                 window=False, vcost=None, hard=False):
        self.key = key
        self.name = name
        self.glyphs = glyphs
        self.fg = fg
        self.bg = bg
        self.walk = walk
        self.see = see
        self.cost = cost
        self.cover = cover
        self.tall = tall
        self.hp = hp
        self.armor = armor
        self.into = into
        self.burnt = burnt
        self.flam = flam
        self.water = water
        self.pos_cover = pos_cover
        self.conceal = conceal
        self.dig = dig
        self.crush = crush
        self.floor = floor
        self.door = door
        self.sound = sound
        self.desc = desc
        self.window = window
        self.vcost = vcost
        self.hard = hard


DEFS: list[TileDef] = []
ID: dict[str, int] = {}


def T(key, name, glyphs, fg, bg, **kw):
    d = TileDef(key, name, glyphs, fg, bg, **kw)
    d.id = len(DEFS)
    DEFS.append(d)
    ID[key] = d.id
    return d


def variant(base_key, key, name=None, fg=None, bg=None, **kw):
    b = DEFS[ID[base_key]]
    attrs = {s: getattr(b, s) for s in TileDef.__slots__ if s not in ("id", "key")}
    attrs.update(kw)
    if name:
        attrs["name"] = name
    if fg:
        attrs["fg"] = fg
    if bg:
        attrs["bg"] = bg
    n = attrs.pop("name")
    g = attrs.pop("glyphs")
    f = attrs.pop("fg")
    bb = attrs.pop("bg")
    return T(key, n, g, f, bb, **attrs)


# ------------------------------------------------------------------ ground
T("void", "nothing", " ", (0, 0, 0), (0, 0, 0), walk=False, see=False)
T("grass", "grass", ".,'`.", (85, 150, 60), (24, 50, 20), dig=True, flam=12, conceal=8,
  burnt="burnt", into="dirt")
variant("grass", "grass_dry", "dry grass", fg=(160, 160, 80), bg=(55, 55, 25), flam=30)
variant("grass", "grass_autumn", "wet grass", fg=(130, 130, 60), bg=(45, 45, 22), flam=6)
T("tall_grass", "tall grass", "\"\";\"", (120, 175, 70), (30, 58, 22), dig=True, flam=30,
  conceal=45, cost=110, burnt="burnt", into="dirt")
variant("tall_grass", "tall_grass_dry", "dry tall grass", fg=(190, 175, 90), bg=(70, 62, 30),
        flam=55)
variant("tall_grass", "kunai", "kunai grass", fg=(150, 190, 80), bg=(40, 70, 25), conceal=65,
        cost=140, flam=40)
T("wheat", "wheat field", "\"\"\"'", (215, 190, 85), (80, 68, 28), dig=True, flam=55,
  conceal=50, cost=120, burnt="burnt", into="dirt")
T("corn", "maize", "||!|", (160, 175, 60), (45, 60, 20), see=False, dig=True, flam=35,
  conceal=75, cost=150, burnt="burnt", into="dirt", crush=0)
T("sunflower", "sunflowers", "*|*|", (235, 200, 40), (45, 70, 25), see=False, dig=True,
  flam=30, conceal=75, cost=150, burnt="burnt", into="dirt")
T("plowed", "ploughed field", "=-=-", (120, 90, 55), (55, 40, 25), dig=True, cost=130,
  into="dirt")
T("dirt", "dirt", ".,.`", (140, 110, 70), (52, 40, 25), dig=True, into="dirt")
T("mud", "mud", "~,~.", (115, 88, 55), (48, 35, 20), dig=True, cost=190, into="mud", sound=-2)
T("burnt", "scorched earth", ".,`'", (80, 70, 60), (28, 24, 21), dig=True, into="dirt")
T("road", "dirt road", ".·.:", (170, 140, 95), (78, 62, 40), cost=90, dig=True, into="dirt",
  vcost=60)
T("paved", "paved road", ".·.·", (160, 160, 155), (62, 62, 60), cost=90, into="rubble_light",
  hp=400, armor=80, vcost=50)
T("cobble", "cobblestones", "·:·.", (170, 160, 140), (70, 65, 55), cost=95, into="rubble_light",
  hp=500, armor=90, vcost=55)
T("sand", "sand", ".,·`", (220, 200, 140), (125, 108, 68), cost=120, dig=True, into="sand")
T("wet_sand", "wet sand", ".,.·", (190, 170, 120), (95, 84, 58), cost=115, dig=True,
  into="wet_sand")
T("shingle", "shingle", ":∙°:", (175, 175, 165), (82, 82, 76), cost=160, pos_cover=12,
  into="shingle", sound=3)
T("snow", "snow", ".,'.", (230, 235, 245), (165, 172, 188), cost=130, dig=True, into="dirt",
  sound=-2)
T("deep_snow", "deep snow", "∙.:·", (240, 245, 255), (185, 190, 205), cost=190, dig=True,
  into="snow", conceal=10, sound=-3)
T("ash", "volcanic ash", ".,·`", (95, 88, 82), (36, 33, 31), cost=170, dig=True, into="ash",
  sound=-2)
T("rock_ground", "rocky ground", ".,`:", (150, 140, 125), (72, 66, 58), cost=115, into="rock_ground")
T("floor_wood", "wooden floor", ".", (150, 110, 70), (70, 50, 32), floor=True, flam=40,
  burnt="burnt", into="rubble_wood", hp=150, armor=10)
T("floor_stone", "stone floor", ".", (165, 160, 150), (78, 76, 70), floor=True,
  into="rubble_light", hp=400, armor=40)
T("floor_concrete", "concrete floor", ".", (140, 140, 140), (82, 82, 82), floor=True,
  into="rubble_light", hp=1500, armor=100)
T("runway", "airfield", ".·", (140, 140, 130), (70, 70, 65), cost=90, into="crater",
  hp=600, armor=60, vcost=45)
T("paddy", "rice paddy", "~\"~,", (130, 180, 100), (38, 70, 60), cost=260, water=1,
  conceal=25, into="paddy", sound=2)

# ------------------------------------------------------------------ water
T("shallow", "shallow water", "~≈~~", (110, 160, 230), (30, 62, 115), cost=240, water=1,
  conceal=15, into="shallow", sound=2, vcost=250)
T("deep", "deep water", "≈~≈≈", (70, 110, 205), (12, 30, 80), cost=380, water=2,
  into="deep", sound=2)
T("surf", "surf", "~≈~≈", (200, 220, 240), (50, 90, 140), cost=260, water=1, into="surf",
  sound=4)
T("ice", "ice", ".-.·", (205, 225, 245), (120, 150, 180), cost=140, into="deep", hp=120,
  armor=20)
T("marsh", "marsh", "\"~,\"", (105, 145, 95), (35, 60, 46), cost=240, water=1, conceal=45,
  into="marsh", flam=5, sound=1)

# ------------------------------------------------------------------ vegetation
T("tree", "tree", "♣♣♣♠", (80, 175, 62), (16, 38, 14), walk=False, see=False, cover=60,
  tall=True, hp=260, armor=35, into="stump", burnt="dead_tree", flam=12, crush=2,
  desc="A tree. The trunk stops bullets; the canopy hides you from the air.")
variant("tree", "pine", "fir tree", fg=(50, 150, 85), bg=(12, 35, 20), glyphs="♣♣♠♣")
variant("tree", "tree_snow", "snowy fir", fg=(60, 120, 80), bg=(150, 160, 175), glyphs="♣♣♠♣")
variant("tree", "tree_autumn", "tree", fg=(170, 110, 40), bg=(45, 35, 15))
variant("tree", "olive", "olive tree", fg=(130, 150, 90), bg=(55, 55, 30), hp=200, armor=30)
T("palm", "palm tree", "ττ♣τ", (90, 170, 60), (28, 50, 20), walk=False, see=True, cover=35,
  tall=True, hp=180, armor=25, into="stump", burnt="dead_tree", flam=10, crush=2)
T("dead_tree", "shattered tree", "ƒ|ƒ¡", (110, 95, 80), (30, 26, 22), walk=False, see=True,
  cover=40, tall=True, hp=140, armor=25, into="stump", flam=10, crush=1)
T("stump", "tree stump", "°•°∙", (130, 100, 60), (40, 32, 22), cost=150, cover=30,
  hp=150, armor=30, into="dirt", flam=5, crush=0, pos_cover=10)
T("log", "fallen tree", "=-=─", (140, 100, 60), (40, 30, 20), cost=260, cover=60, hp=250,
  armor=35, into="dirt", flam=10, crush=1, pos_cover=25)
T("bush", "undergrowth", "%\"%;", (60, 125, 50), (20, 48, 18), see=False, cost=190,
  cover=10, conceal=70, flam=25, hp=40, armor=2, into="grass", burnt="burnt", crush=1)
variant("bush", "bush_snow", "snowy undergrowth", fg=(90, 130, 90), bg=(150, 160, 170))
T("jungle", "dense jungle", "%\"%%;", (58, 118, 54), (16, 44, 20), see=False, cost=260,
  cover=18, conceal=85, flam=6, hp=60, armor=4, into="tall_grass", burnt="burnt", crush=1)
T("bamboo", "bamboo", "¦|¦!", (120, 180, 70), (25, 55, 20), see=False, cost=280, cover=20,
  conceal=80, flam=15, hp=50, armor=4, into="tall_grass", crush=1)
T("scrub", "scrub", ",\"*,", (150, 140, 75), (105, 92, 58), cost=110, conceal=20, flam=30,
  cover=5, into="sand", burnt="sand")
T("hedge", "hedgerow", "▓▓▓▒", (45, 105, 38), (30, 62, 24), walk=False, see=False, cover=92,
  tall=True, hp=520, armor=200, into="rubble_earth", flam=6, crush=2, conceal=60,
  desc="Bocage: an earth bank topped with dense hedge. Impassable except at gaps.")
T("garden_hedge", "garden hedge", "%%\"%", (60, 125, 50), (26, 55, 22), see=False, cost=320,
  cover=30, conceal=60, flam=20, hp=60, armor=5, into="grass", crush=1)

# ------------------------------------------------------------------ walls & buildings
T("wall_brick", "brick wall", "#", (175, 95, 72), (92, 46, 36), walk=False, see=False,
  cover=100, tall=True, hp=700, armor=140, into="rubble", crush=3, sound=25, hard=True)
T("wall_stone", "stone wall", "#", (175, 170, 155), (96, 92, 82), walk=False, see=False,
  cover=100, tall=True, hp=900, armor=170, into="rubble", crush=3, sound=30, hard=True)
T("wall_wood", "wooden wall", "#", (155, 108, 62), (82, 56, 32), walk=False, see=False,
  cover=100, tall=True, hp=260, armor=22, into="rubble_wood", flam=45, burnt="rubble_wood",
  crush=2, sound=12)
T("wall_thatch", "bamboo and thatch wall", "#", (185, 165, 95), (95, 80, 40), walk=False,
  see=False, cover=100, tall=True, hp=120, armor=8, into="rubble_wood", flam=75,
  burnt="burnt", crush=1, sound=6)
T("wall_log", "log wall", "#", (130, 95, 55), (70, 48, 26), walk=False, see=False, cover=100,
  tall=True, hp=900, armor=160, into="rubble_wood", flam=20, burnt="rubble_wood", crush=3,
  sound=20)
T("wall_concrete", "reinforced concrete", "█", (165, 165, 158), (112, 112, 106), walk=False,
  see=False, cover=100, tall=True, hp=5000, armor=600, into="rubble_heavy", crush=9, sound=40,
  hard=True)
T("wall_factory", "factory wall", "#", (150, 120, 100), (85, 68, 58), walk=False, see=False,
  cover=100, tall=True, hp=1200, armor=180, into="rubble_heavy", crush=3, sound=30, hard=True)
T("window", "window", "\"", (170, 210, 230), (60, 60, 70), walk=False, see=True, cover=55,
  tall=True, hp=25, armor=2, into="window_broken", window=True, sound=8,
  desc="A glazed window. You can shoot through it; so can they.")
T("window_broken", "broken window", "'", (150, 170, 180), (50, 45, 45), cost=320, see=True,
  cover=55, tall=True, hp=300, armor=120, into="rubble", window=True, sound=2, pos_cover=0)
T("embrasure", "embrasure", "═", (190, 190, 180), (40, 40, 38), walk=False, see=True,
  cover=92, tall=True, hp=5000, armor=600, into="rubble_heavy", window=True, crush=9,
  desc="A narrow firing slit in concrete.")
T("door", "door", "+", (170, 115, 60), (72, 46, 26), walk=True, see=False, cover=90,
  tall=True, hp=90, armor=15, into="doorway", door=1, flam=40, burnt="doorway", sound=10,
  cost=150, crush=1)
T("door_open", "open door", "'", (170, 115, 60), (50, 35, 22), cover=15, tall=True, hp=90,
  armor=15, into="doorway", door=2, flam=40, burnt="doorway", floor=True, crush=1)
T("doorway", "doorway", ".", (150, 130, 110), (55, 45, 38), floor=True, into="rubble_light")
T("fence", "wooden fence", "|", (160, 120, 75), (40, 32, 22), cost=240, cover=12, tall=True,
  hp=50, armor=4, into="dirt", flam=40, burnt="burnt", crush=1)
T("fence_h", "wooden fence", "-", (160, 120, 75), (40, 32, 22), cost=240, cover=12, tall=True,
  hp=50, armor=4, into="dirt", flam=40, burnt="burnt", crush=1)
T("low_wall", "low stone wall", "=", (170, 165, 150), (70, 66, 58), cost=300, cover=78,
  hp=550, armor=150, into="rubble", crush=2, pos_cover=0, hard=True,
  desc="A waist-high dry-stone wall. Excellent cover if you stay low.")
T("rubble", "rubble", ",;^·", (155, 145, 132), (62, 57, 52), cost=200, cover=45, hp=0,
  into="rubble", pos_cover=30, conceal=25, dig=False, sound=2,
  desc="Broken masonry. Slow going, but good cover.")
T("rubble_light", "debris", ".,;·", (150, 140, 130), (60, 56, 52), cost=130, cover=15,
  into="rubble_light", pos_cover=12, conceal=10)
T("rubble_heavy", "collapsed masonry", "▲^▲∩", (175, 165, 152), (84, 78, 72), cost=320,
  see=False, cover=85, tall=True, hp=0, into="rubble_heavy", pos_cover=40, conceal=50,
  sound=10)
T("rubble_wood", "charred timbers", "=;,/", (120, 90, 60), (40, 30, 22), cost=200, cover=30,
  hp=0, into="rubble_wood", flam=20, burnt="burnt", pos_cover=15, conceal=20)
T("rubble_earth", "broken earth bank", ";,:.", (120, 100, 65), (45, 38, 25), cost=170,
  cover=35, into="dirt", pos_cover=20, conceal=15, dig=True)
T("machinery", "heavy machinery", "Σπ¶Ω", (130, 130, 145), (52, 52, 58), walk=False, see=False,
  cover=95, tall=True, hp=1500, armor=200, into="rubble_heavy", crush=9, hard=True)
T("crates", "crates", "■", (160, 120, 70), (70, 50, 30), walk=False, see=False, cover=55,
  tall=True, hp=150, armor=12, into="rubble_wood", flam=40, crush=2)
T("table", "table", "π", (160, 115, 70), (60, 44, 30), cost=220, cover=25, hp=60, armor=5,
  into="rubble_wood", flam=40, floor=True, crush=1)
T("pew", "church pew", "=", (150, 105, 60), (60, 44, 30), cost=220, cover=30, hp=80, armor=8,
  into="rubble_wood", flam=40, floor=True, crush=1)
T("altar", "altar", "Ω", (220, 210, 180), (90, 85, 75), walk=False, cover=80, hp=600,
  armor=120, into="rubble", floor=True, crush=3)
T("bed", "bed", "≡", (170, 150, 120), (60, 44, 30), cost=200, cover=15, hp=50, armor=4,
  into="rubble_wood", flam=50, floor=True, crush=1)
T("stove", "stove", "Φ", (90, 90, 95), (60, 44, 30), walk=False, cover=70, hp=300, armor=60,
  into="rubble_light", floor=True, crush=2)
T("hay", "hay bales", "■▬■▬", (220, 195, 110), (100, 85, 40), walk=False, see=False, cover=20,
  tall=True, hp=80, armor=2, into="burnt", flam=85, burnt="burnt", crush=1,
  desc="Straw hides you but stops nothing.")
T("wreck", "burnt-out wreck", "&", (95, 85, 75), (38, 34, 30), walk=False, see=False,
  cover=95, tall=True, hp=2500, armor=300, into="rubble_heavy", crush=9, hard=True,
  desc="The blackened hull of a vehicle.")
T("well", "well", "o", (170, 170, 160), (70, 66, 60), walk=False, cover=70, hp=600,
  armor=120, into="rubble", crush=3)
T("grave", "grave marker", "+", (190, 190, 180), (40, 45, 35), cost=120, cover=25, hp=100,
  armor=30, into="dirt")
T("boulder", "boulder", "♦", (150, 145, 135), (70, 66, 60), walk=False, see=True, cover=85,
  tall=True, hp=0, armor=500, into="boulder", crush=9, hard=True)
T("cliff", "rock face", "▲^▲▲", (150, 140, 125), (95, 88, 78), walk=False, see=False,
  cover=100, tall=True, hp=0, into="cliff", crush=9, hard=True, sound=40)
T("bridge", "bridge", "═", (170, 150, 120), (70, 55, 40), cost=95, hp=900, armor=150,
  into="deep", vcost=60, sound=3)
T("rail", "railway", "╪", (140, 130, 120), (60, 52, 45), cost=110, hp=300, armor=60,
  into="rubble_light", vcost=80)

# ------------------------------------------------------------------ defensive works
T("sandbags", "sandbags", "≡", (205, 185, 125), (102, 88, 56), cost=320, cover=86, hp=450,
  armor=90, into="rubble_earth", crush=1, conceal=30, hard=True,
  desc="Sandbag wall. Stops rifle rounds. Crawl behind it.")
T("wire", "barbed wire", "§", (185, 185, 185), (40, 40, 38), cost=650, cover=0, hp=60,
  armor=3, into="dirt", crush=1, sound=2,
  desc="Rusted barbed wire. Crossing it is slow, painful and loud.")
T("hedgehog", "Czech hedgehog", "X", (140, 130, 120), (40, 36, 30), walk=False, cover=40,
  tall=True, hp=900, armor=120, into="rubble_light", crush=9, hard=True,
  desc="Welded steel beams to rip the bottoms out of landing craft and stop tanks.")
T("teeth", "dragon's teeth", "▲", (175, 175, 168), (70, 70, 66), cost=320, cover=60, hp=2000,
  armor=300, into="rubble_light", crush=9, hard=True, desc="Concrete anti-tank obstacles.")
T("trench", "trench", "░", (125, 100, 65), (48, 38, 24), pos_cover=72, conceal=50, dig=True,
  into="crater", desc="A slit trench. Stay low and you're hard to hit.")
T("trench_snow", "snowy trench", "░", (180, 180, 190), (100, 100, 110), pos_cover=72,
  conceal=50, dig=True, into="crater")
T("foxhole", "foxhole", "o", (130, 100, 62), (52, 40, 24), pos_cover=78, conceal=55, dig=True,
  into="crater", desc="A one-man hole in the ground. Home.")
T("crater", "shell crater", "o", (120, 98, 72), (42, 34, 26), cost=150, pos_cover=48,
  conceal=30, dig=True, into="crater", desc="A shell hole. Two never land in the same place, "
  "the old sweats say.")
T("crater_big", "bomb crater", "O", (110, 90, 68), (36, 29, 22), cost=180, pos_cover=58,
  conceal=40, dig=True, into="crater_big")
T("crater_water", "flooded crater", "o", (100, 140, 200), (30, 45, 70), cost=260, water=1,
  pos_cover=45, conceal=30, into="crater_water")
T("spider_hole", "ground", ".,.`", (140, 110, 70), (52, 40, 25), pos_cover=92, conceal=92,
  dig=True, into="crater", desc="Freshly disturbed earth...")
T("atditch", "anti-tank ditch", "▼", (115, 92, 60), (40, 32, 20), cost=260, pos_cover=65,
  conceal=40, crush=9, dig=True, into="atditch")
T("sign", "warning sign", "¡", (230, 220, 90), (40, 40, 30), cost=100, hp=20, armor=1,
  into="dirt", desc="'ACHTUNG MINEN!' - or its local equivalent.")

# ------------------------------------------------------------------ installations
T("canvas", "tent canvas", "▒", (190, 175, 120), (95, 85, 55), walk=False, see=False, cover=4,
  tall=True, hp=30, armor=1, into="burnt", flam=70, burnt="burnt", crush=1, sound=2,
  desc="Canvas. Hides you, stops nothing.")
T("camo_net", "camouflage netting", "░", (95, 110, 55), (35, 45, 22), cost=110, conceal=70,
  flam=40, burnt="burnt", into="dirt", hp=20, armor=1, crush=0,
  desc="Netting strung with scrim. Hides guns from the air.")
T("ammo_stack", "stacked ammunition", "■", (190, 175, 80), (70, 62, 30), walk=False, see=False,
  cover=60, tall=True, hp=120, armor=15, into="crater_big", flam=30, burnt="crater_big",
  crush=9, desc="Crates of shells and cartridges. Resupply here - and don't let it get hit.")
T("fuel_drums", "fuel drums", "◘", (200, 90, 60), (70, 40, 30), walk=False, see=True,
  cover=45, tall=True, hp=60, armor=4, into="burnt", flam=95, burnt="burnt", crush=1,
  desc="Jerricans and drums of petrol.")
T("antenna", "radio mast", "¥", (190, 190, 190), (40, 40, 40), walk=False, see=True,
  cover=5, tall=True, hp=60, armor=10, into="rubble_light", crush=1)
T("redcross", "red cross marker", "+", (230, 30, 30), (220, 220, 220), cost=100,
  into="dirt", desc="A red cross laid out on a white sheet.")
T("plane_parked", "parked aircraft", "╤", (150, 160, 140), (50, 55, 50), walk=False, see=True,
  cover=40, tall=True, hp=220, armor=6, into="wreck", flam=60, burnt="wreck", crush=2,
  desc="An aircraft on the ground, fuelled and armed.")
T("gun_pit", "gun pit", "·", (150, 125, 85), (60, 48, 30), pos_cover=55, conceal=40, dig=True,
  into="crater", desc="A dug-in emplacement.")

# ------------------------------------------------------------------ ships and aircraft (aboard.py)
T("deck_steel", "steel deck", ".·", (150, 152, 158), (62, 64, 70), cost=100, hard=True, sound=3, hp=400, armor=12,
  into="deck_holed", desc="Grey-painted steel plate, non-skid, rivets in rows.")
T("deck_wood", "planked deck", "=·", (190, 165, 120), (92, 76, 52), cost=100, sound=2, hp=300, armor=8,
  into="deck_holed", flam=15, burnt="deck_holed", desc="Teak planking, holystoned white.")
T("deck_inside", "passageway", ".", (140, 142, 148), (52, 54, 60), cost=100, floor=True, hard=True, sound=3,
  hp=300, armor=10, into="deck_holed", desc="A steel passageway below decks, lit by caged bulbs.")
T("deck_holed", "shattered deck", "%,", (120, 110, 100), (40, 36, 34), cost=220, cover=10, sound=4,
  desc="Torn plating, splinters and a hole down into the dark.")
T("wall_steel", "bulkhead", "█", (150, 152, 158), (95, 97, 104), walk=False, see=False, cover=100, tall=True,
  hp=900, armor=25, into="deck_holed", desc="A watertight steel bulkhead.")
T("hull", "hull plating", "▓", (120, 125, 135), (70, 74, 82), walk=False, see=False, cover=100, tall=True,
  hp=1200, armor=30, into="deck_holed", desc="The ship's side.")
T("railing", "guard rail", "┼", (190, 190, 195), (62, 64, 70), cost=420, cover=8, hp=80, armor=4,
  into="deck_steel", desc="Lifelines and stanchions along the deck edge. Over them is the sea.")
T("hatch", "hatch", "▫", (180, 170, 120), (60, 60, 64), cost=180, door=0, hard=True,
  desc="A hatch down through the deck, and a steep steel ladder. (e to go down)")
T("ladder_up", "ladder", "≡", (190, 180, 130), (52, 54, 60), cost=150, floor=True,
  desc="A steel ladder up to the weather deck. (e to climb)")
T("gun_turret", "gun turret", "■", (145, 150, 158), (82, 86, 94), walk=False, see=False, cover=100, tall=True,
  hp=2000, armor=120, desc="An armoured gun house. The guns' crews are inside.")
T("gun_mount", "gun mount", "▪", (150, 155, 160), (80, 84, 90), walk=False, see=True, cover=70, tall=True,
  hp=600, armor=20, desc="An open-backed gun mount behind a splinter shield.")
T("funnel", "funnel", "●", (80, 80, 84), (40, 40, 44), walk=False, see=False, cover=100, tall=True, hp=500,
  armor=10, desc="A funnel, hot to the touch, smoke pouring out of it.")
T("torpedo_tubes", "torpedo tubes", "═", (140, 150, 140), (60, 64, 60), walk=False, see=True, cover=50, tall=True,
  hp=300, armor=10, desc="A bank of torpedo tubes on a turntable.")
T("depth_charges", "depth charge rack", "∩", (120, 130, 120), (50, 54, 50), walk=False, see=True, cover=40,
  hp=200, armor=6, desc="Ash cans in a rack at the stern, ready to roll.")
T("helm", "helm", "*", (220, 200, 120), (52, 54, 60), cost=120, floor=True,
  desc="The wheel, the engine telegraphs and the voice pipes. (e to take the conn)")
T("chart_table", "chart table", "π", (200, 190, 150), (52, 54, 60), walk=False, see=True, cover=30, floor=True,
  desc="The plot: the ship's track, the other ships, the land. (e beside it to study it)")
T("periscope", "periscope", "¦", (200, 200, 170), (52, 54, 60), cost=120, floor=True,
  desc="The attack periscope. (e to raise it and look)")
T("life_raft", "life raft", "▭", (220, 180, 60), (80, 70, 40), walk=False, see=True, cover=20,
  desc="A Carley float lashed to the rail.")
T("sky", "open air", " .", (170, 190, 215), (110, 140, 185), walk=False, see=True, cost=999,
  desc="Nothing but air, and the ground a long way down.")
T("cloud", "cloud", "░▒", (225, 230, 235), (160, 175, 200), walk=False, see=False, cost=999,
  desc="Cloud streaming past.")
T("fuselage", "fuselage", "▓", (150, 155, 150), (90, 95, 90), walk=False, see=False, cover=15, tall=True, hp=120,
  armor=2, into="fuselage_holed", desc="Thin aluminium skin, riveted over the frames.")
T("fuselage_holed", "holed fuselage", "▒", (120, 120, 118), (60, 64, 60), walk=False, see=True, cover=10,
  desc="Torn skin, and the wind screaming through it.")
T("plane_floor", "walkway", ".", (140, 140, 130), (58, 58, 54), cost=130, floor=True, hard=True, sound=3,
  desc="A narrow walkway over the control cables.")
T("catwalk", "bomb bay catwalk", "-", (160, 160, 140), (40, 40, 40), cost=180, floor=True,
  desc="A catwalk no wider than a boot between the bombs, above the doors.")
T("station", "crew station", "Ω", (200, 190, 150), (58, 58, 54), cost=120, floor=True,
  desc="A seat, a gun or a sight. (e to take this station)")
T("hatch_exit", "escape hatch", "○", (230, 180, 90), (58, 58, 54), cost=120, floor=True,
  desc="The escape hatch. (e to bail out)")
T("wing", "wing", "▬", (150, 155, 150), (100, 105, 100), walk=False, see=True, cover=5, hp=200, armor=2,
  desc="The wing, and the engines on it, and the fuel in it.")
T("engine_nacelle", "engine", "◘", (90, 90, 90), (70, 72, 70), walk=False, see=True, cover=20, hp=150, armor=4,
  desc="An engine nacelle, the propeller a grey disc.")

# ship's fittings (shipyard.py)
T("ladder", "ladder", "≡", (200, 190, 140), (52, 54, 60), cost=150, floor=True,
  desc="A steep steel ladder between decks. (< up, > down, or e)")
T("bunk", "bunks", "≡", (150, 150, 160), (48, 50, 56), cost=260, floor=True, cover=10,
  desc="Pipe racks three and four high, a thin mattress on each. (e to turn in)")
T("locker", "lockers", "▯", (120, 125, 135), (48, 50, 56), walk=False, see=False, cover=40, hp=150, armor=4)
T("boiler", "boiler", "Ω", (160, 110, 90), (60, 50, 46), walk=False, see=False, cover=100, tall=True, hp=900,
  armor=25, desc="A boiler, roaring: steam at six hundred pounds.")
T("turbine", "turbine", "Σ", (140, 145, 155), (56, 58, 64), walk=False, see=True, cover=80, hp=900, armor=25,
  desc="The main engine: turbines and reduction gears, shafts turning aft.")
T("ammo_rack", "magazine racks", "■", (190, 170, 90), (60, 56, 40), walk=False, see=False, cover=60, hp=200,
  armor=6, desc="Shells and powder in racks. Everything here explodes.")
T("avgas", "aviation fuel tank", "◘", (200, 110, 70), (60, 44, 40), walk=False, see=False, cover=60, hp=200,
  armor=6, desc="High-octane aviation gasoline. The most dangerous stuff aboard.")
T("ready_locker", "ready-service locker", "▣", (200, 180, 90), (62, 64, 70), walk=False, see=True, cover=30,
  hp=150, armor=6, desc="Ready ammunition for the mounts. (e beside it: take a load to a mount)")
T("repair_locker", "repair locker", "▤", (220, 80, 70), (62, 64, 70), walk=False, see=True, cover=30, hp=150,
  armor=6, desc="Hoses, foam, shoring timber, axes, handy-billy pumps. (e beside it: draw gear)")
T("life_ring", "life ring", "◯", (240, 150, 60), (62, 64, 70), walk=False, see=True, cover=5,
  desc="A life ring on the rail. (e beside it to take it: throw it to a man in the water)")
T("lookout_post", "lookout post", "○", (220, 210, 160), (62, 64, 70), cost=110,
  desc="A lookout's post, with big binoculars on a pedestal. (x to scan; Enter to report what you see)")
T("radar_scope", "radar scope", "◎", (120, 230, 140), (40, 46, 50), cost=120, floor=True,
  desc="A radar repeater, green trace sweeping round.")
T("radio_set", "radio sets", "▥", (150, 160, 150), (48, 50, 56), walk=False, see=True, cover=30, floor=True)
T("elevator", "aircraft elevator", "▒", (170, 150, 110), (80, 70, 55), cost=100, sound=2,
  desc="An aircraft elevator, flush with the deck.")
T("arrest_wire", "arresting wire", "─", (200, 200, 200), (92, 76, 52), cost=110,
  desc="An arresting wire across the deck, raised a few inches on its bows.")
T("catapult", "catapult track", "═", (160, 160, 150), (92, 76, 52), cost=100)
T("catwalk", "gallery catwalk", "#", (150, 150, 150), (50, 52, 56), cost=110, hard=True, sound=3,
  desc="Grating along the deck edge: the gun galleries.")
T("torpedo_rack", "torpedo racks", "═", (150, 160, 150), (52, 54, 60), walk=False, see=True, cover=50, floor=True,
  desc="Reload torpedoes on skids. Men sleep on top of them.")
T("steering_gear", "steering gear", "Ψ", (140, 145, 150), (52, 54, 60), walk=False, see=True, cover=60, floor=True)
T("sea_below", "the sea below", "≈~", (40, 70, 130), (8, 18, 45), walk=False, see=True, cost=999,
  desc="A long way down: the sea.")
T("deck_below", "the deck below", ".", (95, 97, 104), (35, 37, 42), walk=False, see=True, cost=999,
  desc="The deck, below you.")
T("fire_curtain", "fire curtain", "▦", (170, 90, 70), (60, 44, 40), cost=150, door=0,
  desc="A steel roller curtain dividing the hangar - rolled up.")
# (new tiles go on the end: saved maps store tile numbers)
T("pier", "wooden pier", "═", (175, 150, 110), (74, 58, 40), cost=100, hp=500, armor=60, into="deep", vcost=80,
  sound=3, flam=30, burnt="deep", desc="Planks on pilings, tarred black, smelling of fuel oil and fish.")
T("bollard", "bollard", "o", (60, 60, 64), (74, 74, 72), walk=False, see=True, cover=30, hp=0, armor=300,
  desc="An iron bollard for the mooring lines.")

EXPLODE = {}   # tile id -> (power, radius, fire)

# ------------------------------------------------------------------ floors (floors.py)
T("stairs", "stairs", "≡", (200, 170, 120), (70, 52, 34), floor=True, cost=160, flam=30, burnt="burnt",
  into="rubble_wood", hp=150, armor=10,
  desc="A staircase to the floor above. (< to climb it, > to come down)")
T("trapdoor", "cellar trapdoor", "▫", (170, 140, 100), (70, 52, 34), floor=True, flam=20, into="rubble_wood",
  hp=120, armor=8, desc="A trapdoor to the cellar - the safest place in a bombardment. (> to go down, < to come up)")

# ------------------------------------------------------------------ the country's own (mapgen.regional)
variant("corn", "vineyard", "vineyard", fg=(120, 140, 70), bg=(70, 60, 35), conceal=40, cost=140,
        desc="Vines trained on wires, row after row: the rows are cover from view one way, and a firing lane the other.")
variant("corn", "sugarcane", "sugar cane", fg=(140, 170, 80), bg=(40, 60, 25), conceal=65, cost=170,
        desc="Cane taller than a man, cut in lanes. You can't see ten feet into it.")
variant("tree", "cypress", "cypress", fg=(40, 80, 45), bg=(16, 34, 18),
        desc="A dark Italian cypress, tall and narrow as a church spire.")
variant("tree", "birch", "birch", fg=(190, 200, 170), bg=(40, 60, 35),
        desc="A white birch. The Russian forest is full of them: the partisans' country.")
variant("tree", "fir", "spruce", fg=(30, 75, 45), bg=(12, 30, 18), hp=250,
        desc="Dark spruce planted close in rows - the Hürtgen and the Ardennes: tree bursts, and no view at all.")
variant("tree", "apple_tree", "apple tree", fg=(95, 150, 60), bg=(25, 50, 20), hp=150,
        desc="An old apple tree in a Norman orchard: cider and Calvados, and cover.")
variant("tree", "mangrove", "mangrove", fg=(60, 110, 60), bg=(25, 50, 45),
        desc="Mangrove roots in the tidal mud: a wall of stilts nobody walks through.")
variant("low_wall", "drystone", "dry-stone wall", fg=(180, 170, 145), bg=(78, 72, 60),
        desc="Fieldstones stacked without mortar, waist high, older than anyone. Stops a bullet as well as any wall.")
variant("scrub", "camelthorn", "camel thorn", fg=(160, 150, 90), bg=(120, 104, 66),
        desc="Grey-green thorn scrub, all the desert grows. Hides a man lying flat, a little.")
variant("tall_grass", "reeds", "reeds", fg=(150, 160, 90), bg=(45, 60, 40), conceal=70, cost=150,
        desc="Reeds higher than your head, in water to your knees.")
variant("rock_ground", "scree", "scree", fg=(160, 155, 145), bg=(90, 86, 78), cost=220,
        desc="Loose stones on a steep slope: every step slides and clatters.")
variant("boulder", "outcrop", "rock outcrop", fg=(140, 135, 125), bg=(66, 62, 56), hp=2000, armor=300,
        desc="Bare rock breaking through the hillside. The best cover there is.")
T("dune", "sand dune", "~∽~≈", (225, 205, 145), (140, 120, 76), cost=170, pos_cover=30, conceal=10, dig=True,
  into="sand", desc="A ridge of soft sand. Behind it, out of sight; on top of it, on the skyline.")
T("wadi", "wadi bed", ",.·,", (200, 180, 130), (110, 94, 60), cost=110, pos_cover=40, conceal=25, dig=True,
  into="sand", desc="A dry watercourse cut into the desert, a man's height deep: the only dead ground for miles.")
T("tomb", "turtleback tomb", "∩", (175, 170, 150), (85, 82, 72), walk=False, see=False, cover=95, hp=1400,
  armor=220, into="rubble_heavy", tall=True,
  desc="An Okinawan family tomb, stone and concrete, its shape a womb or a turtle's back. The Japanese fought from "
       "them; the families' bones were inside.")

# ------------------------------------------------------------------ landmarks and places (landmarks.py)
variant("tree", "poplar", "poplar", fg=(75, 130, 55), bg=(24, 48, 20), hp=200,
        desc="A Lombardy poplar, one of a line planted along the road so the marching columns had shade.")
T("gravel", "gravel", "·:·∙", (190, 180, 160), (88, 84, 74), cost=95, sound=3, into="gravel", vcost=65,
  desc="Raked gravel. Every footstep crunches.")
T("wall_white", "whitewashed wall", "#", (232, 226, 212), (150, 145, 132), walk=False, see=False, cover=100,
  tall=True, hp=800, armor=150, into="rubble", crush=3, sound=28, hard=True)
T("sail", "windmill sail", "\\", (200, 185, 150), (40, 38, 30), cost=100, hp=60, armor=4, into="rubble_wood",
  flam=40, burnt="burnt", desc="A sail of the windmill, a lattice of laths turning slowly overhead.")
T("sail2", "windmill sail", "/", (200, 185, 150), (40, 38, 30), cost=100, hp=60, armor=4, into="rubble_wood",
  flam=40, burnt="burnt", desc="A sail of the windmill, a lattice of laths turning slowly overhead.")
T("platform", "railway platform", ".·", (190, 185, 175), (96, 94, 90), cost=95, hard=True, sound=3, hp=800,
  armor=100, into="rubble_light", vcost=70, desc="The platform: a timetable, a bench, and nobody waiting.")
T("boxcar", "goods wagon", "▬", (155, 82, 58), (62, 36, 26), walk=False, see=False, cover=80, tall=True, hp=700,
  armor=35, into="wreck", flam=35, burnt="wreck", crush=9, hard=True,
  desc="A goods wagon on the siding: 'Hommes 40, Chevaux 8', or the German or Russian for it.")
T("locomotive", "locomotive", "◙", (80, 80, 84), (30, 30, 32), walk=False, see=False, cover=98, tall=True,
  hp=4000, armor=300, into="wreck", crush=9, hard=True,
  desc="A steam engine, strafed and dead on the rails. Its boiler stops anything short of a shell.")
T("water_tower", "water tower", "Ŧ", (170, 160, 140), (58, 54, 48), walk=False, see=True, cover=35, tall=True,
  hp=900, armor=60, into="rubble_heavy", crush=9, hard=True,
  desc="A water tower on steel legs, a tank on top: the highest thing for miles, and every gunner's aiming mark.")
T("chimney", "factory chimney", "●", (180, 95, 75), (82, 42, 34), walk=False, see=False, cover=100, tall=True,
  hp=2500, armor=180, into="rubble_heavy", crush=9, hard=True,
  desc="A brick chimney, a hundred feet tall. The artillery registers on it; so do the snipers.")
T("silo", "grain silo", "Θ", (195, 192, 182), (104, 102, 96), walk=False, see=False, cover=100, tall=True,
  hp=6000, armor=500, into="rubble_heavy", crush=9, hard=True,
  desc="A concrete silo full of grain. Walls a foot thick: it stops anything.")
T("calvary", "wayside cross", "†", (205, 200, 185), (62, 58, 50), walk=False, see=True, cover=35, tall=True,
  hp=400, armor=90, into="rubble", crush=3, hard=True,
  desc="A stone cross at the roadside, flowers at its foot. Every map in the army marks it.")
T("memorial", "war memorial", "‡", (215, 210, 195), (82, 78, 70), walk=False, see=True, cover=75, tall=True,
  hp=1500, armor=220, into="rubble", crush=9, hard=True,
  desc="The memorial to the last war: a stone soldier and a column of names, the same surnames as the shop signs.")
T("fountain", "fountain", "☼", (150, 190, 230), (82, 82, 86), walk=False, see=True, cover=65, hp=1400, armor=200,
  into="rubble", crush=9, hard=True, desc="A stone basin and a spout. The water still runs.")
T("vault", "family vault", "⌂", (190, 186, 172), (78, 76, 70), walk=False, see=False, cover=95, tall=True, hp=1600,
  armor=240, into="rubble_heavy", crush=9, hard=True,
  desc="A stone family vault with an iron door. Better cover than anything the living built.")
T("timber", "stacked timber", "≡", (175, 135, 85), (72, 52, 32), walk=False, see=False, cover=75, tall=True,
  hp=500, armor=45, into="rubble_wood", flam=45, burnt="burnt", crush=3,
  desc="Sawn logs stacked head-high to season.")
T("sangar", "sangar", "∩", (180, 165, 135), (92, 82, 64), cost=260, cover=72, pos_cover=30, hp=500, armor=140,
  into="rubble", crush=2, hard=True,
  desc="A breastwork of piled stones, where the ground's too hard to dig. Splinters fly off it.")
T("torii", "torii gate", "π", (215, 72, 52), (62, 42, 34), cost=100, cover=10, tall=True, hp=300, armor=40,
  into="rubble_wood", flam=30, burnt="burnt", desc="A red gate of two posts and two beams: the way into the shrine.")
T("stupa", "stupa", "▲", (232, 218, 172), (112, 102, 82), walk=False, see=False, cover=100, tall=True, hp=3000,
  armor=260, into="rubble_heavy", crush=9, hard=True,
  desc="A whitewashed stupa with a gilt spire, a relic sealed inside. The Japanese dug in under them.")
T("oil_tank", "oil storage tank", "O", (172, 172, 166), (66, 66, 64), walk=False, see=False, cover=70, tall=True,
  hp=500, armor=25, into="crater_big", flam=95, burnt="crater_big", crush=9, hard=True,
  desc="A storage tank of fuel oil. One tracer round, and it goes up like the end of the world.")
T("radar", "radar dish", "¤", (195, 200, 195), (54, 58, 54), walk=False, see=True, cover=30, tall=True, hp=350,
  armor=15, into="rubble_light", crush=2,
  desc="A Würzburg radar dish, twenty feet across, on a turntable. It tracks the bombers.")
T("pole", "telegraph pole", "ǂ", (145, 115, 80), (40, 32, 22), walk=False, see=True, cover=10, tall=True, hp=90,
  armor=15, into="dirt", flam=20, burnt="burnt", crush=1,
  desc="A telegraph pole. Follow the wire and you'll find a road, a railway or a headquarters.")
T("tobruk", "Tobruk pit", "Ø", (178, 178, 170), (72, 72, 68), cost=160, pos_cover=88, conceal=45, hard=True,
  hp=3000, armor=500, into="crater",
  desc="A Ringstand: a concrete pit for one machine gun or mortar, a round hole open to the sky.")
T("slag", "slag heap", "^∙^·", (95, 90, 88), (36, 34, 34), cost=230, pos_cover=25, conceal=10, sound=2, into="slag",
  desc="A black hill of mine spoil. Every step slides back half of it.")
T("bracken", "bracken", "\";\",", (140, 150, 70), (44, 52, 24), cost=125, conceal=50, flam=45, dig=True,
  into="grass", burnt="burnt", desc="Waist-high bracken. Lie down in it and you're gone.")

# ------------------------------------------------------------------ parked aircraft, at their real size (parked.py)
T("ac_body", "aircraft fuselage", "█", (150, 155, 140), (60, 62, 56), walk=False, see=False, cover=25, tall=True,
  hp=160, armor=6, into="ac_wreck", burnt="ac_wreck", flam=60, crush=2,
  desc="The fuselage of a parked aircraft: thin alloy skin over the frames. A bullet goes in one side and out the "
       "other.")
T("ac_engine", "aircraft engine", "◘", (120, 120, 118), (50, 50, 48), walk=False, see=False, cover=70, tall=True,
  hp=320, armor=25, into="ac_wreck", burnt="ac_wreck", flam=60, crush=3,
  desc="An engine in its cowling, a ton of steel and alloy: the one part of an aircraft that stops a bullet.")
T("ac_wing", "aircraft wing", "▒", (165, 168, 155), (58, 60, 54), cost=260, see=True, cover=10, conceal=20,
  hp=120, armor=3, into="ac_wreck", burnt="ac_wreck", flam=70, crush=1,
  desc="A wing, with the fuel tanks in it. You can duck under it, slowly.")
T("ac_tail", "tailplane", "▬", (160, 162, 150), (58, 60, 54), cost=200, see=True, cover=5, hp=70, armor=2,
  into="ac_wreck", burnt="ac_wreck", flam=30, crush=1, desc="The tailplane and the fin, chest-high.")
T("ac_wreck", "burnt-out aircraft", "%&%;", (100, 95, 88), (34, 32, 30), cost=240, see=True, cover=25, pos_cover=15,
  conceal=10, into="ac_wreck", desc="Twisted, blackened alloy and a melted engine - what's left of an aircraft.")

NUM = len(DEFS)

# ------------------------------------------------------------------ lookup arrays
WALK = np.array([d.walk for d in DEFS], bool)
SEE = np.array([d.see for d in DEFS], bool)
# what a man sitting high - a tank commander, the periscopes, a man riding on the hull or standing in a
# half-track - sees over that a man on the ground doesn't: crops, undergrowth, garden hedges, hay, crates
LOW_SCREEN = ("corn", "sunflower", "bush", "bush_snow", "garden_hedge", "hay", "crates", "ammo_stack", "vineyard",
              "sugarcane", "reeds")
SEE_HIGH = SEE | np.array([d.key in LOW_SCREEN for d in DEFS], bool)
COST = np.array([d.cost for d in DEFS], np.int32)
COVER = np.array([d.cover for d in DEFS], np.int16)
TALL = np.array([d.tall for d in DEFS], bool)
HP = np.array([d.hp for d in DEFS], np.int32)
ARMOR = np.array([d.armor for d in DEFS], np.int32)
FLAM = np.array([d.flam for d in DEFS], np.int16)
WATER = np.array([d.water for d in DEFS], np.int8)
POS_COVER = np.array([d.pos_cover for d in DEFS], np.int16)
CONCEAL = np.array([d.conceal for d in DEFS], np.int16)
DIG = np.array([d.dig for d in DEFS], bool)
CRUSH = np.array([d.crush for d in DEFS], np.int8)
FLOOR = np.array([d.floor for d in DEFS], bool)
DOOR = np.array([d.door for d in DEFS], np.int8)
SOUND = np.array([d.sound for d in DEFS], np.int16)
WINDOW = np.array([d.window for d in DEFS], bool)
HARD = np.array([d.hard for d in DEFS], bool)
VCOST = np.array([d.vcost if d.vcost is not None else d.cost for d in DEFS], np.int32)
INTO = np.array([ID[d.into] if d.into else d.id for d in DEFS], np.int32)
BURNT = np.array([ID[d.burnt] if d.burnt else d.id for d in DEFS], np.int32)

MAXV = 5
GLYPHS = np.zeros((NUM, MAXV), np.int32)
for _d in DEFS:
    gs = _d.glyphs
    for _i in range(MAXV):
        GLYPHS[_d.id, _i] = ord(gs[_i % len(gs)])
FG = np.array([d.fg for d in DEFS], np.int16)
BG = np.array([d.bg for d in DEFS], np.int16)


EXPLODE[ID["ammo_stack"]] = (320, 5, 1)
EXPLODE[ID["fuel_drums"]] = (160, 3, 3)
EXPLODE[ID["plane_parked"]] = (140, 3, 3)
EXPLODE[ID["ammo_rack"]] = (600, 6, 2)
EXPLODE[ID["avgas"]] = (450, 5, 5)
EXPLODE[ID["oil_tank"]] = (260, 5, 6)
EXPLODE[ID["ac_body"]] = (90, 2, 4)            # fuel, ammunition, sometimes the bombs
EXPLODE[ID["ac_wing"]] = (60, 2, 5)            # the fuel tanks


def tid(key: str) -> int:
    return ID[key]


def tdef(i: int) -> TileDef:
    return DEFS[int(i)]
