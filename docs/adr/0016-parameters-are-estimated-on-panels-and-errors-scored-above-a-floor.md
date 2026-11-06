# 16. Parameters are estimated on panels of funds, and errors are scored above a size floor

- **Status:** Accepted
- **Date:** 2026-11-06

## Context

The filter needs five parameters: the appraisal speed `a`, the beta, the growth intercept, the
idiosyncratic volatility and the appraisal noise. One fund gives at most 47 quarterly reports, and
they are dominated by noise. Relative errors are also unstable when a fund holds very little,
early in its life or as it winds up.

## Decision

- `nowcast.estimate` maximises the filter's prediction-error likelihood (Nelder-Mead, with
  logistic and log transforms) on a **panel** of funds that share the parameters. This mirrors an
  investor with many funds from one manager or strategy, as in Brown, Ghysels and Gredil (2023).
- Errors are relative to the true value and are scored only from the second year, and only where
  the true value exceeds 5 per 100 committed (`nowcast.errors`, `floor=5`).

## Consequences

- With 100 funds per panel, 50 panels give mean estimates of `a = 0.399` (sd 0.008) and
  `beta = 1.198` (sd 0.045) against true values of 0.40 and 1.20.
- One fund alone gives a beta estimate with an interquartile range of 0.53, so the method is
  not for single funds in isolation.
- Before the floor was introduced, the error charts were dominated by the last two years, when
  the true value approaches zero. With the floor they describe the fund's working life.
