"""The chain of command, all the way up - for you and for every other man on the field.

Your squad leader, platoon leader, company and battalion commanders are men on (or
just off) the battlefield.  Above them the regiment, the division, the corps, the
army, the army group or front, the theatre, the army's chief, the head of government
and the head of state.  Where history knows who held a post on a given day, that's
who holds it: Rommel is hit on 17 July 1944 and Kluge takes over Army Group B;
Roosevelt dies on 12 April 1945.  Everyone else is a man with a name, and men die.

You only know what you've been told.  When a commander above you falls, word takes
time to come down the line - quickly by radio, slowly by rumour.  Until it reaches
you, you believe the old man is still in charge.
"""
from __future__ import annotations

import datetime as dt

from .data import commanders as HC
from .data import ranks as R
from .data.nations import random_name

ECH_ORDER = ["squad", "platoon", "company", "battalion", "regiment", "brigade", "division", "corps", "army",
             "front", "army group", "theatre"]
GEN_GRADE = {"regiment": R.COLONEL, "brigade": R.BRIGADIER, "division": R.MAJ_GEN, "corps": R.LT_GEN,
             "army": R.GENERAL, "army group": R.MARSHAL, "front": R.GENERAL}
# chance a day that a commander at this level is killed, wounded, sacked or captured
DAILY_LOSS = {"regiment": 0.015, "brigade": 0.01, "division": 0.005, "corps": 0.002, "army": 0.001,
              "army group": 0.0008, "front": 0.0008}
FATES = [("killed by shellfire at his command post", 3), ("killed by a sniper", 2), ("wounded and evacuated", 4),
         ("relieved of command", 3), ("killed when his car hit a mine", 1), ("killed in an air attack", 2),
         ("taken ill and sent back", 2), ("captured when his headquarters was overrun", 1)]
# how long news takes to reach you, in turns (seconds): (with a radio nearby, without)
NEWS_DELAY = {"regiment": (120, 900), "brigade": (120, 900), "division": (300, 2400), "corps": (900, 5400),
              "army": (1800, 7200), "army group": (1800, 10800), "front": (1800, 10800), "theatre": (3600, 14400),
              "national": (1800, 7200)}


def _date(game) -> tuple:
    d = game.now()
    return (d.year, d.month, d.day)


def _in(holder, date) -> bool:
    a, b = holder[0], holder[1]
    return (a is None or a <= date) and (b is None or date < b)


def holder_at(holders, date):
    """The holder on `date` (from the historical list), or the last one if nobody's recorded after."""
    for h in holders:
        if _in(h, date):
            return h
    past = [h for h in holders if h[1] is not None and h[1] <= date]
    return past[-1] if past else holders[0]


def _parent_name(parent, date):
    if parent is None or isinstance(parent, str):
        return parent
    for a, b, name in parent:
        if (a is None or a <= date) and (b is None or date < b):
            return name
    return parent[-1][2]


def _title(nation, grade_or_title) -> str:
    if isinstance(grade_or_title, str):
        return grade_or_title
    return R.rank_title(nation, grade_or_title)


