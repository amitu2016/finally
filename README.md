# FinAlly — AI Trading Workstation

An AI-powered trading workstation for Indian stock markets (NSE/BSE). Streams live prices, simulates a ₹1,00,000 portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades.

## Quick Start

```bash
cp .env.example .env
# Edit .env — add your OPENROUTER_API_KEY
bash scripts/start_mac.sh
```

Open [http://localhost:8000](http://localhost:8000).

## Features

- Live NSE/BSE price streaming via SSE with flash animations
- Simulated ₹1,00,000 portfolio — buy/sell at market price instantly
- Portfolio heatmap (treemap), P&L chart, positions table
- AI chat assistant (FinAlly) — analyzes your portfolio and executes trades on request
- Watchlist management — manual or via AI

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for LLM chat |
| `USE_REAL_MARKET_DATA` | No | `true` to use live NSE/BSE data (default: simulator) |
| `INDIAN_STOCK_API_KEY` | If above is true | IndianAPI key for real market data |
| `LLM_MOCK` | No | `true` for deterministic mock responses (testing) |

## Stack

- **Frontend**: Next.js (TypeScript), static export, served by FastAPI
- **Backend**: FastAPI (Python/uv), SQLite, SSE streaming
- **AI**: LiteLLM → OpenRouter (Cerebras inference)
- **Market data**: GBM simulator (default) or live IndianAPI

## Development

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Testing

```bash
# Backend unit tests
cd backend && uv run pytest

# E2E (requires Docker)
cd test && docker compose -f docker-compose.test.yml up
```
