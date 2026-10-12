struct Params { w: u32, h: u32, count: u32, unused: u32 }
@group(0) @binding(0) var<storage, read> lights: array<vec4<i32>>;
@group(0) @binding(1) var<storage, read_write> mask: array<atomic<u32>>;
@group(0) @binding(2) var<uniform> params: Params;

@compute @workgroup_size(256)
fn illuminate(@builtin(workgroup_id) group: vec3<u32>, @builtin(local_invocation_index) lane: u32) {
    if group.x >= params.count { return; }
    let light=lights[group.x];
    let x0=max(0,light.x-light.z); let x1=min(i32(params.w),light.x+light.z+1);
    let y0=max(0,light.y-light.z); let y1=min(i32(params.h),light.y+light.z+1);
    if x0>=x1 || y0>=y1 { return; }
    let height=u32(y1-y0); let size=u32(x1-x0)*height;
    for (var i=lane; i<size; i+=256u) {
        let x=x0+i32(i/height); let y=y0+i32(i%height);
        let dx=x-light.x; let dy=y-light.y;
        if light.w!=0 || dx*dx+dy*dy<=light.z*light.z {
            atomicStore(&mask[u32(x)*params.h+u32(y)],1u);
        }
    }
}
