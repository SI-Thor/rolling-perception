//! The per-stream text ledger (SPEC §2.3): the world is text.
//!
//! ```text
//! <ledger_dir>/
//!   lens.txt      rhythm (period/jitter EMA) + appearance baseline
//!   state.txt     current state + budget meter + coverage counters
//!   events.jsonl  append-only: service receipts + published verdicts
//!   health.txt    Panel-1 heartbeat: embed p50/p99, queue, frame age
//! ```
//!
//! Every file is rewritten whole (they are small) except events.jsonl,
//! which is append-only. Text is canonical; any UI is a projection.

use crate::live::FrameOutput;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::time::{SystemTime, UNIX_EPOCH};

pub fn epoch_us() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_micros() as u64)
        .unwrap_or(0)
}

pub fn fmt_opt(v: Option<f64>) -> String {
    match v {
        Some(x) => format!("{x:.4}"),
        None => "null".into(),
    }
}

/// p50 / p99 of a latency window (nearest-rank; empty → (0, 0)).
pub fn percentiles(samples: &[f64]) -> (f64, f64) {
    if samples.is_empty() {
        return (0.0, 0.0);
    }
    let mut s: Vec<f64> = samples.to_vec();
    s.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let at = |q: f64| s[((q * s.len() as f64).ceil() as usize).clamp(1, s.len()) - 1];
    (at(0.50), at(0.99))
}

/// Running counters + windows the ledger files are rendered from.
#[derive(Debug, Default, Clone)]
pub struct Stats {
    pub frames_seen: u64,
    pub frames_changed: u64,
    pub events_published: u64,
    pub tiles_nominated: u64,
    pub tiles_embedded: u64,
    /// Nominated tiles the budget admission shed (§2.1 step 2) —
    /// logged, never silently dropped (SPEC §1 contention row).
    pub tiles_shed: u64,
    /// Verdicts published from the reflex tier alone while the
    /// decision tier was yielded off (§2.3 L3/L4).
    pub reflex_events: u64,
    pub embeds_spent_s: f64,
    pub embed_ms_window: Vec<f64>,
    pub verdict_latency_ms: Vec<f64>,
    pub period_ms_ema: Option<f64>,
    pub jitter_ms_ema: Option<f64>,
    pub tile_score_ema: [Option<f64>; 16],
    pub last_frame: Option<u32>,
    pub last_frame_wall_us: u64,
    pub frames_pending_max: u64,
}

impl Stats {
    pub fn mean_embed_ms(&self) -> f64 {
        if self.embed_ms_window.is_empty() {
            0.0
        } else {
            self.embed_ms_window.iter().sum::<f64>() / self.embed_ms_window.len() as f64
        }
    }
    /// What embedding EVERY tile of every frame would have cost, at
    /// the observed mean embed latency — the baseline the gate is
    /// saving against.
    pub fn embed_everything_estimate_s(&self) -> f64 {
        self.frames_seen as f64 * 16.0 * self.mean_embed_ms() / 1000.0
    }
    pub fn coverage(&self) -> f64 {
        if self.tiles_nominated == 0 {
            1.0
        } else {
            self.tiles_embedded as f64 / self.tiles_nominated as f64
        }
    }
    pub fn spend_ratio(&self) -> f64 {
        let est = self.embed_everything_estimate_s();
        if est <= 0.0 {
            0.0
        } else {
            self.embeds_spent_s / est
        }
    }
}

pub struct Ledger {
    dir: String,
    stream_id: String,
    events: File,
    pub stats: Stats,
    pub rack_up: bool,
    pub rack_started_by_me: bool,
    pub soak: bool,
    pub threshold: f64,
    pub alpha: f64,
    pub gate_diff: Option<f64>,
    /// Yield ladder position (§2.3), maintained by the service's
    /// tenancy loop: "L0".."L4", and why it is there.
    pub yield_rung: String,
    pub yield_reason: String,
    /// L4 unloaded the decision models (and this service owned
    /// them, so it could).
    pub models_unloaded: bool,
    /// Base per-stream budget (§2.2) and the ladder-factored
    /// effective figure, embed-seconds per rolling hour. Set by
    /// the service; `None` when the ledger is driven directly.
    pub budget_base_s: Option<f64>,
    pub budget_effective_s: Option<f64>,
}

