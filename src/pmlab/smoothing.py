"""Smoothed returns and hidden risk: what appraisal-based private equity returns understate, and how to unsmooth them.

An index built from reported NAVs inherits the appraisal's lag (Day 5). Its returns are
autocorrelated, too smooth and too weakly linked to the market. Two standard corrections recover
the true return series from the reported one:

* **Geltner (1993)**: if ``r_obs_t = a r_t + (1 - a) r_obs_{t-1}``, then
  ``r_t = (r_obs_t - (1 - a) r_obs_{t-1}) / a``, with ``1 - a`` estimated as the first-order
  autocorrelation of the reported returns;
* **Getmansky, Lo and Makarov (2004, "GLM")**: ``r_obs_t = theta_0 r_t + ... + theta_k r_{t-k}``
  with the thetas summing to one, estimated by maximum likelihood as a moving average.

The module also builds the index: funds of many vintages sharing one market path, valued at their
true value and at their reported NAV, aggregated each quarter.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy import optimize

from . import fundmodel as fm
from . import nowcast as nc

Array = NDArray[np.float64]


# ------------------------------------------------------------------ an index of funds


@dataclass(frozen=True)
class Index:
    """Quarterly returns of a private equity index, true and reported, and of the market."""

    true: pd.Series
    reported: pd.Series
    market: pd.Series  # the public market's return each quarter

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame({"true": self.true, "reported": self.reported, "market": self.market})


def build_index(
    spec: fm.StochasticSpec | None = None,
    vintages: int = 30,
    funds: int = 40,
    a: float = 0.4,
    noise: float = 0.05,
    seed: int = 0,
    public: float = 0.8,
    premium: float = 0.06,
) -> Index:
    """Funds of ``vintages`` yearly vintages, ``funds`` each, sharing one market path; aggregated by calendar quarter.

    The index return is ``sum(value_t - calls_t + distributions_t) / sum(value_{t-1}) - 1`` over the
    funds alive, computed once from true values and once from reported NAVs. Quarters before
    five vintages are running are dropped, so the index is diversified across vintages.

    The funds' systematic shock is ``public * z_market + sqrt(1 - public^2) * z_private``: a share
    of it is the public market, the rest a factor common to private funds (sector, leverage, the
    buyout cycle) that the public market does not carry. Without it, a thousand funds diversify
    into a pure market bet. The market's own excess return has an expected ``premium`` a year.
    """
    spec = spec or fm.StochasticSpec()
    q = spec.ta.life * spec.steps_per_year
    total = (vintages - 1) * spec.steps_per_year + q
    rng = np.random.default_rng(seed)
    z_pub = rng.standard_normal(total)
    z = public * z_pub + np.sqrt(1.0 - public**2) * rng.standard_normal(total)
    num_t = np.zeros(total)
    num_r = np.zeros(total)
    den_t = np.zeros(total)
    den_r = np.zeros(total)
    for v in range(vintages):
        start = v * spec.steps_per_year
        p = fm.simulate(spec, funds, seed=seed * 1000 + v + 1, market_shocks=z[start : start + q])
        rep = nc.appraise(p.value, p.calls, p.distributions, a, noise, seed=seed * 1000 + 500 + v)
        for x, num, den in ((p.value, num_t, den_t), (rep, num_r, den_r)):
            prev = np.concatenate([np.zeros((funds, 1)), x[:, :-1]], axis=1)
            num[start : start + q] += (x - p.calls + p.distributions).sum(axis=0)
            den[start : start + q] += prev.sum(axis=0)
    mkt = (
        np.exp(
            (premium - 0.5 * spec.market_vol**2) / spec.steps_per_year
            + spec.market_vol * np.sqrt(1 / spec.steps_per_year) * z_pub
        )
        - 1.0
    )
    first = 5 * spec.steps_per_year
    last = (vintages - 1) * spec.steps_per_year + spec.steps_per_year  # while new vintages still join
    idx = pd.period_range("1995Q1", periods=total, freq="Q")[first:last]
    sl = slice(first, last)
    return Index(
        pd.Series(num_t[sl] / den_t[sl] - 1.0, index=idx, name="true"),
        pd.Series(num_r[sl] / den_r[sl] - 1.0, index=idx, name="reported"),
        pd.Series(mkt[sl], index=idx, name="market"),
    )


# ------------------------------------------------------------------ unsmoothing


def geltner(r: pd.Series, a: float | None = None) -> tuple[pd.Series, float]:
    """Geltner's unsmoothing; ``a`` defaults to one minus the first-order autocorrelation of ``r``."""
    if a is None:
        a = 1.0 - float(r.autocorr(1))
    out = (r - (1.0 - a) * r.shift(1)) / a
    return out.dropna().rename("geltner"), a


