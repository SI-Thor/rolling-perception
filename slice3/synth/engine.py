"""Confluence synthesiser experiment — core model.

Thesis under test (Casey): "the game engine is the synthesizer."
A sensor SAMPLER hands a late reader the last raw sample. A
SYNTHESISER (this engine) maintains state corrected by samples and
renders the present by extrapolation — and, per Panel 2 Q3's
evidence kit, labels every serve with its basis so the reader can
always tell a corrected fact from an extrapolation from a stale one:

  basis: corrected | extrapolated | stale
  extrapolation_age_ms    — time since the last correcting read
  tolerance               — the engine's stated error band at that age
  tolerance_exceedance_rate — fraction of corrections whose residual
                            beat the band stated *before* the read
                            arrived (the error model grading itself)

Freshness rule (Panel 2 Q3, verbatim): age > lens period + 3-sigma
jitter forces `stale`, never "now". The rhythm lens mirrors the
substrate's LensFile (crates/rolling-adaptive): EMA period estimate
+ EMA interval variance, alpha = 0.10.

Correction policy is deliberately naive: the corrected position IS
the raw read (no filtering). The experiment is about extrapolation
vs holding, not about filtering — filtering is a different converter
and would confound the comparison.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------- lens

@dataclass
class Lens:
    """Per-stream rhythm estimate: EMA period + jitter, LensFile-style."""

    nominal_period: float
    est_period: float = 0.0
    jitter_var: float = 0.0
    last_arrival: float | None = None
    samples: int = 0
    alpha: float = 0.10

    def observe(self, t: float) -> float | None:
        """Record a read arrival; return the interval, or None for the first."""
        if self.last_arrival is None:
            self.last_arrival = t
            self.est_period = self.nominal_period
            self.samples += 1
            return None
        dt = t - self.last_arrival
        self.last_arrival = t
        if self.samples == 1:
            self.est_period = dt
            self.jitter_var = 0.0
        else:
            dev = dt - self.est_period
            self.est_period += self.alpha * dev
            self.jitter_var += self.alpha * (dev * dev - self.jitter_var)
        self.samples += 1
        return dt

    @property
    def jitter_std(self) -> float:
        return math.sqrt(max(self.jitter_var, 0.0))

    @property
    def stale_threshold(self) -> float:
        """Panel 2 Q3: age > period + 3-sigma jitter is stale, never 'now'."""
        return self.est_period + 3.0 * self.jitter_std


# ---------------------------------------------------------------- engine

@dataclass
class Serve:
    x: float
    y: float
    basis: str               # corrected | extrapolated | stale
    age: float               # seconds since last correction
    tolerance: float         # stated error band (radial, world units)
    stale_threshold: float


@dataclass
class EngineObject:
    """One tracked object: corrected state + learned velocity + error model."""

    name: str
    # corrected state
    t_corr: float | None = None
    px: float = 0.0
    py: float = 0.0
    # learned velocity (EMA of per-read delta velocities)
    vx: float = 0.0
    vy: float = 0.0
    alpha_v: float = 0.35
    # error model: EMA of squared one-step extrapolation residuals
    resid_ms: float = 0.0
    alpha_r: float = 0.15
    n_resid: int = 0
    # exceedance bookkeeping (band stated before the read vs its residual)
    exceed_hist: list[int] = field(default_factory=list)  # 1 = exceeded
    _prev_z: tuple[float, float] | None = None
    _prev_t: float | None = None

    # Stated-band model: band(a) = sigma_r * max(1, a / period).
    # sigma_r is the RMS radial residual of one-period extrapolation.
    # Under an isotropic-Gaussian error model whose scale grows linearly
    # with horizon, P(radial error > band) = exp(-1) ~= 0.368 at every
    # age — that is the calibration target the measurement grades.
    STATED_EXCEEDANCE = math.exp(-1.0)

    def sigma_r(self) -> float:
        return math.sqrt(self.resid_ms) if self.n_resid > 0 else 0.0

    def band(self, age: float, period: float) -> float:
        s = self.sigma_r()
        if s == 0.0:
            return 0.0
        return s * max(1.0, age / period) if period > 0 else s

    def predict(self, t: float) -> tuple[float, float]:
        assert self.t_corr is not None
        a = t - self.t_corr
        return (self.px + self.vx * a, self.py + self.vy * a)

    def correct(self, t: float, zx: float, zy: float, lens: Lens) -> None:
        """Apply one sensor read. Residual is graded against the band
        stated *before* this read — the engine may not grade itself
        with knowledge of the answer."""
        if self.t_corr is not None and self._prev_t is not None:
            age = t - self.t_corr
            px_, py_ = self.predict(t)
            r = math.hypot(zx - px_, zy - py_)
            stated = self.band(age, lens.est_period)
            if stated > 0.0:
                self.exceed_hist.append(1 if r > stated else 0)
            # error-model update (first residual seeds the EMA)
            if self.n_resid == 0:
                self.resid_ms = r * r
            else:
                self.resid_ms += self.alpha_r * (r * r - self.resid_ms)
            self.n_resid += 1
            # velocity update from raw read deltas
            dt = t - self._prev_t
            if dt > 0:
                mvx = (zx - self._prev_z[0]) / dt
                mvy = (zy - self._prev_z[1]) / dt
                self.vx += self.alpha_v * (mvx - self.vx)
                self.vy += self.alpha_v * (mvy - self.vy)
        self.px, self.py = zx, zy
        self.t_corr = t
        self._prev_z = (zx, zy)
        self._prev_t = t

    def serve(self, t: float, lens: Lens) -> Serve:
        assert self.t_corr is not None, "serve before first correction"
        age = t - self.t_corr
        x, y = self.predict(t)
        if age <= 1e-9:
            basis = "corrected"
        elif age <= lens.stale_threshold:
            basis = "extrapolated"
        else:
            basis = "stale"
        return Serve(x=x, y=y, basis=basis, age=age,
                     tolerance=self.band(age, lens.est_period),
                     stale_threshold=lens.stale_threshold)

    def exceedance_rate(self, trailing: int = 100) -> float | None:
        h = self.exceed_hist[-trailing:]
        if not h:
            return None
        return sum(h) / len(h)

    def snapshot(self) -> "EngineObject":
        import copy
        s = copy.copy(self)
        s.exceed_hist = list(self.exceed_hist)
        return s


# ---------------------------------------------------------------- world

class World:
    """Scripted ground-truth trajectories. Analytic, piecewise."""

    T_END = 90.0
    ACCEL_T = 30.0     # speeder starts accelerating
    ACCEL_END = 60.0   # speeder stops accelerating
    ACCEL = 0.35       # units / s^2
    REV_T = 45.0       # reverser flips velocity

    def truth(self, name: str, t: float) -> tuple[float, float]:
        if name == "cruiser":            # constant velocity (control)
            return (10.0 + 2.0 * t, 20.0 + 0.5 * t)
        if name == "glider":             # constant velocity (control)
            return (80.0 - 1.5 * t, 70.0 + 1.0 * t)
        if name == "speeder":            # velocity step-up via sustained accel
            x0, v0 = 10.0, 1.0
            if t < self.ACCEL_T:
                return (x0 + v0 * t, 80.0)
            if t < self.ACCEL_END:
                d = t - self.ACCEL_T
                return (x0 + v0 * self.ACCEL_T + v0 * d + 0.5 * self.ACCEL * d * d, 80.0)
            d = self.ACCEL_END - self.ACCEL_T
            x_mid = x0 + v0 * self.ACCEL_T + v0 * d + 0.5 * self.ACCEL * d * d
            v_end = v0 + self.ACCEL * d
            return (x_mid + v_end * (t - self.ACCEL_END), 80.0)
        if name == "reverser":           # instant direction reversal
            y0, v = 10.0, 3.0
            if t < self.REV_T:
                return (50.0, y0 + v * t)
            return (50.0, y0 + v * self.REV_T - v * (t - self.REV_T))
        raise KeyError(name)

    NAMES = ("cruiser", "glider", "speeder", "reverser")
    CONTROLS = ("cruiser", "glider")


# ---------------------------------------------------------------- sensor

@dataclass
class Read:
    t: float
    z: dict[str, tuple[float, float]]   # noisy observed positions
    dropped: bool = False


class Sensor:
    """The sampler side: jittered cadence, dropped reads, noisy positions."""

    def __init__(self, rng, period=0.5, jitter=0.08, drop_p=0.08, noise=0.05):
        self.rng = rng
        self.period = period
        self.jitter = jitter
        self.drop_p = drop_p
        self.noise = noise

    def stream(self, world: World, t_end: float) -> list[Read]:
        reads: list[Read] = []
        t = 0.0
        while t <= t_end:
            dropped = self.rng.random() < self.drop_p
            z = {}
            for name in world.NAMES:
                x, y = world.truth(name, t)
                z[name] = (x + self.rng.gauss(0.0, self.noise),
                           y + self.rng.gauss(0.0, self.noise))
            reads.append(Read(t=t, z=z, dropped=dropped))
            dt = self.period + self.rng.gauss(0.0, self.jitter)
            t += max(0.1, dt)
        return reads
