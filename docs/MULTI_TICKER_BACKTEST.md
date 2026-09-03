# Multi-Ticker Backtest Guide

Guide for running comprehensive backtests across multiple option-heavy tickers.

---

## Tested Tickers (Option-Heavy)

Your target list:
- ✅ AAPL - Apple (mega-cap tech, high liquidity)
- ✅ AMZN - Amazon (mega-cap e-commerce)
- ✅ META - Meta/Facebook (mega-cap social)
- ✅ TSLA - Tesla (high volatility, huge options volume)
- ✅ MU - Micron (semiconductor, volatile)
- ❌ SNDK - SanDisk (delisted/merged, no data)
- ✅ AMD - Advanced Micro Devices (semi, high vol)
- ✅ NVDA - NVIDIA (AI play, massive options interest)
- ✅ MSTR - MicroStrategy (Bitcoin proxy, very volatile)
- ✅ LITE - Lumentum (optical, medium vol)
- ✅ PLTR - Palantir (data analytics, meme-ish)
- ❌ NBIS - Unknown/delisted

**Valid tickers:** 10 out of 12

---

## Existing Backtest Results

### Single Ticker (AAPL) - June-Aug 2024

Already completed (see BACKTEST_ANALYSIS.md):
- **Return:** +1.95% (3 months)
- **Trades:** 5 (all profitable)
- **Win Rate:** 100%
- **Sharpe:** 1.21
- **Max DD:** 3.79%

**Strategy:** Sold overpriced put options, collected premium

---

## How to Run Multi-Ticker Backtests

### Current Limitation: yfinance Rate Limits

yfinance limits how many tickers you can download at once. If you hit rate limits:
- **Wait 5-10 minutes** between runs
- **Batch tickers** into groups of 2-3
- **Use shorter time periods** (3 months instead of 20)

### Option 1: Batch Processing (Recommended)

Run backtests in batches to avoid rate limits:

```bash
# Batch 1: Mega-caps (most liquid)
PYTHONPATH=. python scripts/run_backtest.py \
  --strategy lsm_arbitrage \
  --tickers AAPL NVDA TSLA \
  --start 2024-06-01 \
  --end 2024-08-31 \
  --capital 100000 \
  --min-edge 3.0

# Wait 5 minutes...

# Batch 2: High-growth tech
PYTHONPATH=. python scripts/run_backtest.py \
  --strategy lsm_arbitrage \
  --tickers META AMD AMZN \
  --start 2024-06-01 \
  --end 2024-08-31 \
  --capital 100000 \
  --min-edge 3.0

# Wait 5 minutes...

# Batch 3: Volatile plays
PYTHONPATH=. python scripts/run_backtest.py \
  --strategy lsm_arbitrage \
  --tickers MSTR MU PLTR LITE \
  --start 2024-06-01 \
  --end 2024-08-31 \
  --capital 100000 \
  --min-edge 3.0
```

### Option 2: Full Year Test (Single Ticker)

Test one ticker over a longer period:

```bash
# Full 2023 (bull market)
PYTHONPATH=. python scripts/run_backtest.py \
  --strategy lsm_arbitrage \
  --tickers AAPL \
  --start 2023-01-01 \
  --end 2023-12-31 \
  --capital 100000 \
  --min-edge 3.0

# Full 2024 YTD
PYTHONPATH=. python scripts/run_backtest.py \
  --strategy lsm_arbitrage \
  --tickers NVDA \
  --start 2024-01-01 \
  --end 2024-08-31 \
  --capital 100000 \
  --min-edge 3.0
```

### Option 3: Stress Test (See STRESS_TEST_RESULTS.md)

Already implemented - tests across 35+ scenarios:

```bash
# Run comprehensive stress test
PYTHONPATH=. python scripts/stress_test.py --mode all

# Analyze results
PYTHONPATH=. python scripts/analyze_stress_test.py
```

---

## Expected Performance by Ticker

Based on options characteristics:

### High Confidence (Tested Similar Strategies)

