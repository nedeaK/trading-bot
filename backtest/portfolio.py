"""Immutable portfolio state for backtesting.

Tracks cash, positions, completed trades, and equity curve.
All updates return new Portfolio instances.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple

from config.constants import SignalType


@dataclass(frozen=True)
class Trade:
    """A completed trade."""
    signal_type: SignalType
    entry_price: float
    exit_price: float
    shares: int
    entry_time: datetime
    exit_time: datetime
    pnl: float
    rr_achieved: float


@dataclass(frozen=True)
class Position:
    """An open position."""
    signal_type: SignalType
    entry_price: float
    shares: int
    stop_loss: float
    take_profit: float
    entry_time: datetime


@dataclass(frozen=True)
class Portfolio:
    """Immutable portfolio state."""
    cash: float
    positions: Tuple[Position, ...] = ()
    trades: Tuple[Trade, ...] = ()
    equity_curve: Tuple[Tuple[datetime, float], ...] = ()

    @property
    def total_equity(self) -> float:
        """Cash + unrealized value of open positions (at entry price)."""
        position_value = sum(p.entry_price * p.shares for p in self.positions)
        return self.cash + position_value

    @property
    def num_open_positions(self) -> int:
        return len(self.positions)


def open_position(
    portfolio: Portfolio,
    signal_type: SignalType,
    entry_price: float,
    shares: int,
    stop_loss: float,
    take_profit: float,
    entry_time: datetime,
) -> Portfolio:
    """Open a new position, deducting cost from cash."""
    cost = entry_price * shares
    if cost > portfolio.cash:
        return portfolio  # Can't afford

    new_position = Position(
        signal_type=signal_type,
        entry_price=entry_price,
        shares=shares,
        stop_loss=stop_loss,
        take_profit=take_profit,
        entry_time=entry_time,
    )

    return Portfolio(
        cash=portfolio.cash - cost,
        positions=portfolio.positions + (new_position,),
        trades=portfolio.trades,
        equity_curve=portfolio.equity_curve,
    )


def close_position(
    portfolio: Portfolio,
    position_index: int,
    exit_price: float,
    exit_time: datetime,
) -> Portfolio:
    """Close a position and record the trade."""
    if position_index >= len(portfolio.positions):
        return portfolio

    pos = portfolio.positions[position_index]

    # Calculate PnL
    if pos.signal_type == SignalType.BUY:
        pnl = (exit_price - pos.entry_price) * pos.shares
    else:  # SELL (short)
        pnl = (pos.entry_price - exit_price) * pos.shares

    # Calculate R:R achieved
    risk = abs(pos.entry_price - pos.stop_loss)
    rr_achieved = pnl / (risk * pos.shares) if risk > 0 and pos.shares > 0 else 0.0

    trade = Trade(
        signal_type=pos.signal_type,
        entry_price=pos.entry_price,
        exit_price=exit_price,
        shares=pos.shares,
        entry_time=pos.entry_time,
        exit_time=exit_time,
        pnl=pnl,
        rr_achieved=rr_achieved,
    )

    # Remove the closed position
    remaining = portfolio.positions[:position_index] + portfolio.positions[position_index + 1:]

    # Add proceeds back to cash
    proceeds = exit_price * pos.shares

    return Portfolio(
        cash=portfolio.cash + proceeds,
        positions=remaining,
        trades=portfolio.trades + (trade,),
        equity_curve=portfolio.equity_curve,
    )


def record_equity(portfolio: Portfolio, timestamp: datetime, equity: float) -> Portfolio:
    """Record a point on the equity curve."""
    return Portfolio(
        cash=portfolio.cash,
        positions=portfolio.positions,
        trades=portfolio.trades,
        equity_curve=portfolio.equity_curve + ((timestamp, equity),),
    )
