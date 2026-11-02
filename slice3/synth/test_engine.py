"""Basis-labelling and evidence-kit tests for the synthesiser engine.

The rules under test are Panel 2 Q3's, verbatim:
  - age == 0 (a correction just landed)          -> corrected
  - 0 < age <= lens period + 3-sigma jitter      -> extrapolated
  - age >  lens period + 3-sigma jitter          -> stale (never "now")
  - the threshold comes from the stream's OWN measured rhythm
  - the stated tolerance band widens with age
  - exceedance is graded against the band stated BEFORE the read

Run: python3 -m unittest test_engine -v
"""

import unittest

from engine import EngineObject, Lens


def fed_lens(intervals, nominal=0.5):
    lens = Lens(nominal_period=nominal)
    t = 0.0
    lens.observe(t)
    for dt in intervals:
        t += dt
        lens.observe(t)
    return lens


def corrected_engine(lens):
    """An engine with two corrections and a learned velocity."""
    e = EngineObject("t")
    e.correct(0.0, 0.0, 0.0, lens)
    e.correct(0.5, 0.25, 0.0, lens)
    return e


class TestBasisRules(unittest.TestCase):
    def setUp(self):
        # clean stream: exact 0.5 s cadence, zero jitter
        self.lens = fed_lens([0.5] * 30)

    def test_fresh_correction_is_corrected(self):
        e = corrected_engine(self.lens)
        sv = e.serve(0.5, self.lens)
        self.assertEqual(sv.basis, "corrected")
        self.assertEqual(sv.age, 0.0)

    def test_within_threshold_is_extrapolated(self):
        e = corrected_engine(self.lens)
        sv = e.serve(0.5 + 0.25, self.lens)
        self.assertEqual(sv.basis, "extrapolated")

    def test_beyond_threshold_is_stale_never_now(self):
        e = corrected_engine(self.lens)
        for age in (0.51, 1.0, 10.0, 3600.0):
            sv = e.serve(0.5 + age, self.lens)
            self.assertEqual(sv.basis, "stale", f"age {age}")

    def test_threshold_boundary_is_inclusive(self):
        # age == period + 3-sigma is still extrapolated; the rule
        # fires strictly ABOVE the threshold.
        e = corrected_engine(self.lens)
        th = self.lens.stale_threshold
        self.assertEqual(e.serve(0.5 + th, self.lens).basis, "extrapolated")
        self.assertEqual(e.serve(0.5 + th + 1e-6, self.lens).basis, "stale")

    def test_clean_stream_threshold_is_one_period(self):
        self.assertAlmostEqual(self.lens.jitter_std, 0.0, places=9)
        self.assertAlmostEqual(self.lens.stale_threshold, 0.5, places=9)

    def test_threshold_learned_from_own_rhythm(self):
        # a jittery stream must earn a wider freshness window than a
        # clean one at the same nominal period — the lens judges its
        # own freshness, not a datasheet's.
        jittery = fed_lens([0.35, 0.65, 0.4, 0.6, 0.3, 0.7] * 6)
        self.assertGreater(jittery.jitter_std, 0.05)
        self.assertGreater(jittery.stale_threshold,
                           self.lens.stale_threshold)

    def test_serve_before_any_correction_refuses(self):
        e = EngineObject("t")
        with self.assertRaises(AssertionError):
            e.serve(0.0, self.lens)


