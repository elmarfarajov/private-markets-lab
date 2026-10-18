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

from .cashflows import CashFlows, fund_irr, irr, irr_roots, mirr, multiples, norstrom, periodic_roots, sign_changes
from .pme import direct_alpha, ks_pme, long_nickels, mpme, pme_plus, report
from .synthetic import FundSpec, gbm_market, simulate_fund


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
    return pd.DataFrame([c.__dict__ for c in checks])


def to_markdown(results: pd.DataFrame) -> str:
    results = results.assign(**{c: results[c].astype(str).str.replace("|", "/") for c in ("reference", "result", "error")})
    lines = ["| Area | Check | Reference | Result | Error | Status |", "|---|---|---|---|---|---|"]
    for row in results.itertuples():
        lines.append(
            f"| {row.area} | {row.check} | {row.reference} | {row.result} | {row.error} | {'PASS' if row.passed else 'FAIL'} |"
        )
    return "\n".join(lines)
