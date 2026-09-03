# Daily Automated Options Trading - Complete Setup Guide

## Overview

The daily trader automatically:
- ✅ Scans for edge opportunities each morning
- ✅ Places trades with proper position sizing
- ✅ Monitors positions with stop losses (30% default)
- ✅ Takes profits at targets (50% default)
- ✅ Closes positions at end of day (optional)
- ✅ Enforces daily loss limits (2% circuit breaker)

---

## Quick Start

### 1. Run Once Manually (Testing)

```bash
cd /Users/kabirhotani/Downloads/options_rl_pricer

# Paper trading test
PYTHONPATH=. python scripts/daily_trader.py \
    --mode paper \
    --tickers TSLA AAPL MU \
    --min-edge 10.0 \
    --max-position-size 5.0 \
    --stop-loss 30.0 \
    --profit-target 50.0
```

### 2. Schedule Daily (Automated)

**Option A: macOS/Linux Cron**

```bash
# Edit crontab
crontab -e

# Add these lines (adjust times for your timezone):

# Morning scan at 9:35 AM ET (5 min after market open)
35 9 * * 1-5 cd /Users/kabirhotani/Downloads/options_rl_pricer && PYTHONPATH=. python scripts/daily_trader.py --mode paper --tickers TSLA AAPL MU --min-edge 10.0 >> logs/trader.log 2>&1

# Hourly monitoring (10 AM - 3 PM)
0 10-14 * * 1-5 cd /Users/kabirhotani/Downloads/options_rl_pricer && PYTHONPATH=. python scripts/daily_trader.py --mode paper --tickers TSLA AAPL MU --min-edge 10.0 >> logs/trader.log 2>&1

# End of day close (3:45 PM)
45 15 * * 1-5 cd /Users/kabirhotani/Downloads/options_rl_pricer && PYTHONPATH=. python scripts/close_all_positions.py --mode paper --confirm >> logs/trader.log 2>&1
```

**Option B: Use the scheduler script**

```bash
# Make executable
chmod +x scripts/schedule_daily_trader.sh

# Edit configuration in the script
nano scripts/schedule_daily_trader.sh

# Schedule it to run every 30 minutes during market hours
*/30 9-15 * * 1-5 /Users/kabirhotani/Downloads/options_rl_pricer/scripts/schedule_daily_trader.sh >> logs/scheduler.log 2>&1
```

---

## Configuration

### Position Sizing

```bash
--max-position-size 5.0  # Each position = max 5% of account
```

**Example with $100k account:**
- Max position value = $5,000
- For $0.50 option = 100 contracts max ($0.50 × 100 shares × 100 contracts = $5,000)

### Risk Management

```bash
--stop-loss 30.0         # Exit if position down 30%
--profit-target 50.0     # Exit if position up 50%
--max-daily-loss 2.0     # Stop trading if down 2% on the day
```

### Edge Threshold

```bash
--min-edge 10.0          # Only trade if LSM shows 10%+ edge
```

**Lower edge = more trades but lower quality**
**Higher edge = fewer trades but higher quality**

Recommended:
- Conservative: 15-20%
- Moderate: 10-15%
- Aggressive: 5-10%

---

## How It Works

### Morning (9:35 AM)

1. Scanner runs across all tickers
2. Filters for:
   - Edge > 10% (configurable)
   - Moneyness: 85%-115% of spot (near-the-money only)
   - Volume > 5 contracts
   - Days to expiry > 5 (avoid very short-dated)
3. Sorts by edge size
4. Places trades up to max positions limit

### During Day (Hourly)

1. Checks existing positions
2. Exits if stop loss hit (-30%)
3. Exits if profit target hit (+50%)
4. Scans for new opportunities if positions < max

### End of Day (3:45 PM)

1. Closes all positions (if `--close-eod` enabled)
2. Generates daily report
3. Logs all trades

---

## Safety Features

### Pre-Trade Checks

- ✅ Market hours validation
- ✅ Position sizing limits
- ✅ Max positions enforced
- ✅ Daily loss circuit breaker

### During Trading

