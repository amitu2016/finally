"""Tests for db.queries CRUD functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from db import queries
from db.database import DEFAULT_USER_ID, get_db, init_db


@pytest.fixture
async def db_conn(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    async with get_db(db_path) as conn:
        yield conn


# ── users / cash ─────────────────────────────────────────────────────────────


async def test_get_user_profile_returns_seeded_user(db_conn):
    profile = await queries.get_user_profile(db_conn)
    assert profile is not None
    assert profile["id"] == DEFAULT_USER_ID
    assert profile["cash_balance"] == 100000.0


async def test_get_user_profile_unknown_user(db_conn):
    profile = await queries.get_user_profile(db_conn, "nonexistent")
    assert profile is None


async def test_update_cash_balance(db_conn):
    await queries.update_cash_balance(db_conn, DEFAULT_USER_ID, 50000.0)
    profile = await queries.get_user_profile(db_conn)
    assert profile["cash_balance"] == 50000.0


# ── positions ────────────────────────────────────────────────────────────────


async def test_get_positions_initially_empty(db_conn):
    positions = await queries.get_positions(db_conn)
    assert positions == []


async def test_upsert_position_inserts(db_conn):
    await queries.upsert_position(db_conn, DEFAULT_USER_ID, "RELIANCE", 10, 2400.0)
    positions = await queries.get_positions(db_conn)
    assert len(positions) == 1
    assert positions[0]["ticker"] == "RELIANCE"
    assert positions[0]["quantity"] == 10
    assert positions[0]["avg_cost"] == 2400.0
    assert positions[0]["updated_at"]


async def test_upsert_position_updates_existing(db_conn):
    await queries.upsert_position(db_conn, DEFAULT_USER_ID, "TCS", 5, 3400.0)
    await queries.upsert_position(db_conn, DEFAULT_USER_ID, "TCS", 8, 3500.0)
    pos = await queries.get_position(db_conn, DEFAULT_USER_ID, "TCS")
    assert pos["quantity"] == 8
    assert pos["avg_cost"] == 3500.0


async def test_upsert_position_zero_quantity_deletes(db_conn):
    await queries.upsert_position(db_conn, DEFAULT_USER_ID, "INFY", 5, 1500.0)
    await queries.upsert_position(db_conn, DEFAULT_USER_ID, "INFY", 0, 0.0)
    pos = await queries.get_position(db_conn, DEFAULT_USER_ID, "INFY")
    assert pos is None


async def test_get_position_unknown_returns_none(db_conn):
    pos = await queries.get_position(db_conn, DEFAULT_USER_ID, "MISSING")
    assert pos is None


async def test_get_positions_ordered_by_ticker(db_conn):
    for t, q in [("ZEEL", 1), ("ABB", 2), ("MRF", 3)]:
        await queries.upsert_position(db_conn, DEFAULT_USER_ID, t, q, 100.0)
    positions = await queries.get_positions(db_conn)
    assert [p["ticker"] for p in positions] == ["ABB", "MRF", "ZEEL"]


# ── trades ───────────────────────────────────────────────────────────────────


async def test_record_trade_returns_row_with_uuid(db_conn):
    trade = await queries.record_trade(
        db_conn, DEFAULT_USER_ID, "RELIANCE", "buy", 10.0, 2450.0
    )
    assert trade["id"]
    assert trade["ticker"] == "RELIANCE"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10.0
    assert trade["price"] == 2450.0
    assert trade["executed_at"]


async def test_record_trade_persisted(db_conn):
    await queries.record_trade(
        db_conn, DEFAULT_USER_ID, "TCS", "sell", 2.0, 3500.0
    )
    trades = await queries.get_trades(db_conn)
    assert len(trades) == 1
    assert trades[0]["ticker"] == "TCS"
    assert trades[0]["side"] == "sell"


async def test_get_trades_ordered_newest_first(db_conn):
    await queries.record_trade(db_conn, DEFAULT_USER_ID, "A", "buy", 1, 10)
    await queries.record_trade(db_conn, DEFAULT_USER_ID, "B", "buy", 1, 20)
    await queries.record_trade(db_conn, DEFAULT_USER_ID, "C", "buy", 1, 30)
    trades = await queries.get_trades(db_conn)
    assert [t["ticker"] for t in trades] == ["C", "B", "A"]


async def test_get_trades_respects_limit(db_conn):
    for i in range(5):
        await queries.record_trade(
            db_conn, DEFAULT_USER_ID, f"T{i}", "buy", 1, 100
        )
    trades = await queries.get_trades(db_conn, limit=3)
    assert len(trades) == 3


# ── snapshots ────────────────────────────────────────────────────────────────


async def test_record_snapshot_persists(db_conn):
    await queries.record_snapshot(db_conn, DEFAULT_USER_ID, 100500.0)
    snaps = await queries.get_snapshots(db_conn)
    assert len(snaps) == 1
    assert snaps[0]["total_value"] == 100500.0
    assert snaps[0]["recorded_at"]


async def test_get_snapshots_oldest_first(db_conn):
    for v in (100.0, 200.0, 300.0):
        await queries.record_snapshot(db_conn, DEFAULT_USER_ID, v)
    snaps = await queries.get_snapshots(db_conn)
    assert [s["total_value"] for s in snaps] == [100.0, 200.0, 300.0]


async def test_get_snapshots_respects_limit(db_conn):
    for v in range(10):
        await queries.record_snapshot(db_conn, DEFAULT_USER_ID, float(v))
    snaps = await queries.get_snapshots(db_conn, limit=3)
    assert len(snaps) == 3
    assert [s["total_value"] for s in snaps] == [7.0, 8.0, 9.0]


# ── watchlist ────────────────────────────────────────────────────────────────


async def test_get_watchlist_returns_seeded_tickers(db_conn):
    wl = await queries.get_watchlist(db_conn)
    assert "RELIANCE" in wl
    assert "TCS" in wl
    assert len(wl) == 10


async def test_add_to_watchlist(db_conn):
    await queries.add_to_watchlist(db_conn, DEFAULT_USER_ID, "BAJFINANCE")
    wl = await queries.get_watchlist(db_conn)
    assert "BAJFINANCE" in wl


async def test_add_to_watchlist_idempotent(db_conn):
    await queries.add_to_watchlist(db_conn, DEFAULT_USER_ID, "BAJFINANCE")
    await queries.add_to_watchlist(db_conn, DEFAULT_USER_ID, "BAJFINANCE")
    wl = await queries.get_watchlist(db_conn)
    assert wl.count("BAJFINANCE") == 1


async def test_remove_from_watchlist(db_conn):
    await queries.remove_from_watchlist(db_conn, DEFAULT_USER_ID, "RELIANCE")
    wl = await queries.get_watchlist(db_conn)
    assert "RELIANCE" not in wl


async def test_remove_unknown_ticker_is_noop(db_conn):
    await queries.remove_from_watchlist(db_conn, DEFAULT_USER_ID, "NEVER")
    wl = await queries.get_watchlist(db_conn)
    assert len(wl) == 10


# ── chat ─────────────────────────────────────────────────────────────────────


async def test_save_message_user(db_conn):
    msg = await queries.save_message(
        db_conn, DEFAULT_USER_ID, "user", "Buy 10 RELIANCE"
    )
    assert msg["id"]
    assert msg["role"] == "user"
    assert msg["content"] == "Buy 10 RELIANCE"
    assert msg["actions"] is None


async def test_save_message_assistant_with_actions(db_conn):
    actions = {"trades": [{"ticker": "RELIANCE", "side": "buy", "quantity": 10}]}
    msg = await queries.save_message(
        db_conn, DEFAULT_USER_ID, "assistant", "Done.", actions=actions
    )
    assert msg["actions"] == actions


async def test_get_chat_history_oldest_first(db_conn):
    await queries.save_message(db_conn, DEFAULT_USER_ID, "user", "hi")
    await queries.save_message(db_conn, DEFAULT_USER_ID, "assistant", "hello")
    await queries.save_message(db_conn, DEFAULT_USER_ID, "user", "buy 5 TCS")
    history = await queries.get_chat_history(db_conn)
    assert [m["content"] for m in history] == ["hi", "hello", "buy 5 TCS"]


async def test_get_chat_history_actions_roundtrip(db_conn):
    actions = {"watchlist_changes": [{"ticker": "ABC", "action": "add"}]}
    await queries.save_message(
        db_conn, DEFAULT_USER_ID, "assistant", "added", actions=actions
    )
    history = await queries.get_chat_history(db_conn)
    assert history[0]["actions"] == actions


async def test_get_chat_history_respects_limit(db_conn):
    for i in range(10):
        await queries.save_message(
            db_conn, DEFAULT_USER_ID, "user", f"msg-{i}"
        )
    history = await queries.get_chat_history(db_conn, limit=3)
    assert len(history) == 3
    assert [m["content"] for m in history] == ["msg-7", "msg-8", "msg-9"]
