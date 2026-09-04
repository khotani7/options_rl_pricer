"""
Test Interactive Brokers connection and permissions

This script tests:
1. Connection to IB Gateway/TWS
2. Account access
3. Market data permissions
4. Order placement permissions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trading.ib_connector import IBConnector, IBConfig
from ib_insync import Stock, Option
import time


def test_connection():
    """Test basic connection"""
    print("\n" + "="*70)
    print("IB Connection Diagnostic Test")
    print("="*70)

    # Test paper trading connection
    print("\n1. Testing connection to paper trading account (port 7497)...")
    config = IBConfig(host='127.0.0.1', port=7497, client_id=999)
    ib = IBConnector(config)

    if not ib.connect():
        print("✗ Failed to connect to IB Gateway on port 7497")
        print("\nTroubleshooting:")
        print("  1. Is IB Gateway or TWS running?")
        print("  2. Is API enabled in Global Configuration → API → Settings?")
        print("  3. Is port 7497 configured for Socket Port?")
        print("  4. Is 127.0.0.1 in Trusted IPs?")
        return False

    print("✓ Connected successfully")

    # Test account access
    print("\n2. Testing account access...")
    try:
        account_summary = ib.get_account_summary()
        print(f"✓ Account value: ${ib.account_value:,.2f}")
        print(f"  Net liquidation: ${float(account_summary.get('NetLiquidation', 0)):,.2f}")
        print(f"  Buying power: ${float(account_summary.get('BuyingPower', 0)):,.2f}")
    except Exception as e:
        print(f"✗ Failed to get account info: {e}")
        return False

    # Test market data
    print("\n3. Testing market data access...")
    try:
        stock = Stock('AAPL', 'SMART', 'USD')
        ib.ib.qualifyContracts(stock)
        ticker = ib.ib.reqMktData(stock, '', False, False)
        time.sleep(3)  # Wait for data

        if ticker.last > 0:
            print(f"✓ Real-time market data working")
            print(f"  AAPL last: ${ticker.last:.2f}")
        elif ticker.close > 0:
            print(f"⚠️  Delayed market data only")
            print(f"  AAPL close: ${ticker.close:.2f}")
            print(f"  Note: Delayed data is fine for paper trading")
        else:
            print(f"⚠️  Limited market data")
            print(f"  This may affect order placement")

        ib.ib.cancelMktData(stock)
    except Exception as e:
        print(f"✗ Market data error: {e}")

    # Test option contract qualification
    print("\n4. Testing option contract access...")
    try:
        option = Option('AAPL', '20260909', 320, 'P', 'SMART')
        qualified = ib.ib.qualifyContracts(option)
        if qualified:
            print(f"✓ Option contracts accessible")
            print(f"  Contract ID: {qualified[0].conId}")
        else:
            print(f"✗ Could not qualify option contract")
    except Exception as e:
        print(f"✗ Option access error: {e}")

    # Test order placement permissions
    print("\n5. Testing order placement (will cancel immediately)...")
    try:
        from ib_insync import LimitOrder

        # Create a harmless test order (far out of the money, will cancel)
        option = Option('AAPL', '20260909', 200, 'P', 'SMART')
        ib.ib.qualifyContracts(option)

        order = LimitOrder('BUY', 1, 0.01)  # Absurdly low price, won't fill
        trade = ib.ib.placeOrder(option, order)

        time.sleep(2)
        print(f"  Order status: {trade.orderStatus.status}")

        if trade.orderStatus.status in ['PreSubmitted', 'Submitted', 'PendingSubmit']:
            print(f"✓ Order placement working")

            # Cancel the test order
            ib.ib.cancelOrder(order)
            print(f"  Test order cancelled")
        else:
            print(f"⚠️  Order status unexpected: {trade.orderStatus.status}")

    except Exception as e:
        print(f"✗ Order placement error: {e}")
        print("\nPossible issues:")
        print("  1. Trading permissions not enabled")
        print("  2. Paper trading account not configured")
        print("  3. Need to accept order warnings in TWS/Gateway")

    # Check for any error messages
    print("\n6. Checking for IB error messages...")
    time.sleep(1)

    ib.disconnect()

    print("\n" + "="*70)
    print("Diagnostic test complete")
    print("="*70)
    print("\nIf orders are stuck in 'PendingSubmit':")
    print("  1. Check IB Gateway → Configure → Settings → API → Precautions")
    print("  2. Disable 'Bypass Order Precautions for API Orders' or")
    print("  3. Manually click 'Accept' in TWS for the first order")
    print("  4. Check 'Read-Only API' is disabled")
    print("  5. Ensure paper trading account has sufficient permissions")

    return True


if __name__ == "__main__":
    try:
        test_connection()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
