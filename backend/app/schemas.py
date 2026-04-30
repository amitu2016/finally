"""Pydantic models for the LLM-facing chat structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TradeAction(BaseModel):
    """A single trade the LLM wants to auto-execute."""

    ticker: str = Field(..., min_length=1, max_length=20)
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)


class WatchlistChange(BaseModel):
    """Add or remove a ticker from the watchlist."""

    ticker: str = Field(..., min_length=1, max_length=20)
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """Top-level structured response returned by the LLM."""

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)
