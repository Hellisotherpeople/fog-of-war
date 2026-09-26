"""The world beyond the battle.

A theatre's war map is only where the story starts.  The front runs on to either side
for as far as you care to walk, each army's rear goes back and back - reserve areas,
depots, towns full of rear-echelon troops - and far enough in any direction the
country itself changes: Normandy's hedgerows give way to the Seine valley, then the
Low Countries, then the Rhineland.  Sectors are made as they're first needed (seen on
a map, walked into) and are then as real as any other.

Nothing here is precise geography: it's the texture of where you are.
"""
from __future__ import annotations

import math
import random

# ---------------------------------------------------------------- deterministic value noise

def _h(ix, iy, seed) -> float:
    n = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def noise(x: float, y: float, seed: int, scale: float = 1.0) -> float:
    """Smooth value noise in [-1, 1]."""
    x *= scale
    y *= scale
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _h(ix, iy, seed)
    b = _h(ix + 1, iy, seed)
    c = _h(ix, iy + 1, seed)
    d = _h(ix + 1, iy + 1, seed)
    v = a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy
    return v * 2 - 1


# ---------------------------------------------------------------- where the land goes
# The theatre's own country, and what lies beyond in each direction:
#   (direction, sectors beyond the edge of the battle map, language, biomes)
# The first rule that applies wins; directions are map directions (N up).

LANG = {"poland39": "pl", "france40": "fr", "crete41": "gr", "barbarossa41": "ru", "moscow41": "ru",
        "alamein42": "ar", "stalingrad42": "ru", "uranus42": "ru", "guadalcanal42": "mel", "tunisia43": "ar",
        "kursk43": "ru", "sicily43": "it", "cassino44": "it", "normandy_airborne44": "fr", "omaha44": "fr",
        "bocage44": "fr", "arnhem44": "nl", "hurtgen44": "de", "bastogne44": "be", "iwojima45": "ja",
        "berlin45": "de", "changsha41": "zh", "kohima44": "in", "karelia44": "fi", "don43": "ru",
        "okinawa45": "ja"}

_WEST = [("farmland", 4), ("village", 3), ("forest", 2), ("town", 1), ("hills", 1)]
_GERMANY = [("forest", 3), ("village", 3), ("farmland", 3), ("town", 2), ("hills", 2)]
_LOW = [("farmland", 4), ("village", 3), ("town", 2), ("marsh", 1)]
_RUSSIA = [("steppe", 3), ("farmland", 3), ("village", 3), ("forest", 2), ("marsh", 1)]
_BALTIC = [("forest", 4), ("marsh", 2), ("village", 2), ("farmland", 2)]
_DESERT = [("desert", 6), ("hills", 2), ("village", 1)]
_ITALY = [("hills", 4), ("farmland", 3), ("village", 3), ("mountain", 2), ("town", 1)]
_CHINA = [("farmland", 4), ("village", 3), ("hills", 2), ("marsh", 1), ("town", 1)]
_BURMA = [("jungle", 5), ("hills", 3), ("village", 1)]

REGIONS = {
    "fr": [("E", 30, "de", _GERMANY), ("N", 30, "be", _LOW), ("S", 30, "fr", _WEST), ("W", 20, "fr", _WEST)],
    "nl": [("E", 12, "de", _GERMANY), ("S", 14, "be", _LOW), ("W", 12, "nl", _LOW)],
    "be": [("E", 10, "de", _GERMANY), ("W", 18, "fr", _WEST), ("N", 16, "nl", _LOW)],
    "de": [("W", 14, "be", _LOW), ("E", 30, "pl", _BALTIC), ("S", 25, "de", _GERMANY)],
    "pl": [("W", 20, "de", _GERMANY), ("E", 30, "ru", _RUSSIA)],
    "ru": [("W", 30, "uk", _RUSSIA), ("N", 30, "ru", _BALTIC)],
    "fi": [("E", 15, "ru", _BALTIC), ("S", 25, "ru", _BALTIC)],
    "it": [("N", 25, "it", _ITALY)],
    "ar": [("E", 25, "ar", _DESERT), ("W", 25, "ar", _DESERT)],
    "zh": [("N", 25, "zh", _CHINA), ("W", 25, "zh", _BURMA)],
    "in": [("E", 12, "my", _BURMA), ("W", 20, "in", _BURMA)],
}

