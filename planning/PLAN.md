# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live Indian stock market data (NSE/BSE), lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default Indian stocks (NSE) with live-updating prices in a grid
- ₹1,00,000 in virtual cash (INR)
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → OpenRouter (Cerebras for fast inference), with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real Indian stock data via free NSE/BSE API if `USE_REAL_MARKET_DATA=true`

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   ├── market/               # Market data abstraction layer (IMPLEMENTED)
│   │   ├── __init__.py       # Public API exports
│   │   ├── base.py           # Abstract MarketDataProvider interface
│   │   ├── types.py          # StockPrice dataclass
│   │   ├── simulator.py      # GBM-based simulator provider
│   │   ├── indian_api.py     # IndianAPI.in polling provider
│   │   ├── fallback.py       # FallbackProvider (IndianAPI + simulator standby)
│   │   └── factory.py        # Environment-driven provider selection
│   ├── tests/                # Backend unit tests (IMPLEMENTED)
│   │   ├── test_factory.py
│   │   ├── test_simulator.py
│   │   ├── test_indian_api.py
│   │   ├── test_fallback.py
│   │   └── test_market_interface.py
│   ├── schema/               # Schema SQL definitions and seed data
│   ├── conftest.py           # pytest configuration
│   └── pyproject.toml        # Python project manifest
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   ├── MARKET_DATA_DESIGN.md # Complete market data implementation design
│   ├── MARKET_INTERFACE.md   # Abstract MarketDataProvider interface specification
│   ├── MARKET_SIMULATOR.md   # GBM simulator algorithm details
│   ├── INDIAN_API.md         # IndianAPI endpoint reference and rate-limit strategy
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/schema/`** contains schema SQL definitions and seed logic. The backend initializes the database at startup — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Use Yahoo Finance as the market data source (free, no key, ~15 min delay).
# Takes priority over INDIAN_STOCK_API_KEY when set to "true".
USE_YAHOO=false

# Optional: IndianAPI key (https://stock.indianapi.in) for real NSE/BSE market data.
# Used only when USE_YAHOO is not "true".
# If set → backend uses FallbackProvider (IndianAPI with automatic simulator fallback)
# If absent → backend uses SimulatorProvider only (GBM-based mock)
INDIAN_STOCK_API_KEY=your-indian-stock-api-key-here

# Optional: Adjusts the IndianAPI poll interval to match actual daily runtime.
# Default assumes 24/7; set to your actual hours/day to use quota more efficiently.
# Example: DAILY_RUNTIME_HOURS=4 → interval drops from 576s to ~96s.
DAILY_RUNTIME_HOURS=24

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `USE_YAHOO=true` → backend uses `YahooFinanceProvider` (free, no key, NSE `.NS` suffix, ~15 min delay, polls every 60s)
- Else if `INDIAN_STOCK_API_KEY` is set → backend uses `FallbackProvider` (IndianAPIProvider as primary, SimulatorProvider as automatic warm standby)
- Else → backend uses `SimulatorProvider` only (GBM-based mock)
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

> **Implementation note**: The original design used a `USE_REAL_MARKET_DATA` boolean flag to toggle market data sources. The implemented factory (`backend/market/factory.py`) instead uses the presence of `INDIAN_STOCK_API_KEY` directly as the selector — simpler and avoids inconsistency between the flag and the key. `USE_YAHOO` was added later as a higher-priority override.

---

## 6. Market Data

### Four Implementations, One Interface (IMPLEMENTED)

All market data providers implement the `MarketDataProvider` abstract base class defined in `backend/market/base.py`. The interface exposes:

- `start()` / `stop()` — async lifecycle management
- `get_price(ticker)` → `StockPrice | None`
- `get_all_prices()` → `dict[str, StockPrice]`
- `get_history(ticker, limit)` → `list[StockPrice]`
- `set_tickers(tickers)` — update tracked ticker set

The `StockPrice` dataclass (`backend/market/types.py`) carries: `ticker`, `price`, `prev_price`, `change_pct`, `timestamp`, `company_name`.

All downstream code (SSE streaming, portfolio snapshots, REST endpoints) is completely agnostic to which provider is active.

### Simulator (Default) — `SimulatorProvider` (IMPLEMENTED)

Located in `backend/market/simulator.py`.

- Generates prices using geometric Brownian motion (GBM) — `price * exp((drift - 0.5σ²)dt + σ√dt·Z)`
- Updates at ~500ms intervals (`TICK_INTERVAL = 0.5`)
- Per-ticker annualized volatility: ITC/HINDUNILVR 0.18 (low), RELIANCE/TCS 0.20–0.22 (mid), SBIN 0.32 (high)
- Occasional random "events" — sudden ±2–5% jumps (~once per 60s per ticker)
- Starts from realistic INR seed prices (RELIANCE ₹2,450, TCS ₹3,450, HDFCBANK ₹1,580, INFY ₹1,560, etc.)
- Runs as an async background task — no external dependencies
- Rolling 200-tick history buffer per ticker

### Indian Stock Market API — `IndianAPIProvider` (IMPLEMENTED)

Located in `backend/market/indian_api.py`. Full API reference: `planning/INDIAN_API.md`.

- **Base URL**: `https://stock.indianapi.in`
- **Authentication**: `X-Api-Key` header — API key from `INDIAN_STOCK_API_KEY` env var
- REST API polling using `GET /stock?name=<ticker>` per ticker
- Prefers `currentPrice.NSE`; falls back to `currentPrice.BSE` if NSE unavailable
- Response fields used: `currentPrice.NSE/BSE`, `percentChange`, `companyName`

