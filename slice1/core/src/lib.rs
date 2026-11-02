//! confluence-watch: the LIVE harbor-watch (Confluence Slice 1 core).
//!
//! Architecture, mirroring the wave-3 split and made live:
//!
//! - **ingest** (Python, `ingest/ingest.py`): owns frame acquisition
//!   (phone MJPEG/JPEG-over-HTTP, or file replay of wave-3/staged
//!   sequences through the identical interface), 4×4 tiling, the µs
//!   frame-diff gate, and I-JEPA embeds of nominated tiles via the
//!   Thor's JEV rack. Emits wave-3-schema records + frame_end
//!   control lines.
//! - **this crate**: spawns the ingest, runs the harbor-watch
//!   cascade incrementally ([`live::LivePipeline`], batch-parity
//!   tested), manages the rack's lifecycle (start if down, stop on
//!   exit iff we started it), and publishes verdicts to the
//!   per-stream text ledger ([`ledger`]).
//! - **the ledger** is canonical: lens.txt (rhythm + appearance),
//!   state.txt (state + budget meter + coverage), events.jsonl
//!   (service receipts + published verdicts with lineage),
//!   health.txt (embed p50/p99, queue, frame age — silence is only
//!   "normal" when health says so).

pub mod config;
pub mod ledger;
pub mod live;
pub mod service;
