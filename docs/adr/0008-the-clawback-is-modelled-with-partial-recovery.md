# 8. The clawback is modelled to a whole-fund entitlement, with partial recovery, and American results always state it

- **Status:** Accepted
- **Date:** 2026-10-19

## Context

A deal-by-deal (American) waterfall pays carry on each winning deal as it exits, before the
fund's later losers are known. The clawback is what makes it fair. At the end, the GP returns any
carry above what the whole fund earned it.

In practice a clawback is rarely recovered in full:

- carry already distributed to individual partners has been taxed, and many agreements cap the
  clawback at the after-tax amount;
- partners leave, and a guarantee from the management company may be weaker than the GP's
  promise;
- some agreements test only at the end of the fund's life, years after the overpayment.

How much of the excess comes back decides whether an American waterfall costs LPs anything. On
Day 2's stylised funds the GP is overpaid in about 80% of American funds, by 24% of all carry paid.

## Decision

- **The entitlement is the smaller of two amounts.** One is `carry` of the fund's total profit
  (distributions minus all contributions, fees included). The other is the largest carry that
  still leaves LPs their hurdle: carry paid plus the LPs' surplus at the hurdle rate, compounded
  to the end. LPs' flows are linear in a final repayment, so this second amount is exact.
- **The GP returns `clawback_recovery` of the excess** at the fund's last date. Recovery is 1 by
  default, and 0.5 is shown alongside as a plausible after-tax case.
- **Every American-waterfall result states its recovery assumption.** "American, full clawback",
  "50% recovered" and "no clawback" are separate rows in every table and chart.
- **The same entitlement test applies to the European waterfall.** It almost never binds there;
  in 20,000 simulated European funds the clawback was zero.

## Consequences

- The suite checks that carry kept equals `min(paid, entitlement)` under full recovery, and never
  exceeds 20% of profit, over 5,000 random American funds.
- With full recovery the American waterfall's carry kept is, on average, slightly *below* the
  European one: the GP keeps `min(paid, entitlement)`, while the European pays close to the
  entitlement. Its present value is still higher, because it is paid earlier. With 50% recovery
  the GP keeps 13% more than under the European waterfall.
- Interest on the clawback, escrow accounts and interim clawback tests are not modelled.
