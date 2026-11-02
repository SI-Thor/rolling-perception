//! # rolling-pipeline
//!
//! The integrated cascade the two sibling crates imply but do not form:
//!
//! ```text
//! producer ──ring──▶ perceive ──ring──▶ decide ──ring──▶ direct ──ring──▶ refine ──ring──▶ publish
//!                        ▲                                                              │
//!                        └──────────── gate (viewport) set by `direct`, ◀────────────┘
//!                                      consumed by `perceive` on its NEXT pass
//! ```
//!
//! Honesty rules, inherited from the sibling crates:
//!
//! * Payload **data** really travels through `rolling_substrate_core`
//!   rings — one [`FluidSubstrateBuffer`] per stage edge, Disruptor
//!   claim/finalize protocol, no direct stage-to-stage calls.
//! * **Lineage** lives in each slot's header while the slot is leased.
//!   Headers are cleared when a slot is re-leased, so a stage captures a
//!   [`LineageSnapshot`] (bitmask + counts — plain copyable values) from
//!   its input's lineage relay, replays those counts into its output
//!   slot's header, then records itself. The published payload's header
//!   therefore shows every stage's exact visit count.
//! * A small control record ([`TickMeta`]: decide's signal summary and
//!   the lineage relay) travels alongside the rings. It is control
//!   state, not payload data, and it is labelled as such — the same
//!   role `Manifold` plays in `rolling-perception`.
//! * **Ops are counted, not timed**, wherever a saving is claimed. The
//!   director/gating saving is proven by counters first; wall time is
//!   reported second and never as the proof.
//! * The only `sleep` models **sensor arrivals** (labelled MODELLED
//!   SENSOR PERIOD at the call site), exactly as in the sibling crate.

use rolling_substrate_core::gating::{gated_apply, Viewport};
use rolling_substrate_core::lineage::COUNTED_NODES;
use rolling_substrate_core::sheaf::SheafGraph;
use rolling_substrate_core::substrate::{FluidSubstrateBuffer, Lease};
use std::hint::black_box;
use std::thread::sleep;
use std::time::{Duration, Instant};

// ------------------------------------------------------------------ stages

/// Stage node ids, recorded in lineage in cascade order.
pub const STAGE_PERCEIVE: usize = 0;
pub const STAGE_DECIDE: usize = 1;
pub const STAGE_DIRECT: usize = 2;
pub const STAGE_REFINE: usize = 3;
pub const STAGE_PUBLISH: usize = 4;
pub const STAGE_NAMES: [&str; 5] = ["perceive", "decide", "direct", "refine", "publish"];

/// Payload geometry: an 8×8 grid in one ring slot.
pub const WIDTH: usize = 8;
pub const HEIGHT: usize = 8;
pub const DIM: usize = WIDTH * HEIGHT;

/// Ring capacity per edge. Each tick finalizes before the next begins,
/// so in-flight depth is 1; 8 leaves generous lap headroom.
const RING_CAP: usize = 8;
/// Sheaf gradient step. Line graph λmax ≤ 4, so α < 0.25 is stable.
const SHEAF_ALPHA: f64 = 0.1;

// --------------------------------------------------------------------- ops

/// Counted operations. Every claimed saving is read off these counters.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Ops {
    /// Elements `perceive` actually processed (inside the gate).
    pub perceive_gated: u64,
    /// Elements `perceive` *would* have processed ungated (full grid,
    /// per payload) — the baseline the gate is measured against.
    pub perceive_baseline: u64,
    pub decide: u64,
    pub direct: u64,
    pub refine: u64,
    pub publish: u64,
}

impl Ops {
    pub fn total(&self) -> u64 {
        self.perceive_gated + self.decide + self.direct + self.refine + self.publish
    }
    /// Fraction of perceive work saved by gating, in [0, 1].
    pub fn gating_saved_fraction(&self) -> f64 {
        if self.perceive_baseline == 0 {
            return 0.0;
        }
        1.0 - (self.perceive_gated as f64 / self.perceive_baseline as f64)
    }
}

// ----------------------------------------------------------------- lineage

