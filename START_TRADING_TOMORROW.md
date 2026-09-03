# 🚀 Start Trading Tomorrow - Quick Guide

**Date created:** September 3, 2026
**Status:** Ready for paper trading

---

## ✅ What's Ready

Your automated options trader is configured with:

1. **Earnings Filter** - Skips trades within 7 days of earnings
2. **Dynamic Edge Thresholds:**
   - AAPL/MSFT: 2.0% (high liquidity)
   - NVDA/META: 2.5% (moderate volatility)
   - TSLA: 4.0% (high volatility)
3. **1.5x Stop-Loss** - Exits when option price hits 1.5x entry
4. **50% Profit Target** - Takes profit automatically
5. **Risk Controls** - Max 20% portfolio exposure, 5% per position

---

## 📋 Tomorrow Morning Checklist

### 9:00 AM ET - Pre-Market Setup

```bash
# 1. Navigate to project
cd /Users/kabirhotani/Downloads/options_rl_pricer

# 2. Start IB Gateway
# - Open IB Gateway app manually
# - Login with PAPER TRADING credentials
# - Verify port 7497 is active

# 3. Test connection
PYTHONPATH=. python test_ib_connection.py

# Should see:
# ✓ Connected to IB Gateway (Paper Trading)
# ✓ Account: DU1234567
```

### 9:25 AM ET - Start Automated Trader

**Option A: Simple Terminal (Recommended for First Time)**

```bash
# Run in terminal - keep window open
PYTHONPATH=. python scripts/run_trader.py \
  --mode paper \
  --tickers AAPL NVDA MSFT \
  --scan-interval 15 \
  --max-positions 5

# Watch it scan for opportunities every 15 minutes
# Press Ctrl+C to stop when done
```

**Option B: Background Process (For All-Day Running)**

```bash
# Start in background with logging
nohup PYTHONPATH=. python scripts/run_trader.py \
  --mode paper \
  --tickers AAPL NVDA MSFT META AMZN \
  --scan-interval 15 \
  --max-positions 5 \
  > outputs/trader_$(date +%Y%m%d).log 2>&1 &

# Save process ID
echo $! > outputs/trader.pid

# Monitor logs in real-time
tail -f outputs/trader_$(date +%Y%m%d).log
```

---

## 📊 What Opportunities Exist Today?

Based on today's scan (Sept 3, 2026):

### AAPL (2.0% threshold)
- **Found:** 10+ opportunities
- **Best edge:** 22.3% on PUT $305 exp 09/09
- **Typical premium:** $0.15 - $2.66
- **Status:** ✓ No earnings this week

### NVDA (2.5% threshold)
- **Found:** 10+ opportunities
- **Best edge:** 30.7% on PUT $202 exp 09/09
- **Typical premium:** $0.11 - $1.77
- **Status:** ✓ No earnings this week

**These would have been auto-traded if the system was running!**

To see full backtest:
```bash
./scripts/backtest_today.sh
```

---

## 🎯 During Trading Day

### What the System Does Automatically

**Every 15 minutes (9:30 AM - 4:00 PM):**
1. Check each ticker for upcoming earnings
2. Scan option chains for LSM edges
3. Compare market price vs. LSM fair value
4. Execute trades if edge > threshold

**Continuously:**
1. Monitor all open positions
2. Exit if price hits 1.5x entry (stop-loss)
3. Exit if profit hits 50% (take profit)
4. Update P&L and risk metrics

### Monitor Progress

```bash
# Watch logs live
tail -f outputs/trader_$(date +%Y%m%d).log

# Check positions
PYTHONPATH=. python -c "
from trading.ib_connector import IBConnector, IBConfig
ib = IBConnector(IBConfig(port=7497))
ib.connect()
print('Positions:', ib.get_positions())
print('Account:', ib.get_account_summary())
"
```

---

## 🛑 Stop Trading (End of Day)

### 4:00 PM ET - Market Close

```bash
# If running in background:
kill $(cat outputs/trader.pid)
rm outputs/trader.pid

# If running in terminal:
# Press Ctrl+C

# Optional: Close all positions before market close
PYTHONPATH=. python scripts/close_all_positions.py --mode paper
```

### Review Performance

```bash
# View today's log
cat outputs/trader_$(date +%Y%m%d).log

# Check final P&L in IB Gateway
# - Open IB Gateway
# - Go to Account → Daily P&L
```

---

## ⚙️ Configuration Options

### Tickers

