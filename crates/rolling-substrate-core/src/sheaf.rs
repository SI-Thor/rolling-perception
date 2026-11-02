//! Sheaf / Laplacian smoothing — Pillar 1's maths, done for real.
//!
//! ## Email claim kept
//! Local sections that disagree with their neighbours should be
//! pulled toward global consistency, and consistency should be
//! measurable. The email names the sheaf Laplacian
//! `Δ_F = D · D^T` over a cellular sheaf.
//!
//! ## Email claim fixed
//! The email's code never builds `D` or `Δ_F`. Its
//! `enforce_sheaf_constraints` is:
//! `if |v| > 10.0 { v *= 0.333 }` — a per-element clamp. A clamp knows
//! nothing about neighbours: `[100, 100, 100]` (perfectly consistent,
//! just large) gets mangled, while `[9, -9, 9, -9]` (maximally
//! inconsistent) passes untouched. That is the opposite of a
//! consistency operator.
//!
//! ## What this module actually does
//! For a graph `G = (V, E)` with scalar sections `s: V -> f64` and the
//! (unsigned) incidence matrix `D` of `G`, the graph Laplacian is
//! `L = D^T D`, and:
//!
//! * energy `E(s) = s^T L s = Σ_{(i,j)∈E} (s_i - s_j)^2 = ||D s||²`
//! * `E(s) = 0` iff `s` is constant on each connected component —
//!   i.e. iff local sections agree everywhere they overlap, which is
//!   exactly the `H^0` consistency condition the email invokes.
//! * The smoothing step `s <- s - α L s` is gradient descent on `E`,
//!   since `∇E = 2 L s`. For `0 < α < 1 / λ_max(L)` it strictly
//!   decreases `E` on any inconsistent `s`. (For line/ring graphs
//!   `λ_max ≤ 4`, so `α < 0.25` is safe; tests use `α = 0.1`.)
//!
//! `D` is never materialised as a matrix — with one scalar per node,
//! `L s` has the closed form `(L s)_i = deg(i)·s_i − Σ_{j~i} s_j`,
//! and `E` is a sum over edges. Claiming a matrix multiply here would
//! be theatre; the implicit form *is* the computation.
//!
//! General sheaf Laplacians with non-identity restriction maps are
//! out of scope and not claimed: this is the constant-sheaf case,
//! which is the case the email's prose actually describes.
//!
//! ## Allocation (2026-11-01, SHEAF-FIX — closes ARCHITECTURE D11)
//!
//! DESIGN §4 claims the sheaf step allocates nothing (pre-allocated
//! scratch); the engine book recorded that as *contradicted*:
//! `laplacian_apply` allocated a fresh `Vec<f64>` on every call, and
//! `smooth_step` inherited one allocation per step. That is now
//! closed. [`SheafGraph::laplacian_apply_into`] writes into a
//! caller-owned buffer with the *identical* accumulation order (same
//! edge order, same per-edge expressions), so its output is
//! bit-identical to the legacy path — pinned by a bitwise-equality
//! test over seeded random graphs, and an allocation-counting test
//! (`tests/sheaf_alloc.rs`) proves the into-path performs **zero**
//! allocations in steady state while the legacy path performs one
//! per call. [`SheafGraph::smooth_step_into`] is the same step with
//! caller scratch. The allocating signatures are unchanged and
//! delegate to the into-paths, so existing consumers
//! (harbor-watch, rolling-pipeline) are source- and
//! behaviour-identical. Bench: `examples/sheaf_bench.rs`.

/// A small undirected graph over section nodes, stored as an edge list.
pub struct SheafGraph {
    n: usize,
    edges: Vec<(usize, usize)>,
}

impl SheafGraph {
    /// Graph from an explicit edge list. Duplicate edges are kept and
    /// count with multiplicity (a multigraph Laplacian — `energy` and
    /// `laplacian_apply` stay mutually consistent either way).
    ///
    /// # Panics
    /// Panics if any edge has an endpoint `>= n` or is a self-loop.
    /// Both are construction-time contract violations: the indexing in
    /// `energy`/`laplacian_apply` is provably in-range precisely
    /// because this constructor rejects such edges once, up front.
    pub fn from_edges(n: usize, edges: Vec<(usize, usize)>) -> Self {
        for &(i, j) in &edges {
            assert!(i < n && j < n, "edge ({i},{j}) out of range for n={n}");
            assert!(i != j, "self-loop ({i},{i}) is meaningless here");
        }
        Self { n, edges }
    }

    /// Ring graph: 0—1—…—(n-1)—0. The neighbour structure of the
    /// substrate ring, and of a vector whose ends wrap.
    pub fn ring(n: usize) -> Self {
        assert!(n >= 3, "a ring needs at least 3 nodes");
        Self::from_edges(n, (0..n).map(|i| (i, (i + 1) % n)).collect())
    }

