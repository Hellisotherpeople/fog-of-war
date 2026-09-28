"""Duty: what's expected of you, and what happens when you don't do it.

As a private you're not left alone.  NCOs and officers who can see or hear you give
you personal orders - get down, see to him, get that ammo over, get on that gun,
put rounds on that hedge, dig, run this message, go and look - and check you did
it.  Do it and you earn their trust (and promotion).  Ignore it and they escalate:
a rebuke, a formal reprimand, stripes taken away.

The same goes for what nobody has to order: patching up the man bleeding next to
you, passing ammunition to a gunner who's run dry.  Comrades do it for you too -
more willingly the better your standing.

Shoot your own men when there's no enemy about and you'll be arrested - or, if it
goes far enough, your own side turns its guns on you.  Shooting men who've
surrendered is a crime where the army cares (and an officer sees it).  Taking
prisoners, and bringing them back to your lines, is rewarded.
"""
from __future__ import annotations

import math

from .data.phrases import lang, phrase

# how seriously each army took the killing of prisoners (and whether an officer would act on it)
CARES_POW = {"usa": 1.0, "uk": 1.0, "canada": 1.0, "australia": 0.9, "newzealand": 1.0, "india": 0.9,
             "france": 0.8, "poland": 0.6, "finland": 0.7, "italy": 0.6, "hungary": 0.4, "romania": 0.4,
             "germany": 0.3, "ussr": 0.1, "japan": 0.0, "china": 0.3}
# (captor, prisoner) -> how likely men of that army were to shoot prisoners out of hand
EXECUTES = {("japan", "*"): 0.45, ("germany", "ussr"): 0.45, ("ussr", "germany"): 0.4, ("germany", "poland"): 0.3,
            ("ussr", "finland"): 0.2, ("finland", "ussr"): 0.15, ("germany", "*"): 0.04, ("ussr", "*"): 0.2,
            ("usa", "japan"): 0.3, ("uk", "japan"): 0.25, ("australia", "japan"): 0.35, ("china", "japan"): 0.4,
            ("hungary", "ussr"): 0.2, ("romania", "ussr"): 0.2, ("usa", "germany"): 0.03, ("uk", "germany"): 0.02}
# how closely superiors watch and how quickly they come down on you
STRICT = {"germany": 1.25, "ussr": 1.35, "japan": 1.45, "italy": 0.9, "usa": 1.0, "uk": 1.05, "france": 1.0,
          "poland": 1.0, "finland": 0.9, "hungary": 1.1, "romania": 1.15, "china": 1.1, "canada": 1.0,
          "australia": 0.85, "newzealand": 0.9, "india": 1.1}

TASK_TEXT = {"help": "See to him! Patch him up!", "ammo": "Get that ammo over to him!", "gun": "Get on that gun!",
             "down": "Get down, you idiot!", "come": "Get back here! On me!", "fire": "Fire, damn you! Put rounds on them!",
             "dig": "Get digging! I want a hole!", "runner": "Take this to him - run!",
             "fetch": "Go back to the dump and get us ammo!", "scout": "Go and have a look up there. Quietly.",
             "escort": "Take the prisoners back to the rear.",
             "track": "Give that tank crew a hand with the track!", "shells": "Get some shells up to that tank!"}
TASK_PHRASE = {"help": "t_help", "ammo": "t_ammo", "gun": "t_gun", "down": "t_down", "come": "t_come",
               "fire": "t_fire", "dig": "t_dig", "runner": "t_runner", "fetch": "t_fetch", "scout": "t_scout",
               "escort": "t_escort", "track": "t_help", "shells": "t_fetch"}
DEADLINE = {"help": 45, "ammo": 60, "gun": 60, "down": 12, "come": 50, "fire": 30, "dig": 500, "runner": 400,
            "fetch": 700, "scout": 300, "escort": 900, "track": 2400, "shells": 1500}
REWARD = {"help": 5, "ammo": 4, "gun": 4, "down": 1, "come": 1, "fire": 2, "dig": 2, "runner": 4, "fetch": 4,
          "scout": 4, "escort": 5, "track": 4, "shells": 5}
EN = ("usa", "uk", "canada", "australia", "newzealand", "india")


def standing_word(rep: float) -> str:
    if rep >= 60:
        return "Your officers trust you with anything."
    if rep >= 30:
        return "You're thought of as a good soldier."
    if rep >= 5:
        return "You do what you're told."
    if rep > -15:
        return "Nobody's sure about you yet."
    if rep > -40:
        return "Your sergeant's got his eye on you."
    if rep > -70:
        return "You're in serious trouble."
    return "They'd shoot you as soon as look at you."


MAX_TASKS = 3                    # orders outstanding at once (from different men, as a rule)


