"""The general's war: divisions and corps, not squads.

From a colonel's regiment to a field marshal's army group, what you command is laid
out across the war map as formations: divisions holding a sector or two each, grouped
into corps and armies.  You give a division an order - attack that sector, hold, move
over there, come out of the line into reserve - and your staff turns it into orders
for every battalion in it.  Attacks by several divisions on the same objective go in
together.  Replacements and fresh units come to your reserve; you decide where they go.
Every ten minutes your chief of staff brings the situation report: strengths, losses,
ground won and lost.  Win ground and you'll be promoted.  Lose it, and bleed your
divisions white doing it, and you'll be relieved.

The numbers are the game's own: each strategic unit is exactly what the battlefield puts
on the ground when you're there - a squad, a gun team, a tank and its crew - so the men,
tanks and guns on this screen are the ones you'll find (and the ones on the map you're
standing on are counted, not estimated).  An attack ordered here goes in for real: walk
or drive into the sector and you're in it; stand next door and you hear it.
"""
from __future__ import annotations

from collections import Counter

from .data import ranks as R
from .data.nations import ordinal, random_name

# what each strategic unit actually is on the ground: one squad, team, gun or vehicle (see spawn.spawn_units)
HEADS = {"mg": 3.5, "mortar": 2.5, "at": 3, "hq": 4, "sniper": 1.4, "eng": 6.4, "tank": 5, "td": 4, "atgun": 4, "ht": 2}
DIV_STYLE = {"germany": "{n}. Infanterie-Division", "ussr": "{o} Rifle Division", "usa": "{o} Infantry Division",
             "uk": "{o} Infantry Division", "canada": "{o} Canadian Infantry Division", "italy": "{n}ª Divisione di fanteria",
             "japan": "{o} Division", "france": "{n}e Division d'Infanterie", "finland": "{n}. Divisioona",
             "hungary": "{o} Light Division", "romania": "{o} Infantry Division", "poland": "{o} Infantry Division",
             "china": "{o} Division", "australia": "{o} Australian Division", "newzealand": "{o} New Zealand Division",
             "india": "{o} Indian Division"}
ECHELON_FOR_GRADE = {13: "regiment", 14: "brigade", 15: "division", 16: "corps", 17: "army", 18: "army group"}


def strength(units: Counter, nation="usa", installs=(), staff=False) -> dict:
    """The men, tanks and guns these units put on the ground when a battle is fought there -
    exactly what the battlefield spawns: one squad per infantry unit, one vehicle (and crew) per
    armoured unit, a rifle squad riding each half-track, three or four guns per battery."""
    from .data.roles import SQUAD_SIZE
    sq = SQUAD_SIZE.get(nation, 8)
    men = 0.0
    for k, n in units.items():
        if k == "inf":
            men += n * sq
        elif k == "ht":
            men += n * (HEADS["ht"] + sq)
        else:
            men += n * HEADS.get(k, 4)
    tanks = units.get("tank", 0) + units.get("td", 0)
    guns = units.get("atgun", 0) + 2 * units.get("mortar", 0)
    if staff and sum(units.values()) > 0:
        men += 4.5                  # the aid post (a surgeon, two orderlies) and the ammunition point
    for kind in installs:
        if kind == "artillery":
            guns += 3.5
            men += 16
        elif kind == "aa":
            guns += 3
            men += 12
        elif kind == "hq":
            men += 9                # a guard section and the intelligence officer
        elif kind == "depot":
            men += 1
    return dict(men=int(round(men)), tanks=int(tanks), guns=int(round(guns)), halftracks=units.get("ht", 0))


def live_strength(game, side) -> dict:
    """Counted, not estimated: the men, tanks and guns of ours on this battlefield right now (and the
    waves still on their way in)."""
    men = sum(1 for a in game.actors if a.side == side and a.alive and a.state == "ok")
    men += sum(v.crew for v in game.vehicles if v.side == side and not v.dead)
    tanks = sum(1 for v in game.vehicles if v.side == side and not v.dead and v.vt.vtype in ("tank", "ltank", "td", "spg"))
    guns = sum(1 for v in game.vehicles if v.side == side and not v.dead and v.vt.vtype in ("atgun", "fieldgun", "aagun"))
    guns += sum(1 for a in game.actors if a.side == side and a.alive and
                any(it.t.kind == "gun" and it.t.get("cat") == "mortar" for it in a.inv))
    ht = sum(1 for v in game.vehicles if v.side == side and not v.dead and v.vt.vtype == "halftrack")
    for w in game.waves:
        if w["side"] == side:
            s = strength(w["units"], game.side_nation(side))
            men += s["men"]
            tanks += s["tanks"]
            guns += s["guns"]
    return dict(men=men, tanks=tanks, guns=guns, halftracks=ht)


