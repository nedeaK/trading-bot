"""Candle pattern analysis for SMC zone detection.

Identifies indecision candles (small body, large wicks) and
impulse candles (large body, small wicks) used in supply/demand
zone detection.
"""

from typing import List

from data.models import Candle


def is_indecision_candle(candle: Candle, threshold: float = 0.5) -> bool:
    """Check if a candle shows indecision.

    An indecision candle has a small body relative to its total range,
    meaning the wicks are large compared to the body.

    Args:
        candle: The candle to analyze.
        threshold: Maximum body-to-range ratio to qualify as indecision.
            Lower = stricter (e.g., 0.3 = body must be < 30% of range).

    Returns:
        True if the candle is indecision.
    """
    if candle.total_range == 0:
        return False
    return candle.body_to_range_ratio < threshold


def is_impulse_candle(
    candle: Candle,
    avg_body_size: float,
    multiplier: float = 2.0,
) -> bool:
    """Check if a candle is an impulse (strong directional move).

    An impulse candle has a large body relative to the average,
    indicating strong buying or selling pressure.

    Args:
        candle: The candle to analyze.
        avg_body_size: Average body size of recent candles.
        multiplier: How many times the average the body must be.

    Returns:
        True if the candle is impulsive.
    """
    if avg_body_size == 0:
        return candle.body_size > 0
    return candle.body_size >= avg_body_size * multiplier


def calculate_avg_body_size(candles: List[Candle], lookback: int = 20) -> float:
    """Calculate the average body size over recent candles.

    Args:
        candles: List of candles.
        lookback: Number of recent candles to average.

    Returns:
        Average body size.
    """
    if not candles:
        return 0.0
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    total = sum(c.body_size for c in recent)
    return total / len(recent)


def find_last_indecision_before_impulse(
    candles: List[Candle],
    impulse_index: int,
    threshold: float = 0.5,
    max_lookback: int = 5,
) -> int:
    """Find the last indecision candle before an impulse move.

    This is the core rule from the Supply-Demand Masterclass:
    "Use the last candle before the impulse."

    Args:
        candles: Full candle list.
        impulse_index: Index of the impulse candle.
        threshold: Indecision threshold (body/range ratio).
        max_lookback: How far back to search.

    Returns:
        Index of the indecision candle, or impulse_index - 1 if none found.
    """
    start = max(0, impulse_index - max_lookback)
    for i in range(impulse_index - 1, start - 1, -1):
        if is_indecision_candle(candles[i], threshold):
            return i
    # Fallback: the candle immediately before the impulse
    return max(0, impulse_index - 1)
