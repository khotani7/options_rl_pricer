# Daily Trading Guide - Automated Options Trading

How to run the automated trader throughout the trading day.

---

## Quick Start (Tomorrow Morning)

### Option 1: Simple - Run in Terminal

```bash
cd /Users/kabirhotani/Downloads/options_rl_pricer

# Start IB Gateway or TWS first (see setup below)
# Then run the trader:
PYTHONPATH=. python scripts/run_trader.py --mode paper --tickers AAPL NVDA MSFT

# Leave terminal open - it will scan every 15 minutes
```

### Option 2: Background Process (Recommended)

```bash
# Run in background with logging
nohup PYTHONPATH=. python scripts/run_trader.py \
  --mode paper \
  --tickers AAPL NVDA MSFT TSLA META \
  > outputs/trader_$(date +%Y%m%d).log 2>&1 &

# Save the process ID
echo $! > outputs/trader.pid

# Check logs in real-time
tail -f outputs/trader_$(date +%Y%m%d).log
```

### Option 3: Scheduled with Cron (Fully Automated)

I'll create a startup script for this below.

---

## Pre-Market Setup (8:00 AM ET)

### Step 1: Start IB Gateway

```bash
# Option A: Manual
# 1. Open IB Gateway application
# 2. Login with paper trading credentials
# 3. Verify port 7497 is active (paper trading)

# Option B: Automated (if you have IB Gateway installed)
open -a "IB Gateway"
# Wait for login, then continue
```

### Step 2: Verify Connection

```bash
# Test IB connection
PYTHONPATH=. python test_ib_connection.py

# Should show:
# ✓ Connected to IB Gateway (Paper Trading)
# ✓ Account: DU1234567
# ✓ Buying power: $100,000
```

### Step 3: Start the Trader

```bash
# Paper trading mode (recommended for testing)
PYTHONPATH=. python scripts/run_trader.py \
  --mode paper \
  --tickers AAPL NVDA MSFT \
  --scan-interval 15 \
  --max-positions 5

# The trader will:
# - Scan for edges every 15 minutes
# - Skip tickers with earnings in next 7 days
# - Use dynamic edge thresholds (2% for AAPL, 2.5% for NVDA, etc.)
# - Apply 1.5x stop-loss on all positions
# - Monitor positions continuously
```

---

## During Market Hours (9:30 AM - 4:00 PM ET)

The trader runs automatically:

### What It Does

**Every 15 minutes:**
1. Check earnings calendar for each ticker
2. Scan option chains for LSM edges
3. Filter by minimum edge threshold (dynamic per ticker)
4. Execute trades if opportunities found

**Continuously:**
1. Monitor open positions
2. Check 1.5x stop-loss on all positions
3. Check 50% profit targets
4. Update P&L and risk metrics

### Monitoring

```bash
# Watch logs live
tail -f outputs/trader_YYYYMMDD.log

# Check positions
PYTHONPATH=. python -c "
from trading.ib_connector import IBConnector, IBConfig
ib = IBConnector(IBConfig(port=7497))
ib.connect()
positions = ib.get_positions()
for p in positions:
    print(f'{p}')
"

# Check account status
PYTHONPATH=. python scripts/check_account.py
```

---

## After Market Close (4:00 PM ET)

### Step 1: Review Performance

```bash
# View today's trading log
cat outputs/trader_$(date +%Y%m%d).log

# Generate performance report
PYTHONPATH=. python scripts/daily_performance_report.py
```

### Step 2: Close Positions (Optional)

```bash
# Close all positions before market close (if desired)
PYTHONPATH=. python scripts/close_all_positions.py --mode paper
```

### Step 3: Stop the Trader

```bash
# If running in background
kill $(cat outputs/trader.pid)

# Verify stopped
ps aux | grep run_trader.py
```

### Step 4: Shutdown IB Gateway

```bash
# Manual: Close IB Gateway app
# Or keep it running for next day
```

---

## Automated Daily Schedule (Advanced)

Create a cron job to run automatically:

### Setup Script

```bash
#!/bin/bash
# File: scripts/schedule_daily_trader.sh

# This script starts the trader at market open and stops at close

TRADER_DIR="/Users/kabirhotani/Downloads/options_rl_pricer"
LOG_FILE="$TRADER_DIR/outputs/trader_$(date +%Y%m%d).log"
PID_FILE="$TRADER_DIR/outputs/trader.pid"

case "$1" in
  start)
    echo "Starting trader at $(date)" >> $LOG_FILE
    cd $TRADER_DIR

    # Start trader in background
    nohup PYTHONPATH=. python scripts/run_trader.py \
      --mode paper \
      --tickers AAPL NVDA MSFT META TSLA \
      --scan-interval 15 \
      --max-positions 5 \
      >> $LOG_FILE 2>&1 &

    echo $! > $PID_FILE
    echo "Trader started (PID: $(cat $PID_FILE))"
    ;;

  stop)
    echo "Stopping trader at $(date)" >> $LOG_FILE
    if [ -f $PID_FILE ]; then
      kill $(cat $PID_FILE)
      rm $PID_FILE
      echo "Trader stopped"
    else
      echo "No PID file found"
    fi
    ;;

  status)
    if [ -f $PID_FILE ] && ps -p $(cat $PID_FILE) > /dev/null; then
      echo "Trader is running (PID: $(cat $PID_FILE))"
    else
      echo "Trader is not running"
    fi
    ;;

  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
```

