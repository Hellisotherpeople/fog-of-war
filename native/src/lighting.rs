//! Exact integer light masks, independent of actor turns and random state.
use numpy::PyArray2;
use pyo3::{exceptions::PyValueError, prelude::*};
use rayon::prelude::*;

pub(crate) fn validate(w: usize, h: usize, lights: &[[i32; 4]]) -> PyResult<()> {
    if w > 100_000
        || h > 100_000
        || w.checked_mul(h).is_none_or(|n| n > 100_000_000)
        || lights.iter().any(|l| {
            l[2] < 0
                || l[2] > 16_384
                || l[0].abs_diff(0) > 1_000_000
                || l[1].abs_diff(0) > 1_000_000
        })
    {
        return Err(PyValueError::new_err("invalid lighting extent"));
    }
    Ok(())
}

pub(crate) fn mask(w: usize, h: usize, lights: &[[i32; 4]]) -> Vec<bool> {
    let mut out = vec![false; w * h];
    if h == 0 {
        return out;
    }
    let fill = |start: usize, rows: &mut [bool]| {
        let end = start + rows.len() / h;
        for &[x, y, r, square] in lights {
            let (x, y, r) = (x as i64, y as i64, r as i64);
            let x0 = (x - r).max(start as i64);
            let x1 = (x + r + 1).min(end as i64);
            let y0 = (y - r).max(0);
            let y1 = (y + r + 1).min(h as i64);
            for px in x0..x1 {
                for py in y0..y1 {
                    if square != 0 || (px - x) * (px - x) + (py - y) * (py - y) <= r * r {
                        rows[(px as usize - start) * h + py as usize] = true;
                    }
                }
            }
        }
    };
    let work: u64 = lights.iter().map(|l| (2 * l[2] as u64 + 1).pow(2)).sum();
    if w * h >= 262144 && work >= 262144 {
        crate::workers::pool().install(|| {
            out.par_chunks_mut(h * 32)
                .enumerate()
                .for_each(|(i, rows)| fill(i * 32, rows))
        });
    } else {
        fill(0, &mut out);
    }
    out
}

#[pyfunction]
pub fn light_mask(
    py: Python<'_>,
    w: usize,
    h: usize,
    lights: Vec<[i32; 4]>,
) -> PyResult<Bound<'_, PyArray2<bool>>> {
    validate(w, h, &lights)?;
    let out = py.detach(|| mask(w, h, &lights));
    Ok(crate::array2(py, w, h, out))
}
