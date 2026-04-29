from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from market.base import MarketDataProvider
from market.types import StockPrice
from market.yahoo import (
    HISTORY_LIMIT,
    POLL_INTERVAL,
    YahooFinanceProvider,
    _fetch_ticker_sync,
    _yahoo_symbol,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def make_fast_info(last_price=2195.75, previous_close=2165.0):
    fi = MagicMock()
    fi.last_price = last_price
    fi.previous_close = previous_close
    return fi


def mock_ticker(mocker, last_price=2195.75, previous_close=2165.0):
    fi = make_fast_info(last_price, previous_close)
    mocker.patch("market.yahoo.yf.Ticker", return_value=MagicMock(fast_info=fi))
    return fi


# ── _yahoo_symbol ─────────────────────────────────────────────────────────────


def test_yahoo_symbol_adds_ns_suffix():
    assert _yahoo_symbol("RELIANCE") == "RELIANCE.NS"


def test_yahoo_symbol_preserves_case():
    assert _yahoo_symbol("TCS") == "TCS.NS"


# ── _fetch_ticker_sync ────────────────────────────────────────────────────────


def test_fetch_ticker_returns_price_and_prev_close(mocker):
    mock_ticker(mocker, last_price=2195.75, previous_close=2165.0)
    result = _fetch_ticker_sync("RELIANCE")
    assert result == {"price": 2195.75, "prev_close": 2165.0}


def test_fetch_ticker_returns_none_on_none_price(mocker):
    mock_ticker(mocker, last_price=None, previous_close=2165.0)
    assert _fetch_ticker_sync("RELIANCE") is None


def test_fetch_ticker_returns_none_on_nan_price(mocker):
    mock_ticker(mocker, last_price=float("nan"), previous_close=2165.0)
    assert _fetch_ticker_sync("RELIANCE") is None


def test_fetch_ticker_uses_price_as_prev_close_when_prev_close_is_none(mocker):
    mock_ticker(mocker, last_price=2195.75, previous_close=None)
    result = _fetch_ticker_sync("RELIANCE")
    assert result is not None
    assert result["prev_close"] == 2195.75


def test_fetch_ticker_uses_price_as_prev_close_when_prev_close_is_nan(mocker):
    mock_ticker(mocker, last_price=2195.75, previous_close=float("nan"))
    result = _fetch_ticker_sync("RELIANCE")
    assert result is not None
    assert result["prev_close"] == 2195.75


def test_fetch_ticker_returns_none_on_exception(mocker):
    mocker.patch("market.yahoo.yf.Ticker", side_effect=Exception("network error"))
    assert _fetch_ticker_sync("RELIANCE") is None


def test_fetch_ticker_uses_ns_suffix(mocker):
    fi = make_fast_info()
    ticker_mock = MagicMock(fast_info=fi)
    patch = mocker.patch("market.yahoo.yf.Ticker", return_value=ticker_mock)
    _fetch_ticker_sync("RELIANCE")
    patch.assert_called_once_with("RELIANCE.NS")


# ── YahooFinanceProvider: interface conformance ───────────────────────────────


def test_yahoo_provider_is_market_data_provider():
    assert isinstance(YahooFinanceProvider(), MarketDataProvider)


# ── YahooFinanceProvider: data access before any poll ────────────────────────


def test_get_price_none_before_poll():
    assert YahooFinanceProvider().get_price("RELIANCE") is None


def test_get_all_prices_empty_before_poll():
    assert YahooFinanceProvider().get_all_prices() == {}


def test_get_history_empty_before_poll():
    assert YahooFinanceProvider().get_history("RELIANCE") == []


def test_get_all_prices_returns_copy():
    p = YahooFinanceProvider()
    assert p.get_all_prices() is not p.get_all_prices()


# ── YahooFinanceProvider: _update_cache ──────────────────────────────────────


def test_update_cache_creates_stock_price():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    sp = p.get_price("RELIANCE")
    assert sp is not None
    assert sp.ticker == "RELIANCE"
    assert sp.price == 2195.75


def test_update_cache_first_update_prev_price_equals_price():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    sp = p.get_price("RELIANCE")
    assert sp.prev_price == 2195.75


def test_update_cache_subsequent_prev_price_tracks_last_price():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    p._update_cache("RELIANCE", 2210.00, 2165.0)
    sp = p.get_price("RELIANCE")
    assert sp.prev_price == 2195.75


def test_update_cache_change_pct_computed_from_prev_close():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    expected = round((2195.75 - 2165.0) / 2165.0 * 100, 2)
    assert p.get_price("RELIANCE").change_pct == expected


def test_update_cache_timestamp_is_utc():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    assert p.get_price("RELIANCE").timestamp.tzinfo is not None


def test_update_cache_accumulates_history():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    p._update_cache("RELIANCE", 2210.00, 2165.0)
    assert len(p.get_history("RELIANCE")) == 2


def test_update_cache_caps_history_at_limit():
    p = YahooFinanceProvider()
    for i in range(HISTORY_LIMIT + 15):
        p._update_cache("RELIANCE", 2000.0 + i, 2000.0)
    assert len(p.get_history("RELIANCE")) == HISTORY_LIMIT


def test_update_cache_independent_per_ticker():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    p._update_cache("TCS", 3450.00, 3400.0)
    assert p.get_price("RELIANCE").price == 2195.75
    assert p.get_price("TCS").price == 3450.00


# ── YahooFinanceProvider: set_tickers ────────────────────────────────────────


def test_set_tickers_updates_tracked_list():
    p = YahooFinanceProvider()
    p.set_tickers(["RELIANCE", "TCS"])
    assert set(p._tickers) == {"RELIANCE", "TCS"}


def test_set_tickers_prunes_stale_cache():
    p = YahooFinanceProvider()
    p._cache["RELIANCE"] = StockPrice("RELIANCE", 2195.75, 2195.75, 0.0, datetime.now(timezone.utc))
    p._tickers = ["RELIANCE", "TCS"]
    p.set_tickers(["TCS"])
    assert p.get_price("RELIANCE") is None
    assert "RELIANCE" not in p._cache


def test_set_tickers_prunes_stale_history():
    p = YahooFinanceProvider()
    p._update_cache("RELIANCE", 2195.75, 2165.0)
    p._tickers = ["RELIANCE", "TCS"]
    p.set_tickers(["TCS"])
    assert p.get_history("RELIANCE") == []
    assert "RELIANCE" not in p._history


def test_set_tickers_retains_kept_entries():
    p = YahooFinanceProvider()
    p._cache["TCS"] = StockPrice("TCS", 3450.0, 3440.0, 0.3, datetime.now(timezone.utc))
    p._tickers = ["RELIANCE", "TCS"]
    p.set_tickers(["TCS"])
    assert p.get_price("TCS") is not None


def test_get_history_limit_respected():
    p = YahooFinanceProvider()
    for i in range(20):
        p._update_cache("RELIANCE", 2000.0 + i, 2000.0)
    assert len(p.get_history("RELIANCE", limit=5)) == 5


# ── YahooFinanceProvider: _poll_all ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_all_populates_cache(mocker):
    mock_ticker(mocker, last_price=2195.75, previous_close=2165.0)
    p = YahooFinanceProvider()
    p.set_tickers(["RELIANCE"])
    await p._poll_all()
    sp = p.get_price("RELIANCE")
    assert sp is not None
    assert sp.price == 2195.75


@pytest.mark.asyncio
async def test_poll_all_skips_failed_ticker(mocker):
    mocker.patch("market.yahoo.yf.Ticker", side_effect=Exception("network error"))
    p = YahooFinanceProvider()
    p.set_tickers(["RELIANCE"])
    await p._poll_all()
    assert p.get_price("RELIANCE") is None


@pytest.mark.asyncio
async def test_poll_all_retains_stale_cache_on_error(mocker):
    stale = StockPrice("RELIANCE", 2100.0, 2095.0, 0.2, datetime.now(timezone.utc))
    mocker.patch("market.yahoo.yf.Ticker", side_effect=Exception("network error"))
    p = YahooFinanceProvider()
    p._cache["RELIANCE"] = stale
    p.set_tickers(["RELIANCE"])
    await p._poll_all()
    assert p.get_price("RELIANCE").price == 2100.0


@pytest.mark.asyncio
async def test_poll_all_accumulates_history(mocker):
    mock_ticker(mocker, last_price=2195.75, previous_close=2165.0)
    p = YahooFinanceProvider()
    p.set_tickers(["RELIANCE"])
    await p._poll_all()
    await p._poll_all()
    assert len(p.get_history("RELIANCE")) == 2


@pytest.mark.asyncio
async def test_poll_all_no_op_with_empty_tickers(mocker):
    patch = mocker.patch("market.yahoo.yf.Ticker")
    p = YahooFinanceProvider()
    p.set_tickers([])
    await p._poll_all()
    patch.assert_not_called()


# ── YahooFinanceProvider: async lifecycle ─────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_without_start_does_not_raise():
    await YahooFinanceProvider().stop()


@pytest.mark.asyncio
async def test_double_start_does_not_create_duplicate_task():
    p = YahooFinanceProvider()
    p.set_tickers([])
    await p.start()
    task = p._task
    await p.start()
    assert p._task is task
    await p.stop()


@pytest.mark.asyncio
async def test_task_is_none_after_stop():
    p = YahooFinanceProvider()
    p.set_tickers([])
    await p.start()
    await p.stop()
    assert p._task is None


@pytest.mark.asyncio
async def test_restart_after_stop_creates_new_task():
    p = YahooFinanceProvider()
    p.set_tickers([])
    await p.start()
    await p.stop()
    await p.start()
    assert p._task is not None
    assert not p._task.done()
    await p.stop()


# ── constants ─────────────────────────────────────────────────────────────────


def test_poll_interval_is_positive():
    assert POLL_INTERVAL > 0


def test_history_limit_is_positive():
    assert HISTORY_LIMIT > 0
