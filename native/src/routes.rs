//! Exact integer shortest paths. Dial's queue retains the frontier for lazy queries.
use crate::{BIG, array2};
use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::{exceptions::PyValueError, prelude::*};
use std::{cell::RefCell, cmp::Reverse, collections::BinaryHeap, sync::Mutex};

#[derive(Default)]
struct Scratch {
    seeds: Vec<(i32, usize)>,
    buckets: Vec<Vec<usize>>,
}

thread_local! {
    // Reuse queue allocations between fields. Repeatedly growing and freeing
    // dense seed queues otherwise leaves hundreds of MB in allocator arenas.
    static SCRATCH: RefCell<Scratch> = RefCell::new(Scratch::default());
}

fn neighbors(mut f: impl FnMut(usize, i32), node: usize, w: usize, h: usize, card: i32, diag: i32) {
    let x = node / h;
    let y = node % h;
    for dx in -1isize..=1 {
        for dy in -1isize..=1 {
            let nx = x as isize + dx;
            let ny = y as isize + dy;
            if (dx != 0 || dy != 0) && nx >= 0 && ny >= 0 && nx < w as isize && ny < h as isize {
                f(
                    nx as usize * h + ny as usize,
                    if dx != 0 && dy != 0 { diag } else { card },
                );
            }
        }
    }
}

pub fn solve(dist: &mut [i32], cost: &[i32], w: usize, h: usize, card: i32, diag: i32) {
    SCRATCH.with(|scratch| solve_inner(dist, cost, w, h, card, diag, &mut scratch.borrow_mut()));
}

pub fn solve_batch(dist: &mut [i32], cost: &[i32], w: usize, h: usize, card: i32, diag: i32) {
    // Jobs may move among Rayon workers. Retain two reusable queues across the
    // pool, rather than a giant per-worker allocation on every thread touched.
    static FREE: Mutex<Vec<Scratch>> = Mutex::new(Vec::new());
    let mut scratch = FREE.lock().unwrap().pop().unwrap_or_default();
    solve_inner(dist, cost, w, h, card, diag, &mut scratch);
    let mut free = FREE.lock().unwrap();
    if free.len() < 2 {
        free.push(scratch);
    }
}

fn solve_inner(
    dist: &mut [i32],
    cost: &[i32],
    w: usize,
    h: usize,
    card: i32,
    diag: i32,
    scratch: &mut Scratch,
) {
    let maxc = cost.iter().copied().max().unwrap_or(0).max(0) as i64;
    let width = maxc * card.max(diag) as i64 + 1;
    // Exceptional user/mod costs must not allocate enormous bucket arrays or overflow.
    if width > 65536 {
        let mut heap: BinaryHeap<_> = dist
            .iter()
            .enumerate()
            .filter(|(_, v)| **v < 10_000_000)
            .map(|(i, v)| Reverse((*v, i)))
            .collect();
        while let Some(Reverse((value, node))) = heap.pop() {
            if value != dist[node] {
                continue;
            }
            neighbors(
                |n, weight| {
                    if cost[n] <= 0 {
                        return;
                    }
                    let candidate = value as i64 + cost[n] as i64 * weight as i64;
                    if candidate < dist[n] as i64 {
                        dist[n] = candidate as i32;
                        heap.push(Reverse((candidate as i32, n)));
                    }
                },
                node,
                w,
                h,
                card,
                diag,
            );
        }
        return;
    }
    let Scratch { seeds, buckets } = scratch;
    seeds.clear();
    seeds.extend(
        dist.iter()
            .enumerate()
            .filter(|(_, v)| **v < 10_000_000)
            .map(|(i, v)| (*v, i)),
    );
    seeds.sort_unstable_by_key(|p| p.0);
    buckets.resize_with(width as usize, Vec::new);
    for bucket in buckets.iter_mut() {
        bucket.clear();
    }
    let mut si = 0;
    let mut pending = 0;
    let mut cur = seeds.first().map_or(0, |s| s.0);
    while pending > 0 || si < seeds.len() {
        if pending == 0 && si < seeds.len() {
            cur = cur.max(seeds[si].0);
        }
        let b = cur.rem_euclid(width as i32) as usize;
        while si < seeds.len() && seeds[si].0 == cur {
            buckets[b].push(seeds[si].1);
            pending += 1;
            si += 1;
        }
        while let Some(node) = buckets[b].pop() {
            pending -= 1;
            if dist[node] != cur {
                continue;
            }
            neighbors(
                |n, weight| {
                    if cost[n] <= 0 {
                        return;
                    }
                    let value = cur as i64 + cost[n] as i64 * weight as i64;
                    if value < dist[n] as i64 {
                        dist[n] = value as i32;
                        buckets[(value.rem_euclid(width)) as usize].push(n);
                        pending += 1;
                    }
                },
                node,
                w,
                h,
                card,
                diag,
            );
        }
        cur += 1;
    }
}

enum Costs {
    Small(Vec<u8>),
    Large(Vec<u16>),
}

impl Costs {
    #[inline]
    fn at(&self, i: usize) -> u16 {
        match self {
            Self::Small(v) => v[i] as u16,
            Self::Large(v) => v[i],
        }
    }
}

#[pyclass]
pub struct DistanceField {
    w: usize,
    h: usize,
    cost: Costs,
    dist: Vec<i32>,
    settled: Vec<bool>,
    buckets: Vec<Vec<usize>>,
    pending: usize,
    current: i32,
}