### Make Executable

```bash
chmod +x scripts/schedule_daily_trader.sh
```

### Add to Crontab

```bash
crontab -e

# Add these lines:
# Start trader at 9:25 AM ET (5 min before market open)
25 9 * * 1-5 /Users/kabirhotani/Downloads/options_rl_pricer/scripts/schedule_daily_trader.sh start

# Stop trader at 4:05 PM ET (5 min after market close)
5 16 * * 1-5 /Users/kabirhotani/Downloads/options_rl_pricer/scripts/schedule_daily_trader.sh stop

# Note: Adjust for your timezone! (above is ET)
```

---

## Configuration Options

### Tickers to Trade

```python
# Conservative (3-5 tickers)
--tickers AAPL MSFT GOOGL

# Moderate (5-8 tickers)
--tickers AAPL MSFT NVDA META AMZN

# Aggressive (8-10 tickers)
--tickers AAPL MSFT NVDA META AMZN TSLA GOOGL JPM XOM
```

### Scan Frequency

```python
--scan-interval 15  # Every 15 minutes (default)
--scan-interval 30  # Every 30 minutes (less aggressive)
--scan-interval 5   # Every 5 minutes (very aggressive)
```

### Risk Limits

Edit `scripts/run_trader.py`:

```python
risk_limits = RiskLimits(
    max_portfolio_exposure=0.20,  # 20% of account
    max_position_size=0.05,       # 5% per position
    max_daily_loss=0.02,          # 2% max daily loss
    max_positions=10,             # Max 10 positions
    stop_loss_multiplier=1.5,     # Exit at 1.5x entry
    profit_target_pct=0.50        # Take profit at 50%
)
```

---

## Safety Checklist

Before starting automated trading:

- [ ] IB Gateway/TWS running on **port 7497** (paper trading)
- [ ] Verified connection with `test_ib_connection.py`
- [ ] Using `--mode paper` flag (NOT live)
- [ ] Set appropriate position size limits
- [ ] Reviewed and understand stop-loss settings
- [ ] Have enough simulated capital ($10k+ recommended)
- [ ] Checked that tickers don't have earnings this week
- [ ] Logs directory exists: `mkdir -p outputs`

---

## Troubleshooting

### "Connection refused" error
```bash
# Check IB Gateway is running
ps aux | grep "IB Gateway"

# Verify port
lsof -i :7497

# Restart IB Gateway
```

### "No edges found"
```bash
# This is normal! It means:
# - No mispriced options detected
# - Earnings filter blocking trades
# - Edge thresholds not met

# Check what's being filtered:
PYTHONPATH=. python scripts/edge_scanner.py --ticker AAPL --min-edge 2.0
```

### "Rate limit exceeded" (yfinance)
```bash
# Wait 60 seconds between scans
# Or reduce number of tickers
# Or increase --scan-interval
```

### Trader stopped unexpectedly
```bash
# Check logs
tail -100 outputs/trader_$(date +%Y%m%d).log

# Common causes:
# - IB Gateway disconnected
# - Daily loss limit hit
# - Network error
```

---

## Next Steps

1. **Tomorrow morning:**
   - Start IB Gateway at 9:20 AM ET
   - Run `scripts/schedule_daily_trader.sh start`
   - Monitor logs for first hour

2. **After first day:**
   - Review performance in logs
   - Adjust risk limits if needed
   - Add/remove tickers based on results

3. **After first week:**
   - Analyze win rate and P&L
   - Consider implementing Week 2 improvements (Kelly sizing, sector limits)
   - Decide if ready for live trading (NOT recommended yet!)

---

## Important Notes

⚠️ **This is PAPER TRADING - No real money is being used**

⚠️ **Do NOT switch to live trading until:**
- Successfully traded paper for 2+ months
- Understand all risk controls
- Validated strategy with real historical data
- Comfortable with potential losses

⚠️ **The system is still experimental:**
- Backtests use simulated options data
- ML filter needs more training data
- Real market conditions may differ significantly

---

**Good luck with your paper trading tomorrow! 🚀**
