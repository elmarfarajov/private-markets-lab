"""A stylised buyout fund built deal by deal, with a known alpha and beta to any index path.

Fund-level cash flows are not public, so the measures of this lab are tested on funds whose
truth is known. The fund here is deliberately simple - Day 3 replaces it with calibrated
cash-flow models - but it has the shape that matters:

* the fund draws its commitment into ``deals`` investments spread over an investment
  period, and returns each at exit, three to seven years later;
* a deal bought at ``t_e`` for cost ``K`` is worth
  ``K (I_t / I_e)^beta exp(alpha (t - t_e) + idio W_{t - t_e})``: its index exposure is
  ``beta``, its outperformance ``alpha`` a year, continuously compounded, and its own risk
  ``idio``;
* an optional management fee, a share of commitment a year, is drawn every third month while the
  fund is alive, and the deals are bought with what is left of the commitment.

With ``beta = 1``, no idiosyncratic risk and no fee, every deal earns exactly the index
times ``exp(alpha t)``, and Direct Alpha must return ``alpha``: that is a test, not a hope.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.typing import NDArray

Array = NDArray[np.float64]
SLACK = 1.0 / 24.0  # half a month: month-end dates measured in days/365 do not land on whole years


@dataclass(frozen=True)
class Market:
    """An index path on a monthly grid: years from the start, and levels."""

    times: Array
    levels: Array

    def level(self, t: Array | float) -> Array:
        return np.asarray(np.interp(t, self.times, self.levels), dtype=np.float64)

    def window(self, start: float, years: float) -> Market:
        """The path from ``start`` for ``years``, re-based to time zero."""
        keep = (self.times >= start - SLACK) & (self.times <= start + years + SLACK)
        return Market(self.times[keep] - self.times[keep][0], self.levels[keep])


def gbm_market(years: float = 15.0, mu: float = 0.07, sigma: float = 0.16, per_year: int = 12, seed: int = 1) -> Market:
    """A log-normal index with drift ``mu`` and volatility ``sigma``, monthly."""
    rng = np.random.default_rng(seed)
    n = int(round(years * per_year))
    dt = 1.0 / per_year
    steps = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n)
    levels = 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(steps)]))
    return Market(np.arange(n + 1, dtype=np.float64) * dt, np.asarray(levels, dtype=np.float64))


def market_from_series(series: pd.Series) -> Market:
    """A monthly index from a dated price series (month-end closes)."""
    monthly = series.resample("ME").last().dropna()
    t = (monthly.index - monthly.index[0]).days.to_numpy() / 365.0
    return Market(np.asarray(t, dtype=np.float64), monthly.to_numpy(dtype=np.float64))


@dataclass(frozen=True)
class FundSpec:
    commitment: float = 100.0
    deals: int = 15
    invest_years: float = 5.0
    hold: tuple[float, float] = (3.0, 7.0)  # years from entry to exit, uniform
    life: float = 12.0
    alpha: float = 0.0  # a year, continuously compounded
    beta: float = 1.0
    idio: float = 0.0  # annual volatility of each deal's own risk
    fee: float = 0.0  # share of commitment a year, drawn quarterly over the life
    seed: int = 7


@dataclass(frozen=True)
class Fund:
    times: Array  # monthly grid, years from the first call
    amounts: Array  # investor's side: calls negative, distributions positive
    navs: Array  # value of unexited deals after each date's flows
    index: Array  # index level at each date
    deals: pd.DataFrame = field(repr=False)  # entry, exit, cost, proceeds

    def until(self, horizon: float) -> tuple[Array, Array, float, Array, Array]:
        """The fund as reported at ``horizon``: flows to date, the NAV then, and index levels and NAVs to date."""
        keep = self.times <= horizon + 1e-9
        return self.times[keep], self.amounts[keep], float(self.navs[keep][-1]), self.index[keep], self.navs[keep]


def simulate_fund(market: Market, spec: FundSpec | None = None) -> Fund:
    """One fund on ``market``'s path; the market must cover the fund's life."""
    spec = spec or FundSpec()
    if market.times[-1] < spec.life - SLACK:
        raise ValueError(f"the market path covers {market.times[-1]:.1f} years; the fund needs {spec.life}")
    rng = np.random.default_rng(spec.seed)
    grid = market.times[market.times <= spec.life + SLACK]
    step = float(grid[1] - grid[0])

    def snap(t: float) -> float:
        return float(grid[min(int(round(t / step)), grid.size - 1)])

    entries = np.sort(rng.uniform(0.0, spec.invest_years, spec.deals))
    entries[0] = 0.0  # the first call opens the fund
    holds = rng.uniform(*spec.hold, spec.deals)
    end = max(snap(min(e + h, spec.life)) for e, h in zip(entries, holds, strict=True))
    # fees every third month of the grid while the fund is alive; the deals get what is left of the commitment
    per_quarter = max(int(round(0.25 / step)), 1)
    fee_dates = np.arange(0, grid.size, per_quarter)
    fee_dates = fee_dates[grid[fee_dates] < end - 1e-9] if spec.fee > 0 else fee_dates[:0]
    quarterly_fee = spec.fee * spec.commitment / 4.0
    invested = spec.commitment - quarterly_fee * fee_dates.size
    if invested <= 0:
        raise ValueError("fees exceed the commitment")
    cost = invested / spec.deals
    amounts = np.zeros_like(grid)
    navs = np.zeros_like(grid)
    rows = []
    for e, h in zip(entries, holds, strict=True):
        te = snap(e)
        tx = snap(min(e + h, spec.life))
        live = (grid >= te) & (grid <= tx)
        ie = float(market.level(te))
        shocks = rng.standard_normal(int(live.sum())) * spec.idio * np.sqrt(step)
        shocks[0] = 0.0
        w = np.cumsum(shocks) - 0.5 * spec.idio**2 * (grid[live] - te)  # the deal's own risk adds no drift
        value = cost * (market.level(grid[live]) / ie) ** spec.beta * np.exp(spec.alpha * (grid[live] - te) + w)
        k_entry = int(np.argmin(np.abs(grid - te)))
        k_exit = int(np.argmin(np.abs(grid - tx)))
        amounts[k_entry] -= cost
        amounts[k_exit] += float(value[-1])
        held = live & (grid < tx)
        navs[held] += value[: int(held.sum())]
        rows.append({"entry": te, "exit": tx, "cost": cost, "proceeds": float(value[-1])})
    amounts[fee_dates] -= quarterly_fee
    used = grid <= end + 1e-9
    return Fund(grid[used], amounts[used], navs[used], market.level(grid[used]), pd.DataFrame(rows))
