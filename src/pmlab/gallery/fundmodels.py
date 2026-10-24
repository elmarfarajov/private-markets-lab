"""Day 3 charts: fund cash-flow models and the secondary market.

Every chart is computed from ``pmlab.fundmodel`` and ``pmlab.secondary``. Funds are model funds
with the parameters stated on each chart; no proprietary data is used. Every number in a subtitle
is computed.
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .. import fundmodel as F
from .. import secondary as S
from ..synthetic import FundSpec, gbm_market, simulate_fund
from .style import PALETTE, SERIES, caption, new_figure, tidy, title_block

SPEC = F.StochasticSpec()
SIMS = 5000  # simulated funds behind each Monte Carlo chart; the tests lower it
REQUIRED = [0.11, 0.13, 0.15, 0.18]
MODEL = (
    "Model fund: Takahashi-Alexander calls (25%, 33%, 50%, 50% of the uncalled, then the rest), bow 2.5, life 12; "
    "expected return 11%, beta 1.2, market volatility 16%, own volatility 20%."
)


@lru_cache(maxsize=1)
def _paths() -> F.Paths:
    return F.simulate(SPEC, SIMS, seed=1)


@lru_cache(maxsize=1)
def _deal_curves() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Mean annual curves of bottom-up deal funds (Day 1's stylised fund) and their dispersion."""
    cc, cd, nv = [], [], []
    for s in range(max(60, SIMS // 20)):
        m = gbm_market(14.0, mu=0.07, sigma=0.16, seed=s)
        f = simulate_fund(m, FundSpec(alpha=0.03, idio=0.25, fee=0.02, seed=1000 + s))
        a, b, c = F.annual_curves(f.times, f.amounts, f.navs, 12)
        cc.append(a)
        cd.append(b)
        nv.append(c)
    arr = [np.array(x) for x in (cc, cd, nv)]
    return arr[0].mean(0), arr[1].mean(0), arr[2].mean(0), arr[0].std(0), arr[1].std(0), arr[2].std(0)


# ------------------------------------------------------------------ 1. the Takahashi-Alexander profile


def ta_profile() -> Figure:
    p = F.takahashi_alexander()
    f = p.frame()
    trough = int(f["cum_net"].idxmin())
    breakeven = int(f.index[f["cum_net"] >= 0][0])
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "The Yale model: a fund's life in a handful of parameters",
        f"Takahashi and Alexander's (2002) model with calls of 25%, 33%, 50% and 50% of the uncalled commitment, growth of 13%, a "
        f"bow of 2.5 and a twelve-year life. The investor is {-f['cum_net'].min():.0f} out of pocket at the bottom of the J-curve in "
        f"year {trough}, breaks even in year {breakeven}, and ends with a multiple of {p.tvpi():.2f} and an IRR of "
        f"{100 * p.irr():.1f}%: the IRR equals the growth rate G exactly, an identity of the model whatever the other parameters.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    x = f.index.to_numpy()
    ax.bar(x - 0.2, -f["calls"], width=0.4, color=PALETTE["slate"], label="calls")
    ax.bar(x + 0.2, f["distributions"], width=0.4, color=PALETTE["blue"], label="distributions")
    ax.plot(x, f["nav"], color=PALETTE["ink"], lw=1.8, marker="o", ms=3, label="NAV")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, title="Annual flows and NAV", xlabel="year", ylabel="per 100 committed")
    ax.legend(fontsize=8.5, loc="upper left")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.fill_between(x, f["cum_net"], 0, where=f["cum_net"] < 0, color=PALETTE["red"], alpha=0.25)
    bx.fill_between(x, f["cum_net"], 0, where=f["cum_net"] >= 0, color=PALETTE["green"], alpha=0.25)
    bx.plot(x, f["cum_net"], color=PALETTE["ink"], lw=2)
    bx.plot(x, f["cum_calls"], color=PALETTE["slate"], lw=1.2, ls="--", label="cumulative calls")
    bx.plot(x, f["cum_distributions"], color=PALETTE["blue"], lw=1.2, ls="--", label="cumulative distributions")
    bx.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(bx, title="The J-curve: cumulative net cash flow", xlabel="year", ylabel="per 100 committed")
    bx.legend(fontsize=8.5, loc="upper left")
    caption(
        fig,
        "Calls C_t = RC_t (K - PIC_{t-1}); distributions D_t = (t/L)^B NAV_{t-1}(1 + G); NAV_t = NAV_{t-1}(1 + G) + C_t - D_t.",
    )
    return fig


# ------------------------------------------------------------------ 2. sensitivity


def ta_sensitivity() -> Figure:
    fig = new_figure(14.5, 6.0)
    base = F.TAParams()
    bows = [1.0, 2.5, 5.0]
    growths = [0.05, 0.13, 0.20]
    schedules = [
        ("fast (50%, 100%)", (0.5, 1.0)),
        ("base", base.rc),
        ("slow (15% a year, then 100%)", (0.15, 0.15, 0.15, 0.15, 0.15, 1.0)),
    ]
    irr_b = {b: F.takahashi_alexander(replace(base, bow=b)).irr() for b in bows}
    tv_b = {b: F.takahashi_alexander(replace(base, bow=b)).tvpi() for b in bows}
    title_block(
        fig,
        "Bow, growth and pace: what each parameter does",
        f"Left: a higher bow holds distributions back - with growth fixed at 13% the IRR stays at 13%, but the multiple rises from "
        f"{tv_b[1.0]:.2f} (bow 1) to {tv_b[5.0]:.2f} (bow 5), because capital stays invested longer. Middle: growth scales the NAV. "
        "Right: the call schedule decides how fast the commitment is put to work - and how long uncalled cash sits idle.",
    )
    ax = fig.add_axes((0.05, 0.13, 0.27, 0.58))
    for b, c in zip(bows, SERIES, strict=False):
        f = F.takahashi_alexander(replace(base, bow=b)).frame()
        ax.plot(f.index, f["distributions"], color=c, lw=1.8, marker="o", ms=3, label=f"bow {b:g} (TVPI {tv_b[b]:.2f})")
    tidy(ax, title="Distributions by bow", xlabel="year", ylabel="per 100 committed")
    ax.legend(fontsize=8)
    bx = fig.add_axes((0.38, 0.13, 0.27, 0.58))
    for g, c in zip(growths, SERIES, strict=False):
        f = F.takahashi_alexander(replace(base, growth=g)).frame()
        bx.plot(f.index, f["nav"], color=c, lw=1.8, marker="o", ms=3, label=f"growth {100 * g:.0f}%")
    tidy(bx, title="NAV by growth", xlabel="year")
    bx.legend(fontsize=8)
    cx = fig.add_axes((0.71, 0.13, 0.27, 0.58))
    for (name, rc), c in zip(schedules, SERIES, strict=False):
        f = F.takahashi_alexander(replace(base, rc=rc)).frame()
        cx.plot(f.index, f["cum_calls"], color=c, lw=1.8, marker="o", ms=3, label=name)
    tidy(cx, title="Cumulative calls by pace", xlabel="year")
    cx.legend(fontsize=8)
    del irr_b
    caption(fig, "Takahashi-Alexander model; one parameter varied at a time from the base case (growth 13%, bow 2.5, life 12).")
    return fig


# ------------------------------------------------------------------ 3-4. calibration


def ta_fit_deals() -> Figure:
    cc, cd, nv, scc, scd, snv = _deal_curves()
    fit = F.calibrate(cc, cd, nv, rc_years=5)
    f = F.takahashi_alexander(fit.params).frame()
    years = np.arange(1, 13)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Eight parameters reproduce a fund built deal by deal",
        f"The Takahashi-Alexander model fitted to the average of {max(60, SIMS // 20)} bottom-up funds (Day 1's stylised fund: fifteen "
        f"deals, 2% fees, 3% alpha, deal volatility 25%). Fitted growth {100 * fit.params.growth:.1f}%, bow {fit.params.bow:.2f}; the "
        f"fit misses by {100 * fit.rmse:.1f}% of commitment on average across the three curves. Shaded bands show one standard "
        "deviation across individual funds: the model describes the average fund, not any one.",
    )
    for k, (obs, sd, fitted, name, colour) in enumerate(
        [
            (cc, scc, f["cum_calls"], "Cumulative calls", PALETTE["slate"]),
            (cd, scd, f["cum_distributions"], "Cumulative distributions", PALETTE["blue"]),
            (nv, snv, f["nav"], "NAV", PALETTE["violet"]),
        ]
    ):
        ax = fig.add_axes((0.05 + 0.33 * k, 0.13, 0.27, 0.58))
        ax.fill_between(years, obs - sd, obs + sd, color=colour, alpha=0.15)
        ax.plot(years, obs, "o", color=colour, ms=5, label="bottom-up funds (mean)")
        ax.plot(years, fitted.to_numpy(), color=PALETTE["ink"], lw=1.8, label="fitted model")
        tidy(ax, title=name, xlabel="year", ylabel="per 100 committed" if k == 0 else None)
        ax.legend(fontsize=8, loc="upper left")
    caption(
        fig,
        "Least squares on all three curves (in units of commitment); call rates for years 1-5 and a tail rate are free, life fixed at 12.",
    )
    return fig


