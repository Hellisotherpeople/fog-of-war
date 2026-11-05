"""Rebindable keys.

The defaults are the ones on the keyboard a soldier would be handed.  A player with an AZERTY board,
a laptop without a number pad, or a hand that knows another game can move them: the interface maps
the key back to the action's canonical character before anything else reads it, and the menus and
help print the player's key, not the default.

No action is allowed to end up bound twice: binding one to a key an action already has swaps the
two.  Movement and the menus keep their function keys, which are never rebound.
"""
from __future__ import annotations

# action: (default, label, group).  Only one-character actions are here.
BINDS = {
    "move_nw": ("y", "North-west", "move"),
    "move_n": ("k", "North", "move"),
    "move_ne": ("u", "North-east", "move"),
    "move_w": ("h", "West", "move"),
    "move_e": ("l", "East", "move"),
    "move_sw": ("b", "South-west", "move"),
    "move_s": ("j", "South", "move"),
    "move_se": ("n", "South-east", "move"),
    "wait": (".", "Wait a second", "move"),
    "crouch": ("c", "Crouch", "stance"),
    "prone": ("p", "Go prone", "stance"),
    "peek": ("q", "Peek out of cover", "stance"),
    "fire": ("f", "Aim and fire", "weapon"),
    "aim": ("a", "Aim longer", "weapon"),
    "reload": ("r", "Reload", "weapon"),
    "mode": ("F", "Fire mode / round", "weapon"),
    "throw": ("t", "Throw", "weapon"),
    "bandage": ("B", "Dress a wound", "body"),
    "shout_medic": ("Y", "Shout for a medic", "body"),
    "inventory": ("i", "Your kit", "kit"),
    "pickup": ("g", "Pick up", "kit"),
    "look": ("x", "Look", "world"),
    "nearby": ("V", "Everything nearby", "world"),
    "battle_map": ("M", "Battlefield map", "world"),
    "map": ("m", "War map", "world"),
    "health": ("@", "Your body", "world"),
    "vehicle": ("e", "Mount / dismount", "world"),
    "talk": ("E", "Talk", "world"),
    "command": ("C", "Command", "command"),
    "orders": ("O", "Orders to your section", "command"),
    "follow_me": ("F9", "Follow me", "command"),
    "trace": ("F8", "Order trace", "command"),
    "search": ("/", "Find a command", "world"),
    "safe_mode": ("!", "Safe mode", "world"),
    "orders_book": ("T", "Orders book", "command"),
}
_SPECIAL = {"follow_me", "trace"}
GROUPS = ("move", "stance", "weapon", "body", "kit", "world", "command")
GROUP_NAME = {"move": "Movement", "stance": "Stance and cover", "weapon": "The weapon", "body": "Your body",
              "kit": "Kit and ground", "world": "The world", "command": "Command"}


def table(settings) -> dict:
    """action -> key, with the player's overrides applied."""
    over = (settings or {}).get("keymap") or {}
    return {a: over.get(a, d) for a, (d, _l, _g) in BINDS.items()}


def reverse(settings) -> dict:
    return {k: a for a, k in table(settings).items() if k and len(k) == 1}


def remap(settings, ch: str) -> str:
    """The canonical key for a typed character, or the character itself."""
    rev = reverse(settings)
    action = rev.get(ch)
    if action is None:
        return ch
    return BINDS[action][0]


def bind(settings, action: str, key: str):
    """Set a key, swapping it from whichever other action had it."""
    if action not in BINDS or len(key) != 1:
        return
    km = dict((settings or {}).get("keymap") or {})
    for other, k in table(settings).items():
        if k == key and other != action:
            km[other] = table(settings)[action]
    km[action] = key
    settings["keymap"] = km


def reset(settings):
    settings["keymap"] = {}


def key_for(settings, action: str) -> str:
    return table(settings).get(action, BINDS.get(action, ("?",))[0])


def label(settings, token: str) -> str:
    """A help keycap with the player's keys: 'f|Tab' -> the bound fire key, then Tab."""
    import re
    canon = {d: a for a, (d, _l, _g) in BINDS.items() if len(d) == 1}
    t = table(settings)
    out = []
    for part in re.split(r"([|/ ])", token):
        a = canon.get(part)
        out.append(t[a] if a else part)
    return "".join(out)
