# Market Data Backend — Implementation Design

This document provides the complete implementation design for FinAlly's market data backend. It covers the unified interface, the GBM simulator, the IndianAPI.in client, the price cache, SSE streaming, and FastAPI integration — all with runnable code snippets.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI Application                                    │
│                                                         │
│  lifespan()                                             │
│    └── create_market_provider()  ← env var selection   │
│          ├── SimulatorProvider   (default)              │
│          └── IndianAPIProvider   (INDIAN_STOCK_API_KEY) │
│                                                         │
│  app.state.market = provider                            │
│                                                         │
│  GET /api/stream/prices  ──── reads provider cache      │
│  GET /api/prices/{ticker}/history ── reads history buf  │
│  POST/DELETE /api/watchlist ──── calls set_tickers()    │
└─────────────────────────────────────────────────────────┘
```

### Provider Selection

```
INDIAN_STOCK_API_KEY set in environment?
    yes  →  IndianAPIProvider  (polls https://stock.indianapi.in every 15s)
    no   →  SimulatorProvider  (GBM in-process loop at 500ms cadence)
```

Both providers implement an identical `MarketDataProvider` interface. All downstream code (SSE, portfolio snapshots, REST endpoints) is completely agnostic to which provider is running.

---

## 2. Core Data Types

All market data flows through a single shared dataclass. Place this in `backend/market/types.py`:

```python
# backend/market/types.py
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StockPrice:
    ticker: str          # NSE symbol, e.g. "RELIANCE"
    price: float         # Current price in INR
    prev_price: float    # Price from the previous tick (for flash direction)
    change_pct: float    # % change from previous session close (or seed)
    timestamp: datetime  # UTC time of this reading
    company_name: str = field(default="")  # Populated by IndianAPIProvider; empty in simulator
```

**Usage example:**

```python
from backend.market.types import StockPrice
from datetime import datetime, timezone

sp = StockPrice(
    ticker="TCS",
    price=3452.50,
    prev_price=3448.20,
    change_pct=0.12,
    timestamp=datetime.now(timezone.utc),
    company_name="Tata Consultancy Services",
)

direction = "up" if sp.price >= sp.prev_price else "down"
print(f"{sp.ticker}: ₹{sp.price:.2f} ({direction})")
# TCS: ₹3452.50 (up)
```

---

## 3. Abstract Interface

All providers implement this interface. Place in `backend/market/base.py`:

```python
# backend/market/base.py
from abc import ABC, abstractmethod
from .types import StockPrice


class MarketDataProvider(ABC):

    @abstractmethod
    async def start(self) -> None:
        """Start the background polling/simulation loop."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the background loop."""

    @abstractmethod
    def get_price(self, ticker: str) -> StockPrice | None:
        """Return the latest cached price, or None if not yet available."""

    @abstractmethod
    def get_all_prices(self) -> dict[str, StockPrice]:
        """Return a snapshot of the latest cached price for every tracked ticker."""

    @abstractmethod
    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        """Return the rolling price history for a ticker (oldest first, newest last)."""

    @abstractmethod
    def set_tickers(self, tickers: list[str]) -> None:
        """
        Replace the full set of tracked tickers.
        Called at startup and whenever the watchlist changes.
        Must be safe to call from a synchronous context (no await).
        """
```

---

## 4. Simulator Provider

The simulator generates realistic INR prices using Geometric Brownian Motion (GBM). It runs entirely in-process — no external API calls, no network dependency.

### 4.1 GBM Algorithm

The discrete GBM update applied at each 500ms tick:

```
S(t + dt) = S(t) * exp( (μ - σ²/2) * dt  +  σ * √dt * Z )
```

- `S(t)` — current price
- `μ` — drift (annualised). Set to `0.0` for no secular trend
- `σ` — annualised volatility (per ticker)
- `dt` — time step in years: `0.5 / (252 × 6.5 × 3600)` at 500ms cadence
- `Z` — standard normal random variable, freshly drawn each tick

**Why GBM?** Log-normal increments prevent negative prices, match the standard Black-Scholes / quant finance model, and produce realistic-looking candlestick charts with minimal code.

### 4.2 Seed Prices and Per-Ticker Volatility

```python
# backend/market/simulator.py  (constants section)

SEED_PRICES: dict[str, float] = {
    "RELIANCE":    2450.00,
    "TCS":         3450.00,
    "HDFCBANK":    1580.00,
    "INFY":        1560.00,
    "ICICIBANK":    950.00,
    "BHARTIARTL":   850.00,
    "SBIN":         600.00,
    "ITC":          420.00,
    "LT":          3200.00,
    "HINDUNILVR":  2300.00,
}

# Annualised volatility per ticker (as a fraction, not percent)
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

DEFAULT_VOL = 0.25   # fallback for unknown/user-added tickers
DEFAULT_SEED = 1000.0
```

Unknown tickers (added by the user at runtime) are initialised at ₹1,000 with 25% annualised vol. The app remains fully functional for any NSE ticker.

### 4.3 GBM Step Function

```python
# backend/market/simulator.py

import math
import random

TICK_INTERVAL = 0.5                               # seconds
TRADING_DAYS_PER_YEAR = 252
HOURS_PER_TRADING_DAY = 6.5
SECONDS_PER_TRADING_YEAR = TRADING_DAYS_PER_YEAR * HOURS_PER_TRADING_DAY * 3600
DT = TICK_INTERVAL / SECONDS_PER_TRADING_YEAR    # ~8.5e-8 years


def gbm_step(price: float, vol: float, drift: float = 0.0) -> float:
    """Apply one GBM tick. Returns the new price."""
    z = random.gauss(0.0, 1.0)
    exponent = (drift - 0.5 * vol ** 2) * DT + vol * math.sqrt(DT) * z
    return price * math.exp(exponent)
```

### 4.4 Random Events

Occasional large moves (±2–5%) make simulated data feel alive:

```python
EVENT_PROBABILITY = TICK_INTERVAL / 60   # ~0.0083 per tick ≈ once per 60s per ticker
EVENT_MIN = 0.02
EVENT_MAX = 0.05


def maybe_apply_event(price: float) -> float:
    """Randomly apply a ±2-5% jump. Returns (possibly unchanged) price."""
    if random.random() > EVENT_PROBABILITY:
        return price
    direction = random.choice([-1, 1])
    magnitude = random.uniform(EVENT_MIN, EVENT_MAX)
    return price * (1.0 + direction * magnitude)
```

### 4.5 Full SimulatorProvider Class

```python
# backend/market/simulator.py

import asyncio
from datetime import datetime, timezone

from .base import MarketDataProvider
from .types import StockPrice


class SimulatorProvider(MarketDataProvider):

    def __init__(self) -> None:
        self._tickers: list[str] = []
        self._cache: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}
        self._task: asyncio.Task | None = None

    # ── Interface: lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        self._task = asyncio.create_task(self._simulate_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── Interface: data access ────────────────────────────────────────────

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return dict(self._cache)

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return list(self._history.get(ticker, []))[-limit:]

    def set_tickers(self, tickers: list[str]) -> None:
        """Initialise new tickers at their seed price; preserve existing state."""
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

    # ── Internal simulation loop ──────────────────────────────────────────

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
            if len(buf) > 200:
                self._history[ticker] = buf[-200:]
