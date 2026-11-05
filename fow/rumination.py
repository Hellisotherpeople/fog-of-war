"""The numbers of one man's fight, and the reason he was in it.

Grim statistics are only useful when they are true and close.  The player's own minutes, rounds and
wounds are counted by the simulation; the world figure is the accepted order of magnitude for the
Second World War, marked as an average.  The "why" line is drawn from what the run actually contains:
the men still standing, the job, the ground.
"""
from __future__ import annotations


def numbers(game):
    p = game.player
    st = game.stats
    minutes = max(0, game.clock // 60)
    shots = p.stats.get("shots", 0)
    wounds = st.get("wounds", 0)
    if minutes < 12 and shots < 40 and wounds < 2:
        return []
    out = []
    bits = [f"{minutes} minutes", f"{shots} rounds fired", f"{p.stats.get('hits', 0)} hits"]
    if wounds:
        bits.append(f"{wounds} wound{'s' if wounds != 1 else ''}")
    if st.get("kills"):
        bits.append(f"{st['kills']} enemy killed by your hand")
    out.append("Your fight: " + ", ".join(bits) + ".")
    out.append("Across the world, the war was killing about thirty thousand people a day, on average, "
               "for six years.")
    if minutes >= 45:
        out.append(f"At that rate, {minutes * 30_000 // 1440:,} people died while you were in the line.")
    return out


def why(game):
    p = game.player
    mates = [a for sq in game.squads if sq.side == p.side and not sq.gone for a in sq.members
             if a is not p and a.alive]
    if p.role in ("medic", "surgeon") and mates:
        return "You were there to get men off the field. Some of them are still on it."
    if mates:
        return f"You did it for the man on your left. {mates[0].last_name} is still there to be owed it."
    if game.sector is not None:
        return f"You did it so the line would not be behind your own street in {game.sector.name}."
    return "You did it because the man beside you had nobody else, and neither did you."
