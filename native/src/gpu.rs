//! Bounded exact GPU relaxation, with CPU completion when a route is longer than the batch.
//! No window/surface, so tcod owns rendering and compute also works headlessly.
use crate::{BIG, array2, routes};
use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::{
    exceptions::{PyRuntimeError, PyValueError},
    prelude::*,
};
use std::{
    sync::{Arc, Mutex, mpsc},
    time::Duration,
};
use wgpu::util::DeviceExt;

struct Buffers {
    n: usize,
    cost: wgpu::Buffer,
    a: wgpu::Buffer,
    b: wgpu::Buffer,
    params: wgpu::Buffer,
    changed: wgpu::Buffer,
    readback: wgpu::Buffer,
    groups: [wgpu::BindGroup; 2],
}

struct LightBuffers {
    n: usize,
    capacity: usize,
    lights: wgpu::Buffer,
    mask: wgpu::Buffer,
    params: wgpu::Buffer,
    readback: wgpu::Buffer,
    group: wgpu::BindGroup,
}

#[pyclass]
pub struct GpuRoutes {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::ComputePipeline,
    buffers: Option<Buffers>,
    light_pipeline: Option<wgpu::ComputePipeline>,
    light_buffers: Option<LightBuffers>,
    error: Arc<Mutex<Option<String>>>,
    #[pyo3(get)]
    name: String,
    #[pyo3(get)]
    backend: String,
    #[pyo3(get)]
    vendor: u32,
    #[pyo3(get)]
    completed_on_gpu: bool,
}

impl GpuRoutes {
    fn open() -> Result<Self, String> {
        let desc = wgpu::InstanceDescriptor::new_without_display_handle().with_env();
        let instance = wgpu::Instance::new(desc);
        let adapter = if let Ok(name) = std::env::var("WGPU_ADAPTER_NAME") {
            pollster::block_on(instance.enumerate_adapters(wgpu::Backends::all()))
                .into_iter()
                .find(|a| {
                    a.get_info()
                        .name
                        .to_lowercase()
                        .contains(&name.to_lowercase())
                })
                .ok_or_else(|| format!("no GPU adapter matches {name:?}"))?
        } else {
            pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                ..Default::default()
            }))
            .map_err(|e| e.to_string())?
        };
        let info = adapter.get_info();
        if info.device_type == wgpu::DeviceType::Cpu {
            return Err("software GPU adapter: using native CPU".into());
        }
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("Fog of War compute"),
            ..Default::default()
        }))
        .map_err(|e| e.to_string())?;
        let error: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));
        let errors = error.clone();
        device.on_uncaptured_error(Arc::new(move |e: wgpu::Error| {
            *errors.lock().unwrap() = Some(e.to_string());
        }));
        let errors = error.clone();
        device.set_device_lost_callback(move |reason, message| {
            *errors.lock().unwrap() = Some(format!("device lost: {reason:?}: {message}"));
        });
        let scope = device.push_error_scope(wgpu::ErrorFilter::Validation);
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("exact integer routes"),
            source: wgpu::ShaderSource::Wgsl(include_str!("routes.wgsl").into()),
        });
        let pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("route relaxation"),
            layout: None,
            module: &shader,
            entry_point: Some("relax"),
            compilation_options: Default::default(),
            cache: None,
        });
        if let Some(e) = pollster::block_on(scope.pop()) {
            return Err(e.to_string());
        }
        Ok(Self {
            device,
            queue,
            pipeline,
            buffers: None,
            light_pipeline: None,
            light_buffers: None,
            error,
            name: info.name,
            backend: format!("{:?}", info.backend),
            vendor: info.vendor,
            completed_on_gpu: false,
        })
    }
    fn allocate(&mut self, n: usize) -> Result<(), String> {
        if self.buffers.as_ref().is_some_and(|b| b.n == n) {
            return Ok(());
        }
        let size = n as u64 * 4;
        let limits = self.device.limits();
        if size > limits.max_storage_buffer_binding_size
            || size + 4 > limits.max_buffer_size
            || n.div_ceil(256) > limits.max_compute_workgroups_per_dimension as usize
        {
            return Err("route grid exceeds GPU limits".into());
        }
        let make = |label, size, usage| {
            self.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some(label),
                size,
                usage,
                mapped_at_creation: false,
            })
        };
        let storage = wgpu::BufferUsages::STORAGE
            | wgpu::BufferUsages::COPY_DST
            | wgpu::BufferUsages::COPY_SRC;
        let cost = make("terrain costs", size, storage);
        let a = make("routes A", size, storage);
        let b = make("routes B", size, storage);
        let changed = make("convergence", 4, storage);
        let params = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("grid parameters"),
                contents: &[0; 16],
                usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            });
        let readback = make(
            "route readback",
            size + 4,
            wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
        );
        let group = |src: &wgpu::Buffer, dst: &wgpu::Buffer| {
            self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("route iteration"),
                layout: &self.pipeline.get_bind_group_layout(0),
                entries: &[
                    wgpu::BindGroupEntry {
                        binding: 0,
                        resource: cost.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 1,
                        resource: src.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 2,
                        resource: dst.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 3,
                        resource: params.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 4,
                        resource: changed.as_entire_binding(),
                    },
                ],
            })
        };
        let groups = [group(&a, &b), group(&b, &a)];
        self.buffers = Some(Buffers {
            n,
            cost,
            a,
            b,
            params,
            changed,
            readback,
            groups,
        });
        Ok(())
    }
    #[allow(clippy::too_many_arguments)]
    fn run(
        &mut self,
        mut dist: Vec<i32>,
        cost: Vec<i32>,
        w: usize,
        h: usize,
        card: i32,
        diag: i32,
        iterations: u32,
    ) -> Result<Vec<i32>, String> {
        if let Some(e) = self.error.lock().unwrap().as_ref() {
            return Err(e.clone());
        }
        if dist.is_empty() {
            self.completed_on_gpu = true;
            return Ok(dist);
        }
        self.allocate(dist.len())?;
        let b = self.buffers.as_ref().unwrap();
        self.queue
            .write_buffer(&b.cost, 0, bytemuck::cast_slice(&cost));
        self.queue
            .write_buffer(&b.a, 0, bytemuck::cast_slice(&dist));
        self.queue.write_buffer(
            &b.params,
            0,
            bytemuck::cast_slice(&[w as u32, h as u32, card as u32, diag as u32]),
        );
        let mut encoder = self.device.create_command_encoder(&Default::default());
        for step in 0..iterations {
            encoder.clear_buffer(&b.changed, 0, None);
            let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                label: Some("route relaxation"),
                timestamp_writes: None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &b.groups[step as usize % 2], &[]);
            pass.dispatch_workgroups(b.n.div_ceil(256) as u32, 1, 1);
        }
        let size = b.n as u64 * 4;
        encoder.copy_buffer_to_buffer(
            if iterations.is_multiple_of(2) {
                &b.a
            } else {
                &b.b
            },
            0,
            &b.readback,
            0,
            size,
        );
        encoder.copy_buffer_to_buffer(&b.changed, 0, &b.readback, size, 4);
        let submission = self.queue.submit([encoder.finish()]);
        let (tx, rx) = mpsc::channel();
        b.readback
            .slice(..)
            .map_async(wgpu::MapMode::Read, move |r| {
                let _ = tx.send(r);
            });
        self.device
            .poll(wgpu::PollType::Wait {
                submission_index: Some(submission),
                timeout: Some(Duration::from_secs(10)),
            })
            .map_err(|e| e.to_string())?;
        rx.recv_timeout(Duration::from_secs(1))
            .map_err(|e| e.to_string())?
            .map_err(|e| e.to_string())?;
        {
            let bytes = b
                .readback
                .slice(..)
                .get_mapped_range()
                .map_err(|e| e.to_string())?;
            let values: &[i32] = bytemuck::cast_slice(&bytes);
            dist.copy_from_slice(&values[..b.n]);
            self.completed_on_gpu = values[b.n] == 0;
        }
        b.readback.unmap();
        if let Some(e) = self.error.lock().unwrap().as_ref() {
            return Err(e.clone());
        }
        // Monotone relaxation preserves the shortest-path fixed point. This completes ALL
        // unresolved paths, including very long detours, without any radius/iteration cutoff.
        if !self.completed_on_gpu {
            routes::solve(&mut dist, &cost, w, h, card, diag);
        }
        Ok(dist)
    }
}

