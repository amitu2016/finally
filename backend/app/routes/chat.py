"""Chat endpoint — LLM-driven assistant with auto trade/watchlist execution."""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from db import queries
from market.base import MarketDataProvider

from ..dependencies import get_db_conn, get_market
from ..llm import build_portfolio_context, call_llm
from ..portfolio import DEFAULT_USER, TradeError, execute_trade
from ..schemas import ChatResponse, TradeAction, WatchlistChange

router = APIRouter()
logger = logging.getLogger("finally.chat")

HISTORY_LIMIT = 20


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


def _format_history(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert DB chat rows to the {role, content} list LiteLLM expects."""
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def _apply_trades(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    trades: list[TradeAction],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Auto-execute LLM-requested trades. Returns (executed, errors)."""
    executed: list[dict[str, Any]] = []
    errors: list[str] = []
    for t in trades:
        try:
            result = await execute_trade(
                db, provider, t.ticker, t.side, t.quantity
            )
        except TradeError as exc:
            errors.append(f"{t.side} {t.quantity} {t.ticker}: {exc.detail}")
            continue
        executed.append(
            {
                "ticker": t.ticker.upper(),
                "side": t.side,
                "quantity": t.quantity,
                "price": result["price"],
            }
        )
    return executed, errors


async def _apply_watchlist_changes(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    changes: list[WatchlistChange],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply LLM-requested watchlist additions/removals. Returns (applied, errors)."""
    applied: list[dict[str, Any]] = []
    errors: list[str] = []
    if not changes:
        return applied, errors

    current = set(await queries.get_watchlist(db, DEFAULT_USER))
    for c in changes:
        ticker = c.ticker.upper()
        if c.action == "add":
            if ticker in current:
                errors.append(f"add {ticker}: already in watchlist")
                continue
            await queries.add_to_watchlist(db, DEFAULT_USER, ticker)
            current.add(ticker)
            applied.append({"ticker": ticker, "action": "add"})
        elif c.action == "remove":
            if ticker not in current:
                errors.append(f"remove {ticker}: not in watchlist")
                continue
            await queries.remove_from_watchlist(db, DEFAULT_USER, ticker)
            current.discard(ticker)
            applied.append({"ticker": ticker, "action": "remove"})
        else:
            errors.append(f"{ticker}: unknown action {c.action}")

    if applied:
        provider.set_tickers(sorted(current))
    return applied, errors


@router.post("/api/chat")
async def chat(
    body: ChatRequest,
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
) -> dict[str, Any]:
    """Send a user message, get an LLM response, auto-execute any actions."""
    portfolio_context = await build_portfolio_context(db, provider)

    history_rows = await queries.get_chat_history(db, DEFAULT_USER, limit=HISTORY_LIMIT)
    messages = _format_history(history_rows)
    messages.append({"role": "user", "content": body.message})

    try:
        response: ChatResponse = await call_llm(messages, portfolio_context)
    except Exception:
        logger.exception("LLM call failed")
        await queries.save_message(db, DEFAULT_USER, "user", body.message)
        fallback = "Sorry, I couldn't process that request right now."
        await queries.save_message(db, DEFAULT_USER, "assistant", fallback)
        return {
            "message": fallback,
            "trades_executed": [],
            "watchlist_changes_applied": [],
            "errors": ["llm_call_failed"],
        }

    trades_executed, trade_errors = await _apply_trades(db, provider, response.trades)
    watchlist_applied, watchlist_errors = await _apply_watchlist_changes(
        db, provider, response.watchlist_changes
    )
    errors = trade_errors + watchlist_errors

    await queries.save_message(db, DEFAULT_USER, "user", body.message)
    actions_payload: dict[str, Any] | None = None
    if trades_executed or watchlist_applied or errors:
        actions_payload = {
            "trades_executed": trades_executed,
            "watchlist_changes_applied": watchlist_applied,
            "errors": errors,
        }
    await queries.save_message(
        db, DEFAULT_USER, "assistant", response.message, actions=actions_payload
    )

    return {
        "message": response.message,
        "trades_executed": trades_executed,
        "watchlist_changes_applied": watchlist_applied,
        "errors": errors,
    }
