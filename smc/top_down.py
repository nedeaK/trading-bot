"""Top-down multi-timeframe analysis flow.

Implements the exact sequential trading flow from the videos:

Step 1: HTF Narrative - Read weekly/daily for major S/D zones and bias
Step 2: MTF Trend - Does market structure agree with the narrative?
Step 3: Scan for Liquidity - Find equal highs/lows forming
Step 4: Wait for Sweep - Did price take out the liquidity?
Step 5: Find Entry Zone - S/D zone at the sweep with imbalance
Step 6: Create Order - Limit order with stop and target

Each step returns None to halt the flow. If any step fails, no trade.
"""

from datetime import datetime
from typing import List, Optional

from config.constants import (
    BiasDirection,
    LiquidityType,
    SignalType,
    TrendType,
    ZoneType,
)
from data.models import (
    Candle,
    LiquiditySetup,
    Narrative,
    Signal,
    SweepEvent,
    TrendContext,
    Zone,
)
from indicators.swing_points import detect_all_swings
from smc.liquidity import (
    detect_liquidity_sweep,
    find_equal_highs,
    find_equal_lows,
)
from smc.structure import classify_structure
from smc.trend import classify_trend
from smc.zones import detect_all_zones, filter_zones_by_trend, mark_extreme_zones


# ── Step 1: HTF Narrative ──


def read_htf_narrative(
    htf_candles: List[Candle],
    swing_window: int = 5,
) -> Narrative:
    """Read the HTF chart to determine directional bias.

    Identifies major supply and demand zones on the weekly/daily chart.
    If price is near demand, bias is LONG (look for buys to supply).
    If price is near supply, bias is SHORT (look for sells to demand).

    Args:
        htf_candles: Higher timeframe candles (weekly/daily).
        swing_window: Window for swing detection.

    Returns:
        Narrative with bias and identified HTF zones.
    """
    if not htf_candles:
        return Narrative(bias=BiasDirection.NEUTRAL)

    # Detect zones on HTF
    zones = detect_all_zones(htf_candles)

    if not zones:
        # Fallback: use trend to infer bias
        swings = detect_all_swings(htf_candles, window=swing_window)
        structure = classify_structure(swings)
        trend = classify_trend(structure)
        if trend == TrendType.BULLISH:
            return Narrative(bias=BiasDirection.LONG)
        elif trend == TrendType.BEARISH:
            return Narrative(bias=BiasDirection.SHORT)
        return Narrative(bias=BiasDirection.NEUTRAL)

    # Find the nearest supply and demand zones
    current_price = htf_candles[-1].close
    supply_zones = [z for z in zones if z.zone_type == ZoneType.SUPPLY]
    demand_zones = [z for z in zones if z.zone_type == ZoneType.DEMAND]

    htf_supply = None
    if supply_zones:
        htf_supply = min(supply_zones, key=lambda z: abs(z.midpoint - current_price))

    htf_demand = None
    if demand_zones:
        htf_demand = min(demand_zones, key=lambda z: abs(z.midpoint - current_price))

    # Determine bias based on proximity
    if htf_supply and htf_demand:
        dist_to_supply = abs(current_price - htf_supply.midpoint)
        dist_to_demand = abs(current_price - htf_demand.midpoint)
        if dist_to_demand < dist_to_supply:
            bias = BiasDirection.LONG  # Near demand, look for buys
        else:
            bias = BiasDirection.SHORT  # Near supply, look for sells
    elif htf_demand:
        bias = BiasDirection.LONG
    elif htf_supply:
        bias = BiasDirection.SHORT
    else:
        bias = BiasDirection.NEUTRAL

    return Narrative(
        bias=bias,
        htf_demand_zone=htf_demand,
        htf_supply_zone=htf_supply,
    )


# ── Step 2: MTF Trend ──


def check_mtf_trend(
    mtf_candles: List[Candle],
    narrative: Narrative,
    swing_window: int = 5,
) -> Optional[TrendContext]:
    """Check if MTF structure agrees with HTF narrative.

    In a buy narrative, we need HH/HL (bullish structure).
    In a sell narrative, we need LL/LH (bearish structure).
    If structure disagrees, return None (don't trade).

    Args:
        mtf_candles: Medium timeframe candles (4H/1H).
        narrative: The HTF narrative with bias.
        swing_window: Window for swing detection.

    Returns:
        TrendContext if aligned, None if misaligned or neutral.
    """
    if narrative.bias == BiasDirection.NEUTRAL:
        return None

    if not mtf_candles:
        return None

    swings = detect_all_swings(mtf_candles, window=swing_window)
    structure = classify_structure(swings)
    trend = classify_trend(structure)

    # Check alignment
    if narrative.bias == BiasDirection.LONG and trend != TrendType.BULLISH:
        return None
    if narrative.bias == BiasDirection.SHORT and trend != TrendType.BEARISH:
        return None

    return TrendContext(
        trend=trend,
        structure_points=tuple(structure),
    )


