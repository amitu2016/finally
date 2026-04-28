from abc import ABC, abstractmethod

from .types import StockPrice


class MarketDataProvider(ABC):

    @abstractmethod
    async def start(self) -> None:
        """Start the background polling/simulation loop."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the background loop."""

    @abstractmethod
    def get_price(self, ticker: str) -> StockPrice | None:
        """Return the latest cached price, or None if not yet available."""

    @abstractmethod
    def get_all_prices(self) -> dict[str, StockPrice]:
        """Return a snapshot of the latest cached price for every tracked ticker."""

    @abstractmethod
    def get_history(self, ticker: str, limit: int = 200) -> list[StockPrice]:
        """Return the rolling price history for a ticker (oldest first, newest last)."""

    @abstractmethod
    def set_tickers(self, tickers: list[str]) -> None:
        """
        Replace the full set of tracked tickers.
        Called at startup and whenever the watchlist changes.
        Safe to call from a synchronous context.
        """
