"""Portfolio (positions, trades, history) endpoints."""

from __future__ import annotations

from typing import Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import queries
from market.base import MarketDataProvider

from ..dependencies import get_current_user, get_db_conn, get_market
from ..portfolio import TradeError, build_portfolio_snapshot, execute_trade as _execute_trade

router = APIRouter()


class TradeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    quantity: float = Field(..., gt=0)
    side: Literal["buy", "sell"]


@router.get("/api/portfolio")
async def get_portfolio(
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
    user_id: str = Depends(get_current_user),
) -> dict:
    return await build_portfolio_snapshot(db, provider, user_id)


@router.post("/api/portfolio/trade")
async def execute_trade(
    body: TradeRequest,
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
    user_id: str = Depends(get_current_user),
) -> dict:
    try:
        result = await _execute_trade(db, provider, body.ticker, body.side, body.quantity, user_id)
    except TradeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return result["snapshot"]


@router.get("/api/portfolio/history")
async def get_portfolio_history(
    db: aiosqlite.Connection = Depends(get_db_conn),
    user_id: str = Depends(get_current_user),
) -> list[dict]:
    snapshots = await queries.get_snapshots(db, user_id)
    return [
        {"total_value": s["total_value"], "recorded_at": s["recorded_at"]}
        for s in snapshots
    ]
