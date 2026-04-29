"""Tests for the API fallback mechanism (FallbackProvider + is_rate_limited)."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest
import respx

from market.fallback import MONITOR_INTERVAL, FallbackProvider
from market.indian_api import BASE_URL, MONTHLY_QUOTA, IndianAPIProvider
from market.simulator import SimulatorProvider
from market.types import StockPrice

SAMPLE_RESPONSE = {
    "tickerId": "RELIANCE",
    "companyName": "Reliance Industries Limited",
    "currentPrice": {"NSE": 2195.75, "BSE": 2196.10},
    "percentChange": 1.25,
}


# ── IndianAPIProvider.is_rate_limited ─────────────────────────────────────────


def test_is_rate_limited_false_initially():
    provider = IndianAPIProvider("test-key")
    assert provider.is_rate_limited is False


def test_is_rate_limited_true_when_quota_exhausted():
    provider = IndianAPIProvider("test-key")
    provider._calls_this_month = MONTHLY_QUOTA
    assert provider.is_rate_limited is True


def test_is_rate_limited_true_when_quota_exceeded():
    provider = IndianAPIProvider("test-key")
    provider._calls_this_month = MONTHLY_QUOTA + 100
    assert provider.is_rate_limited is True


def test_is_rate_limited_false_when_below_quota():
    provider = IndianAPIProvider("test-key")
    provider._calls_this_month = MONTHLY_QUOTA - 1
    assert provider.is_rate_limited is False


def test_is_rate_limited_true_when_flag_set():
    provider = IndianAPIProvider("test-key")
    provider._is_rate_limited = True
    assert provider.is_rate_limited is True


def test_is_rate_limited_resets_on_new_month():
    provider = IndianAPIProvider("test-key")
    provider._is_rate_limited = True
    provider._calls_this_month = MONTHLY_QUOTA
    # Simulate a previous month to trigger reset
    provider._quota_month = (2020, 1)
    provider._maybe_reset_monthly_quota()
    assert provider._is_rate_limited is False
    assert provider._calls_this_month == 0
    assert provider.is_rate_limited is False


def test_is_rate_limited_not_reset_same_month():
    provider = IndianAPIProvider("test-key")
    provider._is_rate_limited = True
    now = datetime.now(timezone.utc)
    provider._quota_month = (now.year, now.month)
    provider._maybe_reset_monthly_quota()
    assert provider._is_rate_limited is True


# ── _poll_one sets is_rate_limited on HTTP 429 ────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_poll_one_sets_rate_limited_on_429():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(429))
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    async with httpx.AsyncClient() as client:
        result = await provider._poll_one(client, "RELIANCE")
    assert result is False
    assert provider._is_rate_limited is True
    assert provider.is_rate_limited is True


@pytest.mark.asyncio
@respx.mock
async def test_poll_one_does_not_set_rate_limited_on_500():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(500))
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    async with httpx.AsyncClient() as client:
        await provider._poll_one(client, "RELIANCE")
    assert provider._is_rate_limited is False


@pytest.mark.asyncio
@respx.mock
async def test_poll_one_does_not_set_rate_limited_on_404():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(404))
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    async with httpx.AsyncClient() as client:
        await provider._poll_one(client, "RELIANCE")
    assert provider._is_rate_limited is False


# ── _poll_loop sets is_rate_limited on quota exhaustion ───────────────────────


@pytest.mark.asyncio
async def test_poll_loop_sets_rate_limited_when_quota_exhausted():
    """When the monthly quota is pre-exhausted, _poll_loop sets _is_rate_limited."""
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    provider._calls_this_month = MONTHLY_QUOTA  # Pre-exhaust quota

    # Run the poll loop briefly then cancel it
    task = asyncio.create_task(provider._poll_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert provider._is_rate_limited is True


# ── FallbackProvider: initial state ──────────────────────────────────────────


def test_fallback_provider_not_using_fallback_initially():
    provider = FallbackProvider("test-key")
    assert provider.is_using_fallback is False


def test_fallback_provider_has_primary_and_fallback():
    provider = FallbackProvider("test-key")
    assert isinstance(provider._primary, IndianAPIProvider)
    assert isinstance(provider._fallback, SimulatorProvider)


# ── FallbackProvider: set_tickers ─────────────────────────────────────────────


def test_set_tickers_propagates_to_both_providers():
    provider = FallbackProvider("test-key")
    provider.set_tickers(["RELIANCE", "TCS"])
    assert set(provider._primary._tickers) == {"RELIANCE", "TCS"}
    assert set(provider._fallback._tickers) == {"RELIANCE", "TCS"}


def test_set_tickers_empty_propagates_to_both():
    provider = FallbackProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    provider.set_tickers([])
    assert provider._primary._tickers == []
    assert provider._fallback._tickers == []


# ── FallbackProvider: data access delegation ─────────────────────────────────


def test_get_price_delegates_to_primary_initially():
    provider = FallbackProvider("test-key")
    sp = StockPrice("RELIANCE", 2195.75, 2190.0, 0.25, datetime.now(timezone.utc))
    provider._primary._cache["RELIANCE"] = sp
    assert provider.get_price("RELIANCE") is sp


def test_get_price_delegates_to_fallback_when_active():
    provider = FallbackProvider("test-key")
    provider._using_fallback = True
    sp = StockPrice("RELIANCE", 2000.0, 1990.0, 0.5, datetime.now(timezone.utc))
    provider._fallback._cache["RELIANCE"] = sp
    assert provider.get_price("RELIANCE") is sp


def test_get_all_prices_delegates_to_primary_initially():
    provider = FallbackProvider("test-key")
    sp = StockPrice("TCS", 3450.0, 3440.0, 0.3, datetime.now(timezone.utc))
    provider._primary._cache["TCS"] = sp
    result = provider.get_all_prices()
    assert "TCS" in result
    assert result["TCS"].price == 3450.0


def test_get_all_prices_delegates_to_fallback_when_active():
    provider = FallbackProvider("test-key")
    provider._using_fallback = True
    sp = StockPrice("TCS", 3100.0, 3090.0, 0.1, datetime.now(timezone.utc))
    provider._fallback._cache["TCS"] = sp
    result = provider.get_all_prices()
    assert "TCS" in result
    assert result["TCS"].price == 3100.0


def test_get_history_delegates_to_primary_initially():
    provider = FallbackProvider("test-key")
    sp = StockPrice("INFY", 1560.0, 1550.0, 0.6, datetime.now(timezone.utc))
    provider._primary._history["INFY"] = [sp]
    assert provider.get_history("INFY") == [sp]


def test_get_history_delegates_to_fallback_when_active():
    provider = FallbackProvider("test-key")
    provider._using_fallback = True
    sp = StockPrice("INFY", 1500.0, 1490.0, 0.4, datetime.now(timezone.utc))
    provider._fallback._history["INFY"] = [sp]
    assert provider.get_history("INFY") == [sp]


def test_get_price_returns_none_when_ticker_not_in_cache():
    provider = FallbackProvider("test-key")
    assert provider.get_price("UNKNOWN") is None


# ── FallbackProvider: automatic fallback trigger ─────────────────────────────


@pytest.mark.asyncio
async def test_monitor_loop_switches_to_fallback_when_rate_limited():
    """When primary is rate-limited, the monitor loop enables the fallback."""
    provider = FallbackProvider("test-key")
    provider._primary._is_rate_limited = True  # Pre-set rate limit flag

    # Run one monitor iteration manually
    async def run_one_iteration():
        await asyncio.sleep(0)  # yield
        # Directly invoke one check as the monitor loop would
        if not provider._using_fallback and provider._primary.is_rate_limited:
            provider._using_fallback = True

    await run_one_iteration()
    assert provider.is_using_fallback is True


@pytest.mark.asyncio
async def test_monitor_loop_does_not_switch_when_not_rate_limited():
    provider = FallbackProvider("test-key")
    provider._primary._is_rate_limited = False
    provider._primary._calls_this_month = 0

    # Simulate one monitor check
    if not provider._using_fallback and provider._primary.is_rate_limited:
        provider._using_fallback = True

    assert provider.is_using_fallback is False


@pytest.mark.asyncio
async def test_monitor_loop_task_switches_to_fallback():
    """Integration test: the actual monitor task switches to fallback on rate limit."""
    with patch("market.fallback.MONITOR_INTERVAL", 0.05):
        provider = FallbackProvider("test-key")
        provider.set_tickers(["RELIANCE"])
        provider._primary._is_rate_limited = True
        provider._monitor_task = asyncio.create_task(provider._monitor_loop())
        await asyncio.sleep(0.15)
        provider._monitor_task.cancel()
        try:
            await provider._monitor_task
        except asyncio.CancelledError:
            pass

    assert provider.is_using_fallback is True


@pytest.mark.asyncio
async def test_fallback_provider_uses_simulator_prices_after_switch():
    """After fallback is triggered, get_price returns simulator prices."""
    provider = FallbackProvider("test-key")
    provider.set_tickers(["RELIANCE"])

    # Seed simulator cache with a price
    sim_price = StockPrice("RELIANCE", 2400.0, 2390.0, -0.5, datetime.now(timezone.utc))
    provider._fallback._cache["RELIANCE"] = sim_price

    # Primary has a different price
    api_price = StockPrice("RELIANCE", 2195.75, 2190.0, 0.25, datetime.now(timezone.utc))
    provider._primary._cache["RELIANCE"] = api_price

    # Before fallback: primary price is returned
    assert provider.get_price("RELIANCE").price == 2195.75

    # After fallback: simulator price is returned
    provider._using_fallback = True
    assert provider.get_price("RELIANCE").price == 2400.0


# ── FallbackProvider: lifecycle ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_without_start_does_not_raise():
    provider = FallbackProvider("test-key")
    await provider.stop()  # Should not raise


@pytest.mark.asyncio
async def test_double_start_does_not_create_duplicate_monitor():
    provider = FallbackProvider("test-key")
    provider.set_tickers([])
    await provider.start()
    task_first = provider._monitor_task

    await provider.start()
    assert provider._monitor_task is task_first

    await provider.stop()


@pytest.mark.asyncio
async def test_monitor_task_is_none_after_stop():
    provider = FallbackProvider("test-key")
    provider.set_tickers([])
    await provider.start()
    await provider.stop()
    assert provider._monitor_task is None


@pytest.mark.asyncio
async def test_both_providers_stopped_on_stop():
    provider = FallbackProvider("test-key")
    provider.set_tickers([])
    await provider.start()

    assert provider._primary._task is not None
    assert provider._fallback._task is not None

    await provider.stop()

    assert provider._primary._task is None
    assert provider._fallback._task is None


# ── FallbackProvider: quota-exhaustion end-to-end ─────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fallback_triggered_by_429_via_poll_one():
    """Receiving a 429 via _poll_one → is_rate_limited → fallback switches."""
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(429))

    provider = FallbackProvider("test-key")
    provider.set_tickers(["RELIANCE"])

    async with httpx.AsyncClient() as client:
        await provider._primary._poll_one(client, "RELIANCE")

    assert provider._primary.is_rate_limited is True
    # Simulate the monitor check
    if not provider._using_fallback and provider._primary.is_rate_limited:
        provider._using_fallback = True

    assert provider.is_using_fallback is True


@pytest.mark.asyncio
async def test_fallback_triggered_by_quota_exhaustion():
    """Exhausting the monthly quota → is_rate_limited → fallback switches."""
    provider = FallbackProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    provider._primary._calls_this_month = MONTHLY_QUOTA

    assert provider._primary.is_rate_limited is True

    # Simulate the monitor check
    if not provider._using_fallback and provider._primary.is_rate_limited:
        provider._using_fallback = True

    assert provider.is_using_fallback is True
