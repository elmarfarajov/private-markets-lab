"""Cash flows of a private fund from the investor's side, and the measures every report quotes.

**Convention.** Amounts are from the limited partner's side: capital calls (contributions,
fees included) are negative, distributions positive. A fund that has not finished carries
a net asset value, which is treated as a final distribution on its date - the convention of
every performance report, and the reason an interim IRR is partly an opinion.

Times are in years. Rates compound annually on an actual/365 basis, the XIRR convention,
so that ``NPV(r) = sum_i a_i (1 + r)^(-t_i)``.

**The internal rate of return** is a root of the NPV, and an NPV can have no root, one, or
several. Writing ``x = ln(1 + r)`` turns the NPV into ``f(x) = sum_i a_i exp(-x t_i)``, a
generalised Dirichlet polynomial. Descartes' rule of signs holds for it: the number of
positive roots is at most the number of sign changes in the amounts taken in time order,
and differs from it by an even number. When the *cumulative* amounts change sign only once
(Norstrom's condition) there is exactly one *positive* IRR - but a negative one can still
exist beside it, as this lab's validation found on random streams. This module finds every
root, not the first one a solver happens to reach, and says when the answer is not unique.

**Multiples** need no rate at all: paid-in capital (PIC), distributions (DPI), the residual
value (RVPI) and their sum (TVPI), each per unit of capital paid in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq

Array = NDArray[np.float64]
DAYS_PER_YEAR = 365.0


@dataclass(frozen=True)
class CashFlows:
    """A stream of dated amounts from the investor's side, with the net asset value left at the end."""

    times: Array  # years, increasing
    amounts: Array  # contributions negative, distributions positive
    nav: float = 0.0  # residual value at times[-1]

    def __post_init__(self) -> None:
        t = np.asarray(self.times, dtype=np.float64)
        a = np.asarray(self.amounts, dtype=np.float64)
        if t.shape != a.shape or t.ndim != 1 or t.size == 0:
            raise ValueError("times and amounts must be one-dimensional and of equal, non-zero length")
        if np.any(np.diff(t) < 0):
            raise ValueError("times must not decrease")
        object.__setattr__(self, "times", t)
        object.__setattr__(self, "amounts", a)

    @classmethod
    def from_dates(cls, dates: Sequence[date], amounts: ArrayLike, nav: float = 0.0) -> CashFlows:
        start = dates[0]
        return cls(np.array([(d - start).days / DAYS_PER_YEAR for d in dates]), np.asarray(amounts, dtype=np.float64), nav)

    def with_nav(self) -> tuple[Array, Array]:
        """Amounts with the residual value added as a distribution at the last date."""
        a = self.amounts.copy()
        a[-1] += self.nav
        return self.times, a

    @property
    def contributions(self) -> float:
        return float(-self.amounts[self.amounts < 0].sum())

    @property
    def distributions(self) -> float:
        return float(self.amounts[self.amounts > 0].sum())


# ---------------------------------------------------------------- present value and the IRR