```

### 4.6 Stretch Goal — Correlated Moves

A single shared market factor `Z_market` drawn per tick makes sector stocks move together (IT stocks: TCS + INFY; banking: HDFCBANK + ICICIBANK + SBIN):

```python
BETA = 0.5  # fraction of variance explained by the market factor


def gbm_step_correlated(price: float, vol: float, z_market: float) -> float:
    z_idio = random.gauss(0.0, 1.0)
    # Blend: β * market shock + √(1-β²) * idiosyncratic shock
    z = BETA * z_market + math.sqrt(1.0 - BETA ** 2) * z_idio
    exponent = (-0.5 * vol ** 2) * DT + vol * math.sqrt(DT) * z
    return price * math.exp(exponent)


# In _tick(), draw z_market once per tick and pass it to each ticker's step:
def _tick_correlated(self) -> None:
    z_market = random.gauss(0.0, 1.0)
    now = datetime.now(timezone.utc)
    for ticker in self._tickers:
        prev = self._cache.get(ticker)
        if prev is None:
            continue
        vol = TICKER_VOL.get(ticker, DEFAULT_VOL)
        new_price = gbm_step_correlated(prev.price, vol, z_market)
        new_price = maybe_apply_event(new_price)
        # ... rest unchanged
```

---

## 5. Indian Stock API Provider

Polls `GET https://stock.indianapi.in/stock?name=<ticker>` concurrently for all tracked tickers every 15 seconds.

### 5.1 API Overview