- ✅ Real-time stop loss monitoring
- ✅ Profit target monitoring
- ✅ Position updates every 30 seconds
- ✅ All trades logged to JSON

### Fail-Safes

- ✅ IB Gateway connection monitoring
- ✅ Automatic reconnection on disconnect
- ✅ Order validation before submission
- ✅ Manual override via Ctrl+C

---

## Monitoring

### View Live Logs

```bash
# Follow trader log
tail -f logs/trader.log

# View today's trades
cat outputs/trading_log_paper_20260903.json | python -m json.tool
```

### Check Positions

```bash
# View current positions
PYTHONPATH=. python scripts/check_positions.py --mode paper

# Close all positions manually
PYTHONPATH=. python scripts/close_all_positions.py --mode paper
```

### Performance Report

```bash
# Generate daily report
PYTHONPATH=. python scripts/daily_report.py --date 2026-09-03
```

---

## Going Live (After Paper Trading Success)

### Prerequisites

1. ✅ At least 1 month of successful paper trading
2. ✅ Win rate > 60%
3. ✅ Max drawdown < 5%
4. ✅ Understand all trades the system makes
5. ✅ Have tested stop losses and profit targets

### Switch to Live

```bash
# Change mode from 'paper' to 'live'
PYTHONPATH=. python scripts/daily_trader.py \
    --mode live \                    # ⚠️  REAL MONEY
    --tickers TSLA AAPL \            # Start with 2-3 tickers
    --min-edge 15.0 \                # Higher threshold for live
    --max-position-size 2.0 \        # Smaller positions
    --max-positions 5                # Fewer concurrent positions
```

**You will be prompted to confirm:**
```
Type 'I UNDERSTAND THE RISKS' to continue:
```

### Live Trading Checklist

- [ ] IB Gateway running on port 7496 (live)
- [ ] Funded live account with margin approval
- [ ] Options trading enabled
- [ ] Position sizing configured conservatively
- [ ] Stop losses working in paper trading
- [ ] Daily loss limits tested
- [ ] Emergency contact (phone number) ready
- [ ] Continuous monitoring for first week

---

## Troubleshooting

### "Market is closed"

- Only runs during 9:30 AM - 4:00 PM ET (Mon-Fri)
- Use `--scan-only` to test outside market hours

### "Failed to connect to IB Gateway"

1. Is IB Gateway running?
2. Are you logged in?
3. Is API enabled (port 7497 for paper)?

### "Position too large for risk limits"

- Option price × 100 > account value × max_position_size%
- Increase `--max-position-size` or trade cheaper options

### "Order stuck in PendingSubmit"

- Market might be closed
- Check IB Gateway messages
- Try market order instead of limit

### "No opportunities found"

- Edge threshold might be too high
- Try `--min-edge 5.0` for more opportunities
- Check if tickers have liquid options

---

## Example Configurations

### Conservative (Retirement Account)

```bash
--tickers SPY QQQ IWM          # Index ETFs only
--min-edge 20.0                # High quality trades only
--max-position-size 2.0        # Small positions
--stop-loss 20.0               # Tight stop loss
--profit-target 30.0           # Quick profit taking
--max-positions 3              # Very selective
```

### Moderate (Growth Account)

```bash
--tickers AAPL TSLA MSFT NVDA AMZN
--min-edge 10.0
--max-position-size 5.0
--stop-loss 30.0
--profit-target 50.0
--max-positions 10
```

### Aggressive (Speculative)

```bash
--tickers TSLA NVDA AMD PLTR COIN
--min-edge 5.0
--max-position-size 10.0
--stop-loss 50.0
--profit-target 100.0
--max-positions 20
```

---

## Support

- IB Gateway issues: Check `docs/IB_SETUP_GUIDE.md`
- Trading strategy: Check `docs/TRADING_GUIDE.md`
- Backtesting results: Check `docs/BACKTEST_ANALYSIS.md`

---

## Legal Disclaimer

This software is for educational purposes. Trading options involves substantial risk of loss. Past performance does not guarantee future results. You are responsible for all trades placed by this system. The authors assume no liability for losses.
