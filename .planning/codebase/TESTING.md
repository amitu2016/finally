# Testing Patterns

**Analysis Date:** 2026-05-02

## Test Framework

**Backend (Python):**
- Runner: `pytest` 8.0.0+
- Config: `backend/pyproject.toml`
  - `asyncio_mode = "auto"` enables pytest-asyncio
  - `testpaths = ["tests"]` limits discovery to `backend/tests/` directory
- Key plugins: `pytest-asyncio>=0.23.0`, `pytest-mock>=3.14.0`, `respx>=0.21.0`

**Frontend (TypeScript):**
- Framework: Playwright `@playwright/test`
- Config: `test/playwright.config.ts`
- Test directory: `test/e2e/`
- Reporter: HTML report output
- Retry strategy: 2 retries in CI, 0 in local development

**Assertion Library:**
- Backend: `pytest` built-in assertions (no explicit import needed)
- Frontend: Playwright test assertions (`expect()`)

**Run Commands:**
```bash
# Backend unit tests
cd backend
uv run pytest

# Backend with coverage
uv run pytest --cov=.

# Backend watch mode (via pytest-watch if available)
uv run pytest-watch

# Frontend E2E tests
cd test
npx playwright test

# Frontend E2E watch mode
npx playwright test --headed --watch
```

## Test File Organization

**Location:**
- Backend: `backend/tests/` directory (co-located with source code parent)
  - Parallel structure to `backend/app/`, `backend/market/`, `backend/db/`
- Frontend: `test/e2e/` directory (separate from `frontend/`)
  - E2E tests run against full application stack

**Naming:**
- Backend: `test_<module>.py` (e.g., `test_routes.py`, `test_simulator.py`, `test_llm.py`)
- Frontend: `<feature>.spec.ts` (e.g., `basic.spec.ts`)

**Structure:**
```
backend/
├── tests/
│   ├── __init__.py              # Empty, marks directory as package
│   ├── conftest.py              # Shared fixtures and configuration
│   ├── test_simulator.py         # Market simulator tests
│   ├── test_factory.py           # Provider factory tests
│   ├── test_indian_api.py        # IndianAPI provider tests
│   ├── test_fallback.py          # Fallback provider tests
│   ├── test_yahoo.py             # Yahoo Finance provider tests
│   ├── test_market_interface.py  # Abstract interface compliance
│   ├── test_routes.py            # REST API route integration tests
│   ├── test_llm.py               # LLM chat integration tests
│   ├── test_queries.py           # Database CRUD tests
│   └── test_db.py                # Database initialization tests
└── conftest.py                   # pytest configuration (path setup)
```

## Test Structure

**Suite Organization:**
```python
# Example from test_routes.py
async def test_health(app_client):
    """Test the health endpoint returns 200 OK."""
    client, _ = app_client
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

**Patterns:**
- Test function names start with `test_` and describe behavior (not "testX")
- Async test functions use `async def test_<name>()`
- Test name reads like a sentence: `test_watchlist_add_and_remove`, `test_gbm_step_always_positive`
- Setup in fixtures decorated with `@pytest.fixture`
- Teardown via `yield` (context manager pattern) or context stack cleanup

**Fixture Setup Example (Python):**
```python
@pytest.fixture
async def app_client(tmp_path: Path) -> Iterator[tuple[TestClient, FakeProvider]]:
    db_path = str(tmp_path / "routes.db")
    await init_db(db_path)  # Initialize fresh DB

    provider = FakeProvider()
    # Populate stub data
    for ticker, price in [("RELIANCE", 2500.0), ("TCS", 3500.0)]:
        provider.add_price(ticker, price, prev=price * 0.99)

    # Create minimal FastAPI app with test dependencies
    app = FastAPI()
    app.state.db_path = db_path
    app.state.market = provider
    app.include_router(health_router)

    # Override dependency injection for testing
    async def _override_db():
        async with get_db(db_path) as conn:
            yield conn
    
    app.dependency_overrides[get_db_conn] = _override_db
    app.dependency_overrides[get_market] = lambda: provider

    with TestClient(app) as client:
        yield client, provider
