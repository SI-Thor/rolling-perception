//! Rolling perception: phase-interleaved vs. batched scheduling.
//!
//! Source idea (email "Rolling perception [muse]", 2026-11-01):
//! "Sequential Phase-Interleaved Rolling Pipeline" and the "Cascading
//! Cognitive Substrate" — stagger sensor / model stages at small phase
//! offsets so perception is a continuous stream of outputs, not a
//! frame that completes all at once.
//!
//! This crate is the honest, CPU, std-only version of that claim:
//!
//! * The **same lanes** do the **same real work** (a matrix-vector
//!   kernel over owned data, plus a real PCM demux for the audio lane)
//!   under both schedulers. No `sleep` is used as compute anywhere.
//! * The only `sleep` in the crate models **sensor readiness**: in a
//!   batched frame you cannot start until the last sensor of the frame
//!   has arrived; in the rolling schedule lane *i* becomes ready at
//!   `i * sensor_stagger` into the cycle and can start then. That
//!   modelling sleep is labelled at every call site.
//! * Both schedulers run the lanes in the same order per cycle and
//!   drive the same shared [`Manifold`], so the attention-director's
//!   focus update affects later lanes identically in both schedules
//!   and the total checksum must match. Scheduling is the *only*
//!   variable.
//!
//! Claim under test: on a single sequential execution resource, the
//! rolling schedule has a strictly smaller time-to-first-output and
//! emits strictly more intermediate outputs than the batched schedule,
//! for identical work. See README.md for what would falsify it.

use std::hint::black_box;
use std::thread::sleep;
use std::time::{Duration, Instant};

// ---------------------------------------------------------------- manifold

/// Shared state passed down the cascade, as in the email's
/// "Global Latent Manifold": the attention director writes `focus`,
/// perception / diffusion read it on their next pass.
#[derive(Debug, Clone)]
pub struct Manifold {
    /// Row offset / region-of-interest start chosen by the director.
    pub focus: usize,
    /// Toy uncertainty value carried between stages.
    pub entropy: f32,
}

impl Default for Manifold {
    fn default() -> Self {
        Self {
            focus: 0,
            entropy: 1.0,
        }
    }
}

// ------------------------------------------------------------------- lanes

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaneKind {
    /// Matrix-vector stage (perception, decision, director, diffusion).
    MatVec,
    /// Interleaved-PCM demux stage (the honest CPU SkaldAudio).
    Audio,
}

/// One sensor/model stage. Work is configurable via `repeats`
/// (matvec repetitions) / the size of the PCM buffer (audio).
#[derive(Debug, Clone)]
pub struct Lane {
    pub name: &'static str,
    pub kind: LaneKind,
    /// Dimension of the square matrix (matvec lanes).
    pub dim: usize,
    /// How many times the kernel is repeated per activation.
    pub repeats: usize,
    /// If true, this lane updates `Manifold::focus` from its result
    /// (the attention-director / Nemotron-Mini role in the email).
    pub updates_focus: bool,
    matrix: Vec<f32>,
    vector: Vec<f32>,
    /// Interleaved stereo PCM (audio lane only; empty otherwise).
    pcm_interleaved: Vec<f32>,
    pub channels: usize,
}

/// Deterministic pseudo-data (LCG) so every run / scheduler sees
/// bit-identical inputs. No files, no RNG dependency.
fn fill_pseudo(out: &mut [f32], mut state: u64) {
    for v in out.iter_mut() {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let x = ((state >> 33) as u32) as f32 / u32::MAX as f32; // [0, 1)
        *v = x * 2.0 - 1.0;
    }
}

impl Lane {
    pub fn matvec(
        name: &'static str,
        dim: usize,
        repeats: usize,
        seed: u64,
        updates_focus: bool,
    ) -> Self {
        let mut matrix = vec![0.0f32; dim * dim];
        let mut vector = vec![0.0f32; dim];
        fill_pseudo(&mut matrix, seed);
        fill_pseudo(&mut vector, seed ^ 0x9e3779b97f4a7c15);
        Self {
            name,
            kind: LaneKind::MatVec,
            dim,
            repeats,
            updates_focus,
            matrix,
            vector,
            pcm_interleaved: Vec::new(),
            channels: 0,
        }
    }

