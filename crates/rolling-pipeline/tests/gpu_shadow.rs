//! Thor-side checks for the `gpu-shadow` executor. This whole file
//! compiles to nothing without `--features gpu-shadow`, and a
//! `gpu-shadow` build only *links* where cuda-thor's build.rs finds
//! libcuda + libnvrtc (the Thor's aarch64 JetPack layout) — so in
//! practice these tests run on the Thor, against the real sm_110.
//!
//! What they establish, honestly:
//! * the construction probe really reaches the device (memory
//!   figures are the device's own, via `cuMemGetInfo`);
//! * the refusal that follows matches the probe — `GpuApiGap` on a
//!   box with a GPU, because cuda-thor v0.2's public API cannot
//!   express the refine stencil (see `executor::API_GAP`);
//! * the CPU side of the GPU/CPU crossover for the sheaf stencil,
//!   measured at the fixture's graph size and at 4,096 nodes. The
//!   GPU side cannot be measured until the API gap closes; the
//!   bench prints the CPU numbers the GPU would have to beat.
#![cfg(feature = "gpu-shadow")]

use rolling_pipeline::executor::{
    Executor, ExecutorError, GpuShadowExecutor, ProbeOutcome, StageRun,
};
use rolling_pipeline::hotspot_payload;
use rolling_substrate_core::sheaf::SheafGraph;
use std::time::Instant;

#[test]
fn real_hardware_probe_and_refusal_agree() {
    let mut exec = GpuShadowExecutor::new();
    match exec.probe() {
        ProbeOutcome::GpuPresent {
            free_bytes,
            total_bytes,
        } => {
            // A real device reported real memory.
            assert!(*total_bytes > 0 && free_bytes <= total_bytes);
            println!("probe: GPU present, free {free_bytes} / total {total_bytes} bytes");
            let err = exec
                .execute_tick(&hotspot_payload(3.0, 3.0, 7))
                .unwrap_err();
            assert!(
                matches!(err, ExecutorError::GpuApiGap { .. }),
                "GPU present, so the refusal must be the API gap, got {err:?}"
            );
            println!("refusal: {err}");
        }
        ProbeOutcome::NoGpu { reason } => {
            println!("probe: no GPU ({reason})");
            let err = exec
                .execute_tick(&hotspot_payload(3.0, 3.0, 7))
                .unwrap_err();
            assert!(matches!(err, ExecutorError::NoGpuBackend { .. }));
        }
    }
    assert!(!exec.caps().available, "no tick can execute yet");
    assert_eq!(exec.receipts().len(), 1);
    assert!(exec.receipts()[0]
        .placements
        .iter()
        .all(|&p| p == StageRun::NotRun));
}

/// Median wall time of one CPU `smooth_step` (the exact stencil the
/// GPU kernel would replace) over `iters` runs, in microseconds.
fn cpu_stencil_us(n: usize, iters: usize) -> f64 {
    let graph = SheafGraph::line(n);
    let mut s: Vec<f64> = (0..n).map(|i| ((i * 7 % 13) as f64) - 6.0).collect();
    // Warm-up (also proves the step runs at this size).
    graph.smooth_step(&mut s, 0.1);
    let mut times: Vec<f64> = Vec::with_capacity(iters);
    for _ in 0..iters {
        let t = Instant::now();
        graph.smooth_step(&mut s, 0.1);
        times.push(t.elapsed().as_secs_f64() * 1e6);
    }
    times.sort_by(|a, b| a.partial_cmp(b).unwrap());
    times[times.len() / 2]
}

#[test]
fn cpu_stencil_cost_at_fixture_and_scaled_graphs() {
    // The pipeline fixture's graph (8x8 grid -> line(64)) and the
    // scaled graph the crossover question is asked at.
    let us64 = cpu_stencil_us(64, 2_000);
    let us4096 = cpu_stencil_us(4_096, 200);
    println!("CPU sheaf smooth_step median: line(64) = {us64:.3} us, line(4096) = {us4096:.2} us");
    // Sanity only — the numbers above are the deliverable, and any
    // GPU round trip (upload + launch + download + sync) must beat
    // them per tick before the shadow placement can win anything.
    assert!(us64 > 0.0 && us4096 > us64);
}
