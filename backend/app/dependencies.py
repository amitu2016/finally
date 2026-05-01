"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import AsyncIterator

import aiosqlite
from fastapi import HTTPException, Query, Request

from db.database import get_db
from market.base import MarketDataProvider

from .auth import decode_token


def get_market(request: Request) -> MarketDataProvider:
    """Return the active market data provider from app state."""
    return request.app.state.market


async def get_db_conn(request: Request) -> AsyncIterator[aiosqlite.Connection]:
    """Yield an aiosqlite connection scoped to the request."""
    async with get_db(request.app.state.db_path) as conn:
        yield conn


def _extract_user_id(token: str | None) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


async def get_current_user(request: Request) -> str:
    """Extract user_id from Authorization: Bearer <token> header."""
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else None
    return _extract_user_id(token)


async def get_current_user_sse(
    request: Request,
    token: str | None = Query(default=None),
) -> str:
    """Like get_current_user but also accepts ?token= query param (for EventSource)."""
    if not token:
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else None
    return _extract_user_id(token)
