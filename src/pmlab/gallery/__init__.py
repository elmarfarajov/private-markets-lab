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
    from . import cashflows

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