class Duty:
    def __init__(self):
        self.rep = 0.0
        self.tasks = []                # the orders you've been given and not yet carried out (orders.py shows them)
        self.strikes = 0
        self.next_task = 60
        self.done = 0
        self.failed = 0
        self.good = {"patched": 0, "rescue": 0, "ammo": 0, "prisoner": 0, "delivered": 0}
        self.ff_accidents = 0
        self.ff_incidents = 0
        self.murders = 0
        self.pow_shot = 0
        self.arrest = None          # dict(turn, by) while you're being told to drop your weapon
        self.disgraced = False
        self.desert_warn = 0        # warnings for running from the fight
        self.last_desert = -999
        self.neglect = {}           # comrade id -> checks he's bled next to you

    # ------------------------------------------------------------ the orders outstanding
    def _tasks(self) -> list:
        t = self.__dict__.get("tasks")
        if t is None:                  # (a save from when there was only ever one)
            old = self.__dict__.pop("task", None)
            t = self.__dict__["tasks"] = [old] if old else []
        return t

    @property
    def task(self):
        """The order you're getting on with: the one you chose (the orders book), else the most pressing."""
        ts = self._tasks()
        if not ts:
            return None
        f = self.__dict__.get("focus")
        for t in ts:
            if t.get("uid") == f:
                return t
        return min(ts, key=lambda t: t["deadline"])

    @task.setter
    def task(self, v):
        ts = self._tasks()
        ts.clear()
        if v is not None:
            ts.append(v)

    def _drop(self, t):
        ts = self._tasks()
        if t in ts:
            ts.remove(t)

    # ------------------------------------------------------------ who's in charge of you
    def superiors(self, game):
        p = game.player
        out = []
        sq = p.squad
        if sq is not None and sq.leader is not None and sq.leader is not p and sq.leader.active and \
                sq.leader.rank > p.rank:
            out.append(sq.leader)
        f = getattr(sq, "formation", None) if sq is not None else None
        while f is not None:
            c = f.commander
            if c is not None and c is not p and c.active and c.rank > p.rank and c not in out:
                out.append(c)
            f = f.parent
        for a in game.actors:
            if a.side == p.side and a.active and a.rank >= 8 and a.rank > p.rank and a not in out and \
                    max(abs(a.x - p.x), abs(a.y - p.y)) <= 14:
                out.append(a)
        return out

    def watching(self, game, sup) -> bool:
        p = game.player
        d = max(abs(sup.x - p.x), abs(sup.y - p.y))
        if d <= game.command.voice_range(game):
            return True
        return d <= 30 and game.map.visible[sup.x, sup.y]

    def watcher(self, game):
        ws = [s for s in self.superiors(game) if self.watching(game, s)]
        if not ws:
            return None
        p = game.player
        return min(ws, key=lambda s: max(abs(s.x - p.x), abs(s.y - p.y)))

    # ------------------------------------------------------------ speaking
    def _say(self, game, sup, key, english):
        """He shouts it (in his language); you read it in the orders panel."""
        spoken = phrase(game.rng, sup.nation, key) if lang(sup.nation) != "en" else english
        sup.say(spoken, game.turn, 3)
        game.msg(f"{sup.rank_short} {sup.last_name}: '{game.player.last_name}! {english}'", "shout")

    # ------------------------------------------------------------ the turn
    def update(self, game):
        p = game.player
        if p is None or not p.alive or p.state != "ok":
            return
        t = game.turn
        if self.arrest is not None:
            self._arrest_check(game)
        self._desertion(game)
        for task in list(self._tasks()):
            if task in self._tasks():
                self._check_task(game, task)
        if len(self._tasks()) < MAX_TASKS and p.body.conscious and not p.downed and p.vehicle is None and \
                t >= self.next_task and not getattr(game, "renegade", False):
            self._maybe_task(game)
        self._neglect(game)

    # ------------------------------------------------------------ personal orders
    def give(self, game, kind, sup, target=None, **data):
        ts = self._tasks()
        if any(t["kind"] == kind for t in ts) or len(ts) >= MAX_TASKS:
            return                     # (he's already told you; or you've enough on)
        uid = self.__dict__.get("_uid", 0) + 1
        self._uid = uid
        ts.append(dict(kind=kind, by=sup.id, by_name=f"{sup.rank_short} {sup.last_name}", target=target,
                       by_role=sup.role_name, by_nation=sup.nation, uid=uid,
                       issued=game.turn, deadline=game.turn + int(DEADLINE[kind] / STRICT.get(sup.nation, 1.0)),
                       nagged=False, **data))
        self._say(game, sup, TASK_PHRASE[kind], TASK_TEXT[kind])
        game.update_orders(force=True)

    def task_text(self, game):
        t = self.task
        if t is None:
            return None
        return f"{t['by_name']}: '{TASK_TEXT[t['kind']]}'"

    def task_point(self, game, t=None):
        t = t or self.task
        if t is None:
            return None
        tg = t.get("target")
        if isinstance(tg, tuple):
            return tg
        if tg is not None:
            a = self._actor(game, tg)
            if a is not None:
                return a.x, a.y
        return None

    def _actor(self, game, aid):
        for a in game.actors:
            if a.id == aid:
                return a
        return None

    def _maybe_task(self, game):
        p = game.player
        rng = game.rng
        sup = self.watcher(game)
        if sup is None:
            self.next_task = game.turn + 20
            return
        strict = STRICT.get(sup.nation, 1.0)
        m = game.map
        # 1. standing up in the open under fire
        if p.stance == 0 and p.suppression > 25 and m.pos_cover[p.x, p.y] < 20:
            return self.give(game, "down", sup)
        # 2. a man bleeding beside you and no medic
        w = self._bleeder(game, 8)
        if w is not None and self._has_dressing(p):
            return self.give(game, "help", sup, w.id)
        # 3. a gunner out of ammunition, and you carry his calibre
        o = self._dry_gunner(game)
        if o is not None:
            return self.give(game, "ammo", sup, o.id)
        # 4. a crew-served weapon lying in the mud
        g = self._orphan_gun(game)
        if g is not None:
            return self.give(game, "gun", sup, g[0], item=g[1])
        # 4b. a tank that's thrown a track, or run out of shells, and you standing about
        vt = self._vehicle_needing(game)
        if vt is not None:
            kind, v = vt
            return self.give(game, kind, sup, (v.x, v.y), vid=v.id,
                             base=v.ai.get("handed_by_player", 0))
        # 5. you haven't fired a shot and they're right there
        c = self._idle_target(game)
        if c is not None:
            return self.give(game, "fire", sup, c)
        sq = p.squad
        quiet = sq is None or game.turn - sq.last_contact > 90
        # 6. straying from your leader
        if sq is not None and sq.leader is sup and max(abs(sup.x - p.x), abs(sup.y - p.y)) > 12:
            return self.give(game, "come", sup, sup.id)
        if rng.random() > 0.35 * strict:
            self.next_task = game.turn + rng.randint(40, 120)
            return
        # 7. digging in when the squad holds
        if quiet and sq is not None and sq.state == "hold" and p.has_tool("shovel") and m.pos_cover[p.x, p.y] < 45:
            return self.give(game, "dig", sup)
        # 8. the squad's short of ammunition: fetch some
        if quiet and sq is not None:
            from .command import low_on_ammo, nearest_ammo
            if low_on_ammo(sq):
                q = nearest_ammo(game, sq, 70)
                if q is not None:
                    return self.give(game, "fetch", sup, q)
        # 9. a message for another squad
        if quiet and rng.random() < 0.3:
            other = self._runner_target(game, sup)
            if other is not None:
                return self.give(game, "runner", sup, other.id)
        # 10. a look over the next hedge
        if quiet and rng.random() < 0.25:
            ec = game.brains[p.side].enemy_center
            if ec is not None:
                dx, dy = ec[0] - p.x, ec[1] - p.y
                d = math.hypot(dx, dy) or 1
                tx, ty = int(p.x + dx / d * 12), int(p.y + dy / d * 12)
                if m.in_bounds(tx, ty) and m.walk[tx, ty]:
                    return self.give(game, "scout", sup, (tx, ty), leg="out")
        self.next_task = game.turn + rng.randint(60, 180)

    def _check_task(self, game, t):
        p = game.player
        k = t["kind"]
        tgt = t.get("target")
        m = game.map
        done = False
        if k == "down":
            done = p.stance == 2 or m.pos_cover[p.x, p.y] >= 40
        elif k == "help":
            a = self._actor(game, tgt)
            if a is None or not a.alive:
                if t.get("tried"):
                    done = True
                else:
                    return self._fail(game, t, "He died while you stood there.")
            else:
                done = a.body.bleed_rate() < 0.1 or a.ai.get("carried_by") is not None or a.ai.get("at_aid") is not None
        elif k == "ammo":
            done = t.get("given", False)
            a = self._actor(game, tgt)
            if a is None or not a.alive:
                self._drop(t)
                return
        elif k in ("track", "shells"):
            from . import maintenance as MT
            v = next((v for v in game.vehicles if v.id == t.get("vid")), None)
            if v is None or v.dead or v.abandoned:
                self._drop(t)
                return
            if k == "track":
                if v.near(p.x, p.y) <= 1 and p.vehicle is None:
                    p.ai["helping"] = v.id               # beside it, you're working
                done = "track" not in MT.repairs(v)
            else:
                done = v.ai.get("handed_by_player", 0) >= t.get("base", 0) + MT.CRATE_ROUNDS // 2 or \
                    MT.shells_short(v) <= 0
        elif k == "gun":
            w = p.weapon
            done = w is not None and w is t.get("item")
            if not done and t.get("item") is not None and t["item"] not in [i for its in m.items.values() for i in its] \
                    and t["item"] not in p.inv:
                self._drop(t)             # somebody else picked it up
                return
        elif k == "fire":
            last = p.ai.get("last_shot")
            done = last is not None and last[2] >= t["issued"] and \
                max(abs(last[0] - tgt[0]), abs(last[1] - tgt[1])) <= 7
        elif k == "come":
            a = self._actor(game, tgt)
            done = a is None or max(abs(a.x - p.x), abs(a.y - p.y)) <= 5
        elif k == "dig":
            done = m.pos_cover[p.x, p.y] >= 45
        elif k == "runner":
            a = self._actor(game, tgt)
            if a is None or not a.alive:
                self._drop(t)
                return
            done = max(abs(a.x - p.x), abs(a.y - p.y)) <= 1
            if done:
                a.say("Got it. Tell him we'll hold." if a.nation in EN else "", game.turn, tone="talk")
        elif k == "fetch":
            sup = self._actor(game, t["by"])
            got = p.ai.get("resupplied_turn", -1) >= t["issued"]
            done = got and (sup is None or max(abs(sup.x - p.x), abs(sup.y - p.y)) <= 6)
        elif k == "scout":
            if t.get("leg") == "out" and max(abs(tgt[0] - p.x), abs(tgt[1] - p.y)) <= 2:
                t["leg"] = "back"
                game.msg("You've had your look. Now get back and tell him.", "info")
            sup = self._actor(game, t["by"])
            done = t.get("leg") == "back" and (sup is None or max(abs(sup.x - p.x), abs(sup.y - p.y)) <= 4)
        elif k == "escort":
            done = self.good["delivered"] >= t.get("need", 1)
        if done:
            return self._complete(game, t)
        if game.turn > t["deadline"]:
            if not t["nagged"]:
                t["nagged"] = True
                t["deadline"] = game.turn + max(10, DEADLINE[k] // 2)
                sup = self._actor(game, t["by"])
                if sup is not None and sup.active and self.watching(game, sup):
                    self._say(game, sup, "rebuke", "I gave you an order!")
                    self.rep -= 1
                return
            return self._fail(game, t)

    def _complete(self, game, t):
        self._drop(t)
        self.done += 1
        if self.done % 5 == 0:
            from .orders import reward_record
            reward_record(game, f"commended by {t['by_name']} for orders carried out in the field.")
            game.command.merit += 1
        r = REWARD.get(t["kind"], 2)
        self.rep = min(100.0, self.rep + r)
        game.command.merit += r * 0.3
        self.strikes = max(0, self.strikes - 1) if self.done % 3 == 0 else self.strikes
        sup = self._actor(game, t["by"])
        if sup is not None and sup.active and self.watching(game, sup) and t["kind"] not in ("down",):
            spoken = phrase(game.rng, sup.nation, "praise")
            if spoken == "Good man." and getattr(game.player, "female", False):
                spoken = "Well done."
            sup.say(spoken, game.turn, 2)
            game.msg(f"{sup.rank_short} {sup.last_name}: '{spoken if lang(sup.nation) == 'en' else 'Well done.'}'",
                     "good")
        self.next_task = game.turn + game.rng.randint(60, 160)
        game.update_orders(force=True)

    def _fail(self, game, t, why=None):
        self._drop(t)
        self.failed += 1
        self.strikes += 1
        self.rep -= 4 * STRICT.get(game.player.nation, 1.0)
        game.msg(why or f"You didn't do what {t['by_name']} told you. He'll remember.", "warn")
        self._escalate(game, t["by_name"])
        self.next_task = game.turn + game.rng.randint(40, 100)
        game.update_orders(force=True)

    def _escalate(self, game, who):
        from .orders import punish
        p = game.player
        if self.strikes < 3:
            words = punish(game, 0, who)
            game.msg(f"{who}: {words}. (You'll serve any extra duty at the next base.)", "warn")
        elif self.strikes == 3:
            words = punish(game, 1, who)
            game.msg(f"{who} puts you on report: {words}.", "warn")
        elif self.strikes == 4:
            words = punish(game, 1, who)
            game.msg(f"{who} puts you on report again: {words}. Once more and it's a court-martial.", "warn")
        elif self.strikes >= 5:
            if p.nation == "ussr" and p.rank <= 1 and not self.__dict__.get("penal"):
                self.penal = True
                self.penal_from = p.unit
                p.unit = "a penal company (shtrafnaya rota)"
                rec = game.command.__dict__.setdefault("record", [])
                rec.append(f"{game.datetime_str()}: sentenced to a penal company - to atone in blood.")
                game.msg("The tribunal sits for ten minutes. You're sent to a penal company, to atone in blood.",
                         "death")
                self.strikes = 2
                return
            self.strikes = 2
            if p.rank > 0:
                from .data.ranks import rank_title
                self.__dict__.setdefault("busted_from", p.rank)       # (valour can give it back: valour())
                p.rank -= 1
                game.msg(f"You're busted down to {rank_title(p.nation, p.rank, False)}.", "death")
                game.command.merit_at_promotion = game.command.merit
                if game.command.billet_squad is not None and game.command.billet_squad.leader is p:
                    game.command.billet_squad = None
            else:
                game.msg("You're given every filthy job going, and put on point for the rest of the war.", "warn")

    # ------------------------------------------------------------ running away
    def _desertion(self, game):
        """Leaving your post in the middle of a fight, in front of the men who command you."""
        p = game.player
        sq = p.squad
        if sq is None or p.vehicle is not None or sq.player_led or game.turn - sq.last_contact > 60:
            return
        if p.ai.get("carried_by") is not None or p.carrying is not None or self._tasks():
            return
        brain = game.brains[p.side]
        if brain.home is None or sq.leader is None or not sq.leader.active:
            return
        # heading for the rear, far from your squad, with your squad still fighting
        far = max(abs(sq.leader.x - p.x), abs(sq.leader.y - p.y)) > 18
        rearward = int(brain.home[p.x, p.y]) < int(brain.home[sq.leader.x, sq.leader.y]) - 10 * 4
        if not (far and rearward) or p.downed or game.medic_bound(p):
            return
        sup = self.watcher(game)
        if sup is None or game.turn - self.last_desert < 20:
            return
        self.last_desert = game.turn
        self.desert_warn += 1
        n = self.desert_warn
        strict = STRICT.get(sup.nation, 1.0)
        harsh = sup.nation in ("ussr", "japan") or (sup.nation == "germany" and game.year >= 1944)
        en = lang(sup.nation) == "en"
        if n == 1:
            self._say(game, sup, "t_come", "Where the hell do you think you're going? Get back here!")
            self.rep -= 3
        elif n == 2:
            text = "Turn around or I'll shoot you myself!" if harsh else "One more step and I'll have you court-martialled!"
            sup.say(text if en else phrase(game.rng, sup.nation, "rebuke"), game.turn, 3)
            game.msg(f"{sup.rank_short} {sup.last_name}: '{text}'", "warn")
            self.rep -= 8
            self.strikes += 1
        elif n >= 3:
            if harsh and game.rng.random() < min(0.9, 0.35 * strict * (n - 2)):
                game.msg(f"{sup.full_name} raises his weapon at you. He means it.", "death")
                w = sup.weapon
                if w is not None and w.t.kind == "gun" and w.loaded > 0:
                    from .actions import fire
                    fire(game, sup, p.x, p.y, p)
                self.rep -= 10
            else:
                self.strikes = max(self.strikes, 5)
                self._escalate(game, sup.full_name)
                self.rep -= 10
                game.__dict__["wanted"] = "desertion"         # the MPs at any base will pick you up (base.py)
                game.msg("You're marked as a deserter. The military police will be waiting.", "warn")

    # ------------------------------------------------------------ nothing succeeds like success
    def valour(self, game, weight, why):
        """Good work in the fight: it's remembered - and it wipes out what you did wrong before.  No company
        commander keeps a charge sheet on the man who took the machine gun: every three points of it takes a
        strike off, and the extra duty, the fine and the stopped leave that came with them; a big enough deed
        gives back the stripe you lost; a Red Army penal soldier who fights well, or bleeds, is rehabilitated
        ('atoned in blood')."""
        p = game.player
        self.valour_pts = self.__dict__.get("valour_pts", 0.0) + weight
        if self.__dict__.get("busted_from") is not None:
            self.since_bust = self.__dict__.get("since_bust", 0.0) + weight
        self.rep = min(100.0, self.rep + weight)
        from . import base as BASE
        st = BASE._state(game)
        before = self.strikes
        lifted = False
        while self.valour_pts >= 3 and (self.strikes > 0 or st.get("fatigues") or st.get("fine_days")):
            self.valour_pts -= 3
            if self.strikes > 0:
                self.strikes -= 1
            if st.get("fatigues"):
                st["fatigues"] = max(0, st["fatigues"] - 3)
                lifted = True
            if st.get("fine_days"):
                st["fine_days"] = max(0, st["fine_days"] - 7)
                lifted = True
        if self.strikes == 0 and before > 0:
            st["leave"] = min(st.get("leave", -10 ** 9), game.turn - 8 * 86400)     # the pass you were stopped
        rec = game.command.__dict__.setdefault("record", [])
        if before >= 3 > self.strikes:
            rec.append(f"{game.datetime_str()}: the charge against you dropped - {why}.")
            game.msg(f"Word comes down that the charge against you has been torn up. {why[0].upper() + why[1:]} "
                     f"saw to that.", "good")
        elif self.strikes < before or lifted:
            game.msg("Nobody mentions the extra duty any more." if lifted else
                     "Whatever they held against you, they've stopped holding it.", "good")
            if self.strikes == 0:
                rec.append(f"{game.datetime_str()}: slate wiped clean - {why}.")
        if (weight >= 4 or self.__dict__.get("since_bust", 0.0) >= 8) and self.__dict__.get("busted_from") is not None \
                and p.rank < self.busted_from:
            self.since_bust = 0.0
            from .data.ranks import rank_title
            p.rank = self.busted_from
            self.__dict__.pop("busted_from", None)
            game.command.merit_at_promotion = game.command.merit
            rec.append(f"{game.datetime_str()}: rank restored - {why}.")
            game.msg(f"You're given your stripes back: {rank_title(p.nation, p.rank, False)} again.", "good")
        if self.__dict__.get("penal") and (weight >= 4 or why.startswith("wounded")):
            self.penal = False
            p.unit = self.__dict__.pop("penal_from", p.unit)
            self.strikes = 0
            rec.append(f"{game.datetime_str()}: rehabilitated from the penal company - atoned in blood.")
            game.msg("You've atoned in blood. The tribunal's sentence is lifted and you go back to your old unit.",
                     "good")

    # ------------------------------------------------------------ what nobody has to order
    def good_deed(self, game, kind, who=None):
        self.good[kind] = self.good.get(kind, 0) + 1
        gain = {"patched": 3, "rescue": 6, "ammo": 2, "prisoner": 2, "delivered": 3}.get(kind, 1)
        self.rep = min(100.0, self.rep + gain)
        under_fire = game.player.suppression > 15 or game.turn - game.player.hit_turn < 30 or \
            bool(game.seen_enemies(15)) if hasattr(game, "seen_enemies") else False
        v = {"rescue": 3.0 if under_fire else 1.0, "patched": 1.5 if under_fire else 0.3, "prisoner": 1.0,
             "delivered": 0.5}.get(kind, 0.0)
        if v:
            self.valour(game, v, {"rescue": "bringing a wounded man in under fire" if under_fire else
                                  "bringing a wounded man in", "patched": "seeing to the wounded under fire",
                                  "prisoner": "taking prisoners", "delivered": "bringing prisoners in"}[kind])
        for t in self._tasks():
            if who is not None and t.get("target") == who.id:
                if t["kind"] == "help":
                    t["tried"] = True
                if t["kind"] == "ammo":
                    t["given"] = True
        if who is not None and who.alive:
            who.morale = min(100.0, who.morale + 8)

    def _neglect(self, game):
        """A comrade bleeding out beside you while you do nothing."""
        p = game.player
        if p.downed or not self._has_dressing(p) or p.vehicle is not None:
            self.neglect = {}
            return
        busy = p.fired_turn >= game.turn - 5 or bool(game.seen_enemies(8))
        seen = {}
        for a in game.actors:
            if a.side != p.side or a is p or not a.alive or a.vehicle is not None:
                continue
            if max(abs(a.x - p.x), abs(a.y - p.y)) > 2 or a.body.bleed_rate() < 1.5:
                continue
            if any(o.role in ("medic", "surgeon") and o.active and max(abs(o.x - a.x), abs(o.y - a.y)) <= 3
                   for o in game.actors if o.side == p.side):
                continue
            n = self.neglect.get(a.id, 0) + (0 if busy else 1)
            seen[a.id] = n
            if n == 4:
                sup = self.watcher(game)
                if sup is not None and not any(t["kind"] == "help" for t in self._tasks()):
                    self.rep -= 2
                    self.give(game, "help", sup, a.id)
                elif a.active:
                    a.say("Help me... please..." if a.nation in EN else "", game.turn, tone="scream")
                    self.rep -= 0.5
        self.neglect = seen

    # ------------------------------------------------------------ friendly fire, murder, prisoners
    def _justified(self, game):
        """Were you in a fight - or firing where you were told to?  (A gunner on a fire mission never sees
        what his rounds land on: short rounds and danger-close calls are the observer's, not his.)"""
        p = game.player
        if p.suppression > 20 or p.hit_turn >= game.turn - 20:
            return True
        sup = getattr(game, "support", None)
        if sup is not None and game.map is not None:
            try:
                if sup.fires.player_mission(game) is not None or game.turn - p.ai.get("mission_fired", -999) < 60:
                    return True
            except Exception:
                pass
        w = p.weapon
        if w is not None and w.t.kind == "gun" and w.t.cat == "mortar" and game.turn - p.fired_turn < 60:
            return True
        if any(getattr(e, "alive", True) for e in getattr(p, "visible", [])):
            return True
        brain = game.brains[p.side]
        return bool(brain.nearest_contacts(p.x, p.y, 1, max_age=25)) and \
            any(math.hypot(c.x - p.x, c.y - p.y) < 30 for c in brain.nearest_contacts(p.x, p.y, 1, max_age=25))

    def on_friendly_hit(self, game, victim, killed=False):
        p = game.player
        if victim is p or victim.side != p.side:
            return
        watcher = self.watcher(game)
        if self._justified(game):
            self.ff_accidents += 1
            self.rep -= 2 + (6 if killed else 0)
            who = watcher or next((a for a in game.actors if a.side == p.side and a.active and a is not p and
                                   max(abs(a.x - p.x), abs(a.y - p.y)) < 10), None)
            if who is not None:
                self._say(game, who, "ff_rebuke", "Watch your fire!")
            if self.ff_accidents in (4, 7):
                self.strikes += 1
                game.msg("Word gets around that you're a danger to your own side.", "warn")
                self._escalate(game, watcher.full_name if watcher else "Your sergeant")
            return
        # no enemy in sight, nobody shooting at you: that was no accident
        self.ff_incidents += 1
        self.rep -= 15 + (25 if killed else 0)
        if killed:
            self.murders += 1
        witness = watcher or next((a for a in game.actors if a.side == p.side and a.active and a is not p and
                                   max(abs(a.x - p.x), abs(a.y - p.y)) < 20), None)
        if self.murders >= 2 or (self.murders >= 1 and self.ff_incidents >= 2) or self.ff_incidents >= 4:
            return self.turn_on_player(game, witness)
        if (self.murders or self.ff_incidents >= 2) and witness is not None and self.arrest is None:
            self.arrest = dict(turn=game.turn, by=witness.id)
            self._say(game, witness, "arrest", "Drop your weapon! Drop it NOW!")
            game.msg("(Drop your weapon - d - or they will shoot you.)", "system")
            return
        if witness is not None:
            self._say(game, witness, "ff_rebuke", "What the hell are you doing?!")

    def _arrest_check(self, game):
        p = game.player
        w = p.weapon
        armed = w is not None and w.t.kind == "gun"
        if not armed:
            self.arrest = None
            self.disgraced = True
            self.rep = min(self.rep, -60)
            if p.rank > 0:
                p.rank = 0
            game.msg("They take your weapons and your stripes. You'll face a court-martial when this is over - "
                     "if you live. Until then you carry ammunition and dig latrines.", "death")
            game.command.billet = None
            game.command.billet_squad = None
            game.update_orders(force=True)
            return
        if game.turn - self.arrest["turn"] > 15:
            witness = self._actor(game, self.arrest["by"])
            self.arrest = None
            self.turn_on_player(game, witness)

    def turn_on_player(self, game, witness=None):
        """Your own side has had enough of you."""
        if getattr(game, "renegade", False):
            return
        game.renegade = True
        self.task = None
        p = game.player
        if witness is not None and witness.active:
            witness.say(phrase(game.rng, witness.nation, "murder"), game.turn, 4)
        game.msg("Your own side turns its guns on you.", "death")
        game._enemy_arr = {}
        if p.squad is not None and p.squad.leader is p:
            p.squad.player_led = False
        game.update_orders(force=True)

    def panic_prisoners(self, game, victim):
        """The others saw it.  Some run, some go for a rifle, some beg."""
        from . import actions as A
        from .senses import los_clear
        rng = game.rng
        game.no_quarter[victim.side] += 1
        for a in list(game.actors):
            if a is victim or a.state != "surrendered" or a.side != victim.side or not a.alive:
                continue
            if max(abs(a.x - victim.x), abs(a.y - victim.y)) > 15 or not los_clear(game, a.x, a.y, victim.x, victim.y):
                continue
            r = rng.random()
            if r < 0.4:
                a.state = "ok"
                a.morale = 0.0
                a.suppression = 90.0
                a.ai["routing"] = None
                a.say(game.shout(a, "retreat"), game.turn, 3)
            elif r < 0.7:
                guns = [it for it in game.map.items_at(a.x, a.y) if it.t.kind == "gun"]
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        guns += [it for it in game.map.items_at(a.x + dx, a.y + dy) if it.t.kind == "gun"]
                a.state = "ok"
                a.morale = 100.0
                a.suppression = 0.0
                a.ai["desperate"] = game.turn
                if guns:
                    g = guns[0]
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            if g in game.map.items_at(a.x + dx, a.y + dy):
                                game.map.remove_item(a.x + dx, a.y + dy, g)
                    if a.add_item(g) is not None:
                        a.wield(g)
                a.say(game.shout(a, "attack"), game.turn, 3)
            else:
                a.say(game.shout(a, "surrender"), game.turn, 4)
                a.stance = 2

    def on_prisoner_shot(self, game, victim):
        p = game.player
        cares = CARES_POW.get(p.nation, 0.5)
        sup = self.watcher(game)
        self.pow_shot += 1
        self.panic_prisoners(game, victim)
        if sup is not None and game.rng.random() < cares:
            self.rep -= 20
            self.strikes += 2
            game.command.merit -= 6
            if lang(sup.nation) == "en" or phrase(game.rng, sup.nation, "pow_shot"):
                self._say(game, sup, "pow_shot", "Christ - he'd surrendered!")
            game.msg(f"{sup.full_name} saw that. There'll be an inquiry.", "warn")
            self._escalate(game, sup.full_name)
            return
        if cares >= 0.5:
            wit = next((a for a in game.actors if a.side == p.side and a.active and a is not p and
                        max(abs(a.x - p.x), abs(a.y - p.y)) < 10), None)
            if wit is not None:
                self.rep -= 5
                if wit.nation in EN:
                    wit.say("What the hell did you do that for?", game.turn, 3)

    def on_surrender_near(self, game, prisoner):
        """An enemy threw down his weapon in front of you: he's your prisoner."""
        p = game.player
        if prisoner.side == p.side or not game.map.visible[prisoner.x, prisoner.y]:
            return
        if max(abs(prisoner.x - p.x), abs(prisoner.y - p.y)) > 10:
            return
        prisoner.ai["captor"] = p.id
        self.good["prisoner"] += 1
        self.rep += 2
        game.command.merit += 1
        from .constants import cap as _cap
        prisoner.ai.setdefault("pw_order", "follow")
        game.msg(f"{_cap(game.name_of(prisoner))} is your prisoner. Search him, and bring him back to our lines. "
                 f"(he'll follow you; right-click him for more)", "good")
        sup = self.watcher(game)
        if sup is not None and len(self._tasks()) < MAX_TASKS and game.rng.random() < 0.5:
            self.give(game, "escort", sup, need=self.good["delivered"] + 1)

    def on_prisoner_delivered(self, game, prisoner):
        self.good["delivered"] += 1
        self.rep += 3
        game.command.merit += 2
        game.msg("A prisoner you took is handed over to the military police behind the lines.", "good")
        # interrogation: his unit, and who commands it
        h = game.__dict__.get("hierarchy")
        if h is not None and getattr(prisoner, "unit", None) and game.rng.random() < 0.7:
            if h.learn_enemy(game, unit_text=prisoner.unit):
                game.msg(f"Interrogated, he names his division and its commanders ({prisoner.unit.split(',')[-1].strip()}).",
                         "radio")

    # ------------------------------------------------------------ helpers for the checks
    def _has_dressing(self, a):
        return a.medical("bandage") is not None or a.medical("tourniquet") is not None

    def _bleeder(self, game, radius):
        p = game.player
        best = None
        for a in game.actors:
            if a.side != p.side or a is p or not a.alive or a.vehicle is not None or a.state != "ok":
                continue
            if max(abs(a.x - p.x), abs(a.y - p.y)) > radius or a.body.bleed_rate() < 0.6:
                continue
            if a.ai.get("carried_by") is not None:
                continue
            if any(o.role in ("medic", "surgeon") and o.active and max(abs(o.x - a.x), abs(o.y - a.y)) <= 8
                   for o in game.actors if o.side == p.side):
                continue
            if best is None or a.body.bleed_rate() > best.body.bleed_rate():
                best = a
        return best

    def _dry_gunner(self, game):
        from .ammo import sources, spare_rounds
        p = game.player
        for a in game.actors:
            if a.side != p.side or a is p or not a.active or a.vehicle is not None:
                continue
            w = a.weapon
            if w is None or w.t.kind != "gun" or not w.t.cal or w.t.cat in ("at_disposable", "flamer"):
                continue
            if max(abs(a.x - p.x), abs(a.y - p.y)) > 10:
                continue
            if w.loaded > w.t.mag // 2 or spare_rounds(a, w) >= w.t.mag:
                continue
            if sources(p, w):
                return a
        return None

    def _vehicle_needing(self, game):
        """A friendly vehicle close by with a thrown track, or short of shells when there's somewhere to get
        them: ('track'|'shells', vehicle) or None."""
        from . import maintenance as MT
        p = game.player
        if p.vehicle is not None or p.carrying is not None:
            return None
        best = None
        for v in game.vehicles:
            if v.side != p.side or v.dead or v.abandoned or v is p.vehicle:
                continue
            d = abs(v.x - p.x) + abs(v.y - p.y)
            if d > 18 or not MT.quiet(game, v):
                continue
            if "track" in MT.repairs(v):
                return "track", v
            if MT.shells_short(v) > max(6, sum(MT.full_load(v)[:2]) * 0.25):
                trucks = [t for t in game.vehicles if t.side == v.side and MT.is_supply_truck(t)
                          and abs(t.x - p.x) + abs(t.y - p.y) < 40]
                if trucks and best is None:
                    best = ("shells", v)
        return best

    def _orphan_gun(self, game):
        p = game.player
        w = p.weapon
        if w is not None and w.t.kind == "gun" and w.t.cat in ("lmg", "hmg", "at_launcher", "at_rifle"):
            return None
        if p.role in ("medic", "surgeon", "radioman", "officer") or p.rank >= 3:
            return None
        for (x, y), items in game.map.items.items():
            if max(abs(x - p.x), abs(y - p.y)) > 10:
                continue
            for it in items:
                if it.t.kind == "gun" and it.t.cat in ("lmg", "hmg", "at_launcher") and (it.loaded > 0 or
                                                                                          p.ammo_for(it) is not None):
                    return (x, y), it
        return None

    def _idle_target(self, game):
        p = game.player
        w = p.weapon
        if w is None or w.t.kind != "gun" or w.loaded <= 0 or p.fired_turn >= game.turn - 40:
            return None
        brain = game.brains[p.side]
        for c in brain.nearest_contacts(p.x, p.y, 3, max_age=10):
            d = math.hypot(c.x - p.x, c.y - p.y)
            if d < w.t.rng and game.map.visible[c.x, c.y]:
                return (c.x, c.y)
        return None

    def _runner_target(self, game, sup):
        p = game.player
        f = getattr(p.squad, "formation", None) if p.squad is not None else None
        if f is None:
            return None
        pool = f.parent.live_squads() if f.parent is not None else f.live_squads()
        cands = []
        for sq in pool:
            if sq is p.squad or sq.leader is None or not sq.leader.active or sq.leader.vehicle is not None:
                continue
            d = max(abs(sq.leader.x - p.x), abs(sq.leader.y - p.y))
            if 15 <= d <= 60:
                cands.append(sq.leader)
        return game.rng.choice(cands) if cands else None