impl DistanceField {
    pub(crate) fn sample(&mut self, x: usize, y: usize) -> PyResult<i32> {
        if x >= self.w || y >= self.h {
            return Err(PyValueError::new_err("query outside distance field"));
        }
        let i = x * self.h + y;
        if self.cost.at(i) > 0 && !self.settled[i] && self.pending > 0 {
            self.advance(x, y, x + 1, y + 1);
        }
        Ok(
            if self.dist[i] > 0 && (self.settled[i] || self.dist[i] == 1) {
                self.dist[i] - 1
            } else {
                BIG
            },
        )
    }
    fn advance(&mut self, x0: usize, y0: usize, x1: usize, y1: usize) {
        let mut remaining = 0;
        for x in x0..x1 {
            for y in y0..y1 {
                let i = x * self.h + y;
                if self.cost.at(i) > 0 && !self.settled[i] {
                    remaining += 1;
                }
            }
        }
        while self.pending > 0 && remaining > 0 {
            let b = self.current as usize % self.buckets.len();
            let Some(node) = self.buckets[b].pop() else {
                self.current += 1;
                continue;
            };
            self.pending -= 1;
            if self.settled[node] || self.dist[node] != self.current {
                continue;
            }
            self.settled[node] = true;
            let x = node / self.h;
            let y = node % self.h;
            if x >= x0 && x < x1 && y >= y0 && y < y1 && self.cost.at(node) > 0 {
                remaining -= 1;
            }
            neighbors(
                |n, weight| {
                    if self.cost.at(n) == 0 || self.settled[n] {
                        return;
                    }
                    let value = self.current + self.cost.at(n) as i32 * weight;
                    if value < BIG + 1 && (self.dist[n] == 0 || value < self.dist[n]) {
                        self.dist[n] = value;
                        let b = value as usize % self.buckets.len();
                        self.buckets[b].push(n);
                        self.pending += 1;
                    }
                },
                node,
                self.w,
                self.h,
                2,
                3,
            );
        }
    }
}

#[pymethods]
impl DistanceField {
    #[new]
    fn new(goals: PyReadonlyArray2<'_, bool>, cost: PyReadonlyArray2<'_, u16>) -> PyResult<Self> {
        let g = goals.as_array();
        let c = cost.as_array();
        if c.shape() != g.shape() {
            return Err(PyValueError::new_err("goal/cost shape mismatch"));
        }
        let (w, h) = c.dim();
        let highest = c.iter().copied().max().unwrap_or(0);
        let width = highest as usize * 3 + 1;
        let cost = if highest <= 255 {
            Costs::Small(c.iter().map(|v| *v as u8).collect())
        } else {
            Costs::Large(c.iter().copied().collect())
        };
        let mut s = Self {
            w,
            h,
            cost,
            // Offset by one: untouched zero pages need no physical backing.
            dist: vec![0; w * h],
            settled: vec![false; w * h],
            buckets: vec![Vec::new(); width],
            pending: 0,
            current: 1,
        };
        for (i, goal) in g.iter().enumerate() {
            if *goal {
                s.dist[i] = 1;
                s.buckets[1 % width].push(i);
                s.pending += 1;
            }
        }
        Ok(s)
    }
    fn item(&mut self, py: Python<'_>, x: usize, y: usize) -> PyResult<i32> {
        if x >= self.w || y >= self.h {
            return Err(PyValueError::new_err("query outside distance field"));
        }
        let i = x * self.h + y;
        if self.cost.at(i) > 0 && !self.settled[i] && self.pending > 0 {
            py.detach(|| self.advance(x, y, x + 1, y + 1));
        }
        Ok(
            if self.dist[i] > 0 && (self.settled[i] || self.dist[i] == 1) {
                self.dist[i] - 1
            } else {
                BIG
            },
        )
    }
    #[pyo3(signature=(x,y,radius=1))]
    fn prepare(&mut self, py: Python<'_>, x: usize, y: usize, radius: usize) {
        let (x0, y0, x1, y1) = (
            x.saturating_sub(radius),
            y.saturating_sub(radius),
            x.saturating_add(radius.saturating_add(1)).min(self.w),
            y.saturating_add(radius.saturating_add(1)).min(self.h),
        );
        py.detach(|| self.advance(x0, y0, x1, y1));
    }
    fn materialize<'py>(&mut self, py: Python<'py>) -> Bound<'py, PyArray2<i32>> {
        py.detach(|| self.advance(0, 0, self.w, self.h));
        array2(
            py,
            self.w,
            self.h,
            self.dist
                .iter()
                .map(|v| if *v > 0 { *v - 1 } else { BIG })
                .collect(),
        )
    }
    #[getter]
    fn settled<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray2<bool>> {
        array2(py, self.w, self.h, self.settled.clone())
    }
    fn inputs<'py>(
        &self,
        py: Python<'py>,
    ) -> (Bound<'py, PyArray2<bool>>, Bound<'py, PyArray2<u16>>) {
        (
            array2(
                py,
                self.w,
                self.h,
                self.dist.iter().map(|v| *v == 1).collect(),
            ),
            array2(
                py,
                self.w,
                self.h,
                (0..self.w * self.h).map(|i| self.cost.at(i)).collect(),
            ),
        )
    }
}
