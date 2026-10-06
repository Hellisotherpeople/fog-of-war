"""Decorations and their citations, retained when the message log and battle counters move on."""
from __future__ import annotations

import math
import textwrap

from .data.ranks import MEDALS

STRIPE_NATIONS = ("uk", "canada", "australia", "newzealand", "india", "ussr")


def record(game, name, level, why, posthumous=False):
    cmd = game.command
    evidence = []
    if "gallantry" in why:
        for key, singular, plural in (("kills", "enemy defeated", "enemies defeated"),
                                     ("objectives", "objective taken", "objectives taken"),
                                     ("acting", "occasion taking command", "occasions taking command"),
                                     ("wounds", "wound in action", "wounds in action")):
            n = cmd.battle.get(key, 0)
            if n:
                evidence.append(f"{n} {singular if n == 1 else plural}")
    elif "conduct of operations" in why:
        evidence.append(f"{cmd.career.get('sectors', 0)} sectors secured under your command")
    entry = dict(name=name, nation=game.player.nation, level=level, why=why,
                 evidence="; ".join(evidence), when=game.datetime_str(exact=True), turn=game.turn,
                 place=game.sector.name, posthumous=bool(posthumous), repeat="(second award)" in name)
    cmd.__dict__.setdefault("award_records", []).append(entry)
    return entry


def records(command, nation):
    """Names in old saves still receive an illustration, without inventing a lost citation."""
    saved = list(command.__dict__.get("award_records") or [])
    out = []
    for name in command.medals:
        entry = next((a for a in saved if a["name"] == name), None)
        if entry is not None:
            out.append(dict(entry))
            saved.remove(entry)
            continue
        bare = name.removesuffix(" (second award)")
        names = MEDALS.get(nation, MEDALS["usa"])
        out.append(dict(name=name, nation=nation, level=names.index(bare) if bare in names else 1,
                        why="Citation unavailable in this older service record.", when="", place="",
                        evidence="", posthumous=False, repeat=bare != name))
    return out


def icon_key(entry):
    return f"award|{entry['nation']}|{entry['level']}|{int(entry.get('repeat', False))}"


