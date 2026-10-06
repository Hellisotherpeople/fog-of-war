"""Command appointments and standing missions, executed by subordinate leaders."""
from __future__ import annotations

from .ai import Order
from .command import contact_point, leader_of, low_on_ammo, nearest_ammo
from .intelligence import distance, local_contacts

# Short period terms; explanations and source limitations are in COMMAND_REALISM.md.
PROFILES = {
    "usa": ("Fire and maneuver", "fire", "bounded"),
    "germany": ("Schwerpunkt / Auftrag", "flank", "free"),
    "uk": ("Fire and movement", "fire", "bounded"),
    "ussr": ("Main attack / successive objectives", "concentrate", "bounded"),
    "japan": ("Envelopment / infiltration", "flank", "bounded"),
    "france": ("Feu et mouvement", "fire", "bounded"),
    "italy": ("Fuoco e movimento", "fire", "bounded"),
    "finland": ("Local initiative / envelopment", "flank", "free"),
}
MISSIONS = {"seize": "Seize and consolidate", "defend": "Defend this area",
            "screen": "Screen and report", "reserve": "Reserve; support nearby units"}
FREEDOM = {"restricted": (8, "Stay on the assigned ground"),
           "bounded": (20, "Local maneuver within the assigned area"),
           "free": (36, "Choose your approach within the mission")}
LOSSES = {"cautious": .15, "normal": .3, "press": .5}


def profile(nation):
    from .data.ranks import COALITION
    return PROFILES.get("uk" if COALITION.get(nation) == "cw" else nation,
                        ("Fire and movement", "fire", "bounded"))


def formations(game):
    seen = set()
    for root in game.command.bases.values():
        while root.parent is not None:
            root = root.parent
        for f in root.walk():
            if f.id not in seen:
                seen.add(f.id)
                yield f


def appointable(game, a):
    p = game.player
    from .data.ranks import same_army, BRIGADIER
    return (a is not p and a.active and not a.downed and a.side == p.side and a.rank < p.rank
            and not a.ai.get("civilian") and a.squad is not None
            and (same_army(p.nation, a.nation) or p.rank >= BRIGADIER))


def administer(game, sq, kind, payload):
    """Revalidate when the instruction arrives: command may have changed in transit."""
    cmd, p = game.command, game.player
    if not cmd.authority(game, sq)[0]:
        return False
    if kind == "appointment":
        a = next((a for a in game.actors if a.id == payload.get("actor")), None)
        if a is None or not appointable(game, a):
            return False
        fid = payload.get("formation")
        if fid is not None:
            f = next((f for f in formations(game) if f.id == fid), None)
            if f is None or f.commander is p or f.side != p.side or f.commander_grade() >= p.rank:
                return False
            if not all(cmd.authority(game, s)[0] for s in f.live_squads()):
                return False
            # One man cannot simultaneously command unrelated formations.
            for old in formations(game):
                if old.commander is a:
                    old.commander = None
            f.commander, f.offmap, f.acting = a, None, True
        else:
            if sq.leader is p or (leader_of(sq) and leader_of(sq).rank >= p.rank):
                return False
            old = a.squad
            if old is not sq:
                if old.leader is a:
                    old.leader = None
                if a in old.members:
                    old.members.remove(a)
                sq.members.append(a)
                a.squad = sq
            sq.leader = a
            sq.player_led = False
        return True
    if kind == "reassign":
        f = next((f for f in formations(game) if f.id == payload.get("formation")), None)
        if f is None or f.side != p.side or f.commander_grade() >= p.rank or sq is p.squad:
            return False
        if not all(cmd.authority(game, s)[0] for s in f.live_squads()):
            return False
        old = sq.formation
        if old is not None:
            if sq is old.hq:
                return False
            if sq in old.squads:
                old.squads.remove(sq)
        sq.formation = f
        if sq not in f.squads:
            f.squads.append(sq)
        cmd._name_squad(sq, f)
        return True
    if kind == "mission":
        if payload.get("mission") not in MISSIONS or payload.get("freedom") not in FREEDOM:
            return False
        if payload.get("risk") not in LOSSES or not game.map.in_bounds(*payload["target"]):
            return False
        sq.rep["intent"] = dict(payload, issued=game.turn, strength=sq.strength(), next=game.turn,
                                  completed=False, source="player")
        sq.rep.pop("construction", None)
        _order(game, sq, "attack" if payload["mission"] == "seize" else "defend", payload["target"])
        return True
    return False


def _order(game, sq, kind, target):
    src = sq.rep.get("intent", {}).get("source", "player")
    game.command.apply(game, sq, Order(kind, target=tuple(target), radius=5,
                                      issued=game.turn, src=src, roe=sq.order.roe))


