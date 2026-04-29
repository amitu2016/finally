"""Yahoo Finance market data provider for Indian NSE stocks.

Uses the yfinance library (unofficial Yahoo Finance API). No API key required.
Data is typically delayed ~15 minutes but generous rate limits make it suitable
for demo and development use.

NSE tickers are mapped to Yahoo symbols by appending the .NS suffix.
"""

import asyncio
import logging
import math
from datetime import datetime, timezone

import yfinance as yf

from .base import MarketDataProvider
from .types import StockPrice

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60.0   # seconds between full-watchlist refresh
HISTORY_LIMIT = 200


def _yahoo_symbol(ticker: str) -> str:
    return f"{ticker}.NS"


def _fetch_ticker_sync(ticker: str) -> dict | None:
    """Blocking fetch for one ticker via yfinance. Returns None on error or missing data."""
    try:
        fi = yf.Ticker(_yahoo_symbol(ticker)).fast_info
        price = fi.last_price
        prev = fi.previous_close

        if price is None or (isinstance(price, float) and math.isnan(price)):
            logger.warning("Yahoo: no valid price for %s", ticker)
            return None

        price = float(price)
        prev_close = float(prev) if (prev is not None and not (isinstance(prev, float) and math.isnan(prev))) else price
        return {"price": price, "prev_close": prev_close}
    except Exception as exc:
        logger.warning("Yahoo: fetch failed for %s: %s", ticker, exc)
        return None


class YahooFinanceProvider(MarketDataProvider):

    def __init__(self) -> None:
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
        while True:
            await self._poll_all()
            await asyncio.sleep(POLL_INTERVAL)

    async def _poll_all(self) -> None:
        loop = asyncio.get_event_loop()
        for ticker in list(self._tickers):
            data = await loop.run_in_executor(None, _fetch_ticker_sync, ticker)
            if data is None:
                continue
            self._update_cache(ticker, data["price"], data["prev_close"])

    def _update_cache(self, ticker: str, price: float, prev_close: float) -> None:
        prev = self._cache.get(ticker)
        prev_price = prev.price if prev else price
        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0

        sp = StockPrice(
            ticker=ticker,
            price=round(price, 2),
            prev_price=prev_price,
            change_pct=change_pct,
            timestamp=datetime.now(timezone.utc),
        )
        self._cache[ticker] = sp
        buf = self._history.setdefault(ticker, [])
        buf.append(sp)
        if len(buf) > HISTORY_LIMIT:
            self._history[ticker] = buf[-HISTORY_LIMIT:]
