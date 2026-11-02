//! P5 — the gating contract's reporting half (PLAN §5.2 / DESIGN
//! §5, ARCHITECTURE P5): cells outside the gate are reported in the
//! snapshot as `stale_by_gate`, each with the tick that last
//! computed it.
//!
//! The identity half (inside-gate results identical, outside
//! untouched) was already proven at the substrate level
//! (`gated_result_identical_on_roi_and_untouched_outside`). This
//! file pins the half that was never built in the pipeline: the
//! marking itself, checked cell by cell against each snapshot's
//! own `gate_used` and the run's history.

use rolling_pipeline::*;
use std::time::Duration;

#[test]
fn snapshots_mark_exactly_the_gate_skipped_tiles_with_correct_ticks() {
    let flat = generate_trace(3, Duration::ZERO);
    let mut pipe = Pipeline::new();
    // The test's own model of the contract: a cell's last-computed
    // tick advances exactly when a snapshot's gate covers it.
    let mut expected_last = vec![0u64; DIM];
    let mut saw_stale = false;
    for (t, entry) in flat.iter().enumerate() {
        let p = pipe.run_tick(&entry.data);
        assert_eq!(p.tick, t as u64);
        assert_eq!(p.last_computed_tick.len(), DIM);
        assert_eq!(p.stale_by_gate.len(), DIM);
        let mut stale_count = 0usize;
        for y in 0..HEIGHT {
            for x in 0..WIDTH {
                let idx = y * WIDTH + x;
                let inside = p.gate_used.contains(x as u32, y as u32);
                if inside {
                    expected_last[idx] = t as u64;
                } else {
                    stale_count += 1;
                }
                assert_eq!(
                    p.stale_by_gate[idx], !inside,
                    "tick {t} cell ({x},{y}): stale mark must be exactly the gate complement"
                );
                assert_eq!(
                    p.last_computed_tick[idx], expected_last[idx],
                    "tick {t} cell ({x},{y}): last-computed tick"
                );
            }
        }
        assert_eq!(
            stale_count as u64,
            DIM as u64 - p.gate_used.area(),
            "tick {t}: stale count == cells outside the gate"
        );
        saw_stale |= stale_count > 0;
    }
    assert!(
        saw_stale,
        "the director narrows the gate after tick 0, so the run must exercise marking"
    );
}

#[test]
fn stale_tiles_keep_the_tick_that_computed_them() {
    // Over a longer run the gate chases the drifting hotspot; cells
    // it left behind keep the tick that last computed them (tick 0
    // for cells no later gate reached) instead of decaying to a
    // default or tracking the current tick.
    let flat = generate_trace(6, Duration::ZERO);
    let mut pipe = Pipeline::new();
    let mut last = None;
    for e in &flat {
        last = Some(pipe.run_tick(&e.data));
    }
    let p = last.unwrap();
    assert!(
        p.stale_by_gate.iter().any(|&s| s),
        "final snapshot must contain stale cells"
    );
    assert!(
        p.last_computed_tick.contains(&0),
        "cells no gate revisited since tick 0 still read tick 0"
    );
    for (idx, &stale) in p.stale_by_gate.iter().enumerate() {
        if !stale {
            assert_eq!(
                p.last_computed_tick[idx], p.tick,
                "a cell computed this tick reads this tick"
            );
        } else {
            assert!(
                p.last_computed_tick[idx] < p.tick,
                "a stale cell's last-computed tick is in the past"
            );
        }
    }
}
