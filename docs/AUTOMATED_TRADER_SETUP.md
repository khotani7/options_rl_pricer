# Automated Trading System Setup Guide

Complete guide to setting up automated options trading with live market data.

---

## Prerequisites

- ✅ Interactive Brokers account (paper or live)
- ✅ IB Gateway installed and running
- ✅ Market data subscription active
- ✅ Python environment with requirements installed

---

## Step 1: Enable Market Data in IB Gateway

Even with a subscription, you need to enable market data in IB Gateway settings.

### Method 1: Via IB Gateway Settings (RECOMMENDED)

1. **Open IB Gateway**

2. **Click Configure** (gear icon ⚙️) at login screen

3. **Navigate to Settings → Market Data**

4. **Enable these options:**
   - ☑ **US Equity and Equity Options Add-On Streaming Bundle**
   - ☑ **US Securities Snapshot and Futures Value Bundle**
   - ☑ **Enable delayed market data** (as fallback)

5. **Click OK** and **login to IB Gateway**

6. **Port 7497** for paper trading, **Port 7496** for live trading

### Method 2: Via Account Management Portal

1. Go to https://www.interactivebrokers.com/portal

2. **Account Management → Settings → User Settings → Market Data Subscriptions**

3. **For your Paper Trading account (DU...)**, verify these are checked:
   - ☑ US Securities Snapshot and Futures Value Bundle
   - ☑ US Equity and Equity Options Add-On Streaming Bundle

4. **Save** and wait 5-10 minutes

5. **Restart IB Gateway**

---

## Step 2: Verify Market Data is Working

Run the test script to verify your subscription:

```bash
python test_market_data.py
```

**Expected output (during market hours):**
```
✓ Connected to IB Gateway

Test 1: Stock Market Data (FREE)
----------------------------------------------------------------------
  AAPL Stock:
    Bid: $220.50
    Ask: $220.52
    Last: $220.51
  ✓ Stock data is working!

Test 2: Options Market Data (REQUIRES SUBSCRIPTION)
----------------------------------------------------------------------
  AAPL 20260918 $220 Call:
    Bid: $12.50
    Ask: $12.70
    Last: $12.60
  ✓ Options data is working!
  ✓ YOUR SUBSCRIPTION IS ACTIVE!
```

**If you see NaN values:**
- Market might be closed (normal after 4pm ET)
- Subscription needs more time to activate (wait 10 minutes)
- IB Gateway needs restart
- Settings not saved properly

---

## Step 3: Test the Edge Scanner

The automated trader uses the edge scanner to find opportunities. Let's test it:

```bash
# Scan AAPL for trading opportunities
python scripts/edge_scanner.py --ticker AAPL --min-edge 3.0
```

**Expected output:**
```
Scanning AAPL option chain...
Spot price: $220.50

Found 5 opportunities:

  1. BUY PUT $215 exp 2026-09-18
     Market: $3.50 | Fair: $3.80 | Edge: +8.6%

  2. SELL CALL $230 exp 2026-09-11
     Market: $2.20 | Fair: $1.95 | Edge: +12.8%
```

**If no opportunities found:**
- Normal! Not every scan finds edges
- Try different tickers: `--ticker MSFT` or `--ticker JPM`
- Lower threshold: `--min-edge 1.0`
- Market conditions matter (low volatility = fewer edges)

---

## Step 4: Configure the Automated Trader

The trader is already configured with safe defaults. Review the settings:

```bash
# View current config
cat scripts/run_trader.py
```

**Key settings:**
- `mode='paper'` - Paper trading by default (safe!)
- `tickers=['AAPL']` - What to scan
- `min_edge_threshold=3.0%` - Minimum edge to trade
- `max_position_size=5%` - Max 5% per position
- `max_daily_loss=2%` - Circuit breaker at 2% loss
- `scan_interval=15 min` - How often to scan

**You can customize these in scripts/run_trader.py if needed.**

---

## Step 5: Run the Automated Trader (Paper Mode)

Now let's start the automated trading system:

```bash
# Start with single ticker (AAPL)
python scripts/run_trader.py --mode paper --tickers AAPL

# Or multiple tickers
python scripts/run_trader.py --mode paper --tickers AAPL MSFT JPM XOM
```

