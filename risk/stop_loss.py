"""Stop loss calculation.

Stop loss is placed above/below the zone with a buffer.
"""

from config.constants import ZoneType
from data.models import Zone


def calculate_stop_loss(zone: Zone, buffer: float = 0.001) -> float:
    """Calculate stop loss price for a zone.

    Supply zone: stop above the zone high.
    Demand zone: stop below the zone low.

    Args:
        zone: The entry zone.
        buffer: Buffer beyond zone as a percentage (0.001 = 0.1%).

    Returns:
        Stop loss price.
    """
    if zone.zone_type == ZoneType.SUPPLY:
        return zone.high * (1 + buffer)
    else:  # DEMAND
        return zone.low * (1 - buffer)
