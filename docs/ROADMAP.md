# Roadmap

Ten days, one area of private markets a day. Each day is a GitHub issue, a branch, a series of
small commits, a pull request with its rationale, green CI and a release (Day N is v0.N.0; Day 10
is v1.0.0). Every day holds its measures to references they share no code with: published worked
examples, independent methods, identities that must hold, and funds whose truth is known.

| Day | Area | Issue | Release | Status |
|---|---|---|---|---|
| 1 | Cash flows and performance measures: every IRR, MIRR, multiples, the PME family, the J-curve | #1 | v0.1.0 | ✅ Done |
| 2 | Fees and waterfalls: European and American carry, hurdles, catch-up, clawback, gross to net | #2 | v0.2.0 | Next |
| 3 | Fund cash-flow models: Takahashi-Alexander, stochastic models, calibration, vintage dispersion | #3 | v0.3.0 | |
| 4 | Secondaries: pricing LP interests, discounts to NAV, continuation funds, NAV loans | #4 | v0.4.0 | |
| 5 | Smoothed returns and true risk: unsmoothing appraisal returns, real estate indices against REITs | #5 | v0.5.0 | |
| 6 | Risk-adjusted performance: stochastic discount factors, cash-flow betas, listed proxies | #6 | v0.6.0 | |
| 7 | Commitment pacing and liquidity: overcommitment, capital-call stress, the denominator effect | #7 | v0.7.0 | |
| 8 | Portfolio construction with illiquid assets: unsmoothed risk, liquidity constraints, dynamic programming | #8 | v0.8.0 | |
| 9 | Hedge funds and liquid alternatives: factor replication, trend following as an option, tail risk | #9 | v0.9.0 | |
| 10 | The platform: a 30-year endowment simulator, dashboard and reproducible reports | #10 | v1.0.0 | |

The deal-level leveraged buyout - operating model, debt schedule, value bridge, exit waterfall -
is not repeated here; it is [lbo-returns-engine](https://github.com/elmarfarajov/lbo-returns-engine).

## Day 1 - cash flows and performance measures ✅

**Issue #1, release v0.1.0.**

- **Every IRR.** The NPV is scanned in `ln(1 + r)` and each root refined. The count is bounded by
  Descartes' rule, and the scan agrees with polynomial roots and with mpmath at 50 digits.
  Norstrom's condition guarantees one *positive* IRR only: 216 of 606 random streams meeting it
  also had a negative one.
- **Published examples reproduced.** Excel's XIRR to its own tolerance, MIRR to the printed
  digit, and Lorie and Savage's pump to 9e-16.
- **The IRR managed.** A subscription line delaying calls by a year lifts the IRR from 10.5% to
  11.5% while the TVPI falls from 1.80 to 1.70.
- **Five PMEs, one identity.** Kaplan-Schoar, Direct Alpha, Long-Nickels, PME+ and mPME agree to
  1e-15 on a fund that replicates the index. On real S&P 500 paths:
  - a beta of 1.8 is credited as 3 to 15 points of alpha;
  - the benchmark moves Direct Alpha by 6 points;
  - identical managers' IRRs span 1% to 20% across vintages.

**Notes:** [cash flows and performance measures](notes/cash-flows-and-performance.md).
