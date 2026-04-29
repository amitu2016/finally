from datetime import datetime, timezone

import httpx
import pytest
import respx

from market.indian_api import (
    BASE_URL,
    IndianAPIProvider,
    _fetch_one,
    _parse_response,
)
from market.types import StockPrice

SAMPLE_RESPONSE = {
    "tickerId": "RELIANCE",
    "companyName": "Reliance Industries Limited",
    "currentPrice": {"NSE": 2195.75, "BSE": 2196.10},
    "percentChange": 1.25,
}


# ── _parse_response ──────────────────────────────────────────────────────────


def test_parse_nse_price():
    sp = _parse_response("RELIANCE", SAMPLE_RESPONSE, prev=None)
    assert sp is not None
    assert sp.ticker == "RELIANCE"
    assert sp.price == 2195.75
    assert sp.change_pct == 1.25
    assert sp.company_name == "Reliance Industries Limited"


def test_parse_falls_back_to_bse_when_nse_none():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"NSE": None, "BSE": 2196.10}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is not None
    assert sp.price == 2196.10


def test_parse_falls_back_to_bse_when_nse_missing():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"BSE": 2196.10}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is not None
    assert sp.price == 2196.10


def test_parse_returns_none_on_missing_current_price():
    data = {**SAMPLE_RESPONSE, "currentPrice": {}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is None


def test_parse_returns_none_when_current_price_absent():
    data = {"tickerId": "RELIANCE", "companyName": "Reliance"}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is None


def test_parse_returns_none_on_zero_price():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"NSE": 0, "BSE": 0}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is None


def test_parse_returns_none_on_negative_price():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"NSE": -10.0}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is None


def test_parse_prev_price_from_cache():
    prev = StockPrice("RELIANCE", 2190.0, 2185.0, 0.5, datetime.now(timezone.utc))
    sp = _parse_response("RELIANCE", SAMPLE_RESPONSE, prev=prev)
    assert sp.prev_price == 2190.0


def test_parse_prev_price_equals_price_when_no_prev():
    sp = _parse_response("RELIANCE", SAMPLE_RESPONSE, prev=None)
    assert sp.prev_price == sp.price


def test_parse_ticker_uses_parameter_not_response():
    sp = _parse_response("MYKEY", SAMPLE_RESPONSE, prev=None)
    assert sp.ticker == "MYKEY"


def test_parse_missing_percent_change_defaults_to_zero():
    data = {k: v for k, v in SAMPLE_RESPONSE.items() if k != "percentChange"}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp.change_pct == 0.0


def test_parse_missing_company_name_defaults_to_empty():
    data = {k: v for k, v in SAMPLE_RESPONSE.items() if k != "companyName"}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp.company_name == ""


def test_parse_timestamp_is_utc():
    sp = _parse_response("RELIANCE", SAMPLE_RESPONSE, prev=None)
    assert sp.timestamp.tzinfo is not None


# ── _fetch_one ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fetch_one_success():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    async with httpx.AsyncClient() as client:
        result = await _fetch_one(client, "RELIANCE", "test-key")
    assert result["tickerId"] == "RELIANCE"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_one_raises_on_404():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await _fetch_one(client, "UNKNOWN", "test-key")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_one_raises_on_429():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(429))
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await _fetch_one(client, "RELIANCE", "test-key")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_one_sends_api_key_header():
    route = respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    async with httpx.AsyncClient() as client:
        await _fetch_one(client, "RELIANCE", "my-secret-key")
    assert route.calls[0].request.headers["X-Api-Key"] == "my-secret-key"


# ── IndianAPIProvider: data access ──────────────────────────────────────────


def test_get_price_none_before_poll():
    provider = IndianAPIProvider("test-key")
    assert provider.get_price("RELIANCE") is None


def test_get_all_prices_empty_before_poll():
    provider = IndianAPIProvider("test-key")
    assert provider.get_all_prices() == {}


def test_get_history_empty_before_poll():
    provider = IndianAPIProvider("test-key")
    assert provider.get_history("RELIANCE") == []


def test_set_tickers_updates_list():
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE", "TCS"])
    assert set(provider._tickers) == {"RELIANCE", "TCS"}


def test_get_all_prices_returns_copy():
    provider = IndianAPIProvider("test-key")
    p1 = provider.get_all_prices()
    p2 = provider.get_all_prices()
    assert p1 is not p2


