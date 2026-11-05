"""Day 5 charts: nowcasting true fund values from stale, noisy reported NAVs with the Kalman filter.

Funds come from the Day 3 stochastic model (``pmlab.fundmodel``); their reported NAVs from
``nowcast.appraise``. The true value is known, so every method is scored against it. Every number
in a subtitle is computed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from matplotlib.figure import Figure

from .. import fundmodel as F
from .. import nowcast as N
from .style import PALETTE, caption, new_figure, tidy, title_block

SPEC = F.StochasticSpec()
TRUE = N.Params.from_spec(SPEC)
SIMS = 2000  # funds behind each chart; the tests lower it
CRASH_Q = 20  # the quarter of the market crash in the crash charts (year 5)
MODEL = (
    "Model funds (Day 3): beta 1.2, market volatility 16%, own volatility 20%, expected return 11%, 12-year life. "
    "Appraisals: a = 0.4 of the gap closed each quarter, noise 5% (ADR 0015)."
)
METHODS = {
    "reported NAV": PALETTE["slate"],
    "market roll-forward": PALETTE["violet"],
    "Kalman filter": PALETTE["blue"],
    "Kalman smoother": PALETTE["green"],
}


def _crash_shocks() -> np.ndarray:
    z = np.random.default_rng(11).standard_normal(48) * 0.6
    z[CRASH_Q] = -3.5  # about a 25% fall in one quarter
    return z


@lru_cache(maxsize=1)
def _normal() -> tuple[N.Data, np.ndarray]:
    p = F.simulate(SPEC, SIMS, seed=1)
    d = N.Data.from_paths(p, seed=9)
    return d, p.value[:, : d.shape[1]]


@lru_cache(maxsize=1)
def _crash() -> tuple[N.Data, np.ndarray]:
    p = F.simulate(SPEC, SIMS, seed=2, market_shocks=_crash_shocks())
    d = N.Data.from_paths(p, seed=10)
    return d, p.value[:, : d.shape[1]]


def _estimates(d: N.Data) -> dict[str, np.ndarray]:
    fl = N.kalman(d, TRUE)
    ms, _ = N.smooth(fl)
    return {
        "reported NAV": d.reported,
        "market roll-forward": N.market_rollforward(d, TRUE.beta),
        "Kalman filter": fl.mean,
        "Kalman smoother": ms,
    }


@lru_cache(maxsize=1)
def _recovery() -> np.ndarray:
    rows = []
    for k in range(max(6, SIMS // 40)):
        rng = np.random.default_rng(100 + k)
        p = F.simulate(SPEC, 100, seed=200 + k, market_shocks=rng.standard_normal(48))
        e = N.estimate(N.Data.from_paths(p, seed=300 + k)).params
        rows.append((e.a, e.beta, e.sigma, e.obs))
    return np.array(rows)


def _q(x: np.ndarray) -> np.ndarray:
    return np.arange(x.shape[-1]) / 4 + 0.25


# ------------------------------------------------------------------ 1-3. what the filter sees


def one_fund() -> Figure:
    d, v = _crash()
    fl = N.kalman(d, TRUE)
    ms, vs = N.smooth(fl)
    i = int(np.argsort(v[:, CRASH_Q])[v.shape[0] // 2])
    t = _q(v[i])
    lo, hi = fl.mean[i] - 1.645 * np.sqrt(fl.var[i]), fl.mean[i] + 1.645 * np.sqrt(fl.var[i])
    k = CRASH_Q
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "After a crash, the reported NAV is still catching up; the filter is not",
        f"One model fund through a market fall of {100 * (1 - np.exp(d.log_market[i, k])):.0f}% in year {k // 4 + 1}. In that quarter its true value moved to "
        f"{v[i, k]:.0f}, the reported NAV to {d.reported[i, k]:.0f} and the filtered nowcast to {fl.mean[i, k]:.0f} (90% band {lo[k]:.0f}-{hi[k]:.0f}). "
        "The filter reads the market's fall the quarter it happens; the appraisal takes several quarters.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.fill_between(t, lo, hi, color=PALETTE["blue"], alpha=0.15, lw=0, label="filter, 90% band")
    ax.plot(t, v[i], color=PALETTE["ink"], lw=2.2, label="true value")
    ax.plot(t, d.reported[i], color=PALETTE["slate"], lw=1.4, ls="--", label="reported NAV")
    ax.plot(t, fl.mean[i], color=PALETTE["blue"], lw=1.6, label="Kalman filter")
    ax.plot(t, ms[i], color=PALETTE["green"], lw=1.2, label="Kalman smoother")
    ax.axvline(t[k], color=PALETTE["accent"], lw=1, ls=":")
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, xlabel="fund age, years", ylabel="value, per 100 committed")
    caption(fig, MODEL)
    return fig


def crash() -> Figure:
    d, v = _crash()
    est = _estimates(d)
    fig = new_figure(14.5, 6.2)
    mean_err = {m: np.nanmean(N.errors(e, v, skip=0), axis=0) for m, e in est.items()}
    k = CRASH_Q
    rep_lag = (
        int(np.argmax(np.abs(mean_err["reported NAV"][k:]) < 0.02)) if (np.abs(mean_err["reported NAV"][k:]) < 0.02).any() else -1
    )
    title_block(
        fig,
        "Reported NAVs overstate value long after a crash; the filter does not",
        f"Average error against the true value across {v.shape[0]:,} funds of one vintage that share a market path with a fall in year {k // 4 + 1}. "
        f"In the crash quarter the reported NAV overstates by {100 * mean_err['reported NAV'][k]:.0f}%, the filter by {100 * mean_err['Kalman filter'][k]:+.1f}%. "
        f"The reported NAV's error stays above 2% for {rep_lag} quarters.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    t = _q(v[0])
    for m, col in METHODS.items():
        ax.plot(t, 100 * mean_err[m], color=col, lw=1.8 if "Kalman" in m else 1.3, label=m)
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    ax.axvline(t[k], color=PALETTE["accent"], lw=1, ls=":")
    ax.set_xlim(t[0], 10)
    ax.legend(frameon=False)
    tidy(ax, xlabel="fund age, years", ylabel="mean error against true value, %")
    caption(fig, MODEL + " Market roll-forward: last reported NAV times beta x this quarter's market return, plus flows.")
    return fig


def errors_by_age() -> Figure:
    d, v = _normal()
    est = _estimates(d)
    r = {m: N.rmse(N.errors(e, v), axis=0) for m, e in est.items()}
    tot = {m: N.rmse(N.errors(e, v)) for m, e in est.items()}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Filtering cuts the error in a fund's value; smoothing cuts it further",
        f"Root-mean-square error against the true value, {v.shape[0]:,} funds in independent markets, years 2-10, fund-quarters worth over 5 per 100 committed. Overall: reported NAV {100 * tot['reported NAV']:.1f}%, "
        f"market roll-forward {100 * tot['market roll-forward']:.1f}%, Kalman filter {100 * tot['Kalman filter']:.1f}%, smoother {100 * tot['Kalman smoother']:.1f}% "
        "(the smoother also uses later reports, so it serves for history, not for today).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    t = _q(v[0])[4:]
    keep = t <= 10
    for m, col in METHODS.items():
        ax.plot(t[keep], 100 * r[m][keep], color=col, lw=1.8, label=m)
    ax.legend(frameon=False)
    tidy(ax, xlabel="fund age, years", ylabel="RMSE, % of true value")
    caption(fig, MODEL + " Filter and smoother use the true parameters; Chart nc-recovery shows they can be estimated.")
    return fig


# ------------------------------------------------------------------ 4-6. can it be trusted


def coverage() -> Figure:
    d, v = _normal()
    fl = N.kalman(d, TRUE)
    z = ((v - fl.mean) / np.sqrt(fl.var))[:, 4:].ravel()
    z = z[np.isfinite(z)]
    levels = np.array([0.5, 0.8, 0.9, 0.95, 0.99])
    from scipy.stats import norm

    emp = np.array([np.mean(np.abs(z) < norm.ppf(0.5 + lv / 2)) for lv in levels])
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "The filter knows how uncertain it is",
        f"Share of true values inside the filter's intervals, {z.size:,} fund-quarters. The 90% interval covers {100 * emp[2]:.1f}% and the 99% interval "
        f"{100 * emp[4]:.1f}%; standardised errors have a standard deviation of {np.std(z):.2f}. The nowcast comes with an honest error bar.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.plot(100 * levels, 100 * levels, color=PALETTE["muted"], ls="--", lw=1)
    ax.plot(100 * levels, 100 * emp, "o-", color=PALETTE["blue"], lw=1.8)
    tidy(ax, title="Coverage", xlabel="nominal, %", ylabel="actual, %")
    ax2 = fig.add_axes((0.56, 0.13, 0.4, 0.58))
    ax2.hist(np.clip(z, -5, 5), bins=60, density=True, color=PALETTE["band"], edgecolor=PALETTE["slate"])
    xs = np.linspace(-5, 5, 200)
    ax2.plot(xs, norm.pdf(xs), color=PALETTE["blue"], lw=1.6)
    tidy(ax2, title="Standardised errors against N(0, 1)")
    caption(fig, MODEL)
    return fig


def recovery() -> Figure:
    est = _recovery()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "The model's parameters can be estimated from reported NAVs, cash flows and the market",
        f"Maximum-likelihood estimates from {est.shape[0]} panels of 100 funds, each panel sharing one market path. Smoothing a: mean {est[:, 0].mean():.2f} "
        f"(true {TRUE.a:.2f}, sd {est[:, 0].std():.2f}); beta: mean {est[:, 1].mean():.2f} (true {TRUE.beta:.2f}, sd {est[:, 1].std():.2f}); appraisal noise: "
        f"{100 * est[:, 3].mean():.1f}% (true {100 * TRUE.obs:.0f}%).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.scatter(est[:, 0], est[:, 1], s=18, color=PALETTE["blue"], alpha=0.7)
    ax.axvline(TRUE.a, color=PALETTE["muted"], ls="--")
    ax.axhline(TRUE.beta, color=PALETTE["muted"], ls="--")
    tidy(ax, title="Each panel's estimate", xlabel="smoothing a", ylabel="beta")
    ax2 = fig.add_axes((0.56, 0.13, 0.4, 0.58))
    ax2.hist(est[:, 2] * 2, bins=15, color=PALETTE["green"], alpha=0.8)
    ax2.axvline(TRUE.sigma * 2, color=PALETTE["ink"], ls="--")
    tidy(ax2, title="Own volatility, a year", xlabel="estimate")
    caption(fig, MODEL)
    return fig


def panel_size() -> Figure:
    sizes = (1, 5, 20, 100)
    draws = max(5, SIMS // 200)
    out = {}
    for n in sizes:
        b = []
        for k in range(draws):
            p = F.simulate(SPEC, n, seed=500 + 7 * k + n, market_shocks=np.random.default_rng(900 + k).standard_normal(48))
            b.append(N.estimate(N.Data.from_paths(p, seed=700 + k)).params.beta)
        out[n] = np.array(b)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "One fund's history is not enough to estimate its model; a portfolio of funds is",
        f"Spread of the beta estimate by the number of funds pooled ({draws} panels each). One fund: median {np.median(out[1]):.2f}, "
        f"interquartile range {np.subtract(*np.percentile(out[1], [75, 25])):.2f}. A hundred funds: {np.median(out[100]):.2f}, range "
        f"{np.subtract(*np.percentile(out[100], [75, 25])):.2f}. Brown, Ghysels and Gredil (2023) also pool funds of a strategy.",
    )
    ax = fig.add_axes((0.08, 0.13, 0.88, 0.58))
    ax.boxplot([np.clip(out[n], -2, 5) for n in sizes], showfliers=False)
    ax.set_xticks(range(1, len(sizes) + 1), [str(n) for n in sizes])
    ax.axhline(TRUE.beta, color=PALETTE["accent"], ls="--", lw=1)
    tidy(ax, xlabel="funds in the panel", ylabel="estimated beta")
    caption(fig, MODEL)
    return fig


# ------------------------------------------------------------------ 7-10. what the smoothing does


def beta_bias() -> Figure:
    a_s = (0.2, 0.4, 0.6, 0.8, 1.0)
    rows = []
    for a in a_s:
        p = F.simulate(SPEC, max(200, SIMS // 5), seed=31, market_shocks=None)
        d = N.Data.from_paths(p, a=a, seed=32)
        rows.append((N.naive_beta(d), N.naive_beta(d, lags=4), N.estimate(d).params.beta))
    r = np.array(rows)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Betas from reported NAVs are too low; the state-space model recovers the true one",
        f"Beta estimated three ways for funds appraised with different smoothing (true beta {TRUE.beta}). At a = 0.4, a regression of reported returns on the "
        f"market gives {r[1, 0]:.2f}, adding four lags (Dimson 1979) {r[1, 1]:.2f}, and the state-space model {r[1, 2]:.2f}. Without smoothing (a = 1) the regression gives {r[4, 0]:.2f}.",
    )
    ax = fig.add_axes((0.08, 0.13, 0.88, 0.58))
    for j, (lab, col) in enumerate(
        (
            ("reported returns", PALETTE["slate"]),
            ("with 4 lags (Dimson)", PALETTE["violet"]),
            ("state-space model", PALETTE["blue"]),
        )
    ):
        ax.plot(a_s, r[:, j], "o-", color=col, lw=1.8, label=lab)
    ax.axhline(TRUE.beta, color=PALETTE["ink"], ls="--", lw=1, label="true beta")
    ax.legend(frameon=False)
    tidy(ax, xlabel="smoothing a (share of the gap closed each quarter)", ylabel="estimated beta")
    caption(fig, MODEL + " Markets independent across funds.")
    return fig


def noise_grid() -> Figure:
    a_s = (0.2, 0.4, 0.6, 0.8, 1.0)
    noises = (0.01, 0.03, 0.05, 0.10, 0.15)
    p = F.simulate(SPEC, max(200, SIMS // 4), seed=41)
    g = np.zeros((len(a_s), len(noises)))
    for i, a in enumerate(a_s):
        for j, nz in enumerate(noises):
            d = N.Data.from_paths(p, a=a, noise=nz, seed=42)
            v = p.value[:, : d.shape[1]]
            par = N.Params(a, TRUE.beta, TRUE.c, TRUE.sigma, nz)
            g[i, j] = N.rmse(N.errors(N.kalman(d, par).mean, v)) / N.rmse(N.errors(d.reported, v))
    fig = new_figure(12.5, 6.4)
    title_block(
        fig,
        "Filtering helps most when appraisals are slow but precise",
        f"Filter error as a share of the reported NAV's error, for each speed of appraisal (rows) and noise level (columns). Slow, precise appraisals (a = 0.2, 1% noise) "
        f"can be unsmoothed: the filter keeps {100 * g[0, 0]:.0f}% of the error. Slow, noisy ones (a = 0.2, 15%) cannot: {100 * g[0, -1]:.0f}%. Fast, precise ones "
        f"leave nothing to add ({100 * g[-1, 0]:.0f}%); fast, noisy ones gain from the market forecast ({100 * g[-1, -1]:.0f}%).",
    )
    ax = fig.add_axes((0.12, 0.12, 0.78, 0.58))
    im = ax.imshow(100 * g, cmap="Blues_r", vmin=0, vmax=100, aspect="auto")
    for i in range(g.shape[0]):
        for j in range(g.shape[1]):
            ax.text(
                j,
                i,
                f"{100 * g[i, j]:.0f}%",
                ha="center",
                va="center",
                fontsize=10,
                color="white" if g[i, j] < 0.5 else PALETTE["ink"],
            )
    ax.set_xticks(range(len(noises)), [f"{100 * n:.0f}%" for n in noises])
    ax.set_yticks(range(len(a_s)), [f"{a:.1f}" for a in a_s])
    fig.colorbar(im, ax=ax, fraction=0.03)
    ax.grid(False)
    tidy(ax, xlabel="appraisal noise a quarter", ylabel="smoothing a")
    caption(fig, MODEL + " Filter run with the true parameters of each cell.")
    return fig


def misspecified() -> Figure:
    d, v = _normal()
    base = N.rmse(N.errors(N.kalman(d, TRUE).mean, v))
    rep = N.rmse(N.errors(d.reported, v))
    a_s = np.array([0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0])
    b_s = np.array([0.0, 0.6, 1.0, 1.2, 1.4, 1.8])
    ea = [N.rmse(N.errors(N.kalman(d, N.Params(a, TRUE.beta, TRUE.c, TRUE.sigma, TRUE.obs)).mean, v)) for a in a_s]
    eb = [N.rmse(N.errors(N.kalman(d, N.Params(TRUE.a, b, TRUE.c, TRUE.sigma, TRUE.obs)).mean, v)) for b in b_s]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "The smoothing must be modelled; the market adds a little more",
        f"Filter error when it assumes the wrong smoothing (left) or the wrong beta (right). True values: a = {TRUE.a}, beta = {TRUE.beta}; filter error {100 * base:.1f}%, "
        f"reported NAV {100 * rep:.1f}%. Assuming a = 1 (no smoothing) gives {100 * ea[-1]:.1f}%; assuming beta = 0 gives {100 * eb[0]:.1f}%.",
    )
    for k, (xs, es, lab, tv) in enumerate(((a_s, ea, "assumed smoothing a", TRUE.a), (b_s, eb, "assumed beta", TRUE.beta))):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        ax.plot(xs, 100 * np.array(es), "o-", color=PALETTE["blue"], lw=1.8, label="Kalman filter")
        ax.axhline(100 * rep, color=PALETTE["slate"], ls="--", lw=1, label="reported NAV")
        ax.axvline(tv, color=PALETTE["muted"], ls=":", lw=1)
        ax.legend(frameon=False)
        tidy(ax, xlabel=lab, ylabel="RMSE, % of true value" if k == 0 else None)
    caption(fig, MODEL)
    return fig


def gain() -> Figure:
    d, v = _normal()
    fl = N.kalman(d, TRUE)
    w = (
        TRUE.a**2
        * fl.pred_var
        / (
            TRUE.a**2 * fl.pred_var
            + (TRUE.obs * (np.concatenate([np.zeros((d.shape[0], 1)), d.reported[:, :-1]], axis=1) + d.calls + 1.0)) ** 2
        )
    )
    m = np.nanmean(w, axis=0)
    t = _q(v[0])
    fig = new_figure(14.5, 5.6)
    title_block(
        fig,
        "How much the filter believes each new report",
        f"Weight the filter puts on the new reported NAV against its own forecast from the market and the cash flows, averaged over funds. It is {m[4]:.2f} in year 2 "
        f"and {m[-1]:.2f} in the last year: the market tells the filter roughly as much as the appraisal does.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(t, m, color=PALETTE["blue"], lw=2)
    ax.set_ylim(0, 1)
    tidy(ax, xlabel="fund age, years", ylabel="weight on the new report")
    caption(fig, MODEL)
    return fig