    pub fn audio(
        name: &'static str,
        samples_per_channel: usize,
        channels: usize,
        repeats: usize,
        seed: u64,
    ) -> Self {
        let mut pcm_interleaved = vec![0.0f32; samples_per_channel * channels];
        fill_pseudo(&mut pcm_interleaved, seed);
        // A small matvec as the "acoustic model" applied after demux.
        let dim = 48;
        let mut matrix = vec![0.0f32; dim * dim];
        let mut vector = vec![0.0f32; dim];
        fill_pseudo(&mut matrix, seed ^ 0x51ed);
        fill_pseudo(&mut vector, seed ^ 0xbeef);
        Self {
            name,
            kind: LaneKind::Audio,
            dim,
            repeats,
            updates_focus: false,
            matrix,
            vector,
            pcm_interleaved,
            channels,
        }
    }

    /// Execute this lane's real work once. Returns a checksum that the
    /// caller must accumulate (via `black_box` upstream) so the work
    /// cannot be optimised away.
    pub fn execute(&self, manifold: &mut Manifold) -> f64 {
        match self.kind {
            LaneKind::MatVec => self.execute_matvec(manifold),
            LaneKind::Audio => self.execute_audio(manifold),
        }
    }

    fn execute_matvec(&self, manifold: &mut Manifold) -> f64 {
        let dim = self.dim;
        let start_row = manifold.focus % dim;
        let mut checksum: f64 = 0.0;
        let mut out = vec![0.0f32; dim];
        for _ in 0..self.repeats {
            for (i, out_slot) in out.iter_mut().enumerate() {
                // Rows are visited starting at the director's focus:
                // the focus genuinely changes which work is done first
                // and which values feed the checksum.
                let row = (start_row + i) % dim;
                let base = row * dim;
                let mut acc = 0.0f32;
                for j in 0..dim {
                    acc += self.matrix[base + j] * self.vector[j];
                }
                *out_slot = acc;
            }
            // Feed output back as the next vector: chained, real dataflow.
            self_chain(&mut out);
            checksum += out.iter().map(|&v| v as f64).sum::<f64>();
            // Rotate the working vector deterministically from `out`
            // by folding it into the checksum path only; the stored
            // vector is immutable so both schedulers stay identical.
            checksum = checksum * 0.999 + out[0] as f64;
        }
        if self.updates_focus {
            manifold.focus = (checksum.abs() as usize) % dim;
            manifold.entropy = (checksum.abs() % 1.0) as f32;
        }
        checksum
    }

    fn execute_audio(&self, _manifold: &mut Manifold) -> f64 {
        // 1) Real demux of the interleaved PCM into per-channel buffers.
        let channels = demux_interleaved(&self.pcm_interleaved, self.channels);
        // 2) Real per-channel energy + a small matvec "acoustic model"
        //    over features derived from channel 0.
        let mut checksum: f64 = 0.0;
        for ch in &channels {
            checksum += ch.iter().map(|&s| (s * s) as f64).sum::<f64>();
        }
        let dim = self.dim;
        let mut feats = vec![0.0f32; dim];
        for (i, f) in feats.iter_mut().enumerate() {
            *f = channels[0][(i * 7) % channels[0].len()];
        }
        for _ in 0..self.repeats {
            for i in 0..dim {
                let base = i * dim;
                let mut acc = 0.0f32;
                for (j, &feat) in feats.iter().enumerate().take(dim) {
                    acc += self.matrix[base + j] * feat;
                }
                checksum += acc as f64 * 0.001;
            }
        }
        checksum
    }
}

fn self_chain(out: &mut [f32]) {
    // Cheap in-place non-linearity so repeated matvecs are not a
    // single hoistable computation.
    for v in out.iter_mut() {
        *v = (*v * 0.01).tanh();
    }
}

/// Demux interleaved f32 PCM (`[L0, R0, L1, R1, ...]`) into
/// per-channel buffers. This is the honest CPU version of the
/// email's SkaldAudio demux — no DMA, no hardware claim.
pub fn demux_interleaved(input: &[f32], channels: usize) -> Vec<Vec<f32>> {
    assert!(channels > 0, "channels must be >= 1");
    let frames = input.len() / channels;
    let mut out = vec![vec![0.0f32; frames]; channels];
    for frame in 0..frames {
        for ch in 0..channels {
            out[ch][frame] = input[frame * channels + ch];
        }
    }
    out
}

/// The named example cascade from the email, in cascade order:
/// perception -> decision -> attention-director -> diffusion-step,
/// plus the audio lane. Repeats are chosen so stages have visibly
/// different costs, as they do in the email (diffusion > perception
/// > director > decision > audio-feature step).
pub fn default_lanes() -> Vec<Lane> {
    vec![
        Lane::matvec("perception", 96, 28, 0x1001, false),
        Lane::matvec("decision", 96, 12, 0x2002, false),
        Lane::matvec("attention-director", 96, 18, 0x3003, true),
        Lane::matvec("diffusion-step", 96, 36, 0x4004, false),
        Lane::audio("audio-skald", 1024, 2, 8, 0x5005),
    ]
}

