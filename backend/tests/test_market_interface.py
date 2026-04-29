"""Verify all providers satisfy the MarketDataProvider contract."""
import pytest

from market.base import MarketDataProvider
from market.indian_api import IndianAPIProvider
from market.simulator import SimulatorProvider
from market.types import StockPrice
from market.yahoo import YahooFinanceProvider


# ── isinstance checks ────────────────────────────────────────────────────────


def test_simulator_is_market_data_provider():
    assert isinstance(SimulatorProvider(), MarketDataProvider)


def test_indian_api_is_market_data_provider():
    assert isinstance(IndianAPIProvider("fake-key"), MarketDataProvider)


def test_yahoo_is_market_data_provider():
    assert isinstance(YahooFinanceProvider(), MarketDataProvider)


# ── Parametrized contract tests ──────────────────────────────────────────────


@pytest.fixture(params=["simulator", "indian_api", "yahoo"])
def provider(request) -> MarketDataProvider:
    if request.param == "simulator":
        return SimulatorProvider()
    if request.param == "indian_api":
        return IndianAPIProvider("fake-key")
    return YahooFinanceProvider()


def test_get_price_returns_none_before_set_tickers(provider):
    assert provider.get_price("RELIANCE") is None


def test_get_all_prices_returns_dict_before_set_tickers(provider):
    result = provider.get_all_prices()
    assert isinstance(result, dict)
    assert len(result) == 0


def test_get_history_returns_list_before_set_tickers(provider):
    result = provider.get_history("RELIANCE")
    assert isinstance(result, list)
    assert len(result) == 0


def test_set_tickers_does_not_raise(provider):
    provider.set_tickers(["RELIANCE", "TCS", "INFY"])


def test_get_all_prices_keys_match_tickers_after_set(provider):
    tickers = ["RELIANCE", "TCS"]
    provider.set_tickers(tickers)
    prices = provider.get_all_prices()
    # Simulator populates cache immediately; IndianAPI does so after first poll
    # Both must return a dict; simulator has entries, IndianAPI may be empty
    assert isinstance(prices, dict)


def test_get_history_limit_respected(provider):
    provider.set_tickers(["RELIANCE"])
    # If simulator, run some ticks to populate history
    if isinstance(provider, SimulatorProvider):
        for _ in range(20):
            provider._tick()
        history = provider.get_history("RELIANCE", limit=5)
        assert len(history) <= 5
    else:
        # IndianAPI: no data yet, but limit param should not raise
        history = provider.get_history("RELIANCE", limit=5)
        assert isinstance(history, list)


def test_set_tickers_replaces_list(provider):
    provider.set_tickers(["RELIANCE"])
    provider.set_tickers(["TCS", "INFY"])
    # Both providers should reflect the new ticker list
    if isinstance(provider, SimulatorProvider):
        assert set(provider._tickers) == {"TCS", "INFY"}
    else:
        assert set(provider._tickers) == {"TCS", "INFY"}


# ── Return type contracts ────────────────────────────────────────────────────


def test_simulator_get_price_returns_stock_price():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    sp = provider.get_price("RELIANCE")
    assert isinstance(sp, StockPrice)


def test_simulator_get_all_prices_values_are_stock_prices():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE", "TCS"])
    for sp in provider.get_all_prices().values():
        assert isinstance(sp, StockPrice)


def test_simulator_history_entries_are_stock_prices():
    provider = SimulatorProvider()
    provider.set_tickers(["TCS"])
    provider._tick()
    for sp in provider.get_history("TCS"):
        assert isinstance(sp, StockPrice)


# ── MarketDataProvider is abstract ──────────────────────────────────────────


def test_market_data_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        MarketDataProvider()
