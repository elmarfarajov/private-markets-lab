"""Carry as an option: the closed form, its limits, and the Monte Carlo valuation."""

import numpy as np
import pytest

from pmlab.carry import (
    black_call,
    break_even_alpha,
    carry_closed_form,
    carry_payoff,
    single_deal_mc,
    strikes,
    value,
)
from pmlab.waterfall import DealModel, Terms, run, single_deal_shape, standard_shape

R = 0.04


def test_black_call_limits_and_parity():
    assert black_call(100, 100, 1, 0.0, 1.0) == 0.0
    assert black_call(120, 100, 1, 0.0, 0.9) == pytest.approx(18.0)
    assert black_call(100, 0.0, 1, 0.2, 0.95) == pytest.approx(95.0)
    c = black_call(100, 90, 2, 0.3, 0.9)
    p_plus_fwd = c - 0.9 * (100 - 90)
    assert p_plus_fwd > 0  # the put is worth something


def test_strikes():
    h, v = strikes(100, 5, Terms())
    assert h == pytest.approx(100 * 1.08**5)
    assert v == pytest.approx(h + 0.2 * (h - 100) / 0.8)
    assert strikes(100, 5, Terms(catch_up=0.0))[1] is None


def test_payoff_matches_the_waterfall_engine():
    v = np.linspace(50, 400, 36)
    for terms in (
        Terms(fee=0.0, post_fee=0.0),
        Terms(fee=0.0, post_fee=0.0, catch_up=0.8),
        Terms(fee=0.0, post_fee=0.0, catch_up=0.0),
    ):
        out = run(single_deal_shape(5.0), (v / 100)[:, None], terms)
        np.testing.assert_allclose(out.carry.sum(axis=1), carry_payoff(v, 100, 5.0, terms), atol=1e-9)


def test_closed_form_limits():
    t = Terms()
    assert carry_closed_form(100, 5, R, 1e-6, t) == pytest.approx(0.0, abs=1e-9)  # out of the money with no volatility
    assert carry_closed_form(100, 5, R, 0.4, Terms(carry=0.0)) == 0.0
    # without a hurdle and with tiny volatility the carry is 20% of the forward profit, discounted
    nh = carry_closed_form(100, 5, R, 1e-6, Terms(hurdle=0.0))
    assert nh == pytest.approx(0.2 * (100 * np.exp(R * 5) - 100) * np.exp(-R * 5), rel=1e-6)


def test_closed_form_rises_with_volatility_and_falls_with_the_hurdle():
    vols = [0.1, 0.2, 0.4, 0.6]
    vals = [carry_closed_form(100, 5, R, s, Terms()) for s in vols]
    assert all(b > a for a, b in zip(vals, vals[1:], strict=False))
    hurdles = [0.0, 0.04, 0.08, 0.12]
    hv = [carry_closed_form(100, 5, R, 0.4, Terms(hurdle=h, catch_up=0.0)) for h in hurdles]
    assert all(b < a for a, b in zip(hv, hv[1:], strict=False))


def test_full_catch_up_beats_no_catch_up():
    assert (
        carry_closed_form(100, 5, R, 0.4, Terms())
        > carry_closed_form(100, 5, R, 0.4, Terms(catch_up=0.8))
        > carry_closed_form(100, 5, R, 0.4, Terms(catch_up=0.0))
    )


@pytest.mark.parametrize("terms", [Terms(), Terms(catch_up=0.8), Terms(catch_up=0.0), Terms(hurdle=0.0)], ids=lambda t: t.label)
def test_monte_carlo_agrees_with_the_closed_form(terms):
    mc, se = single_deal_mc(5.0, R, 0.4, terms, funds=60000, seed=9)
    assert abs(mc - carry_closed_form(100, 5.0, R, 0.4, terms)) < 4 * se


def test_valuation_identity_and_fixed_share():
    v = value(standard_shape(), Terms(), DealModel(seed=12), R, funds=20000)
    assert abs(v.lp + v.fees + v.carry) < 4 * v.lp_se
    assert 0.5 < v.fixed_share < 1.0 and v.gp == pytest.approx(v.fees + v.carry)
    assert v.clawback_probability == 0.0
    am = value(standard_shape(), Terms(waterfall="american", clawback=False), DealModel(seed=12), R, funds=20000)
    assert am.carry > v.carry  # a portfolio of options is worth more


def test_alpha_raises_the_lp_stake_and_break_even_is_positive():
    shape = standard_shape()
    low = value(shape, Terms(), DealModel(seed=13), R, 5000, alpha=0.0).lp
    high = value(shape, Terms(), DealModel(seed=13), R, 5000, alpha=0.08).lp
    assert high > 0 > low
    be = break_even_alpha(shape, Terms(), DealModel(seed=13), R, 5000)
    assert 0.02 < be < 0.07
    assert break_even_alpha(shape, Terms(fee=0.0, post_fee=0.0, carry=0.0), DealModel(seed=13), R, 5000) == pytest.approx(
        0.0, abs=5e-3
    )
