"""Fund cash-flow models: Takahashi and Alexander's deterministic model, a stochastic extension, and calibration.

**Takahashi and Alexander (2002)**, the "Yale model", projects a fund's calls, distributions and
net asset value from a handful of parameters. In year ``t`` of a fund with commitment ``K``:

* calls are a rate of what is still uncalled: ``C_t = RC_t (K - PIC_{t-1})``;
* distributions are a rate of the grown NAV: ``D_t = RD_t NAV_{t-1} (1 + G)``, with
  ``RD_t = max(Y, (t / L)^B)``: a "bow" ``B`` that delays distributions and a life ``L`` at which
  everything left is paid out;
* ``NAV_t = NAV_{t-1} (1 + G) + C_t - D_t``.

**The stochastic model** keeps that skeleton on a quarterly grid and makes it random:

* the fund's true value grows with the market and its own risk,
  ``V_k = V_{k-1} exp((mu - s^2/2) dt + beta s_m sqrt(dt) Z_m + s_i sqrt(dt) Z_i)`` plus calls minus
  distributions, where ``s^2 = beta^2 s_m^2 + s_i^2``, so its expected return is ``mu`` whatever the
  mix;
* call and distribution rates are the Takahashi-Alexander rates, converted to quarters, times
  mean-one lognormal noise;
* the **reported** NAV is an appraisal that lags the true value:
  ``R_k = a V_k + (1 - a)(R_{k-1} + C_k - D_k)``, the smoothing Day 6 studies and the staleness
  secondary buyers price.

**Calibration** fits the deterministic model to any set of fund cash flows by least squares on
their cumulative calls, cumulative distributions and NAV, year by year.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy import optimize

from .cashflows import irr

Array = NDArray[np.float64]


# ------------------------------------------------------------------ Takahashi-Alexander


@dataclass(frozen=True)
class TAParams:
    """Parameters of the Takahashi-Alexander model (annual)."""

    rc: tuple[float, ...] = (0.25, 0.333, 0.5, 0.5, 1.0)  # call rates of the uncalled commitment, year 1, 2, ...
    growth: float = 0.13  # G, a year
    bow: float = 2.5  # B
    life: int = 12  # L, years
    yield_: float = 0.0  # Y, a floor on the distribution rate
    commitment: float = 100.0

    def rate_of_call(self, year: int) -> float:
        return self.rc[year - 1] if year <= len(self.rc) else self.rc[-1]

    def rate_of_distribution(self, year: int) -> float:
        return float(max(self.yield_, min(1.0, (year / self.life) ** self.bow)))


@dataclass(frozen=True)
class Projection:
    """Year-by-year calls, distributions and NAV (index 1..L), from the fund's side as a holder sees it."""

    calls: Array
    distributions: Array
    nav: Array

    @property
    def years(self) -> Array:
        return np.arange(1, self.calls.size + 1, dtype=np.float64)

    @property
    def net(self) -> Array:
        return self.distributions - self.calls

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "calls": self.calls,
                "distributions": self.distributions,
                "nav": self.nav,
                "cum_calls": np.cumsum(self.calls),
                "cum_distributions": np.cumsum(self.distributions),
                "net": self.net,
                "cum_net": np.cumsum(self.net),
            },
            index=pd.Index(self.years.astype(int), name="year"),
        )

    def irr(self) -> float:
        """IRR with each year's flows placed mid-year."""
        return irr(self.years - 0.5, self.net)

    def tvpi(self) -> float:
        return float(self.distributions.sum() / self.calls.sum())


def takahashi_alexander(p: TAParams | None = None) -> Projection:
    """The deterministic model, year by year to the end of the fund's life."""
    p = p or TAParams()
    calls = np.zeros(p.life)
    dist = np.zeros(p.life)
    nav = np.zeros(p.life)
    paid, prev = 0.0, 0.0
    for t in range(1, p.life + 1):
        c = p.rate_of_call(t) * (p.commitment - paid)
        grown = prev * (1.0 + p.growth)
        d = p.rate_of_distribution(t) * grown
        paid += c
        prev = grown + c - d
        calls[t - 1], dist[t - 1], nav[t - 1] = c, d, prev
    return Projection(calls, dist, nav)


# ------------------------------------------------------------------ calibration


@dataclass(frozen=True)
class Fit:
    params: TAParams
    rmse: float  # root-mean-square gap per unit of commitment, over the fitted curves
    success: bool


