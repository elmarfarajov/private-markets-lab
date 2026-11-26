"""Allocating to illiquid assets: commitment pacing, liquidity risk, and the optimal allocation.

**Part 1: an endowment's private equity programme, simulated.** An investor holds liquid assets
(public equity and bonds) and commits each year to a new vintage of private equity. Each vintage
follows the Day 3 stochastic fund model on the scenario's own market path. The investor:

- pays calls and spending out of liquid assets and reinvests distributions;
- values the programme at reported (appraised, lagging) NAV, as real investors do;
- sells part of the programme on the secondary market, at a discount that widens after market
  falls, when liquid assets run out.

:func:`simulate_programme` runs the programme under a pacing rule (:class:`Pacing`) and reports
the allocation, the denominator effect, liquidity shortfalls and the cost of forced sales.

**Part 2: how much to hold.**

- :func:`mean_variance` gives the classic answer with the programme's reported or true risk.
- :func:`solve_dp` gives the answer when the illiquid asset can be rebalanced only at random
  times, at rate ``lam`` a year (Ang, Papanikolaou and Westerfield 2014). It solves a CRRA
  investor's Bellman equation on a grid of the illiquid share, with the liquid part split
  optimally between equity and bonds each year.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from numpy.typing import NDArray

from . import fundmodel as fm

Array = NDArray[np.float64]

PROGRAMME = fm.StochasticSpec(mu=0.10, beta=1.2, idio_vol=0.10, smoothing=0.4)  # a diversified programme, not one fund


@dataclass(frozen=True)
class Market:
    mu: float = 0.07  # public equity, expected return a year (continuously compounded drift + vol^2/2)
    vol: float = 0.16
    r: float = 0.02  # bonds
    equity_share: float = 0.7  # of liquid assets


@dataclass(frozen=True)
class Pacing:
    """Each year commit ``rate x W + gain x (target x W - NAV)`` (floored at zero), ``W`` and NAV at reported values.

    ``gain = 0`` is a constant commitment rate; ``gain > 0`` steers the reported allocation towards
    ``target``.
    """

    target: float = 0.2
    rate: float = 0.08
    gain: float = 0.0
    name: str = "constant"


@dataclass(frozen=True)
class Programme:
    """Quarterly paths, shape (scenarios, quarters), all in units of initial wealth."""

    times: Array
    liquid: Array
    nav_true: Array
    nav_reported: Array
    unfunded: Array
    calls: Array
    distributions: Array
    sold: Array  # reported NAV sold on the secondary market in the quarter
    sale_cost: Array  # discount paid: reported NAV sold minus cash received
    market: Array  # cumulative public-market index (1 at the start)
    commitments: Array = field(repr=False)  # (scenarios, years)

    @property
    def wealth_reported(self) -> Array:
        return self.liquid + self.nav_reported

    @property
    def wealth_true(self) -> Array:
        return self.liquid + self.nav_true

    @property
    def share_reported(self) -> Array:
        return self.nav_reported / self.wealth_reported

    @property
    def share_true(self) -> Array:
        return self.nav_true / self.wealth_true

    @property
    def overcommitment(self) -> Array:
        """(NAV + unfunded commitments) / NAV, at reported values; inf before any NAV exists."""
        with np.errstate(divide="ignore", invalid="ignore"):
            return (self.nav_reported + self.unfunded) / self.nav_reported


def _discount(past_year_market: Array) -> Array:
    """Secondary discount to reported NAV: 5% in calm markets, widening by 0.8 x the past year's market fall, at most 50%."""
    return np.asarray(np.clip(0.05 + 0.8 * np.maximum(0.0, -past_year_market), 0.05, 0.5), dtype=np.float64)


