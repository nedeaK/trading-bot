"""Tests for data models."""

import pytest
from datetime import datetime

from config.constants import (
    BiasDirection,
    LiquidityType,
    SignalType,
    SwingType,
    TrendType,
    ZoneType,
)
from data.models import (
    Candle,
    LiquidityPool,
    Narrative,
    Signal,
    SwingPoint,
    Zone,
    pool_as_swept,
    zone_as_extreme,
    zone_with_tap,
)


class TestCandle:
    def test_from_tuple(self):
        ts = datetime(2024, 1, 1)
        c = Candle.from_tuple((ts, 100, 105, 98, 103, 5000))
        assert c.open == 100
        assert c.high == 105
        assert c.low == 98
        assert c.close == 103
        assert c.volume == 5000

    def test_from_tuple_without_volume(self):
        ts = datetime(2024, 1, 1)
        c = Candle.from_tuple((ts, 100, 105, 98, 103))
        assert c.volume == 0.0

    def test_body_size(self):
        c = Candle(datetime.now(), 100, 105, 98, 103, 0)
        assert c.body_size == 3.0  # |103 - 100|

    def test_total_range(self):
        c = Candle(datetime.now(), 100, 105, 98, 103, 0)
        assert c.total_range == 7.0  # 105 - 98

    def test_upper_wick_bullish(self):
        c = Candle(datetime.now(), 100, 105, 98, 103, 0)
        assert c.upper_wick == 2.0  # 105 - 103

    def test_lower_wick_bullish(self):
        c = Candle(datetime.now(), 100, 105, 98, 103, 0)
        assert c.lower_wick == 2.0  # 100 - 98

    def test_upper_wick_bearish(self):
        c = Candle(datetime.now(), 103, 105, 98, 100, 0)
        assert c.upper_wick == 2.0  # 105 - 103

    def test_lower_wick_bearish(self):
        c = Candle(datetime.now(), 103, 105, 98, 100, 0)
        assert c.lower_wick == 2.0  # 100 - 98

    def test_is_bullish(self):
        c = Candle(datetime.now(), 100, 105, 98, 103, 0)
        assert c.is_bullish is True
        assert c.is_bearish is False

    def test_is_bearish(self):
        c = Candle(datetime.now(), 103, 105, 98, 100, 0)
        assert c.is_bullish is False
        assert c.is_bearish is True

    def test_body_to_range_ratio(self):
        c = Candle(datetime.now(), 100, 105, 98, 103, 0)
        assert abs(c.body_to_range_ratio - 3.0 / 7.0) < 1e-10

    def test_body_to_range_ratio_doji(self):
        c = Candle(datetime.now(), 100, 100, 100, 100, 0)
        assert c.body_to_range_ratio == 0.0

    def test_immutability(self):
        c = Candle(datetime.now(), 100, 105, 98, 103, 0)
        with pytest.raises(AttributeError):
            c.open = 101


class TestZone:
    def _make_zone(self, **kwargs):
        defaults = dict(
            zone_type=ZoneType.SUPPLY,
            high=108.0,
            low=105.0,
            creation_index=4,
            creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        defaults.update(kwargs)
        return Zone(**defaults)

    def test_midpoint(self):
        z = self._make_zone()
        assert z.midpoint == 106.5

    def test_size(self):
        z = self._make_zone()
        assert z.size == 3.0

    def test_is_valid_with_imbalance_untapped(self):
        z = self._make_zone(has_imbalance=True, tap_count=0)
        assert z.is_valid is True

    def test_is_invalid_no_imbalance(self):
        z = self._make_zone(has_imbalance=False)
        assert z.is_valid is False

    def test_is_invalid_after_tap(self):
        z = self._make_zone(tap_count=1)
        assert z.is_valid is False

    def test_zone_with_tap(self):
        z = self._make_zone(tap_count=0)
        tapped = zone_with_tap(z)
        assert tapped.tap_count == 1
        assert z.tap_count == 0  # original unchanged

    def test_zone_as_extreme(self):
        z = self._make_zone(is_extreme=False)
        extreme = zone_as_extreme(z)
        assert extreme.is_extreme is True
        assert z.is_extreme is False  # original unchanged


class TestLiquidityPool:
    def test_strength(self):
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_HIGHS,
            price=108.0,
            swing_indices=(3, 7, 11),
        )
        assert pool.strength == 3

    def test_pool_as_swept(self):
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_HIGHS,
            price=108.0,
            swing_indices=(3, 7),
        )
        swept = pool_as_swept(pool)
        assert swept.swept is True
        assert pool.swept is False  # original unchanged


class TestNarrative:
    def test_long_target_is_supply(self):
        supply = Zone(
            zone_type=ZoneType.SUPPLY, high=120, low=118,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        demand = Zone(
            zone_type=ZoneType.DEMAND, high=102, low=100,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        n = Narrative(
            bias=BiasDirection.LONG,
            htf_demand_zone=demand,
            htf_supply_zone=supply,
        )
        assert n.target_zone == supply

    def test_short_target_is_demand(self):
        supply = Zone(
            zone_type=ZoneType.SUPPLY, high=120, low=118,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        demand = Zone(
            zone_type=ZoneType.DEMAND, high=102, low=100,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        n = Narrative(
            bias=BiasDirection.SHORT,
            htf_demand_zone=demand,
            htf_supply_zone=supply,
        )
        assert n.target_zone == demand

    def test_neutral_target_is_none(self):
        n = Narrative(bias=BiasDirection.NEUTRAL)
        assert n.target_zone is None


class TestSignal:
    def test_risk_reward(self):
        zone = Zone(
            zone_type=ZoneType.SUPPLY, high=108, low=105,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        narrative = Narrative(bias=BiasDirection.SHORT)
        signal = Signal(
            signal_type=SignalType.SELL,
            timestamp=datetime.now(),
            entry_price=107.0,
            stop_loss=109.0,
            take_profit=97.0,
            zone=zone,
            narrative=narrative,
        )
        assert signal.risk == 2.0
        assert signal.reward == 10.0
        assert signal.rr_ratio == 5.0
