# 10. Secondaries are priced from the buyer's required return, on the true value, with staleness separated

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

Secondary prices are quoted as a percentage of the latest reported NAV. A quoted discount mixes:

- what the buyer requires;
- the value of the unfunded commitment it takes over;
- the difference between the reported NAV and what the assets are worth now.

Published discount data (for example semi-annual broker reports) is aggregate and proprietary, and
is not reproduced here (ADR 0004).

## Decision

- **Value = present value of expected future distributions minus calls, at the buyer's required
  return `r`**, continuously compounded, from the fund's state: age, true value, reported NAV and
  uncalled commitment.
- **Expected flows come from the noise-free recursion** (`expected_path`). The validation suite
  checks this against full Monte Carlo of the stochastic model, within 2.1 standard errors.
- **The discount is quoted against the reported NAV**, as the market does, and decomposed into three
  parts: existing assets priced at `r` rather than `μ`, the unfunded commitment, and staleness. The
  parts add up to the total to 10⁻¹⁶ (tested).
- **A buyer requiring the fund's expected return pays exactly NAV** (tested to 10⁻¹⁴). This is the
  anchor: any discount is a statement about required returns or stale prices, not fund quality as
  such.

## Consequences

- Discounts above 100% are possible for very young funds at high required returns. The unfunded
  commitment is then worth less than nothing to the buyer, and the seller would have to pay to exit.
  This is reported, not truncated.
- A buyer's IRR is reported as a distribution over simulated futures, not as the required return. The
  median IRR is below the expected return because fund returns are right-skewed.
- Fund quality (expected `μ` above or below the market's view), information asymmetry and deal
  structure (deferred payment, preferred equity) are not modelled.
