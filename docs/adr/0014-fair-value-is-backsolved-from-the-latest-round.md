# 14. Fair value is backsolved from the latest round, and the overstatement is post-money over fair value

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

A round reveals one price: what the newest investors paid for the newest, most senior shares. The
headline post-money valuation applies that price to every fully diluted share. To find what the
company is worth on the same evidence, one asks what company value makes the price fair given the
round's terms.

## Decision

- `backsolve` finds, by Brent's method, the company value at which the latest class's OPM value
  equals the amount it invested. "Latest" means the class with the highest issue price.
- With that value fixed, every class is valued, including common. Overvaluation is defined as
  post-money / fair value − 1, as in Gornall and Strebulaev (2020).
- Default inputs: volatility 90%, 4 years to exit, risk-free rate 4%. Every chart that depends on
  them repeats them in its caption, and the sensitivity charts vary each one.

## Consequences

- The base company ($3.0bn post-money) is worth $1.80bn: an overstatement of 66.6%. Common is worth
  $16.80, 56% of the Series D price.
- The result depends on the inputs. Volatility has a hump (79% at 60-70% volatility, 31% at 140%).
  Time to exit lowers it (128% at one year, 23% at ten). Neither has a market-observed value for a
  private company, so the note reports ranges, not a single number.
- If the latest class is the most senior, the overstatement does not depend on its price. Its payoff
  scales with its price, so the backsolved value scales too (tested). The overstatement measures the
  structure, not the level, of a valuation.
- The random cap tables are stylised, with term frequencies chosen to be of the order reported in the
  literature. They illustrate the mechanism; they are not an estimate for any real population.
