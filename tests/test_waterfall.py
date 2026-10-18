"""The fee schedule and the waterfalls: hand-checked cases, identities, and properties over random funds."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pmlab.waterfall import (
    DealModel,
    Shape,
    Terms,
    check_conservation,
    flat_multiples,
    gross_to_net,
    run,
    schedule,
    single_deal_shape,
    standard_shape,
)

FREE = Terms(fee=0.0, post_fee=0.0)


def test_terms_are_validated_and_labelled():
    with pytest.raises(ValueError):
        Terms(waterfall="asian")
    with pytest.raises(ValueError):
        Terms(post_basis="nav")
    with pytest.raises(ValueError):
        Terms(carry=1.2)
    assert Terms().label == "2 and 20, 8% hurdle, full catch-up, european"
    assert "no catch-up" in Terms(catch_up=0.0).label and "no hurdle" in Terms(hurdle=0.0).label
    assert Terms(post_fee=0.015).label.startswith("2/1.5 and 20")


def test_a_single_deal_by_hand():
    # 100 in, 200 out after five years, no fees: hurdle 146.93, then a full catch-up, then 80/20
    shape = single_deal_shape(5.0)
    out = run(shape, [[2.0]], FREE)
    assert out.contributions.sum() == pytest.approx(100.0)
    assert out.carry.sum() == pytest.approx(20.0)  # 20% of the 100 profit
    assert out.lp.sum() == pytest.approx(180.0)
    hurdle = 100 * 1.08**5
    below = run(shape, [[hurdle / 100 - 0.01]], FREE)
    assert below.carry.sum() == pytest.approx(0.0)
    # in the catch-up tier every extra pound goes to the GP
    mid = run(shape, [[1.50]], FREE)
    assert mid.carry.sum() == pytest.approx(150 - hurdle)
    assert mid.lp.sum() == pytest.approx(hurdle)


def test_no_catch_up_pays_carry_only_above_the_hurdle():
    out = run(single_deal_shape(5.0), [[2.0]], Terms(fee=0.0, post_fee=0.0, catch_up=0.0))
    assert out.carry.sum() == pytest.approx(0.2 * (200 - 100 * 1.08**5))


def test_partial_catch_up_splits_the_tier():
    terms = Terms(fee=0.0, post_fee=0.0, catch_up=0.8)
    h = 100 * 1.08**5
    v_star = h + 0.2 * (h - 100) / (0.8 - 0.2)
    out = run(single_deal_shape(5.0), [[(h + 5) / 100]], terms)
    assert out.carry.sum() == pytest.approx(0.8 * 5)
    top = run(single_deal_shape(5.0), [[3.0]], terms)
    assert top.carry.sum() == pytest.approx(0.2 * 200)  # past the catch-up, 20% of all profit
    assert v_star < 300


def test_fees_reduce_what_is_invested_and_calls_add_up_to_the_commitment():
    shape = standard_shape()
    s = schedule(shape, Terms())
    assert s.costs.sum() + s.fees.sum() == pytest.approx(100.0)
    assert 0.80 < s.scale < 0.90
    life = schedule(shape, Terms(post_basis="committed"))
    assert life.fees.sum() > s.fees.sum() and life.scale < s.scale
    assert schedule(shape, FREE).scale == pytest.approx(1.0)
    step = schedule(shape, Terms(post_fee=0.01))
    assert step.fees.sum() < s.fees.sum()
    with pytest.raises(ValueError):
        schedule(shape, Terms(fee=0.5, post_basis="committed"))


def test_fees_are_quarterly_in_advance_and_stop_with_the_fund():
    shape = standard_shape()
    s = schedule(shape, Terms())
    k = np.flatnonzero(s.fees)
    assert (np.diff(k) == 3).all() and k[0] == 0
    assert s.times[k[-1]] < shape.end
    assert s.fees[0] == pytest.approx(0.5)  # 2% of 100 a year, a quarter in advance


def test_zero_fees_and_carry_leave_gross_equal_to_net():
    shape = standard_shape()
    out = run(shape, flat_multiples(shape, 0.12), Terms(fee=0.0, post_fee=0.0, carry=0.0))
    gi, ni = out.irrs()
    assert gi[0] == pytest.approx(0.12, abs=1e-6) and ni[0] == pytest.approx(gi[0], abs=1e-9)


def test_gross_to_net_is_monotone_and_below_the_diagonal():
    t = gross_to_net(standard_shape(), Terms(), np.linspace(0.0, 0.3, 7))
    assert (np.diff(t["net_irr"]) > 0).all()
    assert (t["net_irr"] < t["gross_irr"]).all()
    assert (t["fees"] == t["fees"].iloc[0]).all()
    assert np.isnan(t["gp_share"].iloc[0])  # no profit, no share


def test_american_and_european_agree_when_every_deal_is_the_same():
    shape = standard_shape()
    m = flat_multiples(shape, 0.2)
    eu = run(shape, m, Terms())
    am = run(shape, m, Terms(waterfall="american"))
    assert eu.carry_kept[0] == pytest.approx(am.carry_kept[0], rel=1e-9)
    # but the American pays earlier
    assert np.argmax(np.cumsum(am.carry[0]) > 0) <= np.argmax(np.cumsum(eu.carry[0]) > 0)


def test_the_american_waterfall_overpays_and_the_clawback_corrects():
    shape = standard_shape()
    years = shape.exits - shape.entries
    m = np.array([(1 + np.where(np.arange(shape.deals) < 7, 0.30, -0.08)) ** years])
    eu = run(shape, m, Terms())
    am = run(shape, m, Terms(waterfall="american"))
    none = run(shape, m, Terms(waterfall="american", clawback=False))
    half = run(shape, m, Terms(waterfall="american", clawback_recovery=0.5))
    assert am.carry.sum() > eu.carry.sum()
    assert am.clawback[0] > 0 and none.clawback[0] == 0
    assert am.carry_kept[0] == pytest.approx(eu.carry_kept[0], rel=1e-6)
    assert eu.carry_kept[0] < half.carry_kept[0] < none.carry_kept[0]


def test_european_never_owes_a_clawback_on_simulated_funds():
    shape = standard_shape()
    m = DealModel(mu=0.1, sigma=0.5, seed=3).draw(shape, 3000)
    eu = run(shape, m, Terms())
    assert eu.clawback.max() < 1e-9


def test_deal_model_moments():
    shape = standard_shape()
    m = DealModel(mu=0.08, sigma=0.4, rho=0.0, seed=4, common=False).draw(shape, 200000)
    t = shape.exits - shape.entries
    np.testing.assert_allclose(m.mean(axis=0), np.exp(0.08 * t), rtol=0.03)
    rn = DealModel().risk_neutral(0.03)
    assert rn.mu == 0.03 and rn.sigma == DealModel().sigma


def test_correlation_between_deals():
    shape = Shape(np.zeros(2), np.full(2, 5.0), np.full(2, 0.5), 0.0)
    m = DealModel(mu=0.0, sigma=0.3, rho=0.6, seed=5).draw(shape, 100000)
    assert np.corrcoef(np.log(m).T)[0, 1] == pytest.approx(0.6, abs=0.01)


def test_wrong_number_of_deals_is_rejected():
    with pytest.raises(ValueError):
        run(standard_shape(), np.ones((1, 3)), Terms())


@settings(max_examples=40, deadline=None)
@given(
    fee=st.floats(0.0, 0.025),
    carry=st.floats(0.0, 0.3),
    hurdle=st.floats(0.0, 0.12),
    catch_up=st.sampled_from([0.0, 0.5, 0.8, 1.0]),
    waterfall=st.sampled_from(["european", "american"]),
    seed=st.integers(0, 10_000),
)
def test_every_pound_is_accounted_for(fee, carry, hurdle, catch_up, waterfall, seed):
    shape = standard_shape(deals=6)
    terms = Terms(fee=fee, carry=carry, hurdle=hurdle, catch_up=catch_up, waterfall=waterfall)
    m = DealModel(mu=0.1, sigma=0.6, seed=seed).draw(shape, 50)
    out = run(shape, m, terms)
    assert check_conservation(out) < 1e-9
    assert (out.carry >= -1e-12).all() and (out.lp >= -1e-12).all()
    kept = out.carry_kept
    profit = np.maximum(out.gross.sum(axis=1) - out.contributions.sum(), 0.0)
    assert (kept <= carry * profit + 1e-9).all()  # the clawback caps carry at its share of profit