/// Copyable snapshot of a slot header's lineage (bitmask + counts).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct LineageSnapshot {
    pub mask: u64,
    pub counts: [u32; COUNTED_NODES],
}

impl LineageSnapshot {
    fn capture(lease: &Lease<'_>) -> Self {
        let h = lease.lineage();
        let mut counts = [0u32; COUNTED_NODES];
        for (i, c) in counts.iter_mut().enumerate() {
            *c = h.count(i).unwrap_or(0);
        }
        Self { mask: h.visited_mask(), counts }
    }

    /// Replay this snapshot into a freshly leased slot's header, so
    /// lineage accumulates across ring edges even though each slot's
    /// header is cleared on lease.
    fn replay_into(&self, lease: &Lease<'_>) {
        for (node, &n) in self.counts.iter().enumerate() {
            for _ in 0..n {
                lease.record_visit(node);
            }
        }
    }

    pub fn count(&self, stage: usize) -> u32 {
        self.counts[stage]
    }
    pub fn visited(&self, stage: usize) -> bool {
        self.mask & (1u64 << stage) != 0
    }
}

// -------------------------------------------------------------------- meta

/// Control state carried alongside one tick (NOT payload data; the
/// payload itself travels in the rings). Carries decide's signal
/// summary and the lineage relay between stages.
#[derive(Debug, Clone, Copy, Default)]
pub struct TickMeta {
    /// Signal centroid (x, y in grid cells) computed by `decide`.
    pub signal: (f32, f32),
    /// Total |value| mass `decide` saw (0 ⇒ no signal).
    pub signal_mass: f32,
    pub lineage: LineageSnapshot,
}

// ---------------------------------------------------------------- director

/// Deterministic attention director with deadband + hysteresis.
///
/// Policy, per tick: the target is the signal centroid rounded to a
/// cell. If the target is within `deadband` cells (Chebyshev distance)
/// of the current gate centre, the gate is **held** (hysteresis — a
/// jittering signal must not thrash the viewport). Otherwise the centre
/// moves toward the target by at most `max_step` cells per axis and is
/// clamped so the gate stays inside the grid.
#[derive(Debug, Clone)]
pub struct Director {
    pub center: (i32, i32),
    pub gate_size: u32,
    pub deadband: i32,
    pub max_step: i32,
    pub moves: u64,
    pub holds: u64,
}

impl Director {
    pub fn new(gate_size: u32, deadband: i32, max_step: i32) -> Self {
        assert!(gate_size >= 1 && gate_size <= WIDTH as u32);
        Self {
            // Start centred; the initial gate is replaced by the caller
            // with a full-frame gate for the very first pass.
            center: ((WIDTH / 2) as i32, (HEIGHT / 2) as i32),
            gate_size,
            deadband,
            max_step,
            moves: 0,
            holds: 0,
        }
    }

    pub fn gate(&self) -> Viewport {
        let half = (self.gate_size / 2) as i32;
        let x0 = (self.center.0 - half).clamp(0, WIDTH as i32 - self.gate_size as i32);
        let y0 = (self.center.1 - half).clamp(0, HEIGHT as i32 - self.gate_size as i32);
        Viewport::new(
            x0 as u32,
            x0 as u32 + self.gate_size,
            y0 as u32,
            y0 as u32 + self.gate_size,
        )
    }

    /// One policy step against a signal centroid. Returns the new gate.
    pub fn update(&mut self, signal: (f32, f32), ops: &mut Ops) -> Viewport {
        ops.direct += 1;
        let target = (signal.0.round() as i32, signal.1.round() as i32);
        let dx = target.0 - self.center.0;
        let dy = target.1 - self.center.1;
        if dx.abs().max(dy.abs()) <= self.deadband {
            self.holds += 1;
        } else {
            self.center.0 += dx.clamp(-self.max_step, self.max_step);
            self.center.1 += dy.clamp(-self.max_step, self.max_step);
            self.center.0 = self.center.0.clamp(0, WIDTH as i32 - 1);
            self.center.1 = self.center.1.clamp(0, HEIGHT as i32 - 1);
            self.moves += 1;
        }
        self.gate()
    }
}