def update(game, sq):
    intent = sq.rep.get("intent")
    if not intent or sq.gone or game.turn < intent.get("next", 0):
        return
    intent["next"] = game.turn + 15
    leader = leader_of(sq)
    pos = contact_point(sq)
    if pos is None or leader is None or leader.downed or sq.state == "rout":
        return
    target = tuple(intent["target"])
    radius = FREEDOM[intent["freedom"]][0]
    mission = intent["mission"]
    contacts = [c for c in local_contacts(game, sq, 45) if distance((c["x"], c["y"]), target) <= radius]
    loss = 1 - sq.strength() / max(1, intent["strength"])
    if loss >= LOSSES[intent["risk"]] or sq.morale < 20:
        if not intent.get("halted"):
            intent["halted"] = True
            _order(game, sq, "defend", pos)
            sq.rep["initiative_note"] = "Heavy losses; reorganizing and requesting instructions."
        return
    if low_on_ammo(sq) and game.turn - sq.last_contact > 30:
        dump = nearest_ammo(game, sq, max_d=radius)
        if dump and intent["freedom"] != "restricted" and sq.order.kind != "resupply":
            _order(game, sq, "resupply", dump)
            sq.rep["initiative_note"] = "Drawing ammunition; will resume the mission."
        return
    if sq.order.kind == "resupply" and not low_on_ammo(sq):
        _order(game, sq, "attack" if mission == "seize" and not intent["completed"] else "defend", target)
    if intent.get("halted"):
        return
    if mission == "seize":
        if distance(pos, target) <= 5 and not contacts:
            if not intent["completed"]:
                intent["completed"] = True
                _order(game, sq, "dig", target)
                sq.rep["initiative_note"] = "Objective reached; consolidating and covering approaches."
                from .skills import use
                use(game, leader, "leadership", 8)
                if intent.get("source") == "player":
                    use(game, game.player, "leadership", 4)
            return
        if contacts and intent["freedom"] != "restricted" and not intent.get("maneuvered"):
            tactic = profile(sq.nation)[1]
            if tactic == "concentrate":
                # An echelon assembles locally before pushing on to its next objective.
                friends = [q for q in game.squads if q is not sq and q.side == sq.side and not q.gone
                           and contact_point(q) and distance(contact_point(q), pos) <= 12]
                if not friends and game.turn - intent["issued"] < 90:
                    _order(game, sq, "defend", pos)
                    sq.rep["initiative_note"] = "Assembling the local attack echelon before advancing."
                    return
            intent["maneuvered"] = True
            c = contacts[0]
            kind = "suppress" if sq.kind in ("mg", "atgun") else "flank" if tactic == "flank" else "attack"
            _order(game, sq, kind, (c["x"], c["y"]) if kind != "attack" else target)
            sq.rep["initiative_note"] = f"{profile(sq.nation)[0]}: supporting the assigned attack."
    elif mission == "screen" and contacts:
        _order(game, sq, "defend", target)
        sq.order.roe = "return"
        sq.rep["initiative_note"] = "Contact reported; holding the screen and avoiding decisive engagement."
    elif mission == "reserve" and intent["freedom"] != "restricted":
        # A reserve can respond to a neighbour it can hear, or a report on its own net.
        from .command import squad_has_radio
        candidates = [q for q in game.squads if q is not sq and q.side == sq.side and not q.gone
                      and game.turn - q.last_contact < 30 and contact_point(q) is not None
                      and distance(contact_point(q), target) <= radius
                      and (distance(contact_point(q), pos) <= 12 or
                           squad_has_radio(game, sq) and squad_has_radio(game, q))]
        if candidates:
            q = min(candidates, key=lambda q: distance(contact_point(q), pos))
            _order(game, sq, "defend", contact_point(q))
            sq.rep["initiative_note"] = f"Moving to support {q.short or q.name}."
        elif sq.order.target != target:
            _order(game, sq, "defend", target)


def defaults(game, sq):
    """AI armies use the same bounded missions after their higher commander issues orders."""
    if sq.player_led or sq.order.src == "player" or sq.kind in ("staff", "rear", "aid", "supply", "hq"):
        return
    if sq.order.kind not in ("attack", "defend") or sq.rep.get("construction"):
        return
    from .ai import order_target
    target = order_target(game, sq)
    if target is None:
        return
    old = sq.rep.get("intent")
    if old and old.get("source") == "ai" and tuple(old["target"]) == tuple(target):
        return
    sq.rep["intent"] = dict(mission="seize" if sq.order.kind == "attack" else "defend", target=tuple(target),
                             freedom=profile(sq.nation)[2], risk="normal", source="ai", issued=game.turn,
                             strength=sq.strength(), next=game.turn, completed=False)


def staff_support(game):
    """Available headquarters parties keep a senior officer in contact; nobody is spawned."""
    from .intelligence import radio_link
    from .senses import los_clear
    for sq in game.squads:
        if sq.kind != "hq" or sq.gone or sq.player_led or sq.order.src == "player" or sq.rep.get("construction"):
            continue
        leader = leader_of(sq)
        pos = contact_point(sq)
        if leader is None or pos is None or game.turn - sq.last_contact < 90:
            continue
        seniors = [a for a in game.actors if a.side == sq.side and a.active and not a.downed
                   and a.rank >= 12 and a.rank > leader.rank and a.squad is not sq
                   and distance(a.pos, pos) <= 35 and
                   (distance(a.pos, pos) <= 12 and los_clear(game, *pos, *a.pos) or
                    radio_link(game, leader) and radio_link(game, a))]
        if not seniors:
            continue
        chief = max(seniors, key=lambda a: a.rank)
        if distance(chief.pos, pos) > 5:
            game.command.apply(game, sq, Order("defend", target=chief.pos, radius=4,
                                               issued=game.turn, src="staff"))
            sq.rep["initiative_note"] = "Keeping the command group and its radio within reach of the senior officer."
