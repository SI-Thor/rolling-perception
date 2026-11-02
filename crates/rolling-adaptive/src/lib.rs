//! Lens-calibrated adaptive staggering for rolling perception.
//!
//! The sibling `rolling-perception` crate schedules its phase-interleaved
//! lanes with a **fixed** stagger: it assumes each lane's period is known
//! and exact. Real sensors are not like that. They jitter, and their
//! periods drift (temperature, clock skew, load).
//!
//! Casey's doctrine (perception notes, Oct 2026): every sensor carries a
//! **lens file** — a living self-model of the sensor (its delays, drifts,
//! deadbands, failure signatures). Perception reads the world *through*
//! the lens file, never raw; and perception improves by making the lens
//! model more accurate, not by adding channels.
//!
//! This crate is the scheduling consequence of that doctrine, tested
//! honestly and deterministically (logical clock in microseconds, no
//! wall-clock sleeps anywhere):
//!
//! * [`LensFile`] — per-lane running estimates: period (EMA), jitter
//!   (EMA variance), and the last prediction's signed phase error.
//!   Serialisable to a small `key = value` **text** format — canonical
//!   state is text, so a lens can be inspected, diffed, versioned.
//! * [`gen_trace`] — synthetic lanes with *known* ground truth (period,
//!   jitter, slow drift), deterministic seed, so a lens can be graded
//!   against reality rather than against itself.
//! * Two predictors/schedulers fed **identical traces**:
//!   [`predict_fixed`] assumes the nominal period from the trace origin
//!   forever; [`predict_adaptive`] predicts each next arrival from the
//!   lane's own [`LensFile`], updated causally (past arrivals only).
//! * An executor simulation ([`simulate`]) turns predictions into
//!   consequences: the scheduler pre-stages a lane's work to finish at
//!   its predicted arrival. Predict late and the sample waits; predict
//!   well and the run starts the moment the sample lands.
//!
//! What we expect, and measure: on jitter the fixed predictor's phase
//! error is a random walk away from the origin (it grows with sample
//! index), while the adaptive predictor's error stays ~one interval's
//! jitter because it only ever predicts one step ahead from a tracked
//! period. On drift the fixed predictor additionally accumulates the
//! drift linearly. On a perfect zero-jitter, zero-drift sensor the
//! fixed predictor is *exact* and adaptive can at best tie — we print
//! that scenario too, and say so.

use std::fmt::Write as _;

// ------------------------------------------------------------ randomness

/// Deterministic SplitMix64 PRNG (std-only stand-in for a seeded RNG).
#[derive(Debug, Clone)]
pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Self {
        Self(seed ^ 0x9E37_79B9_7F4A_7C15)
    }
    pub fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    /// Uniform in [0, 1).
    pub fn next_f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }
    /// Standard normal via Box–Muller.
    pub fn next_gaussian(&mut self) -> f64 {
        let u1 = (self.next_f64()).max(1e-12);
        let u2 = self.next_f64();
        (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
    }
}

// -------------------------------------------------------------- lens file

/// A lane's lens file: its living self-model, updated on every observed
/// arrival. All times in microseconds.
#[derive(Debug, Clone)]
pub struct LensFile {
    pub lane: String,
    /// Nominal (datasheet) period — what a fixed scheduler assumes.
    pub nominal_period_us: f64,
    /// EMA estimate of the true period.
    pub est_period_us: f64,
    /// EMA variance of the interval, µs². `jitter_std_us()` is its root.
    pub jitter_var_us2: f64,
    /// Last observed arrival time.
    pub last_arrival_us: Option<f64>,
    /// Signed error of the prediction made for the last arrival
    /// (actual − predicted). The lens remembering its own mistakes.
    pub last_phase_error_us: f64,
    /// Arrivals observed so far.
    pub observations: u64,
    /// EMA smoothing factor for period/variance updates.
    pub alpha: f64,
    /// Prediction that was outstanding for the next arrival, if any.
    pending_prediction_us: Option<f64>,
}

impl LensFile {
    pub fn new(lane: &str, nominal_period_us: f64) -> Self {
        Self {
            lane: lane.to_string(),
            nominal_period_us,
            est_period_us: nominal_period_us,
            jitter_var_us2: 0.0,
            last_arrival_us: None,
            last_phase_error_us: 0.0,
            observations: 0,
            // alpha = 0.10: endpoint std of the period estimate is
            // ~0.23 x jitter std, and the steady-state lag behind a
            // linearly drifting period is drift x (1-a)/a = 9 steps of
            // drift — both measured acceptable for our traces (see
            // tests). alpha = 0.25 was tried first and its endpoint
            // noise (~0.38 x jitter) failed the convergence tolerances.
            alpha: 0.10,
            pending_prediction_us: None,
        }
    }

