"""Reusable padded terrain storage. World coordinates and simulation rules are unchanged.

Most 24-tile reframes select another view of the same slabs: overlapping cells are
not copied. At a slab edge, compact once into fresh slabs. Mutable layers replaced
by a kernel (notably smoke) are synchronized before changing the view.
"""
import numpy as np


def outside(rect, keep):
    x0, y0, x1, y1 = rect
    kx0, ky0, kx1, ky1 = keep
    ix0, iy0, ix1, iy1 = max(x0,kx0), max(y0,ky0), min(x1,kx1), min(y1,ky1)
    if ix0 >= ix1 or iy0 >= iy1:
        return [rect]
    return [r for r in ((x0,y0,ix0,y1), (ix1,y0,x1,y1), (ix0,y0,ix1,iy0), (ix0,iy1,ix1,y1))
            if r[0] < r[2] and r[1] < r[3]]


class TerrainWindow:
    PAD = 48

    def __init__(self):
        self.slabs = {}
        self.origin = None
        self.size = None
        self.offset = (0,0)
        self.reused = self.copied = 0

    def prepare(self, old, old_origin, origin, size, layers):
        dx, dy = origin[0]-old_origin[0], origin[1]-old_origin[1]
        overlap = (max(0,-dx), max(0,-dy), min(size,old.w-dx), min(size,old.h-dy))
        reuse = self.origin == old_origin and self.size == (old.w,old.h)
        ox, oy = self.offset
        if reuse:
            for name, slab in self.slabs.items():
                current = getattr(old, name, None)
                view = slab[ox:ox+old.w, oy:oy+old.h]
                if current is not None and (current.shape != view.shape or
                        current.ctypes.data != view.ctypes.data or current.strides != view.strides):
                    view[:] = current
            nx, ny = ox+dx, oy+dy
            reuse = nx >= 0 and ny >= 0 and nx+size <= next(iter(self.slabs.values())).shape[0] and ny+size <= next(iter(self.slabs.values())).shape[1]
        if not reuse:
            self.slabs = {name: np.empty((size+2*self.PAD, size+2*self.PAD),
                dtype=getattr(old, name).dtype if hasattr(old,name) else np.float32) for name in layers}
            nx = ny = self.PAD
        views = {name: slab[nx:nx+size, ny:ny+size] for name,slab in self.slabs.items()}
        x0,y0,x1,y1 = overlap
        if x0 < x1 and y0 < y1:
            if reuse:
                self.reused += (x1-x0)*(y1-y0)
            else:
                for name,view in views.items():
                    previous = getattr(old,name,None)
                    view[x0:x1,y0:y1] = previous[x0+dx:x1+dx,y0+dy:y1+dy] if previous is not None else 0
                self.copied += (x1-x0)*(y1-y0)
        self.origin, self.size, self.offset = origin, (size,size), (nx,ny)
        return views, outside((0,0,size,size), overlap)
