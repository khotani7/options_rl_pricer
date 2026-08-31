# Self-Training American Options Pricer

A reinforcement-learning system that **teaches itself** the optimal early-exercise policy for American options on mid/high-cap equities, calibrated to real market data, and checked against the industry-standard Longstaff-Schwartz Monte Carlo benchmark.

**NEW**: Now includes automated trading system with backtesting, stress testing, and Interactive Brokers integration!

---

## Quick Start

### Option Pricing (RL Model)
```bash
pip install -r requirements.txt

# Quick test
python main.py --ticker AAPL --option-type put --quick

# Full pricing run
python main.py --ticker AAPL --option-type put
```

### Edge Scanner (Find Mispriced Options)
```bash
# Scan for trading opportunities
python scripts/edge_scanner.py --ticker AAPL --min-edge 5.0

# Diagnose specific option
python scripts/diagnose_edge.py --ticker AAPL --strike 305 --expiry 2026-09-11 --type call
```

### Backtesting
```bash
# Run strategy backtest
python scripts/run_backtest.py --tickers AAPL --start 2023-01-01 --end 2024-08-31

# Comprehensive stress test
python scripts/stress_test.py --mode all

# Analyze results
python scripts/analyze_stress_test.py
```

### Paper Trading (Interactive Brokers)
```bash
# Setup IB Gateway first (see docs/IB_SETUP_GUIDE.md)
python scripts/run_trader.py --mode paper --tickers AAPL

# Live trading (use with extreme caution!)
python scripts/run_trader.py --mode live --tickers AAPL
```

---

## What's New: Trading System

This project now includes a complete automated options trading system:

- **LSM Edge Scanner**: Find mispriced American options by comparing Longstaff-Schwartz fair value vs. market prices
- **Backtesting Engine**: Test strategies on historical data with realistic costs and slippage
- **Stress Testing**: Validate across market conditions, parameters, and time periods
- **Automated Trader**: Execute strategies via Interactive Brokers with risk controls
- **Paper Trading**: Test live without risking real money

### Key Features

✅ **Real LSM Pricing**: Uses actual Longstaff-Schwartz Monte Carlo for American options
✅ **Adaptive Time Steps**: Filters out short-dated options (<5 days) that LSM can't price accurately
✅ **Risk Management**: Position sizing, stop-loss, daily loss limits, circuit breakers
✅ **Comprehensive Testing**: 35+ stress test scenarios across market conditions
✅ **IB Integration**: Full paper/live trading via Interactive Brokers Gateway

---

## Project Structure

```
# Core Options Pricing (RL Model)
config.py                   RunConfig defaults + ticker universe
data/
  market_data.py            Live yfinance pull with offline-cache fallback
  calibration_cache.json    Offline snapshot for restricted networks
simulation/
  gbm.py                    Risk-neutral GBM path simulator
pricing/
  lsm.py                    Longstaff-Schwartz benchmark pricer
rl/
  env.py                    Vectorized optimal-stopping environment
  agent.py                  DQN (Double DQN target) + replay buffer
  train.py                  Self-training loop
evaluation/
  evaluate.py               Out-of-sample policy evaluation
  plots.py                  Convergence/boundary/price charts

# Trading System (NEW)
scripts/
  edge_scanner.py           Find mispriced options (LSM vs market)
  diagnose_edge.py          Debug specific option pricing
  run_backtest.py           Strategy backtesting CLI
  run_trader.py             Automated trading CLI
  stress_test.py            Comprehensive stress testing
  analyze_stress_test.py    Results analysis
  test_backtest.py          Quick backtest smoke test

backtesting/
  engine.py                 Backtest simulation engine
  strategies.py             Trading strategies
  data_loader.py            Historical data provider

trading/
  ib_connector.py           Interactive Brokers API wrapper
  automated_trader.py       Automated trading with risk controls

# Documentation
docs/
  QUICKSTART.md             5-minute getting started
  SYSTEM_SUMMARY.md         Complete system overview
  TRADING_GUIDE.md          Comprehensive trading docs
  IB_SETUP_GUIDE.md         Interactive Brokers setup
  BACKTEST_ANALYSIS.md      Backtest results analysis
  STRESS_TEST_RESULTS.md    Stress test findings
  EDGE_SCANNER_FIX.md       Edge scanner bug fix details
  FIX_MARKET_DATA.md        Market data subscription help
  MARKET_HOURS_INFO.md      Trading hours and schedule

# Outputs (ignored by git)
outputs/
  backtest/                 Backtest results
  stress_test/              Stress test results
  *.png                     Charts and visualizations
  *.csv                     Trade logs and metrics
```

