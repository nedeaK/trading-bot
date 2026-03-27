"""Tests for liquidity detection: equal highs/lows, pools, sweeps."""

import pytest
from datetime import datetime

from config.constants import LiquidityType, SwingType
from data.models import Candle, LiquidityPool, SwingPoint
from smc.liquidity import (
    find_equal_highs,
    find_equal_lows,
    detect_liquidity_sweep,
)
from tests.fixtures.sample_data import (
    make_equal_highs_candles,
    make_liquidity_sweep_candles,
)


def _candles_from_tuples(tuples):
    return [Candle.from_tuple(t) for t in tuples]


def _make_swing(index, price, swing_type):
    return SwingPoint(
        index=index,
        timestamp=datetime(2024, 1, 1),
        price=price,
        swing_type=swing_type,
    )


# ── Equal Highs ──


class TestEqualHighs:
    def test_finds_equal_highs(self):
        """Swing highs at similar prices should form a pool."""
        swings = [
            _make_swing(3, 108.0, SwingType.HIGH),
            _make_swing(7, 108.2, SwingType.HIGH),
            _make_swing(11, 107.8, SwingType.HIGH),
        ]
        pools = find_equal_highs(swings, tolerance=0.005)
        assert len(pools) >= 1
        pool = pools[0]
        assert pool.pool_type == LiquidityType.EQUAL_HIGHS
        assert pool.strength >= 2

    def test_no_equal_highs_far_apart(self):
        """Highs too far apart shouldn't cluster."""
        swings = [
            _make_swing(3, 100.0, SwingType.HIGH),
            _make_swing(7, 110.0, SwingType.HIGH),
            _make_swing(11, 120.0, SwingType.HIGH),
        ]
        pools = find_equal_highs(swings, tolerance=0.005)
        assert len(pools) == 0

    def test_ignores_swing_lows(self):
        """Only swing highs should be considered."""
        swings = [
            _make_swing(3, 108.0, SwingType.LOW),
            _make_swing(7, 108.2, SwingType.LOW),
        ]
        pools = find_equal_highs(swings, tolerance=0.005)
        assert len(pools) == 0

    def test_empty_swings(self):
        assert find_equal_highs([], tolerance=0.005) == []

    def test_single_swing(self):
        swings = [_make_swing(3, 108.0, SwingType.HIGH)]
        pools = find_equal_highs(swings, tolerance=0.005)
        assert len(pools) == 0


# ── Equal Lows ──


class TestEqualLows:
    def test_finds_equal_lows(self):
        swings = [
            _make_swing(3, 95.0, SwingType.LOW),
            _make_swing(7, 95.3, SwingType.LOW),
            _make_swing(11, 94.8, SwingType.LOW),
        ]
        pools = find_equal_lows(swings, tolerance=0.005)
        assert len(pools) >= 1
        pool = pools[0]
        assert pool.pool_type == LiquidityType.EQUAL_LOWS
        assert pool.strength >= 2

    def test_no_equal_lows_far_apart(self):
        swings = [
            _make_swing(3, 80.0, SwingType.LOW),
            _make_swing(7, 90.0, SwingType.LOW),
        ]
        pools = find_equal_lows(swings, tolerance=0.005)
        assert len(pools) == 0

    def test_empty_swings(self):
        assert find_equal_lows([], tolerance=0.005) == []


# ── Liquidity Sweep ──


class TestLiquiditySweep:
    def test_detects_sweep_above_equal_highs(self):
        """Candle wicks above the pool price then closes below = sweep."""
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_HIGHS,
            price=108.0,
            swing_indices=(3, 7),
        )
        candles = _candles_from_tuples(make_liquidity_sweep_candles())
        sweep = detect_liquidity_sweep(candles, pool)
        assert sweep is not None
        assert sweep.sweep_price > pool.price
        assert sweep.pool is pool

    def test_no_sweep_without_wick_through(self):
        """If no candle wicks through the pool, no sweep."""
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_HIGHS,
            price=115.0,  # No candle reaches this
            swing_indices=(3, 7),
        )
        candles = _candles_from_tuples(make_liquidity_sweep_candles())
        sweep = detect_liquidity_sweep(candles, pool)
        assert sweep is None

    def test_sweep_below_equal_lows(self):
        """Candle wicks below pool then closes above = sweep of lows."""
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_LOWS,
            price=100.0,
            swing_indices=(3, 7),
        )
        # Create a candle that sweeps below 100 then closes above
        candles = [
            Candle(datetime(2024, 1, 1), 102, 103, 99, 101, 1000),  # wick to 99
        ]
        sweep = detect_liquidity_sweep(candles, pool)
        assert sweep is not None
        assert sweep.sweep_price < pool.price

    def test_empty_candles(self):
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_HIGHS,
            price=108.0,
            swing_indices=(3, 7),
        )
        assert detect_liquidity_sweep([], pool) is None
