"""Follow routine orders until contact or a decision requires the player's hand."""
from .orders import active


def danger(ps):
    g, p = ps.game, ps.game.player
    if g.game_over or not p.alive or not p.body.conscious or p.downed:
        return 'You need to take control.'
    if p.suppression > 5 or g.turn - p.hit_turn < 20 or p.body.bleed_rate() > .5:
        return 'Travel stopped: incoming fire or wounds.'
    if g.seen_enemies():
        return 'Travel stopped: enemy contact.'
    if g.explosive_danger(p.x, p.y, 8) is not None or g.map.fire[p.x, p.y] > 0:
        return 'Travel stopped: immediate danger.'
    if ps.interrupted():
        return 'Travel stopped: something needs your attention.'
    return None


def start(ps):
    if ps.__dict__.get('objective_auto'):
        ps.stop_auto('Objective travel stopped.')
        return
    ps.stop_auto()
    if ps.game.__dict__.get('autopilot'):
        from .succession import set_autopilot
        set_autopilot(ps.game, False)
    ps.mark_interrupt()
    reason = danger(ps)
    if reason:
        ps.game.msg(reason, 'info')
        return
    ps.objective_auto = True
    ps.game.msg('Following your objective. Contact, danger or a decision stops travel; any key cancels.', 'info')
    step(ps)


def step(ps):
    if not ps.__dict__.get('objective_auto'):
        return False
    reason = danger(ps)
    if reason:
        ps.stop_auto(reason)
        return True
    if ps.popups or ps.inv_screen is not None or ps.mode != 'normal':
        ps.objective_auto = False
        return True
    current = active(ps.game)
    if current and (current['key'] == 'fire' or (current.get('task') or {}).get('kind') == 'fire'):
        ps.stop_auto('Your next instruction involves combat. You have control.')
        return True
    before = (ps.game.turn, ps.game.player.pos, ps.game.sector)
    plan = ps._order_plan()
    if plan is None:
        ps.stop_auto('At the objective, or no travel instruction is available. You have control.')
        return True
    ps.cmd_do_order()
    if ps.auto_wait and not ps.popups:
        ps.objective_auto = True
    states = getattr(ps.app, 'states', [])
    if ps.popups or (states and states[-1] is not ps):
        ps.objective_auto = False
    elif not ps.travel_path and not ps.auto_wait and before == (ps.game.turn, ps.game.player.pos, ps.game.sector):
        ps.stop_auto('Your next instruction needs a decision. You have control.')
    return True