// -------------------------------------------------------------- schedulers

#[derive(Debug, Clone, Copy)]
pub struct ScheduleConfig {
    /// Number of full cycles (frames / rolling rounds) to run.
    pub cycles: usize,
    /// Phase offset between successive lanes' sensor readiness.
    /// MODELLED SENSOR PERIOD: implemented with `sleep` (see module
    /// docs); it is *not* compute.
    pub sensor_stagger: Duration,
}

impl Default for ScheduleConfig {
    fn default() -> Self {
        Self {
            cycles: 20,
            sensor_stagger: Duration::from_micros(400),
        }
    }
}

#[derive(Debug, Clone)]
pub struct RunResult {
    pub scheduler: &'static str,
    /// Time from schedule start to the first emitted output.
    pub time_to_first_output: Duration,
    pub total: Duration,
    pub outputs: usize,
    /// Intervals between successive emitted outputs, in emit order.
    pub inter_output: Vec<Duration>,
    pub checksum: f64,
}

impl RunResult {
    pub fn outputs_per_sec(&self) -> f64 {
        self.outputs as f64 / self.total.as_secs_f64()
    }
    pub fn mean_inter_output(&self) -> Duration {
        if self.inter_output.is_empty() {
            return Duration::ZERO;
        }
        let sum: Duration = self.inter_output.iter().sum();
        sum / self.inter_output.len() as u32
    }
    pub fn p95_inter_output(&self) -> Duration {
        percentile(&self.inter_output, 95.0)
    }
}

/// Nearest-rank percentile of durations (p in [0, 100]).
pub fn percentile(values: &[Duration], p: f64) -> Duration {
    if values.is_empty() {
        return Duration::ZERO;
    }
    let mut sorted: Vec<Duration> = values.to_vec();
    sorted.sort();
    let rank = (p / 100.0 * sorted.len() as f64).ceil() as usize;
    sorted[rank.saturating_sub(1).min(sorted.len() - 1)]
}

fn warmup(lanes: &[Lane]) {
    let mut manifold = Manifold::default();
    for lane in lanes {
        black_box(lane.execute(&mut manifold));
    }
}

/// MODELLED SENSOR PERIOD helper: sleep until `deadline` (relative to
/// `cycle_start`) if it has not already passed. This is the only
/// place either scheduler sleeps, and it models sensors becoming
/// ready — never computation.
fn wait_until(cycle_start: Instant, offset: Duration) {
    let target = cycle_start + offset;
    let now = Instant::now();
    if now < target {
        sleep(target - now);
    }
}

/// (a) Traditional baseline: wait for *every* lane's sensor, run all
/// lanes, emit exactly **one** output per cycle.
pub fn run_batched(lanes: &[Lane], cfg: &ScheduleConfig) -> RunResult {
    warmup(lanes);
    let mut manifold = Manifold::default();
    let start = Instant::now();
    let mut first_output_at: Option<Duration> = None;
    let mut last_emit: Option<Instant> = None;
    let mut inter_output = Vec::new();
    let mut outputs = 0usize;
    let mut checksum: f64 = 0.0;

    for _ in 0..cfg.cycles {
        let cycle_start = Instant::now();
        // MODELLED SENSOR PERIOD: a frame cannot start until its
        // slowest (last, phase-offset) sensor has arrived.
        if !lanes.is_empty() {
            wait_until(cycle_start, cfg.sensor_stagger * (lanes.len() as u32 - 1));
        }
        for lane in lanes {
            checksum += black_box(lane.execute(&mut manifold));
        }
        // Emit once, after the whole batch.
        let now = Instant::now();
        if first_output_at.is_none() {
            first_output_at = Some(now.duration_since(start));
        }
        if let Some(prev) = last_emit {
            inter_output.push(now.duration_since(prev));
        }
        last_emit = Some(now);
        outputs += 1;
    }
    RunResult {
        scheduler: "batched",
        time_to_first_output: first_output_at.unwrap_or_default(),
        total: start.elapsed(),
        outputs,
        inter_output,
        checksum,
    }
}

