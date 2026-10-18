# Cash flows and performance measures: what an IRR says, what it hides, and what a PME adds

A private fund is not priced every day. What an investor has are cash flows: capital called
over the first years, distributions as the fund sells its companies, and in between a net
asset value that is the manager's estimate. Every performance figure in private markets is
computed from these flows. This note builds the measures from first principles, holds each
to a reference, and shows where each one misleads.

---

## 1. Conventions

All amounts are from the investor's side: calls (fees included) negative, distributions
positive. An unfinished fund's NAV counts as a distribution on its valuation date, which
makes every interim figure partly an opinion. Times are in years on actual/365, and rates
compound annually, as in Excel's XIRR
([ADR 0001](../adr/0001-one-sign-convention-and-the-nav-is-a-final-distribution.md)).

| Measure | Definition | Needs a rate? |
|---|---|---|
| PIC | capital paid in: the sum of calls | no |
| DPI | distributions / PIC | no |
| RVPI | NAV / PIC | no |
| TVPI | DPI + RVPI | no |
| IRR | the rate at which the NPV of the flows is zero | it *is* the rate |
| MIRR | (FV of distributions at a reinvestment rate / PV of calls at a finance rate)^(1/T) - 1 | two, chosen |

## 2. An IRR is a root

![An IRR is a root](../images/irr-pathologies.png)

With `x = ln(1 + r)` the NPV is `f(x) = sum a_i exp(-x t_i)`. Descartes' rule of signs
holds for it: the number of IRRs is at most the number of sign changes in the flows, in time
order. A conventional investment - money out, then money in - has exactly one. A stream
that pays out and then calls again can have two, or none:

| Stream | Sign changes | IRRs |
|---|---|---|
| Lorie and Savage's pump (1955): -1,600, +10,000, -10,000 | 2 | 25% and 400% |
| refinance in year 2, repay in year 6: -100, +190, -100 | 2 | 8.3% and 16.5% |
| +100, -200, +110 | 2 | none |

Spreadsheet IRR functions return whichever root their iteration reaches from a guess.
`irr_roots` returns every root between -99% and 10,000% a year, and `irr` refuses to answer
when there is not exactly one
([ADR 0002](../adr/0002-an-irr-is-reported-with-every-root-or-not-at-all.md)).

**Norstrom's condition is weaker than often quoted.** When the cumulative flows change sign
once, there is exactly one *positive* IRR. On 606 random streams meeting the condition, the
validation suite found 216 that also had a negative IRR.

## 3. The IRR can be managed

![Borrowing to delay capital calls raises the IRR](../images/irr-manipulation.png)

A subscription credit line lets a fund buy companies with borrowed money and call the
investors' capital months later. The money multiple cannot improve - the line's interest
comes out of the same profits - but the IRR measures time, and time has been shortened.

For the stylised fund in the chart, delaying every call by a year moves the measures like
this:

| | Without the line | Line at 6%, calls a year later |
|---|---|---|
| IRR | 10.5% | 11.5% |
| TVPI | 1.80 | 1.70 |
| Kaplan-Schoar PME | 1.18 | 1.12 |

The investor is worse off by every measure except the one most often quoted.

## 4. The J-curve

![The J-curve](../images/j-curve.png)

Fees and capital go out first and value comes back later. On 300 stylised funds:

- **Cash:** the median fund's cumulative net cash flow bottoms at -82% of commitment in
  year 5 and breaks even in year 9.2.
- **Interim IRR:** deeply negative for the first two years, and not meaningful before the
  fund has invested most of its capital.
- **TVPI:** starts below one, because fees are paid before any value is created.

Young funds should not be ranked on their IRR.

## 5. Public market equivalents

An IRR says nothing about the market a fund lived through. A public market equivalent
replays the fund's flows against an index. With `g_t = I_T / I_t` the growth of the index
from each flow to the valuation date:

| Method | Definition | Assumes |
|---|---|---|
| Kaplan-Schoar (2005) | `(sum D_t g_t + NAV) / (sum C_t g_t)` | a beta of one |
| Direct Alpha (Gredil, Griffiths, Stucke 2014) | `ln(1 + IRR)` of `a_t g_t` and the NAV | a beta of one |
| Long-Nickels (1996) | IRR of the flows with an index account's value as the NAV | an account that can go negative |
| PME+ (Rouvinez 2003) | distributions scaled so the account ends at the NAV | one scaling factor |
| mPME (Cambridge Associates 2013) | the account distributes the fund's share of NAV | a NAV at every date |

