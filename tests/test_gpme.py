"""SDF-based performance: the SDF, fair alpha, GPME and cash-flow betas."""

from __future__ import annotations

import numpy as np
import pytest

from pmlab import gpme as G
from pmlab.pme import ks_pme
from pmlab.synthetic import FundSpec, gbm_market, simulate_fund

MU, SIG, R = 0.08, 0.16, 0.02


def test_lognormal_sdf_formula():
    sd = G.SDF.lognormal(MU, SIG, R)
    assert sd.b == pytest.approx((MU - R) / SIG**2)
    # pricing the market: -a + (1 - b) m + (1 - b)^2 sigma^2 / 2 = 0
    m = MU - 0.5 * SIG**2
    assert -sd.a + (1 - sd.b) * m + 0.5 * (1 - sd.b) ** 2 * SIG**2 == pytest.approx(0.0, abs=1e-14)


def test_kaplan_schoar_is_risk_aversion_one():
    ks = G.SDF.kaplan_schoar()
    t, i = np.array([0.0, 1.0, 2.0]), np.array([100.0, 120.0, 90.0])
    assert ks.discount(t, i) == pytest.approx([1.0, 100 / 120, 100 / 90])


def test_fair_alpha_is_zero_at_beta_one_and_negative_above():
    sd = G.SDF.lognormal(MU, SIG, R)
    assert G.fair_alpha(1.0, sd, MU, SIG) == pytest.approx(0.0, abs=1e-14)
    assert G.fair_alpha(2.0, sd, MU, SIG) == pytest.approx(-(R + SIG**2))  # (1 - beta)(r + beta sigma^2 / 2)
    assert G.fair_alpha(0.0, sd, MU, SIG) == pytest.approx(R)  # a bond earns the bond rate
    assert G.fair_alpha(2.0, G.SDF.kaplan_schoar(), MU, SIG) < G.fair_alpha(2.0, sd, MU, SIG)


def test_fit_recovers_the_sdf_on_a_long_lognormal_sample():
    rng = np.random.default_rng(3)
    x = (MU - 0.5 * SIG**2) / 12 + SIG / np.sqrt(12) * rng.standard_normal(120_000)
    fit = G.SDF.fit(np.r_[1.0, np.exp(np.cumsum(x))], 1 / 12, R)
    assert fit.b == pytest.approx((MU - R) / SIG**2, abs=0.4)


def test_gpme_and_ratio_on_one_fund():
    f = simulate_fund(gbm_market(13, seed=4), FundSpec(beta=1.3, idio=0.2, seed=4))
    ks = G.SDF.kaplan_schoar()
    assert G.pme_ratio(f.times, f.amounts, f.index, ks) == pytest.approx(ks_pme(f.amounts, f.index), rel=1e-12)
    called = -f.amounts[f.amounts < 0].sum()
    assert G.gpme(f.times, f.amounts, f.index, ks) == pytest.approx(G.npv(f.times, f.amounts, f.index, ks) / called)


def test_nav_counts_as_a_final_distribution():
    t, a, i = np.array([0.0, 1.0]), np.array([-100.0, 0.0]), np.array([100.0, 110.0])
    ks = G.SDF.kaplan_schoar()
    assert G.npv(t, a, i, ks, nav=110.0) == pytest.approx(0.0)
    assert G.gpme(t, a, i, ks, nav=110.0) == pytest.approx(0.0)


def test_gpme_is_unbiased_for_fair_funds_and_ks_rewards_leverage():
    sd = G.SDF.lognormal(MU, SIG, R)
    g, k = [], []
    for s in range(150):
        f = simulate_fund(
            gbm_market(13, MU, SIG, seed=200 + s), FundSpec(beta=2.0, alpha=G.fair_alpha(2.0, sd, MU, SIG), idio=0.2, seed=s)
        )
        g.append(G.gpme(f.times, f.amounts, f.index, sd))
        k.append(G.gpme(f.times, f.amounts, f.index, G.SDF.kaplan_schoar()))
    g, k = np.array(g), np.array(k)
    assert abs(g.mean()) < 3 * g.std() / np.sqrt(g.size)
    assert k.mean() > 0.08


def test_cashflow_beta_recovers_beta():
    funds = []
    for s in range(30):
        f = simulate_fund(gbm_market(13, seed=500 + s), FundSpec(beta=0.8, idio=0.0, seed=s))
        funds.append((f.times, f.amounts, f.index))
    est = G.cashflow_beta(funds, R)
    assert est.beta == pytest.approx(0.8, abs=0.05) and est.funds == 30 and est.loss >= 0
