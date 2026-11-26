"""Day 8 charts: allocating to illiquid assets.

An endowment with liquid assets (70% public equity, 30% bonds) commits each year to a private
equity programme (Day 3 model: expected return 10%, beta 1.2, 10% own volatility, appraisals catch
40% of the gap a quarter), spends 4% of reported wealth a year, and sells on the secondary market
when liquid assets fall below a floor. Every number in a subtitle is computed.
"""

from __future__ import annotations

from functools import cache, lru_cache

import numpy as np
from matplotlib.figure import Figure

from .. import allocation as A
from .style import PALETTE, caption, new_figure, tidy, title_block

SCEN = 1000  # scenarios per programme simulation; the tests lower it
RULES = {
    "constant": A.Pacing(target=0.2, rate=0.035, name="constant 3.5% of wealth a year"),
    "feedback": A.Pacing(target=0.2, rate=0.025, gain=0.25, name="2.5% of wealth + 25% of the gap to a 20% target"),
}
RATES = (0.04, 0.06, 0.08, 0.10, 0.12, 0.14)
FLOORS = (0.05, 0.10, 0.20, 0.30)
CRASH = (40, -0.4)  # a 33% fall in the market in the first quarter of year 11
DP = A.DPSpec(mu_i=0.11)
MODEL = (
    "Model endowment: liquid 70% equity (7%, vol 16%), 30% bonds (2%); PE programme of Day 3 funds (10%, beta 1.2, own vol 10%, a = 0.4); "
    "spending 4%; secondary discount 5% + 0.8 x past-year market fall."
)
COL = {"constant": PALETTE["blue"], "feedback": PALETTE["green"], "true": PALETTE["ink"], "reported": PALETTE["slate"]}


@cache
def _run(rule: str = "", rate: float = 0.0, floor: float = 0.05, crash: bool = False) -> A.Programme:
    pacing = RULES[rule] if rule else A.Pacing(rate=rate, name=f"{rate:.0%}")
    return A.simulate_programme(pacing, scenarios=SCEN, seed=3, floor=floor, crash=CRASH if crash else None)


def _band(ax, t, x, col, label) -> None:  # type: ignore[no-untyped-def]
    lo, med, hi = np.percentile(x, [10, 50, 90], axis=0)
    ax.fill_between(t, 100 * lo, 100 * hi, color=col, alpha=0.15, lw=0)
    ax.plot(t, 100 * med, color=col, lw=2, label=label)


# ------------------------------------------------------------------ 1-3. pacing


