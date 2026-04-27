# Indian Stock Market API — Reference

**Provider**: IndianAPI (`https://indianapi.in`)  
**Base URL**: `https://stock.indianapi.in`  
**Plan**: Paid  
**Authentication**: `X-Api-Key: <your-api-key>` header on every request  
**Env var used in project**: `INDIAN_STOCK_API_KEY` (read from `.env`)

---

## FinAlly Project Usage Notes

- Use this API when `USE_REAL_MARKET_DATA=true`
- The most relevant endpoints for live price streaming are **`/stock`** (single ticker) and **`/trending`** (market movers)
- No bulk/batch endpoint exists — poll each ticker individually; batch via asyncio for efficiency
- Markets open **9:15 AM – 3:30 PM IST** weekdays; API returns last available data when closed
- Recommended poll interval: **15 seconds** per ticker (stay well within rate limits)
- On error or timeout, log a warning and retain last cached price — SSE stream must not drop

---

## Authentication

All requests must include:

```http
X-Api-Key: YOUR_API_KEY
```

---

## Endpoints

### 1. Get Company Data by Name

```
GET /stock?name=<name>
```

Retrieve detailed financial data for a specific company. Supports full names, short names, or any search term Livemint accepts.

**Parameters**:
- `name` (required, string) — e.g., `"Reliance"`, `"TCS"`, `"INFY"`

**Sample request**:
```http
GET https://stock.indianapi.in/stock?name=Reliance
X-Api-Key: YOUR_API_KEY
```

**Response** (key fields used by FinAlly):
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
  "yearLow": 1800.00
}
```

**Full response fields**:
| Field | Description |
|---|---|
| `tickerId` | NSE ticker symbol (e.g., `"RELIANCE"`) |
| `companyName` | Full legal company name |
| `industry` | Industry classification |
| `currentPrice.NSE` | Current NSE price (INR) |
| `currentPrice.BSE` | Current BSE price (INR) |
| `percentChange` | % change from previous close |
| `yearHigh` / `yearLow` | 52-week high / low |
| `companyProfile` | Detailed company info |
| `stockTechnicalData` | Technical analysis data |
| `financials` | Financial statements |
| `keyMetrics` | PE ratio, market cap, etc. |
| `futureExpiryDates` | F&O expiry dates |
| `futureOverviewData` | Futures overview |
| `analystView` | Analyst ratings |
| `recosBar` | Recommendation distribution |
| `riskMeter` | Risk score |
| `shareholding` | Promoter/FII/DII holding % |
| `stockCorporateActionData` | Dividends, splits, etc. |
| `recentNews` | Latest news articles |

---

### 2. Trending Stocks

```
GET /trending
```

Top 3 gainers and top 3 losers by percentage change, sourced from a live feed.

**Response structure**:
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
    "top_losers": [
      // same fields
    ]
  }
}
```

Note: null values are stripped from the response automatically.

---

### 3. NSE Most Active

```
GET /NSE_most_active
```

Most actively traded NSE stocks by volume.

**Response**:
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

### 4. BSE Most Active

```
GET /BSE_most_active
```

Same as NSE Most Active, for BSE tickers (`.BO` suffix).

---

### 5. 52-Week High/Low

```
GET /fetch_52_week_high_low_data
```

Stocks hitting new 52-week highs or lows on NSE and BSE.

**Note**: Returns empty list when the market is closed.

**Response**:
```json
{
  "NSE_52WeekHighLow": {
    "high52Week": [
      { "ticker": "RELIANCE.NS", "company": "Reliance Industries", "price": 2200.55, "52_week_high": 2300.00 }
    ],
    "low52Week": [ /* ... */ ]
  },
  "BSE_52WeekHighLow": { /* same structure */ }
}
```

---

### 6. Industry Search

```
GET /industry_search?query=<query>
```

Search companies by industry or sector.

**Parameters**: `query` (required, string)

**Response**:
```json
[
  {
    "id": "50003051",
    "commonName": "Tata Consultancy Services",
    "mgIndustry": "Software & Programming",
    "mgSector": "Technology",
    "stockType": "Equity",
    "exchangeCodeNse": "TCS",
    "nseRic": "TCS.NS",
    "activeStockTrends": {
      "shortTermTrends": "Bearish",
      "longTermTrends": "Moderately Bearish",
      "overallRating": "Moderately Bearish"
    }
  }
]
```

