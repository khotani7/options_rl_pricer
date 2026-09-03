#!/usr/bin/env python3
"""
Close all open positions in IB account

Useful for:
- End of day cleanup
- Emergency exit
- Rebalancing

Usage:
    python close_all_positions.py --mode paper
    python close_all_positions.py --mode live --confirm
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.ib_connector import IBConnector, IBConfig


def main():
    parser = argparse.ArgumentParser(description='Close all open positions')
    parser.add_argument('--mode', type=str, default='paper',
                       choices=['paper', 'live'],
                       help='Trading mode')
    parser.add_argument('--confirm', action='store_true',
                       help='Skip confirmation prompt')
    args = parser.parse_args()

    port = 7496 if args.mode == 'live' else 7497

    # Create connector
    ib_config = IBConfig(port=port, client_id=1)
    connector = IBConnector(ib_config)

    if not connector.connect():
        print("Failed to connect to IB Gateway")
        sys.exit(1)

    try:
        # Get all positions
        positions = connector.get_positions()

        if not positions:
            print("No open positions to close")
            return

        print(f"\nFound {len(positions)} open position(s):")
        print("="*70)

        total_unrealized = 0
        for pos in positions:
            contract = pos['contract']
            qty = pos['quantity']
            avg_cost = pos['avg_cost']
            unrealized = pos['unrealized_pnl']
            total_unrealized += unrealized

            print(f"{contract.symbol} {contract.strike if hasattr(contract, 'strike') else ''}")
            print(f"  Qty: {qty} | Avg Cost: ${avg_cost:.2f} | Unrealized P&L: ${unrealized:,.2f}")

        print("="*70)
        print(f"Total Unrealized P&L: ${total_unrealized:,.2f}")
        print()

        # Confirm
        if not args.confirm:
            if args.mode == 'live':
                confirm = input("⚠️  LIVE MODE - Close all positions with REAL MONEY? (type 'YES'): ")
                if confirm != 'YES':
                    print("Cancelled")
                    return
            else:
                confirm = input("Close all positions? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("Cancelled")
                    return

        # Close all positions
        print("\nClosing positions...")
        for pos in positions:
            contract = pos['contract']
            qty = pos['quantity']

            # Determine action (opposite of current position)
            action = 'SELL' if qty > 0 else 'BUY'

            print(f"  {action} {abs(qty)}x {contract.symbol}...")

            try:
                trade = connector.place_order(
                    contract=contract,
                    action=action,
                    quantity=abs(qty),
                    order_type='MKT',  # Use market orders for quick exit
                    transmit=True
                )

                # Wait for fill
                filled = connector.wait_for_fill(trade, timeout=30)

                if filled:
                    print(f"    ✓ Closed @ ${trade.orderStatus.avgFillPrice:.2f}")
                else:
                    print(f"    ✗ Not filled (status: {trade.orderStatus.status})")

            except Exception as e:
                print(f"    ✗ Error: {e}")

        print("\n✓ Position closing complete")

    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
