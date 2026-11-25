"""Day 7 charts: risk-adjusted performance with a stochastic discount factor.

Model funds (Day 1 deal-built fund: 15 deals, 30% own volatility per deal) on log-normal markets
(drift 8%, volatility 16%, bond 2%), and on the S&P 500 total-return path from 1988. A fund is
"fairly priced" when its deals earn the drift that the true SDF prices at zero. Every number in a
subtitle is computed.
"""

from __future__ import annotations

from functools import cache, lru_cache

import numpy as np
from matplotlib.figure import Figure

from .. import gpme as G
from .. import market
from .. import synthetic as Y
from .style import PALETTE, caption, new_figure, tidy, title_block

SIMS = 400  # funds per Monte Carlo cell; the tests lower it
REPS = 20  # repeated samples for the cash-flow beta charts; the tests lower it
MU, SIG, R = 0.08, 0.16, 0.02
TRUE = G.SDF.lognormal(MU, SIG, R)
KS = G.SDF.kaplan_schoar()
BETAS = (0.5, 1.0, 1.5, 2.0, 2.5)
MODEL = (
    "Model funds: 15 deals bought over 5 years, held 3-7, 30% own volatility each; market log-normal, drift 8%, volatility 16%; bond 2%. "
    "True SDF prices the market and the bond: b = (mu - r) / sigma^2."
)
COL = {"gpme": PALETTE["blue"], "ks": PALETTE["slate"], "true": PALETTE["ink"]}


def _fund(beta: float, alpha: float, s: int, fee: float = 0.0, seed0: int = 1000) -> Y.Fund:
    m = Y.gbm_market(13, MU, SIG, seed=seed0 + s)
    return Y.simulate_fund(m, Y.FundSpec(beta=beta, alpha=alpha, idio=0.3, fee=fee, seed=s))