impl Ledger {
    pub fn open(
        dir: &str,
        stream_id: &str,
        threshold: f64,
        alpha: f64,
        soak: bool,
    ) -> std::io::Result<Self> {
        std::fs::create_dir_all(dir)?;
        let events = OpenOptions::new()
            .create(true)
            .append(true)
            .open(format!("{dir}/events.jsonl"))?;
        let l = Self {
            dir: dir.to_string(),
            stream_id: stream_id.to_string(),
            events,
            stats: Stats::default(),
            rack_up: false,
            rack_started_by_me: false,
            soak,
            threshold,
            alpha,
            gate_diff: None,
            yield_rung: "L0".into(),
            yield_reason: "none".into(),
            models_unloaded: false,
            budget_base_s: None,
            budget_effective_s: None,
        };
        l.write_all()?;
        Ok(l)
    }

    fn path(&self, name: &str) -> String {
        format!("{}/{name}", self.dir)
    }

    pub fn service_event(&mut self, kind: &str, msg: &str) -> std::io::Result<()> {
        writeln!(
            self.events,
            "{{\"kind\":\"service\",\"event\":\"{kind}\",\"msg\":\"{}\",\"wall_us\":{}}}",
            msg.replace('"', "'"),
            epoch_us()
        )?;
        self.events.flush()
    }

    /// Record one processed frame. Verdict events are appended to
    /// events.jsonl only when the frame published a change (silence
    /// is the default — that is the product); counters, state, lens
    /// and health are updated for every frame.
    pub fn record_frame(
        &mut self,
        out: &FrameOutput,
        t_capture_us: u64,
        nominated: u64,
        embedded: u64,
        embed_ms: &[f64],
        frames_pending: u64,
    ) -> std::io::Result<Option<f64>> {
        let now = epoch_us();
        let s = &mut self.stats;
        s.frames_seen += 1;
        s.last_frame = Some(out.verdict.frame);
        s.last_frame_wall_us = now;
        s.tiles_nominated += nominated;
        s.tiles_embedded += embedded;
        for &ms in embed_ms {
            s.embeds_spent_s += ms / 1000.0;
            s.embed_ms_window.push(ms);
            if s.embed_ms_window.len() > 512 {
                s.embed_ms_window.remove(0);
            }
        }
        s.frames_pending_max = s.frames_pending_max.max(frames_pending);
        for tv in &out.tiles {
            if let Some(sc) = tv.smoothed_score {
                let e = s.tile_score_ema[tv.tile as usize];
                s.tile_score_ema[tv.tile as usize] =
                    Some(e.map(|p| p * 0.9 + sc * 0.1).unwrap_or(sc));
            }
        }

        let mut latency_ms = None;
        if out.verdict.changed {
            s.frames_changed += 1;
            s.events_published += 1;
            let lat = (now.saturating_sub(t_capture_us)) as f64 / 1000.0;
            latency_ms = Some(lat);
            s.verdict_latency_ms.push(lat);
            let lineage = out.tiles.iter().fold(0u64, |m, t| m | t.lineage_mask);
            let mut tiles_json = String::new();
            for tv in &out.tiles {
                if !tiles_json.is_empty() {
                    tiles_json.push(',');
                }
                tiles_json.push_str(&format!(
                    "{{\"tile\":{},\"raw\":{},\"smoothed\":{},\"changed\":{},\"stale\":{},\"lineage_mask\":{}}}",
                    tv.tile,
                    fmt_opt(tv.raw_score),
                    fmt_opt(tv.smoothed_score),
                    tv.changed,
                    tv.stale,
                    tv.lineage_mask
                ));
            }
            writeln!(
                self.events,
                "{{\"kind\":\"verdict\",\"stream\":\"{}\",\"frame\":{},\"wall_us\":{},\"t_capture_us\":{},\"verdict_latency_ms\":{:.3},\"changed_tiles\":{:?},\"focus\":{:?},\"lineage_mask\":{},\"stage_ms\":{{\"perceive_decide\":{:.3},\"direct\":{:.3},\"refine\":{:.3},\"publish\":{:.3}}},\"embeds_this_frame\":{},\"energy_before\":{:.4},\"energy_after\":{:.4},\"tiles\":[{}]}}",
                self.stream_id,
                out.verdict.frame,
                now,
                t_capture_us,
                lat,
                out.verdict.changed_tiles,
                out.verdict.focus,
                lineage,
                out.stage_ms.perceive_decide,
                out.stage_ms.direct,
                out.stage_ms.refine,
                out.stage_ms.publish,
                embedded,
                out.verdict.energy_before,
                out.verdict.energy_after,
                tiles_json
            )?;
            self.events.flush()?;
        }
        self.write_all()?;
        Ok(latency_ms)
    }