    pub fn jitter_std_us(&self) -> f64 {
        self.jitter_var_us2.sqrt()
    }

    /// Predict the next arrival from the current lens state:
    /// last arrival + estimated period. (Phase-error feed-forward was
    /// tried during development; with an EMA period estimate it mostly
    /// chases jitter, so the honest predictor is period-only. The phase
    /// error is still *recorded* — it is the lens's health signal.)
    pub fn predict_next_us(&self) -> Option<f64> {
        self.last_arrival_us.map(|t| t + self.est_period_us)
    }

    /// Observe an arrival. If a prediction was outstanding for it, the
    /// signed phase error is recorded and returned. Updates the period
    /// and jitter estimates causally (this arrival only, no future data).
    pub fn observe(&mut self, arrival_us: f64) -> Option<f64> {
        self.observations += 1;
        let err = self.pending_prediction_us.map(|p| {
            self.last_phase_error_us = arrival_us - p;
            arrival_us - p
        });
        if let Some(prev) = self.last_arrival_us {
            let interval = arrival_us - prev;
            if self.observations == 2 {
                // First interval: adopt it wholesale, no jitter info yet.
                self.est_period_us = interval;
                self.jitter_var_us2 = 0.0;
            } else {
                let dev = interval - self.est_period_us;
                self.est_period_us += self.alpha * dev;
                self.jitter_var_us2 = (1.0 - self.alpha) * self.jitter_var_us2
                    + self.alpha * dev * dev;
            }
        }
        self.last_arrival_us = Some(arrival_us);
        self.pending_prediction_us = self.predict_next_us();
        err
    }

    /// Serialise to the lens-as-text format: one `key = value` per line.
    pub fn to_text(&self) -> String {
        let mut s = String::new();
        let _ = writeln!(s, "# lens file v1");
        let _ = writeln!(s, "lane = {}", self.lane);
        let _ = writeln!(s, "nominal_period_us = {:.3}", self.nominal_period_us);
        let _ = writeln!(s, "est_period_us = {:.3}", self.est_period_us);
        let _ = writeln!(s, "jitter_std_us = {:.3}", self.jitter_std_us());
        let _ = writeln!(s, "last_phase_error_us = {:.3}", self.last_phase_error_us);
        let _ = writeln!(s, "observations = {}", self.observations);
        s
    }

    /// Parse a lens file written by [`LensFile::to_text`]. Estimates are
    /// restored; transient state (last arrival, pending prediction) is
    /// not persisted — a lens loaded from text re-anchors on the next
    /// observed arrival.
    pub fn from_text(text: &str) -> Option<Self> {
        let mut lens: Option<LensFile> = None;
        let mut jitter_std = 0.0f64;
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let (k, v) = line.split_once('=')?;
            let (k, v) = (k.trim(), v.trim());
            match k {
                "lane" => {
                    lens = Some(LensFile::new(v, 0.0));
                }
                "nominal_period_us" => lens.as_mut()?.nominal_period_us = v.parse().ok()?,
                "est_period_us" => lens.as_mut()?.est_period_us = v.parse().ok()?,
                "jitter_std_us" => jitter_std = v.parse().ok()?,
                "last_phase_error_us" => {
                    lens.as_mut()?.last_phase_error_us = v.parse().ok()?
                }
                "observations" => lens.as_mut()?.observations = v.parse().ok()?,
                _ => return None,
            }
        }
        let mut lens = lens?;
        lens.jitter_var_us2 = jitter_std * jitter_std;
        Some(lens)
    }
}

// --------------------------------------------------------- trace generator

/// Ground truth for a synthetic lane. The lens never sees this; it is
/// what we grade against.
#[derive(Debug, Clone)]
pub struct LaneTruth {
    pub name: String,
    pub period_us: f64,
    pub jitter_std_us: f64,
    /// Period change per cycle (µs/cycle); slow drift.
    pub drift_us_per_cycle: f64,
    /// Absolute time of the first arrival / phase offset.
    pub phase_us: f64,
}

