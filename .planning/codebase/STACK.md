# Technology Stack

**Analysis Date:** 2026-05-02

## Languages

**Primary:**
- TypeScript 5.x - Frontend React components and configuration (`frontend/`)
- Python 3.12+ - Backend FastAPI server, market data, database, and LLM integration (`backend/`)

**Secondary:**
- SQL - SQLite schema definitions (`backend/db/schema.sql`)
- YAML/Docker - Container configuration

## Runtime

**Environment:**
- Node.js 20 (slim) - Frontend build phase only
- Python 3.12 (slim) - Backend runtime in production container

**Package Managers:**
- npm - Node.js dependencies for frontend
- uv (Astral) - Python package management with lockfile (`backend/uv.lock`)

**Lockfiles:**
- `frontend/package-lock.json` - Node.js dependency lock
- `backend/uv.lock` - Python dependency lock (frozen during Docker build)

## Frameworks

**Frontend:**
- Next.js 16.2.4 - React SSR framework with static export (`output: "export"` in `frontend/next.config.ts`)
- React 19.2.4 - UI component library
- React DOM 19.2.4 - React DOM rendering

**Backend:**
- FastAPI 0.115.0+ - ASGI web framework (`backend/app/main.py`)
- Uvicorn 0.30.0+ - ASGI server (runs with `uv run uvicorn app.main:app`)

**Testing:**
- pytest 8.0.0+ - Python test runner
- pytest-asyncio 0.23.0+ - Async test support
- pytest-mock 3.14.0+ - Mocking utilities
- respx 0.21.0+ - HTTP mock library for API tests
- Playwright 1.49.0+ - E2E browser testing (`test/package.json`)

**Build & Development:**
- Tailwind CSS 4.x - Utility-first CSS framework with PostCSS (`frontend/`)
- @tailwindcss/postcss 4.x - PostCSS plugin
- TypeScript ESC targets ES2017

## Key Dependencies

**Critical:**
- httpx 0.27.0+ - Async HTTP client for API polling (`backend/market/indian_api.py`, `backend/market/yahoo.py`)
- litellm 1.40.0+ - LLM abstraction layer routing to OpenRouter (`backend/app/llm.py`)
- yfinance 0.2.50+ - Yahoo Finance data fetching (`backend/market/yahoo.py`)

**Infrastructure:**
- aiosqlite 0.22.1+ - Async SQLite client (`backend/db/database.py`)
- sse-starlette 3.4.1+ - Server-Sent Events support (`backend/app/routes/prices.py`)
- python-dotenv 1.0.0+ - Environment variable loading from `.env`
- python-jose 3.5.0+ with cryptography - JWT token creation/verification (`backend/app/auth.py`)
- bcrypt 4.0.0+ - Password hashing (`backend/app/auth.py`)

**Frontend Charting:**
- lightweight-charts 5.2.0+ - Lightweight financial charting library
- recharts 3.8.1+ - React chart library for portfolio visualizations

## Configuration

**Environment:**
- `.env` file in project root (gitignored) - Contains API keys and feature flags
- Environment variables are loaded at application startup via `python-dotenv`
- Docker container passes env file via `--env-file .env`

**Key Configuration Files:**
- `frontend/next.config.ts` - Next.js configuration with `output: 'export'` for static build, `trailingSlash: true`, unoptimized images
- `frontend/tsconfig.json` - TypeScript compiler options with path aliases (`@/*` → root)
- `frontend/postcss.config.mjs` - PostCSS configuration for Tailwind
- `backend/pyproject.toml` - Python project manifest with all dependencies and dev tools
- `.env.example` - Template for environment variables (committed to git)

**Docker:**
- `Dockerfile` - Multi-stage build: Node 20 → Python 3.12
- Frontend built to `out/` directory, copied into backend's `static/` directory
- Backend serves static frontend files alongside API routes

## Platform Requirements

**Development:**
- Node.js 20.x (for frontend build)
- Python 3.12+ (for backend)
- uv package manager
- Docker (optional, for container deployment)

**Production:**
- Docker container with Python 3.12 slim base image
- Port 8000 exposed (FastAPI)
- Volume mount at `/app/data` for SQLite database persistence
- Environment variables: `OPENROUTER_API_KEY` (required for LLM), `INDIAN_STOCK_API_KEY` (optional), `USE_YAHOO` (optional)

## Build Pipeline

**Frontend:**
1. `npm install` - Install dependencies
2. `npm run build` - Next.js static export to `out/` directory
3. Output copied to backend's `static/` directory

**Backend:**
1. `uv sync --frozen --no-dev` - Install production dependencies from lockfile
2. Application runs via `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`

**Docker Multi-Stage:**
- Stage 1: Node 20-slim - builds frontend static export
- Stage 2: Python 3.12-slim - installs backend dependencies, copies frontend output to `/app/static`, exposes port 8000

---

*Stack analysis: 2026-05-02*
