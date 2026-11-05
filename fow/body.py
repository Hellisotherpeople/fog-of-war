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


DRESS_WEAR = 900                    # turns before a dressing soaks through (about a quarter of an hour)
TOURNIQUET_RISK = 2400              # turns before a limb starts to die under a tourniquet
TOURNIQUET_LOST = 5400


class Wound:
    __slots__ = ("part", "bleed", "bandaged", "kind", "tourniquet", "dirt", "infection",
                 "dress_turn", "sulfa_turn", "tourniquet_turn", "arterial", "fracture", "burn",
                 "necrosis", "pressure")

    def __init__(self, part: str, bleed: float, kind: str, dirt: float = 0.0):
        self.part = part
        self.bleed = bleed          # ml per turn, before treatment
        self.bandaged = False
        self.tourniquet = False
        self.kind = kind
        self.dirt = dirt            # what went into it: soil, cloth, splinters
        self.infection = 0.0        # 0-100, this wound's own
        self.dress_turn = -9999
        self.sulfa_turn = -9999
        self.tourniquet_turn = 0
        self.arterial = False
        self.fracture = False
        self.burn = kind == "burn"
        self.necrosis = False
        self.pressure = False

    # old saves have none of the clinical fields
    _OLD = {"dirt": 0.0, "infection": 0.0, "dress_turn": -9999, "sulfa_turn": -9999,
            "tourniquet_turn": 0, "arterial": False, "fracture": False, "burn": False,
            "necrosis": False, "pressure": False}

    def __getattr__(self, name):
        if name in Wound._OLD:
            return Wound._OLD[name]
        raise AttributeError(name)

    def _get(self, name, default):
        return getattr(self, name, default)


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
        self.shock = 0.0             # 0-160: the body closing down
        self.sepsis = False
        self.splinted = set()        # parts braced
        self.splint_turn = {}
        self.now = 0                 # the last turn this body was ticked (dressing age)
        self.warm = 0                # turns spent lying warm and covered

    _OLD = {"shock": 0.0, "sepsis": False, "splinted": set(), "splint_turn": {}, "now": 0, "warm": 0}

    def __getattr__(self, name):
        if name in Body._OLD:
            return Body._OLD[name]
        raise AttributeError(name)

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

    def downed(self) -> bool:
        """Can't stand: crawl only."""
        hp = self.hp
        return hp["l_leg"] <= 0 or hp["r_leg"] <= 0 or self.pain - self.morphine >= 120 or self.blood < 3400 \
            or self.__dict__.get("shock", 0.0) >= 100

    def bleed_rate(self) -> float:
        """ml a turn, as things stand: dressings count until they soak through, and an artery needs more."""
        now = self.__dict__.get("now", 0)
        n = 0.0
        for w in self.wounds:
            if w.tourniquet:
                continue
            b = w.bleed
            if w.arterial:
                b += 6.0
            if w.fracture:
                b += 0.4
            if w.bandaged:
                age = now - getattr(w, "dress_turn", -9999)
                if age < DRESS_WEAR:
                    b = 0.0
                else:
                    base = 0.05 if getattr(w, "pressure", False) else 0.2
                    b *= base + (1.0 - base) * min(1.0, (age - DRESS_WEAR) / 1200.0)
            n += b
        return n

    def infection(self) -> float:
        return min(100.0, sum(getattr(w, "infection", 0.0) for w in self.wounds))

    def fever(self) -> float:
        return max(0.0, self.infection() - 25) / 18.0

    def splinted_at(self, part: str) -> bool:
        until = self.__dict__.get("splint_turn", {}).get(part, 0)
        return until > self.__dict__.get("now", 0)

    def fractured(self) -> bool:
        return any(w.fracture for w in self.wounds)

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
        p += max(0.0, self.shock - 40) / 25
        for w in self.wounds:
            if w.fracture and not self.splinted_at(w.part):
                p += 1.5
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
        for w in self.wounds:
            if w.fracture and not self.splinted_at(w.part):
                m -= 0.2 if w.part in ("l_leg", "r_leg") else 0.08
        m -= max(0.0, self.shock - 60) / 300
        return max(0.2, m)

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
            dirt = {"burn": rng.uniform(0.0, 0.1), "blunt": rng.uniform(0.0, 0.3),
                    "blast": rng.uniform(0.2, 0.7), "fragment": rng.uniform(0.25, 0.8),
                    "cut": rng.uniform(0.2, 0.7), "gunshot": rng.uniform(0.3, 0.85)}.get(
                        kind, rng.uniform(0.1, 0.5))
            w = Wound(part, bleed, kind, dirt)
            w.arterial = part not in ("head", "torso") and bleed > 5.5 and rng.random() < 0.4
            w.fracture = part not in ("head", "torso") and kind in ("blunt", "blast", "gunshot") and dmg >= 12 \
                and rng.random() < (0.25 if kind != "blunt" else 0.65)
            self.wounds.append(w)
        self.pain += dmg * (0.9 if kind != "burn" else 1.4)
        if any(w.fracture for w in self.wounds[-1:]):
            self.pain += 12
        self.shock = min(160.0, self.shock + dmg * (0.25 if kind in ("burn", "blast") else 0.12))
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
    def at_rest(self) -> bool:
        """Nothing for update() to do: no wound, drug, drink, daze or blackout, and blood enough to stay up.
        (The thousands of men outside the simulated circle are mostly like this, every second.)"""
        return not (self.wounds or self.pain or self.morphine or self.alcohol or self.stunned or self.deaf or
                    self.unconscious or self.__dict__.get("shock", 0.0)) and self.blood >= 2900

    def update(self, rng: random.Random, turn: int = 0) -> list[str]:
        """One turn of physiology.  Returns event keys."""
        ev = []
        if self.dead:
            return ev
        self.now = turn
        # wounds: soil works its way in, dressings soak through, tourniquets strangle
        for w in self.wounds:
            inf = getattr(w, "infection", 0.0)
            old_dress = turn - getattr(w, "dress_turn", -9999)
            clean = w.bandaged and old_dress < DRESS_WEAR
            control = 0.55 if clean else 1.0
            if getattr(w, "sulfa_turn", -9999) > turn - 1200:
                control *= 0.45
            if w.bandaged and old_dress >= DRESS_WEAR:
                control *= 1.25                       # a sodden, filthy dressing is worse than none
            inf += getattr(w, "dirt", 0.0) * 0.05 * control + (0.008 if w.burn else 0.0)
            w.infection = min(100.0, inf)
            w.dirt = max(0.0, getattr(w, "dirt", 0.0) - 0.00008)
            if w.infection > 72 and not w.necrosis and w.part not in ("head", "torso") \
                    and rng.random() < 0.0004:
                w.necrosis = True
            if w.tourniquet:
                age = turn - getattr(w, "tourniquet_turn", 0)
                if age > TOURNIQUET_RISK and rng.random() < 0.0005:
                    w.necrosis = True
        inf = self.infection()
        if hasattr(self, "temp"):
            target = 37.0 + min(3.6, self.fever() * 0.7)
            self.temp += max(-0.05, min(0.08, (target - self.temp) * 0.05))
        if inf > 90 and not self.sepsis and rng.random() < 0.0007:
            self.sepsis = True
            ev.append("septic")
        if self.sepsis and rng.random() < 0.00035:
            self.dead = True
            self.cause = self.cause or "sepsis"
            ev.append("died_of_sepsis")
        # shock: blood loss, agony, burns close a man down; lying warm, morphine and fluids bring him back
        loss = max(0.0, (3900 - self.blood)) / 3900 * 0.35 + max(0.0, self.effective_pain() - 100) / 2000 + \
            (0.02 if self.burning else 0.0)
        self.shock = min(160.0, self.__dict__.get("shock", 0.0) + loss)
        if not loss:
            self.shock = max(0.0, self.shock - (0.08 if self.__dict__.get("warm", 0) else 0.03) -
                             (0.03 if self.morphine > 10 else 0.0))
        if self.__dict__.get("warm", 0) > 0:
            self.warm -= 1
        if self.shock >= 95 and self.unconscious <= 0 and rng.random() < 0.12:
            self.unconscious = rng.randint(20, 70)
            ev.append("shock")
        if self.shock >= 150 and rng.random() < 0.0015:
            self.dead = True
            self.cause = self.cause or "shock"
            ev.append("shock_death")
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
        return max(ws, key=lambda w: w.bleed + (6 if w.arterial else 0)) if ws else None

    def bleeding_wound(self, part: str | None = None):
        ws = [w for w in self.wounds if not w.bandaged and not w.tourniquet and w.bleed > 0.2
              and (part is None or w.part == part)]
        return max(ws, key=lambda w: w.bleed + (6 if w.arterial else 0)) if ws else None

    def bandage(self, quality: float = 1.0, part: str | None = None, turn: int = 0,
                pressure: bool = False, burn: bool = False) -> Wound | None:
        ws = [w for w in self.wounds if not w.bandaged and not w.tourniquet and (part is None or w.part == part)]
        if not ws:
            return None
        if burn:
            ws = [w for w in ws if w.burn] or ws
        elif pressure:
            ws = [w for w in ws if w.arterial] or ws
        w = max(ws, key=lambda v: v.bleed + (6 if v.arterial else 0))
        w.bandaged = True
        w.pressure = pressure
        w.dress_turn = turn
        w.dirt *= max(0.0, 1.0 - 0.55 * quality)
        w.infection = max(0.0, getattr(w, "infection", 0.0) - 12 * quality)
        return w

    def tourniquet(self, turn: int = 0) -> Wound | None:
        limb = [w for w in self.wounds if w.part not in ("head", "torso") and not w.tourniquet]
        if not limb:
            return None
        part = max(limb, key=lambda w: w.bleed).part
        for w in self.wounds:
            if w.part == part:
                w.tourniquet = True
                w.tourniquet_turn = turn
        return limb[0]

    def splint(self, part: str, turn: int, quality: float = 1.0) -> bool:
        """Brace a broken limb. Returns False if there's nothing broken there."""
        if not any(w.part == part and w.fracture for w in self.wounds):
            return False
        self.splint_turn = dict(self.__dict__.get("splint_turn", {}))
        self.splint_turn[part] = turn + int(43200 * max(0.2, quality))
        self.pain = max(0.0, self.pain - 10)
        return True

    def antisepsis(self, quality: float = 1.0, turn: int = 0) -> int:
        n = 0
        for w in self.wounds:
            if getattr(w, "infection", 0.0) <= 1 and getattr(w, "dirt", 0) <= 0.02:
                continue
            w.infection = max(0.0, getattr(w, "infection", 0.0) * (1 - 0.5 * quality) - 8 * quality)
            w.dirt *= 1 - 0.6 * quality
            w.sulfa_turn = turn
            n += 1
        return n

    def warm(self, turns: int = 600):
        self.warm = turns
        self.shock = max(0.0, self.__dict__.get("shock", 0.0) - 12)

    def heal_blood(self, ml: float):
        self.blood = min(BLOOD_MAX, self.blood + ml)

    # ------------------------------------------------------------ description
    def part_status(self, part: str) -> tuple[str, tuple]:
        r = self.hp[part] / self.max[part]
        if self.hp[part] <= 0:
            return ("mangled" if part not in ("head", "torso") else "destroyed", (170, 0, 0))
        if any(w.part == part and w.necrosis for w in self.wounds):
            return "blackening", (150, 120, 105)
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
        if self.__dict__.get("shock", 0) > 105:
            out.append(("Going grey and cold. Shock.", (170, 190, 220)))
        elif self.__dict__.get("shock", 0) > 65:
            out.append(("Shivering, sick, far away.", (180, 190, 205)))
        inf = self.infection()
        if inf > 75:
            out.append(("The wound stinks. You're burning up.", (230, 160, 90)))
        elif inf > 40:
            out.append(("The wound is angry and hot. Feverish.", (225, 175, 100)))
        for w in self.wounds:
            if w.necrosis and w.part not in ("head", "torso"):
                out.append((f"The {PART_NAME[w.part]} is blackening.", (160, 130, 110)))
                break
        for w in self.wounds:
            if w.fracture and w.part not in ("head", "torso"):
                out.append((f"Something grinds in your {PART_NAME[w.part]}." +
                            ("" if self.splinted_at(w.part) else " It needs splinting."), (220, 200, 140)))
                break
        return out
