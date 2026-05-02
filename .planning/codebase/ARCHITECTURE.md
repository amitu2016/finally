---
title: Architecture
focus: arch
last_mapped: 2026-05-02
---

# Architecture: FinAlly

## Pattern

**Layered monolith** — single Docker container, single port (8000). FastAPI serves both the REST/SSE API and the static Next.js export. No microservices, no service mesh.

```
Browser
  └── Next.js static SPA (served by FastAPI from /static)
        ├── REST calls → /api/*
        └── SSE stream → /api/stream/prices
              └── FastAPI app (backend/app/main.py)
                    ├── Route layer (backend/app/routes/)
                    ├── Domain layer (backend/app/portfolio.py, llm.py)
                    ├── DB layer (backend/db/)
                    └── Market layer (backend/market/)
```

## Layers

### 1. Frontend (Next.js static export)
- Built as static HTML/JS (`output: 'export'`) — no Node.js server in production
- Served by FastAPI's `StaticFiles` mount and SPA catch-all route
- Communicates with backend exclusively via `/api/*` REST and `/api/stream/prices` SSE
- 12 components + 3 custom hooks + 3 lib modules

### 2. FastAPI Application (`backend/app/`)
Entry point: `backend/app/main.py`

**Routers:**
- `auth_router` — `backend/app/routes/auth.py` — user identity
- `health_router` — `backend/app/routes/health.py` — liveness probe
- `prices_router` — `backend/app/routes/prices.py` — SSE stream + price history
- `portfolio_router` — `backend/app/routes/portfolio.py` — positions, trades, snapshots
- `watchlist_router` — `backend/app/routes/watchlist.py` — CRUD for watchlist
- `chat_router` — `backend/app/routes/chat.py` — LLM chat with auto-execution

**Lifespan tasks (startup/shutdown):**
- Database initialization (`init_db`)
- Market provider startup (`create_market_provider()` → `provider.start()`)
- Portfolio snapshot background loop (every 30s)

### 3. Market Data Layer (`backend/market/`)
Abstract interface (`MarketDataProvider`) with 4 implementations:
- `SimulatorProvider` — GBM-based mock, default when no API key set
- `IndianAPIProvider` — Real NSE/BSE data via IndianAPI.in (rate-limited: ~576s/call)
- `YahooFinanceProvider` — Yahoo Finance via `yfinance`, ~15min delay, no key required
- `FallbackProvider` — Wraps IndianAPI + Simulator; auto-switches on rate-limit

Provider selected at startup via `create_market_provider()` (`backend/market/factory.py`) based on env vars.

### 4. Database Layer (`backend/db/`)
- `backend/db/database.py` — SQLite connection management, `init_db()`, `get_db()` async context manager
- `backend/db/queries.py` — All SQL queries as async functions; no ORM

### 5. Domain Logic
- `backend/app/portfolio.py` — Trade execution, P&L calculation, `compute_total_value()`
- `backend/app/llm.py` — LLM chat integration (LiteLLM → OpenRouter/Cerebras), structured output parsing, auto-execution of trades/watchlist changes
- `backend/app/schemas.py` — Pydantic request/response models
- `backend/app/dependencies.py` — FastAPI dependency injection (DB, market provider)

## Data Flow

### Price Streaming (SSE)
```
SimulatorProvider/IndianAPIProvider/Yahoo
  → in-memory price cache (dict[str, StockPrice])
    → /api/stream/prices (SSE, ~500ms cadence)
      → browser EventSource
        → useMarketData hook
          → WatchlistPanel (flash), Sparkline, MainChart, PriceCell
```

### Trade Execution
```
User input (TradeBar) / AI chat
  → POST /api/portfolio/trade
    → portfolio.execute_trade()
      → queries.get_position(), update_position(), record_trade()
        → queries.record_snapshot() (immediate snapshot after trade)
          → 200 OK + updated portfolio
```

### LLM Chat Auto-Execution
```
User message → POST /api/chat
  → llm.chat() builds context (portfolio + watchlist + history)
    → LiteLLM → OpenRouter → Cerebras (gpt-oss-120b)
      → structured JSON response {message, trades[], watchlist_changes[]}
        → auto-execute each trade via portfolio.execute_trade()
        → auto-apply watchlist changes via queries
          → store in chat_messages
            → return full response to frontend
```

### Portfolio Snapshots (background)
```
_snapshot_loop (every 30s)
  → compute_total_value() = cash + Σ(qty × current_price)
    → queries.record_snapshot()
      → portfolio_snapshots table
        → GET /api/portfolio/history → PnLChart
```

## Key Abstractions

| Abstraction | Location | Purpose |
|---|---|---|
| `MarketDataProvider` | `backend/market/base.py` | Abstract interface for all market data sources |
| `StockPrice` | `backend/market/types.py` | Canonical price dataclass shared across all layers |
| `get_db()` | `backend/db/database.py` | Async context manager for SQLite connections |
| `app.state.market` | FastAPI app state | Single market provider instance, injected via dependency |
| `app.state.db_path` | FastAPI app state | DB file path, resolved at startup based on environment |

## Entry Points

| Entry | Path | Trigger |
|---|---|---|
| Backend server | `backend/app/main.py` | `uvicorn app.main:app` |
| DB init | `backend/db/database.py:init_db()` | Called at lifespan startup |
| Market provider | `backend/market/factory.py:create_market_provider()` | Called at lifespan startup |
| Frontend build | `frontend/next.config.ts` | `npm run build` produces `frontend/out/` |
| Docker | `Dockerfile` | Multi-stage: Node→Python; copies `frontend/out/` to `backend/static/` |

---
*Mapped: 2026-05-02*
