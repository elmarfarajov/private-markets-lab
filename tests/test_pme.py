"""Public market equivalents: the identities every method must satisfy, closed forms, and known biases."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pmlab.pme import direct_alpha, ks_pme, long_nickels, mpme, pme_plus, report
from pmlab.synthetic import FundSpec, gbm_market, simulate_fund


@pytest.mark.parametrize("seed", range(5))
def test_a_fund_that_is_the_index_scores_a_pme_of_one_under_every_method(seed):
    f = simulate_fund(gbm_market(15.0, seed=seed), FundSpec(alpha=0.0, seed=seed))
    for horizon in (5.0, 9.0, float(f.times[-1])):
        t, a, nav, idx, navs = f.until(horizon)
        r = report(t, a, idx, nav, navs)
        assert r.ks_pme == pytest.approx(1.0, abs=1e-12)
        assert r.direct_alpha == pytest.approx(0.0, abs=1e-12)
        for index_irr in (r.ln_irr, r.pme_plus_irr, r.mpme_irr):
            assert index_irr == pytest.approx(r.fund_irr, abs=1e-10)


def test_closed_forms_for_a_single_deal():
    r, g, horizon = 0.12, 0.05, 7.0
    t, a, idx = np.array([0.0, horizon]), np.array([-1.0, (1 + r) ** horizon]), np.array([1.0, (1 + g) ** horizon])
    assert ks_pme(a, idx) == pytest.approx(((1 + r) / (1 + g)) ** horizon, rel=1e-14)
    assert direct_alpha(t, a, idx) == pytest.approx(np.log((1 + r) / (1 + g)), abs=1e-14)
    assert long_nickels(t, a, idx).index_irr == pytest.approx(g, abs=1e-12)
    assert pme_plus(t, a, idx)[0] == pytest.approx(g, abs=1e-12)  # no distributions before the end: the scale is moot


@pytest.mark.parametrize("alpha", [-0.05, 0.0, 0.04, 0.1])
def test_direct_alpha_recovers_the_alpha_of_noise_free_beta_one_funds(alpha):
    f = simulate_fund(gbm_market(15.0, seed=4), FundSpec(alpha=alpha, seed=11))
    assert direct_alpha(f.times, f.amounts, f.index) == pytest.approx(alpha, abs=1e-12)


def test_beta_above_one_shows_up_as_alpha_when_the_market_rises():
    rising = gbm_market(15.0, mu=0.12, sigma=0.05, seed=2)
    f = simulate_fund(rising, FundSpec(alpha=0.0, beta=1.5, seed=3))
    assert direct_alpha(f.times, f.amounts, f.index) > 0.02
    assert ks_pme(f.amounts, f.index) > 1.1


def test_long_nickels_breaks_when_a_fund_outruns_the_index():
    f = simulate_fund(gbm_market(15.0, seed=3), FundSpec(alpha=0.05, seed=7))
    ln = long_nickels(f.times, f.amounts, f.index)
    assert ln.negative and np.isnan(ln.index_irr) and len(ln.roots) != 1
    plus, scale = pme_plus(f.times, f.amounts, f.index)
    assert np.isfinite(plus) and 0 < scale < 1  # PME+ shrinks distributions instead


def test_pme_plus_account_ends_at_the_nav_and_mpme_needs_navs():
    f = simulate_fund(gbm_market(15.0, seed=8), FundSpec(alpha=0.03, idio=0.2, seed=8))
    t, a, nav, idx, navs = f.until(8.0)
    _, scale = pme_plus(t, a, idx, nav)
    c, d = np.where(a < 0, -a, 0.0), np.where(a > 0, a, 0.0)
    assert np.sum((c - scale * d) * idx[-1] / idx) == pytest.approx(nav, rel=1e-12)
    assert np.isfinite(mpme(t, a, idx, navs))
    assert report(t, a, idx, nav).mpme_irr is None


@settings(max_examples=60, deadline=None)
@given(st.floats(-0.08, 0.08), st.floats(0.5, 1.8), st.integers(0, 10_000), st.floats(0.5, 50.0))
def test_kaplan_schoar_and_direct_alpha_agree_in_sign_and_are_scale_free(alpha, beta, seed, scale):
    f = simulate_fund(gbm_market(15.0, seed=seed), FundSpec(alpha=alpha, beta=beta, idio=0.3, seed=seed))
    ks = ks_pme(f.amounts, f.index)
    da = direct_alpha(f.times, f.amounts, f.index)
    assert (ks > 1) == (da > 0) or abs(da) < 1e-12
    assert ks_pme(scale * f.amounts, 3.0 * f.index) == pytest.approx(ks, rel=1e-12)
    assert direct_alpha(f.times, scale * f.amounts, 3.0 * f.index) == pytest.approx(da, abs=1e-10)


def test_excess_returns_are_reported_by_method():
    f = simulate_fund(gbm_market(15.0, seed=9), FundSpec(alpha=0.0, idio=0.2, seed=9))
    t, a, nav, idx, navs = f.until(10.0)
    r = report(t, a, idx, nav, navs)
    assert set(r.excess) == {"Long-Nickels", "PME+", "mPME"}
