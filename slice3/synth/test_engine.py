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


if __name__ == "__main__":
    unittest.main()
