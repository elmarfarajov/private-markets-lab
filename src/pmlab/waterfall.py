"""Fees and distribution waterfalls: how a fund's gross proceeds are split between its investors and its manager.

A limited partnership agreement fixes three things, and this module implements each:

* **The management fee.** A share of commitments a year during the investment period, then a
  (usually lower) share of the cost of investments still held, drawn quarterly. Fees are paid out
  of investors' commitments, so a fund charging fees invests less than it raises.
* **The waterfall.** Each distribution passes through four tiers:
  1. *return of capital* - everything to the investors (LPs) until they have their contributions
     back, fees included;
  2. *preferred return* - everything to LPs until their contributions have earned the hurdle
     rate, compounded;
  3. *catch-up* - a share ``catch_up`` of distributions to the manager (GP) until the GP holds
     ``carry`` of all profit distributed so far;
  4. *carried interest* - ``carry`` to the GP, the rest to LPs.
  A **European** (whole-fund) waterfall runs the tiers on the fund's cumulative flows; an
  **American** (deal-by-deal) waterfall runs them on each deal's own capital and proceeds, so the
  GP is paid on winners before the losers are known.
* **The clawback.** At the end of the fund, the GP returns any carry above what the whole-fund
  terms entitle it to - ``carry`` of total profit, and no more than leaves LPs their hurdle - but
  only a share ``clawback_recovery`` of the excess is in practice recovered (carry already taxed,
  partners departed).

Everything is vectorised across simulated funds that share a timeline (same entry and exit
months, same fee schedule) and differ in their deals' multiples, so ten thousand funds run in
well under a second. Amounts are per 100 of commitment; times are on a monthly grid in years.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from .cashflows import CashFlows, irr, multiples

Array = NDArray[np.float64]
STEPS_PER_YEAR = 12


@dataclass(frozen=True)
class Terms:
    """The economic terms of a limited partnership agreement."""

    fee: float = 0.02  # a year, on commitments during the investment period
    post_fee: float | None = None  # a year after it, on the cost of unrealised deals (None: same as ``fee``)
    post_basis: str = "invested"  # "invested" (cost of deals still held) or "committed"
    carry: float = 0.20
    hurdle: float = 0.08  # preferred return, a year, compounded
    catch_up: float = 1.0  # share of distributions to the GP in the catch-up tier; at or below ``carry``: no catch-up
    waterfall: str = "european"  # or "american"
    clawback: bool = True
    clawback_recovery: float = 1.0  # share of an excess the GP actually returns

    def __post_init__(self) -> None:
        if self.waterfall not in ("european", "american"):
            raise ValueError("waterfall must be 'european' or 'american'")
        if self.post_basis not in ("invested", "committed"):
            raise ValueError("post_basis must be 'invested' or 'committed'")
        if not 0.0 <= self.carry < 1.0 or not 0.0 <= self.catch_up <= 1.0:
            raise ValueError("carry must lie in [0, 1) and catch_up in [0, 1]")

    @property
    def label(self) -> str:
        fee = f"{100 * self.fee:g}"
        if self.post_fee is not None and self.post_fee != self.fee:
            fee += f"/{100 * self.post_fee:g}"
        parts = [f"{fee} and {100 * self.carry:g}", f"{100 * self.hurdle:g}% hurdle" if self.hurdle > 0 else "no hurdle"]
        if self.hurdle > 0:
            parts.append(
                "full catch-up"
                if self.catch_up >= 1
                else ("no catch-up" if self.catch_up <= self.carry else f"{100 * self.catch_up:g}% catch-up")
            )
        parts.append(self.waterfall)
        return ", ".join(parts)


@dataclass(frozen=True)
class Shape:
    """The timeline every simulated fund shares: when each deal is bought and sold, and its share of invested capital."""

    entries: Array  # years, on the monthly grid
    exits: Array
    weights: Array  # share of invested capital, summing to one
    invest_years: float = 5.0
    commitment: float = 100.0

    @property
    def deals(self) -> int:
        return int(self.entries.size)

    @property
    def end(self) -> float:
        return float(np.max(self.exits))


def standard_shape(deals: int = 15, invest_years: float = 5.0, hold: tuple[float, float] = (3.0, 7.0), seed: int = 3) -> Shape:
    """Deals bought evenly over the investment period and held between ``hold`` years, on the monthly grid."""
    rng = np.random.default_rng(seed)
    entries = np.round(np.linspace(0.0, invest_years - 0.5, deals) * STEPS_PER_YEAR) / STEPS_PER_YEAR
    holds = np.round(rng.uniform(*hold, deals) * STEPS_PER_YEAR) / STEPS_PER_YEAR
    return Shape(entries, entries + holds, np.full(deals, 1.0 / deals), invest_years)


def single_deal_shape(years: float) -> Shape:
    """One deal bought at the start and sold after ``years``: the case with a closed-form carry value."""
    return Shape(np.array([0.0]), np.array([round(years * STEPS_PER_YEAR) / STEPS_PER_YEAR]), np.array([1.0]), invest_years=0.0)


@dataclass(frozen=True)
class Outcome:
    """The split of a set of simulated funds' cash flows. Rows are funds, columns the monthly grid."""

    terms: Terms
    times: Array
    contributions: Array  # LP calls on each date (positive), the same for every fund: deal costs plus fees
    fees: Array  # management fees on each date
    costs: Array  # deal costs on each date
    gross: Array  # (funds, dates) deal proceeds
    lp: Array  # (funds, dates) LP distributions, before the clawback
    carry: Array  # (funds, dates) carried interest paid
    clawback: Array  # (funds,) returned by the GP to LPs at the end
    entitlement: Array  # (funds,) carry the whole-fund terms allow

    # --------------------------------------------------------------- per-fund cash flows

    def lp_flows(self) -> Array:
        """LP net cash flows: distributions (and the clawback, at the end) minus calls."""
        flows = self.lp - self.contributions[None, :]
        flows[:, -1] += self.clawback
        return flows

    def gross_flows(self) -> Array:
        """The deals' own cash flows, before fees and carry: proceeds minus costs."""
        return self.gross - self.costs[None, :]

    def gp_flows(self) -> Array:
        flows = self.carry + self.fees[None, :]
        flows[:, -1] -= self.clawback
        return flows

    @property
    def carry_kept(self) -> Array:
        return self.carry.sum(axis=1) - self.clawback

    # --------------------------------------------------------------- summaries

    def gross_profit(self) -> Array:
        return np.asarray(self.gross.sum(axis=1) - self.costs.sum(), dtype=np.float64)

    def gp_share(self) -> Array:
        """The GP's take - fees plus carry kept - as a share of the deals' gross profit (NaN when there is none)."""
        profit = self.gross_profit()
        with np.errstate(divide="ignore", invalid="ignore"):
            share = (self.fees.sum() + self.carry_kept) / profit
        return np.asarray(np.where(np.abs(profit) < 1e-6, np.nan, share), dtype=np.float64)

    def tvpi(self) -> tuple[Array, Array]:
        """Gross TVPI (proceeds over deal costs) and net TVPI (LP distributions over LP calls)."""
        gross = self.gross.sum(axis=1) / self.costs.sum()
        net = (self.lp.sum(axis=1) + self.clawback) / self.contributions.sum()
        return gross, net

    def irrs(self, limit: int | None = None) -> tuple[Array, Array]:
        """Gross and net IRRs of each fund (the first ``limit`` funds): the root nearest zero, NaN where none exists."""
        n = self.gross.shape[0] if limit is None else min(limit, self.gross.shape[0])
        g, lpf = self.gross_flows(), self.lp_flows()
        out_g, out_n = np.full(n, np.nan), np.full(n, np.nan)
        for i in range(n):
            out_g[i] = _safe_irr(self.times, g[i])
            out_n[i] = _safe_irr(self.times, lpf[i])
        return out_g, out_n

    def table(self, limit: int | None = None) -> pd.DataFrame:
        gi, ni = self.irrs(limit)
        n = gi.size
        gt, nt = self.tvpi()
        return pd.DataFrame(
            {
                "gross_irr": gi,
                "net_irr": ni,
                "gross_tvpi": gt[:n],
                "net_tvpi": nt[:n],
                "fees": np.full(n, self.fees.sum()),
                "carry": self.carry.sum(axis=1)[:n],
                "clawback": self.clawback[:n],
                "gp_share": self.gp_share()[:n],
            }
        )


