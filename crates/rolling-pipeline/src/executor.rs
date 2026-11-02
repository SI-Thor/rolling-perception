//! # The executor seam — where a tick runs, and where the GPU backend lands
//!
//! Today every stage of the cascade executes on the CPU, sequentially,
//! through `rolling-substrate-core` rings ([`Pipeline::run_tick`]).
//! This module is the seam a second backend plugs into: an
//! [`Executor`] is anything that turns one input payload into one
//! [`Published`] payload while preserving the cascade's contract.
//!
//! ## The contract (what any backend must preserve)
//!
//! * **Same outputs for the same inputs.** For an identical input
//!   payload, `execute_tick` must return the [`Published`] the CPU
//!   cascade returns — checksum bit-identical. Scheduling and
//!   placement are free variables; results are not.
//! * **Lineage complete.** The published lineage mask has every stage
//!   bit set, each stage counted exactly once (mask `0b11111`).
//! * **Sheaf energy non-increasing** per payload across `refine`.
//! * **Ops counted, not timed**, wherever a saving is claimed — a
//!   backend that skips work must skip it in the counters too.
//!
//! ## Execution notes: how the GPU backend lands here
//!
//! The Thor spikes (`results/thor/2026-11-01-spike2.md`, PLAN §6) chose
//! the arrangement; this seam is shaped to receive it:
//!
//! * **Two-stream shadow is the default arrangement.** Stream A runs
//!   production slices; stream B stages/shadow-verifies the next
//!   slice, the host staying one slice ahead per stream. It matched
//!   launch-bound pickup (p50 1.1 µs) with better wall time on big
//!   slices (3.6 → 3.0 ms). A persistent kernel *loses* for slice
//!   work (compute 9–27× slower, resident-grid starvation); its niche
//!   is the tiny-buffer ack path, so no backend here may assume one.
//!   Stream priorities had **no effect** (medians identical to
//!   0.01 ms) — not a design dependency.
//! * **Stage placement under that arrangement:** `perceive`'s gated
//!   kernel (the `cuda-thor` perceive filter is this kernel's GPU
//!   twin) and `decide`'s scaling pass are elementwise and go to
//!   stream A first. `refine`'s sheaf step lands on stream B as a
//!   *shadow*: it runs against the CPU Laplacian for a calibration
//!   window and must agree within tolerance before it is trusted —
//!   the same compile → shadow-test → swap discipline FEASIBILITY §3
//!   records for NVRTC hot-swap, with swaps only at launch boundaries
//!   and retired modules unloaded only after their epoch event
//!   synchronises (cuda-thor spike 3: 1,000/1,000 swaps).
//! * **`direct` and `publish` stay on the CPU permanently.** `direct`
//!   is a control policy over one centroid; `publish` computes the
//!   checksum and lineage — the audit record itself. Both are cheap,
//!   and the record is worth more than their microseconds.
//!
//! ## What ships today
//!
//! * [`Pipeline`] itself implements [`Executor`] (`"cpu-rings"`) —
//!   the shipped backend, delegating to [`Pipeline::run_tick`].
//! * Behind the `gpu-shadow` cargo feature (off by default),
//!   [`GpuShadowExecutor`] probes the device for real at
//!   construction through `cuda-thor`'s public API and records what
//!   it found ([`ProbeOutcome`]); every attempted tick appends a
//!   placement receipt ([`TickReceipt`]) and is then **refused** —
//!   [`ExecutorError::NoGpuBackend`] when the probe found no device,
//!   [`ExecutorError::GpuNotBuilt`] when it found one. An earlier
//!   version of this executor refused because `cuda-thor`'s API
//!   could not express the fill (five named gaps); those gaps are
//!   **closed** — the generic API shipped and a sheaf stencil was
//!   Thor-proven through it
//!   (`crates/cuda-thor/tests/sheaf_stencil.rs`). The executor now
//!   stays unfilled **by choice, on measurement**: the crossover
//!   bound in the README's Composition section puts any GPU-refine
//!   win above ~4,096 stencil nodes, and no workload this pipeline
//!   serves today crosses it. [`NOT_BUILT`] states the reason
//!   verbatim. A "GPU executor" that ran the CPU stage closures
//!   anyway would be a lie with a receipt printer; this one prints
//!   the receipt for the refusal instead.

