"""
Hedge SNOW option positions to lock in profits

Usage:
    python hedge_positions.py --mode paper --ticker SNOW
    python hedge_positions.py --mode live --ticker SNOW
"""

import argparse
from ib_insync import IB, Stock, Option, MarketOrder, LimitOrder
from datetime import datetime

def hedge_positions(ticker, mode='paper'):
    """Hedge option positions to lock in profits"""

    port = 7497 if mode == 'paper' else 7496

    print("=" * 80)
    print(f"HEDGE POSITIONS - {ticker.upper()} ({mode.upper()} mode)")
    print("=" * 80)

    # Connect to IB
    ib = IB()
    print(f"\nConnecting to IB Gateway on port {port}...")
    try:
        ib.connect('127.0.0.1', port, clientId=125)
        print(f"✓ Connected\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return

    # Get account info
    account = ib.managedAccounts()[0]
    print(f"Account: {account}")

    # Get account value
    summary = ib.accountSummary()
    for item in summary:
        if item.tag == 'NetLiquidation':
            print(f"Account Value: ${float(item.value):,.2f}\n")
            break

    # Get all positions
    positions = ib.positions()

    # Filter for ticker options
    option_positions = [pos for pos in positions
                       if hasattr(pos.contract, 'strike')
                       and pos.contract.symbol == ticker.upper()]

    if not option_positions:
        print(f"No {ticker.upper()} option positions found.")
        ib.disconnect()
        return

    # Display current positions
    print(f"{'=' * 80}")
    print(f"CURRENT {ticker.upper()} OPTION POSITIONS")
    print(f"{'=' * 80}\n")

    total_pnl = 0

    for i, pos in enumerate(option_positions, 1):
        contract = pos.contract
        right = "CALL" if contract.right == 'C' else "PUT"

        exp_str = contract.lastTradeDateOrContractMonth
        if len(exp_str) == 8:
            exp_date = f"{exp_str[0:4]}-{exp_str[4:6]}-{exp_str[6:8]}"
        else:
            exp_date = exp_str

        try:
            exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
            days_to_exp = (exp_dt - datetime.now()).days
        except:
            days_to_exp = "?"

        position_type = "LONG" if pos.position > 0 else "SHORT"

        print(f"Position {i}:")
        print(f"  {contract.symbol} ${contract.strike:.0f} {right} exp {exp_date} ({days_to_exp} days)")
        print(f"  {position_type} {abs(pos.position):.0f} contracts")
        print(f"  Avg Cost: ${pos.avgCost:.2f}/share (${pos.avgCost * 100:.2f}/contract)")

        if hasattr(pos, 'unrealizedPNL') and pos.unrealizedPNL:
            cost_basis = abs(pos.position) * pos.avgCost * 100
            pnl_pct = (pos.unrealizedPNL / cost_basis) * 100 if cost_basis > 0 else 0
            print(f"  Unrealized P&L: ${pos.unrealizedPNL:,.2f} ({pnl_pct:+.2f}%)")
            total_pnl += pos.unrealizedPNL
        print()

    print(f"Total Unrealized P&L: ${total_pnl:,.2f}\n")

    # Hedging strategies
    print(f"{'=' * 80}")
    print("HEDGING STRATEGIES")
    print(f"{'=' * 80}\n")

    print("Choose a hedging strategy:\n")
    print("1. CLOSE ALL POSITIONS (Take profits now)")
    print("   - Immediately exit all positions at market")
    print("   - Locks in current P&L")
    print("   - Best if: You want to cash out now\n")

    print("2. BUY PROTECTIVE PUTS (Downside protection)")
    print("   - Buy puts below current price")
    print("   - Limits losses if stock falls")
    print("   - Keeps upside if stock rises")
    print("   - Best if: You have LONG calls or stock\n")

    print("3. SELL COVERED CALLS (Cap upside, collect premium)")
    print("   - Sell calls above current price")
    print("   - Collect premium immediately")
    print("   - Caps gains if stock rises")
    print("   - Best if: You have LONG stock or calls\n")

    print("4. OPPOSITE POSITION (Delta hedge)")
    print("   - Open opposite position to neutralize")
    print("   - If you're SHORT puts → BUY puts")
    print("   - If you're LONG calls → SELL calls")
    print("   - Locks in current value\n")

    print("5. STOCK HEDGE (Use underlying stock)")
    print("   - If LONG calls → SHORT stock")
    print("   - If SHORT puts → LONG stock")
    print("   - Neutralizes delta exposure\n")

    print("6. COLLAR STRATEGY (Buy put + Sell call)")
    print("   - Buy protective put + Sell covered call")
    print("   - Limits both upside and downside")
    print("   - Often zero or low cost\n")

    choice = input("Select strategy (1-6) or 'q' to quit: ").strip()

    if choice == 'q':
        print("Cancelled.")
        ib.disconnect()
        return

    # Execute strategy
    if choice == '1':
        close_all_positions(ib, option_positions, ticker, mode)
    elif choice == '2':
        buy_protective_puts(ib, option_positions, ticker, mode)
    elif choice == '3':
        sell_covered_calls(ib, option_positions, ticker, mode)
    elif choice == '4':
        opposite_position(ib, option_positions, ticker, mode)
    elif choice == '5':
        stock_hedge(ib, option_positions, ticker, mode)
    elif choice == '6':
        collar_strategy(ib, option_positions, ticker, mode)
    else:
        print("Invalid choice.")

    ib.disconnect()


def close_all_positions(ib, positions, ticker, mode):
    """Close all option positions immediately"""
    print(f"\n{'=' * 80}")
    print("CLOSE ALL POSITIONS")
    print(f"{'=' * 80}\n")

    print(f"This will close {len(positions)} {ticker.upper()} option position(s) at MARKET price.\n")

    confirm = input("Are you sure? Type 'YES' to confirm: ").strip()
    if confirm != 'YES':
        print("Cancelled.")
        return

    print("\nClosing positions...\n")

    for pos in positions:
        contract = pos.contract

        # Determine action (reverse of current position)
        if pos.position > 0:
            action = 'SELL'  # We're long, so sell to close
        else:
            action = 'BUY'   # We're short, so buy to close

        quantity = abs(pos.position)

        print(f"{action} {quantity:.0f} {contract.symbol} ${contract.strike:.0f} {contract.right} {contract.lastTradeDateOrContractMonth}")

        try:
            order = MarketOrder(action, quantity)
            order.tif = 'GTC'
            trade = ib.placeOrder(contract, order)

            print(f"  ✓ Order placed (ID: {trade.order.orderId})")

            # Wait for fill
            ib.sleep(2)
            if trade.orderStatus.status == 'Filled':
                print(f"  ✓ Filled at ${trade.orderStatus.avgFillPrice:.2f}")
            else:
                print(f"  Status: {trade.orderStatus.status}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        print()

    print("✓ All positions closed (or orders submitted)")


def buy_protective_puts(ib, positions, ticker, mode):
    """Buy protective puts"""
    print(f"\n{'=' * 80}")
    print("BUY PROTECTIVE PUTS")
    print(f"{'=' * 80}\n")

    # Get current stock price
    stock = Stock(ticker.upper(), 'SMART', 'USD')
    ib.qualifyContracts(stock)
    ticker_obj = ib.reqMktData(stock, '', False, False)
    ib.sleep(3)

    if ticker_obj.last and ticker_obj.last > 0:
        current_price = ticker_obj.last
    elif ticker_obj.close and ticker_obj.close > 0:
        current_price = ticker_obj.close
    else:
        current_price = float(input(f"Enter current {ticker.upper()} stock price: $"))

    ib.cancelMktData(stock)

    print(f"Current {ticker.upper()} price: ${current_price:.2f}\n")

    # Suggest put strikes
    put_5pct_otm = current_price * 0.95
    put_10pct_otm = current_price * 0.90

    print("Suggested protective put strikes:")
    print(f"  1. ${put_5pct_otm:.0f} (5% below current)")
    print(f"  2. ${put_10pct_otm:.0f} (10% below current)")
    print(f"  3. Custom strike\n")

    strike_choice = input("Choose strike (1-3): ").strip()

    if strike_choice == '1':
        strike = put_5pct_otm
    elif strike_choice == '2':
        strike = put_10pct_otm
    elif strike_choice == '3':
        strike = float(input("Enter strike price: $").strip())
    else:
        print("Invalid choice.")
        return

    # Round strike to nearest $5
    strike = round(strike / 5) * 5

    expiry = input("Enter expiration date (YYYYMMDD, e.g., 20260930): ").strip()
    quantity = int(input("Number of put contracts to buy: ").strip())

    print(f"\nBUY {quantity} PUT ${strike:.0f} exp {expiry}")
    confirm = input("Confirm? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("Cancelled.")
        return

    # Create option contract
    put = Option(ticker.upper(), expiry, strike, 'P', 'SMART')
    ib.qualifyContracts(put)

    # Place order
    order = MarketOrder('BUY', quantity)
    order.tif = 'GTC'

    try:
        trade = ib.placeOrder(put, order)
        print(f"✓ Order placed (ID: {trade.order.orderId})")
        print(f"Status: {trade.orderStatus.status}")
    except Exception as e:
        print(f"✗ Error: {e}")


def sell_covered_calls(ib, positions, ticker, mode):
    """Sell covered calls"""
    print(f"\n{'=' * 80}")
    print("SELL COVERED CALLS")
    print(f"{'=' * 80}\n")

    # Get current stock price
    stock = Stock(ticker.upper(), 'SMART', 'USD')
    ib.qualifyContracts(stock)
    ticker_obj = ib.reqMktData(stock, '', False, False)
    ib.sleep(3)

    if ticker_obj.last and ticker_obj.last > 0:
        current_price = ticker_obj.last
    elif ticker_obj.close and ticker_obj.close > 0:
        current_price = ticker_obj.close
    else:
        current_price = float(input(f"Enter current {ticker.upper()} stock price: $"))

    ib.cancelMktData(stock)

    print(f"Current {ticker.upper()} price: ${current_price:.2f}\n")

    # Suggest call strikes
    call_5pct_otm = current_price * 1.05
    call_10pct_otm = current_price * 1.10

    print("Suggested covered call strikes:")
    print(f"  1. ${call_5pct_otm:.0f} (5% above current - more premium)")
    print(f"  2. ${call_10pct_otm:.0f} (10% above current - more upside)")
    print(f"  3. Custom strike\n")

    strike_choice = input("Choose strike (1-3): ").strip()

    if strike_choice == '1':
        strike = call_5pct_otm
    elif strike_choice == '2':
        strike = call_10pct_otm
    elif strike_choice == '3':
        strike = float(input("Enter strike price: $").strip())
    else:
        print("Invalid choice.")
        return

    strike = round(strike / 5) * 5

    expiry = input("Enter expiration date (YYYYMMDD, e.g., 20260930): ").strip()
    quantity = int(input("Number of call contracts to sell: ").strip())

    print(f"\nSELL {quantity} CALL ${strike:.0f} exp {expiry}")
    print("⚠️  This caps your upside at ${strike:.0f}")
    confirm = input("Confirm? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("Cancelled.")
        return

    # Create option contract
    call = Option(ticker.upper(), expiry, strike, 'C', 'SMART')
    ib.qualifyContracts(call)

    # Place order
    order = MarketOrder('SELL', quantity)
    order.tif = 'GTC'

    try:
        trade = ib.placeOrder(call, order)
        print(f"✓ Order placed (ID: {trade.order.orderId})")
        print(f"Status: {trade.orderStatus.status}")
    except Exception as e:
        print(f"✗ Error: {e}")


def opposite_position(ib, positions, ticker, mode):
    """Open opposite position to neutralize"""
    print(f"\n{'=' * 80}")
    print("OPPOSITE POSITION (Delta Hedge)")
    print(f"{'=' * 80}\n")

    print("This will open an equal and opposite position for each existing position.\n")

    for i, pos in enumerate(positions, 1):
        contract = pos.contract
        right = "CALL" if contract.right == 'C' else "PUT"

        if pos.position > 0:
            action = 'SELL'
            desc = f"SELL {abs(pos.position):.0f} {right}s to offset LONG position"
        else:
            action = 'BUY'
            desc = f"BUY {abs(pos.position):.0f} {right}s to offset SHORT position"

        print(f"{i}. {contract.symbol} ${contract.strike:.0f} {right} {contract.lastTradeDateOrContractMonth}")
        print(f"   → {desc}\n")

    confirm = input("Execute opposite positions for all? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("Cancelled.")
        return

    print("\nOpening opposite positions...\n")

    for pos in positions:
        action = 'SELL' if pos.position > 0 else 'BUY'
        quantity = abs(pos.position)

        print(f"{action} {quantity:.0f} {pos.contract.symbol} ${pos.contract.strike:.0f} {pos.contract.right}")

        try:
            order = MarketOrder(action, quantity)
            order.tif = 'GTC'
            trade = ib.placeOrder(pos.contract, order)
            print(f"  ✓ Order placed (ID: {trade.order.orderId})")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        print()

    print("✓ Opposite positions opened - your positions are now delta-neutral")


def stock_hedge(ib, positions, ticker, mode):
    """Hedge with underlying stock"""
    print(f"\n{'=' * 80}")
    print("STOCK HEDGE")
    print(f"{'=' * 80}\n")

    # Calculate total delta exposure
    total_delta_exposure = 0

    for pos in positions:
        # Estimate delta (simplified)
        # Calls have positive delta, puts have negative delta
        # Long positions add to delta, short subtract
        if pos.contract.right == 'C':
            delta = 0.5  # Simplified: assume 0.5 delta for ATM calls
        else:
            delta = -0.5  # Simplified: assume -0.5 delta for ATM puts

        position_delta = pos.position * delta * 100  # 100 shares per contract
        total_delta_exposure += position_delta

    print(f"Estimated total delta exposure: {total_delta_exposure:.0f} shares\n")

    if abs(total_delta_exposure) < 10:
        print("Your position is already nearly delta-neutral. No hedge needed.")
        return

    if total_delta_exposure > 0:
        action = 'SHORT'
        shares_needed = abs(total_delta_exposure)
        print(f"You have POSITIVE delta ({total_delta_exposure:.0f})")
        print(f"To hedge: SHORT {shares_needed:.0f} shares of {ticker.upper()}")
    else:
        action = 'LONG'
        shares_needed = abs(total_delta_exposure)
        print(f"You have NEGATIVE delta ({total_delta_exposure:.0f})")
        print(f"To hedge: BUY {shares_needed:.0f} shares of {ticker.upper()}")

    confirm = input(f"\n{action} {shares_needed:.0f} shares of {ticker.upper()}? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("Cancelled.")
        return

    # Create stock contract
    stock = Stock(ticker.upper(), 'SMART', 'USD')
    ib.qualifyContracts(stock)

    # Place order
    order_action = 'SELL' if action == 'SHORT' else 'BUY'
    order = MarketOrder(order_action, int(shares_needed))
    order.tif = 'GTC'

    try:
        trade = ib.placeOrder(stock, order)
        print(f"✓ Order placed (ID: {trade.order.orderId})")
        print(f"Status: {trade.orderStatus.status}")
    except Exception as e:
        print(f"✗ Error: {e}")


def collar_strategy(ib, positions, ticker, mode):
    """Collar: Buy put + Sell call"""
    print(f"\n{'=' * 80}")
    print("COLLAR STRATEGY (Buy Put + Sell Call)")
    print(f"{'=' * 80}\n")

    print("This combines:")
    print("  - Buy protective put (downside protection)")
    print("  - Sell covered call (collect premium, cap upside)\n")

    # Get current stock price
    stock = Stock(ticker.upper(), 'SMART', 'USD')
    ib.qualifyContracts(stock)
    ticker_obj = ib.reqMktData(stock, '', False, False)
    ib.sleep(3)

    if ticker_obj.last and ticker_obj.last > 0:
        current_price = ticker_obj.last
    elif ticker_obj.close and ticker_obj.close > 0:
        current_price = ticker_obj.close
    else:
        current_price = float(input(f"Enter current {ticker.upper()} stock price: $"))

    ib.cancelMktData(stock)

    print(f"Current {ticker.upper()} price: ${current_price:.2f}\n")

    # Suggest collar strikes
    put_strike = round((current_price * 0.95) / 5) * 5
    call_strike = round((current_price * 1.05) / 5) * 5

    print(f"Suggested collar:")
    print(f"  Buy PUT ${put_strike:.0f} (5% below)")
    print(f"  Sell CALL ${call_strike:.0f} (5% above)\n")

    expiry = input("Enter expiration date (YYYYMMDD, e.g., 20260930): ").strip()
    quantity = int(input("Number of collars (contracts): ").strip())

    print(f"\nCOLLAR: BUY {quantity} PUT ${put_strike:.0f} + SELL {quantity} CALL ${call_strike:.0f}")
    print(f"Protects below ${put_strike:.0f}, capped above ${call_strike:.0f}")
    confirm = input("Confirm? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("Cancelled.")
        return

    print("\nExecuting collar...\n")

    # Buy put
    put = Option(ticker.upper(), expiry, put_strike, 'P', 'SMART')
    ib.qualifyContracts(put)

    put_order = MarketOrder('BUY', quantity)
    put_order.tif = 'GTC'

    try:
        put_trade = ib.placeOrder(put, put_order)
        print(f"✓ BUY PUT order placed (ID: {put_trade.order.orderId})")
    except Exception as e:
        print(f"✗ PUT error: {e}")

    # Sell call
    call = Option(ticker.upper(), expiry, call_strike, 'C', 'SMART')
    ib.qualifyContracts(call)

    call_order = MarketOrder('SELL', quantity)
    call_order.tif = 'GTC'

    try:
        call_trade = ib.placeOrder(call, call_order)
        print(f"✓ SELL CALL order placed (ID: {call_trade.order.orderId})")
    except Exception as e:
        print(f"✗ CALL error: {e}")

    print("\n✓ Collar strategy executed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Hedge option positions')
    parser.add_argument('--ticker', type=str, required=True,
                       help='Ticker symbol (e.g., SNOW)')
    parser.add_argument('--mode', type=str, default='paper',
                       choices=['paper', 'live'],
                       help='Trading mode: paper or live')

    args = parser.parse_args()

    hedge_positions(args.ticker, args.mode)
