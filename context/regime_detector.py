"""Market regime and volatility state detection.

Computes trend regime (trending / ranging / transitioning) and
volatility state (calm / normal / elevated / crisis) from raw candle data.
No external API calls — everything derives from OHLCV.
"""

from typing import List, Tuple
import math

from data.models import Candle


def compute_atr(candles: List[Candle], period: int = 14) -> float:
    """Compute Average True Range over the last `period` candles."""
    if len(candles) < 2:
        return 0.0
    trs: List[float] = []
    for i in range(1, len(candles)):
        prev_close = candles[i - 1].close
        c = candles[i]
        tr = max(
            c.high - c.low,
            abs(c.high - prev_close),
            abs(c.low - prev_close),
        )
        trs.append(tr)
    tail = trs[-period:]
    return sum(tail) / len(tail) if tail else 0.0


def compute_atr_series(candles: List[Candle], period: int = 14) -> List[float]:
    """Return rolling ATR values (one per candle from index period onwards)."""
    if len(candles) < period + 1:
        return []
    trs: List[float] = []
    for i in range(1, len(candles)):
        prev_close = candles[i - 1].close
        c = candles[i]
        tr = max(
            c.high - c.low,
            abs(c.high - prev_close),
            abs(c.low - prev_close),
        )
        trs.append(tr)
    # Simple rolling mean
    atrs: List[float] = []
    for i in range(period - 1, len(trs)):
        atrs.append(sum(trs[i - period + 1: i + 1]) / period)
    return atrs


def compute_ema(candles: List[Candle], period: int) -> float:
    """Compute EMA of closes for `period` candles."""
    if not candles:
        return 0.0
    closes = [c.close for c in candles]
    k = 2.0 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = price * k + ema * (1 - k)
    return ema


def compute_sma(candles: List[Candle], period: int) -> float:
    """Compute simple moving average of closes."""
    if not candles:
        return 0.0
    tail = [c.close for c in candles[-period:]]
    return sum(tail) / len(tail) if tail else 0.0


def detect_volatility_state(candles: List[Candle], lookback: int = 252) -> Tuple[str, float]:
    """Classify current volatility as CALM / NORMAL / ELEVATED / CRISIS.

    Uses ATR percentile relative to the trailing `lookback` sessions.

    Returns:
        (volatility_state, atr_percentile)
    """
    atr_series = compute_atr_series(candles, period=14)
    if not atr_series:
        return "NORMAL", 50.0

    current_atr = atr_series[-1]
    historical = atr_series[-lookback:] if len(atr_series) >= lookback else atr_series
    sorted_atrs = sorted(historical)
    rank = sum(1 for v in sorted_atrs if v <= current_atr)
    percentile = rank / len(sorted_atrs) * 100

    if percentile < 25:
        state = "CALM"
    elif percentile < 60:
        state = "NORMAL"
    elif percentile < 85:
        state = "ELEVATED"
    else:
        state = "CRISIS"

    return state, round(percentile, 1)


def detect_regime(candles: List[Candle]) -> str:
    """Classify market regime as TRENDING / RANGING / TRANSITIONING.

    Uses the relationship between short and long EMAs and recent price
    structure to decide whether the market is directionally moving or
    oscillating within a range.
    """
    if len(candles) < 50:
        return "RANGING"

    ema20 = compute_ema(candles, 20)
    ema50 = compute_ema(candles, 50)
    current = candles[-1].close

    ema_spread_pct = abs(ema20 - ema50) / ema50 * 100 if ema50 else 0

    # Check 20-candle directional consistency
    recent = candles[-20:]
    highs = [c.high for c in recent]
    lows = [c.low for c in recent]
    high_range = max(highs) - min(highs)
    low_range = max(lows) - min(lows)
    price_range = max(highs) - min(lows)
    choppiness = (high_range + low_range) / (2 * price_range) if price_range else 1.0

    if ema_spread_pct > 1.5 and choppiness < 0.8:
        return "TRENDING"
    elif ema_spread_pct < 0.5 or choppiness > 0.9:
        return "RANGING"
    return "TRANSITIONING"


def detect_trend_from_candles(candles: List[Candle], period: int = 20) -> Tuple[str, float]:
    """Simple trend classification: BULLISH / BEARISH / NEUTRAL.

    Returns (trend, pct_vs_ma) — percent above or below the `period`-day MA.
    """
    if not candles or len(candles) < period:
        return "NEUTRAL", 0.0
    ma = compute_sma(candles, period)
    price = candles[-1].close
    pct_vs_ma = (price - ma) / ma * 100 if ma else 0.0

    if pct_vs_ma > 1.0:
        trend = "BULLISH"
    elif pct_vs_ma < -1.0:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    return trend, round(pct_vs_ma, 2)
