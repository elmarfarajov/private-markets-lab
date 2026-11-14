# 17. A model index with a private factor tests the unsmoothing methods

- **Status:** Accepted
- **Date:** 2026-11-14

## Context

Unsmoothing methods are applied to appraisal-based indices (Cambridge Associates, NCREIF, Burgiss)
whose true returns are unknown, so their accuracy cannot be measured on real data. Those indices are
also licensed. A model index whose true returns are known is the only way to score the methods.

A first attempt aggregated 1,200 model funds driven by the public market alone. Their own risks
diversified away, and the true index correlated 0.998 with the market. Real private equity indices
correlate with public markets roughly 0.6-0.8 even after unsmoothing: they carry sector, leverage
and deal-cycle risks the public index does not.

## Decision

- `smoothing.build_index`: 30 yearly vintages of 40 Day 3 model funds, sharing one path of
  systematic shocks. 80% of each shock is the public market and the rest a private factor.
  Reported NAVs come from Day 5's appraisal rule (a = 0.4, 5% noise). The index return each quarter
  is total value change net of flows over total opening value, for true values and for reported
  NAVs. Index quarters start once five vintages are running and stop when new vintages stop
  joining.
- The public market earns a 6% premium, so allocation comparisons are meaningful.
- The calendar labels (2000-2024) are labels only; the index is simulated.
- Unsmoothing: Geltner with `a` from the lag-1 autocorrelation, and GLM's MA(2) by maximum
  likelihood with softmax weights summing to one.

## Consequences

- The study measures how well the methods work when their assumptions hold. Over 60 histories the
  reported index shows a median 51% of the true volatility, Geltner 97% and GLM(2) 77%.
- With four lags GLM is poorly identified on 100 quarters (weights flatten, implied volatility
  67%). Two lags are reported as the base case for that reason.
