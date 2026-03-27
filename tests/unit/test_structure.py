"""Tests for market structure classification: HH/HL/LL/LH, BOS, CHoCH."""

import pytest
from datetime import datetime

from config.constants import StructureType, SwingType, TrendType
from data.models import Candle, StructurePoint, SwingPoint
from smc.structure import (
    classify_structure,
    detect_bos,
    detect_choch,
)
from smc.trend import classify_trend
from tests.fixtures.sample_data import (
    make_consolidation_candles,
    make_downtrend_candles,
    make_uptrend_candles,
)
from indicators.swing_points import detect_all_swings


def _candles_from_tuples(tuples):
    return [Candle.from_tuple(t) for t in tuples]


def _make_swing(index, price, swing_type):
    return SwingPoint(
        index=index,
        timestamp=datetime(2024, 1, 1),
        price=price,
        swing_type=swing_type,
    )


# ── Structure Classification Tests ──


class TestClassifyStructure:
    def test_uptrend_hh_hl(self):
        """Swing highs going up = HH, swing lows going up = HL."""
        swings = [
            _make_swing(0, 99, SwingType.LOW),
            _make_swing(3, 105, SwingType.HIGH),
            _make_swing(5, 101.5, SwingType.LOW),   # HL (101.5 > 99)
            _make_swing(8, 108, SwingType.HIGH),     # HH (108 > 105)
            _make_swing(10, 103.5, SwingType.LOW),   # HL (103.5 > 101.5)
            _make_swing(13, 111, SwingType.HIGH),    # HH (111 > 108)
        ]
        structure = classify_structure(swings)
        # First of each type can't be classified (no previous to compare)
        types = [sp.structure_type for sp in structure]
        assert StructureType.HH in types
        assert StructureType.HL in types
        assert StructureType.LL not in types
        assert StructureType.LH not in types

    def test_downtrend_ll_lh(self):
        """Swing lows going down = LL, swing highs going down = LH."""
        swings = [
            _make_swing(0, 111, SwingType.HIGH),
            _make_swing(3, 104, SwingType.LOW),
            _make_swing(5, 108.5, SwingType.HIGH),   # LH (108.5 < 111)
            _make_swing(8, 100, SwingType.LOW),       # LL (100 < 104)
            _make_swing(10, 106, SwingType.HIGH),     # LH (106 < 108.5)
            _make_swing(13, 96, SwingType.LOW),       # LL (96 < 100)
        ]
        structure = classify_structure(swings)
        types = [sp.structure_type for sp in structure]
        assert StructureType.LL in types
        assert StructureType.LH in types
        assert StructureType.HH not in types
        assert StructureType.HL not in types

    def test_first_pair_unclassified(self):
        """The first swing high and first swing low have no predecessor."""
        swings = [
            _make_swing(0, 99, SwingType.LOW),
            _make_swing(3, 105, SwingType.HIGH),
        ]
        structure = classify_structure(swings)
        assert len(structure) == 0  # No comparisons possible

    def test_empty_swings(self):
        structure = classify_structure([])
        assert structure == []

    def test_single_swing(self):
        swings = [_make_swing(0, 100, SwingType.HIGH)]
        structure = classify_structure(swings)
        assert structure == []

    def test_mixed_structure(self):
        """Trend shift: uptrend then reversal."""
        swings = [
            _make_swing(0, 99, SwingType.LOW),
            _make_swing(2, 105, SwingType.HIGH),
            _make_swing(4, 101, SwingType.LOW),   # HL
            _make_swing(6, 108, SwingType.HIGH),  # HH
            _make_swing(8, 103, SwingType.LOW),   # HL
            _make_swing(10, 106, SwingType.HIGH), # LH (106 < 108) - shift!
            _make_swing(12, 100, SwingType.LOW),  # LL (100 < 103) - confirmed
        ]
        structure = classify_structure(swings)
        types = [sp.structure_type for sp in structure]
        assert StructureType.HH in types
        assert StructureType.HL in types
        assert StructureType.LH in types
        assert StructureType.LL in types


