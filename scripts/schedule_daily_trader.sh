#!/bin/bash
# Daily Options Trading Scheduler
#
# This script runs the automated trader at specific times each day
# Handles:
# - Morning scan at market open (9:35 AM ET)
# - Hourly monitoring throughout the day
# - End-of-day position closing (3:45 PM ET)

# Configuration
PROJECT_DIR="/Users/kabirhotani/Downloads/options_rl_pricer"
MODE="paper"  # Change to "live" for real trading (BE CAREFUL!)
TICKERS="TSLA AAPL MU SPY QQQ"
MIN_EDGE="10.0"
MAX_POSITION_SIZE="5.0"
STOP_LOSS="30.0"
PROFIT_TARGET="50.0"

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment if you have one
# source venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_DIR"

# Get current time
CURRENT_HOUR=$(date +%H)
CURRENT_MINUTE=$(date +%M)

echo "==================================================================="
echo "Daily Trader Scheduler - $(date)"
echo "==================================================================="

# Check if IB Gateway is running
if ! pgrep -f "gateway" > /dev/null; then
    echo "ERROR: IB Gateway is not running!"
    echo "Please start IB Gateway and login before running this script."
    exit 1
fi

# Morning scan (9:35 AM ET - 5 min after market open)
if [ "$CURRENT_HOUR" -eq 9 ] && [ "$CURRENT_MINUTE" -ge 30 ] && [ "$CURRENT_MINUTE" -lt 40 ]; then
    echo "Morning market open - Running initial scan and trades..."
    python scripts/daily_trader.py \
        --mode "$MODE" \
        --tickers $TICKERS \
        --min-edge "$MIN_EDGE" \
        --max-position-size "$MAX_POSITION_SIZE" \
        --stop-loss "$STOP_LOSS" \
        --profit-target "$PROFIT_TARGET"

# Mid-day monitoring (10 AM - 3 PM, every hour)
elif [ "$CURRENT_HOUR" -ge 10 ] && [ "$CURRENT_HOUR" -lt 15 ]; then
    echo "Mid-day monitoring - Checking for new opportunities..."
    python scripts/daily_trader.py \
        --mode "$MODE" \
        --tickers $TICKERS \
        --min-edge "$MIN_EDGE" \
        --max-position-size "$MAX_POSITION_SIZE" \
        --stop-loss "$STOP_LOSS" \
        --profit-target "$PROFIT_TARGET"

# End of day (3:45 PM - close positions before market close)
elif [ "$CURRENT_HOUR" -eq 15 ] && [ "$CURRENT_MINUTE" -ge 45 ]; then
    echo "End of day - Closing all positions..."
    python scripts/close_all_positions.py --mode "$MODE"

else
    echo "Outside trading hours or scheduled scan times"
    echo "Current time: $CURRENT_HOUR:$CURRENT_MINUTE"
fi

echo "==================================================================="
echo "Scheduler run complete"
echo "==================================================================="
