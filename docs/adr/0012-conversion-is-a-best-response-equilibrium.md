# 12. Conversion is decided as a best-response equilibrium, not by a formula

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

At an exit, each class of convertible preferred stock keeps its liquidation preference or converts
into common, whichever pays more. These choices interact. When one class converts, it gives up its
preference, which leaves more for the junior classes, and it adds shares to the residual, which
dilutes everyone else who shares it. Practitioner spreadsheets often fix the conversion order in
advance ("A converts first, then B..."). That ordering breaks once terms differ between rounds:
participation, caps, multiples above 1x or pari passu ranks can all change who converts first.

## Decision

- `venture.payoff` starts from no class converting. Each preferred class in turn switches if
  switching raises its own payout. The loop repeats until no class wants to change.
- The waterfall itself (`_distribute`) is a pure function of the exit value and a set of choices.
  It pays preferences by seniority, pro rata within a rank. The residual then goes, as converted, to
  common, converted preferred and participating preferred. Capped participants are fixed at their cap
  and the rest share again.
- Two identities are tested on random cap tables. The payouts add to the exit value. No class gains by
  reversing its choice.

## Consequences

- Any mix of terms is handled without hand-coded conversion orders. The order in which classes
  convert is an output, and the breakpoint chart reads it off.
- Best response finds *an* equilibrium. With unusual terms more than one could exist, and the one
  found is the one reached from "nobody converts". For the terms used here (standard and
  participating preferred, caps up to 3x), the tests found no case where a class wanted to deviate.
- Each payoff costs a few waterfall passes, so the payoff curve is computed once on a grid
  (ADR 0013) rather than at every simulated exit.
