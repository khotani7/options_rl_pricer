"""
Quick script to buy 1 share of AAPL stock

Usage:
    python buy_aapl_stock.py --mode paper  # Paper trading (safe)
    python buy_aapl_stock.py --mode live   # Live trading (real money!)
"""

import argparse
from ib_insync import IB, Stock, MarketOrder, LimitOrder
import time

def buy_aapl_stock(mode='paper'):
    """Buy 1 share of AAPL stock"""

    # Determine port based on mode
    if mode == 'paper':
        port = 7497
        print("=" * 70)
        print("PAPER TRADING MODE (Safe - No Real Money)")
        print("=" * 70)
    elif mode == 'live':
        port = 7496
        print("=" * 70)
        print("⚠️  LIVE TRADING MODE - REAL MONEY WILL BE USED!")
        print("=" * 70)
        confirm = input("Are you SURE you want to use REAL money? Type 'YES' to confirm: ")
        if confirm != 'YES':
            print("Cancelled. Use --mode paper for safe testing.")
            return
    else:
        print(f"Invalid mode: {mode}. Use 'paper' or 'live'")
        return

    # Connect to IB Gateway
    ib = IB()

    print(f"\nConnecting to IB Gateway on port {port}...")
    try:
        ib.connect('127.0.0.1', port, clientId=123)
        print(f"✓ Connected to IB Gateway ({mode} mode)\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print(f"\nMake sure IB Gateway is running on port {port}")
        print(f"  - Paper trading: port 7497")
        print(f"  - Live trading: port 7496")
        return

    # Get account info
    account = ib.managedAccounts()[0]
    print(f"Account: {account}")

    # Get account value
    summary = ib.accountSummary()
    for item in summary:
        if item.tag == 'NetLiquidation':
            print(f"Account Value: ${float(item.value):,.2f} {item.currency}")
            break

    # Create AAPL stock contract
    print(f"\n{'=' * 70}")
    print("Creating AAPL Stock Order")
    print(f"{'=' * 70}")

    stock = Stock('AAPL', 'SMART', 'USD')
    ib.qualifyContracts(stock)
    print(f"✓ Contract qualified: {stock.symbol}")

    # Get current market price
    ticker = ib.reqMktData(stock, '', False, False)
    ib.sleep(3)  # Wait for data

    if ticker.last and ticker.last > 0:
        current_price = ticker.last
    elif ticker.close and ticker.close > 0:
        current_price = ticker.close
    else:
        print("⚠️  Could not get current price, using estimated $220")
        current_price = 220.0

    print(f"Current AAPL Price: ${current_price:.2f}")
    print(f"Order: BUY 1 share")
    print(f"Estimated Cost: ${current_price:.2f}")

    ib.cancelMktData(stock)

    # Ask for order type
    print(f"\nOrder Type:")
    print(f"  1. Market Order (buy at current market price)")
    print(f"  2. Limit Order (specify max price)")

    order_type = input("Choose order type (1 or 2): ").strip()

    if order_type == '1':
        # Market order
        order = MarketOrder('BUY', 1)
        order.tif = 'GTC'  # Good Till Cancelled to avoid after-hours issues
        print(f"\n✓ Market order created: BUY 1 AAPL at market price")
    elif order_type == '2':
        # Limit order
        limit_price = input(f"Enter limit price (e.g., {current_price:.2f}): ").strip()
        try:
            limit_price = float(limit_price)
            order = LimitOrder('BUY', 1, limit_price)
            order.tif = 'GTC'  # Good Till Cancelled
            print(f"\n✓ Limit order created: BUY 1 AAPL @ ${limit_price:.2f}")
        except ValueError:
            print("Invalid price. Using market order instead.")
            order = MarketOrder('BUY', 1)
            order.tif = 'GTC'
    else:
        print("Invalid choice. Using market order.")
        order = MarketOrder('BUY', 1)
        order.tif = 'GTC'

    # Final confirmation
    print(f"\n{'=' * 70}")
    print(f"READY TO SUBMIT ORDER")
    print(f"{'=' * 70}")
    print(f"Action: BUY")
    print(f"Symbol: AAPL")
    print(f"Quantity: 1 share")
    print(f"Order Type: {order.orderType}")
    if hasattr(order, 'lmtPrice'):
        print(f"Limit Price: ${order.lmtPrice:.2f}")
    print(f"Account: {account} ({mode} mode)")
    print(f"{'=' * 70}")

    proceed = input("\nSubmit order? (yes/no): ").strip().lower()

    if proceed != 'yes':
        print("Order cancelled.")
        ib.disconnect()
        return

    # Place order
    print("\nSubmitting order...")
    try:
        trade = ib.placeOrder(stock, order)
        print(f"✓ Order submitted!")
        print(f"  Order ID: {trade.order.orderId}")
        print(f"  Status: {trade.orderStatus.status}")

        # Wait for fill (max 60 seconds)
        print("\nWaiting for order to fill (max 60 seconds)...")
        for i in range(60):
            ib.sleep(1)
            if trade.orderStatus.status == 'Filled':
                print(f"\n✅ ORDER FILLED!")
                print(f"  Filled at: ${trade.orderStatus.avgFillPrice:.2f}")
                print(f"  Quantity: {trade.orderStatus.filled}")
                print(f"  Time: {trade.log[-1].time}")
                break
            elif trade.orderStatus.status in ['Cancelled', 'Rejected']:
                print(f"\n❌ Order {trade.orderStatus.status}")
                print(f"  Reason: {trade.orderStatus.whyHeld}")
                break

            if i % 5 == 0 and i > 0:
                print(f"  Still waiting... ({i}s) Status: {trade.orderStatus.status}")
        else:
            print(f"\n⏱️  Timeout - Order status: {trade.orderStatus.status}")
            print(f"  Check IB Gateway for order details")

    except Exception as e:
        print(f"❌ Error placing order: {e}")

    # Show current positions
    print(f"\n{'=' * 70}")
    print("Current Positions")
    print(f"{'=' * 70}")

    positions = ib.positions()
    if positions:
        for pos in positions:
            print(f"  {pos.contract.symbol}: {pos.position} shares @ ${pos.avgCost:.2f}")
            if hasattr(pos, 'marketValue'):
                print(f"    Market Value: ${pos.marketValue:.2f}")
            if hasattr(pos, 'unrealizedPNL'):
                print(f"    Unrealized P&L: ${pos.unrealizedPNL:.2f}")
    else:
        print("  No positions")

    # Disconnect
    print(f"\n{'=' * 70}")
    ib.disconnect()
    print("✓ Disconnected from IB Gateway")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Buy 1 share of AAPL stock')
    parser.add_argument('--mode', type=str, default='paper',
                       choices=['paper', 'live'],
                       help='Trading mode: paper (safe) or live (real money)')

    args = parser.parse_args()

    buy_aapl_stock(args.mode)
