"""
Automated Options Trader

Executes strategies with risk controls and monitoring
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import time
import json

from trading.ib_connector import IBConnector, IBConfig, MockIBConnector
from data.market_data import fetch_market_params
from edge_scanner import scan_option_chain
import pandas as pd


@dataclass
class RiskLimits:
    """Risk management parameters"""
    max_portfolio_exposure: float = 0.20  # 20% of account
    max_position_size: float = 0.05  # 5% per position
    max_daily_loss: float = 0.02  # 2% max daily loss
    max_positions: int = 10
    min_edge_threshold_pct: float = 3.0  # Minimum edge to trade
    max_leverage: float = 2.0
    stop_loss_multiplier: float = 1.5  # Exit at 1.5x entry price (tighter than old 30% which was ~2x)
    profit_target_pct: float = 0.50  # Take profit at 50% gain


@dataclass
class TradingConfig:
    """Trading configuration"""
    mode: str = 'paper'  # 'paper' or 'live'
    tickers: List[str] = field(default_factory=lambda: ['AAPL', 'XOM', 'JPM'])
    scan_interval_minutes: int = 15  # How often to scan for opportunities
    max_trades_per_day: int = 5
    order_timeout_seconds: int = 60
    use_limit_orders: bool = True  # False = market orders
    log_file: str = 'outputs/trading_log.json'


class AutomatedTrader:
    """
    Automated options trading system

    Features:
    - Automated edge scanning (LSM fair value vs. market, see edge_scanner.py)
    - Risk-controlled order placement
    - Position monitoring
    - Stop-loss management
    - Performance tracking
    """

    def __init__(self, ib_config: IBConfig, risk_limits: RiskLimits,
                 trading_config: TradingConfig, use_mock: bool = False):
        # --- Safety guard added: cross-check mode against the actual port/
        # connector, so a hand-built config can never drift into live
        # trading (real money) just because `trading_config.mode` still
        # says 'paper' or 'mock'. This is a hard failure, not a warning,
        # by design -- previously nothing enforced this relationship at
        # all, which meant AutomatedTrader would happily transmit real
        # orders against port 7496 while its own logs still printed
        # "Mode: PAPER". run_trader.py's CLI already picks the right port
        # and prompts for live confirmation, but that safety lived only
        # in the CLI layer, not here where it actually matters.
        if trading_config.mode not in ('mock', 'paper', 'live'):
            raise ValueError(f"Unknown trading_config.mode: {trading_config.mode!r}")
        expected_port = {'paper': 7497, 'live': 7496}.get(trading_config.mode)  # None for 'mock'
        if trading_config.mode == 'mock' and not use_mock:
            raise ValueError("trading_config.mode='mock' requires use_mock=True")
        if trading_config.mode in ('paper', 'live') and use_mock:
            raise ValueError(f"trading_config.mode={trading_config.mode!r} but use_mock=True -- refusing, this mismatch would silently run mock trades under a non-mock label")
        if trading_config.mode in ('paper', 'live') and ib_config.port != expected_port:
            raise ValueError(
                f"trading_config.mode={trading_config.mode!r} requires ib_config.port={expected_port} "
                f"(paper=7497, live=7496), got port={ib_config.port}. Refusing to start: this mismatch "
                f"is exactly the kind of bug that could route real orders through what looks like a "
                f"paper-trading run, or vice versa."
            )

        self.risk_limits = risk_limits
        self.trading_config = trading_config

        # Connect to IB
        if use_mock:
            self.ib = MockIBConnector(ib_config)
        else:
            self.ib = IBConnector(ib_config)

        # State
        self.active = False
        self.positions = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.start_of_day_value = 0.0
        self.trading_log = []

    def start(self):
        """Start the automated trader"""
        print(f"\n{'='*70}")
        print(f"Starting Automated Options Trader")
        print(f"{'='*70}")
        print(f"Mode: {self.trading_config.mode.upper()}")
        print(f"Tickers: {', '.join(self.trading_config.tickers)}")
        print(f"Scan interval: {self.trading_config.scan_interval_minutes} minutes")
        print(f"Max positions: {self.risk_limits.max_positions}")
        print(f"Min edge: {self.risk_limits.min_edge_threshold_pct}%")
        print(f"{'='*70}\n")

        # Connect to IB
        if not self.ib.connect():
            print("Failed to connect to Interactive Brokers")
            return

        self.active = True
        self.start_of_day_value = self.ib.account_value

        print("✓ Trader is now active\n")

        # Main trading loop
        try:
            self.run_trading_loop()
        except KeyboardInterrupt:
            print("\n\nStopping trader...")
            self.stop()
        except Exception as e:
            print(f"\n\nError in trading loop: {e}")
            self.stop()

    def stop(self):
        """Stop the automated trader"""
        self.active = False
        self.ib.disconnect()
        self.save_trading_log()
        print("\n✓ Trader stopped")

    def run_trading_loop(self):
        """Main trading loop"""
        last_scan_time = datetime.now() - timedelta(minutes=self.trading_config.scan_interval_minutes)

        while self.active:
            current_time = datetime.now()

            # Check if market is open (9:30 AM - 4:00 PM ET)
            if not self.is_market_open():
                print(f"[{current_time.strftime('%H:%M:%S')}] Market is closed. Waiting...")
                time.sleep(60)
                continue

            # Update positions
            self.update_positions()

            # Check risk limits
            if self.check_risk_limits():
                print(f"[{current_time.strftime('%H:%M:%S')}] Risk limits breached. Halting new trades.")
                time.sleep(60)
                continue

            # Scan for opportunities
            if (current_time - last_scan_time).total_seconds() >= self.trading_config.scan_interval_minutes * 60:
                print(f"\n[{current_time.strftime('%H:%M:%S')}] Scanning for opportunities...")
                self.scan_and_trade()
                last_scan_time = current_time

            # Monitor positions for stop-loss
            self.monitor_stop_losses()

            # Sleep before next iteration
            time.sleep(30)

    def is_market_open(self) -> bool:
        """Check if US options market is open"""
        now = datetime.now()

        # Check if weekend
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        # Check time (9:30 AM - 4:00 PM ET)
        # Note: Adjust for your timezone
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)

        return market_open <= now <= market_close

    def scan_and_trade(self):
        """Scan for edge opportunities and place trades"""

        if self.daily_trades >= self.trading_config.max_trades_per_day:
            print(f"  Max daily trades ({self.trading_config.max_trades_per_day}) reached")
            return

        if len(self.positions) >= self.risk_limits.max_positions:
            print(f"  Max positions ({self.risk_limits.max_positions}) reached")
            return

        # Scan each ticker
        for ticker in self.trading_config.tickers:
            try:
                print(f"  Scanning {ticker}...")

                # Use edge scanner (LSM fair value vs. market -- see edge_scanner.py)
                # Filter for near-the-money options (85% - 115% of spot)
                # This avoids deep OTM lottery tickets that will never hit
                df = scan_option_chain(ticker, min_volume=5,
                                      min_edge_pct=self.risk_limits.min_edge_threshold_pct,
                                      min_moneyness=0.85, max_moneyness=1.15)

                if df is None or df.empty:
                    print(f"    No opportunities found")
                    continue

                # Take best opportunity
                print(f"    Found {len(df)} opportunities")
                best_opp = df.iloc[0]
                print(f"    Best: {best_opp['signal']} ${best_opp['strike']:.0f} @ ${best_opp['market_mid']:.2f} ({best_opp['edge_pct']:+.1f}%)")

                # Check position sizing
                if not self.check_position_size(best_opp['market_mid']):
                    position_value = best_opp['market_mid'] * 100
                    position_pct = (position_value / self.ib.account_value) * 100
                    print(f"    Position too large for risk limits")
                    print(f"    Option price: ${best_opp['market_mid']:.2f} → Position value: ${position_value:.2f}")
                    print(f"    Position %: {position_pct:.2f}% (limit: {self.risk_limits.max_position_size*100:.1f}%)")
                    continue

                # Execute trade
                self.execute_trade(best_opp)

            except Exception as e:
                print(f"  Error scanning {ticker}: {e}")
                continue

    def execute_trade(self, opportunity: pd.Series):
        """Execute a trade based on opportunity"""

        print(f"\n  → Found opportunity: {opportunity['signal']}")
        print(f"    {opportunity['type']} ${opportunity['strike']:.0f} exp {opportunity['expiry']}")
        print(f"    Edge: {opportunity['edge_score']:.1f}% | Market: ${opportunity['market_mid']:.2f}")

        # Create contract
        expiry_formatted = opportunity['expiry'].replace('-', '')  # YYYYMMDD format
        right = 'P' if opportunity['type'] == 'PUT' else 'C'

        contract = self.ib.create_option_contract(
            ticker=opportunity['ticker'],
            expiry=expiry_formatted,
            strike=opportunity['strike'],
            right=right
        )

        # Determine action
        action = 'BUY' if 'BUY' in opportunity['signal'] else 'SELL'

        # Get live market data
        market_data = self.ib.get_market_data(contract, timeout=10)

        if not market_data:
            print(f"    ✗ Could not get market data")
            return

        # Validate market data
        import math
        if (market_data.get('bid') is None or
            market_data.get('ask') is None or
            math.isnan(market_data.get('bid', float('nan'))) or
            math.isnan(market_data.get('ask', float('nan'))) or
            market_data['bid'] <= 0 or
            market_data['ask'] <= 0):
            print(f"    ✗ Invalid market data: bid={market_data.get('bid')}, ask={market_data.get('ask')}")
            print(f"    ℹ️  This is usually due to market data subscription issues")
            print(f"    ℹ️  Enable delayed data in IB Gateway or use market mid price")

            # Fallback: use the market_mid from edge scanner
            if self.trading_config.use_limit_orders:
                limit_price = opportunity['market_mid']
                print(f"    → Using scanner market mid: ${limit_price:.2f}")
                order_type = 'LMT'
            else:
                limit_price = None
                order_type = 'MKT'
        else:
            # Determine price from valid market data
            if self.trading_config.use_limit_orders:
                if action == 'BUY':
                    limit_price = market_data['ask'] * 0.995  # Slightly below ask
                else:
                    limit_price = market_data['bid'] * 1.005  # Slightly above bid

                order_type = 'LMT'
            else:
                limit_price = None
                order_type = 'MKT'

        # Place order
        try:
            trade = self.ib.place_order(
                contract=contract,
                action=action,
                quantity=1,
                order_type=order_type,
                limit_price=limit_price,
                transmit=True
            )

            # Wait for fill
            filled = self.ib.wait_for_fill(trade, timeout=self.trading_config.order_timeout_seconds)

            if filled:
                # Record trade
                self.record_trade(opportunity, action, trade)
                self.daily_trades += 1
                print(f"    ✓ Trade executed successfully\n")
            else:
                print(f"    ✗ Order not filled\n")

        except Exception as e:
            print(f"    ✗ Error placing order: {e}\n")

    def update_positions(self):
        """Update current positions from IB"""
        try:
            positions = self.ib.get_positions()

            for pos in positions:
                key = f"{pos['contract'].symbol}_{pos['contract'].strike}_{pos['contract'].right}"
                self.positions[key] = pos

        except Exception as e:
            print(f"Error updating positions: {e}")

    def monitor_stop_losses(self):
        """Check positions for stop-loss and profit-target triggers"""
        for key, pos in list(self.positions.items()):
            # Get current market price
            current_price = pos.get('market_price', 0)
            entry_price = pos.get('avg_cost', 0)

            if entry_price > 0 and current_price > 0:
                # Calculate P&L %
                pnl_pct = pos['unrealized_pnl'] / (entry_price * abs(pos['quantity'])) * 100

                # Check 1.5x stop-loss (tighter stop for short options)
                # For short options (selling), we lose money when price goes UP
                # Exit if current_price >= 1.5x entry_price
                if current_price >= entry_price * self.risk_limits.stop_loss_multiplier:
                    print(f"\n⚠️  {self.risk_limits.stop_loss_multiplier}x Stop-loss triggered for {key}")
                    print(f"    Entry: ${entry_price:.2f}")
                    print(f"    Current: ${current_price:.2f} ({current_price/entry_price:.2f}x)")
                    print(f"    P&L: {pnl_pct:.1f}%")
                    self.close_position(pos)

                # Check profit target
                elif pnl_pct > self.risk_limits.profit_target_pct * 100:
                    print(f"\n✓ Profit target hit for {key}")
                    print(f"    P&L: {pnl_pct:.1f}% (target: {self.risk_limits.profit_target_pct*100:.0f}%)")
                    self.close_position(pos)

    def close_position(self, position: Dict):
        """Close a position at market"""
        print(f"    Closing position...")

        action = 'SELL' if position['quantity'] > 0 else 'BUY'

        try:
            trade = self.ib.place_order(
                contract=position['contract'],
                action=action,
                quantity=abs(position['quantity']),
                order_type='MKT',
                transmit=True
            )

            filled = self.ib.wait_for_fill(trade, timeout=30)

            if filled:
                print(f"    ✓ Position closed")
            else:
                print(f"    ✗ Failed to close position")

        except Exception as e:
            print(f"    ✗ Error closing position: {e}")

    def check_risk_limits(self) -> bool:
        """
        Check if risk limits are breached

        Returns True if limits breached (halt trading)
        """
        account_summary = self.ib.get_account_summary()
        current_value = float(account_summary.get('NetLiquidation', self.ib.account_value))

        # Check daily loss limit
        daily_pnl = current_value - self.start_of_day_value
        daily_pnl_pct = daily_pnl / self.start_of_day_value

        if daily_pnl_pct < -self.risk_limits.max_daily_loss:
            print(f"\n⚠️  DAILY LOSS LIMIT BREACHED")
            print(f"    Daily P&L: {daily_pnl_pct*100:.2f}% (limit: {-self.risk_limits.max_daily_loss*100:.0f}%)")
            return True

        # Check max positions
        if len(self.positions) >= self.risk_limits.max_positions:
            return True

        return False

    def check_position_size(self, option_price: float) -> bool:
        """Check if position size is within limits"""
        account_value = self.ib.account_value
        position_value = option_price * 100  # Options are per 100 shares

        position_pct = position_value / account_value

        return position_pct <= self.risk_limits.max_position_size

    def record_trade(self, opportunity: pd.Series, action: str, trade):
        """Record trade in log"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'ticker': opportunity['ticker'],
            'type': opportunity['type'],
            'strike': opportunity['strike'],
            'expiry': opportunity['expiry'],
            'action': action,
            'edge_score': opportunity['edge_score'],
            'market_mid': opportunity['market_mid'],
            'order_id': trade.get('order_id', 'N/A')
        }

        self.trading_log.append(log_entry)

    def save_trading_log(self):
        """Save trading log to file"""
        os.makedirs(os.path.dirname(self.trading_config.log_file), exist_ok=True)

        with open(self.trading_config.log_file, 'w') as f:
            json.dump(self.trading_log, f, indent=2)

        print(f"✓ Trading log saved to {self.trading_config.log_file}")

    def get_performance_summary(self) -> Dict:
        """Get performance summary"""
        account_summary = self.ib.get_account_summary()
        current_value = float(account_summary.get('NetLiquidation', self.ib.account_value))

        return {
            'current_value': current_value,
            'start_value': self.start_of_day_value,
            'daily_pnl': current_value - self.start_of_day_value,
            'daily_pnl_pct': (current_value / self.start_of_day_value - 1) * 100,
            'total_trades': self.daily_trades,
            'open_positions': len(self.positions)
        }