@dataclass(frozen=True)
class GLM:
    theta: Array  # smoothing weights, theta_0 first, summing to one
    mu: float
    sigma: float  # volatility of the true return a period
    loglik: float
    true: pd.Series  # the implied true returns

    @property
    def xi(self) -> float:
        """GLM's smoothing index, the sum of squared thetas: 1 for no smoothing, 1/(k+1) for even weights."""
        return float(np.sum(self.theta**2))


def _glm_innovations(x: Array, theta: Array, mu: float) -> Array:
    k = theta.size - 1
    e = np.zeros(x.size)
    for t in range(x.size):
        past = sum(theta[j] * e[t - j] for j in range(1, k + 1) if t - j >= 0)
        e[t] = (x[t] - mu - past) / theta[0]
    return e


def glm(r: pd.Series, k: int = 2) -> GLM:
    """Maximum likelihood (conditional on zero pre-sample shocks) of the GLM MA(k) smoothing model.

    ``r_obs_t - mu = theta_0 e_t + ... + theta_k e_{t-k}``, ``e`` iid normal with variance ``sigma^2``,
    thetas summing to one with ``theta_0 > 0``; the true return is ``mu + e_t``. The likelihood is
    concentrated in ``sigma``; the thetas use a softmax so they stay positive and sum to one.
    """
    x = r.dropna().to_numpy()
    mu = float(x.mean())

    def thetas(z: Array) -> Array:
        w = np.exp(np.r_[0.0, z])
        return np.asarray(w / w.sum(), dtype=np.float64)

    def nll(z: Array) -> float:
        th = thetas(z)
        e = _glm_innovations(x, th, mu)
        s2 = float(np.mean(e**2))
        return float(0.5 * x.size * np.log(s2) + x.size * np.log(th[0]))

    res = optimize.minimize(nll, np.zeros(k), method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 4000})
    th = thetas(res.x)
    e = _glm_innovations(x, th, mu)
    sigma = float(np.sqrt(np.mean(e**2)))
    ll = float(-res.fun - 0.5 * x.size * (np.log(2 * np.pi) + 1.0))
    true = pd.Series(mu + e, index=r.dropna().index, name="glm")
    return GLM(th, mu, sigma, ll, true)


def partial_adjustment_weights(a: float, k: int) -> Array:
    """The thetas a partial-adjustment appraisal with speed ``a`` implies, truncated at ``k`` lags and renormalised."""
    w = a * (1.0 - a) ** np.arange(k + 1)
    return np.asarray(w / w.sum(), dtype=np.float64)


# ------------------------------------------------------------------ what smoothing hides


def risk_table(series: dict[str, pd.Series], market: pd.Series, periods: int = 4) -> pd.DataFrame:
    """Annualised mean, volatility, Sharpe ratio, beta, correlation, worst drawdown and lag-1 autocorrelation."""
    rows = {}
    for name, s in series.items():
        d = pd.concat([s.rename("s"), market.rename("m")], axis=1).dropna()
        nav = (1 + d["s"]).cumprod()
        rows[name] = {
            "mean": periods * d["s"].mean(),
            "vol": np.sqrt(periods) * d["s"].std(),
            "sharpe": np.sqrt(periods) * d["s"].mean() / d["s"].std(),
            "beta": d["s"].cov(d["m"]) / d["m"].var(),
            "corr": d["s"].corr(d["m"]),
            "maxdd": float((nav / nav.cummax() - 1).min()),
            "ac1": d["s"].autocorr(1),
        }
    return pd.DataFrame(rows).T


def horizon_correlation(a: pd.Series, b: pd.Series, horizons: tuple[int, ...] = (1, 2, 4, 8)) -> pd.Series:
    """Correlation of non-overlapping ``h``-period compounded returns, for each horizon."""
    out = {}
    d = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    for h in horizons:
        g = np.arange(len(d)) // h
        agg = (1 + d).groupby(g).prod() - 1
        agg = agg[d.groupby(g).size().to_numpy() == h]
        out[h] = float(agg["a"].corr(agg["b"]))
    return pd.Series(out)


def tangency_weight(asset: pd.Series, market: pd.Series, rf: float = 0.0) -> float:
    """Weight on ``asset`` in the maximum-Sharpe mix of the asset and the market (unconstrained)."""
    d = pd.concat([asset.rename("a"), market.rename("m")], axis=1).dropna()
    mu = d.mean().to_numpy() - rf
    w = np.linalg.solve(d.cov().to_numpy(), mu)
    return float(w[0] / w.sum())
