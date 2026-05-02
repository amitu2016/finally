# Codebase Concerns

**Analysis Date:** 2026-05-02

## Critical Issues

### Missing Frontend `lib/` Directory

**Files:** `frontend/tsconfig.json`, `frontend/components/*.tsx`, `frontend/hooks/*.ts`

Every frontend module imports from `@/lib/api`, `@/lib/types`, `@/lib/auth`, `@/lib/format`. The `frontend/lib/` directory does not exist in the repository. The build will fail at compile time with module not found errors.

**Impact:** Frontend cannot be built or deployed. Application cannot run.

**Fix approach:** Commit the missing library files (`api.ts`, `types.ts`, `auth.ts`, `format.ts`) to `frontend/lib/`. These files are referenced in the code review at `CODE_REVIEW.md` but are not in version control.

---

### Incorrect LLM Mock in Tests

**Files:** `backend/tests/test_llm.py` (lines 111, 130–131)

The test file patches `app.llm.completion` (synchronous function) but the actual code calls `acompletion` (async function). The mock never intercepts the real LLM call.

```python
# llm.py uses this:
from litellm import acompletion
response = await acompletion(model=MODEL, ...)

# test_llm.py patches this (wrong name):
mocker.patch("app.llm.completion", ...)  # should be acompletion
```

**Impact:** `test_real_mode_invokes_completion` and `test_chat_executes_buy_trade` either call the real OpenRouter endpoint (failing without valid API key) or produce incorrect test results. Tests are unreliable.

**Fix approach:** Change all mock patches from `"app.llm.completion"` to `"app.llm.acompletion"` in `test_llm.py`.

---

## High-Risk Issues

### Monthly API Quota Exhaustion in Minutes

**Files:** `backend/market/indian_api.py`

**Current behavior:** The `_poll_all()` function concurrently fetches all 10 tickers via `asyncio.gather()`, making 10 API calls every `FAST_POLL_INTERVAL = 1.0` second (hardcoded). This produces **36,000 calls/hour**, exhausting the 5,000-call monthly quota in approximately **8 minutes**, not one month.

**Specification requirement (from `PLAN.md`):**
> "Round-robin single-ticker polling (not concurrent) to strictly honor rate limits. With 10 tickers, each is refreshed ~every 96 minutes (576s × 10)."

**Impact:** When using `IndianAPIProvider` or `FallbackProvider`, the API quota is consumed almost immediately, forcing fallback to the simulator or blocking all real market data. Users cannot rely on live Indian stock data in production.

**Fix approach:**
1. Implement round-robin single-ticker polling instead of concurrent polling
2. Calculate `QUOTA_CALL_INTERVAL` based on monthly runtime hours and quota (already calculated at `backend/market/indian_api.py:29–41`, but not used in `_poll_all`)
3. Refactor `_poll_loop` to poll one ticker per interval, cycling through the watchlist
4. Remove `asyncio.gather()` from `_poll_all` or eliminate concurrent fetching

---

### E2E Test Suite Incompatible with Authentication System

**Files:** `test/e2e/basic.spec.ts`

The E2E tests assume direct access to the trading app without authentication:
```typescript
await expect(page.getByText('RELIANCE')).toBeVisible();  // expects watchlist to appear on /
```

However, the application requires login (guest or registered) to view the trading interface. The tests call `guestLogin()` within test functions, but do not account for the possibility that the guest login endpoint may have rate limiting (see `GUEST_DAILY_CHAT_LIMIT` in `backend/app/routes/chat.py:26`). Tests may fail due to quota exhaustion.

**Impact:** E2E test suite will not pass against the running application. CI/CD pipelines that rely on these tests will fail.

**Fix approach:**
1. Verify guest login endpoint works correctly with E2E tests
2. Ensure E2E tests run with `LLM_MOCK=true` to avoid consuming the daily chat limit
3. Add rate-limit handling or per-test guest account creation if needed

---

## Security Concerns

### Hardcoded JWT Secret in Development

**Files:** `backend/app/auth.py:14–21`

The JWT secret defaults to `"dev-secret-change-in-production"` if `JWT_SECRET` environment variable is not set. A warning is logged, but the application continues with an insecure default.

```python
_DEFAULT_SECRET = "dev-secret-change-in-production"
SECRET_KEY = os.getenv("JWT_SECRET", _DEFAULT_SECRET)

if SECRET_KEY == _DEFAULT_SECRET:
    logger.warning("JWT_SECRET is not set — using insecure default...")
```

**Risk:** Any deployment that accidentally omits `JWT_SECRET` from environment will use a predictable secret, allowing attackers to forge authentication tokens and access any user account.

**Current mitigation:** Warning is logged, `.env.example` documents the need for this variable.

