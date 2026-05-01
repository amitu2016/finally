"""Async CRUD query functions for FinAlly tables."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

DEFAULT_USER = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


DEFAULT_WATCHLIST = (
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "BHARTIARTL", "SBIN", "ITC", "LT", "HINDUNILVR",
)

# ── auth ─────────────────────────────────────────────────────────────────────


async def create_user(
    db: aiosqlite.Connection, username: str, password_hash: str
) -> dict[str, Any]:
    """Create a user account with a fresh ₹1,00,000 portfolio and default watchlist."""
    user_id = _uuid()
    now = _now()
    await db.execute(
        "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, password_hash, now),
    )
    await db.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (user_id, 100000.0, now),
    )
    await db.executemany(
        "INSERT INTO watchlist (user_id, ticker, added_at) VALUES (?, ?, ?)",
        [(user_id, ticker, now) for ticker in DEFAULT_WATCHLIST],
    )
    await db.commit()
    return {"id": user_id, "username": username, "created_at": now}


async def get_user_by_username(
    db: aiosqlite.Connection, username: str
) -> dict[str, Any] | None:
    cursor = await db.execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE username=?",
        (username,),
    )
    return _row_to_dict(await cursor.fetchone())


async def get_user_by_id(
    db: aiosqlite.Connection, user_id: str
) -> dict[str, Any] | None:
    cursor = await db.execute(
        "SELECT id, username, created_at FROM users WHERE id=?",
        (user_id,),
    )
    return _row_to_dict(await cursor.fetchone())


async def get_all_user_ids(db: aiosqlite.Connection) -> list[str]:
    """Return all user_ids in users_profile (for snapshot loop)."""
    cursor = await db.execute("SELECT id FROM users_profile")
    rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def get_all_watchlist_tickers(db: aiosqlite.Connection) -> list[str]:
    """Return distinct tickers across ALL users' watchlists (for market provider)."""
    cursor = await db.execute("SELECT DISTINCT ticker FROM watchlist")
    rows = await cursor.fetchall()
    return [r["ticker"] for r in rows]


# ── users / portfolio ────────────────────────────────────────────────────────


async def get_user_profile(
    db: aiosqlite.Connection, user_id: str = DEFAULT_USER
) -> dict[str, Any] | None:
    """Return the user's profile row, or None if missing."""
    cursor = await db.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id=?",
        (user_id,),
    )
    return _row_to_dict(await cursor.fetchone())


async def update_cash_balance(
    db: aiosqlite.Connection, user_id: str, new_balance: float
) -> None:
    """Set the user's cash balance to ``new_balance``."""
    await db.execute(
        "UPDATE users_profile SET cash_balance=? WHERE id=?",
        (new_balance, user_id),
    )
    await db.commit()


# ── positions ────────────────────────────────────────────────────────────────


async def get_positions(
    db: aiosqlite.Connection, user_id: str = DEFAULT_USER
) -> list[dict[str, Any]]:
    """Return all open positions for a user, ordered by ticker."""
    cursor = await db.execute(
        "SELECT user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id=? ORDER BY ticker",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_position(
    db: aiosqlite.Connection, user_id: str, ticker: str
) -> dict[str, Any] | None:
    """Return a single position or None."""
    cursor = await db.execute(
        "SELECT user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id=? AND ticker=?",
        (user_id, ticker),
    )
    return _row_to_dict(await cursor.fetchone())


async def upsert_position(
    db: aiosqlite.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    avg_cost: float,
) -> None:
    """Insert or update a position. Deletes the row when quantity is zero."""
    if quantity == 0:
        await db.execute(
            "DELETE FROM positions WHERE user_id=? AND ticker=?",
            (user_id, ticker),
        )
        await db.commit()
        return

    await db.execute(
        "INSERT INTO positions (user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, ticker) DO UPDATE SET "
        "quantity=excluded.quantity, avg_cost=excluded.avg_cost, "
        "updated_at=excluded.updated_at",
        (user_id, ticker, quantity, avg_cost, _now()),
    )
    await db.commit()


# ── trades ───────────────────────────────────────────────────────────────────


async def record_trade(
    db: aiosqlite.Connection,
    user_id: str,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
) -> dict[str, Any]:
    """Append a trade to the trades log and return the inserted row."""
    trade_id = _uuid()
    executed_at = _now()
    await db.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade_id, user_id, ticker, side, quantity, price, executed_at),
    )
    await db.commit()
    return {
        "id": trade_id,
        "user_id": user_id,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": executed_at,
    }