def pacing() -> Figure:
    fig = new_figure(14.5, 6.0)
    c, f = _run("constant"), _run("feedback")

    def y(p: A.Programme, yr: int) -> float:
        return float(np.median(p.share_reported[:, 4 * yr - 1]))

    p10, p90 = np.percentile(c.share_reported[:, 79], [10, 90])
    title_block(
        fig,
        "A constant commitment rate takes a decade to build a 20% allocation and then holds it",
        f"Private equity share of reported wealth, median and 10-90% band over {SCEN:,} market histories. Constant 3.5% of wealth a year: {100 * y(c, 5):.0f}% after five "
        f"years, {100 * y(c, 10):.0f}% after ten, {100 * y(c, 20):.0f}% after twenty (10-90%: {100 * p10:.0f}-{100 * p90:.0f}%). The feedback rule gets there faster "
        f"({100 * y(f, 5):.0f}% at five years) but overshoots and settles at {100 * y(f, 20):.0f}%: steering on a lagging NAV cuts commitments too late.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for k, p in (("constant", c), ("feedback", f)):
        _band(ax, p.times, p.share_reported, COL[k], RULES[k].name)
    ax.axhline(20, color=PALETTE["ink"], lw=0.8, ls="--")
    ax.legend(frameon=False, loc="lower right")
    tidy(ax, xlabel="years", ylabel="private equity, % of reported wealth")
    caption(fig, MODEL)
    return fig


def commitments() -> Figure:
    fig = new_figure(14.5, 6.0)
    c, f = _run("constant"), _run("feedback")
    oc = np.nanmedian(c.overcommitment[:, 79])
    exposure = np.median((c.nav_reported + c.unfunded)[:, 79] / c.wealth_reported[:, 79])
    held = np.median(c.share_reported[:, 79])
    title_block(
        fig,
        f"To hold {100 * held:.0f}% in private equity the investor must have about {100 * exposure:.0f}% of wealth committed",
        f"Left: commitments each year, % of reported wealth (median and 10-90%). Right: (NAV + unfunded commitments) / NAV. With the constant rule the ratio settles at "
        f"{oc:.2f} after twenty years; the feedback rule's commitments swing between {100 * np.percentile(f.commitments[:, 10:], 10):.1f}% and "
        f"{100 * np.percentile(f.commitments[:, 10:], 90):.1f}% of wealth a year after year ten.",
    )
    a1 = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    a2 = fig.add_axes((0.55, 0.13, 0.42, 0.58))
    yrs = np.arange(c.commitments.shape[1])
    for k, p in (("constant", c), ("feedback", f)):
        w = p.wealth_reported[:, ::4][:, : yrs.size]
        _band(a1, yrs, p.commitments / np.where(w > 0, w, np.nan), COL[k], RULES[k].name)
        _band(a2, p.times[8:], p.overcommitment[:, 8:], COL[k], RULES[k].name)
    a2.set_ylim(80, 400)
    a1.legend(frameon=False, loc="upper right", fontsize=8)
    tidy(a1, title="Commitments", xlabel="year", ylabel="% of reported wealth")
    tidy(a2, title="Overcommitment ratio, %", xlabel="years", ylabel="(NAV + unfunded) / NAV, %")
    caption(fig, MODEL)
    return fig


def cashflows() -> Figure:
    fig = new_figure(14.5, 6.0)
    c = _run("constant")
    w = c.wealth_reported
    net = (c.distributions - c.calls).reshape(SCEN, -1, 4).sum(axis=2) / w[:, 3::4]
    med = np.median(net, axis=0)
    first = int(np.argmax(med > 0)) + 1 if (med > 0).any() else -1
    title_block(
        fig,
        "The programme drains liquidity for its first years and pays for itself only later",
        f"Net cash flow of the programme (distributions minus calls), % of reported wealth each year, constant 3.5% rule. Median: {100 * med[0]:.1f}% in year one, "
        f"{100 * med[4]:.1f}% in year five; first positive in year {first}; {100 * np.median(med[20:]):+.1f}% a year after year twenty. In the worst tenth of histories "
        f"the year-twenty figure is {100 * np.percentile(net[:, 19], 10):+.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    _band(ax, np.arange(1, net.shape[1] + 1), net, COL["constant"], "net cash flow")
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    tidy(ax, xlabel="year", ylabel="% of reported wealth")
    caption(fig, MODEL)
    return fig


# ------------------------------------------------------------------ 4-5. a crash


def denominator() -> Figure:
    p, q = _run(rate=0.06, crash=True), _run(rate=0.06)
    k0 = CRASH[0]
    win = np.arange(k0 - 8, k0 + 24)
    t = (win - k0) / 4
    fig = new_figure(14.5, 6.0)
    rep = np.median(p.share_reported[:, win], axis=0)
    tru = np.median(p.share_true[:, win], axis=0)
    base = np.median(q.share_reported[:, win], axis=0)
    i = int(np.argmin(np.abs(t)))  # the quarter of the crash
    title_block(
        fig,
        "The denominator effect: in a crash the reported allocation jumps while the true one falls",
        f"Private equity share of wealth around a 33% market fall (one quarter), commitment rate 6% a year. In the quarter of the fall the reported share jumps to "
        f"{100 * rep[i]:.0f}% (without the fall {100 * base[i]:.0f}%) while the true share drops to {100 * tru[i]:.0f}%: appraisals have not caught up. An investor with "
        "a 35% limit would stop committing on numbers that point the wrong way. Later both shares rise, as the programme's beta of 1.2 recovers faster than liquid assets.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    ax.plot(t, 100 * rep, color=COL["reported"], lw=2, label="reported share, crash")
    ax.plot(t, 100 * tru, color=COL["true"], lw=2, ls="--", label="true share, crash")
    ax.plot(t, 100 * base, color=PALETTE["muted"], lw=1.4, ls=":", label="reported share, no crash")
    ax.axvline(0, color=PALETTE["red"], lw=1)
    ax.legend(frameon=False, loc="lower right")
    tidy(ax, xlabel="years from the crash", ylabel="private equity, % of wealth (median)")
    caption(fig, MODEL + " Crash: log shock -0.4, year 11.")
    return fig


def crisis_flows() -> Figure:
    p, q = _run(rate=0.06, crash=True), _run(rate=0.06)
    k0 = CRASH[0]
    win = np.arange(k0 - 4, k0 + 16)
    t = (win - k0) / 4
    fig = new_figure(14.5, 6.0)
    dc = np.mean(p.distributions[:, k0 : k0 + 8].sum(1)) / np.mean(q.distributions[:, k0 : k0 + 8].sum(1)) - 1
    cc = np.mean(p.calls[:, k0 : k0 + 8].sum(1)) / np.mean(q.calls[:, k0 : k0 + 8].sum(1)) - 1
    title_block(
        fig,
        "In a crash distributions dry up while calls keep coming",
        f"Mean quarterly calls and distributions, % of initial wealth, with and without the crash. Over the two years after it, distributions are {100 * dc:+.0f}% "
        f"and calls {100 * cc:+.0f}% against the no-crash histories. Calls depend on uncalled commitments, which the crash does not change; "
        "distributions depend on fund values, which it does.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for arr, lab, col in ((p.calls, "calls, crash", PALETTE["red"]), (p.distributions, "distributions, crash", PALETTE["blue"])):
        ax.plot(t, 100 * arr[:, win].mean(0), color=col, lw=2, label=lab)
    for arr, lab, col in (
        (q.calls, "calls, no crash", PALETTE["red"]),
        (q.distributions, "distributions, no crash", PALETTE["blue"]),
    ):
        ax.plot(t, 100 * arr[:, win].mean(0), color=col, lw=1.2, ls=":", label=lab)
    ax.axvline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper right", ncol=2)
    tidy(ax, xlabel="years from the crash", ylabel="% of initial wealth a quarter")
    caption(fig, MODEL)
    return fig


# ------------------------------------------------------------------ 6-7. liquidity


@lru_cache(maxsize=1)
def _grid() -> dict[str, np.ndarray]:
    prob = np.zeros((len(RATES), len(FLOORS)))
    prob_c = np.zeros_like(prob)
    cost = np.zeros_like(prob)
    cost_c = np.zeros_like(prob)
    share = np.zeros(len(RATES))
    for i, r in enumerate(RATES):
        for j, fl in enumerate(FLOORS):
            p, c = _run(rate=r, floor=fl), _run(rate=r, floor=fl, crash=True)
            prob[i, j] = (p.sold.sum(1) > 0).mean()
            prob_c[i, j] = (c.sold.sum(1) > 0).mean()
            cost[i, j] = p.sale_cost.sum(1).mean()
            cost_c[i, j] = c.sale_cost.sum(1).mean()
        share[i] = np.median(_run(rate=r).share_reported[:, 80:])
    return {"prob": prob, "prob_c": prob_c, "cost": cost, "cost_c": cost_c, "share": share}


def liquidity() -> Figure:
    g = _grid()
    fig = new_figure(14.5, 6.2)
    j10 = FLOORS.index(0.10)
    safe = [f"{100 * g['share'][i]:.0f}%" for i in range(len(RATES)) if g["prob_c"][i, j10] < 0.01]
    title_block(
        fig,
        "Forced secondary sales are rare until private equity passes half of wealth",
        f"Probability of at least one forced sale in 30 years, by commitment rate (median steady-state allocation in brackets) and the liquidity floor the investor keeps. "
        f"With a 10% floor and a crash in year 11, the probability stays below 1% up to a {safe[-1] if safe else 'n/a'} allocation and reaches "
        f"{100 * g['prob_c'][-1, j10]:.0f}% at {100 * g['share'][-1]:.0f}%.",
    )
    for k, (key, lab) in enumerate((("prob", "No crash"), ("prob_c", "Crash in year 11"))):
        ax = fig.add_axes((0.06 + 0.49 * k, 0.15, 0.4, 0.55))
        im = ax.imshow(100 * g[key], cmap="Blues", vmin=0, vmax=100, aspect="auto")
        for i in range(len(RATES)):
            for j in range(len(FLOORS)):
                v = 100 * g[key][i, j]
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8, color="white" if v > 55 else PALETTE["ink"])
        ax.set_xticks(range(len(FLOORS)), [f"{100 * f:.0f}%" for f in FLOORS])
        ax.set_yticks(range(len(RATES)), [f"{100 * r:.0f}% ({100 * s:.0f}%)" for r, s in zip(RATES, g["share"], strict=True)])
        ax.grid(False)
        tidy(ax, title=lab, xlabel="liquidity floor, % of wealth", ylabel="commitment rate (allocation)")
    fig.colorbar(im, ax=fig.axes, shrink=0.6, label="probability, %")
    caption(fig, MODEL)
    return fig


def sale_cost() -> Figure:
    g = _grid()
    fig = new_figure(14.5, 6.0)
    j = FLOORS.index(0.20)
    title_block(
        fig,
        "Selling into a crash is what makes illiquidity expensive",
        f"Mean discount paid on forced secondary sales over 30 years, % of initial wealth, 20% liquidity floor. At the highest commitment rate "
        f"({100 * g['share'][-1]:.0f}% allocation): {100 * g['cost'][-1, j]:.1f}% without a crash and {100 * g['cost_c'][-1, j]:.1f}% with one. Below a "
        f"{100 * g['share'][3]:.0f}% allocation the cost is under {max(0.1, 100 * g['cost_c'][3, j]):.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for jj, fl in enumerate(FLOORS):
        col = (PALETTE["green"], PALETTE["teal"], PALETTE["blue"], PALETTE["violet"])[jj]
        ax.plot(100 * g["share"], 100 * g["cost_c"][:, jj], "o-", color=col, lw=1.8, label=f"floor {100 * fl:.0f}%, crash")
        ax.plot(100 * g["share"], 100 * g["cost"][:, jj], "o:", color=col, lw=1.0, label=f"floor {100 * fl:.0f}%, no crash")
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=8)
    tidy(ax, xlabel="median steady-state private equity allocation, %", ylabel="discount paid, % of initial wealth")
    caption(fig, MODEL)
    return fig


# ------------------------------------------------------------------ 8-10. how much to hold


def mean_variance() -> Figure:
    m = A.programme_moments()
    mk = A.Market()
    gam = np.linspace(2, 10, 33)
    out = {}
    for k in ("true", "reported"):
        mu = np.array([mk.mu, m[f"{k}_mean"]])
        sd = np.array([mk.vol, m[f"{k}_vol"]])
        cov = np.outer(sd, sd) * np.array([[1, m[f"{k}_corr"]], [m[f"{k}_corr"], 1]])
        out[k] = np.array([A.mean_variance(mu, cov, mk.r, g) for g in gam])
    i5 = int(np.argmin(np.abs(gam - 5)))
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"Mean-variance on reported NAVs puts {out['reported'][i5, 1] / out['true'][i5, 1]:.1f} times as much in private equity as on true moments",
        f"Unconstrained mean-variance weights in public equity and private equity by risk aversion. Programme moments: reported volatility {100 * m['reported_vol']:.0f}% "
        f"and market correlation {m['reported_corr']:.2f}; true {100 * m['true_vol']:.0f}% and {m['true_corr']:.2f}. At risk aversion 5: private equity "
        f"{100 * out['reported'][i5, 1]:.0f}% on reported moments, {100 * out['true'][i5, 1]:.0f}% on true moments. Unconstrained weights: the reported case borrows and shorts public equity.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    ax.plot(gam, 100 * out["reported"][:, 1], color=COL["reported"], lw=2, label="private equity, reported moments")
    ax.plot(gam, 100 * out["true"][:, 1], color=COL["true"], lw=2, label="private equity, true moments")
    ax.plot(gam, 100 * out["reported"][:, 0], color=COL["reported"], lw=1.2, ls=":", label="public equity, reported moments")
    ax.plot(gam, 100 * out["true"][:, 0], color=COL["true"], lw=1.2, ls=":", label="public equity, true moments")
    ax.axhline(0, color=PALETTE["muted"], lw=0.6)
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, xlabel="risk aversion", ylabel="weight, % of wealth")
    caption(fig, MODEL + " Moments: funds aged 4-8.")
    return fig


@cache
def _dp(mu_i: float, lam: float, gamma: float = 5.0) -> A.DPSolution:
    return A.solve_dp(A.with_dp(DP, mu_i=mu_i, gamma=gamma), lam)


LAMS = (1.0, 0.5, 1 / 3, 0.2, 0.1, 0.05)


def dp_target() -> Figure:
    fig = new_figure(14.5, 6.0)
    mus = (0.09, 0.11, 0.13)
    t = {m: [_dp(m, lam).target for lam in LAMS] for m in mus}
    title_block(
        fig,
        "Rebalancing only every few years trims the optimal illiquid allocation, but only a little",
        f"Optimal illiquid share for a CRRA investor (risk aversion 5, 20-year horizon) when the illiquid asset can be rebalanced with probability lambda a year. "
        f"Expected return 11%: {100 * t[0.11][0]:.0f}% when fully liquid, {100 * t[0.11][-2]:.0f}% when rebalanced once a decade on average. 9%: "
        f"{100 * t[0.09][0]:.0f}% to {100 * t[0.09][-2]:.0f}%; 13%: {100 * t[0.13][0]:.0f}% to {100 * t[0.13][-2]:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    x = 1 / np.array(LAMS)
    for m, col in zip(mus, (PALETTE["slate"], PALETTE["blue"], PALETTE["violet"]), strict=True):
        ax.plot(x, 100 * np.array(t[m]), "o-", color=col, lw=2, label=f"illiquid expected return {100 * m:.0f}%")
    ax.set_xscale("log")
    ax.set_xticks(x, [f"{v:.0f}" for v in x])
    ax.minorticks_off()
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, xlabel="average years between rebalancing opportunities (1 / lambda)", ylabel="optimal illiquid share, %")
    caption(
        fig,
        "Illiquid asset: beta 1.2 to public equity (7%, vol 16%), own vol 15%; bonds 2%. Grid of 1% steps; Gauss-Hermite quadrature 7 x 5 nodes.",
    )
    return fig


def dp_policy() -> Figure:
    fig = new_figure(14.5, 6.0)
    cost = [A.illiquidity_cost(A.with_dp(DP, mu_i=0.11), lam, _dp(0.11, 1.0)) for lam in LAMS[1:]]
    s1, s10 = _dp(0.11, 1.0), _dp(0.11, 0.1)
    i0, i40 = 0, int(round(0.4 / 0.01))
    title_block(
        fig,
        "Illiquidity costs little in certainty-equivalent terms; the investor offsets it in the liquid portfolio",
        f"Left: wealth a year the investor would give up for full liquidity (expected return 11%): {100 * cost[-2]:.2f}% when rebalanced once a decade, "
        f"{100 * cost[-1]:.2f}% once in twenty years. Right: optimal equity share of the liquid part by illiquid share. With no illiquid assets it is "
        f"{100 * s1.alpha[i0]:.0f}%; at a 40% illiquid share it falls to {100 * s10.alpha[i40]:.0f}%: the liquid part becomes the shock absorber.",
    )
    a1 = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    a2 = fig.add_axes((0.55, 0.13, 0.42, 0.58))
    a1.plot(1 / np.array(LAMS[1:]), 100 * np.array(cost), "o-", color=PALETTE["blue"], lw=2)
    a1.set_xscale("log")
    a1.set_xticks(1 / np.array(LAMS[1:]), [f"{1 / v:.0f}" for v in LAMS[1:]])
    a1.minorticks_off()
    tidy(a1, title="Cost of illiquidity", xlabel="average years between rebalancing", ylabel="% of wealth a year")
    for s, lab, col in ((s1, "fully liquid", PALETTE["slate"]), (s10, "rebalanced once a decade", PALETTE["blue"])):
        a2.plot(100 * s.theta, 100 * s.alpha, color=col, lw=2, label=lab)
    a2.legend(frameon=False)
    tidy(a2, title="Equity share of the liquid part", xlabel="illiquid share, %", ylabel="%")
    caption(
        fig,
        "CRRA risk aversion 5, 20-year horizon; utility of terminal wealth. Ang, Papanikolaou and Westerfield (2014) style rebalancing at random times.",
    )
    return fig
