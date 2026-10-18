# 7. Carry is valued as an option under risk-neutral pricing; fees at the risk-free rate

- **Status:** Accepted
- **Date:** 2026-10-19

## Context

"What is a manager's pay worth?" has no single answer without a model. Expected carry under the
real-world distribution mixes the value of the option with the manager's assumed skill and the
market's risk premium. A present value needs a discount rate, and the right rate for an option
is not the right rate for a fee.

Metrick and Yasuda (2010) value each component separately:

- **management fees** are close to certain, so they are discounted at the risk-free rate;
- **carry** is an option on the fund's assets, so it is valued under the risk-neutral measure,
  where every investment earns the risk-free rate in expectation.

No fund-level cash flows are public (ADR 0004), so the deal-return model must be stylised, and
its parameters must be stated wherever a result depends on them.

## Decision

- **`pmlab.carry.value` prices fees, carry and the LPs' stake together** on one set of simulated
  funds. Deals are lognormal with expected return `r + alpha`, volatility `sigma` and pairwise
  correlation `rho` (one common factor). With `alpha = 0` the deals are fairly priced, and the
  LPs' stake is worth minus the fees and carry: an identity the validation suite tests.
- **The closed form is the test, not the tool.** For one investment with no fees, the carry is
  `cu C(H) - (cu - c) C(V*)`, two Black-Scholes calls. The waterfall engine must reproduce it by
  Monte Carlo (largest gap 1.1 standard errors in the suite). The closed form must also match
  numerical integration of the payoff against the lognormal density (gap 1.5 × 10⁻⁸).
- **The break-even alpha** is reported as the headline measure of what fees cost. It is the extra
  expected return a year that makes the LPs' stake worth zero, found by Brent's method on common
  random numbers.
- **Default parameters are stated on every chart:** `r = 4%`, deal volatility 40% (60% for the
  venture case), correlation 0.3, fifteen deals over five years held three to seven.

## Consequences

- Every value is conditional on the deal model. The charts therefore show how carry changes with
  volatility, correlation and alpha, rather than one number.
- Risk-neutral values say what the contract is worth, not what a manager expects to earn. Both
  are reported where they differ (the clawback and distribution charts use a 12% real-world
  expected return).
- Monte Carlo noise is reported with each value (standard errors around 0.05 per 100 committed
  at 20,000 funds). The tests use 600 funds per chart point, so CI stays fast.
