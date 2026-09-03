## Future Algorithm Improvements

Roadmap of additional enhancements to consider implementing later.

---

## ✅ Implemented (Sept 2026)

1. ✅ **Vertical Spreads** - Defined risk strategies
2. ✅ **Trailing Stop-Loss** - Lock in profits dynamically
3. ✅ **ML Edge Filter** - XGBoost to filter false edges

---

## 📋 Priority 1: Quick Wins (Easy Implementation)

### 1.1 Add Earnings Calendar Filter

**Problem:** Large losses from earnings surprises
**Solution:** Skip trades 7 days before earnings

**Implementation:**
```python
# strategies/earnings_filter.py
import yfinance as yf

def has_upcoming_earnings(ticker, days_ahead=7):
    stock = yf.Ticker(ticker)
    calendar = stock.calendar
    if calendar and 'Earnings Date' in calendar:
        next_earnings = calendar['Earnings Date'][0]
        days_until = (next_earnings - datetime.now()).days
        return days_until <= days_ahead
    return False

# In edge_scanner.py:
if has_upcoming_earnings(ticker, days_ahead=7):
    print(f"Skipping {ticker} - earnings in next 7 days")
    continue
```

**Impact:** Avoid 10-20% of worst losses
**Effort:** 1-2 hours
**Priority:** HIGH

### 1.2 Dynamic Edge Threshold by Ticker

**Problem:** Fixed 3% edge is too conservative for liquid tickers
**Solution:** Lower threshold for AAPL/NVDA, higher for MSTR

**Implementation:**
```python
EDGE_THRESHOLDS = {
    'AAPL': 2.0,   # High liquidity
    'NVDA': 2.5,   # High liquidity
    'TSLA': 4.0,   # High volatility
    'MSTR': 5.0,   # Very volatile
    'default': 3.0
}

min_edge = EDGE_THRESHOLDS.get(ticker, 3.0)
```

**Impact:** 2-3x more trades on good tickers
**Effort:** 30 minutes
**Priority:** HIGH

### 1.3 Tighter Stop-Loss (1.5x instead of old looser stop)

**Problem:** Average loss > average win on some tickers
**Solution:** Exit at 1.5x entry price (tighter than before)

**Implementation:**
```python
# In automated_trader.py
if current_price >= position.entry_price * 1.5:
    close_position(position, reason="STOP_LOSS_1.5X")
```

**Note:** For short PUT @ $5.00:
- Old: No multiplier-based stop (percentage based)
- New: Exit at $7.50 (1.5x entry)

**Impact:** Reduce avg loss by 30-40%
**Effort:** 15 minutes
**Priority:** HIGH

---

## 📋 Priority 2: Medium-Term (This Month)

### 2.1 Kelly Criterion Position Sizing

**Problem:** Fixed position size doesn't account for risk
**Solution:** Size based on edge and win rate

**Formula:**
```
f = (bp - q) / b
where:
  f = fraction of capital to bet
  b = odds (edge)
  p = win probability
  q = 1 - p
```

**Implementation:**
```python
def kelly_position_size(edge_pct, win_rate, account_value):
    b = edge_pct / 100
    p = win_rate
    q = 1 - p

    kelly = (b * p - q) / b
    kelly = max(0, min(kelly, 0.25))  # Cap at 25%

    return account_value * kelly
```

**Impact:** Better risk-adjusted returns
**Effort:** 2-3 hours
**Priority:** MEDIUM

### 2.2 Sector Exposure Limits

**Problem:** Overconcentration in correlated tickers (NVDA + AMD both semi)
**Solution:** Max 30% in any sector

**Implementation:**
```python
TICKER_SECTORS = {
    'AAPL': 'Tech',
    'NVDA': 'Semi',
    'AMD': 'Semi',
    'TSLA': 'Auto',
    # ...
}

def check_sector_limits(ticker, positions, max_pct=0.30):
    sector = TICKER_SECTORS.get(ticker)
    sector_exposure = sum(
        pos.value for pos in positions
        if TICKER_SECTORS.get(pos.ticker) == sector
    )
    return sector_exposure < account_value * max_pct
```

**Impact:** Reduce correlation risk
**Effort:** 1-2 hours
**Priority:** MEDIUM

### 2.3 Walk-Forward Optimization

**Problem:** Strategy might be overfit to 2024 data
**Solution:** Train on historical, test on future

