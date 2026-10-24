"""Takahashi-Alexander, the stochastic fund model, calibration and secondary pricing."""

from dataclasses import replace

import numpy as np
import pytest

from pmlab import fundmodel as F
from pmlab import secondary as S


def test_ta_by_hand_first_years():
    p = F.takahashi_alexander()
    f = p.frame()
    assert f.loc[1, "calls"] == pytest.approx(25.0)
    assert f.loc[2, "calls"] == pytest.approx(0.333 * 75)
    assert f.loc[1, "distributions"] == 0.0  # nothing to distribute yet
    rd2 = (2 / 12) ** 2.5
    assert f.loc[2, "distributions"] == pytest.approx(rd2 * 25 * 1.13)
    assert f.loc[12, "nav"] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("growth,bow", [(0.05, 1.0), (0.13, 2.5), (0.2, 5.0)])
def test_ta_irr_equals_growth(growth, bow):
    assert F.takahashi_alexander(F.TAParams(growth=growth, bow=bow)).irr() == pytest.approx(growth, abs=1e-10)


def test_ta_yield_floor_and_rates():
    p = F.TAParams(yield_=0.1)
    assert p.rate_of_distribution(1) == pytest.approx(0.1)
    assert p.rate_of_call(9) == p.rc[-1]
    assert F.TAParams().rate_of_distribution(12) == 1.0


def test_higher_bow_raises_tvpi_not_irr():
    lo = F.takahashi_alexander(F.TAParams(bow=1.0))
    hi = F.takahashi_alexander(F.TAParams(bow=5.0))
    assert hi.tvpi() > lo.tvpi()
    assert hi.irr() == pytest.approx(lo.irr(), abs=1e-9)


def test_calibration_recovers_parameters():
    true = F.TAParams(rc=(0.2, 0.3, 0.6, 0.5, 1.0), growth=0.1, bow=2.0)
    f = F.takahashi_alexander(true).frame()
    fit = F.calibrate(f["cum_calls"], f["cum_distributions"], f["nav"], rc_years=4)
    assert fit.success and fit.rmse < 1e-6
    assert fit.params.growth == pytest.approx(0.1, abs=1e-5)
    assert fit.params.bow == pytest.approx(2.0, abs=1e-4)


def test_annual_curves():
    t = np.array([0.5, 1.0, 1.5, 2.0])
    a = np.array([-10.0, -5.0, 3.0, 4.0])
    nav = np.array([10.0, 16.0, 15.0, 13.0])
    cc, cd, nv = F.annual_curves(t, a, nav, 3)
    assert cc.tolist() == [15.0, 15.0, 15.0]
    assert cd.tolist() == [0.0, 7.0, 7.0]
    assert nv.tolist() == [16.0, 13.0, 13.0]


def test_simulation_conserves_and_ends_empty():
    paths = F.simulate(F.StochasticSpec(), 500, seed=1)
    np.testing.assert_allclose(paths.calls.sum(axis=1), 100.0)
    assert np.allclose(paths.value[:, -1], 0.0)
    assert (paths.calls >= 0).all() and (paths.distributions >= 0).all()
    assert paths.times[0] == pytest.approx(0.25) and paths.times.size == 48
    assert paths.annual_calls().shape == (500, 12)


def test_no_noise_and_no_vol_reproduces_expected_path():
    spec = F.StochasticSpec(call_noise=0.0, dist_noise=0.0, market_vol=0.0, idio_vol=0.0, smoothing=1.0)
    paths = F.simulate(spec, 3, seed=2)
    t, c, d = F.expected_path(spec, 0.0, 100.0, 0.0)
    np.testing.assert_allclose(paths.calls[0], c, atol=1e-10)
    np.testing.assert_allclose(paths.distributions[0], d, atol=1e-10)
    np.testing.assert_allclose(paths.reported, paths.value)  # no smoothing


def test_smoothing_lowers_reported_volatility():
    paths = F.simulate(F.StochasticSpec(smoothing=0.3), 300, seed=3)
    k = slice(8, 24)
    true_r = np.diff(np.log(paths.value[:, k] + 1), axis=1).std()
    rep_r = np.diff(np.log(paths.reported[:, k] + 1), axis=1).std()
    assert rep_r < true_r


def test_shared_market_and_vintage_split():
    spec = F.StochasticSpec(idio_vol=0.05)
    d = F.vintage_study(spec, vintages=6, funds=40, seed=1)
    split = F.variance_split(d)
    assert split["between_share"] > 0.5  # little own risk: vintage dominates
    assert split["between"] + split["within"] == pytest.approx(split["total"])


def test_start_from_state():
    paths = F.simulate(F.StochasticSpec(), 200, seed=4, start=4.0, value=80.0, reported=90.0, uncalled=12.0)
    assert paths.times.size == 32
    np.testing.assert_allclose(paths.calls.sum(axis=1), 12.0)


def test_discount_zero_at_mu_and_rises_with_required():
    spec = F.StochasticSpec()
    st = S.expected_state(spec, 3.0)
    assert S.discount(spec, st, spec.mu) == pytest.approx(0.0, abs=1e-10)
    d = [S.discount(spec, st, r) for r in (0.12, 0.15, 0.2)]
    assert d[0] < d[1] < d[2]
    assert S.discount(spec, st, 0.08) < 0  # a buyer that asks less pays a premium


def test_young_funds_have_bigger_discounts():
    spec = F.StochasticSpec()
    ds = [S.discount(spec, S.expected_state(spec, a), 0.15) for a in (1, 3, 5, 9)]
    assert ds == sorted(ds, reverse=True)


def test_decomposition():
    spec = F.StochasticSpec()
    st = S.expected_state(spec, 1.5)
    d = S.decompose(spec, st, 0.15)
    assert d.unfunded > 0 and d.assets > 0 and d.staleness == pytest.approx(0.0, abs=1e-12)
    stale = replace(st, reported=st.value * 1.3)
    ds = S.decompose(spec, stale, 0.15)
    assert ds.staleness > 0 and ds.total > d.total


def test_crash_discount_narrows():
    c = S.crash(F.StochasticSpec(), 5.0, 0.3, 0.14, 8)
    assert c["discount_to_reported"].iloc[0] > c["discount_to_true"].iloc[0]
    assert c["discount_to_reported"].iloc[-1] < c["discount_to_reported"].iloc[0]
    assert c["reported"].iloc[0] > c["true"].iloc[0]


def test_buyer_irr_rises_with_discount():
    spec = F.StochasticSpec()
    st = S.expected_state(spec, 4.0)
    cheap = np.nanmedian(S.buyer_irrs(spec, st, 0.7, 300, 1))
    dear = np.nanmedian(S.buyer_irrs(spec, st, 1.0, 300, 1))
    assert cheap > dear


def test_monte_carlo_matches_shortcut():
    spec = F.StochasticSpec()
    st = S.expected_state(spec, 3.0)
    m, se = S.monte_carlo_value(spec, st, 0.14, 6000, seed=5)
    assert abs(m - S.value(spec, st, 0.14)) < 4 * se


def test_discount_grid_shape():
    g = S.discount_grid(F.StochasticSpec(), [1, 5], [0.11, 0.15])
    assert len(g) == 4 and set(g.columns) == {"age", "required", "discount", "unfunded_share"}