**Recommendations:**
1. Raise an exception at startup if `JWT_SECRET` is not explicitly set (fail fast in production)
2. Ensure Docker deployment scripts and .env setup documentation are explicit about this requirement
3. Consider generating a random secret automatically on first startup if file-based persistence is added

---

### Token Passed in Query String for SSE

**Files:** `frontend/hooks/useMarketData.ts:24`, `backend/app/dependencies.py:43–51`

JWT tokens are passed as query parameters for SSE streams to work around EventSource API limitations (no header support):
```typescript
const url = token ? `/api/stream/prices?token=${encodeURIComponent(token)}` : "/api/stream/prices";
const es = new EventSource(url);
```

**Risk:** Query parameters are typically logged in server logs, browser history, and HTTP access logs, potentially exposing authentication tokens in plaintext. URLs may be cached or forwarded in headers.

**Current mitigation:** Tokens have a 7-day expiration (`TOKEN_EXPIRE_DAYS = 7` in `auth.py:23`). SSE is only for price data (read-only).

**Recommendations:**
1. Use token rotation: issue short-lived SSE tokens separate from main JWT
2. Document this risk in the security section of `PLAN.md`
3. Consider adding a proxy layer that accepts Bearer auth and forwards it to EventSource-compatible streaming

---

## Performance Bottlenecks

### Portfolio Snapshot Recording Every 30 Seconds

**Files:** `backend/app/main.py:33–65`

A background loop records portfolio snapshots every `SNAPSHOT_INTERVAL = 30` seconds for **all users** simultaneously. With many users, this can cause SQLite contention.

```python
SNAPSHOT_INTERVAL = 30
async def _snapshot_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        async with get_db(app.state.db_path) as db:
            user_ids = await queries.get_all_user_ids(db)
            for user_id in user_ids:
                await queries.record_snapshot(db, user_id, total)
```

**Impact:** At scale (100+ concurrent users), SQLite may experience write lock contention. The 30-second snapshot interval may cause noticeable latency in trade execution.

**Fix approach:**
1. For single-container deployments, consider increasing `SNAPSHOT_INTERVAL` to 60–120 seconds
2. Batch snapshot writes or use a write queue to avoid sequential DB transactions
3. Monitor SQLite busy timeout settings in `aiosqlite.connect()`
4. At scale, migrate to a more capable database (PostgreSQL)

---

### Market Data Provider Warm Start Delay with IndianAPI + Fallback

**Files:** `backend/market/fallback.py:41–48`

When using `FallbackProvider`, both the primary `IndianAPIProvider` and `SimulatorProvider` start simultaneously. The simulator adds latency to startup and consumes memory even if the primary never fails.

```python
async def start(self) -> None:
    await self._fallback.start()  # simulator starts immediately
    await self._primary.start()   # primary starts after
    self._monitor_task = asyncio.create_task(self._monitor_loop())
```

**Impact:** Startup takes longer (simulator generates initial prices), and memory is used unnecessarily in most deployments. If primary is fast, fallback startup adds no value.

**Fix approach:**
1. Start simulator only after a delay (e.g., 5–10 seconds) to verify primary is working
2. Alternatively, lazily start simulator on-demand when primary is rate-limited
3. Document the trade-off: faster fallback vs. delayed startup

---

## Fragile Areas

### Frontend Sparkline Data Lost on SSE Reconnect

**Files:** `frontend/hooks/useMarketData.ts:45–54`

Sparkline data (mini-chart price history) is accumulated in React state and resets whenever the SSE connection reconnects. Users see a gap in the chart.

```typescript
es.onmessage = (evt) => {
  // On reconnect, setSparklines is reset to empty object
  setSparklines((prev) => {
    const next = { ...prev };
    for (const tick of ticks) {
      arr.push(tick.price);
      if (arr.length > SPARK_LIMIT) arr.shift();
      next[tick.ticker] = arr;
    }
    return next;
  });
};
```

**Why fragile:** Connection can drop due to browser tab backgrounding, network hiccup, or server restart. Sparklines are lost and reset to empty. Main chart recovers by fetching `/api/prices/{ticker}/history`, but sparklines do not.

**Safe modification:** On reconnect, fetch recent history from the backend to populate sparklines. Alternatively, store sparklines in localStorage (simpler but less accurate).

**Test coverage:** No tests for reconnection behavior.

---

### LLM Chat Error Handling Obscures Root Cause

**Files:** `backend/app/routes/chat.py:114–121`

When the LLM call fails, the error is caught broadly and a generic fallback message is returned:

```python
try:
    response: ChatResponse = await call_llm(messages, portfolio_context)
except Exception:
    logger.exception("LLM call failed")
    return {"message": "Sorry, I couldn't process that request right now.", ..., "errors": ["llm_call_failed"]}
```

**Why fragile:** The user sees only `"llm_call_failed"` without details (timeout, malformed response, API rate limit, etc.). Frontend cannot distinguish between transient errors (retry) and permanent errors (no API key). Debugging in production is difficult.

