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
    # Market data type is NOT a Gateway/TWS UI setting -- it's requested by
    # the API client after connecting, via reqMarketDataType(). There is no
    # checkbox for this in Gateway's Configure menu.
    #   1 = live (requires a paid real-time data subscription)
    #   2 = frozen (last live snapshot before market close)
    #   3 = delayed (free, ~15-20 min behind, used automatically as a
    #       fallback if you don't have a live subscription for a symbol)
    #   4 = delayed-frozen
    # Most paper trading accounts have no live data subscriptions, so this
    # defaults to 3 -- without it, reqMktData calls on unsubscribed symbols
    # return empty/stale ticks instead of falling back to delayed data.
    market_data_type: int = 3


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

            # Request delayed data as a fallback for any symbol without a
            # live subscription -- this is the actual "enable delayed data"
            # step for an API client; it has no equivalent in Gateway's UI.
            data_type_names = {1: 'live', 2: 'frozen', 3: 'delayed', 4: 'delayed-frozen'}
            self.ib.reqMarketDataType(self.config.market_data_type)
            print(f"✓ Market data type requested: "
                  f"{data_type_names.get(self.config.market_data_type, self.config.market_data_type)}")

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
        contract = Option(
            symbol=ticker,
            lastTradeDateOrContractMonth=expiry,
            strike=strike,
            right=right,
            exchange='SMART',
            currency='USD'
        )
        self.ib.qualifyContracts(contract)
        return contract

    def get_market_data(self, contract: Contract, timeout: int = 10) -> Optional[Dict]:
        if not self.connected:
            print("Not connected to IB")
            return None
        try:
            ticker = self.ib.reqMktData(contract, '', False, False)
            start = time.time()

            # Wait for market data, checking both live and delayed fields
            while (time.time() - start < timeout):
                self.ib.sleep(0.5)

                # Check if we have valid bid/ask (either live or delayed)
                has_bid = ticker.bid is not None and ticker.bid > 0 and ticker.bid != -1
                has_ask = ticker.ask is not None and ticker.ask > 0 and ticker.ask != -1

                # For delayed data, also check delayedBid/delayedAsk
                has_delayed_bid = hasattr(ticker, 'delayedBid') and ticker.delayedBid and ticker.delayedBid > 0
                has_delayed_ask = hasattr(ticker, 'delayedAsk') and ticker.delayedAsk and ticker.delayedAsk > 0

                if (has_bid and has_ask) or (has_delayed_bid and has_delayed_ask):
                    break

            # Use delayed data if live not available
            bid = ticker.bid if (ticker.bid and ticker.bid > 0) else getattr(ticker, 'delayedBid', None)
            ask = ticker.ask if (ticker.ask and ticker.ask > 0) else getattr(ticker, 'delayedAsk', None)
            last = ticker.last if (ticker.last and ticker.last > 0) else getattr(ticker, 'delayedLast', None)

            # Validate we have usable data
            if not bid or not ask or bid <= 0 or ask <= 0:
                return None

            return {
                'bid': float(bid), 'ask': float(ask),
                'last': float(last) if last else None,
                'mid': (float(bid) + float(ask)) / 2,
                'bidSize': ticker.bidSize, 'askSize': ticker.askSize,
                'volume': ticker.volume,
                'iv': ticker.impliedVolatility if ticker.impliedVolatility else None
            }
        except Exception as e:
            print(f"Error getting market data: {e}")
            return None

    def place_order(self, contract: Contract, action: str, quantity: int,
                   order_type: str = 'LMT', limit_price: Optional[float] = None,
                   transmit: bool = True) -> Trade:
        if not self.connected:
            raise ConnectionError("Not connected to IB")
        if order_type == 'MKT':
            order = MarketOrder(action, quantity)
        elif order_type == 'LMT':
            if limit_price is None:
                raise ValueError("limit_price required for limit orders")
            order = LimitOrder(action, quantity, limit_price)
        else:
            raise ValueError(f"Unknown order type: {order_type}")

        # Set order properties to avoid IB preset conflicts
        order.tif = 'DAY'  # Time in force
        order.outsideRth = False  # Don't allow outside regular trading hours
        order.transmit = transmit

        trade = self.ib.placeOrder(contract, order)
        self.open_orders[trade.order.orderId] = trade
        print(f"{'✓' if transmit else '○'} Order placed: {action} {quantity}x {contract.symbol} "
              f"{contract.strike}{contract.right} {contract.lastTradeDateOrContractMonth} "
              f"@ {'MKT' if order_type == 'MKT' else f'${limit_price:.2f}'}")
        return trade

    def cancel_order(self, order_id: int):
        if order_id in self.open_orders:
            self.ib.cancelOrder(self.open_orders[order_id].order)
            print(f"Order {order_id} cancelled")
        else:
            print(f"Order {order_id} not found")

    def get_positions(self) -> List[Dict]:
        if not self.connected:
            return []
        positions = []
        for position in self.ib.positions():
            # Some position attributes might not exist, use getattr with defaults
            positions.append({
                'contract': position.contract,
                'quantity': position.position,
                'avg_cost': getattr(position, 'avgCost', 0.0),
                'market_value': getattr(position, 'marketValue', 0.0),
                'unrealized_pnl': getattr(position, 'unrealizedPNL', 0.0),
                'realized_pnl': getattr(position, 'realizedPNL', 0.0)
            })
        return positions

    def get_account_summary(self) -> Dict:
        if not self.connected:
            return {}
        summary = {}
        for av in self.ib.accountValues():
            summary[av.tag] = av.value
        return summary

    def get_open_orders(self) -> List[Trade]:
        if not self.connected:
            return []
        return self.ib.openTrades()

    def wait_for_fill(self, trade: Trade, timeout: int = 60) -> bool:
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
        self.ib.orderStatusEvent += callback

    def run_event_loop(self):
        self.ib.run()


