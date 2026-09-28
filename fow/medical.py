"""Medicine: from a mate's field dressing to the surgeon's table.

Three levels of skill:

  buddy aid   everyone: dressings, tourniquets, sulfa - done roughly.  The untrained
              can overdose a man on morphine and can't run an IV.
  corpsman    medics: pressure-pack chest and head wounds, safe morphine, plasma,
              treat shock, stitch small wounds (some flesh back), triage, and get
              casualties out - dragged, or carried to the aid station.
  surgeon     at an aid station: operations that take ten minutes to an hour -
              wounds closed, blood transfused, ruined limbs saved or taken off.
              Afterwards men heal on the cots over hours and walk back to the line.

The AI does all of this too: medics triage and evacuate, surgeons and orderlies
work the aid station, the walking wounded make their own way back.
"""
from __future__ import annotations

import math

from .body import BLOOD_MAX, PART_NAME, PARTS

UNTRAINED, TRAINED, MEDIC, SURGEON = 0, 1, 2, 3


def skill(a) -> int:
    if a.role == "surgeon":
        return SURGEON
    if a.role == "medic":
        return MEDIC
    if a.rank >= 3 or "veteran" in a.traits:
        return TRAINED
    return UNTRAINED


def skill_name(s: int) -> str:
    return ("buddy aid", "first aid", "corpsman", "surgeon")[s]


def _parts(b):
    """The body's parts, less any already amputated (a stump isn't a wound)."""
    gone = getattr(b, "amputated", None)
    return [p for p in PARTS if p not in gone] if gone else PARTS


def missing_hp(b) -> int:
    return sum(b.max[p] - b.hp[p] for p in _parts(b))


def needs_care(b) -> float:
    """How badly a body needs a medic (0 = not at all)."""
    return b.bleed_rate() * 12 + max(0.0, b.effective_pain() - 70) / 3 + max(0.0, 4200 - b.blood) / 60 + \
        (25 if b.unconscious > 0 else 0)


def should_evacuate(b) -> bool:
    """Bad enough to leave the line for: a ruined limb, a chest or head wound, or half a limb gone."""
    parts = _parts(b)
    if any(b.hp[p] <= 0 for p in parts):
        return True
    if any(b.hp[p] < b.max[p] * 0.45 for p in parts):
        return True
    return any(w.part in ("torso", "head") and (w.bleed > 0.2 or not w.bandaged) for w in b.wounds) and \
        b.hp["torso"] < b.max["torso"] * 0.7


def needs_surgery(b) -> bool:
    """Wounds a dressing won't fix: chest and head wounds, ruined limbs, lost flesh."""
    if any(b.hp[p] <= 0 for p in _parts(b)):
        return True
    if missing_hp(b) > 25:
        return True
    return any(w.part in ("torso", "head") and w.bleed > 0.2 for w in b.wounds)


# ====================================================================== first aid

