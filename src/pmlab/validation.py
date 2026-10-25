"""Validation suite: every measure held to a published value, an independent method, or an identity that must hold.

``pmlab validate`` runs it and ``pmlab validate --out docs/VALIDATION.md`` records it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import fundmodel as fm
from . import secondary as sec
from . import venture as vc
from .carry import carry_closed_form, carry_payoff, single_deal_mc, value
from .cashflows import CashFlows, fund_irr, irr, irr_roots, mirr, multiples, norstrom, periodic_roots, sign_changes
from .pme import direct_alpha, ks_pme, long_nickels, mpme, pme_plus, report
from .synthetic import FundSpec, gbm_market, simulate_fund
from .waterfall import DealModel, Terms, check_conservation, flat_multiples, run, standard_shape


@dataclass
class Check:
    area: str
    check: str
    reference: str
    result: str
    error: str
    passed: bool
    seconds: float


def run_validation(fast: bool = False) -> pd.DataFrame:
    checks: list[Check] = []

    def add(area: str, name: str, fn: Callable[[], tuple[str, str, str, bool]]) -> None:
        start = time.perf_counter()
        reference, result, error, passed = fn()
        checks.append(Check(area, name, reference, result, error, passed, time.perf_counter() - start))

    def xirr_microsoft() -> tuple[str, str, str, bool]:
        # Microsoft's XIRR documentation example; Excel iterates to 1e-8, so its printed ninth digit is not exact
        dates = [date(2008, 1, 1), date(2008, 3, 1), date(2008, 10, 30), date(2009, 2, 15), date(2009, 4, 1)]
        value = fund_irr(CashFlows.from_dates(dates, [-10000, 2750, 4250, 3250, 2750]))
        gap = abs(value - 0.373362535)
        return "0.373362535 (Excel XIRR, documented)", f"{value:.10f}", f"{gap:.1e}", gap < 1e-8

    def mirr_microsoft() -> tuple[str, str, str, bool]:
        flows = [-120000, 39000, 30000, 21000, 37000, 46000]
        five = mirr(np.arange(6), flows, 0.10, 0.12)
        three = mirr(np.arange(4), flows[:4], 0.10, 0.12)
        ok = round(100 * five, 1) == 12.6 and round(100 * three, 1) == -4.8
        return "12.6% and -4.8% (Excel MIRR, documented)", f"{100 * five:.3f}% and {100 * three:.3f}%", "to the printed digit", ok

    def lorie_savage() -> tuple[str, str, str, bool]:
        roots = irr_roots([0, 1, 2], [-1600, 10000, -10000])
        gap = max(abs(roots[0] - 0.25), abs(roots[1] - 4.0)) if len(roots) == 2 else np.inf
        return "25% and 400% (Lorie and Savage, 1955)", ", ".join(f"{100 * r:.6f}%" for r in roots), f"{gap:.1e}", gap < 1e-10

    def irr_vs_numpy_financial() -> tuple[str, str, str, bool]:
        import numpy_financial as npf

        rng = np.random.default_rng(1)
        worst, n = 0.0, 500 if fast else 2000
        for _ in range(n):
            # a conventional investment - one outflow, then inflows - has exactly one IRR by Descartes
            a = np.concatenate([[-rng.uniform(50, 150)], rng.uniform(0, 60, int(rng.integers(2, 15)))])
            worst = max(worst, abs(irr(np.arange(a.size), a) - float(npf.irr(a))))
        return "numpy-financial irr, conventional periodic streams", f"{n} random streams", f"{worst:.1e}", worst < 1e-9

    def norstrom_positive() -> tuple[str, str, str, bool]:
        rng = np.random.default_rng(5)
        tested = violations = with_negative = 0
        for _ in range(500 if fast else 2000):
            a = np.round(rng.normal(0, 100, int(rng.integers(3, 12))), 2)
            if not norstrom(a):
                continue
            tested += 1
            roots = irr_roots(np.arange(a.size), a, lo=-0.99, hi=50.0)
            violations += sum(r > 0 for r in roots) > 1
            with_negative += any(r < 0 for r in roots) and any(r > 0 for r in roots)
        return (
            "Norstrom (1972): at most one positive IRR",
            f"{tested} streams meeting the condition; {with_negative} also have a negative root",
            f"{violations} with two positive roots",
            violations == 0,
        )

    def all_roots() -> tuple[str, str, str, bool]:
        import mpmath as mp

        mp.mp.dps = 50
        rng = np.random.default_rng(2)
        worst, over, n, found = 0.0, 0, 200 if fast else 600, 0
        for _ in range(n):
            a = np.round(rng.normal(0, 100, int(rng.integers(3, 9))), 2)
            ours = irr_roots(np.arange(a.size), a, lo=-0.95, hi=20.0)
            coeffs = [mp.mpf(str(x)) for x in a[::-1]]  # highest power of v first
            exact = sorted(
                float(1 / r.real - 1)
                for r in mp.polyroots(coeffs, maxsteps=200, extraprec=200)
                if abs(r.imag) < 1e-30 and r.real > 0 and -0.95 < float(1 / r.real - 1) < 20.0
            )
            over += len(ours) > sign_changes(a)
            if len(ours) != len(exact):
                worst = np.inf
                continue
            found += len(ours)
            worst = max([worst, *(abs(x - y) for x, y in zip(ours, exact, strict=True))])
        return (
            "every root, from mpmath polynomial roots at 50 digits",
            f"{n} random streams, {found} roots; above Descartes' bound: {over}",
            f"{worst:.1e}",
            worst < 1e-9 and over == 0,
        )

    def periodic_route() -> tuple[str, str, str, bool]:
        rng = np.random.default_rng(3)
        worst = 0.0
        for _ in range(300):
            a = np.round(rng.normal(0, 100, int(rng.integers(3, 8))), 2)
            scan = irr_roots(np.arange(a.size), a, lo=-0.9, hi=10.0)
            poly = [r for r in periodic_roots(a) if -0.9 < r < 10.0]
            if len(scan) == len(poly):
                worst = max([worst, *(abs(x - y) for x, y in zip(scan, poly, strict=True))])
            else:
                worst = np.inf
        return "numpy polynomial roots in v = 1/(1 + r)", "300 random streams, every root", f"{worst:.1e}", worst < 1e-8

    def index_fund() -> tuple[str, str, str, bool]:
        worst = 0.0
        for seed in range(10):
            m = gbm_market(15.0, seed=seed)
            f = simulate_fund(m, FundSpec(alpha=0.0, seed=seed))
            for horizon in (6.0, float(f.times[-1])):
                t, a, nav, idx, navs = f.until(horizon)
                r = report(t, a, idx, nav, navs)
                assert r.mpme_irr is not None
                worst = max(
                    worst,
                    abs(r.ks_pme - 1),
                    abs(r.direct_alpha),
                    abs(r.ln_irr - r.fund_irr),
                    abs(r.pme_plus_irr - r.fund_irr),
                    abs(r.mpme_irr - r.fund_irr),
                )
        return (
            "a fund that is the index: PME 1, alpha 0, index IRRs = fund IRR",
            "10 funds, at year 6 (with NAV) and at the end; all five methods",
            f"{worst:.1e}",
            worst < 1e-10,
        )

    def single_deal() -> tuple[str, str, str, bool]:
        # one investment at 0 growing at r, an index growing at g, sold at T
        r, g, horizon = 0.15, 0.07, 6.0
        t = np.array([0.0, horizon])
        a = np.array([-1.0, (1 + r) ** horizon])
        idx = np.array([1.0, (1 + g) ** horizon])
        ks = ks_pme(a, idx)
        da = direct_alpha(t, a, idx)
        ln = long_nickels(t, a, idx)
        gaps = [abs(ks - ((1 + r) / (1 + g)) ** horizon), abs(da - np.log((1 + r) / (1 + g))), abs(ln.index_irr - g)]
        return (
            "closed forms: PME ((1+r)/(1+g))^T, alpha ln((1+r)/(1+g)), LN IRR g",
            "single deal, r = 15%, g = 7%, six years",
            f"{max(gaps):.1e}",
            max(gaps) < 1e-12,
        )

    def alpha_recovered() -> tuple[str, str, str, bool]:
        worst = 0.0
        for seed, alpha in enumerate((-0.04, 0.0, 0.03, 0.08)):
            f = simulate_fund(gbm_market(15.0, seed=10 + seed), FundSpec(alpha=alpha, beta=1.0, idio=0.0, seed=seed))
            worst = max(worst, abs(direct_alpha(f.times, f.amounts, f.index) - alpha))
        return "the alpha built into noise-free beta-one funds", "alphas -4%, 0, 3%, 8%", f"{worst:.1e}", worst < 1e-10

    def ks_and_alpha_agree() -> tuple[str, str, str, bool]:
        rng = np.random.default_rng(4)
        disagree = 0
        n = 100 if fast else 300
        for i in range(n):
            spec = FundSpec(alpha=float(rng.normal(0, 0.04)), beta=float(rng.uniform(0.6, 1.6)), idio=0.3, seed=i)
            f = simulate_fund(gbm_market(15.0, seed=500 + i), spec)
            ks = ks_pme(f.amounts, f.index)
            da = direct_alpha(f.times, f.amounts, f.index)
            disagree += (ks > 1) != (da > 0)
        return "KS-PME > 1 exactly when Direct Alpha > 0", f"{n} random funds", f"{disagree} disagreements", disagree == 0

    def pme_plus_scale() -> tuple[str, str, str, bool]:
        f = simulate_fund(gbm_market(15.0, seed=7), FundSpec(alpha=0.05, idio=0.2, seed=7))
        t, a, nav, idx, navs = f.until(8.0)
        _, scale = pme_plus(t, a, idx, nav)
        c, d = np.where(a < 0, -a, 0.0), np.where(a > 0, a, 0.0)
        account = float(np.sum((c - scale * d) * idx[-1] / idx))
        gap = abs(account - nav)
        return "PME+ index account ends at the fund's NAV", f"scale {scale:.4f}", f"{gap:.1e}", gap < 1e-9

    def multiples_identity() -> tuple[str, str, str, bool]:
        f = simulate_fund(gbm_market(15.0, seed=8), FundSpec(alpha=0.02, idio=0.25, fee=0.015, seed=8))
        t, a, nav, _, navs = f.until(7.0)
        m = multiples(CashFlows(t, a, nav))
        gap = abs(m.tvpi - m.dpi - m.rvpi) + abs(m.paid_in - float(-a[a < 0].sum()))
        mpme(t, a, f.index[: t.size], navs)  # computable mid-life
        return "TVPI = DPI + RVPI; PIC = calls", f"TVPI {m.tvpi:.4f} at year 7", f"{gap:.1e}", gap < 1e-12

    def waterfall_conservation() -> tuple[str, str, str, bool]:
        shape = standard_shape()
        m = DealModel(mu=0.10, sigma=0.5, rho=0.3, seed=21).draw(shape, 2000)
        gaps = []
        for t in (
            Terms(),
            Terms(waterfall="american"),
            Terms(waterfall="american", clawback_recovery=0.4),
            Terms(catch_up=0.8, hurdle=0.06),
        ):
            gaps.append(check_conservation(run(shape, m, t)))
        gap = max(gaps)
        return "LP + GP flows = the deals' flows, every fund", "2,000 funds x 4 sets of terms", f"{gap:.1e}", gap < 1e-9

    def carry_closed_form_vs_quadrature() -> tuple[str, str, str, bool]:
        from scipy import integrate

        worst = 0.0
        r, years = 0.04, 5.0
        for t in (Terms(), Terms(catch_up=0.8), Terms(catch_up=0.0), Terms(hurdle=0.0, carry=0.3)):
            for sigma in (0.2, 0.5):

                def f(z: float, sigma: float = sigma, t: Terms = t) -> float:
                    v = 100 * np.exp((r - 0.5 * sigma**2) * years + sigma * np.sqrt(years) * z)
                    return float(carry_payoff(v, 100, years, t)) * float(np.exp(-0.5 * z * z)) / float(np.sqrt(2 * np.pi))

                quad = integrate.quad(f, -12, 12, limit=400, points=[0.0])[0] * np.exp(-r * years)
                worst = max(worst, abs(quad - carry_closed_form(100, years, r, sigma, t)))
        return (
            "the payoff integrated against the lognormal density",
            "4 sets of terms x 2 volatilities",
            f"{worst:.1e}",
            worst < 1e-6,
        )

    def carry_engine_vs_formula() -> tuple[str, str, str, bool]:
        n = 50000 if fast else 200000
        zs = []
        for k, (t, sigma) in enumerate(
            ((Terms(), 0.3), (Terms(catch_up=0.8), 0.5), (Terms(catch_up=0.0), 0.4), (Terms(hurdle=0.0), 0.6))
        ):
            mc, se = single_deal_mc(5.0, 0.04, sigma, t, funds=n, seed=100 + k)
            zs.append((mc - carry_closed_form(100, 5.0, 0.04, sigma, t)) / se)
        worst = float(np.max(np.abs(zs)))
        return (
            "Black-Scholes call spread against Monte Carlo through the waterfall",
            f"4 cases, {n:,} paths each",
            f"max |z| {worst:.2f}",
            worst < 4.0,
        )

    def catch_up_identity() -> tuple[str, str, str, bool]:
        shape = standard_shape()
        worst = 0.0
        for g in (0.18, 0.25, 0.35):
            out = run(shape, flat_multiples(shape, g), Terms())
            profit = out.gross.sum() - out.contributions.sum()
            worst = max(worst, abs(float(out.carry.sum()) - 0.2 * profit))
        return "full catch-up: carry = 20% of profit above the catch-up", "gross IRR 18%, 25%, 35%", f"{worst:.1e}", worst < 1e-9

    def clawback_bounds() -> tuple[str, str, str, bool]:
        shape = standard_shape()
        m = DealModel(mu=0.08, sigma=0.6, rho=0.2, seed=22).draw(shape, 5000)
        am = run(shape, m, Terms(waterfall="american"))
        profit = np.maximum(am.gross_profit() - am.fees.sum(), 0.0)
        kept = am.carry_kept
        paid = am.carry.sum(axis=1)
        gap1 = float(np.max(kept - 0.2 * profit))  # never above 20% of net profit
        gap2 = float(np.max(np.abs(kept - np.minimum(paid, am.entitlement))))  # full recovery returns exactly the excess
        worst = max(gap1, gap2)
        return "kept carry = min(paid, entitlement) <= 20% of profit", "5,000 American funds", f"{worst:.1e}", worst < 1e-9

    def risk_neutral_identity() -> tuple[str, str, str, bool]:
        v = value(standard_shape(), Terms(), DealModel(sigma=0.4, rho=0.3, seed=23), 0.04, 20000 if fast else 60000)
        total = v.lp + v.fees + v.carry
        z = total / v.lp_se
        return (
            "zero alpha: LP value = -(fees + carry)",
            f"LP {v.lp:.2f}, fees {v.fees:.2f}, carry {v.carry:.2f}",
            f"z {z:.2f}",
            abs(z) < 4.0,
        )

    def ta_identity() -> tuple[str, str, str, bool]:
        worst = 0.0
        for g in (0.05, 0.13, 0.2):
            for b in (1.0, 2.5, 5.0):
                p_ = fm.takahashi_alexander(fm.TAParams(growth=g, bow=b))
                worst = max(worst, abs(p_.irr() - g), abs(p_.nav[-1]), abs(p_.calls.sum() - 100))
        return (
            "Takahashi-Alexander: IRR = G, NAV ends at 0, calls sum to commitment",
            "9 parameter sets",
            f"{worst:.1e}",
            worst < 1e-9,
        )

    def ta_recovery() -> tuple[str, str, str, bool]:
        true = fm.TAParams(rc=(0.3, 0.4, 0.5, 1.0), growth=0.09, bow=3.0)
        f = fm.takahashi_alexander(true).frame()
        fit = fm.calibrate(f["cum_calls"], f["cum_distributions"], f["nav"], rc_years=3)
        gap = max(
            abs(fit.params.growth - 0.09),
            abs(fit.params.bow - 3.0),
            max(abs(a - b) for a, b in zip(fit.params.rc, true.rc, strict=True)),
        )
        return (
            "calibration recovers known parameters from noise-free curves",
            "rc 30/40/50/100%, G 9%, B 3",
            f"{gap:.1e}",
            gap < 1e-5,
        )

    def stochastic_mean() -> tuple[str, str, str, bool]:
        spec = fm.StochasticSpec(call_noise=0.0, dist_noise=0.0, smoothing=1.0)
        paths = fm.simulate(spec, 40000 if not fast else 15000, seed=41)
        t, c, d = fm.expected_path(spec, 0.0, 100.0, 0.0)
        mc = paths.distributions.mean(axis=0)
        z = float(
            np.max(np.abs(mc - d) / (paths.distributions.std(axis=0, ddof=1) / np.sqrt(paths.distributions.shape[0]) + 1e-12))
        )
        conserve = float(np.max(np.abs(paths.calls.sum(axis=1) - 100.0)))
        return (
            "simulated mean distributions = expected path; calls sum to commitment",
            "48 quarters",
            f"max |z| {z:.2f}, calls {conserve:.1e}",
            z < 4.5 and conserve < 1e-9,
        )

    def secondary_fair_at_mu() -> tuple[str, str, str, bool]:
        spec = fm.StochasticSpec()
        worst = max(abs(sec.discount(spec, sec.expected_state(spec, a), spec.mu)) for a in (0.5, 2, 4, 7, 10))
        return "required return = fund's expected return gives zero discount", "ages 0.5-10", f"{worst:.1e}", worst < 1e-9

    def secondary_mc() -> tuple[str, str, str, bool]:
        spec = fm.StochasticSpec()
        zs = []
        for a, r in ((2.0, 0.15), (5.0, 0.13)):
            st = sec.expected_state(spec, a)
            m, se = sec.monte_carlo_value(spec, st, r, 20000 if not fast else 8000, seed=int(10 * a))
            zs.append((m - sec.value(spec, st, r)) / se)
        w = float(np.max(np.abs(zs)))
        return "expected-path value against full Monte Carlo", "2 states", f"max |z| {w:.2f}", w < 4.0

    def decomposition_adds_up() -> tuple[str, str, str, bool]:
        spec = fm.StochasticSpec()
        worst = 0.0
        for a in (1.0, 3.0, 6.0):
            d = sec.decompose(spec, sec.expected_state(spec, a), 0.16)
            worst = max(worst, abs(d.assets + d.unfunded + d.staleness - d.total))
        return "discount = assets + unfunded + staleness", "3 ages, up-to-date NAV", f"{worst:.1e}", worst < 1e-12

    def vc_conservation() -> tuple[str, str, str, bool]:
        rng = np.random.default_rng(51)
        worst = 0.0
        for _ in range(40 if not fast else 15):
            t = vc.random_company(rng)
            for v in rng.uniform(0, 3 * t.post_money(), 8):
                worst = max(worst, abs(float(vc.payoff(t, float(v))[0].sum()) - v) / max(v, 1.0))
        return "waterfall pays out exactly the exit value", "random cap tables, 8 exits each", f"{worst:.1e}", worst < 1e-10

    def vc_equilibrium() -> tuple[str, str, str, bool]:
        rng = np.random.default_rng(52)
        worst = 0.0
        for _ in range(30 if not fast else 10):
            t = vc.random_company(rng)
            for v in rng.uniform(0, 3 * t.post_money(), 6):
                pay, conv = vc.payoff(t, float(v))
                for i, sec_ in enumerate(t.securities):
                    if sec_.preferred:
                        flipped = list(conv)
                        flipped[i] = not flipped[i]
                        worst = max(worst, float(vc._distribute(t, float(v), flipped)[i] - pay[i]) / max(float(v), 1.0))
        return "no class gains by switching its conversion choice", "random cap tables", f"best gain {worst:.1e}", worst < 1e-9

    def vc_closed_form() -> tuple[str, str, str, bool]:
        # common 80m and one 1x preferred class of 20m shares at $5: payoff V - C(100) + 0.2 C(500)
        t = vc.CapTable((vc.Security("Common", 80.0), vc.Security("Pref", 20.0, 5.0, seniority=1)))
        v0, sig, yrs, r = 400.0, 0.8, 5.0, 0.03

        def call(k: float) -> float:
            f, s = v0 * np.exp(r * yrs), sig * np.sqrt(yrs)
            d1 = (np.log(f / k) + 0.5 * s * s) / s
            return float(np.exp(-r * yrs) * (f * norm.cdf(d1) - k * norm.cdf(d1 - s)))

        exact = v0 - call(100.0) + 0.2 * call(500.0)
        opm = float(vc.Payoffs.build(t, points=3000).value(v0, sig, yrs, r)[1])
        gap = abs(opm / exact - 1)
        return f"{exact:.4f} (Black-Scholes: V - C(100) + 0.2 C(500))", f"{opm:.4f}", f"{gap:.1e}", gap < 1e-4

    def vc_common_limit() -> tuple[str, str, str, bool]:
        # with no preference at all every share is common and worth v0 / shares
        t = vc.example({n: {"multiple": 0.0} for n in ("Series A", "Series B", "Series C", "Series D")})
        vals = vc.Payoffs.build(t, points=800).value(1000.0, 0.9, 4.0, 0.04)
        shares = np.array([s.shares for s in t.securities])
        gap = float(np.max(np.abs(vals / shares - 10.0)))
        return "no preferences: every share worth company / shares", "$10.00 a share", f"{gap:.1e}", gap < 1e-6

    def vc_backsolve() -> tuple[str, str, str, bool]:
        t = vc.example()
        f = vc.backsolve(t)
        price_gap = abs(f.per_share[-1] - 30.0)
        sum_gap = abs(float(f.values.sum()) / f.company - 1)
        return (
            "latest class worth its price; class values add to the company",
            f"${f.per_share[-1]:.6f}; ${f.company:,.1f}m",
            f"{price_gap:.1e}, {sum_gap:.1e}",
            price_gap < 1e-6 and sum_gap < 1e-4,
        )

    def vc_monte_carlo() -> tuple[str, str, str, bool]:
        t = vc.example()
        f = vc.backsolve(t)
        m, se = vc.monte_carlo(t, f.company, 0.9, 4.0, 0.04, paths=20000 if not fast else 6000, seed=53)
        z = float(np.max(np.abs((m - f.values) / se)))
        return "exact OPM integral against Monte Carlo", "6 classes", f"max |z| {z:.2f}", z < 4.0

    add("IRR", "XIRR, published example", xirr_microsoft)
    add("IRR", "MIRR, published examples", mirr_microsoft)
    add("IRR", "Two IRRs: the pump problem", lorie_savage)
    add("IRR", "Against numpy-financial", irr_vs_numpy_financial)
    add("IRR", "Norstrom's condition", norstrom_positive)
    add("IRR", "Every root, 50-digit reference", all_roots)
    add("IRR", "Scan against polynomial roots", periodic_route)
    add("Multiples", "Identities", multiples_identity)
    add("PME", "A fund that is the index", index_fund)
    add("PME", "Closed forms for one deal", single_deal)
    add("PME", "Direct Alpha recovers the true alpha", alpha_recovered)
    add("PME", "Kaplan-Schoar and Direct Alpha agree in sign", ks_and_alpha_agree)
    add("PME", "PME+ scaling", pme_plus_scale)
    add("Waterfall", "Every pound accounted for", waterfall_conservation)
    add("Waterfall", "Catch-up gives exactly the carry share", catch_up_identity)
    add("Waterfall", "Clawback returns exactly the excess", clawback_bounds)
    add("Carry", "Closed form against quadrature", carry_closed_form_vs_quadrature)
    add("Carry", "Closed form against the waterfall engine", carry_engine_vs_formula)
    add("Carry", "LPs lose what the GP gains", risk_neutral_identity)
    add("Fund model", "Takahashi-Alexander identities", ta_identity)
    add("Fund model", "Calibration recovers known parameters", ta_recovery)
    add("Fund model", "Simulation mean matches the expected path", stochastic_mean)
    add("Secondary", "Fair pricing at the fund's expected return", secondary_fair_at_mu)
    add("Secondary", "Expected-path value against Monte Carlo", secondary_mc)
    add("Secondary", "Discount decomposition adds up", decomposition_adds_up)
    add("Venture", "Waterfall pays out the exit value", vc_conservation)
    add("Venture", "Conversion is an equilibrium", vc_equilibrium)
    add("Venture", "One preferred class: closed form", vc_closed_form)
    add("Venture", "No preferences: all shares equal", vc_common_limit)
    add("Venture", "Backsolve prices the latest round", vc_backsolve)
    add("Venture", "OPM integral against Monte Carlo", vc_monte_carlo)
    return pd.DataFrame([c.__dict__ for c in checks])


def to_markdown(results: pd.DataFrame) -> str:
    results = results.assign(**{c: results[c].astype(str).str.replace("|", "/") for c in ("reference", "result", "error")})
    lines = ["| Area | Check | Reference | Result | Error | Status |", "|---|---|---|---|---|---|"]
    for row in results.itertuples():
        lines.append(
            f"| {row.area} | {row.check} | {row.reference} | {row.result} | {row.error} | {'PASS' if row.passed else 'FAIL'} |"
        )
    return "\n".join(lines)
