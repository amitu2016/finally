"""Portfolio (positions, trades, history) endpoints."""

from __future__ import annotations

from typing import Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import queries
from market.base import MarketDataProvider

from ..dependencies import get_db_conn, get_market
from ..portfolio import (
    DEFAULT_USER,
    TradeError,
    build_portfolio_snapshot,
    execute_trade as _execute_trade,
)

router = APIRouter()


class TradeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    quantity: float = Field(..., gt=0)
    side: Literal["buy", "sell"]


@router.get("/api/portfolio")
async def get_portfolio(
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
) -> dict:
    """Return current portfolio: cash, positions with P&L, total value."""
    return await build_portfolio_snapshot(db, provider)


@router.post("/api/portfolio/trade")
async def execute_trade(
    body: TradeRequest,
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
) -> dict:
    """Execute a market order at the current price."""
    try:
        result = await _execute_trade(
            db, provider, body.ticker, body.side, body.quantity
        )
    except TradeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return result["snapshot"]


@router.get("/api/portfolio/history")
async def get_portfolio_history(
    db: aiosqlite.Connection = Depends(get_db_conn),
) -> list[dict]:
    """Return portfolio value snapshots over time, oldest first."""
    snapshots = await queries.get_snapshots(db, DEFAULT_USER)
    return [
        {"total_value": s["total_value"], "recorded_at": s["recorded_at"]}
        for s in snapshots
    ]
