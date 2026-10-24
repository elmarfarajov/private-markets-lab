# 9. Takahashi-Alexander is the skeleton of the fund model, made random rather than replaced

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

Investors project private fund cash flows with one of two families. The first is Takahashi and
Alexander's (2002) deterministic "Yale" model: call rates on the uncalled commitment, a growth rate,
and a "bow" that delays distributions. The second is stochastic models, which add random returns
and random timing (Buchner, Kaserer and Wagner, 2010; Jeet, 2020).

The deterministic model is the industry standard for pacing. Its parameters are easy to read and to
calibrate, but it has no uncertainty, so it cannot answer the questions Days 3 and 8 need:

- What is the 95th percentile of capital calls?
- What is an LP interest worth to a buyer who requires a higher return?

A fully stochastic model with its own parameterisation would be harder to compare with what
practitioners use.

## Decision

- **The deterministic model is kept exactly** (`takahashi_alexander`). Its identities are tested:
  the IRR equals G, the NAV ends at zero, and calls sum to the commitment.
- **The stochastic model keeps the same skeleton** on a quarterly grid. Annual call and distribution
  rates are converted to quarterly ones as `1 − (1 − RC)^(1/4)` and multiplied by mean-one lognormal
  noise. The NAV grows with a market factor (beta) and the fund's own risk, with the drift set so
  that expected growth is `μ` whatever the risk mix. With the noise and volatilities at zero, it
  reproduces the deterministic recursion (tested).
- **The reported NAV is a separate state.** An appraisal moves a share `a` of the way to the true value
  each quarter. Day 6 studies the smoothing this creates; Day 3 uses it to price stale NAVs.
- **Calibration fits the deterministic model** to year-end cumulative calls, cumulative
  distributions and NAV by least squares. It recovers known parameters to 10⁻⁶ from noise-free
  curves, and without bias from noisy ones.

## Consequences

- One parameter set describes both the planning case and its distribution.
- Expected flows of the stochastic model follow the deterministic recursion with growth `e^(μ dt)`,
  because the noise is mean-one and independent of the NAV. This gives a fast valuation shortcut
  (ADR 0010).
- Real funds have skewed deal returns, recycling and fee-driven early calls. The model is a
  description of the average fund, not of any one.