**Safe modification:**
1. Catch specific exceptions: `OpenRouterException`, `TimeoutError`, `ValidationError`
2. Return structured error codes: `"llm_timeout"`, `"llm_invalid_response"`, `"llm_api_error"`
3. Add retry logic in the frontend for transient errors

---

### No Validation of Trade Quantity and Price Bounds

**Files:** `backend/app/portfolio.py:72–132`

Trade execution does not validate that:
- Quantity is positive
- Quantity is not absurdly large (e.g., 1,000,000,000 shares)
- Price is reasonable
- Trade doesn't cause integer overflow

```python
async def execute_trade(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    ticker: str,
    side: str,
    quantity: float,  # no min/max validation
    user_id: str = DEFAULT_USER,
) -> dict[str, Any]:
```

**Risk:** While SQLite handles large floats, malicious or buggy LLM responses could execute a "buy 999999999999 shares" trade, instantly draining the user's portfolio or creating nonsensical positions. Frontend has some validation but backend should not trust it.

**Fix approach:** Add schema validation in `execute_trade()`:
```python
if quantity <= 0 or quantity > 1_000_000:
    raise TradeError(422, "Invalid quantity")
if price <= 0 or price > 1_000_000:
    raise TradeError(422, "Invalid price")
```

---

### Race Condition in Watchlist Updates

**Files:** `backend/app/routes/prices.py:36–64`, `backend/app/routes/watchlist.py`

The SSE price stream reads the watchlist from the database every 5 seconds (`WATCHLIST_REFRESH = 5.0`). If a user removes a ticker from their watchlist, it may still be streamed for up to 5 seconds, and the market provider may still be polling it.

```python
if now - last_refresh >= WATCHLIST_REFRESH:
    async with get_db(db_path) as conn:
        tickers = set(await queries.get_watchlist(conn, user_id))
    last_refresh = now
```

**Impact:** Minor — the price continues streaming until the next refresh cycle. The frontend will ignore prices for removed tickers, so the user sees no effect. However, the backend market provider may poll removed tickers longer than necessary, wasting API quota.

**Fix approach:**
1. Reduce `WATCHLIST_REFRESH` to 1–2 seconds
2. Publish watchlist changes to the SSE stream so clients can reconnect or notify the server
3. Use a message queue or pub/sub system for watchlist updates (scale consideration, not critical now)

---

## Test Coverage Gaps

### No Unit Tests for Trade Validation Edge Cases

**Files:** `backend/tests/test_routes.py`

Tests for trade execution exist but do not cover:
- Fractional shares (currently supported but untested: `quantity: float`)
- Very small quantities (0.001 shares, rounding errors)
- Very large quantities (near integer limits)
- Negative quantities
- Selling at a loss (P&L calculation correctness)
- Zero-cash balance edge case

**Risk:** Subtle bugs in arithmetic (e.g., average cost calculation when quantity → 0) could go undetected.

**Priority:** Medium — application is working, but math should be verified.

---

### No Integration Tests for Multi-User Scenarios

**Files:** `backend/tests/`

All tests use the hardcoded `DEFAULT_USER`. No tests verify:
- Two users have separate portfolios and watchlists
- One user's trade does not affect another's P&L
- Snapshot recording for multiple users simultaneously

**Risk:** If a future refactor accidentally shares state between users, tests will not catch it.

**Priority:** Medium — currently single-user in practice, but multi-user is in the schema.

---

### E2E Tests Incomplete

**Files:** `test/e2e/basic.spec.ts`

Only two tests exist:
1. Check that default watchlist appears
2. Check that header is visible

Missing:
- Buying shares (trade execution)
- Selling shares
- Adding/removing from watchlist
- Chat with AI (would require mocking)
- P&L calculations
- Price streaming (prices update in real-time)
- Error conditions (insufficient cash, invalid ticker)

**Impact:** Deployment confidence is low. No verification that the core user flow (trade, view P&L) works end-to-end.

**Fix approach:** Expand E2E test suite with critical paths before production release.

---

## Missing Critical Features

### No Input Sanitization for Ticker Symbols

**Files:** `backend/app/routes/watchlist.py`, `backend/app/routes/portfolio.py`

Ticker symbols are passed as user input and used directly in database queries. While parameterized queries prevent SQL injection, no validation checks that tickers are reasonable (e.g., uppercase, alphanumeric only).

```python
async def add_to_watchlist(req: AddWatchlistRequest) -> ...:
    ticker = req.ticker  # could be "'; DROP TABLE users; --"
    await queries.add_to_watchlist(db, user_id, ticker)
```

**Risk:** While parameterized queries are safe, accepting arbitrary strings as tickers could create garbage data. A user could add a ticker named `"'; -- MALICIOUS"` and pollute the database.

