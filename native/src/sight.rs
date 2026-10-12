//! Same Bresenham tie breaks and f32 crest tests as the existing Numba kernel.
use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::{exceptions::PyValueError, prelude::*};

#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn sight_lines<'py>(
    py: Python<'py>,
    see: PyReadonlyArray2<'py, bool>,
    high: PyReadonlyArray2<'py, bool>,
    elev: PyReadonlyArray2<'py, f32>,
    rel: bool,
    ax: i64,
    ay: i64,
    h0: f64,
    vhigh: bool,
    tx: PyReadonlyArray1<'py, i64>,
    ty: PyReadonlyArray1<'py, i64>,
    h1: PyReadonlyArray1<'py, f64>,
    thigh: PyReadonlyArray1<'py, bool>,
) -> PyResult<Bound<'py, PyArray1<bool>>> {
    let see = see.as_array();
    let high = high.as_array();
    let elev = elev.as_array();
    let tx = tx.as_array();
    let ty = ty.as_array();
    let h1 = h1.as_array();
    let thigh = thigh.as_array();
    let (w, h) = see.dim();
    let inside = |x: i64, y: i64| x >= 0 && y >= 0 && x < w as i64 && y < h as i64;
    if high.dim() != see.dim()
        || elev.dim() != see.dim()
        || tx.len() != ty.len()
        || tx.len() != h1.len()
        || tx.len() != thigh.len()
        || !inside(ax, ay)
        || tx.iter().zip(ty.iter()).any(|(&x, &y)| !inside(x, y))
    {
        return Err(PyValueError::new_err(
            "sight array shapes or coordinates invalid",
        ));
    }
    // Borrow strided maps under the GIL: copying a whole battlefield for forty rays is wasteful.
    let mut out = Vec::with_capacity(tx.len());
    for k in 0..tx.len() {
        let (bx, by, hb) = (tx[k], ty[k], h1[k]);
        if (bx - ax).abs() <= 1 && (by - ay).abs() <= 1 {
            out.push(true);
            continue;
        }
        let mut hi = vhigh || thigh[k];
        if rel && !hi {
            let zm = elev[((ax + bx) as usize / 2, (ay + by) as usize / 2)] as f64;
            hi = h0 >= 2.5
                || hb >= 2.5
                || elev[(ax as usize, ay as usize)] as f64 + h0 - zm >= 4.0
                || elev[(bx as usize, by as usize)] as f64 + hb - zm >= 4.0;
        }
        let (x0, y0, x1, y1, ha, hz) = if ax < bx || (ax == bx && ay <= by) {
            (ax, ay, bx, by, h0, hb)
        } else {
            (bx, by, ax, ay, hb, h0)
        };
        let mask = if hi { high } else { see };
        let (dx, dy) = (x1 - x0, y1 - y0);
        let (sx, sy) = (dx.signum(), dy.signum());
        let n = dx.abs().max(dy.abs());
        let fa = elev[(x0 as usize, y0 as usize)] as f64 + ha;
        let za = fa as f32;
        let dz = (elev[(x1 as usize, y1 as usize)] as f64 + hz - fa) as f32;
        let (mut x, mut y) = (x0, y0);
        let major = sx * dx > sy * dy;
        let mut e = if major { sx * dx } else { sy * dy };
        let mut ok = true;
        for i in 1..n {
            if major {
                x += sx;
                e -= sy * 2 * dy;
                if e < 0 {
                    y += sy;
                    e += sx * 2 * dx;
                }
            } else {
                y += sy;
                e -= sx * 2 * dx;
                if e < 0 {
                    x += sx;
                    e += sy * 2 * dy;
                }
            }
            if !mask[(x as usize, y as usize)]
                || (rel
                    && elev[(x as usize, y as usize)] > za + dz * (i as f32 / n as f32) + 0.25f32)
            {
                ok = false;
                break;
            }
        }
        out.push(ok);
    }
    Ok(out.into_pyarray(py))
}
