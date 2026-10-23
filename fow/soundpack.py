"""Recorded sound packs (assets/sounds/<pack>): the real weapons, where there are recordings of them.

A pack is a folder of OGG files and a pack.json naming the slot each one fills ("mg42", "garand", "expl_big",
...).  PackBank answers exactly as the synthesised Bank does, so anything the pack has no recording for is
still synthesised.  Automatic weapons are recorded as bursts with each shot's start marked (pack.json
"onsets"); a burst of any length is rebuilt from those shots at the weapon's own rate, with the recording's
real tail - the echo off the hedgerows - after the last round.
"""
from __future__ import annotations

import json
import os
import random

import numpy as np

from .audio import SR, _filter, _norm, _reverb

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")

# a weapon's own recording first, then its family's
WEAPON_SLOTS = {
    "mg42": ("mg42",), "mg42_tripod": ("mg42",), "mg34": ("mg34", "mg42"), "mg34_tripod": ("mg34", "mg42"),
    "m1919": ("mg30cal", "lmg"), "m2hb": ("hmg50", "mg30cal"), "bar": ("bar", "lmg"), "bren": ("bren", "lmg"),
    "dp28": ("dp28", "lmg"), "vickers": ("vickers", "mg30cal", "lmg"), "maxim1910": ("maxim", "mg30cal", "lmg"),
    "maxim_m32": ("maxim", "mg30cal", "lmg"), "type24_maxim": ("maxim", "mg30cal", "lmg"),
    "dshk": ("hmg50",), "besa_hvy": ("hmg50",),
    "thompson_m1a1": ("thompson", "smg"), "thompson_1928": ("thompson", "smg"), "m3_grease": ("m3", "smg"),
    "sten": ("sten", "smg"), "sten_mk2s": ("sten", "smg"), "mp40": ("mp40", "smg"), "mp38": ("mp40", "smg"),
    "ppsh": ("ppsh", "smg"), "ppd40": ("ppsh", "smg"), "pps43": ("ppsh", "smg"),
    "stg44": ("stg44", "smg"), "fg42": ("stg44", "lmg"),
    "m1_garand": ("garand", "rifle_semi", "rifle_bolt"), "svt40": ("rifle_semi", "rifle_bolt"),
    "g43": ("rifle_semi", "rifle_bolt"), "m1_carbine": ("carbine", "rifle_semi", "rifle_bolt"),
    "kar98k": ("kar98k", "rifle_bolt"), "kar98k_zf": ("kar98k", "rifle_bolt"), "mosin": ("mosin", "rifle_bolt"),
    "mosin_pu": ("mosin", "rifle_bolt"), "m44": ("mosin", "rifle_bolt"), "smle": ("enfield", "rifle_bolt"),
    "lee_no4": ("enfield", "rifle_bolt"), "lee_no4t": ("enfield", "rifle_bolt"),
    "m1903": ("springfield", "rifle_bolt"), "m1903a4": ("springfield", "rifle_bolt"),
    "m1911": ("m1911", "pistol"), "p08": ("luger", "pistol"), "p38": ("p38", "pistol"),
    "m97_trench": ("shotgun",), "ptrd": ("at_rifle", "hmg50"), "ptrs": ("at_rifle", "hmg50"),
    "boys": ("at_rifle", "hmg50"), "pzb39": ("at_rifle",),
}
CAT_SLOTS = {"rifle": ("rifle_bolt",), "sniper": ("rifle_bolt",), "carbine": ("carbine", "rifle_semi", "rifle_bolt"),
             "smg": ("smg",), "assault": ("stg44", "smg"), "lmg": ("lmg", "mg42"), "hmg": ("mg30cal", "lmg"),
             "pistol": ("pistol",), "shotgun": ("shotgun",), "at_rifle": ("at_rifle", "hmg50")}
AUTO_CATS = {"smg", "assault", "lmg", "hmg"}
# the synthesised bank's names, and the recordings that stand for them
SYNTH_SLOTS = {
    "rifle": ("rifle_bolt",), "pistol": ("pistol",), "shotgun": ("shotgun",), "atrifle": ("at_rifle",),
    "cannon": ("tank_cannon", "artillery_fire"), "expl_small": ("expl_small", "expl_med"),
    "expl_med": ("expl_med", "expl_small"), "expl_big": ("expl_big", "expl_med"), "mortar": ("mortar_fire",),
    "rocket": ("rocket_launch",), "whistle": ("shell_incoming",), "siren": ("air_raid_siren",),
    "ricochet": ("ricochet",), "whizz": ("bullet_by",), "ping": ("garand_ping",), "clang": ("metal_impact",),
    "reload": ("bolt_cycle", "reload_mag"), "thud": ("body_fall",), "engine": ("tank_engine",),
    "truck": ("truck",), "aircraft": ("aircraft_flyby",), "flamer": ("flamethrower",), "glass": ("glass_break",),
    "whistle_officer": ("officer_whistle",), "radio": ("radio_static",), "step": ("footsteps",),
    "splash": ("splash",), "thunder": ("thunder",), "sonar": ("sonar_ping",), "depth_charge": ("depth_charge",),
    "klaxon": ("dive_klaxon",), "flak": ("flak",), "stuka": ("stuka_siren",), "torpedo": ("torpedo",),
    "naval_gun": ("naval_gun", "tank_cannon"), "bazooka": ("rocket_launch",), "telephone": ("field_telephone",),
}
LOOP_SLOTS = {"battle": "amb_distant_battle", "wind": "amb_wind", "rain": "amb_rain"}