@cache
def _cell(beta: float, excess: float = 0.0, fee: float = 0.0, seed0: int = 1000, scale: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """GPME and KS-PME (as NPV per unit called) of ``scale * SIMS`` funds with drift = fair alpha + ``excess``."""
    a = G.fair_alpha(beta, TRUE, MU, SIG) + excess
    n = scale * SIMS
    g, k = np.empty(n), np.empty(n)
    for s in range(n):
        f = _fund(beta, a, s, fee, seed0)
        g[s] = G.gpme(f.times, f.amounts, f.index, TRUE)
        k[s] = G.gpme(f.times, f.amounts, f.index, KS)
    return g, k


@lru_cache(maxsize=1)
def _sp() -> tuple[Y.Market, G.SDF, float, float]:
    mk = Y.market_from_series(market.load("sp500"))
    x = np.diff(np.log(mk.levels))
    sigma = float(np.sqrt(12 * x.var(ddof=1)))
    mu = float(12 * x.mean() + 0.5 * sigma**2)
    return mk, G.SDF.fit(mk.levels, 1 / 12, R), mu, sigma


@cache
def _dlp(beta: float, n: int, reps: int) -> np.ndarray:
    out = np.empty((reps, 2))
    for j in range(reps):
        funds = []
        for s in range(n):
            f = _fund(beta, 0.0, s, seed0=100_000 * (j + 1) + 7919 * int(10 * beta))
            funds.append((f.times, f.amounts, f.index))
        est = G.cashflow_beta(funds, R)
        out[j] = est.alpha, est.beta
    return out


def _ci(x: np.ndarray) -> float:
    return float(1.96 * x.std(ddof=1) / np.sqrt(x.size))


# ------------------------------------------------------------------ 1-2. the SDF


def sdf() -> Figure:
    mk, fit, mu, sigma = _sp()
    ret = mk.levels[1:] / mk.levels[:-1]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Kaplan-Schoar's PME is an SDF with risk aversion one; the S&P 500's history implies about four",
        f"Monthly discount factor against the S&P 500's monthly gross return, 1988-2026. The SDF that prices the index and a {100 * R:.0f}% bond in this sample "
        f"has b = {fit.b:.2f} (a = {fit.a:+.3f} a year). Kaplan-Schoar's 1/R has b = 1. The index's mean return is {100 * mu:.1f}% a year with "
        f"{100 * sigma:.1f}% volatility, so (mu - r) / sigma^2 = {(mu - R) / sigma**2:.2f}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.6))
    g = np.linspace(ret.min(), ret.max(), 200)
    ax.plot(g, np.exp(-fit.a / 12) * g ** (-fit.b), color=COL["gpme"], lw=2, label=f"GPME SDF, b = {fit.b:.1f}")
    ax.plot(g, 1 / g, color=COL["ks"], lw=2, ls="--", label="Kaplan-Schoar, b = 1")
    ax.hist(ret, bins=60, weights=np.full(ret.size, 0.6 / ret.size * 60 / 1), bottom=0.0, color=PALETTE["band"], zorder=0)
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, xlabel="S&P 500 gross return in the month", ylabel="discount factor M (bars: share of months, scaled)")
    a2 = fig.add_axes((0.69, 0.13, 0.28, 0.6))
    worst, best = ret.argmin(), ret.argmax()
    labels = ["worst month", "median month", "best month"]
    med = np.argsort(ret)[ret.size // 2]
    vals_g = [np.exp(-fit.a / 12) * ret[i] ** (-fit.b) for i in (worst, med, best)]
    vals_k = [1 / ret[i] for i in (worst, med, best)]
    x = np.arange(3)
    a2.bar(x - 0.18, vals_g, 0.34, color=COL["gpme"], label="GPME SDF")
    a2.bar(x + 0.18, vals_k, 0.34, color=COL["ks"], label="KS-PME")
    a2.set_xticks(x, labels)
    a2.legend(frameon=False, loc="upper right")
    tidy(a2, title="Weight on a pound paid in...", ylabel="M")
    caption(
        fig, f"S&P 500 total return (^SP500TR), month-end, from Yahoo; constant {100 * R:.0f}% bond (an assumption, ADR 0018)."
    )
    return fig


def fair_alpha() -> Figure:
    _, fit, mu, sigma = _sp()
    sp_true = G.SDF.lognormal(mu, sigma, R)
    b = np.linspace(0, 3, 61)
    fig = new_figure(14.5, 6.0)
    gap_m = G.fair_alpha(2.0, TRUE, MU, SIG) - G.fair_alpha(2.0, KS, MU, SIG)
    gap_s = G.fair_alpha(2.0, sp_true, mu, sigma) - G.fair_alpha(2.0, KS, mu, sigma)
    title_block(
        fig,
        "KS-PME asks too little of levered funds and too much of unlevered ones",
        f"The drift a deal with market exposure beta needs to break even, under the SDF that prices market and bond and under KS-PME's 1/R. "
        f"A beta-2 fund clears KS-PME with {100 * gap_m:.1f} points a year less than it needs on the model market, and {100 * gap_s:.1f} points less "
        "on the S&P 500's history; the gap is zero at beta one.",
    )
    for k, (m_, s_, sd, lab) in enumerate(
        [
            (MU, SIG, TRUE, "Model market (drift 8%, volatility 16%)"),
            (mu, sigma, sp_true, f"S&P 500 history (drift {100 * mu:.1f}%, volatility {100 * sigma:.1f}%)"),
        ]
    ):
        ax = fig.add_axes((0.06 + 0.49 * k, 0.13, 0.42, 0.58))
        t = np.array([G.fair_alpha(x, sd, m_, s_) for x in b])
        kk = np.array([G.fair_alpha(x, KS, m_, s_) for x in b])
        ax.plot(b, 100 * t, color=COL["gpme"], lw=2, label="needed (true SDF)")
        ax.plot(b, 100 * kk, color=COL["ks"], lw=2, ls="--", label="needed to beat KS-PME")
        ax.fill_between(b, 100 * kk, 100 * t, where=b > 1, color=PALETTE["red"], alpha=0.12, label="KS-PME flatters")
        ax.fill_between(b, 100 * kk, 100 * t, where=b < 1, color=PALETTE["green"], alpha=0.12, label="KS-PME penalises")
        ax.axhline(0, color=PALETTE["muted"], lw=0.6)
        ax.legend(frameon=False, loc="lower left", fontsize=8)
        tidy(ax, title=lab, xlabel="deal market exposure beta", ylabel="break-even drift, % a year")
    caption(
        fig,
        "alpha* = a - (beta - b) m - (beta - b)^2 sigma^2 / 2 with m = mu - sigma^2 / 2 (log-normal market). "
        + f"Bond {100 * R:.0f}%.",
    )
    return fig


# ------------------------------------------------------------------ 3-5. the bias in simulated funds


def bias() -> Figure:
    rows = {b: _cell(b) for b in BETAS}
    fig = new_figure(14.5, 6.0)
    g2, k2 = rows[2.0]
    g05, k05 = rows[0.5]
    title_block(
        fig,
        "On fairly priced funds GPME averages zero at every beta; KS-PME rewards leverage",
        f"Mean NPV per pound called of {SIMS} fairly priced funds at each beta, each on its own market path. Beta 2: GPME {100 * g2.mean():+.1f}% "
        f"(+/- {100 * _ci(g2):.1f}), KS-PME {100 * k2.mean():+.1f}% (+/- {100 * _ci(k2):.1f}). Beta 0.5: GPME {100 * g05.mean():+.1f}%, KS-PME "
        f"{100 * k05.mean():+.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    x = np.arange(len(BETAS))
    for j, (key, lab) in enumerate((("gpme", "GPME (true SDF)"), ("ks", "KS-PME (1/R)"))):
        v = [100 * rows[b][j].mean() for b in BETAS]
        e = [100 * _ci(rows[b][j]) for b in BETAS]
        ax.bar(x + (j - 0.5) * 0.36, v, 0.34, yerr=e, color=COL[key], label=lab, capsize=3, ecolor=PALETTE["muted"])
    ax.set_xticks(x, [f"beta {b:g}" for b in BETAS])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="mean NPV per pound called, % (95% interval)")
    caption(fig, MODEL + " Fairly priced: drift = alpha*(beta) under the true SDF.")
    return fig


def dispersion() -> Figure:
    g, k = _cell(2.0)
    g1, k1 = _cell(1.0)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "One fund tells little: GPME is noisiest when the fund's beta is far from the SDF's risk aversion",
        f"Distribution of NPV per pound called across {SIMS} fairly priced funds. Beta 1: standard deviation {100 * g1.std():.0f}% (GPME) and "
        f"{100 * k1.std():.0f}% (KS-PME). Beta 2: {100 * g.std():.0f}% and {100 * k.std():.0f}%. GPME is unbiased across funds but a single fund's "
        f"value tells little, and least when beta is far from b = {TRUE.b:.2f}, where the SDF does not hedge the fund. Korteweg and Nagel pool funds for that reason.",
    )
    for j, (gg, kk, lab) in enumerate(((g1, k1, "beta 1"), (g, k, "beta 2"))):
        ax = fig.add_axes((0.06 + 0.49 * j, 0.13, 0.42, 0.58))
        lo, hi = np.percentile(np.concatenate([gg, kk]), [1, 99])
        bins = np.linspace(lo, hi, 40)
        ax.hist(gg, bins=bins, color=COL["gpme"], alpha=0.6, label="GPME")
        ax.hist(kk, bins=bins, color=COL["ks"], alpha=0.5, label="KS-PME")
        ax.axvline(0, color=PALETTE["ink"], lw=1)
        ax.legend(frameon=False)
        tidy(ax, title=lab, xlabel="NPV per pound called", ylabel="funds")
    caption(fig, MODEL)
    return fig


