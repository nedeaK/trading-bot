"""Market structure classification: HH/HL/LL/LH, BOS, CHoCH.

Classifies swing points into market structure by comparing each swing
to the previous swing of the same type (high vs high, low vs low).

BOS (Break of Structure): Price pushes past previous HH (bullish) or LL (bearish).
CHoCH (Change of Character): Trend shift - breaks HL in uptrend or LH in downtrend.
"""

from typing import List

from config.constants import StructureType, SwingType
from data.models import StructurePoint, SwingPoint


def classify_structure(swings: List[SwingPoint]) -> List[StructurePoint]:
    """Classify each swing as HH, HL, LL, or LH.

    Compares each swing to the most recent swing of the same type:
    - High > prev high = HH, High < prev high = LH
    - Low > prev low = HL, Low < prev low = LL

    The first swing high and first swing low cannot be classified
    (no predecessor to compare against).

    Args:
        swings: List of SwingPoint objects, sorted by index.

    Returns:
        List of StructurePoint objects (excludes first high and first low).
    """
    if len(swings) < 2:
        return []

    structure_points: List[StructurePoint] = []
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None

    for swing in swings:
        if swing.swing_type == SwingType.HIGH:
            if last_high is not None:
                if swing.price > last_high.price:
                    stype = StructureType.HH
                else:
                    stype = StructureType.LH
                structure_points.append(StructurePoint(
                    swing=swing,
                    structure_type=stype,
                ))
            last_high = swing

        elif swing.swing_type == SwingType.LOW:
            if last_low is not None:
                if swing.price < last_low.price:
                    stype = StructureType.LL
                else:
                    stype = StructureType.HL
                structure_points.append(StructurePoint(
                    swing=swing,
                    structure_type=stype,
                ))
            last_low = swing

    return structure_points


def detect_bos(structure: List[StructurePoint]) -> List[StructurePoint]:
    """Detect Break of Structure events.

    BOS = trend continuation:
    - Bullish BOS: HH (price breaks past previous high)
    - Bearish BOS: LL (price breaks past previous low)

    Returns the StructurePoints where BOS occurred.
    """
    if not structure:
        return []

    bos_events: List[StructurePoint] = []

    for i, sp in enumerate(structure):
        if sp.structure_type == StructureType.HH:
            # Check there's a preceding HL to confirm trend
            preceding_types = [s.structure_type for s in structure[:i]]
            if StructureType.HL in preceding_types:
                bos_events.append(sp)

        elif sp.structure_type == StructureType.LL:
            # Check there's a preceding LH to confirm trend
            preceding_types = [s.structure_type for s in structure[:i]]
            if StructureType.LH in preceding_types:
                bos_events.append(sp)

    return bos_events


def detect_choch(structure: List[StructurePoint]) -> List[StructurePoint]:
    """Detect Change of Character events.

    CHoCH = trend reversal:
    - Bearish CHoCH: After HH/HL pattern, a LL appears (broke the HL)
    - Bullish CHoCH: After LL/LH pattern, a HH appears (broke the LH)

    Returns the StructurePoints where CHoCH occurred.
    """
    if not structure:
        return []

    choch_events: List[StructurePoint] = []

    # Track what the recent trend was
    for i, sp in enumerate(structure):
        preceding = structure[:i]
        if not preceding:
            continue

        if sp.structure_type == StructureType.LL:
            # Check if preceding context was bullish (had HH or HL)
            recent_types = [s.structure_type for s in preceding]
            had_bullish = (
                StructureType.HH in recent_types or StructureType.HL in recent_types
            )
            # And no LL before this (first LL after bullish = CHoCH)
            had_prior_ll = StructureType.LL in recent_types
            if had_bullish and not had_prior_ll:
                choch_events.append(sp)

        elif sp.structure_type == StructureType.HH:
            # Check if preceding context was bearish (had LL or LH)
            recent_types = [s.structure_type for s in preceding]
            had_bearish = (
                StructureType.LL in recent_types or StructureType.LH in recent_types
            )
            # And no HH before this (first HH after bearish = CHoCH)
            had_prior_hh = StructureType.HH in recent_types
            if had_bearish and not had_prior_hh:
                choch_events.append(sp)

    return choch_events
