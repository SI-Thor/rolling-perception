//! Composition tests: the wave crates connected, not just coexisting.
//!
//! * `rolling-adaptive`'s lens drives `rolling-pipeline`'s release
//!   timing (`run_rolling_adaptive`) — proven under injected drift.
//! * The `endtoend` binary's path (adaptive-timed cascade over the
//!   fixture stream) keeps the cascade's trace invariants.
//! * The `Executor` seam's shipped CPU implementation honours the
//!   contract a GPU backend will have to honour.

use rolling_pipeline::executor::{Executor, ExecutorError};
use rolling_pipeline::*;
use std::time::Duration;

/// The correctness half of the adaptive claim, and the prediction
/// half, on one drifted stream: the lens-timed run must publish
/// exactly what the fixed-stagger rolling baseline publishes, while
/// its release-prediction error beats the fixed-stagger control's on
/// the identical stream.
#[test]
fn adaptive_timing_holds_correctness_and_beats_fixed_under_drift() {
    // 12 cycles x 5 payloads; the period starts at 400 us and grows
    // 25 us every cycle (400 -> 675 us across the run).
    let cycles =
        generate_drifted_cycles(12, 5, Duration::from_micros(400), Duration::from_micros(25));
    let nominal = Duration::from_micros(400);

    // Fixed-stagger baseline: the existing rolling scheduler, which
    // releases on the recorded arrivals.
    let mut base_pipe = Pipeline::new();
    let baseline = run_rolling(&mut base_pipe, &cycles);

    // Connected system: releases driven by the calibrated lens.
    let mut lens_pipe = Pipeline::new();
    let rep = run_rolling_adaptive(&mut lens_pipe, &cycles, nominal);

    assert_eq!(rep.report.outputs, baseline.outputs);
    assert_eq!(rep.tick_traces.len(), baseline.outputs);

    // Verdicts identical: per-payload checksums, in order, plus the
    // run total and the counted ops — scheduling is the only variable.
    let mut seq_pipe = Pipeline::new();
    let mut idx = 0;
    for cycle in &cycles {
        for entry in cycle {
            let expected = seq_pipe.run_tick(&entry.data);
            let got = &rep.tick_traces[idx].published;
            assert!(
                (got.checksum - expected.checksum).abs() < 1e-9,
                "payload {idx}: lens-timed checksum {} != baseline {}",
                got.checksum,
                expected.checksum
            );
            idx += 1;
        }
    }
    assert!((rep.report.checksum - baseline.checksum).abs() < 1e-6);
    assert_eq!(
        rep.report.ops, baseline.ops,
        "counted ops must not change with timing"
    );

    // Prediction: both errors graded on the identical stream in the
    // same run (n = payloads - warmup).
    assert_eq!(rep.release_errors_us.len(), 60 - RELEASE_WARMUP);
    assert_eq!(rep.fixed_release_errors_us.len(), 60 - RELEASE_WARMUP);
    let ((_, lens_p95, _), (_, fixed_p95, _)) = rep.release_error_stats();
    eprintln!(
        "drift run: lens release p95 = {lens_p95:.1} us, fixed-stagger control p95 = {fixed_p95:.1} us \
         (lens est period {:.1} us vs true final 675 us)",
        rep.lens.est_period_us
    );
    assert!(
        lens_p95 < fixed_p95,
        "lens p95 {lens_p95:.1} must beat fixed {fixed_p95:.1}"
    );
    assert!(
        lens_p95 < 0.25 * fixed_p95,
        "under this drift the lens should win by a wide margin: {lens_p95:.1} vs {fixed_p95:.1}"
    );
    // The lens really calibrated: its period estimate ends near the
    // drifted truth (675 us), nowhere near the 400 us nominal.
    assert!(
        (rep.lens.est_period_us - 675.0).abs() < 100.0,
        "lens est period {} not tracking the drift",
        rep.lens.est_period_us
    );
}

/// The path the `endtoend` binary runs — fixture stream through the
/// adaptive-timed cascade — keeps the trace invariants: complete
/// lineage on every payload, sheaf energy down on every payload, and
/// the verdict set equal to the known-good set (the plain sequential
/// cascade over the same entries, the baseline the e2e tests use).
#[test]
fn endtoend_path_trace_invariants() {
    let flat = generate_trace(12, Duration::from_micros(400));
    let cycles: Vec<Cycle> = flat
        .chunks(3)
        .map(|chunk| {
            let t0 = chunk[0].arrival;
            chunk
                .iter()
                .map(|e| TraceEntry {
                    arrival: e.arrival - t0,
                    data: e.data.clone(),
                })
                .collect()
        })
        .collect();

    let mut pipe = Pipeline::new();
    let rep = run_rolling_adaptive(&mut pipe, &cycles, Duration::from_micros(400));
    assert_eq!(rep.tick_traces.len(), 12);
    assert_eq!(rep.report.outputs, 12);

    // Known-good verdict set: same entries, plain sequential ticks.
    let mut base = Pipeline::new();
    let mut known_good: Vec<f64> = Vec::new();
    for entry in &flat {
        known_good.push(base.run_tick(&entry.data).checksum);
    }

    for (i, trace) in rep.tick_traces.iter().enumerate() {
        let p = &trace.published;
        assert_eq!(p.tick, i as u64);
        assert_eq!(
            p.lineage.mask, 0b11111,
            "tick {i}: lineage mask must be complete"
        );
        for (stage, name) in STAGE_NAMES.iter().enumerate() {
            assert_eq!(p.lineage.count(stage), 1, "tick {i}: {name} exactly once");
        }
        assert!(
            p.sheaf_energy_after < p.sheaf_energy_before,
            "tick {i}: energy must decrease: {} -> {}",
            p.sheaf_energy_before,
            p.sheaf_energy_after
        );
        assert!(
            (p.checksum - known_good[i]).abs() < 1e-9,
            "tick {i}: verdict {} != known-good {}",
            p.checksum,
            known_good[i]
        );
    }
}

/// The seam's shipped implementation, exercised through the trait
/// object surface a future GPU backend will be used through.
#[test]
fn executor_seam_cpu_impl_honours_contract() {
    let mut exec: Box<dyn Executor> = Box::new(Pipeline::new());
    assert_eq!(exec.name(), "cpu-rings");
    let caps = exec.caps();
    assert!(!caps.gpu && !caps.two_stream_shadow && caps.available);

    let pubd = exec.execute_tick(&hotspot_payload(2.0, 2.0, 42)).unwrap();
    assert_eq!(pubd.lineage.mask, 0b11111);
    assert!(pubd.sheaf_energy_after <= pubd.sheaf_energy_before);

    let err = exec.execute_tick(&[1.0, 2.0]).unwrap_err();
    assert_eq!(
        err,
        ExecutorError::BadInputLength {
            expected: DIM,
            got: 2
        }
    );
}