// ---------------------------------------------------------------- pipeline

/// What `publish` emits for one payload.
#[derive(Debug, Clone)]
pub struct Published {
    pub tick: u64,
    pub checksum: f64,
    pub lineage: LineageSnapshot,
    /// Gate `perceive` actually used for this payload.
    pub gate_used: Viewport,
    pub sheaf_energy_before: f64,
    pub sheaf_energy_after: f64,
    pub data: Vec<f32>,
}

/// The cascade. Owns one ring per stage edge plus the director.
pub struct Pipeline {
    ring_in: FluidSubstrateBuffer,       // producer  -> perceive
    ring_perceived: FluidSubstrateBuffer, // perceive  -> decide
    ring_decided: FluidSubstrateBuffer,  // decide    -> direct
    ring_directed: FluidSubstrateBuffer, // direct    -> refine
    ring_refined: FluidSubstrateBuffer,  // refine    -> publish
    ring_out: FluidSubstrateBuffer,      // publish   -> world
    graph: SheafGraph,
    pub director: Director,
    gate: Viewport,
    tick: u64,
    pub ops: Ops,
}

impl Default for Pipeline {
    fn default() -> Self {
        Self::new()
    }
}

impl Pipeline {
    pub fn new() -> Self {
        Self {
            ring_in: FluidSubstrateBuffer::new(RING_CAP, DIM),
            ring_perceived: FluidSubstrateBuffer::new(RING_CAP, DIM),
            ring_decided: FluidSubstrateBuffer::new(RING_CAP, DIM),
            ring_directed: FluidSubstrateBuffer::new(RING_CAP, DIM),
            ring_refined: FluidSubstrateBuffer::new(RING_CAP, DIM),
            ring_out: FluidSubstrateBuffer::new(RING_CAP, DIM),
            graph: SheafGraph::line(DIM),
            director: Director::new(4, 1, 2),
            // First pass sees the whole frame; the director narrows
            // the gate from the first signal onwards.
            gate: Viewport::full(WIDTH as u32, HEIGHT as u32),
            tick: 0,
            ops: Ops::default(),
        }
    }

    /// Run one payload through all five stages. The payload enters via
    /// the producer ring and leaves via the publish ring.
    pub fn run_tick(&mut self, input: &[f32]) -> Published {
        assert_eq!(input.len(), DIM, "payload must be one {WIDTH}x{HEIGHT} grid");
        let tick = self.tick;
        let mut meta = TickMeta::default();

        // producer: write the payload into the input ring.
        {
            let mut lease = self.ring_in.lease();
            debug_assert_eq!(lease.claim(), tick);
            lease.data_mut().copy_from_slice(input);
            lease.finalize();
        }

        // perceive: gated kernel through the ring. Consumes the gate
        // set by `direct` on the PREVIOUS tick (full frame on tick 0).
        let gate_used = self.gate;
        stage_perceive(
            &self.ring_in,
            &self.ring_perceived,
            tick,
            gate_used,
            &mut meta,
            &mut self.ops,
        );

        // decide: signal summary + a counted scaling pass.
        stage_decide(&self.ring_perceived, &self.ring_decided, tick, &mut meta, &mut self.ops);

        // direct: policy step. The gate it returns is stored and used
        // by perceive on the NEXT tick — the feedback loop.
        let new_gate = stage_direct(
            &self.ring_decided,
            &self.ring_directed,
            tick,
            &mut meta,
            &mut self.director,
            &mut self.ops,
        );

        // refine: one sheaf smoothing step, energy asserted
        // non-increasing per payload inside the stage.
        let (e_before, e_after) = stage_refine(
            &self.ring_directed,
            &self.ring_refined,
            tick,
            &self.graph,
            &mut meta,
            &mut self.ops,
        );

        // publish: checksum + final lineage snapshot, out the last ring.
        let published = stage_publish(
            &self.ring_refined,
            &self.ring_out,
            tick,
            gate_used,
            e_before,
            e_after,
            &mut meta,
            &mut self.ops,
        );

        self.gate = new_gate;
        self.tick += 1;
        published
    }
}

