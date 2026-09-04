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
    max_portfolio_exposure: float = 0.50  # 50% of account notional (for short options with stops)
    max_position_size: float = 0.05  # 5% per position (premium)
    max_daily_loss: float = 0.02  # 2% max daily loss
    max_positions: int = 10
    min_edge_threshold_pct: float = 3.0  # Minimum edge to trade
    max_leverage: float = 2.0
    stop_loss_multiplier: float = 1.25  # Exit at 1.25x entry price = 25% loss (for short options)
    profit_target_pct: float = 0.25  # Take profit at 25% gain (capture theta, avoid gamma risk)


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
    min_premium: float = 0.0  # Minimum option premium ($)
    min_moneyness: float = 0.85  # Min strike/spot ratio
    max_moneyness: float = 1.15  # Max strike/spot ratio
    min_dte: int = 0  # Minimum days to expiration
    max_dte: int = 365  # Maximum days to expiration
    max_spread_pct: float = 100.0  # Max bid-ask spread %
    min_iv_percentile: float = 0.0  # Min IV percentile (0-100)


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
                df = scan_option_chain(ticker, min_volume=5,
                                      min_edge_pct=self.risk_limits.min_edge_threshold_pct,
                                      min_moneyness=self.trading_config.min_moneyness,
                                      max_moneyness=self.trading_config.max_moneyness)

                if df is None or df.empty:
                    print(f"    No opportunities found")
                    continue

                # Apply additional filters
                original_count = len(df)
                filter_reasons = []

                # Filter by minimum premium
                if self.trading_config.min_premium > 0:
                    before = len(df)
                    df = df[df['market_mid'] >= self.trading_config.min_premium]
                    if len(df) < before:
                        filter_reasons.append(f"min_premium=${self.trading_config.min_premium:.2f}")

                # Filter by minimum days to expiration
                if self.trading_config.min_dte > 0:
                    before = len(df)
                    from datetime import datetime, timedelta
                    min_expiry = (datetime.now() + timedelta(days=self.trading_config.min_dte)).strftime('%Y-%m-%d')
                    df = df[df['expiry'] >= min_expiry]
                    if len(df) < before:
                        filter_reasons.append(f"min_dte={self.trading_config.min_dte}d")

                # Filter by maximum days to expiration
                if self.trading_config.max_dte < 365:
                    before = len(df)
                    from datetime import datetime, timedelta
                    max_expiry = (datetime.now() + timedelta(days=self.trading_config.max_dte)).strftime('%Y-%m-%d')
                    df = df[df['expiry'] <= max_expiry]
                    if len(df) < before:
                        filter_reasons.append(f"max_dte={self.trading_config.max_dte}d")

                # Filter by bid-ask spread
                if self.trading_config.max_spread_pct < 100.0:
                    before = len(df)
                    df = df[df['spread_pct'] <= self.trading_config.max_spread_pct]
                    if len(df) < before:
                        filter_reasons.append(f"max_spread<{self.trading_config.max_spread_pct:.0f}%")

                if df.empty:
                    print(f"    Found {original_count} opportunities, but none passed filters:")
                    print(f"    Filtered by: {', '.join(filter_reasons)}")
                    continue

                # Take best opportunity
                print(f"    Found {len(df)} opportunities (filtered from {original_count})")
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

        # Calculate position size
        quantity = self.calculate_position_size(opportunity)
        position_value = quantity * opportunity['market_mid'] * 100
        position_pct = (position_value / self.ib.account_value) * 100

        print(f"    Position sizing:")
        print(f"      Quantity: {quantity} contracts")
        print(f"      Premium: ${opportunity['market_mid']:.2f} × {quantity} × 100 = ${position_value:,.0f}")
        print(f"      Portfolio %: {position_pct:.2f}%")
        if 'SELL' in opportunity['signal']:
            notional_risk = quantity * opportunity['strike'] * 100
            notional_pct = (notional_risk / self.ib.account_value) * 100
            print(f"      Notional risk (if assigned): ${notional_risk:,.0f} ({notional_pct:.1f}% of account)")
        print(f"      IV: {opportunity.get('iv', 0.30)*100:.1f}%")

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

        # Try to get live market data (will fail if no options subscription)
        market_data = self.ib.get_market_data(contract, timeout=10)

        # Validate market data
        import math
        has_valid_data = False
        if market_data:
            if (market_data.get('bid') and
                market_data.get('ask') and
                not math.isnan(market_data.get('bid', float('nan'))) and
                not math.isnan(market_data.get('ask', float('nan'))) and
                market_data['bid'] > 0 and
                market_data['ask'] > 0):
                has_valid_data = True

        if not has_valid_data:
            # Fallback: use the market_mid from edge scanner
            # This is common when you don't have options market data subscription
            print(f"    ℹ️  Using scanner price (no live options data)")

            if self.trading_config.use_limit_orders:
                limit_price = opportunity['market_mid']
                print(f"    → Limit price: ${limit_price:.2f}")
                order_type = 'LMT'
            else:
                limit_price = None
                order_type = 'MKT'
        else:
            # Use live market data
            print(f"    ℹ️  Using live market data (bid: ${market_data['bid']:.2f}, ask: ${market_data['ask']:.2f})")

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
                quantity=quantity,
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
            print(f"    Max positions reached: {len(self.positions)}/{self.risk_limits.max_positions}")
            if len(self.positions) > 0:
                print(f"    Current positions:")
                for key, pos in list(self.positions.items())[:5]:  # Show first 5
                    print(f"      - {key}: qty={pos.get('quantity', 'N/A')}, P&L=${pos.get('unrealized_pnl', 0):.2f}")
            return True

        return False

    def calculate_position_size(self, opportunity: pd.Series) -> int:
        """
        Calculate optimal position size based on:
        1. Target % of portfolio (max_position_size)
        2. Volatility adjustment (higher IV = smaller size)
        3. Risk limits (max notional exposure)

        Returns: Number of contracts to trade
        """
        account_value = self.ib.account_value
        option_price = opportunity['market_mid']
        iv = opportunity.get('iv', 0.30)  # Implied volatility
        strike = opportunity['strike']

        # Base position size: target % of account
        target_value = account_value * self.risk_limits.max_position_size
        base_contracts = int(target_value / (option_price * 100))

        # Volatility adjustment factor
        # Higher IV = more risk → reduce position size
        # Use 30% IV as baseline (typical for equity options)
        baseline_iv = 0.30
        vol_adjustment = baseline_iv / max(iv, 0.15)  # Don't divide by tiny numbers
        vol_adjusted_contracts = int(base_contracts * vol_adjustment)

        # Risk limit: for selling puts, max notional is strike * contracts * 100
        # Cap at 20% of account (max_portfolio_exposure)
        if 'SELL' in opportunity['signal']:
            max_notional = account_value * self.risk_limits.max_portfolio_exposure
            max_contracts_by_notional = int(max_notional / (strike * 100))
            final_contracts = min(vol_adjusted_contracts, max_contracts_by_notional)
        else:
            final_contracts = vol_adjusted_contracts

        # Minimum 1 contract
        final_contracts = max(1, final_contracts)

        return final_contracts

    def check_position_size(self, option_price: float) -> bool:
        """Check if position size is within limits (legacy method)"""
        account_value = self.ib.account_value
        position_value = option_price * 100  # Options are per 100 shares

        position_pct = position_value / account_value

        return position_pct <= self.risk_limits.max_position_size

    def record_trade(self, opportunity: pd.Series, action: str, trade):
        """Record trade in log"""
        # Extract order ID from trade object (ib_insync Trade object)
        order_id = getattr(trade, 'order', None)
        if order_id:
            order_id = getattr(order_id, 'orderId', 'N/A')
        else:
            order_id = 'N/A'

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'ticker': opportunity['ticker'],
            'type': opportunity['type'],
            'strike': opportunity['strike'],
            'expiry': opportunity['expiry'],
            'action': action,
            'edge_score': opportunity['edge_score'],
            'market_mid': opportunity['market_mid'],
            'order_id': order_id
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
