# 15. NAV nowcasting is a state-space model with noisy, partial-adjustment appraisals

- **Status:** Accepted
- **Date:** 2026-11-06

## Context

A fund's reported NAV lags its true value. Day 3's simulator produces reported NAVs by partial
adjustment, `reported_t = a value_t + (1 - a)(reported_{t-1} + flows_t)`, with no error. With a
known `a`, that rule can be inverted exactly (Geltner unsmoothing). The true value would then be
observed, and a filter would add nothing. Real appraisals are both slow and imprecise.

## Decision

- `nowcast.appraise` adds appraisal noise: an error with standard deviation `obs × (last report +
  calls + 1)`, so the appraiser errs in proportion to the fund's size. The base case is `a = 0.4`
  and 5% noise a quarter.
- The true value follows `value_t = g_t value_{t-1} + calls_t - distributions_t`, with
  `log g_t = c + beta log m_t + sigma e_t`. The market return and the cash flows are observed.
- `nowcast.kalman` propagates the exact conditional mean and variance of this model. Because the
  shock is multiplicative, the transition variance is `F^2 (P + q(m^2 + P))` with `q = e^{sigma^2} - 1`.
  This is the best linear filter, not an exact Gaussian one. A fund starts empty, so the state is
  known before its first call.
- `nowcast.smooth` is the Rauch-Tung-Striebel smoother for the same model.

## Consequences

- Without noise and smoothing, the filter returns the true value exactly (validation check).
- The 90% intervals cover 90.1% of true values in 64,500 fund-quarters, so the moment-matched
  filter's uncertainty is honest despite the non-Gaussian shock.
- The model is deliberately simpler than Brown, Ghysels and Gredil (2023). It has one market
  factor, a constant appraisal speed and no reporting lag beyond the quarter.