def sensitivity() -> Figure:
    b = np.linspace(0, 4, 41)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Measured performance depends on the risk aversion assumed; only the true one is neutral for every beta",
        f"Expected NPV per pound of a fairly priced deal held five years, under SDFs that all price the market but differ in b (KS-PME: b = 1). "
        f"The true b here is {TRUE.b:.2f}. At any other b, funds with beta above one look good and funds below one look bad, or the reverse.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    m = MU - 0.5 * SIG**2
    for beta, col in zip(
        BETAS, (PALETTE["green"], PALETTE["ink"], PALETTE["teal"], PALETTE["blue"], PALETTE["violet"]), strict=True
    ):
        fa = G.fair_alpha(beta, TRUE, MU, SIG)
        vals = []
        for bb in b:
            a = (1 - bb) * m + 0.5 * (1 - bb) ** 2 * SIG**2  # prices the market (not the bond unless b is the true one)
            sd = G.SDF(a, bb)
            vals.append(np.exp(5 * (fa - G.fair_alpha(beta, sd, MU, SIG))) - 1)
        ax.plot(b, 100 * np.array(vals), color=col, lw=1.8, label=f"beta {beta:g}")
    ax.axvline(1, color=COL["ks"], ls="--", lw=1)
    ax.axvline(TRUE.b, color=PALETTE["ink"], lw=1)
    ax.text(1, 1.0, " KS-PME", transform=ax.get_xaxis_transform(), va="bottom", fontsize=8, color=PALETTE["muted"])
    ax.text(TRUE.b, 1.0, " true b", transform=ax.get_xaxis_transform(), va="bottom", fontsize=8, color=PALETTE["muted"])
    ax.axhline(0, color=PALETTE["muted"], lw=0.6)
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, xlabel="risk aversion b assumed by the SDF", ylabel="apparent NPV of a fair five-year deal, %")
    caption(fig, MODEL + " Closed form for a single deal.")
    return fig


