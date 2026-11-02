//! trace-gen: write a deterministic v1 trace file (see the crate
//! README for the format) that `pipeline-demo --trace` can replay.
//! Usage: trace-gen [--out trace.txt] [--entries 24] [--stagger-us 400]

use rolling_pipeline::*;
use std::time::Duration;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let get = |name: &str| {
        args.windows(2).find(|w| w[0] == name).map(|w| w[1].clone())
    };
    let out = get("--out").unwrap_or_else(|| "trace.txt".to_string());
    let entries: usize = get("--entries").and_then(|v| v.parse().ok()).unwrap_or(24);
    let stagger_us: u64 = get("--stagger-us").and_then(|v| v.parse().ok()).unwrap_or(400);
    let trace = generate_trace(entries, Duration::from_micros(stagger_us));
    std::fs::write(&out, trace_to_string(&trace)).expect("cannot write trace");
    println!("wrote {} entries (stagger {} us) to {}", trace.len(), stagger_us, out);
}
