# 19. A programme simulation for liquidity and a separate DP for the allocation

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

Two questions need different tools.

- **Liquidity.** Pacing, the denominator effect and forced sales depend on the J-curve,
  unfunded commitments and lagging appraisals: the full fund cash-flow model, over decades.
- **Allocation.** The optimal allocation under illiquidity needs a Bellman equation. Adding
  unfunded commitments and vintage ages to its state makes it high-dimensional (Giommetti and
  Sorensen 2021).

## Decision

- **`simulate_programme`** runs the Day 3 model for every vintage on the scenario's market path,
  with rule-based pacing, spending, a liquidity floor and forced secondary sales. It does not
  optimise.
  - Each vintage is simulated once per scenario for one unit of commitment and then scaled,
    because its flows are linear in commitment.
  - The secondary discount is a hand-chosen function of the past year's market return: 5% plus
    0.8 times the fall, at most 50%.
- **`solve_dp`** solves a CRRA investor's problem with an illiquid asset that can be rebalanced at
  random times (Ang, Papanikolaou and Westerfield 2014).
  - It uses a finite horizon with utility of terminal wealth. An infinite-horizon version without
    consumption has no non-trivial fixed point; the first attempt converged to zero.
  - The state is the illiquid share alone, so there are no unfunded commitments and no spending.
- **Mean-variance** uses the programme's moments measured from the fund model, at true and at
  reported value.

## Consequences

- Each tool answers its own question. The note says plainly that the DP ignores commitments, and
  that the simulation does not optimise.
- The liquidity results depend on the floor and the discount schedule; both are varied or stated.
