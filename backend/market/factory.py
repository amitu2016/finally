import os

from .base import MarketDataProvider
from .fallback import FallbackProvider
from .simulator import SimulatorProvider


def create_market_provider() -> MarketDataProvider:
    """
    Select the market data provider based on environment variables.

    INDIAN_STOCK_API_KEY set → FallbackProvider (IndianAPIProvider with automatic
                               simulator fallback on rate-limit/quota exhaustion)
    INDIAN_STOCK_API_KEY absent → SimulatorProvider (GBM-based mock)
    """
    api_key = os.getenv("INDIAN_STOCK_API_KEY")
    if api_key:
        return FallbackProvider(api_key)
    return SimulatorProvider()
