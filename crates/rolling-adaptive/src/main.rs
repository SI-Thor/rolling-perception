//! Bench: FixedStagger vs AdaptiveStagger on identical traces.
//!
//! Scenarios:
//!  A. jitter + drift  — the real world the lens doctrine addresses
//!  B. jitter, no drift
//!  C. zero jitter, zero drift — fixed's home turf; expect a tie or a
//!     fixed win, and we print whichever it is.
//!
//! Prediction stats use warmup k>=2 for both predictors. Executor:
//! prep 600 µs, run 900 µs per item, freshness deadline 1600 µs.

use rolling_adaptive::*;

fn scenario(name: &str, truths: &[LaneTruth], cycles: usize, seed0: u64) {
    let traces: Vec<Vec<f64>> = truths
        .iter()
        .enumerate()
        .map(|(i, t)| gen_trace(t, cycles, seed0 + 977 * i as u64))
        .collect();
    let nominal = truths[0].period_us;
    let params = ExecParams {
        prep_us: 600.0,
        prep_expiry_us: 2000.0,
        run_us: 900.0,
        freshness_deadline_us: 1600.0,
    };

    let (items_f, errs_f) = build_items(&traces, nominal, false);
    let (items_a, errs_a) = build_items(&traces, nominal, true);
    let (fp50, fp95, _) = stats(&errs_f);
    let (ap50, ap95, _) = stats(&errs_a);
    let sim_f = simulate(items_f, params);
    let sim_a = simulate(items_a, params);

    println!("== {name} ({} lanes x {cycles} cycles) ==", truths.len());
    println!(
        "  prediction |err| us:  fixed  p50={fp50:9.1}  p95={fp95:9.1} | adaptive p50={ap50:9.1}  p95={ap95:9.1}   (p95 ratio {:.2}x)",
        fp95 / ap95.max(1e-9)
    );
    println!(
        "  fresh (<=1600us):     fixed {:5.1}%              | adaptive {:5.1}%",
        sim_f.fresh_pct, sim_a.fresh_pct
    );
    println!(
        "  TTFO us:              fixed {:9.1}              | adaptive {:9.1}",
        sim_f.ttfo_us, sim_a.ttfo_us
    );
    println!(
        "  mean latency us:      fixed {:9.1}              | adaptive {:9.1}",
        sim_f.mean_latency_us, sim_a.mean_latency_us
    );
    println!();
}

fn lanes(period: f64, jitter: f64, drift: f64) -> Vec<LaneTruth> {
    ["perception", "decision", "director", "diffusion"]
        .iter()
        .enumerate()
        .map(|(i, n)| LaneTruth {
            name: n.to_string(),
            period_us: period,
            jitter_std_us: jitter,
            drift_us_per_cycle: drift,
            phase_us: i as f64 * 1250.0,
        })
        .collect()
}

fn main() {
    println!("Lens-calibrated adaptive staggering vs fixed stagger");
    println!("(identical jittered traces; deterministic; logical clock, us)\n");
    scenario("A. jitter 800us + drift +12us/cycle", &lanes(5_000.0, 800.0, 12.0), 400, 0xC0FFEE);
    scenario("B. jitter 800us, no drift", &lanes(5_000.0, 800.0, 0.0), 400, 0xBEEF);
    scenario("C. zero jitter, zero drift (fixed's home turf)", &lanes(5_000.0, 0.0, 0.0), 400, 0xF00D);

    // Show one calibrated lens as text — the deliverable of the doctrine.
    let truth = LaneTruth {
        name: "perception".into(),
        period_us: 5_000.0,
        jitter_std_us: 800.0,
        drift_us_per_cycle: 12.0,
        phase_us: 0.0,
    };
    let trace = gen_trace(&truth, 400, 0xC0FFEE);
    let (_p, lens) = predict_adaptive_named(&trace, 5_000.0, "perception");
    println!("== Lens file after scenario A, lane 'perception' (true period now {:.0} us, true jitter 800 us) ==",
        5_000.0 + 12.0 * 399.0);
    print!("{}", lens.to_text());
}