#[pymethods]
impl GpuRoutes {
    #[new]
    fn new(py: Python<'_>) -> PyResult<Self> {
        py.detach(Self::open).map_err(PyRuntimeError::new_err)
    }
    fn light_mask<'py>(
        &mut self,
        py: Python<'py>,
        w: usize,
        h: usize,
        lights: Vec<[i32; 4]>,
    ) -> PyResult<Bound<'py, PyArray2<bool>>> {
        crate::lighting::validate(w, h, &lights)?;
        let out = py
            .detach(|| self.lights_run(w, h, lights))
            .map_err(PyRuntimeError::new_err)?;
        Ok(array2(py, w, h, out))
    }
    fn release_buffers(&mut self) {
        self.buffers = None;
        self.light_buffers = None;
    }
    #[pyo3(signature=(dist,cost,card=2,diag=3,iterations=16))]
    fn solve<'py>(
        &mut self,
        py: Python<'py>,
        dist: PyReadonlyArray2<'py, i32>,
        cost: PyReadonlyArray2<'py, i32>,
        card: i32,
        diag: i32,
        iterations: u32,
    ) -> PyResult<Bound<'py, PyArray2<i32>>> {
        let d = dist.as_array();
        let c = cost.as_array();
        let (w, h) = d.dim();
        if d.dim() != c.dim()
            || card <= 0
            || diag <= 0
            || !(1..=64).contains(&iterations)
            || d.iter()
                .any(|v| *v < -BIG || (*v >= 10_000_000 && *v != BIG))
            || c.iter()
                .any(|v| (*v as i64) * card.max(diag) as i64 > BIG as i64)
        {
            return Err(PyValueError::new_err(
                "GPU route inputs exceed exact integer domain",
            ));
        }
        let values = d.iter().copied().collect();
        let costs = c.iter().copied().collect();
        let out = py
            .detach(|| self.run(values, costs, w, h, card, diag, iterations))
            .map_err(PyRuntimeError::new_err)?;
        Ok(array2(py, w, h, out))
    }
}

