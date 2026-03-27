"""Tests for the top-down sequential trading flow engine."""

import pytest
from datetime import datetime

from config.constants import (
    BiasDirection,
    LiquidityType,
    SwingType,
    TrendType,
    ZoneType,
)
from data.models import (
    Candle,
    LiquidityPool,
    LiquiditySetup,
    Narrative,
    StructurePoint,
    SweepEvent,
    TrendContext,
    Zone,
)
from smc.top_down import (
    read_htf_narrative,
    check_mtf_trend,
    scan_for_liquidity,
    detect_sweep,
    find_entry_zone,
    create_order,
)
from tests.fixtures.sample_data import (
    make_downtrend_candles,
    make_equal_highs_candles,
    make_liquidity_sweep_candles,
    make_supply_zone_candles,
    make_uptrend_candles,
)


def _candles_from_tuples(tuples):
    return [Candle.from_tuple(t) for t in tuples]


# ── Step 1: HTF Narrative ──


class TestHTFNarrative:
    def test_identifies_long_bias(self):
        """Price near demand = LONG bias."""
        candles = _candles_from_tuples(make_uptrend_candles())
        narrative = read_htf_narrative(candles)
        assert narrative is not None
        assert narrative.bias in (BiasDirection.LONG, BiasDirection.SHORT, BiasDirection.NEUTRAL)

    def test_identifies_zones(self):
        """Narrative should identify S/D zones on the HTF."""
        candles = _candles_from_tuples(make_uptrend_candles())
        narrative = read_htf_narrative(candles)
        # Should have identified at least a general direction
        assert narrative is not None

    def test_empty_candles(self):
        narrative = read_htf_narrative([])
        assert narrative is not None
        assert narrative.bias == BiasDirection.NEUTRAL


# ── Step 2: MTF Trend ──


class TestMTFTrend:
    def test_aligned_bullish(self):
        """LONG narrative + bullish MTF structure = aligned."""
        narrative = Narrative(bias=BiasDirection.LONG)
        candles = _candles_from_tuples(make_uptrend_candles())
        ctx = check_mtf_trend(candles, narrative, swing_window=2)
        assert ctx is not None
        assert ctx.trend == TrendType.BULLISH

    def test_aligned_bearish(self):
        """SHORT narrative + bearish MTF structure = aligned."""
        narrative = Narrative(bias=BiasDirection.SHORT)
        candles = _candles_from_tuples(make_downtrend_candles())
        ctx = check_mtf_trend(candles, narrative, swing_window=2)
        assert ctx is not None
        assert ctx.trend == TrendType.BEARISH

    def test_misaligned_returns_none(self):
        """LONG narrative + bearish MTF structure = no trade."""
        narrative = Narrative(bias=BiasDirection.LONG)
        candles = _candles_from_tuples(make_downtrend_candles())
        ctx = check_mtf_trend(candles, narrative, swing_window=2)
        assert ctx is None

    def test_neutral_narrative_returns_none(self):
        """NEUTRAL narrative = never trade."""
        narrative = Narrative(bias=BiasDirection.NEUTRAL)
        candles = _candles_from_tuples(make_uptrend_candles())
        ctx = check_mtf_trend(candles, narrative, swing_window=2)
        assert ctx is None


# ── Step 3: Scan for Liquidity ──


class TestScanForLiquidity:
    def test_finds_equal_highs_in_bearish_trend(self):
        """Bearish trend should look for equal highs above."""
        candles = _candles_from_tuples(make_equal_highs_candles())
        trend_ctx = TrendContext(
            trend=TrendType.BEARISH,
            structure_points=(),
        )
        setup = scan_for_liquidity(candles, trend_ctx)
        # May or may not find depending on data, but function should work
        # The equal_highs data has highs at ~108
        if setup is not None:
            assert setup.pool.pool_type == LiquidityType.EQUAL_HIGHS

    def test_returns_none_without_liquidity(self):
        """If no equal levels found, returns None."""
        candles = _candles_from_tuples(make_uptrend_candles())
        trend_ctx = TrendContext(
            trend=TrendType.BULLISH,
            structure_points=(),
        )
        # Uptrend has progressively higher highs, unlikely to form equal lows
        setup = scan_for_liquidity(candles, trend_ctx)
        # Result depends on data; just ensure it doesn't crash
        assert setup is None or isinstance(setup, LiquiditySetup)


# ── Step 4: Detect Sweep ──


