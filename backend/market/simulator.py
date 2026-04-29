import asyncio
import math
import random
from datetime import datetime, timezone

from .base import MarketDataProvider
from .types import StockPrice

SEED_PRICES: dict[str, float] = {
    "RELIANCE":   2450.00,
    "TCS":        3450.00,
    "HDFCBANK":   1580.00,
    "INFY":       1560.00,
    "ICICIBANK":   950.00,
    "BHARTIARTL":  850.00,
    "SBIN":        600.00,
    "ITC":         420.00,
    "LT":         3200.00,
    "HINDUNILVR": 2300.00,
}

TICKER_VOL: dict[str, float] = {
    "RELIANCE":   0.22,
    "TCS":        0.20,
    "HDFCBANK":   0.24,
    "INFY":       0.26,
    "ICICIBANK":  0.28,
    "BHARTIARTL": 0.30,
    "SBIN":       0.32,
    "ITC":        0.18,
    "LT":         0.25,
    "HINDUNILVR": 0.18,
}

DEFAULT_VOL = 0.25
DEFAULT_SEED = 1000.0

TICK_INTERVAL = 0.5
TRADING_DAYS_PER_YEAR = 252
HOURS_PER_TRADING_DAY = 6.5
SECONDS_PER_TRADING_YEAR = TRADING_DAYS_PER_YEAR * HOURS_PER_TRADING_DAY * 3600
DT = TICK_INTERVAL / SECONDS_PER_TRADING_YEAR

EVENT_PROBABILITY = TICK_INTERVAL / 60
EVENT_MAGNITUDE_MIN = 0.02
EVENT_MAGNITUDE_MAX = 0.05

HISTORY_LIMIT = 200


def gbm_step(price: float, vol: float, drift: float = 0.0) -> float:
    """Apply one GBM tick and return the new price."""
    z = random.gauss(0.0, 1.0)
    exponent = (drift - 0.5 * vol**2) * DT + vol * math.sqrt(DT) * z
    return price * math.exp(exponent)


def maybe_apply_event(price: float) -> float:
    """Randomly apply a ±2–5% jump (~once per 60s per ticker)."""
    if random.random() > EVENT_PROBABILITY:
        return price
    direction = random.choice([-1, 1])
    magnitude = random.uniform(EVENT_MAGNITUDE_MIN, EVENT_MAGNITUDE_MAX)
    return price * (1.0 + direction * magnitude)


class SimulatorProvider(MarketDataProvider):

    def __init__(self) -> None:
        self._tickers: list[str] = []
        self._cache: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._simulate_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return dict(self._cache)

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return list(self._history.get(ticker, []))[-limit:]

    def set_tickers(self, tickers: list[str]) -> None:
        removed = set(self._tickers) - set(tickers)
        for ticker in removed:
            self._cache.pop(ticker, None)
            self._history.pop(ticker, None)

        now = datetime.now(timezone.utc)
        for ticker in tickers:
            if ticker not in self._cache:
                seed = SEED_PRICES.get(ticker, DEFAULT_SEED)
                self._cache[ticker] = StockPrice(
                    ticker=ticker,
                    price=seed,
                    prev_price=seed,
                    change_pct=0.0,
                    timestamp=now,
                )
        self._tickers = list(tickers)

    async def _simulate_loop(self) -> None:
        while True:
            self._tick()
            await asyncio.sleep(TICK_INTERVAL)

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        for ticker in self._tickers:
            prev = self._cache.get(ticker)
            if prev is None:
                continue

            vol = TICKER_VOL.get(ticker, DEFAULT_VOL)
            new_price = gbm_step(prev.price, vol)
            new_price = maybe_apply_event(new_price)
            new_price = round(new_price, 2)

            seed = SEED_PRICES.get(ticker, prev.price)
            change_pct = round((new_price - seed) / seed * 100, 2)

            sp = StockPrice(
                ticker=ticker,
                price=new_price,
                prev_price=prev.price,
                change_pct=change_pct,
                timestamp=now,
                company_name=prev.company_name,
            )
            self._cache[ticker] = sp
            buf = self._history.setdefault(ticker, [])
            buf.append(sp)
            if len(buf) > HISTORY_LIMIT:
                self._history[ticker] = buf[-HISTORY_LIMIT:]
