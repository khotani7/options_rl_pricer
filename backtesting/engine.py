"""
Backtesting engine for options trading strategies

Simulates trading with realistic costs, slippage, and position management
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Represents an options order"""
    order_id: int
    ticker: str
    strike: float
    maturity_days: int
    option_type: str  # 'put' or 'call'
    side: OrderSide
    quantity: int
    limit_price: Optional[float] = None  # None = market order
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    filled_date: Optional[datetime] = None
    commission: float = 0.65  # Per contract
    notes: str = ""


@dataclass
class Position:
    """Represents an open options position"""
    ticker: str
    strike: float
    maturity_days: int
    option_type: str
    quantity: int  # Positive = long, negative = short
    avg_entry_price: float
    entry_date: datetime
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    max_drawdown: float = 0.0
    max_profit: float = 0.0


@dataclass
class Trade:
    """Represents a completed trade (entry + exit)"""
    entry_date: datetime
    exit_date: datetime
    ticker: str
    strike: float
    option_type: str
    side: str  # 'LONG' or 'SHORT'
    quantity: int
    entry_price: float
    exit_price: float
    realized_pnl: float
    total_commission: float
    hold_days: int
    return_pct: float
    notes: str = ""


@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    initial_capital: float = 100000.0
    max_position_size: float = 0.10  # 10% of capital per position
    max_positions: int = 10
    commission_per_contract: float = 0.65
    slippage_bps: int = 5  # 5 basis points slippage
    margin_requirement: float = 0.20  # 20% margin for short positions
    risk_free_rate: float = 0.04


