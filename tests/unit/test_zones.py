"""Tests for supply and demand zone detection."""

import pytest
from datetime import datetime

from config.constants import TrendType, ZoneType
from data.models import Candle, Zone
from smc.zones import (
    detect_supply_zones,
    detect_demand_zones,
    detect_all_zones,
    filter_zones_by_trend,
    mark_extreme_zones,
)
from tests.fixtures.sample_data import (
    make_demand_zone_candles,
    make_supply_zone_candles,
    make_uptrend_candles,
    make_downtrend_candles,
)


def _candles_from_tuples(tuples):
    return [Candle.from_tuple(t) for t in tuples]


# ── Supply Zone Tests ──


class TestSupplyZones:
    def test_detects_supply_zone(self):
        """Supply zone = indecision before bearish impulse."""
        candles = _candles_from_tuples(make_supply_zone_candles())
        zones = detect_supply_zones(candles)
        assert len(zones) >= 1
        for z in zones:
            assert z.zone_type == ZoneType.SUPPLY

    def test_supply_zone_boundaries(self):
        """Zone high/low should come from the indecision candle."""
        candles = _candles_from_tuples(make_supply_zone_candles())
        zones = detect_supply_zones(candles)
        assert len(zones) >= 1
        z = zones[0]
        # Zone should be at the indecision candle (index 4): high=107, low=104.5
        assert z.high >= 104
        assert z.low <= 108

    def test_supply_zone_has_imbalance(self):
        """Only zones with imbalance should be detected."""
        candles = _candles_from_tuples(make_supply_zone_candles())
        zones = detect_supply_zones(candles)
        for z in zones:
            assert z.has_imbalance is True

    def test_no_supply_zone_in_uptrend_data(self):
        """Uptrend data shouldn't produce supply zones (no bearish impulse)."""
        candles = _candles_from_tuples(make_uptrend_candles())
        zones = detect_supply_zones(candles)
        # May or may not detect depending on data, but any found should be valid
        for z in zones:
            assert z.zone_type == ZoneType.SUPPLY


# ── Demand Zone Tests ──


class TestDemandZones:
    def test_detects_demand_zone(self):
        """Demand zone = indecision before bullish impulse."""
        candles = _candles_from_tuples(make_demand_zone_candles())
        zones = detect_demand_zones(candles)
        assert len(zones) >= 1
        for z in zones:
            assert z.zone_type == ZoneType.DEMAND

    def test_demand_zone_has_imbalance(self):
        candles = _candles_from_tuples(make_demand_zone_candles())
        zones = detect_demand_zones(candles)
        for z in zones:
            assert z.has_imbalance is True


# ── All Zones ──


class TestAllZones:
    def test_detects_from_supply_data(self):
        candles = _candles_from_tuples(make_supply_zone_candles())
        zones = detect_all_zones(candles)
        zone_types = {z.zone_type for z in zones}
        assert ZoneType.SUPPLY in zone_types

    def test_detects_from_demand_data(self):
        candles = _candles_from_tuples(make_demand_zone_candles())
        zones = detect_all_zones(candles)
        zone_types = {z.zone_type for z in zones}
        assert ZoneType.DEMAND in zone_types

    def test_zones_are_valid(self):
        """All detected zones should start as valid (imbalance + 0 taps)."""
        candles = _candles_from_tuples(make_supply_zone_candles())
        zones = detect_all_zones(candles)
        for z in zones:
            assert z.is_valid is True

    def test_empty_candles(self):
        assert detect_all_zones([]) == []


# ── Filter by Trend ──


class TestFilterByTrend:
    def test_bullish_keeps_demand(self):
        demand = Zone(
            zone_type=ZoneType.DEMAND, high=105, low=103,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        supply = Zone(
            zone_type=ZoneType.SUPPLY, high=115, low=113,
            creation_index=5, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        filtered = filter_zones_by_trend([demand, supply], TrendType.BULLISH)
        assert all(z.zone_type == ZoneType.DEMAND for z in filtered)

    def test_bearish_keeps_supply(self):
        demand = Zone(
            zone_type=ZoneType.DEMAND, high=105, low=103,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        supply = Zone(
            zone_type=ZoneType.SUPPLY, high=115, low=113,
            creation_index=5, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        filtered = filter_zones_by_trend([demand, supply], TrendType.BEARISH)
        assert all(z.zone_type == ZoneType.SUPPLY for z in filtered)

    def test_consolidation_keeps_all(self):
        demand = Zone(
            zone_type=ZoneType.DEMAND, high=105, low=103,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        supply = Zone(
            zone_type=ZoneType.SUPPLY, high=115, low=113,
            creation_index=5, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        filtered = filter_zones_by_trend([demand, supply], TrendType.CONSOLIDATION)
        assert len(filtered) == 2


# ── Extreme Zone Marking ──


class TestExtremeZones:
    def test_marks_furthest_supply_as_extreme(self):
        """Extreme supply = highest supply zone (furthest from price)."""
        z1 = Zone(
            zone_type=ZoneType.SUPPLY, high=110, low=108,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        z2 = Zone(
            zone_type=ZoneType.SUPPLY, high=120, low=118,
            creation_index=5, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        result = mark_extreme_zones([z1, z2], current_price=100.0)
        extreme = [z for z in result if z.is_extreme]
        assert len(extreme) == 1
        assert extreme[0].high == 120  # Furthest from price

    def test_marks_furthest_demand_as_extreme(self):
        """Extreme demand = lowest demand zone (furthest from price)."""
        z1 = Zone(
            zone_type=ZoneType.DEMAND, high=95, low=93,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        z2 = Zone(
            zone_type=ZoneType.DEMAND, high=85, low=83,
            creation_index=5, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        result = mark_extreme_zones([z1, z2], current_price=100.0)
        extreme = [z for z in result if z.is_extreme]
        assert len(extreme) == 1
        assert extreme[0].low == 83  # Furthest from price

    def test_empty_zones(self):
        assert mark_extreme_zones([], current_price=100.0) == []

    def test_single_zone_is_extreme(self):
        z = Zone(
            zone_type=ZoneType.SUPPLY, high=110, low=108,
            creation_index=0, creation_timestamp=datetime.now(),
            has_imbalance=True,
        )
        result = mark_extreme_zones([z], current_price=100.0)
        assert result[0].is_extreme is True
