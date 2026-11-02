//! End-to-end tests for the integrated cascade.

use rolling_pipeline::*;
use std::time::Duration;

fn hotspot_cycles(cycles: usize, per_cycle: usize, stagger_us: u64) -> Vec<Cycle> {
    let flat = generate_trace(cycles * per_cycle, Duration::from_micros(stagger_us));
    flat.chunks(per_cycle)
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
        .collect()
}

#[test]
fn end_to_end_lineage_energy_and_gating() {
    let mut pipe = Pipeline::new();
    let jobs = hotspot_cycles(1, 3, 0);
    let mut last = None;
    for entry in &jobs[0] {
        last = Some(pipe.run_tick(&entry.data));
    }
    let pubd = last.unwrap();

    // Lineage of a published payload: all five stages, exactly once.
    for (stage, name) in STAGE_NAMES.iter().enumerate() {
        assert!(pubd.lineage.visited(stage), "{name} missing from lineage");
        assert_eq!(
            pubd.lineage.count(stage),
            1,
            "{name} must appear exactly once"
        );
    }
    assert_eq!(pubd.lineage.mask, 0b11111);

    // Sheaf: the refine step decreased consistency energy.
    assert!(
        pubd.sheaf_energy_after < pubd.sheaf_energy_before,
        "energy must decrease: {} -> {}",
        pubd.sheaf_energy_before,
        pubd.sheaf_energy_after
    );

    // Gating: after the director's first gate, perceive does strictly
    // less counted work than the ungated baseline — by counters.
    assert!(
        pipe.ops.perceive_gated < pipe.ops.perceive_baseline,
        "gated {} !< baseline {}",
        pipe.ops.perceive_gated,
        pipe.ops.perceive_baseline
    );
    // Exact accounting: tick 0 full frame (64) + ticks 1..2 at the
    // director's 4x4 gate (16 each) = 96 of 192 baseline.
    assert_eq!(pipe.ops.perceive_gated, 64 + 16 + 16);
    assert_eq!(pipe.ops.perceive_baseline, 3 * 64);
    assert_eq!(pipe.director.moves + pipe.director.holds, 3);
}

#[test]
fn gate_feedback_lands_on_next_pass() {
    // The gate `direct` sets during tick N is the gate `perceive`
    // reports using on tick N+1 — not the same tick.
    let mut pipe = Pipeline::new();
    let jobs = hotspot_cycles(1, 3, 0);
    let p0 = pipe.run_tick(&jobs[0][0].data);
    assert_eq!(
        p0.gate_used,
        rolling_substrate_core::gating::Viewport::full(8, 8),
        "tick 0 is full-frame"
    );
    let p1 = pipe.run_tick(&jobs[0][1].data);
    assert_eq!(
        p1.gate_used.area(),
        16,
        "tick 1 uses the director's 4x4 gate"
    );
}

#[test]
fn schedulers_same_work_rolling_emits_more_and_first() {
    let cycles = hotspot_cycles(3, 3, 300);

    let mut pb = Pipeline::new();
    let b = run_batched(&mut pb, &cycles);
    let mut pr = Pipeline::new();
    let r = run_rolling(&mut pr, &cycles);

    assert_eq!(b.outputs, 3, "batched emits once per cycle");
    assert_eq!(r.outputs, 9, "rolling emits once per payload");
    assert!(
        (b.checksum - r.checksum).abs() < 1e-6,
        "same work, scheduling is the only variable: {} vs {}",
        b.checksum,
        r.checksum
    );
    assert_eq!(
        b.ops, r.ops,
        "counted ops must be identical under both schedulers"
    );
    assert!(
        r.time_to_first_output < b.time_to_first_output,
        "rolling TTFO {:?} < batched {:?}",
        r.time_to_first_output,
        b.time_to_first_output
    );
    assert!(r.sheaf_energy_after < r.sheaf_energy_before);
}
