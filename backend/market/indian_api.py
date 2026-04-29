import asyncio
import logging
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
QUOTA_SAFETY_FACTOR = 0.9   # use only 90 % of the quota to leave headroom
MIN_CALL_INTERVAL = 1.0     # hard rate limit: at most 1 request per second

SECONDS_PER_MONTH = 30 * 24 * 3600  # conservative 30-day month = 2,592,000 s

# Minimum wait between consecutive API calls to stay within monthly quota.
# Formula: total_seconds / (monthly_budget × safety_factor)
# = 2,592,000 / (5,000 × 0.9) ≈ 576 s
# The max() ensures we never violate the 1-req/sec hard rate limit either.
QUOTA_CALL_INTERVAL: float = max(
    MIN_CALL_INTERVAL,
    SECONDS_PER_MONTH / (MONTHLY_QUOTA * QUOTA_SAFETY_FACTOR),
)

POLL_JITTER = 10.0          # random jitter added to each sleep (seconds)
REQUEST_TIMEOUT = 10.0      # HTTP request timeout (seconds)
MAX_BACKOFF_DELAY = 3600.0  # cap consecutive-failure backoff at 1 hour
HISTORY_LIMIT = 200         # rolling price history buffer per ticker


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
        """Round-robin over all tracked tickers, honouring rate and quota limits.

        One API call is made per iteration (single ticker), then the loop sleeps
        for QUOTA_CALL_INTERVAL seconds. This ensures:
        - At most 1 request per QUOTA_CALL_INTERVAL seconds (≈576 s)
        - Monthly usage stays within MONTHLY_QUOTA × QUOTA_SAFETY_FACTOR calls
        - The 1-req/sec hard rate limit is never violated

        With N tickers, each individual ticker is refreshed every
        QUOTA_CALL_INTERVAL × N seconds (≈96 min for 10 tickers).
        """
        ticker_index = 0
        consecutive_failures = 0

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            while True:
                tickers = self._tickers  # snapshot; list may change between iterations

                if not tickers:
                    await asyncio.sleep(QUOTA_CALL_INTERVAL)
                    consecutive_failures = 0
                    continue

                # Enforce monthly quota before making a call
                self._maybe_reset_monthly_quota()
                if self._calls_this_month >= MONTHLY_QUOTA:
                    logger.warning(
                        "Monthly API quota of %d calls exhausted (%d used). "
                        "Polling paused until next month.",
                        MONTHLY_QUOTA,
                        self._calls_this_month,
                    )
                    await asyncio.sleep(3600)  # re-check hourly
                    continue

                # Round-robin: advance index, wrapping if the ticker list changed
                ticker_index = ticker_index % len(tickers)
                ticker = tickers[ticker_index]
                ticker_index += 1

                success = await self._poll_one(client, ticker)
                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1

                # Exponential backoff on consecutive failures, capped at MAX_BACKOFF_DELAY
                if consecutive_failures:
                    delay = min(
                        QUOTA_CALL_INTERVAL * (2**consecutive_failures),
                        MAX_BACKOFF_DELAY,
                    )
                else:
                    delay = QUOTA_CALL_INTERVAL

                delay += random.uniform(0, POLL_JITTER)
                await asyncio.sleep(delay)

    async def _poll_one(self, client: httpx.AsyncClient, ticker: str) -> bool:
        """Fetch and cache the latest price for a single ticker.

        Increments the monthly call counter regardless of success or failure
        (a network error still consumes quota on the provider side).
        Returns True on success, False on any error.
        """
        self._calls_this_month += 1
        try:
            data = await _fetch_one(client, ticker, self._api_key)
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

    async def _poll_all(self, client: httpx.AsyncClient) -> int:
        """Fetch all tickers concurrently; log errors without interrupting the stream.

        Retained for use in tests. In production the poll loop uses the
        rate-limited round-robin _poll_one path instead.
        Returns the number of tickers successfully updated.
        """
        tasks = [_fetch_one(client, t, self._api_key) for t in self._tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = 0
        for ticker, result in zip(self._tickers, results):
            if isinstance(result, Exception):
                logger.warning("IndianAPI poll failed for %s: %s", ticker, result)
                continue

            prev = self._cache.get(ticker)
            sp = _parse_response(ticker, result, prev)
            if sp is None:
                logger.warning("IndianAPI: no valid price in response for %s", ticker)
                continue

            self._cache[ticker] = sp
            buf = self._history.setdefault(ticker, [])
            buf.append(sp)
            if len(buf) > HISTORY_LIMIT:
                self._history[ticker] = buf[-HISTORY_LIMIT:]
            successes += 1

        return successes