def calibrate(
    cum_calls: ArrayLike, cum_dist: ArrayLike, nav: ArrayLike, life: int = 12, rc_years: int = 3, commitment: float = 100.0
) -> Fit:
    """Fit call rates (one per year for ``rc_years``, then one tail rate), growth and bow to observed annual curves.

    The observed arrays are year-end cumulative calls, cumulative distributions and NAV for years
    1..n (n <= life). Least squares on all three curves, each in units of commitment.
    """
    cc, cd, nv = (np.asarray(x, dtype=np.float64) for x in (cum_calls, cum_dist, nav))
    n = cc.size

    def model(theta: Array) -> TAParams:
        rc = tuple(float(x) for x in theta[: rc_years + 1])  # the last rate applies to every later year
        return TAParams(
            rc=rc, growth=float(theta[rc_years + 1]), bow=float(theta[rc_years + 2]), life=life, commitment=commitment
        )

    def resid(theta: Array) -> Array:
        f = takahashi_alexander(model(theta)).frame().iloc[:n]
        return np.concatenate([f["cum_calls"] - cc, f["cum_distributions"] - cd, f["nav"] - nv]) / commitment

    x0 = np.r_[np.full(rc_years + 1, 0.4), 0.10, 2.0]
    lo = np.r_[np.full(rc_years + 1, 0.0), -0.5, 0.1]
    hi = np.r_[np.full(rc_years + 1, 1.0), 1.0, 10.0]
    sol = optimize.least_squares(resid, x0, bounds=(lo, hi), xtol=1e-12, ftol=1e-12, gtol=1e-12)
    return Fit(model(sol.x), float(np.sqrt(np.mean(sol.fun**2))), bool(sol.success))


def annual_curves(times: ArrayLike, amounts: ArrayLike, navs: ArrayLike, life: int) -> tuple[Array, Array, Array]:
    """Year-end cumulative calls, cumulative distributions and NAV from dated flows (investor's side: calls negative)."""
    t = np.asarray(times, dtype=np.float64)
    a = np.asarray(amounts, dtype=np.float64)
    v = np.asarray(navs, dtype=np.float64)
    cc, cd, nv = np.zeros(life), np.zeros(life), np.zeros(life)
    for y in range(1, life + 1):
        upto = t <= y + 1e-9
        cc[y - 1] = -a[upto & (a < 0)].sum()
        cd[y - 1] = a[upto & (a > 0)].sum()
        nv[y - 1] = v[upto][-1] if upto.any() else 0.0
    return cc, cd, nv


# ------------------------------------------------------------------ the stochastic model


@dataclass(frozen=True)
class StochasticSpec:
    ta: TAParams = field(default_factory=TAParams)
    mu: float = 0.11  # expected return of the fund's assets, a year, continuously compounded
    beta: float = 1.2
    market_vol: float = 0.16
    idio_vol: float = 0.20
    call_noise: float = 0.5  # coefficient of variation of the quarterly call rate
    dist_noise: float = 0.5
    smoothing: float = 0.4  # a: share of the true value the appraisal catches each quarter (1 = no lag)
    steps_per_year: int = 4

    @property
    def total_vol(self) -> float:
        return float(np.sqrt((self.beta * self.market_vol) ** 2 + self.idio_vol**2))


@dataclass(frozen=True)
class Paths:
    """Quarterly simulation of many funds. Rows are funds, columns quarters 1..n (time k * dt)."""

    times: Array
    calls: Array
    distributions: Array
    value: Array  # true NAV after each quarter's flows
    reported: Array  # appraisal NAV
    market: Array  # (funds, quarters) market growth factor each quarter (shared within a vintage if given)

    @property
    def net(self) -> Array:
        return self.distributions - self.calls

    def tvpi(self) -> Array:
        return self.distributions.sum(axis=1) / self.calls.sum(axis=1)

    def irrs(self, limit: int | None = None) -> Array:
        n = self.calls.shape[0] if limit is None else min(limit, self.calls.shape[0])
        out = np.full(n, np.nan)
        for i in range(n):
            try:
                out[i] = irr(self.times, self.net[i])
            except ValueError:
                pass
        return out

    def annual_calls(self, steps_per_year: int = 4) -> Array:
        q = self.calls.shape[1]
        years = q // steps_per_year
        return self.calls[:, : years * steps_per_year].reshape(self.calls.shape[0], years, steps_per_year).sum(axis=2)


def _quarter_rate(annual: float, dt: float) -> float:
    return float(1.0 - (1.0 - min(annual, 1.0)) ** dt) if annual < 1.0 else 1.0


def _noise(rng: np.random.Generator, cv: float, size: tuple[int, ...]) -> Array:
    if cv <= 0:
        return np.ones(size)
    s2 = np.log1p(cv**2)
    return np.asarray(np.exp(rng.normal(-0.5 * s2, np.sqrt(s2), size)), dtype=np.float64)