# islands: the land ends (sector bounds relative to the battle map, inclusive); beyond is sea
ISLANDS = {"crete41": (-14, 22, -1, 9), "iwojima45": (-1, 9, -1, 7), "guadalcanal42": (-12, 20, -1, 9),
           "okinawa45": (-2, 10, -20, 26), "sicily43": (-16, 24, -8, 7)}


# coasts beyond the battle map: (direction, sectors past the map's edge where the sea begins)
COAST = {"bocage44": [("N", 7)], "normandy_airborne44": [("E", 2), ("N", 6)], "omaha44": [],
         "cassino44": [("W", 8)], "alamein42": [("N", 1)], "tunisia43": [("E", 12)], "arnhem44": [("W", 14)],
         "berlin45": [("N", 25)], "poland39": [("N", 22)], "france40": [("N", 26)], "karelia44": [("E", 9)],
         "barbarossa41": [], "hurtgen44": [("N", 30)], "bastogne44": [("N", 28)]}


def coast_sea(theatre_id, w, h, x, y) -> bool:
    rules = COAST.get(theatre_id)
    if not rules:
        return False
    beyond = {"E": x - (w - 1), "W": -x, "S": y - (h - 1), "N": -y}
    wob = int(round(noise(x, y, 13, 0.35) * 1.5))
    return any(beyond[d] >= dist + wob for d, dist in rules)


def region(theatre_id: str, w: int, h: int, x: int, y: int):
    """(language, biomes or None for the theatre's own) for a sector."""
    lang = LANG.get(theatre_id, "en")
    beyond = {"E": x - (w - 1), "W": -x, "S": y - (h - 1), "N": -y}
    best = None
    for d, dist, lg, biomes in REGIONS.get(lang, []):
        # soften the border with a little noise so countries don't meet on a ruler line
        wob = int(round(noise(x, y, 7, 0.3) * 2))
        if beyond[d] >= dist + wob:
            if best is None or beyond[d] - dist > best[0]:
                best = (beyond[d] - dist, lg, biomes)
    if best is not None:
        return best[1], best[2]
    far = max(beyond.values())
    return lang, None if far < 4 else "drift"


def island_sea(theatre_id, x, y) -> bool:
    b = ISLANDS.get(theatre_id)
    if b is None:
        return False
    x0, x1, y0, y1 = b
    # a ragged coast
    wob = noise(x, y, 11, 0.5) * 1.2
    return not (x0 - wob <= x <= x1 + wob and y0 - wob <= y <= y1 + wob)


# ---------------------------------------------------------------- place names