def _safe_irr(times: Array, amounts: Array) -> float:
    if not (np.any(amounts > 0) and np.any(amounts < 0)):
        return float("nan")
    try:
        return irr(times, amounts)
    except ValueError:
        return float("nan")


# ------------------------------------------------------------------- the fee schedule


@dataclass(frozen=True)
class Schedule:
    times: Array
    costs: Array  # deal costs on each date
    fees: Array
    scale: float  # share of commitment that reaches the deals


def schedule(shape: Shape, terms: Terms) -> Schedule:
    """Calls for deals and fees on the monthly grid, with the deals scaled so that calls add up to the commitment.

    Fees on the cost of unrealised deals are proportional to how much is invested, so the invested
    share ``s`` solves ``s * sum(cost) + a + s * b = commitment``, where ``a`` is the fee on
    commitments and ``b`` the fee per unit of invested cost: a linear equation, solved exactly.
    """
    n = int(round(shape.end * STEPS_PER_YEAR)) + 1
    times = np.arange(n) / STEPS_PER_YEAR
    k_entry = np.rint(shape.entries * STEPS_PER_YEAR).astype(int)
    k_exit = np.rint(shape.exits * STEPS_PER_YEAR).astype(int)
    raw_cost = np.zeros(n)
    np.add.at(raw_cost, k_entry, shape.weights * shape.commitment)
    # unrealised cost after each date's deals, per unit of invested scale
    held = np.zeros(n)
    for ke, kx, w in zip(k_entry, k_exit, shape.weights, strict=True):
        held[ke:kx] += w * shape.commitment
    post = terms.fee if terms.post_fee is None else terms.post_fee
    quarter = np.arange(0, n - 1, 3)  # fees quarterly in advance while the fund is alive
    fixed = np.zeros(n)
    per_cost = np.zeros(n)
    for k in quarter:
        if times[k] < shape.invest_years - 1e-9:
            fixed[k] = terms.fee * shape.commitment / 4.0
        elif terms.post_basis == "committed":
            fixed[k] = post * shape.commitment / 4.0
        else:
            per_cost[k] = post * held[k] / 4.0
    s = (shape.commitment - fixed.sum()) / (raw_cost.sum() + per_cost.sum())
    if s <= 0:
        raise ValueError("fees exceed the commitment")
    return Schedule(times, s * raw_cost, fixed + s * per_cost, float(s))


