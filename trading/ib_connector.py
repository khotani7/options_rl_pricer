"""
Interactive Brokers API Integration

Uses ib_insync library for async trading

Setup:
1. Install TWS or IB Gateway
2. Enable API connections in TWS (File → Global Configuration → API → Settings)
3. Install: pip install ib_insync
4. Run TWS/Gateway on port 7497 (paper) or 7496 (live)
"""

from datetime import datetime
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
import asyncio
import time

try:
    from ib_insync import *
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ib_insync not installed. Install with: pip install ib_insync")


@dataclass
class IBConfig:
    """IB Connection configuration"""
    host: str = '127.0.0.1'
    port: int = 7497  # 7497 = paper trading, 7496 = live
    client_id: int = 1
    account: str = ""  # Leave empty to use default account


class IBConnector:
    """
    Interactive Brokers API Connector

    Handles connection, order placement, and position management
    """

    def __init__(self, config: IBConfig):
        if not IB_AVAILABLE:
            raise ImportError("ib_insync is required. Install with: pip install ib_insync")

        self.config = config
        self.ib = IB()
        self.connected = False
        self.account_value = 0.0
        self.positions = {}
        self.open_orders = {}

    def connect(self) -> bool:
        """
        Connect to Interactive Brokers TWS/Gateway

        Returns True if successful
        """
        try:
            self.ib.connect(
                self.config.host,
                self.config.port,
                clientId=self.config.client_id,
                readonly=False  # Set to True for read-only mode
            )

            self.connected = True

            # Get account info
            account_values = self.ib.accountValues()
            for av in account_values:
                if av.tag == 'NetLiquidation':
                    self.account_value = float(av.value)

            print(f"✓ Connected to IB on {self.config.host}:{self.config.port}")
            print(f"✓ Account value: ${self.account_value:,.2f}")

            return True

        except Exception as e:
            print(f"✗ Failed to connect to IB: {e}")
            print(f"  Make sure TWS/IB Gateway is running on port {self.config.port}")
            print(f"  Enable API access in TWS: File → Global Config → API → Settings")
            return False

    def disconnect(self):
        """Disconnect from IB"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            print("Disconnected from IB")

    def create_option_contract(self, ticker: str, expiry: str, strike: float,
                               right: str = 'P') -> Option:
        """
        Create an option contract object

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            expiry: Expiry date in YYYYMMDD format (e.g., '20261002')
            strike: Strike price
            right: 'P' for put, 'C' for call

        Returns:
            Option contract object
        """
        contract = Option(
            symbol=ticker,
            lastTradeDateOrContractMonth=expiry,
            strike=strike,
            right=right,
            exchange='SMART',
            currency='USD'
        )

        # Qualify the contract (get full contract details)
        self.ib.qualifyContracts(contract)

        return contract

    def get_market_data(self, contract: Contract, timeout: int = 10) -> Optional[Dict]:
        """
        Get real-time market data for a contract

        Returns dict with bid, ask, last, etc.
        """
        if not self.connected:
            print("Not connected to IB")
            return None

        try:
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)

            # Wait for data
            start = time.time()
            while (ticker.bid == -1 or ticker.ask == -1) and (time.time() - start < timeout):
                self.ib.sleep(0.1)

            if ticker.bid == -1 or ticker.ask == -1:
                print(f"No market data received for {contract}")
                return None

            return {
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'mid': (ticker.bid + ticker.ask) / 2,
                'bidSize': ticker.bidSize,
                'askSize': ticker.askSize,
                'volume': ticker.volume,
                'iv': ticker.impliedVolatility if ticker.impliedVolatility else None
            }

        except Exception as e:
            print(f"Error getting market data: {e}")
            return None

    def place_order(self, contract: Contract, action: str, quantity: int,
                   order_type: str = 'LMT', limit_price: Optional[float] = None,
                   transmit: bool = True) -> Trade:
        """
        Place an options order

        Args:
            contract: Option contract
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            order_type: 'MKT' (market) or 'LMT' (limit)
            limit_price: Required for limit orders
            transmit: If False, order is staged but not sent

        Returns:
            Trade object
        """
        if not self.connected:
            raise ConnectionError("Not connected to IB")

        # Create order
        if order_type == 'MKT':
            order = MarketOrder(action, quantity)
        elif order_type == 'LMT':
            if limit_price is None:
                raise ValueError("limit_price required for limit orders")
            order = LimitOrder(action, quantity, limit_price)
        else:
            raise ValueError(f"Unknown order type: {order_type}")

        order.transmit = transmit

        # Place order
        trade = self.ib.placeOrder(contract, order)

        # Store in open orders
        self.open_orders[trade.order.orderId] = trade

        print(f"{'✓' if transmit else '○'} Order placed: {action} {quantity}x {contract.symbol} "
              f"{contract.strike}{contract.right} {contract.lastTradeDateOrContractMonth} "
              f"@ {'MKT' if order_type == 'MKT' else f'${limit_price:.2f}'}")

        return trade

    def cancel_order(self, order_id: int):
        """Cancel an open order"""
        if order_id in self.open_orders:
            self.ib.cancelOrder(self.open_orders[order_id].order)
            print(f"Order {order_id} cancelled")
        else:
            print(f"Order {order_id} not found")

    def get_positions(self) -> List[Dict]:
        """
        Get all current positions

        Returns list of position dicts
        """
        if not self.connected:
            return []

        positions = []
        for position in self.ib.positions():
            positions.append({
                'contract': position.contract,
                'quantity': position.position,
                'avg_cost': position.avgCost,
                'market_value': position.marketValue,
                'unrealized_pnl': position.unrealizedPNL,
                'realized_pnl': position.realizedPNL
            })

        return positions

    def get_account_summary(self) -> Dict:
        """Get account summary"""
        if not self.connected:
            return {}

        summary = {}
        for av in self.ib.accountValues():
            summary[av.tag] = av.value

        return summary

    def get_open_orders(self) -> List[Trade]:
        """Get all open orders"""
        if not self.connected:
            return []

        return self.ib.openTrades()

    def wait_for_fill(self, trade: Trade, timeout: int = 60) -> bool:
        """
        Wait for an order to fill

        Returns True if filled, False if timeout
        """
        start = time.time()

        while trade.orderStatus.status != 'Filled' and (time.time() - start < timeout):
            self.ib.sleep(1)

        if trade.orderStatus.status == 'Filled':
            print(f"✓ Order {trade.order.orderId} filled @ ${trade.orderStatus.avgFillPrice:.2f}")
            return True
        else:
            print(f"✗ Order {trade.order.orderId} not filled (status: {trade.orderStatus.status})")
            return False

    def subscribe_to_fills(self, callback: Callable):
        """
        Subscribe to order fill events

        callback: function(trade) called when order fills
        """
        self.ib.orderStatusEvent += callback

    def run_event_loop(self):
        """
        Run the IB event loop

        Call this to keep connection alive and process events
        """
        self.ib.run()


# Mock connector for testing without IB connection
class MockIBConnector:
    """
    Mock IB connector for testing strategies without actual IB connection

    Simulates IB API behavior for development
    """

    def __init__(self, config: IBConfig):
        self.config = config
        self.connected = False
        self.account_value = 100000.0  # Mock $100k account
        self.positions = {}
        self.open_orders = {}
        self.order_id_counter = 1000

    def connect(self) -> bool:
        """Mock connection"""
        self.connected = True
        print(f"✓ [MOCK] Connected to IB (simulated)")
        print(f"✓ [MOCK] Account value: ${self.account_value:,.2f}")
        return True

    def disconnect(self):
        """Mock disconnect"""
        self.connected = False
        print("[MOCK] Disconnected")

    def create_option_contract(self, ticker: str, expiry: str, strike: float, right: str = 'P'):
        """Mock contract creation"""
        return {
            'symbol': ticker,
            'expiry': expiry,
            'strike': strike,
            'right': right
        }

    def get_market_data(self, contract, timeout: int = 10):
        """Mock market data - returns fake bid/ask"""
        import random
        base_price = 10.0
        spread = 0.20

        return {
            'bid': base_price - spread/2,
            'ask': base_price + spread/2,
            'last': base_price,
            'mid': base_price,
            'bidSize': 10,
            'askSize': 10,
            'volume': 100,
            'iv': 0.25
        }

    def place_order(self, contract, action: str, quantity: int, order_type: str = 'LMT',
                   limit_price: Optional[float] = None, transmit: bool = True):
        """Mock order placement"""
        order_id = self.order_id_counter
        self.order_id_counter += 1

        print(f"✓ [MOCK] Order placed: {action} {quantity}x {contract.get('symbol', contract)} "
              f"@ {order_type} {f'${limit_price:.2f}' if limit_price else 'MKT'}")

        return {'order_id': order_id, 'status': 'Filled'}

    def get_positions(self):
        """Mock positions"""
        return []

    def get_account_summary(self):
        """Mock account summary"""
        return {
            'NetLiquidation': self.account_value,
            'TotalCashValue': self.account_value * 0.8,
            'GrossPositionValue': self.account_value * 0.2
        }

    def get_open_orders(self):
        """Mock open orders"""
        return []