def draw_card(con, entry, x, y, w, h=12):
    from . import icons
    bg, edge = (34, 38, 37), (116, 108, 79)
    con.draw_frame(x, y, w, h, fg=edge, bg=bg, clear=True)
    if icons.on():
        icons.pic(x + 1, y + 1, 12, h - 2, icon_key(entry))
    else:
        # A ribbon and medal in the terminal too, rather than dropping back to a name alone.
        stripes = ribbon(entry["nation"], entry["level"])
        for i in range(9):
            con.draw_rect(x + 2 + i, y + 2, 1, 2, ord(" "), bg=stripes[i * len(stripes) // 9][:3])
        if entry["level"] == 0 and entry["nation"] in STRIPE_NATIONS:
            con.draw_rect(x + 5, y + 5, 1, 4, ord(" "), bg=(213, 179, 97))
        else:
            con.print(x + 4, y + 5, "╲│╱", fg=(213, 179, 97), bg=bg)
            con.print(x + 4, y + 6, "─★─", fg=(213, 179, 97), bg=bg)
            con.print(x + 4, y + 7, "╱│╲", fg=(213, 179, 97), bg=bg)
    tx, ty, width = x + 14, y + 1, w - 16
    for text, col in ((entry["name"], (241, 216, 145)),
                      (("POSTHUMOUS · " if entry.get("posthumous") else "") + entry.get("when", ""), (160, 171, 171)),
                      (entry["why"][0:1].upper() + entry["why"][1:], (226, 222, 202)),
                      (entry.get("evidence", ""), (170, 192, 172)),
                      (entry.get("place", ""), (156, 168, 165))):
        for line in textwrap.wrap(text, width):
            if ty >= y + h - 1:
                return
            con.print(tx, ty, line, fg=col, bg=bg)
            ty += 1


def ribbon(nation, level):
    red, blue, white, black, gold, green = ((157, 37, 43, 255), (38, 66, 116, 255), (230, 226, 205, 255),
                                           (28, 29, 30, 255), (220, 165, 52, 255), (38, 96, 66, 255))
    if nation == "usa":
        return ((white, (98, 43, 135, 255), (98, 43, 135, 255), white) if level == 0 else
                (red, white, blue, white, red) if level < 3 else
                (blue, white, red, white, blue) if level == 3 else ((101, 172, 207, 255),) * 4)
    if nation in ("uk", "canada", "australia", "newzealand", "india"):
        return (red,) * 4 if level == 4 else (white, blue, white, blue, white) if level == 1 else (white, red, white)
    return {"germany": (black, white, red, white, black), "ussr": (red, gold, red),
            "italy": (blue, blue, blue), "japan": (white, red, white), "france": (green, red, green, red, green),
            "poland": (red, white, red), "finland": (white, blue, white),
            "china": (blue, white, red), "hungary": (red, white, green),
            "romania": (blue, gold, red)}.get(nation, (blue, white, red))


def paint(c, arg):
    """Stylized service decorations, drawn with the interface's existing vector canvas."""
    nation, level, repeat = arg.split("|")
    level = max(0, min(4, int(level)))
    stripes = ribbon(nation, level)
    gold, silver, bronze = (213, 174, 86, 255), (205, 210, 213, 255), (159, 104, 61, 255)
    metal = silver if level in (0, 2) else bronze if level == 1 else gold
    outline = (74, 59, 36, 255)
    if level == 0 and nation in STRIPE_NATIONS:
        c.rect(.12, .18, .68, .84, (70, 76, 53, 255), outline, .01, r=.025)
        if nation == "ussr":
            c.rect(.19, .46, .61, .54, (190, 52, 39, 255), gold, .01)
        else:
            c.rect(.36, .3, .44, .73, gold, outline, .01)
            for i in range(12):
                c.line([(.365, .31 + i*.034), (.435, .33 + i*.034)], (245, 217, 146, 255), .009)
        return
    c.rect(.18, .05, .62, .39, (13, 15, 15, 200), r=.015)
    for i, col in enumerate(stripes):
        left = .19 + i * .42 / len(stripes)
        c.rect(left, .06, left + .42 / len(stripes), .37, col)
    for i in range(22):
        c.line([(.2 + i * .019, .07), (.2 + i * .019, .36)], (255, 255, 255, 23), .003)
    c.rect(.17, .04, .63, .08, metal, outline, .009)
    c.poly([(.19, .37), (.4, .46), (.61, .37)], stripes[len(stripes) // 2])
    c.ell(.36, .425, .44, .515, None, metal, .02)
    cx, cy, r = .4, .71, .25
    if nation == "usa" and level == 0:
        pts = []
        for i in range(101):
            t = i * math.tau / 100
            pts.append((cx + .016 * 16 * math.sin(t) ** 3,
                        cy - .016 * (13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))))
        c.poly(pts, (103, 42, 129, 255), gold, .023)
        c.ell(.34, .6, .46, .76, gold)
        c.poly([(.33, .81), (.35, .73), (.45, .73), (.49, .81)], gold)
    elif nation == "germany" or level == 3 or (nation in ("uk", "canada", "australia", "india") and level >= 2):
        pts = [(-.24,-.24),(-.1,-.21),(-.09,-.08),(.09,-.08),(.1,-.21),(.24,-.24),
               (.21,-.1),(.08,-.09),(.08,.09),(.21,.1),(.24,.24),(.1,.21),(.09,.08),
               (-.09,.08),(-.1,.21),(-.24,.24),(-.21,.1),(-.08,.09),(-.08,-.09),(-.21,-.1)]
        c.poly([(cx+x, cy+y) for x,y in pts], (35, 36, 38, 255) if nation == "germany" else metal, silver, .022)
        c.ell(.35, .66, .45, .76, metal, outline, .01)
    elif level >= 2 or nation == "usa":
        pts = [(cx + (r if i % 2 == 0 else r * .44) * math.sin(i * math.pi / 5),
                cy - (r if i % 2 == 0 else r * .44) * math.cos(i * math.pi / 5)) for i in range(10)]
        c.poly(pts, (173, 43, 42, 255) if nation == "ussr" and level == 2 else metal, outline, .014)
        for i in range(5):
            c.line([(cx, cy), pts[i*2]], (248, 224, 163, 155), .014)
    else:
        c.ell(cx-r, cy-r, cx+r, cy+r, metal, outline, .018)
        c.ell(cx-r+.025, cy-r+.025, cx+r-.025, cy+r-.025, None, (244, 225, 174, 255), .009)
        c.arc(.23, .53, .57, .89, 25, 155, outline, .015)
        c.text(.33, .61, "V", outline, .23)
    if repeat == "1":
        c.rect(.22, .19, .58, .25, gold, outline, .01)
        c.line([(.26, .21), (.54, .21)], (245, 223, 163, 255), .01)
