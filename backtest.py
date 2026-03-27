"""Entry point for running SMC backtests.

Usage:
    python backtest.py
    python backtest.py --symbol AAPL --start 2022-01-01 --end 2024-12-31
"""

import argparse
import sys

from config.settings import Config, TimeframeConfig, SMCConfig, RiskConfig, BacktestConfig
from config.constants import Timeframe
from data.stock_repository import StockDataRepository
from backtest.engine import run_backtest


def main():
    parser = argparse.ArgumentParser(description="SMC Trading Bot Backtest")
    parser.add_argument("--symbol", default="SPY", help="Ticker symbol")
    parser.add_argument("--start", default="2022-01-01", help="Start date")
    parser.add_argument("--end", default="2024-12-31", help="End date")
    parser.add_argument("--htf", default="1d", help="Higher timeframe")
    parser.add_argument("--mtf", default="1h", help="Medium timeframe")
    parser.add_argument("--ltf", default="15m", help="Lower timeframe")
    parser.add_argument("--balance", type=float, default=100_000, help="Initial balance")
    parser.add_argument("--risk", type=float, default=0.02, help="Risk per trade")
    args = parser.parse_args()

    # Build config
    config = Config(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        timeframes=TimeframeConfig(
            htf=Timeframe(args.htf),
            mtf=Timeframe(args.mtf),
            ltf=Timeframe(args.ltf),
        ),
        smc=SMCConfig(),
        risk=RiskConfig(risk_percent=args.risk),
        backtest=BacktestConfig(initial_balance=args.balance),
    )

    print(f"SMC Backtest: {config.symbol} ({config.start_date} to {config.end_date})")
    print(f"Timeframes: HTF={args.htf}, MTF={args.mtf}, LTF={args.ltf}")
    print(f"Balance: ${config.backtest.initial_balance:,.0f} | Risk: {config.risk.risk_percent:.1%}")
    print("-" * 60)

    # Fetch data
    repo = StockDataRepository()
    try:
        htf_candles = repo.get_historical_data(
            config.symbol, config.timeframes.htf,
            config.start_date, config.end_date,
        )
        mtf_candles = repo.get_historical_data(
            config.symbol, config.timeframes.mtf,
            config.start_date, config.end_date,
        )
        ltf_candles = repo.get_historical_data(
            config.symbol, config.timeframes.ltf,
            config.start_date, config.end_date,
        )
    except Exception as e:
        print(f"Error fetching data: {e}")
        sys.exit(1)

    print(f"Data loaded: HTF={len(htf_candles)}, MTF={len(mtf_candles)}, LTF={len(ltf_candles)} candles")

    # Run backtest
    report = run_backtest(htf_candles, mtf_candles, ltf_candles, config)

    # Print report
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Trades:    {report['total_trades']}")
    print(f"Win Rate:        {report['win_rate']:.1%}")
    print(f"Profit Factor:   {report['profit_factor']:.2f}")
    print(f"Total PnL:       ${report['total_pnl']:,.2f}")
    print(f"Avg R:R:         {report['avg_rr']:.2f}")
    print(f"Max Drawdown:    {report['max_drawdown']:.1%}")
    print(f"Sharpe Ratio:    {report['sharpe_ratio']:.2f}")
    print(f"Final Equity:    ${report['final_equity']:,.2f}")
    print(f"Return:          {report['return_pct']:.2f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
