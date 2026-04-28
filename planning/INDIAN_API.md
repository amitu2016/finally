# Indian Stock Market API — IndianAPI.in

**Provider**: IndianAPI (`https://indianapi.in`)
**Base URL**: `https://stock.indianapi.in`
**Authentication**: `X-Api-Key: <key>` header on every request
**Env var**: `INDIAN_STOCK_API_KEY`

---

## Key Facts for FinAlly

- No batch endpoint — poll each ticker individually; use `asyncio.gather` for concurrency
- Market hours: **9:15 AM – 3:30 PM IST**, weekdays only; API returns last available data when closed
- Recommended poll interval: **15 seconds** per ticker (conservative; well within rate limits)
- On error, retain last cached price and keep the SSE stream alive

---

## Authentication

Every request must include:

```http
X-Api-Key: YOUR_API_KEY
```

---

## Endpoints Used by FinAlly

### GET /stock

Retrieve current price and metadata for a single company.

```
GET https://stock.indianapi.in/stock?name=<ticker_or_name>
X-Api-Key: YOUR_API_KEY
```

**Parameter**: `name` — NSE ticker symbol (e.g., `RELIANCE`, `TCS`, `INFY`) or partial company name.

**Response** (full shape):

```json
{
  "tickerId": "RELIANCE",
  "companyName": "Reliance Industries Limited",
  "industry": "Conglomerate",
  "currentPrice": {
    "BSE": 2200.50,
    "NSE": 2195.75
  },
  "percentChange": 1.25,
  "yearHigh": 2400.00,
  "yearLow": 1800.00,
  "companyProfile": { ... },
  "stockTechnicalData": { ... },
  "financials": { ... },
  "keyMetrics": { ... },
  "analystView": { ... },
  "recosBar": { ... },
  "riskMeter": { ... },
  "shareholding": { ... },
  "stockCorporateActionData": { ... },
  "recentNews": [ ... ]
}
```

**Fields FinAlly uses**:

| Field | Type | Description |
|---|---|---|
| `tickerId` | string | NSE symbol (e.g., `"RELIANCE"`) |
| `companyName` | string | Full company name |
| `currentPrice.NSE` | float | Current NSE price in INR |
| `currentPrice.BSE` | float | Current BSE price in INR |
| `percentChange` | float | % change from previous close |

**Python example**:

```python
import httpx

async def fetch_stock(ticker: str, api_key: str) -> dict:
    url = "https://stock.indianapi.in/stock"
    headers = {"X-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params={"name": ticker}, headers=headers)
        resp.raise_for_status()
        return resp.json()

# Extract the fields we need
data = await fetch_stock("RELIANCE", api_key)
price_nse = data["currentPrice"]["NSE"]
pct_change = data["percentChange"]
```

---

### GET /trending

Top 3 gainers and top 3 losers by % change.

```
GET https://stock.indianapi.in/trending
X-Api-Key: YOUR_API_KEY
```

**Response**:

```json
{
  "trending_stocks": {
    "top_gainers": [
      {
        "ticker_id": "RELIANCE",
        "company_name": "Reliance Industries",
        "price": "2200.50",
        "percent_change": "1.25",
        "net_change": "27.25",
        "high": "2210.00",
        "low": "2170.00",
        "open": "2175.00",
        "volume": "5000000",
        "year_high": "2400.00",
        "year_low": "1800.00",
        "overall_rating": "Bullish",
        "short_term_trends": "Bullish",
        "long_term_trends": "Moderately Bullish",
        "exchange_type": "NSE",
        "ric": "RELI.NS"
      }
    ],
    "top_losers": [ /* same shape */ ]
  }
}
```

Note: all numeric fields are strings in this endpoint (unlike `/stock`).

---

### GET /historical_data

Historical price data for charts.

```
GET https://stock.indianapi.in/historical_data?stock_name=RELIANCE&period=1m&filter=price
X-Api-Key: YOUR_API_KEY
```

**Parameters**:

| Param | Required | Options |
|---|---|---|
| `stock_name` | yes | NSE ticker or name |
| `period` | no (default `5yr`) | `1m`, `6m`, `1yr`, `3yr`, `5yr`, `10yr`, `max` |
| `filter` | no (default `default`) | `price`, `pe`, `sm`, `evebitda`, `ptb`, `mcs` |

**Response**:

```json
{
  "datasets": [
    {
      "metric": "Price",
      "label": "Price on NSE",
      "values": [
        ["2024-06-27", "3934.15"],
        ["2024-06-26", "3910.00"]
      ]
    }
  ],
  "meta": { "is_weekly": false }
}
```

---

### GET /NSE_most_active

Most-traded NSE stocks by volume (useful for watchlist discovery).

```json
[
  {
    "ticker": "RELIANCE.NS",
    "company": "Reliance Industries",
    "price": 2200.55,
    "percent_change": 0.70,
    "net_change": 15.45,
    "volume": 12000000
  }
]
```

---

## Other Available Endpoints (not used by FinAlly)

| Endpoint | Description |
|---|---|
| `GET /BSE_most_active` | Most active BSE stocks |
| `GET /fetch_52_week_high_low_data` | 52-week highs and lows (empty when market closed) |
| `GET /industry_search?query=<q>` | Search companies by industry |
| `GET /historical_stats` | Quarterly/annual financials |
| `GET /stock_target_price?stock_id=<id>` | Analyst price targets |
| `GET /stock_forecasts` | EPS/revenue estimates |
| `GET /price_shockers` | Stocks with large intraday moves |
| `GET /commodities` | MCX futures snapshot |
| `GET /mutual_fund_search` | Mutual fund search |
| `GET /mutual_funds` | All mutual funds with NAV and returns |

---

## Error Handling

| HTTP Status | Meaning | Action |
|---|---|---|
| `200` | Success | Parse and cache |
| `404` | Unknown ticker | Log warning; skip update |
| `429` | Rate limit | Back off; retain cached price |
| `500` | Server error | Log; retain cached price |

**Pattern**: on any non-200 response, log the error and return the last cached `StockPrice`. The SSE stream must never drop due to a failed poll.

---

## Concurrent Multi-Ticker Polling

```python
import asyncio
import httpx

async def poll_all(tickers: list[str], api_key: str) -> dict[str, dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [fetch_one(client, t, api_key) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return {t: r for t, r in zip(tickers, results) if not isinstance(r, Exception)}

async def fetch_one(client: httpx.AsyncClient, ticker: str, api_key: str) -> dict:
    resp = await client.get(
        "https://stock.indianapi.in/stock",
        params={"name": ticker},
        headers={"X-Api-Key": api_key},
    )
    resp.raise_for_status()
    return resp.json()
```
