"""The order of battle: everything you command, from your own headquarters down to the battalion
holding each stretch of the front.

A battalion holds a sector of the war map.  Three battalions make a regiment (or a Commonwealth
brigade), three regiments a division, two or three divisions a corps, three corps an army, and
the army group (or Soviet front) is everything on this part of the war.  Formations are laid out
along the front the way they really were - each holding its own strip of it - and they keep their
names as the line moves: a sector lost is a battalion gone; ground taken is a battalion moved up.

Every formation has a commander.  Where history knows who commanded it on the day, he does
(Model has 9. Armee at Kursk); everyone else is a man with a name and a rank, and men are
killed, wounded and relieved (see hierarchy.py).  You are at the top of it - or, below army group,
at the top of your part of it.

The general staff screen (G) gives orders to these formations; the command roster (C / O) shows
the whole tree, down to the squads of the battalion on the ground you're standing on.
"""
from __future__ import annotations

from .data import ranks as R
from .data.nations import ordinal

LEVELS = ["battalion", "regiment", "division", "corps", "army", "army group"]
SIZE = {"regiment": 3, "division": 3, "corps": 3, "army": 3}       # how many of the level below, at most
MIN_SPLIT = {"army": 2, "corps": 2, "division": 2, "regiment": 2}    # ... and at least, where there's the ground
TOUCH = {"army group": 9, "army": 7, "corps": 4, "division": 3, "regiment": 2}   # war map laid out around you
GRADE = {"battalion": R.LT_COL, "regiment": R.COLONEL, "division": R.MAJ_GEN, "corps": R.LT_GEN,
         "army": R.GENERAL, "army group": R.MARSHAL}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI",
         "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX",
         "XXX", "XXXI", "XXXII", "XXXIII", "XXXIV", "XXXV", "XXXVI", "XXXVII", "XXXVIII", "XXXIX", "XL", "XLI",
         "XLII", "XLIII", "XLIV", "XLV", "XLVI", "XLVII", "XLVIII", "XLIX", "L", "LI", "LII", "LIII", "LIV", "LV",
         "LVI", "LVII", "LVIII", "LIX", "LX"]
ARMY_WORD = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
             "Eleventh", "Twelfth", "Fourteenth", "Fifteenth"]
COMMONWEALTH = ("uk", "canada", "australia", "newzealand", "india")
UK_REGIMENTS = ["Royal Warwickshire Regiment", "East Yorkshire Regiment", "Durham Light Infantry", "Black Watch",
                "Royal Ulster Rifles", "Hampshire Regiment", "Green Howards", "King's Own Scottish Borderers",
                "Devonshire Regiment", "Dorsetshire Regiment", "South Lancashire Regiment", "Royal Norfolk Regiment",
                "Gordon Highlanders", "Seaforth Highlanders", "Royal Scots", "Welsh Guards", "Grenadier Guards",
                "Coldstream Guards", "Royal Berkshire Regiment", "Oxfordshire and Buckinghamshire Light Infantry",
                "Sherwood Foresters", "Essex Regiment", "Middlesex Regiment", "Queen's Royal Regiment"]


def level_name(nation, echelon):
    """What the army called it: a Soviet army group is a front; a Commonwealth regiment is a brigade."""
    if echelon == "army group" and nation == "ussr":
        return "front"
    if echelon == "regiment" and nation in COMMONWEALTH:
        return "brigade"
    return echelon


def _same_level(a, b):
    alias = {"front": "army group", "brigade": "regiment"}
    return alias.get(a, a) == alias.get(b, b)


class Node:
    __slots__ = ("fid", "echelon", "name", "parent", "children", "sector", "hist", "num")

    def __init__(self, fid, echelon, name, parent=None, sector=None, hist=None, num=0):
        self.fid = fid
        self.echelon = echelon
        self.name = name
        self.parent = parent            # fid
        self.children: list[int] = []
        self.sector = sector            # (x, y) for a battalion
        self.hist = hist                # the historical record (commanders.F) this formation is, if any
        self.num = num                  # its number within its parent (I., II., III. Bataillon)


