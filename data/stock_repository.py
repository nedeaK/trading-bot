"""Stock data repository using yfinance.

Temporary implementation - can be swapped for Alpaca, IBKR, etc.
by implementing the MarketDataRepository interface.
"""

from datetime import datetime
from typing import List

import yfinance as yf

from config.constants import Timeframe
from data.models import Candle
from data.repository import MarketDataRepository


# Map our Timeframe enum to yfinance interval strings
_TIMEFRAME_MAP = {
    Timeframe.M1: "1m",
    Timeframe.M5: "5m",
    Timeframe.M15: "15m",
    Timeframe.M30: "30m",
    Timeframe.H1: "1h",
    Timeframe.H4: "1h",  # yfinance doesn't support 4h; we resample
    Timeframe.D1: "1d",
    Timeframe.W1: "1wk",
    Timeframe.MN: "1mo",
}

# yfinance limits intraday data to 60 days for <1d intervals
_INTRADAY_TIMEFRAMES = {
    Timeframe.M1, Timeframe.M5, Timeframe.M15,
    Timeframe.M30, Timeframe.H1, Timeframe.H4,
}


class StockDataRepository(MarketDataRepository):
    """Fetches stock data from Yahoo Finance via yfinance."""

    def get_historical_data(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Candle]:
        interval = _TIMEFRAME_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval=interval,
        )

        if df.empty:
            return []

        # Resample to 4H if needed
        if timeframe == Timeframe.H4:
            df = df.resample("4h").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }).dropna()

        candles = []
        for ts, row in df.iterrows():
            candle = Candle(
                timestamp=ts.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
            candles.append(candle)

        return candles

    def get_available_timeframes(self) -> List[Timeframe]:
        return list(_TIMEFRAME_MAP.keys())
