# Code Review — FinAlly Trading Workstation

This document provides a comprehensive code review of the FinAlly project, conducted by Gemini CLI. The review covers architecture, implementation details, security, performance, and adherence to the project specifications.

---

## Executive Summary

FinAlly is a well-structured, modern full-stack application. It successfully integrates a FastAPI backend with a Next.js frontend, utilizing SSE for real-time updates and LLM-driven agentic features. The codebase is clean, modular, and demonstrates sophisticated patterns (e.g., abstract market providers, structured LLM outputs, automated portfolio snapshots).

However, several critical issues were identified:
1.  **Market Data Quota Exhaustion**: The `IndianAPIProvider` polling strategy will exhaust the monthly quota in minutes rather than lasting a full month.
2.  **Blocking Event Loop**: A synchronous network call in the LLM integration blocks the FastAPI event loop, potentially causing hangs.
3.  **Efficiency Concerns**: The SSE stream implementation performs redundant database lookups on every tick.
4.  **Architectural Mismatches**: There are slight deviations between the `PLAN.md` and the actual implementation (e.g., Auth system).

---

## 1. Backend Architecture & Implementation

### 1.1 Market Data Providers (`backend/market/`)
-   **Strong Pattern**: The use of an abstract `MarketDataProvider` and a factory pattern for switching between Simulator, Yahoo, and IndianAPI is excellent.
-   **Critical Bug (`IndianAPIProvider`)**: 
    -   **Polling Rate**: The provider polls all tickers every 1.0s (`FAST_POLL_INTERVAL`).
    -   **Quota Math**: With 10 tickers, this uses 10 calls/sec = 36,000 calls/hour. The monthly quota is only 5,000 calls. The provider will exhaust its monthly budget in **~8 minutes**.
    -   **Recommendation**: Implement the round-robin single-ticker polling strategy mentioned in `PLAN.md` with a calculated interval based on the remaining monthly quota.
-   **Concurrency**: `YahooFinanceProvider` correctly uses `run_in_executor` for its blocking `yfinance` calls.

### 1.2 LLM Integration (`backend/app/llm.py`)
-   **Critical Bug (Blocking Call)**: 
    -   The `call_llm` function is `async def`, but it calls `litellm.completion(...)`, which is a **synchronous/blocking** function. 
    -   **Impact**: During the network request to OpenRouter (which can take several seconds), the entire FastAPI process is blocked. No other requests (including SSE heartbeats or price updates) will be processed.
    -   **Recommendation**: Use `litellm.acompletion(...)` and await it.
-   **System Prompt**: The system prompt is well-defined and ensures structured output via Pydantic models.

### 1.3 Portfolio & Trades (`backend/app/portfolio.py`)
-   **Validation**: Trade validation (sufficient cash/shares) is robust and uses a custom `TradeError`.
-   **Avg Cost Calculation**: The weighted average cost calculation for buys is correct.
-   **Snapshot Logic**: Portfolio snapshots are recorded after every trade and by a background task, ensuring a rich P&L chart history.

### 1.4 API Routes & SSE
-   **Inefficiency (`stream_prices`)**:
    -   The SSE `event_generator` opens a new SQLite connection and queries the `watchlist` table **every 0.5 seconds per connected client**.
    -   **Impact**: Redundant DB I/O.
    -   **Recommendation**: Cache the user's watchlist and only refresh it when a change is detected (e.g., via a simple cache invalidation or by checking a 'last updated' timestamp).
-   **SPA Support**: `main.py` correctly handles SPA routing with a catch-all route serving `index.html`.

---

## 2. Frontend Architecture & UX

### 2.1 State Management & Hooks
-   **`useMarketData`**: Efficiently manages real-time prices and sparkline accumulation. The use of `EventSource` is appropriate for one-way streaming.
-   **`AuthGate`**: Successfully implements a clean login/registration flow.

### 2.2 UI/UX
-   **Aesthetics**: The dark-themed, terminal-like design matches the "Bloomberg-style" vision.
-   **Real-time Feedback**: Price flashing and live sparklines provide high-frequency visual feedback.
-   **AI Integration**: The `ChatPanel` provides immediate feedback on executed actions (trades/watchlist), making the "agentic" nature of the app clear.

---

## 3. Database & Auth

### 3.1 Schema (`backend/db/schema.sql`)
-   **Future-Proofing**: Inclusion of `user_id` across all tables is a proactive design choice.
-   **Initialization**: `init_db` handles lazy initialization and seeding perfectly for a zero-config setup.

### 3.2 Authentication
-   **Implementation**: Contrary to the initial "No login" plan, a full JWT-based auth system is implemented. This is a positive evolution, though it requires users to sign up even for local demos.

---

## 4. Infrastructure & Security

### 4.1 Docker & Packaging
-   **Multi-stage Build**: The Dockerfile is well-optimized, separating the Node.js build and Python runtime.
-   **Project Management**: Usage of `uv` for Python and `npm` for frontend is modern and follows best practices.

### 4.2 Security
-   **Passwords**: Correctly uses `bcrypt` for hashing.
-   **Secrets**: Env var management for API keys is standard.
-   **SSE Security**: The implementation correctly passes the token via query params for `EventSource`, enabling authenticated streams.

---

## 5. Summary of Recommendations

| Category | Priority | Action |
| :--- | :--- | :--- |
| **Market Data** | 🔴 High | Refactor `IndianAPIProvider` to poll at a rate compatible with the 5,000 call/month quota. |
| **Performance** | 🔴 High | Switch `litellm.completion` to `litellm.acompletion` in `llm.py`. |
| **Efficiency** | 🟡 Med | Cache watchlist in the SSE `event_generator` to avoid excessive DB lookups. |
| **Cleanliness** | 🟢 Low | Consolidate `DEFAULT_WATCHLIST` constants across `database.py` and `queries.py`. |
| **UX** | 🟢 Low | Add a "Demo Mode" or "Guest Access" button to `AuthScreen` to satisfy the "No login" requirement while keeping the Auth system. |

---
**Reviewer:** Gemini CLI  
**Date:** May 1, 2026
