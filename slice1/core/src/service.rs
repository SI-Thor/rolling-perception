//! The live service loop.
//!
//! Flow: [ingest command] --records + frame_end controls, JSONL-->
//! this loop --one frame at a time--> LivePipeline --> Ledger.
//!
//! Records are the exact wave-3 driver schema
//! (`harbor_watch::record::InputRecord`) plus an optional `embed_ms`
//! field the ingest stamps with the rack call's measured latency.
//! Frame boundaries are control lines:
//! `{"control":"frame_end","frame":N,"t_capture_us":<epoch µs>,
//!   "nominated":K,"gate_diff":G}`.
//!
//! Rack lifecycle: the decision embeds are made by the *ingest*
//! against the JEV rack, so before spawning it this service checks
//! the rack's /health. If down and `rack_autostart`, it starts the
//! rack via systemctl, logs that it did, and — on exit, iff it
//! started it and `stop_rack_on_exit` — stops it again. Casey's box
//! is left as it was found.
//!
//! Tenancy (§2.3): a sampler thread watches the host for foreign
//! work; the yield ladder's current orders are written to
//! `<ledger_dir>/control.json` before the ingest spawns (the path
//! is handed over via `$CONFLUENCE_CONTROL_FILE`) and rewritten on
//! every rung transition. The ingest polls it per frame: budget
//! admission in rank order, reflex-only frames when the decision
//! tier is yielded off. Every transition is receipted in
//! events.jsonl as a `yield_rung` service event.

use crate::config::Config;
use crate::ledger::{epoch_us, Ledger};
use crate::live::LivePipeline;
use crate::tenancy::{ControlState, Ladder, LadderConfig, LoadSample, Probe, Rung, SystemProbe};
use harbor_watch::pipeline::Config as PipeConfig;
use harbor_watch::record::{parse_record, InputRecord};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Debug, Default)]
pub struct Summary {
    pub frames: u64,
    pub events: u64,
    pub embeds: u64,
    pub embeds_spent_s: f64,
    pub embed_everything_estimate_s: f64,
    pub verdict_latency_p50_ms: f64,
    pub verdict_latency_max_ms: f64,
    pub rack_started_by_me: bool,
    pub rack_stopped_by_me: bool,
    /// Yield-ladder rung (§2.3) at the end of the run.
    pub final_rung: String,
}

/// Extract a numeric field from a JSON line without a JSON parser
/// (same deliberately small approach as harbor-watch's record codec).
fn json_num(line: &str, key: &str) -> Option<f64> {
    let pat = format!("\"{key}\"");
    let at = line.find(&pat)?;
    let rest = &line[at + pat.len()..];
    let colon = rest.find(':')?;
    let rest = rest[colon + 1..].trim_start();
    let end = rest
        .find(|c: char| c == ',' || c == '}' || c.is_whitespace())
        .unwrap_or(rest.len());
    rest[..end].parse::<f64>().ok()
}

fn rack_health(rack_url: &str) -> bool {
    rack_health_timed(rack_url, Duration::from_secs(3))
}

fn rack_health_timed(rack_url: &str, timeout: Duration) -> bool {
    // Minimal HTTP/1.0 GET on a raw socket: enough for /health.
    let addr = rack_url
        .trim_start_matches("http://")
        .trim_start_matches("https://")
        .trim_end_matches('/');
    let Ok(mut sock) = TcpStream::connect(addr) else {
        return false;
    };
    let _ = sock.set_read_timeout(Some(timeout));
    let _ = sock.set_write_timeout(Some(timeout));
    if sock
        .write_all(b"GET /health HTTP/1.0\r\nHost: x\r\n\r\n")
        .is_err()
    {
        return false;
    }
    let mut buf = String::new();
    let _ = sock.take(256).read_to_string(&mut buf);
    buf.starts_with("HTTP/1.1 200") || buf.starts_with("HTTP/1.0 200")
}

