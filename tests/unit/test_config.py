"""Tests for configuration and constants."""

import pytest
from config.constants import (
    BiasDirection,
    LiquidityType,
    SignalType,
    StructureType,
    SwingType,
    Timeframe,
    TrendType,
    ZoneType,
)
from config.settings import Config, SMCConfig, TimeframeConfig


class TestConstants:
    def test_swing_types_exist(self):
        assert SwingType.HIGH is not None
        assert SwingType.LOW is not None

    def test_structure_types_exist(self):
        assert StructureType.HH is not None
        assert StructureType.HL is not None
        assert StructureType.LL is not None
        assert StructureType.LH is not None

    def test_trend_types_exist(self):
        assert TrendType.BULLISH is not None
        assert TrendType.BEARISH is not None
        assert TrendType.CONSOLIDATION is not None

    def test_zone_types_exist(self):
        assert ZoneType.SUPPLY is not None
        assert ZoneType.DEMAND is not None

    def test_bias_directions(self):
        assert BiasDirection.LONG is not None
        assert BiasDirection.SHORT is not None
        assert BiasDirection.NEUTRAL is not None

    def test_timeframe_values(self):
        assert Timeframe.D1.value == "1d"
        assert Timeframe.H4.value == "4h"
        assert Timeframe.M15.value == "15m"


class TestConfig:
    def test_default_config_is_immutable(self):
        config = Config()
        with pytest.raises(AttributeError):
            config.symbol = "AAPL"

    def test_default_values(self):
        config = Config()
        assert config.symbol == "SPY"
        assert config.smc.swing_window == 5
        assert config.risk.risk_percent == 0.02
        assert config.backtest.initial_balance == 100_000.0

    def test_timeframe_config_defaults(self):
        tf = TimeframeConfig()
        assert tf.htf == Timeframe.D1
        assert tf.mtf == Timeframe.H1
        assert tf.ltf == Timeframe.M15

    def test_custom_config(self):
        config = Config(
            symbol="AAPL",
            smc=SMCConfig(swing_window=7),
        )
        assert config.symbol == "AAPL"
        assert config.smc.swing_window == 7
        # Other defaults preserved
        assert config.risk.risk_percent == 0.02