```bash
# Conservative (3 tickers)
--tickers AAPL MSFT GOOGL

# Moderate (5 tickers) - RECOMMENDED
--tickers AAPL NVDA MSFT META AMZN

# Aggressive (8+ tickers)
--tickers AAPL NVDA MSFT META AMZN TSLA GOOGL JPM
```

### Scan Frequency

```bash
--scan-interval 15  # Every 15 min (default) - RECOMMENDED
--scan-interval 30  # Every 30 min (less aggressive)
--scan-interval 5   # Every 5 min (very aggressive, may hit rate limits)
```

### Position Limits

```bash
--max-positions 5   # Max 5 open positions (conservative)
--max-positions 10  # Max 10 positions (moderate)
--max-positions 3   # Max 3 positions (very conservative)
```

---

## 🔍 Troubleshooting

### "Connection refused" on port 7497
**Solution:**
- IB Gateway not running → Start it
- Wrong port → Verify paper trading uses 7497
- API not enabled → IB Gateway → Settings → API → Enable

### "No edges found" all day
**This is NORMAL!** It means:
- No mispriced options detected (good thing!)
- Earnings filter blocking tickers
- Market fairly priced
- Edge thresholds not met

**Don't worry** - the system is working correctly.

### yfinance rate limit errors
**Solution:**
- Increase `--scan-interval` to 30 minutes
- Reduce number of tickers
- Wait 60 seconds and retry

### Positions not showing in IB Gateway
**Check:**
- Using correct account (paper vs. live)
- Orders actually filled (check IB Gateway → Orders)
- Refresh IB Gateway positions view

---

## ⚠️ Important Warnings

### This is PAPER TRADING
- **No real money** is being used
- Fills may be more optimistic than live trading
- Slippage not accurately modeled

### NOT Ready for Live Trading Yet
Do NOT switch to live trading until:
- [ ] Paper traded successfully for 2+ months
- [ ] Win rate consistently above 60%
- [ ] Understand all risk controls
- [ ] Backtested with REAL historical options data (not simulated)
- [ ] Comfortable with potential losses
- [ ] Verified all edge opportunities manually

### Known Limitations
- Backtests use **simulated** options data
- ML filter needs more training data
- Only tested in bull markets (2023-2024)
- No real OptionMetrics data yet

---

## 📈 Expected Performance (Paper Trading)

Based on backtests and projections:

| Metric | Conservative | Moderate | Aggressive |
|--------|-------------|----------|------------|
| Trades/day | 1-2 | 3-5 | 5-10 |
| Win rate | 70-75% | 65-70% | 60-65% |
| Avg win | $100-300 | $200-500 | $300-800 |
| Avg loss | $150-400 | $300-600 | $500-1000 |
| Daily P&L | +$50-150 | +$100-300 | +$200-600 |

**Reality check:** These are optimistic projections. Real results will vary significantly.

---

## 📝 Daily Routine (Recommended)

### Morning (9:00-9:30 AM)
1. Start IB Gateway
2. Test connection
3. Start automated trader
4. Monitor first scan

### Mid-Day (12:00 PM)
1. Check logs for any trades
2. Verify positions look correct
3. Check for any errors

### End of Day (4:00-4:30 PM)
1. Stop trader
2. Review performance
3. Note any issues
4. Plan adjustments

### Weekly (Friday)
1. Analyze week's performance
2. Calculate win rate, avg P&L
3. Adjust tickers/thresholds if needed
4. Plan next week's tickers

---

## 🎓 Learning Resources

### Understand the Strategy
- `docs/SYSTEM_OVERVIEW.md` - How LSM pricing works
- `docs/TRADING_GUIDE.md` - Trading strategy details
- `docs/FUTURE_IMPROVEMENTS.md` - Roadmap

### Understand the Code
- `scripts/edge_scanner.py` - How edges are detected
- `trading/automated_trader.py` - Risk management
- `strategies/earnings_filter.py` - Earnings detection

---

## ✅ Ready to Start?

Tomorrow morning:
1. ✅ Start IB Gateway at 9:00 AM
2. ✅ Test connection
3. ✅ Run trader at 9:25 AM
4. ✅ Monitor for first hour
5. ✅ Let it run all day
6. ✅ Stop at 4:00 PM
7. ✅ Review results

**Good luck! May the edges be in your favor! 🚀📈**

---

## 📞 Support

If you encounter issues:
1. Check logs: `outputs/trader_YYYYMMDD.log`
2. Review troubleshooting section above
3. Test individual components (`edge_scanner.py`, `test_ib_connection.py`)
4. Verify IB Gateway settings

**Remember:** Paper trading is for learning. Take your time, understand the system, and don't rush to live trading.