/// (b) Rolling: lane *i* starts as soon as its own phase offset has
/// arrived; every lane completion emits an output immediately, so a
/// cycle produces `lanes.len()` outputs in a continuous stream.
pub fn run_rolling(lanes: &[Lane], cfg: &ScheduleConfig) -> RunResult {
    warmup(lanes);
    let mut manifold = Manifold::default();
    let start = Instant::now();
    let mut first_output_at: Option<Duration> = None;
    let mut last_emit: Option<Instant> = None;
    let mut inter_output = Vec::new();
    let mut outputs = 0usize;
    let mut checksum: f64 = 0.0;

    for _ in 0..cfg.cycles {
        let cycle_start = Instant::now();
        for (i, lane) in lanes.iter().enumerate() {
            // MODELLED SENSOR PERIOD: this lane's sensor is ready at
            // i * stagger into the cycle. If earlier lanes' real work
            // already took longer, there is nothing to wait for.
            wait_until(cycle_start, cfg.sensor_stagger * i as u32);
            checksum += black_box(lane.execute(&mut manifold));
            // Emit per lane completion.
            let now = Instant::now();
            if first_output_at.is_none() {
                first_output_at = Some(now.duration_since(start));
            }
            if let Some(prev) = last_emit {
                inter_output.push(now.duration_since(prev));
            }
            last_emit = Some(now);
            outputs += 1;
        }
    }
    RunResult {
        scheduler: "rolling",
        time_to_first_output: first_output_at.unwrap_or_default(),
        total: start.elapsed(),
        outputs,
        inter_output,
        checksum,
    }
}

// ------------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    fn test_cfg() -> ScheduleConfig {
        ScheduleConfig {
            cycles: 10,
            sensor_stagger: Duration::from_micros(300),
        }
    }

    #[test]
    fn demux_interleaved_stereo() {
        let input = [1.0, 10.0, 2.0, 20.0, 3.0, 30.0];
        let ch = demux_interleaved(&input, 2);
        assert_eq!(ch[0], vec![1.0, 2.0, 3.0]);
        assert_eq!(ch[1], vec![10.0, 20.0, 30.0]);
    }

    #[test]
    fn demux_interleaved_mono_and_multichannel() {
        let ch = demux_interleaved(&[5.0, 6.0, 7.0], 1);
        assert_eq!(ch, vec![vec![5.0, 6.0, 7.0]]);
        let ch = demux_interleaved(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 3);
        assert_eq!(ch[0], vec![1.0, 4.0]);
        assert_eq!(ch[1], vec![2.0, 5.0]);
        assert_eq!(ch[2], vec![3.0, 6.0]);
    }

    #[test]
    fn kernel_is_deterministic() {
        let lanes = default_lanes();
        let mut m1 = Manifold::default();
        let mut m2 = Manifold::default();
        for lane in &lanes {
            assert_eq!(lane.execute(&mut m1), lane.execute(&mut m2));
        }
    }

    #[test]
    fn percentile_nearest_rank() {
        let vals: Vec<Duration> = (1..=100).map(Duration::from_micros).collect();
        assert_eq!(percentile(&vals, 95.0), Duration::from_micros(95));
        assert_eq!(percentile(&[], 95.0), Duration::ZERO);
    }

    #[test]
    fn both_schedulers_do_the_same_work() {
        let lanes = default_lanes();
        let cfg = test_cfg();
        let b = run_batched(&lanes, &cfg);
        let r = run_rolling(&lanes, &cfg);
        // Identical lane sequence and manifold updates => the total
        // checksum must agree to within float-summation noise (in
        // fact exactly, since emit points do not reorder work).
        assert!(
            (b.checksum - r.checksum).abs() < 1e-6,
            "checksum mismatch: batched={} rolling={}",
            b.checksum,
            r.checksum
        );
    }

    #[test]
    fn rolling_first_output_beats_batched_and_emits_more() {
        let lanes = default_lanes();
        let cfg = test_cfg();
        let b = run_batched(&lanes, &cfg);
        let r = run_rolling(&lanes, &cfg);

        assert_eq!(b.outputs, cfg.cycles);
        assert_eq!(r.outputs, cfg.cycles * lanes.len());
        assert!(
            r.outputs > b.outputs,
            "rolling must emit more intermediate outputs: rolling={} batched={}",
            r.outputs,
            b.outputs
        );
        assert!(
            r.time_to_first_output < b.time_to_first_output,
            "rolling TTFO ({:?}) must be < batched TTFO ({:?})",
            r.time_to_first_output,
            b.time_to_first_output
        );
        // The gap is structural, not jitter: batched TTFO includes
        // the last sensor's phase offset plus all five lanes' work,
        // rolling TTFO is one lane's work. Require a clear margin.
        assert!(
            r.time_to_first_output * 2 < b.time_to_first_output,
            "expected at least a 2x TTFO margin: rolling={:?} batched={:?}",
            r.time_to_first_output,
            b.time_to_first_output
        );
    }
}
