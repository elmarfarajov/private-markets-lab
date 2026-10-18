# Private Markets Lab

[![CI](https://github.com/elmarfarajov/private-markets-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/elmarfarajov/private-markets-lab/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![Release](https://img.shields.io/badge/release-v0.1.0-e0632b)](https://github.com/elmarfarajov/private-markets-lab/releases)
![mypy](https://img.shields.io/badge/mypy-strict-1b9e77)

**Private equity, private credit, real assets and hedge funds, measured: the cash-flow mathematics,
the fees, the fund models, the risk that smoothed returns hide, and how an endowment allocates to
assets it cannot sell - every measure held to a reference it shares no code with.**

Private markets are where an investor's tools are weakest. There are no daily prices, only
cash flows and a manager's valuation; the standard return measure can have two answers or
none; reported volatility is smoothed away; and the benchmark is a choice. This lab builds
the financial engineering of the asset class over ten days, one part a day.

![Same managers, different decades](docs/images/vintage-irr-vs-pme.png)

---

## Ten days

| Day | Area | Status |
|---|---|---|
| 1 | Cash flows and performance measures: every IRR, MIRR, multiples, the PME family, the J-curve | ✅ v0.1.0 |
| 2 | Fees and waterfalls: European and American carry, hurdles, catch-up, clawback, gross to net | |
| 3 | Fund cash-flow models: Takahashi-Alexander, stochastic models, calibration, vintage dispersion | |
| 4 | Secondaries: pricing LP interests, discounts to NAV, continuation funds, NAV loans | |
| 5 | Smoothed returns and true risk: unsmoothing appraisal returns, real estate indices against REITs | |
| 6 | Risk-adjusted performance: stochastic discount factors, cash-flow betas, listed proxies | |
| 7 | Commitment pacing and liquidity: overcommitment, capital-call stress, the denominator effect | |
| 8 | Portfolio construction with illiquid assets: unsmoothed risk, liquidity constraints, dynamic programming | |
| 9 | Hedge funds and liquid alternatives: factor replication, trend following as an option, tail risk | |
| 10 | The platform: a 30-year endowment simulator, dashboard and reproducible reports | |

The plan and each day's results are in the [roadmap](docs/ROADMAP.md), the charts in the
[gallery](docs/GALLERY.md), the checks in [VALIDATION.md](docs/VALIDATION.md), and the decisions
in the [architecture decision records](docs/adr/README.md). The deal-level LBO model - debt
schedule, value bridge, exit waterfall - is a separate project,
[lbo-returns-engine](https://github.com/elmarfarajov/lbo-returns-engine).

**Day 1: cash flows and performance measures.**

- **Every IRR, not the first one found.** The NPV is scanned in `ln(1 + r)` and every root
  refined. Descartes' rule bounds the count, and `irr` refuses to choose between two answers.
  On random streams, 216 of 606 that met Norstrom's condition also had a negative IRR beside
  the positive one it guarantees.
- **The IRR can be managed.** A subscription line that delays every call by a year lifts a
  fund's IRR from 10.5% to 11.5% while its TVPI falls from 1.80 to 1.70.
- **Five public market equivalents**, held to the identity that a fund replicating the index
  scores a PME of one under all of them, to 1e-15:
  - a PME credits beta as alpha: a zero-alpha fund with beta 1.8 shows 3 to 15 points a year
    against the S&P 500;
  - the benchmark moves the answer by 6 points a year;
  - across 25 vintages, identical managers' IRRs range from 1% to 20% while their Direct Alpha
    stays within three points.

![Five public market equivalents](docs/images/pme-family.png)

The full account is in [cash flows and performance measures](docs/notes/cash-flows-and-performance.md).

## Validation

`pmlab validate` holds every measure to a published value, an independent method, or an identity
that must hold. A selection:

| Check | Reference | Result |
|---|---|---|
| XIRR | Excel's documented example, 0.373362535 | 0.3733625335 (Excel iterates to 1e-8) |
| MIRR | Excel's documented examples, 12.6% and -4.8% | to the printed digit |
| Two IRRs | Lorie and Savage (1955): 25% and 400% | 9e-16 |
| Every root | mpmath polynomial roots at 50 digits, 600 streams | 9e-15; none above Descartes' bound |
| PME identities | a fund that is the index, all five methods | 6.5e-16 |
| Direct Alpha | the alpha built into noise-free funds | 1.4e-17 |

## Quickstart

```bash
git clone https://github.com/elmarfarajov/private-markets-lab.git
cd private-markets-lab
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pmlab validate                 # every check
pmlab market fetch             # index histories for the PMEs (stored locally, never committed)
pmlab irr flows.csv --nav 120 --index sp500   # every IRR, the multiples and the PMEs of your own flows
pmlab gallery                  # every chart
pytest
```

A cash-flow file has two columns, `date` and `amount`, with contributions negative.

## Data

Fund-level cash flows are licensed (Burgiss, Preqin, Cambridge Associates) and are not used or
imitated: funds here are stylised and labelled as such, and published academic figures are cited
as references. Index histories come from Yahoo Finance and stay in the git-ignored `data/`.

## About

Built by Elmar Farajov as an independent research project in quantitative finance, after
[volatility-surface-lab](https://github.com/elmarfarajov/volatility-surface-lab),
[lbo-returns-engine](https://github.com/elmarfarajov/lbo-returns-engine) and
[meridian-investment-platform](https://github.com/elmarfarajov/meridian-investment-platform).
Research and educational use only; not investment advice. Licensed under [MIT](LICENSE).