def simulate_programme(
    pacing: Pacing,
    years: int = 30,
    scenarios: int = 2000,
    seed: int = 0,
    market: Market | None = None,
    spec: fm.StochasticSpec = PROGRAMME,
    spending: float = 0.04,
    crash: tuple[int, float] | None = None,
    floor: float = 0.05,
) -> Programme:
    """Run the programme for ``years``; ``crash = (quarter, log shock)`` adds a one-quarter market shock to every scenario.

    When liquid assets fall below ``floor`` x reported wealth, enough of the programme is sold on the
    secondary market to restore the floor.
    """
    mk = market or Market()
    rng = np.random.default_rng(seed)
    q = spec.steps_per_year
    dt = 1.0 / q
    life_q = spec.ta.life * q
    n_q = years * q
    z = rng.standard_normal((scenarios, n_q + life_q))
    if crash is not None:
        z[:, crash[0]] += crash[1] / (mk.vol * np.sqrt(dt))
    # every vintage's flows per unit commitment, on its scenario's market path (linear in commitment)
    unit = spec.ta.commitment
    vint = [
        fm.simulate(spec, funds=scenarios, seed=seed * 1000 + v + 1, market_shocks=z[:, v * q : v * q + life_q])
        for v in range(years)
    ]
    eq = np.exp((mk.mu - 0.5 * mk.vol**2) * dt + mk.vol * np.sqrt(dt) * z[:, :n_q])
    liquid_growth = mk.equity_share * eq + (1 - mk.equity_share) * np.exp(mk.r * dt)
    index = np.cumprod(eq, axis=1)
    out = {
        k: np.zeros((scenarios, n_q))
        for k in ("liquid", "nav_true", "nav_reported", "unfunded", "calls", "distributions", "sold", "sale_cost")
    }
    held = np.zeros((scenarios, years))  # share of each vintage still held (1 until secondary sales)
    commit = np.zeros((scenarios, years))
    liquid = np.ones(scenarios)
    nav_t = np.zeros(scenarios)
    nav_r = np.zeros(scenarios)
    for k in range(n_q):
        y, qi = divmod(k, q)
        if qi == 0:
            w = liquid + nav_r
            c = np.maximum(0.0, pacing.rate * w + pacing.gain * (pacing.target * w - nav_r))
            commit[:, y] = c
            held[:, y] = 1.0
        calls = np.zeros(scenarios)
        dists = np.zeros(scenarios)
        nav_t = np.zeros(scenarios)
        nav_r = np.zeros(scenarios)
        unfunded = np.zeros(scenarios)
        for v in range(y + 1):
            j = k - v * q  # quarter index within the vintage (0-based)
            if j >= life_q:
                continue
            s = commit[:, v] * held[:, v] / unit
            p = vint[v]
            calls += s * p.calls[:, j]
            dists += s * p.distributions[:, j]
            nav_t += s * p.value[:, j]
            nav_r += s * p.reported[:, j]
            unfunded += s * (unit - p.calls[:, : j + 1].sum(axis=1))
        liquid = liquid * liquid_growth[:, k] + dists - calls - spending * dt * (liquid + nav_r)
        # forced secondary sales: restore liquid assets to the floor
        short = liquid < floor * (liquid + nav_r)
        sold = np.zeros(scenarios)
        cost = np.zeros(scenarios)
        if short.any():
            past = index[:, k] / index[:, max(k - q, 0)] - 1.0 if k >= q else np.zeros(scenarios)
            disc = _discount(past)
            # selling x of reported NAV raises x (1 - d) cash and lowers reported wealth by x d:
            # liquid + x (1 - d) = floor (liquid + nav_r - x d)  =>  x = (floor W - liquid) / (1 - d + floor d)
            need = np.maximum(floor * (liquid + nav_r) - liquid, 0.0) / (1 - disc + floor * disc)
            frac = np.where(short, np.minimum(1.0, need / np.maximum(nav_r, 1e-12)), 0.0)
            sold = frac * nav_r
            cost = sold * disc
            liquid = np.where(short, liquid + sold * (1 - disc), liquid)
            held[:, : y + 1] *= (1.0 - frac)[:, None]
            nav_t *= 1.0 - frac
            nav_r *= 1.0 - frac
            unfunded *= 1.0 - frac
        for name, val in (
            ("liquid", liquid),
            ("nav_true", nav_t),
            ("nav_reported", nav_r),
            ("unfunded", unfunded),
            ("calls", calls),
            ("distributions", dists),
            ("sold", sold),
            ("sale_cost", cost),
        ):
            out[name][:, k] = val
    times = np.asarray(np.arange(1, n_q + 1) * dt, dtype=np.float64)
    return Programme(times, market=index, commitments=commit, **out)


# ------------------------------------------------------------------ how much to hold


def programme_moments(
    spec: fm.StochasticSpec = PROGRAMME, market: Market | None = None, funds: int = 4000, seed: int = 1
) -> dict[str, float]:
    """Annualised mean, volatility and market correlation of the programme's quarterly returns at true and reported value.

    Returns are measured on mature funds (years 4-8), net of flows: ``(V_k + D_k - C_k) / V_{k-1} - 1``.
    """
    mk = market or Market()
    p = fm.simulate(spec, funds=funds, seed=seed)
    q = spec.steps_per_year
    out: dict[str, float] = {}
    lo, hi = 4 * q, 8 * q
    m = np.log(p.market[:, lo:hi]).ravel() + (mk.mu) / q  # market log return with the market's drift
    for name, v in (("true", p.value), ("reported", p.reported)):
        r = (v[:, lo:hi] + p.distributions[:, lo:hi] - p.calls[:, lo:hi]) / v[:, lo - 1 : hi - 1] - 1.0
        out[f"{name}_mean"] = float(q * r.mean())
        out[f"{name}_vol"] = float(np.sqrt(q) * np.mean(r.std(axis=1, ddof=1)))  # time-series vol within a fund, averaged
        out[f"{name}_corr"] = float(np.corrcoef(r.ravel(), m)[0, 1])
    return out


def mean_variance(mu: Array, cov: Array, r: float, gamma: float) -> Array:
    """Unconstrained mean-variance weights ``(1 / gamma) Sigma^-1 (mu - r)``."""
    return np.asarray(np.linalg.solve(cov, np.asarray(mu) - r) / gamma, dtype=np.float64)


