//! endtoend: the composed system in one run — substrate rings →
//! adaptive-timed cascade → gating → sheaf refine → published
//! verdicts, on the pipeline's fixture stream (the `generate_trace`
//! hotspot stream, chunked into cycles).
//!
//! Release timing is driven by the rolling-adaptive lens
//! (`run_rolling_adaptive`); the cascade itself is the shipped CPU
//! executor behind the `Executor` seam. The trace printed per tick
//! is the `TickTrace` the integration tests assert invariants over.
//!
//! Usage: cargo run --release -p rolling-pipeline --bin endtoend

use rolling_pipeline::executor::Executor;
use rolling_pipeline::*;
use std::time::Duration;

fn main() {
    // The fixture stream: 24 hotspot payloads at a nominal 400 us
    // stagger, chunked into cycles of 4 and re-based per cycle —
    // the same construction the end-to-end tests use.
    let stagger = Duration::from_micros(400);
    let flat = generate_trace(24, stagger);
    let cycles: Vec<Cycle> = flat
        .chunks(4)
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
    let caps = pipe.caps();
    println!(
        "endtoend: executor={} gpu={} two-stream-shadow={} available={}",
        pipe.name(),
        caps.gpu,
        caps.two_stream_shadow,
        caps.available
    );
    println!(
        "stream: {} payloads in {} cycles, nominal stagger {} us, stages {}",
        flat.len(),
        cycles.len(),
        stagger.as_micros(),
        STAGE_NAMES.join(" -> ")
    );
    println!(
        "{:>4}  {:<38} {:>5}  {:>17}  {:>9}  {:>9}",
        "tick",
        "stage us (perceive/decide/direct/refine/publish)",
        "mask",
        "sheaf energy",
        "rel err",
        "checksum"
    );

    let rep = run_rolling_adaptive(&mut pipe, &cycles, stagger);
    for (trace, rel) in rep.tick_traces.iter().zip(rep.releases.iter()) {
        let p = &trace.published;
        let stages: Vec<String> = trace
            .stage_durations
            .iter()
            .map(|d| format!("{}", d.as_micros()))
            .collect();
        let rel_err = match rel.predicted_us {
            Some(pred) => format!("{:.0} us", (rel.actual_us - pred).abs()),
            None => "-".to_string(),
        };
        println!(
            "{:>4}  {:<38} {:05b}  {:8.2} -> {:6.2}  {:>9}  {:>9.4}",
            p.tick,
            stages.join("/"),
            p.lineage.mask,
            p.sheaf_energy_before,
            p.sheaf_energy_after,
            rel_err,
            p.checksum,
        );
    }

    let ((lp50, lp95, _), (fp50, fp95, _)) = rep.release_error_stats();
    let r = &rep.report;
    println!(
        "outputs={} ttfo={:.1} us total={:.1} ms checksum={:.4}",
        r.outputs,
        r.time_to_first_output.as_secs_f64() * 1e6,
        r.total.as_secs_f64() * 1e3,
        r.checksum,
    );
    println!(
        "gating: perceive {} of {} ungated -> saved {:.1}% (counted) | director {} moves, {} holds",
        r.ops.perceive_gated,
        r.ops.perceive_baseline,
        r.ops.gating_saved_fraction() * 100.0,
        r.director_moves,
        r.director_holds,
    );
    println!(
        "release prediction |err| us: lens p50={:.1} p95={:.1} | fixed-stagger control p50={:.1} p95={:.1}",
        lp50, lp95, fp50, fp95,
    );
    println!(
        "calibrated lens after the run: est period {:.1} us (nominal {} us), jitter std {:.1} us, {} observations",
        rep.lens.est_period_us,
        stagger.as_micros(),
        rep.lens.jitter_std_us(),
        rep.lens.observations,
    );
}
