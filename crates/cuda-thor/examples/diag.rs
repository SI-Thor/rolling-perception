//! Diagnostic: is the spike-3 free-memory drop linear in swaps (leak) or
//! a one-off driver cache that saturates / is reclaimed at context release?
#[cfg(feature = "cuda-thor")]
fn main() {
    use cuda_thor::gpu;
    for swaps in [100usize, 500, 1000, 100] {
        match gpu::spike3(swaps) {
            Ok(r) => println!(
                "spike3({:4}) verified={} ok={} max_err={:.1e} retire={} free_before={} free_after={} delta={:+} B ({:+.1} KiB/swap) wall={:.1}s",
                swaps, r.epochs_verified, r.all_within_tol, r.max_err, r.retirements,
                r.free_before_bytes, r.free_after_bytes, r.free_delta_bytes,
                (r.free_delta_bytes as f64 / swaps as f64) / 1024.0, r.wall.as_secs_f64()
            ),
            Err(e) => println!("spike3({swaps}) ERROR {e}"),
        }
    }
}
#[cfg(not(feature = "cuda-thor"))]
fn main() { println!("feature off"); }
