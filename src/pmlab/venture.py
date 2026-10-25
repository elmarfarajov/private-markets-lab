"""Venture capital securities as options: the exit waterfall, fair values, and why post-money valuations overstate.

A venture-backed company issues a new class of convertible preferred stock in each round. Each
class has a liquidation preference (a multiple of what it paid, plus any cumulative dividend), a
seniority rank, and the right to convert into common shares. Some participate: they take their
preference *and* share in what is left, up to a cap. At an exit worth ``V`` every class receives
what the waterfall gives it, and each preferred class converts only if converting pays more.

The headline "post-money valuation" multiplies the price of the latest round by all fully diluted
shares, as if every share were worth what the newest, most senior investors paid. They are not:
the newest shares carry the most protection. Gornall and Strebulaev (2020) value every class with an
option-pricing model and find reported valuations of US unicorns well above fair value. This module
reproduces that machinery:

* :func:`payoff` - the waterfall at one exit value, with conversion decided as an equilibrium in
  which no class wants to change its choice;
* :class:`Payoffs` - every class's value under a lognormal exit value (the option-pricing method,
  OPM), computed exactly by integrating the piecewise-linear payoff against the lognormal density;
* :func:`backsolve` - the company value at which the latest round's price is fair, which gives the
  fair value of the company and of its common stock.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import numpy as np
from numpy.typing import NDArray
from scipy import optimize
from scipy.stats import norm

Array = NDArray[np.float64]


@dataclass(frozen=True)
class Security:
    """One class of shares. Common stock has ``price = 0`` and no preference."""

    name: str
    shares: float  # millions of shares, as converted
    price: float = 0.0  # original issue price per share
    multiple: float = 1.0  # liquidation preference as a multiple of what was paid
    seniority: int = 0  # higher is paid first; equal ranks share pro rata
    participating: bool = False
    cap: float | None = None  # participating cap, as a multiple of what was paid (None: uncapped)
    dividend: float = 0.0  # cumulative dividend, a year, added to the preference
    conversion: float = 1.0  # common shares per preferred share

    @property
    def preferred(self) -> bool:
        return self.price > 0

    @property
    def invested(self) -> float:
        return self.shares * self.price

    def preference(self, years: float = 0.0) -> float:
        return self.invested * (self.multiple + self.dividend * years) if self.preferred else 0.0


@dataclass(frozen=True)
class CapTable:
    securities: tuple[Security, ...]
    years: float = 0.0  # time to exit, for cumulative dividends in the waterfall

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.securities]

    @property
    def fully_diluted(self) -> float:
        return float(sum(s.shares * s.conversion for s in self.securities))

    @property
    def latest(self) -> Security:
        """The most recent round: the preferred class with the highest issue price (ties: the last listed)."""
        pref = [s for s in self.securities if s.preferred]
        return max(reversed(pref), key=lambda s: s.price)

    def post_money(self) -> float:
        """The headline valuation: the latest round's price times every fully diluted share."""
        return self.latest.price / self.latest.conversion * self.fully_diluted

    def with_terms(self, name: str, **changes: object) -> CapTable:
        return replace(self, securities=tuple(replace(s, **changes) if s.name == name else s for s in self.securities))  # type: ignore[arg-type]


# ------------------------------------------------------------------ the waterfall


def _distribute(table: CapTable, value: float, convert: Sequence[bool]) -> Array:
    """Payouts to each class at exit ``value`` for a given set of conversion choices."""
    secs = table.securities
    n = len(secs)
    pay = np.zeros(n)
    left = value
    # 1. preferences of the classes that do not convert, by seniority, pro rata within a rank
    holders = [i for i in range(n) if secs[i].preferred and not convert[i]]
    for rank in sorted({secs[i].seniority for i in holders}, reverse=True):
        group = [i for i in holders if secs[i].seniority == rank]
        owed = np.array([secs[i].preference(table.years) for i in group])
        paid = owed if owed.sum() <= left else owed * (left / owed.sum())
        for i, p in zip(group, paid, strict=True):
            pay[i] += p
        left -= float(paid.sum())
        if left <= 0:
            return pay
    # 2. the residual to common, converted preferred and participating preferred, as converted;
    #    capped participants are fixed at their cap and the rest share again
    pool = [i for i in range(n) if not secs[i].preferred or convert[i] or secs[i].participating]
    fixed: set[int] = set()
    while True:
        active = [i for i in pool if i not in fixed]
        sh = np.array([secs[i].shares * secs[i].conversion for i in active])
        total_fixed = sum(pay_fixed for pay_fixed in (_cap_room(secs[i], pay[i]) for i in fixed))
        rest = max(left - total_fixed, 0.0)
        per = rest / sh.sum() if sh.sum() > 0 else 0.0
        newly = [
            i
            for i, s in zip(active, sh, strict=True)
            if secs[i].preferred
            and not convert[i]
            and secs[i].participating
            and secs[i].cap is not None
            and pay[i] + per * s > (secs[i].cap or np.inf) * secs[i].invested + 1e-12
        ]
        if not newly:
            break
        fixed.update(newly)
    for i in fixed:
        pay[i] += _cap_room(secs[i], pay[i])
    for i, s in zip(active, sh, strict=True):
        pay[i] += per * s
    return pay


