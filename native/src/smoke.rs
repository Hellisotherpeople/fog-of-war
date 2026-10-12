//! Fused stencil, preserving NumPy's f32 rounding and neighbor addition order.
use crate::array2;
use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use rayon::prelude::*;
use std::sync::OnceLock;

fn pool() -> &'static rayon::ThreadPool {
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
            .thread_name(|i| format!("fow-grid-{i}"))
            .build()
            .expect("native worker pool")
    })
}

#[pyfunction]
pub fn diffuse<'py>(
    py: Python<'py>,
    smoke: PyReadonlyArray2<'py, f32>,
    wx: i32,
    wy: i32,
    drift: bool,
    rain: bool,
) -> Bound<'py, PyArray2<f32>> {
    let s = smoke.as_array();
    let (w, h) = s.dim();
    let input: Vec<_> = s.iter().copied().collect();
    let out = py.detach(|| {
        let cell = |i: usize| {
            let (mut x, mut y) = (i / h, i % h);
            if drift {
                x = (x as i64 - wx as i64).rem_euclid(w as i64) as usize;
                y = (y as i64 - wy as i64).rem_euclid(h as i64) as usize;
            }
            let j = x * h + y;
            let mut nb = 0.0f32;
            if x > 0 {
                nb += input[j - h];
            }
            if x + 1 < w {
                nb += input[j + h];
            }
            if y > 0 {
                nb += input[j - 1];
            }
            if y + 1 < h {
                nb += input[j + 1];
            }
            let mut value = input[j] * 0.55f32 + nb * 0.1f32;
            if drift {
                value *= 0.97f32;
            }
            value *= if rain { 0.9f32 } else { 0.96f32 };
            if value < 0.02 { 0.0 } else { value }
        };
        if input.len() >= 262144 {
            pool().install(|| (0..input.len()).into_par_iter().map(cell).collect())
        } else {
            (0..input.len()).map(cell).collect()
        }
    });
    array2(py, w, h, out)
}
