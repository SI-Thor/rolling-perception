//! `cuda-thor` — v0.2 Spikes 1 + 3 for SI-Thor/rolling-perception (PLAN §6).
//!
//! * **Spike 1 — NVRTC correctness.** Compile the perceive-filter kernel at
//!   runtime via NVRTC for `-arch=compute_110` (the Thor's real target,
//!   capability 11.0), load it through the driver API, run it, and compare
//!   against the CPU reference in this crate. The seed email's `sm_100`
//!   family is run as a known-wrong control and its behaviour recorded.
//! * **Spike 3 — host-side swap with epoch retirement.** Swap the loaded
//!   module *between* launches only. A retired module is unloaded only after
//!   an event recorded after its last launch has completed. 1,000 swaps
//!   under load, every output reference-checked, driver memory accounted.
//!
//! The GPU half exists only under `--features cuda-thor` and is Thor-only
//! (thin direct FFI to `libcuda` + `libnvrtc`; no cudarc — FEASIBILITY §6).
//! Without the feature this crate is the CPU reference and its tests, and
//! builds anywhere.

/// Perceive-filter kernel source, shared verbatim by the CPU reference and
/// the NVRTC compile so the two cannot drift apart semantically.
/// Variant A: symmetric 3-tap smoothing filter.
/// Variant B: asymmetric filter — spike 3 alternates A/B so a stale module
/// would produce measurably wrong output, not silently similar output.
pub const KERNEL_A: &str = r#"
extern "C" __global__ void perceive(const float* __restrict__ in, float* __restrict__ out, int n){
    int i = blockIdx.x*blockDim.x + threadIdx.x;
    if(i>=n) return;
    int lo = i>0 ? i-1 : 0;
    int hi = i<n-1 ? i+1 : n-1;
    out[i] = 0.25f*in[lo] + 0.5f*in[i] + 0.25f*in[hi];
}"#;

pub const KERNEL_B: &str = r#"
extern "C" __global__ void perceive(const float* __restrict__ in, float* __restrict__ out, int n){
    int i = blockIdx.x*blockDim.x + threadIdx.x;
    if(i>=n) return;
    int lo = i>0 ? i-1 : 0;
    out[i] = 1.5f*in[i] - 0.5f*in[lo] + 0.125f;
}"#;

/// Which kernel variant a module was compiled from.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Variant {
    A,
    B,
}

impl Variant {
    pub fn source(&self) -> &'static str {
        match self {
            Variant::A => KERNEL_A,
            Variant::B => KERNEL_B,
        }
    }
}

/// CPU reference for variant A. Same expression order as the CUDA source;
/// any FMA-contraction difference on the GPU side is absorbed by the stated
/// tolerance in the spike checks (see `TOL`).
pub fn reference_a(input: &[f32]) -> Vec<f32> {
    let n = input.len();
    let mut out = vec![0.0f32; n];
    for i in 0..n {
        let lo = if i > 0 { i - 1 } else { 0 };
        let hi = if i + 1 < n { i + 1 } else { n - 1 };
        out[i] = 0.25 * input[lo] + 0.5 * input[i] + 0.25 * input[hi];
    }
    out
}

/// CPU reference for variant B.
pub fn reference_b(input: &[f32]) -> Vec<f32> {
    let n = input.len();
    let mut out = vec![0.0f32; n];
    for i in 0..n {
        let lo = if i > 0 { i - 1 } else { 0 };
        out[i] = 1.5 * input[i] - 0.5 * input[lo] + 0.125;
    }
    out
}

pub fn reference(variant: Variant, input: &[f32]) -> Vec<f32> {
    match variant {
        Variant::A => reference_a(input),
        Variant::B => reference_b(input),
    }
}

/// Stated FP tolerance for GPU-vs-CPU comparison (PLAN §6 spike 1 allows
/// "bit-for-bit or within a stated FP tolerance" — this is the statement).
/// Sources of divergence: GPU FMA contraction in the 3-term sums. Inputs are
/// O(1), coefficients O(1), so absolute 1e-5 is generous but honest; spikes
/// also report the *observed* max error, which is the real evidence.
pub const TOL: f32 = 1e-5;

/// Deterministic test input (small LCG; no external crates, reproducible
/// on every machine — same generator family as the v0.1 crates).
pub fn test_input(n: usize) -> Vec<f32> {
    let mut state: u32 = 0x1234_5678;
    (0..n)
        .map(|_| {
            state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            ((state >> 9) as f32 / (1u32 << 23) as f32) - 1.0
        })
        .collect()
}

/// Max absolute difference between two slices (0 if lengths differ is
/// treated as infinite error by callers checking lengths first).
pub fn max_abs_err(a: &[f32], b: &[f32]) -> f32 {
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).abs())
        .fold(0.0f32, f32::max)
}

#[cfg(feature = "cuda-thor")]
pub mod gpu;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_a_endpoints_use_clamped_neighbours() {
        let inp = vec![1.0, 2.0, 4.0];
        let out = reference_a(&inp);
        // i=0: 0.25*in[0] + 0.5*in[0] + 0.25*in[1] = 0.25+0.5+0.5
        assert!((out[0] - 1.25).abs() < 1e-7);
        // i=2: 0.25*in[1] + 0.5*in[2] + 0.25*in[2] = 0.5+2+1
        assert!((out[2] - 3.5).abs() < 1e-7);
    }

    #[test]
    fn variants_actually_differ() {
        // Spike 3's correctness check is meaningless if A and B agree.
        let inp = test_input(1024);
        let d = max_abs_err(&reference_a(&inp), &reference_b(&inp));
        assert!(d > 0.1, "variants too similar: max diff {d}");
    }

    #[test]
    fn test_input_is_deterministic() {
        assert_eq!(test_input(64), test_input(64));
    }
}
