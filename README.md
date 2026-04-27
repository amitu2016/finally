# FinAlly — AI Trading Workstation

A Bloomberg-style trading terminal for Indian stocks (NSE/BSE) with an AI assistant that can analyze your portfolio and execute trades via natural language.

## Features

- Live price streaming via SSE (real NSE/BSE data or built-in simulator)
- ₹1,00,000 virtual cash, market orders, instant fills
- Watchlist with sparklines, price flash animations
- Portfolio heatmap (treemap), P&L chart, positions table
- AI chat (Cerebras via OpenRouter) — asks questions, executes trades, manages watchlist

## Quick Start

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
./scripts/start_mac.sh
```

Open http://localhost:8000.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `USE_REAL_MARKET_DATA` | No | Set `true` to use live NSE/BSE prices |
| `INDIAN_STOCK_API_KEY` | If above is true | API key from stock.indianapi.in |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM (testing) |

## Stack

- **Frontend**: Next.js (TypeScript, static export)
- **Backend**: FastAPI + Python (uv)
- **Database**: SQLite
- **AI**: LiteLLM → OpenRouter → Cerebras (`openrouter/openai/gpt-oss-120b`)
- **Deployment**: Single Docker container on port 8000

## Scripts

```bash
./scripts/start_mac.sh        # Build and run
./scripts/start_mac.sh --build # Force rebuild
./scripts/stop_mac.sh         # Stop container (data persists)
```
