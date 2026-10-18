"""Day 1 charts: the IRR's pathologies, how it can be managed, the J-curve, and public market equivalents.

The first three charts need only the code; the PME charts replay funds on real index paths
from the local market history (``pmlab market fetch``) and are skipped where there is none.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from matplotlib.figure import Figure
from numpy.typing import NDArray

from .. import market
from ..cashflows import CashFlows, interim, irr, irr_roots, multiples, npv, sign_changes
from ..pme import direct_alpha, ks_pme, report
from ..synthetic import Fund, FundSpec, Market, gbm_market, market_from_series, simulate_fund
from .style import PALETTE, SERIES, caption, new_figure, tidy, title_block

Array = NDArray[np.float64]
LIFE = 12.0


def irr_pathologies() -> Figure:
    fig = new_figure(14.5, 5.6)
    title_block(
        fig,
        "An IRR is a root, and a cash-flow stream can have none, one or several",
        "The NPV against the discount rate for three streams. Descartes' rule bounds the number of IRRs by the sign changes "
        "in the flows; a stream that pays out early and calls capital late - a real-estate fund refinancing and later repaying "
        "its loan - has two, and no single 'return' describes it.",
    )
    cases = [
        ("Lorie and Savage's pump (1955)", [0.0, 1.0, 2.0], [-1600.0, 10000.0, -10000.0], (-0.5, 5.0)),
        ("refinance in year 2, repay in year 6", [0.0, 2.0, 6.0], [-100.0, 190.0, -100.0], (-0.02, 0.3)),
        ("no IRR: the NPV never reaches zero", [0.0, 1.0, 2.0], [100.0, -200.0, 110.0], (-0.2, 1.0)),
    ]
    for k, (name, t, a, (lo, hi)) in enumerate(cases):
        ax = fig.add_axes((0.05 + 0.325 * k, 0.15, 0.27, 0.6))
        r = np.linspace(lo, hi, 600)
        values = npv(r, t, a)
        ax.plot(100 * r, values, color=SERIES[k], lw=2.0)
        ax.axhline(0, color=PALETTE["ink"], lw=0.7)
        roots = irr_roots(t, a, lo=lo, hi=hi)
        for q in roots:
            ax.plot(100 * q, 0, "o", color=PALETTE["accent"], ms=7, zorder=3)
            ax.annotate(f"{100 * q:.1f}%", (100 * q, 0), xytext=(6, 8), textcoords="offset points", fontsize=9)
        flows = ", ".join(f"{x:+,.0f}" for x in a)
        tidy(ax, title=name, xlabel="discount rate (%)", ylabel="NPV" if k == 0 else None)
        ax.text(
            0.03, 0.04, f"flows {flows}\nsign changes {sign_changes(a)}, IRRs {len(roots)}", transform=ax.transAxes, fontsize=8
        )
    caption(
        fig,
        "IRRs found by scanning the NPV on a grid even in ln(1 + r) and refining each sign change; Descartes bounds the count.",
    )
    return fig


def _subscription_line(f: Fund, delay: float, rate: float) -> tuple[Array, Array]:
    """Every call bridged by a credit line for ``delay`` years: called later, with the line's interest added."""
    t, a = f.times.copy(), f.amounts.copy()
    calls = a < 0
    shifted_t = np.where(calls, t + delay, t)
    shifted_a = np.where(calls, a * (1 + rate) ** delay, a)
    order = np.argsort(shifted_t, kind="stable")
    return shifted_t[order], shifted_a[order]