| Item | Detail |
|---|---|
| Base URL | `https://stock.indianapi.in` |
| Auth | `X-Api-Key: <INDIAN_STOCK_API_KEY>` header |
| Key endpoint | `GET /stock?name=<ticker>` |
| Poll interval | 15 seconds (well within rate limits) |
| Fields used | `currentPrice.NSE`, `currentPrice.BSE`, `percentChange`, `tickerId`, `companyName` |
| Market hours | 9:15 AM – 3:30 PM IST, weekdays; API returns last known price when closed |

### 5.2 Response Shape

```json
{
  "tickerId": "RELIANCE",
  "companyName": "Reliance Industries Limited",
  "currentPrice": {
    "NSE": 2195.75,
    "BSE": 2196.10
  },
  "percentChange": 1.25,
  "yearHigh": 2400.00,
  "yearLow": 1800.00
}
```

Only `currentPrice.NSE` (falling back to `currentPrice.BSE` if NSE is null), `percentChange`, `tickerId`, and `companyName` are consumed. The rest is ignored.

### 5.3 Single-Ticker Fetch

```python
# backend/market/indian_api.py

import httpx

BASE_URL = "https://stock.indianapi.in"


async def _fetch_one(
    client: httpx.AsyncClient,
    ticker: str,
    api_key: str,
) -> dict:
    """Fetch raw JSON for a single ticker. Raises on non-200."""
    resp = await client.get(
        f"{BASE_URL}/stock",
        params={"name": ticker},
        headers={"X-Api-Key": api_key},
    )
    resp.raise_for_status()
    return resp.json()
```

### 5.4 Parsing the Response

```python
from datetime import datetime, timezone
from .types import StockPrice


def _parse_response(ticker: str, data: dict, prev: StockPrice | None) -> StockPrice | None:
    """
    Convert raw IndianAPI JSON to StockPrice.
    Returns None if no valid price is found (e.g. pre-market, bad data).
    """
    raw = data.get("currentPrice", {})
    # Prefer NSE price; fall back to BSE
    price_raw = raw.get("NSE") or raw.get("BSE")
    if not price_raw:
        return None

    price = float(price_raw)
    if price <= 0:
        return None

    return StockPrice(
        ticker=ticker,
        price=price,
        prev_price=prev.price if prev else price,
        change_pct=float(data.get("percentChange") or 0.0),
        timestamp=datetime.now(timezone.utc),
        company_name=data.get("companyName", ""),
    )
```

### 5.5 Full IndianAPIProvider Class

```python
# backend/market/indian_api.py

import asyncio
import logging

import httpx

from .base import MarketDataProvider
from .types import StockPrice

logger = logging.getLogger(__name__)

POLL_INTERVAL = 15  # seconds
REQUEST_TIMEOUT = 10.0  # seconds per ticker


class IndianAPIProvider(MarketDataProvider):

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._tickers: list[str] = []
        self._cache: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}
        self._task: asyncio.Task | None = None

    # ── Interface: lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── Interface: data access ────────────────────────────────────────────

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return dict(self._cache)

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return list(self._history.get(ticker, []))[-limit:]

    def set_tickers(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)

    # ── Internal polling loop ─────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            while True:
                if self._tickers:
                    await self._poll_all(client)
                await asyncio.sleep(POLL_INTERVAL)

    async def _poll_all(self, client: httpx.AsyncClient) -> None:
        """Fetch all tickers concurrently; log errors without crashing."""
        tasks = [_fetch_one(client, t, self._api_key) for t in self._tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for ticker, result in zip(self._tickers, results):
            if isinstance(result, Exception):
                logger.warning("IndianAPI poll failed for %s: %s", ticker, result)
                # Retain the last cached price — SSE stream continues uninterrupted
                continue

            prev = self._cache.get(ticker)
            sp = _parse_response(ticker, result, prev)
            if sp is None:
                logger.warning("IndianAPI: no valid price in response for %s", ticker)
                continue

            self._cache[ticker] = sp
            buf = self._history.setdefault(ticker, [])
            buf.append(sp)
            if len(buf) > 200:
                self._history[ticker] = buf[-200:]
```

### 5.6 Error Handling Matrix

| HTTP Status | Cause | Action |
|---|---|---|
| `200` | Success | Parse and update cache |
| `404` | Unknown ticker | Log warning; retain cached price |
| `429` | Rate limit exceeded | Log warning; retain cached price |
| `5xx` | Server error | Log warning; retain cached price |
| Network timeout | Connectivity issue | `asyncio.gather` captures as exception; retain cached price |

The SSE stream **never drops** due to a failed poll. On any error, `_poll_all` logs and skips the update for that ticker, keeping the last known price in cache.

