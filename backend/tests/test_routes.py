"""Integration tests for the FastAPI routes (health, prices, watchlist, portfolio)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_db_conn, get_market
from app.routes.health import router as health_router
from app.routes.portfolio import router as portfolio_router
from app.routes.prices import router as prices_router
from app.routes.watchlist import router as watchlist_router
from db.database import get_db, init_db
from market.types import StockPrice


class FakeProvider:
    """In-memory MarketDataProvider stub."""

    def __init__(self) -> None:
        self.tickers: list[str] = []
        self._prices: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}

    def add_price(
        self,
        ticker: str,
        price: float,
        prev: float | None = None,
        company: str = "",
    ) -> None:
        prev_price = prev if prev is not None else price
        change_pct = ((price - prev_price) / prev_price * 100.0) if prev_price else 0.0
        sp = StockPrice(
            ticker=ticker,
            price=price,
            prev_price=prev_price,
            change_pct=change_pct,
            timestamp=datetime.now(timezone.utc),
            company_name=company,
        )
        self._prices[ticker] = sp
        self._history.setdefault(ticker, []).append(sp)

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._prices.get(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return dict(self._prices)

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return list(self._history.get(ticker, []))[-limit:]

    def set_tickers(self, tickers: list[str]) -> None:
        self.tickers = list(tickers)


@pytest.fixture
async def app_client(tmp_path: Path) -> Iterator[tuple[TestClient, FakeProvider]]:
    db_path = str(tmp_path / "routes.db")
    await init_db(db_path)

    provider = FakeProvider()
    for ticker, price in [
        ("RELIANCE", 2500.0),
        ("TCS", 3500.0),
        ("HDFCBANK", 1600.0),
        ("INFY", 1550.0),
        ("ICICIBANK", 1100.0),
        ("BHARTIARTL", 1700.0),
        ("SBIN", 800.0),
        ("ITC", 460.0),
        ("LT", 3600.0),
        ("HINDUNILVR", 2400.0),
    ]:
        provider.add_price(ticker, price, prev=price * 0.99, company=ticker)

    app = FastAPI()
    app.state.db_path = db_path
    app.state.market = provider
    app.include_router(health_router)
    app.include_router(prices_router)
    app.include_router(portfolio_router)
    app.include_router(watchlist_router)

    async def _override_db():
        async with get_db(db_path) as conn:
            yield conn

    app.dependency_overrides[get_db_conn] = _override_db
    app.dependency_overrides[get_market] = lambda: provider

    with TestClient(app) as client:
        yield client, provider


# ── health ───────────────────────────────────────────────────────────────────


async def test_health(app_client):
    client, _ = app_client
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── watchlist ────────────────────────────────────────────────────────────────


async def test_watchlist_seeded(app_client):
    client, _ = app_client
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 10
    tickers = {entry["ticker"] for entry in body}
    assert "RELIANCE" in tickers
    reliance = next(e for e in body if e["ticker"] == "RELIANCE")
    assert reliance["price"] == 2500.0
    assert reliance["company_name"] == "RELIANCE"


async def test_watchlist_add_and_remove(app_client):
    client, provider = app_client
    provider.add_price("BAJFINANCE", 7200.0, prev=7100.0, company="Bajaj Finance")

    r = client.post("/api/watchlist", json={"ticker": "BAJFINANCE"})
    assert r.status_code == 201
    entries = r.json()
    assert any(e["ticker"] == "BAJFINANCE" for e in entries)
    assert "BAJFINANCE" in provider.tickers

    r2 = client.post("/api/watchlist", json={"ticker": "BAJFINANCE"})
    assert r2.status_code == 409

    r3 = client.delete("/api/watchlist/BAJFINANCE")
    assert r3.status_code == 200
    assert "BAJFINANCE" not in provider.tickers

    r4 = client.delete("/api/watchlist/BAJFINANCE")
    assert r4.status_code == 404


async def test_watchlist_uppercase_normalization(app_client):
    client, provider = app_client
    provider.add_price("WIPRO", 500.0, prev=495.0)
    r = client.post("/api/watchlist", json={"ticker": "wipro"})
    assert r.status_code == 201
    assert "WIPRO" in provider.tickers


# ── prices ───────────────────────────────────────────────────────────────────


async def test_price_history_empty_for_unknown(app_client):
    client, _ = app_client
    r = client.get("/api/prices/UNKNOWN/history")
    assert r.status_code == 200
    assert r.json() == []


async def test_price_history_returns_data(app_client):
    client, provider = app_client
    provider.add_price("RELIANCE", 2510.0, prev=2500.0)
    r = client.get("/api/prices/RELIANCE/history")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    assert body[-1]["ticker"] == "RELIANCE"
    assert "timestamp" in body[-1]


# ── portfolio ────────────────────────────────────────────────────────────────


async def test_portfolio_initial_state(app_client):
    client, _ = app_client
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["cash_balance"] == 100000.0
    assert body["total_value"] == 100000.0
    assert body["positions"] == []


async def test_buy_then_sell_cycle(app_client):
    client, _ = app_client

    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 10, "side": "buy"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cash_balance"] == 100000.0 - 10 * 2500.0
    pos = next(p for p in body["positions"] if p["ticker"] == "RELIANCE")
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 2500.0

    r2 = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 4, "side": "sell"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["cash_balance"] == 100000.0 - 10 * 2500.0 + 4 * 2500.0
    pos2 = next(p for p in body2["positions"] if p["ticker"] == "RELIANCE")
    assert pos2["quantity"] == 6

    r3 = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 6, "side": "sell"},
    )
    assert r3.status_code == 200
    body3 = r3.json()
    assert body3["positions"] == []
    assert body3["cash_balance"] == 100000.0


async def test_buy_insufficient_cash(app_client):
    client, _ = app_client
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 1000, "side": "buy"},
    )
    assert r.status_code == 422


async def test_sell_insufficient_shares(app_client):
    client, _ = app_client
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 1, "side": "sell"},
    )
    assert r.status_code == 422


async def test_trade_unknown_ticker(app_client):
    client, _ = app_client
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "NOSUCH", "quantity": 1, "side": "buy"},
    )
    assert r.status_code == 404


async def test_trade_validation(app_client):
    client, _ = app_client
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": -5, "side": "buy"},
    )
    assert r.status_code == 422
    r2 = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 1, "side": "hodl"},
    )
    assert r2.status_code == 422


async def test_portfolio_history_records_after_trade(app_client):
    client, _ = app_client
    client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 2, "side": "buy"},
    )
    r = client.get("/api/portfolio/history")
    assert r.status_code == 200
    history = r.json()
    assert len(history) >= 1
    assert "total_value" in history[0]
    assert "recorded_at" in history[0]
