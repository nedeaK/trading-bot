"""Tests for core indicators: swing points, candle analysis, imbalance."""

import pytest
from datetime import datetime

from config.constants import SwingType
from data.models import Candle
from indicators.swing_points import (
    detect_all_swings,
    detect_swing_highs,
    detect_swing_lows,
)
from indicators.candle_analysis import (
    calculate_avg_body_size,
    find_last_indecision_before_impulse,
    is_impulse_candle,
    is_indecision_candle,
)
from indicators.imbalance import detect_imbalance, has_imbalance_into_zone
from tests.fixtures.sample_data import (
    make_downtrend_candles,
    make_supply_zone_candles,
    make_uptrend_candles,
)


def _candles_from_tuples(tuples):
    return [Candle.from_tuple(t) for t in tuples]


# ── Swing Point Tests ──


class TestSwingHighs:
    def test_detects_highs_in_uptrend(self):
        candles = _candles_from_tuples(make_uptrend_candles())
        highs = detect_swing_highs(candles, window=2)
        high_prices = [h.price for h in highs]
        # Should detect the peaks: 105, 108, 111
        assert any(abs(p - 105) < 1 for p in high_prices)
        assert any(abs(p - 108) < 1 for p in high_prices)

    def test_all_swing_types_correct(self):
        candles = _candles_from_tuples(make_uptrend_candles())
        highs = detect_swing_highs(candles, window=2)
        for h in highs:
            assert h.swing_type == SwingType.HIGH

    def test_empty_with_few_candles(self):
        candles = _candles_from_tuples(make_uptrend_candles()[:3])
        highs = detect_swing_highs(candles, window=5)
        assert highs == []

    def test_window_affects_detection(self):
        candles = _candles_from_tuples(make_uptrend_candles())
        small_window = detect_swing_highs(candles, window=1)
        large_window = detect_swing_highs(candles, window=3)
        # Smaller window = more sensitive = more swings
        assert len(small_window) >= len(large_window)


class TestSwingLows:
    def test_detects_lows_in_downtrend(self):
        candles = _candles_from_tuples(make_downtrend_candles())
        lows = detect_swing_lows(candles, window=2)
        low_prices = [l.price for l in lows]
        # Should detect the troughs: 104, 100, 96
        assert any(abs(p - 104) < 1 for p in low_prices)
        assert any(abs(p - 100) < 1 for p in low_prices)

    def test_all_swing_types_correct(self):
        candles = _candles_from_tuples(make_downtrend_candles())
        lows = detect_swing_lows(candles, window=2)
        for l in lows:
            assert l.swing_type == SwingType.LOW


class TestAllSwings:
    def test_sorted_by_index(self):
        candles = _candles_from_tuples(make_uptrend_candles())
        swings = detect_all_swings(candles, window=2)
        indices = [s.index for s in swings]
        assert indices == sorted(indices)

    def test_contains_both_types(self):
        # Use downtrend which has clearer alternating highs and lows
        candles = _candles_from_tuples(make_downtrend_candles())
        swings = detect_all_swings(candles, window=2)
        types = {s.swing_type for s in swings}
        assert SwingType.HIGH in types
        assert SwingType.LOW in types


# ── Candle Analysis Tests ──


class TestIndecisionCandle:
    def test_small_body_large_wicks_is_indecision(self):
        # body = 0.3, range = 2.5 -> ratio = 0.12
        c = Candle(datetime.now(), 105.5, 107, 104.5, 105.8, 0)
        assert is_indecision_candle(c, threshold=0.5) is True

    def test_large_body_is_not_indecision(self):
        # body = 5, range = 7 -> ratio = 0.71
        c = Candle(datetime.now(), 100, 105, 98, 105, 0)
        assert is_indecision_candle(c, threshold=0.5) is False

    def test_doji_zero_range(self):
        c = Candle(datetime.now(), 100, 100, 100, 100, 0)
        assert is_indecision_candle(c) is False

    def test_strict_threshold(self):
        # ratio = 0.3 -> passes 0.5 but not 0.2
        c = Candle(datetime.now(), 100, 105, 95, 103, 0)
        assert is_indecision_candle(c, threshold=0.5) is True
        assert is_indecision_candle(c, threshold=0.2) is False


