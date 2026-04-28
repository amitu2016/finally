# Market Data Interface — Design

This document defines the unified Python interface for market data in FinAlly. The interface is identical whether the backend uses the live IndianAPI.in service or the built-in simulator. All downstream code (SSE streaming, price cache, portfolio snapshots) depends only on this interface.

---

## Selection Logic

```
INDIAN_STOCK_API_KEY set?
    yes  →  IndianAPIProvider  (real market data)
    no   →  SimulatorProvider  (GBM-based mock data)
```

This mirrors the `USE_REAL_MARKET_DATA` env-var design described in PLAN.md. The factory function reads the key from the environment at startup; no other code path selects the provider.

---

## Core Data Type

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StockPrice:
    ticker: str           # NSE symbol, e.g. "RELIANCE"
    price: float          # Current price in INR
    prev_price: float     # Price from the previous tick (for flash direction)
    change_pct: float     # % change from previous session close
    timestamp: datetime   # UTC time of this reading
    company_name: str = ""  # Optional; populated when available
```

Both providers always return `StockPrice`. Downstream code never inspects the raw API response.

---

## Abstract Interface

```python
from abc import ABC, abstractmethod

class MarketDataProvider(ABC):

    @abstractmethod
    async def start(self) -> None:
        """Start background polling / simulation loop."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the background loop."""

    @abstractmethod
    def get_price(self, ticker: str) -> StockPrice | None:
        """Return the latest cached price, or None if not yet available."""

    @abstractmethod
    def get_all_prices(self) -> dict[str, StockPrice]:
        """Return the latest cached price for every tracked ticker."""

    @abstractmethod
    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        """Return the rolling price history (newest last)."""

    @abstractmethod
    def set_tickers(self, tickers: list[str]) -> None:
        """Replace the set of tracked tickers (called when watchlist changes)."""
```

---

## IndianAPIProvider

Polls `GET /stock?name=<ticker>` for each tracked ticker every 15 seconds using `asyncio.gather`.

```python
import asyncio
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://stock.indianapi.in"
POLL_INTERVAL = 15  # seconds


class IndianAPIProvider(MarketDataProvider):

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._tickers: list[str] = []
        self._cache: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}
        self._task: asyncio.Task | None = None

    def set_tickers(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return dict(self._cache)

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return list(self._history.get(ticker, []))[-limit:]

    async def _poll_loop(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            while True:
                if self._tickers:
                    await self._poll_all(client)
                await asyncio.sleep(POLL_INTERVAL)

    async def _poll_all(self, client: httpx.AsyncClient) -> None:
        tasks = [self._fetch_one(client, t) for t in self._tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ticker, result in zip(self._tickers, results):
            if isinstance(result, Exception):
                logger.warning("poll failed for %s: %s", ticker, result)
                continue
            self._update_cache(ticker, result)

    async def _fetch_one(self, client: httpx.AsyncClient, ticker: str) -> dict:
        resp = await client.get(
            f"{BASE_URL}/stock",
            params={"name": ticker},
            headers={"X-Api-Key": self._api_key},
        )
        resp.raise_for_status()
        return resp.json()

    def _update_cache(self, ticker: str, data: dict) -> None:
        prev = self._cache.get(ticker)
        raw_price = data.get("currentPrice", {})
        price = float(raw_price.get("NSE") or raw_price.get("BSE") or 0)
        if price == 0:
            return

        sp = StockPrice(
            ticker=ticker,
            price=price,
            prev_price=prev.price if prev else price,
            change_pct=float(data.get("percentChange") or 0),
            timestamp=datetime.now(timezone.utc),
            company_name=data.get("companyName", ""),
        )
        self._cache[ticker] = sp
        self._history.setdefault(ticker, []).append(sp)
        # Keep only the last 200 points
        if len(self._history[ticker]) > 200:
            self._history[ticker] = self._history[ticker][-200:]
```

---

## SimulatorProvider

Generates realistic INR prices using Geometric Brownian Motion at ~500ms intervals. See `MARKET_SIMULATOR.md` for algorithm details.

```python
class SimulatorProvider(MarketDataProvider):

    def __init__(self) -> None:
        self._tickers: list[str] = []
        self._cache: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}
        self._task: asyncio.Task | None = None

    def set_tickers(self, tickers: list[str]) -> None:
        # Initialize new tickers with seed prices; preserve existing ones
        for t in tickers:
            if t not in self._cache:
                seed = SEED_PRICES.get(t, 1000.0)
                now = datetime.now(timezone.utc)
                self._cache[t] = StockPrice(
                    ticker=t, price=seed, prev_price=seed,
                    change_pct=0.0, timestamp=now,
                )
        self._tickers = list(tickers)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._simulate_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return dict(self._cache)

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return list(self._history.get(ticker, []))[-limit:]

    async def _simulate_loop(self) -> None:
        while True:
            self._tick()
            await asyncio.sleep(0.5)

    def _tick(self) -> None:
        # Implementation described in MARKET_SIMULATOR.md
        ...
```

---

## Factory Function

```python
import os

def create_market_provider() -> MarketDataProvider:
    api_key = os.getenv("INDIAN_STOCK_API_KEY")
    if api_key:
        return IndianAPIProvider(api_key)
    return SimulatorProvider()
```

Called once during FastAPI startup (lifespan). The returned provider is held as application state and shared across all request handlers.

---

## Integration with FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    provider = create_market_provider()
    provider.set_tickers(load_watchlist_from_db())
    await provider.start()
    app.state.market = provider
    yield
    await provider.stop()

app = FastAPI(lifespan=lifespan)
```

---

## SSE Streaming

The SSE endpoint reads from the provider on a timer and pushes price updates:

```python
import asyncio
import json
from fastapi import Request
from fastapi.responses import StreamingResponse

async def price_stream(request: Request):
    provider: MarketDataProvider = request.app.state.market

    async def event_generator():
        while not await request.is_disconnected():
            prices = provider.get_all_prices()
            for ticker, sp in prices.items():
                payload = {
                    "ticker": sp.ticker,
                    "price": sp.price,
                    "prev_price": sp.prev_price,
                    "change_pct": sp.change_pct,
                    "timestamp": sp.timestamp.isoformat(),
                    "direction": "up" if sp.price >= sp.prev_price else "down",
                }
                yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Watchlist Changes

When the user adds or removes a ticker (via `POST /api/watchlist` or `DELETE /api/watchlist/{ticker}`), call `provider.set_tickers(new_list)` immediately. The SSE loop picks up the new ticker within one tick — no client reconnect required.

```python
@app.post("/api/watchlist")
async def add_ticker(body: AddTickerRequest, request: Request):
    # ... persist to DB ...
    tickers = load_watchlist_from_db()
    request.app.state.market.set_tickers(tickers)
    return {"ok": True}
```

---

## SSE Event Shape (frontend contract)

```json
{
  "ticker": "RELIANCE",
  "price": 2195.75,
  "prev_price": 2190.30,
  "change_pct": 1.25,
  "timestamp": "2024-06-27T06:30:00.123456+00:00",
  "direction": "up"
}
```

This shape is identical regardless of which provider is active. The frontend never knows whether it is receiving simulated or real data.
