//! Compact derived position index. Python actors remain authoritative; moves update the index.
use numpy::{PyReadonlyArray1, PyReadonlyArray2};
use pyo3::{exceptions::PyValueError, prelude::*};
use rayon::prelude::*;
use std::collections::HashMap;

#[pyclass]
pub struct SpatialIndex {
    positions: Vec<(f64, f64)>,
    buckets: HashMap<(i64, i64), Vec<usize>>,
    sides: Vec<i8>,          // side code per actor, for the neighbourhood query
    flags: Vec<i8>,          // bit 0 player, bit 1 downed
}

fn cell(x: f64, y: f64) -> (i64, i64) {
    ((x / 16.0).floor() as i64, (y / 16.0).floor() as i64)
}

impl SpatialIndex {
    fn query(&self, x: f64, y: f64, radius: f64) -> Vec<usize> {
        if radius < 0.0 || !radius.is_finite() || !x.is_finite() || !y.is_finite() {
            return Vec::new();
        }
        let lo = cell(x - radius, y - radius);
        let hi = cell(x + radius, y + radius);
        let inside = |i: usize| {
            let p = self.positions[i];
            (p.0 - x).abs() <= radius && (p.1 - y).abs() <= radius
        };
        let mut out = Vec::new();
        let width = hi.0 as i128 - lo.0 as i128 + 1;
        let height = hi.1 as i128 - lo.1 as i128 + 1;
        if width.saturating_mul(height) > self.positions.len() as i128 {
            out.extend((0..self.positions.len()).filter(|&i| inside(i)));
        } else {
            for bx in lo.0..=hi.0 {
                for by in lo.1..=hi.1 {
                    if let Some(ids) = self.buckets.get(&(bx, by)) {
                        out.extend(ids.iter().copied().filter(|&i| inside(i)));
                    }
                }
            }
            out.sort_unstable(); // Original roster order, independent of buckets/worker scheduling.
        }
        out
    }
}

#[pymethods]
impl SpatialIndex {
    #[new]
    #[pyo3(signature = (pos, sides=None, flags=None))]
    fn new(
        pos: PyReadonlyArray2<'_, f32>,
        sides: Option<PyReadonlyArray1<'_, i8>>,
        flags: Option<PyReadonlyArray1<'_, i8>>,
    ) -> PyResult<Self> {
        let a = pos.as_array();
        if a.ncols() != 2 || a.iter().any(|v| !v.is_finite()) {
            return Err(PyValueError::new_err(
                "finite positions with two columns required",
            ));
        }
        let positions: Vec<_> = a
            .rows()
            .into_iter()
            .map(|p| (p[0] as f64, p[1] as f64))
            .collect();
        let n = positions.len();
        let sides: Vec<i8> = sides.map(|s| s.as_array().to_vec()).unwrap_or_else(|| vec![0; n]);
        let flags: Vec<i8> = flags.map(|f| f.as_array().to_vec()).unwrap_or_else(|| vec![0; n]);
        if sides.len() != n || flags.len() != n {
            return Err(PyValueError::new_err("side/flag length mismatch"));
        }
        let mut buckets: HashMap<_, Vec<_>> = HashMap::new();
        for (i, &(x, y)) in positions.iter().enumerate() {
            buckets.entry(cell(x, y)).or_default().push(i);
        }
        Ok(Self { positions, buckets, sides, flags })
    }
    fn set_flags(&mut self, flags: PyReadonlyArray1<'_, i8>) -> PyResult<()> {
        let f = flags.as_array();
        if f.len() != self.positions.len() {
            return Err(PyValueError::new_err("flag length mismatch"));
        }
        self.flags = f.to_vec();
        Ok(())
    }

    /// Occupancy for the nine cells around a man, and the mates within two: the raw material of one step.
    fn context(
        &self,
        x: f64,
        y: f64,
        side: i8,
        vehicles: Vec<(i64, i64)>,
        skip: usize,
    ) -> (Vec<i8>, Vec<(i64, i64)>) {
        let mut occ = vec![0i8; 9];
        for dx in -1..=1i64 {
            for dy in -1..=1i64 {
                let px = x as i64 + dx;
                let py = y as i64 + dy;
                let i = ((dx + 1) * 3 + dy + 1) as usize;
                if vehicles.contains(&(px, py)) {
                    occ[i] = -1;
                    continue;
                }
                if let Some(ids) = self.buckets.get(&cell(px as f64, py as f64)) {
                    for &k in ids {
                        let p = self.positions[k];
                        if p.0 == px as f64 && p.1 == py as f64 {
                            let f = self.flags[k];
                            occ[i] = if self.sides[k] != side || f & 1 != 0 || f & 2 != 0 { -1 } else { 1 };
                            break;
                        }
                    }
                }
            }
        }
        let mut mates = Vec::new();
        let (cx, cy) = cell(x, y);
        for bx in cx - 1..=cx + 1 {
            for by in cy - 1..=cy + 1 {
                if let Some(ids) = self.buckets.get(&(bx, by)) {
                    for &k in ids {
                        if k == skip {
                            continue;
                        }
                        let p = self.positions[k];
                        if self.sides[k] == side && (p.0 - x).abs() <= 2.0 && (p.1 - y).abs() <= 2.0 {
                            mates.push((p.0 as i64, p.1 as i64));
                        }
                    }
                }
            }
        }
        (occ, mates)
    }
    fn move_to(&mut self, index: usize, x: f64, y: f64) -> PyResult<()> {
        if index >= self.positions.len() || !x.is_finite() || !y.is_finite() {
            return Err(PyValueError::new_err("invalid actor position"));
        }
        let old = cell(self.positions[index].0, self.positions[index].1);
        let new = cell(x, y);
        if old != new {
            if let Some(ids) = self.buckets.get_mut(&old) {
                ids.retain(|&i| i != index);
            }
            self.buckets.entry(new).or_default().push(index);
        }
        self.positions[index] = (x, y);
        Ok(())
    }
    fn near(&self, x: f64, y: f64, radius: f64) -> Vec<usize> {
        self.query(x, y, radius)
    }

    /// The `limit` nearest within the square, tie-broken by roster order (stable on squared distance).
    fn nearest(&self, x: f64, y: f64, radius: f64, limit: usize) -> Vec<usize> {
        let mut out = self.query(x, y, radius);
        let dist = |i: usize| {
            let p = self.positions[i];
            (p.0 - x).powi(2) + (p.1 - y).powi(2)
        };
        out.retain(|&i| dist(i) <= radius * radius);
        out.sort_by(|&a, &b| dist(a).partial_cmp(&dist(b)).unwrap_or(std::cmp::Ordering::Equal));
        out.truncate(limit);
        out
    }
    fn near_many(&self, py: Python<'_>, queries: Vec<(f64, f64, f64)>) -> Vec<Vec<usize>> {
        py.detach(|| {
            if queries.len() < 16 {
                queries
                    .iter()
                    .map(|&(x, y, r)| self.query(x, y, r))
                    .collect()
            } else {
                crate::workers::pool().install(|| {
                    queries
                        .par_iter()
                        .map(|&(x, y, r)| self.query(x, y, r))
                        .collect()
                })
            }
        })
    }
}
