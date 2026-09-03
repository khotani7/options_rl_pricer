"""
Backtest Yesterday's Trades - Show actual P/L

Simulates what would have happened if we traded yesterday's opportunities:
- Entry prices from morning scan
- Exit based on 1.5x stop-loss or 50% profit target
- Current market prices to calculate P/L
- Shows when each trade would have exited
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Yesterday's top 5 trades based on our scan
TRADES = [
    {
        'ticker': 'NVDA',
        'type': 'SELL_PUT',
        'strike': 202,
        'expiry': '2026-09-09',
        'entry_price': 0.11,
        'edge': 30.7,
        'reason': 'Highest edge'
    },
    {
        'ticker': 'AAPL',
        'type': 'SELL_PUT',
        'strike': 305,
        'expiry': '2026-09-09',
        'entry_price': 0.15,
        'edge': 22.3,
        'reason': 'High edge, liquid'
    },
    {
        'ticker': 'NVDA',
        'type': 'SELL_PUT',
        'strike': 210,
        'expiry': '2026-09-09',
        'entry_price': 0.17,
        'edge': 25.3,
        'reason': 'High edge'
    },
    {
        'ticker': 'AAPL',
        'type': 'SELL_PUT',
        'strike': 312,
        'expiry': '2026-09-09',
        'entry_price': 0.39,
        'edge': 18.8,
        'reason': 'Good edge, volume'
    },
    {
        'ticker': 'NVDA',
        'type': 'SELL_PUT',
        'strike': 212,
        'expiry': '2026-09-09',
        'entry_price': 0.22,
        'edge': 21.2,
        'reason': 'High edge, volume'
    }
]

# Risk management
STOP_LOSS_MULTIPLIER = 1.5  # Exit at 1.5x entry price
PROFIT_TARGET_PCT = 0.50     # Exit at 50% profit


def get_current_option_price(ticker, strike, expiry, option_type='put'):
    """Get current market price for an option"""
    try:
        stock = yf.Ticker(ticker)
        chain = stock.option_chain(expiry)

        if option_type.lower() == 'put':
            options = chain.puts
        else:
            options = chain.calls

        # Find the strike
        option = options[options['strike'] == strike]

        if len(option) == 0:
            return None

        # Use last price or mid-price
        last = option['lastPrice'].iloc[0]
        bid = option['bid'].iloc[0]
        ask = option['ask'].iloc[0]

        # Use last if available, otherwise use mid
        if last > 0:
            return last
        else:
            return (bid + ask) / 2 if (bid > 0 and ask > 0) else None

    except Exception as e:
        print(f"  Error fetching {ticker} {strike} {option_type}: {e}")
        return None


def simulate_trade(trade, position_size=1):
    """
    Simulate a trade and determine exit price and P/L

    For short options:
    - Entry: Sell option, collect premium
    - Profit: Price goes DOWN (buy back cheaper)
    - Loss: Price goes UP (buy back more expensive)
    - Stop-loss: Exit if price >= 1.5x entry
    - Profit target: Exit if price <= 0.5x entry (50% profit)
    """

    ticker = trade['ticker']
    strike = trade['strike']
    expiry = trade['expiry']
    entry_price = trade['entry_price']
    option_type = trade['type'].split('_')[1].lower()  # 'SELL_PUT' -> 'put'

    # Get current market price
    current_price = get_current_option_price(ticker, strike, expiry, option_type)

    if current_price is None:
        return {
            'status': 'ERROR',
            'exit_price': None,
            'pnl': None,
            'pnl_pct': None,
            'exit_reason': 'Could not fetch current price'
        }

    # Calculate stop-loss and profit target prices
    stop_loss_price = entry_price * STOP_LOSS_MULTIPLIER
    profit_target_price = entry_price * (1 - PROFIT_TARGET_PCT)

    # Determine if trade would have exited
    exit_price = None
    exit_reason = None

    if current_price >= stop_loss_price:
        # Stop-loss triggered
        exit_price = stop_loss_price
        exit_reason = f'STOP_LOSS ({STOP_LOSS_MULTIPLIER}x)'

    elif current_price <= profit_target_price:
        # Profit target hit
        exit_price = profit_target_price
        exit_reason = f'PROFIT_TARGET ({PROFIT_TARGET_PCT*100:.0f}%)'

    else:
        # Still holding
        exit_price = current_price
        exit_reason = 'STILL_OPEN'

    # Calculate P&L (for short options)
    # P&L = (entry_price - exit_price) * 100 * position_size
    # Positive = profit, Negative = loss
    pnl = (entry_price - exit_price) * 100 * position_size
    pnl_pct = ((entry_price - exit_price) / entry_price) * 100

    return {
        'status': 'OPEN' if exit_reason == 'STILL_OPEN' else 'CLOSED',
        'entry_price': entry_price,
        'current_price': current_price,
        'exit_price': exit_price,
        'stop_loss_price': stop_loss_price,
        'profit_target_price': profit_target_price,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'exit_reason': exit_reason
    }


def main():
    print("=" * 80)
    print("BACKTEST: Yesterday's Trades Performance")
    print("=" * 80)
    print(f"Backtest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Entry Date: 2026-09-03 9:35 AM (simulated)")
    print(f"Position Size: 1 contract per trade")
    print(f"Stop-Loss: {STOP_LOSS_MULTIPLIER}x entry price")
    print(f"Profit Target: {PROFIT_TARGET_PCT*100:.0f}% profit")
    print("=" * 80)
    print()

    results = []
    total_pnl = 0

    for i, trade in enumerate(TRADES, 1):
        print(f"Trade #{i}: {trade['type']} {trade['ticker']} ${trade['strike']} PUT")
        print(f"  Expiry: {trade['expiry']}")
        print(f"  Edge: {trade['edge']:.1f}%")
        print(f"  Entry: ${trade['entry_price']:.2f}")

        # Simulate the trade
        result = simulate_trade(trade)

        if result['status'] == 'ERROR':
            print(f"  ❌ {result['exit_reason']}")
            print()
            continue

        # Display results
        print(f"  Current Price: ${result['current_price']:.2f}")
        print(f"  Stop-Loss at: ${result['stop_loss_price']:.2f}")
        print(f"  Profit Target at: ${result['profit_target_price']:.2f}")
        print()

        if result['exit_reason'] == 'STILL_OPEN':
            print(f"  📊 Status: STILL OPEN")
            print(f"  Unrealized P&L: ${result['pnl']:+.2f} ({result['pnl_pct']:+.1f}%)")
        else:
            exit_emoji = "✅" if result['pnl'] > 0 else "❌"
            print(f"  {exit_emoji} Status: CLOSED - {result['exit_reason']}")
            print(f"  Exit Price: ${result['exit_price']:.2f}")
            print(f"  Realized P&L: ${result['pnl']:+.2f} ({result['pnl_pct']:+.1f}%)")

        print()
        print("-" * 80)
        print()

        # Track results
        results.append({
            'trade': f"{trade['ticker']} ${trade['strike']} PUT",
            'entry': trade['entry_price'],
            'current': result['current_price'],
            'exit': result['exit_price'],
            'pnl': result['pnl'],
            'pnl_pct': result['pnl_pct'],
            'status': result['exit_reason']
        })

        total_pnl += result['pnl']

    # Summary
    print("=" * 80)
    print("PORTFOLIO SUMMARY")
    print("=" * 80)

    df = pd.DataFrame(results)

    # Calculate statistics
    closed_trades = df[df['status'] != 'STILL_OPEN']
    open_trades = df[df['status'] == 'STILL_OPEN']

    winning_trades = df[df['pnl'] > 0]
    losing_trades = df[df['pnl'] < 0]

    print(f"\nTotal Trades: {len(df)}")
    print(f"  Closed: {len(closed_trades)}")
    print(f"  Still Open: {len(open_trades)}")
    print()

    print(f"Win/Loss Record:")
    print(f"  Wins: {len(winning_trades)} ({len(winning_trades)/len(df)*100:.0f}%)")
    print(f"  Losses: {len(losing_trades)} ({len(losing_trades)/len(df)*100:.0f}%)")
    print()

    if len(winning_trades) > 0:
        print(f"Average Win: ${winning_trades['pnl'].mean():.2f}")
    if len(losing_trades) > 0:
        print(f"Average Loss: ${losing_trades['pnl'].mean():.2f}")
    print()

    print(f"Total P&L: ${total_pnl:+.2f}")

    # Calculate return on capital (assuming each trade requires ~$500 margin)
    estimated_capital = len(df) * 500
    roi = (total_pnl / estimated_capital) * 100 if estimated_capital > 0 else 0
    print(f"Estimated Capital Used: ${estimated_capital:,.0f}")
    print(f"Return on Capital: {roi:+.2f}%")
    print()

    # Show each trade result
    print("=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    print()

    print(f"{'Trade':<25} {'Entry':<8} {'Current':<8} {'P&L':<10} {'P&L %':<10} {'Status':<20}")
    print("-" * 80)

    for _, row in df.iterrows():
        pnl_emoji = "💰" if row['pnl'] > 0 else "📉" if row['pnl'] < 0 else "➡️"
        print(f"{row['trade']:<25} ${row['entry']:<7.2f} ${row['current']:<7.2f} "
              f"{pnl_emoji} ${row['pnl']:>7.2f} {row['pnl_pct']:>+7.1f}% {row['status']:<20}")

    print()
    print("=" * 80)
    print()

    # Conclusion
    if total_pnl > 0:
        print(f"✅ PROFITABLE: Portfolio up ${total_pnl:.2f} ({roi:+.2f}% ROI)")
    elif total_pnl < 0:
        print(f"❌ LOSS: Portfolio down ${total_pnl:.2f} ({roi:+.2f}% ROI)")
    else:
        print(f"➡️ BREAK EVEN: No net P&L")

    print()

    # Next steps
    print("=" * 80)
    print("INTERPRETATION")
    print("=" * 80)
    print()

    if len(open_trades) > 0:
        print(f"⚠️  {len(open_trades)} trades still open - these could still hit stop-loss or profit target")
        print(f"   Current unrealized P&L on open trades: ${open_trades['pnl'].sum():+.2f}")
        print()

    if len(closed_trades) > 0:
        stop_losses = closed_trades[closed_trades['status'].str.contains('STOP_LOSS')]
        profit_targets = closed_trades[closed_trades['status'].str.contains('PROFIT_TARGET')]

        print(f"Closed Trades Breakdown:")
        print(f"  Stop-losses hit: {len(stop_losses)}")
        print(f"  Profit targets hit: {len(profit_targets)}")
        print()

    win_rate = len(winning_trades) / len(df) * 100

    if win_rate >= 70:
        print("✅ Win rate meets target (70%+)")
    else:
        print(f"⚠️  Win rate below target: {win_rate:.0f}% vs 70% target")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
