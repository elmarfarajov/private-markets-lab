# Roadmap

Ten days, one area of private markets a day. Each day is a GitHub issue, a branch, a series of
small commits, a pull request with its rationale, green CI and a release (Day N is v0.N.0; Day 10
is v1.0.0). Every day holds its measures to references they share no code with: published worked
examples, independent methods, identities that must hold, and funds whose truth is known.

| Day | Area | Issue | Release | Status |
|---|---|---|---|---|
| 1 | Cash flows and performance measures: every IRR, MIRR, multiples, the PME family, the J-curve | #1 | v0.1.0 | ✅ Done |
| 2 | Fees, waterfalls and carried interest as an option: European and American carry, hurdle, catch-up, clawback, Metrick-Yasuda | #2 | v0.2.0 | ✅ Done |
| 3 | Stochastic fund cash-flow models and secondary pricing: Takahashi-Alexander, calibration, discounts to NAV | #3 | v0.3.0 | ✅ Done |
| 4 | Venture capital: preferred stock as a portfolio of options (OPM, Gornall-Strebulaev), post-money valuations | #4 | v0.4.0 | Next |
| 5 | Nowcasting private equity NAVs: state-space models and the Kalman filter on reported values | #5 | v0.5.0 |  |
| 6 | Smoothed returns and hidden risk: Geltner and GLM unsmoothing, appraisal indices against listed proxies | #6 | v0.6.0 |  |
| 7 | Risk-adjusted performance with stochastic discount factors: Korteweg-Nagel GPME, cash-flow betas | #7 | v0.7.0 |  |
| 8 | Optimal allocation with illiquid assets: commitment pacing, liquidity constraints, dynamic programming | #8 | v0.8.0 |  |
| 9 | Hedge funds and liquid alternatives: factor replication, trend following, tail risk | #9 | v0.9.0 |  |
| 10 | The endowment digital twin: a 30-year simulator, dashboard and reproducible reports | #10 | v1.0.0 |  |

The plan was revised on Day 2 to make room for option-based valuation (carry, venture preferred stock),
NAV nowcasting and stochastic discount factors; the issues were retitled to match.

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


## Day 2 - fees, waterfalls and carried interest as an option ✅

**Issue #2, release v0.2.0.**

- **The waterfall engine** (`pmlab.waterfall`). European and American waterfalls, fee bases,
  compounded hurdle, partial catch-up, interim carry, clawback with partial recovery; vectorised
  over funds. Every pound accounted for to 1e-13.
- **Gross to net.** 15% gross becomes 10.2% net under 2 and 20; the GP's take is 34% of gross
  profit. The catch-up pins 6% of simulated funds at exactly the hurdle.
- **Carry as an option** (`pmlab.carry`). Closed form `cu C(H) - (cu - c) C(V*)`, matched by Monte
  Carlo through the waterfall and by quadrature. In present value 83% of the GP's revenue is
  fixed fees; the break-even alpha is 4.0% a year.
- **American waterfalls.** The clawback is owed by 82% of funds. A portfolio of options is worth
  4.9 against 0.7 for an option on a portfolio of independent deals.
- **Sixteen charts, six validation checks, ADRs 0006-0008.**

## Day 3 - fund cash-flow models and the secondary market ✅

**Issue #3, release v0.3.0.**

- **`pmlab.fundmodel`.** Takahashi-Alexander (IRR = G by identity), least-squares calibration, a
  quarterly stochastic model with market beta, own risk, cash-flow noise and smoothed NAVs, and a
  vintage study (46% of IRR variance between vintages).
- **`pmlab.secondary`.** LP interests valued at the buyer's required return; discount zero at the
  fund's expected return; decomposition into assets, unfunded commitment and staleness; crash
  dynamics with stale NAVs; buyer IRR distributions.
- **Sixteen charts, six validation checks, ADRs 0009-0011.**
