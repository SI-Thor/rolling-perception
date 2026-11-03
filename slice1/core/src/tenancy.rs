//! Tenancy: the §2.3 yield ladder as code.
//!
//! The platform is a tenant on the Thor — Casey's bench first.
//! This module samples the host for foreign work and walks a
//! five-rung ladder (L0 = full tenancy … L4 = models unloaded),
//! stepping down when the box stops being ours and back up only
//! with the spec's hysteresis (a clear interval before the first
//! step up, then one step per interval — a bursty user workload
//! must not make perception flap).
//!
//! The ladder is a pure state machine over [`LoadSample`]s: the
//! service feeds it samples from a [`Probe`] on the sampler's
//! cadence and receipts every transition in the ledger. All of
//! the policy numbers live in [`LadderConfig`]; the defaults are
//! the spec's (§2.3: foreign GPU load >20% sustained >5 s yields;
//! 60 s of clear headroom before stepping back up, one rung per
//! 60 s). The memory-pressure threshold for L4 is the one number
//! the spec leaves open ("if the box is under memory pressure");
//! 10% of RAM available is this build's chosen line, exposed in
//! config as `mem_pressure_pct`.

use std::fmt;
use std::time::{Duration, Instant};

/// A rung of the yield ladder. L0 is not named in the spec (it is
/// the un-yielded state); L1–L4 are §2.3's steps verbatim.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Rung {
    L0,
    L1,
    L2,
    L3,
    L4,
}

impl Rung {
    pub fn name(&self) -> &'static str {
        match self {
            Rung::L0 => "L0",
            Rung::L1 => "L1",
            Rung::L2 => "L2",
            Rung::L3 => "L3",
            Rung::L4 => "L4",
        }
    }
    fn down(&self) -> Rung {
        match self {
            Rung::L0 => Rung::L1,
            Rung::L1 => Rung::L2,
            Rung::L2 => Rung::L3,
            Rung::L3 => Rung::L4,
            Rung::L4 => Rung::L4,
        }
    }
    fn up(&self) -> Rung {
        match self {
            Rung::L4 => Rung::L3,
            Rung::L3 => Rung::L2,
            Rung::L2 => Rung::L1,
            Rung::L1 => Rung::L0,
            Rung::L0 => Rung::L0,
        }
    }
}

impl fmt::Display for Rung {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.name())
    }
}

/// What a rung permits. The service wires the flags it has
/// consumers for; flags without a consumer in this service are
/// still computed and published (state.txt / control.json) so a
/// co-located consumer of the same ledger can gate on them.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Capabilities {
    /// §4 backfill exists to be shed first (L1).
    pub backfill_permitted: bool,
    /// Reflective sampling (cascade stage 4) runs (off from L2).
    pub reflective_permitted: bool,
    /// Multiplier on the per-stream decision budget (§2.2):
    /// halved at L2, zero once the decision tier is off.
    pub decision_factor: f64,
    /// The decision tier (embeds) may run at all.
    pub decision_permitted: bool,
    /// L4: decision models should be unloaded.
    pub unload_models: bool,
}

pub fn capabilities(rung: Rung) -> Capabilities {
    match rung {
        Rung::L0 => Capabilities {
            backfill_permitted: true,
            reflective_permitted: true,
            decision_factor: 1.0,
            decision_permitted: true,
            unload_models: false,
        },
        Rung::L1 => Capabilities {
            backfill_permitted: false,
            reflective_permitted: true,
            decision_factor: 1.0,
            decision_permitted: true,
            unload_models: false,
        },
        Rung::L2 => Capabilities {
            backfill_permitted: false,
            reflective_permitted: false,
            decision_factor: 0.5,
            decision_permitted: true,
            unload_models: false,
        },
        Rung::L3 => Capabilities {
            backfill_permitted: false,
            reflective_permitted: false,
            decision_factor: 0.0,
            decision_permitted: false,
            unload_models: false,
        },
        Rung::L4 => Capabilities {
            backfill_permitted: false,
            reflective_permitted: false,
            decision_factor: 0.0,
            decision_permitted: false,
            unload_models: true,
        },
    }
}