**Implementation:**
```python
# Test strategy robustness across time
for year in [2020, 2021, 2022, 2023]:
    # Optimize on this year
    params = optimize_strategy(year)

    # Test on next year
    results = backtest(year + 1, params)

    if results.sharpe < 0.5:
        print(f"Strategy failed in {year + 1}")
```

**Impact:** Validate strategy robustness
**Effort:** 4-6 hours
**Priority:** MEDIUM

### 2.4 IV Percentile Filter

**Problem:** Selling options in low vol = poor premiums
**Solution:** Only trade when IV > 30th percentile

**Implementation:**
```python
import yfinance as yf

def get_iv_percentile(ticker, current_iv, lookback_days=252):
    stock = yf.Ticker(ticker)
    hist = stock.history(period=f"{lookback_days}d")

    # Get historical IVs (proxy with ATR or use options data)
    # Calculate percentile
    percentile = scipy.stats.percentileofscore(historical_ivs, current_iv)

    return percentile

# Filter
if get_iv_percentile(ticker, iv) < 30:
    print(f"Skipping {ticker} - IV too low ({percentile:.0f}th percentile)")
    continue
```

**Impact:** Better premiums, higher win rate
**Effort:** 2-3 hours
**Priority:** MEDIUM

---

## 📋 Priority 3: Long-Term (3-6 Months)

### 3.1 Real Historical Options Data

**Problem:** Backtests use simulated options prices
**Solution:** Get real data from OptionMetrics or Polygon

**Data Sources:**
- **OptionMetrics** - Academic/institutional ($$$)
- **CBOE DataShop** - Official exchange data ($$)
- **Polygon.io** - Affordable API ($)

**Implementation:**
```python
import polygon

client = polygon.OptionsClient(api_key)

# Get real historical options data
options = client.get_historic_trades(
    ticker='AAPL',
    date='2024-06-01',
    strike=215,
    right='P',
    expiry='2024-07-18'
)

# Re-run backtests with real data
backtest_with_real_data(options)
```

**Impact:** Validate simulated backtests
**Effort:** 10-20 hours
**Cost:** $49-199/month for data
**Priority:** HIGH (when ready for production)

### 3.2 Improved LSM Pricing

**Current:** Simple GBM + 350 epochs
**Upgrade:** Stochastic vol + 1000 epochs

**Implementation:**
```python
# Heston stochastic volatility model
def heston_lsm_pricing(S0, K, T, r, q, v0, kappa, theta, sigma, rho):
    # Simulate correlated stock + vol paths
    # Use more epochs (1000 instead of 350)
    # Add jump component for earnings
    pass
```

**Impact:** More accurate pricing
**Effort:** 20-40 hours
**Priority:** MEDIUM

### 3.3 Portfolio Optimization

**Problem:** Trading tickers independently
**Solution:** Optimize at portfolio level

**Implementation:**
```python
from scipy.optimize import minimize

def optimize_portfolio(opportunities, constraints):
    # Objective: Maximize Sharpe ratio
    # Constraints:
    #   - Total exposure < 20%
    #   - Sector limits < 30%
    #   - Correlation limits
    #   - VaR < 10%

    result = minimize(
        objective_function,
        initial_weights,
        constraints=constraints
    )

    return optimal_weights
```

**Impact:** Better risk-adjusted returns
**Effort:** 10-15 hours
**Priority:** LOW (diminishing returns)

### 3.4 Multi-Leg Strategies

**Current:** Vertical spreads
**Add:** Iron condors, butterflies, calendars

**Iron Condor:**
```python
# Sell OTM call + put spreads
# High win rate, low risk, neutral outlook
sell_put_strike = spot * 0.95
buy_put_strike = spot * 0.90
sell_call_strike = spot * 1.05
buy_call_strike = spot * 1.10

max_profit = (sell_put_premium + sell_call_premium
              - buy_put_premium - buy_call_premium) * 100
max_loss = ((sell_put_strike - buy_put_strike) - max_profit/100) * 100
```

**Impact:** More strategies, higher flexibility
**Effort:** 5-10 hours per strategy
**Priority:** MEDIUM

### 3.5 Market Regime Detection

**Problem:** Same strategy doesn't work in all markets
**Solution:** Detect bull/bear/sideways, adjust accordingly

