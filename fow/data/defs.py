"""Template classes for data-driven content (items, vehicles, aircraft, artillery)."""
from __future__ import annotations


class Template:
    """A bag of attributes with class-level defaults.

    Templates are immutable by convention and looked up by id so that game
    state only stores ids (keeps saves small and pickle friendly).
    """
    _defaults: dict = {}

    def __init__(self, id: str, name: str, **kw):
        self.id = id
        self.name = name
        for k, v in self._defaults.items():
            setattr(self, k, v() if callable(v) and not isinstance(v, type) else v)
        for k, v in kw.items():
            setattr(self, k, v)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __repr__(self):
        return f"<{type(self).__name__} {self.id}>"


class ItemType(Template):
    _defaults = dict(
        kind="misc", weight=0.2, volume=0.2, glyph="?", color=(200, 200, 200), desc="",
        # availability
        nations=(), years=(1900.0, 1950.0), freq=10, cat="",
        # firearms
        cal=None, mag=0, dmg=0, disp=1.0, rng=30, modes=("single",), burst=1,
        shot_cost=100, burst_cost=100, reload_cost=200, jam=0.002, heat=0, pen=0,
        hands=2, deploy=False, scope=False, pellets=1, sound="gunshot", loud=70,
        feed="mag", bayonet=0,
        # launchers / explosives / grenades
        blast=0, blast_r=0, frags=0, frag_dmg=0, min_rng=0, backblast=False,
        gtype="", fuse=0, dud=0.0, throw=0, smoke=0, fire=0, charge="",
        # melee
        cost=100,
        # stacking
        stack=1,
        # medical / tool / armor
        med="", power=0, tool="", slot="", prot_bullet=0.0, prot_frag=0.0, warmth=0,
        # consumables
        uses=1,
    )

    @property
    def is_gun(self):
        return self.kind == "gun"

    @property
    def stackable(self):
        return self.kind in ("ammo",) or self.stack > 1


class VehicleType(Template):
    _defaults = dict(
        vtype="tank", nations=(), years=(1900.0, 1950.0), armor=(10, 10, 10, 5), hp=100,
        speed=100, offroad=1.5, crush=0, crew=4, seats=0, main=None, mgs=(), ap=0, he=0,
        open_top=False, water="land", glyph="T", freq=10, static=False, aa=False,
        desc="", turret=True, sound="engine", smoke=0,
    )


class GunMount(Template):
    """A vehicle / emplacement main gun."""
    _defaults = dict(
        cal_mm=75, ap_pen=80, ap_dmg=260, he_power=140, he_radius=3, he_frags=40,
        rng=90, disp=0.35, reload_cost=500, flame=False, sound="cannon", aa=False,
    )


class AircraftType(Template):
    _defaults = dict(
        role="fighter", nations=(), years=(1900.0, 1950.0), speed=6, hp=60,
        guns=((10, 45, 10),), bombs=(), rockets=(), glyph="^", sound="aircraft engines",
        siren=False, night=False, freq=10, cannon_pen=0,
    )


class BatteryType(Template):
    _defaults = dict(
        nations=(), years=(1900.0, 1950.0), power=200, radius=4, frags=60, salvo=8,
        spread=6, delay=40, rocket=False, sound="the shriek of incoming shells",
        freq=10, naval=False, cal="105mm",
    )
