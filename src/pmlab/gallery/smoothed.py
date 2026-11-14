"""Day 6 charts: smoothed returns and the risk they hide.

A model private equity index: 30 yearly vintages of 40 funds (Day 3 model) sharing one market path
and a private factor, valued at true value and at reported NAV (Day 5 appraisals: a = 0.4, 5%
noise). Every number in a subtitle is computed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .. import smoothing as S
from .style import PALETTE, caption, new_figure, tidy, title_block
from .venture import _plain_log

SEEDS = 60  # independent index histories for the robustness charts; the tests lower it
MODEL = (
    "Model index: 30 yearly vintages x 40 funds (Day 3 model, beta 1.2, own volatility 20%), systematic shock 80% public market and 20% "
    "private factor; appraisals close 40% of the gap a quarter with 5% noise (Day 5). Market premium 6%, volatility 16%."
)
COL = {
    "true": PALETTE["ink"],
    "reported": PALETTE["slate"],
    "geltner": PALETTE["blue"],
    "glm": PALETTE["green"],
    "market": PALETTE["violet"],
}
LAB = {
    "true": "true value",
    "reported": "reported NAV",
    "geltner": "Geltner unsmoothed",
    "glm": "GLM unsmoothed",
    "market": "public market",
}


@lru_cache(maxsize=1)
def _base() -> tuple[S.Index, pd.Series, S.GLM, float]:
    ix = S.build_index()
    g, a = S.geltner(ix.reported)
    return ix, g, S.glm(ix.reported, 2), a


def _series() -> dict[str, pd.Series]:
    ix, g, m, _ = _base()
    return {"true": ix.true, "reported": ix.reported, "geltner": g, "glm": m.true}


def _ts(s: pd.Series) -> pd.Series:
    out = (1 + s).cumprod()
    out.index = out.index.to_timestamp()
    return out


@lru_cache(maxsize=1)
def _robust() -> pd.DataFrame:
    rows = []
    for k in range(SEEDS):
        ix = S.build_index(seed=100 + k)
        g, a = S.geltner(ix.reported)
        m = S.glm(ix.reported, 2)
        vt = ix.true.std()
        rows.append(
            {
                "a": a,
                "rep": ix.reported.std() / vt,
                "gel": g.std() / vt,
                "glm": m.true.std() / vt,
                "beta_rep": ix.reported.cov(ix.market) / ix.true.cov(ix.market),
            }
        )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 1-3. the symptom


def paths() -> Figure:
    ix, *_ = _base()
    t = S.risk_table({"true": ix.true, "reported": ix.reported}, ix.market)
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Reported NAVs earn the same return with half the risk",
        f"Growth of 1 in the index at true value and at reported NAV, {len(ix.true)} quarters. Both earn about {100 * t.loc['true', 'mean']:.0f}% a year, "
        f"but the reported index's volatility is {100 * t.loc['reported', 'vol']:.1f}% against {100 * t.loc['true', 'vol']:.1f}%, and its worst drawdown "
        f"{100 * t.loc['reported', 'maxdd']:.0f}% against {100 * t.loc['true', 'maxdd']:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for k in ("true", "reported"):
        ax.plot(_ts(_series()[k]), color=COL[k], lw=1.8, label=LAB[k])
    ax.plot(_ts(ix.market), color=COL["market"], lw=1.1, alpha=0.7, label=LAB["market"])
    ax.set_yscale("log")
    _plain_log(ax, "y")
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="growth of 1 (log)")
    caption(fig, MODEL)
    return fig


def autocorrelation() -> Figure:
    ix, *_ = _base()
    lags = range(1, 9)
    rep = [ix.reported.autocorr(k) for k in lags]
    tru = [ix.true.autocorr(k) for k in lags]
    se = 1.96 / np.sqrt(len(ix.true))
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "Smoothing leaves a fingerprint: autocorrelated returns",
        f"Autocorrelation of quarterly index returns. Reported: {rep[0]:.2f} at lag 1 and {rep[1]:.2f} at lag 2; true: {tru[0]:.2f} and {tru[1]:.2f}. "
        f"Dashed lines: +/-{se:.2f}, the 95% band for no autocorrelation. Listed assets do not behave like this; appraised ones do.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    x = np.arange(1, 9)
    ax.bar(x - 0.2, rep, 0.4, color=COL["reported"], label=LAB["reported"])
    ax.bar(x + 0.2, tru, 0.4, color=COL["true"], label=LAB["true"])
    for v in (se, -se):
        ax.axhline(v, color=PALETTE["muted"], ls="--", lw=0.8)
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    ax.legend(frameon=False)
    tidy(ax, xlabel="lag, quarters", ylabel="autocorrelation")
    caption(fig, MODEL)
    return fig


def risk() -> Figure:
    ix, *_ = _base()
    t = S.risk_table(_series(), ix.market)
    fig = new_figure(14.5, 6.6)
    title_block(
        fig,
        "Unsmoothing restores most of the hidden risk",
        f"Risk of the index four ways. Volatility: reported {100 * t.loc['reported', 'vol']:.1f}%, Geltner {100 * t.loc['geltner', 'vol']:.1f}%, GLM "
        f"{100 * t.loc['glm', 'vol']:.1f}%, true {100 * t.loc['true', 'vol']:.1f}%. Beta: {t.loc['reported', 'beta']:.2f}, {t.loc['geltner', 'beta']:.2f}, "
        f"{t.loc['glm', 'beta']:.2f}, {t.loc['true', 'beta']:.2f}. Sharpe: {t.loc['reported', 'sharpe']:.2f} reported against {t.loc['true', 'sharpe']:.2f} true.",
    )
    keys = ["reported", "glm", "geltner", "true"]
    for k, (col, lab, scale) in enumerate(
        (("vol", "volatility, %", 100), ("beta", "beta", 1), ("sharpe", "Sharpe ratio", 1), ("maxdd", "worst drawdown, %", 100))
    ):
        ax = fig.add_axes((0.05 + 0.24 * k, 0.13, 0.19, 0.55))
        ax.bar(range(4), [scale * t.loc[x, col] for x in keys], color=[COL[x] for x in keys])
        ax.set_xticks(range(4), ["reported", "GLM", "Geltner", "true"], fontsize=8)
        tidy(ax, title=lab)
    caption(fig, MODEL + " Geltner: a from the lag-1 autocorrelation. GLM: two lags, maximum likelihood.")
    return fig


# ------------------------------------------------------------------ 4-6. the cures


def unsmoothed() -> Figure:
    ix, g, m, a = _base()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Unsmoothed returns track the true ones",
        f"Growth of 1 at true value and from the two unsmoothed series. Geltner estimates a = {a:.2f} (true 0.40) from the lag-1 autocorrelation; its quarterly "
        f"returns correlate {g.corr(ix.true):.2f} with the true ones. GLM's correlate {m.true.corr(ix.true):.2f}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for k in ("true", "geltner", "glm"):
        ax.plot(_ts(_series()[k]), color=COL[k], lw=1.6, label=LAB[k])
    ax.set_yscale("log")
    _plain_log(ax, "y")
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="growth of 1 (log)")
    caption(fig, MODEL)
    return fig


def glm_weights() -> Figure:
    ix, _, m2, _ = _base()
    m4 = S.glm(ix.reported, 4)
    pa2, pa4 = S.partial_adjustment_weights(0.4, 2), S.partial_adjustment_weights(0.4, 4)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "GLM finds the smoothing weights with two lags, and loses them with four",
        f"Estimated GLM weights against those the appraisal rule implies (a = 0.4, truncated and rescaled). Two lags: {', '.join(f'{x:.2f}' for x in m2.theta)} against "
        f"{', '.join(f'{x:.2f}' for x in pa2)}. Four lags: {', '.join(f'{x:.2f}' for x in m4.theta)}: the weights flatten, and the implied true volatility jumps to "
        f"{100 * 2 * m4.sigma:.0f}% a year, against {100 * 2 * m2.sigma:.1f}% with two lags and {100 * ix.true.std() * 2:.1f}% in truth.",
    )
    for k, (est, ref, ttl) in enumerate(((m2.theta, pa2, "Two lags"), (m4.theta, pa4, "Four lags"))):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        x = np.arange(est.size)
        ax.bar(x - 0.2, est, 0.4, color=COL["glm"], label="GLM estimate")
        ax.bar(x + 0.2, ref, 0.4, color=PALETTE["muted"], label="appraisal rule")
        ax.legend(frameon=False)
        tidy(ax, title=ttl, xlabel="lag j", ylabel="theta_j" if k == 0 else None)
    caption(fig, MODEL)
    return fig


def speed() -> Figure:
    a_s = (0.2, 0.3, 0.4, 0.6, 0.8, 1.0)
    rows = []
    for a in a_s:
        r = []
        for k in range(max(3, SEEDS // 6)):
            ix = S.build_index(a=a, seed=300 + k)
            g, _ = S.geltner(ix.reported)
            vt = ix.true.std()
            r.append((ix.reported.std() / vt, g.std() / vt, S.glm(ix.reported, 2).true.std() / vt))
        rows.append(np.mean(r, axis=0))
    t = np.array(rows)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "The slower the appraisals, the more risk the reported index hides",
        f"Volatility as a share of the true index's, by appraisal speed a (mean of {max(3, SEEDS // 6)} histories). At a = 0.2 the reported index shows "
        f"{100 * t[0, 0]:.0f}% of the true volatility; at a = 1, {100 * t[-1, 0]:.0f}%. Geltner stays close at every speed ({100 * t[0, 1]:.0f}% at a = 0.2); GLM with two lags "
        f"falls short when appraisals are slow ({100 * t[0, 2]:.0f}% at a = 0.2): two lags cannot hold a long lag.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for j, k in enumerate(("reported", "geltner", "glm")):
        ax.plot(a_s, 100 * t[:, j], "o-", color=COL[k], lw=1.8, label=LAB[k])
    ax.axhline(100, color=PALETTE["ink"], ls="--", lw=1)
    ax.legend(frameon=False)
    tidy(ax, xlabel="appraisal speed a", ylabel="volatility, % of true")
    caption(fig, MODEL.replace("close 40% of the gap", "close a share a of the gap"))
    return fig


# ------------------------------------------------------------------ 7-10. consequences and robustness


def noise() -> Figure:
    levels = (0.0, 0.02, 0.05, 0.10, 0.15)
    rows = []
    for nz in levels:
        r = []
        for k in range(max(3, SEEDS // 6)):
            ix = S.build_index(noise=nz, seed=400 + k)
            g, a = S.geltner(ix.reported)
            r.append((g.std() / ix.true.std(), a))
        rows.append(np.mean(r, axis=0))
    t = np.array(rows)
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "At the index level, appraisal noise barely matters to Geltner's method",
        f"Geltner volatility as a share of true volatility, by appraisal noise per fund. Without noise: {100 * t[0, 0]:.0f}%; at 15% noise: {100 * t[-1, 0]:.0f}%. Noise "
        f"lowers the reported index's autocorrelation, so the estimated speed rises ({t[0, 1]:.2f} to {t[-1, 1]:.2f}) and the unsmoothing is gentler. Across 1,200 funds "
        "most of the noise cancels; for a single fund it would not.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot([100 * x for x in levels], 100 * t[:, 0], "o-", color=COL["geltner"], lw=1.8)
    ax.axhline(100, color=PALETTE["ink"], ls="--", lw=1)
    tidy(ax, xlabel="appraisal noise per fund a quarter, %", ylabel="Geltner volatility, % of true")
    caption(fig, MODEL)
    return fig


def horizons() -> Figure:
    ix, *_ = _base()
    h = (1, 2, 4, 8, 12)
    rep = S.horizon_correlation(ix.reported, ix.market, h)
    tru = S.horizon_correlation(ix.true, ix.market, h)
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "Measured over longer horizons, private equity looks more like public equity",
        f"Correlation with the market of non-overlapping returns over each horizon. Reported: {rep.iloc[0]:.2f} quarterly, {rep.iloc[3]:.2f} over two years. "
        f"True: {tru.iloc[0]:.2f} and {tru.iloc[3]:.2f}. The gap closes with the horizon because the lag washes out; long horizons also leave few observations.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(h, rep.to_numpy(), "o-", color=COL["reported"], lw=1.8, label=LAB["reported"])
    ax.plot(h, tru.to_numpy(), "o-", color=COL["true"], lw=1.8, label=LAB["true"])
    ax.set_ylim(0, 1)
    ax.legend(frameon=False)
    tidy(ax, xlabel="horizon, quarters", ylabel="correlation with the market")
    caption(fig, MODEL)
    return fig


def allocation() -> Figure:
    ix, *_ = _base()
    w = {k: S.tangency_weight(s, ix.market) for k, s in _series().items()}
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "Smoothed risk makes private equity look like the whole portfolio",
        f"Share of private equity in the maximum-Sharpe mix with the public market, using each series' own mean, volatility and correlation. Reported: "
        f"{100 * w['reported']:.0f}% (the market is shorted); true: {100 * w['true']:.0f}%; Geltner: {100 * w['geltner']:.0f}%; GLM: {100 * w['glm']:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    keys = ["reported", "glm", "geltner", "true"]
    ax.bar(range(4), [100 * w[k] for k in keys], color=[COL[k] for k in keys])
    ax.set_xticks(range(4), [LAB[k] for k in keys])
    ax.axhline(100, color=PALETTE["muted"], ls="--", lw=0.8)
    tidy(ax, ylabel="weight in private equity, %")
    caption(fig, MODEL + " Unconstrained; the rest of the portfolio is the market.")
    return fig


def robustness() -> Figure:
    r = _robust()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Across many histories the pattern holds, with sampling noise",
        f"{len(r)} independent 25-year index histories. The reported index shows {100 * r['rep'].median():.0f}% of the true volatility (median); Geltner "
        f"{100 * r['gel'].median():.0f}%, GLM {100 * r['glm'].median():.0f}%. Geltner's estimate of a has median {r['a'].median():.2f} and interquartile range "
        f"{r['a'].quantile(0.25):.2f}-{r['a'].quantile(0.75):.2f} (true 0.40).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.boxplot([100 * r["rep"], 100 * r["glm"], 100 * r["gel"]], showfliers=False)
    ax.set_xticks([1, 2, 3], ["reported", "GLM", "Geltner"])
    ax.axhline(100, color=PALETTE["ink"], ls="--", lw=1)
    tidy(ax, title="Volatility, % of true")
    ax2 = fig.add_axes((0.56, 0.13, 0.4, 0.58))
    ax2.hist(r["a"], bins=15, color=COL["geltner"], alpha=0.8)
    ax2.axvline(0.4, color=PALETTE["ink"], ls="--")
    tidy(ax2, title="Geltner's estimate of a", xlabel="a")
    caption(fig, MODEL)
    return fig
