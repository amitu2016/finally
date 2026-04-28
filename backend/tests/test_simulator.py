import asyncio
from datetime import timezone

import pytest

from market.simulator import (
    DEFAULT_SEED,
    DT,
    HISTORY_LIMIT,
    SEED_PRICES,
    TICKER_VOL,
    SimulatorProvider,
    gbm_step,
    maybe_apply_event,
)
from market.types import StockPrice


# ── GBM helpers ──────────────────────────────────────────────────────────────


def test_gbm_step_always_positive():
    for _ in range(2000):
        assert gbm_step(100.0, 0.25) > 0


def test_gbm_step_produces_different_values():
    prices = {gbm_step(1000.0, 0.30) for _ in range(50)}
    assert len(prices) > 1


def test_gbm_step_zero_vol_changes_slightly():
    # With zero vol, GBM degenerates to deterministic drift (drift=0 → no change expected)
    prices = [gbm_step(500.0, 0.0) for _ in range(10)]
    for p in prices:
        assert abs(p - 500.0) < 1e-6


def test_gbm_step_high_vol_larger_spread():
    low_vol = [gbm_step(1000.0, 0.01) for _ in range(500)]
    high_vol = [gbm_step(1000.0, 1.00) for _ in range(500)]
    low_spread = max(low_vol) - min(low_vol)
    high_spread = max(high_vol) - min(high_vol)
    assert high_spread > low_spread


def test_maybe_apply_event_returns_positive():
    for _ in range(1000):
        assert maybe_apply_event(1000.0) > 0


def test_maybe_apply_event_within_bounds():
    # Events can only change price by at most 5%
    for _ in range(5000):
        result = maybe_apply_event(1000.0)
        assert 940.0 < result < 1060.0


# ── SimulatorProvider: set_tickers / get_price ───────────────────────────────


def test_seed_prices_initialised_correctly():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE", "TCS"])
    assert provider.get_price("RELIANCE").price == SEED_PRICES["RELIANCE"]
    assert provider.get_price("TCS").price == SEED_PRICES["TCS"]


def test_unknown_ticker_uses_default_seed():
    provider = SimulatorProvider()
    provider.set_tickers(["XYZCORP"])
    sp = provider.get_price("XYZCORP")
    assert sp is not None
    assert sp.price == DEFAULT_SEED


def test_get_price_none_for_untracked_ticker():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    assert provider.get_price("TCS") is None


def test_set_tickers_preserves_existing_cache():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    provider._cache["RELIANCE"].price  # confirm it exists

    # Now add a second ticker without losing the first
    provider.set_tickers(["RELIANCE", "TCS"])
    assert provider.get_price("RELIANCE") is not None
    assert provider.get_price("TCS") is not None


def test_set_tickers_updates_ticker_list():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE", "TCS"])
    assert set(provider._tickers) == {"RELIANCE", "TCS"}

    provider.set_tickers(["INFY"])
    assert provider._tickers == ["INFY"]


def test_get_all_prices_returns_all_tracked():
    provider = SimulatorProvider()
    tickers = ["RELIANCE", "TCS", "INFY"]
    provider.set_tickers(tickers)
    prices = provider.get_all_prices()
    assert set(prices.keys()) == set(tickers)


def test_get_all_prices_returns_copy():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    prices1 = provider.get_all_prices()
    prices2 = provider.get_all_prices()
    assert prices1 is not prices2


# ── SimulatorProvider: initial StockPrice fields ─────────────────────────────


def test_initial_price_fields():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    sp = provider.get_price("RELIANCE")
    assert sp.ticker == "RELIANCE"
    assert sp.price == sp.prev_price == SEED_PRICES["RELIANCE"]
    assert sp.change_pct == 0.0
    assert sp.timestamp.tzinfo is not None


# ── SimulatorProvider: history ────────────────────────────────────────────────


def test_history_empty_before_tick():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    assert provider.get_history("RELIANCE") == []


def test_history_accumulates_after_ticks():
    provider = SimulatorProvider()
    provider.set_tickers(["TCS"])
    provider._tick()
    provider._tick()
    history = provider.get_history("TCS")
    assert len(history) == 2


def test_history_capped_at_limit():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    for _ in range(HISTORY_LIMIT + 50):
        provider._tick()
    assert len(provider.get_history("RELIANCE")) == HISTORY_LIMIT


def test_history_newest_matches_cache():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    provider._tick()
    history = provider.get_history("RELIANCE")
    cached = provider.get_price("RELIANCE")
    assert history[-1].price == cached.price


def test_history_limit_param():
    provider = SimulatorProvider()
    provider.set_tickers(["TCS"])
    for _ in range(20):
        provider._tick()
    assert len(provider.get_history("TCS", limit=5)) == 5


def test_get_history_returns_empty_for_untracked():
    provider = SimulatorProvider()
    assert provider.get_history("UNKNOWN") == []


# ── SimulatorProvider: tick logic ─────────────────────────────────────────────


def test_tick_updates_price():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    before = provider.get_price("RELIANCE").price
    provider._tick()
    after = provider.get_price("RELIANCE").price
    # Astronomically unlikely to be identical
    assert after != before


def test_tick_sets_prev_price():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    first = provider.get_price("RELIANCE").price
    provider._tick()
    sp = provider.get_price("RELIANCE")
    assert sp.prev_price == first


def test_tick_change_pct_calculation():
    provider = SimulatorProvider()
    provider.set_tickers(["ITC"])
    provider._tick()
    sp = provider.get_price("ITC")
    expected = round((sp.price - SEED_PRICES["ITC"]) / SEED_PRICES["ITC"] * 100, 2)
    assert sp.change_pct == expected


def test_tick_skips_unknown_cache_entry():
    provider = SimulatorProvider()
    # Add a ticker to the list but NOT to the cache — should not raise
    provider._tickers = ["GHOST"]
    provider._tick()  # should not raise


# ── SimulatorProvider: async lifecycle ────────────────────────────────────────


@pytest.mark.asyncio
async def test_prices_update_after_async_tick():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    initial = provider.get_price("RELIANCE").price

    await provider.start()
    await asyncio.sleep(0.6)
    await provider.stop()

    updated = provider.get_price("RELIANCE").price
    assert updated != initial


@pytest.mark.asyncio
async def test_history_accumulates_async():
    provider = SimulatorProvider()
    provider.set_tickers(["TCS"])

    await provider.start()
    await asyncio.sleep(1.1)
    await provider.stop()

    history = provider.get_history("TCS")
    assert len(history) >= 2
    assert history[-1].price == provider.get_price("TCS").price


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    await provider.start()
    await provider.stop()
    await provider.stop()  # Should not raise


@pytest.mark.asyncio
async def test_stop_without_start():
    provider = SimulatorProvider()
    await provider.stop()  # Should not raise


# ── DT constant ───────────────────────────────────────────────────────────────


def test_dt_is_small_positive():
    assert 0 < DT < 1e-4


def test_all_ticker_vols_present():
    for ticker in SEED_PRICES:
        assert ticker in TICKER_VOL
