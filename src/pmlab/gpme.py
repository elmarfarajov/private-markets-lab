"""Risk-adjusted performance with a stochastic discount factor: Korteweg-Nagel GPME and cash-flow betas.

A private fund's cash flows can be valued like any other payoff: discount each one by a
stochastic discount factor (SDF) ``M`` that prices the assets the investor could have held
instead. Korteweg and Nagel (2016) use the exponential-affine SDF

    M(0, t) = exp(-a t - b ln(I_t / I_0)),

with ``a`` and ``b`` chosen so that ``M`` prices both the public market ``I`` and the risk-free
asset. The generalised PME (GPME) is then the fund's net present value under ``M``; zero means
no abnormal return. Kaplan and Schoar's PME is the special case ``a = 0, b = 1`` (``M = I_0 / I_t``),
which prices the market but not the risk-free rate unless the market's risk premium equals its
variance. When ``b`` differs from one, KS-PME misprices any fund whose market exposure is not
exactly one: with a positive equity premium it rewards leverage.

The module provides:

* :class:`SDF` with a log-normal (closed-form) and an empirical (sample-moment) fit;
* :func:`fair_alpha`: the drift a power-of-the-index payoff needs to be priced at zero under an SDF;
* :func:`gpme` (NPV per unit called), :func:`npv` and :func:`pme_ratio` for one fund;
* :func:`cashflow_beta`: Driessen, Lin and Phalippou's (2012) alpha and beta, chosen so that the
  funds' discounted cash flows are as close to zero as possible.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq, minimize

Array = NDArray[np.float64]


@dataclass(frozen=True)
class SDF:
    """``M(0, t) = exp(-a t - b ln(I_t / I_0))``; ``a`` a year, ``b`` the relative risk aversion."""

    a: float
    b: float

    @classmethod
    def kaplan_schoar(cls) -> SDF:
        return cls(0.0, 1.0)

    @classmethod
    def lognormal(cls, mu: float, sigma: float, r: float) -> SDF:
        """The SDF pricing a log-normal market (arithmetic drift ``mu``, volatility ``sigma``) and a bond at rate ``r``.

        ``b = (mu - r) / sigma^2``, ``a = r - b m + b^2 sigma^2 / 2`` with ``m = mu - sigma^2 / 2``.
        """
        b = (mu - r) / sigma**2
        m = mu - 0.5 * sigma**2
        return cls(r - b * m + 0.5 * b**2 * sigma**2, b)

    @classmethod
    def fit(cls, levels: ArrayLike, dt: float, r: float) -> SDF:
        """The SDF whose sample averages price the market's ``dt`` returns and a bond at rate ``r`` exactly.

        With ``x`` the log returns: ``mean(M) = exp(-r dt)`` gives ``a`` for each ``b``, and ``b``
        solves ``mean(M exp(x)) = 1``.
        """
        x = np.diff(np.log(np.asarray(levels, dtype=np.float64)))

        def a_of(b: float) -> float:
            return r + float(np.log(np.mean(np.exp(-b * x)))) / dt

        def gap(b: float) -> float:
            return float(np.exp(-a_of(b) * dt) * np.mean(np.exp((1.0 - b) * x)) - 1.0)

        b = float(brentq(gap, -20.0, 40.0))
        return cls(a_of(b), b)

    def discount(self, times: ArrayLike, index: ArrayLike) -> Array:
        """``M(0, t)`` at each date, from the index level at that date and at the first date."""
        t = np.asarray(times, dtype=np.float64)
        i = np.asarray(index, dtype=np.float64)
        return np.asarray(np.exp(-self.a * (t - t[0]) - self.b * np.log(i / i[0])), dtype=np.float64)


def fair_alpha(beta: float, sdf: SDF, mu: float, sigma: float) -> float:
    """The drift ``alpha`` at which ``exp(alpha t) (I_t / I_0)^beta`` has price one under ``sdf`` on a log-normal market.

    ``alpha* = a - (beta - b) m - (beta - b)^2 sigma^2 / 2`` with ``m = mu - sigma^2 / 2``. Under the SDF
    that also prices the bond, this is ``(1 - beta)(r + beta sigma^2 / 2)``: a levered power payoff
    has convexity, so it needs a negative drift to be fair when ``beta > 1``.
    """
    m = mu - 0.5 * sigma**2
    return sdf.a - (beta - sdf.b) * m - 0.5 * (beta - sdf.b) ** 2 * sigma**2


def npv(times: ArrayLike, amounts: ArrayLike, index: ArrayLike, sdf: SDF, nav: float = 0.0) -> float:
    """Present value at the first date of the investor's flows (calls negative) and the final NAV."""
    m = sdf.discount(times, index)
    return float(np.sum(m * np.asarray(amounts, dtype=np.float64)) + m[-1] * nav)


