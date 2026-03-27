"""Take profit calculation.

Target is the opposing HTF zone (range-to-range trading).
Fallback to a default R:R ratio if no opposing zone.
"""

from typing import Optional

from config.constants import ZoneType
from data.models import Zone


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    zone: Zone,
    opposing_zone: Optional[Zone] = None,
    default_rr: float = 5.0,
) -> float:
    """Calculate take profit price.

    Primary: target the opposing HTF zone (trade range-to-range).
    Fallback: use default R:R ratio from the risk.

    Args:
        entry_price: Entry price.
        stop_loss: Stop loss price.
        zone: Entry zone (determines direction).
        opposing_zone: The opposing HTF zone to target.
        default_rr: Default risk:reward ratio if no opposing zone.

    Returns:
        Take profit price.
    """
    risk = abs(entry_price - stop_loss)

    if opposing_zone is not None:
        if zone.zone_type == ZoneType.SUPPLY:
            return opposing_zone.high  # Target demand zone high
        else:
            return opposing_zone.low  # Target supply zone low

    # Fallback: default R:R
    if zone.zone_type == ZoneType.SUPPLY:
        return entry_price - (risk * default_rr)
    else:
        return entry_price + (risk * default_rr)
