"""
Test market data freshness - Live vs Delayed vs Stale

This script monitors market data updates to determine if you're getting:
1. Live real-time data (updates every second)
2. Delayed data (15-20 min old but still updating)
3. Stale/snapshot data (not updating at all)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trading.ib_connector import IBConnector, IBConfig
from ib_insync import Stock, Option
import time
from datetime import datetime


def test_stock_data_freshness():
    """Test if stock market data is updating"""
    print("\n" + "="*70)
    print("Market Data Freshness Test")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")

    config = IBConfig(host='127.0.0.1', port=7497, client_id=998)
    ib = IBConnector(config)

    if not ib.connect():
        print("✗ Failed to connect to IB")
        return

    print("✓ Connected to IB Gateway")

    # Test 1: Stock data
    print("\n" + "="*70)
    print("TEST 1: Stock Market Data (AAPL)")
    print("="*70)
    print("Monitoring for 30 seconds to see if data updates...")
    print("(If market is closed, data won't update - that's expected)\n")

    stock = Stock('AAPL', 'SMART', 'USD')
    ib.ib.qualifyContracts(stock)

    # Subscribe to market data
    ticker = ib.ib.reqMktData(stock, '', False, False)
    ib.ib.sleep(2)  # Wait for initial data

    last_values = {}
    update_count = 0

    print(f"{'Time':<12} {'Last':<10} {'Bid':<10} {'Ask':<10} {'Volume':<12} {'Status'}")
    print("-" * 70)

    for i in range(30):
        time_str = datetime.now().strftime('%H:%M:%S')

        # Track what fields updated
        current_values = {
            'last': ticker.last,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'volume': ticker.volume,
            'last_time': ticker.time
        }

        # Check if anything changed
        if current_values != last_values:
            update_count += 1
            status = "✓ UPDATED"
        else:
            status = ""

        print(f"{time_str:<12} "
              f"{ticker.last if ticker.last else 'N/A':<10} "
              f"{ticker.bid if ticker.bid else 'N/A':<10} "
              f"{ticker.ask if ticker.ask else 'N/A':<10} "
              f"{ticker.volume if ticker.volume else 'N/A':<12} "
              f"{status}")

        last_values = current_values.copy()
        time.sleep(1)

    ib.ib.cancelMktData(stock)

    print("\n" + "-" * 70)
    print(f"Updates detected: {update_count}/30")

    if update_count > 10:
        print("✓ LIVE DATA - Getting real-time updates")
        data_type = "LIVE"
    elif update_count > 0:
        print("⚠️  DELAYED DATA - Some updates but may be delayed")
        data_type = "DELAYED"
    else:
        print("✗ STALE DATA - No updates detected (or market is closed)")
        data_type = "STALE"

    # Test 2: Option data
    print("\n" + "="*70)
    print("TEST 2: Option Market Data (AAPL 320P expiring 9/9)")
    print("="*70)
    print("Checking option quotes...\n")

    option = Option('AAPL', '20260909', 320, 'P', 'SMART')
    contracts = ib.ib.qualifyContracts(option)

    if not contracts:
        print("✗ Could not qualify option contract")
    else:
        print(f"✓ Contract qualified: {contracts[0].localSymbol}")

        ticker = ib.ib.reqMktData(contracts[0], '', False, False)
        ib.ib.sleep(3)

        print(f"\nOption Quote:")
        print(f"  Bid: ${ticker.bid if ticker.bid else 'N/A'}")
        print(f"  Ask: ${ticker.ask if ticker.ask else 'N/A'}")
        print(f"  Last: ${ticker.last if ticker.last else 'N/A'}")
        print(f"  Model IV: {ticker.modelGreeks.impliedVol if ticker.modelGreeks else 'N/A'}")

        if ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
            print(f"✓ Option quotes available")
            spread_pct = (ticker.ask - ticker.bid) / ticker.bid * 100
            print(f"  Bid-Ask spread: {spread_pct:.1f}%")

            if spread_pct > 50:
                print(f"  ⚠️  Wide spread - low liquidity")
        else:
            print(f"✗ No valid option quotes")

        ib.ib.cancelMktData(contracts[0])

    # Test 3: Market data type check
    print("\n" + "="*70)
    print("TEST 3: Market Data Subscription Type")
    print("="*70)

    # Check what market data type is being used
    # Type 1 = Live, Type 2 = Frozen, Type 3 = Delayed, Type 4 = Delayed Frozen
    stock = Stock('AAPL', 'SMART', 'USD')
    ib.ib.qualifyContracts(stock)
    ticker = ib.ib.reqMktData(stock, '', False, False)
    ib.ib.sleep(2)

    print(f"\nMarket data type: {ticker.marketDataType}")
    data_type_map = {
        1: "Real-time streaming (LIVE)",
        2: "Frozen (last known value)",
        3: "Delayed streaming (15-20 min delay)",
        4: "Delayed frozen (delayed snapshot)"
    }
    print(f"Meaning: {data_type_map.get(ticker.marketDataType, 'Unknown')}")

    if ticker.marketDataType == 1:
        print("✓ You have LIVE real-time market data")
    elif ticker.marketDataType == 3:
        print("⚠️  You have DELAYED market data (15-20 min delay)")
        print("   This is fine for paper trading but orders may not fill at stale prices")
    else:
        print("⚠️  Market data type unclear")

    ib.ib.cancelMktData(stock)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    current_time = datetime.now()
    is_market_hours = (9 <= current_time.hour < 16) and (current_time.weekday() < 5)

    if not is_market_hours:
        print("⚠️  MARKET IS CLOSED")
        print("   Run this test during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)")
        print("   to see live data updates")
    else:
        print(f"Market Data Type: {data_type}")
        print(f"Update frequency: {update_count} updates in 30 seconds")

        if data_type == "STALE" and is_market_hours:
            print("\n⚠️  PROBLEM DETECTED: No live data during market hours")
            print("\nPossible causes:")
            print("  1. No market data subscription (need live data or delayed)")
            print("  2. IB Gateway not configured for market data")
            print("  3. Account doesn't have market data permissions")
            print("\nTo enable delayed data (free for paper trading):")
            print("  1. IB Gateway → Configure → Settings → Market Data")
            print("  2. Check 'Use delayed market data if real-time is not available'")

    ib.disconnect()


if __name__ == "__main__":
    try:
        test_stock_data_freshness()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
