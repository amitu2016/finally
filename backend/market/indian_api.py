import asyncio
import logging
import random
from datetime import datetime, timezone

import httpx

from .base import MarketDataProvider
from .types import StockPrice

logger = logging.getLogger(__name__)

BASE_URL = "https://stock.indianapi.in"
POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 300
POLL_JITTER = 5.0
REQUEST_TIMEOUT = 10.0
HISTORY_LIMIT = 200


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

    async def _poll_loop(self) -> None:
        consecutive_failures = 0
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            while True:
                if self._tickers:
                    successes = await self._poll_all(client)
                    if successes == 0:
                        consecutive_failures += 1
                    else:
                        consecutive_failures = 0
                else:
                    consecutive_failures = 0
                delay = min(POLL_INTERVAL * (2 ** consecutive_failures), MAX_POLL_INTERVAL)
                delay += random.uniform(0, POLL_JITTER)
                await asyncio.sleep(delay)

    async def _poll_all(self, client: httpx.AsyncClient) -> int:
        """Fetch all tickers concurrently; log errors without interrupting the stream.

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
