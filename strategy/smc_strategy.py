"""Main SMC Strategy class - clean interface wrapping the full pipeline.

This is the top-level API that combines:
- Multi-timeframe data fetching
- Top-down analysis (HTF narrative -> MTF trend -> liquidity -> sweep -> zone)
- Signal generation
- Position sizing
"""

from typing import Dict, List, Optional

from config.settings import Config
from data.models import Candle, Signal
from data.repository import MarketDataRepository
from signals.generator import generate_signals


class SMCStrategy:
    """Smart Money Concepts trading strategy.

    Follows the exact sequential flow from the videos:
    1. HTF Narrative (Weekly/Daily)
    2. MTF Trend confirmation (4H/1H)
    3. Spot liquidity building (equal highs/lows)
    4. Wait for sweep
    5. Find zone at sweep
    6. Place order
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def analyze(
        self,
        htf_candles: List[Candle],
        mtf_candles: List[Candle],
        ltf_candles: List[Candle],
    ) -> List[Signal]:
        """Run the full analysis pipeline and return signals.

        Args:
            htf_candles: Higher timeframe candles.
            mtf_candles: Medium timeframe candles.
            ltf_candles: Lower timeframe candles.

        Returns:
            List of trade signals (typically 0 or 1).
        """
        return generate_signals(
            htf_candles, mtf_candles, ltf_candles,
            config=self.config.smc,
        )

    def analyze_from_repository(
        self,
        repository: MarketDataRepository,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> List[Signal]:
        """Fetch data from repository and run analysis.

        Args:
            repository: Data source.
            symbol: Ticker symbol.
            start_date: Start date string.
            end_date: End date string.

        Returns:
            List of trade signals.
        """
        tf = self.config.timeframes

        htf_candles = repository.get_historical_data(
            symbol, tf.htf, start_date, end_date,
        )
        mtf_candles = repository.get_historical_data(
            symbol, tf.mtf, start_date, end_date,
        )
        ltf_candles = repository.get_historical_data(
            symbol, tf.ltf, start_date, end_date,
        )

        return self.analyze(htf_candles, mtf_candles, ltf_candles)
