"""Trade execution simulation for backtesting.

Simulates limit order fills and checks stop/target hit on each candle.
"""

from datetime import datetime
from typing import Optional, Tuple

from config.constants import SignalType
from data.models import Candle, Signal
from backtest.portfolio import Portfolio, close_position, open_position
from risk.position_sizer import calculate_position_size


def try_fill_signal(
    portfolio: Portfolio,
    signal: Signal,
    candle: Candle,
    slippage: float = 0.0001,
    commission: float = 0.0,
    risk_percent: float = 0.02,
    max_position_pct: float = 0.2,
) -> Portfolio:
    """Try to fill a pending signal on this candle.

    For a BUY signal: fill if candle low <= entry price.
    For a SELL signal: fill if candle high >= entry price.

    Args:
        portfolio: Current portfolio state.
        signal: The signal to fill.
        candle: Current candle to check.
        slippage: Slippage as fraction of price.
        commission: Commission per trade.
        risk_percent: Risk per trade for position sizing.
        max_position_pct: Max position as fraction of equity.

    Returns:
        Updated portfolio (unchanged if not filled).
    """
    filled = False
    fill_price = signal.entry_price

    if signal.signal_type == SignalType.BUY:
        if candle.low <= signal.entry_price:
            filled = True
            fill_price = signal.entry_price * (1 + slippage)
    elif signal.signal_type == SignalType.SELL:
        if candle.high >= signal.entry_price:
            filled = True
            fill_price = signal.entry_price * (1 - slippage)

    if not filled:
        return portfolio

    shares = calculate_position_size(
        equity=portfolio.total_equity,
        entry_price=fill_price,
        stop_loss=signal.stop_loss,
        risk_percent=risk_percent,
        max_position_pct=max_position_pct,
    )

    if shares <= 0:
        return portfolio

    # Deduct commission
    updated = Portfolio(
        cash=portfolio.cash - commission,
        positions=portfolio.positions,
        trades=portfolio.trades,
        equity_curve=portfolio.equity_curve,
    )

    return open_position(
        updated,
        signal_type=signal.signal_type,
        entry_price=fill_price,
        shares=shares,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        entry_time=candle.timestamp,
    )


def check_exits(
    portfolio: Portfolio,
    candle: Candle,
    slippage: float = 0.0001,
) -> Portfolio:
    """Check all open positions for stop loss or take profit hit.

    Processes exits in reverse order to avoid index shifting issues.

    Args:
        portfolio: Current portfolio.
        candle: Current candle to check.
        slippage: Slippage on exit.

    Returns:
        Updated portfolio with any closed positions.
    """
    # Check in reverse to avoid index issues when removing
    for i in range(len(portfolio.positions) - 1, -1, -1):
        pos = portfolio.positions[i]

        exit_price: Optional[float] = None

        if pos.signal_type == SignalType.BUY:
            # Stop loss: price falls to stop
            if candle.low <= pos.stop_loss:
                exit_price = pos.stop_loss * (1 - slippage)
            # Take profit: price rises to target
            elif candle.high >= pos.take_profit:
                exit_price = pos.take_profit * (1 - slippage)

        elif pos.signal_type == SignalType.SELL:
            # Stop loss: price rises to stop
            if candle.high >= pos.stop_loss:
                exit_price = pos.stop_loss * (1 + slippage)
            # Take profit: price falls to target
            elif candle.low <= pos.take_profit:
                exit_price = pos.take_profit * (1 + slippage)

        if exit_price is not None:
            portfolio = close_position(portfolio, i, exit_price, candle.timestamp)

    return portfolio