    /// Line graph: 0—1—…—(n-1). Neighbours in a plain vector.
    pub fn line(n: usize) -> Self {
        assert!(n >= 2, "a line needs at least 2 nodes");
        Self::from_edges(n, (0..n - 1).map(|i| (i, i + 1)).collect())
    }

    /// Number of section nodes.
    pub fn n(&self) -> usize {
        self.n
    }

    /// The edge list, as given at construction.
    pub fn edges(&self) -> &[(usize, usize)] {
        &self.edges
    }

    /// Consistency energy `E(s) = s^T L s = Σ_edges (s_i − s_j)²`.
    /// Zero iff `s` is constant on each connected component.
    ///
    /// # Panics
    /// Panics if `s.len() != self.n()` — a section of the wrong width
    /// is a caller bug, and one clear assert beats an index panic
    /// from inside the edge loop.
    pub fn energy(&self, s: &[f64]) -> f64 {
        assert_eq!(s.len(), self.n);
        self.edges
            .iter()
            .map(|&(i, j)| {
                let d = s[i] - s[j];
                d * d
            })
            .sum()
    }

    /// Apply the Laplacian into a caller-owned buffer:
    /// `(L s)_i = deg(i)·s_i − Σ_{j~i} s_j`, written to `out`.
    ///
    /// Allocation-free: zeroes `out` and accumulates in place.
    /// The accumulation order and per-edge expressions are exactly
    /// those of the original allocating implementation, so the
    /// result is bit-identical to [`Self::laplacian_apply`]
    /// (pinned by test). `out` must not alias `s`.
    ///
    /// # Panics
    /// Panics if `s.len() != self.n()` or `out.len() != self.n()`,
    /// same contract as [`Self::energy`].
    pub fn laplacian_apply_into(&self, s: &[f64], out: &mut [f64]) {
        assert_eq!(s.len(), self.n);
        assert_eq!(out.len(), self.n);
        out.fill(0.0);
        for &(i, j) in &self.edges {
            out[i] += s[i] - s[j];
            out[j] += s[j] - s[i];
        }
    }

    /// Apply the Laplacian: `(L s)_i = deg(i)·s_i − Σ_{j~i} s_j`.
    ///
    /// Allocating convenience wrapper over
    /// [`Self::laplacian_apply_into`]; identical results.
    ///
    /// # Panics
    /// Panics if `s.len() != self.n()`, same contract as
    /// [`Self::energy`].
    pub fn laplacian_apply(&self, s: &[f64]) -> Vec<f64> {
        let mut out = vec![0.0f64; self.n];
        self.laplacian_apply_into(s, &mut out);
        out
    }

    /// One gradient/projection step `s <- s − α·L s`.
    /// Returns the energy *before* the step.
    ///
    /// `alpha` is the caller's contract: energy is guaranteed to not
    /// increase only for `0 < alpha < 2 / λ_max(L)` (see the module
    /// docs; `alpha <= 1 / (2 · max_degree)` is a safe sufficient
    /// bound for any graph). Outside that range the step can increase
    /// energy or diverge — it is a step-size constant chosen by the
    /// caller, not data, so it is documented rather than checked on
    /// this per-step path.
    ///
    /// # Panics
    /// Panics if `s.len() != self.n()`, same contract as
    /// [`Self::energy`].
    pub fn smooth_step(&self, s: &mut [f64], alpha: f64) -> f64 {
        let mut scratch = vec![0.0f64; self.n];
        self.smooth_step_into(s, alpha, &mut scratch)
    }

    /// [`Self::smooth_step`] with caller-owned scratch for `L s`:
    /// the allocation-free refine step. `scratch.len()` must equal
    /// `self.n()`; its contents are overwritten. Bit-identical
    /// arithmetic to `smooth_step` (same apply, same update order).
    ///
    /// # Panics
    /// Panics if `s.len() != self.n()` or `scratch.len() != self.n()`.
    pub fn smooth_step_into(&self, s: &mut [f64], alpha: f64, scratch: &mut [f64]) -> f64 {
        assert_eq!(scratch.len(), self.n);
        let before = self.energy(s);
        self.laplacian_apply_into(s, scratch);
        for (v, g) in s.iter_mut().zip(scratch.iter()) {
            *v -= alpha * g;
        }
        before
    }