**What you'll see:**
```
======================================================================
Starting Automated Options Trader
======================================================================
Mode: PAPER
Tickers: AAPL
Scan interval: 15 minutes
Max positions: 10
Min edge: 3.0%
======================================================================

✓ Connected to IB Gateway (port 7497)
✓ Account value: $1,000,000.00
✓ Trader is now active

[09:45:00] Scanning for opportunities...
  Scanning AAPL...
    Found 2 opportunities
    Best: BUY PUT $215.0 @ $3.50 (+8.6%)

  → Found opportunity: BUY
    PUT $215.0 exp 2026-09-18
    Edge: 8.6% | Market: $3.50

  ✓ Order placed: BUY 1x AAPL 215P 20260918 @ $3.48
  ✓ Order filled at $3.50
  ✓ Trade executed successfully

[09:45:15] Position monitoring...
  AAPL_215.0_P: P&L +2.5% ($87.50)
```

**Controls:**
- **Ctrl+C** to stop the trader gracefully
- Logs saved to `outputs/trading_log.json`
- Trades visible in IB Gateway → Portfolio

---

## Step 6: Monitor the System

While the trader runs, you can:

1. **Watch the console output** - Shows scans, trades, positions

2. **Check IB Gateway** - View orders and positions in real-time

3. **Review logs:**
   ```bash
   cat outputs/trading_log.json
   ```

4. **Monitor performance:**
   - The trader prints P&L updates
   - Check position status every scan interval
   - Stop-loss and profit targets trigger automatically

---

## Safety Features (Already Built-In)

The automated trader has multiple safety guards:

✅ **Mode validation** - Can't accidentally route paper orders to live
✅ **Port verification** - Enforces paper=7497, live=7496
✅ **Position sizing** - Max 5% per position
✅ **Daily loss limit** - Halts at 2% drawdown
✅ **Stop-loss** - 30% per position
✅ **Profit target** - Takes profit at 50% gain
✅ **Max positions** - Limit of 10 concurrent positions
✅ **Market hours check** - Only trades 9:30am-4pm ET
✅ **Short-dated filter** - Blocks options <5 days to expiry

See `trading/automated_trader.py:59-84` for implementation.

---

## Troubleshooting

### No market data (NaN values)

**Solution:**
```bash
# 1. Enable delayed data in IB Gateway
#    Configure → Settings → Market Data → Enable delayed market data

# 2. Restart IB Gateway

# 3. Wait 5-10 minutes for subscription to activate

# 4. Test again
python test_market_data.py
```

### No opportunities found

**This is normal!** The scanner is conservative. Try:
- Lower edge threshold: `--min-edge 1.0`
- More tickers: `--tickers AAPL MSFT JPM XOM`
- Wait for higher volatility (earnings, market events)

### Orders not filling

**In paper trading:**
- Paper fills are simulated
- May take 5-60 seconds
- Limit orders might not fill if price moves
- Use `--use-market-orders` for guaranteed fills

### "Connection refused" error

**IB Gateway not running:**
```bash
# Start IB Gateway
# Login with paper account
# Make sure port 7497 is selected
```

---

## Next Steps

Once you're comfortable with paper trading:

1. **Run for several days** - Validate the system works reliably

2. **Review performance:**
   ```bash
   cat outputs/trading_log.json
   python scripts/analyze_stress_test.py  # Analyze results
   ```

3. **Adjust settings** - Tune edge threshold, position sizing, etc.

4. **Live trading** (EXTREME CAUTION):
   ```bash
   # Only after extensive paper trading!
   python scripts/run_trader.py --mode live --tickers AAPL
   ```

---

## Important Warnings

⚠️ **PAPER TRADE FIRST** - Test extensively before using real money

⚠️ **UNTESTED IN BEAR MARKETS** - Strategy only validated in 2023 bull market

⚠️ **START SMALL** - Even in live mode, start with 1-2 positions max

⚠️ **MONITOR CLOSELY** - Don't leave running unattended initially

⚠️ **CHECK EVERYTHING** - Verify trades, prices, logic before risking capital

---

## Summary

**Setup checklist:**
- ✅ IB Gateway running (port 7497 for paper)
- ✅ Market data subscription active
- ✅ Market data enabled in settings
- ✅ Test script shows live quotes
- ✅ Edge scanner finds opportunities
- ✅ Automated trader running

**To start trading:**
```bash
python scripts/run_trader.py --mode paper --tickers AAPL
```

**To stop:**
- Press Ctrl+C
- Trader will close gracefully
- Logs saved automatically

---

## Support

- **IB Gateway issues:** docs/IB_SETUP_GUIDE.md
- **Market data issues:** docs/FIX_MARKET_DATA.md
- **Trading guide:** docs/TRADING_GUIDE.md
- **System overview:** docs/SYSTEM_SUMMARY.md

Good luck, and happy (paper) trading! 🎯
