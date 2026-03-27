"""LTF confirmation entry logic (optional refinement).

Instead of a limit order at the zone, wait for a LTF structure shift:
- At a supply zone, wait for LTF to shift from HH/HL into LL
- Then sell from the LTF supply zone formed during that shift
- Safer but may miss fast moves from extreme zones
"""

from typing import List, Optional

from config.constants import StructureType, TrendType, ZoneType
from data.models import Candle, Signal, Zone
from indicators.swing_points import detect_all_swings
from smc.structure import classify_structure, detect_choch
from smc.trend import classify_trend
from smc.zones import detect_all_zones
from smc.top_down import create_order
from data.models import Narrative


def confirm_entry_with_ltf_shift(
    ltf_candles: List[Candle],
    entry_zone: Zone,
    narrative: Narrative,
    swing_window: int = 2,
) -> Optional[Signal]:
    """Wait for LTF structure shift at the zone before entering.

    At a supply zone: look for LTF to shift bearish (CHoCH from
    bullish to bearish). At a demand zone: look for LTF to shift
    bullish.

    Args:
        ltf_candles: Lower timeframe candles near the zone.
        entry_zone: The zone we're watching for confirmation.
        narrative: HTF narrative for target calculation.
        swing_window: Window for LTF swing detection.

    Returns:
        Signal if confirmed, None if no confirmation yet.
    """
    if not ltf_candles:
        return None

    swings = detect_all_swings(ltf_candles, window=swing_window)
    structure = classify_structure(swings)

    if not structure:
        return None

    choch_events = detect_choch(structure)

    if entry_zone.zone_type == ZoneType.SUPPLY:
        # Need bearish CHoCH (LL appearing after bullish structure)
        bearish_shift = any(
            c.structure_type == StructureType.LL for c in choch_events
        )
        if not bearish_shift:
            return None

        # Find the LTF supply zone formed during the shift
        ltf_zones = detect_all_zones(ltf_candles)
        ltf_supply = [z for z in ltf_zones if z.zone_type == ZoneType.SUPPLY and z.is_valid]
        if not ltf_supply:
            return None

        # Use the most recent LTF supply zone
        refined_zone = max(ltf_supply, key=lambda z: z.creation_index)
        return create_order(refined_zone, narrative)

    elif entry_zone.zone_type == ZoneType.DEMAND:
        # Need bullish CHoCH (HH appearing after bearish structure)
        bullish_shift = any(
            c.structure_type == StructureType.HH for c in choch_events
        )
        if not bullish_shift:
            return None

        ltf_zones = detect_all_zones(ltf_candles)
        ltf_demand = [z for z in ltf_zones if z.zone_type == ZoneType.DEMAND and z.is_valid]
        if not ltf_demand:
            return None

        refined_zone = max(ltf_demand, key=lambda z: z.creation_index)
        return create_order(refined_zone, narrative)

    return None