use crate::{Pipeline, Published, DIM};
use std::fmt;

/// What an executor can do, declared up front so wiring code can
/// branch on facts instead of probing behaviour.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExecutorCaps {
    /// Executes stage kernels on a GPU.
    pub gpu: bool,
    /// Uses the two-stream shadow arrangement (production stream +
    /// staging/shadow stream, host one slice ahead per stream).
    pub two_stream_shadow: bool,
    /// Can actually execute ticks in this build. A specified-but-absent
    /// backend (the GPU stub) reports `false` here and errors per call.
    pub available: bool,
}

/// Why an [`Executor`] refused a tick.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ExecutorError {
    /// The backend this executor names is not present in this build.
    /// Returned by the `gpu-shadow` executor when its construction
    /// probe finds no usable GPU.
    NoGpuBackend { backend: &'static str },
    /// A GPU is present, but this executor is deliberately not
    /// built: it refuses rather than silently running the CPU
    /// closures under a GPU name. `reason` states why (see
    /// [`NOT_BUILT`][crate::executor::NOT_BUILT] under `gpu-shadow`)
    /// — the crossover bound, not an API absence: the cuda-thor
    /// gaps that once blocked the fill are closed.
    GpuNotBuilt {
        backend: &'static str,
        reason: &'static str,
    },
    /// Payload was not exactly one grid.
    BadInputLength { expected: usize, got: usize },
}

impl fmt::Display for ExecutorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ExecutorError::NoGpuBackend { backend } => {
                write!(f, "no GPU backend in this build (executor '{backend}')")
            }
            ExecutorError::GpuNotBuilt { backend, reason } => {
                write!(
                    f,
                    "GPU present but executor '{backend}' is not built: {reason}"
                )
            }
            ExecutorError::BadInputLength { expected, got } => {
                write!(f, "payload must be {expected} elements, got {got}")
            }
        }
    }
}

impl std::error::Error for ExecutorError {}

/// One payload in, one [`Published`] out, contract preserved (see the
/// module docs). Backends are stateful: ticks are sequential and each
/// tick's gate depends on the previous tick's `direct`, exactly as in
/// [`Pipeline`].
pub trait Executor {
    /// Stable backend name, for traces and logs.
    fn name(&self) -> &'static str;
    /// Declared capabilities.
    fn caps(&self) -> ExecutorCaps;
    /// Execute one cascade tick through this backend.
    fn execute_tick(&mut self, input: &[f32]) -> Result<Published, ExecutorError>;
}

impl Executor for Pipeline {
    fn name(&self) -> &'static str {
        "cpu-rings"
    }

    fn caps(&self) -> ExecutorCaps {
        ExecutorCaps {
            gpu: false,
            two_stream_shadow: false,
            available: true,
        }
    }

    fn execute_tick(&mut self, input: &[f32]) -> Result<Published, ExecutorError> {
        if input.len() != DIM {
            return Err(ExecutorError::BadInputLength {
                expected: DIM,
                got: input.len(),
            });
        }
        Ok(self.run_tick(input))
    }
}

