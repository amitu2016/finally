"""Watchlist CRUD endpoints."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import queries
from market.base import MarketDataProvider

from ..dependencies import get_db_conn, get_market

router = APIRouter()

DEFAULT_USER = "default"


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)


def _format_entry(ticker: str, prices: dict) -> dict:
    p = prices.get(ticker)
    if p is None:
        return {
            "ticker": ticker,
            "price": None,
            "prev_price": None,
            "change_pct": None,
            "company_name": "",
        }
    return {
        "ticker": p.ticker,
        "price": p.price,
        "prev_price": p.prev_price,
        "change_pct": p.change_pct,
        "company_name": p.company_name,
    }


@router.get("/api/watchlist")
async def get_watchlist(
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
) -> list[dict]:
    """Return the watchlist with the latest cached price per ticker."""
    tickers = await queries.get_watchlist(db, DEFAULT_USER)
    prices = provider.get_all_prices()
    return [_format_entry(t, prices) for t in tickers]


@router.post("/api/watchlist", status_code=201)
async def add_watchlist_ticker(
    body: WatchlistAddRequest,
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
) -> dict:
    """Add a ticker to the watchlist; 409 if already present."""
    ticker = body.ticker.upper()
    existing = await queries.get_watchlist(db, DEFAULT_USER)
    if ticker in existing:
        raise HTTPException(status_code=409, detail=f"{ticker} already in watchlist")
    await queries.add_to_watchlist(db, DEFAULT_USER, ticker)
    updated = await queries.get_watchlist(db, DEFAULT_USER)
    provider.set_tickers(updated)
    return {"ticker": ticker, "added": True}


@router.delete("/api/watchlist/{ticker}")
async def remove_watchlist_ticker(
    ticker: str,
    db: aiosqlite.Connection = Depends(get_db_conn),
    provider: MarketDataProvider = Depends(get_market),
) -> dict:
    """Remove a ticker from the watchlist; 404 if not present."""
    ticker = ticker.upper()
    existing = await queries.get_watchlist(db, DEFAULT_USER)
    if ticker not in existing:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")
    await queries.remove_from_watchlist(db, DEFAULT_USER, ticker)
    updated = await queries.get_watchlist(db, DEFAULT_USER)
    provider.set_tickers(updated)
    return {"ticker": ticker, "removed": True}