---

## 6. Factory Function

The single entry point that selects the provider. Place in `backend/market/factory.py`:

```python
# backend/market/factory.py

import os

from .base import MarketDataProvider
from .indian_api import IndianAPIProvider
from .simulator import SimulatorProvider


def create_market_provider() -> MarketDataProvider:
    """
    Select the market data provider based on environment variables.

    - INDIAN_STOCK_API_KEY set  →  IndianAPIProvider (real NSE/BSE data)
    - INDIAN_STOCK_API_KEY absent  →  SimulatorProvider (GBM-based mock)
    """
    api_key = os.getenv("INDIAN_STOCK_API_KEY")
    if api_key:
        return IndianAPIProvider(api_key)
    return SimulatorProvider()
```

Called exactly once during FastAPI application startup.

---

## 7. FastAPI Integration

### 7.1 Lifespan — Startup and Shutdown

```python
# backend/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import load_watchlist_from_db, init_db
from .market.factory import create_market_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise database (creates tables + seeds default data if missing)
    init_db()

    # Create and start the market data provider
    provider = create_market_provider()
    tickers = load_watchlist_from_db()   # e.g. ["RELIANCE", "TCS", ...]
    provider.set_tickers(tickers)
    await provider.start()

    app.state.market = provider

    yield  # App is running

    # Graceful shutdown
    await provider.stop()


app = FastAPI(lifespan=lifespan)
```

### 7.2 Accessing the Provider in Route Handlers

```python
from fastapi import Request
from .market.base import MarketDataProvider


def get_market(request: Request) -> MarketDataProvider:
    return request.app.state.market


@app.get("/api/prices/{ticker}/history")
async def price_history(ticker: str, request: Request):
    provider = get_market(request)
    history = provider.get_history(ticker.upper(), limit=200)
    return [
        {
            "price": sp.price,
            "timestamp": sp.timestamp.isoformat(),
            "change_pct": sp.change_pct,
        }
        for sp in history
    ]
```

---

## 8. Price Cache

The in-memory price cache lives inside each provider instance as two dicts:

```python
self._cache: dict[str, StockPrice]          # ticker → latest StockPrice
self._history: dict[str, list[StockPrice]]  # ticker → rolling 200-point buffer
```

### Access Patterns

| Operation | Method | Notes |
|---|---|---|
| Latest price for one ticker | `get_price("RELIANCE")` | O(1) dict lookup |
| Snapshot of all tickers | `get_all_prices()` | Returns a shallow copy |
| Recent history for chart | `get_history("TCS", limit=200)` | Newest last |

### History Buffer Management

The rolling buffer is capped at 200 entries (~100 seconds at 500ms cadence):

```python
buf = self._history.setdefault(ticker, [])
buf.append(sp)
if len(buf) > 200:
    self._history[ticker] = buf[-200:]
```

This slicing approach is simple and correct. At only 200 items it is fast enough; if the buffer ever grows larger (e.g. if the cap is raised to 10,000), switch to `collections.deque(maxlen=200)` for O(1) appends and automatic eviction.

---

## 9. SSE Streaming Endpoint

### 9.1 Endpoint Implementation

```python
# backend/routes/stream.py

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..market.base import MarketDataProvider

router = APIRouter()

SSE_INTERVAL = 0.5  # seconds between pushes


@router.get("/api/stream/prices")
async def stream_prices(request: Request):
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
                    "company_name": sp.company_name,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(SSE_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable nginx buffering if behind a proxy
        },
    )
```

### 9.2 SSE Event Shape (Frontend Contract)

```json
{
  "ticker": "RELIANCE",
  "price": 2195.75,
  "prev_price": 2190.30,
  "change_pct": 1.25,
  "timestamp": "2024-06-27T06:30:00.123456+00:00",
  "direction": "up",
  "company_name": "Reliance Industries Limited"
}
```

This shape is **identical** regardless of which provider is active. The frontend never knows whether it is receiving simulated or real data.

### 9.3 Frontend SSE Connection (TypeScript)

```typescript
// frontend/lib/useMarketStream.ts

import { useEffect, useRef } from "react";

type PriceEvent = {
  ticker: string;
  price: number;
  prev_price: number;
  change_pct: number;
  timestamp: string;
  direction: "up" | "down";
};

export function useMarketStream(onPrice: (event: PriceEvent) => void) {
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const connect = () => {
      const es = new EventSource("/api/stream/prices");
      esRef.current = es;

      es.onmessage = (e) => {
        try {
          onPrice(JSON.parse(e.data) as PriceEvent);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        es.close();
        // EventSource has built-in reconnection, but we add a brief delay
        setTimeout(connect, 2000);
      };
    };

    connect();
    return () => esRef.current?.close();
  }, []);  // onPrice intentionally excluded — wrap in useCallback at callsite
}
```

