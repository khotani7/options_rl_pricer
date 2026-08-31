# Automated Options Trading System - Complete Guide

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Backtesting](#backtesting)
4. [Paper Trading Setup](#paper-trading-setup)
5. [Live Trading](#live-trading)
6. [Risk Management](#risk-management)
7. [Performance Monitoring](#performance-monitoring)

---

## Overview

This system provides end-to-end options trading capabilities:

- **LSM Pricing Model**: Accurate American options pricing using Longstaff-Schwartz Monte Carlo
- **Edge Detection**: Automated scanning for mispriced options
- **Backtesting Engine**: Test strategies on historical data
- **Automated Trader**: Execute strategies with risk controls
- **IB Integration**: Connect to Interactive Brokers for live trading

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  - yfinance (live market data)                              │
│  - Market calibration (vol, div yield, risk-free rate)      │
│  - Historical price data                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                    Pricing Layer                             │
│  - LSM American options pricer                              │
│  - RL-based exercise policy                                 │
│  - Black-Scholes European pricing                           │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                    Strategy Layer                            │
│  - LSM Arbitrage Strategy                                   │
│  - Early Exercise Premium Strategy                          │
│  - Volatility Skew Strategy                                 │
│  - Custom strategies                                        │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼─────┐   ┌───────▼─────────┐
│ Backtester  │   │  Live Trader    │
│             │   │                 │
│ - Simulate  │   │ - IB API        │
│ - P&L track │   │ - Order mgmt    │
│ - Metrics   │   │ - Risk limits   │
└─────────────┘   └─────────────────┘
```

---

## Backtesting

### Quick Start

```bash
# Run simple backtest
python run_backtest.py --strategy simple --start 2024-01-01 --end 2024-03-31

# LSM arbitrage strategy with custom parameters
python run_backtest.py \
    --strategy lsm_arbitrage \
    --tickers AAPL XOM JPM \
    --capital 100000 \
    --min-edge 3.5 \
    --max-positions 10 \
    --start 2024-01-01 \
    --end 2024-06-30
```

### Available Strategies

1. **LSM Arbitrage**
   - Buy underpriced / Sell overpriced options based on LSM model
   - Entry: |LSM - Market| > edge_threshold
   - Exit: Mean reversion or expiry

2. **Early Exercise Premium**
   - Sell ITM options with excessive American premium
   - Focus on high-dividend stocks and short-dated options
   - Profit from time decay

3. **Volatility Skew**
   - Sell expensive OTM puts, buy cheap ATM puts
   - Profit from skew normalization

### Backtest Results

Results are saved to `outputs/backtest/`:
- `equity_curve.csv`: Daily portfolio value
- `trades.csv`: All executed trades
- `performance_metrics.csv`: Summary statistics

### Performance Metrics Explained

| Metric | Description | Good Value |
|--------|-------------|------------|
| Win Rate | % of profitable trades | >50% |
| Profit Factor | Avg Win / Avg Loss | >1.5 |
| Sharpe Ratio | Risk-adjusted returns | >1.0 |
| Max Drawdown | Largest peak-to-trough decline | <20% |
| Total Return | Overall portfolio return | >10% annual |

---

## Paper Trading Setup

### Step 1: Install Interactive Brokers Software

1. Download **IB Gateway** (lightweight) or **Trader Workstation** (full featured)
   - https://www.interactivebrokers.com/en/trading/tws.php

2. Create a paper trading account
   - Log into your IB account
   - Navigate to Account Management → Settings → Paper Trading
   - Create paper account (virtual $1M)

### Step 2: Configure IB Gateway

1. Launch IB Gateway
2. Log in with your paper trading credentials
3. Go to **Configure → Settings → API → Settings**
4. Enable:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Read-Only API
   - ✅ Download open orders on connection
5. Set Socket Port: **7497** (paper) or **7496** (live)
6. Add to Trusted IPs: `127.0.0.1`
7. Click **OK** and restart Gateway

### Step 3: Install Python Dependencies

```bash
pip install ib_insync
```

### Step 4: Test Connection

```python
from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

print(f"Connected: {ib.isConnected()}")
print(f"Account: {ib.accountValues()}")

ib.disconnect()
```

If successful, you should see your account value.

### Step 5: Run Paper Trader

```bash
# Start paper trader
python run_trader.py --mode paper --tickers AAPL XOM JPM

# With custom settings
python run_trader.py \
    --mode paper \
    --tickers AAPL \
    --scan-interval 15 \
    --max-positions 5 \
    --min-edge 3.0 \
    --max-daily-loss 2.0 \
    --stop-loss 30.0
```

### What Happens:

1. Connects to IB paper account
2. Scans for edge opportunities every 15 minutes
3. Places limit orders when edge > threshold
4. Monitors positions for stop-loss
5. Halts trading if daily loss > 2%
6. Logs all activity to `outputs/trading_log_paper.json`

---

## Live Trading

⚠️ **WARNING**: Live trading uses real money. Only proceed after:
1. ✅ Backtesting shows consistent profits (>6 months)
2. ✅ Paper trading for at least 1 month
3. ✅ Understanding all risk controls
4. ✅ Starting with small capital

### Setup

```bash
# Live trading (use with extreme caution!)
python run_trader.py --mode live --port 7496
```

The system will ask for confirmation:
```
⚠️  WARNING: LIVE TRADING MODE
Type 'I UNDERSTAND THE RISKS' to continue:
```

### Differences from Paper Trading

| Aspect | Paper | Live |
|--------|-------|------|
| Port | 7497 | 7496 |
| Capital | Virtual $1M | Real money |
| Execution | Simulated fills | Real market fills |
| Slippage | Minimal | Can be significant |
| Commissions | Simulated | Real ($0.65+/contract) |

---

## Risk Management

### Built-in Risk Controls

The system has multiple layers of risk protection:

#### 1. Position Limits
```python
RiskLimits(
    max_positions=10,              # Max 10 concurrent positions
    max_position_size=0.05,        # Max 5% of capital per position
    max_portfolio_exposure=0.20,   # Max 20% total options exposure
    max_leverage=2.0               # No more than 2x leverage
)
```

#### 2. Loss Limits
```python
RiskLimits(
    max_daily_loss=0.02,          # 2% daily loss → halt trading
    stop_loss_pct=0.30             # 30% stop loss per position
)
```

#### 3. Edge Requirements
```python
RiskLimits(
    min_edge_threshold_pct=3.0    # Only trade when edge > 3%
)
```

### Circuit Breakers

The system will **halt all trading** if:
- Daily loss exceeds 2% of account value
- More than 10 positions open
- IB connection is lost
- Market is closed

### Manual Override

To stop the trader:
```
Ctrl+C  → Gracefully shuts down, saves logs
```

To force stop:
```
Ctrl+C (twice) → Emergency stop
```

---

## Performance Monitoring

### Real-Time Monitoring

While trader is running, monitor:
- `outputs/trading_log_paper.json` - All trades
- IB Gateway TWS - Live positions
- Console output - Scan results

### Daily Review

```python
# Load trading log
import json
import pandas as pd

with open('outputs/trading_log_paper.json') as f:
    log = json.load(f)

df = pd.DataFrame(log)

# Analyze performance
print(f"Total trades: {len(df)}")
print(f"Avg edge: {df['edge_score'].mean():.1f}%")
print(f"Symbols traded: {df['ticker'].value_counts()}")
```

### Key Metrics to Track

| Metric | How to Calculate | Warning Sign |
|--------|------------------|--------------|
| **Win Rate** | Wins / Total Trades | <40% |
| **Avg Edge** | Mean(edge_score) | <2% |
| **Fill Rate** | Filled / Placed | <50% |
| **Slippage** | Avg(Fill - Limit) | >0.5% |
| **Daily P&L** | Today vs Start | <-2% |

---

## Troubleshooting

### IB Connection Issues

**Problem**: "Failed to connect to IB"

**Solutions**:
1. Check IB Gateway is running
2. Verify port: 7497 (paper) or 7496 (live)
3. Check API settings are enabled
4. Ensure 127.0.0.1 is in Trusted IPs
5. Try different client_id (1, 2, 3...)

### No Opportunities Found

**Problem**: "No significant edge found"

**Solutions**:
1. Lower `--min-edge` threshold (try 2.0%)
2. Add more tickers
3. Check market volatility (low vol = low edge)
4. Verify calibration is working

### Orders Not Filling

**Problem**: Orders placed but not filled

**Solutions**:
1. Use market orders (less slippage risk)
2. Widen limit price spread
3. Check bid-ask spread isn't too wide
4. Ensure sufficient liquidity (volume > 100)

---

## Advanced Usage

### Create Custom Strategy

```python
# my_strategy.py
from backtesting.engine import BacktestEngine, OrderSide

class MyCustomStrategy:
    def __init__(self, param1, param2):
        self.param1 = param1
        self.param2 = param2

    def __call__(self, engine: BacktestEngine, date):
        # Your strategy logic here

        # Example: Buy when edge > threshold
        for ticker in ['AAPL']:
            spot = engine.data_provider.get_stock_price(ticker, date)

            # Your edge calculation
            edge = self.calculate_edge(ticker, spot, date)

            if edge > self.param1:
                engine.place_order(
                    ticker=ticker,
                    strike=spot,
                    maturity_days=30,
                    option_type='put',
                    side=OrderSide.BUY,
                    quantity=1,
                    notes=f"Edge={edge:.1f}%"
                )

    def calculate_edge(self, ticker, spot, date):
        # Your edge logic
        return 5.0  # placeholder
```

### Backtest Custom Strategy

```python
from backtesting.data_loader import BacktestDataProvider
from backtesting.engine import BacktestEngine, BacktestConfig
from my_strategy import MyCustomStrategy

# Setup
config = BacktestConfig(initial_capital=100000)
data_provider = BacktestDataProvider(['AAPL'], '2024-01-01', '2024-06-30')
data_provider.load_all_data()

engine = BacktestEngine(config, data_provider)

# Run
strategy = MyCustomStrategy(param1=3.0, param2=10)
engine.run_backtest(strategy, '2024-01-01', '2024-06-30')

# Results
metrics = engine.get_performance_metrics()
print(metrics)
```

---

## Example Workflows

### Workflow 1: Research → Backtest → Paper → Live

```bash
# 1. Research: Find edge opportunities
python edge_scanner.py --ticker AAPL --min-edge 2.5

# 2. Backtest: Test strategy on historical data
python run_backtest.py --strategy lsm_arbitrage --start 2023-01-01 --end 2024-12-31

# 3. Paper trade: Validate in real-time (1 month minimum)
python run_trader.py --mode paper --tickers AAPL

# 4. Live trade: Start with small capital
python run_trader.py --mode live --max-positions 3 --max-daily-loss 1.0
```

### Workflow 2: Daily Trading Routine

```bash
# Morning (9:00 AM before market open)
# 1. Check overnight changes
python edge_scanner.py --ticker AAPL XOM JPM

# 2. Start automated trader
python run_trader.py --mode paper --scan-interval 15

# During market hours
# 3. Monitor console output and IB TWS

# After market close (4:30 PM)
# 4. Review performance
python -c "import json; print(json.load(open('outputs/trading_log_paper.json'))[-5:])"
```

---

## Safety Checklist

Before going live, ensure:

- [ ] Backtested for >6 months with positive results
- [ ] Paper traded for >1 month
- [ ] Understand every line of code
- [ ] Set appropriate risk limits
- [ ] Start with <10% of total capital
- [ ] Monitor continuously during market hours
- [ ] Have manual override ready (Ctrl+C)
- [ ] Test emergency shutdown procedure
- [ ] Understand IB fees and commissions
- [ ] Have phone number for IB support ready

---

## Support & Resources

- **IB API Documentation**: https://interactivebrokers.github.io/tws-api/
- **ib_insync Docs**: https://ib-insync.readthedocs.io/
- **Project Issues**: Check TRADING_GUIDE.md for common issues

---

## Disclaimer

This software is for educational purposes only. Options trading involves substantial risk and is not suitable for all investors. Past performance does not guarantee future results. The authors assume no liability for any financial losses incurred using this system.

**Always:**
- Start with paper trading
- Use appropriate position sizing
- Set stop-losses
- Monitor risk metrics
- Trade responsibly