async def get_trades(
    db: aiosqlite.Connection,
    user_id: str = DEFAULT_USER,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return recent trades for a user, newest first."""
    cursor = await db.execute(
        "SELECT id, user_id, ticker, side, quantity, price, executed_at "
        "FROM trades WHERE user_id=? ORDER BY executed_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── snapshots ────────────────────────────────────────────────────────────────


async def record_snapshot(
    db: aiosqlite.Connection, user_id: str, total_value: float
) -> None:
    """Insert a portfolio value snapshot with the current timestamp."""
    await db.execute(
        "INSERT INTO portfolio_snapshots (user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?)",
        (user_id, total_value, _now()),
    )
    await db.commit()


async def get_snapshots(
    db: aiosqlite.Connection,
    user_id: str = DEFAULT_USER,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return most-recent snapshots in chronological order (oldest first)."""
    cursor = await db.execute(
        "SELECT id, user_id, total_value, recorded_at FROM ("
        "  SELECT id, user_id, total_value, recorded_at "
        "  FROM portfolio_snapshots WHERE user_id=? "
        "  ORDER BY recorded_at DESC LIMIT ?"
        ") ORDER BY recorded_at ASC",
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── watchlist ────────────────────────────────────────────────────────────────


async def get_watchlist(
    db: aiosqlite.Connection, user_id: str = DEFAULT_USER
) -> list[str]:
    """Return the user's watchlist tickers, ordered by added_at then ticker."""
    cursor = await db.execute(
        "SELECT ticker FROM watchlist WHERE user_id=? "
        "ORDER BY added_at ASC, ticker ASC",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [r["ticker"] for r in rows]


async def add_to_watchlist(
    db: aiosqlite.Connection, user_id: str, ticker: str
) -> None:
    """Add a ticker to the watchlist (idempotent)."""
    await db.execute(
        "INSERT OR IGNORE INTO watchlist (user_id, ticker, added_at) "
        "VALUES (?, ?, ?)",
        (user_id, ticker, _now()),
    )
    await db.commit()


async def remove_from_watchlist(
    db: aiosqlite.Connection, user_id: str, ticker: str
) -> None:
    """Remove a ticker from the watchlist."""
    await db.execute(
        "DELETE FROM watchlist WHERE user_id=? AND ticker=?",
        (user_id, ticker),
    )
    await db.commit()


# ── chat ─────────────────────────────────────────────────────────────────────


async def save_message(
    db: aiosqlite.Connection,
    user_id: str,
    role: str,
    content: str,
    actions: dict | list | None = None,
) -> dict[str, Any]:
    """Persist a chat message and return the inserted row."""
    msg_id = _uuid()
    created_at = _now()
    actions_json = json.dumps(actions) if actions is not None else None
    await db.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, user_id, role, content, actions_json, created_at),
    )
    await db.commit()
    return {
        "id": msg_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": created_at,
    }


async def get_chat_history(
    db: aiosqlite.Connection,
    user_id: str = DEFAULT_USER,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return most-recent chat messages in chronological order (oldest first)."""
    cursor = await db.execute(
        "SELECT id, user_id, role, content, actions, created_at FROM ("
        "  SELECT id, user_id, role, content, actions, created_at "
        "  FROM chat_messages WHERE user_id=? "
        "  ORDER BY created_at DESC LIMIT ?"
        ") ORDER BY created_at ASC",
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["actions"] = json.loads(d["actions"]) if d["actions"] else None
        result.append(d)
    return result
