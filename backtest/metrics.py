"""Backtesting performance metrics.

Calculates Sharpe ratio, max drawdown, win rate, profit factor, etc.
"""

import math
from typing import List, Tuple

from backtest.portfolio import Trade


def win_rate(trades: List[Trade]) -> float:
    """Fraction of trades that were profitable."""
    if not trades:
        return 0.0
    winners = sum(1 for t in trades if t.pnl > 0)
    return winners / len(trades)


def profit_factor(trades: List[Trade]) -> float:
    """Gross profit / gross loss. > 1.0 is profitable."""
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def total_pnl(trades: List[Trade]) -> float:
    """Total profit/loss across all trades."""
    return sum(t.pnl for t in trades)


def avg_rr_achieved(trades: List[Trade]) -> float:
    """Average risk:reward ratio achieved across trades."""
    if not trades:
        return 0.0
    return sum(t.rr_achieved for t in trades) / len(trades)


def max_drawdown(equity_curve: List[Tuple[float, float]]) -> float:
    """Maximum peak-to-trough drawdown as a fraction.

    Args:
        equity_curve: List of (timestamp, equity) tuples.

    Returns:
        Maximum drawdown as a positive fraction (e.g., 0.15 = 15%).
    """
    if len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0][1]
    max_dd = 0.0

    for _, equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    return max_dd


def sharpe_ratio(
    equity_curve: List[Tuple[float, float]],
    risk_free_rate: float = 0.0,
    periods_per_year: float = 252,
) -> float:
    """Annualized Sharpe ratio from equity curve.

    Args:
        equity_curve: List of (timestamp, equity) tuples.
        risk_free_rate: Annual risk-free rate.
        periods_per_year: Number of periods per year (252 for daily).

    Returns:
        Annualized Sharpe ratio.
    """
    if len(equity_curve) < 3:
        return 0.0

    # Calculate returns
    returns = []
    for i in range(1, len(equity_curve)):
        prev_eq = equity_curve[i - 1][1]
        curr_eq = equity_curve[i][1]
        if prev_eq > 0:
            returns.append((curr_eq - prev_eq) / prev_eq)

    if not returns:
        return 0.0

    avg_return = sum(returns) / len(returns)
    if len(returns) < 2:
        return 0.0

    variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
    std_return = math.sqrt(variance)

    if std_return == 0:
        return 0.0

    period_rf = risk_free_rate / periods_per_year
    sharpe = (avg_return - period_rf) / std_return
    return sharpe * math.sqrt(periods_per_year)


def generate_report(trades: List[Trade], equity_curve: List[Tuple[float, float]]) -> dict:
    """Generate a full performance report."""
    return {
        'total_trades': len(trades),
        'win_rate': win_rate(trades),
        'profit_factor': profit_factor(trades),
        'total_pnl': total_pnl(trades),
        'avg_rr': avg_rr_achieved(trades),
        'max_drawdown': max_drawdown(equity_curve),
        'sharpe_ratio': sharpe_ratio(equity_curve),
    }