/// Why [`GpuShadowExecutor`] stays unfilled, stated for the
/// refusal it produces. The cuda-thor API gaps an earlier version
/// of this file named here are closed (the generic API shipped:
/// public `compile`, `Module::load_named`, typed `launch_args`,
/// byte-level transfers, `Gpu::new_stream` — and a sheaf stencil
/// was Thor-proven through it, bit-exact). What remains is the
/// crossover bound, measured not asserted: the CPU refine costs a
/// median 0.268 µs at the fixture's 64-node graph and 10.04 µs at
/// 4,096 nodes, while one launch's pickup alone measures p50
/// 1.1 µs — roughly 4× the entire CPU stencil at fixture scale.
/// A GPU refine cannot win at one-shot launches below ~4,096
/// nodes, so the fill waits for a workload that crosses the bound.
#[cfg(feature = "gpu-shadow")]
pub const NOT_BUILT: &str = "unbuilt by choice (crossover bound): cuda-thor's generic API \
    can express the sheaf stencil and has Thor-proven it, but the CPU refine costs \
    0.268 us at the fixture's 64-node graph and 10.04 us at 4,096 nodes while one \
    launch's pickup alone measures p50 1.1 us, so a GPU refine cannot win below \
    ~4,096 nodes at one-shot launches — and no workload served today crosses that";

/// What [`GpuShadowExecutor`]'s construction probe found, through
/// `cuda-thor`'s public API. Recorded, not acted on beyond the
/// refusal choice: the executor holds no device state afterwards
/// (the probed `Gpu` is dropped — keeping a context it cannot use
/// would be theatre).
#[cfg(feature = "gpu-shadow")]
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProbeOutcome {
    /// A device answered: driver initialised, primary context
    /// retained, memory figures read back. The numbers are the
    /// device's own (`cuMemGetInfo`), recorded at probe time.
    GpuPresent {
        free_bytes: usize,
        total_bytes: usize,
    },
    /// No usable device (driver absent, init failed, or no device
    /// 0). `reason` is cuda-thor's error string, verbatim.
    NoGpu { reason: String },
}

/// Where one stage ran for one tick — the placement half of a
/// [`TickReceipt`]. `NotRun` is a real value, not an omission:
/// a refused tick records that nothing ran, stage by stage.
#[cfg(feature = "gpu-shadow")]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StageRun {
    /// Ran on the CPU (this crate's rings).
    Cpu,
    /// Ran on the GPU production stream (stream A).
    GpuProduction,
    /// Ran on the GPU shadow stream (stream B), as `refine` is
    /// designed to until its calibration window passes.
    GpuShadow,
    /// Did not run — the tick was refused before any stage executed.
    NotRun,
}

/// The two-stream shadow arrangement's intended placement for a
/// stage, per the module docs' execution notes. This is the design
/// map the receipts are read against; it is not a claim that any
/// stage has ever run there.
#[cfg(feature = "gpu-shadow")]
pub fn intended_placement(stage: usize) -> StageRun {
    match stage {
        crate::STAGE_PERCEIVE | crate::STAGE_DECIDE => StageRun::GpuProduction,
        crate::STAGE_REFINE => StageRun::GpuShadow,
        // direct + publish stay on CPU permanently (module docs).
        _ => StageRun::Cpu,
    }
}

/// One attempted tick's receipt: which stages ran where, and the
/// refusal if none did. Appended by `execute_tick` for every
/// well-formed payload, executed or not.
#[cfg(feature = "gpu-shadow")]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TickReceipt {
    /// Tick index within this executor (counts attempts, in order).
    pub tick: u64,
    /// Per-stage placement, in cascade order ([`crate::STAGE_NAMES`]).
    pub placements: [StageRun; 5],
    /// `Some` when the tick was refused (and every placement is
    /// [`StageRun::NotRun`]); `None` when it executed.
    pub refusal: Option<ExecutorError>,
}

/// The two-stream shadow GPU executor. Compiled only with
/// `--features gpu-shadow`.
///
/// Construction probes the device for real (driver init, primary
/// context, `cuMemGetInfo` — all through cuda-thor's public API)
/// and records the outcome. Execution is then refused, typed, on
/// every tick: [`ExecutorError::NoGpuBackend`] when the probe
/// found no device, [`ExecutorError::GpuNotBuilt`] when it found
/// one (see [`NOT_BUILT`]). The executor never runs the CPU stage
/// closures under its GPU name — a fallback that did would produce
/// correct numbers and a false receipt, which is worse than a
/// refusal. The API that would fill it exists and is Thor-proven;
/// the fill is deferred until a workload crosses the crossover
/// bound. When one does, `refine` lands on the shadow stream here
/// and the receipts start recording [`StageRun::GpuShadow`] for it.
#[cfg(feature = "gpu-shadow")]
#[derive(Debug)]
pub struct GpuShadowExecutor {
    probe: ProbeOutcome,
    receipts: Vec<TickReceipt>,
    next_tick: u64,
}