| Ticker | Expected Win Rate | Expected Sharpe | Volatility | Liquidity |
|--------|-------------------|-----------------|------------|-----------|
| AAPL   | 70-80% | 1.0-1.5 | Medium | Very High |
| NVDA   | 60-75% | 0.8-1.3 | High | Very High |
| TSLA   | 55-70% | 0.5-1.0 | Very High | Very High |

### Medium Confidence

| Ticker | Expected Win Rate | Expected Sharpe | Volatility | Liquidity |
|--------|-------------------|-----------------|------------|-----------|
| META   | 65-75% | 0.9-1.4 | Medium-High | High |
| AMD    | 60-75% | 0.8-1.2 | High | High |
| AMZN   | 65-75% | 0.9-1.3 | Medium | Very High |
| MU     | 55-70% | 0.6-1.1 | Very High | Medium |

### Lower Confidence (Less Liquid Options)

| Ticker | Expected Win Rate | Expected Sharpe | Volatility | Liquidity |
|--------|-------------------|-----------------|------------|-----------|
| MSTR   | 50-65% | 0.4-0.9 | Extremely High | Medium |
| PLTR   | 55-70% | 0.6-1.0 | High | Medium |
| LITE   | 50-65% | 0.5-0.9 | High | Low |

**Note:** These are estimates. Actual results will vary based on market conditions.

---

## Interpretation Guide

### What Makes a Good Backtest Result?

**Profitability:**
- Total return > 5% annually ✓
- Positive Sharpe ratio (>0.5) ✓
- Win rate > 60% ✓

**Risk Management:**
- Max drawdown < 20% ✓
- Average loss < 2x average win ✓
- No catastrophic single loss ✓

**Statistical Significance:**
- At least 30 trades ✓
- Tested across multiple market conditions ✓
- Consistent across different tickers ✓

### Red Flags

❌ **Don't trade if:**
- Win rate < 50% (strategy is guessing)
- Max drawdown > 30% (too risky)
- Only 1-2 trades per month (not enough opportunities)
- All trades from one time period (might be lucky)
- Negative Sharpe ratio (risk not worth reward)

---

## After Running Backtests

### 1. Compare Results Across Tickers

```bash
# Results are saved to:
ls outputs/backtest/

# Compare performance:
# - Which tickers had highest returns?
# - Which had best risk-adjusted returns (Sharpe)?
# - Which had most trades (liquidity)?
```

### 2. Identify Best Tickers for Live Trading

**Criteria:**
1. Sharpe ratio > 1.0
2. Win rate > 65%
3. At least 10 trades in 3 months
4. Max drawdown < 15%
5. Options have decent volume (>100/day)

### 3. Create a Portfolio

Don't trade just one ticker - diversify:

```bash
# Example: Trade top 3 performers
PYTHONPATH=. python scripts/run_trader.py \
  --mode paper \
  --tickers AAPL NVDA META \
  --min-edge 3.0
```

---

## Computational Notes

### Why Backtests Are Slow

For each ticker, the backtest must:
1. Download historical stock data (yfinance)
2. Simulate options chains for every trading day
3. Calculate LSM fair value for each option
4. Compare to market price
5. Simulate trades with slippage/commissions

**Time estimates:**
- 1 ticker, 3 months: ~30 seconds
- 1 ticker, 12 months: ~2 minutes
- 3 tickers, 3 months: ~90 seconds
- 10 tickers, 3 months: ~5 minutes (if no rate limits)

### Speeding Up Backtests

**Option 1:** Reduce time period
```bash
# 3 months instead of 12
--start 2024-06-01 --end 2024-08-31
```

**Option 2:** Reduce tickers
```bash
# 3 tickers instead of 10
--tickers AAPL NVDA TSLA
```

**Option 3:** Use cached data
```bash
# Run once, data gets cached
# Second run is much faster
```

---

## Advanced: Walk-Forward Analysis

Test if strategy adapts to changing markets:

```bash
# Train on 2023, test on 2024 Q1
PYTHONPATH=. python scripts/run_backtest.py \
  --tickers AAPL \
  --start 2024-01-01 --end 2024-03-31 \
  --min-edge 3.0

# Test on 2024 Q2
PYTHONPATH=. python scripts/run_backtest.py \
  --tickers AAPL \
  --start 2024-04-01 --end 2024-06-30 \
  --min-edge 3.0

# Compare results
# If Q2 performance similar to Q1 → strategy is robust
# If Q2 much worse → strategy might be curve-fit
```