# ------------------------------------------------------------------- the waterfalls


def run(shape: Shape, multiples_: ArrayLike, terms: Terms) -> Outcome:
    """Split the proceeds of funds whose deals earn ``multiples_`` (funds x deals, proceeds over cost) under ``terms``."""
    m = np.atleast_2d(np.asarray(multiples_, dtype=np.float64))
    if m.shape[1] != shape.deals:
        raise ValueError(f"multiples need {shape.deals} columns, one per deal")
    sch = schedule(shape, terms)
    n_funds, n_dates = m.shape[0], sch.times.size
    k_entry = np.rint(shape.entries * STEPS_PER_YEAR).astype(int)
    k_exit = np.rint(shape.exits * STEPS_PER_YEAR).astype(int)
    deal_cost = sch.scale * shape.weights * shape.commitment
    gross = np.zeros((n_funds, n_dates))
    for j in range(shape.deals):
        gross[:, k_exit[j]] += deal_cost[j] * m[:, j]
    contributions = sch.costs + sch.fees
    if terms.waterfall == "european":
        lp, carry = _european(gross, contributions, terms)
    else:
        lp, carry = _american(m, deal_cost, sch, k_entry, k_exit, terms, n_dates)
    entitlement = _entitlement(sch.times, gross, contributions, lp, carry, terms)
    paid = carry.sum(axis=1)
    claw = np.maximum(paid - entitlement, 0.0) * terms.clawback_recovery if terms.clawback else np.zeros(n_funds)
    return Outcome(terms, sch.times, contributions, sch.fees, sch.costs, gross, lp, carry, claw, entitlement)