def packs():
    """The recorded packs there are."""
    try:
        return sorted(d for d in os.listdir(ROOT) if os.path.exists(os.path.join(ROOT, d, "pack.json")))
    except OSError:
        return []


def _far(x):
    return _norm(_reverb(_filter(x, hi=650), taps=((0.2, 0.4), (0.45, 0.25), (0.8, 0.15))), 0.6)


class PackBank:
    """The synthesised bank with the pack's recordings laid over it."""

    def __init__(self, name, synth):
        import soundfile as sf
        self.name = name
        self.synth = synth
        self.rec: dict[str, list[np.ndarray]] = {}
        self.onsets: dict[str, list] = {}
        self.gain: dict[str, float] = {}
        self._far: dict = {}
        self._bursts: dict = {}
        folder = os.path.join(ROOT, name)
        with open(os.path.join(folder, "pack.json"), encoding="utf-8") as f:
            spec = json.load(f)
        for slot, entries in spec.get("slots", {}).items():
            for e in entries:
                try:
                    x, sr = sf.read(os.path.join(folder, e["file"]), dtype="float32", always_2d=True)
                except Exception:
                    continue
                x = x.mean(axis=1)
                if sr != SR:
                    n = int(round(len(x) * SR / sr))
                    x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
                if not len(x):
                    continue
                x = (x * float(e.get("gain", 1.0))).astype(np.float32)
                self.rec.setdefault(slot, []).append(x)
                self.onsets.setdefault(slot, []).append(
                    [int(o * SR / sr) for o in e["onsets"]] if e.get("onsets") else None)
        self.loops = dict(synth.loops)
        for k, slot in LOOP_SLOTS.items():
            if self.rec.get(slot):
                self.loops[k] = self.rec[slot][0]
        self.s = synth.s

    # ------------------------------------------------------------ the synthesised bank's interface
    def get(self, k):
        base, far = (k[:-4], True) if k.endswith("_far") else (k, False)
        for slot in SYNTH_SLOTS.get(base, ()):
            x = self._pick(slot, far)
            if x is not None:
                return x
        return self.synth.get(k)

    def burst(self, kind, rps, n):
        return self.synth.burst(kind, rps, n)

    def burst_far(self, kind, rps, n):
        return self.synth.burst_far(kind, rps, n)

    # ------------------------------------------------------------ recordings
    def _pick(self, slot, far=False):
        v = self.rec.get(slot)
        if not v:
            return None
        i = random.randrange(len(v))
        if not far:
            return v[i]
        key = (slot, i)
        x = self._far.get(key)
        if x is None:
            x = self._far[key] = _far(v[i])
        return x

    def gun(self, weapon, t, far, n):
        """A weapon's own sound: one shot, or a burst of n."""
        cat = getattr(t, "cat", None)
        slots = WEAPON_SLOTS.get(weapon, ()) + CAT_SLOTS.get(cat, ())
        slot = next((s for s in slots if self.rec.get(s)), None)
        if slot is None:
            return None
        if cat in AUTO_CATS and n > 1:
            return self._burst(slot, weapon, n, far)
        return self._shot(slot, far)

    def _shot(self, slot, far):
        """One round; from a burst recording, its first shot and the echo after the last."""
        i = random.randrange(len(self.rec[slot]))
        ons = self.onsets[slot][i]
        if not ons or len(ons) < 2:
            return self._pick_index(slot, i, far)
        key = ("shot", slot, i, far)
        x = self._bursts.get(key)
        if x is None:
            x = self._build(slot, i, 1)
            if far:
                x = _far(x)
            self._bursts[key] = x
        return x

    def _pick_index(self, slot, i, far):
        if not far:
            return self.rec[slot][i]
        key = (slot, i)
        x = self._far.get(key)
        if x is None:
            x = self._far[key] = _far(self.rec[slot][i])
        return x

    def _burst(self, slot, weapon, n, far):
        n = max(1, min(int(n), 60))
        i = random.randrange(len(self.rec[slot]))
        key = ("burst", slot, i, n, far)
        x = self._bursts.get(key)
        if x is None:
            if len(self._bursts) > 400:
                self._bursts.clear()
            x = self._build(slot, i, n)
            if far:
                x = _far(x)
            self._bursts[key] = x
        return x

    def _build(self, slot, i, n):
        """n rounds from the recording's own shots (cycled if it has fewer), then its tail."""
        x = self.rec[slot][i]
        ons = self.onsets[slot][i]
        if not ons or len(ons) < 2:
            return x
        periods = [(ons[k], ons[k + 1]) for k in range(len(ons) - 1)]
        tail_from = ons[-1]
        fade = int(SR * .004)
        pieces = []
        for k in range(n - 1):
            a, b = periods[k % len(periods)] if k < len(periods) else random.choice(periods)
            seg = x[a:b + fade].copy()
            pieces.append(seg)
        last = x[tail_from:] if n > 1 else x[ons[0]:ons[1]].copy()
        if n == 1:
            # a single round: the first shot, then the burst's own echo, faded in under it
            echo = x[tail_from:][int(SR * .02):]
            last = np.concatenate([last, np.zeros(max(0, len(echo) - len(last)), np.float32)])
            last[:len(echo)] += echo * np.linspace(0, 1, len(echo), dtype=np.float32) ** 2 * .6
        total = sum(len(p) - fade for p in pieces) + len(last)
        out = np.zeros(total + fade, np.float32)
        at = 0
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        for seg in pieces:
            seg[-fade:] *= ramp[::-1]
            out[at:at + len(seg)] += seg
            at += len(seg) - fade
        out[at:at + len(last)] += last
        return _norm(out, 0.95)
