# Coding Conventions

**Analysis Date:** 2026-05-02

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `test_simulator.py`, `market/indian_api.py`, `app/portfolio.py`)
- React/TypeScript components: `PascalCase.tsx` for components, `camelCase.ts` for utilities (e.g., `WatchlistPanel.tsx`, `useMarketData.ts`, `api.ts`)
- Test files: `test_<module>.py` for Python, `<name>.spec.ts` for frontend (e.g., `test_routes.py`, `basic.spec.ts`)

**Functions:**
- Python: `snake_case` for all functions and methods
- TypeScript/React: `camelCase` for functions, `PascalCase` for components and React hooks
- Async functions prefixed with `async` keyword (Python) or function body returns `Promise` (TypeScript)
- Private/internal functions prefixed with `_` (Python convention), e.g., `_enrich_position`, `_make_completion_response`

**Variables:**
- Python: `snake_case` (e.g., `user_id`, `cash_balance`, `market_provider`)
- TypeScript: `camelCase` (e.g., `selectedTicker`, `priceCache`, `eventSource`)
- Constants: `SCREAMING_SNAKE_CASE` in Python, all caps optional in TypeScript
  - Example: `DEFAULT_VOL = 0.25`, `SNAPSHOT_INTERVAL = 30`, `SPARK_LIMIT = 60`

**Types:**
- TypeScript interfaces: `PascalCase`, exported from `@/lib/types.ts`
  - Example: `interface PriceTick { ... }`, `interface Portfolio { ... }`
- Python dataclasses: `PascalCase` (e.g., `StockPrice`, `TradeRequest`, `ChatResponse`)
- Pydantic models: `PascalCase` ending in `Request` or `Response` for API contracts
  - Example: `class TradeRequest(BaseModel)`, `class ChatResponse(BaseModel)`

## Code Style

**Formatting:**
- TypeScript: Tailwind CSS for styling (no separate CSS files)
- Python: Follows PEP 8 conventions (4-space indentation)
- JavaScript/TypeScript: 2-space indentation via implicit formatting
- Line length: No strict enforced maximum, but aim for readability

**Linting:**
- TypeScript: Uses Next.js built-in strict mode (`tsconfig.json` has `"strict": true`)
- Python: No explicit linting config detected; code follows PEP 8 style
- Frontend: Uses Tailwind CSS utility classes (`@tailwindcss/postcss`)

**Type Safety:**
- TypeScript: `tsconfig.json` has `"strict": true`, enabling strict null checks, no implicit any
- Python: Uses type hints throughout (`from __future__ import annotations` for forward compatibility)
  - Optional types use `X | None` syntax (Python 3.10+ union syntax)
- Pydantic models use `Field()` for validation (e.g., `Field(..., min_length=1, max_length=20)`)

## Import Organization

**Order:**
1. Standard library imports (`import asyncio`, `from pathlib import Path`)
2. Third-party imports (`import pytest`, `from fastapi import FastAPI`)
3. Local/relative imports (`from db import queries`, `from market.base import MarketDataProvider`)
4. Type imports (`from typing import Literal, Iterator`, `type { Component }`)

**Python Pattern:**
```python
from __future__ import annotations  # Always first in modules

import asyncio
import logging
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter

from db import queries
from market.base import MarketDataProvider
```

**TypeScript Pattern:**
```typescript
"use client";  // React Server Component directive if needed

import React, { useCallback, useEffect } from "react";  // React imports
import { api } from "@/lib/api";  // App imports with @ alias
import type { Portfolio } from "@/lib/types";  // Type-only imports
```

**Path Aliases:**
- Frontend: `@/*` → `./` in `frontend/` root (configured in `frontend/tsconfig.json`)
  - Usage: `import { api } from "@/lib/api"`, `import { useMarketData } from "@/hooks/useMarketData"`

## Error Handling

**Patterns:**
- Python: Custom exception classes for domain errors (e.g., `TradeError` in `app/portfolio.py`)
  - Includes both HTTP status code and user-facing detail message
  - Caught in route handlers and converted to `HTTPException`
- TypeScript: Try-catch for async operations, error state in hooks
  - Fallback display patterns (e.g., "—" for null values, error messages in state)
- Database: Async context managers (`async with get_db(db_path) as conn`) ensure cleanup
- Network: Fetch errors caught with generic `Error` message extraction
  - SSE stream errors marked as "disconnected" or "connecting" state