def _split(d: Array, lp_cum: Array, gp_cum: Array, k_cum: Array, terms: Terms) -> tuple[Array, Array]:
    """The catch-up and carry tiers for distributions ``d`` that have already cleared the hurdle."""
    c, cu = terms.carry, terms.catch_up
    gp = np.zeros_like(d)
    rest = d.copy()
    if cu > c and c > 0:
        # x distributed in the catch-up tier brings the GP to c of profit: c (L + G - K + x) = G + cu x
        x = (c * (lp_cum + gp_cum - k_cum) - gp_cum) / (cu - c)
        x = np.clip(x, 0.0, rest)
        gp += cu * x
        rest -= x
    gp += c * rest
    return d - gp, gp


def _european(gross: Array, contributions: Array, terms: Terms) -> tuple[Array, Array]:
    n_funds, n_dates = gross.shape
    growth = (1.0 + terms.hurdle) ** (1.0 / STEPS_PER_YEAR)
    hurdle_balance = np.zeros(n_funds)  # contributions grown at the hurdle, less LP distributions grown likewise
    lp_cum = np.zeros(n_funds)
    gp_cum = np.zeros(n_funds)
    k_cum = 0.0
    lp = np.zeros_like(gross)
    carry = np.zeros_like(gross)
    for k in range(n_dates):
        if k:
            hurdle_balance *= growth
        k_cum += contributions[k]
        hurdle_balance += contributions[k]
        d = gross[:, k].copy()
        first = np.minimum(d, np.maximum(hurdle_balance, 0.0))  # return of capital and preferred return
        hurdle_balance -= first
        lp_cum += first
        d -= first
        to_lp, to_gp = _split(d, lp_cum, gp_cum, np.full(n_funds, k_cum), terms)
        lp[:, k] = first + to_lp
        carry[:, k] = to_gp
        lp_cum += to_lp
        gp_cum += to_gp
    return lp, carry


def _american(
    m: Array, deal_cost: Array, sch: Schedule, k_entry: Array, k_exit: Array, terms: Terms, n_dates: int
) -> tuple[Array, Array]:
    """Deal by deal: each deal's capital is its cost plus its share of all fees, earning the hurdle from entry to exit."""
    n_funds = m.shape[0]
    lp = np.zeros((n_funds, n_dates))
    carry = np.zeros((n_funds, n_dates))
    fee_share = sch.fees.sum() * deal_cost / deal_cost.sum()
    for j in range(deal_cost.size):
        capital = deal_cost[j] + fee_share[j]
        months = int(k_exit[j] - k_entry[j])
        required = capital * (1.0 + terms.hurdle) ** (months / STEPS_PER_YEAR)
        d = deal_cost[j] * m[:, j]
        first = np.minimum(d, required)
        rest = d - first
        to_lp, to_gp = _split(rest, first, np.zeros(n_funds), np.full(n_funds, capital), terms)
        lp[:, k_exit[j]] += first + to_lp
        carry[:, k_exit[j]] += to_gp
    return lp, carry