---

### 7. Historical Data

```
GET /historical_data?stock_name=<name>&period=<period>&filter=<filter>
```

Historical price and financial data for a stock.

**Parameters**:
| Param | Required | Default | Options |
|---|---|---|---|
| `stock_name` | yes | — | any ticker/name |
| `period` | no | `5yr` | `1m`, `6m`, `1yr`, `3yr`, `5yr`, `10yr`, `max` |
| `filter` | no | `default` | `price`, `pe`, `sm`, `evebitda`, `ptb`, `mcs` |

**Sample request**:
```http
GET /historical_data?stock_name=TATAMOTORS&period=1yr&filter=price
```

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

### 8. Historical Stats

```
GET /historical_stats?stock_name=<name>&stats=<stats>
```

Quarterly and annual financial statements.

**Parameters**:
- `stock_name` (required)
- `stats` (required): `quarter_results` | `yoy_results` | `balancesheet` | `cashflow` | `ratios` | `shareholding_pattern_quarterly` | `shareholding_pattern_yearly`

---

### 9. Analyst Target Price

```
GET /stock_target_price?stock_id=<stock_id>
```

Analyst price targets and recommendation scores.

**Response**:
```json
{
  "priceTarget": {
    "CurrencyCode": "INR",
    "Mean": 4305.17,
    "High": 4800,
    "Low": 3165,
    "NumberOfEstimates": 41,
    "Median": 4400
  },
  "recommendation": { /* score 1–5 */ }
}
```

**Recommendation scale**: 1=Buy, 2=Outperform, 3=Hold, 4=Underperform, 5=Sell

Snapshots available for: current, 1 week ago, 30 days ago, 60 days ago, 90 days ago.

---

### 10. Stock Forecasts

```
GET /stock_forecasts?stock_id=<id>&measure_code=<code>&period_type=<type>&data_type=<type>&age=<age>
```

Financial estimates and actuals for a given metric.

**Parameters**:
| Param | Options |
|---|---|
| `measure_code` | `EPS`, `DPS`, `ROE`, `ROA`, `SAL` (Revenue), `NET`, `EBI`, `EBT`, `CPS`, `CPX`, `GPS`, `GRM`, `NAV`, `NDT`, `PRE` |
| `period_type` | `ANNUAL`, `INTERIM` |
| `data_type` | `ACTUALS`, `ESTIMATES` |
| `age` | `CURRENT`, `ONE_WEEK_AGO`, `THIRTY_DAYS_AGO`, `SIXTY_DAYS_AGO`, `NINETY_DAYS_AGO` |

---

### 11. Price Shockers

```
GET /price_shockers
```

Stocks with significant intraday price moves.

**Response**:
```json
[
  {
    "ticker": "BPCL.NS",
    "company": "Bharat Petroleum Corporation",
    "price": 309.15,
    "percent_change": -1.27,
    "net_change": -3.98,
    "high": 319,
    "low": 308.7,
    "open": 318,
    "volume": 18726562
  }
]
```

---

### 12. Commodity Futures

```
GET /commodities
```

Active MCX futures contracts snapshot.

**Response fields**:
| Field | Description |
|---|---|
| `commoditySymbol` | e.g., `"ALUMINIUM"` |
| `lastTradedPrice` | Latest trade price |
| `expiryDate` | Contract expiry |
| `totalVolume` | Session volume |
| `openInterest` | Unsettled contracts |
| `priceChange` / `percentageChange` | Change from previous session |
| `priceUnit` | e.g., `"KGS"` |
| `contractSize` | Units per contract |

---

### 13. Mutual Fund Search

```
GET /mutual_fund_search?query=<query>
```

Search mutual fund schemes by name or category.

---

### 14. Mutual Funds Overview

```
GET /mutual_funds
```

All mutual funds with NAV, returns, AUM, and star ratings grouped by category (Large Cap, Mid Cap, etc.).

---

## Error Handling

| Status | Meaning |
|---|---|
| `200` | Success |
| `404` | Resource not found (e.g., unknown stock_id) |
| `429` | Rate limit exceeded |
| `500` | Server error |

On any non-200 response, log the error, retain the last cached price, and continue the SSE stream.
