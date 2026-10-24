"""Pricing an LP interest on the secondary market: what a buyer pays, and why it is usually less than NAV.

A buyer of an LP interest at fund age ``tau`` pays a price ``P`` today and steps into the seller's
position: it receives all future distributions and must meet all future capital calls on the
unfunded commitment. Its value of the interest is the present value of those flows at its own
required return ``r``:

    ``V(r) = sum_k (D_k - C_k) exp(-r t_k)``,

and the **discount to NAV** it can pay is ``1 - V(r) / NAV_reported``. Three things open that
discount:

* **a required return above the fund's expected return.** If ``r = mu`` and the reported NAV is the
  true value, the interest is worth exactly its NAV: existing assets are worth what they are
  expected to return, and every future call is invested at a fair price. Above ``mu``, both the
  existing assets and the unfunded calls are worth less;
* **the unfunded commitment.** Each pound still to be called is a pound invested at ``mu`` and
  valued at ``r``: a liability when ``r > mu``, larger for young funds;
* **a stale NAV.** Appraisals lag the true value (``pmlab.fundmodel``). After a market fall the
  reported NAV overstates the assets, and a buyer pricing the true value quotes a deep discount
  to a number that has not yet caught up.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from .cashflows import irr
from .fundmodel import StochasticSpec, expected_path, simulate

Array = NDArray[np.float64]


@dataclass(frozen=True)
class State:
    """A fund at age ``age`` (years): true value, reported NAV, and commitment still uncalled."""

    age: float
    value: float
    reported: float
    uncalled: float


def expected_state(spec: StochasticSpec, age: float) -> State:
    """The fund's expected state at ``age``, following the noise-free recursion from inception."""
    times, calls, dist = expected_path(spec, 0.0, spec.ta.commitment, 0.0)
    k = int(round(age * spec.steps_per_year))
    g = float(np.exp(spec.mu / spec.steps_per_year))
    v = 0.0
    for c, d in zip(calls[:k], dist[:k], strict=True):
        v = v * g + c - d
    return State(age, v, v, spec.ta.commitment - float(calls[:k].sum()))


def value(spec: StochasticSpec, state: State, required: float) -> float:
    """Present value at ``required`` (a year, continuous) of the expected future flows of an interest in ``state``."""
    t, c, d = expected_path(spec, state.value, state.uncalled, state.age)
    return float(((d - c) * np.exp(-required * t)).sum())


def discount(spec: StochasticSpec, state: State, required: float) -> float:
    """The discount to reported NAV at which the buyer earns exactly ``required``."""
    return 1.0 - value(spec, state, required) / state.reported


@dataclass(frozen=True)
class Decomposition:
    """Where a discount comes from, each piece in units of reported NAV."""

    total: float
    assets: float  # pricing the existing assets at r rather than mu
    unfunded: float  # the value lost on future calls invested at mu, priced at r
    staleness: float  # reported NAV above (or below) the true value


def decompose(spec: StochasticSpec, state: State, required: float) -> Decomposition:
    """Split the discount: existing assets only, then the unfunded commitment, then a stale NAV."""
    assets_only = value(spec, State(state.age, state.value, state.value, 0.0), required)
    with_unfunded = value(spec, state, required)
    assets = 1.0 - assets_only / state.value if state.value > 0 else 0.0
    unfunded = (assets_only - with_unfunded) / state.value if state.value > 0 else 0.0
    total = 1.0 - with_unfunded / state.reported
    staleness = total - (1.0 - with_unfunded / state.value) if state.value > 0 else 0.0
    return Decomposition(total, assets, unfunded, staleness)


def discount_grid(spec: StochasticSpec, ages: Sequence[float], required: Sequence[float]) -> pd.DataFrame:
    rows = []
    for a in ages:
        s = expected_state(spec, a)
        for r in required:
            rows.append(
                {"age": a, "required": r, "discount": discount(spec, s, r), "unfunded_share": s.uncalled / (s.uncalled + s.value)}
            )
    return pd.DataFrame(rows)


def crash(spec: StochasticSpec, age: float, shock: float, required: float, quarters: int = 12) -> pd.DataFrame:
    """A market fall at ``age``: the true value drops by ``shock``; the appraisal catches up at the smoothing rate.

    After the fall the true value follows its expected path. Each quarter the reported NAV moves a
    share ``a`` of the way to the true value (adjusted for the quarter's flows), and the buyer's
    price - set on the true value - is expressed as a discount to the reported NAV.
    """
    s = expected_state(spec, age)
    v = s.value * (1.0 - shock)
    r = s.reported
    u = s.uncalled
    dt = 1.0 / spec.steps_per_year
    a = spec.smoothing
    t, c, d = expected_path(spec, v, u, age)
    rows = []
    for q in range(quarters + 1):
        st = State(age + q * dt, v, r, u)
        rows.append(
            {
                "quarter": q,
                "true": v,
                "reported": r,
                "discount_to_reported": discount(spec, st, required),
                "discount_to_true": 1.0 - value(spec, st, required) / v,
            }
        )
        if q < len(c):
            v = v * np.exp(spec.mu * dt) + c[q] - d[q]
            r = a * v + (1.0 - a) * (r + c[q] - d[q])
            u = u - c[q]
    return pd.DataFrame(rows).set_index("quarter")


def buyer_irrs(spec: StochasticSpec, state: State, price_to_nav: float, funds: int = 4000, seed: int = 0) -> Array:
    """The buyer's IRR on each simulated future, paying ``price_to_nav`` x reported NAV at the start."""
    paths = simulate(spec, funds, seed, start=state.age, value=state.value, reported=state.reported, uncalled=state.uncalled)
    price = price_to_nav * state.reported
    t = np.concatenate([[0.0], paths.times])
    out = np.full(funds, np.nan)
    for i in range(funds):
        flows = np.concatenate([[-price], paths.net[i]])
        try:
            out[i] = irr(t, flows)
        except ValueError:
            pass
    return out


def monte_carlo_value(
    spec: StochasticSpec, state: State, required: float, funds: int = 20000, seed: int = 0
) -> tuple[float, float]:
    """Monte Carlo value and standard error of the interest at ``required``: the check on the expected-path shortcut."""
    paths = simulate(spec, funds, seed, start=state.age, value=state.value, reported=state.reported, uncalled=state.uncalled)
    pv = paths.net @ np.exp(-required * paths.times)
    return float(pv.mean()), float(pv.std(ddof=1) / np.sqrt(funds))