---

## How It Works

### 1. Option Pricing (RL Model)

American option pricing is an *optimal stopping problem*. This project uses:

1. **Market Data**: Real spot, volatility, dividend yield, risk-free rate
2. **Monte Carlo Simulation**: Risk-neutral GBM price paths
3. **Self-Training DQN**: Agent learns optimal early-exercise policy through reinforcement learning
4. **LSM Benchmark**: Longstaff-Schwartz as the authoritative reference

The RL agent teaches itself by playing through simulated paths, with no external labels - only internal consistency of value predictions vs. realized payoffs.

### 2. Trading System (Edge Scanner)

The edge scanner finds mispricing opportunities:

1. **LSM Fair Value**: Calculate American option price using Longstaff-Schwartz with adaptive time steps
2. **Market Price**: Get real option quotes from yfinance
3. **Edge Detection**: Compare fair value vs. market, filter by minimum edge threshold
4. **Signal Generation**: BUY underpriced, SELL overpriced options

**Key Fix**: Filters out options <5 days to expiry (LSM can't price them accurately) and uses adaptive time steps (2-10 per day based on maturity).

---

## Results

### RL Model Performance

| Ticker | Cap | Option | RL Price | LSM Price | BS European |
|--------|-----|--------|----------|-----------|-------------|
| DECK | $12B | 6mo ATM put | 12.53 ± 0.09 | 13.37 ± 0.10 | 13.22 |
| JPM | $946B | 6mo ATM put | 17.78 ± 0.12 | 20.57 ± 0.18 | 20.23 |

The RL agent achieves 6-14% of LSM benchmark after 350 epochs (~90s CPU).

### Trading Strategy Performance (Backtest)

**Bull Market 2023 (Full Year):**
- Return: +11.14% ($11,139 on $100K)
- Trades: 27 (20 wins, 7 losses)
- Win Rate: 74%
- Sharpe Ratio: 1.05
- Max Drawdown: 10.19%

See `docs/STRESS_TEST_RESULTS.md` for full analysis.

---

## Known Limitations

### RL Model
- **Underprices vs. LSM**: DQN exercises too eagerly, giving up time value
- **Treat LSM as authoritative** until RL is fully tuned
- GBM only (no stochastic volatility)
- Research tool, not production system

### Trading System
- **Untested in bear markets**: Only validated in 2023 bull market
- **Simulated historical data**: Backtests use simulated options prices (need real OptionMetrics data)
- **Negative risk/reward**: Avg loss ($639) > avg win ($356), requires >64% win rate
- **API rate limits**: yfinance limits testing throughput

**CRITICAL**: Do not trade with real money until validated across full market cycle (bull, bear, crash, sideways).

---

## Documentation

### Getting Started
- **[QUICKSTART.md](docs/QUICKSTART.md)** - 5-minute getting started guide
- **[SYSTEM_SUMMARY.md](docs/SYSTEM_SUMMARY.md)** - Complete system overview

### Trading
- **[TRADING_GUIDE.md](docs/TRADING_GUIDE.md)** - Comprehensive trading documentation
- **[IB_SETUP_GUIDE.md](docs/IB_SETUP_GUIDE.md)** - Interactive Brokers setup guide
- **[MARKET_HOURS_INFO.md](docs/MARKET_HOURS_INFO.md)** - Trading hours and schedule

### Analysis
- **[BACKTEST_ANALYSIS.md](docs/BACKTEST_ANALYSIS.md)** - Backtest results deep-dive
- **[STRESS_TEST_RESULTS.md](docs/STRESS_TEST_RESULTS.md)** - Comprehensive stress testing
- **[EDGE_SCANNER_FIX.md](docs/EDGE_SCANNER_FIX.md)** - Edge scanner bug fix details

### Troubleshooting
- **[FIX_MARKET_DATA.md](docs/FIX_MARKET_DATA.md)** - IB market data subscription help

---

## Requirements

```bash
pip install -r requirements.txt
```

**Core:**
- numpy, pandas
- torch (PyTorch for RL)
- matplotlib, seaborn (visualization)

**Trading:**
- yfinance (market data)
- ib_insync (Interactive Brokers API)

---

## Usage Examples

### Price a Single Option
```bash
# RL model
python main.py --ticker AAPL --option-type put --moneyness 0.95 --maturity-years 0.5

# Quick test (10s)
python main.py --ticker AAPL --option-type put --quick
```

### Find Trading Opportunities
```bash
# Scan AAPL chain for 5%+ edge
python scripts/edge_scanner.py --ticker AAPL --min-edge 5.0

# Diagnose why option shows edge
python scripts/diagnose_edge.py --ticker AAPL --strike 300 --expiry 2026-09-30 --type put
```

### Backtest Strategy
```bash
# 3-month backtest
python scripts/run_backtest.py --tickers AAPL --start 2024-06-01 --end 2024-08-31

# Comprehensive stress test (35 scenarios)
python scripts/stress_test.py --mode all

# Analyze results
python scripts/analyze_stress_test.py
```

### Paper Trading
```bash
# Setup IB Gateway first (port 7497 for paper)
# See docs/IB_SETUP_GUIDE.md

# Start paper trader
python scripts/run_trader.py --mode paper --tickers AAPL XOM JPM

# Monitor real-time (Ctrl+C to stop)
```

---

## Safety & Disclaimers

⚠️ **PAPER TRADE FIRST**: Always test with paper trading before using real money

⚠️ **NOT FINANCIAL ADVICE**: This is educational/research software

⚠️ **INCOMPLETE VALIDATION**: Strategy only tested in bull markets, NOT crashes/bears

⚠️ **SIMULATED DATA**: Backtests use simulated historical prices, not real options data

⚠️ **CHECK EVERYTHING**: Verify all trades, prices, and logic before risking capital

**Key safeguards implemented:**
- Mode/port validation (prevents paper orders routing to live)
- Position size limits (max 5% per position)
- Daily loss limits (2% max drawdown halt)
- Stop-loss per position (30% max loss)
- Short-dated filter (<5 days blocked)

See `trading/automated_trader.py` lines 59-84 for safety checks.

---

## Extending This

### More Tickers
```python
# Add to config.DEFAULT_UNIVERSE
DEFAULT_UNIVERSE = ['AAPL', 'MSFT', 'JPM', 'XOM', ...]
```

### Richer Models
- Swap GBM → Heston/SABR in `simulation/`
- Bigger DQN network in `rl/agent.py`
- More state features in `rl/env.py`

### Better Data
- Replace simulated backtest data with real OptionMetrics/CBOE data
- Add bid-ask spreads and transaction costs
- Full volatility surface instead of flat vol

### Production Trading
- Add walk-forward optimization
- Implement Kelly position sizing
- Add regime detection (bull/bear/sideways)
- Multi-ticker portfolio optimization

---

## Contributing

This is a research/educational project. Improvements welcome:
- Better RL convergence (more epochs, bigger network, prioritized replay)
- Real historical options data integration
- More robust backtesting (walk-forward, Monte Carlo)
- Additional trading strategies

---

## License

See LICENSE file.

---

## Acknowledgments

- Longstaff-Schwartz (2001) for the LSM algorithm
- Interactive Brokers for API access
- yfinance for free market data

---

**Status**: Research/Educational Tool
**Date**: August 31, 2026
**Version**: 2.0 (with Trading System)
