//! Spike runner: `cargo run --release --features cuda-thor --bin spikes`
//! On the Thor this prints the spike 1 + spike 3 report (the same values
//! the #[ignore]d GPU tests assert). Without the feature it says so and
//! exits 0 — it never pretends to have touched a GPU it did not touch.

#[cfg(feature = "cuda-thor")]
fn main() {
    use cuda_thor::gpu;
    println!("== Spike 1: NVRTC correctness (compute_110) ==");
    match gpu::spike1() {
        Ok(r) => {
            println!("nvrtc version: {}.{}", r.nvrtc_version.0, r.nvrtc_version.1);
            println!(
                "compile -arch=compute_110: {:.1} ms, PTX {} B",
                r.compile_110_ms, r.ptx_bytes
            );
            println!("cuModuleLoadData (PTX): {:.2} ms", r.load_110_ms);
            println!(
                "max_err vs CPU reference: {:.3e}  within tol ({}): {}",
                r.max_err,
                cuda_thor::TOL,
                r.ok_within_tol
            );
            println!(
                "CONTROL compute_100 PTX compile: {}",
                r.control_compute100_ptx_compile
            );
            println!(
                "CONTROL compute_100 PTX load+run: {}",
                r.control_compute100_ptx_load_and_run
            );
            println!(
                "CONTROL sm_100 CUBIN compile: {}",
                r.control_sm100_cubin_compile
            );
            println!("CONTROL sm_100 CUBIN load: {}", r.control_sm100_cubin_load);
            if !r.ok_within_tol {
                std::process::exit(2);
            }
        }
        Err(e) => {
            println!("SPIKE 1 FAILED: {e}");
            std::process::exit(1);
        }
    }
    println!();
    println!("== Spike 3: 1,000 module swaps with epoch retirement ==");
    match gpu::spike3(1000) {
        Ok(r) => {
            println!(
                "swaps: {}  launches/epoch: {}",
                r.swaps, r.launches_per_epoch
            );
            println!(
                "epochs verified: {}  max_err: {:.3e}  all within tol: {}",
                r.epochs_verified, r.max_err, r.all_within_tol
            );
            println!(
                "compile (once per variant, sm_110 CUBIN): A {:.1} ms, B {:.1} ms",
                r.compile_ms_per_variant.0, r.compile_ms_per_variant.1
            );
            println!("mean module load: {:.3} ms", r.mean_load_ms);
            println!(
                "retirements: {} (event already complete at retirement check: {})",
                r.retirements, r.retirements_where_event_already_done
            );
            println!(
                "cuMemGetInfo free: before {} B, after {} B, delta {:+} B ({:+.2} MiB)",
                r.free_before_bytes,
                r.free_after_bytes,
                r.free_delta_bytes,
                r.free_delta_bytes as f64 / 1_048_576.0
            );
            println!("wall: {:.1} s", r.wall.as_secs_f64());
            if !r.all_within_tol || r.epochs_verified != r.swaps {
                std::process::exit(2);
            }
        }
        Err(e) => {
            println!("SPIKE 3 FAILED: {e}");
            std::process::exit(1);
        }
    }
}

#[cfg(not(feature = "cuda-thor"))]
fn main() {
    println!("cuda-thor feature is OFF: no GPU was touched. Rebuild with --features cuda-thor on the Thor.");
}
