"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import AsyncIterator

import aiosqlite
from fastapi import Request

from db.database import get_db
from market.base import MarketDataProvider


def get_market(request: Request) -> MarketDataProvider:
    """Return the active market data provider from app state."""
    return request.app.state.market


async def get_db_conn(request: Request) -> AsyncIterator[aiosqlite.Connection]:
    """Yield an aiosqlite connection scoped to the request."""
    async with get_db(request.app.state.db_path) as conn:
        yield conn
