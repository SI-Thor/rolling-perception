//! Benchmark: batched vs. rolling on identical lanes/work.
//!
//! Usage:
//!   cargo run --release
//!   cargo run --release -- --cycles 120 --stagger-us 400
//!   cargo run --release -- --cycles 50  --stagger-us 0
//!
//! All timings are real `std::time::Instant` measurements of real
//! work (see lib.rs). The only sleep anywhere is the modelled
//! sensor-readiness wait, labelled in lib.rs.

use rolling_perception::{default_lanes, run_batched, run_rolling, RunResult, ScheduleConfig};
use std::time::Duration;

fn parse_arg(args: &[String], flag: &str) -> Option<u64> {
    args.windows(2).find(|w| w[0] == flag).and_then(|w| w[1].parse().ok())
}

fn print_result(r: &RunResult) {
    println!(
        "{:<8} ttfo={:>9.1} us  total={:>9.2} ms  outputs={:>4}  outputs/s={:>9.1}  mean_inter={:>9.1} us  p95_inter={:>9.1} us  checksum={:.4}",
        r.scheduler,
        r.time_to_first_output.as_secs_f64() * 1e6,
        r.total.as_secs_f64() * 1e3,
        r.outputs,
        r.outputs_per_sec(),
        r.mean_inter_output().as_secs_f64() * 1e6,
        r.p95_inter_output().as_secs_f64() * 1e6,
        r.checksum,
    );
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cycles = parse_arg(&args, "--cycles").unwrap_or(120) as usize;
    let stagger_us = parse_arg(&args, "--stagger-us").unwrap_or(400);

    let lanes = default_lanes();
    let cfg = ScheduleConfig { cycles, sensor_stagger: Duration::from_micros(stagger_us) };

    println!("rolling-perception bench");
    println!(
        "cycles={}  lanes/cycle={}  sensor_stagger={} us (MODELLED sensor period, sleep; not compute)",
        cycles,
        lanes.len(),
        stagger_us
    );
    print!("lanes: ");
    for (i, l) in lanes.iter().enumerate() {
        if i > 0 {
            print!(", ");
        }
        print!("{} (dim={}, repeats={})", l.name, l.dim, l.repeats);
    }
    println!("\nwork per scheduler: identical lane sequence, identical kernel, identical manifold updates");
    println!("---");

    // Run each scheduler twice and report the second (warm) run,
    // printing the first as well so nothing is hidden.
    let b1 = run_batched(&lanes, &cfg);
    let r1 = run_rolling(&lanes, &cfg);
    println!("[cold-ish first pass]");
    print_result(&b1);
    print_result(&r1);

    let b = run_batched(&lanes, &cfg);
    let r = run_rolling(&lanes, &cfg);
    println!("[reported pass]");
    print_result(&b);
    print_result(&r);
    println!("---");
    println!(
        "ttfo ratio (batched / rolling): {:.2}x",
        b.time_to_first_output.as_secs_f64() / r.time_to_first_output.as_secs_f64()
    );
    println!(
        "outputs ratio (rolling / batched): {:.1}x",
        r.outputs as f64 / b.outputs as f64
    );
    println!("checksum delta |batched - rolling|: {:.6}", (b.checksum - r.checksum).abs());
}
