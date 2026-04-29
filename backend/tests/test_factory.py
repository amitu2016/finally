import pytest

from market.factory import create_market_provider
from market.fallback import FallbackProvider
from market.simulator import SimulatorProvider
from market.yahoo import YahooFinanceProvider


def test_factory_returns_simulator_without_key(monkeypatch):
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    monkeypatch.delenv("USE_YAHOO", raising=False)
    provider = create_market_provider()
    assert isinstance(provider, SimulatorProvider)


def test_factory_returns_fallback_provider_with_key(monkeypatch):
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "test-key-123")
    monkeypatch.delenv("USE_YAHOO", raising=False)
    provider = create_market_provider()
    assert isinstance(provider, FallbackProvider)


def test_factory_fallback_provider_wraps_indian_api_with_key(monkeypatch):
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "secret-key-abc")
    monkeypatch.delenv("USE_YAHOO", raising=False)
    provider = create_market_provider()
    assert isinstance(provider, FallbackProvider)
    assert provider._primary._api_key == "secret-key-abc"


def test_factory_returns_new_instance_each_call(monkeypatch):
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    monkeypatch.delenv("USE_YAHOO", raising=False)
    p1 = create_market_provider()
    p2 = create_market_provider()
    assert p1 is not p2


def test_factory_empty_key_returns_simulator(monkeypatch):
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "")
    monkeypatch.delenv("USE_YAHOO", raising=False)
    provider = create_market_provider()
    assert isinstance(provider, SimulatorProvider)


# ── USE_YAHOO tests ───────────────────────────────────────────────────────────


def test_factory_returns_yahoo_when_use_yahoo_true(monkeypatch):
    monkeypatch.setenv("USE_YAHOO", "true")
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    assert isinstance(create_market_provider(), YahooFinanceProvider)


def test_factory_yahoo_takes_priority_over_indian_api(monkeypatch):
    monkeypatch.setenv("USE_YAHOO", "true")
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "some-key")
    assert isinstance(create_market_provider(), YahooFinanceProvider)


def test_factory_use_yahoo_false_falls_through_to_indian_api(monkeypatch):
    monkeypatch.setenv("USE_YAHOO", "false")
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "some-key")
    assert isinstance(create_market_provider(), FallbackProvider)


def test_factory_use_yahoo_false_falls_through_to_simulator(monkeypatch):
    monkeypatch.setenv("USE_YAHOO", "false")
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    assert isinstance(create_market_provider(), SimulatorProvider)


def test_factory_use_yahoo_empty_string_falls_through(monkeypatch):
    monkeypatch.setenv("USE_YAHOO", "")
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    assert isinstance(create_market_provider(), SimulatorProvider)