**The identities that must hold do.** A fund that *is* the index scores a Kaplan-Schoar
PME of one, a Direct Alpha of zero, and index IRRs equal to its own under all five methods,
to 1e-15, at the end and mid-life with a NAV. Direct Alpha returns the alpha built into a
noise-free beta-one fund exactly, and is positive exactly when the Kaplan-Schoar PME exceeds
one ([ADR 0003](../adr/0003-measures-are-tested-on-funds-whose-truth-is-known.md)).

![Five PMEs of the same funds](../images/pme-family.png)

On one stylised fund a vintage, 1990-2014, each with a true 3% alpha over the S&P 500 and
25% deal risk:

- **One fund is noisy.** Direct Alpha ranges from -5% to 10% (mean 1.8%) around the true 3%.
- **The IRR-based measures agree with each other where they exist.** Long-Nickels has no
  unique answer in 14 vintages of 25, whenever a fund distributes faster than the index
  account can pay.

## 6. A PME assumes a beta of one

![A PME assumes beta is one](../images/pme-beta-bias.png)

Funds with **zero** alpha and betas from 0.6 to 1.8 were measured against the S&P 500. The
index rose over every fund's life since 1990, so the bias always ran the same way:

- **Beta 1.8:** credited with 3 to 15 points a year of "alpha".
- **Beta 0.6:** debited with 1 to 8 points.

A PME counts levered market exposure as skill, and buyout funds are levered. Day 6
estimates fund betas instead of assuming one.

## 7. The benchmark is half the answer

![The benchmark is half the answer](../images/benchmark-choice.png)

The same funds - a 3% alpha over the S&P 500 by construction, without own risk or fees -
were measured against four total-return benchmarks, vintages 2004-2014:

| Benchmark | Average Direct Alpha |
|---|---|
| S&P 500 total return | 3.00% (by construction) |
| Russell 2000 (IWM) | 4.48% |
| small-cap value (VBR) | 4.09% |
| Nasdaq-100 (QQQ) | -1.35%, negative in every vintage |

The measures differ by 6.1 points a year on average. A PME is not a number without its
benchmark ([ADR 0005](../adr/0005-the-pme-is-a-family-reported-with-its-benchmark.md)).

## 8. The IRR measures the market, the PME the manager

![The IRR measures the market](../images/vintage-irr-vs-pme.png)

Forty funds a vintage with identical skill - 3% a year gross over the S&P 500, 1.5% of
commitment a year in fees - were run on the real index path:

- **The median net IRR swings from 1% to 20%** by vintage, following the market.
- **The median net Direct Alpha stays between -2.0% and 0.7%:** the gross 3% less the fee
  drag.

Ranking funds by IRR across vintages ranks the market.

## Validation

Thirteen checks in `pmlab validate`, all passing ([VALIDATION.md](../VALIDATION.md)):

- **Published examples:** XIRR, MIRR and the pump problem.
- **Independent methods:** numpy-financial; polynomial roots; mpmath at 50 digits on
  every root.
- **Norstrom's condition**, tested for what it guarantees.
- **The PME identities and closed forms:** the index-replicating fund, a single deal,
  alpha recovery, sign agreement, and PME+ scaling.

Excel's XIRR is matched to 1.5e-9, which is the limit of Excel's own 1e-8 tolerance.

## Data

Fund-level cash flows are licensed (Burgiss, Preqin, Cambridge Associates) and not used.
Funds here are stylised and labelled as such. Index histories come from Yahoo Finance,
stored locally by `pmlab market fetch` and never committed
([ADR 0004](../adr/0004-market-data-stays-local-and-proprietary-data-is-not-faked.md)).

## References

- Cambridge Associates (2013). Modified public market equivalent (mPME) methodology.
- Gredil, O., Griffiths, B. and Stucke, R. (2014). Benchmarking private equity: the direct
  alpha method. Working paper.
- Harris, R. S., Jenkinson, T. and Kaplan, S. N. (2014). Private equity performance: what do
  we know? *Journal of Finance* 69(5).
- Kaplan, S. N. and Schoar, A. (2005). Private equity performance: returns, persistence, and
  capital flows. *Journal of Finance* 60(4).
- Long, A. M. and Nickels, C. J. (1996). A private investment benchmark. Working paper,
  University of Texas.
- Lorie, J. H. and Savage, L. J. (1955). Three problems in rationing capital. *Journal of
  Business* 28(4).
- Norstrom, C. J. (1972). A sufficient condition for a unique nonnegative internal rate of
  return. *Journal of Financial and Quantitative Analysis* 7(3).
- Rouvinez, C. (2003). Private equity benchmarking with PME+. *Venture Capital Journal*,
  August.
- Sorensen, M. and Jagannathan, R. (2015). The public market equivalent and private equity
  performance. *Financial Analysts Journal* 71(4).