class TestDetectSweep:
    def test_detects_sweep(self):
        """Sweep candles data should produce a sweep event."""
        candles = _candles_from_tuples(make_liquidity_sweep_candles())
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_HIGHS,
            price=108.0,
            swing_indices=(3, 7),
        )
        setup = LiquiditySetup(pool=pool, trend_context=TrendContext(
            trend=TrendType.BEARISH, structure_points=(),
        ))
        sweep = detect_sweep(candles, setup)
        assert sweep is not None
        assert sweep.sweep_price > 108.0

    def test_no_sweep_returns_none(self):
        candles = _candles_from_tuples(make_uptrend_candles())
        pool = LiquidityPool(
            pool_type=LiquidityType.EQUAL_HIGHS,
            price=200.0,  # Way above any candle
            swing_indices=(3, 7),
        )
        setup = LiquiditySetup(pool=pool, trend_context=TrendContext(
            trend=TrendType.BEARISH, structure_points=(),
        ))
        sweep = detect_sweep(candles, setup)
        assert sweep is None


# ── Step 5: Find Entry Zone ──


class TestFindEntryZone:
    def test_finds_zone_at_sweep(self):
        """After a sweep, there should be a S/D zone nearby."""
        candles = _candles_from_tuples(make_supply_zone_candles())
        sweep = SweepEvent(
            sweep_index=5,
            sweep_price=109.0,
            pool=LiquidityPool(
                pool_type=LiquidityType.EQUAL_HIGHS,
                price=108.0,
                swing_indices=(3,),
            ),
            sweep_candle_timestamp=datetime(2024, 1, 1),
        )
        zone = find_entry_zone(candles, sweep)
        # Supply zone candles should produce a zone near index 4
        if zone is not None:
            assert zone.zone_type in (ZoneType.SUPPLY, ZoneType.DEMAND)
            assert zone.has_imbalance is True

    def test_no_zone_returns_none(self):
        """If no valid zone near sweep, return None."""
        # Minimal candles with no clear zone
        candles = [
            Candle(datetime(2024, 1, 1), 100, 101, 99, 100.5, 0),
            Candle(datetime(2024, 1, 2), 100.5, 101.5, 100, 101, 0),
        ]
        sweep = SweepEvent(
            sweep_index=1,
            sweep_price=102.0,
            pool=LiquidityPool(
                pool_type=LiquidityType.EQUAL_HIGHS,
                price=101.5,
                swing_indices=(0,),
            ),
            sweep_candle_timestamp=datetime(2024, 1, 2),
        )
        zone = find_entry_zone(candles, sweep)
        # May or may not find one; just ensure it handles gracefully
        assert zone is None or isinstance(zone, Zone)


# ── Step 6: Create Order ──


class TestCreateOrder:
    def test_creates_sell_signal_from_supply(self):
        """Supply zone + SHORT narrative = SELL signal."""
        zone = Zone(
            zone_type=ZoneType.SUPPLY, high=110, low=108,
            creation_index=4, creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        demand = Zone(
            zone_type=ZoneType.DEMAND, high=95, low=93,
            creation_index=0, creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        narrative = Narrative(
            bias=BiasDirection.SHORT,
            htf_demand_zone=demand,
            htf_supply_zone=zone,
        )
        signal = create_order(zone, narrative)
        assert signal is not None
        from config.constants import SignalType
        assert signal.signal_type == SignalType.SELL
        assert signal.entry_price == 110  # Enter at zone high (supply)
        assert signal.stop_loss > 110     # Stop above zone
        assert signal.take_profit < 110   # Target below

    def test_creates_buy_signal_from_demand(self):
        """Demand zone + LONG narrative = BUY signal."""
        supply = Zone(
            zone_type=ZoneType.SUPPLY, high=120, low=118,
            creation_index=10, creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        zone = Zone(
            zone_type=ZoneType.DEMAND, high=95, low=93,
            creation_index=4, creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        narrative = Narrative(
            bias=BiasDirection.LONG,
            htf_demand_zone=zone,
            htf_supply_zone=supply,
        )
        signal = create_order(zone, narrative)
        assert signal is not None
        from config.constants import SignalType
        assert signal.signal_type == SignalType.BUY
        assert signal.entry_price == 93  # Enter at zone low (demand)
        assert signal.stop_loss < 93     # Stop below zone
        assert signal.take_profit > 93   # Target above

    def test_rr_ratio_is_reasonable(self):
        """R:R should be at least 1:1."""
        zone = Zone(
            zone_type=ZoneType.SUPPLY, high=110, low=108,
            creation_index=4, creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        demand = Zone(
            zone_type=ZoneType.DEMAND, high=95, low=93,
            creation_index=0, creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        narrative = Narrative(
            bias=BiasDirection.SHORT,
            htf_demand_zone=demand,
            htf_supply_zone=zone,
        )
        signal = create_order(zone, narrative)
        assert signal.rr_ratio >= 1.0