```

## Mocking

**Framework:** `pytest-mock` plugin (provides `mocker` fixture)

**Patterns:**
```python
# Patch environment variables
monkeypatch.setenv("LLM_MOCK", "true")

# Mock function with return value
payload = ChatResponse(message="Hello!", trades=[])
mocker.patch(
    "app.llm.acompletion",
    return_value=_make_completion_response(payload)
)

# Spy on calls
spy = mocker.patch("app.llm.acompletion")
# ... call code ...
spy.assert_called_once()
spy.assert_not_called()

# Mock with side effects (raises exception)
mocker.patch("app.llm.acompletion", side_effect=RuntimeError("boom"))
```

**What to Mock:**
- External API calls (LLM via `app.llm.acompletion`, market APIs via mocked providers)
- Environment variables for feature toggles (`LLM_MOCK`, `USE_YAHOO`)
- Time-dependent operations (simulation loops)
- Async dependencies to accelerate tests

**What NOT to Mock:**
- Database operations (use `tmp_path` fixture for fresh SQLite file per test)
- Core business logic (trade execution, portfolio calculations)
- Internal function calls within the same module (test full flow)

## Fixtures and Factories

**Test Data:**
```python
# Example: FakeProvider stub for market data
class FakeProvider:
    def __init__(self) -> None:
        self.tickers: list[str] = []
        self._prices: dict[str, StockPrice] = {}

    def add_price(self, ticker: str, price: float, prev: float | None = None) -> None:
        """Add a price point to the fake provider."""
        prev_price = prev if prev is not None else price
        change_pct = ((price - prev_price) / prev_price * 100.0) if prev_price else 0.0
        sp = StockPrice(
            ticker=ticker,
            price=price,
            prev_price=prev_price,
            change_pct=change_pct,
            timestamp=datetime.now(timezone.utc),
            company_name=ticker,
        )
        self._prices[ticker] = sp
```

**Location:**
- Backend fixtures: `backend/tests/conftest.py` (shared across all tests) and inline in test files
  - Shared fixtures: database initialization, default price setup
  - Inline fixtures: test-specific app/client setup (`app_client` in `test_routes.py`, `test_llm.py`)
- Frontend: No fixture framework; test data embedded in test functions

**Factory Pattern:**
```python
# From test_routes.py: FakeProvider factory
provider = FakeProvider()
for ticker, price in [
    ("RELIANCE", 2500.0),
    ("TCS", 3500.0),
]:
    provider.add_price(ticker, price, prev=price * 0.99)
```

## Coverage

**Requirements:** Not explicitly enforced; no coverage target specified

**View Coverage:**
```bash
cd backend
uv run pytest --cov=. --cov-report=html
# Open htmlcov/index.html
```

**Coverage File Locations:**
- Backend: `.coverage` file in `backend/` directory
- Report: `backend/htmlcov/` (if generated)

## Test Types

**Unit Tests:**
- Scope: Single function or class in isolation
- Location: `test_simulator.py`, `test_queries.py`, `test_market_interface.py`
- Example: `test_gbm_step_always_positive()` tests GBM math independently
- Fixtures: Minimal; pure functions tested directly

**Integration Tests:**
- Scope: Multiple components working together (e.g., route + database + market provider)
- Location: `test_routes.py`, `test_llm.py`
- Example: `test_chat_executes_buy_trade()` tests route → portfolio → database flow
- Fixtures: Full app setup with `TestClient`, fresh database, stub provider

**E2E Tests:**
- Scope: Full application from browser perspective
- Framework: Playwright
- Location: `test/e2e/basic.spec.ts`
- Example: `test('has title and default watchlist', ...)` loads page, logs in, verifies UI state
- Setup: Docker container running full stack, environment variables injected

## Common Patterns

**Async Testing (Python):**
```python
async def test_something_async(db_conn):
    """Async test via pytest-asyncio."""
    result = await queries.record_trade(db_conn, "default", "RELIANCE", "buy", 10, 2450)
    assert result["ticker"] == "RELIANCE"
    assert result["id"]  # UUID generated
