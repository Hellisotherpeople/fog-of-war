"""A moving tactical window over persistent, unbounded world coordinates.

Sectors remain strategic accounting and generation cells. They are not tactical
walls: adjacent terrain, soldiers and projectiles share one coordinate frame.
The allocation is rectangular for NumPy/tcod, while activation follows distance
from the player. Changing frames does not advance time or recreate combatants.
"""
from collections import deque
from copy import deepcopy
import math
import random
import numpy as np

from .gamemap import GameMap
from .constants import SIDES

LAYERS = ('t', 'hp', 'var', 'fire', 'smoke', 'blood', 'scorch', 'explored', 'elev')
POINTS = frozenset(('target', 'last_pos', 'last_seen_pos', 'origin', 'point', 'pos', 'destination',
                   'path_goal', 'post', 'rally', 'flank_target', 'staff_rendezvous', 'home',
                   'fired_on', 'throw_smoke', 'df_pos', 'anchor', 'src', 'aim_point', 'aim_target'))
POINTS = POINTS | {'last_shot', 'dig_at', 'run_pos', 'source', 'dz', 'task_pile', 'drop_stash'}
POINT_LISTS = frozenset(('path', 'targets', 'tiles', 'route', 'pts', 'rail_tiles'))


def point(value, dx, dy):
    if isinstance(value, (tuple, list)) and len(value) >= 2 and all(isinstance(v, (int, float, np.number)) for v in value[:2]):
        return type(value)((value[0] + dx, value[1] + dy, *value[2:]))
    return value


def records(value, dx, dy):
    """Translate named tactical fields; sector keys, ids, times and vectors stay put."""
    if isinstance(value, dict):
        if 'x' in value and 'y' in value and isinstance(value['x'], (int, float, np.number)):
            value['x'] += dx
            value['y'] += dy
        for xkey, ykey in (('x0','y0'), ('x1','y1'), ('tx','ty')):
            if isinstance(value.get(xkey), (int, float, np.number)) and ykey in value:
                value[xkey] += dx
                value[ykey] += dy
        for key, val in list(value.items()):
            if key in ('sector', 'from_sector', 'to_sector', 'maps', 'map_reports', 'units', 'destination_sector',
                       'world', '_world_sector', '_world_pos'):
                continue
            if key in POINTS:
                value[key] = point(val, dx, dy)
            elif key in POINT_LISTS and isinstance(val, list):
                value[key] = [point(v, dx, dy) for v in val]
            elif key == 'rect':
                value[key] = point(val, dx, dy)
            elif key == 'spots':
                value[key] = [(kind, x + dx, y + dy) for kind, x, y in val]
            elif key == 'casualty_sightings':
                value[key] = {k: (point(v[0], dx, dy), v[1]) for k, v in val.items()}
            elif key == 'positions' and isinstance(val, dict):
                value[key] = {k: point(v, dx, dy) for k, v in val.items()}
            elif key == 'avoid' and isinstance(val, dict):
                value[key] = {point(k, dx, dy):v for k,v in val.items()}
            elif key in ('mourn', 'errand') and isinstance(val, tuple) and len(val) >= 3:
                value[key] = (val[0], val[1]+dx, val[2]+dy, *val[3:])
            if isinstance(value[key], (dict, list)):
                records(value[key], dx, dy)
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, (dict, list)):
                records(entry, dx, dy)


def entity(e, dx, dy):
    e.x += dx
    e.y += dy
    records(e.ai, dx, dy)
    e.ai.pop('path', None)
    e.ai.pop('prog', None)
    e.ai.pop('_watch_lvl', None)
    if getattr(e, 'aim_target', None) is not None:
        e.aim_target = point(e.aim_target, dx, dy)
    # peek is a direction relative to the soldier, not a point on the map.
    if hasattr(e, 'known'):
        e.known = {key: point(val, dx, dy) for key,val in e.known.items()}


def squad(sq, dx, dy, seen):
    for order in (sq.order, sq.positions_order):
        if order is not None and id(order) not in seen:
            seen.add(id(order))
            order.target = point(order.target, dx, dy)
            # Object identity is captured separately before objective lists change.
    sq.positions = {k: point(v, dx, dy) for k, v in sq.positions.items()}
    sq.flank_target = point(sq.flank_target, dx, dy)
    for key in ('beaten', 'fired_from'):
        if key in sq.__dict__:
            setattr(sq, key, point(getattr(sq, key), dx, dy))
    records(sq.__dict__.get('rep', {}), dx, dy)


def remember_objective(sq, m):
    """An objective belongs to its order, never to a subsequent order for the squad."""
    if sq.order.obj is not None and 0 <= sq.order.obj < len(m.objectives):
        sq.order.world_objective = m.objectives[sq.order.obj]
    # Legacy saves kept this on the squad, where it could outlive the order.
    sq.__dict__.pop('_world_objective', None)