/// One host sample. `None` means "this source gave no reading" —
/// the ladder never invents a load figure it did not measure.
#[derive(Debug, Clone, Copy, Default)]
pub struct LoadSample {
    /// GPU utilisation attributable to NON-platform processes,
    /// percent. Attribution matters: the platform's own embeds
    /// load the GPU, and a tenant that yields to itself is a
    /// feedback loop. Sources that cannot attribute (aggregate
    /// counters) report `None`, not the aggregate.
    pub foreign_gpu_pct: Option<f64>,
    /// An interactive session is active (not idle-hinted) — the
    /// user is at the bench.
    pub interactive: bool,
    /// Percent of total RAM still available (MemAvailable).
    pub mem_available_pct: Option<f64>,
}

/// A source of host samples. The service runs one on a thread;
/// tests drive the ladder with scripted probes.
pub trait Probe: Send {
    fn sample(&mut self) -> LoadSample;
}

#[derive(Debug, Clone)]
pub struct LadderConfig {
    /// Foreign GPU % above which load counts as pressure (§2.3: 20).
    pub foreign_gpu_threshold_pct: f64,
    /// How long foreign load must persist before it yields (§2.3: 5 s).
    pub sustain: Duration,
    /// Clear-headroom interval before/between step-ups (§2.3: 60 s).
    pub recovery: Duration,
    /// MemAvailable below this percent of total = memory pressure.
    pub mem_pressure_pct: f64,
}

