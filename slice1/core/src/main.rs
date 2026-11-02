//! confluence-watch CLI: `confluence-watch --config <file>`.
//! Prints a one-line JSON summary of the run to stdout.

use confluence_watch::config::load_config;
use confluence_watch::service;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cfg_path = args
        .windows(2)
        .find(|w| w[0] == "--config")
        .map(|w| w[1].clone())
        .unwrap_or_else(|| "confluence-watch.conf".to_string());
    let cfg = load_config(&cfg_path).unwrap_or_else(|e| {
        eprintln!("config: {e}");
        std::process::exit(2);
    });
    match service::run(&cfg) {
        Ok(s) => {
            println!(
                "{{\"frames\":{},\"events\":{},\"embeds\":{},\"embeds_spent_s\":{:.3},\"embed_everything_estimate_s\":{:.3},\"verdict_latency_p50_ms\":{:.3},\"verdict_latency_max_ms\":{:.3},\"rack_started_by_me\":{},\"rack_stopped_by_me\":{}}}",
                s.frames,
                s.events,
                s.embeds,
                s.embeds_spent_s,
                s.embed_everything_estimate_s,
                s.verdict_latency_p50_ms,
                s.verdict_latency_max_ms,
                s.rack_started_by_me,
                s.rack_stopped_by_me
            );
        }
        Err(e) => {
            eprintln!("confluence-watch: {e}");
            std::process::exit(1);
        }
    }
}