class Landscape:
    WORLD_STATE = ('shells','explosives','pending_explosions','smoke_sources','medevac',
                   'field_order','base_order','mission','intel_pending','_counter_battery','agent')
    def __getstate__(self):
        state = dict(self.__dict__)
        state.pop('_terrain_window', None)  # transient padded storage is never duplicated in saves
        return state

    def __init__(self, game):
        self.w, self.h = game.map_w, game.map_h
        self.radius = max(96, min(640, int(game.setup.get('reality_radius', 240))))
        self.margin = 64
        self.origin = (game.sector.x * self.w, game.sector.y * self.h)
        mission = game.__dict__.get('mission')
        if mission and mission.get('kind') in ('take','hold'):
            mission.setdefault('briefed_objectives', [self.world_pos(*ob.pos) for ob in game.map.objectives])
        self.maps = {(game.sector.x, game.sector.y): game.map}
        game.map._stream_exact = True
        self.actors = {a.id: a for a in game.actors}
        self.vehicles = {v.id: v for v in game.vehicles}
        self.squads = {sq.id: sq for sq in game.squads}
        self.active_actors = set(self.actors)
        self.active_vehicles = set(self.vehicles)
        self.active_squads = set(self.squads)
        self.frame = game.map
        self.center = None
        self._initial = True
        self.reserves = {}
        self.works = []
        self.reserves[(game.sector.x, game.sector.y)] = game.waves
        game.waves = []
        self.refresh(game, force=True)
        game.player_fov()
        self.checkpoint(game)

    def world_pos(self, x, y):
        return self.origin[0] + x, self.origin[1] + y

    def locate_player(self, game, sector):
        if sector is not game.sector:
            game.sector_log.append(f'{game.datetime_str()} - entered {sector.name}')
        game.sector = sector
        sector.visited = True

    def checkpoint(self, game):
        """Retain the land scene before a ship, aircraft or hospital replaces it."""
        self._export(game)
        self.actors.update((a.id,a) for a in game.actors)
        self.vehicles.update((v.id,v) for v in game.vehicles)
        self.squads.update((sq.id,sq) for sq in game.squads)
        self.active_actors = {a.id for a in game.actors}
        self.active_vehicles = {v.id for v in game.vehicles}
        self.active_squads = {sq.id for sq in game.squads}
        self.world_state = {key:game.__dict__[key] for key in self.WORLD_STATE if key in game.__dict__}
        self.world_state_origin = self.origin
        self.world_support = game.support
        self.world_queue = list(game.support.queue)
        self.world_aircraft = list(game.support.aircraft)
        for key,units in self.sector_units(game).items():
            if key in game.strategic.materialized:
                game.strategic.at(*key,create=True).units = units

    def suspend(self, game):
        if self.frame is None:
            return
        if game.map is self.frame:
            self.checkpoint(game)
        elif game.map is None:
            # Narrative scene replacement may clear the map before entering;
            # the land actors and pending events still belong to this frame.
            game.map = self.frame
            self.checkpoint(game)
            game.map = None
        for project in self.frame.__dict__.get('works', []):
            records(project, *self.origin)
            previous = project.get('previous')
            if previous is not None:
                previous.target = point(previous.target, *self.origin)
            if project not in self.works:
                self.works.append(project)
        seen = set()
        for aid in self.active_actors:
            a = self.actors.get(aid)
            if a is None or a is game.player:
                continue
            entity(a,*self.origin)
            a._stream_dormant = True
        for vid in self.active_vehicles:
            v = self.vehicles.get(vid)
            if v is not None:
                entity(v,*self.origin)
                v._stream_dormant = True
        for sid in self.active_squads:
            sq = self.squads.get(sid)
            if sq is not None:
                squad(sq,*self.origin,seen)
                sq.members = [a for a in sq.members if a is not game.player]
        for ob in self.frame.objectives:
            ob._world_pos = self.world_pos(*ob.pos)
            ob.x,ob.y = ob._world_pos
        self.actors.pop(game.player.id,None)
        self.active_actors,self.active_vehicles,self.active_squads = set(),set(),set()
        self.frame = None
        self.__dict__.pop('_terrain_window', None)
        self.center = None
        game.strategic.materialized = set()

    def enter(self, game, sector):
        """Long-distance narrative transfers resume the same land world."""
        self.suspend(game)
        m = self.preload(game,(sector.x,sector.y))
        p = game.player
        game.domain,game.aboard = 'land',None
        game.sector,game.map = sector,m
        _, game.attacker, game.att_edge = game.sector_spec(sector)
        from .strategic import OPP
        game.def_edge = OPP.get(game.att_edge)
        self.origin = (sector.x*self.w,sector.y*self.h)
        for ob in m.objectives:
            world = ob.__dict__.get('_world_pos')
            if world is not None:
                ob.x,ob.y = world[0]-self.origin[0],world[1]-self.origin[1]
        for key in self.WORLD_STATE:
            game.__dict__.pop(key,None)
        for key,value in self.__dict__.get('world_state',{}).items():
            game.__dict__[key] = value
        game.effects,game.sound_marks = [],[]
        if self.__dict__.get('world_support') is not None:
            game.support = self.world_support
            game.support.queue = self.world_queue
            game.support.aircraft = self.world_aircraft
        from .brain import SideBrain
        game.brains = {s:SideBrain(game,s) for s in SIDES}
        old = self.__dict__.get('world_state_origin',self.origin)
        self._shift_game(game,old[0]-self.origin[0],old[1]-self.origin[1])
        walk = np.argwhere(m.walk & (m.water < 2))
        p.x,p.y = (int(v) for v in walk[len(walk)//2]) if len(walk) else (self.w//2,self.h//2)
        p.vehicle,p.squad = None,None
        game.actors,game.vehicles,game.squads = [p],[],[]
        game.waves = []
        for sq in self.squads.values():
            sq.formation = None
        self.frame,self._initial = m,True
        self.refresh(game,force=True)
        game.command.organise(game)
        game.update_orders(force=True)
        game.player_fov()

    def sector_at(self, game, x, y):
        wx, wy = self.world_pos(x, y)
        return game.strategic.at(math.floor(wx / self.w), math.floor(wy / self.h), create=True)

    def local(self, sx, sy, x, y):
        return sx * self.w + x - self.origin[0], sy * self.h + y - self.origin[1]

    def arrival_point(self, game, sector, edge):
        x,y = self.w//2,self.h//2
        if edge == 'N': y = 8
        if edge == 'S': y = self.h-9
        if edge == 'W': x = 8
        if edge == 'E': x = self.w-9
        return self.local(sector.x,sector.y,x,y)

    def waypoint(self, game, x, y):
        """The next walkable leg toward a world point beyond the current buffer."""
        if game.map.in_bounds(x,y):
            return int(x),int(y)
        px,py = game.player.pos
        dx,dy = x-px,y-py
        fractions = [1.]
        for start,delta,size in ((px,dx,game.map.w),(py,dy,game.map.h)):
            if delta:
                fractions.append(((size-17 if delta>0 else 16)-start)/delta)
        fraction = max(0.,min(fractions))
        wx,wy = round(px+dx*fraction),round(py+dy*fraction)
        candidates = [(abs(tx-wx)+abs(ty-wy),tx,ty)
                      for tx in range(max(1,wx-12),min(game.map.w-1,wx+13))
                      for ty in range(max(1,wy-12),min(game.map.h-1,wy+13))
                      if game.map.walk[tx,ty] and game.map.water[tx,ty]<2]
        return min(candidates)[1:] if candidates else (wx,wy)

    def preload(self, game, key):
        import pickle, zlib
        key = tuple(key)
        if key not in self.maps:
            self._generate(game, key)
        elif isinstance(self.maps[key], bytes):
            self.maps[key] = pickle.loads(zlib.decompress(self.maps[key]))
        return self.maps[key]

    def _generate(self, game, key):
        from .game import Game
        from .command import CommandState
        from .brain import SideBrain
        from .spawn import populate
        from .mapgen import generate
        from .support import Support
        sec = game.strategic.at(*key, create=True)
        game.strategic.touch(*key, r=1)
        spec, att, edge = game.sector_spec(sec)
        m = game._load_map(sec) if sec.saved is not None else generate(spec)
        m._stream_exact = True
        self.maps[key] = m
        if not sec.playable:
            return
        ctx = self.context(game, key, m)
        populate(ctx, sec, att, edge)
        from .homefront import populate as civilians
        civilians(ctx)
        ctx.support.fires.populate(ctx)
        ctx.support.fires.link_mortars(ctx)
        if sec.saved is None:
            from .loot import scatter
            scatter(ctx)
        # These troops already exist. Strategic combat must not simulate a
        # second copy of their strength while they are represented as people.
        dx, dy = key[0] * self.w, key[1] * self.h
        seen = set()
        for a in ctx.actors:
            entity(a, dx, dy)
            a._stream_dormant = True
            self.actors[a.id] = a
        for v in ctx.vehicles:
            entity(v, dx, dy)
            v._stream_dormant = True
            self.vehicles[v.id] = v
        for sq in ctx.squads:
            remember_objective(sq, m)
            sq.order.obj = None
            squad(sq, dx, dy, seen)
            self.squads[sq.id] = sq
        self.reserves[key] = ctx.waves

    def context(self, game, key, m):
        from .game import Game
        from .command import CommandState
        from .brain import SideBrain
        from .support import Support
        sec = game.strategic.at(*key, create=True)
        _, att, edge = game.sector_spec(sec)
        # Populate once with the usual force/kit rules in an isolated local frame.
        ctx = Game.__new__(Game)
        ctx.__dict__ = dict(game.__dict__)
        ctx.__dict__.pop('landscape', None)
        ctx.player = None
        ctx.domain, ctx.aboard = 'land', None
        ctx.map, ctx.sector = m, sec
        ctx.attacker, ctx.att_edge = att, edge
        from .strategic import OPP
        ctx.def_edge = OPP.get(edge)
        ctx.rng = random.Random(sec.seed ^ game.seed)
        ctx.actors, ctx.vehicles, ctx.squads = [], [], []
        ctx.soldier_at, ctx.vehicle_at, ctx.peek_at = {}, {}, {}
        ctx._arr_turn, ctx._arr, ctx._enemy_arr = -1, None, {}
        ctx.command = CommandState()
        ctx.messages, ctx.audio_events = deque(maxlen=1), []
        ctx.waves = []
        ctx.first_battle = False
        ctx.brains = {s: SideBrain(ctx, s) for s in SIDES}
        ctx.support = Support(ctx)
        return ctx

    def _export(self, game):
        """Commit terrain damage and items from the moving buffer to generation cells."""
        m, (ox, oy) = game.map, self.origin
        if self._initial:
            return
        for r in m.gen_positions:
            r.setdefault('_world_sector', ((r['x']+ox)//self.w, (r['y']+oy)//self.h))
        for key, cm in list(self.maps.items()):
            if isinstance(cm, bytes):
                continue
            x, y = key[0] * self.w - ox, key[1] * self.h - oy
            x0, y0, x1, y1 = max(0, x), max(0, y), min(m.w, x + self.w), min(m.h, y + self.h)
            if x0 >= x1 or y0 >= y1:
                continue
            dst = (slice(x0 - x, x1 - x), slice(y0 - y, y1 - y))
            src = (slice(x0, x1), slice(y0, y1))
            for name in LAYERS:
                arr = m.__dict__.get(name)
                if arr is None:
                    continue
                if name not in cm.__dict__:
                    cm.__dict__[name] = np.zeros((self.w, self.h), arr.dtype)
                cm.__dict__[name][dst] = arr[src]
            for name in ('items', 'mines'):
                table = cm.__dict__[name]
                for pos in list(table):
                    if x0 <= pos[0] + x < x1 and y0 <= pos[1] + y < y1:
                        del table[pos]
                table.update({(px - x, py - y): v for (px, py), v in m.__dict__[name].items()
                              if x0 <= px < x1 and y0 <= py < y1})
            # Records carry world ownership, so partially visible buildings remain whole.
            recs = [r for r in m.__dict__.get('gen_positions', []) if r.get('_world_sector') == key]
            old = [r for r in cm.__dict__.get('gen_positions', [])
                   if not (x0 <= r['x'] + x < x1 and y0 <= r['y'] + y < y1)]
            for r in recs:
                cp = deepcopy(r)
                records(cp, -x, -y)
                old.append(cp)
            cm.gen_positions = old
            cm.lights = [point(v, -x, -y) for v in m.lights if x0 <= v[0] < x1 and y0 <= v[1] < y1]
            parked = []
            for r in m.parked:
                if x0 <= r['x'] < x1 and y0 <= r['y'] < y1:
                    cp = deepcopy(r)
                    records(cp, -x, -y)
                    parked.append(cp)
            cm.parked = [r for r in cm.__dict__.get('parked', [])
                         if not (x0 <= r['x']+x < x1 and y0 <= r['y']+y < y1)] + parked
            weather = m.__dict__.get('weather_ground')
            if weather:
                old_ground = cm.__dict__.setdefault('weather_ground', dict(wet=0., snow=0., changed={}))
                old_ground.update(wet=weather['wet'], snow=weather['snow'])
                changed = {pos:v for pos,v in old_ground['changed'].items()
                           if not (x0 <= pos[0]+x < x1 and y0 <= pos[1]+y < y1)}
                changed.update({(px-x,py-y):v for (px,py),v in weather['changed'].items()
                                if x0 <= px < x1 and y0 <= py < y1})
                old_ground['changed'] = changed

    def refresh(self, game, force=False):
        p = game.player
        if p is None or game.domain != 'land' or game.map is not self.frame:
            return (0, 0)
        wx, wy = self.world_pos(p.x, p.y)
        center = (wx, wy)
        if not force and self.center is not None and max(abs(wx-self.center[0]), abs(wy-self.center[1])) < 24:
            self.locate_player(game,self.sector_at(game, p.x, p.y))
            return (0, 0)
        self._export(game)
        old_origin = self.origin
        for project in game.map.__dict__.get('works', []):
            records(project, *old_origin)
            previous = project.get('previous')
            if previous is not None:
                previous.target = point(previous.target, *old_origin)
            if project not in self.works:
                self.works.append(project)
        # Preserve target objects before rebuilding the index used by Dijkstra maps.
        for sq in game.squads:
            remember_objective(sq, game.map)
        self.actors.update((a.id, a) for a in game.actors)
        self.vehicles.update((v.id, v) for v in game.vehicles)
        self.squads.update((sq.id, sq) for sq in game.squads)
        seen = set()
        for a in game.actors:
            entity(a, *old_origin)
            a._stream_dormant = True
        for v in game.vehicles:
            entity(v, *old_origin)
            v._stream_dormant = True
        for sq in game.squads:
            squad(sq, *old_origin, seen)
        # Objective objects themselves retain identity as they leave/re-enter the window.
        for ob in game.map.objectives:
            ob.x += old_origin[0]
            ob.y += old_origin[1]
        if self._initial:
            for ob in game.map.objectives:
                ob._world_pos = ob.pos
            # Their canonical map has local objective coordinates only through _world_pos.
        else:
            for ob in game.map.objectives:
                ob._world_pos = ob.pos
        extent = self.radius + self.margin
        # In-flight ordnance keeps its destination simulated until impact.
        # Walking away must never erase the shell which is already in the air.
        for shell in game.shells:
            tx, ty = shell['x']+old_origin[0], shell['y']+old_origin[1]
            extent = max(extent, int(max(abs(tx-wx),abs(ty-wy))+shell['radius']+32))
        self.center, self.origin = center, (center[0] - extent, center[1] - extent)
        ox, oy = self.origin
        size = extent * 2 + 1
        keys = [(sx, sy) for sx in range(ox // self.w, (ox + size - 1) // self.w + 1)
                for sy in range(oy // self.h, (oy + size - 1) // self.h + 1)]
        import pickle, zlib
        for key in keys:
            if key not in self.maps:
                self._generate(game, key)
            elif isinstance(self.maps[key], bytes):
                self.maps[key] = pickle.loads(zlib.decompress(self.maps[key]))
        self.tactical_keys = set(keys)
        game.strategic.materialized = self.tactical_keys
        from .terrain_window import TerrainWindow
        window = self.__dict__.setdefault('_terrain_window', TerrainWindow())
        layers, incoming = window.prepare(game.map, old_origin, self.origin, size, LAYERS)
        m = GameMap(size, size, game.seed, layers=layers, defer_refresh=True)
        m._stream_exact = True
        m.gen_positions, m.parked, m.storeys = [], [], {}
        m.weather_ground = dict(wet=0., snow=0., changed={})
        for key in keys:
            cm = self.maps[key]
            x, y = key[0] * self.w - ox, key[1] * self.h - oy
            x0, y0, x1, y1 = max(0, x), max(0, y), min(size, x + self.w), min(size, y + self.h)
            for bx0,by0,bx1,by1 in incoming:
                ix0,iy0,ix1,iy1 = max(x0,bx0),max(y0,by0),min(x1,bx1),min(y1,by1)
                if ix0 >= ix1 or iy0 >= iy1:
                    continue
                src = (slice(ix0-x,ix1-x), slice(iy0-y,iy1-y))
                dst = (slice(ix0,ix1), slice(iy0,iy1))
                for name in LAYERS:
                    arr = cm.__dict__.get(name)
                    m.__dict__[name][dst] = arr[src] if arr is not None else 0
            for name in ('items', 'mines'):
                m.__dict__[name].update({(px + x, py + y): v for (px, py), v in cm.__dict__[name].items()
                                        if m.in_bounds(px + x, py + y)})
            for ob in cm.objectives:
                pos = ob.__dict__.get('_world_pos')
                if pos is None:
                    pos = ob._world_pos = (ob.x + key[0] * self.w, ob.y + key[1] * self.h)
                lx, ly = pos[0] - ox, pos[1] - oy
                if m.in_bounds(lx, ly):
                    ob.x, ob.y = lx, ly
                    m.objectives.append(ob)
            for r in cm.__dict__.get('gen_positions', []):
                if m.in_bounds(r['x'] + x, r['y'] + y):
                    cp = deepcopy(r)
                    records(cp, x, y)
                    cp['_world_sector'] = key
                    m.gen_positions.append(cp)
            # Keep intersecting buildings intact; floor identity must not
            # disappear because an outer wall lies beyond the terrain buffer.
            m.buildings.extend(point(b,x,y) for b in cm.buildings
                               if b[0]+x < size and b[1]+y < size and b[0]+x+b[2]>0 and b[1]+y+b[3]>0)
            m.storeys.update({point(b,x,y):n for b,n in cm.__dict__.get('storeys', {}).items()
                             if b[0]+x<size and b[1]+y<size and b[0]+x+b[2]>0 and b[1]+y+b[3]>0})
            weather = cm.__dict__.get('weather_ground')
            if weather:
                m.weather_ground['wet'] = max(m.weather_ground['wet'], weather['wet'])
                m.weather_ground['snow'] = max(m.weather_ground['snow'], weather['snow'])
                m.weather_ground['changed'].update({(px+x,py+y):v for (px,py),v in weather['changed'].items()
                                                   if m.in_bounds(px+x,py+y)})
            for r in cm.__dict__.get('parked', []):
                cp = deepcopy(r)
                records(cp, x, y)
                if m.in_bounds(cp['x'], cp['y']):
                    m.parked.append(cp)
            m.labels.extend((label, px + x, py + y) for label, px, py in cm.labels if m.in_bounds(px + x, py + y))
            m.lights.extend(point(v, x, y) for v in cm.lights if m.in_bounds(v[0] + x, v[1] + y))
        # The active circle extends beyond the visible range. Wounded and engaged
        # men remain active in the buffer, rather than losing treatment mid-action.
        def within(e):
            if not (0 <= e.x - ox < size and 0 <= e.y - oy < size):
                return False
            d2 = (e.x - wx) ** 2 + (e.y - wy) ** 2
            incoming = any(abs(e.x-(s['x']+old_origin[0])) <= s['radius']+32 and
                           abs(e.y-(s['y']+old_origin[1])) <= s['radius']+32 for s in game.shells)
            return incoming or d2 <= self.radius ** 2 or (e.id in self.active_actors and
                (getattr(e, 'suppression', 0) > 5 or getattr(e, 'carrying', None) is not None or
                 (hasattr(e, 'body') and e.body.bleed_rate() > 0) or
                 any(e.ai.get(k) for k in ('patient', 'support_job', 'litter', 'runner', 'personnel_dispatch'))))
        actors = [a for a in self.actors.values() if a is p or within(a)]
        vehicles = [v for v in self.vehicles.values() if v is p.vehicle or within(v)]
        for v in vehicles:
            for a in list(v.crew_actors) + list(v.passengers):
                if a not in actors:
                    actors.append(a)
        for a in list(actors):
            if a.carrying is not None and a.carrying not in actors:
                actors.append(a.carrying)
        active_squads = {a.squad.id for a in actors if a.squad is not None} | {v.squad.id for v in vehicles if v.squad is not None}
        squads = [sq for sq in self.squads.values() if sq.id in active_squads]
        seen = set()
        for a in actors:
            entity(a, -ox, -oy)
            a._stream_dormant = False
            a.visible = []
            a.vis_turn = -999
        for v in vehicles:
            entity(v, -ox, -oy)
            v._stream_dormant = False
        objective_ids = {ob._world_pos: i for i, ob in enumerate(m.objectives)}
        for sq in squads:
            squad(sq, -ox, -oy, seen)
            # Dormant squads from older saves have not yet passed through the
            # active-order migration above. Preserve their original assignment.
            legacy = sq.__dict__.pop('_world_objective', None)
            if sq.order.world_objective is None:
                sq.order.world_objective = legacy
            ob = sq.order.world_objective
            sq.order.obj = objective_ids.get(getattr(ob, '_world_pos', None))
            if sq.order.obj is not None:
                # A compressed sector can restore a new instance of the same
                # persistent objective. Bind to the currently simulated one.
                sq.order.world_objective = m.objectives[sq.order.obj]
            elif ob is not None:
                target_wx, target_wy = ob._world_pos
                sq.order.target = (target_wx-ox, target_wy-oy)
        game.actors, game.vehicles, game.squads = actors, vehicles, squads
        for sq in squads:
            if sq.formation is None:
                game.command.attach_squad(game, sq)
        m.works = []
        for project in self.works:
            px, py = project['point']
            if m.in_bounds(px-ox, py-oy):
                records(project, -ox, -oy)
                previous = project.get('previous')
                if previous is not None:
                    previous.target = point(previous.target, -ox, -oy)
                m.works.append(project)
        self.active_actors = {a.id for a in actors}
        self.active_vehicles = {v.id for v in vehicles}
        self.active_squads = active_squads
        dx, dy = old_origin[0] - ox, old_origin[1] - oy
        self._shift_game(game, dx, dy)
        game.map = self.frame = m
        self.locate_player(game,game.strategic.at(wx // self.w, wy // self.h, create=True))
        game.strategic.touch(game.sector.x, game.sector.y, r=2)
        game.strategic.focus = (wx / self.w, wy / self.h)
        m.name, m.biome, m.climate = game.sector.name, game.sector.biome, game.theatre['climate']
        m.refresh()
        game.soldier_at, game.vehicle_at, game.peek_at = {}, {}, {}
        for a in actors:
            if a.alive and a.vehicle is None and a.ai.get('carried_by') is None:
                game.place_on_map(a)
                if getattr(a,"peek",None) is not None:
                    game.peek_at[(a.x+a.peek[0],a.y+a.peek[1])] = a
        for v in vehicles:
            game.place_vehicle(v)
        game._arr_turn, game._arr, game._enemy_arr = -1, None, {}
        game.lit = None
        game.__dict__.pop('_vis_mat', None)
        from .brain import SideBrain
        old_brains = game.brains
        game.brains = {s: SideBrain(game, s) for s in SIDES}
        for side, b in game.brains.items():
            for c in old_brains[side].contacts.values():
                c.x += dx
                c.y += dy
                if m.in_bounds(c.x, c.y):
                    b.contacts[c.id] = c
            b.update(force=True)
        for key, cm in list(self.maps.items()):
            if key not in keys and not isinstance(cm, bytes):
                self.maps[key] = zlib.compress(pickle.dumps(cm, protocol=5), 1)
        self._initial = False
        return dx, dy

    def _shift_game(self, g, dx, dy):
        for key in ('shells', 'explosives', 'effects', 'medevac',
                    'field_order', 'base_order', 'mission', 'intel_pending', 'identity_check',
                    '_counter_battery', '_cb_warn', 'agent'):
            records(g.__dict__.get(key), dx, dy)
        g.impacts = [point(v, dx, dy) for v in g.__dict__.get('impacts', ())]
        g.pending_explosions = [point(v, dx, dy) for v in g.pending_explosions]
        g.smoke_sources = [point(v, dx, dy) for v in g.smoke_sources]
        g.audio_events = [(kind, weapon, x+dx, y+dy, loud, power, turn, extra)
                          for kind, weapon, x, y, loud, power, turn, extra in g.audio_events]
        for mark in g.sound_marks:
            mark.x += dx
            mark.y += dy
        for job in g.support.queue if g.support else []:
            job.x += dx
            job.y += dy
        for plane in g.support.aircraft if g.support else []:
            plane.x += dx
            plane.y += dy
            plane.tx += dx
            plane.ty += dy
        for battery in g.fires.batteries if g.__dict__.get('fires') else []:
            if battery.mission and battery.mission.get('cb_near'):
                battery.mission['cb_near'] = point(battery.mission['cb_near'],dx,dy)
        if g.__dict__.get('_cb_warn'):
            g._cb_warn = [(turn,point(pos,dx,dy),mortar) for turn,pos,mortar in g._cb_warn]
        records(g.command.pending, dx, dy)
        seen = {id(sq.order) for sq in g.squads} | {id(sq.positions_order) for sq in g.squads}
        for job in g.command.pending:
            order = job.get('order')
            if order is not None and id(order) not in seen:
                seen.add(id(order))
                order.target = point(order.target, dx, dy)
                # Retain the actual location even if objective indices change.
                if order.obj is not None and order.obj < len(g.map.objectives):
                    ob = g.map.objectives[order.obj]
                    wx, wy = ob.__dict__.get('_world_pos', ob.pos)
                    order.target = (wx-self.origin[0], wy-self.origin[1])
                    order.obj = None
        records(g.command.known, dx, dy)
        for task in g.duty._tasks():
            records(task, dx, dy)
        g.__dict__.pop('_support_claims', None)
        g.__dict__.pop('_order_hint', None)

    def exit_point(self, game, edge):
        """A walkable crossing on this sector's real boundary, within this frame."""
        from .strategic import DIRS
        sx, sy = game.sector.x, game.sector.y
        px, py = self.world_pos(*game.player.pos)
        dx, dy = DIRS[edge]
        x = (sx+1)*self.w if dx > 0 else sx*self.w-1 if dx < 0 else px
        y = (sy+1)*self.h if dy > 0 else sy*self.h-1 if dy < 0 else py
        candidates = []
        for d in range(max(self.w, self.h)):
            for sign in (1, -1):
                tx, ty = x+(sign*d if dy else 0), y+(sign*d if dx else 0)
                lx, ly = tx-self.origin[0], ty-self.origin[1]
                if not game.map.in_bounds(lx, ly) or not game.map.in_bounds(lx-dx, ly-dy):
                    continue
                if game.map.walk[lx, ly] and game.map.walk[lx-dx, ly-dy]:
                    candidates.append((d, lx, ly))
            if candidates:
                return min(candidates)[1:]
        return x-self.origin[0], y-self.origin[1]

    def background_tick(self, game):
        """Physiology continues outside tactical activation; no paused bleeding."""
        for a in self.actors.values():
            if a.id in self.active_actors or not a.alive:
                continue
            a.body.update(game.rng)
            a.suppression = max(0, a.suppression-3)
            # No stored action credit when the detailed simulation resumes.
            a.moves = min(a.moves, 100)

    def tick_waves(self, game):
        from .spawn import spawn_units, split_local
        for key, waves in list(self.reserves.items()):
            if not any(w['turn'] <= game.turn for w in waves):
                continue
            m = self.preload(game, key)
            ctx = self.context(game, key, m)
            # Arrival placement must respect the people already on this ground.
            for a in self.actors.values():
                wx,wy = self.world_pos(*a.pos) if a.id in self.active_actors else a.pos
                if a.alive and a.vehicle is None and (wx//self.w,wy//self.h) == key:
                    ctx.soldier_at[(wx-key[0]*self.w,wy-key[1]*self.h)] = a
            for v in self.vehicles.values():
                if v.dead:
                    continue
                for x,y in v.cells():
                    wx,wy = self.world_pos(x,y) if v.id in self.active_vehicles else (x,y)
                    if (wx//self.w,wy//self.h) == key:
                        ctx.vehicle_at[(wx-key[0]*self.w,wy-key[1]*self.h)] = v
            keep = []
            for w in waves:
                if w['turn'] > game.turn:
                    keep.append(w)
                    continue
                now, later = split_local(w['units'], scale=game.troop_scale)
                spawn_units(ctx, w['side'], now, w['edge'], w['side'] == ctx.attacker,
                            [], landing=w.get('landing', False), wave=True)
                if later:
                    keep.append(dict(w, units=later, turn=game.turn+300))
            dx, dy = key[0]*self.w, key[1]*self.h
            seen = set()
            for a in ctx.actors:
                entity(a, dx, dy)
                a._stream_dormant = True
                self.actors[a.id] = a
            for v in ctx.vehicles:
                entity(v, dx, dy)
                v._stream_dormant = True
                self.vehicles[v.id] = v
            for sq in ctx.squads:
                remember_objective(sq, m)
                sq.order.obj = None
                squad(sq, dx, dy, seen)
                self.squads[sq.id] = sq
            self.reserves[key] = keep
            # The next UI boundary rebases the new arrivals, including saved
            # cursor/path coordinates. Never change that frame mid-AI iteration.
            self.center = None

    def sector_units(self, game):
        from collections import Counter
        result = {key: {s: Counter() for s in SIDES} for key in self.maps}
        active = self.active_actors
        for sq in self.squads.values():
            if getattr(sq, 'no_count', False):
                continue
            living = [a for a in sq.members if a.alive and a.state == 'ok' and not a.is_player]
            if not living:
                continue
            a = next((a for a in living if a is sq.leader), living[0])
            wx, wy = self.world_pos(*a.pos) if a.id in active else a.pos
            key = wx//self.w, wy//self.h
            counts = result.setdefault(key, {s: Counter() for s in SIDES})[sq.side]
            if len(living) >= max(2, sq.initial*.3) and not any(v.vt.vtype == 'halftrack' for v in sq.vehicles):
                counts[{'rifle':'inf', 'assault':'inf', 'mg':'mg', 'mortar':'mortar', 'at':'at',
                        'hq':'hq', 'sniper':'sniper', 'engineer':'eng'}.get(sq.kind, 'inf')] += 1
            for v in sq.vehicles:
                if v.dead or v.vt.vtype in ('truck','car','lc','amtrac','aagun','fieldgun'):
                    continue
                counts['atgun' if v.static else 'ht' if v.vt.vtype == 'halftrack' else
                       'td' if v.vt.vtype in ('td','spg') else 'tank'] += 1
        for key, waves in self.reserves.items():
            for w in waves:
                result.setdefault(key, {s: Counter() for s in SIDES})[w['side']].update(w['units'])
        return result

    def squad_key(self, sq):
        a = next((a for a in sq.members if a.alive and a.state == 'ok'), None)
        v = next((v for v in sq.vehicles if not v.dead), None)
        e = a or v
        if e is None:
            return None
        active = self.active_actors if a is not None else self.active_vehicles
        wx,wy = self.world_pos(*e.pos) if e.id in active else e.pos
        return wx//self.w, wy//self.h

    @staticmethod
    def squad_kind(sq):
        v = next((v for v in sq.vehicles if not v.dead), None)
        if v:
            return 'atgun' if v.static else 'ht' if v.vt.vtype == 'halftrack' else 'td' if v.vt.vtype in ('td','spg') else 'tank'
        return {'rifle':'inf','assault':'inf','mg':'mg','mortar':'mortar','at':'at','hq':'hq',
                'sniper':'sniper','engineer':'eng'}.get(sq.kind,'inf')

    def transfer(self, game, src, dst, side, units):
        """Coarse travel outside the bubble retains the actual unit and people."""
        from collections import Counter
        moved = Counter()
        if src not in self.maps or src in game.strategic.materialized:
            return moved
        selected = []
        for sq in list(self.squads.values()):
            if sq.side != side or getattr(sq,'no_count',False) or self.squad_key(sq) != src:
                continue
            kind = self.squad_kind(sq)
            if moved[kind] >= units.get(kind,0):
                continue
            if any(a.id in self.active_actors for a in sq.members):
                continue
            selected.append(sq)
            moved[kind] += 1
        if not selected:
            return moved
        sector = game.strategic.at(*dst,create=True)
        if dst not in self.maps:
            # Strategic arrival already added these units. Generate only the
            # destination's other forces, then move the original people there.
            original = sector.units[side]
            sector.units[side] = original - moved
            try:
                m = self.preload(game,dst)
            finally:
                sector.units[side] = original
        else:
            m = self.preload(game,dst)
        walk = np.argwhere(m.walk & (m.water < 2))
        for sq in selected:
            dx,dy = (dst[0]-src[0])*self.w, (dst[1]-src[1])*self.h
            for a in sq.members:
                entity(a,dx,dy)
            for v in sq.vehicles:
                entity(v,dx,dy)
            squad(sq,dx,dy,set())
            # Coarse travel represents actual elapsed movement. On arrival,
            # retain formation offsets where possible and find dry ground.
            for a in sq.members:
                x,y = int(a.x-dst[0]*self.w),int(a.y-dst[1]*self.h)
                if len(walk) and (not m.in_bounds(x,y) or not m.walk[x,y] or m.water[x,y] >= 2):
                    px,py = walk[np.argmin(((walk-(x,y))**2).sum(axis=1))]
                    entity(a,int(px)-x,int(py)-y)
        self.center = None
        return moved

    def reconcile(self, game):
        """Apply coarse losses/replacements to dormant people, never active combat."""
        from collections import Counter
        existing = self.sector_units(game)
        for key, current in existing.items():
            if key in game.strategic.materialized:
                continue
            sec = game.strategic.at(*key,create=True)
            for side in SIDES:
                losses = current[side] - sec.units[side]
                # Reserves which never entered the tactical battle remain abstract.
                for wave in self.reserves.get(key,[]):
                    if wave['side'] != side:
                        continue
                    removed = wave['units'] & losses
                    wave['units'] -= removed
                    losses -= removed
                for sq in self.squads.values():
                    kind = self.squad_kind(sq)
                    if sq.side != side or getattr(sq,'no_count',False) or losses[kind] <= 0 or self.squad_key(sq) != key:
                        continue
                    if any(a.id in self.active_actors for a in sq.members):
                        continue
                    for a in sq.members:
                        if a.alive:
                            a.body.dead = True
                            a._killed = True
                    for v in sq.vehicles:
                        v.hp = 0
                        v.dead = True
                    losses[kind] -= 1
                added = sec.units[side] - current[side]
                if added:
                    self.reserves.setdefault(key,[]).append(dict(side=side,units=Counter(added),
                        edge=game.theatre['attacker_from'],turn=game.turn+30,landing=False))

    def battle_check(self, game):
        from .strategic import power
        counts = self.sector_units(game)
        for key, units in counts.items():
            if key not in game.strategic.materialized:
                continue
            sec = game.strategic.at(*key, create=True)
            if not sec.playable:
                continue
            present = {side:power(units[side]) > 0 for side in SIDES}
            # Staff, stragglers and the player count as physical occupants too.
            for a in game.actors:
                if a.active and not a.ai.get('civilian') and self.sector_at(game,*a.pos) is sec:
                    present[a.side] = True
            owners = [side for side in SIDES if present[side]]
            if len(owners) == 1 and sec.control != owners[0]:
                game.strategic._capture(sec, owners[0])
                if sec is game.sector:
                    game._sector_won(owners[0])


def ensure(game):
    if game.__dict__.get('domain', 'land') != 'land' or game.map is None or game.player is None:
        return None
    st = game.__dict__.get('landscape')
    if st is not None and st.frame is game.map:
        return st
    if game.map.w != game.map_w or game.map.h != game.map_h or not game.setup.get('seamless', True):
        return None
    game.landscape = Landscape(game)
    return game.landscape


def refresh_play(ps):
    g = ps.game
    st = ensure(g)
    if st is None:
        return
    old = ps.__dict__.get('_land_origin') or st.origin
    st.refresh(g)
    dx, dy = old[0]-st.origin[0], old[1]-st.origin[1]
    ps._land_origin = st.origin
    if dx or dy:
        for key in ('cursor', 'hover', 'travel_dest', 'view_center', 'cam_c', 'cam_target', '_view_pos'):
            value = ps.__dict__.get(key)
            if value is not None:
                ps.__dict__[key] = point(value, dx, dy)
        if ps.travel_path:
            ps.travel_path = [point(v, dx, dy) for v in ps.travel_path]
        ps.travel_blind = {point(v, dx, dy) for v in ps.__dict__.get('travel_blind', ())}
        ps.cam.x0 += dx
        ps.cam.y0 += dy
        g.player_fov()
