"""The chain of command.

Each side on the battlefield is organised into formations - squads in platoons,
platoons in companies, companies in a battalion - with commanders at every level.
The player holds a billet in that tree (rifleman, squad leader, platoon leader,
company commander ... five-star general) and may order:

  * any unit in their own chain of command, and
  * any other friendly unit whose leader they outrank.  Below general rank only
    within their own army: a British lieutenant can't order Americans about.

Orders travel by voice, hand signal, radio, relay through a subordinate
commander, or by runner, and all of them take time.  Units report back; what you
know of your own men is only as fresh as their last report.  Leaders die and the
next man takes over - sometimes that's you.  Merit earns promotion and medals.
"""
from __future__ import annotations

import math

from .ai import Order, order_target
from .constants import cap, other_side
from .data import ranks as R
from .data.nations import NATIONS, ordinal, random_name
from .data.phrases import ORDER_PHRASE, lang, phrase
from .senses import direction_word

ECHELONS = ["squad", "platoon", "company", "battalion", "regiment", "brigade", "division", "corps", "army",
            "army group"]
ECHELON_GRADE = {"squad": R.SERGEANT, "platoon": R.LT2, "company": R.CAPTAIN, "battalion": R.LT_COL,
                 "regiment": R.COLONEL, "brigade": R.BRIGADIER, "division": R.MAJ_GEN, "corps": R.LT_GEN,
                 "army": R.GENERAL, "army group": R.MARSHAL}
ROLE_ECHELON = {"company_commander": "company", "battalion_commander": "battalion",
                "regiment_commander": "regiment", "brigade_commander": "brigade",
                "division_commander": "division", "corps_commander": "corps", "army_commander": "army",
                "army_group_commander": "army group"}
# how many sectors of the war map a commander can reach
REACH = {R.COLONEL: 1, R.BRIGADIER: 1, R.MAJ_GEN: 2, R.LT_GEN: 3, R.GENERAL: 5, R.MARSHAL: 99}

# orders that can be passed by hand signal
SIGNAL_OK = {"move", "attack", "assault", "hold", "retreat", "regroup", "come", "dig", "flank"}
STATE_WORD = {"idle": "waiting", "hold": "holding", "advance": "advancing", "bound": "bounding forward",
              "assault": "assaulting", "flank": "flanking", "engaged": "in contact", "retreat": "falling back",
              "rout": "routing", "banzai": "charging", "follow": "following", "suppress": "suppressing",
              "resupply": "drawing ammunition"}
KIND_WORD = {"inf": "infantry", "mg": "an MG", "hmg": "a heavy MG", "sniper": "a sniper", "tank": "armour",
             "atgun": "an AT gun", "vehicle": "a vehicle", "sound": "movement", "bunker": "a bunker",
             "mortar": "mortars", "officer": "infantry"}


# ====================================================================== naming

def _cw(n):
    return R.COALITION.get(n) == "cw"


def _veh_short(name):
    import re
    name = re.sub(r"^[\d.,/]+ ?(cm|mm)\s+", "", name).replace("'", "")
    words = [w for w in name.split() if w not in ("QF", "OQF")]
    if not words:
        return "gun"
    base = words[0] + (" " + words[1] if len(words[0]) <= 3 and len(words) > 1 else "")
    return base[:11]


def company_name(nation, i):
    if nation == "usa":
        return f"Co. {'ABCDEFGHIKLM'[i % 12]}"
    if _cw(nation):
        return f"{'ABCD'[i % 4]} Company"
    return {"germany": f"{i + 1}. Kompanie", "italy": f"{i + 1}ª Compagnia", "france": f"{i + 1}e compagnie",
            "poland": f"{i + 1}. kompania", "finland": f"{i + 1}. komppania", "hungary": f"{i + 1}. század",
            "romania": f"Compania {i + 1}"}.get(nation, f"{ordinal(i + 1)} Company")


def platoon_name(nation, i, coy):
    if _cw(nation):
        return f"{coy * 3 + i + 7} Platoon"
    return {"germany": f"{i + 1}. Zug", "italy": f"{i + 1}° Plotone", "france": f"{i + 1}e section",
            "poland": f"{i + 1}. pluton", "finland": f"{i + 1}. joukkue"}.get(nation, f"{ordinal(i + 1)} Platoon")


def squad_name(nation, i):
    if _cw(nation):
        return f"{i + 1} Section"
    return {"germany": f"{i + 1}. Gruppe", "italy": f"{i + 1}ª Squadra", "france": f"{i + 1}e groupe",
            "poland": f"{i + 1}. drużyna", "finland": f"{i + 1}. ryhmä",
            "ussr": f"{ordinal(i + 1)} Section"}.get(nation, f"{ordinal(i + 1)} Squad")


def abbreviate(name: str) -> str:
    for a, b in (("Platoon", "Plt"), ("Company", "Coy"), ("Squad", "Sqd"), ("Section", "Sec"),
                 ("Kompanie", "Kp."), ("Battalion", "Bn"), ("Gruppe", "Gr."), ("Weapons", "Wpns")):
        name = name.replace(a, b)
    return name


SPECIAL_NAMES = {
    "weapons": {"usa": "Weapons Platoon", "germany": "schwerer Zug", "uk": "Support Platoon",
                "ussr": "Weapons Platoon"},
    "armour": {"usa": "Tank Platoon", "germany": "Panzerzug", "uk": "Tank Troop", "ussr": "Tank Platoon"},
    "guns": {"usa": "AT Platoon", "germany": "Pak-Zug", "uk": "Anti-Tank Platoon", "ussr": "AT Battery"},
    "garrison": {"usa": "Garrison troops", "germany": "Stützpunkt-Besatzung", "uk": "Garrison troops"},
}


def special_name(kind, nation):
    t = SPECIAL_NAMES[kind]
    return t.get(nation) or t.get("uk" if _cw(nation) else "usa")


# ====================================================================== formations

class Formation:
    def __init__(self, fid, side, nation, echelon, name, parent=None, special=None):
        self.id = fid
        self.side = side
        self.nation = nation
        self.echelon = echelon
        self.name = name
        self.special = special          # weapons / armour / guns / garrison
        self.parent = parent
        self.children: list[Formation] = []
        self.squads: list = []
        self.hq = None                  # the squad that is this formation's headquarters
        self.commander = None           # an Actor on the battlefield
        self.offmap = None              # (grade, name) - commanding from beyond the map edge
        self.acting = False
        self.callsign = ""
        self.oob_fid = None             # the formation in your order of battle (oob.py) this is
        if parent is not None:
            parent.children.append(self)

    @property
    def short(self):
        return abbreviate(self.name)

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def all_squads(self):
        out = []
        for f in self.walk():
            out += f.squads
        return out

    def live_squads(self):
        return [sq for sq in self.all_squads() if not sq.gone and (sq.members or sq.vehicles)]

    def maneuver_squads(self):
        return [sq for sq in self.squads if sq is not self.hq]

    def chain(self):
        f = self
        while f is not None:
            yield f
            f = f.parent

    def commander_grade(self):
        c = self.commander
        if c is not None and c.alive and c.state == "ok":
            return c.rank
        if self.offmap:
            return self.offmap[0]
        return -1

    def commander_label(self):
        c = self.commander
        if c is not None and c.alive and c.state == "ok":
            if c.is_player:
                return "you" + (" (acting)" if self.acting else "")
            return f"{c.rank_short} {c.last_name}" + (" (acting)" if self.acting else "")
        if self.offmap:
            g, nm = self.offmap[0], self.offmap[1]
            title = self.offmap[2] if len(self.offmap) > 2 else R.rank_title(self.nation, g)
            if self.__dict__.get("oob_fid") is not None:
                return f"{title} {nm}"
            return f"{title} {nm.split()[-1]} (off-map)"
        return "no commander"

    def title(self):
        if self.parent is not None and self.echelon == "platoon":
            return f"{self.name}, {self.parent.name}"
        return self.name


def leader_of(sq):
    ld = sq.leader
    if ld is not None and ld.active and not ld.downed and ld in sq.members:
        return ld
    cands = [m for m in sq.members if m.active and not m.downed]
    return max(cands, key=lambda m: (m.rank, m.skill)) if cands else None


def leader_grade(sq):
    ld = leader_of(sq)
    if ld is not None:
        return ld.rank
    if any(v.active for v in sq.vehicles):
        return getattr(sq, "leader_grade", R.SERGEANT)
    return -1


def leader_name(sq):
    ld = leader_of(sq)
    if ld is not None:
        return "you" if ld.is_player else f"{ld.rank_short} {ld.last_name}"
    if sq.vehicles:
        tc = sq.rep.get("tc")
        return tc or "the crew"
    return "nobody"


