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
//!
//! Beyond the two spikes, the GPU module carries a small generic kernel
//! surface — the additions rolling-pipeline's executor seam specified
//! (its README's Composition section; ARCHITECTURE claim D13):
//! [`gpu::compile`] over the NVRTC path, `Module::load_named` for
//! arbitrary kernel names, `Module::launch_args` taking typed
//! [`KernelArg`] descriptors instead of the hardcoded perceive
//! signature, byte-level `DevBuf` copies, and `Gpu::new_stream` for
//! the two-stream shadow's second stream. The descriptors and the
//! launch-shape validation live here, not behind the feature, so
//! their encoding is unit-tested on any machine.

#![warn(missing_docs)]

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

/// Variant B kernel source: asymmetric filter (see [`KERNEL_A`] for
/// the sharing rationale).
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
    /// Symmetric 3-tap smoothing filter ([`KERNEL_A`]).
    A,
    /// Asymmetric filter ([`KERNEL_B`]) — spike 3's wrong-module
    /// detector: its output differs measurably from A's.
    B,
}

impl Variant {
    /// The CUDA source for this variant ([`KERNEL_A`] or
    /// [`KERNEL_B`]).
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

/// CPU reference for either variant — dispatches to
/// [`reference_a`] / [`reference_b`].
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

/// Max absolute difference between two equal-length slices.
///
/// Contract: the slices must have equal length. With unequal lengths
/// the comparison silently covers only the common prefix (`zip`
/// semantics) — a too-short `b` could hide an arbitrarily wrong tail.
/// Every caller in this crate compares a GPU readback against the
/// reference for the *same* `n`, so the lengths are equal by
/// construction; the `debug_assert` pins that in debug builds, and
/// the property tests pin the equal-length behaviour.
pub fn max_abs_err(a: &[f32], b: &[f32]) -> f32 {
    debug_assert_eq!(
        a.len(),
        b.len(),
        "max_abs_err compares a common prefix only — lengths must match"
    );
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).abs())
        .fold(0.0f32, f32::max)
}

/// One typed kernel argument for `gpu::Module::launch_args`.
///
/// The driver API takes a `void**` whose elements point at each
/// argument's *value*; a raw pointer array at the call site (the
/// shape the generic launch was first specified in) makes the
/// argument list's types and lifetimes invisible to the compiler.
/// This descriptor keeps them visible: each variant *is* the value
/// the driver will read, and `launch_args` materialises owned
/// storage for the whole list before building the pointer array.
///
/// Deliberately not feature-gated: the encoding below is pure CPU
/// work and is unit-tested on machines with no GPU.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum KernelArg {
    /// A device pointer (`CUdeviceptr`), passed by value as the
    /// kernel's pointer parameter. Build one from a live buffer with
    /// `KernelArg::from_devbuf` (in the `gpu` module) — a raw `u64`
    /// here is the caller's claim that it names a live allocation,
    /// which is part of `launch_args`' safety contract.
    DevPtr(u64),
    /// A 32-bit float, passed by value.
    F32(f32),
    /// A 64-bit float, passed by value.
    F64(f64),
    /// A 32-bit signed integer, passed by value.
    I32(i32),
    /// A 64-bit signed integer, passed by value.
    I64(i64),
    /// A 32-bit unsigned integer, passed by value.
    U32(u32),
    /// A 64-bit unsigned integer, passed by value.
    U64(u64),
}

impl KernelArg {
    /// Size in bytes of the value the driver reads for this
    /// argument: 8 for a device pointer and the 64-bit scalars,
    /// 4 for the 32-bit scalars.
    pub fn size(&self) -> usize {
        match self {
            KernelArg::DevPtr(_) | KernelArg::F64(_) | KernelArg::I64(_) | KernelArg::U64(_) => 8,
            KernelArg::F32(_) | KernelArg::I32(_) | KernelArg::U32(_) => 4,
        }
    }

    /// Write the value's bytes into `dst` in little-endian order
    /// (every host this crate targets — x86_64, aarch64 — is
    /// little-endian, and the device shares the host's order for
    /// scalar kernel arguments) and return the number of bytes
    /// written, which is [`Self::size`]. Bytes of `dst` beyond the
    /// value are left untouched.
    ///
    /// # Panics
    /// Panics if `dst` is shorter than [`Self::size`] — same
    /// contract shape as `copy_from_slice`: a too-small destination
    /// for a fixed-size value is a caller bug, stated once here
    /// rather than checked at every call.
    pub fn write_into(&self, dst: &mut [u8]) -> usize {
        let n = self.size();
        assert!(
            dst.len() >= n,
            "KernelArg::write_into needs {n} B, dst has {} B",
            dst.len()
        );
        match self {
            KernelArg::DevPtr(v) => dst[..8].copy_from_slice(&v.to_le_bytes()),
            KernelArg::F32(v) => dst[..4].copy_from_slice(&v.to_le_bytes()),
            KernelArg::F64(v) => dst[..8].copy_from_slice(&v.to_le_bytes()),
            KernelArg::I32(v) => dst[..4].copy_from_slice(&v.to_le_bytes()),
            KernelArg::I64(v) => dst[..8].copy_from_slice(&v.to_le_bytes()),
            KernelArg::U32(v) => dst[..4].copy_from_slice(&v.to_le_bytes()),
            KernelArg::U64(v) => dst[..8].copy_from_slice(&v.to_le_bytes()),
        }
        n
    }
}

