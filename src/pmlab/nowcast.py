"""Nowcasting a private fund's true value from its stale reported NAVs, with a state-space model and the Kalman filter.

A fund's reported NAV is an appraisal. It moves only part of the way towards the true value each
quarter (Geltner 1993; the Day 3 simulator uses the same rule):

    reported_t = a * value_t + (1 - a) * (reported_{t-1} + calls_t - distributions_t),

so a market fall shows up in reported NAVs over several quarters. The true value is not observed,
but three things are: the reported NAV, the fund's cash flows and the public market's return. The
true value evolves as

    value_t = g_t * value_{t-1} + calls_t - distributions_t,    log g_t = c + beta * log m_t + sigma * e_t,

with ``m_t`` the market's growth factor and ``e_t`` standard normal. Given the market return, the
transition is linear in the state with a variance proportional to the state's second moment, and
the observation is linear in the state. The filter below propagates the exact conditional mean
and variance (a moment-matched Kalman filter, the best linear estimator), for many funds at once.
Appraisals are also noisy, so the reported NAV carries an error ``e_t`` on top of the lag.
Parameters ``(a, beta, c, sigma, obs)`` are estimated by maximum likelihood on a panel of funds that
share them, as an investor with a portfolio of funds from one manager or strategy would.

This follows the idea of Brown, Ghysels and Gredil (2023), who nowcast buyout and venture NAVs
from public-market returns and cash flows, in a deliberately simple form.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import optimize

from .fundmodel import Paths

Array = NDArray[np.float64]
LOG2PI = float(np.log(2.0 * np.pi))


@dataclass(frozen=True)
class Params:
    """Quarterly parameters. ``a``: share of the true value the appraisal catches each quarter (1 = no lag)."""

    a: float = 0.4
    beta: float = 1.2
    c: float = 0.0  # log growth intercept a quarter, given the market
    sigma: float = 0.10  # idiosyncratic volatility a quarter
    obs: float = 0.05  # appraisal noise a quarter, relative to the anchor (last report plus calls)

    @classmethod
    def from_spec(cls, spec: object) -> Params:
        """The true parameters behind :func:`pmlab.fundmodel.simulate` for a :class:`StochasticSpec`."""
        dt = 1.0 / spec.steps_per_year  # type: ignore[attr-defined]
        s2 = spec.total_vol**2  # type: ignore[attr-defined]
        c = (spec.mu - 0.5 * s2) * dt + spec.beta * 0.5 * spec.market_vol**2 * dt  # type: ignore[attr-defined]
        return cls(spec.smoothing, spec.beta, c, spec.idio_vol * np.sqrt(dt))  # type: ignore[attr-defined]


def appraise(value: Array, calls: Array, distributions: Array, a: float, noise: float, seed: int = 0) -> Array:
    """Reported NAVs from true values: a partial adjustment towards the true value plus appraisal noise.

    ``reported_t = a value_t + (1 - a)(reported_{t-1} + calls_t - distributions_t) + e_t``, with
    ``e_t`` normal with standard deviation ``noise * (reported_{t-1} + calls_t + 1)``: the appraiser
    anchors on the last report, and errs in proportion to the fund's size.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(value.shape)
    out = np.zeros_like(value)
    prev = np.zeros(value.shape[0])
    for t in range(value.shape[1]):
        flow = calls[:, t] - distributions[:, t]
        r = a * value[:, t] + (1.0 - a) * (prev + flow) + noise * (prev + calls[:, t] + 1.0) * z[:, t]
        out[:, t] = r
        prev = r
    return out


@dataclass(frozen=True)
class Data:
    """Observed quantities, each (funds, quarters): cash flows, reported NAV and the market's log growth."""

    calls: Array
    distributions: Array
    reported: Array
    log_market: Array

    @classmethod
    def from_paths(cls, p: Paths, a: float = 0.4, noise: float = 0.05, seed: int = 0, quarters: int | None = None) -> Data:
        """Observed data for simulated funds, with reported NAVs from :func:`appraise`.

        Uses the first ``quarters`` (default all but the last, when the fund is wound up).
        """
        n = p.calls.shape[1] - 1 if quarters is None else quarters
        c, d = p.calls[:, :n], p.distributions[:, :n]
        return cls(c, d, appraise(p.value[:, :n], c, d, a, noise, seed), np.log(p.market[:, :n]))

    @property
    def shape(self) -> tuple[int, int]:
        return self.calls.shape


@dataclass(frozen=True)
class Filtered:
    mean: Array  # E[value_t | data up to t]
    var: Array
    pred_mean: Array  # E[value_t | data up to t-1]
    pred_var: Array
    growth: Array  # F_t, the expected growth factor given the market
    loglik: float


