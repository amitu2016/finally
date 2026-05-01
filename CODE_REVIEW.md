# Code Review — FinAlly AI Trading Workstation

**Reviewer:** Claude (Anthropic)
**Date:** 2026-05-01
**Branch:** `main` (post-PR #19)
**Scope:** Full codebase review — backend, frontend, infrastructure, tests

---

## Executive Summary

FinAlly is a well-structured full-stack trading workstation with a clean layered architecture. The market data abstraction, database layer, and LLM integration demonstrate strong engineering. However, several critical defects were found: **the frontend `lib/` module directory is entirely missing**, breaking the build; the `IndianAPIProvider` exhausts its monthly API quota in under 10 minutes; a test stubs the wrong function name (patching `completion` instead of `acompletion`); and an E2E test suite that predates the authentication system and will not pass.

Severity legend: 🔴 Critical — 🟠 High — 🟡 Medium — 🟢 Low/Style

---

## 1. Critical Issues

### 🔴 1.1 Missing `frontend/lib/` Directory

**Files:** `frontend/components/*.tsx`, `frontend/hooks/*.ts`

Every frontend module imports from `@/lib/api`, `@/lib/types`, `@/lib/auth`, and `@/lib/format`:

```ts
import { api } from "@/lib/api";
import type { AuthUser } from "@/lib/auth";
import { formatINR, pnlColor } from "@/lib/format";
import type { PriceTick, WatchlistEntry } from "@/lib/types";
```

The `frontend/lib/` directory does not exist in the repository. The TypeScript path alias `@/* → ./*` (defined in `tsconfig.json`) resolves `@/lib/api` to `frontend/lib/api.ts`, which is absent. The frontend **cannot be built** from a fresh checkout in its current state.

**Fix:** Commit the missing `lib/` files (`api.ts`, `types.ts`, `auth.ts`, `format.ts`) to the repository.

---

### 🔴 1.2 `IndianAPIProvider` Exhausts Monthly Quota in ~8 Minutes

**File:** `backend/market/indian_api.py:142–158`

The `_poll_loop` calls `_poll_all` every `FAST_POLL_INTERVAL = 1.0` second. `_poll_all` fetches all tickers concurrently:

```python
async def _poll_all(self, client: httpx.AsyncClient) -> int:
    results = await asyncio.gather(
        *[self._poll_one(client, t) for t in self._tickers]
    )
```

With 10 default tickers, this makes **10 API calls per second = 36,000 calls/hour**. The monthly quota is 5,000 calls, which is exhausted in **~8 minutes** — not one month.

The `PLAN.md` specification explicitly requires round-robin single-ticker polling every ~576 seconds to stay within quota:

> *Round-robin single-ticker polling (not concurrent) to strictly honor rate limits. With 10 tickers, each is refreshed ~every 96 minutes (576s × 10).*

The implemented `FAST_POLL_INTERVAL` constant and the comment "Fetch all tickers concurrently" directly contradict this.

**Fix:** Implement round-robin single-ticker polling with a calculated interval derived from the remaining monthly budget. Remove `asyncio.gather` from `_poll_all`.

---

### 🔴 1.3 Test Stubs Wrong LLM Function Name

**File:** `backend/tests/test_llm.py:111, 130–131`

`llm.py` imports and calls `acompletion`:

```python
# llm.py
from litellm import acompletion
response = await acompletion(model=MODEL, ...)
```

The test stubs `app.llm.completion` (synchronous) instead of `app.llm.acompletion`:

```python
mock_completion = mocker.patch(
    "app.llm.completion", return_value=_make_completion_response(payload)
)
result = await llm.call_llm(...)
mock_completion.assert_called_once()  # never called — wrong name
```

The mock does not intercept the real `acompletion` call. `test_real_mode_invokes_completion` and `test_chat_executes_buy_trade` will either call the real OpenRouter endpoint (failing without a key) or produce incorrect results.

**Fix:** Change all mock paths from `"app.llm.completion"` to `"app.llm.acompletion"`.

---

### 🔴 1.4 E2E Tests Predate Authentication System

**File:** `test/e2e/basic.spec.ts`

```ts
test('has title and default watchlist', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('RELIANCE')).toBeVisible();
```

The application now shows an `AuthGate` login screen before any watchlist content. The test navigates to `/` and immediately looks for `RELIANCE`, which will not be visible until the user authenticates. Both E2E tests will fail.

Additionally, `test('can navigate to trade section')` checks for text `'Portfolio Value'` and `'Cash Balance'`, but the actual `Header` component displays the labels `"Total Value"` and `"Cash"` (see `frontend/components/Header.tsx:36,40`).

**Fix:** Update E2E tests to handle the auth flow (guest login or seeded credentials) before asserting on application state.

---

## 2. High-Priority Issues

### 🟠 2.1 Test Incorrectly Subscripts Watchlist List Response

**File:** `backend/tests/test_routes.py:137`

```python
r = client.post("/api/watchlist", json={"ticker": "BAJFINANCE"})
assert r.status_code == 201
assert r.json()["ticker"] == "BAJFINANCE"   # ← TypeError: list indices must be integers
```

The `POST /api/watchlist` endpoint returns the full watchlist as `list[dict]`. Subscripting a list with a string key raises `TypeError`. The assertion should find the entry in the list:

```python
entries = r.json()
assert any(e["ticker"] == "BAJFINANCE" for e in entries)
```

---

### 🟠 2.2 Insecure JWT Secret Default

**File:** `backend/app/auth.py:11`

```python
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
```

The fallback `"dev-secret-change-in-production"` is publicly visible in the source code. If the `JWT_SECRET` environment variable is not set (e.g., a docker run without `--env-file`), all JWT tokens are signed with a known key, allowing trivial token forgery.

**Fix:** Make the application fail fast if `JWT_SECRET` is absent in production mode, or generate and persist a random key on first startup.

---

### 🟠 2.3 `TradeBar` Ticker Input Desynchronizes from Selection

**File:** `frontend/components/TradeBar.tsx:13`

```tsx
const [ticker, setTicker] = useState(initialTicker ?? "");
```

`useState` initializes from `initialTicker` once, at mount. When the user selects a different ticker in the watchlist, `initialTicker` changes but the trade bar's input does not update. The user must manually retype the ticker every time they switch the chart view.

**Fix:** Add a `useEffect` to sync the state when `initialTicker` changes:

```tsx
useEffect(() => {
  if (initialTicker) setTicker(initialTicker);
}, [initialTicker]);
```

---

### 🟠 2.4 Token Exposed in SSE URL Query Parameter

**File:** `frontend/hooks/useMarketData.ts:23–24`

```ts
const url = token ? `/api/stream/prices?token=${encodeURIComponent(token)}` : "/api/stream/prices";
```

The JWT token is appended as a query parameter because `EventSource` does not support custom headers. This means the token appears in server access logs, browser history, and proxy logs.

**Fix:** Issue a short-lived (30–60s) SSE-specific token on demand from a new endpoint (e.g., `POST /api/auth/sse-token`), and use that one-time token in the query parameter instead of the long-lived session JWT.

---

### 🟠 2.5 Shared Guest Account Creates Data Collision

**File:** `backend/app/routes/auth.py:61–70`

```python
@router.post("/api/guest")
async def guest_login(db):
    user = await queries.get_user_by_username(db, DEMO_USERNAME)
    if not user:
        user = await queries.create_user(db, DEMO_USERNAME, hash_password(DEMO_PASSWORD))
    return {"token": create_token(user["id"]), ...}
```

All guest users receive a token for the same shared `"demo"` account. Any guest can deplete the shared cash balance, fill positions, or spam the chat — ruining the experience for all other concurrent guests.

**Fix:** Create a fresh ephemeral user per guest session (or per IP), or use a read-only demo mode. If keeping the shared account, add a periodic reset job.

---

## 3. Medium-Priority Issues

### 🟡 3.1 `DAILY_RUNTIME_HOURS` Environment Variable Unused

**Files:** `.env.example`, `PLAN.md`

`.env.example` documents `DAILY_RUNTIME_HOURS` for adjusting the IndianAPI poll interval, but no code reads this variable. `PLAN.md` states it should affect the quota interval calculation. This dead documentation misleads operators.

**Fix:** Either implement the variable in `IndianAPIProvider` or remove it from `.env.example`.

---

### 🟡 3.2 `PORT` Environment Variable in Dockerfile Is Unused

**File:** `Dockerfile:39`

```dockerfile
ENV PORT=8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`ENV PORT=8000` is set but the `CMD` hardcodes `--port 8000`. The `PORT` env var has no effect. Container orchestrators (App Runner, Cloud Run) typically inject `PORT` at runtime, and the server would still bind to 8000.

**Fix:** Reference the variable: `"--port", "${PORT:-8000}"` — or use uvicorn's `--port $PORT` idiom (requires a shell entrypoint).

---

### 🟡 3.3 Unpinned `uv` Version in Dockerfile

**File:** `Dockerfile:14`

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
```

`:latest` means every `docker build` may pull a different `uv` version. A breaking change in `uv` would silently break builds.

**Fix:** Pin to a specific version: `ghcr.io/astral-sh/uv:0.6.x`.

---

### 🟡 3.4 SSE Opens a DB Connection Per Tick (Every 5 Seconds)

**File:** `backend/app/routes/prices.py:52–54`

```python
if now - last_refresh >= WATCHLIST_REFRESH:
    async with get_db(db_path) as conn:
        tickers = set(await queries.get_watchlist(conn, user_id))
    last_refresh = now
```

Each SSE client opens a new SQLite connection every `WATCHLIST_REFRESH = 5.0` seconds. With 100 concurrent users, that is 20 connection opens/second. SQLite handles this fine due to its lightweight connection model, but the pattern does not scale.

**Note:** The Gemini review claimed this happened every 0.5s (every SSE tick). The actual code uses a 5-second cache, which is much better, but the concern about connection churn at scale remains.

**Fix for scale:** Share a per-user watchlist cache in app state and invalidate it on watchlist mutations.

---

### 🟡 3.5 `PriceCell` Flash Effect Has Double-Trigger on Flash State Change

**File:** `frontend/components/PriceCell.tsx:14–24`

```tsx
useEffect(() => {
  ...
  previous.current = price;
  if (!flash) return;
  const t = setTimeout(() => setFlash(""), 500);
  return () => clearTimeout(t);
}, [price, flash]);
```

`flash` is included in the dependency array, so setting `setFlash("flash-up")` causes the effect to re-run. On the second run, `previous.current` has already been updated to the new price, so no flash is re-set and a new timeout is created. The animation works correctly but the logic is confusing and the double-run wastes a microtask cycle.

**Fix:** Use a separate `useEffect` for the timeout cleanup, with only `flash` in its dependency array:

```tsx
useEffect(() => {
  if (!flash) return;
  const t = setTimeout(() => setFlash(""), 500);
  return () => clearTimeout(t);
}, [flash]);
```

---

### 🟡 3.6 No Rate Limiting on Trade and Watchlist Endpoints

**File:** `backend/app/routes/portfolio.py`, `backend/app/routes/watchlist.py`

The guest chat limit (`GUEST_DAILY_LIMIT = 10`) exists, but trade and watchlist endpoints have no rate limiting. A malicious or runaway client could spam hundreds of trades per second, generating enormous `portfolio_snapshots` table growth (one snapshot per trade).

**Fix:** Add a simple per-user rate limit on trade execution (e.g., 10 trades/minute).

---

### 🟡 3.7 `portfolio_snapshots` Table Has No Cleanup

**File:** `backend/app/main.py:33–49`

A snapshot is written every 30 seconds plus after every trade. After 30 days, a single user accumulates 86,400 snapshots from the background loop alone. The `get_snapshots` query caps reads at 500 rows, but the table grows unboundedly.

**Fix:** Periodically delete snapshots older than N days, or use a downsampling strategy (keep 1/hour after 24h, 1/day after 7d).

---

### 🟡 3.8 No Validation That Ticker Exists Before Watchlist Add

**File:** `backend/app/routes/watchlist.py:47–54`

```python
ticker = body.ticker.upper()
existing = await queries.get_watchlist(db, user_id)
if ticker in existing:
    raise HTTPException(status_code=409, ...)
await queries.add_to_watchlist(db, user_id, ticker)
```

Any string up to 20 characters can be added to the watchlist (e.g., `"NOTREAL"`, `"🚀🚀🚀"`). The market provider will track these and return null prices indefinitely, cluttering the UI.

**Fix:** Validate the ticker against a known NSE/BSE list, or verify the market provider returns a non-null price before accepting the add.

---

### 🟡 3.9 `DEFAULT_WATCHLIST` Exported from Wrong Module

**File:** `backend/db/database.py:14`

```python
from .queries import DEFAULT_WATCHLIST
```

`database.py` re-exports `DEFAULT_WATCHLIST` from `queries.py` so that `test_db.py` can import it from `db.database`. This creates a circular dependency risk and blurs module responsibility. Constants shared by both modules should live in a dedicated `constants.py` or at the package level.

---

### 🟡 3.10 `test_db.py` Missing `users` Table Assertion

**File:** `backend/tests/test_db.py:31–45`

```python
expected = {
    "users_profile", "watchlist", "positions",
    "trades", "portfolio_snapshots", "chat_messages",
}
```

The `users` table (for auth) is created in `schema.sql` but is missing from the expected set. A regression that drops or renames this table would not be caught by this test.

---

## 4. Low-Priority / Style Issues

### 🟢 4.1 Duplicate `DEFAULT_USER` / `DEFAULT_USER_ID` Constants

`backend/db/queries.py:11` defines `DEFAULT_USER = "default"`.
`backend/db/database.py:18` defines `DEFAULT_USER_ID = "default"`.
`backend/app/portfolio.py:12` defines `DEFAULT_USER = "default"`.

All three are the same value. A single source-of-truth constant would prevent drift.

---

### 🟢 4.2 `FakeProvider` Duplicated Across Test Files

`backend/tests/test_routes.py` and `backend/tests/test_llm.py` each define their own `FakeProvider` class with identical interfaces. Extracting to `backend/tests/conftest.py` or a shared `backend/tests/helpers.py` removes the duplication.

---

### 🟢 4.3 `TradeBar` `onTrade` Return Type Is `unknown`

**File:** `frontend/components/TradeBar.tsx:8`

```ts
interface Props {
  onTrade: (req: TradeRequest) => Promise<unknown>;
}
```

The actual return value is `Portfolio`, which the caller (`usePortfolio.executeTrade`) already types correctly. Using `unknown` here weakens type safety. Change to `Promise<Portfolio>`.

---

### 🟢 4.4 `asyncio.get_event_loop()` Deprecation

**File:** `backend/app/routes/prices.py:51`

```python
now = asyncio.get_event_loop().time()
```

`asyncio.get_event_loop()` is deprecated since Python 3.10 and emits a `DeprecationWarning` when called from a context without a running loop. Replace with `asyncio.get_running_loop().time()`.

---

### 🟢 4.5 `PortfolioHeatmap` Content Prop Interface Fragility

**File:** `frontend/components/PortfolioHeatmap.tsx:29–37`

```ts
interface ContentProps {
  x?: number; y?: number; width?: number; height?: number;
  ticker?: string; pnl_pct?: number; fill?: string;
}
```

Recharts injects custom data keys into the `Content` component through undocumented internals. If Recharts changes how it passes data, the `ticker` and `pnl_pct` props would silently become `undefined`. Consider defensive defaults or a library upgrade that provides a stable content API.

---

### 🟢 4.6 `useWatchlist` `addTicker` Misses `refresh` Dependency

**File:** `frontend/hooks/useWatchlist.ts:37–44`

```ts
const addTicker = useCallback(
  async (ticker: string) => {
    ...
    const updated = await api.addWatchlist(cleaned);
    setEntries(updated);
  },
  [],  // ← empty deps, but setEntries is stable so this is OK
);
```

The empty dependency array is technically correct (`setEntries` from `useState` is stable), but omitting `setEntries` from the `useCallback` deps will trigger an ESLint `react-hooks/exhaustive-deps` warning. Adding `[]` without explanation is a code smell.

---

### 🟢 4.7 No `no-console` Discipline in Frontend

No linting configuration is present (`eslint.config.*` is absent). The project does not enforce consistent error handling or `console.log` discipline on the frontend. Adding an ESLint config with `@typescript-eslint` and `eslint-plugin-react-hooks` would catch several of the issues above at development time.

---

## 5. Architecture Observations

### Multi-User vs. Single-User Design Tension

`PLAN.md` specified a no-login single-user design. The implementation added a full JWT auth system with registration, login, and guest access. This is a positive evolution but the schema still seeds a `"default"` user profile (via `init_db`), which is now orphaned — the legacy `DEFAULT_USER = "default"` profile never gets a corresponding `users` row, making it unreachable through the auth system.

**File:** `backend/db/database.py:41–49` — seeds `users_profile` for `"default"` but not `users`.

---

### Simulator `change_pct` Uses Seed Price, Not Previous Close

**File:** `backend/market/simulator.py:134–135`

```python
seed = SEED_PRICES.get(ticker, prev.price)
change_pct = round((new_price - seed) / seed * 100, 2)
```

The simulator calculates `change_pct` as the percentage change from the **initial seed price**, not from yesterday's close. After the server has been running for days, `change_pct` for a drifted ticker may show `+150%`. Real market data providers use the previous day's close. This creates a UX inconsistency when mixing simulator and real providers.

---

### Race Condition in Multi-Client Watchlist Updates

When two concurrent clients add different tickers simultaneously, the sequence:
1. Client A calls `get_watchlist` → [R, T, H]
2. Client B calls `get_watchlist` → [R, T, H]
3. Client A adds X → DB = [R, T, H, X]
4. Client B adds Y → DB = [R, T, H, Y] (X lost from the perspective of this read)

Both clients then call `provider.set_tickers(all_tickers)`, which correctly reads all distinct tickers across all users. The market provider state is eventually consistent, but the watchlist route response returned to Client A does not include Y (and vice versa). This is an inherent limitation of the optimistic-read pattern without transactions or locking. For a single-user demo, this is acceptable.

---

### `FallbackProvider` Does Not Re-Enable Primary After Quota Reset

**File:** `backend/market/fallback.py:76–83`

```python
async def _monitor_loop(self) -> None:
    while True:
        await asyncio.sleep(MONITOR_INTERVAL)
        if not self._using_fallback and self._primary.is_rate_limited:
            self._using_fallback = True
```

Once `_using_fallback` is `True`, `_monitor_loop` never sets it back to `False`. The fallback is documented as "permanent for the lifetime of this instance." However, `IndianAPIProvider` already implements monthly quota reset (`_maybe_reset_monthly_quota`), and `is_rate_limited` can transition from `True` to `False` on a month rollover. The `FallbackProvider` will not re-enable the primary even when the quota resets, requiring a full server restart. A comment in the code should make this restart requirement explicit, or the monitor should poll `is_rate_limited` and switch back when it clears.

---

## 6. Positive Highlights

- **Market data abstraction** (`backend/market/base.py`) is well-designed with a clean ABC interface, enabling easy addition of new providers.
- **LLM structured outputs** via Pydantic (`backend/app/schemas.py`) ensure type-safe response parsing and auto-execution of trades.
- **Database initialization** is idempotent and zero-config; `init_db` handles schema creation and seeding atomically.
- **Portfolio math** (weighted average cost, P&L calculation) is correct and well-tested.
- **SSE implementation** correctly caches the price snapshot (`provider.get_all_prices()`) rather than querying each price individually.
- **Dockerfile** uses a proper multi-stage build separating Node.js and Python runtimes.
- **`FallbackProvider`** design with a warm simulator standby is elegant — no cold-start on API failure.
- **Test coverage** for the database layer (`test_db.py`, `test_queries.py`) is thorough.
- **Visual design** matches the Bloomberg-terminal aesthetic described in `PLAN.md` with appropriate color tokens and price flash animations.
- **`bcrypt`** is used correctly for password hashing (cost factor from library default, not a fixed value).

---

## 7. Summary Table

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1.1 | 🔴 Critical | `frontend/` | `lib/` directory missing — frontend cannot build |
| 1.2 | 🔴 Critical | `market/indian_api.py` | Quota exhausted in ~8 min instead of 1 month |
| 1.3 | 🔴 Critical | `tests/test_llm.py` | Mocks `completion` instead of `acompletion` |
| 1.4 | 🔴 Critical | `test/e2e/basic.spec.ts` | E2E tests predate auth system, will fail |
| 2.1 | 🟠 High | `tests/test_routes.py:137` | List subscripted with string key → TypeError |
| 2.2 | 🟠 High | `app/auth.py:11` | Weak JWT secret fallback |
| 2.3 | 🟠 High | `components/TradeBar.tsx` | Ticker input desynchronizes from selection |
| 2.4 | 🟠 High | `hooks/useMarketData.ts` | JWT token exposed in SSE query parameter |
| 2.5 | 🟠 High | `routes/auth.py` | Shared guest account causes data collision |
| 3.1 | 🟡 Medium | `.env.example` | `DAILY_RUNTIME_HOURS` documented but unused |
| 3.2 | 🟡 Medium | `Dockerfile` | `PORT` env var unused; CMD hardcodes port |
| 3.3 | 🟡 Medium | `Dockerfile` | Unpinned `uv:latest` |
| 3.4 | 🟡 Medium | `routes/prices.py` | SSE opens DB conn every 5s per client |
| 3.5 | 🟡 Medium | `components/PriceCell.tsx` | Double-trigger flash effect |
| 3.6 | 🟡 Medium | `routes/portfolio.py` | No rate limiting on trade endpoint |
| 3.7 | 🟡 Medium | `db/queries.py` | `portfolio_snapshots` grows unboundedly |
| 3.8 | 🟡 Medium | `routes/watchlist.py` | No ticker existence validation |
| 3.9 | 🟡 Medium | `db/database.py` | `DEFAULT_WATCHLIST` re-exported from wrong module |
| 3.10 | 🟡 Medium | `tests/test_db.py` | Missing `users` table in expected set |
| 4.1–4.7 | 🟢 Low | Various | Duplicate constants, deprecated API, missing linting |
| Arch | — | `db/database.py:41` | Legacy `"default"` profile has no `users` row |
| Arch | — | `market/simulator.py:134` | `change_pct` uses seed price, not prev close |
| Arch | — | `market/fallback.py:76` | Fallback never re-enables primary after quota reset |