def _cap_room(s: Security, already: float) -> float:
    return max((s.cap or np.inf) * s.invested - already, 0.0)


def payoff(table: CapTable, value: float, max_rounds: int = 50) -> tuple[Array, list[bool]]:
    """Payout to each class at exit ``value``, with each preferred class converting only if that pays more.

    Conversion is found by best response: starting from nobody converting, each class in turn
    switches if switching raises its own payout, until no class wants to change. Converting gives up
    the preference for an as-converted share of the residual, so the classes with the lowest
    preference per share convert first as the exit value rises.
    """
    n = len(table.securities)
    convert = [False] * n
    for _ in range(max_rounds):
        changed = False
        for i, s in enumerate(table.securities):
            if not s.preferred:
                continue
            here = _distribute(table, value, convert)[i]
            flipped = list(convert)
            flipped[i] = not flipped[i]
            there = _distribute(table, value, flipped)[i]
            if there > here + 1e-9 * max(1.0, abs(here)):
                convert = flipped
                changed = True
        if not changed:
            break
    return _distribute(table, value, convert), convert


# ------------------------------------------------------------------ the option-pricing method


def _grid(table: CapTable, top: float | None = None, points: int = 1500) -> Array:
    pref = sum(s.preference(table.years) for s in table.securities)
    hi = top or max(50.0 * pref, 50.0 * table.post_money(), 1.0)
    lo = max(pref, 1e-6) * 1e-4
    return np.concatenate([[0.0], np.geomspace(lo, hi, points)])


@dataclass(frozen=True)
class Payoffs:
    """Payouts of every class on a grid of exit values; between grid points the payoff is taken as linear."""

    table: CapTable
    values: Array  # exit values, increasing
    pay: Array  # (len(values), classes)
    converts: Array = field(repr=False)  # (len(values), classes) bool

    @classmethod
    def build(cls, table: CapTable, points: int = 1500) -> Payoffs:
        v = _grid(table, points=points)
        out = np.zeros((v.size, len(table.securities)))
        conv = np.zeros_like(out, dtype=bool)
        for k, x in enumerate(v):
            p, c = payoff(table, float(x))
            out[k] = p
            conv[k] = c
        return cls(table, v, out, conv)

    def value(self, v0: float, sigma: float, years: float, r: float) -> Array:
        """Present value of each class: E^Q[payoff(V_T)] e^{-rT}, V_T lognormal with forward v0 e^{rT}.

        Exact for the linear interpolation of the payoff: on each interval [a, b] the payoff is
        ``alpha + beta V`` and E[(alpha + beta V) 1{a < V < b}] uses P(V > K) = N(d2) and
        E[V 1{V > K}] = F N(d1). Beyond the last grid point the last slope continues.
        """
        f = v0 * np.exp(r * years)
        s = sigma * np.sqrt(years)
        v = self.values
        with np.errstate(divide="ignore"):
            d1 = np.where(v > 0, (np.log(f / np.where(v > 0, v, 1.0)) + 0.5 * s * s) / s, np.inf)
        d2 = d1 - s
        prob = norm.cdf(d2)  # P(V_T > v_k)
        part = f * norm.cdf(d1)  # E[V_T 1{V_T > v_k}]
        dv = np.diff(v)[:, None]
        beta = np.diff(self.pay, axis=0) / dv
        alpha = self.pay[:-1] - beta * v[:-1, None]
        pr = (prob[:-1] - prob[1:])[:, None]
        pt = (part[:-1] - part[1:])[:, None]
        body = (alpha * pr + beta * pt).sum(axis=0)
        a_t = self.pay[-1] - beta[-1] * v[-1]
        tail = a_t * prob[-1] + beta[-1] * part[-1]
        return np.asarray((body + tail) * np.exp(-r * years), dtype=np.float64)

    def breakpoints(self) -> Array:
        """Exit values where any class's slope changes (to grid precision)."""
        slope = np.diff(self.pay, axis=0) / np.diff(self.values)[:, None]
        jump = np.abs(np.diff(slope, axis=0)).max(axis=1) > 1e-6
        return self.values[1:-1][jump]


@dataclass(frozen=True)
class Fair:
    """The outcome of backsolving a round."""

    company: float  # fair value of the company's equity today
    post_money: float
    values: Array  # value of each class
    per_share: Array  # value per as-converted share of each class

    @property
    def overvaluation(self) -> float:
        """How much the post-money valuation exceeds fair value, as a share of fair value."""
        return self.post_money / self.company - 1.0