def gpme(times: ArrayLike, amounts: ArrayLike, index: ArrayLike, sdf: SDF, nav: float = 0.0) -> float:
    """Korteweg-Nagel GPME: the NPV under ``sdf`` per unit of capital called (undiscounted); zero means no abnormal return.

    The NPV is linear in the cash flows, so its average across funds is an unbiased estimate of the
    expected NPV. A ratio of discounted distributions to discounted calls (:func:`pme_ratio`) is not.
    """
    a = np.asarray(amounts, dtype=np.float64)
    return npv(times, a, index, sdf, nav) / float(np.sum(np.where(a < 0, -a, 0.0)))


def pme_ratio(times: ArrayLike, amounts: ArrayLike, index: ArrayLike, sdf: SDF, nav: float = 0.0) -> float:
    """Discounted distributions (and NAV) over discounted calls; with the Kaplan-Schoar SDF this is KS-PME."""
    a = np.asarray(amounts, dtype=np.float64)
    m = sdf.discount(times, index)
    calls = float(np.sum(m * np.where(a < 0, -a, 0.0)))
    dists = float(np.sum(m * np.where(a > 0, a, 0.0)) + m[-1] * nav)
    return dists / calls


# ------------------------------------------------------------------ cash-flow betas


@dataclass(frozen=True)
class CashflowBeta:
    alpha: float  # a year
    beta: float
    loss: float  # mean squared NPV per unit of calls at the optimum
    funds: int


def _growth(times: Array, index: Array, alpha: float, beta: float, r: float) -> Array:
    """Compounded ``1 + (r + alpha) dt + beta (R - 1 - r dt)`` along the fund's grid, one at the first date."""
    dt = np.diff(times)
    ret = index[1:] / index[:-1] - 1.0
    step = 1.0 + (r + alpha) * dt + beta * (ret - r * dt)
    return np.concatenate([[1.0], np.cumprod(np.maximum(step, 1e-6))])


def cashflow_beta(
    funds: Sequence[tuple[ArrayLike, ArrayLike, ArrayLike]], r: float, start: tuple[float, float] = (0.0, 1.0)
) -> CashflowBeta:
    """Driessen-Lin-Phalippou alpha and beta: minimise the mean squared NPV per unit of calls across funds.

    Each fund is ``(times, amounts, index)`` on its own grid, liquidated (no NAV). A cash flow at ``t``
    is discounted by the compounded return of a portfolio holding ``beta`` in the market and
    ``1 - beta`` in the bond, plus ``alpha`` a year.
    """
    data = [
        (np.asarray(t, dtype=np.float64), np.asarray(a, dtype=np.float64), np.asarray(i, dtype=np.float64)) for t, a, i in funds
    ]
    scale = [float(np.sum(np.where(a < 0, -a, 0.0))) for _, a, _ in data]

    def loss(p: Array) -> float:
        total = 0.0
        for (t, a, i), s in zip(data, scale, strict=True):
            total += (float(np.sum(a / _growth(t, i, float(p[0]), float(p[1]), r))) / s) ** 2
        return total / len(data)

    res = minimize(loss, np.asarray(start), method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 4000})
    return CashflowBeta(float(res.x[0]), float(res.x[1]), float(res.fun), len(data))