@lru_cache(maxsize=1)
def _recovery() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    true = F.TAParams()
    base = F.takahashi_alexander(true).frame()
    rows = []
    for _ in range(120):
        noise = 1.0 + 0.08 * rng.standard_normal((12, 3))
        fit = F.calibrate(
            base["cum_calls"] * noise[:, 0], base["cum_distributions"] * noise[:, 1], base["nav"] * noise[:, 2], rc_years=4
        )
        rows.append({"growth": fit.params.growth, "bow": fit.params.bow, "rc1": fit.params.rc[0], "rmse": fit.rmse})
    return pd.DataFrame(rows)


def ta_recovery() -> Figure:
    r = _recovery()
    true = F.TAParams()
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "With noisy data the parameters are recovered without bias, within a few per cent",
        f"Parameters re-estimated from the base model's curves with 8% multiplicative noise in every point, 120 times. Growth: true "
        f"13.0%, estimates {100 * r['growth'].mean():.1f}% on average (standard deviation {100 * r['growth'].std():.1f} points). Bow: "
        f"true 2.50, estimates {r['bow'].mean():.2f} (standard deviation {r['bow'].std():.2f}). Without noise both are recovered to "
        "within 1e-6.",
    )
    for k, (col, truth, label, scale) in enumerate(
        [
            ("growth", true.growth, "growth G", 100),
            ("bow", true.bow, "bow B", 1),
            ("rc1", true.rc[0], "first-year call rate", 100),
        ]
    ):
        ax = fig.add_axes((0.05 + 0.33 * k, 0.13, 0.27, 0.58))
        ax.hist(scale * r[col], bins=24, color=SERIES[k], alpha=0.8)
        ax.axvline(scale * truth, color=PALETTE["ink"], lw=1.6, label="true value")
        tidy(ax, title=label, xlabel=label + (", %" if scale == 100 else ""), ylabel="estimates" if k == 0 else None)
        ax.legend(fontsize=8)
    caption(
        fig,
        "Least-squares calibration (pmlab.fundmodel.calibrate) on year-end cumulative calls, cumulative distributions and NAV.",
    )
    return fig


