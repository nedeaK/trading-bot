"""Supply and demand zone detection and validation.

Implements the zone detection pipeline from the Supply-Demand Masterclass:
1. Find impulse candles (strong directional moves)
2. Find the last indecision candle before each impulse (= the zone)
3. Validate with imbalance (unfilled gap)
4. Mark extreme zones (furthest from price = highest probability)
5. Filter by trend (uptrend = demand only, downtrend = supply only)
6. First tap rule (zone invalid after first retest)
"""

from typing import List

from config.constants import TrendType, ZoneType
from data.models import Candle, Zone, zone_as_extreme
from indicators.candle_analysis import (
    calculate_avg_body_size,
    find_last_indecision_before_impulse,
    is_impulse_candle,
)
from indicators.imbalance import has_imbalance_into_zone


def _create_zone_from_candle(
    candles: List[Candle],
    zone_index: int,
    zone_type: ZoneType,
    impulse_index: int,
) -> Zone:
    """Create a Zone from the indecision candle at zone_index.

    The zone boundaries are the high and low of the indecision candle.
    If the next candle's wick extends further, extend the zone.
    """
    zone_candle = candles[zone_index]
    zone_high = zone_candle.high
    zone_low = zone_candle.low

    # Extend zone if adjacent candle wick goes further
    if zone_index + 1 < len(candles) and zone_index + 1 < impulse_index:
        next_candle = candles[zone_index + 1]
        zone_high = max(zone_high, next_candle.high)
        zone_low = min(zone_low, next_candle.low)

    imbalance = has_imbalance_into_zone(candles, zone_index, impulse_index)

    return Zone(
        zone_type=zone_type,
        high=zone_high,
        low=zone_low,
        creation_index=zone_index,
        creation_timestamp=zone_candle.timestamp,
        has_imbalance=imbalance,
    )


def detect_supply_zones(
    candles: List[Candle],
    threshold: float = 0.5,
    impulse_multiplier: float = 2.0,
) -> List[Zone]:
    """Detect supply zones: indecision candle before bearish impulse.

    Args:
        candles: List of Candle objects.
        threshold: Indecision body/range ratio threshold.
        impulse_multiplier: How large the impulse must be vs average.

    Returns:
        List of valid supply Zones (with imbalance).
    """
    if len(candles) < 3:
        return []

    avg_body = calculate_avg_body_size(candles)
    zones: List[Zone] = []

    for i in range(1, len(candles)):
        candle = candles[i]
        # Supply zone: bearish impulse (large red candle)
        if candle.is_bearish and is_impulse_candle(candle, avg_body, impulse_multiplier):
            zone_idx = find_last_indecision_before_impulse(
                candles, i, threshold=threshold,
            )
            zone = _create_zone_from_candle(candles, zone_idx, ZoneType.SUPPLY, i)
            if zone.has_imbalance:
                zones.append(zone)

    return zones


def detect_demand_zones(
    candles: List[Candle],
    threshold: float = 0.5,
    impulse_multiplier: float = 2.0,
) -> List[Zone]:
    """Detect demand zones: indecision candle before bullish impulse.

    Args:
        candles: List of Candle objects.
        threshold: Indecision body/range ratio threshold.
        impulse_multiplier: How large the impulse must be vs average.

    Returns:
        List of valid demand Zones (with imbalance).
    """
    if len(candles) < 3:
        return []

    avg_body = calculate_avg_body_size(candles)
    zones: List[Zone] = []

    for i in range(1, len(candles)):
        candle = candles[i]
        # Demand zone: bullish impulse (large green candle)
        if candle.is_bullish and is_impulse_candle(candle, avg_body, impulse_multiplier):
            zone_idx = find_last_indecision_before_impulse(
                candles, i, threshold=threshold,
            )
            zone = _create_zone_from_candle(candles, zone_idx, ZoneType.DEMAND, i)
            if zone.has_imbalance:
                zones.append(zone)

    return zones


def detect_all_zones(
    candles: List[Candle],
    threshold: float = 0.5,
    impulse_multiplier: float = 2.0,
) -> List[Zone]:
    """Detect all supply and demand zones."""
    if not candles:
        return []
    supply = detect_supply_zones(candles, threshold, impulse_multiplier)
    demand = detect_demand_zones(candles, threshold, impulse_multiplier)
    all_zones = supply + demand
    return sorted(all_zones, key=lambda z: z.creation_index)


def filter_zones_by_trend(zones: List[Zone], trend: TrendType) -> List[Zone]:
    """Filter zones by trend direction.

    From the PDFs:
    - Uptrend = trade demand zones only (buy the dip)
    - Downtrend = trade supply zones only (sell the rally)
    - Consolidation = keep all (no filter)
    """
    if trend == TrendType.BULLISH:
        return [z for z in zones if z.zone_type == ZoneType.DEMAND]
    elif trend == TrendType.BEARISH:
        return [z for z in zones if z.zone_type == ZoneType.SUPPLY]
    return list(zones)


def mark_extreme_zones(
    zones: List[Zone],
    current_price: float,
) -> List[Zone]:
    """Mark the extreme zone in each category.

    Extreme zone = the furthest imbalanced zone from current price.
    - Extreme supply = highest supply zone
    - Extreme demand = lowest demand zone

    These are the highest-probability zones per the PDF.
    """
    if not zones:
        return []

    supply_zones = [z for z in zones if z.zone_type == ZoneType.SUPPLY]
    demand_zones = [z for z in zones if z.zone_type == ZoneType.DEMAND]

    extreme_supply = None
    if supply_zones:
        extreme_supply = max(supply_zones, key=lambda z: z.high)

    extreme_demand = None
    if demand_zones:
        extreme_demand = min(demand_zones, key=lambda z: z.low)

    result: List[Zone] = []
    for z in zones:
        if z is extreme_supply or z is extreme_demand:
            result.append(zone_as_extreme(z))
        else:
            result.append(z)

    return result
