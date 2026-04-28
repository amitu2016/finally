import os

from .base import MarketDataProvider
from .indian_api import IndianAPIProvider
from .simulator import SimulatorProvider


def create_market_provider() -> MarketDataProvider:
    """
    Select the market data provider based on environment variables.

    INDIAN_STOCK_API_KEY set → IndianAPIProvider (real NSE/BSE data)
    INDIAN_STOCK_API_KEY absent → SimulatorProvider (GBM-based mock)
    """
    api_key = os.getenv("INDIAN_STOCK_API_KEY")
    if api_key:
        return IndianAPIProvider(api_key)
    return SimulatorProvider()
