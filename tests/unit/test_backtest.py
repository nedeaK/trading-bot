"""Tests for backtesting engine: portfolio, executor, metrics."""

import pytest
from datetime import datetime

from config.constants import SignalType, ZoneType
from data.models import Candle, Narrative, Signal, Zone
from config.constants import BiasDirection
from backtest.portfolio import (
    Portfolio,
    close_position,
    open_position,
    record_equity,
)
from backtest.executor import check_exits, try_fill_signal
from backtest.metrics import (
    avg_rr_achieved,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    total_pnl,
    win_rate,
    generate_report,
)
from backtest.portfolio import Trade


# ── Portfolio Tests ──


class TestPortfolio:
    def test_initial_state(self):
        p = Portfolio(cash=100_000)
        assert p.cash == 100_000
        assert p.num_open_positions == 0
        assert p.total_equity == 100_000
        assert p.trades == ()

    def test_open_position(self):
        p = Portfolio(cash=100_000)
        p2 = open_position(
            p, SignalType.BUY, entry_price=50.0, shares=100,
            stop_loss=48.0, take_profit=60.0,
            entry_time=datetime(2024, 1, 1),
        )
        assert p2.cash == 95_000  # 100k - 5k
        assert p2.num_open_positions == 1
        assert p.cash == 100_000  # Original unchanged

    def test_open_position_insufficient_cash(self):
        p = Portfolio(cash=1_000)
        p2 = open_position(
            p, SignalType.BUY, entry_price=50.0, shares=100,
            stop_loss=48.0, take_profit=60.0,
            entry_time=datetime(2024, 1, 1),
        )
        assert p2 is p  # Unchanged

    def test_close_position_profit(self):
        p = Portfolio(cash=95_000)
        p = open_position(
            p, SignalType.BUY, entry_price=50.0, shares=100,
            stop_loss=48.0, take_profit=60.0,
            entry_time=datetime(2024, 1, 1),
        )
        # After open: cash = 95k - 5k = 90k
        assert p.cash == 90_000
        p2 = close_position(p, 0, exit_price=55.0, exit_time=datetime(2024, 1, 5))
        assert p2.num_open_positions == 0
        assert p2.cash == 90_000 + 5500  # 90k + proceeds (55 * 100)
        assert len(p2.trades) == 1
        assert p2.trades[0].pnl == 500  # (55 - 50) * 100

    def test_close_position_loss(self):
        p = Portfolio(cash=95_000)
        p = open_position(
            p, SignalType.BUY, entry_price=50.0, shares=100,
            stop_loss=48.0, take_profit=60.0,
            entry_time=datetime(2024, 1, 1),
        )
        p2 = close_position(p, 0, exit_price=48.0, exit_time=datetime(2024, 1, 5))
        assert p2.trades[0].pnl == -200  # (48 - 50) * 100

    def test_close_short_position(self):
        p = Portfolio(cash=95_000)
        p = open_position(
            p, SignalType.SELL, entry_price=50.0, shares=100,
            stop_loss=52.0, take_profit=40.0,
            entry_time=datetime(2024, 1, 1),
        )
        p2 = close_position(p, 0, exit_price=45.0, exit_time=datetime(2024, 1, 5))
        assert p2.trades[0].pnl == 500  # (50 - 45) * 100

    def test_record_equity(self):
        p = Portfolio(cash=100_000)
        p2 = record_equity(p, datetime(2024, 1, 1), 100_000)
        assert len(p2.equity_curve) == 1

    def test_immutability(self):
        p = Portfolio(cash=100_000)
        with pytest.raises(AttributeError):
            p.cash = 50_000


# ── Executor Tests ──


