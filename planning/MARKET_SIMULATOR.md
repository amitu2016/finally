# Market Simulator — Technical Reference

The simulator generates realistic NSE price streams for all 10 default tickers without any external API calls. It runs as an in-process background task and produces data in the same `StockPrice` format as the live IndianAPI.in provider.

---

## Algorithm: Geometric Brownian Motion (GBM)

Each tick applies the GBM discrete update:

```
S(t+dt) = S(t) * exp((μ - σ²/2) * dt + σ * √dt * Z)
```

Where:
- `S(t)` — current price
- `μ` — drift (annualised expected return), defaults to `0.0` (no secular trend)
- `σ` — volatility (annualised standard deviation), per-ticker
- `dt` — time step in years; at 500ms cadence, `dt = 0.5 / (252 * 6.5 * 3600)`
- `Z` — standard normal random variable, drawn each tick

This produces log-normally distributed price increments — the same model used in Black-Scholes and standard quantitative finance.

---

## Seed Prices and Per-Ticker Volatility

Realistic INR seed prices for the 10 default NSE tickers. Volatility is annualised and calibrated to approximate each stock's historical realised vol.

```python
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

# Annualised volatility per ticker (fraction, not percent)
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

DEFAULT_VOL = 0.25  # fallback for unknown tickers
```

---

## Tick Implementation

```python
import math
import random
from datetime import datetime, timezone

TICK_INTERVAL = 0.5          # seconds between ticks
TRADING_DAYS_PER_YEAR = 252
HOURS_PER_DAY = 6.5
SECONDS_PER_YEAR = TRADING_DAYS_PER_YEAR * HOURS_PER_DAY * 3600
DT = TICK_INTERVAL / SECONDS_PER_YEAR  # time step in years

def gbm_step(price: float, vol: float, drift: float = 0.0) -> float:
    z = random.gauss(0.0, 1.0)
    exponent = (drift - 0.5 * vol ** 2) * DT + vol * math.sqrt(DT) * z
    return price * math.exp(exponent)
```

---

## Random Events

Roughly once per 60 seconds on average (~1/120 chance per 500ms tick), a random "event" fires on a randomly selected ticker, applying an additional ±2–5% instantaneous move. This creates the sudden jumps that make simulated data feel alive.

```python
EVENT_PROBABILITY = TICK_INTERVAL / 60  # ~0.0083 per tick
EVENT_MAGNITUDE_MIN = 0.02
EVENT_MAGNITUDE_MAX = 0.05

def maybe_apply_event(price: float) -> float:
    if random.random() > EVENT_PROBABILITY:
        return price
    direction = random.choice([-1, 1])
    magnitude = random.uniform(EVENT_MAGNITUDE_MIN, EVENT_MAGNITUDE_MAX)
    return price * (1 + direction * magnitude)
```

---

## Full Tick Method

```python
def _tick(self) -> None:
    now = datetime.now(timezone.utc)
    for ticker in self._tickers:
        prev_sp = self._cache.get(ticker)
        if prev_sp is None:
            continue

        vol = TICKER_VOL.get(ticker, DEFAULT_VOL)
        new_price = gbm_step(prev_sp.price, vol)
        new_price = maybe_apply_event(new_price)
        new_price = round(new_price, 2)

        seed = SEED_PRICES.get(ticker, prev_sp.price)
        change_pct = (new_price - seed) / seed * 100

        sp = StockPrice(
            ticker=ticker,
            price=new_price,
            prev_price=prev_sp.price,
            change_pct=round(change_pct, 2),
            timestamp=now,
            company_name=prev_sp.company_name,
        )
        self._cache[ticker] = sp
        self._history.setdefault(ticker, []).append(sp)
        if len(self._history[ticker]) > 200:
            self._history[ticker] = self._history[ticker][-200:]
```

---

## Output Format — Matches Production API

The simulator produces `StockPrice` objects with identical fields to those parsed from the IndianAPI.in `/stock` response:

| Field | Simulator source | IndianAPI source |
|---|---|---|
| `ticker` | set by `set_tickers()` | `data["tickerId"]` |
| `price` | GBM output | `data["currentPrice"]["NSE"]` |
| `prev_price` | previous cached price | previous cached price |
| `change_pct` | `(price - seed) / seed * 100` | `data["percentChange"]` |
| `timestamp` | `datetime.now(timezone.utc)` | `datetime.now(timezone.utc)` |
| `company_name` | empty string (not needed) | `data["companyName"]` |

The SSE event emitted downstream is byte-for-byte identical.

---

## Properties of the Generated Data

| Property | Value |
|---|---|
| Tick cadence | 500 ms |
| Price distribution | Log-normal per tick (GBM) |
| Drift | Zero (no secular trend) |
| Typical intraday range | ±1–3% for σ=0.25 tickers |
| Random event frequency | ~1 per 60 seconds, per ticker |
| Random event size | ±2–5% instantaneous jump |
| History buffer depth | 200 ticks (~100 seconds) |
| Price floor | None (GBM cannot reach zero in finite time) |

---

## Unknown Tickers

When `set_tickers()` is called with a ticker not in `SEED_PRICES`, the simulator initialises it at `₹1,000.00` with `DEFAULT_VOL = 0.25`. This is intentional: the app should function for any NSE ticker a user adds, even without a calibrated seed price.

---

## Why GBM

- Simple, standard, well-understood
- No external data dependency
- Produces realistic-looking candlestick-style movement
- log-normal distribution prevents negative prices
- Easily parameterised per ticker
- Fast enough to run in a Python asyncio event loop at 500ms cadence with 10+ tickers

The simulator is not intended to match real market microstructure (order flow, mean reversion, volatility clustering). Its only requirements are: realistic-looking price charts, the same data shape as the live API, and fast execution.

---

## Stretch Goal: Correlated Moves

The initial implementation uses independent GBM per ticker. A future enhancement can add a common market factor:

```python
# Market factor: one shared Z drawn per tick
Z_market = random.gauss(0.0, 1.0)
BETA = 0.5  # fraction of move explained by market

def gbm_step_correlated(price: float, vol: float, z_market: float) -> float:
    z_idio = random.gauss(0.0, 1.0)
    z = BETA * z_market + math.sqrt(1 - BETA**2) * z_idio
    exponent = (-0.5 * vol**2) * DT + vol * math.sqrt(DT) * z
    return price * math.exp(exponent)
```

This makes IT stocks (TCS, INFY) and banking stocks (HDFCBANK, ICICIBANK, SBIN) move together, which is visually convincing. Not needed for the initial build.
