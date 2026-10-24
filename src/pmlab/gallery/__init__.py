"""The chart gallery: every figure the documentation shows, rebuilt from source with ``pmlab gallery``.

Each chart is an :class:`Item` - the file it writes, what it shows, the function that
draws it, and the day it belongs to - so the gallery page (``docs/GALLERY.md``) and the
images cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from matplotlib.figure import Figure

from .. import market
from .style import save

DAYS: dict[int, str] = {
    1: "Cash flows and performance measures",
    2: "Fees, waterfalls and carried interest as an option",
    3: "Fund cash-flow models and the secondary market",
}


@dataclass(frozen=True)
class Item:
    filename: str
    title: str
    description: str
    build: Callable[[], Figure]
    day: int
    requires: str | None = None  # "market": drawn from the local index history (``pmlab market fetch``)

    def available(self) -> bool:
        return self.requires is None or market.available()


def items() -> tuple[Item, ...]:
    # imported here so that the package imports without the charts' own dependencies being loaded
    from . import cashflows, fees
    from . import fundmodels as fm

    return (
        Item(
            "irr-pathologies.png",
            "An IRR is a root, and a stream can have none, one or several",
            "The NPV against the rate for the pump problem, a refinance-and-repay fund, and a stream with no IRR.",
            cashflows.irr_pathologies,
            1,
        ),
        Item(
            "irr-manipulation.png",
            "Borrowing to delay capital calls raises the IRR",
            "A subscription credit line against the IRR, the TVPI and the Kaplan-Schoar PME.",
            cashflows.irr_manipulation,
            1,
        ),
        Item(
            "j-curve.png",
            "The J-curve",
            "Net cash flow, interim IRR and multiples of 300 stylised funds through their lives.",
            cashflows.j_curve,
            1,
        ),
        Item(
            "pme-family.png",
            "Five public market equivalents of the same funds",
            "Kaplan-Schoar, Direct Alpha, Long-Nickels, PME+ and mPME on funds with a known 3% alpha over the S&P 500.",
            cashflows.pme_family,
            1,
            "market",
        ),
        Item(
            "pme-beta-bias.png",
            "A PME assumes beta is one",
            "Funds with zero alpha and betas from 0.6 to 1.8, measured against the S&P 500, vintage by vintage.",
            cashflows.pme_beta_bias,
            1,
            "market",
        ),
        Item(
            "benchmark-choice.png",
            "The benchmark is half the answer",
            "The same funds' Direct Alpha against four total-return benchmarks.",
            cashflows.benchmark_choice,
            1,
            "market",
        ),
        Item(
            "vintage-irr-vs-pme.png",
            "The IRR measures the market, the PME the manager",
            "Identical managers across 25 vintages: net IRR against net Direct Alpha.",
            cashflows.vintage_irr_vs_pme,
            1,
            "market",
        ),
        Item(
            "waterfall-tiers.png",
            "Four tiers decide who gets each pound",
            "The European waterfall's tiers and the GP's share of profit.",
            fees.waterfall_tiers,
            2,
        ),
        Item(
            "carry-as-options.png",
            "Carried interest is a call spread",
            "The carry payoff as two calls, and its Black-Scholes value.",
            fees.carry_as_options,
            2,
        ),
        Item(
            "gross-to-net.png",
            "From gross to net",
            "Net IRR against gross IRR under six sets of terms.",
            fees.gross_to_net_chart,
            2,
        ),
        Item(
            "gp-share.png",
            "Two and twenty takes more than twenty",
            "The GP's take as a share of gross profit.",
            fees.gp_share_chart,
            2,
        ),
        Item(
            "fee-schedules.png",
            "Fees come out of the commitment",
            "Quarterly fees under four fee bases, and what is left to invest.",
            fees.fee_schedules,
            2,
        ),
        Item(
            "european-vs-american.png",
            "Deal by deal, winners are paid first",
            "Cumulative carry under each waterfall for one fund, and the clawback.",
            fees.european_vs_american,
            2,
        ),
        Item(
            "clawback.png",
            "The clawback is the rule",
            "How often and how much an American waterfall overpays, across 20,000 funds.",
            fees.clawback_distribution,
            2,
        ),
        Item(
            "carry-vega.png",
            "Riskier deals are worth more to the GP",
            "Carry and the LPs' stake against deal volatility.",
            fees.carry_vega,
            2,
        ),
        Item(
            "carry-correlation.png",
            "A portfolio of options",
            "Carry value against the correlation between deals.",
            fees.carry_correlation,
            2,
        ),
        Item(
            "gp-revenue.png",
            "Most of a manager's pay is fixed",
            "Present value of fees and carry per 100 committed (Metrick-Yasuda).",
            fees.gp_revenue,
            2,
        ),
        Item(
            "break-even-alpha.png",
            "Four points a year to break even",
            "The LPs' stake against deal alpha, and the break-even alpha.",
            fees.break_even,
            2,
        ),
        Item(
            "hurdle-catch-up.png",
            "A hurdle with a catch-up is a timing device",
            "Carry value against the hurdle rate for four catch-ups.",
            fees.hurdle_catch_up,
            2,
        ),
        Item(
            "closed-form-check.png",
            "Engine and formula agree",
            "Closed-form carry against Monte Carlo through the waterfall.",
            fees.closed_form_check,
            2,
        ),
        Item(
            "fee-heatmap.png", "The fee costs more than the carry", "Gross minus net IRR by fee and carry.", fees.fee_heatmap, 2
        ),
        Item(
            "net-distribution.png",
            "Fees shift the distribution, carry trims the top",
            "Gross and net IRRs of 4,000 simulated funds.",
            fees.net_distribution,
            2,
        ),
        Item("carry-delta.png", "Carry rewards skill", "Carry and fees against deal alpha.", fees.carry_delta, 2),
        Item("ta-profile.png", "The Yale model", "Takahashi-Alexander flows, NAV and J-curve.", fm.ta_profile, 3),
        Item("ta-sensitivity.png", "Bow, growth and pace", "What each Takahashi-Alexander parameter does.", fm.ta_sensitivity, 3),
        Item(
            "ta-fit-deals.png",
            "Six parameters reproduce a deal-built fund",
            "The model fitted to bottom-up deal funds.",
            fm.ta_fit_deals,
            3,
        ),
        Item(
            "ta-recovery.png",
            "Recovering the parameters from noisy data",
            "Re-estimated growth, bow and call rate.",
            fm.ta_recovery,
            3,
        ),
        Item(
            "stochastic-fan.png",
            "One model, many futures",
            "Fan charts of NAV and cumulative net cash flow.",
            fm.stochastic_fan,
            3,
        ),
        Item(
            "fund-outcomes.png",
            "The market explains much of a fund's outcome",
            "TVPI distribution and IRR against the market.",
            fm.outcomes,
            3,
        ),
        Item("vintage-dispersion.png", "Vintage matters", "IRRs of 25 vintages sharing market paths.", fm.vintage_dispersion, 3),
        Item(
            "capital-calls.png",
            "Plan for the 95th percentile of calls",
            "Annual capital calls and their tail.",
            fm.capital_calls,
            3,
        ),
        Item("nav-smoothing.png", "Reported NAVs lag and understate risk", "True against reported NAV.", fm.smoothing, 3),
        Item(
            "discount-by-age.png",
            "Young funds trade at deep discounts",
            "Secondary discount by fund age and required return.",
            fm.discount_by_age,
            3,
        ),
        Item(
            "discount-heatmap.png",
            "Secondary pricing in one table",
            "Discount by age and required return.",
            fm.discount_heatmap,
            3,
        ),
        Item(
            "discount-decomposition.png",
            "Where the discount comes from",
            "Assets against the unfunded commitment.",
            fm.discount_decomposition,
            3,
        ),
        Item(
            "crash-discount.png",
            "Stale NAVs widen discounts after a fall",
            "Discount to reported and true NAV after a 30% fall.",
            fm.crash_discount,
            3,
        ),
        Item("buyer-irr.png", "Buying at a discount", "Buyer IRR distributions at three prices.", fm.buyer_irr, 3),
        Item(
            "secondary-vs-primary.png",
            "A secondary buyer skips the J-curve",
            "Cumulative cash flow, primary against secondary.",
            fm.secondary_vs_primary,
            3,
        ),
        Item(
            "secondary-mc-check.png",
            "The shortcut prices as simulation does",
            "Expected-path value against Monte Carlo.",
            fm.mc_check,
            3,
        ),
    )


def build(out_dir: str | Path = "docs/images", only: str | None = None) -> list[Path]:
    """Draw every chart (or the one named, or one day's) into ``out_dir``."""
    written = []
    for item in items():
        if only and only not in (item.filename, str(item.day)):
            continue
        if not item.available():
            print(f"skipped {item.filename}: needs the local index history (pmlab market fetch)")
            continue
        written.append(save(item.build(), Path(out_dir) / item.filename))
    return written


def markdown(prefix: str = "images") -> str:
    """The gallery page, generated, so it always lists exactly the charts there are."""
    lines = ["# Gallery", "", "Every chart is rebuilt from source with `pmlab gallery`.", ""]
    for day, title in DAYS.items():
        lines += [f"## Day {day}: {title}", ""]
        for item in items():
            if item.day == day:
                lines += [f"**{item.title}** - {item.description}", "", f"![{item.title}]({prefix}/{item.filename})", ""]
    return "\n".join(lines)
