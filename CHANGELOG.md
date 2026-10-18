# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

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
