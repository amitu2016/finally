"""Portfolio computation helpers shared by routes and the snapshot loop."""

from __future__ import annotations

from typing import Any

import aiosqlite

from db import queries
from market.base import MarketDataProvider

DEFAULT_USER = "default"


class TradeError(Exception):
    """Raised when a trade fails validation (insufficient cash/shares, unknown ticker)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _enrich_position(pos: dict[str, Any], provider: MarketDataProvider) -> dict[str, Any]:
    ticker = pos["ticker"]
    quantity = pos["quantity"]
    avg_cost = pos["avg_cost"]
    price_obj = provider.get_price(ticker)
    current_price = price_obj.price if price_obj else avg_cost
    cost_basis = avg_cost * quantity
    unrealized_pnl = (current_price - avg_cost) * quantity
    pnl_pct = (unrealized_pnl / cost_basis * 100.0) if cost_basis else 0.0
    return {
        "ticker": ticker,
        "quantity": quantity,
        "avg_cost": avg_cost,
        "current_price": current_price,
        "unrealized_pnl": unrealized_pnl,
        "pnl_pct": pnl_pct,
    }


async def build_portfolio_snapshot(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    user_id: str = DEFAULT_USER,
) -> dict[str, Any]:
    """Return the current portfolio state with enriched positions and totals."""
    profile = await queries.get_user_profile(db, user_id)
    cash_balance = profile["cash_balance"] if profile else 0.0
    raw_positions = await queries.get_positions(db, user_id)
    enriched = [_enrich_position(p, provider) for p in raw_positions]
    positions_value = sum(p["quantity"] * p["current_price"] for p in enriched)
    total_value = cash_balance + positions_value
    return {
        "cash_balance": cash_balance,
        "total_value": total_value,
        "positions": enriched,
    }


async def compute_total_value(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    user_id: str = DEFAULT_USER,
) -> float:
    """Compute total portfolio value (cash + holdings)."""
    snapshot = await build_portfolio_snapshot(db, provider, user_id)
    return snapshot["total_value"]


async def execute_trade(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER,
) -> dict[str, Any]:
    """Execute a market order at the current price.

    Raises ``TradeError`` on validation failure (unknown ticker, insufficient
    cash/shares). On success, records the trade plus a fresh snapshot and
    returns the post-trade portfolio snapshot.
    """
    ticker = ticker.upper()
    price_obj = provider.get_price(ticker)
    if price_obj is None:
        raise TradeError(404, f"No price available for {ticker}")
    price = price_obj.price

    profile = await queries.get_user_profile(db, user_id)
    if profile is None:
        raise TradeError(500, "User profile missing")
    cash = profile["cash_balance"]
    position = await queries.get_position(db, user_id, ticker)

    if side == "buy":
        cost = price * quantity
        if cost > cash:
            raise TradeError(
                422, f"Insufficient cash: need {cost:.2f}, have {cash:.2f}"
            )
        if position is None:
            new_qty = quantity
            new_avg = price
        else:
            new_qty = position["quantity"] + quantity
            new_avg = (
                (position["avg_cost"] * position["quantity"]) + (price * quantity)
            ) / new_qty
        await queries.update_cash_balance(db, user_id, cash - cost)
        await queries.upsert_position(db, user_id, ticker, new_qty, new_avg)
    elif side == "sell":
        if position is None or position["quantity"] < quantity:
            held = position["quantity"] if position else 0
            raise TradeError(
                422, f"Insufficient shares: need {quantity}, have {held}"
            )
        proceeds = price * quantity
        new_qty = position["quantity"] - quantity
        await queries.update_cash_balance(db, user_id, cash + proceeds)
        await queries.upsert_position(
            db, user_id, ticker, new_qty, position["avg_cost"]
        )
    else:
        raise TradeError(422, f"Unknown trade side: {side}")

    await queries.record_trade(db, user_id, ticker, side, quantity, price)
    snapshot = await build_portfolio_snapshot(db, provider, user_id)
    await queries.record_snapshot(db, user_id, snapshot["total_value"])
    return {"price": price, "snapshot": snapshot}