SYL = {
    "fr": dict(pre=["Saint-", "Le ", "La ", "Mont", "Beau", "Ville", "Neuf", "Pont-", "Bois-", "Val-", "Fontaine-",
                    "Notre-Dame-de-", "Sainte-", "Les ", ""],
               root=["Aubin", "Martin", "Pierre", "Lô", "Clair", "Denis", "Rémy", "Hilaire", "André", "Germain", "Côme",
                     "Marcel", "Vigor", "Laurent", "Jean", "Honor", "Sever", "Cyr", "Quentin", "Omer", "Gilles"],
               suf=["ville", "court", "mont", "bourg", "ières", "ay", "y", "ot", "ange", "eville", "igny", "ac",
                    "-sur-Vire", "-sur-Seine", "-les-Bois", "-en-Auge", "-la-Forêt", "-le-Vieux", ""]),
    "be": dict(pre=["Saint-", "Mont-", "", "", "Neu", "Hou", "Ber"],
               root=["Hubert", "Vith", "Foy", "Noville", "Mande", "Fouche", "Lierneux", "Wardin", "Bizory", "Hemroulle",
                     "Longchamps", "Mageret", "Recogne", "Senonchamps", "Mande"],
               suf=["", "", "ange", "court", "sart", "fontaine", "mont"]),
    "nl": dict(pre=["Ooster", "Wester", "Nieuw-", "Oud-", "Groot-", "Klein-", ""],
               root=["beek", "hout", "wijk", "dorp", "Heve", "Elst", "Driel", "Wolf", "Bemmel", "Grave", "Zeist",
                     "Ede", "Rhenen", "Ren", "Amer", "Voor"],
               suf=["", "hoven", "dam", "drecht", "wijk", "hem", "sum", "horst", "veen", "rode"]),
    "de": dict(pre=["Ober", "Nieder", "Groß ", "Klein ", "Alt", "Neu", "Hohen", "Bad ", ""],
               root=["Kessel", "Linden", "Eichen", "Birken", "Buchen", "Stein", "Mühl", "Schön", "Rot", "Weiß", "Rosen",
                     "Hart", "Wald", "Berg", "Hagen", "Kirch", "Brück", "Hessen", "Frank", "Wolfs"],
               suf=["dorf", "heim", "hausen", "burg", "feld", "bach", "au", "stedt", "rode", "ingen", "berg", "weiler",
                    "brück", "hof", "tal"]),
    "pl": dict(pre=["Nowa ", "Stara ", "Wielka ", "Mała ", "", "", ""],
               root=["Wola", "Brzez", "Lip", "Dąb", "Kamień", "Zawada", "Kozie", "Grab", "Sosn", "Olsz", "Bór", "Mił",
                     "Rad", "Bogu", "Jasie"],
               suf=["ów", "owo", "ice", "iny", "ka", "no", "sk", "ec", "ów Mały", "owice", ""]),
    "ru": dict(pre=["Novo", "Staro", "Krasno", "Bolshaya ", "Malaya ", "Verkhnyaya ", "Nizhnyaya ", "", "", ""],
               root=["Ivan", "Petr", "Mikhail", "Alekse", "Sosn", "Berez", "Lip", "Dubr", "Kamen", "Krasn", "Belo",
                     "Cherno", "Pokrov", "Voskresen", "Nikol", "Uspen", "Sokol", "Orl", "Zelen", "Gorod"],
               suf=["ovka", "ino", "evo", "ovo", "sk", "skoye", "ets", "ka", "ki", "any", "ishche", "grad"]),
    "uk": dict(pre=["Novo", "Staro", "Velyka ", "Mala ", "", ""],
               root=["Ivan", "Petr", "Mykol", "Sosn", "Berez", "Lyp", "Dubr", "Kamyan", "Bila", "Cherkas", "Pokrov",
                     "Zelen", "Horod", "Oleksand"],
               suf=["ivka", "ne", "ove", "ivtsi", "ychi", "ka", "ky", "hrad", "pil"]),
    "fi": dict(pre=["", "", "Ylä-", "Ala-", "Iso-", "Pikku-"],
               root=["Kivi", "Koivu", "Mänty", "Suo", "Joki", "Mäki", "Lampi", "Salmi", "Niemi", "Harju", "Kuusi",
                     "Pihla", "Karhu", "Susi"],
               suf=["la", "järvi", "koski", "vaara", "salo", "niemi", "lahti", "mäki", "lampi", "suo"]),
    "it": dict(pre=["San ", "Santa ", "Monte ", "Castel", "Borgo ", "Villa ", "Rocca ", "Poggio ", "", ""],
               root=["Giorgio", "Pietro", "Angelo", "Vittorio", "Marco", "Lucia", "Maria", "Rosso", "Verde", "Fiore",
                     "Lago", "Sasso", "Ferro", "Olmo", "Leone"],
               suf=["", "", "ello", "ano", "ino", " di Sopra", " di Sotto", " al Monte", "ara", "one"]),
    "gr": dict(pre=["Agia ", "Agios ", "Kato ", "Ano ", "Palaio", "Neo", ""],
               root=["Galat", "Kast", "Plat", "Mal", "Stavr", "Kolymb", "Vouk", "Kandan", "Alikian", "Perivol",
                     "Modi", "Tavron", "Pyrgos"],
               suf=["as", "os", "i", "ia", "ari", "ada", "ou", "elli"]),
    "ar": dict(pre=["Bir ", "Sidi ", "El ", "Wadi ", "Deir el ", "Tel el ", "Qaret ", "Ras ", "Djebel ", "Bou "],
               root=["Hakeim", "Rezegh", "Abd", "Muhammad", "Aqqaqir", "Alam", "Kidney", "Rahman", "Omar", "Haleima",
                     "Ghobi", "Salem", "Chergui", "Zitoun"],
               suf=["", "", "", " Ridge", " Pass", " Wells"]),
    "ja": dict(pre=["", "", "Kita-", "Minami-", "Higashi-", "Nishi-", "Shin-"],
               root=["Kaka", "Naha", "Shuri", "Yona", "Kade", "Tobaru", "Maeda", "Kochi", "Motobu", "Nakagusu",
                     "Ishi", "Taka", "Yama", "Kawa", "Hira", "Oki"],
               suf=["zu", "bara", "gawa", "yama", "shima", "mura", "saki", "hama", "moto", ""]),
    "zh": dict(pre=["", "", "Xin", "Da", "Xiao", "Shang", "Xia"],
               root=["hua", "shan", "shui", "jia", "li", "he", "tian", "long", "feng", "yang", "an", "ping", "qiao"],
               suf=["zhen", "cun", "pu", "ji", "ling", "kou", "wan", "tang", " xian"]),
    "in": dict(pre=["", "", ""],
               root=["Jessami", "Phek", "Kohima", "Zubza", "Jotsoma", "Merema", "Aradura", "Pulie", "Chakha", "Khonoma",
                     "Litan", "Ukhrul", "Imphal", "Bishen"],
               suf=["", "", " Ridge", " Spur", " Village", "pur"]),
    "my": dict(pre=["", "", ""],
               root=["Tamu", "Kalewa", "Tiddim", "Myit", "Shwe", "Kyauk", "Mawla", "Pinle", "Sitt", "Yaw", "Pyin"],
               suf=["", "kyina", "gyi", "daw", "taung", "myo", "zin"]),
    "mel": dict(pre=["", "", "Point ", "Mount "],
               root=["Matani", "Tenaru", "Lunga", "Kokum", "Tassa", "Mata", "Koli", "Aola", "Gavaga", "Kukum", "Tetere",
                     "Marovo", "Ruavatu"],
               suf=["", "", "kau", "fongo", "ga", "ri", " River"]),
    "en": dict(pre=["Upper ", "Lower ", "Great ", "Little ", "", ""],
               root=["Ash", "Oak", "Brook", "Mill", "Stone", "Thorn", "Wood", "Marsh", "Kings", "Church"],
               suf=["ford", "ham", "ton", "ley", "field", "bury", "wick", "stead", "by"]),
}
MILITARY = ["Hill {n}", "Point {n}", "Height {n}", "Crossroads {l}", "Wood {l}", "Ridge {l}", "Farm {l}"]


def place_name(lang: str, rng: random.Random) -> str:
    if rng.random() < 0.12:
        return rng.choice(MILITARY).format(n=rng.randint(60, 600), l="ABCDEFGHJK"[rng.randint(0, 9)])
    s = SYL.get(lang) or SYL["en"]
    pre = rng.choice(s["pre"]) if rng.random() < 0.55 else ""
    root = rng.choice(s["root"])
    suf = rng.choice(s["suf"])
    name = pre + root + suf
    if pre.endswith(("-", " ")) or not pre:
        return name[0].upper() + name[1:]
    return pre + root.lower() + suf


COUNTRY = {"fr": "France", "be": "Belgium", "nl": "the Netherlands", "de": "Germany", "pl": "Poland", "ru": "Russia",
           "uk": "the Ukraine", "fi": "Finland", "it": "Italy", "gr": "Crete", "ar": "the desert", "ja": "the island",
           "zh": "China", "in": "the Naga hills", "my": "Burma", "mel": "the Solomons", "en": "the country"}
