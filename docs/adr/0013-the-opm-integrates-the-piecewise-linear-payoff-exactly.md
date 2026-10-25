# 13. The OPM integrates the piecewise-linear payoff exactly; Monte Carlo is the check

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

The option-pricing method (OPM) values each class as the discounted risk-neutral expectation of its
exit payoff, with the exit value lognormal. The AICPA's valuation guide and Gornall and Strebulaev
(2020) use it. Every class's payoff is piecewise linear in the exit value, so each class is a
portfolio of calls on the company. Practitioners usually find the breakpoints by hand and add up
Black-Scholes calls. That is exact, but only when the breakpoints are right, and finding them is
where errors creep in.

## Decision

- `Payoffs.build` evaluates the equilibrium payoff (ADR 0012) on a geometric grid of exit values
  (1,500 points by default, from 10⁻⁴ of the total preference to 50 times the post-money).
- `Payoffs.value` integrates the linear interpolation **exactly** against the lognormal density. On
  each interval the payoff is α + βV, and E[(α + βV)·1{a < V < b}] needs only N(d₂) and F·N(d₁) at
  the two ends. Beyond the last point, the last slope continues.
- Monte Carlo with the discounted exit value as a control variate checks the integral. The plain
  estimator was too noisy for a lognormal with 90% volatility over 4 years.
- A one-class cap table, whose value V − C(P) + α·C(P/α) is known in closed form, checks both the
  waterfall and the integral.

## Consequences

- Breakpoints are found automatically, to grid precision, and reported (`breakpoints`).
- Class values add up to the company value exactly, because the interpolated payoffs add up to V
  at every grid point.
- The closed-form check agrees to 3 × 10⁻⁷. Monte Carlo agrees within 0.7 standard errors in the
  validation run.
- The method assumes one lognormal exit at a fixed date. Real exits are early or late, and IPOs often
  void the preferences. Both are outside the model and are discussed in the note.
