"""
Run a backtest on historical options data

Example usage:
    # Simple backtest
    python run_backtest.py --strategy simple --start 2024-01-01 --end 2024-03-31

    # LSM arbitrage strategy
    python run_backtest.py --strategy lsm_arbitrage --capital 100000 --start 2024-01-01

    # Early exercise premium strategy
    python run_backtest.py --strategy early_exercise --min-edge 3.5
"""

import argparse
from datetime import datetime, timedelta
import sys
import os

from backtesting.data_loader import BacktestDataProvider
from backtesting.engine import BacktestEngine, BacktestConfig
from backtesting.strategies import (
    simple_buy_and_hold,
    LSMArbitrageStrategy,
    EarlyExercisePremiumStrategy,
    VolatilitySkewStrategy
)


def main():
    parser = argparse.ArgumentParser(description='Backtest options trading strategies')
    parser.add_argument('--strategy', type=str, default='simple',
                       choices=['simple', 'lsm_arbitrage', 'early_exercise', 'vol_skew'],
                       help='Strategy to backtest')
    parser.add_argument('--tickers', type=str, nargs='+', default=['AAPL'],
                       help='Tickers to trade')
    parser.add_argument('--start', type=str, default='2024-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-03-31',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000,
                       help='Initial capital')
    parser.add_argument('--min-edge', type=float, default=3.0,
                       help='Minimum edge threshold %')
    parser.add_argument('--max-positions', type=int, default=10,
                       help='Maximum concurrent positions')

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"Options Strategy Backtester")
    print(f"{'='*70}\n")

    # Create backtest config
    config = BacktestConfig(
        initial_capital=args.capital,
        max_positions=args.max_positions,
        commission_per_contract=0.65,
        slippage_bps=5
    )

    # Load data
    print(f"Loading historical data for {', '.join(args.tickers)}...")
    data_provider = BacktestDataProvider(args.tickers, args.start, args.end)
    data_provider.load_all_data()

    # Create engine
    engine = BacktestEngine(config, data_provider)

    # Select strategy
    if args.strategy == 'simple':
        strategy = simple_buy_and_hold
        strategy_name = "Simple Buy & Hold"
    elif args.strategy == 'lsm_arbitrage':
        strategy = LSMArbitrageStrategy(edge_threshold_pct=args.min_edge)
        strategy_name = "LSM Arbitrage"
    elif args.strategy == 'early_exercise':
        strategy = EarlyExercisePremiumStrategy(min_premium_pct=args.min_edge)
        strategy_name = "Early Exercise Premium"
    elif args.strategy == 'vol_skew':
        strategy = VolatilitySkewStrategy(skew_threshold_pct=10.0)
        strategy_name = "Volatility Skew"

    print(f"Strategy: {strategy_name}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Capital: ${args.capital:,.2f}\n")

    # Run backtest
    engine.run_backtest(strategy, args.start, args.end)

    # Display results
    print(f"\n{'='*70}")
    print(f"BACKTEST RESULTS")
    print(f"{'='*70}\n")

    metrics = engine.get_performance_metrics()

    # Handle case when no trades executed
    if 'error' in metrics:
        print(f"No trades executed: {metrics['error']}")
        print("\nThis is normal for backtesting when:")
        print("  - Historical data simulation doesn't find edge")
        print("  - Strategy is too conservative")
        print("  - Time period is too short")
        return

    print(f"Performance Metrics:")
    print(f"  Total Trades:       {metrics['total_trades']}")
    print(f"  Winning Trades:     {metrics['winning_trades']}")
    print(f"  Losing Trades:      {metrics['losing_trades']}")
    print(f"  Win Rate:           {metrics['win_rate']:.1f}%")
    print(f"  Average Win:        ${metrics['avg_win']:.2f}")
    print(f"  Average Loss:       ${metrics['avg_loss']:.2f}")
    print(f"  Profit Factor:      {metrics['profit_factor']:.2f}")
    print()
    print(f"Returns:")
    print(f"  Total P&L:          ${metrics['total_pnl']:,.2f}")
    print(f"  Total Commission:   ${metrics['total_commission']:,.2f}")
    print(f"  Net P&L:            ${metrics['net_pnl']:,.2f}")
    print(f"  Total Return:       {metrics['total_return_pct']:.2f}%")
    print()
    print(f"Risk Metrics:")
    print(f"  Sharpe Ratio:       {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:       {metrics['max_drawdown_pct']:.2f}%")
    print()

    # Export results
    engine.export_results()

    print(f"\n{'='*70}")
    print(f"Detailed results exported to outputs/backtest/")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