**Fix approach:** Add a regex validator to the Pydantic schema:
```python
class AddWatchlistRequest(BaseModel):
    ticker: str = Field(..., regex=r"^[A-Z0-9]{1,10}$")
```

---

### No Rate Limiting on API Endpoints

**Files:** `backend/app/main.py`, `backend/app/routes/*.py`

There is a daily chat limit for guest accounts (`GUEST_DAILY_CHAT_LIMIT = 10` in `chat.py:26`), but no rate limiting on:
- `/api/portfolio/trade` — users could spam market orders
- `/api/watchlist` (add/remove) — users could modify watchlist rapidly
- `/api/portfolio` — users could poll constantly
- `/api/auth/register` — users could spam account creation

**Risk:** A malicious user could hammer trade endpoints, causing performance degradation or database overload. Without rate limiting, no protection against automated attacks.

**Fix approach:**
1. Add a rate-limit middleware (e.g., `slowapi` for FastAPI)
2. Implement per-user rate limits (e.g., 10 trades/minute, 100 portfolio reads/minute)
3. Document limits in API docs

---

### No Graceful Shutdown of Market Provider on Docker Stop

**Files:** `backend/app/main.py:90–98`, `Dockerfile:41`

The FastAPI lifespan cancels the snapshot task but relies on the market provider's `stop()` method being called. If the Docker container receives SIGTERM/SIGKILL before the lifespan exits, the provider task may be abandoned mid-operation.

```python
try:
    yield
finally:
    snapshot_task.cancel()
    await provider.stop()  # may not be called on SIGKILL
```

**Risk:** Minor in practice (the task will be cleaned up by the OS), but could leave resources open (e.g., HTTP connections) if the provider does not use context managers.

**Fix approach:** Ensure all provider tasks use try/finally or async context managers; add explicit shutdown grace period in Dockerfile.

---

## Dependencies at Risk

### Deprecated or Unmaintained Libraries

**Files:** `backend/pyproject.toml`, `frontend/package.json`

Not detected during exploration. Current dependencies appear actively maintained (FastAPI, Next.js, pydantic, aiosqlite). However:

- `yfinance` (for Yahoo Finance provider) is a third-party unofficial wrapper — Yahoo can change their API at any time
- `sse_starlette` is a community package, not part of FastAPI core — consider moving to FastAPI 0.104+ built-in streaming support if available

**Recommendations:**
1. Pin major.minor versions in lockfiles (done)
2. Set up dependabot or similar for security alerts
3. Periodically audit for unmaintained dependencies

---

## Scaling Limits

### SQLite Concurrency Ceiling

**Files:** `backend/app/main.py`, `backend/db/database.py:52–57`

SQLite uses file-level locking, which means only one write transaction can execute at a time. Under heavy load (100+ users trading simultaneously), write contention will become a bottleneck.

**Current capacity:** ~10–50 concurrent users (estimated, depends on trade frequency)

**Limit:** SQLite's `PRAGMA busy_timeout` (default 5000ms) will cause trade requests to hang or fail if write lock cannot be acquired within 5 seconds.

**Scaling path:**
1. At 50+ users: increase `busy_timeout` and monitor latency
2. At 100+ users: migrate to PostgreSQL (see `PLAN.md` note on database choice)
3. Implement connection pooling and prepared statements

---

## Architectural Anti-Patterns

### Broad Exception Handling Masks Real Errors

**Files:** `backend/app/main.py:63–64`, `backend/app/routes/chat.py:114–121`

```python
except Exception:
    logger.exception("snapshot loop error")  # continues silently
```

**Why it's wrong:** If the snapshot loop encounters a critical error (e.g., database corruption), the loop silently logs and continues, potentially skipping snapshots indefinitely without alerting the user or stopping the application.

**Better pattern:** Catch specific exceptions and let critical errors propagate:
```python
except (sqlite3.DatabaseError, asyncio.CancelledError):
    raise
except Exception:
    logger.exception("snapshot loop error")
```

---

### Global State via `request.app.state`

**Files:** `backend/app/main.py:75–80`, `backend/app/dependencies.py:16–18`

The market provider and database path are stored in FastAPI's `app.state` and accessed via request:

```python
# In lifespan
app.state.db_path = db_path
app.state.market = provider

# In dependency
def get_market(request: Request) -> MarketDataProvider:
    return request.app.state.market
```

**Why it's fragile:** If a dependency is used in a background task or outside the request context, `request.app.state` is unavailable. Testing requires mounting the app and creating a request context. Refactoring is error-prone.

**Better pattern:** Use a application context object or dependency injection container that doesn't require a request:
```python
# Alternative
app.market = provider  # Simple but less clean
# or
app.context = ApplicationContext(db_path, provider)  # DI pattern
```

---

*Concerns audit: 2026-05-02*