fn systemctl(action: &str) -> bool {
    Command::new("sudo")
        .args(["-n", "systemctl", action, "jev-rack"])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// The tenancy runtime: a sampler thread feeding the yield
/// ladder (§2.3), the ladder itself, and the L4 rack actions.
/// The main loop owns the ledger (single writer); the sampler
/// only publishes samples through the shared slot.
struct TenancyRuntime {
    ladder: Ladder,
    shared: Arc<Mutex<Option<(u64, LoadSample, Instant)>>>,
    stop: Arc<AtomicBool>,
    handle: Option<std::thread::JoinHandle<()>>,
    last_seq: u64,
    control_path: String,
    /// L4 stopped the rack (and this service owned it).
    models_unloaded: bool,
    /// A tenancy reload was issued; decision stays off until the
    /// rack answers health again (reload is paid on recovery,
    /// §2.3 L4 — 11.9 s cold, so it starts at the L4 exit step,
    /// not when decision is next wanted).
    reload_pending: bool,
}

impl TenancyRuntime {
    fn start(cfg: &Config, mut probe: Box<dyn Probe>) -> Self {
        let shared: Arc<Mutex<Option<(u64, LoadSample, Instant)>>> = Arc::new(Mutex::new(None));
        let stop = Arc::new(AtomicBool::new(false));
        let (s2, stop2) = (shared.clone(), stop.clone());
        let interval = Duration::from_millis(cfg.tenancy_sample_ms.max(10));
        let handle = std::thread::spawn(move || {
            let mut seq: u64 = 0;
            loop {
                if stop2.load(Ordering::Relaxed) {
                    break;
                }
                let sample = probe.sample();
                seq += 1;
                if let Ok(mut slot) = s2.lock() {
                    *slot = Some((seq, sample, Instant::now()));
                }
                // Sleep the interval in short slices so shutdown
                // is prompt.
                let mut waited = Duration::ZERO;
                while waited < interval && !stop2.load(Ordering::Relaxed) {
                    std::thread::sleep(Duration::from_millis(25));
                    waited += Duration::from_millis(25);
                }
            }
        });
        Self {
            ladder: Ladder::new(LadderConfig {
                foreign_gpu_threshold_pct: 20.0,
                sustain: Duration::from_secs_f64(cfg.tenancy_sustain_s),
                recovery: Duration::from_secs_f64(cfg.tenancy_recovery_s),
                mem_pressure_pct: cfg.mem_pressure_pct,
            }),
            shared,
            stop,
            handle: Some(handle),
            last_seq: 0,
            control_path: format!("{}/control.json", cfg.ledger_dir),
            models_unloaded: false,
            reload_pending: false,
        }
    }

    fn shutdown(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
    }

    fn control_state(&self, cfg: &Config, rack_up: bool) -> ControlState {
        let caps = self.ladder.capabilities();
        ControlState {
            rung: self.ladder.rung(),
            decision_enabled: caps.decision_permitted && rack_up && !self.reload_pending,
            budget_embed_s_per_hour: cfg.budget_embed_s_per_hour * caps.decision_factor,
            reflective_enabled: caps.reflective_permitted,
            backfill_permitted: caps.backfill_permitted,
            reason: String::new(),
        }
    }

    fn write_control(&self, cfg: &Config, rack_up: bool, reason: &str) {
        let mut st = self.control_state(cfg, rack_up);
        st.reason = reason.to_string();
        if let Err(e) = st.write(&self.control_path) {
            eprintln!("[confluence-watch] tenancy control write failed: {e}");
        }
    }

    /// Per-frame tenancy tick: poll a pending rack reload, then —
    /// if the sampler produced a fresh sample — evaluate the
    /// ladder and act on any transition (receipts, ledger fields,
    /// control file, L4 rack unload / recovery reload).
    fn tick(
        &mut self,
        ledger: &mut Ledger,
        cfg: &Config,
        rack_started_by_me: bool,
        rack_up: &mut bool,
        rack_stopped_by_me: &mut bool,
    ) {
        // Reload poll: cheap, every tick, short timeout.
        if self.reload_pending && rack_health_timed(&cfg.rack_url, Duration::from_millis(300)) {
            *rack_up = true;
            ledger.rack_up = true;
            self.reload_pending = false;
            ledger
                .service_event("rack_up", "rack healthy again after tenancy L4 reload")
                .ok();
            self.write_control(cfg, *rack_up, "recovered");
        }

        let fresh = {
            let slot = self.shared.lock().ok();
            match slot.and_then(|s| *s) {
                Some((seq, sample, at)) if seq != self.last_seq => {
                    self.last_seq = seq;
                    Some((sample, at))
                }
                _ => None,
            }
        };
        let Some((sample, at)) = fresh else {
            return;
        };
        let Some(tr) = self.ladder.evaluate(&sample, at) else {
            return;
        };

        // ---- receipt the transition with the figures that caused it
        ledger.yield_rung = tr.to.name().to_string();
        ledger.yield_reason = tr.cause.name().to_string();
        let caps = self.ladder.capabilities();
        ledger.budget_effective_s = Some(cfg.budget_embed_s_per_hour * caps.decision_factor);
        ledger
            .service_event(
                "yield_rung",
                &format!(
                    "{} -> {} cause={} foreign_gpu_pct={} mem_available_pct={} decision_factor={:.2}",
                    tr.from.name(),
                    tr.to.name(),
                    tr.cause.name(),
                    sample
                        .foreign_gpu_pct
                        .map(|v| format!("{v:.1}"))
                        .unwrap_or_else(|| "unknown".into()),
                    sample
                        .mem_available_pct
                        .map(|v| format!("{v:.1}"))
                        .unwrap_or_else(|| "unknown".into()),
                    caps.decision_factor
                ),
            )
            .ok();

        // ---- L4 actions: unload decision models we own; reload
        // them on the way back up.
        if tr.to == Rung::L4 && *rack_up {
            if rack_started_by_me {
                ledger
                    .service_event(
                        "rack_stop",
                        "rung L4: decision models unloaded by tenancy (this service owns the rack)",
                    )
                    .ok();
                if systemctl("stop") {
                    *rack_up = false;
                    ledger.rack_up = false;
                    *rack_stopped_by_me = true;
                    self.models_unloaded = true;
                    ledger.models_unloaded = true;
                } else {
                    ledger
                        .service_event(
                            "rack_stop_failed",
                            "rung L4: systemctl stop jev-rack failed; decision tier stays off, models still loaded",
                        )
                        .ok();
                }
            } else {
                ledger
                    .service_event(
                        "yield_models_not_owned",
                        "rung L4: decision models are not owned by this service; decision tier suspended, models left running",
                    )
                    .ok();
            }
        }
        if tr.from == Rung::L4 && self.models_unloaded {
            ledger
                .service_event(
                    "rack_start",
                    "tenancy recovery: reloading decision models (reload cost paid on recovery)",
                )
                .ok();
            if systemctl("start") {
                self.reload_pending = true;
            } else {
                ledger
                    .service_event(
                        "rack_start_failed",
                        "tenancy recovery: systemctl start jev-rack failed; decision tier stays off until the rack returns",
                    )
                    .ok();
                self.reload_pending = true; // health poll notices a manual return too
            }
        }
        self.write_control(cfg, *rack_up, tr.cause.name());
    }
}

/// Parse a reflex control line from the ingest:
/// `{"control":"reflex","frame":F,"t_capture_us":T,"nominated_tiles":[..],...}`
/// Returns (frame, t_capture_us, nominated tiles).
fn parse_reflex(line: &str) -> Option<(u32, u64, Vec<u32>)> {
    let frame = json_num(line, "frame")? as u32;
    let t_capture_us = json_num(line, "t_capture_us").unwrap_or(0.0) as u64;
    let mut tiles = Vec::new();
    if let Some(at) = line.find("\"nominated_tiles\"") {
        let rest = &line[at..];
        if let (Some(open), Some(close)) = (rest.find('['), rest.find(']')) {
            for part in rest[open + 1..close].split(',') {
                if let Ok(t) = part.trim().parse::<u32>() {
                    tiles.push(t);
                }
            }
        }
    }
    Some((frame, t_capture_us, tiles))
}

pub fn run(cfg: &Config) -> Result<Summary, String> {
    let probe: Option<Box<dyn Probe>> = if cfg.tenancy {
        let units = cfg
            .tenancy_platform_units
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();
        Some(Box::new(SystemProbe::new(units)))
    } else {
        None
    };
    run_inner(cfg, probe)
}

/// The service loop with an injected tenancy probe (tests drive
/// the yield ladder with scripted host pressure — see
/// tests/tenancy.rs).
pub fn run_with_probe(cfg: &Config, probe: Box<dyn Probe>) -> Result<Summary, String> {
    run_inner(cfg, Some(probe))
}

fn run_inner(cfg: &Config, probe: Option<Box<dyn Probe>>) -> Result<Summary, String> {
    let mut ledger = Ledger::open(
        &cfg.ledger_dir,
        &cfg.stream_id,
        cfg.threshold,
        cfg.alpha,
        cfg.soak,
    )
    .map_err(|e| format!("ledger open: {e}"))?;
    ledger
        .service_event("start", &format!("stream {} starting", cfg.stream_id))
        .ok();
    ledger.budget_base_s = Some(cfg.budget_embed_s_per_hour);
    ledger.budget_effective_s = Some(cfg.budget_embed_s_per_hour);

    // ---- rack lifecycle: ensure up before ingest starts embedding
    let mut rack_started_by_me = false;
    let mut rack_stopped_by_me = false;
    let mut up = rack_health(&cfg.rack_url);
    if !up && cfg.rack_autostart {
        eprintln!("[confluence-watch] rack down at startup; starting jev-rack");
        ledger
            .service_event("rack_start", "rack was down; started by this service")
            .ok();
        if systemctl("start") {
            for _ in 0..60 {
                std::thread::sleep(Duration::from_secs(1));
                if rack_health(&cfg.rack_url) {
                    up = true;
                    break;
                }
            }
            rack_started_by_me = up;
        }
    }
    ledger.rack_up = up;
    ledger.rack_started_by_me = rack_started_by_me;
    ledger.write_all().ok();
    if !up {
        return Err(format!(
            "JEV rack not healthy at {} (rack_autostart={})",
            cfg.rack_url, cfg.rack_autostart
        ));
    }
    let mut rack_up = up;

    // ---- tenancy: start the sampler + ladder (if a probe is
    // configured) and publish the initial control file BEFORE the
    // ingest spawns — the ingest polls it per frame. With tenancy
    // off there is no ladder, but the control file still carries
    // the §2.2 budget at its full figure: metering becoming
    // enforcement is not a tenancy-only feature.
    let control_path = format!("{}/control.json", cfg.ledger_dir);
    let mut tenancy: Option<TenancyRuntime> = probe.map(|p| TenancyRuntime::start(cfg, p));
    match &tenancy {
        Some(t) => t.write_control(cfg, rack_up, "start"),
        None => {
            let st = ControlState {
                rung: Rung::L0,
                decision_enabled: rack_up,
                budget_embed_s_per_hour: cfg.budget_embed_s_per_hour,
                reflective_enabled: true,
                backfill_permitted: true,
                reason: "tenancy_off".into(),
            };
            let _ = st.write(&control_path);
        }
    }

    // ---- spawn ingest (or read our own stdin)
    let mut child: Option<Child> = None;
    let mut reader: Box<dyn BufRead> = if cfg.ingest_cmd.is_empty() {
        Box::new(BufReader::new(std::io::stdin()))
    } else {
        let mut c = Command::new("sh")
            .arg("-c")
            .arg(&cfg.ingest_cmd)
            .env("CONFLUENCE_CONTROL_FILE", &control_path)
            .stdout(Stdio::piped())
            .spawn()
            .map_err(|e| format!("spawn ingest: {e}"))?;
        let out = c.stdout.take().expect("piped stdout");
        child = Some(c);
        Box::new(BufReader::new(out))
    };

    let pipe_cfg = PipeConfig {
        threshold: cfg.threshold,
        alpha: cfg.alpha,
        focus_k: cfg.focus_k,
    };
    let mut pipeline: Option<LivePipeline> = None;
    let mut pending: Vec<InputRecord> = Vec::new();
    let mut pending_embed_ms: Vec<f64> = Vec::new();
    let mut pending_reflex: Option<(u32, u64, Vec<u32>)> = None;
    let mut last_frame_wall: Option<std::time::Instant> = None;
    let mut frames_processed: u64 = 0;
    let mut frames_received: u64 = 0;
    let mut verdict_latencies: Vec<f64> = Vec::new();
    let mut summary = Summary::default();

    let mut line = String::new();
    loop {
        line.clear();
        let n = reader
            .read_line(&mut line)
            .map_err(|e| format!("read ingest: {e}"))?;
        if n == 0 {
            break; // ingest EOF: clean end of stream
        }
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if line.contains("\"control\"") {
            if line.contains("\"frame_end\"") {
                let frame = json_num(line, "frame").unwrap_or(0.0) as u32;
                let t_capture_us = json_num(line, "t_capture_us").unwrap_or(0.0) as u64;
                let nominated = json_num(line, "nominated").unwrap_or(0.0) as u64;
                if let Some(g) = json_num(line, "gate_diff") {
                    ledger.gate_diff = Some(g);
                }
                // Budget admission sheds, counted by the ingest:
                // logged here, never silently dropped (§2.1).
                ledger.stats.tiles_shed += json_num(line, "shed").unwrap_or(0.0) as u64;
                frames_received += 1;
                // Lens rhythm: wall interval between frame arrivals.
                let now = std::time::Instant::now();
                if let Some(prev) = last_frame_wall {
                    ledger.observe_period(now.duration_since(prev).as_secs_f64() * 1000.0);
                }
                last_frame_wall = Some(now);

                // Tenancy tick: a fresh host sample may move the
                // yield ladder; the new control governs the NEXT
                // frame (this frame was embedded under the last).
                if let Some(t) = tenancy.as_mut() {
                    t.tick(
                        &mut ledger,
                        cfg,
                        rack_started_by_me,
                        &mut rack_up,
                        &mut rack_stopped_by_me,
                    );
                }

                if pipeline.is_none() && !pending.is_empty() {
                    let dim = pending[0].embedding.len();
                    pipeline = Some(LivePipeline::new(dim, pipe_cfg.clone()));
                }
                let reflex = pending_reflex
                    .take()
                    .filter(|(f, _, _)| *f == frame && pending.is_empty());
                if let Some((_, reflex_t_capture, reflex_tiles)) = reflex {
                    // Reflex-only frame: nothing was embedded (the
                    // decision tier is yielded off, or its budget
                    // is spent). The frame still publishes its
                    // basis — an unperceived-change verdict.
                    let rung = tenancy
                        .as_ref()
                        .map(|t| t.ladder.rung())
                        .unwrap_or(Rung::L0);
                    let basis = if rung >= Rung::L3 {
                        format!(
                            "decision tier yielded at rung {} ({}); reflex diff only",
                            rung.name(),
                            ledger.yield_reason
                        )
                    } else {
                        "decision budget exhausted; reflex diff only".to_string()
                    };
                    ledger
                        .record_reflex_frame(frame, reflex_t_capture, &reflex_tiles, &basis)
                        .map_err(|e| format!("ledger write: {e}"))?;
                } else if let Some(p) = pipeline.as_mut() {
                    let recs = std::mem::take(&mut pending);
                    let emb_ms = std::mem::take(&mut pending_embed_ms);
                    let embedded = recs.len() as u64;
                    let pending_now = frames_received - frames_processed - 1;
                    let out = p.process_frame(frame, recs);
                    if let Some(lat) = ledger
                        .record_frame(
                            &out,
                            t_capture_us,
                            nominated,
                            embedded,
                            &emb_ms,
                            pending_now,
                        )
                        .map_err(|e| format!("ledger write: {e}"))?
                    {
                        verdict_latencies.push(lat);
                    }
                } else {
                    // Frames with no records yet (pipeline not sized):
                    // count them so state stays honest.
                    ledger.stats.frames_seen += 1;
                    ledger.stats.tiles_nominated += nominated;
                    ledger.write_all().ok();
                }
                frames_processed += 1;

                if cfg.max_frames > 0 && frames_processed >= cfg.max_frames as u64 {
                    break;
                }
                if !cfg.stop_file.is_empty() && std::path::Path::new(&cfg.stop_file).exists() {
                    eprintln!("[confluence-watch] stop file seen; shutting down");
                    break;
                }
            } else if line.contains("\"reflex\"") {
                if let Some(r) = parse_reflex(line) {
                    pending_reflex = Some(r);
                }
            }
            continue;
        }
        match parse_record(line) {
            Ok(rec) => {
                if let Some(ms) = json_num(line, "embed_ms") {
                    pending_embed_ms.push(ms);
                }
                pending.push(rec);
            }
            Err(e) => {
                eprintln!("[confluence-watch] skipping malformed line: {e}");
            }
        }
    }

    if let Some(mut c) = child {
        let _ = c.kill();
        let _ = c.wait();
    }
    if let Some(t) = tenancy.as_mut() {
        t.shutdown();
    }

    summary.frames = ledger.stats.frames_seen;
    summary.events = ledger.stats.events_published;
    summary.embeds = ledger.stats.tiles_embedded;
    summary.embeds_spent_s = ledger.stats.embeds_spent_s;
    summary.embed_everything_estimate_s = ledger.stats.embed_everything_estimate_s();
    let (p50, _) = crate::ledger::percentiles(&verdict_latencies);
    summary.verdict_latency_p50_ms = p50;
    summary.verdict_latency_max_ms = verdict_latencies.iter().cloned().fold(0.0, f64::max);
    summary.rack_started_by_me = rack_started_by_me;
    summary.rack_stopped_by_me = rack_stopped_by_me;
    summary.final_rung = tenancy
        .as_ref()
        .map(|t| t.ladder.rung().name().to_string())
        .unwrap_or_else(|| "L0".into());

    // ---- rack lifecycle: restore as found. Tenancy may already
    // have stopped the rack at L4 (that stop counts); and if L4
    // unloaded it but the operator's exit policy is to leave the
    // rack running, reload it — the box is left as it was found.
    let models_unloaded = tenancy.as_ref().map(|t| t.models_unloaded).unwrap_or(false);
    if rack_started_by_me && cfg.stop_rack_on_exit && rack_up {
        eprintln!("[confluence-watch] stopping jev-rack (this service started it)");
        ledger
            .service_event("rack_stop", "rack stopped by this service (it started it)")
            .ok();
        if systemctl("stop") {
            summary.rack_stopped_by_me = true;
            ledger.rack_up = false;
        }
    } else if models_unloaded && rack_started_by_me {
        eprintln!("[confluence-watch] restarting jev-rack (tenancy unloaded it; exit policy leaves it running)");
        ledger
            .service_event(
                "rack_start",
                "rack restarted at exit (tenancy L4 had unloaded it; stop_rack_on_exit is false)",
            )
            .ok();
        if systemctl("start") {
            summary.rack_stopped_by_me = false;
        }
    }
    ledger
        .service_event(
            "stop",
            &format!(
                "frames={} events={} embeds={}",
                summary.frames, summary.events, summary.embeds
            ),
        )
        .ok();
    ledger.write_all().ok();
    let _ = epoch_us();
    Ok(summary)
}