class TestExecutor:
    def _make_signal(self, signal_type, entry, stop, target):
        zone = Zone(
            zone_type=ZoneType.SUPPLY if signal_type == SignalType.SELL else ZoneType.DEMAND,
            high=entry + 2, low=entry - 2,
            creation_index=0, creation_timestamp=datetime(2024, 1, 1),
            has_imbalance=True,
        )
        return Signal(
            signal_type=signal_type,
            timestamp=datetime(2024, 1, 1),
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            zone=zone,
            narrative=Narrative(bias=BiasDirection.LONG),
        )

    def test_fill_buy_signal(self):
        p = Portfolio(cash=100_000)
        signal = self._make_signal(SignalType.BUY, 50.0, 48.0, 60.0)
        candle = Candle(datetime(2024, 1, 1), 51, 52, 49, 51, 1000)  # Low 49 <= 50
        p2 = try_fill_signal(p, signal, candle, slippage=0.0, risk_percent=0.02, max_position_pct=1.0)
        assert p2.num_open_positions == 1

    def test_no_fill_when_price_doesnt_reach(self):
        p = Portfolio(cash=100_000)
        signal = self._make_signal(SignalType.BUY, 50.0, 48.0, 60.0)
        candle = Candle(datetime(2024, 1, 1), 52, 53, 51, 52, 1000)  # Low 51 > 50
        p2 = try_fill_signal(p, signal, candle, slippage=0.0)
        assert p2 is p  # Unchanged

    def test_check_stop_loss(self):
        p = Portfolio(cash=95_000)
        p = open_position(
            p, SignalType.BUY, 50.0, 100, 48.0, 60.0,
            datetime(2024, 1, 1),
        )
        candle = Candle(datetime(2024, 1, 2), 49, 49, 47, 48, 1000)  # Low hits stop
        p2 = check_exits(p, candle, slippage=0.0)
        assert p2.num_open_positions == 0
        assert len(p2.trades) == 1

    def test_check_take_profit(self):
        p = Portfolio(cash=95_000)
        p = open_position(
            p, SignalType.BUY, 50.0, 100, 48.0, 60.0,
            datetime(2024, 1, 1),
        )
        candle = Candle(datetime(2024, 1, 2), 58, 61, 57, 60, 1000)  # High hits target
        p2 = check_exits(p, candle, slippage=0.0)
        assert p2.num_open_positions == 0
        assert p2.trades[0].pnl > 0


# ── Metrics Tests ──


class TestMetrics:
    def _make_trades(self):
        return [
            Trade(SignalType.BUY, 50, 55, 100, datetime(2024, 1, 1),
                  datetime(2024, 1, 5), pnl=500, rr_achieved=2.5),
            Trade(SignalType.BUY, 50, 48, 100, datetime(2024, 1, 6),
                  datetime(2024, 1, 10), pnl=-200, rr_achieved=-1.0),
            Trade(SignalType.SELL, 55, 50, 100, datetime(2024, 1, 11),
                  datetime(2024, 1, 15), pnl=500, rr_achieved=2.5),
        ]

    def test_win_rate(self):
        trades = self._make_trades()
        assert abs(win_rate(trades) - 2 / 3) < 0.01

    def test_win_rate_empty(self):
        assert win_rate([]) == 0.0

    def test_profit_factor(self):
        trades = self._make_trades()
        pf = profit_factor(trades)
        assert pf == 1000 / 200  # 5.0

    def test_total_pnl(self):
        trades = self._make_trades()
        assert total_pnl(trades) == 800

    def test_avg_rr(self):
        trades = self._make_trades()
        avg = avg_rr_achieved(trades)
        assert abs(avg - (2.5 - 1.0 + 2.5) / 3) < 0.01

    def test_max_drawdown(self):
        curve = [
            (datetime(2024, 1, 1), 100_000),
            (datetime(2024, 1, 2), 105_000),
            (datetime(2024, 1, 3), 95_000),   # 9.5% dd from 105k
            (datetime(2024, 1, 4), 110_000),
        ]
        dd = max_drawdown(curve)
        expected = (105_000 - 95_000) / 105_000
        assert abs(dd - expected) < 0.001

    def test_max_drawdown_empty(self):
        assert max_drawdown([]) == 0.0

    def test_sharpe_ratio_flat(self):
        """Flat equity = zero returns = zero sharpe."""
        curve = [
            (datetime(2024, 1, i), 100_000) for i in range(1, 10)
        ]
        assert sharpe_ratio(curve) == 0.0

    def test_generate_report(self):
        trades = self._make_trades()
        curve = [
            (datetime(2024, 1, 1), 100_000),
            (datetime(2024, 1, 5), 100_500),
            (datetime(2024, 1, 10), 100_300),
            (datetime(2024, 1, 15), 100_800),
        ]
        report = generate_report(trades, curve)
        assert report['total_trades'] == 3
        assert report['win_rate'] > 0
        assert 'sharpe_ratio' in report