# ── IndianAPIProvider: cache update via _poll_all ────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_populates_cache():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    async with httpx.AsyncClient() as client:
        await provider._poll_all(client)

    sp = provider.get_price("RELIANCE")
    assert sp is not None
    assert sp.price == 2195.75
    assert sp.company_name == "Reliance Industries Limited"


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_skips_failed_ticker():
    respx.get(f"{BASE_URL}/stock", params={"name": "RELIANCE"}).mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    respx.get(f"{BASE_URL}/stock", params={"name": "TCS"}).mock(
        return_value=httpx.Response(500)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE", "TCS"])
    async with httpx.AsyncClient() as client:
        await provider._poll_all(client)

    assert provider.get_price("RELIANCE") is not None
    assert provider.get_price("TCS") is None  # failed poll, no cache entry


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_retains_stale_cache_on_error():
    stale = StockPrice("TCS", 3440.0, 3430.0, 0.3, datetime.now(timezone.utc), "TCS")
    provider = IndianAPIProvider("test-key")
    provider._cache["TCS"] = stale
    provider.set_tickers(["TCS"])

    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as client:
        await provider._poll_all(client)

    assert provider.get_price("TCS").price == 3440.0


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_accumulates_history():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])

    async with httpx.AsyncClient() as client:
        await provider._poll_all(client)
        await provider._poll_all(client)

    assert len(provider.get_history("RELIANCE")) == 2


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_caps_history_at_limit():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])

    async with httpx.AsyncClient() as client:
        for _ in range(210):
            await provider._poll_all(client)

    assert len(provider.get_history("RELIANCE")) == 200


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_skips_invalid_price_response():
    bad_response = {"tickerId": "RELIANCE", "currentPrice": {}}
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=bad_response)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])

    async with httpx.AsyncClient() as client:
        await provider._poll_all(client)

    assert provider.get_price("RELIANCE") is None


# ── IndianAPIProvider: async lifecycle ──────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_without_start():
    provider = IndianAPIProvider("test-key")
    await provider.stop()  # Should not raise


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    provider = IndianAPIProvider("test-key")
    provider.set_tickers([])
    await provider.start()
    await provider.stop()
    await provider.stop()  # Should not raise


# ── _parse_response: defensive numeric parsing ──────────────────────────────


def test_parse_returns_none_on_string_price():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"NSE": "not-a-number"}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is None


def test_parse_returns_none_on_dict_price():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"NSE": {"nested": "object"}}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is None


def test_parse_accepts_string_encoded_number():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"NSE": "2195.75"}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is not None
    assert sp.price == 2195.75


# ── IndianAPIProvider: set_tickers prunes stale state ───────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_set_tickers_prunes_stale_cache():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE", "TCS"])
    async with httpx.AsyncClient() as client:
        await provider._poll_all(client)

    assert provider.get_price("RELIANCE") is not None

    provider.set_tickers(["TCS"])
    assert provider.get_price("RELIANCE") is None
    assert "RELIANCE" not in provider._cache


@pytest.mark.asyncio
@respx.mock
async def test_set_tickers_prunes_stale_history():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    async with httpx.AsyncClient() as client:
        await provider._poll_all(client)
        await provider._poll_all(client)

    assert len(provider.get_history("RELIANCE")) > 0

    provider.set_tickers([])
    assert provider.get_history("RELIANCE") == []
    assert "RELIANCE" not in provider._history


def test_set_tickers_keeps_retained_cache():
    provider = IndianAPIProvider("test-key")
    provider._cache["TCS"] = StockPrice("TCS", 3440.0, 3430.0, 0.3, datetime.now(timezone.utc))
    provider.set_tickers(["TCS", "RELIANCE"])
    provider.set_tickers(["TCS"])
    assert provider.get_price("TCS") is not None


# ── IndianAPIProvider: double-start guard ────────────────────────────────────


@pytest.mark.asyncio
async def test_double_start_does_not_create_duplicate_task():
    provider = IndianAPIProvider("test-key")
    provider.set_tickers([])

    await provider.start()
    task_first = provider._task

    await provider.start()
    assert provider._task is task_first

    await provider.stop()


@pytest.mark.asyncio
async def test_task_is_none_after_stop():
    provider = IndianAPIProvider("test-key")
    provider.set_tickers([])
    await provider.start()
    await provider.stop()
    assert provider._task is None


@pytest.mark.asyncio
async def test_restart_after_stop_creates_new_task():
    provider = IndianAPIProvider("test-key")
    provider.set_tickers([])

    await provider.start()
    await provider.stop()
    assert provider._task is None

    await provider.start()
    assert provider._task is not None
    assert not provider._task.done()

    await provider.stop()


# ── IndianAPIProvider: _poll_all success count ───────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_returns_success_count():
    respx.get(f"{BASE_URL}/stock", params={"name": "RELIANCE"}).mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    respx.get(f"{BASE_URL}/stock", params={"name": "TCS"}).mock(
        return_value=httpx.Response(500)
    )
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE", "TCS"])
    async with httpx.AsyncClient() as client:
        count = await provider._poll_all(client)

    assert count == 1


@pytest.mark.asyncio
@respx.mock
async def test_poll_all_returns_zero_on_all_failures():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(503))
    provider = IndianAPIProvider("test-key")
    provider.set_tickers(["RELIANCE"])
    async with httpx.AsyncClient() as client:
        count = await provider._poll_all(client)

    assert count == 0
