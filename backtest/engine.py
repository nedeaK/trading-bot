"""Event-driven backtest engine with multi-timeframe support.

Iterates through LTF candles, generates signals using the top-down
pipeline, executes trades, and tracks portfolio state.
"""

from typing import Dict, List, Optional

from config.settings import BacktestConfig, Config, SMCConfig, RiskConfig
from data.models import Candle, Signal
from backtest.executor import check_exits, try_fill_signal
from backtest.metrics import generate_report
from backtest.portfolio import Portfolio, record_equity
from signals.generator import generate_signals


def run_backtest(
    htf_candles: List[Candle],
    mtf_candles: List[Candle],
    ltf_candles: List[Candle],
    config: Optional[Config] = None,
) -> Dict:
    """Run a full backtest on historical data.

    Iterates through LTF candles sequentially:
    1. Check exits on current candle (stop/take profit)
    2. Try to fill pending signals
    3. Generate new signals using the top-down pipeline
    4. Record equity

    Args:
        htf_candles: Higher timeframe candles.
        mtf_candles: Medium timeframe candles.
        ltf_candles: Lower timeframe candles (iteration timeframe).
        config: Full configuration (defaults used if None).

    Returns:
        Performance report dictionary.
    """
    if config is None:
        config = Config()

    smc = config.smc
    risk = config.risk
    bt = config.backtest

    portfolio = Portfolio(cash=bt.initial_balance)
    pending_signals: List[Signal] = []

    for i, candle in enumerate(ltf_candles):
        # 1. Check exits
        portfolio = check_exits(portfolio, candle, slippage=bt.slippage)

        # 2. Try to fill pending signals
        unfilled: List[Signal] = []
        for signal in pending_signals:
            new_portfolio = try_fill_signal(
                portfolio, signal, candle,
                slippage=bt.slippage,
                commission=bt.commission,
                risk_percent=risk.risk_percent,
                max_position_pct=risk.max_position_size,
            )
            if new_portfolio is portfolio:
                unfilled.append(signal)  # Not filled yet
            else:
                portfolio = new_portfolio
        pending_signals = unfilled

        # 3. Generate new signals (use candles up to current point)
        # Only generate if no pending signals and no open positions
        if not pending_signals and portfolio.num_open_positions == 0:
            # Use all available candles up to proportional point
            htf_slice = _proportional_slice(htf_candles, i, len(ltf_candles))
            mtf_slice = _proportional_slice(mtf_candles, i, len(ltf_candles))
            ltf_slice = ltf_candles[:i + 1]

            if len(htf_slice) >= 5 and len(mtf_slice) >= 5:
                new_signals = generate_signals(
                    htf_slice, mtf_slice, ltf_slice, smc,
                )
                pending_signals.extend(new_signals)

        # 4. Record equity
        equity = portfolio.cash + sum(
            candle.close * p.shares for p in portfolio.positions
        )
        portfolio = record_equity(portfolio, candle.timestamp, equity)

    # Close any remaining positions at last candle price
    if ltf_candles and portfolio.positions:
        last_price = ltf_candles[-1].close
        from backtest.portfolio import close_position
        for i in range(len(portfolio.positions) - 1, -1, -1):
            portfolio = close_position(
                portfolio, i, last_price, ltf_candles[-1].timestamp,
            )

    trades = list(portfolio.trades)
    equity_curve = list(portfolio.equity_curve)

    report = generate_report(trades, equity_curve)
    report['final_equity'] = portfolio.cash
    report['initial_balance'] = bt.initial_balance
    report['return_pct'] = (
        (portfolio.cash - bt.initial_balance) / bt.initial_balance * 100
        if bt.initial_balance > 0 else 0.0
    )

    return report


def _proportional_slice(
    candles: List[Candle],
    current_ltf_index: int,
    total_ltf: int,
) -> List[Candle]:
    """Get a proportional slice of higher-TF candles.

    Maps the current position in LTF to a proportional position
    in the higher timeframe data.
    """
    if not candles or total_ltf == 0:
        return []
    ratio = (current_ltf_index + 1) / total_ltf
    end_idx = max(1, int(len(candles) * ratio))
    return candles[:end_idx]
