//! D12 stress proof: the migrated cascade under volume.
//!
//! Round 2's bench (`docs/RING-BENCH.md`) showed the shipped
//! Disruptor ring, consumed as a queue, tearing 5–27% of a million
//! reads *silently* — no consumer release, no drop policy, no
//! counters, so nothing even noticed. The migrated cascade must
//! pass the test that ring could not:
//!
//! * **Phase A — exactness.** Two independent pipelines run the
//!   same deterministic 250,000-payload stream in lockstep. Every
//!   published checksum and every payload element must agree
//!   *bitwise*, in order. Any message lost, duplicated, reordered,
//!   or torn on any of the five migrated edges shifts or corrupts
//!   the stream and breaks this equality — the cascade's transforms
//!   are deterministic, so bitwise agreement is the exact claim.
//! * **Phase B — volume.** Pipeline A continues alone to
//!   1,000,000 messages total. Every migrated ring (capacity 8)
//!   wraps 125,000 times. A loss in this phase cannot pass
//!   silently either: the sequential cascade receives before it
//!   sends, so an empty lane panics loudly in `recv_edge`.
//! * **Accounting.** Afterwards, every migrated edge's INV-R4
//!   counters (`Pipeline::edge_stats`) must read
//!   `produced == consumed == 1,000,000`, zero drops of either
//!   kind, zero in flight, conservation holding. The Disruptor
//!   could not have produced this evidence about itself at all.
//!
//! Cost: the full cascade runs per message (no fast-path
//! re-implementation — this is `Pipeline::run_tick`, the shipped
//! code path). Measured on the dev VM: ~2.1 µs/tick release,
//! ~14.6 µs/tick debug, so this test is ~2.5 s in release and
//! ~17 s in a debug test run.

use rolling_pipeline::*;
use std::time::Instant;

/// Total messages driven through pipeline A (phase A + B).
const MESSAGES: u64 = 1_000_000;
/// Messages driven through both pipelines in lockstep (phase A).
const TWIN_MESSAGES: u64 = 250_000;
/// Ring capacity of every migrated edge (lib.rs `RING_CAP`).
const RING_CAP: u64 = 8;

/// The deterministic stress stream: a hotspot wandering the grid,
/// every payload distinct (distinct LCG seed per index), so a
/// shifted, duplicated, or torn message cannot masquerade as its
/// neighbour.
fn stress_payload(i: u64) -> Vec<f32> {
    hotspot_payload(
        1.0 + (i % 101) as f32 * 0.05,
        1.0 + (i % 97) as f32 * 0.055,
        0x5EED + i,
    )
}

fn assert_edge_accounting(pipe: &Pipeline, expected: u64, who: &str) {
    for (edge, stats) in pipe.edge_stats() {
        assert_eq!(stats.produced, expected, "{who}/{edge}: produced");
        assert_eq!(stats.consumed, expected, "{who}/{edge}: consumed");
        assert_eq!(stats.dropped_newest, 0, "{who}/{edge}: dropped_newest");
        assert_eq!(stats.dropped_oldest, 0, "{who}/{edge}: dropped_oldest");
        assert_eq!(stats.in_flight(), 0, "{who}/{edge}: in flight at drain");
        assert!(
            stats.conservation_holds(),
            "{who}/{edge}: INV-R4 conservation"
        );
        assert!(
            expected / RING_CAP >= 3,
            "{who}/{edge}: test must wrap every ring at least 3 times"
        );
    }
}

#[test]
fn migrated_cascade_million_messages_exact_and_accounted() {
    let started = Instant::now();
    let mut a = Pipeline::new();
    let mut b = Pipeline::new();

    // Phase A — twin lockstep, bitwise.
    for i in 0..TWIN_MESSAGES {
        let payload = stress_payload(i);
        let pa = a.run_tick(&payload);
        let pb = b.run_tick(&payload);
        assert_eq!(pa.tick, i, "pipeline A tick order");
        assert_eq!(pb.tick, i, "pipeline B tick order");
        assert_eq!(pa.lineage.mask, 0b11111, "tick {i}: lineage complete");
        assert_eq!(
            pa.checksum.to_bits(),
            pb.checksum.to_bits(),
            "tick {i}: checksums diverged — a message was lost, duplicated, or torn"
        );
        assert_eq!(pa.data.len(), pb.data.len());
        for (j, (x, y)) in pa.data.iter().zip(pb.data.iter()).enumerate() {
            assert_eq!(
                x.to_bits(),
                y.to_bits(),
                "tick {i} element {j}: payload bits diverged"
            );
        }
    }
    assert_edge_accounting(&b, TWIN_MESSAGES, "B");
    eprintln!(
        "ring stress phase A: {TWIN_MESSAGES} twin ticks exact in {:?}",
        started.elapsed()
    );

    // Phase B — A alone to the full million.
    for i in TWIN_MESSAGES..MESSAGES {
        let payload = stress_payload(i);
        let pa = a.run_tick(&payload);
        assert_eq!(pa.tick, i, "pipeline A tick order");
        assert_eq!(pa.lineage.mask, 0b11111, "tick {i}: lineage complete");
    }
    assert_edge_accounting(&a, MESSAGES, "A");
    eprintln!(
        "ring stress: {MESSAGES} messages, every migrated ring wrapped {} times, {:?} total",
        MESSAGES / RING_CAP,
        started.elapsed()
    );
}
