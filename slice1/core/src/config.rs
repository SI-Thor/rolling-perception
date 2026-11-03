//! Service configuration: a plain `key = value` text file, the same
//! shape as the LensFile — a technician can read and edit it with no
//! tooling. Unknown keys are ignored (forward compatibility); bad
//! numbers are hard errors with the key named.

use std::collections::BTreeMap;
use std::fmt;

#[derive(Debug, Clone)]
pub struct Config {
    pub stream_id: String,
    /// Directory holding lens.txt / state.txt / events.jsonl / health.txt.
    pub ledger_dir: String,
    /// Shell command that produces ingest records on stdout (the
    /// Python ingest). Empty = read records from our own stdin
    /// (tests, manual driving).
    pub ingest_cmd: String,
    pub rack_url: String,
    /// If the rack is down at startup, start it (and remember we did).
    pub rack_autostart: bool,
    /// Stop the rack at exit ONLY if this service started it.
    pub stop_rack_on_exit: bool,
    pub threshold: f64,
    pub alpha: f64,
    pub focus_k: usize,
    /// Soak mode: run unattended until the stop file / EOF, appending
    /// precision self-report placeholders to state.txt.
    pub soak: bool,
    /// 0 = unlimited.
    pub max_frames: u32,
    /// Checked once per frame; if it appears, shut down cleanly.
    pub stop_file: String,
    /// Per-stream decision budget in embed-seconds per rolling
    /// hour (SPEC §2.2). Default 300 = the spec's camera class
    /// default. The yield ladder (§2.3) scales this by its rung
    /// factor; the ingest enforces the effective figure via the
    /// control file, admitting nominated tiles in rank order.
    pub budget_embed_s_per_hour: f64,
    /// Run the §2.3 tenancy sampler + yield ladder. When false,
    /// the ladder never moves (the budget is still enforced at
    /// its full, unfactored figure).
    pub tenancy: bool,
    /// Host sampler cadence in ms (spec: 2000).
    pub tenancy_sample_ms: u64,
    /// Foreign load must persist this long before yielding, in
    /// seconds (spec: 5). Interactive-session signals bypass it.
    pub tenancy_sustain_s: f64,
    /// Clear-headroom interval before/between recovery steps, in
    /// seconds (spec: 60 — both numbers are the same interval).
    pub tenancy_recovery_s: f64,
    /// MemAvailable below this percent of total RAM counts as
    /// memory pressure — the L4 trigger. (The spec names the
    /// trigger, not the number; 10 is this build's line.)
    pub mem_pressure_pct: f64,
    /// Comma-separated systemd units whose MainPIDs count as
    /// platform processes for foreign-load attribution.
    pub tenancy_platform_units: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            stream_id: "stream0".into(),
            ledger_dir: "ledger".into(),
            ingest_cmd: String::new(),
            rack_url: "http://127.0.0.1:8077".into(),
            rack_autostart: true,
            stop_rack_on_exit: true,
            threshold: 0.25,
            alpha: 0.1,
            focus_k: 4,
            soak: false,
            max_frames: 0,
            stop_file: String::new(),
            budget_embed_s_per_hour: 300.0,
            tenancy: true,
            tenancy_sample_ms: 2000,
            tenancy_sustain_s: 5.0,
            tenancy_recovery_s: 60.0,
            mem_pressure_pct: 10.0,
            tenancy_platform_units: "jev-rack".into(),
        }
    }
}

#[derive(Debug)]
pub struct ConfigError(pub String);
impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}
impl std::error::Error for ConfigError {}

pub fn parse_config(text: &str) -> Result<Config, ConfigError> {
    let mut kv: BTreeMap<String, String> = BTreeMap::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(eq) = line.find('=') {
            kv.insert(
                line[..eq].trim().to_string(),
                line[eq + 1..].trim().to_string(),
            );
        }
    }
    let mut cfg = Config::default();
    let get = |k: &str| kv.get(k).cloned();
    if let Some(v) = get("stream_id") {
        cfg.stream_id = v;
    }
    if let Some(v) = get("ledger_dir") {
        cfg.ledger_dir = v;
    }
    if let Some(v) = get("ingest_cmd") {
        cfg.ingest_cmd = v;
    }
    if let Some(v) = get("rack_url") {
        cfg.rack_url = v;
    }
    if let Some(v) = get("stop_file") {
        cfg.stop_file = v;
    }
    let num = |k: &str| -> Result<Option<f64>, ConfigError> {
        match get(k) {
            Some(s) => s
                .parse::<f64>()
                .map(Some)
                .map_err(|_| ConfigError(format!("bad number for {k}: {s:?}"))),
            None => Ok(None),
        }
    };
    let boolean = |k: &str| -> Result<Option<bool>, ConfigError> {
        match get(k).as_deref() {
            Some("true") => Ok(Some(true)),
            Some("false") => Ok(Some(false)),
            Some(other) => Err(ConfigError(format!("bad boolean for {k}: {other:?}"))),
            None => Ok(None),
        }
    };
    if let Some(v) = boolean("rack_autostart")? {
        cfg.rack_autostart = v;
    }
    if let Some(v) = boolean("stop_rack_on_exit")? {
        cfg.stop_rack_on_exit = v;
    }
    if let Some(v) = boolean("soak")? {
        cfg.soak = v;
    }
    if let Some(v) = boolean("tenancy")? {
        cfg.tenancy = v;
    }
    if let Some(v) = get("tenancy_platform_units") {
        cfg.tenancy_platform_units = v;
    }
    if let Some(v) = num("threshold")? {
        cfg.threshold = v;
    }
    if let Some(v) = num("alpha")? {
        cfg.alpha = v;
    }
    if let Some(v) = num("focus_k")? {
        cfg.focus_k = v as usize;
    }
    if let Some(v) = num("max_frames")? {
        cfg.max_frames = v as u32;
    }
    if let Some(v) = num("budget_embed_s_per_hour")? {
        cfg.budget_embed_s_per_hour = v;
    }
    if let Some(v) = num("tenancy_sample_ms")? {
        cfg.tenancy_sample_ms = v as u64;
    }
    if let Some(v) = num("tenancy_sustain_s")? {
        cfg.tenancy_sustain_s = v;
    }
    if let Some(v) = num("tenancy_recovery_s")? {
        cfg.tenancy_recovery_s = v;
    }
    if let Some(v) = num("mem_pressure_pct")? {
        cfg.mem_pressure_pct = v;
    }
    Ok(cfg)
}

pub fn load_config(path: &str) -> Result<Config, ConfigError> {
    let text = std::fs::read_to_string(path)
        .map_err(|e| ConfigError(format!("cannot read config {path}: {e}")))?;
    parse_config(&text)
}
