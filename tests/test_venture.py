"""Venture securities: the exit waterfall, conversion, the option-pricing method and the backsolve."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from scipy.stats import norm

from pmlab import venture as V


def _two(**pref: object) -> V.CapTable:
    """Common 80m shares and one preferred class of 20m shares at $5 ($100m invested)."""
    return V.CapTable((V.Security("Common", 80.0), V.Security("Pref", 20.0, 5.0, seniority=1, **pref)))  # type: ignore[arg-type]


def _call(v0: float, k: float, sigma: float, years: float, r: float) -> float:
    f, s = v0 * np.exp(r * years), sigma * np.sqrt(years)
    d1 = (np.log(f / k) + 0.5 * s * s) / s
    return float(np.exp(-r * years) * (f * norm.cdf(d1) - k * norm.cdf(d1 - s)))


def test_security_terms():
    s = V.Security("D", 8.0, 30.0, multiple=1.5, dividend=0.08)
    assert s.preferred and s.invested == 240.0
    assert s.preference() == pytest.approx(360.0)
    assert s.preference(years=2.0) == pytest.approx(240.0 * (1.5 + 0.16))
    assert V.Security("Common", 10.0).preference(5.0) == 0.0


def test_the_example_cap_table():
    t = V.example()
    assert t.fully_diluted == pytest.approx(100.0)
    assert t.latest.name == "Series D" and t.post_money() == pytest.approx(3000.0)
    t2 = t.with_terms("Series D", multiple=2.0)
    assert t2.securities[-1].multiple == 2.0 and t.securities[-1].multiple == 1.0


def test_latest_round_ties_go_to_the_last_listed():
    t = V.CapTable((V.Security("C", 10.0), V.Security("A", 5.0, 2.0), V.Security("B", 5.0, 2.0)))
    assert t.latest.name == "B"


def test_a_non_participating_preferred_takes_the_lesser_then_converts():
    t = _two()
    for v, want in ((50.0, 50.0), (100.0, 100.0), (300.0, 100.0), (500.0, 100.0), (800.0, 160.0)):
        pay, conv = V.payoff(t, v)
        assert pay[1] == pytest.approx(want) and pay.sum() == pytest.approx(v)
    assert V.payoff(t, 400.0)[1] == [False, False] and V.payoff(t, 800.0)[1] == [False, True]


def test_participation_and_its_cap():
    full = _two(participating=True)
    pay, _ = V.payoff(full, 600.0)
    assert pay[1] == pytest.approx(100.0 + 0.2 * 500.0)  # preference plus a fifth of the rest
    capped = _two(participating=True, cap=1.5)
    pay, conv = V.payoff(capped, 400.0)
    assert pay[1] == pytest.approx(150.0) and not conv[1]  # the cap binds before converting pays
    pay, conv = V.payoff(capped, 1000.0)
    assert pay[1] == pytest.approx(200.0) and conv[1]  # converting gives a fifth of 1,000


def test_seniority_and_pari_passu():
    secs = (V.Security("Common", 50.0), V.Security("A", 25.0, 2.0, seniority=1), V.Security("B", 25.0, 4.0, seniority=2))
    pay, _ = V.payoff(V.CapTable(secs), 120.0)
    assert pay[2] == pytest.approx(100.0) and pay[1] == pytest.approx(20.0) and pay[0] == 0.0
    flat = V.CapTable(tuple(replace(s, seniority=1) if s.preferred else s for s in secs))
    pay, _ = V.payoff(flat, 120.0)
    assert pay[1] == pytest.approx(40.0) and pay[2] == pytest.approx(80.0)  # pro rata to 50 and 100 owed


def test_cumulative_dividend_raises_the_preference():
    t = replace(_two(dividend=0.1), years=3.0)
    pay, _ = V.payoff(t, 120.0)
    assert pay[1] == pytest.approx(120.0)  # 100 x (1 + 0.3) = 130 owed, only 120 there
    assert V.payoff(t, 1000.0)[0][1] == pytest.approx(200.0)


def test_conservation_and_equilibrium_on_random_companies():
    rng = np.random.default_rng(3)
    for _ in range(15):
        t = V.random_company(rng)
        for v in rng.uniform(0, 4 * t.post_money(), 5):
            pay, conv = V.payoff(t, float(v))
            assert pay.sum() == pytest.approx(v, rel=1e-10, abs=1e-9)
            assert (pay >= -1e-12).all()
            for i, s in enumerate(t.securities):
                if s.preferred:
                    flipped = list(conv)
                    flipped[i] = not flipped[i]
                    assert V._distribute(t, float(v), flipped)[i] <= pay[i] + 1e-9 * max(1.0, v)


def test_payoffs_are_monotone_in_the_exit_value():
    p = V.Payoffs.build(V.example(), points=600)
    assert (np.diff(p.pay, axis=0) >= -1e-9).all()
    assert len(p.breakpoints()) >= 4


def test_opm_matches_black_scholes_for_one_class():
    t = _two()
    v0, sig, yrs, r = 400.0, 0.8, 5.0, 0.03
    exact = v0 - _call(v0, 100.0, sig, yrs, r) + 0.2 * _call(v0, 500.0, sig, yrs, r)
    vals = V.Payoffs.build(t, points=3000).value(v0, sig, yrs, r)
    assert vals[1] == pytest.approx(exact, rel=1e-4)
    assert vals.sum() == pytest.approx(v0, rel=1e-9)  # class values add to the company


def test_the_backsolve_prices_the_latest_round():
    f = V.backsolve(V.example())
    assert f.per_share[-1] == pytest.approx(30.0, rel=1e-9)
    assert f.company < f.post_money and f.overvaluation == pytest.approx(f.post_money / f.company - 1)
    assert f.per_share[0] < f.per_share[2] < f.per_share[-1]  # common below early preferred below the latest
    assert 1500.0 < f.company < 2100.0


def test_more_protection_means_a_larger_overstatement():
    base = V.backsolve(V.example()).overvaluation
    rich = V.backsolve(V.example({"Series D": {"multiple": 2.0}})).overvaluation
    flat = V.backsolve(V.example({n: {"seniority": 1} for n in ("Series A", "Series B", "Series C", "Series D")})).overvaluation
    assert rich > base > flat > 0


def test_no_preference_means_no_overstatement():
    t = V.example({n: {"multiple": 0.0} for n in ("Series A", "Series B", "Series C", "Series D")})
    f = V.backsolve(t)
    assert f.overvaluation == pytest.approx(0.0, abs=1e-6)


def test_the_overstatement_falls_with_time_to_exit():
    t = V.example()
    short = V.backsolve(t, years=1.0).overvaluation
    long = V.backsolve(t, years=8.0).overvaluation
    assert short > long > 0


def test_the_overstatement_does_not_depend_on_the_latest_price():
    t = V.example()
    a = V.backsolve(t.with_terms("Series D", price=15.0)).overvaluation
    b = V.backsolve(t.with_terms("Series D", price=45.0)).overvaluation
    assert a == pytest.approx(b, abs=1e-3)


def test_monte_carlo_agrees_with_the_integral():
    t = V.example()
    f = V.backsolve(t)
    m, se = V.monte_carlo(t, f.company, 0.9, 4.0, 0.04, paths=4000, seed=1)
    assert np.all(np.abs(m - f.values) < 4.5 * se)


def test_the_random_sample():
    rows = V.overvaluation_sample(n=6, seed=2)
    assert len(rows) == 6
    for row in rows:
        assert row["overvaluation"] > 0 and 0 < row["common_discount"] < 1
        assert 3 <= row["rounds"] <= 6 and 0 < row["latest_share"] < 1