def npv(rate: float | Array, times: ArrayLike, amounts: ArrayLike) -> Array:
    """``sum_i a_i (1 + r)^(-t_i)`` for one rate or many."""
    r = np.atleast_1d(np.asarray(rate, dtype=np.float64))
    t = np.asarray(times, dtype=np.float64)
    a = np.asarray(amounts, dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        return np.asarray(np.exp(-np.log1p(r)[:, None] * t[None, :]) @ a, dtype=np.float64)


def sign_changes(amounts: ArrayLike) -> int:
    """Sign changes in the non-zero amounts, in time order: Descartes' bound on the number of IRRs."""
    a = np.asarray(amounts, dtype=np.float64)
    s = np.sign(a[a != 0])
    return int(np.count_nonzero(s[1:] != s[:-1]))


def norstrom(amounts: ArrayLike) -> bool:
    """Norstrom (1972): one sign change in the cumulative amounts, ending non-zero, guarantees exactly one positive IRR."""
    c = np.cumsum(np.asarray(amounts, dtype=np.float64))
    return sign_changes(c) == 1 and c[-1] != 0


def irr_roots(times: ArrayLike, amounts: ArrayLike, lo: float = -0.99, hi: float = 100.0, points: int = 4001) -> list[float]:
    """Every IRR in ``(lo, hi)``: the NPV is scanned on a grid even in ``ln(1 + r)`` and each sign change refined.

    Roots where the NPV touches zero without crossing (double roots) are reported when the
    scan lands within 1e-12 of zero relative to the stream's size; Descartes' bound caps the count.
    """
    t = np.asarray(times, dtype=np.float64)
    a = np.asarray(amounts, dtype=np.float64)
    if not np.any(a):
        raise ValueError("every amount is zero: the NPV is zero at every rate")
    x = np.linspace(np.log1p(lo), np.log1p(hi), points)
    r = np.expm1(x)
    f = npv(r, t, a)
    scale = float(np.abs(a).sum())
    roots: list[float] = []
    for i in range(points - 1):
        if f[i] == 0.0:
            roots.append(float(r[i]))
        elif np.sign(f[i]) != np.sign(f[i + 1]) and f[i + 1] != 0.0:
            roots.append(float(brentq(lambda q: float(npv(q, t, a)[0]), r[i], r[i + 1], xtol=1e-15, rtol=1e-15, maxiter=200)))
    # touching roots: a local minimum of |f| that is numerically zero and not already found
    small = np.abs(f) <= 1e-12 * scale
    for j in np.flatnonzero(small):
        if all(abs(r[j] - q) > 1e-6 * (1 + abs(q)) for q in roots):
            roots.append(float(r[j]))
    return sorted(roots)


def irr(times: ArrayLike, amounts: ArrayLike) -> float:
    """The IRR when it is unique; otherwise ``ValueError`` naming the roots found."""
    roots = irr_roots(times, amounts)
    if len(roots) != 1:
        raise ValueError(f"the IRR is not unique: {len(roots)} roots {[round(q, 6) for q in roots]}")
    return roots[0]


def fund_irr(cf: CashFlows) -> float:
    """The fund's IRR with its residual value treated as a final distribution."""
    return irr(*cf.with_nav())


def mirr(times: ArrayLike, amounts: ArrayLike, finance_rate: float, reinvest_rate: float) -> float:
    """Modified IRR: contributions discounted at ``finance_rate``, distributions compounded at ``reinvest_rate`` to the end.

    ``(FV of distributions / PV of contributions)^(1/T) - 1``; it always exists and is unique.
    """
    t = np.asarray(times, dtype=np.float64)
    a = np.asarray(amounts, dtype=np.float64)
    horizon = float(t[-1] - t[0])
    pv = -float(np.sum(np.where(a < 0, a, 0.0) * (1 + finance_rate) ** (-(t - t[0]))))
    fv = float(np.sum(np.where(a > 0, a, 0.0) * (1 + reinvest_rate) ** (t[-1] - t)))
    return float((fv / pv) ** (1.0 / horizon) - 1.0)


def periodic_roots(amounts: ArrayLike) -> list[float]:
    """IRRs of equally spaced amounts, from the roots of the polynomial in ``v = 1/(1 + r)``: an independent route."""
    a = np.asarray(amounts, dtype=np.float64)
    roots = np.roots(a[::-1])  # sum_k a_k v^k = 0, coefficients highest power first
    v = roots[(np.abs(roots.imag) < 1e-10) & (roots.real > 0)].real
    return sorted(float(1.0 / x - 1.0) for x in v)


# ---------------------------------------------------------------- multiples


@dataclass(frozen=True)
class Multiples:
    paid_in: float
    distributed: float
    residual: float
    dpi: float
    rvpi: float
    tvpi: float


def multiples(cf: CashFlows) -> Multiples:
    pic = cf.contributions
    if pic <= 0:
        raise ValueError("no capital has been paid in")
    dist = cf.distributions
    return Multiples(pic, dist, cf.nav, dist / pic, cf.nav / pic, (dist + cf.nav) / pic)


def interim(
    times: ArrayLike, amounts: ArrayLike, navs: ArrayLike, at: ArrayLike | None = None, points: int = 801
) -> dict[str, Array]:
    """DPI, RVPI, TVPI and the interim IRR at each date, given the reported NAV after each date's flows.

    The IRR is computed only at the date indices ``at`` (all dates by default), on a scan of ``points``.
    """
    t = np.asarray(times, dtype=np.float64)
    a = np.asarray(amounts, dtype=np.float64)
    v = np.asarray(navs, dtype=np.float64)
    pic = np.cumsum(np.where(a < 0, -a, 0.0))
    dist = np.cumsum(np.where(a > 0, a, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        dpi = np.where(pic > 0, dist / pic, np.nan)
        rvpi = np.where(pic > 0, v / pic, np.nan)
    rates = np.full(t.size, np.nan)
    for i in range(t.size) if at is None else np.asarray(at, dtype=int):
        if t[i] - t[0] < 0.25:
            continue  # the IRR over a few weeks is an annualised artefact
        flows = a[: i + 1].copy()
        flows[-1] += v[i]
        roots = irr_roots(t[: i + 1], flows, lo=-0.999, points=points)
        if len(roots) == 1:
            rates[i] = roots[0]
    return {"dpi": dpi, "rvpi": rvpi, "tvpi": dpi + rvpi, "irr": rates, "paid_in": pic, "net": np.cumsum(a)}