# ------------------------------------------------------------------ 5-9. the stochastic model


def stochastic_fan() -> Figure:
    p = _paths()
    t = p.times
    cum = np.cumsum(p.net, axis=1)
    qs = [5, 25, 50, 75, 95]
    nav_q = np.percentile(p.value, qs, axis=0)
    cum_q = np.percentile(cum, qs, axis=0)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "One model, many futures: the spread of NAVs and cash flows",
        f"{SIMS:,} model funds. The median NAV peaks at {nav_q[2].max():.0f} per 100 committed; the 5th-95th percentile range at that "
        f"point runs from {nav_q[0][np.argmax(nav_q[2])]:.0f} to {nav_q[4][np.argmax(nav_q[2])]:.0f}. The median investor is "
        f"{-cum_q[2].min():.0f} out of pocket at the trough and ends {cum_q[2][-1]:+.0f}; one fund in twenty ends below "
        f"{cum_q[0][-1]:+.0f}, one in twenty above {cum_q[4][-1]:+.0f}.",
    )
    for k, (q, title) in enumerate([(nav_q, "True NAV"), (cum_q, "Cumulative net cash flow")]):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        ax.fill_between(t, q[0], q[4], color=PALETTE["blue"], alpha=0.15, label="5th-95th percentile")
        ax.fill_between(t, q[1], q[3], color=PALETTE["blue"], alpha=0.3, label="25th-75th")
        ax.plot(t, q[2], color=PALETTE["ink"], lw=2, label="median")
        ax.axhline(0, color=PALETTE["ink"], lw=0.7)
        tidy(ax, title=title, xlabel="years", ylabel="per 100 committed")
        ax.legend(fontsize=8, loc="upper left")
    caption(fig, MODEL + " Call and distribution rates with 50% noise; quarterly.")
    return fig


