"""Public market equivalents: a private fund measured against what the same money would have done in an index.

An IRR says nothing about the market a fund lived through: a 15% IRR from a vintage that
caught a bull market can be worse than 10% from one that caught a crash. A public market
equivalent (PME) replays the fund's cash flows against an index. With index levels ``I_t``
at each cash-flow date and ``I_T`` at the valuation date, write ``g_t = I_T / I_t`` for
what one unit put into the index at ``t`` is worth at ``T``.

* **Kaplan-Schoar PME** (2005): ``(sum D_t g_t + NAV_T) / (sum C_t g_t)``. A ratio above
  one beat the index. It is the only member of the family with an economic interpretation
  - it is the fund's value under a log-utility investor's discount factor (Sorensen and
  Jagannathan, 2015) - but it assumes the fund's beta to the index is one.
* **Direct Alpha** (Gredil, Griffiths and Stucke, 2014): the IRR of the flows compounded
  to ``T`` at the index, ``a_t g_t`` plus ``NAV_T``; reported continuously compounded,
  ``ln(1 + IRR)``. It is zero exactly when the Kaplan-Schoar PME is one, and it is the
  rate of outperformance a fund earning the index times ``exp(alpha t)`` would show.
* **Long-Nickels** (1996): contributions bought and distributions sold in an index
  account; the account's final value replaces the NAV and the IRR of the result is the
  index's "IRR". The account can go negative when a fund distributes faster than the
  index could have grown - the method's known defect.
* **PME+** (Rouvinez, 2003): distributions scaled by one factor so the index account ends
  at the fund's NAV, which keeps it positive.
* **mPME** (Cambridge Associates, 2013): the index account pays out the same *fraction*
  of itself as the fund distributes of its NAV, which needs the fund's NAV at each date.

All five agree in one place: a fund that *is* the index scores a PME of one and an index
IRR equal to its own. That identity, and closed forms for a single deal, are the tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .cashflows import irr, irr_roots

Array = NDArray[np.float64]


def _split(amounts: ArrayLike) -> tuple[Array, Array]:
    a = np.asarray(amounts, dtype=np.float64)
    return np.where(a < 0, -a, 0.0), np.where(a > 0, a, 0.0)


def ks_pme(amounts: ArrayLike, index: ArrayLike, nav: float = 0.0, index_end: float | None = None) -> float:
    """Kaplan-Schoar PME; ``index`` at each cash-flow date, ``index_end`` at the valuation date (default: the last)."""
    c, d = _split(amounts)
    i = np.asarray(index, dtype=np.float64)
    end = float(i[-1] if index_end is None else index_end)
    g = end / i
    return float((np.sum(d * g) + nav) / np.sum(c * g))


def direct_alpha(
    times: ArrayLike, amounts: ArrayLike, index: ArrayLike, nav: float = 0.0, index_end: float | None = None
) -> float:
    """Direct Alpha, continuously compounded: ``ln(1 + IRR)`` of the flows compounded to the end at the index."""
    i = np.asarray(index, dtype=np.float64)
    end = float(i[-1] if index_end is None else index_end)
    flows = np.asarray(amounts, dtype=np.float64) * end / i
    flows[-1] += nav
    return float(np.log1p(irr(times, flows)))


@dataclass(frozen=True)
class LongNickels:
    index_irr: float  # NaN when the replayed stream has no unique IRR
    roots: list[float]  # every IRR of the replayed stream
    account: Array  # the index account's value after each date's flows
    negative: bool  # the account went below zero somewhere


def long_nickels(times: ArrayLike, amounts: ArrayLike, index: ArrayLike, nav: float = 0.0) -> LongNickels:
    """Long-Nickels: the fund's flows replayed in an index account, whose final value stands in for the NAV."""
    c, d = _split(amounts)
    i = np.asarray(index, dtype=np.float64)
    account = np.empty_like(i)
    value = 0.0
    for k in range(i.size):
        value = (value * i[k] / i[k - 1] if k else 0.0) + c[k] - d[k]
        account[k] = value
    flows = d - c
    flows[-1] += account[-1]
    del nav  # the fund's own NAV is replaced by the account's value: that is the method
    roots = irr_roots(times, flows)
    value = roots[0] if len(roots) == 1 else float("nan")
    return LongNickels(value, roots, account, bool(np.any(account < 0)))


def pme_plus(times: ArrayLike, amounts: ArrayLike, index: ArrayLike, nav: float = 0.0) -> tuple[float, float]:
    """PME+: (index IRR, scaling factor) with distributions scaled so the index account ends at the fund's NAV."""
    c, d = _split(amounts)
    i = np.asarray(index, dtype=np.float64)
    g = i[-1] / i
    scale = float((np.sum(c * g) - nav) / np.sum(d * g)) if np.sum(d) > 0 else 0.0
    flows = scale * d - c
    flows[-1] += nav
    return irr(times, flows), scale


def mpme(times: ArrayLike, amounts: ArrayLike, index: ArrayLike, navs: ArrayLike) -> float:
    """Cambridge Associates' mPME: the index account distributes the same share of itself as the fund of its NAV.

    ``navs`` are the fund's NAVs after each date's flows; the last is the valuation NAV.
    """
    c, d = _split(amounts)
    i = np.asarray(index, dtype=np.float64)
    v = np.asarray(navs, dtype=np.float64)
    value = 0.0
    paid = np.zeros_like(i)
    for k in range(i.size):
        value = (value * i[k] / i[k - 1] if k else 0.0) + c[k]
        before = d[k] + v[k]
        share = d[k] / before if before > 0 else 0.0
        paid[k] = share * value
        value -= paid[k]
    flows = paid - c
    flows[-1] += value
    return irr(times, flows)


@dataclass(frozen=True)
class PMEReport:
    fund_irr: float
    ks_pme: float
    direct_alpha: float  # continuously compounded
    ln_irr: float
    ln_negative: bool
    pme_plus_irr: float
    pme_plus_scale: float
    mpme_irr: float | None

    @property
    def excess(self) -> dict[str, float]:
        """Fund IRR less each method's index IRR, in the method's own terms."""
        out = {"Long-Nickels": self.fund_irr - self.ln_irr, "PME+": self.fund_irr - self.pme_plus_irr}
        if self.mpme_irr is not None:
            out["mPME"] = self.fund_irr - self.mpme_irr
        return out


def report(times: ArrayLike, amounts: ArrayLike, index: ArrayLike, nav: float = 0.0, navs: ArrayLike | None = None) -> PMEReport:
    """Every PME of one fund against one index."""
    flows = np.asarray(amounts, dtype=np.float64).copy()
    flows[-1] += nav
    ln = long_nickels(times, amounts, index, nav)
    plus, scale = pme_plus(times, amounts, index, nav)
    return PMEReport(
        irr(times, flows),
        ks_pme(amounts, index, nav),
        direct_alpha(times, amounts, index, nav),
        ln.index_irr,
        ln.negative,
        plus,
        scale,
        mpme(times, amounts, index, navs) if navs is not None else None,
    )