impl Default for LadderConfig {
    fn default() -> Self {
        Self {
            foreign_gpu_threshold_pct: 20.0,
            sustain: Duration::from_secs(5),
            recovery: Duration::from_secs(60),
            mem_pressure_pct: 10.0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Cause {
    ForeignGpu,
    InteractiveSession,
    MemoryPressure,
    Recovery,
}

impl Cause {
    pub fn name(&self) -> &'static str {
        match self {
            Cause::ForeignGpu => "foreign_gpu_load",
            Cause::InteractiveSession => "interactive_session",
            Cause::MemoryPressure => "memory_pressure",
            Cause::Recovery => "recovery",
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct Transition {
    pub from: Rung,
    pub to: Rung,
    pub cause: Cause,
}

/// The yield ladder state machine (pure; the clock is injected so
/// tests can run the spec's 5 s / 60 s timings in milliseconds).
pub struct Ladder {
    cfg: LadderConfig,
    rung: Rung,
    pressure_since: Option<Instant>,
    clear_since: Option<Instant>,
    last_step_up: Option<Instant>,
}

impl Ladder {
    pub fn new(cfg: LadderConfig) -> Self {
        Self {
            cfg,
            rung: Rung::L0,
            pressure_since: None,
            clear_since: None,
            last_step_up: None,
        }
    }

    pub fn rung(&self) -> Rung {
        self.rung
    }

    pub fn capabilities(&self) -> Capabilities {
        capabilities(self.rung)
    }

    /// Feed one sample. Returns the transition if the rung moved
    /// (at most one rung per call — the service calls this once
    /// per fresh sample, so step-down cadence is the sampler's).
    pub fn evaluate(&mut self, sample: &LoadSample, now: Instant) -> Option<Transition> {
        let foreign = sample
            .foreign_gpu_pct
            .map(|p| p > self.cfg.foreign_gpu_threshold_pct)
            .unwrap_or(false);
        let pressure_now = foreign || sample.interactive;
        if pressure_now {
            if self.pressure_since.is_none() {
                self.pressure_since = Some(now);
            }
        } else {
            self.pressure_since = None;
        }
        // An interactive session is a signal in itself (§2.3: "or
        // any interactive session activity signal") — it does not
        // wait out the 5 s sustain that GPU load must prove.
        let sustained = sample.interactive
            || self
                .pressure_since
                .map(|t| now.duration_since(t) >= self.cfg.sustain)
                .unwrap_or(false);
        let mem_pressure = sample
            .mem_available_pct
            .map(|m| m < self.cfg.mem_pressure_pct)
            .unwrap_or(false);

        // ---- step down (yield): at most one rung per evaluation.
        // Foreign pressure alone floors at L3; L4 is reserved for
        // memory pressure, the spec's own L4 trigger. Memory
        // pressure on its own also walks the ladder down — a box
        // out of RAM is a tenancy emergency whether or not a GPU
        // process caused it.
        if self.rung < Rung::L4 && (sustained || mem_pressure) {
            let ceiling = if mem_pressure { Rung::L4 } else { Rung::L3 };
            if self.rung < ceiling {
                let from = self.rung;
                self.rung = from.down();
                self.clear_since = None;
                let cause = if sample.interactive {
                    Cause::InteractiveSession
                } else if sustained {
                    Cause::ForeignGpu
                } else {
                    Cause::MemoryPressure
                };
                return Some(Transition {
                    from,
                    to: self.rung,
                    cause,
                });
            }
        }

        // ---- step up (recovery), hysteretic per §2.3: a full
        // clear interval before the first step, then one rung per
        // interval. Any pressure resets the clear clock, so a
        // boundary-straddling workload cannot flap the ladder.
        if !pressure_now && !mem_pressure {
            let clear_since = *self.clear_since.get_or_insert(now);
            let clear_for = now.duration_since(clear_since);
            let since_last_up = self.last_step_up.map(|t| now.duration_since(t));
            if self.rung > Rung::L0
                && clear_for >= self.cfg.recovery
                && since_last_up
                    .map(|d| d >= self.cfg.recovery)
                    .unwrap_or(true)
            {
                let from = self.rung;
                self.rung = from.up();
                self.last_step_up = Some(now);
                return Some(Transition {
                    from,
                    to: self.rung,
                    cause: Cause::Recovery,
                });
            }
        } else {
            self.clear_since = None;
        }
        None
    }
}

// ---------------------------------------------------------------------------
// System probe: /proc + nvidia-smi + loginctl, all best-effort.
// ---------------------------------------------------------------------------

/// The production probe. Every source is optional and fails to
/// `None`/`false`: a box where nothing can be measured reports
/// "no foreign work seen", and the ladder simply never yields —
/// the pre-ladder status quo, never a fabricated yield.
pub struct SystemProbe {
    /// systemd units whose MainPIDs count as platform (the rack).
    platform_units: Vec<String>,
    rack_pid_cache: Option<u32>,
}

impl SystemProbe {
    pub fn new(platform_units: Vec<String>) -> Self {
        Self {
            platform_units,
            rack_pid_cache: None,
        }
    }

    fn mem_available_pct() -> Option<f64> {
        let text = std::fs::read_to_string("/proc/meminfo").ok()?;
        let mut total = None;
        let mut avail = None;
        for line in text.lines() {
            let mut parts = line.split_whitespace();
            let (Some(label), Some(value)) = (parts.next(), parts.next()) else {
                continue;
            };
            match label {
                "MemTotal:" => total = value.parse::<f64>().ok(),
                "MemAvailable:" => avail = value.parse::<f64>().ok(),
                _ => {}
            }
        }
        match (total, avail) {
            (Some(t), Some(a)) if t > 0.0 => Some(100.0 * a / t),
            _ => None,
        }
    }

    /// Our own process tree (this service + descendants: the
    /// ingest lives here) plus the platform units' MainPIDs.
    fn platform_pids(&mut self) -> Vec<u32> {
        let mut pids = vec![std::process::id()];
        // Descendants via a /proc ppid walk.
        let mut ppid: Vec<(u32, u32)> = Vec::new();
        if let Ok(rd) = std::fs::read_dir("/proc") {
            for e in rd.flatten() {
                let name = e.file_name();
                let Some(pid) = name.to_str().and_then(|s| s.parse::<u32>().ok()) else {
                    continue;
                };
                if let Ok(stat) = std::fs::read_to_string(format!("/proc/{pid}/stat")) {
                    // comm may contain spaces/parens; ppid is the
                    // field after the LAST ')'.
                    if let Some(close) = stat.rfind(')') {
                        let rest: Vec<&str> = stat[close + 1..].split_whitespace().collect();
                        if let Some(pp) = rest.get(1).and_then(|s| s.parse::<u32>().ok()) {
                            ppid.push((pid, pp));
                        }
                    }
                }
            }
        }
        let mut grew = true;
        while grew {
            grew = false;
            for (pid, pp) in &ppid {
                if pids.contains(pp) && !pids.contains(pid) {
                    pids.push(*pid);
                    grew = true;
                }
            }
        }
        // Platform systemd units (the rack, if it is up).
        if self.rack_pid_cache.is_none() {
            for unit in &self.platform_units {
                if let Some(pid) = unit_main_pid(unit) {
                    self.rack_pid_cache = Some(pid);
                }
            }
        }
        if let Some(pid) = self.rack_pid_cache {
            // Drop the cache if that pid is gone (unit restarted).
            if std::path::Path::new(&format!("/proc/{pid}")).exists() {
                pids.push(pid);
            } else {
                self.rack_pid_cache = None;
            }
        }
        pids
    }

    fn foreign_gpu_pct(&mut self) -> Option<f64> {
        // nvidia-smi is the only source here that can ATTRIBUTE
        // load to processes. Aggregate counters (devfreq etc.)
        // cannot tell foreign load from our own embeds, so they
        // are deliberately not used: no attribution, no reading.
        let util = run_capture(
            "nvidia-smi",
            &[
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
        )?
        .trim()
        .parse::<f64>()
        .ok()?;
        let apps = run_capture(
            "nvidia-smi",
            &["--query-compute-apps=pid", "--format=csv,noheader"],
        )?;
        let platform = self.platform_pids();
        let foreign_present = apps
            .lines()
            .filter_map(|l| l.trim().parse::<u32>().ok())
            .any(|pid| !platform.contains(&pid));
        // A graphics-only foreign load (a game on the desktop)
        // holds no compute context; the interactive signal is the
        // ladder's coverage for that case, not this number.
        Some(if foreign_present { util } else { 0.0 })
    }

    fn interactive() -> bool {
        // systemd's idle hint is the honest activity signal: a
        // session exists on the Thor whenever Casey is logged in,
        // idle or not, and presence alone must not pin the
        // platform at a yielded rung forever.
        let Some(out) = run_capture("loginctl", &["--no-legend", "list-sessions"]) else {
            return false;
        };
        for line in out.lines() {
            let Some(id) = line.split_whitespace().next() else {
                continue;
            };
            let idle = run_capture(
                "loginctl",
                &["show-session", id, "-p", "IdleHint", "--value"],
            );
            let ty = run_capture("loginctl", &["show-session", id, "-p", "Type", "--value"]);
            match (idle, ty) {
                (Some(i), Some(t))
                    if i.trim() == "no" && (t.trim() == "wayland" || t.trim() == "x11") =>
                {
                    return true;
                }
                _ => {}
            }
        }
        false
    }
}

impl Probe for SystemProbe {
    fn sample(&mut self) -> LoadSample {
        LoadSample {
            foreign_gpu_pct: self.foreign_gpu_pct(),
            interactive: Self::interactive(),
            mem_available_pct: Self::mem_available_pct(),
        }
    }
}

fn unit_main_pid(unit: &str) -> Option<u32> {
    run_capture("systemctl", &["show", "-p", "MainPID", "--value", unit])?
        .trim()
        .parse::<u32>()
        .ok()
        .filter(|&p| p > 0)
}

fn run_capture(cmd: &str, args: &[&str]) -> Option<String> {
    let out = std::process::Command::new(cmd).args(args).output().ok()?;
    if out.status.success() {
        Some(String::from_utf8_lossy(&out.stdout).to_string())
    } else {
        None
    }
}

// ---------------------------------------------------------------------------
// Control file: the ladder's orders to the ingest.
// ---------------------------------------------------------------------------

/// What the service writes to `<ledger_dir>/control.json` — the
/// one control channel to the ingest (which polls it per frame;
/// the service passes the path via `$CONFLUENCE_CONTROL_FILE`
/// when it spawns the ingest). Plain JSON, hand-formatted like
/// everything else in this crate (no serde dependency).
#[derive(Debug, Clone)]
pub struct ControlState {
    pub rung: Rung,
    pub decision_enabled: bool,
    /// Effective per-stream decision budget, embed-seconds per
    /// rolling hour (§2.2 base × the rung's decision factor).
    pub budget_embed_s_per_hour: f64,
    pub reflective_enabled: bool,
    pub backfill_permitted: bool,
    pub reason: String,
}

impl ControlState {
    pub fn to_json(&self) -> String {
        format!(
            "{{\"rung\":\"{}\",\"decision_enabled\":{},\"budget_embed_s_per_hour\":{:.3},\"reflective_enabled\":{},\"backfill_permitted\":{},\"reason\":\"{}\",\"updated_wall_us\":{}}}",
            self.rung.name(),
            self.decision_enabled,
            self.budget_embed_s_per_hour,
            self.reflective_enabled,
            self.backfill_permitted,
            self.reason.replace('"', "'"),
            crate::ledger::epoch_us()
        )
    }

    pub fn write(&self, path: &str) -> std::io::Result<()> {
        std::fs::write(path, self.to_json())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg_fast() -> LadderConfig {
        LadderConfig {
            foreign_gpu_threshold_pct: 20.0,
            sustain: Duration::from_millis(50),
            recovery: Duration::from_millis(100),
            mem_pressure_pct: 10.0,
        }
    }

    fn foreign(pct: f64) -> LoadSample {
        LoadSample {
            foreign_gpu_pct: Some(pct),
            interactive: false,
            mem_available_pct: Some(50.0),
        }
    }

    fn clear() -> LoadSample {
        foreign(0.0)
    }

    #[test]
    fn foreign_load_must_sustain_before_it_yields() {
        let mut l = Ladder::new(cfg_fast());
        let t0 = Instant::now();
        // Samples every 20 ms at 50% foreign: no yield until the
        // 5 s-equivalent (here 50 ms) sustain has elapsed.
        assert!(l.evaluate(&foreign(50.0), t0).is_none());
        assert!(l
            .evaluate(&foreign(50.0), t0 + Duration::from_millis(20))
            .is_none());
        assert!(l
            .evaluate(&foreign(50.0), t0 + Duration::from_millis(40))
            .is_none());
        let tr = l
            .evaluate(&foreign(50.0), t0 + Duration::from_millis(60))
            .expect("sustained load yields");
        assert_eq!(
            (tr.from, tr.to, tr.cause),
            (Rung::L0, Rung::L1, Cause::ForeignGpu)
        );
    }

    #[test]
    fn ladder_walks_down_one_rung_per_evaluation_and_floors_at_l3() {
        let mut l = Ladder::new(cfg_fast());
        let t0 = Instant::now();
        let mut t = t0;
        // Prime the sustain clock.
        l.evaluate(&foreign(80.0), t);
        let mut seen = Vec::new();
        for _ in 0..8 {
            t += Duration::from_millis(20);
            if let Some(tr) = l.evaluate(&foreign(80.0), t) {
                seen.push(tr.to);
            }
        }
        assert_eq!(seen, vec![Rung::L1, Rung::L2, Rung::L3]);
        assert_eq!(l.rung(), Rung::L3, "no L4 without memory pressure");
    }

    /// Evaluate `sample` every 20 ms until the ladder reaches
    /// `target` (or the step budget runs out — then the caller's
    /// assert on the rung fails with the actual position).
    fn drive(l: &mut Ladder, sample: &LoadSample, t: &mut Instant, target: Rung) {
        for _ in 0..50 {
            if l.rung() == target {
                return;
            }
            *t += Duration::from_millis(20);
            l.evaluate(sample, *t);
        }
    }

    #[test]
    fn memory_pressure_unlocks_l4() {
        let mut l = Ladder::new(cfg_fast());
        let mut t = Instant::now();
        l.evaluate(&foreign(80.0), t);
        drive(&mut l, &foreign(80.0), &mut t, Rung::L3);
        assert_eq!(l.rung(), Rung::L3);
        let starved = LoadSample {
            mem_available_pct: Some(4.0),
            ..foreign(80.0)
        };
        t += Duration::from_millis(20);
        let tr = l.evaluate(&starved, t).expect("mem pressure steps to L4");
        assert_eq!(tr.to, Rung::L4);
    }

    #[test]
    fn memory_pressure_alone_walks_the_ladder() {
        let mut l = Ladder::new(cfg_fast());
        let t0 = Instant::now();
        let starved = LoadSample {
            foreign_gpu_pct: Some(0.0),
            interactive: false,
            mem_available_pct: Some(2.0),
        };
        let mut seen = Vec::new();
        for i in 0..6 {
            if let Some(tr) = l.evaluate(&starved, t0 + Duration::from_millis(20 * i)) {
                seen.push((tr.to, tr.cause));
            }
        }
        assert_eq!(seen.len(), 4);
        assert_eq!(seen[3], (Rung::L4, Cause::MemoryPressure));
    }

    #[test]
    fn interactive_signal_yields_without_sustain() {
        let mut l = Ladder::new(cfg_fast());
        let s = LoadSample {
            foreign_gpu_pct: Some(0.0),
            interactive: true,
            mem_available_pct: Some(50.0),
        };
        let tr = l
            .evaluate(&s, Instant::now())
            .expect("interactive activity yields on the first sample");
        assert_eq!(tr.cause, Cause::InteractiveSession);
        assert_eq!(tr.to, Rung::L1);
    }

    #[test]
    fn recovery_is_hysteretic_one_rung_per_interval() {
        let mut l = Ladder::new(cfg_fast());
        // Drive to L3.
        let mut t = Instant::now();
        l.evaluate(&foreign(90.0), t);
        drive(&mut l, &foreign(90.0), &mut t, Rung::L3);
        assert_eq!(l.rung(), Rung::L3);
        // Pressure ends at t. Clear for less than the recovery
        // interval: nothing.
        let clear_start = t + Duration::from_millis(20);
        assert!(l.evaluate(&clear(), clear_start).is_none());
        assert!(l
            .evaluate(&clear(), clear_start + Duration::from_millis(80))
            .is_none());
        // A full interval of clear: exactly one step up.
        let tr = l
            .evaluate(&clear(), clear_start + Duration::from_millis(110))
            .expect("one step up after a clear interval");
        assert_eq!((tr.from, tr.to), (Rung::L3, Rung::L2));
        // The next step needs another full interval.
        assert!(l
            .evaluate(&clear(), clear_start + Duration::from_millis(150))
            .is_none());
        let tr = l
            .evaluate(&clear(), clear_start + Duration::from_millis(220))
            .expect("second step up after a second interval");
        assert_eq!((tr.from, tr.to), (Rung::L2, Rung::L1));
    }

    #[test]
    fn boundary_straddling_pressure_never_yields_or_flaps() {
        let mut l = Ladder::new(cfg_fast());
        let t0 = Instant::now();
        // Alternate foreign/clear every 20 ms for a simulated
        // 10 minutes: the sustain clock resets on every clear
        // sample, so the ladder must never move.
        for i in 0..30_000u64 {
            let s = if i % 2 == 0 { foreign(75.0) } else { clear() };
            assert!(
                l.evaluate(&s, t0 + Duration::from_millis(20 * i)).is_none(),
                "flap at step {i}"
            );
        }
        assert_eq!(l.rung(), Rung::L0);
        // And once yielded, brief clear blips (< recovery) must
        // not step it back up either.
        let mut t = t0;
        l.evaluate(&foreign(90.0), t);
        drive(&mut l, &foreign(90.0), &mut t, Rung::L3);
        assert_eq!(l.rung(), Rung::L3);
        for i in 0..500u64 {
            let s = if i % 2 == 0 { clear() } else { foreign(75.0) };
            assert!(l.evaluate(&s, t + Duration::from_millis(20 * i)).is_none());
        }
        assert_eq!(l.rung(), Rung::L3);
    }

    #[test]
    fn capabilities_match_the_spec_rungs() {
        assert!(capabilities(Rung::L0).backfill_permitted);
        assert!(!capabilities(Rung::L1).backfill_permitted);
        assert!(capabilities(Rung::L1).decision_permitted);
        assert_eq!(capabilities(Rung::L2).decision_factor, 0.5);
        assert!(!capabilities(Rung::L2).reflective_permitted);
        assert!(!capabilities(Rung::L3).decision_permitted);
        assert!(!capabilities(Rung::L4).decision_permitted);
        assert!(capabilities(Rung::L4).unload_models);
    }
}
