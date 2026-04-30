"""Tests for LLM chat integration: schema parsing, mock mode, route auto-execution."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import llm
from app.dependencies import get_db_conn, get_market
from app.routes.chat import router as chat_router
from app.routes.portfolio import router as portfolio_router
from app.routes.watchlist import router as watchlist_router
from app.schemas import ChatResponse
from db import queries
from db.database import get_db, init_db
from market.types import StockPrice


class FakeProvider:
    def __init__(self) -> None:
        self.tickers: list[str] = []
        self._prices: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}

    def add_price(self, ticker: str, price: float, prev: float | None = None) -> None:
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


def _make_completion_response(payload: ChatResponse | str) -> SimpleNamespace:
    """Build a SimpleNamespace mimicking the litellm.completion return value."""
    raw = payload.model_dump_json() if isinstance(payload, ChatResponse) else payload
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw))]
    )


@pytest.fixture
async def app_client(tmp_path: Path) -> Iterator[tuple[TestClient, FakeProvider]]:
    db_path = str(tmp_path / "chat.db")
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
        provider.add_price(ticker, price, prev=price * 0.99)

    app = FastAPI()
    app.state.db_path = db_path
    app.state.market = provider
    app.include_router(portfolio_router)
    app.include_router(watchlist_router)
    app.include_router(chat_router)

    async def _override_db():
        async with get_db(db_path) as conn:
            yield conn

    app.dependency_overrides[get_db_conn] = _override_db
    app.dependency_overrides[get_market] = lambda: provider

    with TestClient(app) as client:
        yield client, provider


# ── mock mode ────────────────────────────────────────────────────────────────


async def test_mock_mode_returns_deterministic_response(monkeypatch, mocker):
    monkeypatch.setenv("LLM_MOCK", "true")
    spy = mocker.patch("app.llm.completion")

    result = await llm.call_llm([{"role": "user", "content": "hi"}], "ctx")

    assert isinstance(result, ChatResponse)
    assert result.message == "Mock response: portfolio looks good!"
    assert result.trades == []
    assert result.watchlist_changes == []
    spy.assert_not_called()


async def test_real_mode_invokes_completion(monkeypatch, mocker):
    monkeypatch.setenv("LLM_MOCK", "false")
    payload = ChatResponse(message="Hello!", trades=[], watchlist_changes=[])
    mock_completion = mocker.patch(
        "app.llm.completion", return_value=_make_completion_response(payload)
    )

    result = await llm.call_llm(
        [{"role": "user", "content": "hi"}], "Cash: INR 100000"
    )

    assert result.message == "Hello!"
    mock_completion.assert_called_once()
    kwargs = mock_completion.call_args.kwargs
    assert kwargs["model"] == llm.MODEL
    assert kwargs["response_format"] is ChatResponse
    assert kwargs["extra_body"] == llm.EXTRA_BODY
    # System prompt + user message
    assert kwargs["messages"][0]["role"] == "system"
    assert "Cash: INR 100000" in kwargs["messages"][0]["content"]
    assert kwargs["messages"][-1] == {"role": "user", "content": "hi"}


# ── portfolio context rendering ──────────────────────────────────────────────


async def test_portfolio_context_includes_cash_and_watchlist(app_client):
    client, provider = app_client
    # Create a position via the trade endpoint so DB state is realistic
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "RELIANCE", "quantity": 2, "side": "buy"},
    )
    assert r.status_code == 200

    from db.database import get_db as _get_db

    async with _get_db(client.app.state.db_path) as db:
        ctx = await llm.build_portfolio_context(db, provider)

    assert "Cash: INR" in ctx
    assert "RELIANCE: 2" in ctx
    assert "Watchlist:" in ctx
    assert "TCS" in ctx  # seeded watchlist


# ── chat endpoint: trade auto-execution ──────────────────────────────────────


async def test_chat_executes_buy_trade(app_client, monkeypatch, mocker):
    client, _ = app_client
    monkeypatch.setenv("LLM_MOCK", "false")
    payload = ChatResponse(
        message="Buying 5 RELIANCE for you.",
        trades=[{"ticker": "RELIANCE", "side": "buy", "quantity": 5}],
        watchlist_changes=[],
    )
    mocker.patch(
        "app.llm.completion", return_value=_make_completion_response(payload)
    )

    r = client.post("/api/chat", json={"message": "buy 5 reliance"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["message"] == "Buying 5 RELIANCE for you."
    assert len(body["trades_executed"]) == 1
    assert body["trades_executed"][0]["ticker"] == "RELIANCE"
    assert body["trades_executed"][0]["price"] == 2500.0
    assert body["errors"] == []

    # Cash should have decreased
    p = client.get("/api/portfolio").json()
    assert p["cash_balance"] == 100000.0 - 5 * 2500.0
    pos = next(x for x in p["positions"] if x["ticker"] == "RELIANCE")
    assert pos["quantity"] == 5


async def test_chat_insufficient_cash_reports_error(app_client, monkeypatch, mocker):
    client, _ = app_client
    monkeypatch.setenv("LLM_MOCK", "false")
    payload = ChatResponse(
        message="Trying to buy.",
        trades=[{"ticker": "RELIANCE", "side": "buy", "quantity": 100000}],
        watchlist_changes=[],
    )
    mocker.patch(
        "app.llm.completion", return_value=_make_completion_response(payload)
    )

    r = client.post("/api/chat", json={"message": "buy a ton"})
    assert r.status_code == 200
    body = r.json()
    assert body["trades_executed"] == []
    assert len(body["errors"]) == 1
    assert "Insufficient cash" in body["errors"][0]

    # Portfolio untouched
    p = client.get("/api/portfolio").json()
    assert p["cash_balance"] == 100000.0
    assert p["positions"] == []


async def test_chat_applies_watchlist_changes(app_client, monkeypatch, mocker):
    client, provider = app_client
    monkeypatch.setenv("LLM_MOCK", "false")
    provider.add_price("BAJFINANCE", 7200.0, prev=7100.0)
    payload = ChatResponse(
        message="Added BAJFINANCE, removed ITC.",
        trades=[],
        watchlist_changes=[
            {"ticker": "BAJFINANCE", "action": "add"},
            {"ticker": "ITC", "action": "remove"},
        ],
    )
    mocker.patch(
        "app.llm.completion", return_value=_make_completion_response(payload)
    )

    r = client.post("/api/chat", json={"message": "swap watchlist"})
    assert r.status_code == 200
    body = r.json()
    assert {c["ticker"] for c in body["watchlist_changes_applied"]} == {
        "BAJFINANCE",
        "ITC",
    }
    assert "BAJFINANCE" in provider.tickers
    assert "ITC" not in provider.tickers


async def test_chat_persists_history(app_client, monkeypatch, mocker):
    client, _ = app_client
    monkeypatch.setenv("LLM_MOCK", "false")
    payload = ChatResponse(message="Noted.", trades=[], watchlist_changes=[])
    mocker.patch(
        "app.llm.completion", return_value=_make_completion_response(payload)
    )

    client.post("/api/chat", json={"message": "hello there"})

    from db.database import get_db as _get_db

    async with _get_db(client.app.state.db_path) as db:
        rows = await queries.get_chat_history(db)
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "hello there"
    assert rows[1]["role"] == "assistant"
    assert rows[1]["content"] == "Noted."


async def test_chat_llm_failure_returns_fallback(app_client, monkeypatch, mocker):
    client, _ = app_client
    monkeypatch.setenv("LLM_MOCK", "false")
    mocker.patch("app.llm.completion", side_effect=RuntimeError("boom"))

    r = client.post("/api/chat", json={"message": "anything"})
    assert r.status_code == 200
    body = r.json()
    assert "couldn't process" in body["message"]
    assert body["errors"] == ["llm_call_failed"]


async def test_chat_mock_mode_via_endpoint(app_client, monkeypatch, mocker):
    client, _ = app_client
    monkeypatch.setenv("LLM_MOCK", "true")
    spy = mocker.patch("app.llm.completion")

    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert r.json()["message"] == "Mock response: portfolio looks good!"
    spy.assert_not_called()