def contact_point(sq):
    ld = leader_of(sq)
    if ld is not None:
        if ld.vehicle is not None:
            return ld.vehicle.x, ld.vehicle.y
        return ld.x, ld.y
    for v in sq.vehicles:
        if v.active:
            return v.x, v.y
    return None


def strength(sq):
    return sum(1 for m in sq.members if m.active and not m.downed), sum(1 for v in sq.vehicles if v.active)


def strength_text(sq, known=None):
    """Men and vehicles - live, or as last reported (known: the command's snapshot)."""
    men, veh = strength(sq) if known is None else (known.get("men", 0), known.get("veh", 0))
    if veh and not men:
        return f"{veh} vehicle{'s' if veh != 1 else ''}"
    s = f"{men}/{max(men, sq.rep.get('men0', men))}"
    if veh:
        s += f" +{veh}v"
    return s


def unit_label(sq):
    return sq.short or sq.name


def vehicle_has_radio(game, v) -> bool:
    r = v.ai.get("radio")
    if r is None:
        vt = v.vt
        armoured = vt.vtype in ("tank", "td", "spg", "ltank", "armcar", "tankette")
        if not armoured:
            r = False
        else:
            n = v.nation
            p = {"usa": 1.0, "uk": 1.0, "canada": 1.0, "germany": 1.0, "australia": 1.0, "poland": 0.9,
                 "ussr": 0.9 if game.year >= 1943 else 0.25, "japan": 0.3, "italy": 0.8 if game.year >= 1942 else 0.2,
                 "france": 0.25, "china": 0.2}.get(n, 0.6)
            r = game.rng.random() < p
        v.ai["radio"] = r
    return r and v.parts.get("radio", 2) > 0          # fitted - and not shot to pieces (vdamage.py)


def has_radio(a) -> bool:
    return a.has_tool("radio") is not None or a.has_tool("handradio") is not None


HANDRADIO = {"usa": ("scr536", 1943.0, 0.85), "uk": ("ws38", 1942.0, 0.6), "canada": ("ws38", 1942.0, 0.6),
             "australia": ("ws38", 1942.5, 0.5), "newzealand": ("ws38", 1942.5, 0.5), "india": ("ws38", 1943.0, 0.4),
             "poland": ("ws38", 1943.5, 0.4), "germany": ("feldfu", 1944.0, 0.3)}


def squad_has_radio(game, sq) -> bool:
    for m in sq.members:
        if m.active and not m.downed and has_radio(m):
            return True
    return any(v.active and vehicle_has_radio(game, v) for v in sq.vehicles)