def first_aid(game, medic, patient, item=None) -> int | None:
    """The best thing this man can do for that one, right now.  Returns time taken, or None."""
    from . import actions as A
    s = skill(medic)
    b = patient.body
    if s < MEDIC:
        return A.treat(game, medic, patient, item)
    rng = game.rng
    self_aid = medic is patient
    who = "yourself" if (self_aid and medic.is_player) else ("you" if patient.is_player else game.name_of(patient))
    kit = medic.medical("kit")
    # 1. bleeding: pack it properly
    w = b.worst_wound()
    if w is not None:
        limb = w.part not in ("head", "torso")
        if limb and w.bleed > 5 and medic.medical("tourniquet"):
            return A.treat(game, medic, patient, medic.medical("tourniquet"))
        dressing = medic.medical("bandage")
        if dressing is None:
            return None
        n = 0
        while b.worst_wound() is not None and n < (4 if kit else 2):
            ww = b.worst_wound()
            ww.bandaged = True
            ww.bleed *= 0.02 if ww.part in ("torso", "head") else 0.0
            n += 1
            if kit is not None:
                kit.uses -= 1
                if kit.uses <= 0:
                    medic.remove_item(kit)
                    kit = None
                    dressing = medic.medical("bandage")      # the kit's used up: on to loose dressings, if any
                    if dressing is None:
                        break
            else:
                A._consume(medic, dressing)
                dressing = medic.medical("bandage")
                if dressing is None:
                    break
        medic.stats["bandaged"] += n
        game.msg_for(medic, patient, f"pack{'s' if not medic.is_player else ''} {'the wounds' if n > 1 else 'the wound'} "
                                     f"on {who} and bind{'s' if not medic.is_player else ''} {'them' if n > 1 else 'it'} tight",
                     "good")
        return 220 + 120 * n
    # 2. shock and blood loss: plasma
    if b.blood < 3800 and medic.medical("plasma"):
        it = medic.medical("plasma")
        b.heal_blood(it.t.power)
        if b.unconscious > 0:
            b.unconscious = max(0, b.unconscious // 3)
        A._consume(medic, it)
        game.msg_for(medic, patient, f"hang{'s' if not medic.is_player else ''} a bottle of plasma for {who}", "good")
        return 500
    # 3. pain: a safe dose
    if b.effective_pain() > 70 and b.morphine < 90 and medic.medical("morphine"):
        it = medic.medical("morphine")
        b.morphine += min(it.t.power, 120 - b.morphine)
        A._consume(medic, it)
        game.msg_for(medic, patient, f"give{'s' if not medic.is_player else ''} {who} a measured shot of morphine", "good")
        return 100
    # 4. knocked out: bring him round
    if b.unconscious > 0 and b.blood > 3200:
        b.unconscious = max(0, b.unconscious - 60)
        game.msg_for(medic, patient, f"slap{'s' if not medic.is_player else ''} {who} awake and talk{'s' if not medic.is_player else ''} {patient.him if not patient.is_player else 'you'} round",
                     "info")
        return 150
    # 5. stitch what can be stitched
    worst = min((p for p in PARTS if 0 < b.hp[p] < b.max[p] * 0.7), key=lambda p: b.hp[p] / b.max[p], default=None)
    if worst is not None and (kit is not None or medic.medical("bandage")):
        gain = min(int(b.max[worst] * 0.2), int(b.max[worst] * 0.7) - b.hp[worst])
        if gain > 0:
            b.hp[worst] += gain
            b.pain = max(0.0, b.pain - gain * 0.5)
            if kit is not None:
                kit.uses -= 1
                if kit.uses <= 0:
                    medic.remove_item(kit)
            game.msg_for(medic, patient, f"clean{'s' if not medic.is_player else ''} and stitch{'es' if not medic.is_player else ''} "
                                         f"the wound in {who if patient.is_player or self_aid else patient.his} {PART_NAME[worst]}",
                         "good")
            return 400 + gain * 25
    return None


def can_help(game, medic, patient) -> bool:
    b = patient.body
    if b.worst_wound() is not None and (medic.medical("bandage") or medic.medical("tourniquet")):
        return True
    s = skill(medic)
    if s >= MEDIC:
        if b.blood < 3800 and medic.medical("plasma"):
            return True
        if b.effective_pain() > 70 and b.morphine < 90 and medic.medical("morphine"):
            return True
        if b.unconscious > 0 and b.blood > 3200:
            return True
        if any(0 < b.hp[p] < b.max[p] * 0.7 for p in PARTS) and (medic.medical("kit") or medic.medical("bandage")):
            return True
    elif b.effective_pain() > 90 and medic.medical("morphine"):
        return True
    return False


# ====================================================================== the aid station

def aid_posts(game, side):
    """(x, y, rect) of this side's aid stations on the map."""
    m = game.map
    out = []
    for rec in getattr(m, "gen_positions", []) or []:
        if rec.get("kind") == "aid" and rec.get("side") == side:
            out.append((rec["x"], rec["y"], rec["rect"]))
    return out


def nearest_aid(game, a):
    posts = aid_posts(game, a.side)
    if not posts:
        return None
    return min(posts, key=lambda p: max(abs(p[0] - a.x), abs(p[1] - a.y)))


def at_aid_post(game, a) -> bool:
    for x, y, (rx, ry, rw, rh) in aid_posts(game, a.side):
        if rx <= a.x < rx + rw and ry <= a.y < ry + rh:
            return True
    return False


def cot_near(game, x, y, radius=10):
    """A free cot (or failing that a free floor tile) at the aid station."""
    from . import tiles as T
    m = game.map
    best = None
    bd = 1e9
    bed = T.ID.get("bed")
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            xx, yy = x + dx, y + dy
            if not m.in_bounds(xx, yy) or (xx, yy) in game.soldier_at or (xx, yy) in game.vehicle_at:
                continue
            if not m.walk[xx, yy]:
                continue
            d = abs(dx) + abs(dy) - (20 if m.t[xx, yy] == bed else 0)
            if d < bd:
                bd, best = d, (xx, yy)
    return best


def surgery_time(b) -> int:
    """Ten minutes to an hour on the table."""
    ruined = sum(1 for p in PARTS if b.hp[p] <= 0)
    return int(600 + missing_hp(b) * 22 + ruined * 900 + sum(w.bleed for w in b.wounds) * 40)


def begin_surgery(game, surgeon, patient) -> int | None:
    """Put the patient under.  The operation runs as a job on the surgeon."""
    if patient.ai.get("surgery") is not None:
        return None
    t = surgery_time(patient.body)
    patient.ai["surgery"] = dict(by=surgeon.id, start=game.turn, end=game.turn + t)
    surgeon.ai["operating"] = patient.id
    patient.body.unconscious = max(patient.body.unconscious, t + 30)       # under anaesthetic
    patient.body.morphine = max(patient.body.morphine, 40)
    if game.can_see(patient.x, patient.y) or patient.is_player or surgeon.is_player:
        game.msg_for(surgeon, patient, f"begin{'s' if not surgeon.is_player else ''} to operate on "
                                       f"{'you' if patient.is_player else game.name_of(patient)} "
                                       f"(about {max(10, t // 60)} minutes)", "info")
    return t


def finish_surgery(game, surgeon, patient):
    """What the knife could do."""
    rng = game.rng
    b = patient.body
    job = patient.ai.pop("surgery", None)
    if surgeon is not None:
        surgeon.ai.pop("operating", None)
    if not patient.alive:
        return "dead"
    s = skill(surgeon) if surgeon is not None else MEDIC
    severity = missing_hp(b) / max(1, sum(b.max.values())) + (0.4 if b.blood < 3000 else 0)
    p_die = max(0.01, 0.25 * severity - (0.08 if s >= SURGEON else 0))
    if rng.random() < p_die:
        b.dead = True
        b.cause = "wounds, on the operating table"
        game.kill(patient, None)
        game.msg("The surgeon straightens up and shakes his head.", "death") if (patient.is_player or
                                                                                 game.can_see(patient.x, patient.y)) else None
        return "died"
    for w in b.wounds:
        w.bleed = 0.0
        w.bandaged = True
    b.wounds = [w for w in b.wounds if w.tourniquet]            # a tourniqueted limb comes off or is saved below
    lost = []
    for p in PARTS:
        if b.hp[p] <= 0 and p not in ("head", "torso"):
            if rng.random() < (0.45 if s >= SURGEON else 0.2):
                b.hp[p] = int(b.max[p] * 0.3)                   # saved
            else:
                lost.append(p)                                  # amputated
                b.max[p] = max(1, b.max[p])
        elif b.hp[p] < b.max[p] * 0.5:
            b.hp[p] = int(b.max[p] * 0.5)
    b.wounds = [w for w in b.wounds if w.part in lost]
    for w in b.wounds:
        w.bleed = 0.0
    patient.ai["amputated"] = sorted(set(patient.ai.get("amputated", [])) | set(lost))
    b.amputated = set(patient.ai["amputated"])                   # (a stump is healed, not a wound to operate on)
    if b.blood < 4200:
        b.heal_blood(4200 - b.blood)                            # transfusion
    b.pain = min(b.pain, 60)
    b.morphine = max(b.morphine, 60)
    b.unconscious = 40
    patient.ai["recovering"] = game.turn
    if patient.is_player:
        game.msg("You come to on a cot, stitched and bandaged. " +
                 (f"Your {', '.join(PART_NAME[p] for p in lost)} is gone." if lost else
                  "The doctor says you'll live."), "good" if not lost else "warn")
    return "amputated" if lost else "saved"


def recover(game, a, turns):
    """Mending over time: fast on a cot after surgery, slow at the aid station, very slow in the line."""
    b = a.body
    if b.dead or b.bleed_rate() > 0.05:
        return
    if a.ai.get("surgery") is not None:
        return
    amputated = set(a.ai.get("amputated", []))
    care = 1.0 / 120 if a.ai.get("recovering") is not None else (1.0 / 300 if at_aid_post(game, a) else 1.0 / 3000)
    gain = turns * care
    for p in PARTS:
        if p in amputated or b.hp[p] <= 0:
            continue
        if b.hp[p] < b.max[p]:
            frac = a.ai.get("_heal_" + p, 0.0) + gain * (b.max[p] / 40)
            whole = int(frac)
            a.ai["_heal_" + p] = frac - whole
            b.hp[p] = min(b.max[p], b.hp[p] + whole)
    if at_aid_post(game, a) and b.blood < BLOOD_MAX:
        b.heal_blood(turns * 0.6)
    if a.ai.get("recovering") is not None and missing_hp(b) <= sum(b.max.values()) * 0.1:
        a.ai.pop("recovering", None)


def fit_for_duty(a) -> bool:
    b = a.body
    amputated = set(a.ai.get("amputated", []))
    if amputated & {"l_leg", "r_leg"} or len(amputated & {"l_arm", "r_arm"}) >= 1:
        return False
    return b.bleed_rate() < 0.05 and not b.downed() and all(b.hp[p] >= b.max[p] * 0.6 for p in PARTS)
