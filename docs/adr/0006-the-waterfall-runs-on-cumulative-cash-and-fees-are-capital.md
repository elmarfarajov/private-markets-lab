# 6. The waterfall runs on cumulative cash, fees count as contributed capital, and funds are simulated in bulk

- **Status:** Accepted
- **Date:** 2026-10-19

## Context

A distribution waterfall can be written many ways, and the differences are not cosmetic.
Partnership agreements differ on four things:

- **what "capital" is:** contributions for deals only, or for deals and fees;
- **how the preferred return accrues:** simple or compounded, on capital called or outstanding;
- **how the catch-up is sized:** a share of distributions until the GP holds its carry share of
  profit to date, or of profit to the end;
- **when carry is paid:** as each distribution is made, or only at the end.

The European waterfall is also path-dependent. A later capital call (for fees, or a follow-on
investment) reopens the hurdle, so the tiers must be evaluated in date order on cumulative
amounts, not on the fund's totals.

Day 2's charts and checks need tens of thousands of funds per point: risk-neutral values,
clawback frequencies, break-even alphas.

## Decision

- **Fees are contributed capital.** The first tier returns everything LPs have paid in, fees
  included, and the preferred return accrues on it. This is the ILPA-recommended convention and
  the common one in buyout agreements.
- **The preferred return compounds monthly at `(1 + h)^(1/12)`** on contributions outstanding:
  the balance grows at the hurdle, rises with each call, and falls with each LP distribution.
  It never goes negative, so capital called later starts a fresh hurdle.
- **The catch-up is sized on cumulative profit distributed.** A tranche `x` in the catch-up tier
  solves `c (L + G - K + x) = G + cu x`, where `L` and `G` are cumulative LP and GP distributions
  and `K` cumulative contributions. A catch-up at or below the carry rate is treated as none.
- **Carry is paid as distributions are made** (interim carry), and the clawback (ADR 0008) settles
  the account at the end.
- **The American waterfall** runs the same tiers on each deal alone. A deal's capital is its cost
  plus its pro-rata share of all fees, and it earns the hurdle from entry to exit.
- **Funds sharing a timeline are run together.** Entry months, exit months and the fee schedule
  are fixed; only the deals' multiples differ between funds. Every tier is then a vector
  operation over funds, and 20,000 funds run in well under a second.
- **The invested share is solved, not assumed.** The fee on invested cost depends on how much is
  invested, so the invested share is the solution of a linear equation that makes calls add up to
  the commitment exactly.

## Consequences

- One function, `check_conservation`, holds the whole engine to an identity: LP plus GP flows
  equal the deals' flows, for every fund, to 10⁻¹³. A property-based test runs it on random terms.
- Hand-checked single-deal cases test every tier boundary (hurdle 146.93, catch-up end 158.67 on
  100 invested for five years).
- Fund timelines with recycling, follow-ons or deal-specific fee offsets are out of scope for Day 2.
  The timeline object (`Shape`) is where they would enter.