# ------------------------------------------------------------------ 6. the real path


def vintages() -> Figure:
    mk, fit, mu, sigma = _sp()
    sp_true = G.SDF.lognormal(mu, sigma, R)
    starts = np.arange(0, mk.times[-1] - 12 + 1e-9, 1.0)
    rows = []
    for k, s0 in enumerate(starts):
        w = mk.window(float(s0), 12.0)
        for beta in (1.0, 2.0):
            g, kk = [], []
            for j in range(20):
                f = Y.simulate_fund(
                    w, Y.FundSpec(beta=beta, alpha=G.fair_alpha(beta, sp_true, mu, sigma), idio=0.3, seed=100 * k + j)
                )
                g.append(G.gpme(f.times, f.amounts, f.index, fit))
                kk.append(G.gpme(f.times, f.amounts, f.index, KS))
            rows.append((1988 + s0, beta, np.mean(g), np.mean(kk)))
    arr = np.array(rows)
    fig = new_figure(14.5, 6.2)
    b2 = arr[arr[:, 1] == 2.0]
    b1 = arr[arr[:, 1] == 1.0]
    title_block(
        fig,
        f"On one market path, GPME with b = {fit.b:.1f} swings by hundreds of points; KS-PME is steadier but tilts towards leverage",
        f"Mean NPV per pound called of 20 fairly priced funds per vintage, 12-year life, vintages {int(b2[0, 0])}-{int(b2[-1, 0])}. KS-PME rates the beta-2 funds above "
        f"the beta-1 funds in {int((b2[:, 3] > b1[:, 3]).sum())} of {len(b2)} vintages (median tilt {100 * np.median(b2[:, 3] - b1[:, 3]):+.0f} points); GPME in "
        f"{int((b2[:, 2] > b1[:, 2]).sum())} (median {100 * np.median(b2[:, 2] - b1[:, 2]):+.0f}). Both are fair by construction, so neither should tilt.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    ax.plot(b2[:, 0], 100 * b2[:, 2], color=COL["gpme"], lw=2, marker="o", ms=4, label="beta 2, GPME")
    ax.plot(b2[:, 0], 100 * b2[:, 3], color=COL["ks"], lw=2, marker="s", ms=4, label="beta 2, KS-PME")
    ax.plot(b1[:, 0], 100 * b1[:, 2], color=COL["gpme"], lw=1, ls=":", label="beta 1, GPME")
    ax.plot(b1[:, 0], 100 * b1[:, 3], color=COL["ks"], lw=1, ls=":", label="beta 1, KS-PME")
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper left", ncol=2)
    tidy(ax, xlabel="vintage (first call)", ylabel="mean NPV per pound called, %")
    caption(
        fig,
        f"S&P 500 total return 1988-2026; SDF fitted to the whole sample (b = {fit.b:.2f}); bond {100 * R:.0f}%. Model funds, fairly priced at the sample's moments.",
    )
    return fig


# ------------------------------------------------------------------ 7-8. cash-flow betas


def cf_beta() -> Figure:
    est = {b: _dlp(b, 200, REPS) for b in BETAS}
    fig = new_figure(14.5, 6.0)
    med = {b: float(np.median(est[b][:, 1])) for b in BETAS}
    over = np.median([np.median(est[b][:, 0]) + G.fair_alpha(b, TRUE, MU, SIG) for b in BETAS])
    title_block(
        fig,
        "Cash-flow betas recover the planted market exposure from 200 funds; the alpha comes out too high",
        f"Driessen-Lin-Phalippou estimates in {REPS} samples of 200 funds at each planted beta. Median beta: "
        + ", ".join(f"{b:g} -> {med[b]:.2f}" for b in BETAS)
        + f". Deals have zero drift, so the expected arithmetic alpha against the levered portfolio is -alpha*(beta); the estimates sit {100 * over:.1f} points "
        "a year above it at the median, because minimising squared NPVs favours discount rates that shrink the noisy distributions.",
    )
    a1 = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    a2 = fig.add_axes((0.55, 0.13, 0.42, 0.58))
    a1.boxplot([est[b][:, 1] for b in BETAS], positions=list(BETAS), widths=0.25, showfliers=False)
    a1.plot([0.3, 2.7], [0.3, 2.7], color=PALETTE["muted"], ls="--", lw=0.8)
    a1.set_xticks(list(BETAS), [f"{b:g}" for b in BETAS])
    tidy(a1, title="Estimated beta", xlabel="planted beta", ylabel="estimate")
    a2.boxplot([100 * est[b][:, 0] for b in BETAS], positions=list(BETAS), widths=0.25, showfliers=False)
    conv = [-100 * G.fair_alpha(b, TRUE, MU, SIG) for b in BETAS]
    a2.plot(BETAS, conv, "o", color=PALETTE["red"], label="expected: -alpha*(beta)")
    a2.set_xticks(list(BETAS), [f"{b:g}" for b in BETAS])
    a2.legend(frameon=False, loc="upper left")
    tidy(a2, title="Estimated alpha", xlabel="planted beta", ylabel="% a year")
    caption(fig, MODEL + " Each sample: funds on independent market paths.")
    return fig


def cf_noise() -> Figure:
    sizes = (25, 50, 100, 200, 400)
    est = {n: _dlp(1.5, n, REPS) for n in sizes}
    sd = {n: float(est[n][:, 1].std(ddof=1)) for n in sizes}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "A cash-flow beta needs hundreds of funds; a single manager's track record cannot pin it down",
        f"Spread of the beta estimate across {REPS} samples, planted beta 1.5. Standard deviation: "
        + ", ".join(f"{n} funds {sd[n]:.2f}" for n in sizes)
        + ". The error falls roughly with the square root of the number of funds.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.6))
    ax.boxplot([est[n][:, 1] for n in sizes], tick_labels=[str(n) for n in sizes], showfliers=False)
    ax.axhline(1.5, color=PALETTE["red"], lw=1)
    tidy(ax, xlabel="funds in the sample", ylabel="estimated beta")
    a2 = fig.add_axes((0.69, 0.13, 0.28, 0.6))
    n = np.array(sizes, dtype=float)
    a2.plot(n, [sd[s] for s in sizes], "o-", color=COL["gpme"], label="measured")
    a2.plot(n, sd[sizes[0]] * np.sqrt(sizes[0] / n), "--", color=PALETTE["muted"], label="1 / sqrt(N) from 25 funds")
    a2.legend(frameon=False)
    tidy(a2, title="Standard deviation", xlabel="funds", ylabel="beta estimate")
    caption(fig, MODEL)
    return fig


# ------------------------------------------------------------------ 9-10. tests and fees


def power() -> Figure:
    ex = np.array([-0.04, -0.02, -0.01, 0.0, 0.01, 0.02, 0.04])
    n = min(100, SIMS)
    fig = new_figure(14.5, 6.0)
    res = {}
    for beta in (1.0, 2.0):
        g_rate, k_rate = [], []
        for e in ex:
            g, k = _cell(beta, float(e), seed0=7000, scale=5)
            m = g.size // n
            gs, ks = g[: n * m].reshape(-1, n), k[: n * m].reshape(-1, n)
            tg = gs.mean(axis=1) / (gs.std(axis=1, ddof=1) / np.sqrt(n))
            tk = ks.mean(axis=1) / (ks.std(axis=1, ddof=1) / np.sqrt(n))
            g_rate.append(float(np.mean(np.abs(tg) > 1.96)))
            k_rate.append(float(np.mean(np.abs(tk) > 1.96)))
        res[beta] = (np.array(g_rate), np.array(k_rate))
    g0, k0 = res[2.0][0][3], res[2.0][1][3]
    title_block(
        fig,
        "KS-PME tests have more power on unlevered funds, but on levered funds they find skill that is not there",
        f"Share of samples of {n} funds in which the mean NPV per pound is significantly different from zero (5% test), against the drift above fair. "
        f"Beta 2, no skill: GPME rejects in {100 * g0:.0f}% of samples, KS-PME in {100 * k0:.0f}%. Samples: {5 * SIMS // n} per point.",
    )
    for j, beta in enumerate((1.0, 2.0)):
        ax = fig.add_axes((0.06 + 0.49 * j, 0.13, 0.42, 0.58))
        ax.plot(100 * ex, 100 * res[beta][0], "o-", color=COL["gpme"], label="GPME")
        ax.plot(100 * ex, 100 * res[beta][1], "s--", color=COL["ks"], label="KS-PME")
        ax.axhline(5, color=PALETTE["muted"], lw=0.8, ls=":")
        ax.set_ylim(-3, 103)
        ax.legend(frameon=False, loc="lower right")
        tidy(ax, title=f"beta {beta:g}", xlabel="deal drift above fair, % a year", ylabel="rejection rate, %")
    caption(fig, MODEL + " t-test on the cross-sectional mean of fund NPVs.")
    return fig


def fees() -> Figure:
    fee_grid = (0.0, 0.01, 0.015, 0.02, 0.03)
    fig = new_figure(14.5, 6.0)
    gm = [_cell(1.5, 0.03, f, seed0=3000)[0].mean() for f in fee_grid]
    km = [_cell(1.5, 0.03, f, seed0=3000)[1].mean() for f in fee_grid]
    be_g = float(np.interp(0.0, -np.array(gm), fee_grid))
    be_k = float(np.interp(0.0, -np.array(km), fee_grid))
    title_block(
        fig,
        f"Three points of skill a year pay for a fee of about {100 * be_g:.1f}%; KS-PME puts the break-even at {100 * be_k:.1f}%",
        f"Mean NPV per pound called of {SIMS} beta-1.5 funds whose deals earn 3% a year above fair, by annual management fee. GPME: "
        f"{100 * gm[0]:+.1f}% with no fee, {100 * gm[3]:+.1f}% at 2%. KS-PME: {100 * km[0]:+.1f}% and {100 * km[3]:+.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    x = 100 * np.array(fee_grid)
    ax.plot(x, 100 * np.array(gm), "o-", color=COL["gpme"], lw=2, label="GPME")
    ax.plot(x, 100 * np.array(km), "s--", color=COL["ks"], lw=2, label="KS-PME")
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False)
    tidy(ax, xlabel="management fee, % of commitment a year", ylabel="mean NPV per pound called, %")
    caption(fig, MODEL + " Fees drawn quarterly while the fund is alive; no carry.")
    return fig
