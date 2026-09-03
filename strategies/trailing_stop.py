"""
Trailing Stop-Loss for Options Trading

A trailing stop locks in profits as a position moves in your favor while
protecting against reversals.

Features:
1. Dynamic stop-loss that "trails" the price
2. Locks in profits automatically
3. Gives position room to breathe
4. Exits on reversals

Example:
- Sell PUT @ $5.00
- Initial stop: $10.00 (2x entry)
- Price drops to $2.50 (up 50%)
  → Trailing stop activates at $3.75 (protect 25% of gain)
- If price rises back to $3.75 → EXIT, lock in $1.25 profit
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class TrailingStop:
    """Trailing stop-loss manager for options positions"""

    entry_price: float
    current_price: float
    position_type: str  # 'long' or 'short'

    # Stop parameters
    initial_stop_multiplier: float = 2.0  # Initial stop at 2x entry
    activation_threshold: float = 0.20  # Activate trailing after 20% profit
    trail_percentage: float = 0.50  # Protect 50% of gains

    # State
    highest_profit_pct: float = 0.0
    stop_price: Optional[float] = None
    is_trailing: bool = False

    def update(self, current_price: float) -> dict:
        """
        Update stop-loss based on current price

        Returns:
            dict with:
                - should_exit: bool
                - reason: str
                - stop_price: float
                - profit_locked: float
        """
        self.current_price = current_price

        # Calculate current P&L percentage
        if self.position_type == 'short':
            # For short options, profit when price decreases
            pnl_pct = (self.entry_price - current_price) / self.entry_price
        else:
            # For long options, profit when price increases
            pnl_pct = (current_price - self.entry_price) / self.entry_price

        # Update highest profit seen
        if pnl_pct > self.highest_profit_pct:
            self.highest_profit_pct = pnl_pct

        # Check initial stop-loss (2x entry price)
        if self.position_type == 'short':
            # Short option: stop if price rises too much
            initial_stop = self.entry_price * self.initial_stop_multiplier
            if current_price >= initial_stop:
                return {
                    'should_exit': True,
                    'reason': 'INITIAL_STOP_LOSS',
                    'stop_price': initial_stop,
                    'profit_locked': (self.entry_price - current_price) * 100,
                    'pnl_pct': pnl_pct * 100
                }
        else:
            # Long option: stop if price falls too much
            initial_stop = self.entry_price / self.initial_stop_multiplier
            if current_price <= initial_stop:
                return {
                    'should_exit': True,
                    'reason': 'INITIAL_STOP_LOSS',
                    'stop_price': initial_stop,
                    'profit_locked': (current_price - self.entry_price) * 100,
                    'pnl_pct': pnl_pct * 100
                }

        # Activate trailing stop if we've hit the profit threshold
        if not self.is_trailing and self.highest_profit_pct >= self.activation_threshold:
            self.is_trailing = True
            print(f"  ✓ Trailing stop activated at {self.highest_profit_pct * 100:.1f}% profit")

        # Update trailing stop price
        if self.is_trailing:
            # Protect trail_percentage of the highest profit
            profit_to_protect = self.highest_profit_pct * self.trail_percentage

            if self.position_type == 'short':
                # For short, trailing stop is above entry
                self.stop_price = self.entry_price * (1 - profit_to_protect)

                # Check if trailing stop hit
                if current_price >= self.stop_price:
                    actual_profit = (self.entry_price - current_price) / self.entry_price
                    return {
                        'should_exit': True,
                        'reason': 'TRAILING_STOP',
                        'stop_price': self.stop_price,
                        'profit_locked': (self.entry_price - current_price) * 100,
                        'pnl_pct': actual_profit * 100,
                        'peak_profit_pct': self.highest_profit_pct * 100
                    }
            else:
                # For long, trailing stop is below entry
                self.stop_price = self.entry_price * (1 + profit_to_protect)

                # Check if trailing stop hit
                if current_price <= self.stop_price:
                    actual_profit = (current_price - self.entry_price) / self.entry_price
                    return {
                        'should_exit': True,
                        'reason': 'TRAILING_STOP',
                        'stop_price': self.stop_price,
                        'profit_locked': (current_price - self.entry_price) * 100,
                        'pnl_pct': actual_profit * 100,
                        'peak_profit_pct': self.highest_profit_pct * 100
                    }

        # No exit signal
        return {
            'should_exit': False,
            'reason': None,
            'stop_price': self.stop_price,
            'profit_locked': None,
            'pnl_pct': pnl_pct * 100,
            'is_trailing': self.is_trailing,
            'highest_profit_pct': self.highest_profit_pct * 100
        }


class PositionManager:
    """Manage multiple positions with trailing stops"""

    def __init__(self):
        self.positions = {}  # key: position_id, value: TrailingStop

    def add_position(
        self,
        position_id: str,
        entry_price: float,
        position_type: str,
        initial_stop_multiplier: float = 2.0,
        activation_threshold: float = 0.20,
        trail_percentage: float = 0.50
    ):
        """Add a new position to track"""
        self.positions[position_id] = TrailingStop(
            entry_price=entry_price,
            current_price=entry_price,
            position_type=position_type,
            initial_stop_multiplier=initial_stop_multiplier,
            activation_threshold=activation_threshold,
            trail_percentage=trail_percentage
        )

    def update_position(self, position_id: str, current_price: float) -> dict:
        """Update a position and check for exit signals"""
        if position_id not in self.positions:
            raise ValueError(f"Position {position_id} not found")

        return self.positions[position_id].update(current_price)

    def get_position_status(self, position_id: str) -> dict:
        """Get current status of a position"""
        if position_id not in self.positions:
            return None

        pos = self.positions[position_id]
        return {
            'entry_price': pos.entry_price,
            'current_price': pos.current_price,
            'stop_price': pos.stop_price,
            'is_trailing': pos.is_trailing,
            'highest_profit_pct': pos.highest_profit_pct * 100,
        }

    def remove_position(self, position_id: str):
        """Remove a position (after exit)"""
        if position_id in self.positions:
            del self.positions[position_id]


# Example usage and testing
if __name__ == "__main__":
    print("=" * 70)
    print("TRAILING STOP-LOSS SIMULATION")
    print("=" * 70)

    # Simulate a SHORT PUT trade
    print("\nScenario: SHORT PUT @ $5.00")
    print("-" * 70)

    stop = TrailingStop(
        entry_price=5.00,
        current_price=5.00,
        position_type='short',
        initial_stop_multiplier=2.0,  # Stop at $10
        activation_threshold=0.20,  # Activate at 20% profit
        trail_percentage=0.50  # Protect 50% of gains
    )

    # Simulate price movements
    price_path = [
        5.00,  # Entry
        4.50,  # +10% profit
        4.00,  # +20% profit → trailing stop activates!
        3.50,  # +30% profit → stop moves down
        3.00,  # +40% profit → stop moves down more
        3.50,  # Reversal... check if stop hit
        4.00,  # Reversal continues...
        3.75,  # Should trigger trailing stop!
    ]

    print("\nPrice Path Simulation:")
    print(f"{'Price':<10} {'P&L %':<10} {'Action':<20} {'Stop Price':<12}")
    print("-" * 70)

    for price in price_path:
        result = stop.update(price)

        pnl_pct = result['pnl_pct']
        action = "Hold"
        if result['should_exit']:
            action = f"EXIT ({result['reason']})"

        stop_price = f"${result['stop_price']:.2f}" if result['stop_price'] else "N/A"

        print(f"${price:<9.2f} {pnl_pct:>6.1f}%    {action:<20} {stop_price}")

        if result['should_exit']:
            print(f"\n✓ Position closed!")
            print(f"  Entry: ${stop.entry_price:.2f}")
            print(f"  Exit: ${price:.2f}")
            print(f"  Profit: ${result['profit_locked']:.2f} ({result['pnl_pct']:.1f}%)")
            if 'peak_profit_pct' in result:
                print(f"  Peak profit was: {result['peak_profit_pct']:.1f}%")
            break

    print("\n" + "=" * 70)
    print("BENEFITS OF TRAILING STOP")
    print("=" * 70)
    print("""
