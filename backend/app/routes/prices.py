"""Price streaming and history endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from db import queries
from db.database import get_db
from market.base import MarketDataProvider
from market.types import StockPrice

from ..dependencies import get_current_user, get_current_user_sse, get_market

router = APIRouter()

STREAM_INTERVAL = 0.5          # seconds between SSE pushes
WATCHLIST_REFRESH = 5.0        # seconds between watchlist DB re-reads


def _serialize(p: StockPrice) -> dict:
    return {
        "ticker": p.ticker,
        "price": p.price,
        "prev_price": p.prev_price,
        "change_pct": p.change_pct,
        "timestamp": p.timestamp.isoformat(),
        "company_name": p.company_name,
    }


@router.get("/api/stream/prices")
async def stream_prices(
    request: Request,
    user_id: str = Depends(get_current_user_sse),
) -> EventSourceResponse:
    """SSE stream of latest prices for the authenticated user's watchlist."""
    db_path = request.app.state.db_path
    provider: MarketDataProvider = request.app.state.market

    async def event_generator() -> AsyncIterator[dict]:
        tickers: set[str] = set()
        last_refresh = -WATCHLIST_REFRESH  # force immediate load on first tick
        while True:
            if await request.is_disconnected():
                break
            now = asyncio.get_event_loop().time()
            if now - last_refresh >= WATCHLIST_REFRESH:
                async with get_db(db_path) as conn:
                    tickers = set(await queries.get_watchlist(conn, user_id))
                last_refresh = now
            prices = provider.get_all_prices()
            for ticker in tickers:
                p = prices.get(ticker)
                if p is None:
                    continue
                yield {"data": json.dumps(_serialize(p))}
            await asyncio.sleep(STREAM_INTERVAL)

    return EventSourceResponse(event_generator())


@router.get("/api/prices/{ticker}/history")
async def price_history(
    ticker: str,
    provider: MarketDataProvider = Depends(get_market),
    user_id: str = Depends(get_current_user),
) -> list[dict]:
    """Return the rolling in-memory price history for a ticker."""
    history = provider.get_history(ticker.upper(), 200)
    return [_serialize(p) for p in history]
