"""
View all positions in IB account (stocks and options)

Usage:
    python view_positions.py --mode paper
    python view_positions.py --mode live
"""

import argparse
from ib_insync import IB
from datetime import datetime

def view_positions(mode='paper'):
    """View all positions in IB account"""

    # Determine port based on mode
    port = 7497 if mode == 'paper' else 7496

    print("=" * 80)
    print(f"IB Account Positions ({mode.upper()} mode)")
    print("=" * 80)

    # Connect to IB Gateway
    ib = IB()

    print(f"\nConnecting to IB Gateway on port {port}...")
    try:
        ib.connect('127.0.0.1', port, clientId=124)
        print(f"✓ Connected\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print(f"\nMake sure IB Gateway is running on port {port}")
        return

    # Get account info
    account = ib.managedAccounts()[0]
    print(f"Account: {account}")

    # Get account value
    summary = ib.accountSummary()
    for item in summary:
        if item.tag == 'NetLiquidation':
            print(f"Net Liquidation: ${float(item.value):,.2f} {item.currency}")
        elif item.tag == 'TotalCashValue':
            print(f"Cash: ${float(item.value):,.2f} {item.currency}")

    print(f"\n{'=' * 80}")
    print("POSITIONS")
    print(f"{'=' * 80}\n")

    # Get all positions
    positions = ib.positions()

    if not positions:
        print("No positions")
        ib.disconnect()
        return

    # Separate stocks and options
    stock_positions = []
    option_positions = []

    for pos in positions:
        if hasattr(pos.contract, 'strike'):  # It's an option
            option_positions.append(pos)
        else:  # It's a stock
            stock_positions.append(pos)

    # Display stock positions
    if stock_positions:
        print("📊 STOCK POSITIONS")
        print("-" * 80)
        for pos in stock_positions:
            print(f"\n{pos.contract.symbol}")
            print(f"  Quantity: {pos.position:,.0f} shares")
            print(f"  Avg Cost: ${pos.avgCost:.2f}")
            if hasattr(pos, 'marketValue') and pos.marketValue:
                print(f"  Market Value: ${pos.marketValue:,.2f}")
            if hasattr(pos, 'unrealizedPNL') and pos.unrealizedPNL:
                pnl_pct = (pos.unrealizedPNL / (abs(pos.position) * pos.avgCost)) * 100
                print(f"  Unrealized P&L: ${pos.unrealizedPNL:,.2f} ({pnl_pct:+.2f}%)")
        print()

    # Display option positions
    if option_positions:
        print("📈 OPTION POSITIONS")
        print("-" * 80)

        for pos in option_positions:
            contract = pos.contract

            # Determine if it's a call or put
            right = "CALL" if contract.right == 'C' else "PUT"

            # Format expiration date
            exp_str = contract.lastTradeDateOrContractMonth
            if len(exp_str) == 8:  # Format: YYYYMMDD
                exp_date = f"{exp_str[0:4]}-{exp_str[4:6]}-{exp_str[6:8]}"
            else:
                exp_date = exp_str

            # Calculate days to expiry
            try:
                exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
                days_to_exp = (exp_dt - datetime.now()).days
            except:
                days_to_exp = "?"

            print(f"\n{contract.symbol} ${contract.strike:.0f} {right} exp {exp_date} ({days_to_exp} days)")

            # Show if long or short
            if pos.position > 0:
                print(f"  Position: LONG {abs(pos.position):.0f} contracts")
            else:
                print(f"  Position: SHORT {abs(pos.position):.0f} contracts")

            print(f"  Avg Cost: ${pos.avgCost:.2f} per share (${pos.avgCost * 100:.2f} per contract)")

            if hasattr(pos, 'marketValue') and pos.marketValue:
                print(f"  Market Value: ${pos.marketValue:,.2f}")

            if hasattr(pos, 'unrealizedPNL') and pos.unrealizedPNL:
                # Calculate P&L percentage
                cost_basis = abs(pos.position) * pos.avgCost * 100
                if cost_basis > 0:
                    pnl_pct = (pos.unrealizedPNL / cost_basis) * 100
                    print(f"  Unrealized P&L: ${pos.unrealizedPNL:,.2f} ({pnl_pct:+.2f}%)")
                else:
                    print(f"  Unrealized P&L: ${pos.unrealizedPNL:,.2f}")
        print()

    # Summary
    print(f"{'=' * 80}")
    print(f"SUMMARY")
    print(f"{'=' * 80}")
    print(f"Stock Positions: {len(stock_positions)}")
    print(f"Option Positions: {len(option_positions)}")
    print(f"Total Positions: {len(positions)}")

    # Calculate total P&L
    total_pnl = sum(pos.unrealizedPNL for pos in positions if hasattr(pos, 'unrealizedPNL') and pos.unrealizedPNL)
    if total_pnl:
        print(f"\nTotal Unrealized P&L: ${total_pnl:,.2f}")

    print(f"{'=' * 80}\n")

    # Disconnect
    ib.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='View IB account positions')
    parser.add_argument('--mode', type=str, default='paper',
                       choices=['paper', 'live'],
                       help='Trading mode: paper or live')

    args = parser.parse_args()

    view_positions(args.mode)
