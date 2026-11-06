"""Nowcasting: the appraisal rule, the Kalman filter and smoother, estimation and the shortcuts."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from pmlab import fundmodel as fm
from pmlab import nowcast as N

SPEC = fm.StochasticSpec()
TRUE = N.Params.from_spec(SPEC)


@pytest.fixture(scope="module")
def sim():
    p = fm.simulate(SPEC, 400, seed=5)
    d = N.Data.from_paths(p, seed=6)
    return p, d, p.value[:, : d.shape[1]]


def test_true_parameters_match_the_simulator():
    assert TRUE.a == SPEC.smoothing and TRUE.beta == SPEC.beta
    assert TRUE.sigma == pytest.approx(SPEC.idio_vol / 2)
    assert TRUE.c == pytest.approx((SPEC.mu - 0.5 * SPEC.total_vol**2) / 4 + SPEC.beta * SPEC.market_vol**2 / 8)


def test_appraisal_without_noise_follows_the_partial_adjustment_rule():
    v = np.array([[10.0, 20.0, 15.0]])
    c = np.array([[10.0, 5.0, 0.0]])
    d = np.array([[0.0, 0.0, 2.0]])
    r = N.appraise(v, c, d, a=0.5, noise=0.0)
    assert r[0, 0] == pytest.approx(0.5 * 10 + 0.5 * 10)
    assert r[0, 1] == pytest.approx(0.5 * 20 + 0.5 * (r[0, 0] + 5))
    assert r[0, 2] == pytest.approx(0.5 * 15 + 0.5 * (r[0, 1] - 2))
    assert np.array_equal(N.appraise(v, c, d, 1.0, 0.0), v)


def test_data_from_paths_drops_the_wind_up_quarter(sim):
    p, d, _ = sim
    assert d.shape == (400, p.calls.shape[1] - 1)
    assert np.allclose(d.log_market, np.log(p.market[:, :-1]))


def test_filter_beats_reported_nav_and_smoother_beats_filter(sim):
    _, d, v = sim
    fl = N.kalman(d, TRUE)
    ms, vs = N.smooth(fl)
    rep, flt, smo = (N.rmse(N.errors(x, v)) for x in (d.reported, fl.mean, ms))
    assert smo < flt < rep
    assert (vs <= fl.var + 1e-9).all()
    assert np.isfinite(fl.loglik)


def test_state_is_known_before_the_first_report(sim):
    _, d, _ = sim
    fl = N.kalman(d, TRUE)
    assert np.allclose(fl.pred_var[:, 0], 0.0)
    assert np.allclose(fl.pred_mean[:, 0], d.calls[:, 0] - d.distributions[:, 0])


def test_likelihood_peaks_near_the_true_smoothing(sim):
    _, d, _ = sim
    ll = {a: N.kalman(d, replace(TRUE, a=a)).loglik for a in (0.2, 0.4, 0.7)}
    assert ll[0.4] > ll[0.2] and ll[0.4] > ll[0.7]


def test_estimate_recovers_parameters():
    p = fm.simulate(SPEC, 150, seed=7, market_shocks=np.random.default_rng(8).standard_normal(48))
    e = N.estimate(N.Data.from_paths(p, seed=9))
    assert e.success
    assert e.params.a == pytest.approx(0.4, abs=0.06) and e.params.beta == pytest.approx(1.2, abs=0.2)


def test_naive_beta_is_biased_down(sim):
    _, d, _ = sim
    r = N.reported_returns(d)
    assert np.isnan(r[:, 0]).all()
    b0 = N.naive_beta(d)
    assert 0.3 < b0 < 0.7
    assert N.naive_beta(d, lags=4) > b0


def test_unsmoothed_appraisals_give_the_true_beta():
    p = fm.simulate(SPEC, 400, seed=10)
    d = N.Data.from_paths(p, a=1.0, noise=0.0, seed=11)
    assert N.naive_beta(d) == pytest.approx(1.2, abs=0.1)


def test_market_rollforward(sim):
    _, d, _ = sim
    rf = N.market_rollforward(d, 1.0)
    assert rf[:, 0] == pytest.approx(d.calls[:, 0] - d.distributions[:, 0])
    t = 10
    assert rf[3, t] == pytest.approx(d.reported[3, t - 1] * np.exp(d.log_market[3, t]) + d.calls[3, t] - d.distributions[3, t])


def test_errors_floor_and_rmse():
    est = np.array([[1.0, 11.0, 2.0]])
    tru = np.array([[1.0, 10.0, 1.0]])
    e = N.errors(est, tru, skip=0, floor=5.0)
    assert np.isnan(e[0, 0]) and e[0, 1] == pytest.approx(0.1) and np.isnan(e[0, 2])
    assert N.rmse(e) == pytest.approx(0.1)
    assert N.rmse(np.array([[0.1, 0.3]]), axis=0).shape == (2,)