class MockIBConnector:
    """Mock IB connector for testing strategies without actual IB connection"""

    def __init__(self, config: IBConfig):
        self.config = config
        self.connected = False
        self.account_value = 100000.0
        self.positions = {}
        self.open_orders = {}
        self.order_id_counter = 1000

    def connect(self) -> bool:
        self.connected = True
        print(f"✓ [MOCK] Connected to IB (simulated)")
        print(f"✓ [MOCK] Account value: ${self.account_value:,.2f}")
        return True

    def disconnect(self):
        self.connected = False
        print("[MOCK] Disconnected")

    def create_option_contract(self, ticker: str, expiry: str, strike: float, right: str = 'P'):
        return {'symbol': ticker, 'expiry': expiry, 'strike': strike, 'right': right}

    def get_market_data(self, contract, timeout: int = 10):
        base_price = 10.0
        spread = 0.20
        return {
            'bid': base_price - spread/2, 'ask': base_price + spread/2,
            'last': base_price, 'mid': base_price,
            'bidSize': 10, 'askSize': 10, 'volume': 100, 'iv': 0.25
        }

    def place_order(self, contract, action: str, quantity: int, order_type: str = 'LMT',
                   limit_price: Optional[float] = None, transmit: bool = True):
        order_id = self.order_id_counter
        self.order_id_counter += 1
        print(f"✓ [MOCK] Order placed: {action} {quantity}x {contract.get('symbol', contract)} "
              f"@ {order_type} {f'${limit_price:.2f}' if limit_price else 'MKT'}")
        return {'order_id': order_id, 'status': 'Filled'}

    def get_positions(self):
        return []

    def get_account_summary(self):
        return {
            'NetLiquidation': self.account_value,
            'TotalCashValue': self.account_value * 0.8,
            'GrossPositionValue': self.account_value * 0.2
        }

    def get_open_orders(self):
        return []