/// Generate `cycles` arrival times (µs) for one lane:
/// interval_k = period + drift·k + gaussian·jitter, clamped to ≥ 10% of
/// the period so intervals stay physical. Deterministic in `seed`.
pub fn gen_trace(truth: &LaneTruth, cycles: usize, seed: u64) -> Vec<f64> {
    let mut rng = Rng::new(seed);
    let mut out = Vec::with_capacity(cycles);
    let mut t = truth.phase_us;
    for k in 0..cycles {
        if k > 0 {
            let period_k = truth.period_us + truth.drift_us_per_cycle * (k as f64 - 1.0);
            let interval = (period_k + rng.next_gaussian() * truth.jitter_std_us)
                .max(0.1 * truth.period_us);
            t += interval;
        }
        out.push(t);
    }
    out
}

// -------------------------------------------------------------- predictors

/// Predictions aligned with `trace` (index k = prediction *for* arrival
/// k). Entries before a predictor can first predict are `None`.
///
/// Fixed: arrival_k ≈ first_arrival + k · nominal_period. This is the
/// sibling crate's assumption made explicit — period known, exact,
/// anchored at the origin — so both jitter and drift accumulate in its
/// phase error as k grows.
pub fn predict_fixed(trace: &[f64], nominal_period_us: f64) -> Vec<Option<f64>> {
    let origin = trace.first().copied().unwrap_or(0.0);
    (0..trace.len())
        .map(|k| {
            if k == 0 {
                None
            } else {
                Some(origin + k as f64 * nominal_period_us)
            }
        })
        .collect()
}

/// Adaptive: walk the trace causally with a [`LensFile`]; the prediction
/// for arrival k is whatever the lens said after observing arrival k−1.
pub fn predict_adaptive_named(
    trace: &[f64],
    nominal_period_us: f64,
    lane_name: &str,
) -> (Vec<Option<f64>>, LensFile) {
    let mut lens = LensFile::new(lane_name, nominal_period_us);
    let mut preds = Vec::with_capacity(trace.len());
    for (k, &t) in trace.iter().enumerate() {
        preds.push(if k == 0 { None } else { lens.predict_next_us() });
        lens.observe(t);
    }
    (preds, lens)
}

/// [`predict_adaptive_named`] with a generic lane name.
pub fn predict_adaptive(trace: &[f64], nominal_period_us: f64) -> (Vec<Option<f64>>, LensFile) {
    predict_adaptive_named(trace, nominal_period_us, "lane")
}

/// Absolute prediction errors |actual − predicted| over indices where
/// `preds` has an entry and k ≥ `warmup` (both predictors judged over
/// the same window; warmup lets the lens see its first intervals).
pub fn prediction_errors(trace: &[f64], preds: &[Option<f64>], warmup: usize) -> Vec<f64> {
    let mut errs = Vec::new();
    for (k, (&t, p)) in trace.iter().zip(preds).enumerate() {
        if k < warmup {
            continue;
        }
        if let Some(p) = p {
            errs.push((t - p).abs());
        }
    }
    errs
}

pub fn percentile(sorted: &[f64], q: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    let idx = ((sorted.len() as f64 * q).ceil() as usize).clamp(1, sorted.len()) - 1;
    sorted[idx]
}

pub fn stats(errs: &[f64]) -> (f64, f64, f64) {
    let mut s = errs.to_vec();
    s.sort_by(|a, b| a.partial_cmp(b).unwrap());
    (percentile(&s, 0.50), percentile(&s, 0.95), percentile(&s, 0.99))
}

// -------------------------------------------------------- executor simulate

/// One item of work: lane `lane`, sample index `k`, ground-truth arrival.
#[derive(Debug, Clone)]
pub struct Item {
    pub lane: usize,
    pub k: usize,
    pub arrival_us: f64,
    pub predicted_us: f64,
}

/// Executor parameters (µs).
#[derive(Debug, Clone, Copy)]
pub struct ExecParams {
    /// Pre-staging work per item, done by the lane's *own* front-end
    /// (per-lane, parallel across lanes) so it is ready at the
    /// predicted arrival.
    pub prep_us: f64,
    /// If the actual arrival is more than this long *after* the
    /// prediction, the staged prep has gone stale and must be redone
    /// on arrival (costing another `prep_us`). This is what punishes
    /// wildly-early predictions, not just late ones.
    pub prep_expiry_us: f64,
    /// Run work per item on the single shared executor (can only start
    /// once the sample has arrived *and* staging finished).
    pub run_us: f64,
    /// An output is "fresh" if it is emitted within this long of arrival.
    pub freshness_deadline_us: f64,
}

