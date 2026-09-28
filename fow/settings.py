"""Persistent user settings (~/.fogofwar/settings.json)."""
from __future__ import annotations

import json
import os

SETTINGS_DIR = os.environ.get("FOW_HOME") or os.path.join(os.path.expanduser("~"), ".fogofwar")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "settings.json")

DEFAULTS = {
    "sprites": True,          # graphical tiles on the battlefield (F2)
    "sound": True,            # audio (F3)
    "volume": 0.8,
    "ambience": True,
    "voices": True,           # soldiers' shouts and radio traffic, spoken
    "voice_engine": "neural", # "neural" (Piper: natural, local; needs piper-tts) or "system" (say / espeak: instant)
    "font": "ttf",            # "ttf" (DejaVu Sans Mono, crisp at any size) or "bitmap"
    "font_scale": 1.0,        # >1 bigger text (fewer columns fit, window grows)
    "zoom": 1.4,              # sprite size relative to a text row (mouse wheel / + -)
    "zoom_ascii": 1.0,        # ASCII map cell size relative to a text cell
    "show_numbers": False,    # hit chances as numbers instead of words
    "pictures": True,         # the kit, the body, the watch... drawn in the interface (icons.py), not only named
    "anim_speed": "fast",     # fast / normal / slow / very slow: how long shots and blasts stay on screen
    "auto_center": True,      # the view glides back to you whenever you move
    "edge_scroll": False,     # the mouse at the edge of the battlefield scrolls it
    "shake": True,            # the view jolts when shells land close
    "safe_mode": True,        # stop and warn before a step while the enemy's in sight or you're under fire
    "going": False,           # X: the ground tinted by the going (red: no way through; amber: slow)
    "hints": True,            # a line under your orders with the keys for what's beside you
    # the sound mixer (each 0..1, on top of the master volume)
    "vol_weapons": 0.9,       # gunfire, shells, explosions, ricochets
    "vol_ambience": 0.45,     # the distant battle, wind and rain
    "vol_voices": 0.9,        # shouts, orders, the radio
    "vol_effects": 0.8,       # footsteps, engines, doors, digging, the ringing in your ears
    "vol_ui": 0.6,            # clicks and rustles of the interface
    "sound_log": "all",       # which sounds are written in the message log: all / near / off
    "battlefield": "large",   # for new games: standard / large / huge (see game.BATTLEFIELDS)
    "autosave": True,         # save every few minutes of real time as well as on quitting
    "minimap": False,         # the minimap is open when a game starts
    # when you die (succession.py): off - the end; on - carry on as someone else; choose - pick who
    "succession": "off",
    "succession_rule": "squad",   # squad / unit / nearest / role / rank / random / killer
    "succession_side": "own",     # own / any
    "succession_lives": 0,        # 0: no limit
}
ANIM_SPEEDS = ("fast", "normal", "slow", "very slow")
ANIM_FRAME = {"fast": 0.035, "normal": 0.07, "slow": 0.16, "very slow": 0.32}


class Settings(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}                         # (a settings file that isn't settings: ignore it)
            for k, v in data.items():
                if k in DEFAULTS and type(v) is type(DEFAULTS[k]) or (k in DEFAULTS and isinstance(DEFAULTS[k], float) and isinstance(v, (int, float))):
                    self[k] = v
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH) or SETTINGS_DIR, exist_ok=True)
            tmp = SETTINGS_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dict(self), f, indent=2)
            os.replace(tmp, SETTINGS_PATH)       # (all or nothing: a crash mid-write doesn't lose your settings)
        except OSError:
            pass

    def toggle(self, key):
        self[key] = not self[key]
        self.save()
        return self[key]
