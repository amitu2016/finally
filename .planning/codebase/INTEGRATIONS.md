# External Integrations

**Analysis Date:** 2026-05-02

## APIs & External Services

**Market Data (Four Provider Strategy):**
- **Yahoo Finance** - Free, no API key required, ~15 min delay
  - SDK/Client: `yfinance` 0.2.50+
  - Implementation: `backend/market/yahoo.py` - YahooFinanceProvider
  - URL: Yahoo Finance free tier (unofficial API)
  - Ticker mapping: NSE tickers → `{ticker}.NS` suffix
  - Poll interval: 60 seconds
  - Fallback to simulator on network error

- **IndianAPI.in** - Real-time NSE/BSE data
  - SDK/Client: `httpx` async HTTP client
  - Implementation: `backend/market/indian_api.py` - IndianAPIProvider
  - URL: `https://stock.indianapi.in`
  - Auth: API key via `X-Api-Key` header from `INDIAN_STOCK_API_KEY` env var
  - Rate limit: 5,000 calls/month; safety factor 0.9 → effective 4,500 calls/month
  - Quota interval: ~576 seconds between consecutive calls (round-robin single-ticker polling)
  - With 10 tickers: each refreshed ~every 96 minutes
  - HTTP 429 handling: exponential backoff, capped at 1 hour, marks provider as rate-limited
  - Random ±10s jitter per sleep to avoid thundering herd
  - Monthly quota resets automatically on calendar-month rollover
  - Error recovery: logs warning, retains last cached price, SSE stream continues
  - Quota status available via `get_quota_status()` method

- **GBM Simulator** (Default Fallback) - Geometric Brownian Motion mock
  - Implementation: `backend/market/simulator.py` - SimulatorProvider
  - No external dependencies, pure Python
  - Update interval: ~500ms
  - Per-ticker volatility: 0.18-0.32 (annualized)
  - Random ±2-5% jumps (~once per 60s per ticker)
  - Rolling 200-tick history buffer

- **FallbackProvider** - Hybrid wrapper
  - Implementation: `backend/market/fallback.py` - FallbackProvider
  - Wraps IndianAPIProvider as primary, SimulatorProvider as automatic warm standby
  - Simulator starts immediately at `start()` — no cold-start delay
  - Background monitor (30s interval) checks for rate-limit/quota exhaustion
  - On rate-limit: transparently switches to simulator for remainder of session
  - Fallback is permanent; restart to re-attempt real API

**Provider Selection:**
- `USE_YAHOO=true` → YahooFinanceProvider
- `INDIAN_STOCK_API_KEY` set → FallbackProvider (IndianAPI + simulator)
- Neither → SimulatorProvider (default)
- Implementation: `backend/market/factory.py` - `create_market_provider()`

## Data Storage

**Databases:**
- SQLite 3 (built-in)
  - Connection: `db/finally.db` (development) or `/app/data/finally.db` (Docker volume)
  - Client: `aiosqlite` 0.22.1+ - async SQLite driver
  - Path: Volume-mounted at `/app/data` in Docker for persistence across restarts
  - Lazy initialization: schema created and default data seeded at startup via `backend/db/database.py:init_db()`
  - Schema: `backend/db/schema.sql`

**Tables:**
- `users_profile` - User cash balance and metadata
- `watchlist` - User's watched tickers (composite key: user_id, ticker)
- `positions` - Current holdings (composite key: user_id, ticker); deleted when quantity reaches zero
- `trades` - Append-only trade history (indexed on user_id, executed_at)
- `portfolio_snapshots` - Portfolio value snapshots every 30s (indexed on user_id, recorded_at)
- `chat_messages` - Conversation history with LLM (indexed on user_id, created_at)
- `users` - User authentication (username, password_hash)

**File Storage:**
- Local filesystem only — no external object storage
- Frontend static files served from `backend/static/` (populated during Docker build from Next.js export)

**Caching:**
- In-memory provider cache: each market data provider maintains dict[str, StockPrice] of latest prices
- Rolling history buffer: each provider stores up to 200 price points per ticker

## Authentication & Identity

**Auth Provider:**
- Custom JWT implementation (not delegated to external service)
- Implementation: `backend/app/auth.py` - uses `python-jose[cryptography]` 3.5.0+
- Algorithm: HS256
- Token expiry: 7 days
- Secret: `JWT_SECRET` env var (defaults to dev-secret; warns if not set in logs)

