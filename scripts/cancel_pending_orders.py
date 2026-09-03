"""
Cancel all pending orders in IB
"""
from trading.ib_connector import IBConnector, IBConfig

ib_config = IBConfig(port=7497)
connector = IBConnector(ib_config)

def main():
    if not connector.connect():
        raise SystemExit("Could not connect to IB Gateway")

    try:
        # Get all open orders
        open_orders = connector.ib.openTrades()

        if not open_orders:
            print("No open orders to cancel")
            return

        print(f"Found {len(open_orders)} open order(s):")
        for trade in open_orders:
            print(f"  Order {trade.order.orderId}: {trade.order.action} {trade.contract.symbol} - {trade.orderStatus.status}")

        # Cancel all
        confirm = input("\nCancel all? (yes/no): ")
        if confirm.lower() == 'yes':
            for trade in open_orders:
                connector.ib.cancelOrder(trade.order)
                print(f"✓ Cancelled order {trade.order.orderId}")
        else:
            print("Cancelled nothing")

    finally:
        connector.disconnect()

if __name__ == "__main__":
    main()
