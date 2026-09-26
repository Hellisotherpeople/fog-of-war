"""Soldier figures, painted from what each man is actually wearing and carrying.

A figure is drawn side-on (the classic roguelike tileset convention over a top-down
map) on a 32x32 logical grid, painted at 96x96 and outlined so it reads against
any ground.  Everything comes from the soldier's kit:

  headgear    the actual helmet or cap item (M1, Brodie, Stahlhelm, SSh-40, Adrian,
              Type 90, M33, wz.31, field cap, peaked cap, tanker's helmet)
  weapon      the model in his hands - a Garand isn't a Kar98k, a Thompson isn't a
              PPSh with its drum, a Bren has its top magazine and a DP its pan
  back        pack, radio and aerial, flamethrower tanks, rocket bag, a slung rifle
  webbing     belt, straps, pouches, stick grenades in the belt, binoculars, the
              medic's armband, greatcoats and snow smocks, field dressings
  pose        standing, kneeling, prone, aiming, hands up, down and bleeding
  facing      left or right, from where he last moved or fired
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 3                    # master pixels per logical pixel
G = 32                   # logical grid
MS = S * G               # master size (96)
OUTLINE = (24, 22, 20)
METAL = (48, 48, 52)
DARKMETAL = (32, 32, 36)
WOOD = (122, 80, 44)
LIGHTWOOD = (150, 105, 60)
WHITE = (236, 236, 230)
RED = (200, 25, 25)

# nation -> (jacket, trousers, helmet, webbing, boots)
UNIFORMS = {
    "usa": ((112, 104, 70), (96, 92, 66), (82, 90, 58), (150, 136, 92), (70, 50, 34)),
    "uk": ((138, 116, 74), (128, 108, 70), (92, 90, 60), (168, 152, 108), (50, 38, 28)),
    "canada": ((132, 112, 72), (124, 104, 68), (92, 90, 60), (160, 146, 104), (50, 38, 28)),
    "australia": ((146, 124, 80), (138, 116, 76), (96, 92, 62), (168, 152, 108), (60, 44, 30)),
    "newzealand": ((138, 116, 74), (128, 108, 70), (92, 90, 60), (168, 152, 108), (50, 38, 28)),
    "india": ((150, 128, 84), (142, 120, 80), (96, 92, 62), (168, 152, 108), (60, 44, 30)),
    "ussr": ((128, 118, 76), (104, 98, 66), (70, 88, 54), (112, 92, 60), (40, 32, 26)),
    "france": ((122, 112, 82), (112, 104, 78), (84, 92, 76), (100, 78, 50), (48, 38, 30)),
    "poland": ((112, 110, 78), (104, 102, 74), (82, 90, 62), (104, 82, 52), (44, 34, 26)),
    "china": ((96, 106, 112), (90, 98, 104), (94, 102, 96), (112, 92, 60), (70, 66, 60)),
    "germany": ((96, 102, 90), (88, 92, 84), (80, 84, 80), (40, 36, 32), (28, 26, 24)),
    "italy": ((124, 120, 94), (116, 112, 88), (102, 106, 86), (82, 66, 46), (50, 40, 30)),
    "japan": ((146, 130, 86), (138, 122, 82), (120, 110, 72), (104, 82, 52), (80, 62, 40)),
    "finland": ((108, 112, 102), (98, 102, 94), (92, 98, 94), (64, 56, 46), (40, 34, 28)),
    "hungary": ((126, 112, 76), (116, 104, 72), (96, 96, 72), (72, 56, 40), (40, 32, 26)),
    "romania": ((122, 116, 86), (112, 108, 80), (92, 96, 76), (72, 56, 40), (40, 32, 26)),
}
DESERT = {"uk": ((190, 166, 116), (184, 160, 112)), "australia": ((190, 166, 116), (184, 160, 112)),
          "newzealand": ((190, 166, 116), (184, 160, 112)), "india": ((190, 166, 116), (184, 160, 112)),
          "germany": ((176, 156, 104), (168, 150, 100)), "italy": ((174, 154, 108), (166, 146, 104)),
          "usa": ((150, 134, 92), (130, 118, 84))}
TROPICAL = {"usa": ((92, 108, 76), (88, 102, 72)), "japan": ((150, 136, 92), (140, 126, 86)),
            "australia": ((96, 108, 74), (90, 102, 70)), "uk": ((92, 104, 72), (88, 98, 68)),
            "india": ((96, 106, 74), (90, 100, 70))}
CREW = {"germany": (36, 36, 40), "ussr": (62, 66, 76), "usa": (104, 100, 72), "uk": (96, 88, 64)}
SKINS = {"india": [(150, 102, 70), (132, 88, 60), (166, 116, 80)],
         "japan": [(214, 178, 132), (200, 164, 120), (222, 188, 142)],
         "china": [(212, 176, 130), (198, 162, 118), (220, 186, 140)]}
SKIN_DEFAULT = [(218, 174, 138), (204, 158, 122), (190, 142, 106), (226, 186, 150)]

HELMET_STYLE = {"helmet_m1": "m1", "helmet_brodie": "brodie", "stahlhelm": "stahlhelm", "ssh40": "ssh",
                "adrian": "adrian", "type90": "type90", "m33_it": "m33", "wz31": "wz31", "tanker_helmet": "tanker",
                "soft_cap": "cap", "peaked_cap": "peaked", None: "bare"}
HELMET_COLOR = {"germany": (78, 82, 78), "usa": (84, 92, 58), "uk": (96, 92, 62), "ussr": (72, 92, 56),
                "japan": (120, 112, 74), "italy": (104, 108, 88), "france": (86, 94, 80), "finland": (82, 90, 84),
                "china": (86, 92, 88), "poland": (84, 92, 64)}

# weapon id -> silhouette
WEAPON_SHAPE = {
    "m1_garand": "garand", "m1903": "rifle", "smle": "smle", "lee_no4": "smle", "mosin": "mosin", "svt40": "svt",
    "kar98k": "k98", "g43": "svt", "carcano": "rifle", "type38": "arisaka", "type99": "arisaka", "mas36": "rifle",
    "lebel": "mosin", "wz29": "k98", "hanyang88": "rifle", "chiang": "k98", "m39": "mosin", "35m": "rifle",
    "vz24": "k98", "m1903a4": "sniper", "lee_no4t": "sniper", "mosin_pu": "sniper", "kar98k_zf": "sniper",
    "type97_sniper": "sniper", "m1_carbine": "carbine", "m44": "carbine",
    "thompson_m1a1": "thompson", "thompson_1928": "thompson_drum", "m3_grease": "grease", "sten": "sten",
    "owen": "owen", "ppsh": "ppsh", "ppd40": "ppsh", "pps43": "pps", "mp40": "mp40", "mp38": "mp40",
    "mab38": "mab", "type100": "type100", "mas38": "mab", "suomi": "suomi", "kiraly": "mab", "orita": "mab",
    "bar": "bar", "bren": "bren", "dp28": "dp", "mg34": "mg34", "mg42": "mg42", "breda30": "breda",
    "type11": "breda", "type96": "bren", "type99_lmg": "bren", "fm2429": "bren", "wz28": "bar", "zb26": "bren",
    "lahti_saloranta": "bren", "solothurn31m": "bren",
    "stg44": "stg", "fg42": "fg42", "m97_trench": "shotgun",
    "boys": "atrifle", "ptrd": "atrifle", "ptrs": "atrifle", "pzb39": "atrifle", "solothurn": "atrifle",
    "type97_at": "atrifle", "ur_wz35": "atrifle", "lahti_l39": "atrifle",
    "bazooka": "bazooka", "panzerschreck": "schreck", "piat": "piat",
    "pzf30k": "faust", "pzf60": "faust", "pzf100": "faust",
    "katana": "katana", "dadao": "sword", "szabla": "sword", "shovel": "shovel",
}
CAT_SHAPE = {"rifle": "rifle", "sniper": "sniper", "carbine": "carbine", "smg": "mp40", "lmg": "bren",
             "hmg": "hmg", "pistol": "pistol", "shotgun": "shotgun", "at_rifle": "atrifle", "assault": "stg",
             "at_launcher": "bazooka", "at_disposable": "faust", "flamer": "flamer", "mortar": "mortar"}


def weapon_shape(item) -> str:
    if item is None:
        return "none"
    t = item.t
    if t.kind == "melee":
        return WEAPON_SHAPE.get(item.tid, "knife")
    if t.kind != "gun":
        return "none"
    return WEAPON_SHAPE.get(item.tid) or CAT_SHAPE.get(t.cat, "rifle")


LONG_ARMS = {"garand", "rifle", "smle", "mosin", "svt", "k98", "arisaka", "sniper", "carbine", "shotgun", "stg",
             "fg42"}


# ====================================================================== the look of a soldier

def look(a, game) -> tuple:
    """Everything visible about a soldier, as a hashable key for the sprite cache."""
    inv = a.invent
    head = inv.slots["head"]
    helm = HELMET_STYLE.get(head.tid if head is not None else None, "m1")
    w = a.weapon
    wshape = weapon_shape(w)
    # something slung on the back that isn't in his hands
    sling = "none"
    for slot in ("primary", "secondary"):
        it = inv.slots[slot]
        if it is not None and it is not w and it.t.kind == "gun":
            sh = weapon_shape(it)
            if sh in LONG_ARMS or sh in ("mp40", "thompson", "ppsh", "bren", "bar", "dp", "atrifle"):
                sling = "long" if sh in LONG_ARMS or sh == "atrifle" else "short"
                break
    pack = inv.slots["pack"]
    back = "none"
    if w is not None and w.t.kind == "gun" and w.t.cat == "flamer":
        back = "flamer"
    elif pack is not None:
        if pack.t.tool == "radio":
            back = "radio"
        elif pack.tid == "sack":
            back = "rocketbag"
        elif pack.tid in ("su_veshmeshok", "jp_haversack", "us_musette", "fr_musette"):
            back = "sack"
        elif pack.tid in ("de_tornister", "de_aframe"):
            back = "tornister"
        else:
            back = "pack"
    if back not in ("radio",) and any(it.t.tool == "radio" for it in inv.items() if it.t.kind == "tool"):
        back = "radio"
    if back == "none" and any(it.t.kind == "gun" and it.t.cat == "mortar" and it is not w for it in inv.items()):
        back = "mortar"
    rig = inv.slots["rig"]
    rigk = "none"
    if rig is not None:
        rigk = "bandolier" if rig.tid in ("bandolier", "su_drum") else "medic" if rig.tid == "medic_bags" else \
            "leather" if rig.tid.startswith("de_") or rig.tid in ("it_giberne", "fr_cartouchieres") else "web"
    body = inv.slots["body"]
    coat = "none"
    if body is not None:
        coat = "smock" if body.tid == "snow_smock" else "coat" if body.tid == "winter_coat" else "none"
    items = inv.items()
    stick = any(it.t.kind == "grenade" and it.t.gtype == "stick" for it in items)
    frag = any(it.t.kind == "grenade" and it.t.gtype in ("frag", "gammon") for it in items)
    binos = any(it.t.tool == "binoculars" for it in items)
    shovel = any(it.tid == "shovel" for it in items) and wshape != "shovel"
    medic = a.role == "medic"
    b = a.body
    bandaged = any(wd.bandaged for wd in b.wounds)
    bleeding = b.bleed_rate() > 1.0
    # pose
    if a.state == "surrendered":
        pose = "hands_up"
    elif a.downed:
        pose = "downed"
    else:
        aiming = a.fired_turn >= game.turn - 2 or (a.aim_turns > 0 and a.aim_target is not None)
        base = {0: "stand", 1: "kneel", 2: "prone"}[a.stance]
        pose = base + ("_aim" if aiming and wshape != "none" else "")
    face = 1 if getattr(a, "face", 1) >= 0 else -1
    clim = game.map.climate if getattr(game, "map", None) is not None else "summer"
    crew = a.role == "tank_crew"
    skin = a.id % len(SKINS.get(a.nation, SKIN_DEFAULT))
    return (a.nation, clim, crew, skin, helm, wshape, sling, back, rigk, coat, stick, frag, binos, shovel, medic,
            bandaged, bleeding, pose, face)


# ====================================================================== drawing

class Fig:
    """A little drawing surface in logical units."""

    def __init__(self):
        self.img = Image.new("RGBA", (MS, MS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    @staticmethod
    def _p(pts):
        return [(x * S, y * S) for x, y in pts]

    def rect(self, x0, y0, x1, y1, col):
        self.d.rectangle((x0 * S, y0 * S, x1 * S - 1, y1 * S - 1), fill=tuple(col) + (255,))

    def ell(self, x0, y0, x1, y1, col):
        self.d.ellipse((x0 * S, y0 * S, x1 * S - 1, y1 * S - 1), fill=tuple(col) + (255,))

    def poly(self, pts, col):
        self.d.polygon(self._p(pts), fill=tuple(col) + (255,))

    def line(self, pts, col, w=1.0):
        self.d.line(self._p(pts), fill=tuple(col) + (255,), width=max(1, int(round(w * S))))
        r = w * S / 2
        for x, y in self._p(pts):          # round joints
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(col) + (255,))

    def part(self, origin, ang, shapes, su=1.0, sv=1.0):
        """Draw a rigid object (a weapon) given in its own (u along it, v across it) coordinates."""
        ox, oy = origin
        ca, sa = math.cos(ang), math.sin(ang)

        def tr(u, v):
            u *= su
            v *= sv
            return ox + u * ca - v * sa, oy + u * sa + v * ca
        for kind, geo, col in shapes:
            if kind == "box":
                u0, v0, u1, v1 = geo
                self.poly([tr(u0, v0), tr(u1, v0), tr(u1, v1), tr(u0, v1)], col)
            elif kind == "poly":
                self.poly([tr(u, v) for u, v in geo], col)
            elif kind == "disc":
                u, v, r = geo
                x, y = tr(u, v)
                r *= sv
                self.ell(x - r, y - r, x + r, y + r, col)
            elif kind == "line":
                self.line([tr(u, v) for u, v in geo[:-1]], col, geo[-1] * sv)


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


# weapon shapes in (u, v): u from the grip forward, v down; the hands hold it at u=0 (trigger) and u=grip2
def weapon_parts(shape):
    W, Wl, M, D = WOOD, LIGHTWOOD, METAL, DARKMETAL
    if shape in ("rifle", "k98", "arisaka", "mosin", "smle", "garand", "svt"):
        L = {"mosin": 14.5, "arisaka": 14.5, "k98": 13, "smle": 12.5, "garand": 12.5, "svt": 12.5}.get(shape, 13)
        parts = [("poly", [(-5.5, -0.2), (0, -0.5), (0, 0.9), (-2, 1.1), (-5.5, 1.9)], W),   # stock
                 ("box", (0, -0.5, 4.5, 0.6), M),                                            # receiver
                 ("box", (1, 0.0, L - 3, 0.9), W if shape != "svt" else Wl),                 # handguard
                 ("box", (4, -0.35, L, 0.2), D)]                                             # barrel
        if shape == "smle":
            parts.append(("box", (L - 1.2, -0.4, L, 0.5), D))                                # snub nose
        if shape == "garand":
            parts.append(("box", (0.3, 0.6, 2.0, 1.1), M))                                   # clip well
        if shape == "svt":
            parts.append(("box", (0.5, 0.6, 1.8, 2.2), D))                                   # box magazine
        if shape == "k98":
            parts.append(("line", [(1.2, -0.5), (1.8, -1.3), 0.5], M))                       # bolt handle
        return parts, 5.0
    if shape == "sniper":
        return [("poly", [(-5.5, -0.2), (0, -0.5), (0, 0.9), (-2, 1.1), (-5.5, 1.9)], W),
                ("box", (0, -0.5, 4.5, 0.6), M), ("box", (1, 0.0, 10, 0.9), W), ("box", (4, -0.35, 13.5, 0.2), D),
                ("box", (0.2, -1.9, 4.4, -0.8), D), ("box", (-0.2, -2.1, 0.4, -0.7), D),
                ("box", (4.2, -2.1, 4.8, -0.7), D)], 5.0
    if shape == "carbine":
        return [("poly", [(-4.5, -0.2), (0, -0.4), (0, 0.8), (-1.6, 1.0), (-4.5, 1.6)], W),
                ("box", (0, -0.4, 3.5, 0.5), M), ("box", (1, 0.0, 7.5, 0.8), W), ("box", (3, -0.3, 9.5, 0.15), D),
                ("box", (1.0, 0.5, 2.0, 2.0), D)], 4.0
    if shape == "shotgun":
        return [("poly", [(-5, -0.2), (0, -0.5), (0, 0.9), (-2, 1.1), (-5, 1.9)], W), ("box", (0, -0.6, 4, 0.7), M),
                ("box", (3, -0.4, 10.5, 0.1), D), ("box", (4, 0.1, 9.5, 0.6), D), ("box", (5, 0.2, 7.5, 1.2), W)], 6.0
    if shape in ("thompson", "thompson_drum"):
        p = [("poly", [(-4.5, 0), (0, -0.3), (0, 0.9), (-4.5, 1.8)], W), ("box", (0, -0.6, 5, 0.8), M),
             ("box", (5, -0.4, 8.5, 0.3), D), ("box", (3.6, 0.6, 4.6, 2.4), W)]
        if shape == "thompson_drum":
            p.append(("disc", (2.0, 2.2, 1.8), D))
        else:
            p.append(("box", (1.4, 0.7, 2.4, 3.6), D))
        return p, 4.0
    if shape == "grease":
        return [("line", [(-4, 0.6), (0, 0.4), 0.5], M), ("box", (0, -0.7, 4.5, 0.8), M),
                ("box", (4.5, -0.3, 6.5, 0.3), D), ("box", (0.6, 0.7, 1.5, 3.8), D)], 3.0
    if shape == "sten":
        return [("line", [(-4, 0.2), (-4, 1.4), (0, 0.4), 0.45], M), ("box", (0, -0.5, 5, 0.6), D),
                ("box", (5, -0.25, 7, 0.25), D), ("box", (1.5, -3.8, 2.3, -0.5), D)], 3.5
    if shape == "owen":
        return [("line", [(-4, 0.6), (0, 0.3), 0.6], M), ("box", (0, -0.6, 5.5, 0.7), M), ("box", (1.2, -3.5, 2.2, -0.6), D),
                ("box", (5.5, -0.3, 7.5, 0.3), D)], 4.0
    if shape in ("ppsh", "pps"):
        p = [("poly", [(-4.5, 0), (0, -0.4), (0, 0.9), (-4.5, 1.9)], W) if shape == "ppsh" else
             ("line", [(-4, 0.2), (-4, 1.4), (0, 0.4), 0.45], M),
             ("box", (0, -0.7, 5.5, 0.7), D), ("box", (5.5, -0.3, 7.2, 0.3), D)]
        p.append(("disc", (1.8, 2.0, 1.9), D) if shape == "ppsh" else ("poly", [(1.2, 0.7), (2.2, 0.7), (3.0, 3.8), (2.0, 4.0)], D))
        return p, 4.0
    if shape in ("mp40", "mab", "type100", "suomi"):
        wood = shape in ("mab", "type100", "suomi")
        p = [("poly", [(-4.5, 0), (0, -0.4), (0, 0.9), (-4.5, 1.8)], W) if wood else
             ("line", [(-4.5, 0.3), (-4.5, 1.2), (0, 0.5), 0.45], D),
             ("box", (0, -0.6, 5, 0.6), D), ("box", (5, -0.25, 7.3, 0.25), D)]
        if shape == "suomi":
            p.append(("disc", (2.0, 2.0, 1.8), D))
        else:
            p.append(("box", (1.8, 0.6, 2.8, 4.4), D))
        return p, 4.2
    if shape in ("stg", "fg42"):
        return [("poly", [(-4.5, -0.2), (0, -0.3), (0, 0.9), (-4.5, 1.7)], W), ("box", (0, -0.7, 5.5, 0.6), D),
                ("box", (5.5, -0.25, 9, 0.2), D), ("poly", [(1.6, 0.6), (2.6, 0.6), (3.6, 3.2), (2.6, 3.6)], D)] if shape == "stg" else \
            [("line", [(-4.5, 0.2), (0, 0.2), 0.8], M), ("box", (0, -0.7, 5, 0.6), D), ("box", (5, -0.25, 9, 0.2), D),
             ("box", (1.4, -3.0, 2.2, -0.6), D), ("line", [(6.5, 0.3), (8, 2.8), 0.35], D)], 5.0
    if shape in ("bren", "bar", "dp", "breda"):
        p = [("poly", [(-5, -0.3), (0, -0.6), (0, 1.0), (-5, 1.9)], W if shape != "bren" else DARKMETAL),
             ("box", (0, -0.8, 6, 0.8), D), ("box", (6, -0.3, 11, 0.3), D),
             ("line", [(8.5, 0.3), (7.8, 3.2), 0.35], D), ("line", [(8.5, 0.3), (9.4, 3.2), 0.35], D)]      # bipod
        if shape == "bren":
            p += [("poly", [(1.6, -0.8), (3.2, -0.8), (4.4, -4.2), (3.2, -4.4)], D), ("box", (-0.2, 0.7, 0.6, 2.0), D)]
        elif shape == "bar":
            p += [("box", (1.6, 0.7, 3.2, 2.8), D)]
        elif shape == "dp":
            p += [("poly", [(0.2, -1.0), (5.2, -1.0), (4.8, -2.0), (0.6, -2.0)], D)]
        else:
            p += [("box", (1.0, -1.8, 3.8, -0.8), D)]
        return p, 6.0
    if shape in ("mg34", "mg42"):
        p = [("poly", [(-5, -0.2), (0, -0.5), (0, 0.9), (-5, 1.7)], D), ("box", (0, -0.7, 7, 0.8), D),
             ("box", (7, -0.35, 11.5, 0.35), D), ("line", [(9, 0.3), (8.2, 3.2), 0.35], D),
             ("line", [(9, 0.3), (9.8, 3.2), 0.35], D)]
        if shape == "mg42":
            p.append(("box", (5, -0.6, 9, 0.6), M))                 # the ventilated jacket
        # the belt hanging from the feed tray
        p.append(("line", [(1.5, 0.8), (1.0, 2.2), (1.8, 3.4), 0.6], (150, 120, 50)))
        return p, 6.0
    if shape == "hmg":
        return [("box", (-2, -0.8, 1.5, 1.2), D), ("box", (1.5, -1.2, 9, 1.0), M), ("box", (9, -0.3, 12, 0.3), D),
                ("line", [(1.5, 0.6), (1.0, 2.4), (2.0, 3.6), 0.6], (150, 120, 50))], 4.5
    if shape == "atrifle":
        return [("poly", [(-5, -0.2), (0, -0.4), (0, 1.0), (-5, 1.8)], W), ("box", (0, -0.6, 5, 0.7), M),
                ("box", (5, -0.3, 17, 0.3), D), ("box", (16, -0.7, 17.5, 0.7), D),
                ("line", [(9, 0.3), (8.4, 2.8), 0.35], D), ("line", [(9, 0.3), (9.6, 2.8), 0.35], D)], 6.0
    if shape == "pistol":
        return [("box", (0, -0.6, 3.2, 0.4), D), ("poly", [(0, 0), (0.9, 0), (0.5, 1.8), (-0.4, 1.7)], D)], 0.0
    if shape == "bazooka":
        return [("box", (-6, -0.9, 10, 0.9), (82, 92, 58)), ("box", (-6.4, -1.1, -5.4, 1.1), (60, 68, 44)),
                ("box", (0.3, 0.8, 1.2, 2.4), D), ("box", (3.4, 0.8, 4.2, 2.2), W)], 3.5
    if shape == "schreck":
        return [("box", (-6, -1.0, 10, 1.0), (84, 88, 80)), ("box", (3.0, -4.2, 4.0, -1.0), (74, 78, 70)),
                ("box", (0.3, 0.9, 1.2, 2.4), D)], 3.5
    if shape == "piat":
        return [("box", (-4, -1.0, 6, 1.2), (70, 76, 56)), ("poly", [(6, -0.6), (9, -0.9), (9, 0.9), (6, 0.8)], (60, 66, 48)),
                ("box", (-1, 1.0, 0, 2.6), D), ("box", (-5, -0.4, -4, 1.2), (60, 66, 48))], 3.0
    if shape == "faust":
        return [("box", (-4, -0.35, 5, 0.35), (86, 94, 60)), ("disc", (6.3, 0, 1.7), (70, 80, 50)),
                ("poly", [(7.8, -0.9), (9.0, 0), (7.8, 0.9)], (60, 70, 44)), ("box", (0.8, -1.4, 1.8, -0.35), (200, 60, 40))], 3.0
    if shape == "flamer":
        return [("line", [(-1, 0.2), (10, 0.2), 0.7], M), ("box", (9.5, -0.5, 11, 0.9), D), ("box", (0, 0.4, 1, 2.0), D),
                ("disc", (11.3, 0.2, 0.5), (255, 150, 40))], 4.0
    if shape == "mortar":
        return [("box", (-3, -1.0, 7, 1.0), (72, 80, 60)), ("box", (-3.8, -1.6, -3, 1.6), D)], 3.0
    if shape == "katana":
        return [("box", (-2.5, -0.35, 0.8, 0.35), (40, 30, 30)), ("box", (0.8, -0.8, 1.1, 0.8), (190, 160, 60)),
                ("poly", [(1.1, -0.3), (12, -0.6), (12.8, -0.9), (12, 0.1), (1.1, 0.25)], (215, 218, 224))], 0.0
    if shape == "sword":
        return [("box", (-1.5, -0.35, 0.8, 0.35), (60, 40, 30)), ("box", (0.8, -0.9, 1.1, 0.9), (170, 150, 60)),
                ("poly", [(1.1, -0.4), (10, -0.6), (11, 0), (1.1, 0.4)], (205, 208, 214))], 0.0
    if shape == "shovel":
        return [("line", [(-4, 0), (4, 0), 0.6], W), ("poly", [(4, -1.2), (7, -1.0), (7.6, 0), (7, 1.0), (4, 1.2)], (76, 80, 70))], 0.0
    if shape == "knife":
        return [("box", (-1.5, -0.35, 0.5, 0.35), (70, 50, 36)), ("poly", [(0.5, -0.4), (4.5, -0.2), (5, 0.1), (0.5, 0.4)], (200, 204, 210))], 0.0
    return [], 0.0


HEAVY = {"bren", "bar", "dp", "breda", "mg34", "mg42", "hmg", "atrifle"}
WU, WV = 1.28, 1.35          # weapons drawn larger than life, so the model reads at tile size
KH = 1.32                    # and so are heads (the helmet is the best clue to the army)
SHOULDER = {"bazooka", "schreck", "piat", "mortar"}


def paint_figure(key) -> np.ndarray:
    (nation, clim, crew, skin_i, helm, wshape, sling, back, rigk, coat, stick, frag, binos, shovel, medic,
     bandaged, bleeding, pose, face) = key
    jacket, trousers, helmc, webc, boots = UNIFORMS.get(nation, UNIFORMS["usa"])
    if clim == "desert" and nation in DESERT:
        jacket, trousers = DESERT[nation]
    elif clim == "tropical" and nation in TROPICAL:
        jacket, trousers = TROPICAL[nation]
    if crew:
        jacket = trousers = CREW.get(nation, shade(jacket, 0.8))
    helmc = HELMET_COLOR.get(nation, helmc)
    if clim == "desert" and helm in ("stahlhelm", "brodie", "m33"):
        helmc = mix(helmc, (170, 150, 100), 0.6)          # sand paint
    if coat == "smock":
        jacket = (226, 228, 232)
        trousers = mix(trousers, (214, 216, 220), 0.7)
        helmc = mix(helmc, (230, 232, 236), 0.75)
    elif coat == "coat":
        jacket = shade(mix(jacket, (110, 104, 88), 0.3), 0.92)
    skin = (SKINS.get(nation, SKIN_DEFAULT))[skin_i % len(SKINS.get(nation, SKIN_DEFAULT))]
    f = Fig()
    if pose == "prone" or pose == "prone_aim":
        _prone(f, key, jacket, trousers, helmc, webc, boots, skin)
    elif pose == "downed":
        _downed(f, key, jacket, trousers, helmc, webc, boots, skin)
    else:
        _upright(f, key, jacket, trousers, helmc, webc, boots, skin)
    img = f.img
    if face < 0:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return _finish(img, pose)


def _finish(img, pose):
    """Dark outline for contrast, and a soft shadow on the ground."""
    a = img.split()[3]
    grow = a.filter(ImageFilter.MaxFilter(S * 2 + 1 if S % 2 else S * 2 - 1))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    # shadow
    sh = Image.new("L", img.size, 0)
    ds = ImageDraw.Draw(sh)
    if pose in ("prone", "prone_aim", "downed"):
        ds.ellipse((3 * S, 25.5 * S, 29 * S, 30.5 * S), fill=110)
    else:
        ds.ellipse((8 * S, 28.2 * S, 24 * S, 31.2 * S), fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(S * 0.8))
    out.paste((0, 0, 0, 255), (0, 0), sh)
    ol = Image.new("RGBA", img.size, OUTLINE + (255,))
    out.paste(ol, (0, 0), grow)
    out.alpha_composite(img)
    return np.asarray(out, np.uint8).copy()


def _head(f, hx, hy, skin, helm, helmc, medic, bandage=False, nation="", k=KH):
    """Head at (hx, hy) = centre, facing right; k scales it."""
    f.ell(hx - 2.6 * k, hy - 2.6 * k, hx + 2.6 * k, hy + 2.8 * k, skin)
    f.rect(hx + 1.2 * k, hy - 0.4 * k, hx + 2.3 * k, hy + 0.3 * k, shade(skin, 0.55))          # eye / brow shadow
    f.rect(hx - 0.8 * k, hy + 2.2 * k, hx + 1.8 * k, hy + 3.4 * k, shade(skin, 0.85))          # chin/neck
    c = helmc
    hi = shade(c, 1.18)
    lo = shade(c, 0.72)
    if helm == "m1":
        f.ell(hx - 3.3 * k, hy - 4.2 * k, hx + 3.3 * k, hy + 1.2 * k, c)
        f.rect(hx - 3.6 * k, hy + 0.2 * k, hx + 3.6 * k, hy + 1.1 * k, lo)
        f.ell(hx - 1.8 * k, hy - 3.6 * k, hx + 0.4 * k, hy - 2.2 * k, hi)
    elif helm == "brodie":
        f.ell(hx - 2.4 * k, hy - 4.0 * k, hx + 2.4 * k, hy + 0.2 * k, c)
        f.ell(hx - 4.6 * k, hy - 1.0 * k, hx + 4.6 * k, hy + 0.9 * k, lo)
        f.ell(hx - 1.2 * k, hy - 3.4 * k, hx + 0.4 * k, hy - 2.4 * k, hi)
    elif helm in ("stahlhelm", "wz31"):
        f.ell(hx - 3.1 * k, hy - 4.2 * k, hx + 3.1 * k, hy + 0.8 * k, c)
        # the flared skirt, low at the back and over the ears
        f.poly([(hx - 3.4 * k, hy - 0.8 * k), (hx + 3.2 * k, hy - 0.6 * k), (hx + 3.4 * k, hy + 0.3 * k), (hx - 1.0 * k, hy + 0.4 * k),
                (hx - 3.8 * k, hy + 2.0 * k)], lo)
        f.ell(hx - 1.6 * k, hy - 3.6 * k, hx + 0.4 * k, hy - 2.4 * k, hi)
    elif helm == "ssh":
        f.ell(hx - 3.2 * k, hy - 4.4 * k, hx + 3.2 * k, hy + 1.2 * k, c)
        f.poly([(hx - 3.5 * k, hy + 0.0 * k), (hx + 3.3 * k, hy + 0.1 * k), (hx + 3.5 * k, hy + 0.9 * k), (hx - 3.6 * k, hy + 1.2 * k)], lo)
        f.ell(hx - 1.8 * k, hy - 3.8 * k, hx + 0.2 * k, hy - 2.6 * k, hi)
    elif helm == "adrian":
        f.ell(hx - 3.0 * k, hy - 4.0 * k, hx + 3.0 * k, hy + 0.8 * k, c)
        f.poly([(hx - 4.2 * k, hy + 0.6 * k), (hx - 2.8 * k, hy - 0.4 * k), (hx + 2.8 * k, hy - 0.4 * k), (hx + 4.4 * k, hy + 0.2 * k),
                (hx + 3.2 * k, hy + 0.9 * k), (hx - 3.2 * k, hy + 1.0 * k)], lo)
        f.poly([(hx - 1.2 * k, hy - 4.1 * k), (hx + 0.8 * k, hy - 5.2 * k), (hx + 1.6 * k, hy - 4.0 * k)], lo)     # crest
    elif helm == "type90":
        f.ell(hx - 2.9 * k, hy - 4.0 * k, hx + 2.9 * k, hy + 0.6 * k, c)
        f.rect(hx - 3.1 * k, hy - 0.1 * k, hx + 3.1 * k, hy + 0.6 * k, lo)
        f.poly([(hx + 0.5 * k, hy - 3.2 * k), (hx + 1.1 * k, hy - 2.2 * k), (hx - 0.1 * k, hy - 2.2 * k)], (220, 190, 60))
    elif helm == "m33":
        f.ell(hx - 3.1 * k, hy - 4.2 * k, hx + 3.1 * k, hy + 1.0 * k, c)
        f.poly([(hx + 2.0 * k, hy - 0.2 * k), (hx + 4.0 * k, hy + 0.3 * k), (hx + 2.6 * k, hy + 0.8 * k)], lo)       # short visor
        f.ell(hx - 1.6 * k, hy - 3.6 * k, hx + 0.4 * k, hy - 2.4 * k, hi)
    elif helm == "tanker":
        f.ell(hx - 3.0 * k, hy - 3.8 * k, hx + 3.0 * k, hy + 1.6 * k, (70, 58, 44))
        for k in (-1.2, 0.4, 2.0):
            f.line([(hx - 2.2 * k, hy + k - 2.0), (hx + 2.2 * k, hy + k - 2.0)], (50, 40, 30), 0.35)
        f.rect(hx + 0.6 * k, hy - 1.4 * k, hx + 3.0 * k, hy - 0.2 * k, (120, 130, 110))                   # goggles
    elif helm == "cap":
        f.poly([(hx - 3.0 * k, hy - 1.6 * k), (hx - 2.2 * k, hy - 3.8 * k), (hx + 2.6 * k, hy - 3.2 * k), (hx + 3.0 * k, hy - 1.4 * k)], c)
        f.rect(hx - 3.0 * k, hy - 1.9 * k, hx + 3.0 * k, hy - 1.2 * k, lo)
    elif helm == "peaked":
        f.poly([(hx - 3.2 * k, hy - 1.4 * k), (hx - 3.6 * k, hy - 4.6 * k), (hx + 3.2 * k, hy - 4.2 * k), (hx + 2.8 * k, hy - 1.4 * k)], c)
        f.rect(hx - 3.2 * k, hy - 1.9 * k, hx + 2.9 * k, hy - 1.1 * k, shade(c, 0.5))
        f.poly([(hx + 1.4 * k, hy - 1.4 * k), (hx + 4.4 * k, hy - 0.8 * k), (hx + 1.6 * k, hy - 0.6 * k)], (30, 28, 26))  # visor
        f.rect(hx - 0.2 * k, hy - 3.3 * k, hx + 1.0 * k, hy - 2.5 * k, (210, 180, 70))                    # badge
    # the details that tell one army from another at a glance
    if helm == "m1" and nation in ("usa",):
        for dx, dy in ((-2.2, -2.8), (-0.6, -3.6), (1.0, -3.0), (2.2, -1.8), (-1.4, -1.4), (0.4, -2.0)):
            f.rect(hx + dx * k, hy + dy * k, hx + (dx + 0.7) * k, hy + (dy + 0.5) * k, shade(c, 0.6))   # netting
    if helm == "ssh":
        f.poly([(hx - 3.9 * k, hy + 1.6 * k), (hx - 3.5 * k, hy + 0.0 * k), (hx - 2.4 * k, hy + 0.9 * k)], lo)
    if nation == "ussr" and helm in ("ssh", "cap"):
        sx, sy = (hx + 1.3 * k, hy - 2.2 * k) if helm == "ssh" else (hx + 1.6 * k, hy - 2.2 * k)
        f.poly([(sx, sy - 0.9 * k), (sx + 0.3 * k, sy - 0.2 * k), (sx + 0.9 * k, sy - 0.1 * k), (sx + 0.4 * k, sy + 0.3 * k),
                (sx + 0.6 * k, sy + 1.0 * k), (sx, sy + 0.6 * k), (sx - 0.6 * k, sy + 1.0 * k), (sx - 0.4 * k, sy + 0.3 * k),
                (sx - 0.9 * k, sy - 0.1 * k), (sx - 0.3 * k, sy - 0.2 * k)], (205, 30, 30))                 # red star
    if nation == "japan" and helm in ("cap", "type90"):
        f.poly([(hx - 3.0 * k, hy - 1.4 * k), (hx - 0.6 * k, hy - 1.2 * k), (hx - 0.8 * k, hy + 2.8 * k),
                (hx - 3.4 * k, hy + 2.4 * k)], shade(c, 0.9))                                           # neck flaps
        if helm == "cap":
            f.poly([(hx + 1.6 * k, hy - 1.6 * k), (hx + 4.0 * k, hy - 1.0 * k), (hx + 1.8 * k, hy - 0.8 * k)], lo)
    if medic and helm in ("m1", "brodie", "stahlhelm", "ssh", "adrian", "type90", "m33", "wz31"):
        f.ell(hx - 1.6 * k, hy - 3.4 * k, hx + 1.4 * k, hy - 0.8 * k, WHITE)
        f.rect(hx - 1.1 * k, hy - 2.4 * k, hx + 0.9 * k, hy - 1.8 * k, RED)
        f.rect(hx - 0.4 * k, hy - 3.1 * k, hx + 0.2 * k, hy - 1.1 * k, RED)
    if bandage:
        f.rect(hx - 2.6 * k, hy - 0.4 * k, hx + 2.4 * k, hy + 0.5 * k, WHITE)


def _torso_details(f, key, x0, y0, x1, y1, webc, coat, ):
    (nation, clim, crew, skin_i, helm, wshape, sling, back, rigk, coatk, stick, frag, binos, shovel, medic,
     bandaged, bleeding, pose, face) = key
    if rigk in ("web", "leather", "medic"):
        wc = webc if rigk != "leather" else (44, 38, 32)
        f.line([(x0 + 0.6, y0 + 0.4), (x1 - 0.6, y1 - 1.4)], wc, 0.7)                  # cross strap
        f.rect(x0 - 0.2, y1 - 1.6, x1 + 0.2, y1 - 0.5, wc)                              # belt
        f.rect(x1 - 1.6, y1 - 2.6, x1 - 0.2, y1 - 1.2, shade(wc, 0.8))                  # pouches
        f.rect(x0 + 1.4, y1 - 2.6, x0 + 2.8, y1 - 1.2, shade(wc, 0.8))
    elif rigk == "bandolier":
        f.line([(x0 + 0.2, y0 + 0.2), (x1 - 0.2, y1 - 1.0)], (120, 110, 76), 1.4)
        for k in range(3):
            t = 0.25 + k * 0.25
            f.rect(x0 + (x1 - x0) * t - 0.3, y0 + (y1 - y0 - 1) * t - 0.3, x0 + (x1 - x0) * t + 0.5,
                   y0 + (y1 - y0 - 1) * t + 0.5, (90, 82, 56))
        f.rect(x0 - 0.2, y1 - 1.6, x1 + 0.2, y1 - 0.6, (80, 64, 42))
    if rigk == "medic" or medic:
        f.rect(x0 - 0.6, y1 - 3.0, x0 + 1.2, y1 - 0.8, (180, 170, 140))                  # medic bag
    if stick:
        f.line([(x1 - 0.6, y1 - 1.0), (x1 + 1.2, y1 - 4.2)], LIGHTWOOD, 0.55)           # stick grenade in the belt
        f.rect(x1 + 0.6, y1 - 5.4, x1 + 2.0, y1 - 3.8, (70, 76, 70))
    elif frag:
        f.ell(x0 + 3.0, y0 + 1.4, x0 + 4.6, y0 + 3.2, (60, 70, 50))                      # grenade on the strap
    if binos:
        f.rect(x1 - 2.2, y0 + 1.2, x1 - 0.4, y0 + 2.8, (30, 30, 32))
        f.rect(x1 - 2.2, y0 + 2.8, x1 - 1.6, y0 + 3.4, (30, 30, 32))
    if coatk == "coat":
        f.rect(x1 - 1.6, y0 + 1.0, x1 - 1.0, y0 + 1.6, (60, 56, 40))                     # buttons
        f.rect(x1 - 1.6, y0 + 3.0, x1 - 1.0, y0 + 3.6, (60, 56, 40))
    if bleeding:
        f.ell(x0 + 2.0, y0 + 2.4, x0 + 4.0, y0 + 4.6, (150, 12, 12))


def _back(f, key, bx, by, jacket, webc):
    """Back gear, drawn behind the body.  (bx, by) = top of the shoulders at the back."""
    (nation, clim, crew, skin_i, helm, wshape, sling, back, rigk, coat, stick, frag, binos, shovel, medic,
     bandaged, bleeding, pose, face) = key
    if sling == "long":
        f.line([(bx - 1.0, by + 9.5), (bx + 3.5, by - 6.5)], WOOD, 1.1)
        f.line([(bx + 2.0, by - 1.0), (bx + 4.2, by - 8.0)], DARKMETAL, 0.6)
    elif sling == "short":
        f.line([(bx - 1.2, by + 6.5), (bx + 2.6, by - 1.5)], DARKMETAL, 1.2)
    if back == "radio":
        f.rect(bx - 3.6, by - 0.6, bx + 0.6, by + 7.2, (78, 84, 58))
        f.rect(bx - 3.2, by + 0.4, bx + 0.2, by + 1.2, (50, 54, 38))
        f.line([(bx - 2.6, by - 0.4), (bx - 5.2, by - 13.5)], (36, 36, 36), 0.35)          # the aerial
        f.ell(bx - 5.6, by - 14.0, bx - 4.8, by - 13.2, (36, 36, 36))
    elif back == "flamer":
        f.ell(bx - 4.2, by - 0.8, bx - 0.4, by + 8.6, (104, 104, 92))
        f.ell(bx - 3.0, by - 0.2, bx + 0.6, by + 8.8, (120, 120, 106))
        f.line([(bx - 0.6, by + 8.0), (bx + 3.0, by + 9.6), (bx + 5.0, by + 7.0)], (40, 40, 40), 0.5)
    elif back == "rocketbag":
        f.rect(bx - 3.4, by + 0.2, bx + 0.2, by + 7.0, (104, 96, 66))
        for k in range(2):
            f.rect(bx - 3.0 + k * 1.6, by - 2.2, bx - 1.8 + k * 1.6, by + 0.6, (70, 74, 56))
    elif back == "mortar":
        f.line([(bx - 2.0, by + 8.0), (bx + 1.0, by - 4.0)], (72, 80, 60), 1.6)
        f.rect(bx - 3.6, by + 6.0, bx - 0.4, by + 8.6, (60, 64, 50))
    elif back == "tornister":
        f.rect(bx - 3.4, by + 0.2, bx + 0.2, by + 5.6, (110, 88, 60))
        f.rect(bx - 3.4, by + 0.2, bx + 0.2, by + 1.4, (80, 64, 44))
    elif back == "sack":
        f.ell(bx - 3.8, by + 0.8, bx + 0.6, by + 7.4, shade(mix(jacket, (140, 130, 100), 0.4), 0.9))
    elif back == "pack":
        f.rect(bx - 3.0, by + 0.2, bx + 0.4, by + 6.8, shade(webc, 0.78))
        f.rect(bx - 3.0, by + 0.2, bx + 0.4, by + 1.2, shade(webc, 0.6))
    if shovel and back not in ("radio", "flamer"):
        f.rect(bx - 2.0, by + 6.6, bx + 0.4, by + 9.2, (80, 84, 72))


def _weapon(f, key, grip, ang):
    shape = key[5]
    parts, _ = weapon_parts(shape)
    if parts:
        f.part(grip, ang, parts, WU, WV)


def _grip2(shape):
    return weapon_parts(shape)[1] * WU


def _arm(f, shoulder, hand, jacket, skin, w=1.8):
    f.line([shoulder, hand], shade(jacket, 0.92), w)
    hx, hy = hand
    f.ell(hx - 0.9, hy - 0.9, hx + 0.9, hy + 0.9, skin)


def _upright(f, key, jacket, trousers, helmc, webc, boots, skin):
    (nation, clim, crew, skin_i, helm, wshape, sling, back, rigk, coat, stick, frag, binos, shovel, medic,
     bandaged, bleeding, pose, face) = key
    kneel = pose.startswith("kneel")
    aim = pose.endswith("_aim")
    hands_up = pose == "hands_up"
    drop = 4.6 if kneel else 0.0             # a kneeling man is shorter
    top = 11.4 + drop                        # shoulders
    hip = 20.6 + drop
    x0, x1 = 12.2, 19.6                      # torso
    # back gear first
    _back(f, key, x0 + 0.8, top, jacket, webc)
    # legs
    if kneel:
        # rear knee on the ground, front shin upright
        f.line([(x0 + 1.8, hip), (x0 - 1.0, 28.2)], trousers, 2.3)
        f.line([(x0 - 1.0, 28.2), (x0 - 4.2, 28.6)], shade(trousers, 0.85), 2.0)
        f.rect(x0 - 5.8, 27.6, x0 - 3.4, 29.6, boots)
        f.line([(x1 - 1.6, hip), (x1 + 2.6, hip + 1.0)], trousers, 2.4)
        f.line([(x1 + 2.6, hip + 1.0), (x1 + 2.4, 28.4)], shade(trousers, 0.9), 2.2)
        f.rect(x1 + 1.2, 27.6, x1 + 4.6, 29.8, boots)
    else:
        f.line([(x0 + 1.6, hip), (x0 + 0.4, 27.6)], shade(trousers, 0.9), 2.3)
        f.line([(x1 - 1.4, hip), (x1 + 0.6, 27.6)], trousers, 2.3)
        f.rect(x0 - 0.9, 27.4, x0 + 2.3, 29.8, boots)
        f.rect(x1 - 0.8, 27.4, x1 + 2.6, 29.8, boots)
        if nation == "usa" and not crew:
            f.rect(x0 - 0.6, 25.6, x0 + 1.9, 27.6, (160, 146, 104))                    # canvas leggings
            f.rect(x1 - 0.4, 25.6, x1 + 2.2, 27.6, (160, 146, 104))
    # torso (a greatcoat hangs to the knee)
    f.rect(x0, top, x1, hip + 0.6, jacket)
    if coat in ("coat", "smock") and not kneel:
        f.poly([(x0, hip - 0.5), (x1, hip - 0.5), (x1 + 1.4, hip + 5.6), (x0 - 1.2, hip + 5.6)], jacket)
    f.rect(x0, top, x0 + 1.4, hip + 0.6, shade(jacket, 0.82))                          # shading at the back
    _torso_details(f, key, x0, top, x1, hip, webc, coat)
    if medic:
        f.rect(x0 + 0.6, top + 2.2, x0 + 3.2, top + 3.8, WHITE)                        # armband
        f.rect(x0 + 1.5, top + 2.4, x0 + 2.3, top + 3.6, RED)
    # head
    hx, hy = 16.2 + (0.8 if aim else 0), top - 3.3 * KH
    rear_sh = (x0 + 2.2, top + 1.6)
    front_sh = (x1 - 1.2, top + 1.4)
    if hands_up:
        _head(f, hx, hy, skin, helm, helmc, medic, bandaged, nation)
        _arm(f, rear_sh, (x0 + 0.4, top - 8.0), jacket, skin)
        _arm(f, front_sh, (x1 + 0.6, top - 8.2), jacket, skin)
        return
    # the weapon and the arms that hold it
    if wshape in SHOULDER:
        grip = (x1 - 0.5, top + 1.6)
        ang = 0.0 if aim else -0.12
        _arm(f, rear_sh, (grip[0] - 1.0, grip[1] + 1.4), jacket, skin)
        _head(f, hx, hy, skin, helm, helmc, medic, bandaged, nation)
        _weapon(f, key, (grip[0] - 1.2, grip[1] - 1.8), ang)
        _arm(f, front_sh, (grip[0] + 2.6, grip[1] + 0.8), jacket, skin)
        return
    _head(f, hx, hy, skin, helm, helmc, medic, bandaged, nation)
    if wshape == "none":
        _arm(f, rear_sh, (x0 + 0.8, hip - 0.6), jacket, skin)
        _arm(f, front_sh, (x1 + 0.4, hip - 0.4), jacket, skin)
        return
    heavy = wshape in HEAVY
    one_hand = wshape in ("pistol", "katana", "sword", "knife")
    if one_hand:
        if aim or wshape in ("katana", "sword"):
            hand = (x1 + 5.2, top + 1.8) if aim else (x1 + 2.8, top - 1.0)
            ang = 0.0 if wshape == "pistol" else (-1.1 if not aim else -0.5)
        else:
            hand = (x1 + 1.0, hip - 0.8)
            ang = 1.0
        _arm(f, rear_sh, (x0 + 0.8, hip - 0.6), jacket, skin)
        _weapon(f, key, hand, ang)
        _arm(f, front_sh, hand, jacket, skin)
        return
    if aim:
        # shouldered: stock in the shoulder, sighting along the barrel
        grip = (x1 + 0.6, top + 1.4)
        ang = 0.02
        _weapon(f, key, grip, ang)
        _arm(f, rear_sh, (grip[0] + 0.2, grip[1] + 0.8), jacket, skin)
        g2 = _grip2(wshape)
        _arm(f, front_sh, (grip[0] + min(g2, 7.0), grip[1] + 1.0), jacket, skin)
    else:
        # port arms / carried low for the heavy ones
        if heavy:
            grip = (x0 + 3.2, hip - 1.8)
            ang = -0.18
        else:
            grip = (x0 + 3.4, hip - 1.2)
            ang = -0.72
        _weapon(f, key, grip, ang)
        _arm(f, rear_sh, grip, jacket, skin)
        g2 = min(_grip2(wshape), 6.5)
        _arm(f, front_sh, (grip[0] + g2 * math.cos(ang), grip[1] + g2 * math.sin(ang)), jacket, skin)


def _prone(f, key, jacket, trousers, helmc, webc, boots, skin):
    (nation, clim, crew, skin_i, helm, wshape, sling, back, rigk, coat, stick, frag, binos, shovel, medic,
     bandaged, bleeding, pose, face) = key
    y = 24.6
    # legs out behind, boots at the left
    f.line([(4.0, y + 1.6), (13.0, y + 1.0)], trousers, 2.2)
    f.line([(4.6, y + 3.2), (13.0, y + 2.4)], shade(trousers, 0.88), 2.0)
    f.rect(1.4, y + 0.4, 4.4, y + 2.6, boots)
    f.rect(2.0, y + 2.4, 5.0, y + 4.4, boots)
    # body along the ground
    f.ell(11.5, y - 2.2, 22.5, y + 3.2, jacket)
    if back in ("radio", "rocketbag", "pack", "tornister", "sack", "flamer"):
        col = {"radio": (78, 84, 58), "flamer": (110, 110, 98), "rocketbag": (104, 96, 66)}.get(back, shade(webc, 0.78))
        f.ell(13.0, y - 4.4, 20.0, y - 0.6, col)
        if back == "radio":
            f.line([(14.5, y - 4.0), (9.0, y - 12.5)], (36, 36, 36), 0.35)
    if rigk != "none":
        f.rect(12.2, y + 0.4, 21.6, y + 1.3, webc if rigk != "leather" else (44, 38, 32))
    if medic:
        f.rect(16.0, y - 1.4, 18.4, y + 0.0, WHITE)
        f.rect(16.8, y - 1.2, 17.6, y - 0.2, RED)
    if bleeding:
        f.ell(15.0, y + 1.6, 19.5, y + 4.6, (140, 10, 10))
    # head up, looking forward
    _head(f, 24.4, y - 2.0, skin, helm, helmc, medic, bandaged, nation, k=1.2)
    if wshape not in ("none",):
        parts, _ = weapon_parts(wshape)
        if wshape in SHOULDER:
            f.part((19.5, y - 3.6), 0.0, parts, WU, WV)
        else:
            f.part((21.6, y + 0.6), -0.05, parts, WU * 0.85, WV)
        f.ell(22.0, y + 0.2, 23.8, y + 2.0, skin)          # hands on the weapon
        f.ell(25.8, y + 0.4, 27.4, y + 2.0, skin)


def _downed(f, key, jacket, trousers, helmc, webc, boots, skin):
    (nation, clim, crew, skin_i, helm, wshape, sling, back, rigk, coat, stick, frag, binos, shovel, medic,
     bandaged, bleeding, pose, face) = key
    y = 24.0
    f.ell(8.0, y - 1.5, 26.0, y + 6.0, (120, 12, 12))       # blood under him
    f.line([(4.0, y + 2.4), (13.0, y + 1.2)], trousers, 2.2)
    f.line([(5.0, y + 0.2), (12.5, y + 1.8)], shade(trousers, 0.88), 2.0)   # one knee drawn up
    f.rect(2.0, y + 1.2, 5.0, y + 3.4, boots)
    f.rect(3.0, y - 1.0, 6.0, y + 1.0, boots)
    f.ell(11.5, y - 2.2, 22.5, y + 3.2, jacket)
    f.ell(15.0, y - 2.6, 19.0, y + 0.2, skin)                # a hand pressed to the wound
    if bandaged:
        f.rect(14.0, y - 0.6, 18.0, y + 0.6, WHITE)
    _head(f, 24.4, y + 0.2, skin, helm, helmc, medic, False, nation, k=1.2)
