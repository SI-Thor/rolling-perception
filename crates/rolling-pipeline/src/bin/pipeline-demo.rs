//! pipeline-demo: run the whole cascade under both schedulers and
//! print a compact report. Usage:
//!   pipeline-demo [--trace FILE] [--cycles 6] [--per-cycle 4] [--stagger-us 400]
//! Without --trace, a synthetic trace is generated in memory (the
//! same generator `trace-gen` writes to disk).

use rolling_pipeline::*;
use std::time::Duration;

fn arg<T: std::str::FromStr>(args: &[String], name: &str, default: T) -> T {
    args.windows(2)
        .find(|w| w[0] == name)
        .and_then(|w| w[1].parse().ok())
        .unwrap_or(default)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cycles_n: usize = arg(&args, "--cycles", 6);
    let per_cycle: usize = arg(&args, "--per-cycle", 4);
    let stagger_us: u64 = arg(&args, "--stagger-us", 400);

    let cycles: Vec<Cycle> = if let Some(pos) = args.iter().position(|a| a == "--trace") {
        let path = args.get(pos + 1).expect("--trace needs a file path");
        let flat = load_trace(std::path::Path::new(path)).expect("cannot load trace");
        // Re-base arrivals per cycle chunk so cycle semantics match
        // the synthetic path (arrivals relative to cycle start).
        flat.chunks(per_cycle)
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
            .collect()
    } else {
        let flat = generate_trace(cycles_n * per_cycle, Duration::from_micros(stagger_us));
        flat.chunks(per_cycle)
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
            .collect()
    };

    println!(
        "rolling-pipeline demo: {} cycles x {} payloads ({}x{} grid, stages {})",
        cycles.len(),
        cycles.first().map(|c| c.len()).unwrap_or(0),
        WIDTH,
        HEIGHT,
        STAGE_NAMES.join(" -> ")
    );

    let mut reports = Vec::new();
    for rolling in [false, true] {
        let mut pipe = Pipeline::new();
        let rep = if rolling {
            run_rolling(&mut pipe, &cycles)
        } else {
            run_batched(&mut pipe, &cycles)
        };
        println!(
            "{:8} outputs={:3}  ttfo={:9.1} us  total={:9.1} ms  checksum={:.4}  p95_inter={:8.1} us",
            rep.scheduler,
            rep.outputs,
            rep.time_to_first_output.as_secs_f64() * 1e6,
            rep.total.as_secs_f64() * 1e3,
            rep.checksum,
            rolling_perception::percentile(&rep.inter_output, 95.0).as_secs_f64() * 1e6,
        );
        reports.push(rep);
    }
    let r = &reports[1];
    let b = &reports[0];
    println!(
        "checksum delta batched-vs-rolling: {:.6} (0 = identical work)",
        (b.checksum - r.checksum).abs()
    );
    println!(
        "ops (identical under both schedulers): perceive gated {} / ungated baseline {} -> gating saved {:.1}%  | decide {} direct {} refine {} publish {} total {}",
        r.ops.perceive_gated,
        r.ops.perceive_baseline,
        r.ops.gating_saved_fraction() * 100.0,
        r.ops.decide,
        r.ops.direct,
        r.ops.refine,
        r.ops.publish,
        r.ops.total(),
    );
    println!(
        "sheaf energy (summed over payloads): {:.3} -> {:.3}  (refine, per payload asserted non-increasing)",
        r.sheaf_energy_before, r.sheaf_energy_after
    );
    println!(
        "director: {} gate moves, {} deadband holds",
        r.director_moves, r.director_holds
    );
    if let Some(l) = &r.sample_lineage {
        let stages: Vec<String> = (0..5)
            .map(|s| format!("{}:{}", STAGE_NAMES[s], l.count(s)))
            .collect();
        println!(
            "sample payload lineage (mask {:05b}): {}",
            l.mask,
            stages.join(" ")
        );
    }
}