    /// Record one frame perceived by the REFLEX tier alone — the
    /// decision tier is yielded off (§2.3 L3/L4) or its budget is
    /// spent, so no tile was embedded. The frame still counts,
    /// the nominations still count, and if anything was nominated
    /// an "unperceived change" verdict publishes: the change feed
    /// degrades in resolution, never in liveness. The event is
    /// marked `unperceived` with its basis in plain words and a
    /// zero lineage mask — no cascade stage ran, and the record
    /// must not pretend one did.
    pub fn record_reflex_frame(
        &mut self,
        frame: u32,
        t_capture_us: u64,
        nominated_tiles: &[u32],
        basis: &str,
    ) -> std::io::Result<()> {
        let now = epoch_us();
        let s = &mut self.stats;
        s.frames_seen += 1;
        s.last_frame = Some(frame);
        s.last_frame_wall_us = now;
        s.tiles_nominated += nominated_tiles.len() as u64;
        if !nominated_tiles.is_empty() {
            s.events_published += 1;
            s.reflex_events += 1;
            let lat = (now.saturating_sub(t_capture_us)) as f64 / 1000.0;
            writeln!(
                self.events,
                "{{\"kind\":\"verdict\",\"stream\":\"{}\",\"frame\":{},\"wall_us\":{},\"t_capture_us\":{},\"verdict_latency_ms\":{:.3},\"unperceived\":true,\"basis\":\"{}\",\"changed_tiles\":{:?},\"focus\":[],\"lineage_mask\":0,\"embeds_this_frame\":0,\"tiles\":[]}}",
                self.stream_id,
                frame,
                now,
                t_capture_us,
                lat,
                basis.replace('"', "'"),
                nominated_tiles
            )?;
            self.events.flush()?;
        }
        self.write_all()
    }

    /// Observe a frame-arrival interval for the lens rhythm stats.
    pub fn observe_period(&mut self, period_ms: f64) {
        let s = &mut self.stats;
        match s.period_ms_ema {
            None => {
                s.period_ms_ema = Some(period_ms);
                s.jitter_ms_ema = Some(0.0);
            }
            Some(p) => {
                let dev = (period_ms - p).abs();
                s.jitter_ms_ema = Some(s.jitter_ms_ema.unwrap_or(0.0) * 0.9 + dev * 0.1);
                s.period_ms_ema = Some(p * 0.9 + period_ms * 0.1);
            }
        }
    }

    pub fn write_all(&self) -> std::io::Result<()> {
        std::fs::write(self.path("lens.txt"), self.lens_text())?;
        std::fs::write(self.path("state.txt"), self.state_text())?;
        std::fs::write(self.path("health.txt"), self.health_text())?;
        Ok(())
    }

    pub fn lens_text(&self) -> String {
        let s = &self.stats;
        let mut t = String::new();
        t.push_str(&format!("stream_id = {}\n", self.stream_id));
        t.push_str(&format!(
            "period_ms = {}\n",
            s.period_ms_ema
                .map(|v| format!("{v:.2}"))
                .unwrap_or_else(|| "unknown".into())
        ));
        t.push_str(&format!(
            "jitter_ms = {}\n",
            s.jitter_ms_ema
                .map(|v| format!("{v:.2}"))
                .unwrap_or_else(|| "unknown".into())
        ));
        t.push_str(&format!("threshold = {:.4}\n", self.threshold));
        t.push_str(&format!("alpha = {:.4}\n", self.alpha));
        if let Some(g) = self.gate_diff {
            t.push_str(&format!("gate_diff = {g:.4}\n"));
        }
        t.push_str(&format!("frames_observed = {}\n", s.frames_seen));
        t.push_str("tile_score_ema =");
        for e in s.tile_score_ema.iter() {
            t.push_str(&format!(" {}", fmt_opt(*e)));
        }
        t.push('\n');
        t
    }

