import pytest

from market.factory import create_market_provider
from market.indian_api import IndianAPIProvider
from market.simulator import SimulatorProvider


def test_factory_returns_simulator_without_key(monkeypatch):
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    provider = create_market_provider()
    assert isinstance(provider, SimulatorProvider)


def test_factory_returns_indian_api_with_key(monkeypatch):
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "test-key-123")
    provider = create_market_provider()
    assert isinstance(provider, IndianAPIProvider)


def test_factory_indian_api_receives_key(monkeypatch):
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "secret-key-abc")
    provider = create_market_provider()
    assert isinstance(provider, IndianAPIProvider)
    assert provider._api_key == "secret-key-abc"


def test_factory_returns_new_instance_each_call(monkeypatch):
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    p1 = create_market_provider()
    p2 = create_market_provider()
    assert p1 is not p2


def test_factory_empty_key_returns_simulator(monkeypatch):
    # Empty string is falsy, so treated as "not set"
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "")
    provider = create_market_provider()
    assert isinstance(provider, SimulatorProvider)
