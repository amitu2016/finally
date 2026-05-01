"""Async SQLite connection and initialization."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from .queries import DEFAULT_WATCHLIST

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DEFAULT_USER_ID = "default"
DEFAULT_CASH = 100000.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db(db_path: str) -> None:
    """Create schema and seed default data if the database is empty."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    schema_sql = SCHEMA_PATH.read_text()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        await db.executescript(schema_sql)
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) AS n FROM users_profile")
        row = await cursor.fetchone()
        if row["n"] > 0:
            return

        now = _now()
        await db.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_CASH, now),
        )
        await db.executemany(
            "INSERT INTO watchlist (user_id, ticker, added_at) VALUES (?, ?, ?)",
            [(DEFAULT_USER_ID, ticker, now) for ticker in DEFAULT_WATCHLIST],
        )
        await db.commit()


@asynccontextmanager
async def get_db(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager yielding an aiosqlite connection with Row factory."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        yield db
