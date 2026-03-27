"""Synthetic OHLCV data for testing SMC concepts.

Each fixture creates a known pattern so tests can verify detection logic
against predictable data.
"""

from datetime import datetime, timedelta


def _make_candle_tuple(index, open_, high, low, close, volume=1000):
    """Helper to create a candle tuple (timestamp, open, high, low, close, volume)."""
    ts = datetime(2024, 1, 1) + timedelta(hours=index)
    return (ts, open_, high, low, close, volume)


def make_uptrend_candles():
    """Clear uptrend: HH and HL pattern.

    Pattern: price moves up with higher highs and higher lows.
    Swing points at indices: 0(L), 3(H), 5(L), 8(H), 10(L), 13(H)
    """
    return [
        _make_candle_tuple(0, 100, 101, 99, 100.5),    # 0: swing low ~99
        _make_candle_tuple(1, 100.5, 102, 100, 101.5),
        _make_candle_tuple(2, 101.5, 103, 101, 102.5),
        _make_candle_tuple(3, 102.5, 105, 102, 104),    # 3: swing high ~105
        _make_candle_tuple(4, 104, 104.5, 102, 102.5),
        _make_candle_tuple(5, 102.5, 103, 101.5, 102),  # 5: HL ~101.5
        _make_candle_tuple(6, 102, 104, 101.5, 103.5),
        _make_candle_tuple(7, 103.5, 106, 103, 105.5),
        _make_candle_tuple(8, 105.5, 108, 105, 107),    # 8: HH ~108
        _make_candle_tuple(9, 107, 107.5, 104, 104.5),
        _make_candle_tuple(10, 104.5, 105, 103.5, 104), # 10: HL ~103.5
        _make_candle_tuple(11, 104, 106, 103.5, 105.5),
        _make_candle_tuple(12, 105.5, 108, 105, 107.5),
        _make_candle_tuple(13, 107.5, 111, 107, 110),   # 13: HH ~111
        _make_candle_tuple(14, 110, 110.5, 108, 109),
    ]


def make_downtrend_candles():
    """Clear downtrend: LL and LH pattern.

    Pattern: price moves down with lower lows and lower highs.
    """
    return [
        _make_candle_tuple(0, 110, 111, 109, 110.5),    # 0: swing high ~111
        _make_candle_tuple(1, 110.5, 110.5, 108, 108.5),
        _make_candle_tuple(2, 108.5, 109, 106, 106.5),
        _make_candle_tuple(3, 106.5, 107, 104, 105),    # 3: swing low ~104
        _make_candle_tuple(4, 105, 107.5, 104.5, 107),
        _make_candle_tuple(5, 107, 108.5, 106.5, 108),  # 5: LH ~108.5
        _make_candle_tuple(6, 108, 108, 105, 105.5),
        _make_candle_tuple(7, 105.5, 106, 102, 102.5),
        _make_candle_tuple(8, 102.5, 103, 100, 101),    # 8: LL ~100
        _make_candle_tuple(9, 101, 104, 100.5, 103.5),
        _make_candle_tuple(10, 103.5, 106, 103, 105.5), # 10: LH ~106
        _make_candle_tuple(11, 105.5, 105.5, 102, 102.5),
        _make_candle_tuple(12, 102.5, 103, 98, 98.5),
        _make_candle_tuple(13, 98.5, 99, 96, 97),       # 13: LL ~96
        _make_candle_tuple(14, 97, 100, 96.5, 99),
    ]


def make_consolidation_candles():
    """Sideways consolidation: no clear HH/HL or LL/LH.

    Price oscillates between ~98 and ~102.
    """
    return [
        _make_candle_tuple(0, 100, 102, 99, 101),
        _make_candle_tuple(1, 101, 101.5, 99, 99.5),
        _make_candle_tuple(2, 99.5, 101, 98.5, 100.5),
        _make_candle_tuple(3, 100.5, 102, 99.5, 101.5),
        _make_candle_tuple(4, 101.5, 102, 99, 99.5),
        _make_candle_tuple(5, 99.5, 101.5, 98.5, 101),
        _make_candle_tuple(6, 101, 102.5, 99.5, 100),
        _make_candle_tuple(7, 100, 101.5, 98.5, 99),
        _make_candle_tuple(8, 99, 101, 98, 100.5),
        _make_candle_tuple(9, 100.5, 102, 99, 101),
    ]


