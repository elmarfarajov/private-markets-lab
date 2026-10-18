"""Carried interest as an option, and what a manager's pay is worth today (Metrick and Yasuda, 2010).

The GP's carry pays nothing unless the fund clears its hurdle, and a share of the upside if it
does: it is a call option on the fund, written by the LPs. For a single investment of ``K``
held ``T`` years with no fees, the hurdle amount is ``H = K (1 + h)^T``, and the waterfall pays
the GP

* nothing while the proceeds ``V`` are below ``H``;
* ``cu (V - H)`` in the catch-up tier, until it holds ``c`` of the profit, at
  ``V* = H + c (H - K) / (cu - c)``;
* ``c`` of everything above.

So ``carry = cu (V - H)^+ - (cu - c) (V - V*)^+``: long ``cu`` calls struck at the hurdle and
short ``cu - c`` calls struck where the catch-up ends. Without a catch-up it is ``c (V - H)^+``.
Under risk-neutral lognormal proceeds its value is two Black-Scholes calls; with many deals,
fees, an American waterfall and a clawback it is valued by Monte Carlo on the waterfall engine.

Fees are (nearly) certain and discounted at the risk-free rate; carry is valued under the
risk-neutral measure, where every deal earns the risk-free rate in expectation. LPs then lose,
in present value, exactly what the GP gains: the fees and the carry. The **break-even alpha** is
the extra return a year the deals must earn for the LPs' investment to be worth what it costs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import optimize
from scipy.stats import norm

from .waterfall import DealModel, Shape, Terms, run, single_deal_shape

Array = NDArray[np.float64]


def black_call(forward: float, strike: float, years: float, sigma: float, discount: float) -> float:
    """Black (1976) call on a lognormal forward: ``discount * (F N(d1) - X N(d2))``."""
    if strike <= 0:
        return discount * (forward - strike)
    if sigma <= 0 or years <= 0:
        return discount * max(forward - strike, 0.0)
    s = sigma * np.sqrt(years)
    d1 = (np.log(forward / strike) + 0.5 * s * s) / s
    return float(discount * (forward * norm.cdf(d1) - strike * norm.cdf(d1 - s)))


def strikes(capital: float, years: float, terms: Terms) -> tuple[float, float | None]:
    """The hurdle amount ``H`` and the end of the catch-up ``V*`` (None when there is no catch-up)."""
    h = capital * (1.0 + terms.hurdle) ** years
    if terms.catch_up > terms.carry and terms.carry > 0:
        return h, h + terms.carry * (h - capital) / (terms.catch_up - terms.carry)
    return h, None


def carry_payoff(value: ArrayLike, capital: float, years: float, terms: Terms) -> Array:
    """The GP's carry from a single investment returning ``value``, from the option decomposition (not the waterfall code)."""
    v = np.asarray(value, dtype=np.float64)
    h, v_star = strikes(capital, years, terms)
    if v_star is None:
        return terms.carry * np.maximum(v - h, 0.0)
    return terms.catch_up * np.maximum(v - h, 0.0) - (terms.catch_up - terms.carry) * np.maximum(v - v_star, 0.0)


def carry_closed_form(capital: float, years: float, r: float, sigma: float, terms: Terms) -> float:
    """Present value of the carry on one investment of ``capital`` held ``years``, priced at cost, with no fees."""
    forward = capital * np.exp(r * years)
    disc = float(np.exp(-r * years))
    h, v_star = strikes(capital, years, terms)
    if v_star is None:
        return terms.carry * black_call(forward, h, years, sigma, disc)
    return terms.catch_up * black_call(forward, h, years, sigma, disc) - (terms.catch_up - terms.carry) * black_call(
        forward, v_star, years, sigma, disc
    )


@dataclass(frozen=True)
class Valuation:
    """Present values per 100 of commitment, at the risk-free rate under the risk-neutral measure."""

    fees: float
    carry: float  # carry kept, after the clawback
    carry_se: float
    lp: float  # value of the LPs' position: proceeds less calls, discounted
    lp_se: float
    clawback_probability: float
    funds: int

    @property
    def gp(self) -> float:
        return self.fees + self.carry

    @property
    def fixed_share(self) -> float:
        """The share of the GP's revenue that does not depend on performance."""
        return self.fees / self.gp if self.gp > 0 else float("nan")


def value(shape: Shape, terms: Terms, model: DealModel, r: float, funds: int = 20000, alpha: float = 0.0) -> Valuation:
    """Value fees, carry and the LP stake with deals earning ``r + alpha`` in expectation (``alpha = 0``: fairly priced)."""
    m = replace(model, mu=r + alpha).draw(shape, funds)
    out = run(shape, m, terms)
    disc = np.exp(-r * out.times)
    carry_pv = out.carry @ disc - out.clawback * disc[-1]
    lp_pv = out.lp_flows() @ disc
    return Valuation(
        fees=float(out.fees @ disc),
        carry=float(carry_pv.mean()),
        carry_se=float(carry_pv.std(ddof=1) / np.sqrt(funds)),
        lp=float(lp_pv.mean()),
        lp_se=float(lp_pv.std(ddof=1) / np.sqrt(funds)),
        clawback_probability=float((out.clawback > 1e-9).mean()),
        funds=funds,
    )


def break_even_alpha(shape: Shape, terms: Terms, model: DealModel, r: float, funds: int = 20000) -> float:
    """The extra expected return a year, on every deal, that makes the LPs' stake worth zero (common random numbers)."""

    def lp(alpha: float) -> float:
        return value(shape, terms, model, r, funds, alpha).lp

    return float(optimize.brentq(lp, -0.05, 0.30, xtol=1e-6))


def single_deal_mc(years: float, r: float, sigma: float, terms: Terms, funds: int = 200000, seed: int = 5) -> tuple[float, float]:
    """Monte Carlo value and standard error of the carry on one fee-free investment, through the waterfall engine."""
    shape = single_deal_shape(years)
    t = replace(terms, fee=0.0, post_fee=0.0, clawback=False)
    model = DealModel(mu=r, sigma=sigma, rho=0.0, seed=seed, common=False)
    out = run(shape, model.draw(shape, funds), t)
    pv = out.carry.sum(axis=1) * np.exp(-r * shape.end)
    return float(pv.mean()), float(pv.std(ddof=1) / np.sqrt(funds))
