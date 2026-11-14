"""Smoothed returns: the index, Geltner and GLM unsmoothing, and the risk measures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pmlab import smoothing as S


@pytest.fixture(scope="module")
def ix():
    return S.build_index(vintages=20, funds=20, seed=3)


def test_index_shape_and_smoothing(ix):
    assert len(ix.true) == len(ix.reported) == len(ix.market) == (20 - 1 - 5 + 1) * 4
    assert ix.reported.autocorr(1) > 0.4 > abs(ix.true.autocorr(1))
    assert ix.reported.std() < 0.8 * ix.true.std()
    assert set(ix.frame().columns) == {"true", "reported", "market"}


def test_public_share_sets_the_correlation():
    pure = S.build_index(vintages=15, funds=30, public=1.0, seed=4)
    mixed = S.build_index(vintages=15, funds=30, public=0.6, seed=4)
    assert pure.true.corr(pure.market) > 0.95 > mixed.true.corr(mixed.market)


def test_geltner_estimates_a_and_restores_volatility(ix):
    g, a = S.geltner(ix.reported)
    assert 0.25 < a < 0.6
    assert g.std() == pytest.approx(ix.true.std(), rel=0.25)
    g2, a2 = S.geltner(ix.reported, a=0.5)
    assert a2 == 0.5 and len(g2) == len(ix.reported) - 1


def test_glm_on_white_noise_puts_the_weight_on_lag_zero():
    x = pd.Series(np.random.default_rng(5).normal(0.01, 0.05, 2000))
    fit = S.glm(x, 2)
    assert fit.theta[0] > 0.9 and fit.xi > 0.8
    assert fit.sigma == pytest.approx(0.05, rel=0.05)
    assert np.isfinite(fit.loglik)


def test_glm_weights_follow_partial_adjustment(ix):
    fit = S.glm(ix.reported, 2)
    assert fit.theta.sum() == pytest.approx(1.0)
    assert np.all(np.diff(fit.theta) < 0)  # declining weights, as partial adjustment implies


def test_partial_adjustment_weights():
    w = S.partial_adjustment_weights(0.5, 2)
    assert w == pytest.approx(np.array([0.5, 0.25, 0.125]) / 0.875)
    assert S.partial_adjustment_weights(1.0, 3)[0] == pytest.approx(1.0)


def test_risk_table(ix):
    t = S.risk_table({"true": ix.true, "reported": ix.reported}, ix.market)
    assert list(t.columns) == ["mean", "vol", "sharpe", "beta", "corr", "maxdd", "ac1"]
    assert t.loc["reported", "vol"] < t.loc["true", "vol"]
    assert t.loc["reported", "beta"] < t.loc["true", "beta"]
    assert (t["maxdd"] <= 0).all()


def test_horizon_correlation_of_a_series_with_itself():
    s = pd.Series(np.random.default_rng(6).normal(0, 0.05, 80))
    hc = S.horizon_correlation(s, s, (1, 4))
    assert hc.to_numpy() == pytest.approx([1.0, 1.0])


def test_tangency_weight():
    rng = np.random.default_rng(7)
    m = pd.Series(rng.normal(0.015, 0.08, 400))
    a = pd.Series(rng.normal(0.015, 0.08, 400))
    assert 0.2 < S.tangency_weight(a, m) < 0.8  # two similar uncorrelated assets: about half each