```

**Error Testing (Python):**
```python
async def test_insufficient_cash_reports_error(app_client, monkeypatch, mocker):
    client, _ = app_client
    monkeypatch.setenv("LLM_MOCK", "false")
    payload = ChatResponse(
        message="Trying to buy.",
        trades=[{"ticker": "RELIANCE", "side": "buy", "quantity": 100000}],
    )
    mocker.patch("app.llm.acompletion", return_value=_make_completion_response(payload))

    r = client.post("/api/chat", json={"message": "buy a ton"})
    assert r.status_code == 200  # Endpoint succeeds
    body = r.json()
    assert body["trades_executed"] == []  # But trade wasn't executed
    assert "Insufficient cash" in body["errors"][0]  # Reason provided
```

**Database Fixture Pattern:**
```python
@pytest.fixture
async def db_conn(tmp_path: Path):
    """Provide a fresh, initialized database connection for each test."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)  # Create schema, seed data
    async with get_db(db_path) as conn:
        yield conn
    # Cleanup: tmp_path automatically removed by pytest
```

**Frontend E2E Pattern (Playwright):**
```typescript
test('has title and default watchlist', async ({ page }) => {
  await page.goto('/');

  // Expect title
  await expect(page).toHaveTitle(/FinAlly/);

  // Log in as guest before asserting on app state
  await guestLogin(page);

  // Check for watchlist items (at least one of the defaults)
  await expect(page.getByText('RELIANCE')).toBeVisible();
  await expect(page.getByText('TCS')).toBeVisible();
});

async function guestLogin(page: import('@playwright/test').Page) {
  await expect(page.getByText('FinAlly')).toBeVisible();
  await page.getByRole('button', { name: /Try as Guest/i }).click();
  await expect(page.getByText('AI Trading Workstation')).toBeVisible({ timeout: 10000 });
}
```

## Test Coverage by Area

| Area | Test File | Test Count | Pattern |
|------|-----------|------------|---------|
| Market simulator GBM | `test_simulator.py` | 15+ | Unit: math correctness, randomness bounds |
| Market provider factory | `test_factory.py` | 5+ | Unit: env var selection logic |
| IndianAPI client | `test_indian_api.py` | 20+ | Integration: HTTP parsing, rate limiting (mocked) |
| Fallback provider | `test_fallback.py` | 10+ | Integration: provider switching |
| Yahoo Finance | `test_yahoo.py` | 10+ | Integration: ticker mapping, fallback on error |
| REST API routes | `test_routes.py` | 15+ | Integration: endpoint contracts, status codes |
| Database queries | `test_queries.py` | 20+ | Unit: CRUD logic with fresh DB per test |
| Database initialization | `test_db.py` | 5+ | Unit: schema creation, seed data |
| LLM chat integration | `test_llm.py` | 10+ | Integration: mock/real mode, trade execution, error handling |
| E2E (Playwright) | `test/e2e/basic.spec.ts` | 2+ | Full stack: login, watchlist, navigation |

## Continuous Integration

**CI Setup:** Not visible in codebase (likely GitHub Actions or similar external)
- Playwright config respects `process.env.CI` flag
- Retries enabled in CI (2 retries), disabled locally (0 retries)
- Workers reduced to 1 in CI for stability (parallel in local)

**Environment Variables for Testing:**
- `LLM_MOCK=true` — deterministic mock responses, skips OpenRouter calls
- `USE_YAHOO=true` — uses Yahoo Finance (slower, ~15min delay)
- `OPENROUTER_API_KEY` — optional, used in real LLM mode (mocked in tests)

---

*Testing analysis: 2026-05-02*