def kalman(data: Data, p: Params) -> Filtered:
    """Filter every fund. A fund starts empty, so the state is known exactly before the first call."""
    funds, n = data.shape
    q = np.exp(p.sigma**2) - 1.0
    m = np.zeros(funds)
    v = np.zeros(funds)
    prev = np.zeros(funds)  # reported NAV last quarter
    out = {k: np.zeros((funds, n)) for k in ("mean", "var", "pm", "pv", "f")}
    ll = 0.0
    for t in range(n):
        f = np.exp(p.c + p.beta * data.log_market[:, t] + 0.5 * p.sigma**2)
        flow = data.calls[:, t] - data.distributions[:, t]
        pm = f * m + flow
        pv = f**2 * (v + q * (m**2 + v))
        h = (p.obs * (prev + data.calls[:, t] + 1.0)) ** 2
        base = (1.0 - p.a) * (prev + flow)
        s = p.a**2 * pv + h
        innov = data.reported[:, t] - p.a * pm - base
        k = p.a * pv / s
        m = pm + k * innov
        v = (1.0 - k * p.a) * pv
        ll += float(-0.5 * np.sum(LOG2PI + np.log(s) + innov**2 / s))
        prev = data.reported[:, t]
        out["mean"][:, t], out["var"][:, t], out["pm"][:, t], out["pv"][:, t], out["f"][:, t] = m, v, pm, pv, f
    return Filtered(out["mean"], out["var"], out["pm"], out["pv"], out["f"], ll)


def smooth(fl: Filtered) -> tuple[Array, Array]:
    """Rauch-Tung-Striebel smoother: the best estimate of each past quarter's value given all the data."""
    ms, vs = fl.mean.copy(), fl.var.copy()
    for t in range(fl.mean.shape[1] - 2, -1, -1):
        j = np.divide(
            fl.growth[:, t + 1] * fl.var[:, t],
            fl.pred_var[:, t + 1],
            out=np.zeros_like(ms[:, t]),
            where=fl.pred_var[:, t + 1] > 0,
        )
        ms[:, t] = fl.mean[:, t] + j * (ms[:, t + 1] - fl.pred_mean[:, t + 1])
        vs[:, t] = fl.var[:, t] + j**2 * (vs[:, t + 1] - fl.pred_var[:, t + 1])
    return ms, vs


# ------------------------------------------------------------------ estimation


def _unpack(x: Array) -> Params:
    return Params(
        a=float(1.0 / (1.0 + np.exp(-x[0]))), beta=float(x[1]), c=float(x[2]), sigma=float(np.exp(x[3])), obs=float(np.exp(x[4]))
    )


@dataclass(frozen=True)
class Estimate:
    params: Params
    loglik: float
    success: bool


def estimate(data: Data, start: Params | None = None) -> Estimate:
    """Maximum likelihood for ``(a, beta, c, sigma, obs)`` on a panel of funds sharing them."""
    s = start or Params(a=0.5, beta=1.0, c=0.02, sigma=0.1, obs=0.03)
    x0 = np.array([np.log(s.a / (1.0 - s.a)), s.beta, s.c, np.log(s.sigma), np.log(s.obs)])
    res = optimize.minimize(
        lambda x: -kalman(data, _unpack(x)).loglik,
        x0,
        method="Nelder-Mead",
        options={"xatol": 1e-5, "fatol": 1e-4, "maxiter": 6000},
    )
    return Estimate(_unpack(res.x), float(-res.fun), bool(res.success))


# ------------------------------------------------------------------ the shortcuts an investor might use instead


def reported_returns(data: Data) -> Array:
    """Quarterly returns of the reported NAV, net of flows: (reported_t - calls + distributions) / reported_{t-1} - 1."""
    prev = np.concatenate([np.zeros((data.shape[0], 1)), data.reported[:, :-1]], axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (data.reported - data.calls + data.distributions) / prev - 1.0
    return np.where(prev > 1e-9, r, np.nan)


def naive_beta(data: Data, lags: int = 0, skip: int = 4) -> float:
    """Pooled OLS slope of reported log returns on the market's log return and ``lags`` of its lags (Dimson 1979: summed)."""
    r = np.log1p(reported_returns(data))[:, skip:]
    lm = data.log_market[:, skip:]
    cols = [lm]
    for k in range(1, lags + 1):
        cols.append(np.concatenate([np.full((lm.shape[0], k), np.nan), lm[:, :-k]], axis=1))
    x = np.stack([c.ravel() for c in cols], axis=1)
    y = r.ravel()
    ok = np.isfinite(y) & np.isfinite(x).all(axis=1)
    xm = np.column_stack([np.ones(ok.sum()), x[ok]])
    b = np.linalg.lstsq(xm, y[ok], rcond=None)[0]
    return float(b[1:].sum())


def market_rollforward(data: Data, beta: float = 1.0) -> Array:
    """The practitioner shortcut: last reported NAV rolled forward one quarter with beta times the market, plus flows."""
    prev = np.concatenate([np.zeros((data.shape[0], 1)), data.reported[:, :-1]], axis=1)
    return prev * np.exp(beta * data.log_market) + data.calls - data.distributions


def errors(estimate_: Array, truth: Array, skip: int = 4, floor: float = 5.0) -> Array:
    """Relative errors (estimate / truth - 1) after the first ``skip`` quarters.

    Fund-quarters with a true value below ``floor`` (per 100 committed) are left out: early and late
    in the life the fund holds little, and relative errors there say nothing useful.
    """
    t = truth[:, skip:]
    with np.errstate(divide="ignore", invalid="ignore"):
        e = estimate_[:, skip:] / t - 1.0
    return np.where(t > floor, e, np.nan)


def rmse(e: Array, axis: int | None = None) -> Array | float:
    out = np.sqrt(np.nanmean(e**2, axis=axis))
    return float(out) if axis is None else np.asarray(out)