---

## 10. Watchlist Sync

When the user adds or removes a ticker, the route handler persists to the database and immediately calls `set_tickers()`. The SSE loop picks up the new ticker within one 500ms tick — no client reconnect required.

```python
# backend/routes/watchlist.py

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..database import add_ticker_to_db, remove_ticker_from_db, load_watchlist_from_db

router = APIRouter()


class AddTickerRequest(BaseModel):
    ticker: str


@router.post("/api/watchlist")
async def add_ticker(body: AddTickerRequest, request: Request):
    ticker = body.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=422, detail="ticker is required")

    add_ticker_to_db(ticker)                             # persist to SQLite
    tickers = load_watchlist_from_db()                   # reload full list
    request.app.state.market.set_tickers(tickers)        # update provider

    return {"ok": True, "ticker": ticker}


@router.delete("/api/watchlist/{ticker}")
async def remove_ticker(ticker: str, request: Request):
    ticker = ticker.upper().strip()
    remove_ticker_from_db(ticker)

    tickers = load_watchlist_from_db()
    request.app.state.market.set_tickers(tickers)

    return {"ok": True, "ticker": ticker}


@router.get("/api/watchlist")
async def get_watchlist(request: Request):
    provider = request.app.state.market
    prices = provider.get_all_prices()
    # Return tickers even if no price cached yet
    tickers = load_watchlist_from_db()
    return [
        {
            "ticker": t,
            "price": prices[t].price if t in prices else None,
            "change_pct": prices[t].change_pct if t in prices else None,
            "direction": (
                "up" if t in prices and prices[t].price >= prices[t].prev_price
                else "down" if t in prices else None
            ),
            "company_name": prices[t].company_name if t in prices else "",
        }
        for t in tickers
    ]
```

---

## 11. Module Layout

```
backend/
├── main.py                  # FastAPI app, lifespan, router registration
├── database.py              # SQLite init, watchlist/portfolio helpers
├── market/
│   ├── __init__.py
│   ├── types.py             # StockPrice dataclass
│   ├── base.py              # MarketDataProvider ABC
│   ├── simulator.py         # SimulatorProvider + GBM helpers
│   ├── indian_api.py        # IndianAPIProvider + HTTP helpers
│   └── factory.py           # create_market_provider()
└── routes/
    ├── stream.py            # GET /api/stream/prices (SSE)
    ├── watchlist.py         # GET/POST/DELETE /api/watchlist
    ├── portfolio.py         # GET /api/portfolio, POST /api/portfolio/trade
    └── chat.py              # POST /api/chat
```

---

## 12. Testing

### 12.1 Unit Tests — Simulator

```python
# backend/tests/test_simulator.py

import asyncio
from datetime import timezone

import pytest

from backend.market.simulator import SimulatorProvider, SEED_PRICES, gbm_step, DT


def test_gbm_step_stays_positive():
    for _ in range(1000):
        p = gbm_step(100.0, 0.25)
        assert p > 0


def test_seed_prices_initialised():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE", "TCS"])
    assert provider.get_price("RELIANCE").price == SEED_PRICES["RELIANCE"]
    assert provider.get_price("TCS").price == SEED_PRICES["TCS"]


def test_unknown_ticker_gets_default_seed():
    provider = SimulatorProvider()
    provider.set_tickers(["XYZCORP"])
    assert provider.get_price("XYZCORP").price == 1000.0


@pytest.mark.asyncio
async def test_prices_update_after_tick():
    provider = SimulatorProvider()
    provider.set_tickers(["RELIANCE"])
    initial = provider.get_price("RELIANCE").price

    await provider.start()
    await asyncio.sleep(0.6)   # wait for at least one tick
    await provider.stop()

    updated = provider.get_price("RELIANCE").price
    # Prices must have changed (astronomically unlikely to be identical)
    assert updated != initial


@pytest.mark.asyncio
async def test_history_accumulates():
    provider = SimulatorProvider()
    provider.set_tickers(["TCS"])

    await provider.start()
    await asyncio.sleep(1.1)   # ~2 ticks
    await provider.stop()

    history = provider.get_history("TCS")
    assert len(history) >= 2
    # Newest entry matches the current cache
    assert history[-1].price == provider.get_price("TCS").price
```

