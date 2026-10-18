"""The stylised fund, the market history interface, the gallery registry and the command line."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from pmlab import gallery, market
from pmlab.cashflows import CashFlows, multiples
from pmlab.cli import build_parser, main
from pmlab.synthetic import FundSpec, Market, gbm_market, market_from_series, simulate_fund
from pmlab.validation import to_markdown


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close("all")


def test_the_fund_draws_its_commitment_and_returns_every_deal():
    m = gbm_market(15.0, seed=1)
    f = simulate_fund(m, FundSpec(deals=12, fee=0.015, seed=2))
    assert len(f.deals) == 12
    fees = 100.0 - f.deals["cost"].sum()
    assert fees / (0.015 * 100.0 / 4) == pytest.approx(round(fees / 0.375))  # whole quarters of fees
    # deals and fees use the whole commitment (a fee and an exit can fall on the same date, so net the flows)
    assert f.deals["proceeds"].sum() - f.amounts.sum() == pytest.approx(100.0, rel=1e-12)
    assert f.navs[-1] == 0.0 and f.times[-1] <= 12.0 + 1e-9
    assert (f.deals["exit"] - f.deals["entry"]).between(3.0 - 0.05, 7.0 + 0.05).all()
    assert multiples(CashFlows(f.times, f.amounts)).tvpi > 0


def test_a_market_too_short_is_refused_and_windows_rebase():
    with pytest.raises(ValueError, match="covers"):
        simulate_fund(gbm_market(10.0), FundSpec())
    m = gbm_market(20.0, seed=3)
    w = m.window(5.0, 12.0)
    assert w.times[0] == 0.0 and w.times[-1] == pytest.approx(12.0)
    assert w.levels[0] == pytest.approx(float(m.level(5.0)))


def test_a_monthly_market_from_a_price_series():
    idx = pd.date_range("2000-01-01", periods=400, freq="D")
    series = pd.Series(np.linspace(100, 140, 400), index=idx)
    m = market_from_series(series)
    assert isinstance(m, Market) and m.times[0] == 0.0 and m.levels[-1] == pytest.approx(140.0)


def test_market_files_round_trip(tmp_path):
    frame = pd.DataFrame({"date": pd.date_range("2010-01-31", periods=3, freq="ME"), "close": [1.0, 2.0, 3.0]})
    for name in market.TICKERS:
        frame.to_csv(tmp_path / f"{name}.csv", index=False)
    assert market.available(tmp_path)
    assert market.load("sp500", tmp_path).tolist() == [1.0, 2.0, 3.0]


def test_the_gallery_lists_each_chart_once_and_draws_the_offline_ones(monkeypatch):
    from pmlab.gallery import fees

    monkeypatch.setattr(fees, "SIMS", 600)  # the charts' Monte Carlo, at a size a test can afford
    for cached in (fees._value, fees._vega, fees._revenue, fees._alpha_curves):
        cached.cache_clear()
    names = [i.filename for i in gallery.items()]
    assert len(names) == len(set(names))
    page = gallery.markdown()
    assert all(page.count(f"(images/{n})") == 1 for n in names)
    for item in gallery.items():
        if item.requires is None:
            fig = item.build()
            assert fig.axes and item.day in gallery.DAYS
    for cached in (fees._value, fees._vega, fees._revenue, fees._alpha_curves):
        cached.cache_clear()


@pytest.mark.parametrize("item", [i for i in gallery.items() if i.requires == "market"], ids=lambda i: i.filename)
def test_the_market_charts_draw_where_the_history_is_stored(item):
    if not item.available():
        pytest.skip("drawn from the local index history, which this machine does not have")
    assert item.build().axes


def test_the_irr_command(tmp_path, capsys):
    pd.DataFrame({"date": ["2020-01-01", "2021-01-01", "2022-01-01"], "amount": [-1600, 10000, -10000]}).to_csv(
        tmp_path / "pump.csv", index=False
    )
    main(["irr", str(tmp_path / "pump.csv")])
    out = capsys.readouterr().out
    assert "IRRs (2; Descartes allows 2)" in out and "TVPI" in out
    pd.DataFrame({"date": ["2015-03-01", "2018-06-30"], "amount": [-100, 40]}).to_csv(tmp_path / "fund.csv", index=False)
    main(["irr", str(tmp_path / "fund.csv"), "--nav", "120"])
    assert "IRR: " in capsys.readouterr().out


def test_the_parser_and_the_markdown_table():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["nothing"])
    table = pd.DataFrame(
        [{"area": "A", "check": "c", "reference": "r", "result": "x", "error": "0", "passed": True, "seconds": 0.0}]
    )
    assert "| A | c | r | x | 0 | PASS |" in to_markdown(table)


def test_the_validation_suite_passes_in_fast_mode(capsys):
    main(["validate", "--fast"])
    assert "FAIL" not in capsys.readouterr().out


def test_the_fees_command(capsys):
    main(["fees", "--funds", "2000", "--waterfall", "american"])
    out = capsys.readouterr().out
    assert "terms: 2 and 20, 8% hurdle, full catch-up, american" in out and "of GP revenue is fixed" in out
