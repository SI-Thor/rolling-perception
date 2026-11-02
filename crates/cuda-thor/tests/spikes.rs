//! GPU spike tests — `#[ignore]`d AND feature-gated, so plain
//! `cargo test` (any machine, no CUDA) exercises only the CPU reference,
//! and `cargo test --features cuda-thor` without `-- --ignored` still does
//! not touch the GPU. Run on the Thor with:
//!   cargo test --release --features cuda-thor -- --ignored --nocapture

#[cfg(feature = "cuda-thor")]
use cuda_thor::{gpu, TOL};

#[test]
#[ignore = "needs the Thor GPU"]
#[cfg(feature = "cuda-thor")]
fn spike1_nvrtc_compute110_matches_cpu_reference() {
    let r = gpu::spike1().expect("spike 1 must run on the Thor");
    assert!(
        r.ok_within_tol,
        "GPU vs CPU reference max_err {} exceeds stated tol {}",
        r.max_err, TOL
    );
    // The control result is recorded, not asserted: PTX forward-compat is
    // allowed to succeed; a native sm_100 CUBIN succeeding on sm_110 would
    // be a surprise worth reading in the report either way.
    println!("sm_100 CUBIN load control: {}", r.control_sm100_cubin_load);
    println!(
        "compute_100 PTX control: compile={} run={}",
        r.control_compute100_ptx_compile, r.control_compute100_ptx_load_and_run
    );
}

#[test]
#[ignore = "needs the Thor GPU"]
#[cfg(feature = "cuda-thor")]
fn spike3_thousand_swaps_epoch_retirement_no_leak() {
    // Warm-up run first: the driver's unified-memory pools on this shared
    // box fluctuate by ±150 MB between samples (measured 2026-11-01:
    // consecutive in-process runs of 100/500/1000/100 swaps reported
    // deltas of +74.7 MB, +6.4 MB, −139.7 MB, −10.1 MB, with net ≈ +24 MB
    // across all 2,700 swaps — pool noise, not a per-swap slope). A leak
    // gate tighter than the instrument's noise would be theatre, so:
    //   * exactness is asserted STRUCTURALLY (loads == unloads == 1000,
    //     every epoch verified), and
    //   * the memory gate is set by arithmetic: the CUBIN is ~2–4 KB, so
    //     even a pathological 384 KB-per-swap leak is what −384 MB over
    //     1,000 swaps would mean. Anything at or above that is a leak;
    //     below it is indistinguishable from this box's pool noise.
    let warm = gpu::spike3(200).expect("warm-up spike 3 must run");
    assert_eq!(warm.retirements, 200);
    let r = gpu::spike3(1000).expect("spike 3 must run on the Thor");
    assert_eq!(r.epochs_verified, 1000, "every epoch must be verified");
    assert!(
        r.all_within_tol,
        "max_err {} exceeds tol {}",
        r.max_err, TOL
    );
    assert_eq!(
        r.retirements, 1000,
        "every module must be retired exactly once"
    );
    assert!(
        r.free_delta_bytes > -(384 * 1024 * 1024),
        "possible module leak beyond instrument noise: free memory delta {} B over 1000 swaps",
        r.free_delta_bytes
    );
    println!(
        "spike3 measured run: delta {:+} B over 1000 swaps (warm-up delta {:+} B over 200)",
        r.free_delta_bytes, warm.free_delta_bytes
    );
}
