# 2. An IRR is reported with every root, or not at all

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The IRR is a root of the NPV. Spreadsheet `IRR` and `XIRR`, `numpy-financial` and most
libraries return whichever root their iteration reaches from a guess, and fail silently
when there is none. Private-fund streams are not always conventional:

- recallable distributions;
- real-estate refinancings followed by loan repayments;
- an investor's share of a clawback.

Any of these can give a stream two IRRs, or none.

## Decision

- **`irr_roots` returns every IRR between -99% and 10,000% a year.** It scans the NPV on
  a grid even in `ln(1 + r)`, refines each sign change with Brent's method, and catches
  roots where the NPV touches zero without crossing.
- **`irr` returns a number only when the root is unique.** Otherwise it raises, naming
  the roots.
- **Descartes' rule bounds the count** and is reported beside it. Norstrom's condition
  is stated for what it guarantees: one *positive* IRR, and no more than that.
- **Long-Nickels, whose replayed stream can lose its unique IRR, reports NaN and its
  roots** rather than an arbitrary one.

## Consequences

- **Two independent routes agree with the scan.** Polynomial roots in `1/(1 + r)` agree
  for periodic streams to 4e-15, and mpmath's 50-digit polynomial roots agree on every
  root of 600 random streams to 9e-15. No count exceeds Descartes' bound.
- **Norstrom's condition is weaker than often quoted.** Of 606 random streams that met
  it, 216 had a negative IRR beside the positive one.
- **Streams whose IRR lies outside the range are reported as having none.** The range is
  stated in the function, and the tests keep to it.
