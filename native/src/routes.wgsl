// One Jacobi relaxation. Each dispatch sees the complete previous iteration.
// Only integer arithmetic: Metal, Vulkan and DX12 produce identical distances.
struct Params { width:u32, height:u32, cardinal:i32, diagonal:i32 }
@group(0) @binding(0) var<storage,read> costs:array<i32>;
@group(0) @binding(1) var<storage,read> previous:array<i32>;
@group(0) @binding(2) var<storage,read_write> next:array<i32>;
@group(0) @binding(3) var<uniform> p:Params;
@group(0) @binding(4) var<storage,read_write> changed:atomic<u32>;

@compute @workgroup_size(256)
fn relax(@builtin(global_invocation_id) id:vec3<u32>) {
    let i=id.x;
    if i>=p.width*p.height {return;}
    var best=previous[i];
    let c=costs[i];
    if c>0 {
        let x=i32(i/p.height); let y=i32(i%p.height);
        for(var dx:i32=-1;dx<=1;dx++) {
            for(var dy:i32=-1;dy<=1;dy++) {
                let nx=x+dx;let ny=y+dy;
                if (dx!=0 || dy!=0) && nx>=0 && ny>=0 && nx<i32(p.width) && ny<i32(p.height) {
                    let before=previous[u32(nx)*p.height+u32(ny)];
                    if before<100000000 {
                        let weight=select(p.cardinal,p.diagonal,dx!=0 && dy!=0);
                        best=min(best,before+c*weight);
                    }
                }
            }
        }
    }
    next[i]=best;
    if best!=previous[i] {atomicStore(&changed,1u);}
}