def simulate(
    spec: StochasticSpec,
    funds: int = 5000,
    seed: int = 0,
    market_shocks: ArrayLike | None = None,
    start: float = 0.0,
    value: float = 0.0,
    reported: float | None = None,
    uncalled: float | None = None,
) -> Paths:
    """Simulate ``funds`` funds quarter by quarter.

    ``market_shocks``, if given, is a (quarters,) or (funds, quarters) array of standard normal market
    draws, so that funds of one vintage can share a market path. Calls follow the
    Takahashi-Alexander call rates of the year, converted to a quarterly rate; distributions the
    distribution rate of the year, likewise; both with lognormal noise, capped at everything
    available. The last quarter of the life pays out what is left.

    ``start`` (years), ``value``, ``reported`` and ``uncalled`` continue a fund from a given state,
    which is how a secondary buyer's future is simulated; times are then measured from ``start``.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / spec.steps_per_year
    k0 = int(round(start * spec.steps_per_year))
    n = spec.ta.life * spec.steps_per_year - k0
    times = np.asarray(np.arange(1, n + 1) * dt, dtype=np.float64)
    if market_shocks is None:
        zm = rng.standard_normal((funds, n))
    else:
        zm = np.broadcast_to(np.asarray(market_shocks, dtype=np.float64), (funds, n)).copy()
    zi = rng.standard_normal((funds, n))
    s2 = spec.total_vol**2
    log_growth = (spec.mu - 0.5 * s2) * dt + spec.beta * spec.market_vol * np.sqrt(dt) * zm + spec.idio_vol * np.sqrt(dt) * zi
    growth = np.exp(log_growth)
    mkt = np.exp((-0.5 * spec.market_vol**2) * dt + spec.market_vol * np.sqrt(dt) * zm)
    cnoise = _noise(rng, spec.call_noise, (funds, n))
    dnoise = _noise(rng, spec.dist_noise, (funds, n))
    calls = np.zeros((funds, n))
    dist = np.zeros((funds, n))
    val = np.zeros((funds, n))
    rep = np.zeros((funds, n))
    uncalled_ = np.full(funds, spec.ta.commitment if uncalled is None else uncalled)
    v = np.full(funds, value)
    r = np.full(funds, value if reported is None else reported)
    a = spec.smoothing
    for k in range(n):
        year = int(np.floor((k + k0) * dt)) + 1
        grown = v * growth[:, k]
        c = np.minimum(_quarter_rate(spec.ta.rate_of_call(year), dt) * cnoise[:, k], 1.0) * uncalled_
        if k == n - 1:
            d = grown.copy()
        else:
            d = np.minimum(_quarter_rate(spec.ta.rate_of_distribution(year), dt) * dnoise[:, k], 1.0) * grown
        uncalled_ = uncalled_ - c
        v = grown + c - d
        r = a * v + (1.0 - a) * (r + c - d)
        r = np.maximum(r, 0.0)
        calls[:, k], dist[:, k], val[:, k], rep[:, k] = c, d, v, r
    return Paths(times, calls, dist, val, rep, mkt)


def expected_path(spec: StochasticSpec, value: float, uncalled: float, age: float) -> tuple[Array, Array, Array]:
    """Expected future calls, distributions and times from a fund's state at ``age`` (years), with no noise.

    Noise is mean one and independent of the fund's value, so expected flows follow the deterministic
    recursion with growth ``exp(mu dt)``, as long as the caps on the rates do not bind.
    """
    dt = 1.0 / spec.steps_per_year
    n = spec.ta.life * spec.steps_per_year
    start = int(round(age * spec.steps_per_year))
    g = float(np.exp(spec.mu * dt))
    times, calls, dist = [], [], []
    v, u = value, uncalled
    for k in range(start, n):
        year = int(np.floor(k * dt)) + 1
        grown = v * g
        c = _quarter_rate(spec.ta.rate_of_call(year), dt) * u
        d = grown if k == n - 1 else _quarter_rate(spec.ta.rate_of_distribution(year), dt) * grown
        u -= c
        v = grown + c - d
        times.append((k + 1) * dt - age)
        calls.append(c)
        dist.append(d)
    return np.asarray(times), np.asarray(calls), np.asarray(dist)


def vintage_study(spec: StochasticSpec, vintages: int = 25, funds: int = 400, seed: int = 0) -> pd.DataFrame:
    """Funds of each vintage share one market path; returns each fund's IRR and TVPI with its vintage."""
    rng = np.random.default_rng(seed)
    n = spec.ta.life * spec.steps_per_year
    rows = []
    for v in range(vintages):
        shocks = rng.standard_normal(n)
        paths = simulate(spec, funds, seed=seed + 1000 + v, market_shocks=shocks)
        mret = float(np.prod(paths.market[0]) ** (1.0 / spec.ta.life) - 1.0)
        irrs = paths.irrs()
        for i in range(funds):
            rows.append({"vintage": v, "irr": irrs[i], "tvpi": float(paths.tvpi()[i]), "market": mret})
    return pd.DataFrame(rows)


def variance_split(frame: pd.DataFrame, column: str = "irr") -> dict[str, float]:
    """Share of the variance of ``column`` across funds that lies between vintages rather than within them."""
    d = frame.dropna(subset=[column])
    total = float(d[column].var(ddof=0))
    between = float(d.groupby("vintage")[column].transform("mean").var(ddof=0))
    return {
        "total": total,
        "between": between,
        "within": total - between,
        "between_share": between / total if total > 0 else np.nan,
    }


def with_params(spec: StochasticSpec, **changes: object) -> StochasticSpec:
    return replace(spec, **changes)  # type: ignore[arg-type]