@dataclass(frozen=True)
class DPSpec:
    gamma: float = 5.0
    horizon: int = 20  # years; utility of wealth at the horizon, the illiquid asset then valued in full
    mu_m: float = 0.07
    vol_m: float = 0.16
    r: float = 0.02
    mu_i: float = 0.09  # illiquid asset, expected return a year
    beta_i: float = 1.2
    idio_i: float = 0.15
    grid: int = 81  # illiquid share from 0 to theta_max
    theta_max: float = 0.8
    alphas: int = 21  # equity share of the liquid part, 0 to 1
    nodes: tuple[int, int] = (7, 5)


@dataclass(frozen=True)
class DPSolution:
    theta: Array  # grid of illiquid shares
    value: Array  # v(theta) at the start: V(W, theta) = W^(1 - gamma) v(theta) / (1 - gamma)
    alpha: Array  # optimal equity share of the liquid part at each theta, first year
    target: float  # theta chosen at the start (and whenever rebalancing is possible, first year)
    lam: float

    def at_target(self) -> float:
        return float(np.interp(self.target, self.theta, self.value))


def _returns(spec: DPSpec) -> tuple[Array, Array, Array]:
    zm, wm = np.polynomial.hermite_e.hermegauss(spec.nodes[0])
    zi, wi = np.polynomial.hermite_e.hermegauss(spec.nodes[1])
    zm_, zi_ = np.meshgrid(zm, zi, indexing="ij")
    w = (np.outer(wm, wi) / (wm.sum() * wi.sum())).ravel()
    rm = np.exp(spec.mu_m - 0.5 * spec.vol_m**2 + spec.vol_m * zm_.ravel())
    s_i = np.sqrt((spec.beta_i * spec.vol_m) ** 2 + spec.idio_i**2)
    ri = np.exp(spec.mu_i - 0.5 * s_i**2 + spec.beta_i * spec.vol_m * zm_.ravel() + spec.idio_i * zi_.ravel())
    return rm, ri, w


def solve_dp(spec: DPSpec, lam: float) -> DPSolution:
    """Backward induction for a CRRA investor whose illiquid share can be reset only with probability ``lam`` a year.

    Utility is over wealth at the horizon, ``W^(1-g) / (1-g)``; by homogeneity
    ``V_t(W, theta) = W^(1-g) v_t(theta) / (1-g)`` with ``v_T = 1``. Each year the investor picks the
    equity share ``alpha`` of the liquid part; wealth grows by
    ``G = theta R_I + (1 - theta)(alpha R_m + (1 - alpha) R_f)`` and the illiquid share becomes
    ``theta R_I / G``. At the start of each later year the investor may, with probability ``lam``,
    reset theta to its best value:
    ``v_t(theta) = opt_alpha E[G^(1-g) (lam opt v_{t+1} + (1 - lam) v_{t+1}(theta'))]``, where "opt" is
    the maximum when ``g < 1`` and the minimum when ``g > 1`` (``V = v W^(1-g) / (1-g)`` is then negative).
    At the start the investor chooses theta freely.
    """
    rm, ri, w = _returns(spec)
    rf = np.exp(spec.r)
    th = np.linspace(0.0, spec.theta_max, spec.grid)
    al = np.linspace(0.0, 1.0, spec.alphas)
    g = 1.0 - spec.gamma
    G = th[:, None, None] * ri[None, None, :] + (1 - th)[:, None, None] * (
        al[None, :, None] * rm[None, None, :] + (1 - al)[None, :, None] * rf
    )
    nxt = np.clip(th[:, None, None] * ri[None, None, :] / G, 0.0, spec.theta_max)
    Gg = G**g
    opt, arg = (np.min, np.argmin) if g < 0 else (np.max, np.argmax)
    v = np.ones(spec.grid)
    q = np.zeros((spec.grid, spec.alphas))
    for _ in range(spec.horizon):
        cont = lam * float(opt(v)) + (1 - lam) * np.interp(nxt, th, v)
        q = np.einsum("tan,n->ta", Gg * cont, w)
        v = opt(q, axis=1)
    return DPSolution(th, v, al[arg(q, axis=1)], float(th[arg(v)]), lam)


def illiquidity_cost(spec: DPSpec, lam: float, liquid: DPSolution | None = None) -> float:
    """Share of initial wealth, a year, that an investor would pay to make the illiquid asset fully liquid (``lam = 1``).

    With ``V = W^(1-g) v / (1-g)``, an investor with wealth ``1 - c`` and a liquid asset is as well off
    as one with wealth 1 and an illiquid one when ``(1 - c)^(1-g) v_liquid = v_illiquid``; the annual
    figure spreads ``c`` evenly over the horizon.
    """
    a = solve_dp(spec, lam)
    b = liquid or solve_dp(spec, 1.0)
    c = 1.0 - (a.at_target() / b.at_target()) ** (1.0 / (1.0 - spec.gamma))
    return float(1.0 - (1.0 - c) ** (1.0 / spec.horizon))


def with_dp(spec: DPSpec, **changes: object) -> DPSpec:
    return replace(spec, **changes)  # type: ignore[arg-type]
