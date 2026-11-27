"""Public index histories for public market equivalents, stored locally and never committed.

A PME is only as meaningful as its benchmark, and the literature's central finding about
buyout performance - that it beats the S&P 500 but much less clearly a small-cap index -
is a statement about the benchmark. Four total-return series from Yahoo Finance, month-end:

* ``sp500``: the S&P 500 total return index (``^SP500TR``), from 1988;
* ``small``: the iShares Russell 2000 ETF, adjusted for distributions (``IWM``), from 2000;
* ``nasdaq``: the Invesco QQQ ETF, adjusted (``QQQ``), from 1999;
* ``value``: the Vanguard Small-Cap Value ETF, adjusted (``VBR``), from 2004.

The ETFs carry their expense ratios, a few basis points a year. The files live under
``data/market`` (``pmlab market fetch``), which git ignores: the quotes are Yahoo's to
license, not this repository's to publish.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

TICKERS = {"sp500": "^SP500TR", "small": "IWM", "nasdaq": "QQQ", "value": "VBR"}
LABELS = {
    "sp500": "S&P 500 total return",
    "small": "Russell 2000 (IWM)",
    "nasdaq": "Nasdaq-100 (QQQ)",
    "value": "small-cap value (VBR)",
}


def data_root() -> Path:
    """``$PMLAB_DATA`` or ``data/market`` in the repository."""
    configured = os.environ.get("PMLAB_DATA")
    return Path(configured) if configured else Path(__file__).resolve().parents[2] / "data" / "market"


def available(root: Path | None = None) -> bool:
    base = root or data_root()
    return all((base / f"{name}.csv").exists() for name in TICKERS)


def fetch(root: Path | None = None) -> Path:  # pragma: no cover - network
    """Download month-end total-return closes, up to the last complete month."""
    import yfinance as yf

    base = root or data_root()
    base.mkdir(parents=True, exist_ok=True)
    today = date.today()
    for name, ticker in TICKERS.items():
        frame = yf.Ticker(ticker).history(period="max", auto_adjust=True)
        if frame is None or frame.empty:
            raise RuntimeError(f"no history for {ticker}")
        close = frame["Close"]
        close.index = close.index.tz_localize(None)
        monthly = close.resample("ME").last().dropna()
        monthly = monthly[monthly.index < pd.Timestamp(today.year, today.month, 1)]
        monthly.rename("close").to_frame().rename_axis("date").to_csv(base / f"{name}.csv")
    meta = {"fetched": today.isoformat(), "source": "Yahoo Finance", "tickers": TICKERS}
    (base / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return base


def load(name: str, root: Path | None = None) -> pd.Series:
    """Month-end closes of one series, indexed by date."""
    base = root or data_root()
    frame = pd.read_csv(base / f"{name}.csv", parse_dates=["date"]).set_index("date")
    return frame["close"].astype(float).rename(name)


# ---------------------------------------------------------------- liquid alternatives (Day 9)

ALTS = {
    "spy": "SPY",
    "efa": "EFA",
    "eem": "EEM",
    "ief": "IEF",
    "tlt": "TLT",
    "gld": "GLD",
    "dbc": "DBC",
    "uup": "UUP",
    "fxy": "FXY",
    "fxe": "FXE",
    "qai": "QAI",
    "dbmf": "DBMF",
    "put": "^PUT",
    "vix": "^VIX",
    "tbill": "^IRX",
}
TREND = ("spy", "efa", "eem", "ief", "tlt", "gld", "dbc", "uup", "fxy", "fxe")
ASSET_CLASS = {
    "spy": "equity", "efa": "equity", "eem": "equity",
    "ief": "bonds", "tlt": "bonds",
    "gld": "commodities", "dbc": "commodities",
    "uup": "currencies", "fxy": "currencies", "fxe": "currencies",
}  # fmt: skip


def alts_root() -> Path:
    """``$PMLAB_ALTS`` or ``data/alts`` in the repository: daily closes, never committed."""
    configured = os.environ.get("PMLAB_ALTS")
    return Path(configured) if configured else data_root().parent / "alts"


def alts_available(root: Path | None = None) -> bool:
    base = root or alts_root()
    return all((base / f"{name}.csv").exists() for name in ALTS)


def fetch_alts(root: Path | None = None) -> Path:  # pragma: no cover - network
    """Download daily adjusted closes of the liquid-alternative universe, up to the last complete month."""
    import yfinance as yf

    base = root or alts_root()
    base.mkdir(parents=True, exist_ok=True)
    today = date.today()
    for name, ticker in ALTS.items():
        frame = yf.Ticker(ticker).history(period="max", auto_adjust=True)
        if frame is None or frame.empty:
            raise RuntimeError(f"no history for {ticker}")
        close = frame["Close"]
        close.index = close.index.tz_localize(None).normalize()
        close = close[close.index < pd.Timestamp(today.year, today.month, 1)]
        close.rename("close").to_frame().rename_axis("date").to_csv(base / f"{name}.csv")
    meta = {"fetched": today.isoformat(), "source": "Yahoo Finance", "frequency": "daily", "tickers": ALTS}
    (base / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return base


def load_alts(names: tuple[str, ...] | None = None, root: Path | None = None) -> pd.DataFrame:
    """Daily closes of the named series (all by default), one column each."""
    base = root or alts_root()
    cols = {n: load(n, base) for n in (names or tuple(ALTS))}
    return pd.DataFrame(cols)
