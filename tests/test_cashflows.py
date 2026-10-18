"""IRRs - every root, published examples, an independent route - MIRR and the multiples."""

from __future__ import annotations

from datetime import date

import numpy as np
import numpy_financial as npf
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pmlab.cashflows import (
    CashFlows,
    fund_irr,
    interim,
    irr,
    irr_roots,
    mirr,
    multiples,
    norstrom,
    npv,
    periodic_roots,
    sign_changes,
)


def test_microsofts_xirr_example_to_excels_tolerance():
    dates = [date(2008, 1, 1), date(2008, 3, 1), date(2008, 10, 30), date(2009, 2, 15), date(2009, 4, 1)]
    value = fund_irr(CashFlows.from_dates(dates, [-10000, 2750, 4250, 3250, 2750]))
    assert value == pytest.approx(0.373362535, abs=1e-8)


def test_microsofts_mirr_examples():
    flows = [-120000, 39000, 30000, 21000, 37000, 46000]
    assert round(100 * mirr(np.arange(6), flows, 0.10, 0.12), 1) == 12.6
    assert round(100 * mirr(np.arange(4), flows[:4], 0.10, 0.12), 1) == -4.8
    assert mirr(np.arange(6), flows, 0.10, 0.12) == pytest.approx(npf.mirr(flows, 0.10, 0.12), abs=1e-14)


def test_the_pump_problem_has_two_irrs_and_irr_refuses_to_choose():
    assert irr_roots([0, 1, 2], [-1600, 10000, -10000]) == pytest.approx([0.25, 4.0], abs=1e-12)
    assert periodic_roots([-1600, 10000, -10000]) == pytest.approx([0.25, 4.0], abs=1e-12)
    with pytest.raises(ValueError, match="not unique: 2 roots"):
        irr([0, 1, 2], [-1600, 10000, -10000])


def test_a_stream_with_no_irr():
    assert irr_roots([0, 1, 2], [100, -200, 110]) == []
    with pytest.raises(ValueError, match="0 roots"):
        irr([0, 1, 2], [100, -200, 110])


def test_a_double_root_is_found_once():
    # (1 - v)^2 = 1 - 2v + v^2: the NPV touches zero at r = 0
    roots = irr_roots([0, 1, 2], [1.0, -2.0, 1.0], lo=-0.5, hi=1.0)
    assert roots == pytest.approx([0.0], abs=1e-6)


def test_norstrom_guarantees_one_positive_root_but_not_uniqueness():
    a = [-100, 230, -132]  # cumulative -100, 130, -2: two sign changes, Norstrom fails; roots 10% and 20%
    assert not norstrom(a)
    assert irr_roots([0, 1, 2], a) == pytest.approx([0.1, 0.2], abs=1e-12)
    rng = np.random.default_rng(0)
    for _ in range(300):
        flows = np.round(rng.normal(0, 100, int(rng.integers(3, 10))), 2)
        if norstrom(flows):
            assert sum(r > 0 for r in irr_roots(np.arange(flows.size), flows)) == 1


@settings(max_examples=150, deadline=None)
@given(
    st.lists(st.floats(0.0, 80.0), min_size=2, max_size=12),
    st.floats(30.0, 200.0),
    st.floats(0.1, 2.0),
)
def test_conventional_streams_one_root_matching_numpy_financial(inflows, outlay, spacing):
    a = np.array([-outlay, *inflows])
    times = np.arange(a.size) * spacing
    if np.sum(inflows) == 0 or float(npv(-0.99, times, a)[0]) <= 0 or float(npv(100.0, times, a)[0]) >= 0:
        return  # an IRR below -99% or above 10,000% a year lies outside the scanned range (documented)
    roots = irr_roots(np.arange(a.size) * spacing, a)
    assert len(roots) == 1
    assert float(npv(roots[0], np.arange(a.size) * spacing, a)[0]) == pytest.approx(0.0, abs=1e-8 * np.abs(a).sum())
    if spacing == 1.0:
        assert roots[0] == pytest.approx(float(npf.irr(a)), abs=1e-9)


@settings(max_examples=100, deadline=None)
@given(st.lists(st.floats(-100.0, 100.0), min_size=3, max_size=8), st.floats(0.5, 20.0), st.floats(0.0, 5.0))
def test_roots_are_invariant_to_scale_and_to_a_time_shift_and_bounded_by_descartes(flows, scale, shift):
    a = np.array(flows)
    if not np.any(a):
        with pytest.raises(ValueError, match="every amount is zero"):
            irr_roots(np.arange(a.size), a)
        return
    t = np.arange(a.size, dtype=float)
    base = irr_roots(t, a, lo=-0.9, hi=20.0)
    assert len(base) <= sign_changes(a)
    assert irr_roots(t + shift, scale * a, lo=-0.9, hi=20.0) == pytest.approx(base, abs=1e-8)


def test_multiples_and_interim_measures():
    cf = CashFlows(np.array([0.0, 1.0, 2.0, 3.0]), np.array([-60.0, -40.0, 30.0, 50.0]), nav=70.0)
    m = multiples(cf)
    assert (m.paid_in, m.distributed, m.dpi, m.rvpi, m.tvpi) == pytest.approx((100.0, 80.0, 0.8, 0.7, 1.5))
    path = interim(cf.times, cf.amounts, np.array([60.0, 105.0, 95.0, 70.0]))
    assert path["tvpi"][-1] == pytest.approx(1.5)
    assert path["dpi"][1] == 0.0 and path["paid_in"][1] == 100.0
    assert np.isnan(path["irr"][0])  # too early for an annual rate
    assert path["irr"][-1] == pytest.approx(fund_irr(cf), abs=1e-10)


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError):
        CashFlows(np.array([0.0, 1.0]), np.array([1.0]))
    with pytest.raises(ValueError):
        CashFlows(np.array([1.0, 0.0]), np.array([-1.0, 2.0]))
    with pytest.raises(ValueError, match="no capital"):
        multiples(CashFlows(np.array([0.0]), np.array([5.0])))