def _entitlement(times: Array, gross: Array, contributions: Array, lp: Array, carry: Array, terms: Terms) -> Array:
    """Carry the whole-fund terms allow: ``carry`` of total profit, and no more than leaves LPs their hurdle.

    LPs have earned the hurdle when their flows' value at the hurdle rate is not negative. Returning
    ``e`` of carry at the end changes that value by ``e`` discounted from the end, so the largest
    carry consistent with the hurdle is the carry paid plus the LP surplus, compounded to the end.
    """
    profit = gross.sum(axis=1) - contributions.sum()
    by_share = terms.carry * np.maximum(profit, 0.0)
    disc = (1.0 + terms.hurdle) ** (-times)
    lp_value = (lp - contributions[None, :]) @ disc
    paid = carry.sum(axis=1)
    by_hurdle = paid + lp_value / disc[-1]
    return np.asarray(np.maximum(np.minimum(by_share, by_hurdle), 0.0), dtype=np.float64)


# ------------------------------------------------------------------- deterministic funds and simulated deals


def flat_multiples(shape: Shape, gross_irr: float, funds: int = 1) -> Array:
    """Every deal earns exactly ``gross_irr`` a year: a fund whose gross IRR is known."""
    years = shape.exits - shape.entries
    return np.asarray(np.tile((1.0 + gross_irr) ** years, (funds, 1)), dtype=np.float64)


@dataclass(frozen=True)
class DealModel:
    """Lognormal deal multiples with a common factor: ``ln M = (mu - s^2/2) t + s (sqrt(rho) Z + sqrt(1 - rho) e) sqrt(t)``."""

    mu: float = 0.15  # expected gross return a year, continuously compounded
    sigma: float = 0.40  # a deal's volatility a year
    rho: float = 0.30  # correlation between any two deals
    seed: int = 11
    common: bool = field(default=True)  # one factor draw per fund (True) or none

    def draw(self, shape: Shape, funds: int) -> Array:
        rng = np.random.default_rng(self.seed)
        t = shape.exits - shape.entries
        z = rng.standard_normal((funds, 1)) if self.common else np.zeros((funds, 1))
        e = rng.standard_normal((funds, shape.deals))
        shock = np.sqrt(self.rho) * z + np.sqrt(1.0 - self.rho) * e
        return np.asarray(np.exp((self.mu - 0.5 * self.sigma**2) * t + self.sigma * np.sqrt(t) * shock), dtype=np.float64)

    def risk_neutral(self, r: float) -> DealModel:
        return replace(self, mu=r)


def gross_to_net(shape: Shape, terms: Terms, gross_irrs: ArrayLike) -> pd.DataFrame:
    """Net IRR, net TVPI and the GP's share of profit for funds whose every deal earns each gross IRR."""
    rows = []
    for g in np.atleast_1d(np.asarray(gross_irrs, dtype=np.float64)):
        out = run(shape, flat_multiples(shape, float(g)), terms)
        gi, ni = out.irrs()
        gt, nt = out.tvpi()
        rows.append(
            {
                "gross_irr": float(gi[0]),
                "net_irr": float(ni[0]),
                "gross_tvpi": float(gt[0]),
                "net_tvpi": float(nt[0]),
                "fees": float(out.fees.sum()),
                "carry": float(out.carry_kept[0]),
                "gp_share": float(out.gp_share()[0]),
            }
        )
    return pd.DataFrame(rows)


def check_conservation(out: Outcome) -> float:
    """Largest gap, over funds, between the deals' cash flows and the sum of LP and GP flows (zero up to rounding)."""
    total = out.lp_flows() + out.gp_flows()
    return float(np.max(np.abs(total.sum(axis=1) - out.gross_flows().sum(axis=1))))


def lp_cashflows(out: Outcome, fund: int = 0) -> CashFlows:
    return CashFlows(out.times, out.lp_flows()[fund])


def net_multiples(out: Outcome, fund: int = 0) -> float:
    return multiples(lp_cashflows(out, fund)).tvpi
