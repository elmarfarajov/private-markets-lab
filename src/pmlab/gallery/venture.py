"""Day 4 charts: venture capital preferred stock as options, and what post-money valuations overstate.

The company is stylised (``pmlab.venture.example``): founders and an option pool, Series A to D at
$0.50, $2, $8 and $30 a share, each senior to the last, 1x non-participating preferences. Post-money
after Series D is $3.0bn. Option-pricing inputs are stated on each chart. Every number in a
subtitle is computed.
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .. import venture as V
from .style import PALETTE, SERIES, caption, new_figure, tidy, title_block

matplotlib.rcParams["text.parse_math"] = False  # dollar signs in captions are currency, not mathematics

SIGMA, YEARS, R = 0.9, 4.0, 0.04
SIMS = 200  # random companies in the sample chart; the tests lower it
CLASS_COLOURS = [PALETTE["slate"], "#b6bfc8", PALETTE["green"], PALETTE["teal"], PALETTE["violet"], PALETTE["blue"]]
BASE = "Stylised company: common 40m and options 10m shares; Series A-D 15m, 15m, 12m, 8m shares at $0.50, $2, $8, $30, each senior, 1x."
OPM = f"OPM: lognormal exit value, volatility {100 * SIGMA:.0f}%, {YEARS:.0f} years to exit, risk-free rate {100 * R:.0f}%."


@lru_cache(maxsize=1)
def _table() -> V.CapTable:
    return V.example()


@lru_cache(maxsize=1)
def _payoffs() -> V.Payoffs:
    return V.Payoffs.build(replace(_table(), years=YEARS))


@lru_cache(maxsize=1)
def _fair() -> V.Fair:
    return V.backsolve(_table(), SIGMA, YEARS, R, _payoffs())


@lru_cache(maxsize=32)
def _fair_terms(key: str) -> V.Fair:
    terms = TERMS[key]
    t = V.example(terms)
    return V.backsolve(t, SIGMA, YEARS, R)


TERMS: dict[str, dict[str, dict[str, object]]] = {
    "base: each round senior, 1x, non-participating": {},
    "Series D 1.5x preference": {"Series D": {"multiple": 1.5}},
    "Series D 2x preference": {"Series D": {"multiple": 2.0}},
    "Series D participating, uncapped": {"Series D": {"participating": True}},
    "Series D participating, 3x cap": {"Series D": {"participating": True, "cap": 3.0}},
    "Series D 8% cumulative dividend": {"Series D": {"dividend": 0.08}},
    "Series D pari passu with C": {"Series D": {"seniority": 3}},
    "all rounds pari passu": {n: {"seniority": 1} for n in ("Series A", "Series B", "Series C", "Series D")},
}


@lru_cache(maxsize=1)
def _sample() -> pd.DataFrame:
    return pd.DataFrame(V.overvaluation_sample(SIMS, SIGMA, YEARS, R, seed=4))


def _plain_log(ax, axis: str = "x") -> None:  # type: ignore[no-untyped-def]
    """Plain numbers on a log axis (mathtext is off, so the default 10^k labels would print raw)."""
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

    a = ax.xaxis if axis == "x" else ax.yaxis
    a.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    a.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}" if x >= 1 else f"{x:g}"))
    a.set_minor_formatter(NullFormatter())


def _fmt(v: float) -> str:
    return f"${v / 1000:.2f}bn" if v >= 1000 else f"${v:.0f}m"


# ------------------------------------------------------------------ 1. the waterfall


def waterfall() -> Figure:
    p = _payoffs()
    keep = p.values <= 6000
    v, pay = p.values[keep], p.pay[keep]
    names = _table().names
    fig = new_figure(14.5, 6.6)
    t = _table()
    bp = p.breakpoints()
    title_block(
        fig,
        "Who gets what at exit: the preferred stack, then everyone",
        f"Payout to each class by exit value. Below {_fmt(t.securities[5].invested)} Series D takes everything; then C, B and A recover "
        f"their money in turn; above about {_fmt(float(bp[bp < 1500].max()))} every class but D has converted, and D converts only "
        f"above {_fmt(float(bp.max()))}, roughly the {_fmt(t.post_money())} post-money valuation. Until then the newest investors hold "
        "a senior claim, not common stock.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    ax.stackplot(v, pay.T, colors=CLASS_COLOURS, labels=names, alpha=0.9)
    tidy(ax, title="Payout by class", xlabel="exit value, $m", ylabel="payout, $m")
    ax.legend(fontsize=8, loc="upper left")
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    share = pay / np.where(v[:, None] > 0, v[:, None], 1)
    for k, (n, c) in enumerate(zip(names, CLASS_COLOURS, strict=True)):
        bx.plot(v[1:], 100 * share[1:, k], color=c if k != 1 else PALETTE["muted"], lw=1.6, label=n)
    bx.set_xscale("log")
    _plain_log(bx)
    tidy(bx, title="Share of the exit, %", xlabel="exit value, $m (log)")
    caption(fig, BASE + " Conversion: each class converts only if converting pays it more (an equilibrium).")
    return fig


def _switch(k: int) -> float:
    """The exit value at which class ``k`` starts to convert: the grid bracket, refined by bisection on the exact payoff."""
    p = _payoffs()
    on = p.converts[:, k]
    if not on.any():
        return float("nan")
    j = int(np.argmax(on))
    lo, hi = float(p.values[j - 1]), float(p.values[j])
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if V.payoff(_table(), mid)[1][k] else (mid, hi)
    return hi


def conversion_map() -> Figure:
    p = _payoffs()
    keep = (p.values >= 50) & (p.values <= 10000)
    v, conv = p.values[keep], p.converts[keep]
    names = [n for n, s in zip(_table().names, _table().securities, strict=True) if s.preferred]
    idx = [k for k, s in enumerate(_table().securities) if s.preferred]
    first = {n: _switch(k) for n, k in zip(names, idx, strict=True)}
    fig = new_figure(14.5, 5.6)
    title_block(
        fig,
        "Preferred shareholders convert one class at a time, cheapest first",
        "Exit values at which each class finds converting to common worth more than its preference: Series A at "
        f"{_fmt(first['Series A'])}, B at {_fmt(first['Series B'])}, C at {_fmt(first['Series C'])}, D at {_fmt(first['Series D'])}. "
        "A class converts when its as-converted share of the residual exceeds its preference, so the classes that paid least a share convert first.",
    )
    ax = fig.add_axes((0.12, 0.15, 0.85, 0.55))
    for j, (n, k) in enumerate(zip(names, idx, strict=True)):
        on = conv[:, k]
        ax.fill_between(v, j - 0.35, j + 0.35, where=on, color=CLASS_COLOURS[k], alpha=0.9, step="mid")
        ax.fill_between(v, j - 0.35, j + 0.35, where=~on, color=PALETTE["band"], step="mid")
        ax.axvline(first[n], color=CLASS_COLOURS[k], lw=0.8, ls=":")
    ax.set_xscale("log")
    _plain_log(ax)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([f"{n} (${_table().securities[k].price:g})" for n, k in zip(names, idx, strict=True)])
    tidy(ax, xlabel="exit value, $m (log scale): coloured = converted to common, grey = takes its preference")
    caption(fig, BASE)
    return fig


def option_decomposition() -> Figure:
    p = _payoffs()
    keep = p.values <= 5000
    v = p.values[keep]
    k = _table().names.index("Series D")
    d = p.pay[keep, k]
    pref = _table().securities[k].invested
    bp = p.breakpoints()
    vstar = float(bp.max())
    share = _table().securities[k].shares / _table().fully_diluted
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Series D holds debt plus a call: a bond-like floor and an option to share the upside",
        f"Series D's payout against exit value (black) and its pieces: the first {_fmt(pref)} of the exit (min(V, {pref:.0f})), plus "
        f"{100 * share:.0f}% of the exit above {_fmt(vstar)}, where converting beats the preference - a call option with that strike. "
        "Common stock is the mirror image: it pays nothing until every preference is covered.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    ax.plot(v, np.minimum(v, pref), color=PALETTE["blue"], lw=1.4, ls="--", label=f"floor: min(V, {pref:.0f})")
    ax.plot(
        v,
        share * np.maximum(v - vstar, 0),
        color=PALETTE["violet"],
        lw=1.4,
        ls="--",
        label=f"call: {100 * share:.0f}% of (V - {vstar:.0f})+",
    )
    ax.plot(v, d, color=PALETTE["ink"], lw=2.2, label="Series D payout")
    tidy(ax, title="Series D", xlabel="exit value, $m", ylabel="payout, $m")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    bx.plot(v, p.pay[keep, 0], color=PALETTE["slate"], lw=2, label="Common")
    tidy(bx, title="Common", xlabel="exit value, $m", ylabel="payout, $m")
    caption(fig, BASE + " The floor is senior: D's preference is paid before any other class.")
    return fig


# ------------------------------------------------------------------ 4-6. post-money against fair value


def post_vs_fair() -> Figure:
    f = _fair()
    t = _table()
    names = t.names
    prices = np.array([s.price for s in t.securities])
    latest = t.latest.price
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        f"A {_fmt(f.post_money)} unicorn worth {_fmt(f.company)}: post-money overstates fair value by {100 * f.overvaluation:.0f}%",
        f"The fair company value at which Series D's ${latest:.0f} is a fair price, by the option-pricing method. Series D shares are "
        f"worth $30.00, but common shares only ${f.per_share[0]:.2f}, {100 * f.per_share[0] / latest:.0f}% of the headline price: "
        "the post-money valuation prices every share like the most senior one.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.36, 0.58))
    ax.bar([0, 1], [f.post_money, f.company], color=[PALETTE["slate"], PALETTE["blue"]], width=0.55)
    for x, val in zip([0, 1], [f.post_money, f.company], strict=True):
        ax.text(x, val + 40, _fmt(val), ha="center", fontsize=10)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["post-money\n(price x all shares)", "fair value\n(OPM)"])
    tidy(ax, title="Company value", ylabel="$m")
    bx = fig.add_axes((0.52, 0.13, 0.45, 0.58))
    x = np.arange(len(names))
    bx.bar(x - 0.2, f.per_share, width=0.4, color=CLASS_COLOURS, label="fair value per share")
    bx.bar(x + 0.2, prices, width=0.4, color="none", edgecolor=PALETTE["ink"], label="price paid")
    bx.axhline(latest, color=PALETTE["accent"], lw=1, ls="--")
    bx.text(len(names) - 0.6, latest + 0.5, "Series D price", fontsize=8, color=PALETTE["accent"], ha="right")
    bx.set_xticks(x)
    bx.set_xticklabels(names, fontsize=8.5)
    tidy(bx, title="Fair value per share, $", ylabel="$ per share")
    bx.legend(fontsize=8, loc="upper left")
    caption(fig, BASE + " " + OPM)
    return fig


def sensitivity() -> Figure:
    t = _table()
    sig = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4]
    yrs = [1, 2, 3, 4, 5, 6, 8, 10]
    p_by_year = {y: V.Payoffs.build(replace(t, years=y)) for y in sorted(set(yrs) | {YEARS})}
    ov_s = [V.backsolve(t, s, YEARS, R, p_by_year[YEARS]).overvaluation for s in sig]
    ov_t = [V.backsolve(t, SIGMA, y, R, p_by_year[y]).overvaluation for y in yrs]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "The overstatement depends on volatility and the time to exit, and not in one direction",
        f"Left: overvaluation against exit-value volatility ({100 * min(ov_s):.0f}% to {100 * max(ov_s):.0f}%). It peaks at 60-70% "
        f"volatility; one reading: a calm company's exit is near the preference stack, where seniority is worth most; at high volatility every class "
        f"is mostly an option on the upside. Right: against years to exit, from {100 * ov_t[0]:.0f}% at one year to {100 * ov_t[-1]:.0f}% "
        "at ten - the further away the exit, the more the company can grow past the preferences.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.plot(100 * np.array(sig), 100 * np.array(ov_s), color=PALETTE["blue"], lw=2, marker="o")
    ax.axvline(100 * SIGMA, color=PALETTE["muted"], ls="--", lw=0.8)
    tidy(
        ax,
        title=f"Against volatility ({YEARS:.0f} years to exit)",
        xlabel="volatility of exit value, % a year",
        ylabel="overvaluation, %",
    )
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.plot(yrs, 100 * np.array(ov_t), color=PALETTE["violet"], lw=2, marker="o")
    bx.axvline(YEARS, color=PALETTE["muted"], ls="--", lw=0.8)
    tidy(bx, title=f"Against time to exit (volatility {100 * SIGMA:.0f}%)", xlabel="years to exit", ylabel="overvaluation, %")
    caption(fig, BASE + f" Risk-free rate {100 * R:.0f}%.")
    return fig


def term_effects() -> Figure:
    rows = [(k, _fair_terms(k)) for k in TERMS]
    base = rows[0][1]
    fig = new_figure(14.5, 6.4)
    two = dict(rows)["Series D 2x preference"]
    title_block(
        fig,
        "Investor-friendly terms in the latest round inflate the headline valuation",
        f"Overvaluation of the same $3.0bn post-money company under different Series D terms. The base case overstates by "
        f"{100 * base.overvaluation:.0f}%; a 2x liquidation preference by {100 * two.overvaluation:.0f}%, because investors paying "
        f"$30 a share for that protection imply a much lower value for the company. Making rounds pari passu lowers it to "
        f"{100 * dict(rows)['all rounds pari passu'].overvaluation:.0f}%.",
    )
    ax = fig.add_axes((0.3, 0.13, 0.45, 0.58))
    y = np.arange(len(rows))[::-1]
    vals = [100 * f.overvaluation for _, f in rows]
    cols = [PALETTE["slate"]] + [PALETTE["red"] if v > vals[0] else PALETTE["blue"] for v in vals[1:]]
    ax.barh(y, vals, color=cols, height=0.6)
    for yi, v in zip(y, vals, strict=True):
        ax.text(v + 2, yi, f"{v:.0f}%", va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels([k for k, _ in rows], fontsize=8.5)
    tidy(ax, title="Post-money over fair value", xlabel="overvaluation, %")
    bx = fig.add_axes((0.82, 0.13, 0.15, 0.58))
    bx.barh(y, [f.per_share[0] for _, f in rows], color=PALETTE["slate"], height=0.6)
    bx.set_yticks([])
    tidy(bx, title="Common, $/share")
    caption(fig, BASE + " " + OPM)
    return fig


# ------------------------------------------------------------------ 7-8. backsolve and common stock


def backsolve_curve() -> Figure:
    p = _payoffs()
    t = _table()
    k = t.names.index("Series D")
    v0 = np.linspace(400, 4000, 60)
    d_val = np.array([p.value(x, SIGMA, YEARS, R)[k] for x in v0]) / t.securities[k].shares
    c_val = np.array([p.value(x, SIGMA, YEARS, R)[0] for x in v0]) / t.securities[0].shares
    f = _fair()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Backsolving: the round's price pins down the company's value",
        f"Value per share of Series D and of common stock as the company's value varies. Series D's $30 price is fair at a company value "
        f"of {_fmt(f.company)} (the backsolve); at that value common is worth ${f.per_share[0]:.2f}. Series D's value falls only "
        "slowly as the company value falls - its preference protects it - so a price far above common's value is consistent with a "
        "modest company value.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(v0, d_val, color=PALETTE["blue"], lw=2, label="Series D, $ per share")
    ax.plot(v0, c_val, color=PALETTE["slate"], lw=2, label="common, $ per share")
    ax.plot(v0, v0 / t.fully_diluted, color=PALETTE["muted"], lw=1, ls=":", label="company value / fully diluted shares")
    ax.axhline(30, color=PALETTE["accent"], lw=1, ls="--")
    ax.axvline(f.company, color=PALETTE["accent"], lw=1, ls="--")
    ax.annotate(
        f"fair value {_fmt(f.company)}",
        (f.company, 30),
        xytext=(10, -30),
        textcoords="offset points",
        fontsize=8.5,
        color=PALETTE["accent"],
    )
    ax.axvline(f.post_money, color=PALETTE["muted"], lw=0.8)
    ax.text(f.post_money + 30, 2, "post-money", fontsize=8, color=PALETTE["muted"])
    tidy(ax, xlabel="company value today, $m", ylabel="$ per share")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(fig, BASE + " " + OPM)
    return fig


def common_value() -> Figure:
    t = _table()
    sig = [0.5, 0.9, 1.3]
    yrs = np.array([1, 2, 3, 4, 5, 6, 8])
    fig = new_figure(14.5, 6.0)
    vals = {s: [V.backsolve(t, s, float(y), R).per_share[0] for y in yrs] for s in sig}
    title_block(
        fig,
        "Common stock is worth a fraction of the latest price; at high volatility, the more so the nearer the exit",
        f"Fair value of a common share (what employees' options are written on) against years to exit. At volatility 90% and four years "
        f"it is ${vals[0.9][3]:.2f}, {100 * vals[0.9][3] / 30:.0f}% of Series D's $30; with one year to go, ${vals[0.9][0]:.2f}. This is "
        "the gap a 409A valuation measures, and why employee options look cheap against the headline price.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for s, c in zip(sig, SERIES, strict=False):
        ax.plot(yrs, vals[s], color=c, lw=2, marker="o", label=f"volatility {100 * s:.0f}%")
    ax.axhline(30, color=PALETTE["accent"], lw=1, ls="--")
    ax.text(yrs[-1], 30.5, "Series D price $30", fontsize=8, color=PALETTE["accent"], ha="right")
    tidy(ax, xlabel="years to exit", ylabel="fair value of a common share, $")
    ax.legend(fontsize=8.5)
    caption(fig, BASE + f" Backsolved to Series D's price at each horizon; risk-free rate {100 * R:.0f}%.")
    return fig


# ------------------------------------------------------------------ 9-10. a sample of unicorns


def sample_distribution() -> Figure:
    d = _sample()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"Across {len(d)} stylised unicorns, post-money valuations overstate by {100 * d['overvaluation'].median():.0f}% at the median",
        f"Random companies with three to six rounds and terms drawn at illustrative rates (latest round senior in "
        f"{100 * d['senior'].mean():.0f}%, participating in {100 * d['participating'].mean():.0f}%, multiple above 1x in "
        f"{100 * (d['multiple'] > 1).mean():.0f}%). Overvaluation ranges from {100 * d['overvaluation'].min():.0f}% to "
        f"{100 * d['overvaluation'].max():.0f}%; common stock is worth {100 * (1 - d['common_discount'].median()):.0f}% of the latest "
        "price at the median. Gornall and Strebulaev (2020) report an average of 48% for real US unicorns.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.hist(100 * d["overvaluation"].clip(upper=3), bins=30, color=PALETTE["blue"], alpha=0.8)
    ax.axvline(100 * d["overvaluation"].median(), color=PALETTE["ink"], ls="--")
    tidy(ax, title="Overvaluation", xlabel="post-money over fair value, % (300 = 300 or more)", ylabel="companies")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.hist(100 * (1 - d["common_discount"]), bins=30, color=PALETTE["slate"], alpha=0.8)
    tidy(bx, title="Common share value as % of the latest price", xlabel="%", ylabel="companies")
    caption(fig, f"Stylised sample (pmlab.venture.random_company), not real companies. {OPM}")
    return fig


def sample_drivers() -> Figure:
    d = _sample()
    groups = [
        ("latest round senior", d["senior"] == 1),
        ("latest round pari passu", d["senior"] == 0),
        ("latest participating", d["participating"] == 1),
        ("latest non-participating", d["participating"] == 0),
        ("latest multiple > 1x", d["multiple"] > 1),
        ("latest multiple 1x", d["multiple"] == 1),
    ]
    med = [(n, 100 * d.loc[m, "overvaluation"].median(), int(m.sum())) for n, m in groups]
    fig = new_figure(14.5, 6.0)
    corr = d["latest_share"].corr(d["overvaluation"])
    title_block(
        fig,
        "What drives the overstatement: the latest round's protection and size",
        f"Median overvaluation by the latest round's terms. A liquidation multiple above 1x lifts it from {med[5][1]:.0f}% to "
        f"{med[4][1]:.0f}%, participation from {med[3][1]:.0f}% to {med[2][1]:.0f}%. Right: the smaller the latest round's share of the "
        f"company, the larger the overstatement (correlation {corr:.2f}): a small senior round says little about the value of the rest.",
    )
    ax = fig.add_axes((0.25, 0.13, 0.35, 0.58))
    y = np.arange(len(med))[::-1]
    ax.barh(y, [m for _, m, _ in med], color=[PALETTE["red"], PALETTE["blue"]] * 3, height=0.6)
    for yi, (_, m, n) in zip(y, med, strict=True):
        ax.text(m + 2, yi, f"{m:.0f}% (n={n})", va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels([n for n, _, _ in med], fontsize=8.5)
    tidy(ax, title="Median overvaluation, %")
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    bx.scatter(100 * d["latest_share"], 100 * d["overvaluation"], s=10, color=PALETTE["violet"], alpha=0.6)
    tidy(bx, title="Against the latest round's size", xlabel="latest round, % of fully diluted shares", ylabel="overvaluation, %")
    caption(fig, f"Stylised sample of {len(d)} companies. {OPM}")
    return fig


# ------------------------------------------------------------------ 11-12. down rounds and dilution


def down_round() -> Figure:
    t = _table()
    prices = [10, 15, 20, 30, 45, 60]
    rows = []
    for pr in prices:
        tt = t.with_terms("Series D", price=float(pr))
        f = V.backsolve(tt, SIGMA, YEARS, R)
        rows.append((pr, f.post_money, f.company, f.per_share[0], f.per_share[4]))
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Raise at any price and the overstatement stays the same: it comes from the structure, not the price",
        f"The same company raising Series D (8m shares) at different prices. From a ${prices[0]} round to a ${prices[-1]} round the "
        f"post-money and the fair value both multiply by {rows[-1][1] / rows[0][1]:.1f}, and the overstatement is "
        f"{100 * (rows[0][1] / rows[0][2] - 1):.1f}% at every price. The reason is exact: the most senior class's payoff, min(V, 8P) "
        "until it converts at V = 100P, scales with its price P, so the value that makes P fair scales too. The junior classes' "
        f"share of the fair value shifts instead; common rises from ${rows[0][3]:.2f} to ${rows[-1][3]:.2f} a share.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.plot(prices, [r[1] for r in rows], color=PALETTE["slate"], lw=2, marker="o", label="post-money")
    ax.plot(prices, [r[2] for r in rows], color=PALETTE["blue"], lw=2, marker="o", label="fair value")
    tidy(ax, title="Company value", xlabel="Series D price, $", ylabel="$m")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.plot(prices, [r[3] for r in rows], color=PALETTE["slate"], lw=2, marker="o", label="common")
    bx.plot(prices, [r[4] for r in rows], color=PALETTE["violet"], lw=2, marker="o", label="Series C")
    tidy(bx, title="Fair value per share", xlabel="Series D price, $", ylabel="$ per share")
    bx.legend(fontsize=8.5)
    caption(fig, BASE + " Series D's price varied, its share count fixed. " + OPM)
    return fig


def protection_value() -> Figure:
    p = _payoffs()
    t = _table()
    v0 = np.geomspace(200, 20000, 50)
    fig = new_figure(14.5, 6.0)
    k = t.names.index("Series D")
    share = t.securities[k].shares / t.fully_diluted
    vals = np.array([p.value(x, SIGMA, YEARS, R)[k] for x in v0])
    plain = share * v0
    prem = vals / plain - 1
    f = _fair()
    at_fair = f.values[k] / (share * f.company) - 1
    title_block(
        fig,
        "The preference is worth most when the company is worth least",
        f"Series D's value against the same {100 * share:.0f}% of the company held pro rata. At the fair value of "
        f"{_fmt(f.company)} the preferred is worth {100 * at_fair:.1f}% more, which is the overvaluation itself: the round's price "
        f"is fair there, and post-money is that price on every share. At {_fmt(v0[0])} it is worth {1 + prem[0]:.1f} times its pro rata "
        f"share; at {_fmt(v0[-1])}, {100 * prem[-1]:.0f}% more. Protection is a put on the company's failure.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(v0, 100 * prem, color=PALETTE["blue"], lw=2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    _plain_log(ax)
    _plain_log(ax, "y")
    ax.axvline(f.company, color=PALETTE["accent"], ls="--", lw=1)
    tidy(ax, xlabel="company value today, $m (log)", ylabel="Series D value over its pro rata share, % (log)")
    caption(fig, BASE + " " + OPM)
    return fig


# ------------------------------------------------------------------ 13-14. checks and the exit distribution


def opm_vs_mc() -> Figure:
    f = _fair()
    t = _table()
    mc, se = V.monte_carlo(t, f.company, SIGMA, YEARS, R, paths=max(2000, SIMS * 50), seed=11)
    z = (mc - f.values) / se
    fig = new_figure(14.5, 5.6)
    title_block(
        fig,
        "The exact option-pricing integral agrees with brute-force simulation",
        f"Value of each class from the exact integral of the waterfall against the lognormal density (bars) and from Monte Carlo with "
        f"{max(2000, SIMS * 50):,} exits and the exit value as a control variate (points, 95% intervals). The largest gap is "
        f"{np.abs(z).max():.1f} standard errors.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    x = np.arange(len(t.names))
    ax.bar(x, f.values, color=CLASS_COLOURS, alpha=0.6, width=0.6)
    ax.errorbar(x, mc, yerr=1.96 * se, fmt="o", color=PALETTE["ink"], capsize=4)
    ax.set_xticks(x)
    ax.set_xticklabels(t.names)
    tidy(ax, ylabel="value of the class, $m")
    caption(fig, BASE + " " + OPM)
    return fig


def exit_distribution() -> Figure:
    f = _fair()
    t = _table()
    rng = np.random.default_rng(3)
    mu = 0.20
    vt = f.company * np.exp((mu - 0.5 * SIGMA**2) * YEARS + SIGMA * np.sqrt(YEARS) * rng.standard_normal(4000))
    tt = replace(t, years=YEARS)
    pay = np.array([V.payoff(tt, float(x))[0] for x in vt])
    k = t.names.index("Series D")
    mult_d = pay[:, k] / t.securities[k].invested
    mult_c = pay[:, 0] / (f.per_share[0] * t.securities[0].shares)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Same company, different bets: Series D loses less often, common wins bigger",
        f"Outcomes at exit in 4,000 scenarios with the company expected to grow {100 * mu:.0f}% a year. Series D loses money in "
        f"{100 * np.mean(mult_d < 1):.0f}% of exits, while common - bought at its fair value of ${f.per_share[0]:.2f} - loses in "
        f"{100 * np.mean(mult_c < 1):.0f}%, but returns more than 3x in {100 * np.mean(mult_c > 3):.0f}% against "
        f"{100 * np.mean(mult_d > 3):.0f}% for D. Fair value equates their prices, not their risks.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    bins = np.linspace(0, 6, 61)
    ax.hist(np.clip(mult_d, 0, 6), bins=bins, color=PALETTE["blue"], alpha=0.55, label="Series D, bought at $30")
    ax.hist(
        np.clip(mult_c, 0, 6),
        bins=bins,
        color=PALETTE["slate"],
        alpha=0.55,
        label=f"common, bought at fair value ${f.per_share[0]:.2f}",
    )
    ax.axvline(1, color=PALETTE["red"], lw=1)
    tidy(ax, xlabel="multiple of money at exit (6 = 6 or more)", ylabel="scenarios")
    ax.legend(fontsize=8.5)
    caption(
        fig,
        BASE
        + f" Real-world exit value: lognormal, growth {100 * mu:.0f}% a year, volatility {100 * SIGMA:.0f}%, {YEARS:.0f} years.",
    )
    return fig


def breakpoint_table() -> Figure:
    p = _payoffs()
    t = _table()
    bp = p.breakpoints()
    # cluster grid-resolution duplicates
    clusters: list[float] = []
    for b in bp:
        if not clusters or b > clusters[-1] * 1.03:
            clusters.append(float(b))
    fig = new_figure(14.5, 5.8)
    slopes = np.diff(p.pay, axis=0) / np.diff(p.values)[:, None]
    title_block(
        fig,
        f"Breakpoints: the payoff is a sum of {len(clusters)} call options on the company",
        "Each class's share of a marginal pound of exit value, between the breakpoints where a preference is filled or a class converts. "
        "The option-pricing method values each class as a portfolio of calls struck at these breakpoints - "
        "which is why the payoffs, and the values, are exact for any volatility and horizon.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.8, 0.55))
    mids = p.values[:-1]
    keep = (mids > 10) & (mids < 6000)
    ax.stackplot(mids[keep], (100 * slopes[keep]).T, colors=CLASS_COLOURS, labels=t.names, alpha=0.9)
    for b in clusters:
        ax.axvline(b, color=PALETTE["ink"], lw=0.6, ls=":")
    ax.set_xscale("log")
    _plain_log(ax)
    ax.set_ylim(0, 100)
    tidy(ax, xlabel="exit value, $m (log); dotted: breakpoints", ylabel="share of the marginal pound, %")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    caption(fig, BASE)
    return fig