#[derive(Debug)]
pub struct SimResult {
    pub items: usize,
    /// Outputs emitted within the freshness deadline, as a percentage.
    pub fresh_pct: f64,
    /// Time from trace start (earliest arrival) to the first output.
    pub ttfo_us: f64,
    /// Mean output latency after arrival.
    pub mean_latency_us: f64,
}

/// Executor simulation, in two resource layers (a first version put
/// staging on the shared executor too; with 4 lanes x 1500 µs of work
/// per 1250 µs mean inter-arrival that queue saturates, both
/// schedulers drown identically, and nothing is measured but the
/// overload — that version is documented in README.md as a dead end):
///
/// 1. **Per-lane stager** (parallel across lanes): stages item k to be
///    ready at its predicted arrival: `stage_done = predicted` if the
///    stager is free in time. Predict late (predicted > arrival) and
///    the sample waits until `stage_done`. Predict too *early*
///    (arrival − predicted > `prep_expiry_us`) and the staged prep
///    expires: it is redone on arrival, `stage_done = arrival + prep`.
/// 2. **One shared executor**: runs items in ready order
///    (ready = max(arrival, stage_done)), `run_us` each.
///
/// Both schedulers get identical resources, identical items, identical
/// arrivals. The only difference is the predictions — which is the
/// claim under test.
pub fn simulate(mut items: Vec<Item>, params: ExecParams) -> SimResult {
    // Stage per lane, in sample order.
    items.sort_by(|a, b| {
        a.lane
            .cmp(&b.lane)
            .then(a.k.cmp(&b.k))
    });
    let mut stage_done = vec![0.0f64; items.len()];
    {
        let mut stager_free: std::collections::HashMap<usize, f64> = std::collections::HashMap::new();
        for (idx, it) in items.iter().enumerate() {
            let free_at = stager_free.get(&it.lane).copied().unwrap_or(f64::NEG_INFINITY);
            let start = (it.predicted_us - params.prep_us).max(free_at);
            let mut done = start + params.prep_us;
            if it.arrival_us - it.predicted_us > params.prep_expiry_us {
                // Staged far too early: prep expired before the sample
                // landed. Redo it on arrival.
                done = done.max(it.arrival_us) + params.prep_us;
            }
            stage_done[idx] = done;
            stager_free.insert(it.lane, done);
        }
    }
    // Run on the shared executor in ready order.
    let mut order: Vec<usize> = (0..items.len()).collect();
    order.sort_by(|&a, &b| {
        let ra = items[a].arrival_us.max(stage_done[a]);
        let rb = items[b].arrival_us.max(stage_done[b]);
        ra.partial_cmp(&rb).unwrap()
    });
    let t_start = items.iter().map(|i| i.arrival_us).fold(f64::INFINITY, f64::min);
    let mut free = f64::NEG_INFINITY;
    let mut fresh = 0usize;
    let mut lat_sum = 0.0;
    let mut first_out: Option<f64> = None;
    for &idx in &order {
        let it = &items[idx];
        let run_start = it.arrival_us.max(stage_done[idx]).max(free);
        let out = run_start + params.run_us;
        free = out;
        let lat = out - it.arrival_us;
        lat_sum += lat;
        if lat <= params.freshness_deadline_us {
            fresh += 1;
        }
        match first_out {
            None => first_out = Some(out),
            Some(f) if out < f => first_out = Some(out),
            _ => {}
        }
    }
    SimResult {
        items: items.len(),
        fresh_pct: 100.0 * fresh as f64 / items.len() as f64,
        ttfo_us: first_out.unwrap_or(0.0) - t_start,
        mean_latency_us: lat_sum / items.len() as f64,
    }
}

/// Build the item list for a set of lane traces under one predictor
/// (`fixed` or `adaptive`), sharing the same warmup rule for stats.
pub fn build_items(
    traces: &[Vec<f64>],
    nominal_period_us: f64,
    adaptive: bool,
) -> (Vec<Item>, Vec<f64>) {
    let mut items = Vec::new();
    let mut all_errs = Vec::new();
    for (lane, trace) in traces.iter().enumerate() {
        let preds = if adaptive {
            predict_adaptive(trace, nominal_period_us).0
        } else {
            predict_fixed(trace, nominal_period_us)
        };
        all_errs.extend(prediction_errors(trace, &preds, 2));
        for (k, &t) in trace.iter().enumerate() {
            // k = 0 has no prediction; stage it at its arrival (both
            // schedulers get this for free, identically).
            let predicted = preds[k].unwrap_or(t);
            items.push(Item { lane, k, arrival_us: t, predicted_us: predicted });
        }
    }
    (items, all_errs)
}

