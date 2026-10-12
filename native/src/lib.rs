//! Array-sized work crosses the Python boundary; game decisions and RNG stay ordered.
use numpy::ndarray::Array2;
use numpy::{IntoPyArray, PyArray2, PyReadonlyArray2, PyReadwriteArray2};
use pyo3::{exceptions::PyValueError, prelude::*};
use rayon::prelude::*;
#[cfg(feature = "gpu")]
mod gpu;
mod lighting;
mod movement;
mod routes;
mod sight;
mod smoke;
mod spatial;
mod workers;

const BIG: i32 = 100_000_000;

fn array2<T: numpy::Element>(
    py: Python<'_>,
    w: usize,
    h: usize,
    data: Vec<T>,
) -> Bound<'_, PyArray2<T>> {
    Array2::from_shape_vec((w, h), data)
        .expect("validated array shape")
        .into_pyarray(py)
}

#[pyfunction]
fn dijkstra<'py>(
    py: Python<'py>,
    mut dist: PyReadwriteArray2<'py, i32>,
    cost: PyReadonlyArray2<'py, i32>,
    card: i32,
    diag: i32,
) -> PyResult<()> {
    let c = cost.as_array();
    let mut d = dist.as_array_mut();
    if c.shape() != d.shape() || card <= 0 || diag <= 0 {
        return Err(PyValueError::new_err(
            "equal shapes and positive step weights required",
        ));
    }
    // Own buffers while detached: Python cannot race a worker by mutating a NumPy alias.
    let costs: Vec<i32> = c.iter().copied().collect();
    let mut values: Vec<i32> = d.iter().copied().collect();
    let (w, h) = c.dim();
    py.detach(|| routes::solve(&mut values, &costs, w, h, card, diag));
    for (cell, value) in d.iter_mut().zip(values) {
        *cell = value;
    }
    Ok(())
}

#[pymodule]
fn _fow_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("version", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(dijkstra, m)?)?;
    m.add_function(wrap_pyfunction!(dijkstra_many, m)?)?;
    m.add_class::<routes::DistanceField>()?;
    m.add_class::<spatial::SpatialIndex>()?;
    m.add_function(wrap_pyfunction!(sight::sight_lines, m)?)?;
    m.add_function(wrap_pyfunction!(smoke::diffuse, m)?)?;
    m.add_function(wrap_pyfunction!(movement::step_scores, m)?)?;
    m.add_function(wrap_pyfunction!(lighting::light_mask, m)?)?;
    #[cfg(feature = "gpu")]
    m.add_class::<gpu::GpuRoutes>()?;
    Ok(())
}

#[pyfunction]
fn dijkstra_many<'py>(
    py: Python<'py>,
    seeds: Vec<PyReadonlyArray2<'py, i32>>,
    costs: Vec<PyReadonlyArray2<'py, i32>>,
    card: i32,
    diag: i32,
) -> PyResult<Vec<Bound<'py, PyArray2<i32>>>> {
    if seeds.len() != costs.len() || card <= 0 || diag <= 0 {
        return Err(PyValueError::new_err(
            "matching batches and positive step weights required",
        ));
    }
    let mut jobs = Vec::new();
    for (seed, cost) in seeds.iter().zip(&costs) {
        let d = seed.as_array();
        let c = cost.as_array();
        if d.dim() != c.dim() {
            return Err(PyValueError::new_err("route shape mismatch"));
        }
        jobs.push((
            d.nrows(),
            d.ncols(),
            d.iter().copied().collect::<Vec<_>>(),
            c.iter().copied().collect::<Vec<_>>(),
        ));
    }
    py.detach(|| {
        workers::pool().install(|| {
            jobs.par_iter_mut()
                .for_each(|(w, h, d, c)| routes::solve_batch(d, c, *w, *h, card, diag))
        })
    });
    Ok(jobs
        .into_iter()
        .map(|(w, h, d, _)| array2(py, w, h, d))
        .collect())
}