def outcomes() -> Figure:
    p = _paths()
    irr = p.irrs(min(SIMS, 3000))
    tv = p.tvpi()[: irr.size]
    mret = np.prod(p.market[: irr.size], axis=1) ** (1.0 / SPEC.ta.life) - 1.0
    ok = np.isfinite(irr)
    slope, icpt = np.polyfit(mret[ok], irr[ok], 1)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "The market a fund lives through explains much of its outcome",
        f"Outcomes of model funds with the same skill. Median TVPI {np.median(tv):.2f}, median IRR {100 * np.nanmedian(irr):.1f}%; "
        f"{100 * np.mean(tv < 1):.0f}% lose money. Each point a year of market shock over the fund's life adds {slope:.2f} points of "
        f"IRR, and the market explains {100 * np.corrcoef(mret[ok], irr[ok])[0, 1] ** 2:.0f}% of the variation in IRRs; the rest is "
        "the fund's own risk.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.hist(np.clip(tv, 0, 6), bins=60, color=PALETTE["blue"], alpha=0.8)
    ax.axvline(1.0, color=PALETTE["red"], lw=1.2)
    ax.axvline(np.median(tv), color=PALETTE["ink"], lw=1.2, ls="--")
    tidy(ax, title="TVPI", xlabel="multiple (6 = 6 or more)", ylabel="funds")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.scatter(100 * mret, 100 * irr, s=4, color=PALETTE["violet"], alpha=0.35)
    g = np.linspace(float(np.min(mret[ok])), float(np.max(mret[ok])), 10)
    bx.plot(100 * g, 100 * (icpt + slope * g), color=PALETTE["ink"], lw=1.8)
    tidy(
        bx,
        title="IRR against the market over the fund's life",
        xlabel="market shock (zero-mean market return), % a year",
        ylabel="fund IRR, %",
    )
    caption(fig, MODEL)
    return fig