Without trailing stop:
  - Ride position all the way down from +40% to -20%
  - Watch profits evaporate
  - Exit at loss

With trailing stop:
  - Lock in profits as position moves in your favor
  - Protect gains (50% of peak profit)
  - Exit with profit even on reversals
  - Sleep better at night!

Example above:
  - Peak profit: +40% ($2.00)
  - Trailing stop protected 50% of that = +20% ($1.00)
  - Exited at +25% ($1.25) when price reversed
  - WITHOUT trailing stop: might have held to $0 or worse
    """)

    # Test with position manager
    print("\n" + "=" * 70)
    print("POSITION MANAGER - Multiple Positions")
    print("=" * 70)

    manager = PositionManager()

    # Add multiple positions
    manager.add_position('AAPL_215P', entry_price=4.70, position_type='short')
    manager.add_position('NVDA_500C', entry_price=12.50, position_type='long')

    print("\nTracking 2 positions:")
    print("1. AAPL SHORT PUT @ $4.70")
    print("2. NVDA LONG CALL @ $12.50")

    # Update AAPL position
    print("\nAPPL PUT drops to $2.35 (+50% profit):")
    result = manager.update_position('AAPL_215P', 2.35)
    print(f"  P&L: {result['pnl_pct']:.1f}%")
    print(f"  Trailing: {result['is_trailing']}")
    print(f"  Stop at: ${result['stop_price']:.2f}" if result['stop_price'] else "  No stop yet")

    # Get status
    status = manager.get_position_status('AAPL_215P')
    print(f"\nPosition Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
