//! Compact derived position index. Python actors remain authoritative; moves update the index.
use numpy::PyReadonlyArray2;
use pyo3::{exceptions::PyValueError, prelude::*};
use rayon::prelude::*;
use std::collections::HashMap;

#[pyclass]
pub struct SpatialIndex {
    positions: Vec<(f64, f64)>,
    buckets: HashMap<(i64, i64), Vec<usize>>,
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
    fn new(pos: PyReadonlyArray2<'_, f32>) -> PyResult<Self> {
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
        let mut buckets: HashMap<_, Vec<_>> = HashMap::new();
        for (i, &(x, y)) in positions.iter().enumerate() {
            buckets.entry(cell(x, y)).or_default().push(i);
        }
        Ok(Self { positions, buckets })
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
