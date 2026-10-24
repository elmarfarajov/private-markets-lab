# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-10-24

Day 3: fund cash-flow models and the secondary market.

### Added

- **`pmlab.fundmodel`**: the Takahashi-Alexander model and its projection; least-squares
  calibration to annual curves; annual curves from dated flows; a quarterly stochastic model (market
  beta, own risk, lognormal cash-flow noise, appraisal smoothing) that can start from any fund
  state; the noise-free expected path; a vintage study and the between/within variance split.
- **`pmlab.secondary`**: fund states, the value and discount of an LP interest at a required return,
  the decomposition of a discount, discount grids, crash dynamics with stale NAVs, buyer IRR
  distributions, and a Monte Carlo check.
- Sixteen charts, the Day 3 note, ADRs 0009-0011.
- Six validation checks (25 in all) and 20 tests.

## [0.2.0] - 2026-10-19

Day 2: fees, waterfalls and carried interest as an option.

### Added

- **`pmlab.waterfall`**: `Terms` (fee bases, carry, hurdle, catch-up, European or American, clawback
  recovery); the fee schedule with the invested share solved exactly; vectorised European and
  American waterfalls; the clawback to a whole-fund entitlement; gross-to-net tables; a lognormal
  deal model with a common factor; a conservation check.
- **`pmlab.carry`**: Black (1976) calls; the carry's option decomposition and closed form;
  risk-neutral valuation of fees, carry and the LPs' stake; the break-even alpha; single-deal Monte
  Carlo through the waterfall.
- **`pmlab fees`** command: gross to net and the contract's value for any terms.
- Sixteen charts, the Day 2 note, ADRs 0006-0008.
- Six validation checks (19 in all) and 28 tests, including a property-based conservation test.

### Changed

- The ten-day plan was revised (Days 3-10) and the issues retitled.
- Chart subtitles wrap narrower so that they are not cut off.

## [0.1.0] - 2026-10-18

Day 1: cash flows and performance measures. Every IRR of a stream, the multiples, five public
market equivalents, and the stylised funds and real index paths that test them.

### Added

- **`pmlab.cashflows`**:
  - `CashFlows`, with one sign convention and the NAV as a final distribution;
  - NPV, and every IRR in a range (`irr_roots`), with Descartes' bound;
  - Norstrom's condition, a unique-or-refuse `irr`, MIRR, the multiples, and interim measures
    along a fund's life.
- **`pmlab.pme`**: Kaplan-Schoar, Direct Alpha, Long-Nickels (reporting its failures), PME+,
  mPME, and a report of all five.
- **`pmlab.synthetic`**: a stylised fund built deal by deal with a known alpha, beta, own risk
  and fees, on simulated or real index paths.
- **`pmlab.market`**: four total-return benchmarks from Yahoo Finance, stored locally by
  `pmlab market fetch`.
- **`pmlab validate`**: 13 checks against published examples, independent methods, identities
  and known truths.
- **`pmlab irr`**: every IRR, the multiples and the PMEs of a cash-flow file.
- **Seven charts**, a methodology note, ADRs 0001 to 0005, and tests, including
  property-based ones.

### Found

- **Norstrom's condition guarantees one positive IRR, not a unique one.** 216 of 606 random
  streams meeting it also had a negative IRR.
- **Long-Nickels has no unique IRR** for 14 of 25 stylised funds with a 3% alpha, whenever the
  index account goes negative.
- **A zero-alpha fund with beta 1.8 shows 3 to 15 points a year of Direct Alpha** against the
  S&P 500 in every vintage since 1990.
