# 1. One sign convention, and the NAV is a final distribution

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

Private fund data comes from the limited partner's ledger, the general partner's
reports and consultants' databases. Each signs its flows differently, and an unfinished
fund carries a net asset value that is an estimate, not cash. A measure computed on
mixed conventions is silently wrong.

## Decision

- **Every amount is from the investor's side:**
  - capital calls, management fees included, are negative;
  - distributions are positive.
- **An unfinished fund's NAV is treated as a distribution on its valuation date.** That
  is the convention of every performance report. `CashFlows.with_nav()` applies it in
  one place.
- **Times are in years, on actual/365.** Rates compound annually (the XIRR convention),
  except Direct Alpha, which is reported continuously compounded as its authors define
  it.

## Consequences

- **An interim IRR or TVPI is partly an opinion.** The NAV in it is the manager's
  valuation; the J-curve chart shows how little an early interim IRR means.
- **One convention serves every measure:** IRR, MIRR, the multiples, and all five PMEs
  read the same `CashFlows`. The validation suite checks that they agree where theory
  says they must.