#[cfg(feature = "gpu-shadow")]
impl GpuShadowExecutor {
    /// Construct and probe the hardware (see [`ProbeOutcome`]).
    pub fn new() -> Self {
        Self::with_probe(Self::probe_hardware())
    }

    /// Construct with a recorded probe outcome instead of probing.
    /// This is how tests and wiring exercise both refusal paths
    /// without depending on the machine they run on.
    pub fn with_probe(probe: ProbeOutcome) -> Self {
        Self {
            probe,
            receipts: Vec::new(),
            next_tick: 0,
        }
    }

    /// Probe through cuda-thor's public API: `Gpu::new` +
    /// `mem_info`, then drop the `Gpu` (context released). Any
    /// error becomes [`ProbeOutcome::NoGpu`] with the reason kept.
    fn probe_hardware() -> ProbeOutcome {
        match cuda_thor::gpu::Gpu::new() {
            Ok(gpu) => match gpu.mem_info() {
                Ok((free_bytes, total_bytes)) => ProbeOutcome::GpuPresent {
                    free_bytes,
                    total_bytes,
                },
                Err(e) => ProbeOutcome::NoGpu { reason: e },
            },
            Err(e) => ProbeOutcome::NoGpu { reason: e },
        }
    }

    /// The recorded construction probe.
    pub fn probe(&self) -> &ProbeOutcome {
        &self.probe
    }

    /// Every attempted tick's receipt, in order.
    pub fn receipts(&self) -> &[TickReceipt] {
        &self.receipts
    }

    /// The typed refusal this executor's probe implies. Pure: the
    /// same probe always yields the same refusal.
    fn refusal(&self) -> ExecutorError {
        match &self.probe {
            ProbeOutcome::NoGpu { .. } => ExecutorError::NoGpuBackend {
                backend: "gpu-two-stream-shadow",
            },
            ProbeOutcome::GpuPresent { .. } => ExecutorError::GpuNotBuilt {
                backend: "gpu-two-stream-shadow",
                reason: NOT_BUILT,
            },
        }
    }
}

