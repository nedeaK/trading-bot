"""Imbalance (Fair Value Gap) detection.

An imbalance exists when there is an unfilled price gap between
consecutive candle wicks. This validates supply/demand zones -
zones without imbalance are not tradeable.
"""

from typing import List, Optional, Tuple

from data.models import Candle


def detect_imbalance(
    candle_before: Candle,
    candle_after: Candle,
) -> Optional[Tuple[float, float]]:
    """Check for an imbalance (gap) between two candles.

    A bearish imbalance exists when candle_before's low is above
    candle_after's high (gap down).
    A bullish imbalance exists when candle_before's high is below
    candle_after's low (gap up).

    Args:
        candle_before: The earlier candle.
        candle_after: The later candle.

    Returns:
        (gap_low, gap_high) tuple if imbalance exists, None otherwise.
    """
    # Bearish imbalance: gap down
    if candle_before.low > candle_after.high:
        return (candle_after.high, candle_before.low)

    # Bullish imbalance: gap up
    if candle_after.low > candle_before.high:
        return (candle_before.high, candle_after.low)

    return None


def has_imbalance_into_zone(
    candles: List[Candle],
    zone_index: int,
    impulse_start: int,
) -> bool:
    """Check if there's an unfilled imbalance between a zone and the impulse.

    From the Supply-Demand Masterclass: a zone is only valid if there's
    an imbalance (open price range) between the zone candle and the
    impulse. If wicks have filled the gap, the zone is invalid.

    Args:
        candles: Full candle list.
        zone_index: Index of the zone (indecision) candle.
        impulse_start: Index where the impulse begins.

    Returns:
        True if imbalance exists into the zone.
    """
    if impulse_start <= zone_index or impulse_start >= len(candles):
        return False

    zone_candle = candles[zone_index]

    # Check each candle in the impulse for a gap with the zone candle
    for i in range(impulse_start, min(impulse_start + 3, len(candles))):
        gap = detect_imbalance(zone_candle, candles[i])
        if gap is not None:
            # Verify the gap hasn't been filled by intermediate candles
            gap_low, gap_high = gap
            filled = False
            for j in range(zone_index + 1, i):
                if candles[j].low <= gap_low and candles[j].high >= gap_high:
                    filled = True
                    break
            if not filled:
                return True

    return False
