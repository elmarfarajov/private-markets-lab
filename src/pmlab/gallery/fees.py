"""Day 2 charts: fees, waterfalls, and carried interest as an option.

Every chart is computed from the waterfall engine and the option formulas; no market data is
needed. Funds are stylised - fifteen deals bought over five years and held three to seven - and
the deal model's parameters are stated on each chart. Every number in a subtitle is computed.
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from ..carry import Valuation, break_even_alpha, carry_closed_form, carry_payoff, single_deal_mc, strikes, value
from ..waterfall import DealModel, Shape, Terms, gross_to_net, run, schedule, standard_shape
from .style import PALETTE, SERIES, caption, new_figure, tidy, title_block

R = 0.04  # risk-free rate a year, continuously compounded
MODEL = DealModel(mu=R, sigma=0.40, rho=0.30, seed=11)
BASE = Terms()
TERM_SETS: list[tuple[str, Terms]] = [
    ("2 and 20, 8% hurdle, full catch-up (European)", BASE),
    ("2 and 20, American, full clawback", Terms(waterfall="american")),
    ("2 and 20, no hurdle", Terms(hurdle=0.0)),
    ("2 and 20, 8% hurdle, no catch-up", Terms(catch_up=0.0)),
    ("1.5 and 15, 8% hurdle", Terms(fee=0.015, carry=0.15)),
    ("2.5 and 30 (top venture)", Terms(fee=0.025, carry=0.30, hurdle=0.0)),
]
SIMS = 20000  # simulated funds behind each Monte Carlo chart; the tests lower it
STRUCT = "Stylised fund: 15 deals bought evenly over five years, held three to seven, commitment 100."


@lru_cache(maxsize=1)
def _shape() -> Shape:
    return standard_shape()


@lru_cache(maxsize=64)
def _value(terms: Terms, sigma: float = 0.40, rho: float = 0.30, alpha: float = 0.0, half: bool = False) -> Valuation:
    return value(_shape(), terms, replace(MODEL, sigma=sigma, rho=rho), R, SIMS // 2 if half else SIMS, alpha)


# ------------------------------------------------------------------ 1. the waterfall's tiers


def waterfall_tiers() -> Figure:
    k, years = 100.0, 5.0
    v = np.linspace(0.0, 400.0, 801)
    h, v_star = strikes(k, years, BASE)
    assert v_star is not None
    gp = carry_payoff(v, k, years, BASE)
    lp = v - gp
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Four tiers decide who gets each pound",
        f"One investment of 100 held five years, no fees. LPs take everything up to {h:.0f} - their capital and an 8% preferred "
        f"return compounded. The GP then takes every pound until it holds 20% of the profit, at proceeds of {v_star:.0f}: the "
        "catch-up. Above that the split is 80/20. With a full catch-up the hurdle delays the carry but does not reduce it.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.fill_between(v, 0, lp, color=PALETTE["blue"], alpha=0.75, label="to the LPs")
    ax.fill_between(v, lp, v, color=PALETTE["accent"], alpha=0.85, label="to the GP (carried interest)")
    for x, name in [(k, "capital"), (h, "hurdle"), (v_star, "catch-up ends")]:
        ax.axvline(x, color=PALETTE["ink"], lw=0.8, ls="--")
        ax.text(x + 3, 375, name, fontsize=8, color=PALETTE["muted"], rotation=90, va="top")
    tidy(ax, title="Proceeds split, European waterfall", xlabel="proceeds of the fund", ylabel="amount received")
    ax.legend(fontsize=8.5, loc="lower right")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    profit = np.maximum(v - k, 1e-9)
    for terms, label, colour in [
        (BASE, "full catch-up", PALETTE["accent"]),
        (Terms(catch_up=0.8), "80% catch-up", PALETTE["violet"]),
        (Terms(catch_up=0.0), "no catch-up", PALETTE["blue"]),
        (Terms(hurdle=0.0), "no hurdle", PALETTE["slate"]),
    ]:
        share = carry_payoff(v, k, years, terms) / profit
        bx.plot(v[v > k], 100 * share[v > k], color=colour, lw=1.8, label=label)
    bx.axhline(20, color=PALETTE["ink"], lw=0.7, ls=":")
    tidy(bx, title="The GP's share of the profit", xlabel="proceeds of the fund", ylabel="carry as % of profit")
    bx.legend(fontsize=8.5, loc="lower right")
    caption(fig, "8% hurdle compounded annually on capital outstanding; 20% carry. The tiers are computed by pmlab.waterfall.")
    return fig


# ------------------------------------------------------------------ 2. carry as options


def carry_as_options() -> Figure:
    k, years = 100.0, 5.0
    h, v_star = strikes(k, years, BASE)
    assert v_star is not None
    v = np.linspace(0.0, 400.0, 801)
    long_leg = BASE.catch_up * np.maximum(v - h, 0.0)
    short_leg = -(BASE.catch_up - BASE.carry) * np.maximum(v - v_star, 0.0)
    fig = new_figure(14.5, 6.2)
    sig = [0.2, 0.4, 0.6]
    vals = {s: carry_closed_form(k, years, R, s, BASE) for s in sig}
    title_block(
        fig,
        "Carried interest is a call spread written by the investors",
        f"Left: the carry on one investment is one call struck at the hurdle ({h:.0f}) less 0.8 of a call struck where the "
        f"catch-up ends ({v_star:.0f}). Right: its value today with five years to run, by Black-Scholes. A fairly priced fund "
        f"(proceeds worth 100 today) gives the GP carry worth {vals[0.2]:.1f}, {vals[0.4]:.1f} and {vals[0.6]:.1f} at volatilities "
        "of 20%, 40% and 60%: the riskier the fund, the more the option is worth.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.plot(v, long_leg, color=PALETTE["blue"], lw=1.3, ls="--", label=f"1 call struck at {h:.0f}")
    ax.plot(v, short_leg, color=PALETTE["violet"], lw=1.3, ls="--", label=f"-0.8 call struck at {v_star:.0f}")
    ax.plot(v, long_leg + short_leg, color=PALETTE["accent"], lw=2.4, label="carry payoff")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, title="Payoff at exit", xlabel="proceeds at exit", ylabel="carry")
    ax.legend(fontsize=8.5, loc="upper left")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    v0 = np.linspace(20, 300, 141)
    for s, colour in zip(sig, SERIES, strict=False):
        # value of the carry on a fund worth v0 today whose capital was 100
        pv = [_carry_value_at(x, k, years, s) for x in v0]
        bx.plot(v0, pv, color=colour, lw=1.8, label=f"volatility {100 * s:.0f}%")
    bx.plot(
        v0,
        carry_payoff(v0 * np.exp(R * years), k, years, BASE) * np.exp(-R * years),
        color=PALETTE["ink"],
        lw=1,
        ls=":",
        label="intrinsic (no volatility)",
    )
    bx.axvline(k, color=PALETTE["muted"], lw=0.8, ls="--")
    tidy(
        bx,
        title="Value with five years to run",
        xlabel="value of the fund's assets today (capital 100)",
        ylabel="present value of carry",
    )
    bx.legend(fontsize=8.5, loc="upper left")
    caption(
        fig, f"Black (1976) on lognormal proceeds, risk-free rate {100 * R:.0f}% a year; 8% hurdle, full catch-up, 20% carry."
    )
    return fig


def _carry_value_at(v0: float, capital: float, years: float, sigma: float, terms: Terms = BASE) -> float:
    from ..carry import black_call

    h, v_star = strikes(capital, years, terms)
    fwd = v0 * np.exp(R * years)
    disc = float(np.exp(-R * years))
    if v_star is None:
        return terms.carry * black_call(fwd, h, years, sigma, disc)
    return terms.catch_up * black_call(fwd, h, years, sigma, disc) - (terms.catch_up - terms.carry) * black_call(
        fwd, v_star, years, sigma, disc
    )


# ------------------------------------------------------------------ 3. gross to net


@lru_cache(maxsize=1)
def _g2n() -> dict[str, pd.DataFrame]:
    grid = np.linspace(0.0, 0.30, 31)
    return {label: gross_to_net(_shape(), t, grid) for label, t in TERM_SETS}


def gross_to_net_chart() -> Figure:
    data = _g2n()
    base = data[TERM_SETS[0][0]]
    at15 = base.iloc[15]
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "From gross to net: what the investors keep",
        f"Net IRR against gross IRR when every deal earns the same return. Under 2 and 20 with an 8% hurdle, a 15% gross IRR "
        f"becomes {100 * at15['net_irr']:.1f}% net, and a {at15['gross_tvpi']:.2f}x gross multiple {at15['net_tvpi']:.2f}x; the gap is "
        f"{100 * (at15['gross_irr'] - at15['net_irr']):.1f} points. At low returns the fee is most of the gap, at high returns "
        "the carry: the spread is never below the fee drag.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    colours = [PALETTE["accent"], PALETTE["red"], PALETTE["slate"], PALETTE["blue"], PALETTE["green"], PALETTE["violet"]]
    for (label, _), colour in zip(TERM_SETS, colours, strict=True):
        d = data[label]
        ax.plot(100 * d["gross_irr"], 100 * d["net_irr"], color=colour, lw=1.7, label=label)
        bx.plot(100 * d["gross_irr"], 100 * (d["gross_irr"] - d["net_irr"]), color=colour, lw=1.7)
    ax.plot([0, 30], [0, 30], color=PALETTE["ink"], lw=0.8, ls=":", label="no fees")
    tidy(ax, title="Net IRR", xlabel="gross IRR, %", ylabel="net IRR to LPs, %")
    ax.legend(fontsize=7.5, loc="upper left")
    tidy(bx, title="Gross minus net", xlabel="gross IRR, %", ylabel="percentage points")
    caption(
        fig, STRUCT + " Fees quarterly in advance: 2% of commitments for five years, then 2% of the cost of deals still held."
    )
    return fig


def gp_share_chart() -> Figure:
    data = _g2n()
    fig = new_figure(14.5, 6.0)
    base = data[TERM_SETS[0][0]]
    row = base.iloc[(base["gross_tvpi"] - 1.5).abs().argmin()]
    row2 = base.iloc[(base["gross_tvpi"] - 2.5).abs().argmin()]
    title_block(
        fig,
        "'Two and twenty' takes far more than twenty per cent of the profit",
        f"The GP's take - fees plus carry - as a share of the deals' gross profit. Under 2 and 20 the GP takes "
        f"{100 * row['gp_share']:.0f}% of the profit of a fund returning {row['gross_tvpi']:.1f}x gross and "
        f"{100 * row2['gp_share']:.0f}% of one returning {row2['gross_tvpi']:.1f}x; below about 1.5x the fees alone exceed a third "
        "of the profit. The headline 20% is only the limit for very successful funds.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    colours = [PALETTE["accent"], PALETTE["red"], PALETTE["slate"], PALETTE["blue"], PALETTE["green"], PALETTE["violet"]]
    for (label, _), colour in zip(TERM_SETS, colours, strict=True):
        d = data[label]
        ok = d["gross_tvpi"] > 1.2
        ax.plot(d.loc[ok, "gross_tvpi"], 100 * d.loc[ok, "gp_share"], color=colour, lw=1.8, label=label)
    ax.axhline(20, color=PALETTE["ink"], lw=0.8, ls=":")
    ax.text(1.22, 17, "headline carry 20%", fontsize=8, color=PALETTE["muted"])
    ax.set_ylim(0, 80)
    tidy(ax, xlabel="gross multiple of the deals (TVPI)", ylabel="GP take, % of gross profit")
    ax.legend(fontsize=8, ncol=2, loc="upper right")
    caption(fig, STRUCT + " Every deal earns the same gross return; take = (fees + carry kept) / (proceeds - deal costs).")
    return fig


# ------------------------------------------------------------------ 5. fee schedules


def fee_schedules() -> Figure:
    shape = _shape()
    variants = [
        ("2% on commitments for life", Terms(post_basis="committed")),
        ("2% on commitments, then on invested cost", BASE),
        ("2% then 1.5% on invested cost", Terms(post_fee=0.015)),
        ("1.5% then 1% on invested cost", Terms(fee=0.015, post_fee=0.01)),
    ]
    fig = new_figure(14.5, 6.0)
    totals = {label: schedule(shape, t) for label, t in variants}
    life = totals[variants[0][0]]
    std = totals[variants[1][0]]
    title_block(
        fig,
        "Fees come out of the commitment: a fund charging 2% invests only about 85%",
        f"Quarterly management fees over the fund's life. Charged on commitments for life, fees total {life.fees.sum():.1f} of "
        f"every 100 and only {100 * life.scale:.0f} reaches the deals; switching to the cost of deals still held after year five "
        f"cuts fees to {std.fees.sum():.1f} and lets {100 * std.scale:.0f} be invested. Every pound of fee is a pound that never "
        "compounds.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    colours = [PALETTE["red"], PALETTE["accent"], PALETTE["blue"], PALETTE["green"]]
    for (label, _), colour in zip(variants, colours, strict=True):
        s = totals[label]
        k = s.fees > 0
        ax.step(s.times[k], s.fees[k], where="post", color=colour, lw=1.6, label=label)
    ax.axvline(shape.invest_years, color=PALETTE["muted"], ls="--", lw=0.8)
    ax.text(
        shape.invest_years + 0.1, ax.get_ylim()[1] * 0.95, "investment period ends", fontsize=8, color=PALETTE["muted"], va="top"
    )
    tidy(ax, title="Fee per quarter", xlabel="years since first close", ylabel="per 100 committed")
    ax.legend(fontsize=8, loc="lower left")
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    y = np.arange(len(variants))[::-1]
    fees_tot = [totals[label].fees.sum() for label, _ in variants]
    bx.barh(y, fees_tot, color=colours, height=0.6)
    for yi, f, (label, _) in zip(y, fees_tot, variants, strict=True):
        bx.text(f + 0.3, yi, f"{f:.1f} fees, {100 * totals[label].scale:.0f} invested", va="center", fontsize=8)
    bx.set_yticks([])
    bx.set_xlim(0, max(fees_tot) * 1.9)
    tidy(bx, title="Total over the life", xlabel="fees per 100 committed")
    caption(fig, STRUCT + " Fees quarterly in advance while any deal is held; invested share solved so that calls add up to 100.")
    return fig


# ------------------------------------------------------------------ 6. European against American on one fund


@lru_cache(maxsize=1)
def _story_fund() -> np.ndarray:
    """A fund whose early deals win and late deals lose: the case where the waterfalls differ most."""
    shape = _shape()
    years = shape.exits - shape.entries
    gross = np.where(np.arange(shape.deals) < 7, 0.30, -0.08)
    return np.array([(1 + gross) ** years])


def european_vs_american() -> Figure:
    shape = _shape()
    m = _story_fund()
    eu = run(shape, m, BASE)
    am = run(shape, m, Terms(waterfall="american"))
    am_half = run(shape, m, Terms(waterfall="american", clawback_recovery=0.5))
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Deal by deal, the GP is paid on the winners before the losers are known",
        f"One fund whose first seven deals return 30% a year and last eight lose 8%. The American waterfall pays "
        f"{am.carry.sum():.1f} of carry as the winners exit; the European pays {eu.carry.sum():.1f}, and only once the whole "
        f"fund has returned capital and hurdle. At the end the clawback returns {am.clawback[0]:.1f} - if it can be recovered "
        f"in full. At 50% recovery the GP keeps {am_half.carry_kept[0]:.1f} against the {eu.carry_kept[0]:.1f} the fund's terms allow.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    for out, label, colour, ls in [
        (eu, "European (whole fund)", PALETTE["blue"], "-"),
        (am, "American (deal by deal)", PALETTE["accent"], "-"),
    ]:
        cum = np.cumsum(out.carry[0])
        ax.step(out.times, cum, where="post", color=colour, lw=2, ls=ls, label=label)
    end = am.times[-1]
    ax.annotate(
        "",
        xy=(end, am.carry_kept[0]),
        xytext=(end, am.carry.sum()),
        arrowprops={"arrowstyle": "->", "color": PALETTE["red"], "lw": 1.5},
    )
    ax.text(
        end - 0.2,
        (am.carry_kept[0] + am.carry.sum()) / 2,
        f"clawback\n{am.clawback[0]:.1f}",
        ha="right",
        fontsize=8,
        color=PALETTE["red"],
    )
    tidy(ax, title="Cumulative carry paid", xlabel="years since first close", ylabel="per 100 committed")
    ax.legend(fontsize=8.5, loc="upper left")
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    labels = ["European", "American,\nfull clawback", "American,\n50% recovered", "American,\nno clawback"]
    am_none = run(shape, m, Terms(waterfall="american", clawback=False))
    kept = [eu.carry_kept[0], am.carry_kept[0], am_half.carry_kept[0], am_none.carry_kept[0]]
    bx.bar(range(4), kept, color=[PALETTE["blue"], PALETTE["accent"], PALETTE["accent"], PALETTE["red"]], alpha=0.9)
    for i, kv in enumerate(kept):
        bx.text(i, kv + 0.2, f"{kv:.1f}", ha="center", fontsize=8.5)
    bx.set_xticks(range(4))
    bx.set_xticklabels(labels, fontsize=7.5)
    tidy(bx, title="Carry the GP keeps", ylabel="per 100 committed")
    caption(
        fig,
        STRUCT
        + " 2 and 20, 8% hurdle, full catch-up. The clawback limits carry to 20% of profit and to what leaves LPs their hurdle.",
    )
    return fig


# ------------------------------------------------------------------ 7. the clawback across many funds


def clawback_distribution() -> Figure:
    shape = _shape()
    m = replace(MODEL, mu=0.12).draw(shape, SIMS)
    am = run(shape, m, Terms(waterfall="american"))
    trig = am.clawback > 1e-9
    paid = am.carry.sum(axis=1)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Under an American waterfall the clawback is the rule, not the exception",
        f"{SIMS:,} simulated funds with deals expected to earn 12% a year (volatility 40%, correlation 0.3). The GP is overpaid "
        f"in {100 * trig.mean():.0f}% of funds; the average excess is {am.clawback[trig].mean():.1f} per 100 committed, "
        f"{100 * am.clawback.sum() / paid.sum():.0f}% of all carry paid. Every point of that which cannot be recovered - carry "
        "already taxed, partners gone - is a transfer from LPs to the GP.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.hist(am.clawback[trig], bins=60, color=PALETTE["violet"], alpha=0.85)
    tidy(ax, title="Clawback owed, where any", xlabel="per 100 committed", ylabel="funds")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    gt, _ = am.tvpi()
    order = np.argsort(gt)
    bins = np.quantile(gt, np.linspace(0, 1, 11))
    idx = np.digitize(gt, bins[1:-1])
    mid = [float(np.median(gt[idx == b])) for b in range(10)]
    prob = [float(trig[idx == b].mean()) for b in range(10)]
    size = [float(am.clawback[idx == b].mean()) for b in range(10)]
    bx.bar(range(10), 100 * np.array(prob), color=PALETTE["blue"], alpha=0.8, label="share of funds owing a clawback (left)")
    bx.set_xticks(range(10))
    bx.set_xticklabels([f"{x:.1f}x" for x in mid], fontsize=8)
    bx.set_ylim(0, 135)
    tidy(bx, title="By gross multiple decile", xlabel="median gross multiple in the decile", ylabel="% of funds")
    cx = bx.twinx()
    cx.plot(range(10), size, color=PALETTE["red"], marker="o", lw=1.6, label="mean clawback, per 100 (right)")
    cx.grid(False)
    cx.spines["right"].set_visible(True)
    h1, l1 = bx.get_legend_handles_labels()
    h2, l2 = cx.get_legend_handles_labels()
    bx.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left")
    del order
    caption(fig, STRUCT + " 2 and 20, 8% hurdle, full catch-up, American waterfall, clawback to the whole-fund entitlement.")
    return fig


# ------------------------------------------------------------------ 8. vega: the incentive to take risk


@lru_cache(maxsize=1)
def _vega() -> dict[str, list[float]]:
    sig = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    out: dict[str, list[float]] = {"sigma": sig}
    for key, t in [("eu", BASE), ("am", Terms(waterfall="american")), ("am_none", Terms(waterfall="american", clawback=False))]:
        vals = [_value(t, sigma=s) for s in sig]
        out[key] = [v.carry for v in vals]
        out[key + "_lp"] = [v.lp for v in vals]
    out["fees"] = [_value(BASE, sigma=s).fees for s in sig]
    return out


def carry_vega() -> Figure:
    d = _vega()
    sig = np.array(d["sigma"])
    fig = new_figure(14.5, 6.0)
    i2, i6 = d["sigma"].index(0.2), d["sigma"].index(0.6)
    title_block(
        fig,
        "Riskier deals are worth more to the GP and less to the investors",
        f"Present value of the carry and of the LPs' stake as deal volatility rises, every deal fairly priced. Raising volatility "
        f"from 20% to 60% lifts the European carry from {d['eu'][i2]:.1f} to {d['eu'][i6]:.1f} per 100 committed, and the "
        f"LPs lose the same amount: the carry is a call, and a call gains from volatility. Fees ({d['fees'][0]:.1f}) do not "
        "change. Deal-by-deal carry without a clawback is worth the most.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    for key, label, colour in [
        ("eu", "European", PALETTE["blue"]),
        ("am", "American, full clawback", PALETTE["accent"]),
        ("am_none", "American, no clawback", PALETTE["red"]),
    ]:
        ax.plot(100 * sig, d[key], color=colour, marker="o", lw=1.8, ms=4, label=label)
    tidy(ax, title="Present value of the carry", xlabel="deal volatility, % a year", ylabel="per 100 committed")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    for key, label, colour in [
        ("eu_lp", "European", PALETTE["blue"]),
        ("am_lp", "American, full clawback", PALETTE["accent"]),
        ("am_none_lp", "American, no clawback", PALETTE["red"]),
    ]:
        bx.plot(100 * sig, d[key], color=colour, marker="o", lw=1.8, ms=4, label=label)
    bx.axhline(-d["fees"][0], color=PALETTE["ink"], ls=":", lw=0.9)
    bx.text(12, -d["fees"][0] + 0.3, "fees alone", fontsize=8, color=PALETTE["muted"])
    tidy(bx, title="Value of the LPs' stake (zero alpha)", xlabel="deal volatility, % a year", ylabel="per 100 committed")
    caption(
        fig,
        STRUCT
        + f" Risk-neutral Monte Carlo, {SIMS:,} funds, deals correlated 0.3, risk-free rate {100 * R:.0f}%; 2 and 20, 8% hurdle.",
    )
    return fig


# ------------------------------------------------------------------ 9. correlation: an option on a portfolio or a portfolio of options


def carry_correlation() -> Figure:
    rhos = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
    eu = [_value(BASE, rho=r).carry for r in rhos]
    am = [_value(Terms(waterfall="american", clawback=False), rho=r).carry for r in rhos]
    amc = [_value(Terms(waterfall="american"), rho=r).carry for r in rhos]
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "A portfolio of options is worth more than an option on a portfolio",
        f"Carry value against the correlation between deals. Whole-fund carry is one option on the portfolio: diversification "
        f"lowers its volatility, and with independent deals it is worth {eu[0]:.1f}. Deal-by-deal carry without a clawback is an "
        f"option on every deal, worth {am[0]:.1f} - and it barely depends on correlation. At perfect correlation the two "
        f"nearly coincide ({eu[-1]:.1f} and {am[-1]:.1f}).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(rhos, eu, color=PALETTE["blue"], marker="o", lw=2, label="European (option on the portfolio)")
    ax.plot(rhos, amc, color=PALETTE["accent"], marker="o", lw=2, label="American, full clawback")
    ax.plot(rhos, am, color=PALETTE["red"], marker="o", lw=2, label="American, no clawback (portfolio of options)")
    tidy(ax, xlabel="correlation between any two deals", ylabel="present value of carry, per 100 committed")
    ax.legend(fontsize=8.5, loc="center right")
    caption(fig, STRUCT + f" Risk-neutral Monte Carlo, {SIMS:,} funds, deal volatility 40%; 2 and 20, 8% hurdle, full catch-up.")
    return fig


# ------------------------------------------------------------------ 10. what the GP earns (Metrick-Yasuda)


@lru_cache(maxsize=1)
def _revenue() -> list[tuple[str, Valuation]]:
    rows: list[tuple[str, Valuation]] = []
    for label, t in TERM_SETS:
        sigma = 0.60 if "venture" in label else 0.40
        rows.append((label, _value(t, sigma=sigma)))
    return rows


def gp_revenue() -> Figure:
    rows = _revenue()
    fig = new_figure(14.5, 6.2)
    base = rows[0][1]
    title_block(
        fig,
        "Most of what a manager earns does not depend on performance",
        f"Present value of the GP's revenue per 100 committed, fees discounted at the risk-free rate and carry valued as an option "
        f"(Metrick and Yasuda, 2010). Under 2 and 20 the GP expects {base.gp:.1f}: {base.fees:.1f} in fees and {base.carry:.1f} in "
        f"carry, so {100 * base.fixed_share:.0f}% of its pay is fixed. Even a venture fund with 30% carry and 60% deal "
        f"volatility earns only {100 * (1 - rows[-1][1].fixed_share):.0f}% of its pay from performance.",
    )
    ax = fig.add_axes((0.24, 0.13, 0.72, 0.58))
    y = np.arange(len(rows))[::-1]
    fees = [v.fees for _, v in rows]
    car = [v.carry for _, v in rows]
    ax.barh(y, fees, color=PALETTE["slate"], height=0.6, label="management fees")
    ax.barh(y, car, left=fees, color=PALETTE["accent"], height=0.6, label="carried interest")
    for yi, f, c, (_, v) in zip(y, fees, car, rows, strict=True):
        ax.text(f + c + 0.3, yi, f"{f + c:.1f}  ({100 * v.fixed_share:.0f}% fixed)", va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels([label for label, _ in rows], fontsize=8.5)
    ax.set_xlim(0, max(f + c for f, c in zip(fees, car, strict=True)) * 1.3)
    tidy(ax, xlabel="present value per 100 committed")
    ax.legend(fontsize=8.5, loc="upper right")
    caption(
        fig,
        STRUCT
        + f" Risk-neutral Monte Carlo, {SIMS:,} funds; deal volatility 40% (60% for venture), correlation 0.3, r = {100 * R:.0f}%.",
    )
    return fig


# ------------------------------------------------------------------ 11. break-even alpha


@lru_cache(maxsize=1)
def _alpha_curves() -> dict[str, object]:
    alphas = np.linspace(-0.02, 0.10, 13)
    out: dict[str, object] = {"alpha": alphas}
    for label, t in TERM_SETS[:5]:
        out[label] = [_value(t, alpha=float(a), half=True).lp for a in alphas]
        out[label + "_be"] = break_even_alpha(_shape(), t, MODEL, R, SIMS // 2)
    return out


def break_even() -> Figure:
    d = _alpha_curves()
    alphas = np.asarray(d["alpha"])
    fig = new_figure(14.5, 6.0)
    labels = [label for label, _ in TERM_SETS[:5]]
    be = {label: float(d[label + "_be"]) for label in labels}  # type: ignore[arg-type]
    title_block(
        fig,
        "To be worth its fees, a fund must beat the market by about four points a year",
        f"Value of the LPs' stake against the deals' extra expected return (alpha) over a fairly priced investment. Under 2 and "
        f"20 the stake is worth zero at an alpha of {100 * be[labels[0]]:.1f}% a year; a 1.5 and 15 fund needs "
        f"{100 * be[labels[4]]:.1f}%. Only a manager who can beat the market by that much leaves investors better off than "
        "the index.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    colours = [PALETTE["accent"], PALETTE["red"], PALETTE["slate"], PALETTE["blue"], PALETTE["green"]]
    for label, colour in zip(labels, colours, strict=True):
        ax.plot(100 * alphas, d[label], color=colour, lw=1.8, label=label)
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    tidy(ax, title="Value of the LPs' stake", xlabel="deal alpha, % a year", ylabel="per 100 committed")
    ax.legend(fontsize=7.5, loc="upper left")
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    y = np.arange(len(labels))[::-1]
    bx.barh(y, [100 * be[label] for label in labels], color=colours, height=0.6)
    for yi, label in zip(y, labels, strict=True):
        bx.text(100 * be[label] + 0.05, yi, f"{100 * be[label]:.1f}%", va="center", fontsize=8.5)
    bx.set_yticks([])
    tidy(bx, title="Break-even alpha", xlabel="% a year")
    caption(
        fig,
        STRUCT
        + f" Deals priced at cost earning r + alpha; volatility 40%, correlation 0.3, r = {100 * R:.0f}%; {SIMS // 2:,} funds, common random numbers.",
    )
    return fig


# ------------------------------------------------------------------ 12. hurdle and catch-up


def hurdle_catch_up() -> Figure:
    hurdles = np.linspace(0.0, 0.14, 29)
    fig = new_figure(14.5, 6.0)
    variants = [
        (1.0, "full catch-up", PALETTE["accent"]),
        (0.8, "80% catch-up", PALETTE["violet"]),
        (0.5, "50% catch-up", PALETTE["teal"]),
        (0.0, "no catch-up", PALETTE["blue"]),
    ]
    vals = {
        cu: [carry_closed_form(100, 5, R, 0.4, Terms(hurdle=float(h), catch_up=cu)) for h in hurdles] for cu, _, _ in variants
    }
    i8 = int(np.argmin(np.abs(hurdles - 0.08)))
    title_block(
        fig,
        "A hurdle with a full catch-up is mostly a timing device",
        f"Present value of the carry on one investment held five years (volatility 40%) against the hurdle rate. Moving from no "
        f"hurdle to 8% cuts the carry from {vals[1.0][0]:.2f} to {vals[1.0][i8]:.2f} with a full catch-up, but to "
        f"{vals[0.0][i8]:.2f} without one. The catch-up returns to the GP what the hurdle took, for every fund that clears it.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    for cu, label, colour in variants:
        ax.plot(100 * hurdles, vals[cu], color=colour, lw=1.9, label=label)
    ax.axvline(8, color=PALETTE["muted"], ls="--", lw=0.8)
    tidy(ax, title="Value of the carry", xlabel="hurdle rate, % a year", ylabel="per 100 invested")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    g = np.linspace(0.0, 0.30, 31)
    for cu, label, colour in variants:
        net = gross_to_net(_shape(), Terms(catch_up=cu), g)
        bx.plot(100 * g, net["carry"], color=colour, lw=1.9, label=label)
    tidy(bx, title="Carry on funds with a known gross IRR", xlabel="gross IRR, %", ylabel="carry kept, per 100 committed")
    caption(fig, f"Left: closed form, Black (1976), r = {100 * R:.0f}%, 20% carry. Right: " + STRUCT)
    return fig


# ------------------------------------------------------------------ 13. closed form against Monte Carlo


def closed_form_check() -> Figure:
    sig = np.linspace(0.05, 0.8, 16)
    fig = new_figure(14.5, 5.8)
    variants = [
        (BASE, "full catch-up", PALETTE["accent"]),
        (Terms(catch_up=0.0), "no catch-up", PALETTE["blue"]),
        (Terms(hurdle=0.0), "no hurdle", PALETTE["slate"]),
    ]
    zs = []
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for t, label, colour in variants:
        cf = [carry_closed_form(100, 5, R, float(s), t) for s in sig]
        ax.plot(100 * sig, cf, color=colour, lw=1.8, label=f"{label}: closed form")
        pts = sig[::3]
        for s in pts:
            mc, se = single_deal_mc(5, R, float(s), t, funds=5 * SIMS, seed=int(1000 * s))
            zs.append((mc - carry_closed_form(100, 5, R, float(s), t)) / se)
            ax.errorbar(100 * s, mc, yerr=1.96 * se, fmt="o", color=colour, ms=4, capsize=3)
    title_block(
        fig,
        "The waterfall engine prices the carry exactly as the option formula does",
        f"Closed-form value of the carry on one investment (lines) against Monte Carlo through the waterfall code (points with 95% "
        f"intervals, {5 * SIMS:,} paths each). Across {len(zs)} comparisons the largest gap is {max(abs(z) for z in zs):.1f} standard "
        "errors: two independent routes - Black-Scholes and the four-tier waterfall - agree.",
    )
    tidy(ax, xlabel="volatility, % a year", ylabel="present value of carry, per 100 invested")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(fig, f"One investment of 100 held five years, no fees, r = {100 * R:.0f}%, 8% hurdle where stated, 20% carry.")
    return fig


# ------------------------------------------------------------------ 14. fee drag heatmap


def fee_heatmap() -> Figure:
    fees = np.array([0.01, 0.0125, 0.015, 0.0175, 0.02, 0.025])
    carries = np.array([0.10, 0.15, 0.20, 0.25, 0.30])
    shape = _shape()
    grid = np.empty((fees.size, carries.size))
    for i, f in enumerate(fees):
        for j, c in enumerate(carries):
            d = gross_to_net(shape, Terms(fee=float(f), carry=float(c)), [0.15])
            grid[i, j] = 100 * (d["gross_irr"].iloc[0] - d["net_irr"].iloc[0])
    fig = new_figure(14.5, 6.4)
    title_block(
        fig,
        "The fee costs investors more than the carry",
        f"Gross minus net IRR, in percentage points, for a fund whose deals all earn 15% a year, by management fee and carry. "
        f"2 and 20 costs {grid[4, 2]:.1f} points. Halving the fee to 1% saves {grid[4, 2] - grid[0, 2]:.1f} points; halving the "
        f"carry to 10% saves {grid[4, 2] - grid[4, 0]:.1f}. For a fund near the hurdle the fee is the bigger lever.",
    )
    ax = fig.add_axes((0.15, 0.12, 0.6, 0.6))
    im = ax.imshow(grid, cmap="Blues", aspect="auto")
    for i in range(fees.size):
        for j in range(carries.size):
            ax.text(
                j,
                i,
                f"{grid[i, j]:.1f}",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if grid[i, j] > grid.mean() + 0.5 else PALETTE["ink"],
            )
    ax.set_xticks(range(carries.size))
    ax.set_xticklabels([f"{100 * c:.0f}%" for c in carries])
    ax.set_yticks(range(fees.size))
    ax.set_yticklabels([f"{100 * f:g}%" for f in fees])
    ax.grid(False)
    tidy(ax, xlabel="carried interest", ylabel="management fee a year")
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label("gross minus net IRR, points")
    caption(
        fig, STRUCT + " 8% hurdle, full catch-up, European waterfall; fee on commitments for five years, then on invested cost."
    )
    return fig


# ------------------------------------------------------------------ 15. gross and net across simulated funds


def net_distribution() -> Figure:
    shape = _shape()
    m = replace(MODEL, mu=0.12).draw(shape, SIMS // 5)
    out = run(shape, m, BASE)
    gi, ni = out.irrs()
    ok = np.isfinite(gi) & np.isfinite(ni)
    gi, ni = gi[ok], ni[ok]
    pinned = float(np.mean(np.abs(ni - BASE.hurdle) < 0.0025))
    gq = np.percentile(gi, [10, 50, 90])
    nq = np.percentile(ni, [10, 50, 90])
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Fees shift the whole distribution, carry trims the top",
        f"Gross and net IRRs of {SIMS // 5:,} simulated funds with deals expected to earn 12% a year. The median fund earns "
        f"{100 * gq[1]:.1f}% gross and {100 * nq[1]:.1f}% net; the bottom decile {100 * gq[0]:.1f}% and {100 * nq[0]:.1f}%, "
        f"the top decile {100 * gq[2]:.1f}% and {100 * nq[2]:.1f}%. The spike: {100 * pinned:.0f}% of funds net within a quarter "
        "point of the 8% hurdle, because in the catch-up tier every extra pound goes to the GP and the LPs stay pinned at the "
        "hurdle.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    bins = list(np.linspace(-0.15, 0.40, 56))
    ax.hist(gi, bins=bins, color=PALETTE["slate"], alpha=0.6, label="gross")
    ax.hist(ni, bins=bins, color=PALETTE["blue"], alpha=0.6, label="net to LPs")
    ax.axvline(BASE.hurdle, color=PALETTE["accent"], lw=1, ls="--")
    ax.text(BASE.hurdle + 0.005, ax.get_ylim()[1] * 0.92, "8% hurdle", fontsize=8, color=PALETTE["accent"])
    tidy(ax, title="IRR distribution", xlabel="IRR", ylabel="funds")
    ax.xaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    order = np.argsort(gi)
    gap = (gi - ni)[order]
    dec = np.array_split(np.arange(gi.size), 10)
    bx.bar(range(10), [100 * gap[d].mean() for d in dec], color=PALETTE["slate"], alpha=0.85)
    bx.set_xticks(range(10))
    bx.set_xticklabels([f"{100 * gi[order][d].mean():.0f}%" for d in dec], fontsize=8)
    tidy(bx, title="Gross minus net by gross-IRR decile", xlabel="mean gross IRR in the decile", ylabel="percentage points")
    caption(
        fig,
        STRUCT + " Deals: expected return 12%, volatility 40%, correlation 0.3. 2 and 20, 8% hurdle, full catch-up, European.",
    )
    return fig


# ------------------------------------------------------------------ 16. carry against alpha


def carry_delta() -> Figure:
    d = _alpha_curves()
    alphas = np.asarray(d["alpha"])
    fig = new_figure(14.5, 5.8)
    eu = [_value(BASE, alpha=float(a), half=True) for a in alphas]
    am = [_value(Terms(waterfall="american", clawback=False), alpha=float(a), half=True) for a in alphas]
    i0 = int(np.argmin(np.abs(alphas)))
    i6 = int(np.argmin(np.abs(alphas - 0.06)))
    title_block(
        fig,
        "Carry rewards skill steeply, and pays something even without it",
        f"Present value of the GP's carry and fees against the deals' alpha. With no skill the carry is worth "
        f"{eu[i0].carry:.1f} per 100 committed - an option's time value; with 6% alpha it is worth {eu[i6].carry:.1f}. Deal-by-deal "
        f"carry without a clawback pays {am[i0].carry:.1f} for no skill at all. Fees, {eu[0].fees:.1f}, are paid regardless.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(100 * alphas, [v.carry for v in eu], color=PALETTE["accent"], lw=2, marker="o", ms=4, label="carry, European")
    ax.plot(
        100 * alphas,
        [v.carry for v in am],
        color=PALETTE["red"],
        lw=2,
        marker="o",
        ms=4,
        label="carry, American without clawback",
    )
    ax.plot(100 * alphas, [v.fees for v in eu], color=PALETTE["slate"], lw=2, ls="--", label="management fees")
    ax.axvline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, xlabel="deal alpha, % a year", ylabel="present value per 100 committed")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(
        fig,
        STRUCT
        + f" Deals priced at cost earning r + alpha, volatility 40%, correlation 0.3, r = {100 * R:.0f}%; {SIMS // 2:,} funds.",
    )
    return fig
