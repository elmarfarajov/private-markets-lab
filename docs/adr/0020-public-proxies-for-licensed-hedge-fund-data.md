# 20. Public proxies for licensed hedge-fund data, and option factors without option prices

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

Hedge-fund research runs on HFR, Lipper TASS and BarclayHedge, all licensed. Fung and Hsieh's
trend factors use option prices, and Agarwal and Naik's option factors use traded S&P 500 options.
Neither kind of data can be committed or bought for this project, and the project does not
imitate licensed data (ADR 0004).

## Decision

- **Funds.** Public instruments stand in for hedge-fund indices: QAI (a hedge-fund index
  tracker), DBMF (a managed-futures tracker) and the CBOE S&P 500 PutWrite index. A trend
  strategy is built from ten ETFs by a published rule. They are named as what they are.
- **Option factors.** The lookback-straddle premium uses trailing 63-day realised volatility,
  priced for daily monitoring with the Broadie-Glasserman-Kou shift, because the payoff is
  measured on daily closes. The put factor is priced by Black-Scholes at the VIX.
- **Storage.** Daily closes come from Yahoo Finance and stay under the git-ignored `data/alts`,
  fetched by `pmlab market fetch`. The charts that need them are skipped where they are absent.

## Consequences

- The note cannot study survivorship, backfill or self-selection, the main biases in hedge-fund
  databases, and says so.
- The factors' levels depend on the volatility proxies; the regressions' slopes and R² do much
  less. The comparison with Fung and Hsieh's R² is in direction, not in size.
- A pricing error in the first version (continuous formula, daily payoff) made the straddle
  factor lose 14% a month by construction. A validation check now holds the daily formula to
  Monte Carlo.