def make_supply_zone_candles():
    """Candles with a clear supply zone.

    Index 4 is an indecision candle (small body, large wicks)
    followed by a strong bearish impulse at index 5-6.
    There is an imbalance (gap) between index 4 low and index 6 high.
    """
    return [
        _make_candle_tuple(0, 100, 101, 99.5, 100.5),
        _make_candle_tuple(1, 100.5, 103, 100, 102.5),
        _make_candle_tuple(2, 102.5, 105, 102, 104.5),
        _make_candle_tuple(3, 104.5, 106, 104, 105.5),
        _make_candle_tuple(4, 105.5, 107, 104.5, 105.8),  # indecision: body=0.3, range=2.5
        _make_candle_tuple(5, 105, 105.2, 101, 101.5),    # impulse down (gap: 104.5 to 105.2)
        _make_candle_tuple(6, 101.5, 102, 98, 98.5),      # continued impulse
        _make_candle_tuple(7, 98.5, 99.5, 97, 99),
        _make_candle_tuple(8, 99, 100, 97.5, 98),
    ]


def make_demand_zone_candles():
    """Candles with a clear demand zone.

    Index 4 is an indecision candle followed by a strong bullish impulse.
    """
    return [
        _make_candle_tuple(0, 110, 110.5, 109, 109.5),
        _make_candle_tuple(1, 109.5, 110, 107, 107.5),
        _make_candle_tuple(2, 107.5, 108, 105, 105.5),
        _make_candle_tuple(3, 105.5, 106, 104, 104.5),
        _make_candle_tuple(4, 104.5, 105.5, 103, 104.2),  # indecision: body=0.3, range=2.5
        _make_candle_tuple(5, 105, 109, 104.8, 108.5),    # impulse up (gap: 105.5 to 104.8)
        _make_candle_tuple(6, 108.5, 112, 108, 111.5),    # continued impulse
        _make_candle_tuple(7, 111.5, 113, 111, 112.5),
        _make_candle_tuple(8, 112.5, 113.5, 112, 113),
    ]


def make_equal_highs_candles():
    """Candles with equal highs forming (liquidity pool above).

    Indices 3, 7, 11 all have highs near ~108 (within tolerance).
    """
    return [
        _make_candle_tuple(0, 100, 101, 99, 100.5),
        _make_candle_tuple(1, 100.5, 104, 100, 103),
        _make_candle_tuple(2, 103, 107, 102.5, 106),
        _make_candle_tuple(3, 106, 108, 105, 106.5),     # high ~108
        _make_candle_tuple(4, 106.5, 107, 104, 104.5),
        _make_candle_tuple(5, 104.5, 105.5, 103, 104),
        _make_candle_tuple(6, 104, 107, 103.5, 106.5),
        _make_candle_tuple(7, 106.5, 108.2, 105.5, 106), # high ~108.2
        _make_candle_tuple(8, 106, 107, 104, 104.5),
        _make_candle_tuple(9, 104.5, 105, 102.5, 103),
        _make_candle_tuple(10, 103, 106, 102.5, 105.5),
        _make_candle_tuple(11, 105.5, 107.8, 105, 106),  # high ~107.8
        _make_candle_tuple(12, 106, 107, 104.5, 105),
    ]


def make_liquidity_sweep_candles():
    """Candles showing a liquidity sweep above equal highs then reversal.

    Equal highs at ~108 (indices 3, 7).
    Index 10 sweeps above to 109.5 then closes below = sweep.
    Index 11+ sells off = reversal after sweep.
    """
    return [
        _make_candle_tuple(0, 100, 101, 99, 100.5),
        _make_candle_tuple(1, 100.5, 104, 100, 103),
        _make_candle_tuple(2, 103, 107, 102.5, 106),
        _make_candle_tuple(3, 106, 108, 105, 106.5),      # equal high ~108
        _make_candle_tuple(4, 106.5, 107, 103, 103.5),
        _make_candle_tuple(5, 103.5, 105, 102, 104.5),
        _make_candle_tuple(6, 104.5, 107, 104, 106.5),
        _make_candle_tuple(7, 106.5, 108.1, 105.5, 106),  # equal high ~108.1
        _make_candle_tuple(8, 106, 107, 104, 106.5),
        _make_candle_tuple(9, 106.5, 108, 106, 107.5),
        _make_candle_tuple(10, 107.5, 109.5, 106, 106.5), # SWEEP: wick above 108, closes below
        _make_candle_tuple(11, 106.5, 107, 103, 103.5),   # sell off begins
        _make_candle_tuple(12, 103.5, 104, 100, 100.5),   # continued sell
        _make_candle_tuple(13, 100.5, 101, 98, 98.5),
    ]