/// Copy a published input claim into a fresh output lease, replay the
/// lineage relay into the output header, and record this stage. The
/// shared skeleton every stage is built from — data moves ring→ring,
/// never stage→stage.
fn handoff<'a>(
    input: &FluidSubstrateBuffer,
    output: &'a FluidSubstrateBuffer,
    claim: u64,
    meta: &TickMeta,
    stage: usize,
) -> (Lease<'a>, LineageSnapshot) {
    assert!(input.is_published(claim), "stage input claim {claim} not published");
    // SAFETY: claim is published on `input`, ticks are strictly
    // sequential in this crate, and the next lap of that slot cannot be
    // leased until this stage has finished copying (the producer of the
    // next tick runs after this tick completes).
    let data: Vec<f32> = unsafe { input.read_published(claim) }.to_vec();
    let mut lease = output.lease();
    debug_assert_eq!(lease.claim(), claim, "rings must advance in lockstep, one claim per tick");
    lease.data_mut().copy_from_slice(&data);
    meta.lineage.replay_into(&lease);
    lease.record_visit(stage);
    let snapshot = LineageSnapshot::capture(&lease);
    (lease, snapshot)
}

// ------------------------------------------------------------------ stages

fn stage_perceive(
    input: &FluidSubstrateBuffer,
    output: &FluidSubstrateBuffer,
    claim: u64,
    gate: Viewport,
    meta: &mut TickMeta,
    ops: &mut Ops,
) {
    let (mut lease, snapshot) = handoff(input, output, claim, meta, STAGE_PERCEIVE);
    ops.perceive_baseline += DIM as u64;
    // The counted kernel: real per-element work, applied ONLY inside
    // the gate by gated_apply — skipped elements are never touched,
    // and the closure call count is the op count.
    let gated_before = ops.perceive_gated;
    let stats = gated_apply(lease.data_mut(), WIDTH, HEIGHT, &gate, |v| {
        ops.perceive_gated += 1;
        *v = (*v * 1.5).tanh() * 2.0;
    });
    debug_assert_eq!(
        ops.perceive_gated - gated_before,
        stats.processed as u64,
        "op counter and gated_apply counts must agree"
    );
    meta.lineage = snapshot;
    lease.finalize();
}

fn stage_decide(
    input: &FluidSubstrateBuffer,
    output: &FluidSubstrateBuffer,
    claim: u64,
    meta: &mut TickMeta,
    ops: &mut Ops,
) {
    let (mut lease, snapshot) = handoff(input, output, claim, meta, STAGE_DECIDE);
    // Signal summary: |value|-weighted centroid over the grid, plus a
    // counted scaling pass so decide does real work on the payload.
    let (mut sx, mut sy, mut mass) = (0.0f32, 0.0f32, 0.0f32);
    let data = lease.data_mut();
    for y in 0..HEIGHT {
        for x in 0..WIDTH {
            let v = &mut data[y * WIDTH + x];
            *v *= 1.25;
            ops.decide += 1;
            let m = v.abs();
            sx += x as f32 * m;
            sy += y as f32 * m;
            mass += m;
        }
    }
    if mass > 0.0 {
        meta.signal = (sx / mass, sy / mass);
    }
    meta.signal_mass = mass;
    meta.lineage = snapshot;
    lease.finalize();
}

fn stage_direct(
    input: &FluidSubstrateBuffer,
    output: &FluidSubstrateBuffer,
    claim: u64,
    meta: &mut TickMeta,
    director: &mut Director,
    ops: &mut Ops,
) -> Viewport {
    let (lease, snapshot) = handoff(input, output, claim, meta, STAGE_DIRECT);
    // Direct does not transform payload data; it transforms the
    // CONTROL state (the gate). The payload passes through the ring
    // untouched, with lineage recorded.
    let gate = director.update(meta.signal, ops);
    meta.lineage = snapshot;
    lease.finalize();
    gate
}