**Trade Execution Validation:**
- Explicit checks before state mutation (sufficient cash for buys, shares for sells)
- Validation happens in `execute_trade()` in `app/portfolio.py` before any database writes
- Errors raised as `TradeError(status_code, detail)` with specific messages

## Logging

**Framework:** Python uses `logging` module, TypeScript/React uses `console` (no logging framework)

**Patterns:**
- Python: Module-level logger created as `logger = logging.getLogger("finally.<module>")`
  - Log level set to INFO by default in `app/main.py`
  - Exceptions logged with `logger.exception()` in catch-all blocks
- TypeScript: Minimal logging; errors logged via `console.error()` if needed
- Sensitive data: Never logged (API keys, passwords, tokens)

## Comments

**When to Comment:**
- Brief docstrings for functions explaining purpose, parameters, and return value (not inline comments)
- Complex algorithms documented inline (e.g., GBM math in `market/simulator.py`)
- Section headers as comment blocks (e.g., `# ── users / portfolio ────`)

**JSDoc/TSDoc:**
- Python: Module docstrings at top of files (triple quotes)
  - Function docstrings included for public APIs
  - Example: `"""Execute a market order at the current price.\n\nRaises ``TradeError`` on..."""`
- TypeScript: No JSDoc comments observed; types are self-documenting via interface definitions

**Pattern Example (Python):**
```python
def execute_trade(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER,
) -> dict[str, Any]:
    """Execute a market order at the current price.

    Raises ``TradeError`` on validation failure (unknown ticker, insufficient
    cash/shares). On success, records the trade plus a fresh snapshot and
    returns the post-trade portfolio snapshot.
    """
```

## Function Design

**Size:** Prefer short functions with single responsibility
- Example: `_enrich_position()` takes raw position, returns enriched with current prices
- Example: `gbm_step()` pure function with 3 lines of logic
- Complex workflows broken into smaller steps (e.g., `build_portfolio_snapshot()` orchestrates `_enrich_position()`)

**Parameters:**
- Explicit over implicit; prefer named parameters for clarity
- Use type hints everywhere (no untyped parameters)
- Default values used sparingly (e.g., `user_id: str = DEFAULT_USER`)
- Dataclass/Pydantic models preferred over many scalar parameters

**Return Values:**
- Single return type (no overloaded returns based on flags)
- `dict[str, Any]` for flexible API responses, typed dataclasses/Pydantic for contracts
- `None` for void operations; nullable types marked with `| None`
- Async functions in Python return coroutines; handled with `await` syntax

## Module Design

**Exports:**
- Python: `__init__.py` files export public API from submodules
  - Example: `backend/market/__init__.py` exports `create_market_provider`, `StockPrice`
- TypeScript: Explicit named exports, no default exports except for pages
  - Example: `export function useMarketData(): MarketDataState { ... }`

**Barrel Files:**
- Python: `from db import queries` loads all query functions
- TypeScript: `@/lib/types.ts` centralizes all type definitions; imported as `import type { ... }`

**Monolithic vs. Split:**
- Market data providers: Each implementation in separate file (`simulator.py`, `indian_api.py`, `yahoo.py`), unified by `MarketDataProvider` abstract base class
- Routes: Each domain in separate file (`auth.py`, `portfolio.py`, `watchlist.py`, `prices.py`) included in main app
- Hooks: Each hook in separate file (`useMarketData.ts`, `usePortfolio.ts`, `useWatchlist.ts`)

## Async Patterns

**Python:**
- `async def` for all database operations and I/O
- `async with` for resource management (database connections, contexts)
- `asyncio.create_task()` for background work (e.g., market data simulation loop)
- `await` for dependencies (never fire-and-forget except for tasks)

**TypeScript/React:**
- `Promise<T>` return type for async operations
- `useEffect` hook with `void refresh()` pattern for async state updates
- Try-finally blocks for cleanup (e.g., `es.close()` in `useMarketData`)
- No top-level await in components; always wrapped in useEffect

## Testing Patterns Reflected in Code

- `@pytest.fixture` decorators for test setup (database, fake providers)
- Mock/stub providers implement the same interface as real implementations
- Structured mocking via `monkeypatch.setenv()` for environment toggles
- Tests are discoverable by file naming convention (`test_*.py`, `*.spec.ts`)

---

*Convention analysis: 2026-05-02*
