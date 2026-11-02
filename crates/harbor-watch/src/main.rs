//! harbor-watch CLI.
//!
//! ```text
//! harbor-watch <input.jsonl> --out <verdicts.jsonl> [--threshold 0.25] [--alpha 0.1] [--truth <truth.jsonl>]
//! harbor-watch --compare <all.jsonl> <changed.jsonl> [--threshold 0.25]
//! harbor-watch --make-fixture <path.jsonl> [--dim 1280] [--seed 7]
//! ```
//!
//! Single-file mode prints a JSON summary to stdout and writes one
//! verdict object per (frame, tile) to --out.
//! --compare runs both strategy files and reports time-to-first-
//! change-verdict (stream-time, as defined in ablation::compare) and
//! verdict agreement. --make-fixture writes the synthetic fixture and
//! a `<path>.truth.jsonl` sidecar next to it.

use harbor_watch::ablation;
use harbor_watch::fixture;
use harbor_watch::pipeline::{run_records, Config};
use harbor_watch::record::{parse_jsonl, record_to_json};
use std::collections::BTreeMap;
use std::time::Instant;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.windows(2).find(|w| w[0] == name).map(|w| w[1].clone())
}

fn fmt_opt(v: Option<f64>) -> String {
    match v {
        Some(x) => format!("{x:.6}"),
        None => "null".into(),
    }
}

fn verdict_json(v: &harbor_watch::pipeline::TileVerdict) -> String {
    format!(
        "{{\"frame\":{},\"tile\":{},\"t_arrival_us\":{},\"driver_diff\":{},\"raw_score\":{},\"smoothed_score\":{},\"changed_raw\":{},\"changed\":{},\"focus\":{},\"stale\":{},\"lineage_mask\":{}}}",
        v.frame,
        v.tile,
        v.t_arrival_us,
        fmt_opt(v.driver_diff),
        fmt_opt(v.raw_score),
        fmt_opt(v.smoothed_score),
        v.changed_raw,
        v.changed,
        v.focus,
        v.stale,
        v.lineage_mask
    )
}

fn load(path: &str) -> Vec<harbor_watch::record::InputRecord> {
    let text = std::fs::read_to_string(path).unwrap_or_else(|e| {
        eprintln!("cannot read {path}: {e}");
        std::process::exit(2);
    });
    parse_jsonl(&text).unwrap_or_else(|e| {
        eprintln!("{path}: {e}");
        std::process::exit(2);
    })
}