# ── BOS (Break of Structure) Tests ──


class TestDetectBOS:
    def test_bullish_bos(self):
        """BOS occurs when price breaks past previous HH."""
        swings = [
            _make_swing(0, 99, SwingType.LOW),
            _make_swing(3, 105, SwingType.HIGH),
            _make_swing(5, 101, SwingType.LOW),
            _make_swing(8, 108, SwingType.HIGH),  # HH - breaks past 105
        ]
        structure = classify_structure(swings)
        bos_events = detect_bos(structure)
        assert len(bos_events) > 0
        # BOS should reference the HH that broke past previous high
        bos_types = [b.structure_type for b in bos_events]
        assert StructureType.HH in bos_types

    def test_bearish_bos(self):
        """BOS occurs when price breaks past previous LL."""
        swings = [
            _make_swing(0, 111, SwingType.HIGH),
            _make_swing(3, 104, SwingType.LOW),
            _make_swing(5, 108, SwingType.HIGH),
            _make_swing(8, 100, SwingType.LOW),  # LL - breaks past 104
        ]
        structure = classify_structure(swings)
        bos_events = detect_bos(structure)
        assert len(bos_events) > 0
        bos_types = [b.structure_type for b in bos_events]
        assert StructureType.LL in bos_types

    def test_no_bos_in_consolidation(self):
        """No BOS when structure doesn't trend."""
        swings = [
            _make_swing(0, 100, SwingType.LOW),
            _make_swing(2, 105, SwingType.HIGH),
            _make_swing(4, 101, SwingType.LOW),   # HL
            _make_swing(6, 104, SwingType.HIGH),  # LH
        ]
        structure = classify_structure(swings)
        bos_events = detect_bos(structure)
        assert len(bos_events) == 0

    def test_empty_structure(self):
        assert detect_bos([]) == []


# ── CHoCH (Change of Character) Tests ──


class TestDetectCHoCH:
    def test_bearish_choch(self):
        """CHoCH: uptrend breaks a HL = shift bearish.

        After making HH/HL, the next low goes below the previous HL.
        """
        swings = [
            _make_swing(0, 99, SwingType.LOW),
            _make_swing(3, 105, SwingType.HIGH),
            _make_swing(5, 101, SwingType.LOW),   # HL
            _make_swing(8, 108, SwingType.HIGH),  # HH
            _make_swing(10, 103, SwingType.LOW),  # HL
            _make_swing(12, 106, SwingType.HIGH), # LH - first sign
            _make_swing(14, 100, SwingType.LOW),  # LL - CHoCH: broke below HL of 103
        ]
        structure = classify_structure(swings)
        choch_events = detect_choch(structure)
        assert len(choch_events) > 0
        # The CHoCH is the LL that broke the HL
        assert any(c.structure_type == StructureType.LL for c in choch_events)

    def test_bullish_choch(self):
        """CHoCH: downtrend breaks a LH = shift bullish.

        After making LL/LH, the next high goes above the previous LH.
        """
        swings = [
            _make_swing(0, 111, SwingType.HIGH),
            _make_swing(3, 104, SwingType.LOW),
            _make_swing(5, 108, SwingType.HIGH),  # LH
            _make_swing(8, 100, SwingType.LOW),   # LL
            _make_swing(10, 106, SwingType.HIGH), # LH
            _make_swing(12, 98, SwingType.LOW),   # LL
            _make_swing(14, 110, SwingType.HIGH), # HH - CHoCH: broke above LH of 106
        ]
        structure = classify_structure(swings)
        choch_events = detect_choch(structure)
        assert len(choch_events) > 0
        assert any(c.structure_type == StructureType.HH for c in choch_events)

    def test_no_choch_in_clean_trend(self):
        """No CHoCH if trend continues cleanly."""
        swings = [
            _make_swing(0, 99, SwingType.LOW),
            _make_swing(3, 105, SwingType.HIGH),
            _make_swing(5, 101, SwingType.LOW),   # HL
            _make_swing(8, 108, SwingType.HIGH),  # HH
            _make_swing(10, 103, SwingType.LOW),  # HL
            _make_swing(13, 111, SwingType.HIGH), # HH
        ]
        structure = classify_structure(swings)
        choch_events = detect_choch(structure)
        assert len(choch_events) == 0

    def test_empty_structure(self):
        assert detect_choch([]) == []