def backsolve(table: CapTable, sigma: float = 0.9, years: float = 4.0, r: float = 0.04, payoffs: Payoffs | None = None) -> Fair:
    """Find the company value at which the latest round's shares are worth exactly what was paid."""
    p = payoffs or Payoffs.build(replace(table, years=years))
    k = table.names.index(table.latest.name)
    target = table.latest.invested

    def gap(v0: float) -> float:
        return float(p.value(v0, sigma, years, r)[k] - target)

    hi = table.post_money()
    while gap(hi) < 0:
        hi *= 2.0
    v0 = float(optimize.brentq(gap, 1e-9 * hi, hi, xtol=1e-10 * hi, rtol=1e-12))
    vals = p.value(v0, sigma, years, r)
    shares = np.array([s.shares * s.conversion for s in table.securities])
    return Fair(v0, table.post_money(), vals, vals / shares)


def monte_carlo(
    table: CapTable, v0: float, sigma: float, years: float, r: float, paths: int = 20000, seed: int = 0
) -> tuple[Array, Array]:
    """Monte Carlo value of each class with its standard error (exit value as control variate): the check on the OPM integral."""
    rng = np.random.default_rng(seed)
    vt = v0 * np.exp((r - 0.5 * sigma**2) * years + sigma * np.sqrt(years) * rng.standard_normal(paths))
    t = replace(table, years=years)
    pay = np.array([payoff(t, float(x))[0] for x in vt]) * np.exp(-r * years)
    # control variate: the discounted exit value, whose mean v0 is known; each class's payoff
    # moves with it, so regressing it out removes most of the sampling noise of a skewed lognormal
    x = vt * np.exp(-r * years) - v0
    beta = (pay - pay.mean(axis=0)).T @ x / (x @ x)
    adj = pay - np.outer(x, beta)
    return adj.mean(axis=0), adj.std(axis=0, ddof=1) / np.sqrt(paths)


# ------------------------------------------------------------------ examples


def example(terms: dict[str, dict[str, object]] | None = None) -> CapTable:
    """A stylised late-stage company: founders and an option pool, and four rounds at rising prices.

    Shares in millions; prices in dollars. Post-money after Series D: $30.00 x 100m = $3.0bn.
    """
    secs = (
        Security("Common", 40.0),
        Security("Options", 10.0),
        Security("Series A", 15.0, 0.50, seniority=1),
        Security("Series B", 15.0, 2.00, seniority=2),
        Security("Series C", 12.0, 8.00, seniority=3),
        Security("Series D", 8.0, 30.00, seniority=4),
    )
    t = CapTable(secs)
    if terms:
        for name, change in terms.items():
            t = t.with_terms(name, **change)
    return t


def random_company(rng: np.random.Generator) -> CapTable:
    """A stylised venture-backed company with three to six rounds and terms drawn at rates of the order Gornall and
    Strebulaev (2020) report: senior latest rounds common, participation, multiples above one and cumulative
    dividends occasional. The rates are illustrative, not estimates."""
    rounds = int(rng.integers(3, 7))
    common = float(rng.uniform(30, 60))
    pool = float(rng.uniform(5, 15))
    secs = [Security("Common", common), Security("Options", pool)]
    price = float(rng.uniform(0.3, 1.0))
    senior_stack = rng.random() < 0.7  # each round senior to the last, or all pari passu
    for k in range(rounds):
        shares = float(rng.uniform(8, 20))
        participating = bool(rng.random() < 0.15)
        multiple = float(rng.choice([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.25, 1.5, 2.0]))
        dividend = 0.08 if rng.random() < 0.08 else 0.0
        secs.append(
            Security(
                f"Series {'ABCDEF'[k]}",
                shares,
                price,
                multiple=multiple,
                seniority=k + 1 if senior_stack else 1,
                participating=participating,
                cap=3.0 if participating and rng.random() < 0.5 else None,
                dividend=dividend,
            )
        )
        price *= float(rng.uniform(1.6, 3.5))
    return CapTable(tuple(secs))


def overvaluation_sample(
    n: int = 200, sigma: float = 0.9, years: float = 4.0, r: float = 0.04, seed: int = 0
) -> list[dict[str, float]]:
    """Fair value against post-money for ``n`` random companies."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        t = random_company(rng)
        f = backsolve(t, sigma, years, r, Payoffs.build(replace(t, years=years), points=500))
        common = f.per_share[0]
        latest = t.latest.price / t.latest.conversion
        lt = t.latest
        rows.append(
            {
                "overvaluation": f.overvaluation,
                "common_discount": 1.0 - common / latest,
                "rounds": float(sum(s.preferred for s in t.securities)),
                "latest_share": lt.shares * lt.conversion / t.fully_diluted,
                "senior": float(lt.seniority > max(s.seniority for s in t.securities if s.preferred and s is not lt)),
                "participating": float(lt.participating),
                "multiple": lt.multiple,
                "post_money": f.post_money,
            }
        )
    return rows