class TestToleranceAndExceedance(unittest.TestCase):
    def setUp(self):
        self.lens = fed_lens([0.5] * 30)

    def test_band_widens_with_age(self):
        e = corrected_engine(self.lens)
        e.correct(1.0, 0.5, 0.0, self.lens)  # seed a residual
        b1 = e.band(0.5, self.lens.est_period)
        b2 = e.band(2.0, self.lens.est_period)
        b3 = e.band(10.0, self.lens.est_period)
        self.assertGreater(b1, 0.0)
        self.assertGreater(b2, b1)
        self.assertGreater(b3, b2)

    def test_exceedance_graded_against_prior_band(self):
        e = EngineObject("t")
        e.correct(0.0, 0.0, 0.0, self.lens)
        e.correct(0.5, 0.25, 0.0, self.lens)   # seeds sigma_r, no grade
        e.correct(1.0, 0.5, 0.0, self.lens)    # gentle: inside the band
        e.correct(1.5, 2.5, 0.0, self.lens)    # teleport: beats the band
        self.assertEqual(e.exceed_hist, [0, 1])
        self.assertAlmostEqual(e.exceedance_rate(), 0.5)

    def test_serve_carries_the_evidence_kit(self):
        e = corrected_engine(self.lens)
        sv = e.serve(0.75, self.lens)
        self.assertAlmostEqual(sv.age, 0.25)
        self.assertGreater(sv.tolerance, 0.0)
        self.assertAlmostEqual(sv.stale_threshold,
                               self.lens.stale_threshold)


def warmed_engine(lens, snap_k=None, n=40, decontam=None):
    """An engine warmed on wobbly constant-velocity motion (vx ~ +3)
    until sigma_r has settled to the wobble level (~0.04). Returns
    (engine, t_last, x_last)."""
    e = EngineObject("t")
    e.snap_k = snap_k
    e.decontam = decontam
    t = x = 0.0
    for i in range(n):
        t = i * 0.5
        x = 3.0 * t + (0.02 if i % 2 else -0.02)
        e.correct(t, x, 0.0, lens)
    return e, t, x


class TestSnapRule(unittest.TestCase):
    def setUp(self):
        self.lens = fed_lens([0.5] * 30)   # threshold exactly 0.5

    def test_snap_fires_on_true_reversal(self):
        e, t_last, x_last = warmed_engine(self.lens, snap_k=3.0)
        self.assertEqual(e.n_snaps, 0)        # no warm-up false snaps
        # velocity flips +3 -> -3 at t_last; next read is reversed
        e.correct(t_last + 0.5, x_last - 1.5, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 1)
        self.assertAlmostEqual(e.vx, -3.0, delta=0.2)
        # and the following read is unremarkable: no second snap
        e.correct(t_last + 1.0, x_last - 3.0, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 1)

    def test_without_snap_the_same_reversal_only_blends(self):
        e, t_last, x_last = warmed_engine(self.lens, snap_k=None)
        e.correct(t_last + 0.5, x_last - 1.5, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 0)
        # EMA(0.35) from +3 toward -3 lands near +0.9: still the
        # wrong sign — the failure the snap rule exists to fix.
        self.assertGreater(e.vx, 0.3)

    def test_guard_suppresses_gap_artefact_then_snaps_on_rhythm(self):
        e, t_last, x_last = warmed_engine(self.lens, snap_k=3.0)
        v_pre = e.vx
        # the object reverses at t_last + 1.3, but no read arrives
        # for 1.5 s (a dropped-read gap): the gap-exit residual
        # beats 3x band, yet the correction is age 1.5 > threshold
        # 0.5, so the guard must refuse to judge it a contradiction.
        z_gap = x_last + 3.0 * 1.3 - 3.0 * 0.2
        e.correct(t_last + 1.5, z_gap, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 0)
        self.assertEqual(e.n_snap_suppressed, 1)
        # velocity is the plain EMA blend toward the gap-average
        # delta — NOT a reset to it.
        mvx = (z_gap - x_last) / 1.5
        self.assertAlmostEqual(
            e.vx, v_pre + e.alpha_v * (mvx - v_pre), places=6)
        # the contradiction persists, so the next on-rhythm read
        # (object still moving at -3) snaps.
        e.correct(t_last + 2.0, z_gap - 1.5, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 1)
        self.assertAlmostEqual(e.vx, -3.0, delta=0.2)


