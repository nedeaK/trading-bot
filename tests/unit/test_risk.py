"""Tests for risk management: stop loss, take profit, position sizing."""

import pytest
from datetime import datetime

from config.constants import ZoneType
from data.models import Zone
from risk.stop_loss import calculate_stop_loss
from risk.take_profit import calculate_take_profit
from risk.position_sizer import calculate_position_size


def _make_zone(zone_type, high, low):
    return Zone(
        zone_type=zone_type, high=high, low=low,
        creation_index=0, creation_timestamp=datetime(2024, 1, 1),
        has_imbalance=True,
    )


# ── Stop Loss ──


class TestStopLoss:
    def test_supply_zone_stop_above(self):
        zone = _make_zone(ZoneType.SUPPLY, 110, 108)
        sl = calculate_stop_loss(zone, buffer=0.001)
        assert sl > 110  # Above the zone high
        assert abs(sl - 110.11) < 0.01

    def test_demand_zone_stop_below(self):
        zone = _make_zone(ZoneType.DEMAND, 95, 93)
        sl = calculate_stop_loss(zone, buffer=0.001)
        assert sl < 93  # Below the zone low
        assert abs(sl - 92.907) < 0.01

    def test_zero_buffer(self):
        zone = _make_zone(ZoneType.SUPPLY, 100, 98)
        sl = calculate_stop_loss(zone, buffer=0.0)
        assert sl == 100.0  # Exactly at zone high


# ── Take Profit ──


class TestTakeProfit:
    def test_with_opposing_zone_sell(self):
        zone = _make_zone(ZoneType.SUPPLY, 110, 108)
        opposing = _make_zone(ZoneType.DEMAND, 95, 93)
        tp = calculate_take_profit(110, 110.11, zone, opposing)
        assert tp == 95  # Opposing demand zone high

    def test_with_opposing_zone_buy(self):
        zone = _make_zone(ZoneType.DEMAND, 95, 93)
        opposing = _make_zone(ZoneType.SUPPLY, 110, 108)
        tp = calculate_take_profit(93, 92.907, zone, opposing)
        assert tp == 108  # Opposing supply zone low

    def test_default_rr_sell(self):
        zone = _make_zone(ZoneType.SUPPLY, 110, 108)
        tp = calculate_take_profit(110, 111, zone, default_rr=5.0)
        assert tp == 105  # 110 - (1 * 5)

    def test_default_rr_buy(self):
        zone = _make_zone(ZoneType.DEMAND, 95, 93)
        tp = calculate_take_profit(93, 92, zone, default_rr=5.0)
        assert tp == 98  # 93 + (1 * 5)


# ── Position Sizing ──


class TestPositionSizer:
    def test_basic_calculation(self):
        """100k equity, 2% risk, $2 risk per share = 1000 shares.
        But capped by max_position (20% of 100k / 50 = 400).
        """
        shares = calculate_position_size(
            equity=100_000, entry_price=50, stop_loss=48,
            risk_percent=0.02, max_position_pct=1.0,  # No cap
        )
        assert shares == 1000

    def test_capped_by_max_position(self):
        """Position size limited by max_position_pct."""
        shares = calculate_position_size(
            equity=100_000, entry_price=50, stop_loss=49.99,
            risk_percent=0.02, max_position_pct=0.1,
        )
        # Risk says 200,000 shares but max position = 10k/50 = 200
        assert shares == 200

    def test_zero_risk_returns_zero(self):
        """If entry == stop, no position (infinite leverage)."""
        shares = calculate_position_size(
            equity=100_000, entry_price=50, stop_loss=50,
        )
        assert shares == 0

    def test_returns_integer(self):
        shares = calculate_position_size(
            equity=100_000, entry_price=33.33, stop_loss=32.33,
        )
        assert isinstance(shares, int)

    def test_small_account(self):
        shares = calculate_position_size(
            equity=1_000, entry_price=100, stop_loss=95,
            risk_percent=0.02, max_position_pct=1.0,
        )
        assert shares == 4  # 20 / 5 = 4
