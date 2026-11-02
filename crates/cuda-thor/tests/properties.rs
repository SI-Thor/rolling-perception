//! Randomised invariant (property) tests for the CPU side of
//! cuda-thor. Std-only, hand-rolled: the generator is the crate's own
//! LCG family (the constants in `cuda_thor::test_input`), re-seeded
//! per round so failures reproduce from the seed in the message.
//!
//! The GPU tests stay feature-gated and `#[ignore]`d in `spikes.rs`;
//! everything here is the CPU reference, which is the part the GPU
//! results are judged against — so it gets judged against a naive
//! f64 stencil written directly from the kernel text, not against
//! itself.

use cuda_thor::{max_abs_err, reference, reference_a, reference_b, test_input, Variant};

/// The crate LCG (same constants as `test_input`), seedable.
struct Rng(u32);

impl Rng {
    fn new(seed: u32) -> Self {
        Rng(seed | 1)
    }
    fn next_u32(&mut self) -> u32 {
        self.0 = self.0.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
        self.0
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next_u32() as usize) % n
    }
    fn f32_unit(&mut self) -> f32 {
        ((self.next_u32() >> 9) as f32 / (1u32 << 23) as f32) - 1.0
    }
    fn input(&mut self, n: usize) -> Vec<f32> {
        (0..n).map(|_| self.f32_unit()).collect()
    }
}

/// Naive variant A, from the kernel text, in f64 with isize index
/// math: clamped neighbours, same coefficients.
fn naive_a(input: &[f32]) -> Vec<f64> {
    let n = input.len() as isize;
    (0..n)
        .map(|i| {
            let lo = (i - 1).max(0) as usize;
            let hi = (i + 1).min(n - 1) as usize;
            0.25 * input[lo] as f64 + 0.5 * input[i as usize] as f64 + 0.25 * input[hi] as f64
        })
        .collect()
}

/// Naive variant B, same construction.
fn naive_b(input: &[f32]) -> Vec<f64> {
    let n = input.len() as isize;
    (0..n)
        .map(|i| {
            let lo = (i - 1).max(0) as usize;
            1.5 * input[i as usize] as f64 - 0.5 * input[lo] as f64 + 0.125
        })
        .collect()
}

#[test]
fn references_match_naive_f64_stencil() {
    for seed in 1..=25u32 {
        let mut rng = Rng::new(seed.wrapping_mul(0x9E37_79B9));
        for &n in &[0usize, 1, 2, 3, 17, 256] {
            let input = rng.input(n);
            for (got, want, name) in [
                (reference_a(&input), naive_a(&input), "A"),
                (reference_b(&input), naive_b(&input), "B"),
            ] {
                assert_eq!(got.len(), want.len(), "seed {seed} n {n} variant {name}");
                for i in 0..n {
                    let err = (got[i] as f64 - want[i]).abs();
                    assert!(
                        err <= 1e-5,
                        "seed {seed} n {n} variant {name} i {i}: {err} exceeds f32-vs-f64 slack"
                    );
                }
            }
        }
        // One large random size per seed.
        let n = 1000 + rng.below(3000);
        let input = rng.input(n);
        let err_a = max_abs_err(
            &reference_a(&input),
            &naive_a(&input)
                .iter()
                .map(|&v| v as f32)
                .collect::<Vec<_>>(),
        );
        assert!(err_a <= 1e-5, "seed {seed} n {n}: variant A err {err_a}");
    }
}

#[test]
fn reference_dispatch_matches_direct_functions() {
    for seed in 1..=10u32 {
        let mut rng = Rng::new(seed.wrapping_mul(0x85EB_CA6B));
        let n = rng.below(600);
        let input = rng.input(n);
        // Dispatch is the same code path, so equality is exact — the
        // property is that it stays that way.
        assert_eq!(
            reference(Variant::A, &input),
            reference_a(&input),
            "seed {seed}"
        );
        assert_eq!(
            reference(Variant::B, &input),
            reference_b(&input),
            "seed {seed}"
        );
    }
}

#[test]
fn variants_stay_measurably_different_on_random_inputs() {
    // Spike 3's stale-module detection rests on this: if A and B ever
    // agreed on realistic inputs, a wrong-module swap would pass
    // verification silently.
    for seed in 1..=15u32 {
        let mut rng = Rng::new(seed.wrapping_mul(0xC2B2_AE35));
        let input = rng.input(256);
        let d = max_abs_err(&reference_a(&input), &reference_b(&input));
        assert!(d > 1e-3, "seed {seed}: variants suspiciously close ({d})");
    }
}

#[test]
fn max_abs_err_metric_properties() {
    for seed in 1..=15u32 {
        let mut rng = Rng::new(seed.wrapping_mul(0x27D4_EB2F));
        let n = rng.below(500);
        let a = rng.input(n);
        let b = rng.input(n);
        assert_eq!(
            max_abs_err(&a, &a),
            0.0,
            "seed {seed}: self-error must be 0"
        );
        assert_eq!(
            max_abs_err(&a, &b),
            max_abs_err(&b, &a),
            "seed {seed}: symmetry"
        );
        // A constant offset shows up as the offset (to f32 rounding).
        let shifted: Vec<f32> = a.iter().map(|&v| v + 0.5).collect();
        let err = max_abs_err(&a, &shifted);
        assert!((err - 0.5).abs() <= 1e-6, "seed {seed}: offset err {err}");
        // Triangle-style bound against a third vector.
        let c = rng.input(n);
        assert!(
            max_abs_err(&a, &c) <= max_abs_err(&a, &b) + max_abs_err(&b, &c) + 1e-6,
            "seed {seed}: triangle bound"
        );
    }
}

#[test]
fn test_input_is_deterministic_prefixed_and_in_range() {
    // Determinism across calls.
    assert_eq!(test_input(1024), test_input(1024));
    // Prefix property: the generator is a stream, so asking for more
    // must not change the beginning — spike code relies on comparing
    // runs at different n.
    let big = test_input(4096);
    for &k in &[0usize, 1, 63, 1024] {
        assert_eq!(&big[..k], &test_input(k)[..], "prefix at {k}");
    }
    // Range: ((state >> 9) / 2^23) - 1 lies in [-1, 1).
    assert!(big.iter().all(|&v| (-1.0..1.0).contains(&v)));
    // Empty is empty.
    assert!(test_input(0).is_empty());
}