@lru_cache(maxsize=1)
def _vintages() -> pd.DataFrame:
    return F.vintage_study(SPEC, vintages=25, funds=max(40, SIMS // 25), seed=2)


def vintage_dispersion() -> Figure:
    d = _vintages()
    split = F.variance_split(d)
    order = d.groupby("vintage")["market"].first().sort_values().index
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Vintage matters: funds of one year rise and fall together",
        f"Twenty-five vintages of model funds; funds of a vintage share one market path, differ in their own risk. "
        f"{100 * split['between_share']:.0f}% of the variance of IRRs lies between vintages, {100 * (1 - split['between_share']):.0f}% "
        "within them. Comparing a fund with its vintage peers - quartile rankings, PMEs - removes almost half of the noise; "
        "comparing across vintages partly compares markets.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    data = [100 * d.loc[d["vintage"] == v, "irr"].dropna().to_numpy() for v in order]
    bp = ax.boxplot(data, positions=range(len(order)), widths=0.6, patch_artist=True, showfliers=False)
    for b in bp["boxes"]:
        b.set_facecolor(PALETTE["blue"])
        b.set_alpha(0.5)
    for key in ("medians", "whiskers", "caps"):
        for line in bp[key]:
            line.set_color(PALETTE["ink"])
    m = d.groupby("vintage")["market"].first().reindex(order)
    ax.plot(
        range(len(order)),
        100 * m.to_numpy(),
        color=PALETTE["accent"],
        marker="o",
        ms=4,
        lw=1.2,
        label="market shock over the vintage's life, % a year (zero mean)",
    )
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([str(int(v) + 1) for v in order], fontsize=7.5)
    tidy(ax, xlabel="vintage (sorted by the market shock it lived through)", ylabel="IRR, %")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(fig, MODEL + f" {max(40, SIMS // 25)} funds per vintage.")
    return fig


def capital_calls() -> Figure:
    p = _paths()
    ann = p.annual_calls()
    yrs = np.arange(1, ann.shape[1] + 1)
    q = np.percentile(ann, [50, 95, 99], axis=0)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Capital calls are uncertain: plan for the 95th percentile, not the median",
        f"Calls per year per 100 committed. In year 1 the median fund calls {q[0][0]:.0f}, but one in twenty calls {q[1][0]:.0f} and "
        f"one in a hundred {q[2][0]:.0f}; in year 2 the 95th percentile is {q[1][1]:.0f} against a median of {q[0][1]:.0f}. An investor "
        "with many commitments must hold liquid reserves for the bad tail of calls - the problem of commitment pacing (Day 8).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    bp = ax.boxplot([ann[:, k] for k in range(5)], positions=yrs[:5], widths=0.5, patch_artist=True, showfliers=False)
    for b in bp["boxes"]:
        b.set_facecolor(PALETTE["slate"])
        b.set_alpha(0.5)
    for line in bp["medians"]:
        line.set_color(PALETTE["ink"])
    ax.plot(yrs[:5], q[1][:5], color=PALETTE["red"], marker="o", lw=1.5, label="95th percentile")
    ax.plot(yrs[:5], q[2][:5], color=PALETTE["red"], marker="o", lw=1, ls="--", label="99th percentile")
    tidy(ax, xlabel="year of the fund", ylabel="calls in the year, per 100 committed")
    ax.legend(fontsize=8.5)
    caption(
        fig,
        MODEL + " Call rates with 50% lognormal noise.",
    )
    return fig


def smoothing() -> Figure:
    p = _paths()
    i = int(np.argmin(np.abs(p.value[:, 20] - np.median(p.value[:, 20]))))
    true_r = np.diff(p.value, axis=1) - np.diff(np.cumsum(p.calls - p.distributions, axis=1), axis=1)
    rep_r = np.diff(p.reported, axis=1) - np.diff(np.cumsum(p.calls - p.distributions, axis=1), axis=1)
    base = p.value[:, :-1]
    base_r = p.reported[:, :-1]
    ok = (base > 5) & (base_r > 5)
    vt = np.nanstd(np.where(ok, true_r / np.where(ok, base, 1), np.nan), axis=1)
    vr = np.nanstd(np.where(ok, rep_r / np.where(ok, base_r, 1), np.nan), axis=1)
    ratio = float(np.nanmedian(vr / vt))
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Reported NAVs lag the true value and understate risk",
        f"Appraisals move {100 * SPEC.smoothing:.0f}% of the way to the true value each quarter. Left: one fund's true and reported "
        f"NAV. Right: across {SIMS:,} funds the reported quarterly returns have a median volatility of {100 * ratio:.0f}% of the true "
        "volatility. Smoothed NAVs make private assets look safer than they are (Day 6) and leave stale prices that secondary buyers "
        "discount.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.plot(p.times, p.value[i], color=PALETTE["blue"], lw=1.8, label="true value")
    ax.plot(p.times, p.reported[i], color=PALETTE["accent"], lw=1.8, ls="--", label="reported NAV")
    tidy(ax, title="One fund", xlabel="years", ylabel="per 100 committed")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.hist(100 * vr / vt, bins=50, color=PALETTE["violet"], alpha=0.8)
    bx.axvline(100, color=PALETTE["ink"], lw=1)
    tidy(bx, title="Reported volatility as % of true", xlabel="%", ylabel="funds")
    caption(
        fig,
        "Model fund as in the other Day 3 charts. Reported NAV: R_k = a V_k + (1 - a)(R_{k-1} + C_k - D_k), a = 0.4; quarterly returns net of flows.",
    )
    return fig


# ------------------------------------------------------------------ 10-16. the secondary market


def discount_by_age() -> Figure:
    ages = [0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    g = S.discount_grid(SPEC, ages, REQUIRED)
    fig = new_figure(14.5, 6.0)
    at = {r: g[(g["required"] == r)].set_index("age")["discount"] for r in REQUIRED}
    title_block(
        fig,
        "Young funds trade at deep discounts; mature ones close to NAV",
        f"The discount to NAV at which a buyer earns its required return, by fund age. A buyer wanting 15% when the fund is expected "
        f"to earn 11% pays {100 * (1 - at[0.15][2]):.0f}% of NAV in year 2, {100 * (1 - at[0.15][5]):.0f}% in year 5 and "
        f"{100 * (1 - at[0.15][9]):.0f}% in year 9. Young funds carry unfunded commitments - calls the buyer must meet at a return "
        "below its own - against a small NAV; in year 1 at 18% the discount exceeds 100%, so the buyer would have to be paid to take "
        "the interest. At a required return equal to the fund's expected 11%, every discount is zero.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    for r, c in zip(REQUIRED, [PALETTE["muted"], PALETTE["blue"], PALETTE["violet"], PALETTE["red"]], strict=True):
        ax.plot(ages, 100 * at[r].to_numpy(), color=c, marker="o", ms=4, lw=1.8, label=f"required return {100 * r:.0f}%")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_ylim(-5, 100)
    tidy(ax, title="Discount to NAV", xlabel="fund age at purchase, years", ylabel="%")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    sh = g[g["required"] == REQUIRED[0]].set_index("age")["unfunded_share"]
    bx.bar(ages, 100 * sh.to_numpy(), width=0.4, color=PALETTE["slate"])
    tidy(bx, title="Unfunded share of exposure", xlabel="age", ylabel="% of NAV + unfunded")
    caption(
        fig,
        "Model fund as in the other Day 3 charts. Value = expected future distributions minus calls, discounted at the required return.",
    )
    return fig


def discount_heatmap() -> Figure:
    ages = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    req = [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.18, 0.20]
    g = S.discount_grid(SPEC, ages, req).pivot(index="required", columns="age", values="discount")
    fig = new_figure(14.5, 6.4)
    title_block(
        fig,
        "Secondary pricing in one table: age against the buyer's required return",
        f"Discount to NAV, %. Each point of required return above the fund's expected 11% costs about "
        f"{100 * (g.loc[0.14, 5] - g.loc[0.13, 5]):.1f} points of discount in year 5 and {100 * (g.loc[0.14, 2] - g.loc[0.13, 2]):.1f} in "
        "year 2. A buyer that asks less than the fund's expected return pays a premium. Market discounts therefore measure required "
        "returns - liquidity, risk and the buyers' own cost of capital - as much as fund quality. Above 100%, the price is negative.",
    )
    ax = fig.add_axes((0.12, 0.12, 0.72, 0.6))
    data = 100 * g.to_numpy()
    im = ax.imshow(data, cmap="Blues", aspect="auto", vmin=min(0, data.min()), vmax=min(100, data.max()))
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(
                j,
                i,
                f"{data[i, j] + 0.0:.0f}" if abs(data[i, j]) >= 0.5 else "0",
                ha="center",
                va="center",
                fontsize=8.5,
                color="white" if data[i, j] > 50 else PALETTE["ink"],
            )
    ax.set_xticks(range(len(ages)))
    ax.set_xticklabels([str(a) for a in ages])
    ax.set_yticks(range(len(req)))
    ax.set_yticklabels([f"{100 * r:.0f}%" for r in req])
    ax.grid(False)
    tidy(ax, xlabel="fund age at purchase, years", ylabel="buyer's required return")
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label("discount to NAV, %")
    caption(fig, MODEL)
    return fig


def discount_decomposition() -> Figure:
    ages = [1, 2, 3, 4, 5, 6, 7, 8]
    r = 0.15
    parts = [S.decompose(SPEC, S.expected_state(SPEC, a), r) for a in ages]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Where the discount comes from: the assets, and the commitment still to come",
        f"The discount at a 15% required return split into the cost of pricing existing assets at 15% rather than 11%, and the "
        f"loss on future calls invested at 11% but valued at 15%. In year 1 the unfunded commitment is "
        f"{100 * parts[0].unfunded / parts[0].total:.0f}% of the discount; by year 5, when nothing is left to call, none of it. "
        "Staleness adds a third piece after market falls (next chart).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    x = np.arange(len(ages))
    a_ = [100 * p.assets for p in parts]
    u_ = [100 * p.unfunded for p in parts]
    ax.bar(x, a_, color=PALETTE["blue"], width=0.6, label="existing assets priced at 15%")
    ax.bar(x, u_, bottom=a_, color=PALETTE["slate"], width=0.6, label="unfunded commitment")
    for xi, p in zip(x, parts, strict=True):
        ax.text(float(xi), 100 * (p.assets + p.unfunded) + 1, f"{100 * p.total:.0f}%", ha="center", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels([f"year {a}" for a in ages])
    tidy(ax, ylabel="discount to NAV, %")
    ax.legend(fontsize=8.5)
    caption(fig, MODEL + " Pieces in units of NAV; with an up-to-date NAV they add up to the total discount.")
    return fig


def crash_discount() -> Figure:
    c = S.crash(SPEC, 5.0, 0.30, 0.14, 12)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "After a market fall, secondary discounts widen because NAVs are stale",
        f"A 30% fall in the true value of a five-year-old fund. The buyer, requiring 14%, prices the true value: a discount of "
        f"{100 * c['discount_to_true'].iloc[0]:.0f}% to it, but {100 * c['discount_to_reported'].iloc[0]:.0f}% to the reported NAV, "
        f"which has not yet moved. As appraisals catch up the quoted discount narrows to {100 * c['discount_to_reported'].iloc[4]:.0f}% "
        "after a year with no further shock - the pattern of 2008-09 and 2022.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.plot(c.index, c["true"], color=PALETTE["blue"], lw=2, marker="o", ms=3, label="true value")
    ax.plot(c.index, c["reported"], color=PALETTE["accent"], lw=2, ls="--", marker="o", ms=3, label="reported NAV")
    tidy(ax, title="True and reported NAV after the fall", xlabel="quarters after the fall", ylabel="per 100 committed")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.plot(c.index, 100 * c["discount_to_reported"], color=PALETTE["red"], lw=2, marker="o", ms=3, label="to the reported NAV")
    bx.plot(c.index, 100 * c["discount_to_true"], color=PALETTE["blue"], lw=2, marker="o", ms=3, label="to the true value")
    bx.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(bx, title="Discount quoted", xlabel="quarters after the fall", ylabel="%")
    bx.legend(fontsize=8.5)
    caption(
        fig,
        "Model fund as in the other Day 3 charts. Appraisal smoothing a = 0.4 a quarter; after the fall the true value follows its expected path.",
    )
    return fig


def buyer_irr() -> Figure:
    st = S.expected_state(SPEC, 4.0)
    prices = [0.7, 0.85, 1.0]
    irrs = {p: S.buyer_irrs(SPEC, st, p, min(SIMS, 3000), seed=7) for p in prices}
    fig = new_figure(14.5, 6.0)
    q = {p: np.nanpercentile(irrs[p], [10, 50, 90]) for p in prices}
    title_block(
        fig,
        "Buying at a discount shifts the whole distribution of returns",
        f"Buyer IRRs on a four-year-old fund bought at 70%, 85% and 100% of NAV. At NAV the median buyer earns "
        f"{100 * q[1.0][1]:.1f}%; at 85% of NAV, {100 * q[0.85][1]:.1f}%; at 70%, {100 * q[0.7][1]:.1f}%. The spread stays wide - the "
        f"10th to 90th percentile at 85% runs from {100 * q[0.85][0]:.0f}% to {100 * q[0.85][2]:.0f}% - because a discount buys "
        "return, not certainty.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    bins = list(np.linspace(-0.3, 0.8, 70))
    for p, c in zip(prices, [PALETTE["green"], PALETTE["blue"], PALETTE["slate"]], strict=True):
        ax.hist(
            np.clip(irrs[p], -0.3, 0.8),
            bins=bins,
            color=c,
            alpha=0.45,
            label=f"bought at {100 * p:.0f}% of NAV (median {100 * q[p][1]:.1f}%)",
        )
    ax.xaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    tidy(ax, xlabel="buyer's IRR", ylabel="futures")
    ax.legend(fontsize=8.5)
    caption(fig, MODEL + f" {min(SIMS, 3000):,} simulated futures from the fund's expected state in year 4.")
    return fig


def secondary_vs_primary() -> Figure:
    p = _paths()
    primary = np.median(np.cumsum(p.net, axis=1), axis=0)
    st = S.expected_state(SPEC, 4.0)
    d = S.discount(SPEC, st, 0.14)
    price = (1 - d) * st.reported
    sec_paths = F.simulate(SPEC, min(SIMS, 3000), seed=9, start=4.0, value=st.value, reported=st.reported, uncalled=st.uncalled)
    sec = np.median(np.cumsum(sec_paths.net, axis=1), axis=0) - price
    t_sec = np.concatenate([[0.0], sec_paths.times])
    sec = np.concatenate([[-price], sec])
    be_p = p.times[np.argmax(primary >= 0)]
    be_s = t_sec[np.argmax(sec >= 0)]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "A secondary buyer pays up front and gets its money back in half the time",
        f"Median cumulative net cash flow, each investor measured from its own entry. The primary investor commits in year 0, is "
        f"{-float(np.min(primary)):.0f} out of pocket at the trough and breaks even after {be_p:.1f} years. A buyer entering in year 4 at a "
        f"{100 * d:.0f}% discount (priced for 14%) pays {price:.0f} at once - a deeper trough - but breaks even after {be_s:.1f} years. "
        "Secondaries sell the J-curve: the buyer gives up the early years and the commitment risk for a shorter wait.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(p.times, primary, color=PALETTE["slate"], lw=2, label="primary investor, from its commitment in year 0")
    ax.plot(t_sec, sec, color=PALETTE["blue"], lw=2, label="secondary buyer, from its purchase in year 4")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    for be, c in ((be_p, PALETTE["slate"]), (be_s, PALETTE["blue"])):
        ax.axvline(be, color=c, lw=0.9, ls=":")
    tidy(ax, xlabel="years since the investor's own entry", ylabel="cumulative net cash flow, per 100 committed")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(
        fig,
        "Model fund as in the other Day 3 charts. The buyer pays (1 - discount) x reported NAV and takes over the remaining calls.",
    )
    return fig


def mc_check() -> Figure:
    ages = [1, 3, 5, 7]
    rows = []
    for a in ages:
        st = S.expected_state(SPEC, a)
        for r in (0.11, 0.15):
            mc, se = S.monte_carlo_value(SPEC, st, r, min(SIMS * 2, 10000), seed=int(100 * a + 1000 * r))
            rows.append((a, r, S.value(SPEC, st, r), mc, se))
    z = [(m - v) / s for _, _, v, m, s in rows]
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "The expected-path shortcut prices the interest as full simulation does",
        f"Value of an LP interest from the noise-free expected path (bars) against Monte Carlo over the full stochastic model "
        f"(points with 95% intervals). Across {len(rows)} cases the largest gap is {max(abs(x) for x in z):.1f} standard errors. Noise "
        "in calls, distributions and returns averages out because it is mean-one and independent of the fund's value.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    x = np.arange(len(rows))
    ax.bar(
        x,
        [v for _, _, v, _, _ in rows],
        color=[PALETTE["blue"] if r == 0.11 else PALETTE["violet"] for _, r, _, _, _ in rows],
        alpha=0.6,
        width=0.6,
    )
    ax.errorbar(
        x, [m for _, _, _, m, _ in rows], yerr=[1.96 * s for _, _, _, _, s in rows], fmt="o", color=PALETTE["ink"], capsize=3
    )
    ax.set_xticks(x)
    ax.set_xticklabels([f"year {a}\nr = {100 * r:.0f}%" for a, r, _, _, _ in rows], fontsize=8)
    tidy(ax, ylabel="value of the interest, per 100 committed")
    caption(fig, MODEL + f" Monte Carlo with {min(SIMS * 2, 10000):,} futures per case.")
    return fig