fn stage_refine(
    input: &FluidSubstrateBuffer,
    output: &FluidSubstrateBuffer,
    claim: u64,
    graph: &SheafGraph,
    meta: &mut TickMeta,
    ops: &mut Ops,
) -> (f64, f64) {
    let (mut lease, snapshot) = handoff(input, output, claim, meta, STAGE_REFINE);
    let mut s: Vec<f64> = lease.data_mut().iter().map(|&v| v as f64).collect();
    let before = graph.energy(&s);
    graph.smooth_step(&mut s, SHEAF_ALPHA);
    let after = graph.energy(&s);
    // The sheaf claim, asserted per payload, not assumed: one gradient
    // step at α < 1/λmax never increases consistency energy.
    assert!(
        after <= before + 1e-12,
        "sheaf energy increased on tick {claim}: {before} -> {after}"
    );
    ops.refine += (DIM + graph.edges().len()) as u64;
    for (dst, &v) in lease.data_mut().iter_mut().zip(s.iter()) {
        *dst = v as f32;
    }
    meta.lineage = snapshot;
    lease.finalize();
    (before, after)
}

fn stage_publish(
    input: &FluidSubstrateBuffer,
    output: &FluidSubstrateBuffer,
    claim: u64,
    gate_used: Viewport,
    e_before: f64,
    e_after: f64,
    meta: &mut TickMeta,
    ops: &mut Ops,
) -> Published {
    let (mut lease, snapshot) = handoff(input, output, claim, meta, STAGE_PUBLISH);
    let mut checksum = 0.0f64;
    for &v in lease.data_mut().iter() {
        checksum += v as f64;
        ops.publish += 1;
    }
    let data = lease.data_mut().to_vec();
    meta.lineage = snapshot;
    lease.finalize();
    Published {
        tick: claim,
        checksum: black_box(checksum),
        lineage: snapshot,
        gate_used,
        sheaf_energy_before: e_before,
        sheaf_energy_after: e_after,
        data,
    }
}

// ------------------------------------------------------------------- trace

/// One recorded arrival: offset from its cycle's start + one payload.
#[derive(Debug, Clone)]
pub struct TraceEntry {
    pub arrival: Duration,
    pub data: Vec<f32>,
}

/// Deterministic pseudo-noise (the sibling crate's LCG).
fn fill_pseudo(out: &mut [f32], mut state: u64) {
    for v in out.iter_mut() {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        let x = ((state >> 33) as u32) as f32 / u32::MAX as f32;
        *v = x * 2.0 - 1.0;
    }
}

/// A payload with a Gaussian hotspot at (`hx`, `hy`) plus noise — a
/// signal the director can actually track.
pub fn hotspot_payload(hx: f32, hy: f32, seed: u64) -> Vec<f32> {
    let mut data = vec![0.0f32; DIM];
    fill_pseudo(&mut data, seed);
    for (i, v) in data.iter_mut().enumerate() {
        let x = (i % WIDTH) as f32;
        let y = (i / WIDTH) as f32;
        let d2 = (x - hx) * (x - hx) + (y - hy) * (y - hy);
        *v = (-d2 / 3.0).exp() + 0.05 * *v;
    }
    data
}

/// Generate a deterministic trace: a hotspot drifting across the grid,
/// one entry per `stagger`, arrivals relative to the trace start.
/// This is the generator behind the file-replay producer — the same
/// entries `trace-gen` writes to disk and [`load_trace`] reads back.
pub fn generate_trace(entries: usize, stagger: Duration) -> Vec<TraceEntry> {
    (0..entries)
        .map(|i| {
            let t = i as f32;
            TraceEntry {
                arrival: stagger * i as u32,
                data: hotspot_payload(1.0 + 0.55 * t, 1.0 + 0.4 * t, 0xA11CE + i as u64),
            }
        })
        .collect()
}

/// Serialise a trace in the documented v1 text format (see README).
pub fn trace_to_string(trace: &[TraceEntry]) -> String {
    let mut out = String::from("# rolling-trace v1\n# columns: arrival_us, then 64 payload floats (8x8 row-major)\n");
    for e in trace {
        out.push_str(&format!("{}", e.arrival.as_micros()));
        for v in &e.data {
            out.push_str(&format!(" {:.6}", v));
        }
        out.push('\n');
    }
    out
}

