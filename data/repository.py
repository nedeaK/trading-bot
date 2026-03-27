"""Abstract market data repository interface.

Broker-agnostic interface so data sources can be swapped
without touching strategy code.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from config.constants import Timeframe
from data.models import Candle


class MarketDataRepository(ABC):
    """Abstract interface for fetching market data."""

    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Candle]:
        """Fetch historical OHLCV data for a symbol.

        Args:
            symbol: Ticker symbol (e.g., "SPY", "AAPL").
            timeframe: Candle timeframe.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            List of Candle objects sorted by timestamp ascending.
        """

    @abstractmethod
    def get_available_timeframes(self) -> List[Timeframe]:
        """Return the timeframes supported by this data source."""
