"""Hedge funds and liquid alternatives: trend following, lookback straddles, replication, tail risk and fees.

Hedge-fund returns are, to a first approximation, exposures to factors, and some of those
exposures are not linear. This module holds the tools to see which:

* **Trend following** as time-series momentum (Moskowitz, Ooi and Pedersen, 2012): each asset is
  held long or short by the sign of its past twelve-month excess return, at a 40% volatility
  target, and the portfolio averages the assets.
* **The lookback straddle** (Fung and Hsieh, 2001): a trend follower's payoff resembles an option
  that pays the range of a price over a period. It is priced in closed form (Goldman, Sosin and
  Gatto, 1979) and checked against Monte Carlo with the Broadie-Glasserman-Kou continuity shift;
  monthly straddle returns on liquid ETFs are the trend factors.
* **Linear clones** (Hasanhodzic and Lo, 2007): a rolling regression on liquid factors, applied out
  of sample and renormalised to the target's volatility.
* **Tail risk**: an at-the-money put factor (Agarwal and Naik, 2004) priced from the VIX, and the
  manipulation-proof performance measure (Goetzmann, Ingersoll, Spiegel and Welch, 2007).
* **Fees**: 2 and 20 with a high-water mark, accrued monthly and crystallised once a year.

Every function takes plain pandas or numpy data; the ETF histories are loaded by ``market``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

Array = np.ndarray
BGK = 0.5826  # -zeta(1/2) / sqrt(2 pi): the Broadie-Glasserman-Kou continuity correction


# ------------------------------------------------------------------ data helpers


def monthly_rf(tbill_daily: pd.Series) -> pd.Series:
    """Monthly risk-free return earned during each month: last month's 13-week bill yield / 12."""
    return (tbill_daily.resample("ME").last() / 100 / 12).shift(1).rename("rf")