**Implementation:**
```python
def detect_market_regime(ticker):
    hist = yf.Ticker(ticker).history(period="3mo")

    # Calculate trend indicators
    sma_50 = hist['Close'].rolling(50).mean()
    sma_200 = hist['Close'].rolling(200).mean()
    current_price = hist['Close'][-1]

    # Volatility
    volatility = hist['Close'].pct_change().std() * np.sqrt(252)

    if current_price > sma_50 > sma_200 and volatility < 0.25:
        return 'BULL'
    elif current_price < sma_50 < sma_200:
        return 'BEAR'
    elif volatility > 0.40:
        return 'VOLATILE'
    else:
        return 'SIDEWAYS'

# Adjust strategy
regime = detect_market_regime('AAPL')
if regime == 'BULL':
    # Sell puts (bullish)
    pass
elif regime == 'BEAR':
    # Sell calls (bearish)
    pass
elif regime == 'SIDEWAYS':
    # Iron condors (neutral)
    pass
```

**Impact:** Adapt to market conditions
**Effort:** 3-5 hours
**Priority:** MEDIUM

---

## 🔬 Research Ideas (Not Yet Validated)

### R1. Reinforcement Learning for Trade Timing

Use RL to learn optimal entry/exit timing beyond LSM edge.

### R2. Sentiment Analysis

Scrape Twitter/Reddit for stock sentiment, use as signal.

### R3. Order Flow Analysis

Use CBOE order flow data to detect institutional activity.

### R4. Liquidity Scoring

Create liquidity score (bid-ask, volume, OI), filter illiquid options.

### R5. Greeks-Based Hedging

Delta-hedge with stock, optimize gamma/vega exposure.

---

## 📊 Prioritization Matrix

| Feature | Impact | Effort | Priority | Status |
|---------|--------|--------|----------|--------|
| Vertical Spreads | High | Medium | 1 | ✅ Done |
| Trailing Stop | High | Low | 1 | ✅ Done |
| ML Edge Filter | High | Medium | 1 | ✅ Done |
| Earnings Filter | High | Low | 1 | ✅ Done |
| Dynamic Edge Threshold | High | Low | 1 | ✅ Done |
| Tighter Stop-Loss | Medium | Low | 1 | ✅ Done |
| Kelly Sizing | High | Medium | 2 | 📋 Todo |
| Sector Limits | Medium | Low | 2 | 📋 Todo |
| Walk-Forward | Medium | Medium | 2 | 📋 Todo |
| IV Percentile Filter | Medium | Medium | 2 | 📋 Todo |
| Real Options Data | High | High | 3 | 📋 Todo |
| Better LSM | Medium | High | 3 | 📋 Todo |
| Portfolio Optimizer | Low | High | 3 | 📋 Todo |
| Multi-Leg | Medium | Medium | 3 | 📋 Todo |
| Regime Detection | Medium | Low | 3 | 📋 Todo |

---

## 🎯 Recommended Implementation Order

**Week 1:** ✅ COMPLETED (Sept 3, 2026)
1. ✅ Earnings filter (1 hour) - DONE
2. ✅ Dynamic edge threshold (1 hour) - DONE
3. ✅ Tighter stop-loss (1 hour) - DONE

**Week 2:**
4. Kelly position sizing (3 hours)
5. Sector limits (2 hours)

**Week 3:**
6. IV percentile filter (3 hours)
7. Walk-forward backtest (6 hours)

**Month 2:**
8. Get real options data (research + setup)
9. Re-run backtests with real data
10. Validate strategy performance

**Month 3+:**
11. Improve LSM pricing (Heston model)
12. Add market regime detection
13. Implement iron condors

---

## 💡 Quick Wins Summary

**Do These First (Total: 3-4 hours)**

1. ✅ Vertical spreads (done)
2. ✅ Trailing stops (done)
3. ✅ ML filter (done)
4. Earnings filter - avoid earnings weeks
5. Dynamic edge - 2% for AAPL, 5% for MSTR
6. Tighter stop - 2x entry instead of 30%

**Expected Impact:**
- Win rate: 67% → 75%
- Avg loss: -$1,200 → -$800
- Total trades: +50% (more opportunities)
- Sharpe ratio: 1.5 → 2.0+

---

## 📝 Notes

- Focus on **reducing losses** first (stop-loss, spreads)
- Then **increase opportunities** (lower edge threshold, more tickers)
- Finally **optimize** (Kelly sizing, portfolio management)

- Don't over-optimize on 2024 data - validate with walk-forward
- Real options data is critical before going live with real money
- ML filter needs real historical outcomes to train properly

---

**Last Updated:** September 3, 2026
**Implemented:** 6/15 improvements (40% complete!)
**Next Priority:** Kelly position sizing + sector limits (Week 2)