class TestImpulseCandle:
    def test_large_body_is_impulse(self):
        c = Candle(datetime.now(), 100, 108, 99, 107, 0)
        assert is_impulse_candle(c, avg_body_size=3.0, multiplier=2.0) is True

    def test_small_body_is_not_impulse(self):
        c = Candle(datetime.now(), 100, 101, 99, 100.5, 0)
        assert is_impulse_candle(c, avg_body_size=3.0, multiplier=2.0) is False

    def test_zero_avg_body(self):
        c = Candle(datetime.now(), 100, 105, 99, 104, 0)
        assert is_impulse_candle(c, avg_body_size=0.0) is True


class TestAvgBodySize:
    def test_basic_average(self):
        candles = [
            Candle(datetime.now(), 100, 105, 98, 103, 0),  # body = 3
            Candle(datetime.now(), 103, 108, 101, 106, 0),  # body = 3
        ]
        assert calculate_avg_body_size(candles) == 3.0

    def test_empty_list(self):
        assert calculate_avg_body_size([]) == 0.0


class TestFindIndecisionBeforeImpulse:
    def test_finds_indecision_in_supply_zone_data(self):
        candles = _candles_from_tuples(make_supply_zone_candles())
        # Index 5 is the impulse, index 4 is indecision
        idx = find_last_indecision_before_impulse(candles, impulse_index=5)
        assert idx == 4

    def test_fallback_to_previous_candle(self):
        # All candles have large bodies - no indecision
        candles = [
            Candle(datetime.now(), 100, 106, 99, 105, 0),  # ratio ~0.83
            Candle(datetime.now(), 105, 112, 104, 111, 0),  # ratio ~0.75
            Candle(datetime.now(), 111, 115, 110, 114, 0),  # ratio ~0.6
        ]
        idx = find_last_indecision_before_impulse(
            candles, impulse_index=2, threshold=0.3
        )
        assert idx == 1  # fallback to impulse_index - 1


# ── Imbalance Tests ──


class TestImbalance:
    def test_bearish_imbalance_gap_down(self):
        before = Candle(datetime.now(), 105, 107, 104, 106, 0)
        after = Candle(datetime.now(), 101, 103, 100, 102, 0)
        gap = detect_imbalance(before, after)
        assert gap is not None
        assert gap == (103, 104)  # gap between after.high and before.low

    def test_bullish_imbalance_gap_up(self):
        before = Candle(datetime.now(), 100, 103, 99, 102, 0)
        after = Candle(datetime.now(), 105, 108, 104, 107, 0)
        gap = detect_imbalance(before, after)
        assert gap is not None
        assert gap == (103, 104)  # gap between before.high and after.low

    def test_no_imbalance_overlapping_wicks(self):
        before = Candle(datetime.now(), 100, 105, 99, 103, 0)
        after = Candle(datetime.now(), 102, 106, 101, 104, 0)
        gap = detect_imbalance(before, after)
        assert gap is None

    def test_no_imbalance_touching_wicks(self):
        before = Candle(datetime.now(), 100, 105, 99, 103, 0)
        after = Candle(datetime.now(), 105, 108, 105, 107, 0)
        gap = detect_imbalance(before, after)
        assert gap is None


class TestHasImbalanceIntoZone:
    def test_supply_zone_has_imbalance(self):
        candles = _candles_from_tuples(make_supply_zone_candles())
        # Zone at index 4, impulse at index 5
        assert has_imbalance_into_zone(candles, zone_index=4, impulse_start=5) is True

    def test_invalid_indices(self):
        candles = _candles_from_tuples(make_supply_zone_candles())
        assert has_imbalance_into_zone(candles, zone_index=5, impulse_start=3) is False
