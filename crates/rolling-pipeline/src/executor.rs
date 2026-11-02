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
//! * Behind the `gpu-shadow` cargo feature (off by default), the
//!   [`GpuShadowExecutor`] **stub**: the specified type, capabilities
//!   declared, construction wired — and `execute_tick` returns
//!   [`ExecutorError::NoGpuBackend`]. It is a compile-checked
//!   placeholder for the backend described above, not a fake GPU
//!   implementation: it computes nothing and says so, typed.

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
    /// Returned by the `gpu-shadow` stub until the real two-stream
    /// shadow backend lands behind this seam.
    NoGpuBackend { backend: &'static str },
    /// Payload was not exactly one grid.
    BadInputLength { expected: usize, got: usize },
}

impl fmt::Display for ExecutorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ExecutorError::NoGpuBackend { backend } => {
                write!(f, "no GPU backend in this build (executor '{backend}')")
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

/// The two-stream shadow GPU executor, as specified in the module
/// docs — **stub**. Compiled only with `--features gpu-shadow`.
///
/// The type exists so the seam is real in code: wiring, capability
/// checks and error handling can all be written and tested against it
/// before the backend (cuda-thor's FFI route, PLAN §6) is plugged in.
/// It holds no device state and computes nothing; every tick is
/// refused with [`ExecutorError::NoGpuBackend`].
#[cfg(feature = "gpu-shadow")]
#[derive(Debug, Default)]
pub struct GpuShadowExecutor {
    _seam_only: (),
}

#[cfg(feature = "gpu-shadow")]
impl GpuShadowExecutor {
    pub fn new() -> Self {
        Self::default()
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
            available: false,
        }
    }

    fn execute_tick(&mut self, _input: &[f32]) -> Result<Published, ExecutorError> {
        Err(ExecutorError::NoGpuBackend {
            backend: "gpu-two-stream-shadow",
        })
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
    fn gpu_shadow_stub_is_typed_and_unavailable() {
        let mut exec = GpuShadowExecutor::new();
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
    }
}
