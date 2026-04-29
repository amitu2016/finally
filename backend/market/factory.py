import os

from .base import MarketDataProvider
from .fallback import FallbackProvider
from .simulator import SimulatorProvider
from .yahoo import YahooFinanceProvider


def create_market_provider() -> MarketDataProvider:
    """
    Select the market data provider based on environment variables.

    USE_YAHOO=true              → YahooFinanceProvider (no API key, ~15 min delay)
    INDIAN_STOCK_API_KEY set    → FallbackProvider (IndianAPI + simulator standby)
    Neither                     → SimulatorProvider (GBM-based mock)
    """
    if os.getenv("USE_YAHOO", "").lower() == "true":
        return YahooFinanceProvider()
    api_key = os.getenv("INDIAN_STOCK_API_KEY")
    if api_key:
        return FallbackProvider(api_key)
    return SimulatorProvider()
