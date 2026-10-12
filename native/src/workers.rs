//! One bounded pool shared by native jobs; never run Python or draw game randomness here.
use std::sync::OnceLock;

pub fn pool() -> &'static rayon::ThreadPool {
    static POOL: OnceLock<rayon::ThreadPool> = OnceLock::new();
    POOL.get_or_init(|| {
        let default = std::thread::available_parallelism()
            .map_or(2, usize::from)
            .saturating_sub(2)
            .clamp(1, 8);
        let n = std::env::var("FOW_NATIVE_THREADS")
            .ok()
            .and_then(|s| s.parse::<usize>().ok())
            .unwrap_or(default)
            .clamp(1, 64);
        rayon::ThreadPoolBuilder::new()
            .num_threads(n)
            .thread_name(|i| format!("fow-compute-{i}"))
            .build()
            .expect("native worker pool")
    })
}