**Password Security:**
- Hashing: bcrypt 4.0.0+ via `bcrypt.hashpw()` and `bcrypt.gensalt()`
- Verification: constant-time `bcrypt.checkpw()`

**Auth Flow:**
- POST `/api/auth/register` - Create new user account
- POST `/api/auth/login` - Authenticate with username/password
- POST `/api/auth/guest` - Auto-login to demo account (creates if doesn't exist)
- Frontend stores JWT in `localStorage` under key `finally_token`
- All API requests include `Authorization: Bearer {token}` header (see `frontend/lib/api.ts`)

**Token Endpoints:**
- Bearer tokens sent in HTTP header for all authenticated endpoints
- SSE stream (`/api/stream/prices`) extracts user_id from token for per-user watchlist filtering

## Monitoring & Observability

**Error Tracking:**
- Not detected - no external error tracking service configured

**Logs:**
- Python logging module with basicConfig: level INFO
- Logger format: default (module name prefix)
- Backend logs to stdout (suitable for Docker container logging)
- Market data providers log warnings on API failures, rate-limits, quota issues
- LLM errors logged to `logger` (module: "finally.llm")

## CI/CD & Deployment

**Hosting:**
- Docker container (single-container deployment)
- Port: 8000 (exposed)
- No native cloud-specific integrations; container can deploy to any Docker-compatible platform

**Container Structure:**
- Multi-stage Dockerfile: Node 20-slim → Python 3.12-slim
- Dependency installation: `uv sync --frozen --no-dev`
- Static frontend files copied from Node build to `/app/static`

**CI Pipeline:**
- Not detected - no GitHub Actions, GitLab CI, or other CI service configured

**Deployment:**
- Start: `scripts/start_mac.sh` or `scripts/start_windows.ps1` (wraps `docker run`)
- Environment: Docker runs with `--env-file .env` for credentials
- Database: Volume mount at `/app/data` persists SQLite across restarts

## Environment Configuration

**Required env vars:**
- `OPENROUTER_API_KEY` - OpenRouter API key for LLM chat (for Cerebras inference via LiteLLM)

**Optional env vars:**
- `INDIAN_STOCK_API_KEY` - IndianAPI.in key for real NSE/BSE data
- `USE_YAHOO` - Set to "true" to use Yahoo Finance instead of IndianAPI (free, ~15 min delay)
- `DAILY_RUNTIME_HOURS` - Adjusts IndianAPI poll interval (default 24); set to your actual hours/day
- `LLM_MOCK` - Set to "true" for deterministic mock LLM responses (testing only)
- `JWT_SECRET` - JWT signing secret (defaults to dev-secret; should be set in production)

**Secrets location:**
- `.env` file at project root (gitignored, not committed)
- `.env.example` committed as template
- Docker reads env file via `--env-file .env` flag at container startup

## Webhooks & Callbacks

**Incoming:**
- Not detected - no webhook endpoints for external services

**Outgoing:**
- Not detected - no outbound webhooks to external services

---

## LLM Integration (ChatGPT-compatible)

**Service:**
- OpenRouter (proxy to multiple LLM providers)

**SDK/Client:**
- `litellm` 1.40.0+ - LLM abstraction layer
- Model: `openrouter/openai/gpt-oss-120b`
- Provider: Cerebras (fast inference backend)

**Auth:**
- API key: `OPENROUTER_API_KEY` env var

**Integration Point:**
- `backend/app/routes/chat.py` - POST `/api/chat` endpoint
- `backend/app/llm.py` - Portfolio context building, prompt construction, structured output parsing
- Structured output schema: JSON with `message` (required), `trades` (optional array), `watchlist_changes` (optional array)
- Response: Complete JSON (no token streaming) — fast enough due to Cerebras inference
- Auto-execution: Trades and watchlist changes in LLM response are validated and executed immediately

**Mock Mode:**
- `LLM_MOCK=true` env var - Returns deterministic mock response for E2E tests
- Mock response: `{"message": "Mock response: portfolio looks good!", "trades": [], "watchlist_changes": []}`
- Used in Playwright E2E tests for reproducibility and speed

---

*Integration audit: 2026-05-02*
