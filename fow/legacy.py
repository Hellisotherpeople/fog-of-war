"""What it may come to, after you.

The game can't know the future, so this is explicitly a guess - but a guess built from what actually
happened: the men you kept alive, the ground you took, the convoy you cut, the camp you ran, the
prisoner you shot.  Effects are chained forward by months and years, the way a soldier's small act
reaches men he will never meet.

Every line is hedged.  The screen says so once: none of it is certain.
"""
from __future__ import annotations


def _names(game, n=2):
    p = game.player
    out = []
    for sq in game.squads:
        if sq.side != p.side or sq.gone:
            continue
        for a in sq.members:
            if a is p or not a.alive:
                continue
            if max(abs(a.x - p.x), abs(a.y - p.y)) <= 40:
                out.append(a)
    out.sort(key=lambda a: (-a.skill, a.id))
    return out[:n]


def project(game):
    """[(text, tone)] - tone: good, bad, mixed, flat."""
    p = game.player
    st = game.stats
    out = []
    mates = _names(game, 2)
    if mates:
        a = mates[0]
        out.append((f"{a.rank_short} {a.last_name} was with you when it happened. He will make corporal by "
                    f"the spring, and use your way of doing things on the men he trains.", "good"))
        if len(mates) > 1:
            out.append((f"{mates[1].last_name} will not talk about the war after it. His son will find the "
                        f"medal in a drawer in 1961 and not know what it was for.", "flat"))
    if st.get("objectives", 0):
        out.append((f"The ground you took is held until the next push. The maps drawn from it will still "
                    f"be used in the planning of a battle you will never see.", "good"))
    if st.get("batteries_silenced", 0):
        out.append(("The battery you silenced will be traced to a field two miles back, rebuilt, and firing "
                    "again in a week. For one week, some other company's supply road ran quiet.", "mixed"))
    if st.get("civilian_deaths", 0):
        n = st["civilian_deaths"]
        out.append((f"{n} dead civilians in {game.sector.name}. The district's letter of complaint will run "
                    f"to two pages; a copy will still be in the mayor's file after the war.", "bad"))
    ugly = game.__dict__.get("atrocities") or {}
    counts = ugly.get("counts") or {}
    if counts.get("prisoner_shot"):
        line = "A prisoner you shot will be argued about in the battalion's history."
        if getattr(p, "service", "") == "ss":
            line += " The SS book credits the decision; the line companies will keep arguing."
        out.append((line, "mixed"))
    c = game.__dict__.get("camp")
    if c is not None:
        alive = c.get("prisoners", 0)
        out.append((f"The camp's labour still returns {c.get('labour', 0):.0f} crates' worth to the depots. "
                    f"Most of its prisoners will see 1945; {max(0, c.get('dead', 0))} will not.", "mixed"))
    pol = game.__dict__.get("politics")
    if pol is not None:
        out.append(("The direction you set will be quoted in a staff college exercise in 1949 as an example, "
                    "and its cost will be left out.", "mixed"))
    if st.get("kills", 0) >= 10:
        out.append((f"Your name will appear in the regimental roll with {st['kills']} confirmed. It will mean "
                    f"less to the men who read it than the number suggests.", "flat"))
    if not out:
        out.append(("Your kit goes to the next man through the depot. The section has a gap for a week and "
                    "then it has a name it has already stopped saying.", "flat"))
        out.append(("The war barely notices. Most soldiers are in this column.", "flat"))
    out.append(("The replacements will be younger than you were. Nobody will tell them what the ground "
                "is like, and they will learn it the same way.", "flat"))
    return out
