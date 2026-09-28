"""Hit locations, wounds, bleeding, pain and consciousness."""
from __future__ import annotations

import random

PARTS = ("head", "torso", "l_arm", "r_arm", "l_leg", "r_leg")
PART_NAME = {"head": "head", "torso": "torso", "l_arm": "left arm", "r_arm": "right arm",
             "l_leg": "left leg", "r_leg": "right leg"}
MAXHP = {"head": 28, "torso": 68, "l_arm": 38, "r_arm": 38, "l_leg": 48, "r_leg": 48}
BLOOD_MAX = 5000

# hit location weights by stance (standing, crouching, prone)
HIT_WEIGHTS = {
    0: {"head": 9, "torso": 45, "l_arm": 11, "r_arm": 11, "l_leg": 12, "r_leg": 12},
    1: {"head": 12, "torso": 48, "l_arm": 12, "r_arm": 12, "l_leg": 8, "r_leg": 8},
    2: {"head": 24, "torso": 36, "l_arm": 17, "r_arm": 17, "l_leg": 3, "r_leg": 3},
}
# behind cover the lower body is protected
COVER_WEIGHTS = {"head": 22, "torso": 40, "l_arm": 19, "r_arm": 19, "l_leg": 0, "r_leg": 0}


class Wound:
    __slots__ = ("part", "bleed", "bandaged", "kind", "tourniquet")

    def __init__(self, part: str, bleed: float, kind: str):
        self.part = part
        self.bleed = bleed          # ml per turn
        self.bandaged = False
        self.tourniquet = False
        self.kind = kind


