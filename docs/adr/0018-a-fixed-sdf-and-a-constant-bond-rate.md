# 18. A fixed SDF and a constant bond rate for GPME

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

Korteweg and Nagel (2016) estimate the SDF's two parameters jointly with the fund cross-section,
by GMM. They use moment conditions that price the market, the Treasury bill and the funds, with
standard errors that allow for overlapping fund lives. That needs fund-level cash flows, which are
licensed. This lab has model funds and one public index history (the S&P 500 total return, from
Yahoo), but no stored risk-free series.

## Decision

- **The SDF is fixed before the funds are measured:**
  - on simulated markets, the log-normal closed form b = (μ − r)/σ²;
  - on the S&P 500, the sample-moment fit (`SDF.fit`), which prices the index's monthly returns
    and the bond exactly in sample.
- **The bond rate is a constant 2% a year.** It is a parameter of every function, not a
  hidden default.
- **GPME is reported as NPV per pound called,** which is linear and unbiased across funds. The
  ratio form (`pme_ratio`) is kept for comparison with KS-PME, but it is not averaged.
- **Cash-flow betas use Driessen, Lin and Phalippou's squared-NPV objective on single funds**,
  without vintage portfolios.

## Consequences

- The study measures the measures: GPME's neutrality across betas, KS-PME's bias, their noise and
  their power, on funds whose true value is known.
- b on the S&P 500 (4.39) depends on the bond rate: about 4.2 at 3%. The fitted SDF should not be
  read as an estimate of investors' risk aversion.
- The cash-flow alpha is biased upwards by about 1.5 points a year. The note reports the bias
  rather than correcting it.
