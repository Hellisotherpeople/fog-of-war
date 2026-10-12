"""Native queries, movement and worker batches preserve decisions and random draws."""
from unittest.mock import patch
import numpy as np
import pytest
from fow import native
from fow.constants import BIG

N = pytest.importorskip('_fow_native')


def test_spatial_roster_order_moves_negative_coordinates_and_parallel_batches():
    rng = np.random.default_rng(67)
    pos = rng.integers(-200,200,(2000,2)).astype(np.float32)
    index = N.SpatialIndex(pos)
    queries = [(int(x),int(y),r) for x,y in pos[:70] for r in (0,7,16,60,500)]
    for i in range(0,len(pos),11):
        pos[i] += (37,-43)
        index.move_to(i,*map(float,pos[i]))
    expected = [np.flatnonzero((np.abs(pos[:,0]-x)<=r)&(np.abs(pos[:,1]-y)<=r)).tolist() for x,y,r in queries]
    assert index.near_many(queries) == expected
    assert [index.near(*q) for q in queries] == expected


def test_parallel_routes_keep_all_destinations_detours_and_negative_seeds():
    import tcod
    rng = np.random.default_rng(3)
    costs = [rng.integers(0,20,(100,90),dtype=np.int32) for _ in range(5)]
    seeds = [np.full(c.shape,BIG,np.int32) for c in costs]
    for d,c in zip(seeds,costs):
        c[50,:-1] = 0
        d[0,0],d[95,80] = -300,5
    expected = [d.copy() for d in seeds]
    for d,c in zip(expected,costs):
        tcod.path.dijkstra2d(d,c,2,3,out=d)
    for result,wanted in zip(N.dijkstra_many(seeds,costs,2,3),expected):
        np.testing.assert_array_equal(result,wanted)


@pytest.mark.parametrize('lazy',[False,True])
def test_movement_choices_and_rng_match_original_under_live_obstacles(lazy):
    from test_command_realism import scene,soldier
    from fow import ai
    from fow.gamemap import Mine
    from fow.distancefield import RustDistanceField
    g=scene()
    a=soldier(g,20,20)
    soldier(g,19,20)
    soldier(g,21,20,nation='germany')
    g.map.set(20,19,'wall_brick')
    g.map.refresh()
    g.map.fire[19,19]=30
    g.map.mines[21,21]=Mine('ap',a.side)
    g.map.mines[21,21].known.add(a.side)
    rng=np.random.default_rng(78)
    maps=[rng.integers(0,100,g.map.t.shape,dtype=np.int32) for _ in range(3)]
    if lazy:
        cost=np.ones(g.map.t.shape,np.int32)
        cost[22,:-2]=0
        goal=np.zeros(cost.shape,bool); goal[24,20]=True
        maps[0]=RustDistanceField(goal,cost)
    g.brains[a.side].exposure=rng.random(g.map.t.shape).astype(np.float32)
    for x,y in ((20,20),(0,0),(g.map.w-1,g.map.h-1)):
        a.x,a.y=x,y
        for seed in range(20):
            kwargs=dict(exposure_w=.3,cohesion=(19.5,21),spread=1,stay_bias=.1,
                        keep_range=(maps[2],5,.2))
            fields=[(maps[0],.4),(maps[1],-.2),(None,1)]
            g.rng.seed(seed)
            with patch.object(native,'core',None):
                expected=ai.best_step(g,a,fields,**kwargs)
            after=g.rng.getstate()
            g.rng.seed(seed)
            with patch.object(native,'core',N):
                result=ai.best_step(g,a,fields,**kwargs)
            assert result==expected
            assert g.rng.getstate()==after


def light_reference(w,h,lights):
    out=np.zeros((w,h),bool)
    xs=np.arange(w)[:,None]; ys=np.arange(h)[None,:]
    for x,y,r,square in lights:
        if square:
            out[max(0,x-r):min(w,x+r+1),max(0,y-r):min(h,y+r+1)]=True
        else:
            out |= (xs-x)**2+(ys-y)**2<=r*r
    return out


@pytest.mark.parametrize('shape',[(0,5),(1,1),(73,61),(600,550)])
def test_native_lighting_matches_circles_square_fires_and_boundaries(shape):
    w,h=shape
    rng=np.random.default_rng(4)
    lights=[(int(x),int(y),int(r),int(square)) for x,y,r,square in zip(
        rng.integers(-20,w+20,100),rng.integers(-20,h+20,100),rng.integers(0,80,100),rng.integers(0,2,100))]
    # Squares wholly outside the map use ordinary clipped geometry, not Python negative-stop slices.
    lights=[l for l in lights if l[0]+l[2]>=0 and l[1]+l[2]>=0]
    np.testing.assert_array_equal(N.light_mask(w,h,lights),light_reference(w,h,lights))


def test_gpu_lighting_integer_parity_reuse_and_resize():
    try:
        gpu=N.GpuRoutes()
    except (AttributeError,RuntimeError) as e:
        import os
        if os.environ.get('FOW_REQUIRE_GPU'): pytest.fail(str(e))
        pytest.skip(str(e))
    for w,h in ((73,61),(600,550),(73,61)):
        rng=np.random.default_rng(47)
        lights=[(int(x),int(y),int(r),int(square)) for x,y,r,square in zip(
            rng.integers(-20,w+20,80),rng.integers(-20,h+20,80),rng.integers(0,80,80),rng.integers(0,2,80))]
        np.testing.assert_array_equal(gpu.light_mask(w,h,lights),N.light_mask(w,h,lights))
        np.testing.assert_array_equal(gpu.light_mask(w,h,[]),np.zeros((w,h),bool))


def test_lighting_device_failure_falls_back_without_changing_the_mask(monkeypatch):
    class Broken:
        def light_mask(self,*args):
            raise RuntimeError('injected lighting device loss')
    monkeypatch.setattr(native,'core',N)
    monkeypatch.setattr(native,'_gpu',Broken())
    monkeypatch.setattr(native,'_gpu_failed',False)
    monkeypatch.setattr(native,'_reason',None)
    monkeypatch.setenv('FOW_GPU','on')
    lights=[(10,10,5,0),(20,20,3,1)]
    np.testing.assert_array_equal(native.light_mask(40,40,lights),N.light_mask(40,40,lights))
    assert native._gpu_failed and 'device loss' in native._reason
