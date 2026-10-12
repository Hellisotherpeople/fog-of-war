"""Exact, demand-driven Dijkstra fields for large tactical scenes.

The search frontier persists between queries. A requested distance is returned
only after it is settled, including detours beyond the requested neighborhood.
This reduces unused work without cropping routes or approximating costs. The
existing eager tcod/Dial implementation remains the optional-numba fallback.
"""
import numpy as np
from .constants import BIG
from . import fastpath

_kernel = None


def _compile():
    global _kernel
    if _kernel is not None:
        return _kernel
    if not fastpath.accelerated():
        _kernel = False
        return False
    import numba

    @numba.njit(cache=True, nogil=True)
    def advance(cost, distances, settled, nodes, values, size, x0,y0,x1,y1):
        w,h = cost.shape
        remaining = 0
        for x in range(x0,x1):
            for y in range(y0,y1):
                if cost[x,y] > 0 and not settled[x,y]:
                    remaining += 1
        while size and remaining:
            node,value = nodes[0],values[0]
            size -= 1
            if size:
                last_node,last_value = nodes[size],values[size]
                i = 0
                while 2*i+1 < size:
                    child = 2*i+1
                    if child+1 < size and values[child+1] < values[child]:
                        child += 1
                    if values[child] >= last_value:
                        break
                    nodes[i],values[i] = nodes[child],values[child]
                    i = child
                nodes[i],values[i] = last_node,last_value
            x,y = node//h,node%h
            if settled[x,y] or distances[x,y] != value:
                continue
            settled[x,y] = 1
            if x0 <= x < x1 and y0 <= y < y1 and cost[x,y] > 0:
                remaining -= 1
            # Expand even the last requested cell: later queries reuse this frontier.
            for dx in range(-1,2):
                nx = x+dx
                if nx < 0 or nx >= w:
                    continue
                for dy in range(-1,2):
                    ny = y+dy
                    if (dx == 0 and dy == 0) or ny < 0 or ny >= h or cost[nx,ny] <= 0 or settled[nx,ny]:
                        continue
                    candidate = value + cost[nx,ny] * (3 if dx and dy else 2)
                    old = distances[nx,ny]
                    if candidate >= BIG+1 or (old and candidate >= old):
                        continue
                    distances[nx,ny] = candidate
                    if size == len(nodes):
                        nn = np.empty(len(nodes)*2,np.int64)
                        vv = np.empty(len(values)*2,np.int32)
                        nn[:size],vv[:size] = nodes,values
                        nodes,values = nn,vv
                    i = size
                    size += 1
                    while i:
                        parent = (i-1)//2
                        if values[parent] <= candidate:
                            break
                        nodes[i],values[i] = nodes[parent],values[parent]
                        i = parent
                    nodes[i],values[i] = nx*h+ny,candidate
        return nodes,values,size
    _kernel = advance
    return advance


class DistanceField:
    def __init__(self, goals, cost):
        # Terrain costs are small nonnegative integers; retain every value in
        # the smallest exact representation instead of keeping a second int32 map.
        highest = int(cost.max(initial=0))
        dtype = np.uint8 if highest <= 255 else np.uint16 if highest <= 65535 else np.int32
        self.cost = cost.astype(dtype,copy=False)
        self.shape = cost.shape
        # Zero means unknown; stored distances are offset by one. Untouched
        # zero-filled pages need no physical backing on supported operating systems.
        self.distances = np.zeros(self.shape,np.int32)
        self.settled = np.zeros(self.shape,np.uint8)
        seeds = np.flatnonzero(goals)
        capacity = max(256,len(seeds)*2)
        self.nodes = np.empty(capacity,np.int64)
        self.values = np.empty(capacity,np.int32)
        self.nodes[:len(seeds)] = seeds
        self.values[:len(seeds)] = 1
        self.distances[goals] = 1
        self.size = len(seeds)
        self.kernel = _compile()

    def __getstate__(self):
        state = dict(self.__dict__)
        state.pop('kernel',None)
        return state

    def __setstate__(self,state):
        self.__dict__.update(state)
        self.kernel = _compile()
        if not self.kernel:
            from .brain import dijkstra
            self.eager = dijkstra(self.distances == 1,self.cost)

    def prepare(self, x,y,radius=1):
        if 'eager' in self.__dict__:
            return
        x,y = int(x),int(y)
        x0,y0 = max(0,x-radius),max(0,y-radius)
        x1,y1 = min(self.shape[0],x+radius+1),min(self.shape[1],y+radius+1)
        if self.size and np.any((self.cost[x0:x1,y0:y1]>0) & (self.settled[x0:x1,y0:y1]==0)):
            self.nodes,self.values,self.size = self.kernel(self.cost,self.distances,self.settled,
                self.nodes,self.values,self.size,x0,y0,x1,y1)

    def item(self, x,y):
        x,y = int(x),int(y)
        if 'eager' in self.__dict__:
            return int(self.eager[x,y])
        if not self.settled[x,y] and self.cost[x,y] > 0 and self.size:
            self.prepare(x,y,0)
        value = self.distances[x,y]
        return int(value)-1 if value and (self.settled[x,y] or value == 1) else BIG

    def __getitem__(self, key):
        if isinstance(key,tuple) and len(key)==2 and all(isinstance(v,(int,np.integer)) for v in key):
            return self.item(*key)
        return self.materialize()[key]

    def materialize(self):
        if 'eager' in self.__dict__:
            return self.eager
        if self.size:
            self.nodes,self.values,self.size = self.kernel(self.cost,self.distances,self.settled,
                self.nodes,self.values,self.size,0,0,*self.shape)
        return np.where(self.distances>0,self.distances-1,BIG).astype(np.int32)


def field(goals,cost):
    if cost.size >= 100000 and _compile():
        return DistanceField(goals,cost)
    from .brain import dijkstra
    return dijkstra(goals,cost)