def low_on_ammo(sq) -> bool:
    """Half the squad's guns down to their last couple of magazines."""
    from .ammo import spare_rounds
    act = [m for m in sq.members if m.active and m.weapon is not None and m.weapon.t.kind == "gun"
           and m.weapon.t.cat not in ("at_disposable", "flamer")]
    if not act:
        return False
    low = sum(1 for m in act if m.weapon.loaded + spare_rounds(m, m.weapon) < m.weapon.t.mag * 2)
    return low >= max(1, len(act) // 2)


def ammo_points(game, side):
    """Ammunition dumps and crates on our side of the field."""
    from . import tiles as T
    import numpy as np
    m = game.map
    tid = T.ID["ammo_stack"]
    pts = getattr(m, "_ammo_tiles", None)
    if pts is None:
        pts = [(int(x), int(y)) for x, y in np.argwhere(m.t == tid)]
        m._ammo_tiles = pts
    out = [pt for pt in pts if m.t[pt[0], pt[1]] == tid]
    for (x, y), items in m.items.items():
        if any(it.tid == "ammo_crate" for it in items):
            out.append((x, y))
    edge = game.home_edge(side)
    if edge:
        def ours(pt):
            x, y = pt
            return {"N": y < m.h * 0.6, "S": y > m.h * 0.4, "W": x < m.w * 0.6, "E": x > m.w * 0.4}.get(edge, True)
        out = [pt for pt in out if ours(pt)]
    return out


def nearest_ammo(game, sq, max_d=999):
    pt = contact_point(sq)
    if pt is None:
        return None
    best = None
    bd = max_d
    for q in ammo_points(game, sq.side):
        d = max(abs(q[0] - pt[0]), abs(q[1] - pt[1]))
        if d < bd:
            best, bd = q, d
    return best


def status_word(sq):
    w = STATE_WORD.get(sq.state, sq.state)
    act = [m for m in sq.members if m.active]
    if act and sum(m.suppression for m in act) / len(act) > 55 and sq.state not in ("rout", "retreat"):
        w = "pinned down"
    return w


# ====================================================================== the player's command

class CommandState:
    def __init__(self):
        self.roots = {}                 # side -> top Formation (may sit above the battalion)
        self.bases = {}                 # side -> the battalion on this battlefield
        self.billet = None              # the Formation you command
        self.billet_squad = None        # the squad you lead in person
        self.attached = set()           # squad ids you've taken under command
        self.pending = []               # orders on their way
        self.known = {}                 # squad id -> last report {x, y, turn, men, state}
        self.merit = 0.0
        self.merit_at_promotion = 0.0
        self.medals: list[str] = []
        self.promotions: list = []
        self.battle = {"kills": 0, "objectives": 0, "acting": 0, "wounds": 0, "orders": 0}
        self.career = {"sectors": 0, "objectives": 0, "battles": 0}
        self.next_fid = 1
        self.report_turn = -99
        self.report_queue: list = []
        self.chatter_turn = 0
        self.refused = {}               # squad id -> turn they last refused
        self.strategic_orders = []      # standing orders on the war map
        self.last_quiet_check = 0
        self.fav_callsign = {}

    # ------------------------------------------------------------ building the order of battle
    def fid(self):
        self.next_fid += 1
        return self.next_fid

    def organise(self, game):
        """Build both sides' order of battle for a freshly populated sector."""
        if game.player is not None:
            from . import oob as OB
            OB.update(game)
        self.roots = {}
        self.bases = {}
        self.pending = []
        self.known = {}
        self.attached = set()
        self.billet = None
        self.billet_squad = None
        self.report_queue = []
        p = game.player
        if p is not None and "unit0" not in p.ai:
            p.ai["unit0"] = p.unit
        for sq in game.squads:
            sq.formation = None
        for side in (game.player_side, other_side(game.player_side)):
            squads = [sq for sq in game.squads if sq.side == side]
            nation = game.side_nation(side) if side != game.player_side else game.player_nation
            root = Formation(self.fid(), side, nation, "battalion", self._battalion_name(game, side, nation))
            root.offmap = (R.LT_COL, random_name(game.rng, nation, male=True))
            root.callsign = self._callsign(nation, 0, "bn")
            self.roots[side] = root
            self.bases[side] = root
            first = []
            if p is not None and side == p.side and p.squad is not None and p.squad in squads:
                first = [p.squad]
            order = first + [sq for sq in squads if sq.kind == "hq" and sq not in first] + \
                [sq for sq in squads if sq.kind != "hq" and sq not in first]
            for sq in order:
                self.attach_squad(game, sq)
        if p is not None:
            self._assign_billet(game)
        for root in self.bases.values():
            self._issue_radios(game, root)
        if p is not None:
            # the start-line positions everyone was given in the briefing
            for sq in self.chain_squads(game):
                self.known[sq.id] = self._snapshot(game, sq)

    def _issue_radios(self, game, root):
        """Platoon radios where the army had them."""
        from .entities import Item
        spec = HANDRADIO.get(root.nation)
        if spec is None:
            return
        iid, since, chance = spec
        if game.year < since:
            return
        for f in root.walk():
            if f.echelon != "platoon" or f.special is not None:
                continue
            c = f.commander
            if c is None or c.is_player or has_radio(c) or c.ai.get("radio_issued"):
                continue
            c.ai["radio_issued"] = True
            if game.rng.random() < chance:
                c.add_item(Item(iid))
        p = game.player
        if p is not None and p.side == root.side and p.role == "officer" and not has_radio(p) and \
                not p.ai.get("radio_issued") and game.rng.random() < chance:
            p.ai["radio_issued"] = True
            p.add_item(Item(iid))

    def _battalion_name(self, game, side, nation):
        p = game.player
        ob = game.__dict__.get("oob")
        if ob is not None and p is not None and side == p.side and game.sector is not None:
            fid = ob.local_battalion(game)
            if fid is not None and ob.node(fid) is not None:
                return ob.node(fid).name
        unit0 = p.ai.get("unit0", p.unit) if p is not None else ""
        if p is not None and side == p.side and unit0:
            parts = [x.strip() for x in unit0.split(",")]
            if len(parts) >= 3:
                return f"{parts[1]}, {parts[2]}"
            if len(parts) == 2:
                return parts[1]
        from .data.nations import unit_designation
        parts = [x.strip() for x in unit_designation(game.rng, nation).split(",")]
        return ", ".join(parts[1:3]) if len(parts) >= 3 else parts[-1]

    def _callsign(self, nation, i, level):
        names, boss = R.CALLSIGNS.get(nation, R.CALLSIGNS["usa"])
        if level == "bn":
            return {"usa": "Blue", "uk": "Hello", "germany": "Kranich", "ussr": "Sokol"}.get(nation, "Base")
        return names[i % len(names)]

    def _companies(self, root):
        return [f for f in root.children if f.echelon == "company"]

    def _new_company(self, game, root):
        i = len(self._companies(root))
        name = company_name(root.nation, i)
        p = game.player
        if p is not None and root.side == p.side and i == 0 and p.unit:
            name = p.ai.get("unit0", p.unit).split(",")[0].strip()
        f = Formation(self.fid(), root.side, root.nation, "company", name, root)
        f.offmap = (R.CAPTAIN, random_name(game.rng, root.nation, male=True))
        f.callsign = self._callsign(root.nation, i, "coy")
        return f

    def _special(self, game, parent, kind):
        for f in parent.children:
            if f.special == kind:
                return f
        f = Formation(self.fid(), parent.side, parent.nation, "platoon", special_name(kind, parent.nation), parent,
                      special=kind)
        return f

    def attach_squad(self, game, sq):
        """Fit a squad into its side's order of battle (on arrival, or when the tree is built)."""
        root = self.bases.get(sq.side)
        if root is None or getattr(sq, "formation", None) is not None:
            return
        kind = sq.kind
        p = game.player
        sq.rep["men0"] = max(sq.rep.get("men0", 0), len(sq.members))
        if getattr(sq, "no_count", False) and not (p is not None and p.squad is sq):
            f = self._special(game, root, "garrison")
        elif kind == "tank" or (sq.vehicles and not sq.members and kind not in ("atgun",)):
            f = self._special(game, root, "armour")
        elif kind == "atgun":
            f = self._special(game, root, "guns")
        elif kind == "hq":
            f = self._place_hq(game, root, sq, p)
        elif kind in ("mg", "mortar", "at", "sniper"):
            coys = self._companies(root) or [self._new_company(game, root)]
            coy = min(coys, key=lambda c: len(self._special(game, c, "weapons").squads))
            f = self._special(game, coy, "weapons")
        else:
            f = self._maneuver_platoon(game, root)
        f.squads.append(sq)
        sq.formation = f
        self._name_squad(sq, f)
        if sq.vehicles and not sq.members:
            sq.leader_grade = R.LT if (f.special == "armour" and len(f.squads) == 1) else R.SERGEANT
            sq.rep["tc"] = f"{R.rank_title(sq.nation, sq.leader_grade)} {random_name(game.rng, sq.nation).split()[-1]}"
        self._set_commander(game, f)

    def _place_hq(self, game, root, sq, p):
        mine = p is not None and p.squad is sq
        role = p.role if mine else None
        # the player's own HQ goes where the player's billet is
        if mine and role in ROLE_ECHELON and ECHELONS.index(ROLE_ECHELON[role]) >= ECHELONS.index("battalion"):
            root.hq = sq
            return root
        if mine and role == "company_commander":
            coy = next((c for c in self._companies(root) if c.hq is None), None) or self._new_company(game, root)
            coy.hq = sq
            return coy
        if mine and role == "officer":
            plt = self._leaderless_platoon(root) or self._new_platoon(game, root)
            plt.hq = sq
            return plt
        # others: company headquarters first, then platoon leaders
        coy = next((c for c in self._companies(root) if c.hq is None), None)
        if coy is None and not self._companies(root):
            coy = self._new_company(game, root)
        if coy is not None:
            coy.hq = sq
            return coy
        plt = self._leaderless_platoon(root)
        if plt is None:
            plt = self._new_platoon(game, root)
        plt.hq = sq
        return plt

    def _leaderless_platoon(self, root):
        for coy in self._companies(root):
            for plt in coy.children:
                if plt.special is None and plt.hq is None:
                    return plt
        return None

    def _new_platoon(self, game, root):
        coys = self._companies(root)
        coy = None
        for c in coys:
            if len([f for f in c.children if f.special is None]) < 3:
                coy = c
                break
        if coy is None:
            coy = self._new_company(game, root)
        i = len([f for f in coy.children if f.special is None])
        return Formation(self.fid(), root.side, root.nation, "platoon",
                         platoon_name(root.nation, i, coys.index(coy) if coy in coys else len(coys)), coy)

    def _maneuver_platoon(self, game, root):
        for coy in self._companies(root):
            for plt in coy.children:
                if plt.special is None and len(plt.maneuver_squads()) < 3:
                    return plt
        return self._new_platoon(game, root)

    def _name_squad(self, sq, f):
        if f.special in ("armour", "guns"):
            v = next((v for v in sq.vehicles), None)
            base = v.vt.name if v is not None else "section"
            i = len(f.squads)
            sq.short = f"{_veh_short(base)} {i}"
            sq.name = f"{base} ({f.short})"
            return
        if f.special == "garrison":
            sq.short = "Garrison"
            return
        if sq is f.hq:
            sq.short = f"{f.short} HQ"
            sq.name = f"{f.name} HQ"
            return
        if f.special == "weapons":
            sq.short = {"mg": "MG team", "mortar": "Mortars", "at": "AT team", "sniper": "Sniper"}.get(sq.kind,
                                                                                                     sq.kind)
            n = sum(1 for o in f.squads if o.kind == sq.kind)
            if n > 1:
                sq.short += f" {n}"
            sq.name = f"{sq.short}, {f.parent.name if f.parent else f.name}"
            return
        i = len(f.maneuver_squads()) - 1
        nm = squad_name(sq.nation, i)
        sq.short = f"{abbreviate(nm)}/{f.short.split()[0]}"
        sq.name = f"{nm}, {f.title()}"

    def _set_commander(self, game, f):
        """Who leads this formation now?"""
        old = f.commander
        f.acting = False
        f.commander = None
        if f.hq is not None and not f.hq.gone:
            ld = leader_of(f.hq)
            if ld is not None:
                f.commander = ld
                want = ECHELON_GRADE.get(f.echelon, 0)
                # a company HQ officer is the company commander: give him the bars for it
                if not ld.is_player and ld.rank >= R.LT2 and ld.rank < want and f.echelon == "company":
                    ld.rank = want
                f.acting = ld.rank < want - 1 if f.echelon != "platoon" else ld.rank < R.LT2
        if f.commander is None and f.echelon == "platoon" and f.special is None:
            # no officer: the senior squad leader has the platoon
            lds = [leader_of(sq) for sq in f.squads if not sq.gone]
            lds = [x for x in lds if x is not None]
            if lds:
                f.commander = max(lds, key=lambda m: (m.rank, m.skill))
                f.acting = f.commander.rank < R.LT2
        if f.commander is None and f.special == "weapons":
            lds = [x for x in (leader_of(sq) for sq in f.squads if not sq.gone) if x is not None]
            if lds:
                f.commander = max(lds, key=lambda m: (m.rank, m.skill))
                f.acting = True
        return old is not f.commander

    def _assign_billet(self, game):
        p = game.player
        sq = p.squad
        self.billet = None
        self.billet_squad = sq if (sq is not None and sq.player_led and sq.leader is p) else None
        root = self.roots.get(p.side)
        if root is None:
            return
        from . import oob as OB
        ob = game.__dict__.get("oob")
        if ob is not None and ob.root is not None and ob.side == p.side and OB.top_echelon(game) == ob.top:
            self._billet_from_oob(game, root, sq, ob)
            return
        if p.role in ROLE_ECHELON:
            ech = ROLE_ECHELON[p.role]
            if ECHELONS.index(ech) >= ECHELONS.index("battalion"):
                top = root
                # the formations above this battalion are the player's, commanded from its HQ
                cur = ECHELONS.index("battalion")
                want = ECHELONS.index(ech)
                chain_names = self._higher_names(game, p)
                # Commonwealth battalions sat in brigades; everyone else's in regiments
                skip = "regiment" if (_cw(p.nation) or ech == "brigade") else "brigade"
                while cur < want:
                    cur += 1
                    if ECHELONS[cur] == skip and ech != skip:
                        continue
                    up = Formation(self.fid(), root.side, root.nation, ECHELONS[cur],
                                   chain_names.get(ECHELONS[cur], cap(ECHELONS[cur])))
                    up.children.append(top)
                    top.parent = up
                    top = up
                self.roots[p.side] = top
                if top is not root:
                    root.commander = None
                    root.offmap = (R.LT_COL, random_name(game.rng, root.nation))
                else:
                    root.offmap = None
                top.commander = p
                top.offmap = None
                top.hq = sq
                if root.hq is sq and top is not root:
                    root.hq = None
                    root.squads.remove(sq)
                    top.squads.append(sq)
                    sq.formation = top
                self.billet = top
                # the obituary should name what you commanded
                names = [top.name]
                if top.echelon in ("battalion", "regiment", "brigade"):
                    div = chain_names.get("division")
                    if div and div not in top.name:
                        names.append(div)
                p.unit = ", ".join(names)
                return
        # otherwise: the formation whose HQ is the player's squad, if any
        if sq is not None and sq.formation is not None and sq.formation.hq is sq:
            f = sq.formation
            f.commander = p
            f.acting = p.rank < ECHELON_GRADE.get(f.echelon, 0) - (1 if f.echelon == "platoon" else 0)
            self.billet = f
        elif sq is not None and sq.formation is not None and sq.formation.commander is p:
            self.billet = sq.formation

    def _billet_from_oob(self, game, root, sq, ob):
        """Your command as it stands on the war map: every formation with its commander, down to the
        battalion in each sector - and on this battlefield, down to the squads."""
        from . import oob as OB
        p = game.player
        here = (game.sector.x, game.sector.y)
        local_fid = ob.local_battalion(game)

        def mk(n, parent):
            ech = OB.level_name(ob.nation, n.echelon)
            ech = ech if ech in ECHELONS else n.echelon
            grade, title, name, hist = ob.commander_full(game, n)
            if n.fid == local_fid:
                f = root
                f.name = n.name
                if parent is not None:
                    f.parent = parent
                    parent.children.append(f)
            else:
                f = Formation(self.fid(), root.side, root.nation, ech, n.name, parent)
            f.oob_fid = n.fid
            if n.fid != ob.root and (f is not root or f.commander is None or f.commander.is_player):
                f.offmap = (grade, name, title)
            for c in n.children:
                cn = ob.node(c)
                if cn is not None:
                    mk(cn, f)
            return f

        top = mk(ob.node(ob.root), None)
        if local_fid is None and root is not top:
            # this battlefield isn't one of your sectors (you've gone forward into an attack): the battalion
            # here belongs to the regiment next door it's attacking out of
            host = top
            st = game.strategic
            best = None
            for fid_ in [ob.bn_of.get((here[0] + dx, here[1] + dy)) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))]:
                if fid_ is not None and ob.node(fid_) is not None and ob.node(fid_).parent is not None:
                    best = ob.node(fid_).parent
                    break
            if best is not None:
                host = next((f for f in top.walk() if f.oob_fid == best), top)
            root.parent = host
            host.children.append(root)
            del st
        self.roots[p.side] = top
        top.commander = p
        top.offmap = None
        top.hq = sq
        if sq is not None:
            sq.short = {"army group": "Army Grp HQ", "army": "Army HQ", "corps": "Corps HQ", "division": "Div HQ",
                        "regiment": "Rgt HQ", "brigade": "Bde HQ"}.get(top.echelon, "HQ")
            sq.name = f"{top.name} headquarters"
        if sq is not None and sq.formation is not None and sq.formation is not top and sq in sq.formation.squads:
            if sq.formation.hq is sq:
                sq.formation.hq = None
            sq.formation.squads.remove(sq)
            top.squads.append(sq)
            sq.formation = top
            if root.hq is None or root.hq is sq:
                root.hq = None
                self._set_commander(game, root)
        self.billet = top
        # the formations above your own belong to someone else: the chain of command shows them (hierarchy.py)
        chain = {x.echelon: x.name for x in ob.chain(local_fid)} if local_fid else {}
        hn = self._higher_names(game, p)
        for e, nm in chain.items():
            hn[OB.level_name(ob.nation, e)] = nm
            hn[e] = nm
        p.unit = top.name

    def _higher_names(self, game, p):
        if "higher" in p.ai:
            return p.ai["higher"]
        parts = [x.strip() for x in (p.ai.get("unit0", p.unit) or "").split(",")]
        out = {}
        if len(parts) >= 3:
            out["regiment"] = parts[2]
        if len(parts) >= 4:
            out["division"] = parts[3]
        th = game.theatre
        nat = p.nation
        W = R.words(nat)
        out.setdefault("regiment", f"{ordinal(game.rng.randint(2, 400))} {W[3]}")
        out.setdefault("division", f"{ordinal(game.rng.randint(1, 120))} {W[4]}")
        out["brigade"] = {"usa": f"Combat Command {game.rng.choice('ABR')}",
                          "germany": f"Kampfgruppe {random_name(game.rng, 'germany').split()[-1]}",
                          "ussr": f"{ordinal(game.rng.randint(1, 250))} Tank Brigade"}.get(
            nat, f"{ordinal(game.rng.randint(1, 50))} Brigade")
        out["corps"] = {"germany": f"{'XIV LXXXIV II XLVII LVI'.split()[game.rng.randint(0, 4)]}. Armeekorps",
                        "ussr": f"{ordinal(game.rng.randint(1, 60))} Rifle Corps"}.get(
            nat, f"{['V', 'VII', 'XIX', 'XXX', 'II', 'I'][game.rng.randint(0, 5)]} Corps")
        out["army"] = {"germany": f"{game.rng.randint(1, 18)}. Armee", "ussr": f"{ordinal(game.rng.randint(1, 70))} Army",
                       "japan": f"{ordinal(game.rng.randint(14, 32))} Army"}.get(nat, f"{ordinal(game.rng.randint(1, 9))} Army")
        out["army group"] = {"germany": f"Heeresgruppe {game.rng.choice(['Mitte', 'Nord', 'Süd', 'B', 'C', 'A'])}",
                             "ussr": f"{game.rng.choice(['1st Belorussian', '1st Ukrainian', 'Voronezh', 'Western', 'Stalingrad', 'Don'])} Front",
                             "uk": "21st Army Group", "usa": "12th Army Group"}.get(nat, th.get("battle", "Army Group"))
        p.ai["higher"] = out
        return out

    # ------------------------------------------------------------ queries
    def billet_echelon(self):
        if self.billet is not None:
            return self.billet.echelon
        if self.billet_squad is not None:
            return "squad"
        return None

    def billet_title(self, game):
        p = game.player
        if self.billet is not None:
            f = self.billet
            t = f.title() if f.echelon == "platoon" else f.name
            return t + (" (acting)" if f.acting else "")
        if self.billet_squad is not None:
            return f"{unit_label(self.billet_squad)}"
        return ""

    def is_top_commander(self, game):
        return self.billet is not None and self.billet is self.roots.get(game.player_side)

    def chain_squads(self, game):
        out = []
        seen = set()
        if self.billet is not None:
            for sq in self.billet.live_squads():
                if id(sq) not in seen:
                    seen.add(id(sq))
                    out.append(sq)
        if self.billet_squad is not None and not self.billet_squad.gone and id(self.billet_squad) not in seen:
            out.insert(0, self.billet_squad)
            seen.add(id(self.billet_squad))
        for sq in game.squads:
            if sq.id in self.attached and id(sq) not in seen and not sq.gone:
                out.append(sq)
                seen.add(id(sq))
        return out

    def in_chain(self, game, sq):
        if sq.id in self.attached:
            return True
        if self.billet_squad is sq:
            return True
        f = getattr(sq, "formation", None)
        if f is None or self.billet is None:
            return False
        return any(x is self.billet for x in f.chain())

    def authority(self, game, sq):
        """(allowed, reason)."""
        p = game.player
        if sq.side != p.side:
            return False, "enemy"
        if self.in_chain(game, sq):
            return True, "chain"
        if sq is p.squad and sq.player_led:
            return True, "chain"
        lg = leader_grade(sq)
        if lg < 0:
            return False, "Nobody there is in any state to take orders."
        if p.rank <= lg:
            who = leader_name(sq)
            if p.rank == lg:
                return False, f"{cap(who)} is your equal, not your subordinate."
            return False, f"{cap(who)} outranks you."
        if not R.same_army(p.nation, sq.nation) and p.rank < R.BRIGADIER:
            return False, (f"They're {NATIONS[sq.nation]['adj']}. Below general rank you can't order "
                           f"another army's men about.")
        return True, "rank"

    def player_radio(self, game):
        """Can the player get on a radio right now: carrying one or with the radioman at hand?"""
        p = game.player
        if has_radio(p):
            return True
        if p.vehicle is not None and vehicle_has_radio(game, p.vehicle):
            return True
        staff = 12 if p.rank >= R.BRIGADIER else 3      # a general's staff keep the set within call
        for a in game.actors:
            if a is p or a.side != p.side or not a.active or a.downed or not has_radio(a):
                continue
            d = max(abs(a.x - p.x), abs(a.y - p.y))
            if a.squad is p.squad and d <= staff:
                return True
            if d <= 3 and p.rank >= R.LT2:
                return True
        return False

    def voice_range(self, game):
        return max(4, int(12 - getattr(game, "noise", 0) / 10))

    def runners(self, game):
        p = game.player
        sq = p.squad
        if sq is None:
            return []
        out = []
        for m in sq.members:
            if m is p or not m.active or m.downed or m.vehicle is not None or m.ai.get("runner"):
                continue
            if max(abs(m.x - p.x), abs(m.y - p.y)) > 10:
                continue
            if m.role in ("radioman", "medic") and len(sq.members) > 3:
                continue
            out.append(m)
        out.sort(key=lambda m: (m.role not in ("rifleman", "smg_gunner"), -m.skill))
        return out

    def channel(self, game, sq, kind=None):
        """How an order would reach this squad: dict(kind, delay, note) or None."""
        p = game.player
        if sq is p.squad and sq.player_led:
            return dict(kind="direct", delay=0, note="your own squad - they're right here")
        pt = contact_point(sq)
        if pt is None:
            return None
        px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        d = max(abs(pt[0] - px), abs(pt[1] - py))
        ld = leader_of(sq)
        buttoned = ld is None or ld.vehicle is not None
        vr = self.voice_range(game)
        if p.vehicle is not None:
            vr = 2
        deaf = ld is not None and ld.body.deaf > 0
        if ((buttoned and d <= 1) or (not buttoned and d <= vr)) and not deaf:
            note = "you bang on the hull and shout" if buttoned else "they can hear you"
            return dict(kind="voice", delay=2, note=note)
        m = game.map
        seen = m.in_bounds(*pt) and m.visible[pt[0], pt[1]]
        if not buttoned and seen and d <= 32 and (kind is None or kind in SIGNAL_OK):
            return dict(kind="signal", delay=4, note="hand signals - they can see you")
        if self.player_radio(game) and squad_has_radio(game, sq):
            return dict(kind="radio", delay=int(8 + d / 12), note="radio")
        # relay: radio or shout to their platoon commander, who passes it on
        f = getattr(sq, "formation", None)
        c = f.commander if f is not None else None
        if c is not None and c is not p and c.active and not c.downed and c.squad is not sq:
            cd = max(abs(c.x - px), abs(c.y - py))
            reach = cd <= vr or (self.player_radio(game) and c.squad is not None and squad_has_radio(game, c.squad))
            dd = max(abs(c.x - pt[0]), abs(c.y - pt[1]))
            if reach and dd <= 25:
                return dict(kind="relay", delay=int(10 + dd * 1.2 + (0 if cd <= vr else 8)),
                            note=f"through {c.rank_short} {c.last_name}")
        rs = self.runners(game)
        if rs:
            return dict(kind="runner", delay=int(d * 1.4) + 5, note=f"runner ({rs[0].rank_short} {rs[0].last_name})",
                        runner=rs[0])
        return None

    # ------------------------------------------------------------ issuing orders
    def make_order(self, game, kind, target=None, sq=None, roe=None):
        t = game.turn
        if kind == "come":
            p = game.player
            return Order("move", target=(p.x, p.y), radius=4, issued=t, src="player",
                         roe=roe or (sq.order.roe if sq is not None else "free"))
        radius = {"defend": 7, "hold": 6, "move": 4, "attack": 4, "assault": 4, "ambush": 6, "dig": 6}.get(kind, 5)
        carry = sq is not None and kind not in ("ambush",) and sq.order.kind != "ambush"
        o = Order(kind, target=target, radius=radius, issued=t, src="player",
                  roe=roe or (sq.order.roe if carry else "free"))
        if kind == "ambush":
            o.roe = "hold"
        # snap a target next to an objective onto it
        if target is not None and kind in ("attack", "defend", "move"):
            for i, ob in enumerate(game.map.objectives):
                if max(abs(ob.x - target[0]), abs(ob.y - target[1])) <= 3:
                    o.obj = i
                    o.radius = ob.radius
                    break
        return o

    def issue(self, game, squads, kind, target=None, roe=None, say=True, forced_channel=None, label=None):
        """Send an order to one or more squads.  Returns (sent, failures)."""
        p = game.player
        self._last_roe = roe or "free"
        sent = []
        fails = []
        runner_jobs = {}
        chans_used = set()
        for sq in squads:
            ok, why = self.authority(game, sq)
            if not ok:
                fails.append((sq, why))
                continue
            ch = forced_channel or self.channel(game, sq, kind)
            if ch is None:
                fails.append((sq, "no way to reach them"))
                continue
            if kind in ("roe", "release", "report", "attach", "mission", "appointment", "reassign", "build", "cancel_build") or kind.startswith("task_"):
                order = None
            elif kind in ("hold", "dig") and target is None:
                order = self.make_order(game, kind, contact_point(sq), sq)
            elif kind == "ambush" and target is None:
                order = self.make_order(game, "ambush", contact_point(sq), sq)
            elif kind == "resupply":
                q = nearest_ammo(game, sq)
                if q is None:
                    fails.append((sq, "no ammunition dump on our side of the field"))
                    continue
                order = self.make_order(game, "resupply", q, sq)
            else:
                order = self.make_order(game, kind, target, sq, roe)
            job = dict(sq=sq.id, kind=kind, order=order, roe=roe, channel=ch["kind"], issued=game.turn,
                       due=game.turn + ch["delay"], runner=None, payload=target)
            chans_used.add(ch["kind"])
            if ch["kind"] == "direct":
                self.deliver(game, sq, job, quiet=True)
                sent.append(sq)
                continue
            if ch["kind"] == "radio" and game.rng.random() < 0.04 + (0.15 if p.suppression > 40 else 0):
                job["garbled"] = True
            if ch["kind"] == "runner":
                r = ch.get("runner")
                if r is None:
                    fails.append((sq, "no runner"))
                    continue
                # one runner per destination squad; send another man for the next
                if r.id in runner_jobs:
                    others = [x for x in self.runners(game) if x.id not in runner_jobs]
                    if not others:
                        fails.append((sq, "no one left to send"))
                        continue
                    r = others[0]
                runner_jobs[r.id] = job
                job["runner"] = r.id
                r.ai["runner"] = dict(sq=sq.id, job=id(job))
                r.say(phrase(game.rng, r.nation, "runner"), game.turn)
            self.pending.append(job)
            sent.append(sq)
        if sent and say:
            self._announce(game, sent, kind, None if isinstance(target, dict) else target, label, chans_used)
        if sent:
            self.battle["orders"] += 1
        return sent, fails

    def _announce(self, game, sent, kind, target, label=None, chans=None):
        p = game.player
        chans = chans or set()
        what = ORDER_TEXT.get(kind, kind)
        if target is not None and not isinstance(target, dict):
            d = math.hypot(target[0] - p.x, target[1] - p.y)
            where = f" {direction_word(target[0] - p.x, target[1] - p.y)}, {int(d * 2.2 / 10) * 10 or 10} yards" \
                if d > 4 else " here"
        else:
            where = ""
        who = label or (unit_label(sent[0]) if len(sent) == 1 else f"{len(sent)} units")
        who = abbreviate(who.split(",")[0])
        if "radio" in chans or "relay" in chans:
            cs = self._callsign_for(game, sent[0])
            game.msg(f"You, on the radio: '{cs}, {what}{where}. Over.'", "radio")
            p.stance = p.stance
        if chans & {"voice", "direct"}:
            text = f"{who}! {cap(what)}{where}!" if kind != "roe" else f"{who}! {cap(what)}!"
            key = ORDER_PHRASE.get(kind if kind != "roe" else f"roe_{self._last_roe}")
            spoken = None
            if lang(p.nation) != "en":
                spoken = (phrase(game.rng, p.nation, key) if key else
                          game.shout(p, "attack") if kind in ("attack", "assault") else "")
            p.say(text, game.turn, voice=spoken)
            game.msg(f"You shout: '{text}'", "shout")
            game.emit_sound(p.x, p.y, 55, "shout", text, p.side, p)
        if "signal" in chans:
            game.msg(f"You signal {who}: {what}.", "info")
        if "runner" in chans:
            game.msg(f"You scribble the order for {who} and send a runner.", "info")

    def _callsign_for(self, game, sq):
        f = getattr(sq, "formation", None)
        if f is not None and f.special in ("armour", "guns"):
            base = {"armour": {"usa": "Steel", "uk": "Hotel", "canada": "Hotel", "germany": "Löwe",
                               "ussr": "Tigr", "japan": "Tora"},
                    "guns": {"usa": "Hammer", "uk": "Anvil", "germany": "Keule", "ussr": "Molot"}}[f.special]
            nm = base.get(sq.nation) or base.get("usa")
            return f"{nm} {f.squads.index(sq) + 1 if sq in f.squads else 1}"
        coy = None
        while f is not None:
            if f.echelon == "company":
                coy = f
                break
            f = f.parent
        base = coy.callsign if coy is not None and coy.callsign else (sq.short or "Unit")
        if sq.formation is not None and sq.formation.echelon == "platoon" and sq.formation.parent is coy:
            try:
                pi = [x for x in coy.children if x.special is None].index(sq.formation) + 1
                si = sq.formation.squads.index(sq) + 1
                return f"{base} {pi}-{si}"
            except ValueError:
                pass
        return base

    # ------------------------------------------------------------ delivery
    def update(self, game):
        t = game.turn
        if self.pending:
            keep = []
            for job in self.pending:
                sq = self._squad(game, job["sq"])
                if sq is None:
                    continue
                if job["runner"] is not None:
                    r = self._actor(game, job["runner"])
                    if r is None or not r.active or r.downed:
                        if t - job["issued"] > 30:
                            game.msg(f"Your runner to {unit_label(sq)} hasn't come back.", "warn")
                        else:
                            keep.append(job)
                            continue
                        continue
                    if t - job["issued"] > 600:
                        r.ai["runner"] = None
                        continue
                    keep.append(job)
                    continue
                if t >= job["due"]:
                    if job.get("garbled"):
                        game.msg(f"Radio: static. {unit_label(sq)} doesn't acknowledge.", "radio")
                        continue
                    self.deliver(game, sq, job)
                else:
                    keep.append(job)
            self.pending = keep
        if t % 25 == 0:
            for sq in game.squads:
                if getattr(sq, "formation", None) is None and not sq.gone and sq.side in self.bases:
                    self.attach_squad(game, sq)
        if t % 5 == 0:
            self._observe(game)
        if t % 10 == 3:
            self._succession(game)
        if t % 10 == 7:
            self._reports(game)
        self._flush_reports(game)
        if t % 30 == 11:
            self._chatter(game)

    def runner_destination(self, game, job):
        sq = self._squad(game, job["sq"])
        if sq is None:
            return None
        return contact_point(sq)

    def runner_arrived(self, game, runner, rjob):
        for job in list(self.pending):
            if job.get("runner") == runner.id and job["sq"] == rjob["sq"]:
                self.pending.remove(job)
                sq = self._squad(game, job["sq"])
                if sq is not None:
                    self.deliver(game, sq, job)
                break

    def _squad(self, game, sid):
        for sq in game.squads:
            if sq.id == sid:
                return sq if not sq.gone else None
        return None

    def _actor(self, game, aid):
        for a in game.actors:
            if a.id == aid:
                return a
        return None

    def deliver(self, game, sq, job, quiet=False):
        rng = game.rng
        t = game.turn
        p = game.player
        kind = job["kind"]
        ld = leader_of(sq)
        speaker = ld
        chan = job["channel"]
        if not self.authority(game, sq)[0]:
            return False
        if chan == "radio" and not (self.player_radio(game) and squad_has_radio(game, sq)):
            return False
        if sq.state == "rout":
            if not quiet and (chan in ("voice", "signal") or rng.random() < 0.5):
                game.msg(f"{unit_label(sq)} is running. Nobody's listening.", "warn")
            return False
        # a suicidal order to broken men: they may refuse - once
        if kind in ("attack", "assault", "flank") and sq.morale < 14 and not sq.player_led:
            last = self.refused.get(sq.id, -999)
            if t - last > 120 and rng.random() < 0.55:
                self.refused[sq.id] = t
                line = rng.choice(R.REFUSE.get(sq.nation, R.REFUSE["usa"])).format(
                    rank=R.address(sq.nation, p.rank))
                self._reply(game, sq, speaker, line, chan)
                game.msg("(Give the order again to insist. It will cost them.)", "system")
                return False
            if t - last <= 120:
                for m in sq.members:
                    m.morale -= 6
        if kind in ("mission", "appointment", "reassign"):
            from .intent import administer
            if not administer(game, sq, kind, job.get("payload") or {}):
                if not quiet:
                    game.msg(f"{unit_label(sq)}: appointment or mission could not be carried out.", "warn")
                return False
        elif kind == "build":
            from .fieldworks import assign
            payload = job.get("payload") or {}
            ok, why = assign(game, sq, payload.get("kind"), payload.get("point", (0, 0)))
            if not quiet:
                game.msg(why, "info" if ok else "warn")
            if not ok:
                return False
        elif kind == "cancel_build":
            from .fieldworks import cancel
            cancel(game, sq)
        elif kind == "roe":
            sq.order.roe = job["roe"]
            if sq.order.kind == "ambush" and job["roe"] == "free":
                sq.order.kind = "hold"
            sq.order.src = "player"
        elif kind == "release":
            sq.rep.pop("intent", None)
            from .fieldworks import cancel
            cancel(game, sq)
            sq.order.src = "ai"
            self.attached.discard(sq.id)
        elif kind == "report":
            self._report(game, sq, forced=True)
            return True
        elif kind == "attach":
            self.attached.add(sq.id)
        elif kind.startswith("task_"):
            from .tasks import assign, finish
            if kind == "task_stop":
                finish(game, sq, "stopped")
            else:
                assign(game, sq, kind[5:], by=p)
        else:
            o = job["order"]
            if o is None:
                return False
            if kind == "come":
                o.target = (p.x, p.y)
            sq.rep.pop("intent", None)
            from .fieldworks import cancel
            cancel(game, sq)
            self.apply(game, sq, o)
        if not self.in_chain(game, sq) and kind not in ("release",):
            self.attached.add(sq.id)
        self.known[sq.id] = self._snapshot(game, sq)
        if not quiet:
            line = rng.choice(R.ACK.get(sq.nation, R.ACK["usa"])).format(rank=R.address(sq.nation, p.rank))
            if kind == "attach" or (job.get("rank_attach") and rng.random() < 0.5):
                line = rng.choice(["Who the hell are you? ...Yes, sir.", "About time somebody took charge.",
                                   line])
            self._reply(game, sq, speaker, line, chan)
        return True

    def _reply(self, game, sq, speaker, line, chan):
        if speaker is not None and not speaker.is_player:
            speaker.say(line, game.turn, 3)
        if chan in ("radio", "relay"):
            game.msg(f"Radio ({unit_label(sq)}): '{line}'", "radio")
        elif chan == "runner":
            game.msg(f"{cap(unit_label(sq))} has your order. ({line})", "info")
        elif speaker is not None and game.can_see(speaker.x, speaker.y):
            game.msg(f"{speaker.rank_short} {speaker.last_name}: '{line}'", "shout")

    def apply(self, game, sq, o):
        """Put an order into effect."""
        sq.order = o
        sq.arrived = False
        sq.positions = {}
        sq.state_turn = game.turn
        k = o.kind
        if k == "assault":
            sq.state = "assault"
        elif k == "flank":
            sq.flank_target = o.target
            sq.state = "flank"
        elif k in ("hold", "dig"):
            sq.arrived = True
            sq.state = "hold"
        elif k == "retreat":
            sq.state = "retreat"
        elif k == "dismount":
            for v in sq.vehicles:
                if v.active and v.passengers:
                    game.disembark_all(v)
            o.kind = "hold"
            o.target = contact_point(sq)
            sq.arrived = True
        elif k == "suppress":
            sq.state = "suppress"
        if sq.player_led and k not in ("follow",):
            # the player's own squad carries out the order while the player stays in command
            sq.player_led = True

    # ------------------------------------------------------------ knowing where your men are
    def _snapshot(self, game, sq):
        pt = contact_point(sq) or (0, 0)
        men, veh = strength(sq)
        return dict(x=pt[0], y=pt[1], turn=game.turn, men=men, veh=veh, state=status_word(sq), ld=leader_name(sq))

    def _observe(self, game):
        p = game.player
        m = game.map
        vr = self.voice_range(game)
        for sq in self.chain_squads(game):
            pt = contact_point(sq)
            if pt is None:
                continue
            d = max(abs(pt[0] - p.x), abs(pt[1] - p.y))
            if d <= vr or (m.in_bounds(*pt) and m.visible[pt[0], pt[1]]):
                self.known[sq.id] = self._snapshot(game, sq)

    def known_of(self, game, sq):
        k = self.known.get(sq.id)
        if k is None and self.in_chain(game, sq) and game.turn < 30:
            k = self._snapshot(game, sq)          # the start-line positions from the briefing
            self.known[sq.id] = k
        return k

    # ------------------------------------------------------------ reports from subordinates
    def _can_report(self, game, sq):
        if sq.player_led:
            return None
        if self.player_radio(game) and squad_has_radio(game, sq):
            return "radio"
        pt = contact_point(sq)
        if pt is not None and max(abs(pt[0] - game.player.x), abs(pt[1] - game.player.y)) <= self.voice_range(game):
            return "voice"
        return None

    def _reports(self, game):
        t = game.turn
        for sq in self.chain_squads(game):
            if sq.player_led:
                continue
            ch = self._can_report(game, sq)
            rep = sq.rep
            men, veh = strength(sq)
            ev = None
            prev_men = rep.get("men", men)
            if sq.arrived and not rep.get("arrived") and sq.order.src == "player":
                ev = "arrived"
            elif men <= prev_men - 2:
                ev = "casualties"
            elif t - sq.last_contact < 10 and t - rep.get("contact_turn", -999) > 200:
                ev = "contact"
                rep["contact_turn"] = t
            elif sq.state == "retreat" and rep.get("state") != "retreat":
                ev = "retreat"
            rep["arrived"] = sq.arrived
            rep["state"] = sq.state
            if ev is None and t >= getattr(sq, "next_report", 0) and ch == "radio":
                ev = "routine"
            if ev is None:
                continue
            rep["men"] = men
            if ch is None:
                continue
            sq.next_report = t + game.rng.randint(150, 260)
            self.report_queue.append((self._priority(ev), t, sq.id, ev, ch))

    def _priority(self, ev):
        return {"casualties": 0, "contact": 1, "retreat": 1, "leader": 0, "arrived": 2, "routine": 3}.get(ev, 3)

    def _flush_reports(self, game):
        t = game.turn
        if not self.report_queue or t - self.report_turn < 12:
            return
        self.report_queue.sort()
        pri, when, sid, ev, ch = self.report_queue.pop(0)
        self.report_queue = [r for r in self.report_queue if t - r[1] < 120][:6]
        sq = self._squad(game, sid)
        if sq is None:
            return
        self.report_turn = t
        self._report(game, sq, ev=ev, ch=ch)

    def _report(self, game, sq, ev="routine", ch=None, forced=False):
        p = game.player
        ch = ch or self._can_report(game, sq) or "runner"
        self.known[sq.id] = self._snapshot(game, sq)
        pt = contact_point(sq)
        if pt is None:
            return
        men, veh = strength(sq)
        lead = {"arrived": "In position", "casualties": "Taking casualties",
                "retreat": "We're pulling back"}.get(ev) or cap(status_word(sq))
        d = math.hypot(pt[0] - p.x, pt[1] - p.y)
        if d > 6:
            lead += f", {int(d * 2.2 / 50 + 0.5) * 50 or 50} yards {direction_word(pt[0] - p.x, pt[1] - p.y)} of you"
        parts = [lead]
        parts.append(f"{men} men" + (f" and {veh} vehicle{'s' if veh != 1 else ''}" if veh else "")
                     if men else f"{veh} vehicle{'s' if veh != 1 else ''}")
        brain = game.brains[sq.side]
        cs = brain.nearest_contacts(pt[0], pt[1], 1, max_age=20)
        if cs:
            c = cs[0]
            dd = math.hypot(c.x - pt[0], c.y - pt[1])
            if dd < 45:
                parts.append(cap(f"{KIND_WORD.get(c.kind, 'enemy')} {int(dd * 2.2 / 50 + 0.5) * 50 or 50} yards "
                                 f"{direction_word(c.x - pt[0], c.y - pt[1])} of us"))
        if low_on_ammo(sq):
            parts.append("Low on ammunition")
        text = ". ".join(parts) + "."
        who = unit_label(sq)
        if ch == "radio":
            game.msg(f"Radio ({who}): '{text}'", "radio")
        else:
            ld = leader_of(sq)
            nm = f"{ld.rank_short} {ld.last_name}" if ld else who
            game.msg(f"{nm} ({who}): '{text}'", "shout")
            if ld is not None:
                ld.say(text[:40], game.turn, 2, voice=text if lang(ld.nation) == "en" else "", tone="talk")

    # ------------------------------------------------------------ succession
    def on_leader_change(self, game, sq, old, new):
        p = game.player
        if new is p:
            if not sq.player_led:
                sq.player_led = True
                sq.order = Order("follow", issued=game.turn, src="player")
                self.billet_squad = sq
                who = f"{old.rank_short} {old.last_name}" if old is not None else "Your squad leader"
                game.msg(f"{who} is down. You're the senior man left. The squad is yours.", "warn")
                self.battle["acting"] += 1
                self.merit += 3
                game.update_orders(force=True)
            return
        if self.in_chain(game, sq) and old is not None and not sq.player_led:
            ch = self._can_report(game, sq)
            if ch is not None:
                self.report_queue.append((0, game.turn, sq.id, "leader", ch))
                game.msg(f"{'Radio' if ch == 'radio' else unit_label(sq)}: '{old.rank_short} {old.last_name} "
                         f"is down. {new.rank_short} {new.last_name} has {unit_label(sq)}.'",
                         "radio" if ch == "radio" else "shout")
        for f in (getattr(sq, "formation", None),):
            if f is not None and f.hq is sq:
                self._set_commander(game, f)

    def _succession(self, game):
        p = game.player
        for side, root in self.roots.items():
            for f in root.walk():
                c = f.commander
                if c is None or (c.alive and c.state == "ok" and not c.downed):
                    continue
                if c.is_player:
                    continue
                prev = c
                changed = self._set_commander(game, f)
                if f.commander is None and f.echelon in ("company", "battalion"):
                    # the HQ is gone: the senior man in the formation takes over
                    cands = [leader_of(sq) for sq in f.live_squads()]
                    cands = [x for x in cands if x is not None]
                    if cands:
                        f.commander = max(cands, key=lambda m: (m.rank, m.is_player, m.skill))
                        f.acting = True
                if not changed and f.commander is prev:
                    continue
                if side != p.side:
                    continue
                if f.commander is p:
                    self._player_succeeds(game, f, prev)
                elif (p.squad is not None and p.squad in f.all_squads()) or \
                        (self.billet is not None and any(x is f for x in self.billet.chain())):
                    nm = f"{f.commander.rank_short} {f.commander.last_name}" if f.commander else "nobody"
                    game.msg(f"Word comes: {prev.rank_short} {prev.last_name} is down. {nm} has {f.name}.", "radio")

    def _player_succeeds(self, game, f, prev):
        p = game.player
        cur = self.billet_echelon()
        if cur is not None and ECHELONS.index(cur) >= ECHELONS.index(f.echelon):
            return
        self.billet = f
        f.acting = p.rank < ECHELON_GRADE.get(f.echelon, 0)
        self.battle["acting"] += 1
        self.merit += 4
        game.msg(f"{prev.rank_short} {prev.last_name} is dead. You're the senior {'man' if p.rank < R.LT2 else 'officer'} "
                 f"left: {f.title()} is yours. (C for command)", "warn")
        game.update_orders(force=True)

    # ------------------------------------------------------------ merit, promotion, medals
    def on_kill(self, game, victim):
        if victim.side == game.player.side or getattr(victim, "state", "ok") != "ok":
            return
        from .recognition import claim
        from .skills import use
        p = game.player
        tank = getattr(victim, "vt", None) is not None
        # Crew experience follows the job actually performed; kill credit is separate.
        skill = "gunnery" if p.vehicle is not None else "marksmanship"
        if p.vehicle is not None and p.vehicle.player_station == "driver":
            skill = "driving"
        use(game, p, skill, 2 if tank else .8)
        claim(game, "kills", .6 if tank else .15,
              f"knocking out the {victim.vt.name}" if tank else "your part in the fighting", victim.pos,
              restore_trust=not victim.ai.get('incapacitated_before_fatal_hit', False))

    def on_objective(self, game, i, side):
        p = game.player
        if side != p.side:
            return
        ob = game.map.objectives[i]
        near = max(abs(ob.x - p.x), abs(ob.y - p.y)) <= ob.radius + 12
        mine = any(sq.order.src == "player" and sq.order.obj == i for sq in self.chain_squads(game))
        if near or mine:
            self.career["objectives"] += 1
            from .recognition import claim
            from .skills import use
            claim(game, "objectives", 3, f"taking {ob.name}", ob.pos)
            use(game, p, "leadership" if mine else "observation", 4)

    def on_wounded(self, game):
        from .recognition import claim
        claim(game, "wounds", .2, "wounded in action")

    def on_sector_won(self, game, side):
        if side != game.player_side:
            return
        self.career["sectors"] += 1
        from .recognition import claim
        claim(game, "objectives", 3, f"the fighting for {game.sector.name}")
        self.consider_promotion(game, "the fighting for " + game.sector.name)

    def on_new_battle(self, game):
        self.career["battles"] += 1
        self.battle = {k: 0 for k in self.battle}

    def _medal(self, game, level):
        lst = R.MEDALS.get(game.player.nation, R.MEDALS["usa"])
        return lst[max(0, min(level, len(lst) - 1))]

    def _award(self, game, level, why, posthumous=False):
        name = self._medal(game, level)
        if name in self.medals and level > 0:
            name2 = f"{name} (second award)"
            if name2 in self.medals:
                return None
            name = name2
        self.medals.append(name)
        from .awards import record
        record(game, name, level, why, posthumous)
        if not posthumous:
            game.msg(f"You are awarded the {name} {why}.", "good")
            # This decoration records existing evidence; it is not a new witnessed deed.
            game.duty.rep = min(100., game.duty.rep + (6.0 if level > 0 else .5))
        return name

    def valour_score(self):
        b = self.battle
        return b["kills"] * .4 + 4 * b["objectives"] + 1.5 * b["wounds"]

    def _battle_awards(self, game, posthumous=False):
        s = self.valour_score()
        lvl = 0
        for need, l in ((24, 4), (15, 3), (9, 2), (5, 1)):
            if s >= need:
                lvl = l
                break
        if lvl and game.player.rank < R.BRIGADIER:
            from .recognition import recommend_award
            name = recommend_award(game, lvl, f"for gallantry at {game.sector.name}", posthumous)
            for k in ("kills", "objectives", "acting", "wounds"):
                if name is not None:
                    self.battle[k] = 0          # decorated for these deeds; start counting afresh
            return name
        if game.player.rank >= R.BRIGADIER and self.career["sectors"] >= 2 and self.career["sectors"] % 2 == 0:
            from .recognition import recommend_award
            return recommend_award(game, 3, "for the conduct of operations", posthumous)
        return None

    def posthumous(self, game):
        """Called when the player dies: the citation they won't read."""
        name = self._battle_awards(game, posthumous=True)
        return name

    def promotion_need(self, grade):
        if grade < R.SERGEANT:
            return 5 + grade * 2
        if grade < R.LT2:
            return 10 + (grade - R.SERGEANT) * 3
        if grade < R.COLONEL:
            return 14 + (grade - R.LT2) * 5
        return 30 + (grade - R.COLONEL) * 10

    def consider_promotion(self, game, why=""):
        from .recognition import consider
        return consider(game, why)

    def _after_promotion(self, game):
        p = game.player
        sq = p.squad
        if sq is None or sq.player_led:
            return
        ld = leader_of(sq)
        if ld is not None and ld is not p and p.rank > ld.rank and p.rank >= R.CORPORAL:
            sq.leader = p
            sq.player_led = True
            sq.order = Order("follow", issued=game.turn, src="player")
            self.billet_squad = sq
            ld.say(phrase(game.rng, ld.nation, "senior_now"), game.turn, tone="talk")
            game.msg(f"{ld.rank_short} {ld.last_name} hands you the squad.", "info")
        if p.rank >= R.LT2 and self.billet is None and sq.formation is not None:
            f = sq.formation
            if f.echelon == "platoon" and (f.commander is None or f.commander.rank < p.rank):
                f.commander = p
                f.acting = False
                self.billet = f
                game.msg(f"You're given {f.title()}.", "good")
        game.update_orders(force=True)

    # ------------------------------------------------------------ radio chatter
    def _chatter(self, game):
        p = game.player
        t = game.turn
        if t < self.chatter_turn or not self.player_radio(game):
            return
        rng = game.rng
        self.chatter_turn = t + rng.randint(90, 260)
        cands = [sq for sq in game.squads if sq.side == p.side and not sq.gone and squad_has_radio(game, sq)
                 and sq is not p.squad]
        if not cands:
            return
        sq = rng.choice(cands)
        cs = self._callsign_for(game, sq)
        root = self.roots.get(p.side)
        boss = root.callsign if root is not None else "Base"
        pt = contact_point(sq)
        brain = game.brains[sq.side]
        c = brain.nearest_contacts(pt[0], pt[1], 1, max_age=25) if pt else []
        st = sq.state
        if c and math.hypot(c[0].x - pt[0], c[0].y - pt[1]) < 35:
            k = KIND_WORD.get(c[0].kind, "enemy")
            lines = [f"{boss}, {cs}: we have {k} {direction_word(c[0].x - pt[0], c[0].y - pt[1])} of our position, "
                     f"engaging. Over.",
                     f"{cs} to {boss}: held up by {k}. Request fire on grid {c[0].x:03d}{c[0].y:03d}. Over.",
                     f"{boss}, this is {cs}, contact, wait out."]
        elif st == "retreat":
            lines = [f"{boss}, {cs}: we're pulling back, we can't hold here. Over.",
                     f"{cs}, {boss}: negative, hold your position! Hold! Over."]
        elif st in ("advance", "bound"):
            lines = [f"{boss}, {cs}: moving to phase line, no contact. Over.",
                     f"{cs} crossing the start line now. Out."]
        else:
            men, veh = strength(sq)
            lines = [f"{boss}, {cs}: in position, {men} effectives. Over.",
                     f"{cs}, {boss}: radio check, over. ... {boss}, {cs}: loud and clear, out.",
                     f"All stations {boss}: stand to. Out."]
        game.msg(f"Radio chatter: '{rng.choice(lines)}'", "radio")

    # ------------------------------------------------------------ the war map
    def strategic_reach(self, game):
        g = game.player.rank
        if g < R.COLONEL:
            return 0
        return max(v for k, v in REACH.items() if g >= k)

    def can_order_sector(self, game, s):
        st = game.strategic
        here = game.sector
        reach = self.strategic_reach(game)
        if reach <= 0:
            return False, "You don't command anything on that scale."
        from .intelligence import map_report
        report = map_report(game, s)
        if s is not here and (report is None or report["control"] != game.player_side):
            return False, "No friendly holding is marked on your situation sheet."
        if abs(s.x - here.x) + abs(s.y - here.y) > reach:
            return False, "Beyond your command."
        from .intelligence import headquarters
        if not self.player_radio(game) and not headquarters(game) and s is not here:
            return False, "You need a radio - or your staff - to reach them."
        return True, ""

    def add_strategic_order(self, game, kind, src, dst=None):
        self.strategic_orders = [o for o in self.strategic_orders if not (o["src"] == src and (
            o["kind"] == kind or kind in ("attack", "hold", "move") and o["kind"] in ("attack", "hold", "move")))]
        self.strategic_orders.append(dict(kind=kind, src=src, dst=dst, turn=game.turn))


ORDER_TEXT = {"move": "move up", "attack": "take that position", "assault": "assault, go now",
              "flank": "work around the flank", "suppress": "suppress that position", "defend": "hold that ground",
              "hold": "hold where you are", "dig": "dig in", "ambush": "set an ambush and hold your fire",
              "retreat": "fall back", "regroup": "close up on your leader", "come": "on me, to my position",
              "mount": "mount up", "dismount": "dismount", "roe": "change of fire orders",
              "report": "report your status", "release": "carry on, use your own judgement",
              "attach": "you're under my command", "resupply": "go back and draw ammunition",
              "task_ammo": "scrounge ammunition off the dead", "task_medical": "find dressings and medical kit",
              "task_weapons": "pick up grenades and any weapons", "task_papers": "search the enemy dead for papers",
              "task_casevac": "get the wounded back", "task_prisoners": "take the prisoners back",
              "task_repair": "give the tankers a hand", "task_stop": "leave that, back to your places"}
