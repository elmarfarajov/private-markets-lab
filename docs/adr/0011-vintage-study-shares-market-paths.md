# 11. Vintage dispersion is measured with funds that share a market path

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

Comparing funds with their vintage peers is standard practice: quartile rankings, PMEs and vintage
benchmarks all rest on it. The value of a peer comparison depends on how much of a fund's outcome is
common to its vintage.

## Decision

- `vintage_study` simulates 25 vintages. Funds within a vintage share one market path and differ only
  in their own risk and cash-flow noise.
- The variance of IRRs is split into between-vintage and within-vintage parts (`variance_split`),
  using the law of total variance. The two parts add to the total, which is tested.
- The market factor in the simulation is a zero-mean shock. Charts label it as a shock, not a return,
  because the fund's expected return sits in its own drift.

## Consequences

- With beta 1.2, market volatility 16% and own volatility 20%, about 46% of the variance of IRRs lies
  between vintages. Peer comparison removes almost half of the noise, not most of it.
- The share depends on the ratio of market to own risk: with own volatility 5%, more than half lies
  between vintages (tested). Real buyout funds' own risk is uncertain, so the number is illustrative.
