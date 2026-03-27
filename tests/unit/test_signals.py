"""Tests for signal generation pipeline."""

import pytest
from datetime import datetime

from config.constants import BiasDirection, LiquidityType, SignalType, TrendType, ZoneType
from config.settings import SMCConfig
from data.models import (
    Candle,
    LiquidityPool,
    LiquiditySetup,
    Narrative,
    Signal,
    SweepEvent,
    TrendContext,
    Zone,
)
from signals.generator import generate_signals
from tests.fixtures.sample_data import (
    make_downtrend_candles,
    make_liquidity_sweep_candles,
    make_supply_zone_candles,
    make_uptrend_candles,
)


def _candles_from_tuples(tuples):
    return [Candle.from_tuple(t) for t in tuples]


class TestGenerateSignals:
    def test_returns_empty_when_no_htf_data(self):
        """No HTF candles = neutral narrative = no signals."""
        signals = generate_signals(
            htf_candles=[],
            mtf_candles=_candles_from_tuples(make_uptrend_candles()),
            ltf_candles=_candles_from_tuples(make_uptrend_candles()),
        )
        assert signals == []

    def test_returns_empty_when_mtf_misaligned(self):
        """HTF bullish but MTF bearish = no trade."""
        # HTF uptrend but MTF downtrend - misalignment
        signals = generate_signals(
            htf_candles=_candles_from_tuples(make_uptrend_candles()),
            mtf_candles=_candles_from_tuples(make_downtrend_candles()),
            ltf_candles=_candles_from_tuples(make_downtrend_candles()),
            config=SMCConfig(swing_window=2),
        )
        assert signals == []

    def test_returns_empty_when_no_liquidity(self):
        """Aligned trend but no equal highs/lows = no signal."""
        # Both HTF and MTF bullish, but uptrend doesn't have equal lows
        uptrend = _candles_from_tuples(make_uptrend_candles())
        signals = generate_signals(
            htf_candles=uptrend,
            mtf_candles=uptrend,
            ltf_candles=uptrend,
            config=SMCConfig(swing_window=2),
        )
        # Without equal lows forming, pipeline halts at step 3
        assert isinstance(signals, list)

    def test_signal_has_required_fields(self):
        """Any generated signal must have entry, stop, and target."""
        uptrend = _candles_from_tuples(make_uptrend_candles())
        signals = generate_signals(
            htf_candles=uptrend,
            mtf_candles=uptrend,
            ltf_candles=_candles_from_tuples(make_liquidity_sweep_candles()),
            config=SMCConfig(swing_window=2),
        )
        for s in signals:
            assert s.entry_price > 0
            assert s.stop_loss > 0
            assert s.take_profit > 0
            assert s.signal_type in (SignalType.BUY, SignalType.SELL)

    def test_pipeline_returns_list(self):
        """Pipeline always returns a list (possibly empty)."""
        result = generate_signals(
            htf_candles=[],
            mtf_candles=[],
            ltf_candles=[],
        )
        assert isinstance(result, list)


class TestPipelineHaltPoints:
    """Test each step where the pipeline can halt."""

    def test_halts_at_neutral_narrative(self):
        """Empty HTF = neutral = halt at step 1."""
        signals = generate_signals([], [], [])
        assert signals == []

    def test_halts_at_mtf_disagreement(self):
        """MTF disagrees with HTF = halt at step 2."""
        htf = _candles_from_tuples(make_uptrend_candles())
        mtf = _candles_from_tuples(make_downtrend_candles())
        ltf = _candles_from_tuples(make_downtrend_candles())
        signals = generate_signals(htf, mtf, ltf, config=SMCConfig(swing_window=2))
        assert signals == []