class Operations:
    def __init__(self):
        self.divs = {}           # id -> dict(name, corps, sectors: set of (x, y), order, target, status, log)
        self.div_of = {}         # (x, y) -> division id
        self.corps = {}          # id -> dict(name, divs)
        self.reserve = Counter()
        self.arriving = []       # (tick due, (x, y), Counter)
        self.next_id = 1
        self.reports = []
        self.score = 0.0         # ground won and lost, weighed
        self.last_held = None
        self.last_strength = None
        self.warnings = 0
        self.chief = None

    # ------------------------------------------------------------ building the order of battle
    def _div_name(self, game, i):
        nat = game.player_nation
        th = game.theatre
        pool = [d for d in th.get("divisions", {}).get(nat, []) if "Division" in d or "Divisioona" in d
                or "Army" in d or "division" in d.lower()]
        used = {d["name"] for d in self.divs.values()}
        for d in pool:
            if d not in used:
                return d
        for _ in range(20):
            n = game.rng.randint(1, 120 if nat not in ("finland", "newzealand") else 18)
            name = DIV_STYLE.get(nat, "{o} Division").format(n=n, o=ordinal(n))
            if name not in used:
                return name
        return name

    def organise(self, game):
        """Your formations, from the order of battle (oob.py): the ones you give orders to on the war map
        are the level below your own command (battalions for a colonel, regiments for a division,
        divisions from corps up), grouped under the level above them."""
        from . import oob as OB
        if game.command.strategic_reach(game) <= 0:
            return
        if self.chief is None:
            self.chief = random_name(game.rng, game.player_nation)
        for r in OB.update(game):
            if r not in self.reports:
                self.reports.append(r)
        ob = game.__dict__.get("oob")
        if ob is None or ob.root is None:
            return
        top = ob.top
        unit_ech = {"regiment": "battalion", "division": "regiment"}.get(top, "division")
        i = OB.LEVELS.index(unit_ech)
        group_ech = OB.LEVELS[i + 1] if OB.LEVELS[i + 1] != top else None
        divs = {}
        for n in ob.at_level(unit_ech):
            old = self.divs.get(n.fid)
            if old is None or old.get("fid") != n.fid:
                old = dict(fid=n.fid, order="hold", target=None, status="holding", log=[], since=game.turn)
            old["name"] = n.name
            old["sectors"] = ob.sectors_of(n.fid)
            old["echelon"] = OB.level_name(ob.nation, unit_ech)
            par = ob.node(n.parent)
            old["corps"] = par.fid if group_ech and par is not None and par.echelon == group_ech else None
            if old["sectors"]:
                divs[n.fid] = old
        self.divs = divs
        self.div_of = {k: fid for fid, d in divs.items() for k in d["sectors"]}
        self.corps = {}
        if group_ech:
            for g in ob.at_level(group_ech):
                chain = [x.name for x in ob.chain(g.fid) if x.fid != ob.root]
                self.corps[g.fid] = dict(name=" / ".join(reversed(chain)), divs=[c for c in g.children if c in divs],
                                         echelon=OB.level_name(ob.nation, group_ech))

    def div_units(self, game, did) -> Counter:
        st = game.strategic
        side = game.player_side
        u = Counter()
        for k in self.divs[did]["sectors"]:
            c = st.at(*k)
            if c is None or c is game.sector:
                continue
            u.update(c.units[side])
        return u

    def div_strength(self, game, did) -> dict:
        """Men, tanks and guns: counted on the battlefield you're on, from the units elsewhere."""
        st = game.strategic
        side = game.player_side
        nat = game.player_nation
        out = dict(men=0, tanks=0, guns=0, halftracks=0)
        for k in self.divs[did]["sectors"]:
            c = st.at(*k)
            if c is None:
                continue
            if c is game.sector:
                s = live_strength(game, side)
            else:
                s = strength(c.units[side], nat, [i[0] for i in c.installs(side)], staff=True)
            for key in out:
                out[key] += s[key]
        return out

    def totals(self, game) -> dict:
        t = dict(men=0, tanks=0, guns=0, halftracks=0)
        for did in self.divs:
            s = self.div_strength(game, did)
            for k in t:
                t[k] += s[k]
        r = strength(self.reserve, game.player_nation)
        for k in t:
            t[k] += r[k]
        # reserves on the road to the front are still ours (not casualties)
        for _due, _k, u in getattr(self, "arriving", []):
            a = strength(u, game.player_nation)
            for k in t:
                t[k] += a[k]
        return t

    # ------------------------------------------------------------ orders
    def order(self, game, did, kind, target=None):
        """A division order: attack / hold / move / reserve / counterattack."""
        d = self.divs.get(did)
        if d is None:
            return "No such division."
        from .intelligence import headquarters, map_sector
        if not game.command.player_radio(game) and not headquarters(game):
            return "The staff needs a working radio or a command post to transmit these orders."
        st = game.strategic
        d["order"], d["target"] = kind, target
        d["since"] = game.turn
        cmd = game.command
        side = game.player_side
        # the staff turns it into sector orders for every battalion in the division
        for k in list(d["sectors"]):
            cmd.strategic_orders = [o for o in cmd.strategic_orders if tuple(o["src"]) != k]
        if kind == "attack" and target:
            tgt = st.at(*target)
            if tgt is None or map_sector(game, tgt).control == side:
                return "That is marked as friendly ground on your situation sheet."
            srcs = [k for k in d["sectors"] if abs(k[0] - target[0]) + abs(k[1] - target[1]) == 1]
            if not srcs:
                return f"{d['name']} isn't next to {tgt.name}. Move it up first."
            for k in srcs:
                cmd.add_strategic_order(game, "attack", k, target)
            for k in d["sectors"]:
                if k not in srcs:
                    cmd.add_strategic_order(game, "hold", k)
            d["status"] = f"attacking {tgt.name}"
            return f"{d['name']} will attack {tgt.name}."
        if kind == "move" and target:
            tgt = st.at(*target)
            if tgt is None or map_sector(game, tgt).control != side:
                return "No friendly route is marked there on your situation sheet."
            for k in d["sectors"]:
                if k != tuple(target):
                    cmd.add_strategic_order(game, "move", k, target)
            d["status"] = f"moving to {tgt.name}"
            return f"{d['name']} is moving up to {tgt.name}."
        if kind == "hold":
            for k in d["sectors"]:
                cmd.add_strategic_order(game, "hold", k)
            d["status"] = "digging in"
            return f"{d['name']} will dig in and hold."
        if kind == "reserve":
            # out of the line: half of it, to be refitted and sent where you choose
            got = Counter()
            for k in d["sectors"]:
                c = st.at(*k)
                if c is None or c is game.sector:
                    continue
                got.update(st._detach(c.units[side], 0.5))
            self.reserve.update(got)
            d["status"] = "half pulled back into reserve"
            n = strength(got, game.player_nation)["men"]
            return f"{d['name']} sends {n:,} men back into army reserve."
        return "Understood."

    def commit(self, game, target, share=0.5):
        """Send part of the reserve to a sector: it arrives in half an hour or so."""
        from .intelligence import headquarters, map_sector
        if not game.command.player_radio(game) and not headquarters(game):
            return "No working radio or command post to reach the reserve."
        st = game.strategic
        c = st.at(*target)
        if c is None or map_sector(game, c).control != game.player_side:
            return "Reserves go to our own sectors."
        if sum(self.reserve.values()) == 0:
            return "The reserve is empty."
        sent = st._detach(self.reserve, share)
        if sum(sent.values()) == 0:
            sent, self.reserve = Counter(self.reserve), Counter()
        self.arriving.append((st.ticks + 3, tuple(target), sent))
        s = strength(sent, game.player_nation)
        return f"{s['men']:,} men, {s['tanks']} tanks and {s['guns']} guns of the reserve are on the road to {c.name}."

    # ------------------------------------------------------------ every strategic tick
    def before_tick(self, game):
        """Standing division orders go out again; converging attacks go in together (the planning shows)."""
        st = game.strategic
        for did, d in list(self.divs.items()):
            if d["order"] in ("attack", "move") and d["target"]:
                c = st.at(*d["target"])
                done = c is None or (d["order"] == "attack" and c.control == game.player_side)
                if not done:
                    self.order(game, did, d["order"], d["target"])
        targets = Counter(tuple(o["dst"]) for o in game.command.strategic_orders if o["kind"] == "attack" and o.get("dst"))
        st.concentration = {t: n for t, n in targets.items() if n >= 2}

    def after_tick(self, game):
        """Arrivals, replacements, the situation report, and what the high command thinks of you."""
        st = game.strategic
        side = game.player_side
        rng = game.rng
        self.organise(game)
        keep = []
        for due, k, u in self.arriving:
            if st.ticks >= due:
                c = st.at(*k)
                if c is not None and c.control == side:
                    if c is game.sector:
                        game.schedule_wave(side, u, game.home_edge(side) or "S", delay=rng.randint(20, 90))
                    else:
                        c.units[side].update(u)
                    self.reports.append(f"Reserves have arrived at {c.name}.")
                else:
                    self.reserve.update(u)
            else:
                keep.append((due, k, u))
        self.arriving = keep
        # fresh units from the rear, for you to place
        if st.ticks % 3 == 0 and game.player.rank >= 15:
            self.reserve["inf"] += st.sc(rng.randint(1, 3))
            if game.theatre["armor"].get(side, 0) > 0.3 and rng.random() < 0.5:
                self.reserve["tank"] += st.sc(1)
        # the report
        from .intelligence import headquarters
        if not game.command.player_radio(game) and not headquarters(game):
            return
        reports = st.__dict__.get("situation_reports", {}).get(side, {})
        keys = {k for d in self.divs.values() for k in d["sectors"]}
        held = sum(reports.get(k, {}).get("control") == side for k in keys)
        units = Counter()
        for k in keys:
            units.update(reports.get(k, {}).get("units", {}).get(side, {}))
        tot = strength(units, game.player_nation)
        lines = []
        if self.last_held is not None:
            dh = held - self.last_held
            if dh > 0:
                lines.append(f"We have gained {dh} sector{'s' if dh > 1 else ''}.")
                self.score += dh
            elif dh < 0:
                lines.append(f"We have lost {-dh} sector{'s' if dh < -1 else ''}.")
                self.score += dh * 1.3
        if self.last_strength is not None:
            lost = self.last_strength["men"] - tot["men"]
            if lost > 0:
                lines.append(f"Casualties since the last report: about {lost:,} men"
                             + (f", {self.last_strength['tanks'] - tot['tanks']} tanks" if self.last_strength['tanks']
                                > tot['tanks'] else "") + ".")
                if lost > self.last_strength["men"] * 0.08:
                    self.score -= 0.5
        for did, d in self.divs.items():
            if d["order"] == "attack" and d["target"]:
                c = st.at(*d["target"])
                if c is not None and reports.get(tuple(d["target"]), {}).get("control") == side:
                    lines.append(f"{d['name']} has taken {c.name}!")
                    d["order"], d["target"], d["status"] = "hold", None, "consolidating"
                    game.command.strategic_orders = [o for o in game.command.strategic_orders
                                                     if tuple(o["src"]) not in d["sectors"]]
        lines += self.reports
        self.reports = []
        self.last_held = held
        self.last_strength = tot
        if lines:
            game.msg(f"Situation report ({self.chief}, chief of staff): " + " ".join(lines[:5]), "radio")
        self._judge(game)

    def _judge(self, game):
        """The high command keeps score."""
        p = game.player
        if self.score >= 4:
            self.score = 0
            game.command.merit += 10
            game.msg("A signal from higher headquarters: your command is mentioned in dispatches. Well done.", "good")
        elif self.score <= -4:
            self.score = 0
            self.warnings += 1
            if self.warnings >= 2 and p.rank > R.COLONEL:
                p.rank -= 1
                game.msg(f"You are relieved of your command. Higher headquarters sends a replacement; you are "
                         f"reduced to {R.rank_title(p.nation, p.rank, False)} and told to wait for orders.", "death")
                self.warnings = 0
            else:
                game.msg("A curt signal from higher headquarters: 'Explain your losses.' Another setback and you'll "
                         "be relieved.", "warn")
