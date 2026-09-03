"""
Run the automated options trader

SETUP INSTRUCTIONS:
1. Install TWS or IB Gateway from Interactive Brokers
2. Enable API in TWS: File → Global Configuration → API → Settings
   - Enable ActiveX and Socket Clients
   - Add 127.0.0.1 to Trusted IPs
   - Set Socket port: 7497 (paper) or 7496 (live)
3. Install ib_insync: pip install ib_insync
4. Start TWS/Gateway
5. Run this script

Example usage:
    # Paper trading (recommended to start)
    python run_trader.py --mode paper

    # Mock mode (no IB connection, for testing)
    python run_trader.py --mode mock

    # Live trading (use with caution!)
    python run_trader.py --mode live

    # Custom parameters
    python run_trader.py --mode paper --max-positions 5 --min-edge 4.0
"""

import argparse
import sys

from trading.automated_trader import AutomatedTrader, RiskLimits, TradingConfig
from trading.ib_connector import IBConfig


def main():
    parser = argparse.ArgumentParser(description='Run automated options trader')
    parser.add_argument('--mode', type=str, default='mock',
                       choices=['mock', 'paper', 'live'],
                       help='Trading mode')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                       help='IB Gateway host')
    parser.add_argument('--port', type=int, default=None,
                       help='IB Gateway port (default: 7497 for paper, 7496 for live)')
    parser.add_argument('--tickers', type=str, nargs='+', default=['AAPL', 'XOM', 'JPM'],
                       help='Tickers to trade')
    parser.add_argument('--scan-interval', type=int, default=15,
                       help='Scan interval in minutes')
    parser.add_argument('--max-positions', type=int, default=10,
                       help='Maximum concurrent positions')
    parser.add_argument('--min-edge', type=float, default=3.0,
                       help='Minimum edge threshold %')
    parser.add_argument('--max-daily-loss', type=float, default=2.0,
                       help='Max daily loss % (circuit breaker)')
    parser.add_argument('--stop-loss', type=float, default=30.0,
                       help='Stop loss % per position')
    parser.add_argument('--max-position-size', type=float, default=5.0,
                       help='Max position size as % of account (default: 5.0)')
    parser.add_argument('--client-id', type=int, default=1,
                       help='IB API client ID (use different IDs for multiple connections)')

    args = parser.parse_args()

    # Determine port
    if args.port is None:
        if args.mode == 'live':
            port = 7496
        else:
            port = 7497
    else:
        port = args.port

    # Display warning for live trading
    if args.mode == 'live':
        print("\n" + "="*70)
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("="*70)
        print("You are about to trade with REAL MONEY.")
        print("Make sure you have:")
        print("  1. Thoroughly backtested your strategy")
        print("  2. Paper traded for at least 1 month")
        print("  3. Set appropriate risk limits")
        print("  4. Monitored the system continuously")
        print()
        confirmation = input("Type 'I UNDERSTAND THE RISKS' to continue: ")

        if confirmation != "I UNDERSTAND THE RISKS":
            print("\nExiting...")
            sys.exit(0)

    # Create configurations
    ib_config = IBConfig(
        host=args.host,
        port=port,
        client_id=args.client_id
    )

    risk_limits = RiskLimits(
        max_positions=args.max_positions,
        max_daily_loss=args.max_daily_loss / 100.0,
        min_edge_threshold_pct=args.min_edge,
        stop_loss_pct=args.stop_loss / 100.0,
        max_position_size=args.max_position_size / 100.0,
        max_portfolio_exposure=0.20  # 20% total exposure
    )

    trading_config = TradingConfig(
        mode=args.mode,
        tickers=args.tickers,
        scan_interval_minutes=args.scan_interval,
        max_trades_per_day=10,
        use_limit_orders=True,
        log_file=f'outputs/trading_log_{args.mode}.json'
    )

    # Create and start trader
    use_mock = (args.mode == 'mock')

    trader = AutomatedTrader(
        ib_config=ib_config,
        risk_limits=risk_limits,
        trading_config=trading_config,
        use_mock=use_mock
    )

    # Start trading
    trader.start()


if __name__ == "__main__":
    main()