/// Load a v1 trace file. Lines starting with `#` and blank lines are
/// skipped; every other line is `arrival_us` + exactly 64 floats.
pub fn load_trace(path: &std::path::Path) -> std::io::Result<Vec<TraceEntry>> {
    let text = std::fs::read_to_string(path)?;
    parse_trace(&text).map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
}

pub fn parse_trace(text: &str) -> Result<Vec<TraceEntry>, String> {
    let mut out = Vec::new();
    for (lineno, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let mut it = line.split_whitespace();
        let arrival_us: u64 = it
            .next()
            .ok_or_else(|| format!("line {}: missing arrival", lineno + 1))?
            .parse()
            .map_err(|_| format!("line {}: bad arrival_us", lineno + 1))?;
        let data: Vec<f32> = it
            .map(|t| t.parse::<f32>().map_err(|_| format!("line {}: bad float {t:?}", lineno + 1)))
            .collect::<Result<_, _>>()?;
        if data.len() != DIM {
            return Err(format!("line {}: expected {DIM} floats, got {}", lineno + 1, data.len()));
        }
        out.push(TraceEntry { arrival: Duration::from_micros(arrival_us), data });
    }
    if out.is_empty() {
        return Err("trace contains no entries".into());
    }
    Ok(out)
}

// --------------------------------------------------------------- schedulers

/// One cycle of jobs: entries with arrivals relative to the cycle start.
pub type Cycle = Vec<TraceEntry>;

#[derive(Debug, Clone)]
pub struct ScheduleReport {
    pub scheduler: &'static str,
    pub outputs: usize,
    pub time_to_first_output: Duration,
    pub total: Duration,
    pub checksum: f64,
    pub ops: Ops,
    /// Summed sheaf energy over all payloads, before / after `refine`.
    pub sheaf_energy_before: f64,
    pub sheaf_energy_after: f64,
    /// Lineage of the first published payload (the sample).
    pub sample_lineage: Option<LineageSnapshot>,
    pub director_moves: u64,
    pub director_holds: u64,
    /// Inter-output intervals (for percentiles via the sibling crate).
    pub inter_output: Vec<Duration>,
}

/// MODELLED SENSOR PERIOD: sleep until `offset` after `cycle_start`.
/// Models arrival timing only — never computation.
fn wait_until(cycle_start: Instant, offset: Duration) {
    let target = cycle_start + offset;
    let now = Instant::now();
    if now < target {
        sleep(target - now);
    }
}

/// Batched: per cycle, wait for the cycle's last arrival, run every
/// payload through the full cascade, emit ONE output per cycle.
pub fn run_batched(pipe: &mut Pipeline, cycles: &[Cycle]) -> ScheduleReport {
    run(pipe, cycles, false)
}

/// Rolling: per cycle, each payload runs the full cascade the moment
/// its own arrival lands; every payload emits an output.
pub fn run_rolling(pipe: &mut Pipeline, cycles: &[Cycle]) -> ScheduleReport {
    run(pipe, cycles, true)
}

