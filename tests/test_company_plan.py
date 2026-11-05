"""The company plan: a main effort, a supporting attack and a reserve; outposts, a main line and a
counterattack; bounds and a limit of advance; and holding the ground deciding the sector."""
from unittest.mock import patch

from test_command_realism import scene, soldier
from fow import ai, commander, plan
from fow.constants import other_side
from fow.gamemap import Objective
from fow.orders import book


def field(n_squads=5, side_attacks=True, nation="usa"):
    """A clear field, the attack coming from the north, three objectives one behind another."""
    g = scene()
    g.squads = [sq for sq in g.squads if sq is not g.player.squad]
    g.player.squad.player_led = False
    g.att_edge = "N"
    obs = [Objective("the orchard", 20, 20, 5), Objective("the church", 44, 24, 5),
           Objective("Hill 112", 32, 50, 6)]
    for ob in obs:
        ob.owner = None
        plan.classify(g.map, ob)
    g.map.objectives = obs
    g.map.__dict__.pop("objective_reports", None)
    sqs = []
    for i in range(n_squads):
        a = soldier(g, 12 + i * 8, 4 + (i % 2) * 2, nation=nation, role="rifleman")
        for j in range(3):
            b = soldier(g, a.x + 1 + j, a.y + 1, nation=nation, role="rifleman")
            g.squads.remove(b.squad)
            b.squad = a.squad
            a.squad.members.append(b)
        a.squad.initial = 4
        sqs.append(a.squad)
    side = sqs[0].side
    g.attacker = side if side_attacks else other_side(side)
    return g, side, sqs, obs


def report(g, side, ob, owner):
    """Word of who holds it reaches the side's headquarters."""
    ob.owner = owner
    ob.__dict__.setdefault("reported_owners", {})[side] = owner


def run(g, side):
    with patch("fow.command.low_on_ammo", return_value=False):
        commander.commander_update(g, side)
    return g.plans[(side, plan.sector_key(g, 30, 30))]


def test_objectives_are_ground_with_a_value():
    g, side, sqs, obs = field()
    assert [(o.kind, o.value) for o in obs] == [("point", 1), ("village", 2), ("height", 3)]
    farm = Objective("the collective farm", 1, 1)
    assert plan.classify(g.map, farm) == ("village", 2)      # ("col" is a hill word, but not here)


def test_attack_has_a_main_effort_a_supporting_attack_and_a_reserve_in_bounds():
    g, side, sqs, obs = field()
    p = run(g, side)
    assert p["posture"] == "attack" and p["scheme"] == "deliberate"
    roles = [p["roles"][sq.id] for sq in sqs]
    assert roles.count("reserve") == 1 and roles.count("fix") == 1 and roles.count("main") == 3
    # the first bound is the two nearer objectives; the hill behind them is the limit of advance
    assert len(p["phases"]) == 2 and p["limit"] == plan.ob_key(obs[2])
    assert p["main"] == plan.ob_key(obs[1])                 # the church matters more than the orchard
    assert p["fix"] == plan.ob_key(obs[0])
    for sq in sqs:
        role = p["roles"][sq.id]
        if role == "main":
            assert sq.order.kind == "attack" and sq.order.obj == 1
            assert sq.rep["intent"]["mission"] == "seize"
        elif role == "fix":
            assert sq.order.kind == "attack" and sq.order.obj == 0 and sq.rep["intent"]["risk"] == "cautious"
        else:
            assert sq.order.kind == "defend" and sq.order.obj is None
            assert sq.rep["intent"]["mission"] == "reserve"
    text = plan.brief(g, p)
    assert "A deliberate attack: the church" in text and "fixes the orchard" in text
    assert "Limit of advance: Hill 112" in text and "goes in to the south" in text


def test_orders_stand_while_the_plan_goes_on():
    g, side, sqs, obs = field()
    run(g, side)
    issued = [sq.order.issued for sq in sqs]
    g.turn += 20
    run(g, side)
    assert [sq.order.issued for sq in sqs] == issued


def test_bound_won_the_reserve_passes_through_and_the_rest_hold():
    g, side, sqs, obs = field()
    p = run(g, side)
    reserve = [sq for sq in sqs if p["roles"][sq.id] == "reserve"]
    report(g, side, obs[0], side)
    report(g, side, obs[1], side)
    g.turn += 20
    p = run(g, side)
    assert p["phase"] == 1 and p["main"] == plan.ob_key(obs[2]) and p["committed"]
    assert all(p["roles"][sq.id] == "main" and sq.order.kind == "attack" and sq.order.obj == 2 for sq in reserve)
    holders = [sq for sq in sqs if sq not in reserve]
    assert all(p["roles"][sq.id] == "hold" and sq.order.kind == "defend" for sq in holders)
    assert any("reserve goes through to Hill 112" in t for _, t in p["log"])
    report(g, side, obs[2], side)
    g.turn += 20
    p = run(g, side)
    assert p["posture"] == "defend" and p["scheme"] == "consolidate"


