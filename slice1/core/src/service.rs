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

use crate::config::Config;
use crate::ledger::{epoch_us, Ledger};
use crate::live::LivePipeline;
use harbor_watch::pipeline::Config as PipeConfig;
use harbor_watch::record::{parse_record, InputRecord};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::time::Duration;

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
    // Minimal HTTP/1.0 GET on a raw socket: enough for /health.
    let addr = rack_url
        .trim_start_matches("http://")
        .trim_start_matches("https://")
        .trim_end_matches('/');
    let Ok(mut sock) = TcpStream::connect(addr) else {
        return false;
    };
    let _ = sock.set_read_timeout(Some(Duration::from_secs(3)));
    let _ = sock.set_write_timeout(Some(Duration::from_secs(3)));
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

pub fn run(cfg: &Config) -> Result<Summary, String> {
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

    // ---- rack lifecycle: ensure up before ingest starts embedding
    let mut rack_started_by_me = false;
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

    // ---- spawn ingest (or read our own stdin)
    let mut child: Option<Child> = None;
    let mut reader: Box<dyn BufRead> = if cfg.ingest_cmd.is_empty() {
        Box::new(BufReader::new(std::io::stdin()))
    } else {
        let mut c = Command::new("sh")
            .arg("-c")
            .arg(&cfg.ingest_cmd)
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
    let mut last_frame_wall: Option<std::time::Instant> = None;
    let mut frames_processed: u64 = 0;
    let mut frames_received: u64 = 0;
    let mut verdict_latencies: Vec<f64> = Vec::new();
    let mut summary = Summary::default();

    let mut line = String::new();
    loop {
        line.clear();
        let n = reader.read_line(&mut line).map_err(|e| format!("read ingest: {e}"))?;
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
                frames_received += 1;
                // Lens rhythm: wall interval between frame arrivals.
                let now = std::time::Instant::now();
                if let Some(prev) = last_frame_wall {
                    ledger.observe_period(now.duration_since(prev).as_secs_f64() * 1000.0);
                }
                last_frame_wall = Some(now);

                if pipeline.is_none() && !pending.is_empty() {
                    let dim = pending[0].embedding.len();
                    pipeline = Some(LivePipeline::new(dim, pipe_cfg.clone()));
                }
                if let Some(p) = pipeline.as_mut() {
                    let recs = std::mem::take(&mut pending);
                    let emb_ms = std::mem::take(&mut pending_embed_ms);
                    let embedded = recs.len() as u64;
                    let pending_now = frames_received - frames_processed - 1;
                    let out = p.process_frame(frame, recs);
                    if let Some(lat) =
                        ledger
                            .record_frame(&out, t_capture_us, nominated, embedded, &emb_ms, pending_now)
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
                if !cfg.stop_file.is_empty()
                    && std::path::Path::new(&cfg.stop_file).exists()
                {
                    eprintln!("[confluence-watch] stop file seen; shutting down");
                    break;
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

    summary.frames = ledger.stats.frames_seen;
    summary.events = ledger.stats.events_published;
    summary.embeds = ledger.stats.tiles_embedded;
    summary.embeds_spent_s = ledger.stats.embeds_spent_s;
    summary.embed_everything_estimate_s = ledger.stats.embed_everything_estimate_s();
    let (p50, _) = crate::ledger::percentiles(&verdict_latencies);
    summary.verdict_latency_p50_ms = p50;
    summary.verdict_latency_max_ms =
        verdict_latencies.iter().cloned().fold(0.0, f64::max);
    summary.rack_started_by_me = rack_started_by_me;

    // ---- rack lifecycle: restore as found
    if rack_started_by_me && cfg.stop_rack_on_exit {
        eprintln!("[confluence-watch] stopping jev-rack (this service started it)");
        ledger
            .service_event("rack_stop", "rack stopped by this service (it started it)")
            .ok();
        summary.rack_stopped_by_me = systemctl("stop");
        ledger.rack_up = false;
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