fn run(pipe: &mut Pipeline, cycles: &[Cycle], rolling: bool) -> ScheduleReport {
    let start = Instant::now();
    let mut first: Option<Duration> = None;
    let mut last_emit: Option<Instant> = None;
    let mut inter_output = Vec::new();
    let mut outputs = 0usize;
    let mut checksum = 0.0f64;
    let (mut e_before, mut e_after) = (0.0f64, 0.0f64);
    let mut sample_lineage = None;
    let ops_start = pipe.ops;
    let (moves0, holds0) = (pipe.director.moves, pipe.director.holds);

    let emit = |now: Instant,
                    first: &mut Option<Duration>,
                    last_emit: &mut Option<Instant>,
                    inter_output: &mut Vec<Duration>,
                    outputs: &mut usize| {
        if first.is_none() {
            *first = Some(now.duration_since(start));
        }
        if let Some(prev) = *last_emit {
            inter_output.push(now.duration_since(prev));
        }
        *last_emit = Some(now);
        *outputs += 1;
    };

    for cycle in cycles {
        let cycle_start = Instant::now();
        if !rolling {
            // MODELLED SENSOR PERIOD: the batch cannot start until its
            // last arrival has landed.
            if let Some(last) = cycle.iter().map(|e| e.arrival).max() {
                wait_until(cycle_start, last);
            }
        }
        for entry in cycle {
            if rolling {
                // MODELLED SENSOR PERIOD: this payload's own arrival.
                wait_until(cycle_start, entry.arrival);
            }
            let pubd = pipe.run_tick(&entry.data);
            checksum += pubd.checksum;
            e_before += pubd.sheaf_energy_before;
            e_after += pubd.sheaf_energy_after;
            if sample_lineage.is_none() {
                sample_lineage = Some(pubd.lineage);
            }
            if rolling {
                emit(Instant::now(), &mut first, &mut last_emit, &mut inter_output, &mut outputs);
            }
        }
        if !rolling && !cycle.is_empty() {
            emit(Instant::now(), &mut first, &mut last_emit, &mut inter_output, &mut outputs);
        }
    }

    let ops = Ops {
        perceive_gated: pipe.ops.perceive_gated - ops_start.perceive_gated,
        perceive_baseline: pipe.ops.perceive_baseline - ops_start.perceive_baseline,
        decide: pipe.ops.decide - ops_start.decide,
        direct: pipe.ops.direct - ops_start.direct,
        refine: pipe.ops.refine - ops_start.refine,
        publish: pipe.ops.publish - ops_start.publish,
    };
    ScheduleReport {
        scheduler: if rolling { "rolling" } else { "batched" },
        outputs,
        time_to_first_output: first.unwrap_or_default(),
        total: start.elapsed(),
        checksum,
        ops,
        sheaf_energy_before: e_before,
        sheaf_energy_after: e_after,
        sample_lineage,
        director_moves: pipe.director.moves - moves0,
        director_holds: pipe.director.holds - holds0,
        inter_output,
    }
}

// -------------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn director_deadband_holds_and_steps() {
        let mut d = Director::new(4, 1, 2);
        let mut ops = Ops::default();
        let c0 = d.center;
        d.update((c0.0 as f32 + 0.6, c0.1 as f32 - 0.4), &mut ops); // rounds within deadband
        assert_eq!(d.holds, 1);
        assert_eq!(d.center, c0, "deadband must hold the gate");
        d.update((c0.0 as f32 + 10.0, c0.1 as f32), &mut ops); // far signal
        assert_eq!(d.moves, 1);
        assert_eq!(d.center.0, c0.0 + 2, "movement clamped to max_step");
        let g = d.gate();
        assert!(g.xmax <= WIDTH as u32 && g.ymax <= HEIGHT as u32, "gate stays in grid");
    }

    #[test]
    fn trace_roundtrip_through_text() {
        let trace = generate_trace(4, Duration::from_micros(500));
        let text = trace_to_string(&trace);
        let back = parse_trace(&text).unwrap();
        assert_eq!(back.len(), trace.len());
        for (a, b) in trace.iter().zip(back.iter()) {
            assert_eq!(a.arrival, b.arrival);
            for (x, y) in a.data.iter().zip(b.data.iter()) {
                assert!((x - y).abs() < 1e-6);
            }
        }
    }

    #[test]
    fn trace_file_replay() {
        let trace = generate_trace(3, Duration::from_micros(250));
        let path = std::env::temp_dir().join("rolling-pipeline-test-trace.txt");
        std::fs::write(&path, trace_to_string(&trace)).unwrap();
        let loaded = load_trace(&path).unwrap();
        std::fs::remove_file(&path).ok();
        assert_eq!(loaded.len(), 3);
        assert_eq!(loaded[2].arrival, Duration::from_micros(500));
        // And the replayed entries really drive the cascade:
        let mut pipe = Pipeline::new();
        let pubd = pipe.run_tick(&loaded[0].data);
        assert_eq!(pubd.tick, 0);
    }
}
