"""Swing high and swing low detection.

A swing high is a candle whose high is the highest within `window`
candles on either side. A swing low is the opposite.
"""

from typing import List

from config.constants import SwingType
from data.models import Candle, SwingPoint


def detect_swing_highs(candles: List[Candle], window: int = 5) -> List[SwingPoint]:
    """Find swing highs in candle data.

    A swing high at index i means candles[i].high is the maximum
    high in the range [i - window, i + window].

    Args:
        candles: List of Candle objects.
        window: Number of candles on each side to compare.

    Returns:
        List of SwingPoint objects for detected swing highs.
    """
    if len(candles) < (2 * window + 1):
        return []

    swing_highs = []
    for i in range(window, len(candles) - window):
        current_high = candles[i].high
        is_highest = True
        for j in range(i - window, i + window + 1):
            if j == i:
                continue
            if candles[j].high >= current_high:
                is_highest = False
                break
        if is_highest:
            swing_highs.append(SwingPoint(
                index=i,
                timestamp=candles[i].timestamp,
                price=current_high,
                swing_type=SwingType.HIGH,
            ))

    return swing_highs


def detect_swing_lows(candles: List[Candle], window: int = 5) -> List[SwingPoint]:
    """Find swing lows in candle data.

    A swing low at index i means candles[i].low is the minimum
    low in the range [i - window, i + window].
    """
    if len(candles) < (2 * window + 1):
        return []

    swing_lows = []
    for i in range(window, len(candles) - window):
        current_low = candles[i].low
        is_lowest = True
        for j in range(i - window, i + window + 1):
            if j == i:
                continue
            if candles[j].low <= current_low:
                is_lowest = False
                break
        if is_lowest:
            swing_lows.append(SwingPoint(
                index=i,
                timestamp=candles[i].timestamp,
                price=current_low,
                swing_type=SwingType.LOW,
            ))

    return swing_lows


def detect_all_swings(candles: List[Candle], window: int = 5) -> List[SwingPoint]:
    """Detect all swing highs and lows, sorted by index."""
    highs = detect_swing_highs(candles, window)
    lows = detect_swing_lows(candles, window)
    all_swings = highs + lows
    return sorted(all_swings, key=lambda s: s.index)