impl GpuRoutes {
    fn lights_run(
        &mut self,
        w: usize,
        h: usize,
        lights: Vec<[i32; 4]>,
    ) -> Result<Vec<bool>, String> {
        if let Some(e) = self.error.lock().unwrap().as_ref() {
            return Err(e.clone());
        }
        let n = w * h;
        if n == 0 || lights.is_empty() {
            return Ok(vec![false; n]);
        }
        let limits = self.device.limits();
        if n as u64 * 4 > limits.max_storage_buffer_binding_size
            || lights.len() > limits.max_compute_workgroups_per_dimension as usize
        {
            return Err("lighting exceeds GPU limits".into());
        }
        if self.light_pipeline.is_none() {
            let scope = self.device.push_error_scope(wgpu::ErrorFilter::Validation);
            let shader = self
                .device
                .create_shader_module(wgpu::ShaderModuleDescriptor {
                    label: Some("exact light masks"),
                    source: wgpu::ShaderSource::Wgsl(include_str!("lighting.wgsl").into()),
                });
            self.light_pipeline = Some(self.device.create_compute_pipeline(
                &wgpu::ComputePipelineDescriptor {
                    label: Some("light masks"),
                    layout: None,
                    module: &shader,
                    entry_point: Some("illuminate"),
                    compilation_options: Default::default(),
                    cache: None,
                },
            ));
            if let Some(e) = pollster::block_on(scope.pop()) {
                return Err(e.to_string());
            }
        }
        let pipeline = self.light_pipeline.as_ref().unwrap();
        if self
            .light_buffers
            .as_ref()
            .is_none_or(|b| b.n != n || b.capacity < lights.len())
        {
            let make = |label, size, usage| {
                self.device.create_buffer(&wgpu::BufferDescriptor {
                    label: Some(label),
                    size,
                    usage,
                    mapped_at_creation: false,
                })
            };
            let capacity = lights.len().next_power_of_two();
            let sources = make(
                "light sources",
                (capacity * 16) as u64,
                wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST,
            );
            let mask = make(
                "resident light mask",
                (n * 4) as u64,
                wgpu::BufferUsages::STORAGE
                    | wgpu::BufferUsages::COPY_SRC
                    | wgpu::BufferUsages::COPY_DST,
            );
            let params = make(
                "light extent",
                16,
                wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            );
            let readback = make(
                "light readback",
                (n * 4) as u64,
                wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
            );
            let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("lights"),
                layout: &pipeline.get_bind_group_layout(0),
                entries: &[
                    wgpu::BindGroupEntry {
                        binding: 0,
                        resource: sources.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 1,
                        resource: mask.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 2,
                        resource: params.as_entire_binding(),
                    },
                ],
            });
            self.light_buffers = Some(LightBuffers {
                n,
                capacity,
                lights: sources,
                mask,
                params,
                readback,
                group,
            });
        }
        let b = self.light_buffers.as_ref().unwrap();
        self.queue
            .write_buffer(&b.lights, 0, bytemuck::cast_slice(&lights));
        self.queue.write_buffer(
            &b.params,
            0,
            bytemuck::cast_slice(&[w as u32, h as u32, lights.len() as u32, 0]),
        );
        let mut encoder = self.device.create_command_encoder(&Default::default());
        encoder.clear_buffer(&b.mask, 0, None);
        {
            let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                label: Some("lighting"),
                timestamp_writes: None,
            });
            pass.set_pipeline(pipeline);
            pass.set_bind_group(0, &b.group, &[]);
            pass.dispatch_workgroups(lights.len() as u32, 1, 1);
        }
        encoder.copy_buffer_to_buffer(&b.mask, 0, &b.readback, 0, (n * 4) as u64);
        let submission = self.queue.submit([encoder.finish()]);
        let (tx, rx) = mpsc::channel();
        b.readback
            .slice(..)
            .map_async(wgpu::MapMode::Read, move |r| {
                let _ = tx.send(r);
            });
        self.device
            .poll(wgpu::PollType::Wait {
                submission_index: Some(submission),
                timeout: Some(Duration::from_secs(10)),
            })
            .map_err(|e| e.to_string())?;
        rx.recv_timeout(Duration::from_secs(1))
            .map_err(|e| e.to_string())?
            .map_err(|e| e.to_string())?;
        let out = {
            let bytes = b
                .readback
                .slice(..)
                .get_mapped_range()
                .map_err(|e| e.to_string())?;
            bytemuck::cast_slice::<u8, u32>(&bytes)
                .iter()
                .map(|&v| v != 0)
                .collect()
        };
        b.readback.unmap();
        if let Some(e) = self.error.lock().unwrap().as_ref() {
            return Err(e.clone());
        }
        Ok(out)
    }
}
