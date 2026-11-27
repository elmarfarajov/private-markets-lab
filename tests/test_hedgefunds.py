"""Hedge funds: lookback straddles, trend following, clones, the put factor, MPPM and fees."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pmlab import hedgefunds as H

IDX = pd.date_range("2000-01-31", periods=240, freq="ME")


def test_lookback_matches_hull() -> None:
    assert H.lookback_call(50, 50, 0.25, 0.10, 0.40) == pytest.approx(8.04, abs=0.005)
    assert H.lookback_put(50, 50, 0.25, 0.10, 0.40) == pytest.approx(7.79, abs=0.005)


def test_straddle_zero_rate_limit_and_monotone_in_vol() -> None:
    assert H.lookback_straddle(1 / 12, 0.0, 0.2) == pytest.approx(H.lookback_straddle(1 / 12, 0.0005, 0.2), rel=1e-3)
    p = H.lookback_straddle(1 / 12, 0.02, np.array([0.1, 0.2, 0.4]))
    assert np.all(np.diff(p) > 0)
    assert H.lookback_straddle(1 / 12, 0.02, 0.2, dt=1 / 252) < H.lookback_straddle(1 / 12, 0.02, 0.2)


def test_straddle_against_monte_carlo() -> None:
    cf = float(H.lookback_straddle(0.25, 0.03, 0.25))
    mc, se = H.lookback_mc(0.25, 0.03, 0.25, steps=200, paths=40_000, seed=1)
    assert abs(mc - cf) < 4 * se + 0.002


def test_ols_recovers_coefficients() -> None:
    rng = np.random.default_rng(2)
    x = pd.DataFrame(rng.normal(size=(240, 2)), IDX, ["a", "b"])
    y = 0.01 + 0.5 * x["a"] - 0.2 * x["b"] + rng.normal(0, 0.01, 240)
    fit = H.ols(pd.Series(y, IDX), x)
    assert fit.coef.to_numpy() == pytest.approx([0.01, 0.5, -0.2], abs=0.005) and fit.r2 > 0.99


def test_tsmom_goes_long_a_rising_asset() -> None:
    days = pd.bdate_range("2000-01-03", "2004-12-31")
    rng = np.random.default_rng(3)
    up = 100 * np.exp(np.cumsum(0.0008 + 0.01 * rng.standard_normal(len(days))))
    down = 100 * np.exp(np.cumsum(-0.0008 + 0.01 * rng.standard_normal(len(days))))
    daily = pd.DataFrame({"up": up, "down": down}, days)
    rf = pd.Series(0.0, daily.resample("ME").last().index)
    t = H.tsmom(daily, rf, min_assets=2)
    pos = t.positions.dropna()
    assert (pos["up"].iloc[-12:] > 0).all() and (pos["down"].iloc[-12:] < 0).all()
    assert t.portfolio.mean() > 0


def test_linear_clone_recovers_weights_and_is_out_of_sample() -> None:
    rng = np.random.default_rng(4)
    x = pd.DataFrame(rng.normal(0.0, 0.04, (240, 3)), IDX, ["a", "b", "c"])
    y = x @ np.array([0.6, 0.0, -0.4])
    c = H.linear_clone(y, x, renormalise=False)
    assert c.weights.to_numpy() == pytest.approx(np.tile([0.6, 0.0, -0.4], (216, 1)), abs=1e-10)
    assert c.returns.index[0] == IDX[24]
    q = H.clone_quality(c)
    assert q["correlation"] == pytest.approx(1.0) and q["tracking_error"] < 1e-10


def test_put_factor_loses_the_premium_when_the_market_rises() -> None:
    days = pd.bdate_range("2010-01-01", "2010-12-31")
    index = pd.Series(np.linspace(100, 130, len(days)), days)
    vix = pd.Series(20.0, days)
    rf = pd.Series(0.0, index.resample("ME").last().index)
    f = H.put_factor(index, vix, rf).dropna()
    assert (f == -1.0).all()


def test_mppm_constant_returns_and_risk_aversion() -> None:
    r = pd.Series(0.01, IDX)
    rf = pd.Series(0.002, IDX)
    assert H.mppm(r, rf, 3) == pytest.approx(12 * np.log(1.01 / 1.002))
    rng = np.random.default_rng(5)
    noisy = pd.Series(0.01 + 0.05 * rng.standard_normal(240), IDX)
    assert H.mppm(noisy, rf, 6) < H.mppm(noisy, rf, 2)


def test_fees_high_water_mark() -> None:
    g = (1.12) ** (1 / 12) - 1
    f = H.two_and_twenty(np.full((1, 24), g))
    year = ((1 + g) * (1 - 0.02 / 12)) ** 12
    assert np.prod(1 + f.net[0, :12]) == pytest.approx(1 + 0.8 * (year - 1), rel=1e-12)
    # a loss then the same gain back: no incentive fee with the mark, some without
    path = np.r_[np.full(12, -0.02), np.full(12, 1 / 0.98 - 1)][None, :]
    assert H.two_and_twenty(path, mgmt=0.0).incentive.sum() == pytest.approx(0.0)
    assert H.two_and_twenty(path, mgmt=0.0, high_water=False).incentive.sum() > 0


def test_fee_share_falls_with_sharpe() -> None:
    assert H.fee_share(1.0, 0.1, paths=300) < H.fee_share(0.5, 0.1, paths=300)