#[cfg(feature = "gpu-shadow")]
impl Default for GpuShadowExecutor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(feature = "gpu-shadow")]
impl Executor for GpuShadowExecutor {
    fn name(&self) -> &'static str {
        "gpu-two-stream-shadow"
    }

    fn caps(&self) -> ExecutorCaps {
        ExecutorCaps {
            gpu: true,
            two_stream_shadow: true,
            // False, and it stays false until a tick can actually
            // execute on the device: capability means execution,
            // not presence.
            available: false,
        }
    }

    fn execute_tick(&mut self, input: &[f32]) -> Result<Published, ExecutorError> {
        if input.len() != DIM {
            return Err(ExecutorError::BadInputLength {
                expected: DIM,
                got: input.len(),
            });
        }
        let refusal = self.refusal();
        self.receipts.push(TickReceipt {
            tick: self.next_tick,
            placements: [StageRun::NotRun; 5],
            refusal: Some(refusal.clone()),
        });
        self.next_tick += 1;
        Err(refusal)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hotspot_payload;

    #[test]
    fn cpu_executor_satisfies_the_contract() {
        let mut exec = Pipeline::new();
        assert_eq!(exec.name(), "cpu-rings");
        assert_eq!(
            exec.caps(),
            ExecutorCaps {
                gpu: false,
                two_stream_shadow: false,
                available: true
            }
        );
        let pubd = exec.execute_tick(&hotspot_payload(3.0, 3.0, 7)).unwrap();
        assert_eq!(pubd.lineage.mask, 0b11111, "lineage must be complete");
        for stage in 0..5 {
            assert_eq!(pubd.lineage.count(stage), 1, "stage {stage} exactly once");
        }
        assert!(pubd.sheaf_energy_after <= pubd.sheaf_energy_before);
    }

    #[test]
    fn cpu_executor_rejects_wrong_payload_length() {
        let mut exec = Pipeline::new();
        let err = exec.execute_tick(&[0.0f32; 3]).unwrap_err();
        assert_eq!(
            err,
            ExecutorError::BadInputLength {
                expected: DIM,
                got: 3
            }
        );
    }

    #[cfg(feature = "gpu-shadow")]
    #[test]
    fn gpu_shadow_without_gpu_refuses_typed_and_receipts() {
        let mut exec = GpuShadowExecutor::with_probe(ProbeOutcome::NoGpu {
            reason: "test: no device".to_string(),
        });
        assert_eq!(exec.name(), "gpu-two-stream-shadow");
        assert_eq!(
            exec.caps(),
            ExecutorCaps {
                gpu: true,
                two_stream_shadow: true,
                available: false
            }
        );
        let err = exec
            .execute_tick(&hotspot_payload(3.0, 3.0, 7))
            .unwrap_err();
        assert_eq!(
            err,
            ExecutorError::NoGpuBackend {
                backend: "gpu-two-stream-shadow"
            }
        );
        assert!(err.to_string().contains("no GPU backend in this build"));
        // The refusal is receipted: one attempt, nothing ran.
        assert_eq!(exec.receipts().len(), 1);
        let r = &exec.receipts()[0];
        assert_eq!(r.tick, 0);
        assert!(r.placements.iter().all(|&p| p == StageRun::NotRun));
        assert_eq!(r.refusal, Some(err));
    }

    #[cfg(feature = "gpu-shadow")]
    #[test]
    fn gpu_shadow_with_gpu_refuses_as_unbuilt_not_silently_on_cpu() {
        let mut exec = GpuShadowExecutor::with_probe(ProbeOutcome::GpuPresent {
            free_bytes: 1 << 30,
            total_bytes: 2 << 30,
        });
        let err = exec
            .execute_tick(&hotspot_payload(3.0, 3.0, 7))
            .unwrap_err();
        match err {
            ExecutorError::GpuNotBuilt { backend, reason } => {
                assert_eq!(backend, "gpu-two-stream-shadow");
                // The reason is the measured crossover bound, not
                // the closed API gaps: checkable against the
                // README's Composition section and cuda-thor's
                // Thor-proven stencil test.
                assert!(reason.contains("unbuilt by choice"), "{reason}");
                assert!(reason.contains("crossover"), "{reason}");
                assert!(reason.contains("4,096"), "{reason}");
            }
            other => panic!("expected GpuNotBuilt, got {other:?}"),
        }
        // A present GPU does not soften the capability claim, and
        // the receipt still records that no stage ran anywhere.
        assert!(!exec.caps().available);
        assert_eq!(exec.receipts().len(), 1);
        assert!(exec.receipts()[0]
            .placements
            .iter()
            .all(|&p| p == StageRun::NotRun));
    }

    #[cfg(feature = "gpu-shadow")]
    #[test]
    fn gpu_shadow_intended_placement_matches_the_design() {
        use crate::{STAGE_DECIDE, STAGE_DIRECT, STAGE_PERCEIVE, STAGE_PUBLISH, STAGE_REFINE};
        assert_eq!(intended_placement(STAGE_PERCEIVE), StageRun::GpuProduction);
        assert_eq!(intended_placement(STAGE_DECIDE), StageRun::GpuProduction);
        assert_eq!(intended_placement(STAGE_DIRECT), StageRun::Cpu);
        assert_eq!(intended_placement(STAGE_REFINE), StageRun::GpuShadow);
        assert_eq!(intended_placement(STAGE_PUBLISH), StageRun::Cpu);
    }
}