# ── Trend Classification Tests ──


class TestClassifyTrend:
    def test_bullish_trend(self):
        """HH + HL = BULLISH."""
        swings = [
            _make_swing(0, 99, SwingType.LOW),
            _make_swing(3, 105, SwingType.HIGH),
            _make_swing(5, 101, SwingType.LOW),   # HL
            _make_swing(8, 108, SwingType.HIGH),  # HH
            _make_swing(10, 103, SwingType.LOW),  # HL
            _make_swing(13, 111, SwingType.HIGH), # HH
        ]
        structure = classify_structure(swings)
        trend = classify_trend(structure)
        assert trend == TrendType.BULLISH

    def test_bearish_trend(self):
        """LL + LH = BEARISH."""
        swings = [
            _make_swing(0, 111, SwingType.HIGH),
            _make_swing(3, 104, SwingType.LOW),
            _make_swing(5, 108, SwingType.HIGH),  # LH
            _make_swing(8, 100, SwingType.LOW),   # LL
            _make_swing(10, 106, SwingType.HIGH), # LH
            _make_swing(13, 96, SwingType.LOW),   # LL
        ]
        structure = classify_structure(swings)
        trend = classify_trend(structure)
        assert trend == TrendType.BEARISH

    def test_consolidation(self):
        """Mixed HH/HL and LL/LH = CONSOLIDATION."""
        swings = [
            _make_swing(0, 100, SwingType.LOW),
            _make_swing(2, 105, SwingType.HIGH),
            _make_swing(4, 101, SwingType.LOW),   # HL
            _make_swing(6, 104, SwingType.HIGH),  # LH
            _make_swing(8, 99, SwingType.LOW),    # LL
            _make_swing(10, 106, SwingType.HIGH), # HH
        ]
        structure = classify_structure(swings)
        trend = classify_trend(structure)
        assert trend == TrendType.CONSOLIDATION

    def test_empty_structure_is_consolidation(self):
        assert classify_trend([]) == TrendType.CONSOLIDATION

    def test_with_real_uptrend_data(self):
        """Integration: detect swings from synthetic uptrend then classify."""
        candles = _candles_from_tuples(make_uptrend_candles())
        swings = detect_all_swings(candles, window=2)
        structure = classify_structure(swings)
        trend = classify_trend(structure)
        assert trend == TrendType.BULLISH

    def test_with_real_downtrend_data(self):
        """Integration: detect swings from synthetic downtrend then classify."""
        candles = _candles_from_tuples(make_downtrend_candles())
        swings = detect_all_swings(candles, window=2)
        structure = classify_structure(swings)
        trend = classify_trend(structure)
        assert trend == TrendType.BEARISH

    def test_trend_lookback(self):
        """Only consider recent structure points for trend."""
        # Old bearish structure followed by bullish structure
        swings = [
            _make_swing(0, 111, SwingType.HIGH),
            _make_swing(3, 104, SwingType.LOW),
            _make_swing(5, 108, SwingType.HIGH),  # LH
            _make_swing(8, 100, SwingType.LOW),   # LL
            # shift
            _make_swing(10, 105, SwingType.HIGH), # LH still
            _make_swing(12, 102, SwingType.LOW),  # HL (102 > 100)
            _make_swing(14, 110, SwingType.HIGH), # HH (110 > 105)
            _make_swing(16, 106, SwingType.LOW),  # HL (106 > 102)
            _make_swing(18, 115, SwingType.HIGH), # HH (115 > 110)
        ]
        structure = classify_structure(swings)
        # With lookback=4 should be bullish (recent structure)
        trend = classify_trend(structure, lookback=4)
        assert trend == TrendType.BULLISH