### 12.2 Unit Tests — IndianAPI Response Parsing

```python
# backend/tests/test_indian_api.py

from backend.market.indian_api import _parse_response


SAMPLE_RESPONSE = {
    "tickerId": "RELIANCE",
    "companyName": "Reliance Industries Limited",
    "currentPrice": {"NSE": 2195.75, "BSE": 2196.10},
    "percentChange": 1.25,
}


def test_parse_nse_price():
    sp = _parse_response("RELIANCE", SAMPLE_RESPONSE, prev=None)
    assert sp is not None
    assert sp.ticker == "RELIANCE"
    assert sp.price == 2195.75
    assert sp.change_pct == 1.25
    assert sp.company_name == "Reliance Industries Limited"


def test_parse_falls_back_to_bse():
    data = {**SAMPLE_RESPONSE, "currentPrice": {"NSE": None, "BSE": 2196.10}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is not None
    assert sp.price == 2196.10


def test_parse_returns_none_on_missing_price():
    data = {**SAMPLE_RESPONSE, "currentPrice": {}}
    sp = _parse_response("RELIANCE", data, prev=None)
    assert sp is None


def test_prev_price_set_from_cache():
    from backend.market.types import StockPrice
    from datetime import datetime, timezone

    prev = StockPrice("RELIANCE", 2190.0, 2185.0, 0.5, datetime.now(timezone.utc))
    sp = _parse_response("RELIANCE", SAMPLE_RESPONSE, prev=prev)
    assert sp.prev_price == 2190.0
```

### 12.3 Unit Tests — Interface Conformance

```python
# backend/tests/test_market_interface.py
"""Verify both providers satisfy the MarketDataProvider contract."""

import pytest
from backend.market.simulator import SimulatorProvider
from backend.market.indian_api import IndianAPIProvider
from backend.market.base import MarketDataProvider


def test_simulator_is_provider():
    assert isinstance(SimulatorProvider(), MarketDataProvider)


def test_indian_api_is_provider():
    assert isinstance(IndianAPIProvider("fake-key"), MarketDataProvider)


@pytest.mark.parametrize("provider", [
    SimulatorProvider(),
    IndianAPIProvider("fake-key"),
])
def test_get_price_returns_none_before_set_tickers(provider):
    assert provider.get_price("RELIANCE") is None


@pytest.mark.parametrize("provider", [
    SimulatorProvider(),
    IndianAPIProvider("fake-key"),
])
def test_get_all_prices_returns_dict(provider):
    prices = provider.get_all_prices()
    assert isinstance(prices, dict)


@pytest.mark.parametrize("provider", [
    SimulatorProvider(),
    IndianAPIProvider("fake-key"),
])
def test_get_history_returns_list(provider):
    history = provider.get_history("RELIANCE")
    assert isinstance(history, list)
```

### 12.4 Factory Tests

```python
# backend/tests/test_factory.py

import os
import pytest

from backend.market.factory import create_market_provider
from backend.market.simulator import SimulatorProvider
from backend.market.indian_api import IndianAPIProvider


def test_factory_returns_simulator_without_key(monkeypatch):
    monkeypatch.delenv("INDIAN_STOCK_API_KEY", raising=False)
    provider = create_market_provider()
    assert isinstance(provider, SimulatorProvider)


def test_factory_returns_indian_api_with_key(monkeypatch):
    monkeypatch.setenv("INDIAN_STOCK_API_KEY", "test-key-123")
    provider = create_market_provider()
    assert isinstance(provider, IndianAPIProvider)
```

---

## 13. Key Design Decisions

| Decision | Rationale |
|---|---|
| Single `StockPrice` dataclass | One type flows through the entire stack; frontend SSE shape is always identical |
| In-memory cache inside provider | O(1) reads from SSE/REST handlers with no DB round-trip for hot-path price reads |
| `set_tickers()` is synchronous | Called from route handlers (sync context); the async loop reads `self._tickers` on the next iteration |
| 200-point rolling history | ~100 seconds of sparkline data at 500ms cadence; small memory footprint (~160 tickers × 200 × ~150 bytes) |
| `asyncio.gather` with `return_exceptions=True` | One ticker's network failure never blocks or crashes the poll for the others |
| History buffer slicing | Simple correctness; at 200 items the cost is negligible; switch to `deque(maxlen=200)` if buffer depth increases |
| GBM drift = 0 | No secular trend; prices wander realistically without drifting to unrealistic values over a long demo session |
