"""Tests for db.database (init_db, get_db, schema, seeding)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db.database import (
    DEFAULT_CASH,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST,
    get_db,
    init_db,
)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


async def test_init_db_creates_file(db_path: str):
    await init_db(db_path)
    assert Path(db_path).exists()


async def test_init_db_creates_all_tables(db_path: str):
    await init_db(db_path)
    expected = {
        "users",
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    }
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        rows = await cursor.fetchall()
        names = {r["name"] for r in rows}
    assert expected.issubset(names)


async def test_init_db_seeds_default_user(db_path: str):
    await init_db(db_path)
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT id, cash_balance FROM users_profile WHERE id=?",
            (DEFAULT_USER_ID,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row["id"] == DEFAULT_USER_ID
    assert row["cash_balance"] == DEFAULT_CASH


async def test_init_db_seeds_default_watchlist(db_path: str):
    await init_db(db_path)
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT ticker FROM watchlist WHERE user_id=? ORDER BY ticker",
            (DEFAULT_USER_ID,),
        )
        rows = await cursor.fetchall()
    tickers = {r["ticker"] for r in rows}
    assert tickers == set(DEFAULT_WATCHLIST)


async def test_init_db_idempotent(db_path: str):
    """Re-running init_db must not duplicate seed data."""
    await init_db(db_path)
    await init_db(db_path)
    async with get_db(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM users_profile")
        users = (await cursor.fetchone())["n"]
        cursor = await db.execute("SELECT COUNT(*) AS n FROM watchlist")
        wl = (await cursor.fetchone())["n"]
    assert users == 1
    assert wl == len(DEFAULT_WATCHLIST)


async def test_init_db_does_not_clobber_existing_data(db_path: str):
    """If users_profile is non-empty, seed step is skipped."""
    await init_db(db_path)
    async with get_db(db_path) as db:
        await db.execute(
            "UPDATE users_profile SET cash_balance=? WHERE id=?",
            (42.0, DEFAULT_USER_ID),
        )
        await db.commit()
    await init_db(db_path)
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT cash_balance FROM users_profile WHERE id=?",
            (DEFAULT_USER_ID,),
        )
        row = await cursor.fetchone()
    assert row["cash_balance"] == 42.0


async def test_init_db_creates_parent_dirs(tmp_path: Path):
    nested = tmp_path / "nested" / "deeper" / "test.db"
    await init_db(str(nested))
    assert nested.exists()


async def test_get_db_uses_row_factory(db_path: str):
    await init_db(db_path)
    async with get_db(db_path) as db:
        assert db.row_factory is sqlite3.Row
        cursor = await db.execute(
            "SELECT id FROM users_profile LIMIT 1"
        )
        row = await cursor.fetchone()
    assert row["id"] == DEFAULT_USER_ID


async def test_trades_side_check(db_path: str):
    await init_db(db_path)
    async with get_db(db_path) as db:
        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("t1", DEFAULT_USER_ID, "RELIANCE", "hold", 1.0, 100.0, "2026-01-01"),
            )
            await db.commit()
