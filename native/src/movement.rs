//! Score a soldier's complete neighborhood in one call. Random ties stay on the game RNG.
use crate::routes::DistanceField;
use numpy::{PyReadonlyArray1, PyReadonlyArray2};
use pyo3::{exceptions::PyValueError, prelude::*};

fn sample(field: &Bound<'_, PyAny>, points: &[(usize, usize)]) -> PyResult<Vec<f64>> {
    if let Ok(a) = field.extract::<PyReadonlyArray2<'_, i32>>() {
        let a = a.as_array();
        if points
            .iter()
            .any(|&(x, y)| x >= a.nrows() || y >= a.ncols())
        {
            return Err(PyValueError::new_err("movement field shape mismatch"));
        }
        Ok(points.iter().map(|&(x, y)| a[(x, y)] as f64).collect())
    } else {
        let mut a = field.extract::<PyRefMut<'_, DistanceField>>()?;
        points
            .iter()
            .map(|&(x, y)| a.sample(x, y).map(|v| v as f64))
            .collect()
    }
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn step_scores(
    tiles: PyReadonlyArray2<'_, i32>,
    fire: PyReadonlyArray2<'_, i16>,
    walk: PyReadonlyArray1<'_, bool>,
    doors: PyReadonlyArray1<'_, i8>,
    water: PyReadonlyArray1<'_, i8>,
    x: i64,
    y: i64,
    occupancy: Vec<i8>,
    mines: Vec<bool>,
    maps: Vec<(Bound<'_, PyAny>, f64)>,
    exposure: Option<PyReadonlyArray2<'_, f32>>,
    exposure_weight: f64,
    cohesion: Option<(f64, f64)>,
    spread: f64,
    stay_bias: f64,
    avoid_fire: bool,
    mates: Vec<(i64, i64)>,
    keep: Option<(Bound<'_, PyAny>, f64, f64)>,
    swap_cost: f64,
    unit: f64,
    big: f64,
) -> PyResult<Vec<(i64, i64, f64)>> {
    let t = tiles.as_array();
    let fire = fire.as_array();
    let walk = walk.as_array();
    let doors = doors.as_array();
    let water = water.as_array();
    let exp = exposure.as_ref().map(|a| a.as_array());
    if occupancy.len() != 9
        || mines.len() != 9
        || fire.dim() != t.dim()
        || exp.as_ref().is_some_and(|a| a.dim() != t.dim())
    {
        return Err(PyValueError::new_err("invalid movement snapshot"));
    }
    let mut points = Vec::new();
    let mut steps = Vec::new();
    let mut scores = Vec::new();
    for dx in -1..=1 {
        for dy in -1..=1 {
            let (px, py) = (x + dx, y + dy);
            let i = ((dx + 1) * 3 + dy + 1) as usize;
            if px < 0 || py < 0 || px >= t.nrows() as i64 || py >= t.ncols() as i64 {
                continue;
            }
            let tid = t[(px as usize, py as usize)] as usize;
            if tid >= walk.len() || tid >= doors.len() || tid >= water.len() {
                return Err(PyValueError::new_err("invalid terrain id"));
            }
            let stay = dx == 0 && dy == 0;
            if !stay && (!(walk[tid] || doors[tid] != 0) || occupancy[i] < 0) {
                continue;
            }
            points.push((px as usize, py as usize));
            steps.push((dx, dy, i, tid));
            scores.push(if !stay && occupancy[i] > 0 {
                swap_cost
            } else {
                0.0
            });
        }
    }
    let mut valid = vec![true; points.len()];
    for (map, weight) in maps {
        let ids: Vec<_> = (0..points.len()).filter(|&i| valid[i]).collect();
        let queries: Vec<_> = ids.iter().map(|&i| points[i]).collect();
        let values = sample(&map, &queries)?;
        for (&i, &value) in ids.iter().zip(&values) {
            if value >= big / 2.0 {
                valid[i] = false;
            } else {
                scores[i] += weight * value;
            }
        }
    }
    if let Some((map, distance, weight)) = keep {
        let ids: Vec<_> = (0..points.len()).filter(|&i| valid[i]).collect();
        let queries: Vec<_> = ids.iter().map(|&i| points[i]).collect();
        let values = sample(&map, &queries)?;
        for (&i, &value) in ids.iter().zip(&values) {
            if value < big / 2.0 {
                scores[i] += weight * (value - distance * unit).abs();
            }
        }
    }
    let mut out = Vec::new();
    for i in 0..scores.len() {
        if !valid[i] {
            continue;
        }
        let (px, py) = points[i];
        let (dx, dy, j, tid) = steps[i];
        let s = &mut scores[i];
        if let Some(e) = exp.as_ref() {
            *s += exposure_weight * e[(px, py)] as f64 * unit;
        }
        if let Some((cx, cy)) = cohesion {
            let d = (px as f64 - cx).abs().max((py as f64 - cy).abs());
            if d > spread {
                *s += (d - spread) * unit * 1.5;
            }
        }
        let n = mates
            .iter()
            .filter(|&&(mx, my)| (mx - px as i64).abs() <= 1 && (my - py as i64).abs() <= 1)
            .count();
        if n > 1 {
            *s += (n - 1) as f64 * 1.2;
        }
        if avoid_fire && fire[(px, py)] > 0 {
            *s += 60.0;
        }
        if dx != 0 || dy != 0 {
            if mines[j] {
                *s += 200.0;
            }
            if water[tid] >= 2 {
                *s += 40.0;
            }
            *s += 0.4;
        } else {
            *s -= stay_bias;
        }
        out.push((dx, dy, *s));
    }
    Ok(out)
}
