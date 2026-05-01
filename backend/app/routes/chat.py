"""Chat endpoint — LLM-driven assistant with auto trade/watchlist execution."""

from __future__ import annotations

import logging
import os
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import queries
from market.base import MarketDataProvider

from ..dependencies import get_current_user, get_db_conn, get_market
from ..llm import build_portfolio_context, call_llm
from ..portfolio import TradeError, execute_trade
from ..schemas import ChatResponse, TradeAction, WatchlistChange

router = APIRouter()
logger = logging.getLogger("finally.chat")

HISTORY_LIMIT = 20
GUEST_USERNAME = "demo"
GUEST_DAILY_LIMIT = int(os.getenv("GUEST_DAILY_CHAT_LIMIT", "10"))


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


def _format_history(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def _apply_trades(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    trades: list[TradeAction],
    user_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    executed: list[dict[str, Any]] = []
    errors: list[str] = []
    for t in trades:
        try:
            result = await execute_trade(db, provider, t.ticker, t.side, t.quantity, user_id)
        except TradeError as exc:
            errors.append(f"{t.side} {t.quantity} {t.ticker}: {exc.detail}")
            continue
        executed.append({"ticker": t.ticker.upper(), "side": t.side, "quantity": t.quantity, "price": result["price"]})
    return executed, errors


async def _apply_watchlist_changes(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    changes: list[WatchlistChange],
    user_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    applied: list[dict[str, Any]] = []
    errors: list[str] = []
    if not changes:
        return applied, errors

    current = set(await queries.get_watchlist(db, user_id))
    for c in changes:
        ticker = c.ticker.upper()
        if c.action == "add":
            if ticker in current:
                errors.append(f"add {ticker}: already in watchlist")
                continue
            await queries.add_to_watchlist(db, user_id, ticker)
            current.add(ticker)
            applied.append({"ticker": ticker, "action": "add"})
        elif c.action == "remove":
            if ticker not in current:
                errors.append(f"remove {ticker}: not in watchlist")
                continue
            await queries.remove_from_watchlist(db, user_id, ticker)
            current.discard(ticker)
            applied.append({"ticker": ticker, "action": "remove"})
        else:
            errors.append(f"{ticker}: unknown action {c.action}")

    if applied:
        all_tickers = await queries.get_all_watchlist_tickers(db)
        provider.set_tickers(all_tickers)
    return applied, errors


@router.post("/api/chat")
async def chat(
    body: ChatRequest,
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    user = await queries.get_user_by_id(db, user_id)
    if user and user["username"] == GUEST_USERNAME:
        count = await queries.count_recent_messages(db, user_id, hours=24)
        if count >= GUEST_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Guest accounts are limited to {GUEST_DAILY_LIMIT} AI messages per day. Create a free account to continue.",
            )

    portfolio_context = await build_portfolio_context(db, provider, user_id)

    history_rows = await queries.get_chat_history(db, user_id, limit=HISTORY_LIMIT)
    messages = _format_history(history_rows)
    messages.append({"role": "user", "content": body.message})

    try:
        response: ChatResponse = await call_llm(messages, portfolio_context)
    except Exception:
        logger.exception("LLM call failed")
        await queries.save_message(db, user_id, "user", body.message)
        fallback = "Sorry, I couldn't process that request right now."
        await queries.save_message(db, user_id, "assistant", fallback)
        return {"message": fallback, "trades_executed": [], "watchlist_changes_applied": [], "errors": ["llm_call_failed"]}

    trades_executed, trade_errors = await _apply_trades(db, provider, response.trades, user_id)
    watchlist_applied, watchlist_errors = await _apply_watchlist_changes(db, provider, response.watchlist_changes, user_id)
    errors = trade_errors + watchlist_errors

    await queries.save_message(db, user_id, "user", body.message)
    actions_payload: dict[str, Any] | None = None
    if trades_executed or watchlist_applied or errors:
        actions_payload = {"trades_executed": trades_executed, "watchlist_changes_applied": watchlist_applied, "errors": errors}
    await queries.save_message(db, user_id, "assistant", response.message, actions=actions_payload)

    return {"message": response.message, "trades_executed": trades_executed, "watchlist_changes_applied": watchlist_applied, "errors": errors}