# ── Step 3: Scan for Liquidity ──


def scan_for_liquidity(
    candles: List[Candle],
    trend_context: TrendContext,
    swing_window: int = 3,
    tolerance: float = 0.003,
) -> Optional[LiquiditySetup]:
    """Find equal highs/lows forming within the trend.

    In a bearish trend, look for equal highs (liquidity above).
    In a bullish trend, look for equal lows (liquidity below).

    Args:
        candles: Candles to scan for liquidity.
        trend_context: Current trend context.
        swing_window: Window for swing detection.
        tolerance: Price tolerance for equal levels.

    Returns:
        LiquiditySetup if found, None otherwise.
    """
    swings = detect_all_swings(candles, window=swing_window)

    if trend_context.trend == TrendType.BEARISH:
        pools = find_equal_highs(swings, tolerance=tolerance)
    elif trend_context.trend == TrendType.BULLISH:
        pools = find_equal_lows(swings, tolerance=tolerance)
    else:
        return None

    if not pools:
        return None

    # Return the strongest pool (most touches)
    strongest = max(pools, key=lambda p: p.strength)
    return LiquiditySetup(pool=strongest, trend_context=trend_context)


# ── Step 4: Detect Sweep ──


def detect_sweep(
    candles: List[Candle],
    setup: LiquiditySetup,
) -> Optional[SweepEvent]:
    """Check if price has swept the liquidity pool.

    Price must take out the equal highs/lows - the market grabs
    stops and breakout orders, then reverses. If no sweep, no trade.

    Args:
        candles: Candles to scan for the sweep.
        setup: The liquidity setup to watch.

    Returns:
        SweepEvent if sweep detected, None otherwise.
    """
    return detect_liquidity_sweep(candles, setup.pool)


# ── Step 5: Find Entry Zone ──


def find_entry_zone(
    candles: List[Candle],
    sweep: SweepEvent,
) -> Optional[Zone]:
    """Find the S/D zone at or near the sweep point.

    At or near where the sweep happened, identify the supply/demand zone.
    The zone must have an imbalance. Prefer the extreme zone.

    Args:
        candles: Candles around the sweep area.
        sweep: The sweep event.

    Returns:
        The entry Zone if found, None otherwise.
    """
    if not candles:
        return None

    # Detect zones in the candle data
    zones = detect_all_zones(candles)

    if not zones:
        return None

    # Filter: only valid zones with imbalance
    valid = [z for z in zones if z.is_valid]
    if not valid:
        return None

    # For equal highs sweep -> supply zone; for equal lows sweep -> demand zone
    if sweep.pool.pool_type == LiquidityType.EQUAL_HIGHS:
        relevant = [z for z in valid if z.zone_type == ZoneType.SUPPLY]
    else:
        relevant = [z for z in valid if z.zone_type == ZoneType.DEMAND]

    if not relevant:
        # Fallback: any valid zone near the sweep
        relevant = valid

    if not relevant:
        return None

    # Mark extreme zones and prefer them
    current_price = candles[-1].close
    marked = mark_extreme_zones(relevant, current_price)
    extreme = [z for z in marked if z.is_extreme]

    if extreme:
        return extreme[0]

    # Otherwise return the zone closest to the sweep
    return min(marked, key=lambda z: abs(z.creation_index - sweep.sweep_index))


# ── Step 6: Create Order ──


def create_order(
    zone: Zone,
    narrative: Narrative,
    stop_buffer: float = 0.001,
    default_rr: float = 5.0,
) -> Signal:
    """Build a limit order signal with stop and target.

    Sell limit at supply zone, buy limit at demand zone.
    Stop loss above/below the zone.
    Target: opposing zone (range-to-range) or default R:R.

    Args:
        zone: The entry zone.
        narrative: HTF narrative with opposing zone for target.
        stop_buffer: Buffer beyond zone for stop loss (percentage).
        default_rr: Default risk:reward ratio if no opposing zone.

    Returns:
        Signal with entry, stop, and target.
    """
    zone_size = zone.size

    if zone.zone_type == ZoneType.SUPPLY:
        signal_type = SignalType.SELL
        entry_price = zone.high  # Sell at top of supply zone
        stop_loss = zone.high + (zone.high * stop_buffer)

        # Target: opposing demand zone or default R:R
        if narrative.htf_demand_zone:
            take_profit = narrative.htf_demand_zone.high
        else:
            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * default_rr)

    else:  # DEMAND
        signal_type = SignalType.BUY
        entry_price = zone.low  # Buy at bottom of demand zone
        stop_loss = zone.low - (zone.low * stop_buffer)

        # Target: opposing supply zone or default R:R
        if narrative.htf_supply_zone:
            take_profit = narrative.htf_supply_zone.low
        else:
            risk = entry_price - stop_loss
            take_profit = entry_price + (risk * default_rr)

    return Signal(
        signal_type=signal_type,
        timestamp=zone.creation_timestamp,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        zone=zone,
        narrative=narrative,
    )
