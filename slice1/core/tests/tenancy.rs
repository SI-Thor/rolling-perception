//! Yield-ladder integration tests (§2.3): the full service loop
//! driven by a scripted tenancy probe (host pressure as a
//! recording, not a live box) and a fake ingest that honours the
//! control file the way ingest.py does — records when decision is
//! enabled, reflex lines when it is not.
//!
//! Timings are the spec's ratios at test scale: sample 20 ms,
//! sustain 50 ms, recovery 100 ms (config carries the knobs; the
//! spec defaults are 2000 ms / 5 s / 60 s). Assertions check the
//! ORDER of rung transitions and their effects (embeds stop,
//! reflex verdicts publish, embeds resume), never exact frames.

use confluence_watch::config::Config;
use confluence_watch::service;
use confluence_watch::tenancy::{LoadSample, Probe};
use std::io::Write as _;

fn tempdir(tag: &str) -> String {
    let d = std::env::temp_dir().join(format!(
        "confluence-watch-tenancy-{tag}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d.to_string_lossy().to_string()
}

/// A probe that plays back a script of samples; the last one
/// repeats when the script runs out.
struct ScriptProbe {
    script: Vec<LoadSample>,
    idx: usize,
}

impl Probe for ScriptProbe {
    fn sample(&mut self) -> LoadSample {
        let s = self
            .script
            .get(self.idx)
            .copied()
            .unwrap_or_else(|| *self.script.last().expect("non-empty script"));
        self.idx += 1;
        s
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

/// Fake ingest: two tiles per frame, 100 ms embed stamps, honours
/// $CONFLUENCE_CONTROL_FILE exactly like ingest.py's contract —
/// decision off ⇒ a reflex line and no records.
const FAKE_INGEST: &str = r#"
import json, os, time
ctl = os.environ.get("CONFLUENCE_CONTROL_FILE", "")
emb = [0.01] * 8
frame = 0
while True:
    decision = True
    try:
        with open(ctl) as fh:
            decision = bool(json.load(fh).get("decision_enabled", True))
    except Exception:
        decision = True
    t = int(time.time() * 1e6)
    if decision:
        for tile in (0, 1):
            print(json.dumps({"seq": 0, "frame": frame, "tile": tile,
                              "t_arrival_us": t, "diff_score": 9.0,
                              "embed_ms": 100.0, "embedding": emb}), flush=True)
    else:
        print(json.dumps({"control": "reflex", "frame": frame,
                          "t_capture_us": t, "nominated_tiles": [0, 1],
                          "decision_enabled": False}), flush=True)
    print(json.dumps({"control": "frame_end", "frame": frame,
                      "t_capture_us": t, "nominated": 2, "shed": 0,
                      "gate_diff": 3.0}), flush=True)
    frame += 1
    time.sleep(0.012)
"#;

fn stub_rack() -> String {
    use std::io::Read;
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let addr = listener.local_addr().unwrap();
    std::thread::spawn(move || {
        for mut s in listener.incoming().flatten() {
            let mut buf = [0u8; 512];
            let _ = s.read(&mut buf);
            let _ = s.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}");
        }
    });
    format!("http://{addr}")
}

fn test_config(dir: &str, max_frames: u32) -> (Config, String) {
    let script_path = format!("{dir}/fake_ingest.py");
    std::fs::write(&script_path, FAKE_INGEST).unwrap();
    let cfg = Config {
        stream_id: "tenancy-test".into(),
        ledger_dir: format!("{dir}/ledger"),
        ingest_cmd: format!("python3 {script_path}"),
        rack_url: stub_rack(),
        rack_autostart: false,
        stop_rack_on_exit: true,
        budget_embed_s_per_hour: 1.0e9,
        tenancy: true,
        tenancy_sample_ms: 20,
        tenancy_sustain_s: 0.05,
        tenancy_recovery_s: 0.1,
        mem_pressure_pct: 10.0,
        max_frames,
        ..Config::default()
    };
    (cfg, script_path)
}

/// The rung sequence from the yield_rung receipts, in order.
fn rung_transitions(events: &str) -> Vec<(String, String)> {
    events
        .lines()
        .filter(|l| l.contains("\"yield_rung\""))
        .filter_map(|l| {
            let msg = l.split("\"msg\":\"").nth(1)?;
            let mut parts = msg.split_whitespace();
            let from = parts.next()?.to_string();
            let arrow = parts.next()?;
            let to = parts.next()?.to_string();
            assert_eq!(arrow, "->");
            Some((from, to))
        })
        .collect()
}

#[test]
fn ladder_yields_under_foreign_load_and_recovers_with_hysteresis() {
    let dir = tempdir("yield");
    let (cfg, _) = test_config(&dir, 140);
    // ~40 samples of heavy foreign load (a wide margin over the
    // ingest's startup time), then clear forever.
    let mut script: Vec<LoadSample> = (0..40).map(|_| foreign(60.0)).collect();
    script.push(clear());
    let summary = service::run_with_probe(&cfg, Box::new(ScriptProbe { script, idx: 0 }))
        .expect("service run");

    let events = std::fs::read_to_string(format!("{}/events.jsonl", cfg.ledger_dir)).unwrap();
    let transitions = rung_transitions(&events);
    let downs: Vec<&(String, String)> = transitions
        .iter()
        .take_while(|(f, t)| rung_rank(t) > rung_rank(f))
        .collect();
    assert_eq!(
        downs.len(),
        3,
        "expected L0->L1->L2->L3 under sustained load, got {transitions:?}"
    );
    assert_eq!(downs[0].1, "L1");
    assert_eq!(downs[1].1, "L2");
    assert_eq!(downs[2].1, "L3");
    let ups: Vec<&(String, String)> = transitions[downs.len()..].iter().collect();
    assert_eq!(
        ups.len(),
        3,
        "expected a one-rung-per-interval recovery, got {transitions:?}"
    );
    assert_eq!(ups[0].1, "L2");
    assert_eq!(ups[1].1, "L1");
    assert_eq!(ups[2].1, "L0");

    // During L3 the feed kept publishing — as unperceived verdicts.
    assert!(
        events.contains("\"unperceived\":true"),
        "reflex frames must publish while yielded: {events}"
    );
    // And perception really stopped while off, then resumed:
    // every frame nominates 2 tiles, but embeds < 2 per frame.
    assert!(summary.embeds > 0, "decision tier ran before the yield");
    assert!(
        summary.embeds < 2 * summary.frames,
        "embeds must fall while the ladder is down: {} embeds over {} frames",
        summary.embeds,
        summary.frames
    );
    assert_eq!(summary.final_rung, "L0");
    let health = std::fs::read_to_string(format!("{}/health.txt", cfg.ledger_dir)).unwrap();
    assert!(health.contains("yield_rung = L0"), "{health}");
    assert!(health.contains("silence_basis = decision"), "{health}");
    let control = std::fs::read_to_string(format!("{}/control.json", cfg.ledger_dir)).unwrap();
    assert!(control.contains("\"decision_enabled\":true"), "{control}");
}

#[test]
fn memory_pressure_reaches_l4_and_reports_unowned_models() {
    let dir = tempdir("l4");
    let (cfg, _) = test_config(&dir, 50);
    let starved = LoadSample {
        foreign_gpu_pct: Some(0.0),
        interactive: false,
        mem_available_pct: Some(2.0),
    };
    let summary = service::run_with_probe(
        &cfg,
        Box::new(ScriptProbe {
            script: vec![starved],
            idx: 0,
        }),
    )
    .expect("service run");
    assert_eq!(summary.final_rung, "L4");
    let events = std::fs::read_to_string(format!("{}/events.jsonl", cfg.ledger_dir)).unwrap();
    let transitions = rung_transitions(&events);
    assert_eq!(transitions.len(), 4, "L0->L1->L2->L3->L4: {transitions:?}");
    assert_eq!(transitions[3].1, "L4");
    // The rack was not started by this service, so L4 must NOT
    // stop it — it receipts that the models are not ours to unload.
    assert!(
        events.contains("yield_models_not_owned"),
        "L4 with a foreign-owned rack must receipt the limit: {events}"
    );
    assert!(!summary.rack_stopped_by_me);
    let health = std::fs::read_to_string(format!("{}/health.txt", cfg.ledger_dir)).unwrap();
    assert!(health.contains("yield_rung = L4"), "{health}");
    assert!(
        health.contains("yield_reason = memory_pressure"),
        "{health}"
    );
    assert!(health.contains("decision_tier = reflex_only"), "{health}");
    assert!(health.contains("silence_basis = reflex"), "{health}");
    // Silence at L4 is reflex-tier silence, and health says so —
    // it must not read as a dead lane.
    assert!(health.contains("silence_meaningful = true"), "{health}");
}

#[test]
fn alternating_pressure_never_yields() {
    let dir = tempdir("flap");
    let (cfg, _) = test_config(&dir, 70);
    let script: Vec<LoadSample> = (0..400)
        .map(|i| if i % 2 == 0 { foreign(75.0) } else { clear() })
        .collect();
    let summary = service::run_with_probe(&cfg, Box::new(ScriptProbe { script, idx: 0 }))
        .expect("service run");
    let events = std::fs::read_to_string(format!("{}/events.jsonl", cfg.ledger_dir)).unwrap();
    assert!(
        !events.contains("\"yield_rung\""),
        "boundary-straddling pressure must never yield: {events}"
    );
    assert_eq!(summary.final_rung, "L0");
    // Decision never switched off: every frame embedded both tiles.
    assert_eq!(summary.embeds, 2 * summary.frames);
}

fn rung_rank(r: &str) -> u32 {
    r.trim_start_matches('L').parse().unwrap_or(0)
}
