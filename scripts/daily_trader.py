#!/usr/bin/env python3
"""
Daily Automated Options Trader

Runs once per day at market open:
1. Scans for edge opportunities
2. Places trades with position sizing
3. Monitors positions with stop losses
4. Closes at end of day or when targets hit

Usage:
    # Run once (manual)
    python daily_trader.py --mode paper --tickers TSLA AAPL MU

    # Schedule daily at 9:35 AM ET (5 min after market open)
    # Add to crontab: 35 9 * * 1-5 cd /path/to/options_rl_pricer && PYTHONPATH=. python scripts/daily_trader.py --mode paper

Configuration:
    --mode: paper or live
    --tickers: Space-separated list of tickers
    --min-edge: Minimum edge % to trade (default: 10%)
    --max-position-size: Max % of account per position (default: 5%)
    --stop-loss: Stop loss % (default: 30%)
    --profit-target: Take profit % (default: 50%)
    --max-positions: Max concurrent positions (default: 10)
    --close-eod: Close all positions at end of day (default: True)
"""

import argparse
import sys
import os
import time
from datetime import datetime, time as dt_time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.automated_trader import AutomatedTrader, RiskLimits, TradingConfig
from trading.ib_connector import IBConfig


def is_market_hours() -> bool:
    """Check if currently in market hours (9:30 AM - 4:00 PM ET)"""
    now = datetime.now()

    # Check if weekend
    if now.weekday() >= 5:
        return False

    # Check time (9:30 AM - 4:00 PM ET)
    # TODO: Adjust for your timezone
    market_open = dt_time(9, 30)
    market_close = dt_time(16, 0)

    current_time = now.time()
    return market_open <= current_time <= market_close


def main():
    parser = argparse.ArgumentParser(description='Daily automated options trader')
    parser.add_argument('--mode', type=str, default='paper',
                       choices=['paper', 'live'],
                       help='Trading mode (default: paper)')
    parser.add_argument('--tickers', type=str, nargs='+',
                       default=['AAPL', 'TSLA', 'MU', 'SPY', 'QQQ'],
                       help='Tickers to trade')
    parser.add_argument('--min-edge', type=float, default=10.0,
                       help='Minimum edge threshold % (default: 10.0)')
    parser.add_argument('--max-position-size', type=float, default=5.0,
                       help='Max position size as % of account (default: 5.0)')
    parser.add_argument('--stop-loss', type=float, default=30.0,
                       help='Stop loss % per position (default: 30.0)')
    parser.add_argument('--profit-target', type=float, default=50.0,
                       help='Take profit % (default: 50.0)')
    parser.add_argument('--max-positions', type=int, default=10,
                       help='Maximum concurrent positions (default: 10)')
    parser.add_argument('--max-daily-loss', type=float, default=2.0,
                       help='Max daily loss % circuit breaker (default: 2.0)')
    parser.add_argument('--close-eod', action='store_true', default=True,
                       help='Close all positions at end of day (default: True)')
    parser.add_argument('--scan-only', action='store_true',
                       help='Only scan and report, do not place trades')

    args = parser.parse_args()

    # Safety check: market hours
    if not is_market_hours():
        print(f"Market is currently closed. Options trade 9:30 AM - 4:00 PM ET (Mon-Fri)")
        print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if args.scan_only:
            print("Continuing with scan-only mode...")
        else:
            print("Exiting. Use --scan-only to scan anyway.")
            sys.exit(0)

    # Determine port
    port = 7496 if args.mode == 'live' else 7497

    # Live trading confirmation
    if args.mode == 'live':
        print("\n" + "="*70)
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("="*70)
        print("You are about to trade with REAL MONEY.")
        print(f"Tickers: {', '.join(args.tickers)}")
        print(f"Max position size: {args.max_position_size}%")
        print(f"Stop loss: {args.stop_loss}%")
        print(f"Max daily loss: {args.max_daily_loss}%")
        print()
        confirmation = input("Type 'I UNDERSTAND THE RISKS' to continue: ")
        if confirmation != "I UNDERSTAND THE RISKS":
            print("\nExiting...")
            sys.exit(0)

    print("\n" + "="*70)
    print(f"Daily Options Trader - {args.mode.upper()} Mode")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tickers: {', '.join(args.tickers)}")
    print(f"Min edge: {args.min_edge}%")
    print(f"Position size: {args.max_position_size}%")
    print(f"Stop loss: {args.stop_loss}%")
    print(f"Profit target: {args.profit_target}%")
    print(f"Max positions: {args.max_positions}")
    print(f"Close EOD: {args.close_eod}")
    print("="*70 + "\n")

    # Create configurations
    ib_config = IBConfig(
        host='127.0.0.1',
        port=port,
        client_id=1
    )

    risk_limits = RiskLimits(
        max_positions=args.max_positions,
        max_daily_loss=args.max_daily_loss / 100.0,
        min_edge_threshold_pct=args.min_edge,
        stop_loss_pct=args.stop_loss / 100.0,
        max_position_size=args.max_position_size / 100.0,
        max_portfolio_exposure=0.20
    )

    trading_config = TradingConfig(
        mode=args.mode,
        tickers=args.tickers,
        scan_interval_minutes=60,  # Scan every hour during market
        max_trades_per_day=20,
        use_limit_orders=True,
        log_file=f'outputs/trading_log_{args.mode}_{datetime.now().strftime("%Y%m%d")}.json'
    )

    # Create trader
    trader = AutomatedTrader(
        ib_config=ib_config,
        risk_limits=risk_limits,
        trading_config=trading_config,
        use_mock=False
    )

    if args.scan_only:
        print("SCAN-ONLY MODE: Will not place trades\n")
        # TODO: Implement scan-only mode
        # Just run scanner and print results without placing orders
        from scripts.edge_scanner import scan_option_chain
        for ticker in args.tickers:
            print(f"\nScanning {ticker}...")
            df = scan_option_chain(ticker, min_volume=5,
                                  min_edge_pct=args.min_edge,
                                  min_moneyness=0.85, max_moneyness=1.15)
            if df is not None and not df.empty:
                print(f"Found {len(df)} opportunities:")
                for i, row in df.head(5).iterrows():
                    print(f"  {row['signal']} ${row['strike']:.0f} @ ${row['market_mid']:.2f} "
                          f"({row['edge_pct']:+.1f}% edge)")
        return

    # Start trader
    try:
        trader.start()
    except KeyboardInterrupt:
        print("\n\nStopping trader...")
        trader.stop()
    except Exception as e:
        print(f"\n\nError: {e}")
        trader.stop()
        raise


if __name__ == "__main__":
    main()