class TestDecontamination(unittest.TestCase):
    """SNAP2: a snap-grade residual is a regime change, not a sample
    of the error distribution — it must not inflate the band its
    successors are judged by (the v1 snap flaw: one fire at 3x,
    then the contaminated band grades the follow-on at ~2x and the
    snap never re-fires)."""

    def setUp(self):
        self.lens = fed_lens([0.5] * 30)   # threshold exactly 0.5

    def test_variantA_excludes_firing_and_followon_residuals(self):
        e, t_last, x_last = warmed_engine(self.lens, snap_k=3.0,
                                          decontam="A")
        pre = e.resid_ms
        self.assertGreater(pre, 0.0)
        # reversal fires the snap; its residual is excluded, so
        # sigma_r is bit-identical to its pre-event value.
        e.correct(t_last + 0.5, x_last - 1.5, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 1)
        self.assertEqual(e.resid_ms, pre)
        # the object flips BACK at the next read — a follow-on
        # contradiction graded against the decontaminated band.
        # In the v1 engine this read graded ~2x and never re-fired.
        e.correct(t_last + 1.0, x_last, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 2)
        self.assertEqual(e.resid_ms, pre)
        self.assertEqual(e.n_decontam_excluded, 2)

    def test_variantA_below_grade_read_still_updates_and_closes(self):
        e, t_last, x_last = warmed_engine(self.lens, snap_k=3.0,
                                          decontam="A")
        pre = e.resid_ms
        e.correct(t_last + 0.5, x_last - 1.5, 0.0, self.lens)
        self.assertTrue(e._transient_open)
        # an ordinary on-trajectory read (residual ~0) is NOT
        # snap-grade: under exclusion it still enters the EMA
        # (that is what distinguishes A from the freeze) and it
        # closes the grade-driven transient.
        e.correct(t_last + 1.0, x_last - 3.0, 0.0, self.lens)
        self.assertFalse(e._transient_open)
        self.assertLess(e.resid_ms, pre)
        self.assertEqual(e.n_decontam_excluded, 1)

    def test_variantB_freeze_holds_sigma_then_ema_resumes(self):
        e, t_last, x_last = warmed_engine(self.lens, snap_k=3.0,
                                          decontam="B")
        pre = e.resid_ms
        e.correct(t_last + 0.5, x_last - 1.5, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 1)
        self.assertEqual(e.resid_ms, pre)
        # TRANSIENT_READS ordinary reads (residual ~0, which would
        # drag the EMA down): the freeze holds sigma_r exactly.
        for i in range(1, EngineObject.TRANSIENT_READS + 1):
            e.correct(t_last + 0.5 + 0.5 * i,
                      x_last - 1.5 - 1.5 * i, 0.0, self.lens)
            self.assertEqual(e.resid_ms, pre,
                             f"transient read {i} moved sigma_r")
        self.assertEqual(e.n_decontam_excluded,
                         1 + EngineObject.TRANSIENT_READS)
        # the transient is over: the next read's residual enters
        # the EMA again — it resumes from the frozen value.
        i = EngineObject.TRANSIENT_READS + 1
        e.correct(t_last + 0.5 + 0.5 * i,
                  x_last - 1.5 - 1.5 * i, 0.0, self.lens)
        self.assertLess(e.resid_ms, pre)

    def test_decontam_inert_without_snap_armed(self):
        # comparability guard: with snap_k=None no snap can fire,
        # no transient opens, and the EMA eats even a reversal
        # residual exactly as the v1 engine does.
        e, t_last, x_last = warmed_engine(self.lens, snap_k=None,
                                          decontam="B")
        pre = e.resid_ms
        e.correct(t_last + 0.5, x_last - 1.5, 0.0, self.lens)
        self.assertEqual(e.n_snaps, 0)
        self.assertEqual(e.n_decontam_excluded, 0)
        self.assertGreater(e.resid_ms, pre)


if __name__ == "__main__":
    unittest.main()
