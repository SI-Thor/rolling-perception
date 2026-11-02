//! P13 — deterministic replay (PLAN §5.0/§5.5, ARCHITECTURE P13):
//! same trace ⇒ bit-identical snapshot sequence, both schedulers.
//!
//! Before this file, the claim's proof stopped at "the text format
//! round-trips" (with unstated rounding) plus one tick of replay.
//! The probe behind it found the round-trip was NOT lossless — the
//! writer's `{:.6}` changed all 384 floats of a 6-entry trace in
//! their low bits — so the writer now emits Display (shortest
//! round-trip) floats, and this file asserts the whole sequence:
//! every field of every `Published`, bit for bit, not a checksum
//! of a subset.

use rolling_pipeline::*;
use std::time::Duration;

fn assert_snapshot_identical(a: &Published, b: &Published, ctx: &str) {
    assert_eq!(a.tick, b.tick, "{ctx}: tick");
    assert_eq!(
        a.checksum.to_bits(),
        b.checksum.to_bits(),
        "{ctx}: checksum"
    );
    assert_eq!(
        a.sheaf_energy_before.to_bits(),
        b.sheaf_energy_before.to_bits(),
        "{ctx}: energy before"
    );
    assert_eq!(
        a.sheaf_energy_after.to_bits(),
        b.sheaf_energy_after.to_bits(),
        "{ctx}: energy after"
    );
    assert_eq!(a.gate_used, b.gate_used, "{ctx}: gate used");
    assert_eq!(a.lineage, b.lineage, "{ctx}: lineage");
    assert_eq!(a.data.len(), b.data.len(), "{ctx}: data length");
    for (i, (x, y)) in a.data.iter().zip(b.data.iter()).enumerate() {
        assert_eq!(x.to_bits(), y.to_bits(), "{ctx}: data[{i}]");
    }
    assert_eq!(
        a.last_computed_tick, b.last_computed_tick,
        "{ctx}: last-computed ticks"
    );
    assert_eq!(a.stale_by_gate, b.stale_by_gate, "{ctx}: stale marks");
}

#[test]
fn text_replay_reproduces_the_whole_snapshot_sequence_bit_identically() {
    let entries = generate_trace(24, Duration::from_micros(400));

    // The original run, over the in-memory entries.
    let mut orig_pipe = Pipeline::new();
    let original: Vec<Published> = entries
        .iter()
        .map(|e| orig_pipe.run_tick(&e.data))
        .collect();

    // The replay: serialise, parse back, run again from scratch.
    let text = trace_to_string(&entries);
    let parsed = parse_trace(&text).unwrap();
    assert_eq!(parsed.len(), entries.len());
    for (i, (a, b)) in entries.iter().zip(parsed.iter()).enumerate() {
        assert_eq!(a.arrival, b.arrival, "entry {i}: arrival");
        for (j, (x, y)) in a.data.iter().zip(b.data.iter()).enumerate() {
            assert_eq!(
                x.to_bits(),
                y.to_bits(),
                "entry {i} float {j}: the text round-trip must be lossless"
            );
        }
    }
    let mut replay_pipe = Pipeline::new();
    let replayed: Vec<Published> = parsed
        .iter()
        .map(|e| replay_pipe.run_tick(&e.data))
        .collect();

    assert_eq!(original.len(), replayed.len());
    for (i, (a, b)) in original.iter().zip(replayed.iter()).enumerate() {
        assert_snapshot_identical(a, b, &format!("snapshot {i}"));
    }
}

#[test]
fn both_schedulers_drive_the_identical_snapshot_sequence() {
    let flat = generate_trace(24, Duration::ZERO);
    let cycles: Vec<Cycle> = flat
        .chunks(4)
        .map(|chunk| {
            let t0 = chunk[0].arrival;
            chunk
                .iter()
                .map(|e| TraceEntry {
                    arrival: e.arrival - t0,
                    data: e.data.clone(),
                })
                .collect()
        })
        .collect();

    // The snapshot sequence itself, driven manually in the entry
    // order both schedulers use.
    let mut seq_pipe = Pipeline::new();
    let sequence: Vec<Published> = flat.iter().map(|e| seq_pipe.run_tick(&e.data)).collect();
    let seq_checksum: f64 = sequence.iter().map(|p| p.checksum).sum();
    let seq_e_before: f64 = sequence.iter().map(|p| p.sheaf_energy_before).sum();
    let seq_e_after: f64 = sequence.iter().map(|p| p.sheaf_energy_after).sum();

    let mut pb = Pipeline::new();
    let b = run_batched(&mut pb, &cycles);
    let mut pr = Pipeline::new();
    let r = run_rolling(&mut pr, &cycles);

    // Scheduling changes when outputs are emitted, never what the
    // cascade computed: every aggregate over the sequence, the
    // first snapshot's lineage, and the counted ops must match the
    // manual sequence bit for bit under BOTH schedulers.
    for (name, rep) in [("batched", &b), ("rolling", &r)] {
        assert_eq!(
            rep.checksum.to_bits(),
            seq_checksum.to_bits(),
            "{name}: checksum over the snapshot sequence"
        );
        assert_eq!(
            rep.sheaf_energy_before.to_bits(),
            seq_e_before.to_bits(),
            "{name}: summed energy before"
        );
        assert_eq!(
            rep.sheaf_energy_after.to_bits(),
            seq_e_after.to_bits(),
            "{name}: summed energy after"
        );
        assert_eq!(
            rep.sample_lineage,
            Some(sequence[0].lineage),
            "{name}: first snapshot's lineage"
        );
        assert_eq!(rep.ops, seq_pipe.ops, "{name}: counted ops");
        assert_eq!(
            rep.director_moves, seq_pipe.director.moves,
            "{name}: director moves"
        );
        assert_eq!(
            rep.director_holds, seq_pipe.director.holds,
            "{name}: director holds"
        );
    }
    // The one sanctioned difference: emission count.
    assert_eq!(b.outputs, 6, "batched emits once per cycle");
    assert_eq!(r.outputs, 24, "rolling emits once per payload");
}
