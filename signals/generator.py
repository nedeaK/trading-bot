"""Signal generation pipeline - orchestrates the sequential trading flow.

This is the main entry point that chains together all 6 steps of the
SMC trading flow. Each step must succeed for a signal to be generated.
If any step returns None, the flow halts (no trade).
"""

from typing import List, Optional

from config.settings import SMCConfig
from data.models import Candle, Signal
from smc.top_down import (
    check_mtf_trend,
    create_order,
    detect_sweep,
    find_entry_zone,
    read_htf_narrative,
    scan_for_liquidity,
)


def generate_signals(
    htf_candles: List[Candle],
    mtf_candles: List[Candle],
    ltf_candles: List[Candle],
    config: Optional[SMCConfig] = None,
) -> List[Signal]:
    """Run the complete SMC trading flow and generate signals.

    Sequential flow (each step must succeed):
    1. Read HTF narrative (bias + major zones)
    2. Check MTF trend alignment
    3. Scan for liquidity building
    4. Detect sweep of liquidity
    5. Find entry zone at sweep
    6. Create order signal

    Args:
        htf_candles: Higher timeframe candles (weekly/daily).
        mtf_candles: Medium timeframe candles (4H/1H).
        ltf_candles: Lower timeframe candles (15m/5m) for entry.
        config: SMC detection parameters.

    Returns:
        List of Signal objects (0 or 1 signals typically).
    """
    if config is None:
        config = SMCConfig()

    # Step 1: HTF Narrative
    narrative = read_htf_narrative(htf_candles, swing_window=config.swing_window)

    # Step 2: MTF Trend
    trend_context = check_mtf_trend(
        mtf_candles, narrative, swing_window=config.swing_window,
    )
    if trend_context is None:
        return []  # Wait - MTF doesn't agree

    # Step 3: Scan for Liquidity
    liquidity_setup = scan_for_liquidity(
        mtf_candles,
        trend_context,
        swing_window=max(1, config.swing_window // 2),
        tolerance=config.liquidity_tolerance,
    )
    if liquidity_setup is None:
        return []  # Wait - no liquidity building

    # Step 4: Detect Sweep
    sweep = detect_sweep(ltf_candles, liquidity_setup)
    if sweep is None:
        return []  # Wait - no sweep happened

    # Step 5: Find Entry Zone
    zone = find_entry_zone(ltf_candles, sweep)
    if zone is None:
        return []  # Wait - no valid zone at sweep

    # Step 6: Create Order
    signal = create_order(zone, narrative)

    return [signal]
