"""Liquidity detection: equal highs/lows, pools, and sweeps.

Equal highs/lows are areas where stop losses and breakout orders
cluster. When price sweeps through these levels, it grabs liquidity
then reverses - this is the entry trigger in the SMC flow.
"""

from typing import List, Optional

from config.constants import LiquidityType, SwingType
from data.models import Candle, LiquidityPool, SwingPoint, SweepEvent


def find_equal_highs(
    swings: List[SwingPoint],
    tolerance: float = 0.001,
) -> List[LiquidityPool]:
    """Find clusters of swing highs at similar prices.

    Equal highs indicate a liquidity pool above (stop losses from
    shorts and breakout orders from longs cluster there).

    Args:
        swings: List of swing points.
        tolerance: Maximum relative price difference to consider equal.
            0.001 = within 0.1% of each other.

    Returns:
        List of LiquidityPool objects for detected equal highs.
    """
    highs = [s for s in swings if s.swing_type == SwingType.HIGH]
    return _cluster_swings(highs, LiquidityType.EQUAL_HIGHS, tolerance)


def find_equal_lows(
    swings: List[SwingPoint],
    tolerance: float = 0.001,
) -> List[LiquidityPool]:
    """Find clusters of swing lows at similar prices.

    Equal lows indicate a liquidity pool below (stop losses from
    longs and breakout orders from shorts cluster there).
    """
    lows = [s for s in swings if s.swing_type == SwingType.LOW]
    return _cluster_swings(lows, LiquidityType.EQUAL_LOWS, tolerance)


def _cluster_swings(
    swings: List[SwingPoint],
    pool_type: LiquidityType,
    tolerance: float,
) -> List[LiquidityPool]:
    """Group swings at similar price levels into liquidity pools."""
    if len(swings) < 2:
        return []

    # Sort by price for clustering
    sorted_swings = sorted(swings, key=lambda s: s.price)
    pools: List[LiquidityPool] = []
    used = set()

    for i, base in enumerate(sorted_swings):
        if i in used:
            continue

        cluster = [base]
        cluster_indices = {i}

        for j in range(i + 1, len(sorted_swings)):
            if j in used:
                continue
            candidate = sorted_swings[j]
            # Check if within tolerance of the base price
            if base.price == 0:
                continue
            if abs(candidate.price - base.price) / base.price <= tolerance:
                cluster.append(candidate)
                cluster_indices.add(j)

        if len(cluster) >= 2:
            avg_price = sum(s.price for s in cluster) / len(cluster)
            indices = tuple(s.index for s in cluster)
            pools.append(LiquidityPool(
                pool_type=pool_type,
                price=avg_price,
                swing_indices=indices,
            ))
            used.update(cluster_indices)

    return pools


def detect_liquidity_sweep(
    candles: List[Candle],
    pool: LiquidityPool,
) -> Optional[SweepEvent]:
    """Detect if price has swept through a liquidity pool.

    A sweep occurs when a candle's wick goes through the pool level
    but the body (close) is on the other side - indicating a false
    breakout / stop hunt.

    For equal highs: wick above pool price, close below = sweep.
    For equal lows: wick below pool price, close above = sweep.

    Args:
        candles: List of candles to scan.
        pool: The liquidity pool to check for sweep.

    Returns:
        SweepEvent if sweep detected, None otherwise.
    """
    if not candles:
        return None

    for i, candle in enumerate(candles):
        if pool.pool_type == LiquidityType.EQUAL_HIGHS:
            # Wick above pool price, close below
            if candle.high > pool.price and candle.close < pool.price:
                return SweepEvent(
                    sweep_index=i,
                    sweep_price=candle.high,
                    pool=pool,
                    sweep_candle_timestamp=candle.timestamp,
                )

        elif pool.pool_type == LiquidityType.EQUAL_LOWS:
            # Wick below pool price, close above
            if candle.low < pool.price and candle.close > pool.price:
                return SweepEvent(
                    sweep_index=i,
                    sweep_price=candle.low,
                    pool=pool,
                    sweep_candle_timestamp=candle.timestamp,
                )

    return None