def monthly_returns(daily: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Month-end to month-end simple returns."""
    return daily.resample("ME").last().pct_change(fill_method=None)


def excess(daily: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    r = monthly_returns(daily)
    return r.sub(rf.reindex(r.index), axis=0)


@dataclass(frozen=True)
class OLS:
    coef: pd.Series
    t: pd.Series
    se: pd.Series
    r2: float
    n: int
    resid: pd.Series


def ols(y: pd.Series, x: pd.DataFrame, lags: int = 3, constant: bool = True) -> OLS:
    """Least squares with Newey-West (Bartlett) standard errors."""
    data = pd.concat([y.rename("_y"), x], axis=1).dropna()
    yy = data["_y"].to_numpy()
    xx = data.drop(columns="_y")
    if constant:
        xx = xx.assign(const=1.0)[["const", *x.columns]]
    xm = xx.to_numpy(dtype=float)
    n, k = xm.shape
    b, *_ = np.linalg.lstsq(xm, yy, rcond=None)
    e = yy - xm @ b
    inv = np.linalg.inv(xm.T @ xm)
    u = xm * e[:, None]
    s = u.T @ u
    for lag in range(1, lags + 1):
        g = u[lag:].T @ u[:-lag]
        s += (1 - lag / (lags + 1)) * (g + g.T)
    cov = inv @ s @ inv * n / (n - k)
    se = np.sqrt(np.diag(cov))
    r2 = 1 - e @ e / np.sum((yy - yy.mean()) ** 2)
    names = list(xx.columns)
    return OLS(pd.Series(b, names), pd.Series(b / se, names), pd.Series(se, names), float(r2), n, pd.Series(e, data.index))


# ------------------------------------------------------------------ trend following


def ex_ante_vol(daily: pd.DataFrame, com: int = 60) -> pd.DataFrame:
    """Annualised exponentially weighted daily volatility (centre of mass 60 days), at each month end."""
    r = daily.pct_change(fill_method=None)
    vol = np.sqrt(r.ewm(com=com, min_periods=com).var() * 261)
    return vol.resample("ME").last()


@dataclass(frozen=True)
class TSMOM:
    assets: pd.DataFrame  # each asset's scaled excess return
    positions: pd.DataFrame  # leverage held over the next month (signed)
    portfolio: pd.Series  # equal-weighted average of the available assets


def tsmom(daily: pd.DataFrame, rf: pd.Series, lookback: int = 12, target: float = 0.40, min_assets: int = 6) -> TSMOM:
    """Time-series momentum: sign of the past ``lookback``-month excess return, scaled to ``target`` volatility."""
    ex = excess(daily, rf)
    past = np.log1p(ex).rolling(lookback, min_periods=lookback).sum()
    pos = np.sign(past) * target / ex_ante_vol(daily).reindex(ex.index)
    assets = pos.shift(1) * ex
    count = assets.notna().sum(axis=1)
    port = assets.mean(axis=1)[count >= min_assets]
    return TSMOM(assets, pos, port.rename("tsmom"))


def compound(r: pd.Series | pd.DataFrame, freq: str = "QE") -> pd.Series | pd.DataFrame:
    """Compound monthly returns to a lower frequency, keeping only complete periods."""
    g = r.add(1).resample(freq)
    out = g.prod() - 1
    return out[g.count() == g.size().max()] if isinstance(r, pd.Series) else out


def smile(y: pd.Series, x: pd.Series) -> OLS:
    """y = a + b x + c x^2: a positive c is the trend follower's convexity in the market."""
    frame = pd.DataFrame({"x": x, "x2": x**2})
    return ols(y, frame, lags=1)


# ------------------------------------------------------------------ lookback straddle


def _r(r: float | Array) -> Array:
    """The formulas divide by r; below 1bp a year the limit is approached at 1bp."""
    return np.asarray(np.maximum(np.asarray(r, dtype=float), 1e-4))


def lookback_call(s: float | Array, smin: float | Array, t: float, r: float | Array, sigma: float | Array) -> Array:
    """Floating-strike lookback call, pays S_T - min S (Goldman, Sosin and Gatto, 1979; no dividends)."""
    s, smin, r, sigma = np.asarray(s, float), np.asarray(smin, float), _r(r), np.asarray(sigma, float)
    v = sigma * np.sqrt(t)
    k = sigma**2 / (2 * r)
    lr = np.log(s / smin)
    a1 = (lr + (r + sigma**2 / 2) * t) / v
    a2 = a1 - v
    a3 = (lr + (-r + sigma**2 / 2) * t) / v
    y1 = -2 * (r - sigma**2 / 2) * lr / sigma**2
    return np.asarray(
        s * norm.cdf(a1) - s * k * norm.cdf(-a1) - smin * np.exp(-r * t) * (norm.cdf(a2) - k * np.exp(y1) * norm.cdf(-a3))
    )


def lookback_put(s: float | Array, smax: float | Array, t: float, r: float | Array, sigma: float | Array) -> Array:
    """Floating-strike lookback put, pays max S - S_T."""
    s, smax, r, sigma = np.asarray(s, float), np.asarray(smax, float), _r(r), np.asarray(sigma, float)
    v = sigma * np.sqrt(t)
    k = sigma**2 / (2 * r)
    lr = np.log(smax / s)
    b1 = (lr + (-r + sigma**2 / 2) * t) / v
    b2 = b1 - v
    b3 = (lr + (r - sigma**2 / 2) * t) / v
    y2 = 2 * (r - sigma**2 / 2) * lr / sigma**2
    return np.asarray(
        smax * np.exp(-r * t) * (norm.cdf(b1) - k * np.exp(y2) * norm.cdf(-b3)) + s * k * norm.cdf(-b2) - s * norm.cdf(b2)
    )


def lookback_straddle(t: float, r: float | Array, sigma: float | Array, dt: float | None = None) -> Array:
    """Price, per unit of the underlying, of a new lookback straddle: it pays max S - min S over [0, t].

    With ``dt`` the extremes are taken only at dates ``dt`` apart (daily closes, say), and the
    continuous prices are shifted by Broadie, Glasserman and Kou's correction c = 0.5826 sigma sqrt(dt):
    call_m(S, m) = e^c call(S, m e^-c) - (e^c - 1) S and put_m(S, M) = e^-c put(S, M e^c) - (1 - e^-c) S.
    """
    if dt is None:
        return np.asarray(lookback_call(1.0, 1.0, t, r, sigma) + lookback_put(1.0, 1.0, t, r, sigma))
    c = BGK * np.asarray(sigma, float) * np.sqrt(dt)
    up, down = np.exp(c), np.exp(-c)
    call = up * lookback_call(1.0, down, t, r, sigma) - (up - 1)
    put = down * lookback_put(1.0, up, t, r, sigma) - (1 - down)
    return np.asarray(call + put)


def lookback_mc(
    t: float, r: float, sigma: float, steps: int = 252, paths: int = 200_000, seed: int = 0, shift: bool = True
) -> tuple[float, float]:
    """Monte Carlo price and standard error of the straddle, monitored at ``steps`` dates (antithetic).

    With ``shift`` the discrete maximum and minimum are moved out by exp(+-0.5826 sigma sqrt(dt)),
    Broadie, Glasserman and Kou's correction towards continuous monitoring.
    """
    rng = np.random.default_rng(seed)
    dt = t / steps
    z = rng.standard_normal((paths // 2, steps))
    z = np.vstack([z, -z])
    logs = np.cumsum((r - sigma**2 / 2) * dt + sigma * np.sqrt(dt) * z, axis=1)
    hi = np.exp(np.maximum(logs.max(axis=1), 0.0))
    lo = np.exp(np.minimum(logs.min(axis=1), 0.0))
    if shift:
        c = np.exp(BGK * sigma * np.sqrt(dt))
        hi, lo = hi * c, lo / c
    pay = np.exp(-r * t) * (hi - lo)
    half = pay.reshape(2, -1).mean(axis=0)
    return float(pay.mean()), float(half.std(ddof=1) / np.sqrt(half.size))


def straddle_returns(daily: pd.DataFrame, rf: pd.Series, window: int = 63) -> pd.DataFrame:
    """Monthly return on buying a one-month lookback straddle on each asset.

    The premium is the closed-form price for daily monitoring at last month's close, with trailing
    ``window``-day realised volatility standing in for implied volatility (no option data are used);
    the payoff is the month's range of daily closes, including last month's close.
    """
    close = daily.resample("ME").last()
    s0 = close.shift(1)
    hi = np.maximum(daily.resample("ME").max(), s0)
    lo = np.minimum(daily.resample("ME").min(), s0)
    vol = (daily.pct_change(fill_method=None).rolling(window).std() * np.sqrt(252)).resample("ME").last().shift(1)
    r = rf.reindex(close.index).to_numpy()[:, None] * 12
    premium = s0 * lookback_straddle(1 / 12, np.nan_to_num(r, nan=0.0), vol.to_numpy(), dt=1 / 252)
    return (hi - lo) / premium - 1


def class_factors(straddles: pd.DataFrame, classes: dict[str, str]) -> pd.DataFrame:
    """Average straddle return within each asset class (trend factors by market)."""
    groups: dict[str, list[str]] = {}
    for name, cls in classes.items():
        groups.setdefault(cls, []).append(name)
    return pd.DataFrame({cls: straddles[cols].mean(axis=1) for cls, cols in groups.items()})


# ------------------------------------------------------------------ replication


@dataclass(frozen=True)
class Clone:
    returns: pd.Series  # out-of-sample clone excess return
    weights: pd.DataFrame  # weights held in each month (after renormalisation)
    target: pd.Series


def linear_clone(target: pd.Series, factors: pd.DataFrame, window: int = 24, renormalise: bool = True) -> Clone:
    """Rolling regression without a constant, applied one month ahead (Hasanhodzic and Lo, 2007).

    Weights for month t use only months t - window .. t - 1; with ``renormalise`` they are scaled
    so the clone's in-window volatility equals the target's.
    """
    data = pd.concat([target.rename("_y"), factors], axis=1).dropna()
    y, x = data["_y"].to_numpy(), data.drop(columns="_y").to_numpy()
    out, wts, idx = [], [], []
    for t in range(window, len(data)):
        ys, xs = y[t - window : t], x[t - window : t]
        w, *_ = np.linalg.lstsq(xs, ys, rcond=None)
        if renormalise:
            fit = xs @ w
            w = w * ys.std(ddof=1) / fit.std(ddof=1)
        out.append(x[t] @ w)
        wts.append(w)
        idx.append(data.index[t])
    rets = pd.Series(out, idx, name="clone")
    return Clone(rets, pd.DataFrame(wts, idx, factors.columns), data["_y"].loc[idx])


def clone_quality(c: Clone) -> dict[str, float]:
    gap = c.target - c.returns
    return {
        "months": float(len(c.returns)),
        "correlation": float(c.target.corr(c.returns)),
        "tracking_error": float(gap.std(ddof=1) * np.sqrt(12)),
        "target_mean": float(c.target.mean() * 12),
        "clone_mean": float(c.returns.mean() * 12),
        "vol_ratio": float(c.returns.std(ddof=1) / c.target.std(ddof=1)),
    }


# ------------------------------------------------------------------ tail risk


def bs_put(s: float | Array, k: float | Array, t: float, r: float | Array, sigma: float | Array) -> Array:
    s, k, r, sigma = (np.asarray(a, float) for a in (s, k, r, sigma))
    d1 = (np.log(s / k) + (r + sigma**2 / 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    return np.asarray(k * np.exp(-r * t) * norm.cdf(-d2) - s * norm.cdf(-d1))


def put_factor(index_daily: pd.Series, vix_daily: pd.Series, rf: pd.Series, moneyness: float = 1.0) -> pd.Series:
    """Monthly return on buying a one-month put struck at ``moneyness`` x last month's close.

    Priced by Black-Scholes at last month-end's VIX (Agarwal and Naik's option factor, built from
    the index and its implied volatility rather than from traded option prices).
    """
    close = index_daily.resample("ME").last()
    s0 = close.shift(1)
    vol = vix_daily.resample("ME").last().shift(1) / 100
    r = rf.reindex(close.index) * 12
    k = moneyness * s0
    premium = bs_put(s0, k, 1 / 12, r.fillna(0.0), vol)
    payoff = np.maximum(k - close, 0.0)
    return (payoff / premium - 1).rename(f"put{moneyness:.2f}")


def max_drawdown(r: pd.Series) -> float:
    wealth = (1 + r.dropna()).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def mppm(r: pd.Series, rf: pd.Series, rho: float = 3.0, periods: int = 12) -> float:
    """Goetzmann-Ingersoll-Spiegel-Welch manipulation-proof measure: an annualised certainty-equivalent excess return."""
    data = pd.concat([r, rf], axis=1).dropna()
    rel = (1 + data.iloc[:, 0]) / (1 + data.iloc[:, 1])
    return float(np.log(np.mean(rel ** (1 - rho))) * periods / (1 - rho))


def summary(r: pd.Series, rf: pd.Series, market: pd.Series | None = None) -> dict[str, float]:
    """Annualised excess mean, volatility, Sharpe, skewness, excess kurtosis, worst month, drawdown, MPPM."""
    data = pd.concat([r.rename("r"), rf.rename("rf")], axis=1).dropna()
    ex = data["r"] - data["rf"]
    out = {
        "months": float(len(ex)),
        "mean": float(ex.mean() * 12),
        "vol": float(ex.std(ddof=1) * np.sqrt(12)),
        "sharpe": float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)),
        "skew": float(ex.skew()),
        "kurt": float(ex.kurt()),
        "worst": float(ex.min()),
        "drawdown": max_drawdown(data["r"]),
        "mppm3": mppm(data["r"], data["rf"], 3.0),
    }
    if market is not None:
        m = (market - rf).reindex(ex.index)
        out["beta"] = float(ex.cov(m) / m.var())
    return out


# ------------------------------------------------------------------ fees


@dataclass(frozen=True)
class Fees:
    net: Array  # net monthly returns (paths x months)
    management: Array  # management fee paid each month, per unit of starting capital
    incentive: Array  # incentive fee crystallised each month, per unit of starting capital


def two_and_twenty(gross: Array, mgmt: float = 0.02, perf: float = 0.20, crystallise: int = 12, high_water: bool = True) -> Fees:
    """Net returns under a management fee on assets and an incentive fee over a high-water mark.

    Each month the gross return is earned and mgmt/12 of assets is paid. The incentive fee,
    ``perf`` of the gain above the high-water mark, is accrued in the reported NAV every month
    and paid every ``crystallise`` months, when the mark resets to the NAV after the fee. Without
    ``high_water`` the mark resets to the NAV at every crystallisation, so losses are forgiven.
    """
    g = np.atleast_2d(np.asarray(gross, float))
    paths, months = g.shape
    gnav = np.ones(paths)
    hwm = np.ones(paths)
    prev = np.ones(paths)
    net = np.empty_like(g)
    mg = np.zeros_like(g)
    inc = np.zeros_like(g)
    for t in range(months):
        gnav = gnav * (1 + g[:, t])
        mg[:, t] = gnav * mgmt / 12
        gnav = gnav - mg[:, t]
        accrued = perf * np.maximum(gnav - hwm, 0.0)
        nav = gnav - accrued
        if (t + 1) % crystallise == 0:
            inc[:, t] = accrued
            gnav = nav
            hwm = np.maximum(hwm, gnav) if high_water else gnav.copy()
        net[:, t] = nav / prev - 1
        prev = nav
    return Fees(net, mg, inc)


def fee_share(
    sharpe: float, vol: float, years: int = 10, paths: int = 4000, seed: int = 0, mgmt: float = 0.02, high_water: bool = True
) -> float:
    """Share of a fund's mean gross return taken by fees (normal monthly returns, no risk-free rate)."""
    rng = np.random.default_rng(seed)
    mu = sharpe * vol / 12
    g = mu + vol / np.sqrt(12) * rng.standard_normal((paths, years * 12))
    f = two_and_twenty(g, mgmt=mgmt, high_water=high_water)
    return float(1 - f.net.mean() / g.mean())