// ------------------------------------------------------------------ tests

#[cfg(test)]
mod tests {
    use super::*;

    fn drift_trace() -> (LaneTruth, Vec<f64>) {
        let truth = LaneTruth {
            name: "cam-left".into(),
            period_us: 5_000.0,
            jitter_std_us: 800.0,
            drift_us_per_cycle: 12.0,
            phase_us: 0.0,
        };
        let trace = gen_trace(&truth, 400, 0xC0FFEE);
        (truth, trace)
    }

    #[test]
    fn lens_converges_to_ground_truth_without_drift() {
        let truth = LaneTruth {
            name: "imu".into(),
            period_us: 5_000.0,
            jitter_std_us: 300.0,
            drift_us_per_cycle: 0.0,
            phase_us: 1_000.0,
        };
        let trace = gen_trace(&truth, 300, 42);
        let mut lens = LensFile::new("imu", 4_000.0); // nominal deliberately wrong
        for &t in &trace {
            lens.observe(t);
        }
        assert!(
            (lens.est_period_us - 5_000.0).abs() < 100.0,
            "est period {} not within 100us of 5000",
            lens.est_period_us
        );
        assert!(
            (lens.jitter_std_us() - 300.0).abs() < 120.0,
            "est jitter {} not near 300",
            lens.jitter_std_us()
        );
    }

    #[test]
    fn lens_tracks_slow_drift() {
        let (truth, trace) = drift_trace();
        let mut lens = LensFile::new("cam-left", truth.period_us);
        for &t in &trace {
            lens.observe(t);
        }
        // True period at the end: 5000 + 12*399 ≈ 9788. Lens must be
        // within 5% of the *current* period, nowhere near the start.
        let true_now = 5_000.0 + 12.0 * 399.0;
        assert!(
            (lens.est_period_us - true_now).abs() < 0.05 * true_now,
            "est {} vs current true {}",
            lens.est_period_us,
            true_now
        );
    }

    #[test]
    fn adaptive_prediction_p95_beats_fixed_on_jitter_and_drift() {
        let (truth, trace) = drift_trace();
        let fixed_errs = prediction_errors(&trace, &predict_fixed(&trace, truth.period_us), 2);
        let (ap, _lens) = predict_adaptive(&trace, truth.period_us);
        let adap_errs = prediction_errors(&trace, &ap, 2);
        let (_, fixed_p95, _) = stats(&fixed_errs);
        let (_, adap_p95, _) = stats(&adap_errs);
        assert!(
            adap_p95 < fixed_p95,
            "adaptive p95 {adap_p95:.0}us must beat fixed p95 {fixed_p95:.0}us"
        );
        // And by a wide margin on this trace (drift dominates fixed).
        assert!(adap_p95 < 0.5 * fixed_p95, "adap {adap_p95:.0} vs fixed {fixed_p95:.0}");
    }

    #[test]
    fn fixed_is_exact_on_a_perfect_sensor() {
        let truth = LaneTruth {
            name: "perfect".into(),
            period_us: 4_000.0,
            jitter_std_us: 0.0,
            drift_us_per_cycle: 0.0,
            phase_us: 500.0,
        };
        let trace = gen_trace(&truth, 100, 7);
        let errs = prediction_errors(&trace, &predict_fixed(&trace, 4_000.0), 2);
        assert!(errs.iter().all(|&e| e == 0.0), "fixed must be exact here");
    }

    #[test]
    fn lens_text_roundtrip() {
        let (_truth, trace) = drift_trace();
        let mut lens = LensFile::new("cam-left", 5_000.0);
        for &t in &trace[..50] {
            lens.observe(t);
        }
        let text = lens.to_text();
        let back = LensFile::from_text(&text).expect("parse");
        assert_eq!(back.lane, "cam-left");
        assert!((back.est_period_us - lens.est_period_us).abs() < 0.01);
        assert!((back.jitter_std_us() - lens.jitter_std_us()).abs() < 0.01);
        assert_eq!(back.observations, lens.observations);
        assert!(text.contains("est_period_us"));
    }

    #[test]
    fn trace_is_deterministic_and_drifts() {
        let (truth, a) = drift_trace();
        let b = gen_trace(&truth, 400, 0xC0FFEE);
        assert_eq!(a, b);
        // Last interval should be much longer than the first (drift).
        let first = a[1] - a[0];
        let last = a[399] - a[398];
        assert!(last > first + 2_000.0, "first {first:.0} last {last:.0}");
    }
}
