"""Day 9 charts: hedge funds and liquid alternatives.

Ten liquid ETFs (equities, bonds, commodities, currencies) carry the trend-following strategy;
QAI and DBMF, two public funds that track hedge-fund and managed-futures indices, stand in for the
licensed hedge-fund indices; the CBOE S&P 500 PutWrite index (^PUT) is the tail-risk case. All are
Yahoo Finance daily closes stored under data/alts (``pmlab market fetch``). Every number in a
subtitle is computed.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, NullFormatter

from .. import hedgefunds as H
from .. import market as M
from .style import PALETTE, SERIES, caption, new_figure, tidy, title_block

PATHS = 100_000  # Monte Carlo paths for the straddle checks; the tests lower it
FEE_PATHS = 2000  # simulated funds per fee point; the tests lower it
LOOKBACKS = (1, 3, 6, 12)
CLONE_FACTORS = ("spy", "eem", "ief", "gld", "dbc", "uup")
SOURCE = "Source: Yahoo Finance daily closes (ETFs adjusted for distributions); risk-free = 13-week T-bill (^IRX)."


@cache
def _data() -> tuple[pd.DataFrame, pd.Series]:
    d = M.load_alts()
    return d, H.monthly_rf(d["tbill"])


@cache
def _tsmom(lookback: int = 12) -> H.TSMOM:
    d, rf = _data()
    return H.tsmom(d[list(M.TREND)], rf, lookback=lookback)


@cache
def _factors() -> pd.DataFrame:
    d, rf = _data()
    return H.class_factors(H.straddle_returns(d[list(M.TREND)], rf), M.ASSET_CLASS)


def _ex(name: str) -> pd.Series:
    d, rf = _data()
    return (H.monthly_returns(d[name]) - rf).dropna().rename(name)


@cache
def _clones() -> dict[str, H.Clone]:
    d, rf = _data()
    x = H.excess(d[list(CLONE_FACTORS)], rf)
    targets = {"QAI (hedge-fund index tracker)": _ex("qai"), "PutWrite index": _ex("put"),
               "DBMF (managed-futures tracker)": _ex("dbmf"), "Trend following (12-month TSMOM)": _tsmom(12).portfolio}  # fmt: skip
    return {k: H.linear_clone(v, x) for k, v in targets.items()}


def _log_y(ax) -> None:  # type: ignore[no-untyped-def]
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: f"{v:g}" if f"{v:.1g}"[0] in "25" else ""))


def _short(name: str) -> str:
    return name.split(" (")[0]


def _cum(r: pd.Series) -> pd.Series:
    return (1 + r.dropna()).cumprod()


# ------------------------------------------------------------------ 1-2. trend following


def tsmom() -> Figure:
    d, rf = _data()
    p = _tsmom(12).portfolio
    spy = _ex("spy").reindex(p.index)
    dbmf = _ex("dbmf")
    s_p, s_m = H.summary(p + rf.reindex(p.index), rf, spy + rf.reindex(p.index)), H.summary(spy + rf.reindex(p.index), rf)
    y08, m08 = (1 + p["2008"]).prod() - 1, (1 + spy["2008"]).prod() - 1
    y22, m22 = (1 + p["2022"]).prod() - 1, (1 + spy["2022"]).prod() - 1
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        f"Trend following earned as much as equities, and made {y08:+.0%} and {y22:+.0%} in equities' two worst years, 2008 and 2022",
        f"Time-series momentum on 10 ETFs, {p.index[0]:%b %Y}-{p.index[-1]:%b %Y}: Sharpe {s_p['sharpe']:.2f} against the S&P 500's {s_m['sharpe']:.2f}, "
        f"beta {s_p['beta']:+.2f}; S&P 500 {m08:+.0%} in 2008 and {m22:+.0%} in 2022. DBMF, a public managed-futures tracker, correlates {p.corr(dbmf):.2f} with it.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.62, 0.62))
    ax.plot(_cum(p).index, _cum(p), color=PALETTE["blue"], lw=2, label=f"TSMOM (vol {s_p['vol']:.0%})")
    ax.plot(_cum(spy).index, _cum(spy), color=PALETTE["slate"], lw=1.6, label=f"S&P 500 (vol {s_m['vol']:.0%})")
    start = dbmf.index[0]
    base = float(_cum(p).loc[:start].iloc[-1])
    ax.plot(_cum(dbmf).index, base * _cum(dbmf), color=PALETTE["green"], lw=1.6, label="DBMF, from its launch")
    for yr in ("2008", "2022"):
        ax.axvspan(pd.Timestamp(f"{yr}-01-01"), pd.Timestamp(f"{yr}-12-31"), color=PALETTE["band"], zorder=0)
    _log_y(ax)
    ax.legend(loc="upper left")
    tidy(ax, title="Growth of $1 of excess return (log scale)")
    ax2 = fig.add_axes((0.75, 0.13, 0.23, 0.62))
    yearly = pd.DataFrame({"tsmom": H.compound(p, "YE"), "spy": H.compound(spy, "YE")}).dropna()
    yearly = yearly[yearly.index.year < p.index[-1].year] if p.index[-1].month < 12 else yearly
    ax2.scatter(100 * yearly["spy"], 100 * yearly["tsmom"], color=PALETTE["blue"], s=28)
    for t, row in yearly.iterrows():
        if t.year in (2008, 2022):
            ax2.annotate(
                str(t.year),
                (100 * row["spy"], 100 * row["tsmom"]),
                xytext=(5, -3),
                textcoords="offset points",
                color=PALETTE["accent"],
            )
    ax2.axhline(0, color=PALETTE["muted"], lw=0.8)
    ax2.axvline(0, color=PALETTE["muted"], lw=0.8)
    tidy(ax2, title="Calendar years", xlabel="S&P 500 excess return (%)", ylabel="TSMOM excess return (%)")
    caption(
        fig,
        "Each ETF long or short by the sign of its 12-month excess return, at 40% ex-ante volatility (EWMA, 60-day centre of mass); equal weights. "
        + SOURCE,
    )
    return fig


def smile() -> Figure:
    fig = new_figure(14.5, 6.0)
    spy_q = H.compound(_ex("spy"))
    fits = {}
    for lb in (3, 12):
        q = H.compound(_tsmom(lb).portfolio)
        fits[lb] = (q, H.smile(q, spy_q.reindex(q.index)))
    c3, c12 = fits[3][1], fits[12][1]
    title_block(
        fig,
        "The trend follower's smile: convex in the market, but only weakly so in twenty years of quarters",
        f"Quarterly excess returns on the S&P 500's: curvature c = {c3.coef['x2']:.2f} (t = {c3.t['x2']:.1f}) for a 3-month lookback "
        f"and {c12.coef['x2']:.2f} (t = {c12.t['x2']:.1f}) for 12 months; R² {c3.r2:.0%} and {c12.r2:.0%}. The payoff looks like a straddle, but the sample cannot prove it.",
    )
    for k, lb in enumerate((3, 12)):
        q, fit = fits[lb]
        x = spy_q.reindex(q.index)
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.62))
        ax.scatter(100 * x, 100 * q, s=22, color=SERIES[k], alpha=0.75)
        g = np.linspace(x.min(), x.max(), 100)
        ax.plot(100 * g, 100 * (fit.coef["const"] + fit.coef["x"] * g + fit.coef["x2"] * g**2), color=PALETTE["ink"], lw=1.8)
        ax.axhline(0, color=PALETTE["muted"], lw=0.8)
        tidy(
            ax,
            title=f"{lb}-month lookback: {len(q)} quarters",
            xlabel="S&P 500 excess return in the quarter (%)",
            ylabel="TSMOM excess return (%)",
        )
    caption(fig, "Fit y = a + b x + c x² by least squares, Newey-West t (1 lag). " + SOURCE)
    return fig


# ------------------------------------------------------------------ 3-4. lookback straddle


@cache
def _straddle_grid() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    vols = np.array([0.1, 0.2, 0.3, 0.4, 0.6])
    out: dict[str, np.ndarray] = {
        "cont": H.lookback_straddle(1 / 12, 0.03, vols),
        "disc": H.lookback_straddle(1 / 12, 0.03, vols, dt=1 / 252),
    }
    out["mc"] = np.array(
        [H.lookback_mc(1 / 12, 0.03, v, steps=21, paths=PATHS, seed=i, shift=False)[0] for i, v in enumerate(vols)]
    )
    steps = np.array([5, 10, 21, 42, 84])
    mc = np.array([H.lookback_mc(1 / 12, 0.03, 0.2, steps=int(n), paths=PATHS, seed=50 + int(n), shift=False)[0] for n in steps])
    out["steps"], out["mc_steps"] = steps, mc
    out["err_cont"] = H.lookback_straddle(1 / 12, 0.03, 0.2) / mc - 1
    out["err_disc"] = np.array([float(H.lookback_straddle(1 / 12, 0.03, 0.2, dt=1 / 12 / n)) for n in steps]) / mc - 1
    return vols, out


def straddle_price() -> Figure:
    vols, g = _straddle_grid()
    i = int(np.argmin(np.abs(vols - 0.2)))
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"Pricing the range with the continuous formula overcharges a daily-monitored straddle by {g['cont'][i] / g['mc'][i] - 1:.0%}; the shifted formula is within {abs(g['err_disc'][2]):.1%}",
        f"One-month lookback straddle (pays max S - min S), r = 3%. At 20% volatility: continuous closed form {g['cont'][i]:.4f}, daily Monte Carlo {g['mc'][i]:.4f}, "
        f"Broadie-Glasserman-Kou shifted formula {g['disc'][i]:.4f}. Unshifted, the straddle factor would lose about that much every month by construction.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.62))
    ax.plot(100 * vols, 100 * g["cont"], color=PALETTE["slate"], lw=1.8, label="continuous monitoring (Goldman-Sosin-Gatto)")
    ax.plot(100 * vols, 100 * g["disc"], color=PALETTE["blue"], lw=2, label="daily monitoring, shifted formula")
    ax.scatter(
        100 * vols, 100 * g["mc"], color=PALETTE["accent"], zorder=3, s=30, label=f"Monte Carlo, 21 dates, {PATHS:,} paths"
    )
    ax.legend(loc="upper left")
    tidy(ax, title="Price, % of the underlying", xlabel="volatility (%)")
    ax2 = fig.add_axes((0.56, 0.13, 0.42, 0.62))
    ax2.plot(g["steps"], 100 * g["err_cont"], "o-", color=PALETTE["slate"], label="continuous formula")
    ax2.plot(g["steps"], 100 * g["err_disc"], "o-", color=PALETTE["blue"], label="shifted formula")
    ax2.axhline(0, color=PALETTE["muted"], lw=0.8)
    ax2.set_xscale("log")
    ax2.set_xticks(g["steps"], [str(s) for s in g["steps"]])
    ax2.xaxis.set_minor_formatter(NullFormatter())
    ax2.legend()
    tidy(ax2, title="Error against Monte Carlo at 20% volatility (%)", xlabel="monitoring dates in the month")
    caption(
        fig,
        "Monte Carlo: antithetic GBM paths, the extremes include the start price. Shift c = 0.5826 σ √Δt applied to the running extremes (Broadie, Glasserman and Kou, 1997).",
    )
    return fig


def straddle_betas() -> Figure:
    fac = _factors()
    spy = _ex("spy").rename("S&P 500")
    r2s, caps = [], []
    fits = {}
    for lb in LOOKBACKS:
        p = _tsmom(lb).portfolio
        fits[lb] = H.ols(p, fac)
        r2s.append(fits[lb].r2)
        caps.append(H.ols(p, spy.to_frame()).r2)
    dbmf = H.ols(_ex("dbmf"), fac)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"One-month range factors explain at most {max(r2s):.0%} of trend returns: Fung and Hsieh's straddle is a slower, longer option",
        f"R² of monthly TSMOM returns on four lookback-straddle factors (one per asset class): {', '.join(f'{lb}m {r:.0%}' for lb, r in zip(LOOKBACKS, r2s, strict=True))}; "
        f"on the S&P 500 alone at most {max(caps):.0%}. DBMF on the straddle factors: R² {dbmf.r2:.0%}, {dbmf.n} months. Loadings are mostly positive, as the theory says.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.36, 0.62))
    xs = np.arange(len(LOOKBACKS))
    ax.bar(xs - 0.18, 100 * np.array(r2s), 0.36, color=PALETTE["blue"], label="four straddle factors")
    ax.bar(xs + 0.18, 100 * np.array(caps), 0.36, color=PALETTE["slate"], label="S&P 500 only")
    ax.set_xticks(xs, [f"{lb} months" for lb in LOOKBACKS])
    ax.legend()
    tidy(ax, title="R² by TSMOM lookback (%)")
    ax2 = fig.add_axes((0.50, 0.13, 0.48, 0.62))
    cls = list(fac.columns)
    xs = np.arange(len(cls))
    for k, (lab, f) in enumerate([("3-month TSMOM", fits[3]), ("12-month TSMOM", fits[12]), ("DBMF", dbmf)]):
        ax2.bar(xs + (k - 1) * 0.26, f.t[cls], 0.26, color=SERIES[k], label=lab)
    ax2.axhline(1.96, color=PALETTE["muted"], lw=0.8, ls="--")
    ax2.axhline(-1.96, color=PALETTE["muted"], lw=0.8, ls="--")
    ax2.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax2.set_xticks(xs, cls)
    ax2.legend()
    tidy(ax2, title="Newey-West t-statistics of the straddle loadings (dashed: ±1.96)")
    caption(
        fig,
        "Straddle factor = monthly return on a one-month lookback straddle on each ETF, priced with trailing 63-day realised volatility (no option data), averaged within the class. "
        + SOURCE,
    )
    return fig


# ------------------------------------------------------------------ 5-6. replication


def clones() -> Figure:
    cl = _clones()
    q = {k: H.clone_quality(c) for k, c in cl.items()}
    fig = new_figure(14.5, 7.6)
    best = max(q, key=lambda k: q[k]["correlation"])
    worst = min(q, key=lambda k: q[k]["correlation"])
    corrs = ", ".join(f"{_short(k)} {v['correlation']:.2f}" for k, v in q.items())
    title_block(
        fig,
        "Linear clones copy linear exposures: a hedge-fund index tracks at 0.9, trend following at almost nothing",
        f"Out-of-sample correlation of a 24-month rolling regression clone on six liquid ETFs: {corrs}. "
        f"Best {_short(best)}, worst {_short(worst)}: a clone sees average weights, not the switches a trend follower makes.",
    )
    for k, (name, c) in enumerate(cl.items()):
        ax = fig.add_axes((0.06 + 0.48 * (k % 2), 0.43 - 0.33 * (k // 2), 0.42, 0.26))
        ax.plot(_cum(c.target).index, _cum(c.target), color=PALETTE["ink"], lw=1.7, label="target")
        ax.plot(_cum(c.returns).index, _cum(c.returns), color=SERIES[k % 3], lw=1.5, label="clone")
        tidy(ax, title=f"{name}: corr {q[name]['correlation']:.2f}, tracking error {q[name]['tracking_error']:.0%}")
        if k == 0:
            ax.legend(loc="upper left")
    caption(
        fig,
        "Clone: weights from months t-24..t-1 without a constant, scaled to the target's in-window volatility, applied in month t (Hasanhodzic and Lo, 2007). Excess returns. "
        + SOURCE,
    )
    return fig


def clone_weights() -> Figure:
    cl = _clones()
    q = pd.DataFrame({k.split(" (")[0]: H.clone_quality(c) for k, c in cl.items()}).T
    name = next(iter(cl))
    w = cl[name].weights
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"The QAI clone leans on {' and '.join(c.upper() for c in w.abs().mean().nlargest(2).index)}; its tracking error is {q.iloc[0]['tracking_error']:.1%} a year against {q.iloc[3]['tracking_error']:.0%} for trend following",
        f"Left: out-of-sample tracking error and mean excess return gap (target - clone, a year). Right: weights of the {name.split(' (')[0]} clone; "
        f"its average S&P 500 weight is {w['spy'].mean():.2f} and Treasury (IEF) weight {w['ief'].mean():.2f}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.38, 0.62))
    xs = np.arange(len(q))
    ax.bar(xs - 0.18, 100 * q["tracking_error"], 0.36, color=PALETTE["slate"], label="tracking error")
    ax.bar(xs + 0.18, 100 * (q["target_mean"] - q["clone_mean"]), 0.36, color=PALETTE["blue"], label="mean gap, target - clone")
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.set_xticks(xs, [s.replace(" following", "\nfollowing").replace(" index", "\nindex") for s in q.index])
    ax.legend()
    tidy(ax, title="% a year")
    ax2 = fig.add_axes((0.52, 0.13, 0.46, 0.62))
    for k, col in enumerate(w.columns):
        ax2.plot(w.index, w[col], lw=1.5, color=(SERIES + (PALETTE["red"],))[k], label=col.upper())
    ax2.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax2.legend(ncol=3, loc="upper left")
    tidy(ax2, title="Clone weights (excess-return units)")
    caption(fig, SOURCE)
    return fig


# ------------------------------------------------------------------ 7-9. tail risk


def putwrite() -> Figure:
    d, rf = _data()
    put = H.monthly_returns(d["put"]).loc["1996-09":]
    spy = H.monthly_returns(d["spy"]).reindex(put.index)
    sp, ss = H.summary(put, rf), H.summary(spy, rf)
    fig = new_figure(14.5, 6.6)
    title_block(
        fig,
        f"Writing index puts: a higher Sharpe ratio than the index ({sp['sharpe']:.2f} vs {ss['sharpe']:.2f}) bought with a left tail",
        f"CBOE S&P 500 PutWrite index, {put.index[0]:%b %Y}-{put.index[-1]:%b %Y}: volatility {sp['vol']:.0%} vs {ss['vol']:.0%}, skewness {sp['skew']:.2f} vs {ss['skew']:.2f}, "
        f"excess kurtosis {sp['kurt']:.1f} vs {ss['kurt']:.1f}, worst month {sp['worst']:.0%} vs {ss['worst']:.0%}. Smooth until it is not.",
    )
    ax = fig.add_axes((0.06, 0.40, 0.92, 0.38))
    ax.plot(_cum(put).index, _cum(put), color=PALETTE["blue"], lw=2, label="PutWrite")
    ax.plot(_cum(spy).index, _cum(spy), color=PALETTE["slate"], lw=1.6, label="S&P 500 (SPY)")
    _log_y(ax)
    ax.set_xlim(put.index[0], put.index[-1])
    ax.legend(loc="upper left")
    tidy(ax, title="Growth of $1, total return (log scale)")
    ax2 = fig.add_axes((0.06, 0.10, 0.92, 0.22))
    for r, col, lab in ((put, PALETTE["blue"], "PutWrite"), (spy, PALETTE["slate"], "S&P 500")):
        w = _cum(r)
        ax2.plot(w.index, 100 * (w / w.cummax() - 1), color=col, lw=1.4, label=lab)
    ax2.set_xlim(put.index[0], put.index[-1])
    tidy(ax2, title=f"Drawdown (%): worst {sp['drawdown']:.0%} and {ss['drawdown']:.0%}")
    caption(fig, "PutWrite: sells one-month at-the-money S&P 500 puts, collateralised in T-bills. " + SOURCE)
    return fig


def put_factor() -> Figure:
    d, rf = _data()
    put, mkt = _ex("put"), _ex("spy").rename("mkt")
    pf = H.put_factor(d["spy"], d["vix"], rf)
    capm = H.ols(put, mkt.to_frame())
    an = H.ols(put, pd.concat([mkt, pf], axis=1))
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"The put writer's alpha is a written put: {12 * capm.coef['const']:.1%} a year against the market, {12 * an.coef['const']:+.1%} once a put factor is added",
        f"Monthly excess returns, {capm.n} months. CAPM: alpha t = {capm.t['const']:.1f}, beta {capm.coef['mkt']:.2f}. With Agarwal-Naik's at-the-money put factor: "
        f"loading {an.coef[pf.name]:.4f} (t = {an.t[pf.name]:.1f}), beta {an.coef['mkt']:.2f}. A linear model counts the insurance premium as skill.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.46, 0.62))
    data = pd.concat([put, mkt], axis=1).dropna()
    ax.scatter(100 * data["mkt"], 100 * data["put"], s=12, color=PALETTE["blue"], alpha=0.6)
    g = np.linspace(data["mkt"].min(), data["mkt"].max(), 100)
    ax.plot(100 * g, 100 * (capm.coef["const"] + capm.coef["mkt"] * g), color=PALETTE["ink"], lw=1.6, label="CAPM line")
    ax.plot(
        100 * g,
        100 * np.minimum(g, 0.012),
        color=PALETTE["accent"],
        lw=1.4,
        ls="--",
        label="short put shape: min(market, premium)",
    )
    ax.legend(loc="upper left")
    tidy(ax, title="PutWrite against the S&P 500, monthly excess (%)", xlabel="S&P 500", ylabel="PutWrite")
    ax2 = fig.add_axes((0.62, 0.13, 0.36, 0.62))
    a = 1200 * np.array([capm.coef["const"], an.coef["const"]])
    e = 1200 * 1.96 * np.array([capm.se["const"], an.se["const"]])
    ax2.bar([0, 1], a, color=[PALETTE["slate"], PALETTE["blue"]], yerr=e, capsize=6)
    ax2.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax2.set_xticks([0, 1], ["CAPM", "CAPM + put factor"])
    tidy(ax2, title="Alpha, % a year (95% interval)")
    caption(
        fig,
        "Put factor: return on buying a one-month at-the-money put on SPY, priced by Black-Scholes at last month-end's VIX and the T-bill rate. "
        + SOURCE,
    )
    return fig


def measures() -> Figure:
    d, rf = _data()
    series = {"S&P 500": H.monthly_returns(d["spy"]), "PutWrite": H.monthly_returns(d["put"]), "QAI": H.monthly_returns(d["qai"]),
              "TSMOM 12m": _tsmom(12).portfolio + rf}  # fmt: skip
    start = max(s.dropna().index[1] for s in series.values())
    tab = pd.DataFrame({k: H.summary(s.loc[start:], rf) for k, s in series.items()}).T
    for rho in (2, 4, 6):
        tab[f"mppm{rho}"] = [H.mppm(s.loc[start:], rf, rho) for s in series.values()]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"Sharpe ignores leverage: TSMOM ties QAI at {tab.loc['TSMOM 12m', 'sharpe']:.2f}, but its ρ = 6 certainty equivalent is "
        f"{tab.loc['TSMOM 12m', 'mppm6']:.1%} vs {tab.loc['QAI', 'mppm6']:.1%}",
        f"Common period {tab['months'].iloc[0]:.0f} months from {start:%b %Y}. Sharpe ratios {', '.join(f'{k} {v:.2f}' for k, v in tab['sharpe'].items())}. "
        f"MPPM is the certainty-equivalent excess return of an investor with relative risk aversion ρ; skewness {', '.join(f'{v:.2f}' for v in tab['skew'])}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.36, 0.62))
    xs = np.arange(len(tab))
    ax.bar(xs, tab["sharpe"], color=[SERIES[k] for k in range(len(tab))])
    ax.set_xticks(xs, tab.index)
    tidy(ax, title="Sharpe ratio")
    ax2 = fig.add_axes((0.50, 0.13, 0.48, 0.62))
    for k, rho in enumerate((2, 4, 6)):
        ax2.bar(xs + (k - 1) * 0.26, 100 * tab[f"mppm{rho}"], 0.26, color=SERIES[k], label=f"ρ = {rho}")
    ax2.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax2.set_xticks(xs, tab.index)
    ax2.legend()
    tidy(ax2, title="Manipulation-proof performance measure, % a year")
    caption(fig, "MPPM = ln(mean[((1+r)/(1+rf))^(1-ρ)]) x 12 / (1-ρ) (Goetzmann, Ingersoll, Spiegel and Welch, 2007). " + SOURCE)
    return fig


# ------------------------------------------------------------------ 10. fees


@cache
def _fee_grid() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    vols = np.array([0.05, 0.10, 0.15, 0.20, 0.30])
    out = {}
    for sh in (0.5, 1.0):
        out[f"all{sh}"] = np.array([H.fee_share(sh, v, paths=FEE_PATHS) for v in vols])
        out[f"inc{sh}"] = np.array([H.fee_share(sh, v, paths=FEE_PATHS, mgmt=0.0) for v in vols])
        out[f"nohwm{sh}"] = np.array([H.fee_share(sh, v, paths=FEE_PATHS, mgmt=0.0, high_water=False) for v in vols])
    return vols, out


def fees() -> Figure:
    vols, g = _fee_grid()
    i = int(np.argmin(np.abs(vols - 0.10)))
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"2 and 20 takes {g['all0.5'][i]:.0%} of a Sharpe-0.5 fund's gross return at 10% volatility; the high-water mark saves {100 * (g['nohwm0.5'][i] - g['inc0.5'][i]):.0f} points of it",
        f"Share of the mean gross return paid in fees, simulated funds with normal monthly returns over 10 years. Sharpe 1.0 at 10% volatility: {g['all1.0'][i]:.0%}. "
        f"The 2% management fee is fixed in assets, so it bites hardest on low-volatility funds; the incentive fee alone takes {g['inc0.5'][i]:.0%} with the mark and {g['nohwm0.5'][i]:.0%} without.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.62))
    for k, sh in enumerate((0.5, 1.0)):
        ax.plot(100 * vols, 100 * g[f"all{sh}"], "o-", color=SERIES[k], lw=2, label=f"2 and 20, Sharpe {sh}")
        ax.plot(100 * vols, 100 * g[f"inc{sh}"], "o--", color=SERIES[k], lw=1.4, label=f"20% incentive only, Sharpe {sh}")
    ax.legend()
    tidy(ax, title="Fees, % of mean gross return", xlabel="gross volatility (%)")
    ax2 = fig.add_axes((0.56, 0.13, 0.42, 0.62))
    for k, sh in enumerate((0.5, 1.0)):
        ax2.plot(100 * vols, 100 * g[f"nohwm{sh}"], "o-", color=SERIES[k], lw=1.6, label=f"no high-water mark, Sharpe {sh}")
        ax2.plot(100 * vols, 100 * g[f"inc{sh}"], "o--", color=SERIES[k], lw=1.4, label=f"high-water mark, Sharpe {sh}")
    ax2.axhline(20, color=PALETTE["muted"], lw=0.8)
    ax2.legend()
    tidy(ax2, title="Incentive fee alone, % of mean gross return", xlabel="gross volatility (%)")
    caption(
        fig,
        f"{FEE_PATHS:,} funds per point; incentive fee accrued monthly, crystallised yearly; zero risk-free rate, so gross return = excess return.",
    )
    return fig