**Rate-limit management** (key implementation detail):
- Monthly quota: 5,000 calls/month with 90% safety factor → effective budget ~4,500 calls
- `QUOTA_CALL_INTERVAL ≈ 576s` — minimum wait between consecutive API calls
- **Round-robin single-ticker polling** (not concurrent) to strictly honor rate limits
- With 10 tickers, each is refreshed ~every 96 minutes (576s × 10)
- HTTP 429 response → marks provider as `is_rate_limited = True`
- Exponential backoff on consecutive failures, capped at 1 hour
- Random ±10s jitter added to each sleep to avoid thundering herd
- Monthly quota resets automatically on calendar-month rollover
- `get_quota_status()` returns usage stats (calls used, remaining, quota month)
- On any error, logs a warning and retains last cached prices; SSE stream continues uninterrupted

### Fallback Provider — `FallbackProvider` (IMPLEMENTED, new in recent PRs)

Located in `backend/market/fallback.py`. This provider was added beyond the original design spec.

- Wraps `IndianAPIProvider` as primary with `SimulatorProvider` as automatic warm standby
- **Simulator starts immediately** at `start()` — no cold-start delay if API becomes rate-limited
- Background monitor task (30s interval) checks `IndianAPIProvider.is_rate_limited`
- On rate-limit or quota exhaustion → transparently switches all data reads to the simulator
- Fallback is **permanent** for the lifetime of the instance; restart to re-attempt the real API
- `set_tickers()` propagates to both underlying providers simultaneously

### Yahoo Finance — `YahooFinanceProvider` (IMPLEMENTED)

Located in `backend/market/yahoo.py`.

- Uses the `yfinance` library (unofficial Yahoo Finance API) — **no API key required**
- NSE tickers mapped to Yahoo symbols via `.NS` suffix (e.g. `RELIANCE` → `RELIANCE.NS`)
- Polls all tracked tickers sequentially every 60 seconds via a thread-pool executor
- Data is typically delayed ~15 minutes (Yahoo Finance free tier)
- `fast_info.last_price` / `fast_info.previous_close` used for current and previous prices
- `change_pct` computed as `(last_price - previous_close) / previous_close × 100`
- Handles `None` / `NaN` prices and network errors gracefully — retains last cached price
- Rolling 200-price history buffer per ticker

### Provider Selection — `create_market_provider()` (IMPLEMENTED)

Located in `backend/market/factory.py`.

```python
USE_YAHOO=true              → YahooFinanceProvider()     # free, no key, ~15 min delay
INDIAN_STOCK_API_KEY set    → FallbackProvider(api_key)  # IndianAPI + auto-fallback to simulator
Neither                     → SimulatorProvider()         # GBM simulation only
```

### Shared Price Cache

- Each provider maintains its own in-memory cache (`dict[str, StockPrice]`) and rolling history buffer (`dict[str, list[StockPrice]]`)
- The cache holds: latest `StockPrice` per ticker (price, prev_price, change_pct, timestamp, company_name)
- Rolling history: last 200 price points per ticker (`HISTORY_LIMIT = 200`)
- SSE streams read from the active provider's cache and push updates to connected clients
- `set_tickers()` is called at startup and on every watchlist change; the provider self-manages additions and removals

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- Server pushes price updates for all tickers currently in the watchlist at a regular cadence (~500ms). The stream reads the watchlist from the DB on each tick, so newly added tickers appear automatically within one tick — no client reconnect required.
- Each SSE event contains ticker, price, previous price, timestamp, and change direction
- Client handles reconnection automatically (EventSource has built-in retry)
- The market provider supplies prices via `get_all_prices()` — agnostic to whether data comes from SimulatorProvider, IndianAPIProvider, or FallbackProvider

