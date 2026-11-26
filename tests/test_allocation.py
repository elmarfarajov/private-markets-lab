"""Allocating to illiquid assets: the programme simulation, mean-variance and the DP."""

from __future__ import annotations

import numpy as np
import pytest

from pmlab import allocation as A


@pytest.fixture(scope="module")
def prog():
    return A.simulate_programme(A.Pacing(rate=0.05), years=12, scenarios=200, seed=1)


def test_programme_shapes_and_accounting(prog):
    n = 12 * 4
    assert prog.liquid.shape == (200, n) and prog.commitments.shape == (200, 12)
    assert np.all(prog.nav_true >= 0) and np.all(prog.unfunded >= -1e-12)
    assert np.allclose(prog.wealth_reported, prog.liquid + prog.nav_reported)
    assert prog.share_reported[:, 0].max() < 0.05 < np.median(prog.share_reported[:, -1])


def test_constant_rule_commits_a_share_of_wealth(prog):
    w = prog.wealth_reported[:, 3::4][:, :11]
    assert prog.commitments[:, 1:12] == pytest.approx(0.05 * w, rel=1e-12)


def test_feedback_rule_never_commits_negative():
    p = A.simulate_programme(A.Pacing(rate=0.0, gain=0.5, target=0.1), years=12, scenarios=100, seed=2)
    assert np.all(p.commitments >= 0) and (p.commitments == 0).any()


def test_discount_widens_after_falls():
    d = A._discount(np.array([0.2, 0.0, -0.2, -0.9]))
    assert d.tolist() == pytest.approx([0.05, 0.05, 0.21, 0.5])


def test_forced_sales_only_when_liquidity_is_tight():
    calm = A.simulate_programme(A.Pacing(rate=0.03), years=15, scenarios=100, seed=3, floor=0.05)
    tight = A.simulate_programme(A.Pacing(rate=0.14), years=15, scenarios=100, seed=3, floor=0.3)
    assert calm.sold.sum() == 0 and tight.sold.sum() > 0
    assert np.all(tight.sale_cost <= 0.5 * tight.sold + 1e-15)


def test_crash_raises_reported_share_and_lowers_true_share():
    a = A.simulate_programme(A.Pacing(rate=0.06), years=12, scenarios=200, seed=4, crash=(40, -0.4))
    b = A.simulate_programme(A.Pacing(rate=0.06), years=12, scenarios=200, seed=4)
    k = 40
    assert np.median(a.share_reported[:, k]) > np.median(b.share_reported[:, k])
    assert np.median(a.share_true[:, k]) < np.median(b.share_true[:, k])


def test_programme_moments_reported_is_smoother():
    m = A.programme_moments(funds=600)
    assert m["reported_vol"] < 0.7 * m["true_vol"] and m["reported_corr"] < m["true_corr"]


def test_mean_variance_formula():
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    w = A.mean_variance(np.array([0.08, 0.1]), cov, 0.02, 4.0)
    assert cov @ w * 4.0 == pytest.approx([0.06, 0.08])


def test_dp_targets_and_cost():
    d = A.DPSpec(mu_i=0.11, grid=41, theta_max=0.8, alphas=11, horizon=10)
    liquid, slow = A.solve_dp(d, 1.0), A.solve_dp(d, 0.1)
    assert slow.target <= liquid.target
    assert A.illiquidity_cost(d, 1.0, liquid) == pytest.approx(0.0, abs=1e-12)
    assert A.illiquidity_cost(d, 0.1, liquid) > 0
    assert liquid.alpha[0] >= liquid.alpha[-1]  # more illiquid risk, less public equity in the liquid part