def irr_manipulation() -> Figure:
    m = gbm_market(16.0, seed=11)
    f = simulate_fund(m, FundSpec(alpha=0.03, seed=5))
    delays = np.linspace(0.0, 1.0, 13)
    rates = (0.03, 0.06)
    fig = new_figure(14.0, 5.8)
    base_irr = irr(f.times, f.amounts)
    t1, a1 = _subscription_line(f, 1.0, 0.06)
    title_block(
        fig,
        "Borrowing to delay capital calls raises the IRR and lowers the money multiple",
        f"The same fund, its calls bridged by a subscription credit line. Delaying every call by a year lifts the IRR from "
        f"{100 * base_irr:.1f}% to {100 * irr(t1, a1):.1f}% with the line at 6% - while the investor gets back less per dollar "
        "paid in, because the interest is paid out of the same profits. The IRR rewards the timing, not the investment.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.4, 0.6))
    ax2 = fig.add_axes((0.56, 0.15, 0.4, 0.6))
    for k, rate in enumerate(rates):
        irrs, tvpis, pmes = [], [], []
        for d in delays:
            t, a = _subscription_line(f, float(d), rate)
            irrs.append(irr(t, a))
            tvpis.append(multiples(CashFlows(t, a)).tvpi)
            pmes.append(ks_pme(a, m.level(t), 0.0, float(m.level(t[-1]))))
        ax.plot(12 * delays, 100 * np.array(irrs), "o-", ms=3.5, color=SERIES[k], lw=1.8, label=f"IRR, line at {rate:.0%}")
        ax2.plot(12 * delays, tvpis, "o-", ms=3.5, color=SERIES[k], lw=1.8, label=f"TVPI, line at {rate:.0%}")
        ax2.plot(12 * delays, pmes, "s--", ms=3, color=SERIES[k], lw=1.2, label=f"Kaplan-Schoar PME, line at {rate:.0%}")
    tidy(ax, title="internal rate of return", xlabel="months each call is delayed", ylabel="% a year")
    ax.legend(fontsize=8)
    tidy(ax2, title="what the investor actually gets per dollar", xlabel="months each call is delayed", ylabel="multiple")
    ax2.legend(fontsize=8)
    caption(
        fig,
        "Stylised fund: 15 deals, alpha 3% a year to a simulated index (7% drift, 16% volatility), "
        "no fees; the line's interest is called with the capital.",
    )
    return fig


@lru_cache(maxsize=1)
def _population(n: int = 300) -> list[tuple[Fund, Market]]:
    rng = np.random.default_rng(21)
    out = []
    for i in range(n):
        m = gbm_market(LIFE + 1.0, mu=0.07, sigma=0.16, seed=1000 + i)
        spec = FundSpec(alpha=float(rng.normal(0.02, 0.03)), idio=0.25, fee=0.015, seed=2000 + i)
        out.append((simulate_fund(m, spec), m))
    return out


def j_curve() -> Figure:
    funds = _population()
    quarter = np.arange(0.0, LIFE + 1e-9, 0.25)
    net, tvpi, dpi, rates = [], [], [], []
    for f, _ in funds:
        idx = np.searchsorted(f.times, quarter, side="right") - 1
        path = interim(f.times, f.amounts, f.navs, at=np.unique(np.clip(idx, 0, None)))
        net.append(path["net"][idx] / 100.0)
        tvpi.append(path["tvpi"][idx])
        dpi.append(path["dpi"][idx])
        rates.append(path["irr"][idx])
    net_a, tvpi_a, dpi_a, irr_a = (np.array(x) for x in (net, tvpi, dpi, rates))
    fig = new_figure(14.5, 5.8)
    trough = np.nanmedian(net_a, axis=0)
    title_block(
        fig,
        "The J-curve: fees and capital go out first, value comes back later",
        f"300 stylised funds on simulated markets. The median fund's net cash position bottoms at "
        f"{100 * float(np.min(trough)):.0f}% of "
        f"commitment in year {quarter[np.argmin(trough)]:.1f} and breaks even in year "
        f"{quarter[np.argmax(trough >= 0)]:.1f}. The interim IRR is deeply negative early and meaningless for the first "
        "years - the reason fund reports quote multiples, and the reason young funds should not be ranked.",
    )
    panels = [
        (net_a * 100, "cumulative net cash flow", "% of commitment"),
        (irr_a * 100, "interim IRR (NAV as a final distribution)", "% a year"),
        (tvpi_a, "TVPI and DPI", "multiple of paid-in"),
    ]
    for k, (data, name, unit) in enumerate(panels):
        ax = fig.add_axes((0.05 + 0.325 * k, 0.15, 0.27, 0.6))
        lo, mid, hi = (np.nanpercentile(data, q, axis=0) for q in (10, 50, 90))
        ax.fill_between(quarter, lo, hi, color=PALETTE["band"], label="10th-90th percentile")
        ax.plot(quarter, mid, color=SERIES[0], lw=2.0, label="median")
        if k == 2:
            d_lo, d_mid, d_hi = (np.nanpercentile(dpi_a, q, axis=0) for q in (10, 50, 90))
            ax.plot(quarter, d_mid, color=SERIES[1], lw=1.8, label="DPI, median")
            ax.axhline(1.0, color=PALETTE["muted"], lw=0.8, ls="--")
        if k == 1:
            ax.set_ylim(-60, 40)
        ax.axhline(0.0, color=PALETTE["ink"], lw=0.6)
        tidy(ax, title=name, xlabel="fund year", ylabel=unit)
        ax.legend(fontsize=7.5, loc="lower right" if k != 1 else "lower right")
    caption(
        fig,
        "Each fund: 15 deals over five years, alpha drawn N(2%, 3%), deal volatility 25%, fees 1.5% "
        "of commitment a year; index 7% drift, 16% volatility.",
    )
    return fig


# ---------------------------------------------------------------- real index paths


@lru_cache(maxsize=4)
def _real(name: str = "sp500") -> tuple[Market, float]:
    """The index as a monthly Market, and the calendar year of its first month."""
    series = market.load(name)
    first = series.index[0]
    return market_from_series(series), first.year + (first.month - 1) / 12.0


def _vintage(m: Market, start_year: float, vintage: float) -> Market:
    return m.window(vintage - start_year, LIFE)


def pme_family() -> Figure:
    m, start = _real("sp500")
    vintages = np.arange(1990, 2015)
    rows = []
    for v in vintages:
        window = _vintage(m, start, float(v))
        f = simulate_fund(window, FundSpec(alpha=0.03, beta=1.0, idio=0.25, seed=int(v)))
        rows.append(report(f.times, f.amounts, f.index, 0.0, f.navs))
    fig = new_figure(14.5, 6.0)
    da = np.array([r.direct_alpha for r in rows])
    title_block(
        fig,
        "Five public market equivalents of the same funds",
        "One stylised buyout fund a year, 1990-2014, each earning 3% a year over the S&P 500 (total return) with 25% deal "
        f"risk, replayed against the index. One fund a vintage is noisy: Direct Alpha scatters from {100 * da.min():.0f}% to "
        f"{100 * da.max():.0f}% around the true 3% (mean {100 * da.mean():.1f}%). The IRR-based "
        f"measures agree with each other where "
        "they exist - but Long-Nickels has no unique answer whenever a fund distributes faster than the index account can pay.",
    )
    ax = fig.add_axes((0.05, 0.15, 0.42, 0.6))
    fund = np.array([r.fund_irr for r in rows])
    ax.plot(vintages, 100 * fund, "o-", color=PALETTE["ink"], lw=1.6, ms=3.5, label="fund IRR")
    ax.plot(
        vintages,
        100 * np.array([r.ln_irr for r in rows]),
        "s-",
        color=PALETTE["slate"],
        lw=1.2,
        ms=3,
        label="Long-Nickels index IRR",
    )
    ax.plot(vintages, 100 * np.array([r.pme_plus_irr for r in rows]), "^-", color=SERIES[1], lw=1.2, ms=3, label="PME+ index IRR")
    ax.plot(vintages, 100 * np.array([r.mpme_irr for r in rows]), "v-", color=SERIES[2], lw=1.2, ms=3, label="mPME index IRR")
    bad = [v for v, r in zip(vintages, rows, strict=True) if np.isnan(r.ln_irr)]
    for v in bad:
        ax.axvline(float(v), color=PALETTE["red"], lw=0.6, alpha=0.4)
    tidy(ax, title="fund IRR and each method's index IRR", xlabel="vintage", ylabel="% a year")
    ax.legend(fontsize=7.5)
    ax2 = fig.add_axes((0.56, 0.15, 0.4, 0.6))
    ax2.plot(vintages, 100 * da, "o-", color=SERIES[0], lw=1.8, ms=3.5, label="Direct Alpha")
    ax2.axhline(3.0, color=PALETTE["accent"], lw=1.2, ls="--", label="true alpha, 3%")
    ax2b = ax2.twinx()
    ax2b.plot(vintages, [r.ks_pme for r in rows], "s-", color=SERIES[1], lw=1.2, ms=3, label="Kaplan-Schoar PME (right)")
    ax2b.set_ylabel("Kaplan-Schoar PME")
    ax2b.spines["right"].set_visible(True)
    tidy(ax2, title="Direct Alpha and the Kaplan-Schoar PME", xlabel="vintage", ylabel="% a year")
    lines = ax2.get_legend_handles_labels()
    more = ax2b.get_legend_handles_labels()
    ax2.legend(lines[0] + more[0], lines[1] + more[1], fontsize=7.5, loc="lower right")
    caption(
        fig,
        f"Red lines: vintages where the Long-Nickels index account goes negative and its IRR is not "
        f"unique ({len(bad)} of {len(vintages)}).",
    )
    return fig


def pme_beta_bias() -> Figure:
    m, start = _real("sp500")
    vintages = np.arange(1990, 2015)
    betas = (0.6, 1.0, 1.4, 1.8)
    colours = (PALETTE["blue"], PALETTE["slate"], PALETTE["violet"], PALETTE["red"])
    results = {}
    for b in betas:
        da, ks = [], []
        for v in vintages:
            f = simulate_fund(_vintage(m, start, float(v)), FundSpec(alpha=0.0, beta=b, idio=0.0, seed=int(v)))
            da.append(direct_alpha(f.times, f.amounts, f.index))
            ks.append(ks_pme(f.amounts, f.index))
        results[b] = (100 * np.array(da), np.array(ks))
    hi, lo = results[betas[-1]][0], results[betas[0]][0]
    fig = new_figure(14.0, 5.8)
    title_block(
        fig,
        "A PME assumes the fund's beta is one, and alpha absorbs the rest",
        f"Funds with no alpha at all and betas from 0.6 to 1.8 to the S&P 500. In every vintage since 1990 the index rose over "
        f"the fund's life, so the beta-1.8 fund is credited with {hi.min():.0f} to {hi.max():.0f} points a year of 'alpha' and "
        f"the beta-0.6 fund with {lo.max():.0f} to {lo.min():.0f}. A PME counts levered market exposure as skill - and buyout "
        "funds are levered.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.4, 0.6))
    ax2 = fig.add_axes((0.56, 0.15, 0.4, 0.6))
    for b, colour in zip(betas, colours, strict=True):
        da_b, ks_b = results[b]
        ax.plot(vintages, da_b, "o-", ms=3, lw=1.6, color=colour, label=f"beta {b}")
        ax2.plot(vintages, ks_b, "o-", ms=3, lw=1.6, color=colour, label=f"beta {b}")
    ax.axhline(0.0, color=PALETTE["accent"], lw=1.2, ls="--", label="true alpha, 0")
    ax2.axhline(1.0, color=PALETTE["accent"], lw=1.2, ls="--", label="true PME, 1")
    tidy(ax, title="Direct Alpha of funds with zero alpha", xlabel="vintage", ylabel="% a year")
    tidy(ax2, title="Kaplan-Schoar PME", xlabel="vintage")
    ax.legend(fontsize=8)
    ax2.legend(fontsize=8)
    caption(
        fig,
        "Deal values follow (I_t / I_entry)^beta with no own risk or fees; a beta above one adds "
        "Jensen convexity, so 'zero alpha' is relative to the levered index.",
    )
    return fig


def benchmark_choice() -> Figure:
    names = ("sp500", "small", "nasdaq", "value")
    paths = {n: _real(n) for n in names}
    vintages = np.arange(2004, 2015)
    fig = new_figure(14.0, 5.8)
    sp, sp_start = paths["sp500"]
    results: dict[str, list[float]] = {n: [] for n in names}
    for v in vintages:
        f = simulate_fund(_vintage(sp, sp_start, float(v)), FundSpec(alpha=0.03, beta=1.0, idio=0.0, seed=int(v)))
        for n in names:
            m, start = paths[n]
            window = _vintage(m, start, float(v))
            levels = window.level(f.times)
            results[n].append(direct_alpha(f.times, f.amounts, levels))
    spread = np.array([max(results[n][i] for n in names) - min(results[n][i] for n in names) for i in range(vintages.size)])
    title_block(
        fig,
        "The benchmark is half the answer",
        "The same funds - 3% a year over the S&P 500 by construction - measured against four total-return benchmarks. "
        f"Their Direct Alpha differs by {100 * spread.mean():.1f} points a year on average across vintages: against the "
        f"Nasdaq-100 these funds show negative alpha in every vintage (worst {100 * min(results['nasdaq']):.1f}%), against small "
        "caps they mostly look better than against the S&P. A PME without its benchmark is not a number.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.55, 0.6))
    colours = (PALETTE["blue"], PALETTE["green"], PALETTE["violet"], PALETTE["slate"])
    for n, colour in zip(names, colours, strict=True):
        ax.plot(vintages, 100 * np.array(results[n]), "o-", ms=3.5, lw=1.8, color=colour, label=market.LABELS[n])
    ax.axhline(3.0, color=PALETTE["accent"], lw=1.2, ls="--", label="alpha over the S&P 500, 3%")
    tidy(ax, title="Direct Alpha by benchmark", xlabel="vintage", ylabel="% a year")
    ax.legend(fontsize=8)
    ax2 = fig.add_axes((0.7, 0.15, 0.27, 0.6))
    means = [100 * float(np.mean(results[n])) for n in names]
    ax2.barh([market.LABELS[n] for n in names], means, color=colours)
    ax2.axvline(3.0, color=PALETTE["accent"], lw=1.2, ls="--")
    ax2.invert_yaxis()
    tidy(ax2, title="average over vintages", xlabel="% a year")
    caption(
        fig,
        "Funds without own risk or fees, so the differences are the benchmarks'; ETFs adjusted for "
        "distributions carry their small expense ratios.",
    )
    return fig


def vintage_irr_vs_pme() -> Figure:
    m, start = _real("sp500")
    vintages = np.arange(1990, 2015)
    per = 40
    irr_q, da_q = [], []
    for v in vintages:
        window = _vintage(m, start, float(v))
        irrs, das = [], []
        for s in range(per):
            f = simulate_fund(window, FundSpec(alpha=0.03, idio=0.25, fee=0.015, seed=int(v) * 100 + s))
            irrs.append(irr(f.times, f.amounts))
            das.append(direct_alpha(f.times, f.amounts, f.index))
        irr_q.append(np.percentile(irrs, (25, 50, 75)))
        da_q.append(np.percentile(das, (25, 50, 75)))
    irr_a, da_a = 100 * np.array(irr_q), 100 * np.array(da_q)
    irr_lo, irr_hi = float(np.min(irr_a[:, 1])), float(np.max(irr_a[:, 1]))
    da_lo, da_hi = float(np.min(da_a[:, 1])), float(np.max(da_a[:, 1]))
    fig = new_figure(14.0, 5.8)
    title_block(
        fig,
        "Same managers, different decades: the IRR measures the market, the PME the manager",
        "Forty funds a vintage with identical skill - 3% a year over the S&P 500 gross, 1.5% fees - on the real index path. "
        f"The median IRR ranges from {irr_lo:.0f}% to {irr_hi:.0f}% by vintage; the median Direct Alpha "
        f"stays between {da_lo:.1f}% and {da_hi:.1f}%. Ranking funds by IRR across vintages ranks the market.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.88, 0.6))
    ax.fill_between(vintages, irr_a[:, 0], irr_a[:, 2], color=PALETTE["band"])
    ax.plot(vintages, irr_a[:, 1], "o-", color=PALETTE["ink"], lw=1.8, ms=3.5, label="net IRR, median and interquartile range")
    ax.fill_between(vintages, da_a[:, 0], da_a[:, 2], color=SERIES[0], alpha=0.15)
    ax.plot(vintages, da_a[:, 1], "o-", color=SERIES[0], lw=1.8, ms=3.5, label="net Direct Alpha, median and interquartile range")
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    tidy(ax, xlabel="vintage", ylabel="% a year")
    ax.legend(fontsize=8.5)
    caption(
        fig,
        "Each fund: 15 deals, 25% deal volatility, fees 1.5% of commitment a year for twelve years; "
        "the net alpha is the gross 3% less the fee drag.",
    )
    return fig
