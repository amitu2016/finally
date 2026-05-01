import asyncio
import logging
import os
import random
from datetime import datetime, timezone

import httpx

from .base import MarketDataProvider
from .types import StockPrice

logger = logging.getLogger(__name__)

BASE_URL = "https://stock.indianapi.in"

# --------------------------------------------------------------------------- #
# Rate-limit and quota constants                                               #
# --------------------------------------------------------------------------- #

MONTHLY_QUOTA = 5000        # maximum API calls per calendar month
SAFETY_FACTOR = 0.9         # use 90% of quota to leave headroom
EFFECTIVE_QUOTA = int(MONTHLY_QUOTA * SAFETY_FACTOR)  # 4500 calls/month

REQUEST_TIMEOUT = 10.0      # HTTP request timeout (seconds)
HISTORY_LIMIT = 200         # rolling price history buffer per ticker
JITTER = 10.0               # ±seconds of random jitter per sleep


def _compute_call_interval() -> float:
    """Seconds between consecutive API calls to stay within the monthly quota.

    Reads DAILY_RUNTIME_HOURS to adjust for servers that don't run 24/7.
    Default assumes continuous operation (24 h/day × 30 days/month).
    """
    daily_hours = float(os.getenv("DAILY_RUNTIME_HOURS", "24"))
    monthly_runtime_seconds = daily_hours * 3600 * 30
    return monthly_runtime_seconds / EFFECTIVE_QUOTA


# Recalculated at module load time; DAILY_RUNTIME_HOURS must be set before import.
QUOTA_CALL_INTERVAL: float = _compute_call_interval()


def _parse_response(ticker: str, data: dict, prev: StockPrice | None) -> StockPrice | None:
    """Convert raw IndianAPI JSON to StockPrice. Returns None if no valid price found."""
    raw = data.get("currentPrice", {})
    price_raw = raw.get("NSE") or raw.get("BSE")
    if not price_raw:
        return None

    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        return None

    if price <= 0:
        return None

    return StockPrice(
        ticker=ticker,
        price=price,
        prev_price=prev.price if prev else price,
        change_pct=float(data.get("percentChange") or 0.0),
        timestamp=datetime.now(timezone.utc),
        company_name=data.get("companyName", ""),
    )


async def _fetch_one(client: httpx.AsyncClient, ticker: str, api_key: str) -> dict:
    """Fetch raw JSON for a single ticker. Raises on non-200."""
    resp = await client.get(
        f"{BASE_URL}/stock",
        params={"name": ticker},
        headers={"X-Api-Key": api_key},
    )
    resp.raise_for_status()
    return resp.json()


class IndianAPIProvider(MarketDataProvider):

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._tickers: list[str] = []
        self._cache: dict[str, StockPrice] = {}
        self._history: dict[str, list[StockPrice]] = {}
        self._task: asyncio.Task | None = None
        # Monthly quota tracking (resets automatically on calendar-month rollover)
        now = datetime.now(timezone.utc)
        self._quota_month: tuple[int, int] = (now.year, now.month)
        self._calls_this_month: int = 0
        self._is_rate_limited: bool = False

    @property
    def is_rate_limited(self) -> bool:
        """True when the API is rate-limited (HTTP 429) or the monthly quota is exhausted."""
        return self._is_rate_limited or self._calls_this_month >= MONTHLY_QUOTA

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return dict(self._cache)

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return list(self._history.get(ticker, []))[-limit:]

    def set_tickers(self, tickers: list[str]) -> None:
        removed = set(self._tickers) - set(tickers)
        for ticker in removed:
            self._cache.pop(ticker, None)
            self._history.pop(ticker, None)
        self._tickers = list(tickers)

    # ---------------------------------------------------------------------- #
    # Quota helpers                                                           #
    # ---------------------------------------------------------------------- #

    def _maybe_reset_monthly_quota(self) -> None:
        """Reset the monthly call counter when a new calendar month begins."""
        now = datetime.now(timezone.utc)
        current_month = (now.year, now.month)
        if current_month != self._quota_month:
            self._calls_this_month = 0
            self._is_rate_limited = False
            self._quota_month = current_month
            logger.info(
                "Monthly API quota reset for %04d-%02d",
                current_month[0],
                current_month[1],
            )

    def get_quota_status(self) -> dict:
        """Return current monthly API usage statistics."""
        self._maybe_reset_monthly_quota()
        return {
            "calls_this_month": self._calls_this_month,
            "monthly_quota": MONTHLY_QUOTA,
            "calls_remaining": max(0, MONTHLY_QUOTA - self._calls_this_month),
            "quota_month": f"{self._quota_month[0]:04d}-{self._quota_month[1]:02d}",
        }

    # ---------------------------------------------------------------------- #
    # Polling implementation                                                  #
    # ---------------------------------------------------------------------- #

    async def _poll_loop(self) -> None:
        """Round-robin single-ticker polling to stay within the monthly quota.

        Polls one ticker per QUOTA_CALL_INTERVAL seconds (±jitter), cycling
        through all tracked tickers sequentially. With 10 tickers and the
        default 576 s interval, each ticker refreshes roughly every 96 minutes
        — comfortably within the 5,000 call/month budget.
        """
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            idx = 0
            while True:
                self._maybe_reset_monthly_quota()

                if self._calls_this_month >= MONTHLY_QUOTA:
                    self._is_rate_limited = True
                    logger.warning(
                        "Monthly quota of %d calls exhausted. Pausing for 1h.",
                        MONTHLY_QUOTA,
                    )
                    await asyncio.sleep(3600)
                    continue

                if self._is_rate_limited:
                    await asyncio.sleep(QUOTA_CALL_INTERVAL)
                    continue

                tickers = self._tickers
                if tickers:
                    ticker = tickers[idx % len(tickers)]
                    idx += 1
                    await self._poll_one(client, ticker)

                jitter = random.uniform(-JITTER, JITTER)
                await asyncio.sleep(max(10.0, QUOTA_CALL_INTERVAL + jitter))

    async def _poll_one(self, client: httpx.AsyncClient, ticker: str) -> bool:
        """Fetch and cache the latest price for a single ticker.

        Increments the monthly call counter regardless of success or failure
        (a network error still consumes quota on the provider side).
        Returns True on success, False on any error.
        """
        self._calls_this_month += 1
        try:
            data = await _fetch_one(client, ticker, self._api_key)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._is_rate_limited = True
                logger.warning(
                    "IndianAPI rate limit hit (HTTP 429) for %s. "
                    "Provider marked as rate-limited.",
                    ticker,
                )
            else:
                logger.warning("IndianAPI poll failed for %s: %s", ticker, exc)
            return False
        except Exception as exc:
            logger.warning("IndianAPI poll failed for %s: %s", ticker, exc)
            return False

        prev = self._cache.get(ticker)
        sp = _parse_response(ticker, data, prev)
        if sp is None:
            logger.warning("IndianAPI: no valid price in response for %s", ticker)
            return False

        self._cache[ticker] = sp
        buf = self._history.setdefault(ticker, [])
        buf.append(sp)
        if len(buf) > HISTORY_LIMIT:
            self._history[ticker] = buf[-HISTORY_LIMIT:]
        return True