class BacktestEngine:
    """
    Core backtesting engine

    Simulates trading strategies with realistic market conditions
    """

    def __init__(self, config: BacktestConfig, data_provider):
        self.config = config
        self.data_provider = data_provider

        # Portfolio state
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.trades: List[Trade] = []

        # Performance tracking
        self.equity_curve = []
        self.daily_returns = []

        # Counters
        self.order_id_counter = 0
        self.current_date = None

    def simulate_paths(self, S0, r, q, sigma, T, n_steps, n_paths, rng):
        """
        Simulate GBM paths for LSM pricing

        This is a wrapper around the simulation.gbm module for convenience
        """
        from simulation.gbm import simulate_gbm_paths
        return simulate_gbm_paths(S0, r, q, sigma, T, n_steps, n_paths, rng)

    def place_order(self, ticker: str, strike: float, maturity_days: int,
                   option_type: str, side: OrderSide, quantity: int,
                   limit_price: Optional[float] = None, notes: str = "") -> Order:
        """
        Place an order (market or limit)

        Returns Order object
        """
        self.order_id_counter += 1

        order = Order(
            order_id=self.order_id_counter,
            ticker=ticker,
            strike=strike,
            maturity_days=maturity_days,
            option_type=option_type,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            commission=self.config.commission_per_contract,
            notes=notes
        )

        self.orders.append(order)
        return order

    def process_orders(self, date: datetime):
        """
        Process pending orders for the current date

        Simulates order fills with realistic slippage
        """
        for order in self.orders:
            if order.status != OrderStatus.PENDING:
                continue

            # Get market quote
            quote = self.data_provider.get_option_quote(
                order.ticker, date, order.strike, order.maturity_days, order.option_type
            )

            if quote is None:
                order.status = OrderStatus.REJECTED
                order.notes += " | No market data available"
                continue

            # Determine fill price with slippage
            if order.side == OrderSide.BUY:
                market_price = quote['ask']
                if order.limit_price and order.limit_price < quote['bid']:
                    # Limit price too low, order doesn't fill
                    continue
                fill_price = min(order.limit_price, market_price) if order.limit_price else market_price
            else:  # SELL
                market_price = quote['bid']
                if order.limit_price and order.limit_price > quote['ask']:
                    # Limit price too high, order doesn't fill
                    continue
                fill_price = max(order.limit_price, market_price) if order.limit_price else market_price

            # Add slippage (in basis points)
            slippage = fill_price * (self.config.slippage_bps / 10000.0)
            if order.side == OrderSide.BUY:
                fill_price += slippage
            else:
                fill_price -= slippage

            # Calculate total cost
            total_cost = fill_price * order.quantity * 100  # Options are per 100 shares
            commission = order.commission * order.quantity

            # Check if we have enough capital
            if order.side == OrderSide.BUY:
                required_capital = total_cost + commission
                if required_capital > self.cash:
                    order.status = OrderStatus.REJECTED
                    order.notes += " | Insufficient capital"
                    continue
                self.cash -= required_capital
            else:  # SELL (short)
                # For shorts, we receive cash but need margin
                margin_required = total_cost * self.config.margin_requirement
                if margin_required > self.cash:
                    order.status = OrderStatus.REJECTED
                    order.notes += " | Insufficient margin"
                    continue
                self.cash += (total_cost - commission)

            # Fill the order
            order.status = OrderStatus.FILLED
            order.filled_price = fill_price
            order.filled_date = date

            # Update or create position
            self._update_position(order, fill_price, date)

    def _update_position(self, order: Order, fill_price: float, date: datetime):
        """Update positions after order fill"""
        pos_key = f"{order.ticker}_{order.strike}_{order.maturity_days}_{order.option_type}"

        if pos_key in self.positions:
            # Existing position
            pos = self.positions[pos_key]

            if order.side == OrderSide.BUY:
                # Adding to long or reducing short
                new_qty = pos.quantity + order.quantity
            else:
                # Adding to short or reducing long
                new_qty = pos.quantity - order.quantity

            if new_qty == 0:
                # Position closed - record trade
                self._record_trade(pos, fill_price, date)
                del self.positions[pos_key]
            else:
                # Update average entry price
                total_value = pos.avg_entry_price * abs(pos.quantity) + fill_price * order.quantity
                pos.quantity = new_qty
                pos.avg_entry_price = total_value / abs(new_qty)
        else:
            # New position
            qty = order.quantity if order.side == OrderSide.BUY else -order.quantity
            self.positions[pos_key] = Position(
                ticker=order.ticker,
                strike=order.strike,
                maturity_days=order.maturity_days,
                option_type=order.option_type,
                quantity=qty,
                avg_entry_price=fill_price,
                entry_date=date
            )

    def _record_trade(self, position: Position, exit_price: float, exit_date: datetime):
        """Record a completed trade"""
        hold_days = (exit_date - position.entry_date).days

        if position.quantity > 0:  # Long position
            pnl = (exit_price - position.avg_entry_price) * position.quantity * 100
            side = "LONG"
        else:  # Short position
            pnl = (position.avg_entry_price - exit_price) * abs(position.quantity) * 100
            side = "SHORT"

        commission = self.config.commission_per_contract * abs(position.quantity) * 2  # Entry + exit
        realized_pnl = pnl - commission

        return_pct = realized_pnl / (position.avg_entry_price * abs(position.quantity) * 100) * 100

        trade = Trade(
            entry_date=position.entry_date,
            exit_date=exit_date,
            ticker=position.ticker,
            strike=position.strike,
            option_type=position.option_type,
            side=side,
            quantity=abs(position.quantity),
            entry_price=position.avg_entry_price,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            total_commission=commission,
            hold_days=hold_days,
            return_pct=return_pct
        )

        self.trades.append(trade)

    def update_positions(self, date: datetime):
        """Mark-to-market all open positions"""
        total_unrealized_pnl = 0

        for pos_key, pos in list(self.positions.items()):
            # Get current market price
            quote = self.data_provider.get_option_quote(
                pos.ticker, date, pos.strike, pos.maturity_days, pos.option_type
            )

            if quote is None:
                continue

            current_price = quote['mid']
            pos.current_value = current_price * abs(pos.quantity) * 100

            if pos.quantity > 0:  # Long
                unrealized_pnl = (current_price - pos.avg_entry_price) * pos.quantity * 100
            else:  # Short
                unrealized_pnl = (pos.avg_entry_price - current_price) * abs(pos.quantity) * 100

            pos.unrealized_pnl = unrealized_pnl
            total_unrealized_pnl += unrealized_pnl

            # Track max profit/drawdown
            pos.max_profit = max(pos.max_profit, unrealized_pnl)
            pos.max_drawdown = min(pos.max_drawdown, unrealized_pnl)

            # Auto-close positions at expiry
            if pos.maturity_days <= 0:
                # Exercise or expire
                self._record_trade(pos, current_price, date)
                del self.positions[pos_key]

            # Decrement days to maturity
            pos.maturity_days -= 1

        return total_unrealized_pnl

    def get_portfolio_value(self) -> float:
        """Calculate total portfolio value"""
        positions_value = sum(pos.current_value for pos in self.positions.values())
        return self.cash + positions_value

    def run_backtest(self, strategy: Callable, start_date: str, end_date: str):
        """
        Run backtest with a given strategy

        strategy: Callable that takes (engine, date) and places orders

        Example:
            def my_strategy(engine, date):
                # Strategy logic
                engine.place_order('AAPL', 315, 30, 'put', OrderSide.BUY, 1)
        """
        trading_dates = self.data_provider.get_trading_dates()
        trading_dates = trading_dates[(trading_dates >= start_date) & (trading_dates <= end_date)]

        print(f"\n{'='*70}")
        print(f"Running Backtest: {start_date} to {end_date}")
        print(f"{'='*70}")
        print(f"Initial Capital: ${self.config.initial_capital:,.2f}\n")

        for date in trading_dates:
            self.current_date = date

            # 1. Update positions (mark-to-market)
            unrealized_pnl = self.update_positions(date)

            # 2. Process pending orders
            self.process_orders(date)

            # 3. Run strategy to generate new signals
            strategy(self, date)

            # 4. Record equity
            portfolio_value = self.get_portfolio_value()
            self.equity_curve.append({
                'date': date,
                'cash': self.cash,
                'positions_value': portfolio_value - self.cash,
                'total_value': portfolio_value,
                'unrealized_pnl': unrealized_pnl,
                'num_positions': len(self.positions)
            })

            # Calculate daily return
            if len(self.equity_curve) > 1:
                prev_value = self.equity_curve[-2]['total_value']
                daily_return = (portfolio_value - prev_value) / prev_value
                self.daily_returns.append(daily_return)

        # Close all remaining positions at end
        for pos in list(self.positions.values()):
            quote = self.data_provider.get_option_quote(
                pos.ticker, self.current_date, pos.strike, pos.maturity_days, pos.option_type
            )
            if quote:
                self._record_trade(pos, quote['mid'], self.current_date)

        self.positions.clear()

        print(f"\nBacktest Complete!")
        print(f"Final Portfolio Value: ${self.get_portfolio_value():,.2f}")
        print(f"Total Return: {(self.get_portfolio_value() / self.config.initial_capital - 1) * 100:.2f}%")
        print(f"Total Trades: {len(self.trades)}")

    def get_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        if not self.trades:
            return {"error": "No trades executed"}

        # Trade statistics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.realized_pnl > 0]
        losing_trades = [t for t in self.trades if t.realized_pnl < 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        avg_win = np.mean([t.realized_pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.realized_pnl for t in losing_trades]) if losing_trades else 0

        # P&L
        total_pnl = sum(t.realized_pnl for t in self.trades)
        total_commission = sum(t.total_commission for t in self.trades)

        # Returns
        final_value = self.get_portfolio_value()
        total_return = (final_value / self.config.initial_capital - 1) * 100

        # Risk metrics
        returns_array = np.array(self.daily_returns) if self.daily_returns else np.array([0])
        sharpe_ratio = np.mean(returns_array) / np.std(returns_array) * np.sqrt(252) if np.std(returns_array) > 0 else 0

        # Max drawdown
        equity_values = [e['total_value'] for e in self.equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for value in equity_values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'total_pnl': total_pnl,
            'total_commission': total_commission,
            'net_pnl': total_pnl - total_commission,
            'total_return_pct': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown_pct': max_dd * 100,
            'initial_capital': self.config.initial_capital,
            'final_value': final_value
        }

    def export_results(self, output_dir: str = 'outputs/backtest'):
        """Export backtest results to CSV"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        # Equity curve
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.to_csv(f'{output_dir}/equity_curve.csv', index=False)

        # Trades
        trades_df = pd.DataFrame([vars(t) for t in self.trades])
        trades_df.to_csv(f'{output_dir}/trades.csv', index=False)

        # Performance metrics
        metrics = self.get_performance_metrics()
        metrics_df = pd.DataFrame([metrics])
        metrics_df.to_csv(f'{output_dir}/performance_metrics.csv', index=False)

        print(f"\nResults exported to {output_dir}/")
