"""How hard the war is, as a setting rather than a mood.

A preset changes a handful of real numbers: how well the enemy is trained and how hard he looks, how fast
you bleed, whether the game coaches you, and whether a run can be reloaded after death.  Nothing here is a
cheat key - the same simulation runs either way, and every value is visible in the difficulty screen.

    recruit     green conscripts opposite you, a slow bleed, the coach on, many lives
    veteran     the war as written
    realistic   trained and watchful enemy, a faster bleed, no coaching, one life unless you say otherwise
    custom      your own numbers

The preset is fixed per run (it is part of the save), except for the assist toggles, which are settings.
"""
from __future__ import annotations

PRESETS = ("recruit", "veteran", "realistic", "custom")
DEFAULT = "veteran"

# enemy_skill and enemy_spot scale his training and his eyes; player_bleed scales your blood loss;
# enemy_morale scales how long he stays in a fight.  assist is convenience, not simulated.
VALUES = {
    "recruit": dict(enemy_skill=0.78, enemy_spot=0.82, enemy_morale=0.88, player_bleed=0.78),
    "veteran": dict(enemy_skill=1.0, enemy_spot=1.0, enemy_morale=1.0, player_bleed=1.0),
    "realistic": dict(enemy_skill=1.14, enemy_spot=1.1, enemy_morale=1.1, player_bleed=1.22),
    "custom": dict(enemy_skill=1.0, enemy_spot=1.0, enemy_morale=1.0, player_bleed=1.0),
}
ASSIST = {
    "recruit": dict(hints=True, safe=True, autopilot=True, lives=3),
    "veteran": dict(hints=True, safe=True, autopilot=True, lives=0),
    "realistic": dict(hints=False, safe=False, autopilot=True, lives=0),
    "custom": dict(hints=True, safe=True, autopilot=True, lives=0),
}
LABELS = {
    "recruit": "Recruit - green enemy, a slow bleed, coached",
    "veteran": "Veteran - the war as written",
    "realistic": "Realistic - trained and watchful enemy, no coaching, a faster bleed",
    "custom": "Custom - your own numbers",
}
FIELDS = ("enemy_skill", "enemy_spot", "enemy_morale", "player_bleed")


def title(preset) -> str:
    return LABELS.get(preset, preset)


def make(preset=DEFAULT, custom=None) -> dict:
    preset = preset if preset in PRESETS else DEFAULT
    d = dict(kind=preset)
    base = VALUES["veteran"] if preset == "custom" else VALUES[preset]
    d.update(base)
    if preset == "custom":
        for k in FIELDS:
            try:
                d[k] = round(max(0.25, min(2.5, float((custom or {}).get(k, 1.0)))), 2)
            except (TypeError, ValueError):
                pass
    return d


def of(game) -> dict:
    d = game.__dict__.get("difficulty")
    if not isinstance(d, dict):
        d = game.__dict__["difficulty"] = make(game.setup.get("difficulty", DEFAULT))
    return d


def get(game, key, default=1.0) -> float:
    try:
        return float(of(game).get(key, default))
    except (TypeError, ValueError):
        return default


def kind(game) -> str:
    return str(of(game).get("kind", DEFAULT))


def assist(game, key, default=False):
    return bool(ASSIST.get(kind(game), ASSIST[DEFAULT]).get(key, default))


def ironman(game) -> bool:
    return bool(game.setup.get("ironman"))


def scale_enemy(game, a) -> None:
    """Give an enemy's training and morale the preset's weight (called once, at his creation)."""
    if a.is_player or a.side == game.player_side:
        return
    k = get(game, "enemy_skill")
    m = get(game, "enemy_morale")
    if k != 1.0:
        a.skill = max(0.0, min(10.0, getattr(a, "skill", 5.0) * k))
        s = a.__dict__.get("skills")
        if isinstance(s, dict):
            for key in list(s):
                s[key] = round(max(0.0, min(10.0, s[key] * k)), 1)
    if m != 1.0:
        a.morale = max(1.0, min(100.0, a.morale * m))


def lines(preset=None) -> list[tuple[str, str]]:
    """What the difficulty screen says, plainly."""
    k = preset or DEFAULT
    v = VALUES.get(k, VALUES[DEFAULT])
    return [
        ("Enemy training", f"{v['enemy_skill']:.2f}x"),
        ("Enemy eyes", f"{v['enemy_spot']:.2f}x"),
        ("Enemy resolve", f"{v['enemy_morale']:.2f}x"),
        ("Your bleeding", f"{v['player_bleed']:.2f}x"),
        ("Coaching", "on" if ASSIST.get(k, {}).get("hints") else "off"),
        ("Safe mode default", "on" if ASSIST.get(k, {}).get("safe") else "off"),
        ("Life after death", "succession allowed" if ASSIST.get(k, {}).get("lives") else
         ("one life" if k == "realistic" else "off")),
    ]