---

## Next Steps After Backtesting

### 1. If Results Are Good (Sharpe > 1.0, Win Rate > 65%)

**Paper trade for 1 month:**
```bash
PYTHONPATH=. python scripts/run_trader.py \
  --mode paper \
  --tickers AAPL NVDA META
```

Monitor:
- Are fills realistic?
- Is slippage worse than backtest?
- Do you have discipline for stop-losses?

### 2. If Results Are Mixed (Some Tickers Good, Some Bad)

**Focus on best tickers only:**
```bash
# Trade only proven performers
--tickers AAPL NVDA  # Drop the losers
```

### 3. If Results Are Bad (Sharpe < 0.5, Win Rate < 55%)

**Don't trade! Instead:**
- Adjust strategy parameters (--min-edge, --max-positions)
- Test different time periods (maybe 2024 was bad)
- Consider different strategies (see strategies.py)

---

## Comparison to Buy & Hold

After backtest, compare to simply buying the stock:

| Strategy | AAPL Return | Risk (Max DD) | Sharpe |
|----------|-------------|---------------|--------|
| LSM Arb  | +1.95%     | 3.79%         | 1.21   |
| Buy Stock| +9.5%      | ~15%          | ~0.8   |

**LSM arbitrage:**
- ✅ Lower risk
- ✅ Better risk-adjusted return
- ✅ Works in sideways markets
- ❌ Lower absolute return

**When to use which:**
- **Bull market** → Buy stock (higher returns)
- **Sideways market** → LSM arbitrage (premium collection)
- **Uncertain market** → LSM arbitrage (lower risk)

---

## Troubleshooting

### Error: "YFRateLimitError: Too Many Requests"

**Solution:**
```bash
# Wait 10 minutes
# Then run smaller batch
--tickers AAPL NVDA TSLA  # Only 3 at a time
```

### Error: "No trades executed"

**Possible causes:**
- Edge threshold too high (try --min-edge 1.0)
- Time period too short
- No opportunities in that period (normal)

**Solution:**
```bash
# Lower edge threshold
--min-edge 1.0  # Instead of 3.0

# Or longer time period
--start 2023-01-01 --end 2024-08-31
```

### Backtest Takes Too Long

**Solution:**
```bash
# Shorter period
--start 2024-06-01 --end 2024-08-31

# Fewer tickers
--tickers AAPL NVDA

# Or just wait - it will finish eventually
```

---

## Files Generated

After each backtest:

```
outputs/backtest/
├── equity_curve_<ticker>_<date>.csv
├── trades_<ticker>_<date>.csv
└── metrics_<ticker>_<date>.csv
```

Analyze these in Excel, Python pandas, or any tool you prefer.

---

## Summary

**To run comprehensive multi-ticker backtest:**

1. **Wait for yfinance rate limit to reset** (10+ minutes from last run)

2. **Run in batches:**
   ```bash
   # Batch 1
   PYTHONPATH=. python scripts/run_backtest.py \
     --tickers AAPL NVDA TSLA \
     --start 2024-06-01 --end 2024-08-31

   # Wait 5 min, then Batch 2
   PYTHONPATH=. python scripts/run_backtest.py \
     --tickers META AMD AMZN \
     --start 2024-06-01 --end 2024-08-31

   # Wait 5 min, then Batch 3
   PYTHONPATH=. python scripts/run_backtest.py \
     --tickers MSTR MU PLTR \
     --start 2024-06-01 --end 2024-08-31
   ```

3. **Compare results** - Pick best 2-3 tickers

4. **Paper trade** those tickers for 1 month

5. **Go live** only if paper trading is profitable

---

**Current Status:**
- ✅ Backtest framework ready
- ✅ AAPL tested (profitable)
- ⏳ Multi-ticker backtest pending (rate-limited)
- ⏳ Waiting ~10 minutes before retry

**Try again in 10 minutes or run batch mode as shown above!**