---

## 7. Database

### SQLite with Lazy Initialization

The backend initializes the SQLite database during application startup (FastAPI lifespan event). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `100000.0`) — ₹1,00,000 INR
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- PRIMARY KEY `(user_id, ticker)` — composite, no separate id column
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)

**positions** — Current holdings (one row per ticker per user)
- PRIMARY KEY `(user_id, ticker)` — composite, no separate id column
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- When quantity reaches zero (full sell), the row is deleted.

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each trade execution.
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL — `cash_balance + Σ(quantity × current_price)` for all open positions, computed from the in-memory price cache at snapshot time
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `id="default"`, `cash_balance=100000.0` (₹1,00,000 INR)
- Ten watchlist entries (NSE): RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, BHARTIARTL, SBIN, ITC, LT, HINDUNILVR

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |
| GET | `/api/prices/{ticker}/history` | Recent price history for a ticker (from in-memory rolling buffer) |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use cerebras-inference skill to use LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. Structured Outputs should be used to interpret the results.

There is an OPENROUTER_API_KEY in the .env file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads recent conversation history from the `chat_messages` table
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → OpenRouter, requesting structured output, using the cerebras-inference skill
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response
7. Stores the message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — Cerebras inference is fast enough that a loading indicator is sufficient)

Chat history is persisted in the database but is **not restored to the frontend on page reload** — the conversation starts fresh each session. This is intentional for simplicity; the stored history is available for future enhancement.

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "RELIANCE", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "BAJFINANCE", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications. Each entry: `{"ticker": "...", "action": "add" | "remove"}`

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the LLM can inform the user.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), daily change %, and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker showing price over time. On ticker selection, fetches recent history from `GET /api/prices/{ticker}/history` to pre-populate the chart; then appends new prices from the SSE stream. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme
- Sparkline data resets on SSE reconnect (acceptable for demo). The main chart re-fetches from `/api/prices/{ticker}/history` on reconnect to restore recent history.

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

The `db/` directory in the project root maps to `/app/db` in the container. The backend writes `finally.db` to this path.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Indian Stock Market API response parsing works, Yahoo Finance ticker mapping and fetch logic works, all implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, ₹1,00,000 balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Implementation Status

This section tracks what has been built versus what remains planned.

### ✅ Implemented (Market Data Layer — PRs #10–13, #17)

| Component | File | Status |
|---|---|---|
| Abstract interface | `backend/market/base.py` | ✅ Done |
| StockPrice dataclass | `backend/market/types.py` | ✅ Done |
| GBM simulator | `backend/market/simulator.py` | ✅ Done |
| IndianAPI client | `backend/market/indian_api.py` | ✅ Done |
| Fallback provider | `backend/market/fallback.py` | ✅ Done |
| Yahoo Finance provider | `backend/market/yahoo.py` | ✅ Done |
| Provider factory | `backend/market/factory.py` | ✅ Done |
| Market interface tests | `backend/tests/test_market_interface.py` | ✅ Done |
| Simulator tests | `backend/tests/test_simulator.py` | ✅ Done |
| IndianAPI tests | `backend/tests/test_indian_api.py` | ✅ Done |
| Fallback tests | `backend/tests/test_fallback.py` | ✅ Done |
| Yahoo Finance tests | `backend/tests/test_yahoo.py` | ✅ Done |
| Factory tests | `backend/tests/test_factory.py` | ✅ Done |
| CLI demo | `backend/demo.py` | ✅ Done |
| Planning docs | `planning/MARKET_DATA_DESIGN.md`, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `INDIAN_API.md` | ✅ Done |

### ❌ Not Yet Implemented

| Component | Notes |
|---|---|
| FastAPI application | `backend/app/main.py` — lifespan, routes, SSE |
| REST API endpoints | All `/api/*` routes |
| SQLite database layer | Schema creation, seed data, ORM queries |
| LLM chat integration | LiteLLM → OpenRouter → Cerebras, structured output |
| Portfolio management | Trade execution, positions, cash balance |
| Watchlist CRUD | DB-backed add/remove with SSE integration |
| Portfolio snapshots | Background task + `/api/portfolio/history` |
| Frontend | Next.js project, all React components |
| Dockerfile | Multi-stage build (Node → Python) |
| Start/stop scripts | `scripts/start_mac.sh`, `start_windows.ps1`, etc. |
| E2E tests | Playwright test suite in `test/` |

---