class OOB:
    def __init__(self, side, nation, top):
        self.side = side
        self.nation = nation
        self.top = top                  # the echelon you command
        self.nodes: dict[int, Node] = {}
        self.root = None
        self.bn_of: dict = {}           # sector (x, y) -> battalion fid
        self.next_fid = 1
        self.used = {}                  # echelon -> set of numbers already given out
        self.hist_used = set()

    # ------------------------------------------------------------------ queries
    def node(self, fid):
        return self.nodes.get(fid)

    def walk(self, fid=None):
        n = self.nodes.get(self.root if fid is None else fid)
        if n is None:
            return
        yield n
        for c in n.children:
            yield from self.walk(c)

    def sectors_of(self, fid):
        return {n.sector for n in self.walk(fid) if n.sector is not None}

    def chain(self, fid):
        n = self.nodes.get(fid)
        while n is not None:
            yield n
            n = self.nodes.get(n.parent)

    def at_level(self, echelon):
        return [n for n in self.nodes.values() if n.echelon == echelon]

    def label(self, n):
        return n.name

    def local_battalion(self, game):
        """The battalion fighting on the ground you're standing on: the one holding it - or, in an attack,
        the one that's gone in from the sector next door."""
        here = (game.sector.x, game.sector.y)
        fid = self.bn_of.get(here)
        if fid is not None:
            return fid
        edge = game.home_edge(self.side) if game.map is not None else None
        from .strategic import DIRS
        order = ([edge] if edge in DIRS else []) + [e for e in DIRS if e != edge]
        for e in order:
            dx, dy = DIRS[e]
            fid = self.bn_of.get((here[0] + dx, here[1] + dy))
            if fid is not None:
                return fid
        return None

    def commander(self, game, n):
        """(rank title, name, historical?) of the man commanding this formation - you, at the top."""
        g, title, name, hist = self.commander_full(game, n)
        return title, name, hist

    def commander_full(self, game, n):
        """(grade, rank title, name, historical?)."""
        from .hierarchy import holder_at, _date, _title
        if n.fid == self.root:
            p = game.player
            return p.rank, p.rank_full, p.name, False
        if n.hist is not None:
            h = holder_at(n.hist[4], _date(game))
            grade = h[2] if isinstance(h[2], int) else GRADE.get(n.echelon, R.COLONEL)
            return grade, _title(self.nation, h[2]), h[3], True
        hier = game.__dict__.get("hierarchy")
        if hier is None:
            from .hierarchy import Hierarchy
            hier = game.hierarchy = Hierarchy()
        key = ("gen", self.nation, n.echelon, n.name)
        lst = hier.gen.get(key)
        if lst is None:
            from .data.nations import random_name
            rng = game.rng
            g = GRADE.get(n.echelon, R.COLONEL)
            if n.echelon == "regiment" and self.nation in COMMONWEALTH:
                g = R.BRIGADIER                        # a Commonwealth brigade had a brigadier
            if n.echelon == "battalion" and rng.random() < 0.35:
                g = R.MAJOR                            # plenty of battalions had a major
            elif n.echelon == "division" and rng.random() < 0.3:
                g -= 1
            elif n.echelon == "army group" and rng.random() < 0.4:
                g = R.GENERAL
            lst = hier.gen[key] = [dict(name=random_name(rng, self.nation, male=True), grade=g, since=game.turn,
                                        fate=None)]
        cur = lst[-1]
        return cur["grade"], R.rank_title(self.nation, cur["grade"]), cur["name"], False

    def strength(self, game, fid):
        from .operations import live_strength, strength
        st = game.strategic
        out = dict(men=0, tanks=0, guns=0, halftracks=0)
        for k in self.sectors_of(fid):
            c = st.at(*k)
            if c is None:
                continue
            if c is game.sector:
                s = live_strength(game, self.side)
            else:
                s = strength(c.units[self.side], self.nation, [i[0] for i in c.installs(self.side)], staff=True)
            for key in out:
                out[key] += s[key]
        return out

    # ------------------------------------------------------------------ building it
    def _fid(self):
        self.next_fid += 1
        return self.next_fid

    def _add(self, echelon, parent, sector=None, name=None, hist=None):
        par = self.nodes.get(parent)
        num = (len(par.children) + 1) if par is not None else 1
        n = Node(self._fid(), echelon, name or "", parent, sector, hist, num)
        self.nodes[n.fid] = n
        if par is not None:
            par.children.append(n.fid)
        if sector is not None:
            self.bn_of[sector] = n.fid
        return n

    def _remove(self, fid):
        n = self.nodes.pop(fid, None)
        if n is None:
            return
        for c in list(n.children):
            self._remove(c)
        par = self.nodes.get(n.parent)
        if par is not None and fid in par.children:
            par.children.remove(fid)
        if n.sector is not None and self.bn_of.get(n.sector) == fid:
            del self.bn_of[n.sector]
        if n.hist is not None:
            self.hist_used.discard(n.hist[2])

    def update(self, game, sectors):
        """Keep the tree in step with the ground we hold: `sectors` are ours, within your reach."""
        st = game.strategic
        keys = {(c.x, c.y) for c in sectors}
        reports = []
        if self.root is None:
            self._build(game, sectors)
            return reports
        # ground lost: the battalion that held it is gone (to the rear, or into the bag)
        for k, fid in list(self.bn_of.items()):
            c = st.at(*k)
            if c is None or c.control != self.side:
                n = self.nodes.get(fid)
                if n is not None:
                    reports.append(f"{n.name} has been driven out of {c.name if c else 'its sector'}.")
                self._remove(fid)
        # formations with nothing left in them are disbanded, their men sent to the others
        for n in sorted(list(self.nodes.values()), key=lambda n: LEVELS.index(n.echelon)):
            if n.fid != self.root and n.echelon != "battalion" and n.fid in self.nodes and not self.sectors_of(n.fid):
                reports.append(f"{n.name} has ceased to exist as a fighting formation.")
                self._remove(n.fid)
        # ground won, or come into reach: a battalion moves up into it
        for c in sorted((c for c in sectors if (c.x, c.y) not in self.bn_of), key=lambda c: st._axes(c.x, c.y)):
            reg = self._home_for(game, c, "regiment")
            n = self._add("battalion", reg.fid, (c.x, c.y))
            n.name = self._name(game, n)
        return reports

    def _home_for(self, game, c, echelon):
        """The formation at `echelon` a new sector's battalion joins: the nearest with room, or a new one."""
        st = game.strategic
        best, bd = None, 1e9
        for n in self.at_level(echelon):
            if len(n.children) >= SIZE.get(echelon, 99):
                continue
            ss = self.sectors_of(n.fid)
            if not ss:
                continue
            d = min(abs(x - c.x) + abs(y - c.y) for x, y in ss)
            if d < bd:
                bd, best = d, n
        if best is not None and bd <= 3:
            return best
        if echelon == self.top:
            return self.nodes[self.root]
        up = LEVELS[LEVELS.index(echelon) + 1]
        par = self._home_for(game, c, up) if LEVELS.index(up) <= LEVELS.index(self.top) else self.nodes[self.root]
        n = self._add(echelon, par.fid)
        n.hist = self._hist_for(game, echelon, par)
        n.name = n.hist[2] if n.hist else self._name(game, n)
        return n

    def _build(self, game, sectors):
        """The first layout: formations side by side along the front, each with its strip of it."""
        st = game.strategic
        top = self.top
        root = self._add(top, None)
        root.hist = self._hist_for(game, top, None)
        root.name = (root.hist[2] if root.hist else None) or self._root_name(game)
        self.root = root.fid
        if top == "battalion":
            return
        # sort the ground along the front (then front to rear): neighbours end up together
        order = sorted(sectors, key=lambda c: st._axes(c.x, c.y))
        levels = LEVELS[:LEVELS.index(top)]            # battalion ... the level just below yours
        cap = {"battalion": 1}                         # battalions one formation of each kind can hold
        for a, b in zip(levels, levels[1:]):
            cap[b] = cap[a] * SIZE.get(b, 3)

        def lay(parent, idx, block):
            lvl = levels[idx]
            if lvl == "battalion":
                for c in block:
                    n = self._add("battalion", parent.fid, (c.x, c.y))
                    n.name = self._name(game, n)
                return
            # enough formations to hold it - and never a single one where two or three would have stood
            k = min(len(block), max(MIN_SPLIT.get(lvl, 1) if parent.fid == self.root or lvl != "regiment" else 1,
                                    -(-len(block) // cap[lvl])))
            k = max(1, k)
            per = -(-len(block) // k)
            for i in range(0, len(block), per):
                n = self._add(lvl, parent.fid)
                n.hist = self._hist_for(game, lvl, parent)
                n.name = n.hist[2] if n.hist else self._name(game, n)
                lay(n, idx - 1, block[i:i + per])

        lay(root, len(levels) - 1, order)

    # ------------------------------------------------------------------ history and names
    def _hist(self, game):
        from .data import commanders as HC
        th = game.theatre.get("id", "")
        return [r for r in HC.F.get(th, []) if self.nation in r[0]]

    def _hist_for(self, game, echelon, parent):
        """A historical formation of this kind that belongs under `parent` (and isn't taken)."""
        from .hierarchy import _date, _parent_name
        date = _date(game)
        recs = [r for r in self._hist(game) if _same_level(r[1], echelon) and r[2] not in self.hist_used]
        if not recs:
            return None
        pname = parent.name if parent is not None else None
        fits = [r for r in recs if pname is not None and _parent_name(r[3], date) == pname]
        if not fits and parent is not None:
            # history puts it under a formation higher up this chain (a division straight under an army)
            ups = [x.name for x in self.chain(parent.fid)]
            fits = sorted((r for r in recs if _parent_name(r[3], date) in ups[1:]),
                          key=lambda r: ups.index(_parent_name(r[3], date)))
        if not fits and parent is not None and parent.hist is None:
            fits = [r for r in recs if not any(_same_level(x[1], parent.echelon) and x[2] == _parent_name(r[3], date)
                                               for x in self._hist(game))]
        if not fits and parent is None:
            # your own command: the one your own division belongs to, if you know it
            p = game.player
            mine = (p.ai.get("unit0") or p.unit or "")
            fits = [r for r in recs if r[2] in mine] or recs[:1]
        if not fits:
            return None
        r = fits[0]
        self.hist_used.add(r[2])
        return r

    def _root_name(self, game):
        p = game.player
        hn = game.command._higher_names(game, p)
        return hn.get(level_name(self.nation, self.top)) or hn.get(self.top) or self._fresh(game, self.top, None)

    def _number(self, game, echelon, lo, hi):
        used = self.used.setdefault(echelon, set())
        if not self.__dict__.get("_hist_nums"):
            # numbers history has already given out (XLVI. Panzerkorps, 292. Infanterie-Division) aren't reused
            import re
            self._hist_nums = True
            for r in self._hist(game):
                m = re.match(r"^([IVXL]+)\.", r[2])
                if m and m.group(1) in ROMAN and _same_level(r[1], "corps"):
                    self.used.setdefault("corps", set()).add(ROMAN.index(m.group(1)) + 1)
                m = re.match(r"^(\d+)", r[2])
                if m:
                    lvl = "army" if _same_level(r[1], "army") else r[1]
                    self.used.setdefault(lvl, set()).add(int(m.group(1)))
        for _ in range(50):
            k = game.rng.randint(lo, hi)
            if k not in used:
                used.add(k)
                return k
        k = max(used | {hi}) + 1
        used.add(k)
        return k

    def _name(self, game, n):
        par = self.nodes.get(n.parent)
        return self._fresh(game, n.echelon, par, n)

    def _fresh(self, game, echelon, par, n=None):
        nat = self.nation
        num = lambda lo, hi: self._number(game, echelon, lo, hi)  # noqa: E731
        idx = (n.num if n is not None else 1)
        if echelon == "battalion":
            pname = par.name if par is not None else ""
            if nat == "germany":
                return f"{ROMAN[min(idx, 20) - 1]}./{pname}" if pname else f"{ROMAN[idx - 1]}. Bataillon"
            if nat in COMMONWEALTH:
                rg = UK_REGIMENTS[(hash((pname, idx)) & 0x7FFFFFFF) % len(UK_REGIMENTS)]
                return f"{ordinal(game.rng.randint(1, 7))} Bn, {rg}" if nat == "uk" else f"{ordinal(idx)} Battalion, {pname}"
            if nat == "italy":
                return f"{idx}° Battaglione, {pname}"
            if nat == "france":
                return f"{idx}e Bataillon, {pname}"
            return f"{ordinal(idx)} Battalion, {pname}"
        if echelon == "regiment":
            if nat == "germany":
                return f"Grenadier-Regiment {num(1, 1100)}"
            if nat in COMMONWEALTH:
                return f"{ordinal(num(1, 250))} Infantry Brigade"
            if nat == "ussr":
                return f"{ordinal(num(1, 1400))} Rifle Regiment"
            if nat == "italy":
                return f"{num(1, 300)}° Reggimento Fanteria"
            if nat == "france":
                return f"{num(1, 170)}e Régiment d'Infanterie"
            if nat == "finland":
                return f"JR {num(1, 61)}"
            return f"{ordinal(num(1, 440))} Infantry Regiment"
        if echelon == "division":
            from .operations import DIV_STYLE
            hist = {r[2] for r in self._hist(game)}
            pool = [d for d in game.theatre.get("divisions", {}).get(nat, []) if d not in self._names()
                    and d not in hist and any(w in d for w in ("ivision", "Divisioona", "Divisione", "Division"))]
            if pool and game.rng.random() < 0.6:
                return pool[0]
            k = num(1, 400 if nat in ("germany", "ussr") else 120)
            return DIV_STYLE.get(nat, "{o} Division").format(n=k, o=ordinal(k))
        if echelon == "corps":
            k = num(1, 59)
            if nat == "germany":
                return f"{ROMAN[k - 1]}. {'Panzerkorps' if game.rng.random() < 0.3 else 'Armeekorps'}"
            if nat == "ussr":
                return f"{ordinal(k)} {'Guards ' if game.rng.random() < 0.25 else ''}Rifle Corps"
            if nat == "italy":
                return f"{ROMAN[k % 30]} Corpo d'Armata"
            return f"{ROMAN[k % 36]} Corps"
        if echelon == "army":
            if nat == "germany":
                k = num(1, 20)
                return f"{k}. {'Panzerarmee' if game.rng.random() < 0.3 else 'Armee'}"
            if nat == "ussr":
                return f"{ordinal(num(1, 70))} {'Guards ' if game.rng.random() < 0.25 else ''}Army"
            if nat in ("usa", "uk"):
                return f"{ARMY_WORD[num(1, len(ARMY_WORD)) - 1]} Army"
            if nat == "japan":
                return f"{ordinal(num(10, 36))} Army"
            if nat == "italy":
                return f"{num(1, 11)}ª Armata"
            return f"{ordinal(num(1, 9))} Army"
        if echelon == "army group":
            if nat == "germany":
                return f"Heeresgruppe {game.rng.choice(['Mitte', 'Nord', 'Süd', 'A', 'B', 'C', 'F', 'G'])}"
            if nat == "ussr":
                return f"{game.rng.choice(['1st Belorussian', '2nd Ukrainian', 'Bryansk', 'Kalinin', 'Steppe'])} Front"
            return f"{ordinal(num(6, 21))} Army Group"
        return echelon.title()

    def _names(self):
        return {n.name for n in self.nodes.values()}


# ---------------------------------------------------------------------- the game's side of it
def top_echelon(game):
    """The formation you command on the war map (None below colonel)."""
    from .command import ECHELONS, ROLE_ECHELON
    from .operations import ECHELON_FOR_GRADE
    p = game.player
    if p is None or game.command.strategic_reach(game) <= 0:
        return None
    cands = [e for e in (ROLE_ECHELON.get(p.role), ECHELON_FOR_GRADE.get(min(18, p.rank))) if e]
    cands = ["regiment" if e == "brigade" else e for e in cands if e in ECHELONS]
    cands = [e for e in cands if e in LEVELS and LEVELS.index(e) >= 1]
    if not cands:
        return None
    return max(cands, key=LEVELS.index)


def update(game):
    """Build or refresh your order of battle.  Returns the staff's reports of formations lost."""
    top = top_echelon(game)
    if top is None:
        return []
    ob = game.__dict__.get("oob")
    if ob is None or ob.top != top or ob.side != game.player_side:
        ob = game.oob = OOB(game.player_side, game.player_nation, top)
    st = game.strategic
    reach = game.command.strategic_reach(game)
    here = game.sector
    st.touch(here.x, here.y, TOUCH.get(top, 3))           # the front your command holds, laid out on the map
    mine = [s for s in st.active() if s.control == game.player_side and s.playable
            and abs(s.x - here.x) + abs(s.y - here.y) <= reach]
    # the ground you're standing on is always part of your command (if it's ours)
    if here.control == game.player_side and here not in mine:
        mine.append(here)
    return ob.update(game, mine)
