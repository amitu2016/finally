"""LLM chat integration via LiteLLM → OpenRouter → Cerebras."""

from __future__ import annotations

import logging
import os

import aiosqlite
from litellm import completion

from db import queries
from market.base import MarketDataProvider

from .portfolio import DEFAULT_USER, build_portfolio_snapshot
from .schemas import ChatResponse

logger = logging.getLogger("finally.llm")

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant for Indian stocks (NSE/BSE). "
    "You help the user analyze their portfolio, suggest trades, and manage "
    "their watchlist. Be concise, data-driven, and professional. "
    "When the user asks to buy or sell, include each trade in the `trades` "
    "array. When asked to add or remove a ticker, include the change in the "
    "`watchlist_changes` array. Always respond with valid JSON matching the "
    "required schema."
)

MOCK_RESPONSE = ChatResponse(
    message="Mock response: portfolio looks good!",
    trades=[],
    watchlist_changes=[],
)


def _is_mock_mode() -> bool:
    return os.getenv("LLM_MOCK", "false").lower() == "true"


async def build_portfolio_context(
    db: aiosqlite.Connection,
    provider: MarketDataProvider,
    user_id: str = DEFAULT_USER,
) -> str:
    """Render the user's portfolio + watchlist as a human-readable string for the LLM."""
    snapshot = await build_portfolio_snapshot(db, provider, user_id)
    watchlist = await queries.get_watchlist(db, user_id)
    prices = provider.get_all_prices()

    lines = [
        f"Cash: INR {snapshot['cash_balance']:.2f}",
        f"Total portfolio value: INR {snapshot['total_value']:.2f}",
    ]

    positions = snapshot["positions"]
    if positions:
        lines.append("Positions:")
        for p in positions:
            lines.append(
                f"  - {p['ticker']}: {p['quantity']} shares @ avg INR "
                f"{p['avg_cost']:.2f}, current INR {p['current_price']:.2f}, "
                f"P&L INR {p['unrealized_pnl']:.2f} ({p['pnl_pct']:+.2f}%)"
            )
    else:
        lines.append("Positions: (none)")

    if watchlist:
        lines.append("Watchlist:")
        for t in watchlist:
            sp = prices.get(t)
            if sp is not None:
                lines.append(
                    f"  - {t}: INR {sp.price:.2f} ({sp.change_pct:+.2f}%)"
                )
            else:
                lines.append(f"  - {t}: (no price)")
    else:
        lines.append("Watchlist: (empty)")

    return "\n".join(lines)


async def call_llm(
    messages: list[dict], portfolio_context: str
) -> ChatResponse:
    """Call the LLM and return a parsed ``ChatResponse``.

    If ``LLM_MOCK=true`` is set, returns a deterministic mock response and
    skips the network call.
    """
    if _is_mock_mode():
        return MOCK_RESPONSE.model_copy()

    system_content = SYSTEM_PROMPT + "\n\nCurrent portfolio:\n" + portfolio_context
    full_messages = [{"role": "system", "content": system_content}] + messages

    response = completion(
        model=MODEL,
        messages=full_messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    raw = response.choices[0].message.content
    return ChatResponse.model_validate_json(raw)
