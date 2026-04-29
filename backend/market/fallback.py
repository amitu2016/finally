import asyncio
import logging

from .base import MarketDataProvider
from .indian_api import IndianAPIProvider
from .simulator import SimulatorProvider
from .types import StockPrice

logger = logging.getLogger(__name__)

MONITOR_INTERVAL = 30.0  # seconds between rate-limit checks


class FallbackProvider(MarketDataProvider):
    """Wraps IndianAPIProvider with automatic fallback to SimulatorProvider.

    When the Indian Stock API returns HTTP 429 or the monthly quota is exhausted,
    all data requests are transparently rerouted to the built-in GBM simulator.
    The simulator runs as a warm standby from the moment start() is called, so
    prices are available immediately upon fallback with no cold-start delay.

    The fallback is permanent for the lifetime of this instance; restart the
    provider to re-attempt the real API (e.g. after a quota month rolls over).
    """

    def __init__(self, api_key: str) -> None:
        self._primary = IndianAPIProvider(api_key)
        self._fallback = SimulatorProvider()
        self._using_fallback: bool = False
        self._monitor_task: asyncio.Task | None = None

    @property
    def is_using_fallback(self) -> bool:
        """True when the simulator is active due to API rate limiting."""
        return self._using_fallback

    @property
    def _active(self) -> MarketDataProvider:
        return self._fallback if self._using_fallback else self._primary

    async def start(self) -> None:
        if self._monitor_task is not None and not self._monitor_task.done():
            return
        # Simulator starts first so it is warm and has prices ready immediately
        # if a fallback is triggered soon after startup.
        await self._fallback.start()
        await self._primary.start()
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        await self._primary.stop()
        await self._fallback.stop()

    def get_price(self, ticker: str) -> StockPrice | None:
        return self._active.get_price(ticker)

    def get_all_prices(self) -> dict[str, StockPrice]:
        return self._active.get_all_prices()

    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        return self._active.get_history(ticker, limit)

    def set_tickers(self, tickers: list[str]) -> None:
        self._primary.set_tickers(tickers)
        self._fallback.set_tickers(tickers)

    async def _monitor_loop(self) -> None:
        """Periodically check whether the primary provider is rate-limited."""
        while True:
            await asyncio.sleep(MONITOR_INTERVAL)
            if not self._using_fallback and self._primary.is_rate_limited:
                self._using_fallback = True
                logger.warning(
                    "IndianAPI rate limited or quota exhausted. "
                    "Switching to simulator fallback for market data."
                )
