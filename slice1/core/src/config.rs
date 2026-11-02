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
    Ok(cfg)
}

pub fn load_config(path: &str) -> Result<Config, ConfigError> {
    let text = std::fs::read_to_string(path)
        .map_err(|e| ConfigError(format!("cannot read config {path}: {e}")))?;
    parse_config(&text)
}
