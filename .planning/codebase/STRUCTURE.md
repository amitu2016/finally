---
title: Structure
focus: arch
last_mapped: 2026-05-02
---

# Directory Structure: FinAlly

## Top-Level Layout

```
finally/
├── backend/                  # FastAPI + Python (uv project)
├── frontend/                 # Next.js TypeScript (static export)
├── db/                       # Runtime volume mount — finally.db lives here
│   └── .gitkeep
├── planning/                 # Project documentation (agent reference)
├── scripts/                  # Start/stop Docker scripts
├── test/                     # Playwright E2E tests
├── .planning/                # GSD planning artifacts
├── Dockerfile                # Multi-stage build (Node → Python)
├── .env                      # Gitignored; .env.example committed
├── .env.example
└── .gitignore
```

## Backend (`backend/`)

```
backend/
├── app/                      # FastAPI application
│   ├── main.py               # Entry point: lifespan, routers, static serving
│   ├── schemas.py            # Pydantic request/response models
│   ├── dependencies.py       # FastAPI dependency injection
│   ├── portfolio.py          # Trade execution, P&L, compute_total_value
│   ├── llm.py                # LLM chat integration (LiteLLM → OpenRouter)
│   ├── auth.py               # Auth utilities
│   └── routes/               # API route handlers
│       ├── auth.py           # GET /api/me, POST /api/auth/*
│       ├── chat.py           # POST /api/chat
│       ├── health.py         # GET /api/health
│       ├── portfolio.py      # GET/POST /api/portfolio, /api/portfolio/trade
│       ├── prices.py         # GET /api/stream/prices, /api/prices/{ticker}/history
│       └── watchlist.py      # GET/POST/DELETE /api/watchlist
│
├── db/                       # Database layer
│   ├── database.py           # SQLite connection, init_db(), get_db()
│   └── queries.py            # All SQL as async functions (no ORM)
│
├── market/                   # Market data abstraction layer
│   ├── base.py               # Abstract MarketDataProvider interface
│   ├── types.py              # StockPrice dataclass
│   ├── simulator.py          # GBM simulator (default)
│   ├── indian_api.py         # IndianAPI.in polling provider
│   ├── fallback.py           # FallbackProvider (IndianAPI + Simulator)
│   ├── yahoo.py              # Yahoo Finance via yfinance
│   ├── factory.py            # create_market_provider() — env-driven selection
│   └── __init__.py
│
├── tests/                    # pytest unit tests
│   ├── test_db.py
│   ├── test_factory.py
│   ├── test_fallback.py
│   ├── test_indian_api.py
│   ├── test_llm.py
│   ├── test_market_interface.py
│   ├── test_queries.py
│   ├── test_routes.py
│   ├── test_simulator.py
│   └── test_yahoo.py
│
├── demo.py                   # CLI market data demo
├── conftest.py               # pytest configuration
├── pyproject.toml            # uv project manifest
└── uv.lock                   # Lockfile
```

## Frontend (`frontend/`)

```
frontend/
├── app/                      # Next.js App Router
│   ├── layout.tsx            # Root layout (fonts, global styles)
│   └── page.tsx              # Single-page app root
│
├── components/               # React components
│   ├── Header.tsx            # Portfolio value, cash, connection status
│   ├── WatchlistPanel.tsx    # Watchlist grid with price flash + sparklines
│   ├── MainChart.tsx         # Selected ticker detailed chart
│   ├── PnLChart.tsx          # Portfolio value over time
│   ├── PortfolioHeatmap.tsx  # Treemap of positions by weight/P&L
│   ├── PositionsTable.tsx    # Holdings table with unrealized P&L
│   ├── TradeBar.tsx          # Buy/sell input (market orders)
│   ├── ChatPanel.tsx         # AI chat sidebar
│   ├── AddTickerForm.tsx     # Add ticker to watchlist
│   ├── AuthGate.tsx          # Auth wrapper
│   ├── PriceCell.tsx         # Price display with flash animation
│   └── Sparkline.tsx         # Mini sparkline chart
│
├── hooks/                    # Custom React hooks
│   ├── useMarketData.ts      # SSE connection + price state management
│   ├── usePortfolio.ts       # Portfolio state + trade execution
│   └── useWatchlist.ts       # Watchlist CRUD
│
├── lib/                      # Utilities
│   ├── api.ts                # Typed API client functions
│   ├── auth.ts               # Auth helpers
│   ├── format.ts             # Number/currency formatters
│   └── types.ts              # Shared TypeScript interfaces
│
├── out/                      # Static export output (gitignored, built by CI)
├── next.config.ts            # output: 'export', basePath config
├── package.json
└── tsconfig.json
```

## Key File Locations

| What | Where |
|------|-------|
| App startup | `backend/app/main.py` |
| All SQL queries | `backend/db/queries.py` |
| Market provider selection | `backend/market/factory.py` |
| LLM integration | `backend/app/llm.py` |
| Trade execution logic | `backend/app/portfolio.py` |
| SSE streaming endpoint | `backend/app/routes/prices.py` |
| Frontend entry | `frontend/app/page.tsx` |
| SSE client hook | `frontend/hooks/useMarketData.ts` |
| API client | `frontend/lib/api.ts` |
| Docker build | `Dockerfile` |
| E2E tests | `test/` |
| Project planning docs | `planning/` |
| Environment template | `.env.example` |

## Naming Conventions

**Backend:**
- Modules: `snake_case` (e.g., `indian_api.py`, `portfolio.py`)
- Classes: `PascalCase` (e.g., `SimulatorProvider`, `StockPrice`)
- Async functions: `snake_case` with `async def`
- Route files: named by resource (`watchlist.py`, `portfolio.py`)

**Frontend:**
- Components: `PascalCase.tsx` (e.g., `WatchlistPanel.tsx`)
- Hooks: `camelCase.ts` prefixed with `use` (e.g., `useMarketData.ts`)
- Lib modules: `camelCase.ts` (e.g., `api.ts`, `format.ts`)
- Types: `PascalCase` interfaces in `lib/types.ts`

## Build Artifacts

| Artifact | Location | Created by |
|----------|----------|------------|
| Frontend static files | `frontend/out/` | `npm run build` |
| Backend static mount | `backend/static/` | Dockerfile COPY step |
| SQLite database | `db/finally.db` | Runtime (gitignored) |
| Python venv | `backend/.venv/` | `uv sync` |

---
*Mapped: 2026-05-02*