def test_a_stalled_main_effort_brings_in_the_reserve():
    g, side, sqs, obs = field()
    p = run(g, side)
    for sq in sqs:
        if p["roles"][sq.id] == "main":
            sq.rep["intent"]["halted"] = True
    g.turn += 20
    p = run(g, side)
    assert p["committed"] and "reserve" not in p["roles"].values()
    assert any("held up" in t for _, t in p["log"])


def test_outnumbered_attack_is_limited_to_what_matters():
    g, side, sqs, obs = field(n_squads=3)
    for i, ob in enumerate(obs):
        for k in range(6):
            e = soldier(g, ob.x + k, ob.y, nation="germany", role="rifleman")
            g.brains[side].contacts[e.id] = ai_contact(g, e)
    p = run(g, side)
    assert p["scheme"] == "limited" and len(p["phases"]) == 1
    assert p["limit"] == p["main"]


def ai_contact(g, e):
    from fow.brain import Contact
    return Contact(e.id, e.x, e.y, g.turn, "inf", ref=e)


def test_defence_has_an_outpost_a_main_line_and_a_reserve_that_counterattacks():
    g, side, sqs, obs = field(side_attacks=False)
    for ob in obs:
        report(g, side, ob, side)
    p = run(g, side)
    assert p["posture"] == "defend" and p["scheme"] == "defence in depth"
    roles = sorted(p["roles"][sq.id] for sq in sqs)
    assert roles == ["line", "line", "line", "outpost", "reserve"]
    # forward is toward the north, where they come from: the orchard is the outpost
    assert p["outpost"] == plan.ob_key(obs[0]) and p["main"] == plan.ob_key(obs[2])
    out = next(sq for sq in sqs if p["roles"][sq.id] == "outpost")
    assert out.rep["intent"]["mission"] == "screen" and out.order.obj == 0
    assert "Expect them from the north" in plan.brief(g, p)
    # the church is lost: the reserve goes straight back in
    report(g, side, obs[1], other_side(side))
    g.turn += 20
    p = run(g, side)
    res = next(sq for sq in sqs if p["roles"][sq.id] == "counter")
    assert res.order.kind == "attack" and res.order.obj == 1 and p["counter"] == plan.ob_key(obs[1])


def test_holding_the_ground_makes_a_beaten_enemy_give_up_the_sector():
    g, side, sqs, obs = field()
    for ob in obs:
        report(g, side, ob, side)
    e = soldier(g, 60, 52, nation="germany", role="rifleman")
    e.squad.initial = 8                                    # what's left of a section
    run(g, side)
    assert e.squad.order.kind != "retreat"
    g.turn += plan.COLLAPSE_HOLD + 20
    run(g, side)
    assert e.squad.order.kind == "retreat"


def test_unbeaten_enemy_does_not_give_up():
    g, side, sqs, obs = field()
    for ob in obs:
        report(g, side, ob, side)
    e = soldier(g, 60, 52, nation="germany", role="rifleman")
    run(g, side)
    g.turn += plan.COLLAPSE_HOLD + 20
    run(g, side)
    assert e.squad.order.kind != "retreat"


def test_the_player_is_told_his_part_but_gives_his_own_orders():
    g, side, sqs, obs = field()
    p0 = g.player
    sq = sqs[0]
    sq.members.append(p0)
    p0.squad, sq.leader, sq.player_led = sq, p0, True
    p0.x, p0.y = sq.members[0].x, sq.members[0].y + 1
    sq.order = ai.Order("hold", target=p0.pos)
    p = run(g, side)
    assert sq.id in p["roles"] and sq.order.kind == "hold"
    text, pt = plan.for_player(g)
    assert "Your section:" in text and pt is not None
    entry = next(o for o in book(g) if o["key"] == "command")
    assert entry["text"] == text


def test_soviet_attack_concentrates_and_has_no_supporting_attack():
    g, side, sqs, obs = field(nation="ussr")
    p = run(g, side)
    assert p["scheme"] == "concentrated" and p["fix"] is None
    assert "fix" not in p["roles"].values()


def test_a_meeting_engagement_goes_for_the_key_ground_and_the_withdrawn_stay_withdrawn():
    g, side, sqs, obs = field()
    g.attacker = None
    g.sector.control = None
    p = run(g, side)
    assert p["posture"] == "meeting" and p["main"] == plan.ob_key(obs[2])     # the hill
    mains = [sq for sq in sqs if p["roles"][sq.id] == "main"]
    assert mains and all(sq.order.kind == "attack" and sq.order.obj == 2 for sq in mains)
    plan.withdraw(g, side, plan.sector_key(g, 30, 30), sqs)
    g.turn += 20
    run_any = commander.commander_update
    with patch("fow.command.low_on_ammo", return_value=False):
        run_any(g, side)
    assert all(sq.order.kind == "retreat" for sq in sqs)
