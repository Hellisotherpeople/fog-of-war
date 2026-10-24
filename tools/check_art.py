#!/usr/bin/env python3
"""List the items an artist owes drawings for, and validate assets/art/*.txt.

  tools/check_art.py --list GROUP      ids, names, descriptions and lore for one group
  tools/check_art.py [GROUP]           validate every art file; report GROUP's (or all) missing ids
Groups: handguns longarms crewed ordnance ammunition wearables gear personal
"""
import os
import sys
import textwrap

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fow.game  # noqa: E402,F401  (registers every item, the vehicles' machine guns too)
from fow.data.items import ITEMS  # noqa: E402
from fow.data.lore import LORE  # noqa: E402
from fow import itemart  # noqa: E402

PERSONAL = {"ration", "chocolate", "flask", "cigarettes", "lighter", "gum", "stimulant", "charm", "flag", "medal",
            "ring", "rosary", "coin", "cards", "bible", "letter", "photo", "dogtags", "harmonica", "newspaper",
            "money", "shave", "sewing", "watch", "canteen", "trade", "document", "papers", "cover_papers"}
GROUPS = {
    "handguns": lambda t: t.kind == "gun" and t.cat in ("pistol", "smg", "carbine", "shotgun", "assault"),
    "longarms": lambda t: t.kind == "gun" and t.cat in ("rifle", "sniper", "at_rifle", "at_launcher", "at_disposable"),
    "crewed": lambda t: t.kind == "gun" and t.cat in ("lmg", "hmg", "mortar", "flamer"),
    "ordnance": lambda t: t.kind in ("grenade", "explosive", "melee", "medical"),
    "ammunition": lambda t: t.kind in ("ammo", "mag", "clip"),
    "wearables": lambda t: t.kind in ("armor", "container", "corpse"),
    "gear": lambda t: t.kind == "tool" and t.tool not in PERSONAL,
    "personal": lambda t: t.kind == "tool" and t.tool in PERSONAL,
}
ALLOWED = set(map(chr, range(32, 127)))


def group_ids(g):
    return [t.id for t in ITEMS.values() if g is None or GROUPS[g](t)]


def main(argv):
    if argv[:1] == ["--list"]:
        for i in group_ids(argv[1]):
            t = ITEMS[i]
            print(f"\n## {i}: {t.name}  [{t.kind} {t.cat or t.tool or t.slot or t.gtype or t.med}]")
            for s in (t.desc, LORE.get(i, "")):
                if s:
                    print(textwrap.fill(s, 110))
        return 0
    errors, owners = [], {}
    for name in sorted(os.listdir(itemart.ART_DIR)) if os.path.isdir(itemart.ART_DIR) else []:
        if not name.endswith(".txt"):
            continue
        with open(os.path.join(itemart.ART_DIR, name), encoding="utf-8") as f:
            art = itemart.parse(f.read())
        for i, rows in art.items():
            where = f"{name}: {i}"
            if i in owners:
                errors.append(f"{where}: also drawn in {owners[i]}")
            owners[i] = name
            if i not in ITEMS:
                errors.append(f"{where}: no such item")
            if not rows:
                errors.append(f"{where}: empty drawing")
            if len(rows) > itemart.MAX_H or any(len(r) > itemart.MAX_W for r in rows):
                errors.append(f"{where}: {max(map(len, rows), default=0)}x{len(rows)} exceeds "
                              f"{itemart.MAX_W}x{itemart.MAX_H}")
            bad = {c for r in rows for c in r} - ALLOWED
            if bad:
                errors.append(f"{where}: characters outside printable ASCII: {''.join(sorted(bad))!r}")
    missing = [i for i in group_ids(argv[0] if argv else None) if i not in owners]
    for e in errors:
        print("ERROR", e)
    print(f"{len(owners)} items drawn; {len(missing)} missing" + (": " + " ".join(missing) if missing else ""))
    return 1 if errors or missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
