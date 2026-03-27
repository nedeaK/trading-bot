"""Trend classification from market structure.

Determines if the market is BULLISH, BEARISH, or in CONSOLIDATION
based on the pattern of HH/HL/LL/LH structure points.
"""

from typing import List

from config.constants import StructureType, TrendType
from data.models import StructurePoint


def classify_trend(
    structure: List[StructurePoint],
    lookback: int = 0,
) -> TrendType:
    """Classify the current trend from structure points.

    Rules (from the PDFs):
    - Uptrend (HH + HL) = BULLISH
    - Downtrend (LL + LH) = BEARISH
    - Mixed or insufficient data = CONSOLIDATION

    Args:
        structure: List of classified StructurePoints.
        lookback: If > 0, only consider the last N structure points.
                  If 0, consider all points.

    Returns:
        TrendType indicating current market trend.
    """
    if not structure:
        return TrendType.CONSOLIDATION

    points = structure[-lookback:] if lookback > 0 else structure

    if not points:
        return TrendType.CONSOLIDATION

    types = [sp.structure_type for sp in points]

    bullish_count = sum(
        1 for t in types if t in (StructureType.HH, StructureType.HL)
    )
    bearish_count = sum(
        1 for t in types if t in (StructureType.LL, StructureType.LH)
    )

    total = len(types)
    if total == 0:
        return TrendType.CONSOLIDATION

    bullish_ratio = bullish_count / total
    bearish_ratio = bearish_count / total

    # Need a clear majority (>60%) for a trending classification
    if bullish_ratio > 0.6:
        return TrendType.BULLISH
    elif bearish_ratio > 0.6:
        return TrendType.BEARISH
    else:
        return TrendType.CONSOLIDATION