/// Launch-shape validation shared by `gpu::Module::launch_args`
/// (which calls it before any FFI) and this crate's unit tests.
/// The checks are the driver's own limits, stated as typed errors
/// here so a malformed configuration is rejected identically on
/// every machine: every grid and block dimension at least 1, grid
/// y/z at most 65535 (`cuLaunchKernel`'s documented caps), and the
/// block's total thread count at most 1024. Gated to its two
/// consumers — without the feature and outside tests it would be
/// dead code, and this crate does not carry allows for that.
#[cfg(any(feature = "cuda-thor", test))]
fn check_launch_dims(grid: (u32, u32, u32), block: (u32, u32, u32)) -> Result<(), String> {
    if grid.0 == 0 || grid.1 == 0 || grid.2 == 0 {
        return Err(format!("launch grid dims must all be >= 1, got {grid:?}"));
    }
    if grid.1 > 65535 || grid.2 > 65535 {
        return Err(format!("launch grid y/z must be <= 65535, got {grid:?}"));
    }
    if block.0 == 0 || block.1 == 0 || block.2 == 0 {
        return Err(format!("launch block dims must all be >= 1, got {block:?}"));
    }
    let threads = block.0 as u64 * block.1 as u64 * block.2 as u64;
    if threads > 1024 {
        return Err(format!(
            "launch block {block:?} has {threads} threads, over the 1024 cap"
        ));
    }
    Ok(())
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

    #[test]
    fn kernel_arg_sizes_match_the_value_types() {
        // These sizes are what cuLaunchKernel reads through the
        // pointer array; a drift here corrupts every argument after
        // it, so they are pinned exactly, not approximately.
        assert_eq!(KernelArg::DevPtr(0).size(), 8);
        assert_eq!(KernelArg::F32(0.0).size(), 4);
        assert_eq!(KernelArg::F64(0.0).size(), 8);
        assert_eq!(KernelArg::I32(0).size(), 4);
        assert_eq!(KernelArg::I64(0).size(), 8);
        assert_eq!(KernelArg::U32(0).size(), 4);
        assert_eq!(KernelArg::U64(0).size(), 8);
    }

    #[test]
    fn kernel_arg_encoding_is_the_value_bytes_little_endian() {
        // One representative per variant; the expected bytes are
        // computed independently via to_le_bytes on the raw value
        // (for the floats, on their bit patterns). Only the first
        // size() bytes of each expectation are compared below, so
        // the 4-byte expectations are zero-padded to the array size.
        fn pad4(b: [u8; 4]) -> [u8; 8] {
            let mut o = [0u8; 8];
            o[..4].copy_from_slice(&b);
            o
        }
        let cases: [(KernelArg, [u8; 8]); 7] = [
            (
                KernelArg::DevPtr(0x1122_3344_5566_7788),
                0x1122_3344_5566_7788u64.to_le_bytes(),
            ),
            (
                KernelArg::F32(-0.5),
                pad4((-0.5f32).to_bits().to_le_bytes()),
            ),
            (KernelArg::F64(1.5), 1.5f64.to_bits().to_le_bytes()),
            (KernelArg::I32(-2), pad4((-2i32).to_le_bytes())),
            (KernelArg::I64(-3), (-3i64).to_le_bytes()),
            (
                KernelArg::U32(0xDEAD_BEEF),
                pad4(0xDEAD_BEEFu32.to_le_bytes()),
            ),
            (KernelArg::U64(42), 42u64.to_le_bytes()),
        ];
        // write_into must produce exactly size() bytes and leave
        // the rest of the destination untouched, so compare the
        // written prefix against the expectation and the tail
        // against a sentinel.
        for (arg, expect_full) in cases {
            let mut buf = [0xAAu8; 8];
            let n = arg.write_into(&mut buf);
            assert_eq!(n, arg.size(), "{arg:?}");
            assert_eq!(&buf[..n], &expect_full[..n], "{arg:?}");
            assert!(
                buf[n..].iter().all(|&b| b == 0xAA),
                "{arg:?} wrote past its size"
            );
        }
    }

    #[test]
    #[should_panic(expected = "write_into needs 8 B")]
    fn kernel_arg_write_into_rejects_a_short_buffer() {
        let mut buf = [0u8; 4];
        KernelArg::F64(1.0).write_into(&mut buf);
    }

    #[test]
    fn launch_dims_validation_accepts_real_shapes_and_rejects_bad_ones() {
        // Shapes the crate itself launches, plus the exact caps.
        assert!(check_launch_dims((1, 1, 1), (256, 1, 1)).is_ok());
        assert!(check_launch_dims((4, 1, 1), (1024, 1, 1)).is_ok());
        assert!(check_launch_dims((1, 65535, 65535), (32, 32, 1)).is_ok());
        // Error paths: each rejected shape names its own failure.
        assert!(check_launch_dims((0, 1, 1), (256, 1, 1))
            .unwrap_err()
            .contains("grid dims"));
        assert!(check_launch_dims((1, 65536, 1), (256, 1, 1))
            .unwrap_err()
            .contains("grid y/z"));
        assert!(check_launch_dims((1, 1, 1), (0, 1, 1))
            .unwrap_err()
            .contains("block dims"));
        assert!(check_launch_dims((1, 1, 1), (1025, 1, 1))
            .unwrap_err()
            .contains("1024 cap"));
        assert!(check_launch_dims((1, 1, 1), (33, 32, 1))
            .unwrap_err()
            .contains("1024 cap"));
    }
}