fn load_truth(path: &str) -> BTreeMap<(u32, u32), bool> {
    let text = std::fs::read_to_string(path).unwrap_or_else(|e| {
        eprintln!("cannot read {path}: {e}");
        std::process::exit(2);
    });
    let mut m = BTreeMap::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let get = |k: &str| -> u32 {
            let pat = format!("\"{k}\":");
            let at = line
                .find(&pat)
                .unwrap_or_else(|| panic!("truth line missing {k}: {line}"));
            let rest = &line[at + pat.len()..];
            let end = rest.find([',', '}']).unwrap_or(rest.len());
            rest[..end].trim().parse().expect("truth number")
        };
        m.insert(
            (get("frame"), get("tile")),
            line.contains("\"changed\":true"),
        );
    }
    m
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cfg = Config {
        threshold: opt(&args, "--threshold")
            .map(|s| s.parse().expect("--threshold number"))
            .unwrap_or(0.25),
        alpha: opt(&args, "--alpha")
            .map(|s| s.parse().expect("--alpha number"))
            .unwrap_or(0.1),
        ..Config::default()
    };

    if let Some(path) = opt(&args, "--make-fixture") {
        let dim: usize = opt(&args, "--dim")
            .map(|s| s.parse().expect("--dim"))
            .unwrap_or(1280);
        let seed: u64 = opt(&args, "--seed")
            .map(|s| s.parse().expect("--seed"))
            .unwrap_or(7);
        let fx = fixture::generate(dim, seed);
        let mut out = String::new();
        for r in &fx.records {
            out.push_str(&record_to_json(r));
            out.push('\n');
        }
        std::fs::write(&path, out).expect("write fixture");
        let truth_path = format!("{path}.truth.jsonl");
        let mut t = String::new();
        for frame in 1..fixture::FRAMES {
            for tile in 0..16u32 {
                t.push_str(&format!(
                    "{{\"frame\":{},\"tile\":{},\"changed\":{}}}\n",
                    frame,
                    tile,
                    fx.truth_changed(frame, tile)
                ));
            }
        }
        std::fs::write(&truth_path, t).expect("write truth");
        println!(
            "{{\"fixture\":\"{path}\",\"truth\":\"{truth_path}\",\"dim\":{dim},\"records\":{}}}",
            fx.records.len()
        );
        return;
    }

    if args.first().map(|s| s == "--compare").unwrap_or(false) {
        let all_recs = load(&args[1]);
        let ch_recs = load(&args[2]);
        let t0 = Instant::now();
        let all_out = run_records(&all_recs, cfg.clone());
        let wall_all = t0.elapsed().as_secs_f64() * 1e3;
        let t0 = Instant::now();
        let ch_out = run_records(&ch_recs, cfg);
        let wall_ch = t0.elapsed().as_secs_f64() * 1e3;
        let mut rep = ablation::compare(&all_out, &ch_out, &all_recs, &ch_recs);
        rep.wall_all_ms = wall_all;
        rep.wall_changed_ms = wall_ch;
        let us = |v: Option<u64>| {
            v.map(|x| x.to_string())
                .unwrap_or_else(|| "\"missed\"".into())
        };
        println!(
            "{{\"reference_frame\":{},\"ttfc_all_us\":{},\"ttfc_changed_us\":{},\"wall_all_ms\":{:.3},\"wall_changed_ms\":{:.3},\"records_all\":{},\"records_changed\":{},\"tile_agreement\":{:.4},\"tile_pairs\":{},\"frame_agreement\":{:.4},\"frame_pairs\":{}}}",
            rep.reference_frame
                .map(|f| f.to_string())
                .unwrap_or_else(|| "null".into()),
            us(rep.ttfc_all_us),
            us(rep.ttfc_changed_us),
            rep.wall_all_ms,
            rep.wall_changed_ms,
            rep.records_all,
            rep.records_changed,
            rep.tile_agreement,
            rep.tile_pairs,
            rep.frame_agreement,
            rep.frame_pairs
        );
        return;
    }

    if args.is_empty() {
        eprintln!("usage: harbor-watch <input.jsonl> --out <verdicts.jsonl> | --compare <all> <changed> | --make-fixture <path>");
        std::process::exit(2);
    }
    let recs = load(&args[0]);
    let t0 = Instant::now();
    let out = run_records(&recs, cfg);
    let wall = t0.elapsed().as_secs_f64() * 1e3;

    if let Some(vpath) = opt(&args, "--out") {
        let mut s = String::new();
        for v in &out.tiles {
            s.push_str(&verdict_json(v));
            s.push('\n');
        }
        std::fs::write(&vpath, s).expect("write verdicts");
    }

    let flagged: usize = out.tiles.iter().filter(|v| v.changed).count();
    let flagged_raw: usize = out.tiles.iter().filter(|v| v.changed_raw).count();
    let e_before: f64 = out.frames.iter().map(|f| f.energy_before).sum();
    let e_after: f64 = out.frames.iter().map(|f| f.energy_after).sum();
    let mut summary = format!(
        "{{\"records\":{},\"frames\":{},\"dim\":{},\"ingest_ring_dim\":{},\"decide_ring_dim\":{},\"tiles_flagged_refined\":{},\"tiles_flagged_raw\":{},\"frames_changed\":{},\"sheaf_energy_before\":{:.4},\"sheaf_energy_after\":{:.4},\"wall_ms\":{:.3}",
        recs.len(),
        out.frames.len(),
        out.dim,
        out.ingest_dim,
        out.decide_dim,
        flagged,
        flagged_raw,
        out.frames.iter().filter(|f| f.changed).count(),
        e_before,
        e_after,
        wall
    );
    if let Some(tpath) = opt(&args, "--truth") {
        let truth = load_truth(&tpath);
        let ab = ablation::evaluate(&out, &|f, t| truth.get(&(f, t)).copied().unwrap_or(false));
        summary.push_str(&format!(
            ",\"ablation\":{{\"raw\":{{\"tp\":{},\"fp\":{},\"fn\":{},\"precision\":{:.4},\"recall\":{:.4}}},\"refined\":{{\"tp\":{},\"fp\":{},\"fn\":{},\"precision\":{:.4},\"recall\":{:.4}}}}}",
            ab.raw.tp, ab.raw.fp, ab.raw.fn_, ab.raw.precision(), ab.raw.recall(),
            ab.refined.tp, ab.refined.fp, ab.refined.fn_, ab.refined.precision(), ab.refined.recall()
        ));
    }
    summary.push('}');
    println!("{summary}");
}
