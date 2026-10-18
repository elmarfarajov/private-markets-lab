# 5. The PME is reported as a family, with its benchmark, and Direct Alpha leads

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

Five public market equivalents are in common use, and they answer slightly different
questions:

- **Kaplan-Schoar:** a ratio.
- **Direct Alpha:** a rate.
- **Long-Nickels, PME+ and mPME:** each an "index IRR" to compare with the fund's.

Each rests on an assumption. Kaplan-Schoar assumes the fund's beta to the index is one;
Long-Nickels can lose its unique IRR; mPME needs a NAV at every date.

## Decision

- **`report()` computes all five for one fund and one index.**
- **Direct Alpha is the headline rate.** It is the outperformance a fund earning the
  index times `exp(alpha t)` would show, and it is zero exactly when the Kaplan-Schoar
  PME is one. The Kaplan-Schoar PME is shown beside it.
- **Long-Nickels is reported with its failure:** NaN, the roots, and a flag when its
  index account went negative.
- **Every PME is quoted with its benchmark.** Four total-return benchmarks are available
  locally.

## Consequences

- **On 25 stylised funds with a true 3% alpha over the S&P 500, the IRR-based measures
  agree where they exist.** Long-Nickels has no unique answer in 14 vintages of 25.
- **A beta away from one is credited as alpha.** Funds with zero alpha and a beta of 1.8
  show 3 to 15 points a year of Direct Alpha against the S&P 500 in every vintage since
  1990. Day 6 estimates fund betas instead of assuming one.
- **The benchmark changes the answer by several points a year.** The same funds measured
  against the Nasdaq-100 show negative alpha in every vintage from 2004.