class Body:
    def __init__(self, toughness: float = 1.0):
        self.max = {p: int(MAXHP[p] * toughness) for p in PARTS}
        self.hp = dict(self.max)
        self.blood = float(BLOOD_MAX)
        self.wounds: list[Wound] = []
        self.pain = 0.0
        self.morphine = 0.0
        self.alcohol = 0.0
        self.unconscious = 0         # turns remaining (or >0 while in shock)
        self.stunned = 0             # turns of disorientation
        self.deaf = 0                # turns of deafness after blasts
        self.burning = 0
        self.dead = False
        self.cause = ""
        self.killer = None
        self.drown = 0               # turns spent struggling in deep water

    # ------------------------------------------------------------ queries
    @property
    def alive(self) -> bool:
        return not self.dead

    @property
    def conscious(self) -> bool:
        return not self.dead and self.unconscious <= 0

    def legs_ok(self) -> int:
        return (self.hp["l_leg"] > 0) + (self.hp["r_leg"] > 0)

    def arms_ok(self) -> int:
        return (self.hp["l_arm"] > 0) + (self.hp["r_arm"] > 0)

    def can_walk(self) -> bool:
        return self.legs_ok() == 2 and self.effective_pain() < 120

    def downed(self) -> bool:
        """Can't stand: crawl only."""
        hp = self.hp
        return hp["l_leg"] <= 0 or hp["r_leg"] <= 0 or self.pain - self.morphine >= 120 or self.blood < 3400

    def bleed_rate(self) -> float:
        return sum(w.bleed for w in self.wounds if not w.bandaged and not w.tourniquet)

    def aim_penalty(self) -> float:
        """Extra dispersion in degrees from injuries."""
        p = 0.0
        for arm in ("l_arm", "r_arm"):
            r = self.hp[arm] / self.max[arm]
            p += (1 - r) * 1.2
            if self.hp[arm] <= 0:
                p += 2.5
        p += max(0.0, self.effective_pain() - 30) / 40
        if self.blood < 4200:
            p += (4200 - self.blood) / 500
        p += self.alcohol * 0.3
        if self.stunned:
            p += 3
        return p

    def effective_pain(self) -> float:
        return max(0.0, self.pain - self.morphine)

    def speed_mult(self) -> float:
        m = 1.0
        for leg in ("l_leg", "r_leg"):
            r = self.hp[leg] / self.max[leg]
            m -= (1 - r) * 0.25
        m -= max(0.0, self.effective_pain() - 40) / 300
        if self.blood < 4000:
            m -= (4000 - self.blood) / 4000
        return max(0.25, m)

    # ------------------------------------------------------------ damage
    def pick_part(self, rng: random.Random, stance: int, covered: bool = False) -> str:
        w = COVER_WEIGHTS if covered else HIT_WEIGHTS.get(stance, HIT_WEIGHTS[0])
        parts = [p for p in PARTS if w[p] > 0]
        return rng.choices(parts, [w[p] for p in parts])[0]

    def damage(self, rng: random.Random, part: str, dmg: float, kind: str = "gunshot") -> dict:
        """Apply damage; returns a dict describing the effect."""
        if self.dead:
            return {"dead": True, "part": part, "dmg": 0}
        dmg = max(0, dmg)
        before = self.hp[part]
        self.hp[part] = max(0, self.hp[part] - int(round(dmg)))
        overflow = max(0, dmg - before)
        # damage to destroyed limbs spills into the torso
        if overflow > 0 and part not in ("head", "torso"):
            self.hp["torso"] = max(0, self.hp["torso"] - int(overflow * 0.35))
        bleed_mult = {"gunshot": 0.10, "fragment": 0.09, "cut": 0.12, "burn": 0.01,
                      "blunt": 0.02, "blast": 0.05}.get(kind, 0.08)
        bleed = dmg * bleed_mult * (1.8 if part == "torso" else 1.2 if part == "head" else 1.0)
        if self.hp[part] <= 0 and part not in ("head", "torso"):
            bleed *= 2.2
        if bleed > 0.2:
            self.wounds.append(Wound(part, bleed, kind))
        self.pain += dmg * (0.9 if kind != "burn" else 1.4)
        res = {"part": part, "dmg": dmg, "dead": False, "disabled": self.hp[part] <= 0 < before}
        if self.hp["head"] <= 0 or self.hp["torso"] <= 0:
            self.dead = True
            res["dead"] = True
        elif dmg >= 25 and rng.random() < dmg / 90:
            self.stunned = max(self.stunned, rng.randint(1, 3))
        if not self.dead and self.effective_pain() > 150 and rng.random() < 0.5:
            self.unconscious = max(self.unconscious, rng.randint(20, 90))
            res["knocked_out"] = True
        return res

    # ------------------------------------------------------------ time
    def update(self, rng: random.Random) -> list[str]:
        """One turn of physiology.  Returns event keys."""
        ev = []
        if self.dead:
            return ev
        rate = self.bleed_rate()
        if rate > 0:
            self.blood -= rate
            # slow natural clotting on small wounds
            for w in self.wounds:
                if not w.bandaged and w.bleed < 1.5 and rng.random() < 0.01:
                    w.bleed *= 0.8
        # pain eases slowly; morphine wears off
        self.pain = max(0.0, self.pain - 0.05 - self.pain * 0.0008)
        self.morphine = max(0.0, self.morphine - 0.03)
        self.alcohol = max(0.0, self.alcohol - 0.002)
        if self.stunned:
            self.stunned -= 1
        if self.deaf:
            self.deaf -= 1
        if self.unconscious > 0:
            self.unconscious -= 1
            if self.unconscious == 0 and (self.blood < 2900 or self.effective_pain() > 170):
                self.unconscious = rng.randint(10, 40)
            if self.unconscious == 0:
                ev.append("woke")
        if self.blood < 2900 and self.unconscious <= 0:
            self.unconscious = rng.randint(30, 120)
            ev.append("fainted")
        if self.effective_pain() > 190 and self.unconscious <= 0 and rng.random() < 0.05:
            self.unconscious = rng.randint(15, 60)
            ev.append("shock")
        if self.blood < 2100:
            self.dead = True
            self.cause = self.cause or "blood loss"
            ev.append("bled_out")
        if self.morphine > 180:
            if rng.random() < 0.02:
                self.dead = True
                self.cause = "a morphine overdose"
                ev.append("overdose")
        return ev

    # ------------------------------------------------------------ treatment
    def worst_wound(self, bandageable_only=True):
        ws = [w for w in self.wounds if not w.bandaged and not w.tourniquet]
        return max(ws, key=lambda w: w.bleed) if ws else None

    def bandage(self, quality: float = 1.0) -> Wound | None:
        w = self.worst_wound()
        if not w:
            return None
        w.bandaged = True
        w.bleed *= max(0.0, 0.15 * (1.2 - quality))
        return w

    def tourniquet(self) -> Wound | None:
        limb = [w for w in self.wounds if w.part not in ("head", "torso") and not w.tourniquet]
        if not limb:
            return None
        part = max(limb, key=lambda w: w.bleed).part
        for w in self.wounds:
            if w.part == part:
                w.tourniquet = True
        return limb[0]

    def heal_blood(self, ml: float):
        self.blood = min(BLOOD_MAX, self.blood + ml)

    # ------------------------------------------------------------ description
    def part_status(self, part: str) -> tuple[str, tuple]:
        r = self.hp[part] / self.max[part]
        if self.hp[part] <= 0:
            return ("mangled" if part not in ("head", "torso") else "destroyed", (170, 0, 0))
        if r > 0.95:
            return "fine", (120, 200, 120)
        if r > 0.8:
            return "bruised", (190, 210, 110)
        if r > 0.6:
            return "hurt", (230, 200, 70)
        if r > 0.35:
            return "wounded", (240, 140, 50)
        return "badly hurt", (240, 60, 40)

    def part_bleeding(self, part: str) -> str:
        b = sum(w.bleed for w in self.wounds if w.part == part and not w.bandaged and not w.tourniquet)
        if b <= 0.05:
            if any(w.part == part and w.tourniquet for w in self.wounds):
                return "tourniquet"
            if any(w.part == part and w.bandaged for w in self.wounds):
                return "bandaged"
            return ""
        if b < 2:
            return "bleeding"
        if b < 5:
            return "bleeding badly"
        return "gushing blood"

    def feel(self) -> list[tuple[str, tuple]]:
        """Diegetic condition lines."""
        out = []
        if self.blood < 2900:
            out.append(("Everything is going dark...", (200, 60, 60)))
        elif self.blood < 3400:
            out.append(("You can barely stand. So cold.", (220, 80, 80)))
        elif self.blood < 4200:
            out.append(("Lightheaded, dry-mouthed.", (230, 150, 90)))
        p = self.effective_pain()
        if p > 150:
            out.append(("Blinding agony.", (240, 50, 50)))
        elif p > 90:
            out.append(("Terrible pain.", (240, 100, 60)))
        elif p > 45:
            out.append(("It hurts.", (230, 170, 80)))
        elif p > 15:
            out.append(("Aching.", (200, 190, 120)))
        if self.morphine > 30:
            out.append(("Warm and floaty (morphine).", (170, 170, 230)))
        if self.alcohol > 1:
            out.append(("A little drunk.", (200, 170, 120)))
        if self.deaf:
            out.append(("Ears ringing.", (180, 180, 180)))
        if self.stunned:
            out.append(("Dazed.", (200, 200, 120)))
        return out
