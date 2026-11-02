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

    /// Apply the Laplacian: `(L s)_i = deg(i)·s_i − Σ_{j~i} s_j`.
    ///
    /// # Panics
    /// Panics if `s.len() != self.n()`, same contract as
    /// [`Self::energy`].
    pub fn laplacian_apply(&self, s: &[f64]) -> Vec<f64> {
        assert_eq!(s.len(), self.n);
        let mut out = vec![0.0f64; self.n];
        for &(i, j) in &self.edges {
            out[i] += s[i] - s[j];
            out[j] += s[j] - s[i];
        }
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
        let before = self.energy(s);
        let ls = self.laplacian_apply(s);
        for (v, g) in s.iter_mut().zip(ls.iter()) {
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

    #[test]
    fn line_graph_endpoints_have_degree_one() {
        let g = SheafGraph::line(3);
        // s = [1,0,0]: (Ls)_0 = 1*(1-0) = 1, (Ls)_1 = (0-1)+(0-0) = -1
        assert_eq!(g.laplacian_apply(&[1.0, 0.0, 0.0]), vec![1.0, -1.0, 0.0]);
    }
}