    pub fn state_text(&self) -> String {
        let s = &self.stats;
        let mut t = String::new();
        t.push_str(&format!("stream_id = {}\n", self.stream_id));
        t.push_str(&format!("frames_seen = {}\n", s.frames_seen));
        t.push_str(&format!("frames_changed = {}\n", s.frames_changed));
        t.push_str(&format!("events_published = {}\n", s.events_published));
        t.push_str(&format!(
            "last_frame = {}\n",
            s.last_frame
                .map(|f| f.to_string())
                .unwrap_or_else(|| "none".into())
        ));
        t.push_str(&format!("tiles_nominated = {}\n", s.tiles_nominated));
        t.push_str(&format!("tiles_embedded = {}\n", s.tiles_embedded));
        t.push_str(&format!("tiles_shed = {}\n", s.tiles_shed));
        t.push_str(&format!("reflex_events = {}\n", s.reflex_events));
        if let (Some(base), Some(eff)) = (self.budget_base_s, self.budget_effective_s) {
            t.push_str(&format!("budget_embed_s_per_hour = {base:.1}\n"));
            t.push_str(&format!("budget_effective_embed_s_per_hour = {eff:.1}\n"));
        }
        t.push_str(&format!("yield_rung = {}\n", self.yield_rung));
        t.push_str(&format!("yield_reason = {}\n", self.yield_reason));
        t.push_str(&format!(
            "backfill_permitted = {}\n",
            self.yield_rung == "L0"
        ));
        t.push_str(&format!("coverage = {:.4}\n", s.coverage()));
        t.push_str(&format!("embeds_spent_s = {:.3}\n", s.embeds_spent_s));
        t.push_str(&format!(
            "embed_everything_estimate_s = {:.3}\n",
            s.embed_everything_estimate_s()
        ));
        t.push_str(&format!("spend_ratio = {:.4}\n", s.spend_ratio()));
        t.push_str(&format!(
            "rack = {}\n",
            if self.rack_up { "up" } else { "down" }
        ));
        t.push_str(&format!(
            "rack_started_by_me = {}\n",
            self.rack_started_by_me
        ));
        t.push_str(&format!("soak = {}\n", self.soak));
        if self.soak {
            // Precision self-report placeholders: in soak the human
            // labels arrive out of band (console lane); until then the
            // honest report is the raw counts, labelled as such.
            t.push_str("precision_self_report = placeholder (events fired and spend below; labels pending)\n");
            t.push_str(&format!("soak_events_fired = {}\n", s.events_published));
            t.push_str(&format!("soak_spend_ratio = {:.4}\n", s.spend_ratio()));
        }
        t.push_str(&format!("updated_wall_us = {}\n", epoch_us()));
        t
    }

    /// Which tier's silence a quiet ledger currently speaks with:
    /// "decision" (the full cascade is perceiving), "reflex"
    /// (yielded to L3/L4 — diffs are counted, nothing is embedded),
    /// or "none" (nothing has been seen / the perceiving tier is
    /// down, so quiet means nothing at all).
    pub fn silence_basis(&self) -> &'static str {
        let s = &self.stats;
        if s.frames_seen == 0 {
            return "none";
        }
        match self.yield_rung.as_str() {
            "L3" | "L4" => "reflex",
            _ if self.rack_up => "decision",
            _ => "none",
        }
    }

    /// The decision tier's posture in plain words (health.txt).
    pub fn decision_tier(&self) -> &'static str {
        match self.yield_rung.as_str() {
            "L0" | "L1" => "full",
            "L2" => "halved",
            "L4" if self.models_unloaded => "reflex_only_models_unloaded",
            "L3" | "L4" => "reflex_only",
            _ => "full",
        }
    }

    pub fn health_text(&self) -> String {
        let s = &self.stats;
        let (p50, p99) = percentiles(&s.embed_ms_window);
        let age_ms = if s.last_frame_wall_us == 0 {
            -1.0
        } else {
            epoch_us().saturating_sub(s.last_frame_wall_us) as f64 / 1000.0
        };
        format!(
            "embed_ms_p50 = {:.2}\nembed_ms_p99 = {:.2}\nembed_ms_n = {}\nframes_pending_max = {}\nlast_frame_age_ms = {:.1}\nrack = {}\nyield_rung = {}\nyield_reason = {}\ndecision_tier = {}\nsilence_basis = {}\nsilence_meaningful = {}\nupdated_wall_us = {}\n",
            p50,
            p99,
            s.embed_ms_window.len(),
            s.frames_pending_max,
            age_ms,
            if self.rack_up { "up" } else { "down" },
            self.yield_rung,
            self.yield_reason,
            self.decision_tier(),
            self.silence_basis(),
            // Panel-1 amendment: silence is only "normal" when health
            // says so — a starved lane must not look calm. The tier
            // whose silence is on offer must itself be alive: at
            // L0–L2 that is the rack-backed decision tier; at
            // L3/L4 the reflex tier needs no rack, only frames.
            self.silence_basis() != "none",
            epoch_us()
        )
    }
}