    /// `steps` smoothing steps; returns the energy trajectory,
    /// including the initial energy (length `steps + 1`).
    ///
    /// # Panics
    /// Panics if `s.len() != self.n()`, same contract as
    /// [`Self::energy`].
    pub fn smooth(&self, s: &mut [f64], alpha: f64, steps: usize) -> Vec<f64> {
        let mut traj = Vec::with_capacity(steps + 1);
        traj.push(self.energy(s));
        for _ in 0..steps {
            self.smooth_step(s, alpha);
            traj.push(self.energy(s));
        }
        traj
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn consistent_input_has_zero_energy_and_is_fixed_point() {
        let g = SheafGraph::ring(8);
        let mut s = vec![3.25f64; 8];
        assert_eq!(g.energy(&s), 0.0);
        g.smooth_step(&mut s, 0.1);
        assert!(
            s.iter().all(|&v| v == 3.25),
            "consistent state must not be mangled"
        );
    }

    #[test]
    fn clamp_counterexample_is_caught() {
        // The email's clamp would leave this untouched (|v| <= 10)
        // and mangle [100,100,100,...]. Energy does the opposite,
        // correctly on both:
        let g = SheafGraph::line(4);
        assert!(g.energy(&[9.0, -9.0, 9.0, -9.0]) > 0.0);
        assert_eq!(g.energy(&[100.0, 100.0, 100.0, 100.0]), 0.0);
    }

    #[test]
    fn energy_strictly_decreases_on_inconsistent_input() {
        let g = SheafGraph::ring(16);
        let mut s: Vec<f64> = (0..16).map(|i| ((i * 7) % 5) as f64 - 2.0).collect();
        let traj = g.smooth(&mut s, 0.1, 20);
        for w in traj.windows(2) {
            assert!(
                w[1] < w[0],
                "energy must strictly decrease: {} -> {}",
                w[0],
                w[1]
            );
        }
        assert!(
            traj[20] < traj[0] * 0.01,
            "should be near-consistent after 20 steps"
        );
    }

    #[test]
    fn smoothing_preserves_mean_on_ring() {
        // L's null space is the constants and 1^T L = 0, so the mean
        // is an invariant of the step — consistency is reached by
        // agreement, not by shrinking everything toward zero.
        let g = SheafGraph::ring(8);
        let mut s: Vec<f64> = (0..8).map(|i| i as f64).collect();
        let mean0: f64 = s.iter().sum::<f64>() / 8.0;
        g.smooth(&mut s, 0.1, 200);
        let mean1: f64 = s.iter().sum::<f64>() / 8.0;
        assert!((mean0 - mean1).abs() < 1e-9);
        assert!(g.energy(&s) < 1e-6);
    }

    #[test]
    fn laplacian_of_constant_is_zero() {
        let g = SheafGraph::line(5);
        assert!(g.laplacian_apply(&[1.0; 5]).iter().all(|&v| v == 0.0));
    }

    /// Minimal seeded LCG (std-only) for the parity test below.
    struct Lcg(u64);
    impl Lcg {
        fn next_f64(&mut self) -> f64 {
            self.0 = self
                .0
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let m = (self.0 >> 11) as f64 / (1u64 << 53) as f64;
            m * 20.0 - 10.0
        }
        fn coin(&mut self, p: f64) -> bool {
            self.next_f64() + 10.0 < p * 20.0
        }
    }

    #[test]
    fn into_path_is_bitwise_identical_to_legacy() {
        // The D11 fix must not change a single bit: same edge order,
        // same per-edge expressions. Compare bit patterns, not
        // tolerances, across seeded random graphs (incl. multigraph
        // duplicates and empty edge sets).
        for seed in 1..=60u64 {
            let mut rng = Lcg(seed.wrapping_mul(0x9E37_79B9_7F4A_7C15));
            let n = 2 + (seed as usize % 29);
            let mut edges = Vec::new();
            for i in 0..n {
                for j in (i + 1)..n {
                    if rng.coin(0.25) {
                        edges.push((i, j));
                        if rng.coin(0.2) {
                            edges.push((i, j)); // duplicate: multiplicity path
                        }
                    }
                }
            }
            let g = SheafGraph::from_edges(n, edges);
            let s: Vec<f64> = (0..n).map(|_| rng.next_f64()).collect();
            let legacy = g.laplacian_apply(&s);
            let mut into = vec![f64::NAN; n]; // poisoned: must be fully overwritten
            g.laplacian_apply_into(&s, &mut into);
            for i in 0..n {
                assert_eq!(
                    legacy[i].to_bits(),
                    into[i].to_bits(),
                    "seed {seed} node {i}: legacy {} vs into {}",
                    legacy[i],
                    into[i]
                );
            }
            // smooth_step vs smooth_step_into: identical trajectory.
            let mut a = s.clone();
            let mut b = s.clone();
            let mut scratch = vec![0.0f64; n];
            for _ in 0..10 {
                let ea = g.smooth_step(&mut a, 0.05);
                let eb = g.smooth_step_into(&mut b, 0.05, &mut scratch);
                assert_eq!(ea.to_bits(), eb.to_bits(), "seed {seed}: step energy bits");
            }
            for i in 0..n {
                assert_eq!(a[i].to_bits(), b[i].to_bits(), "seed {seed}: smoothed bits");
            }
        }
    }

    #[test]
    fn line_graph_endpoints_have_degree_one() {
        let g = SheafGraph::line(3);
        // s = [1,0,0]: (Ls)_0 = 1*(1-0) = 1, (Ls)_1 = (0-1)+(0-0) = -1
        assert_eq!(g.laplacian_apply(&[1.0, 0.0, 0.0]), vec![1.0, -1.0, 0.0]);
    }
}