class Hierarchy:
    def __init__(self):
        self.gen = {}           # post key -> [dict(name, grade, since, fate)] for the posts history doesn't fill
        self.believed = {}      # post key -> the name you think holds it
        self.pending = {}       # post key -> (turn you'll hear, message, name)
        self.enemy_known = set()   # enemy formation names whose commanders intelligence has identified
        self.last_tick = 0

    # ------------------------------------------------------------ the posts
    def _formations(self, game, nation):
        th = game.theatre.get("id", "")
        return [r for r in HC.F.get(th, []) if nation in r[0]]

    def _find(self, game, nation, name):
        for r in self._formations(game, nation):
            if r[2] == name:
                return r
        return None

    def _gen_post(self, game, nation, echelon, name):
        key = ("gen", nation, echelon, name)
        lst = self.gen.get(key)
        if lst is None:
            rng = game.rng
            g = GEN_GRADE.get(echelon, R.COLONEL)
            if echelon == "division" and rng.random() < 0.3:
                g -= 1
            lst = self.gen[key] = [dict(name=random_name(rng, nation, male=True), grade=g, since=game.turn, fate=None)]
        return key, lst

    def _national(self, game, nation):
        th = game.theatre.get("id", "")
        return HC.NATIONAL_OVERRIDE.get(th, {}).get(nation) or HC.NATIONAL.get(nation, [])

    def _unit_parts(self, a):
        return [x.strip() for x in (a.ai.get("unit0") or a.unit or "").split(",") if x.strip()]

    def posts(self, game, a):
        """Every post above this man, bottom to top: (echelon, unit name, key, holder dict or tuple, kind)."""
        date = _date(game)
        nation = a.nation
        out = []
        sq = a.squad
        top_local = None
        if sq is not None:
            leader = sq.leader if sq.leader is not None and sq.leader.alive else None
            out.append(("squad", getattr(sq, "short", "") or sq.name, ("local", sq.id), leader, "local"))
            f = getattr(sq, "formation", None)
            while f is not None:
                out.append((f.echelon, f.name, ("local", "f", f.id), f, "formation"))
                top_local = f.echelon
                f = f.parent
        parts = self._unit_parts(a)
        # his designation reads company, (battalion,) regiment, division - the last two are what matter here
        div_part = parts[-1] if parts else None
        reg_part = parts[-2] if len(parts) >= 3 else None
        hist = (self._find(game, nation, div_part) if div_part else None) or \
            (self._find(game, nation, reg_part) if reg_part else None)
        lvl = ECH_ORDER.index(top_local) if top_local in ECH_ORDER else 0
        # the regiment (and the division, if history doesn't know it) is a man with a name
        for ech, part in (("regiment", reg_part), ("division", div_part)):
            if part is None or (hist is not None and hist[2] == part) or ECH_ORDER.index(ech) <= lvl:
                continue
            if ech == "division" and hist is not None:
                continue
            key, lst = self._gen_post(game, nation, ech, part)
            out.append((ech, part, key, lst[-1], "gen"))
            lvl = ECH_ORDER.index(ech)
        # history from there up
        r = hist
        if r is None:
            divs = [x for x in self._formations(game, nation) if x[1] in ("division", "brigade")]
            if divs:
                r = self._find(game, nation, _parent_name(divs[0][3], date))
            else:
                tops = [x for x in self._formations(game, nation)]
                r = tops[-1] if tops else None
                # climb to something with no lower historical formation: take the lowest listed
                if tops:
                    r = min(tops, key=lambda x: ECH_ORDER.index(x[1]) if x[1] in ECH_ORDER else 99)
        seen = set()
        while r is not None and r[2] not in seen:
            seen.add(r[2])
            ech = r[1]
            if ech not in ECH_ORDER or ECH_ORDER.index(ech) > lvl:
                out.append((ech, r[2], ("hist", r[2]), holder_at(r[4], date), "hist"))
                lvl = ECH_ORDER.index(ech) if ech in ECH_ORDER else lvl
            r = self._find(game, nation, _parent_name(r[3], date)) if r[3] else None
        if not any(p[4] == "hist" for p in out):
            # nothing historical above: the corps and army are men with names too
            hn = game.command._higher_names(game, a) if a.is_player else None
            for ech in ("corps", "army"):
                if ECH_ORDER.index(ech) <= lvl:
                    continue
                name = (hn or {}).get(ech) or f"{ech.title()} HQ"
                key, lst = self._gen_post(game, nation, ech, name)
                out.append((ech, name, key, lst[-1], "gen"))
        for post, holders in self._national(game, nation):
            out.append(("national", post, ("nat", nation, post), holder_at(holders, date), "hist"))
        return out

    # ------------------------------------------------------------ what you know
    def _true_name(self, game, holder, kind):
        if kind == "hist":
            return holder[3]
        if kind == "gen":
            return holder["name"]
        return None

    def label(self, game, nation, holder, kind, key, mine=True):
        """'Maj. Gen. Charles Gerhardt' - as far as you know."""
        if kind == "local":
            if holder is None:
                return "no leader"
            if holder.is_player:
                return "you"
            return f"{holder.rank_short} {holder.name}"
        if kind == "formation":
            return holder.commander_label()
        if not mine and key not in self.enemy_known and not (isinstance(key, tuple) and key[0] == "nat"):
            return "commander unknown"            # (everyone knows who runs the enemy's country)
        name = self.believed.get(key) if mine else None
        if kind == "hist":
            grade, true = holder[2], holder[3]
        else:
            grade, true = holder["grade"], holder["name"]
        if name is None or name == true:
            return f"{_title(nation, grade)} {true}"
        # you still think it's the old man
        return f"{name}"

    def chain_lines(self, game, a, viewer=None):
        """Printable chain for any soldier, as the viewer (default: you) knows it."""
        viewer = viewer or game.player
        mine = a.side == viewer.side
        out = []
        for ech, unit, key, holder, kind in self.posts(game, a):
            lab = self.label(game, a.nation, holder, kind, key, mine=mine)
            if ech == "national":
                out.append((unit, lab))
            else:
                out.append((f"{ech.title()}: {unit}", lab))
        return out

    # ------------------------------------------------------------ time passes
    def tick(self, game):
        """Every ten minutes: commanders fall; news travels."""
        rng = game.rng
        if game.turn - self.last_tick < 600:
            self._deliver(game)
            return
        self.last_tick = game.turn
        p = game.player
        # generated commanders: the odds of a day, a tenth of an hour at a time
        for key, lst in self.gen.items():
            ech = key[2]
            if rng.random() < DAILY_LOSS.get(ech, 0.002) / 144.0:
                cur = lst[-1]
                cur["fate"] = rng.choices([f for f, _ in FATES], [w for _, w in FATES])[0]
                nat = key[1]
                lst.append(dict(name=random_name(rng, nat, male=True), grade=max(R.MAJOR, cur["grade"] - (1 if rng.random() < 0.6
                                                                                            else 0)),
                                since=game.turn, fate=None))
        # the posts above you: has anything changed that you don't know about yet?
        if p is not None and p.alive:
            radio = game.player_near_radio(p.side)
            for ech, unit, key, holder, kind in self.posts(game, p):
                if kind not in ("hist", "gen"):
                    continue
                true = self._true_name(game, holder, kind)
                title = _title(p.nation, holder[2] if kind == "hist" else holder["grade"])
                known = self.believed.get(key)
                if known is None:
                    self.believed[key] = f"{title} {true}"     # what you were told when you joined
                    continue
                if known.endswith(true) or key in self.pending:
                    continue
                d = NEWS_DELAY.get(ech if ech in NEWS_DELAY else "national", (1800, 7200))
                when = game.turn + rng.randint(d[0] // 2, d[0]) if radio else game.turn + rng.randint(d[0], d[1])
                fate = self._fate_of_previous(game, key, kind, unit)
                where = unit if ech != "national" else f"the post of {unit}"
                msg = (f"Word comes down the line: {known} {fate}. {title} {true} takes over {where}."
                       if fate else f"Word comes down the line: {title} {true} now holds {where}.")
                self.pending[key] = (when, msg, f"{title} {true}")
        self._deliver(game)

    def _fate_of_previous(self, game, key, kind, unit):
        if kind == "gen":
            lst = self.gen.get(key) or []
            return lst[-2]["fate"] if len(lst) >= 2 else None
        date = _date(game)
        for recs in ([r for r in HC.F.get(game.theatre.get("id", ""), []) if r[2] == unit],):
            for r in recs:
                prev = [h for h in r[4] if h[1] is not None and h[1] <= date]
                if prev:
                    return prev[-1][4]
        nat = key[1] if len(key) > 2 else None
        for post, holders in self._national(game, nat) if nat else []:
            if post == unit:
                prev = [h for h in holders if h[1] is not None and h[1] <= date]
                if prev:
                    return prev[-1][4]
        return None

    def _deliver(self, game):
        for key, (when, msg, name) in list(self.pending.items()):
            if game.turn >= when:
                del self.pending[key]
                self.believed[key] = name
                game.msg(msg, "radio")

    def learn_enemy(self, game, unit_text=None, everything=False, nation=None):
        """Intelligence identifies enemy commanders: those in a man's designation (and above), or all of them."""
        th = game.theatre.get("id", "")
        recs = [r for r in HC.F.get(th, []) if nation is None or nation in r[0]]
        names = set()
        if everything:
            names = {r[2] for r in recs}
        elif unit_text:
            date = _date(game)
            todo = [r for r in recs if r[2] in unit_text]
            while todo:
                r = todo.pop()
                if r[2] in names:
                    continue
                names.add(r[2])
                par = _parent_name(r[3], date)
                todo += [x for x in recs if x[2] == par]
            for part in [x.strip() for x in unit_text.split(",")]:
                for key in self.gen:
                    if key[3] == part:
                        self.enemy_known.add(key)
        for n in names:
            self.enemy_known.add(("hist", n))
        return len(names)
