# Automated Options Trading System

An intelligent options trading system combining **Longstaff-Schwartz Monte Carlo pricing**, **automated edge detection**, and **Interactive Brokers integration** for systematic options selling with risk management.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 Features

### Core Capabilities
- **LSM Fair Value Pricing**: American option pricing using Longstaff-Schwartz Monte Carlo
- **Automated Edge Scanner**: Find mispriced options by comparing market prices to LSM fair value
- **Position Sizing**: Volatility-adjusted position sizing (5% of portfolio, IV-scaled)
- **Risk Management**: Automated stop-loss (25% loss) and profit targets (25% gain)
- **Live Trading**: Full Interactive Brokers integration for paper/live trading
- **Backtesting Engine**: Historical performance testing with realistic slippage
- **Stress Testing**: 35+ market scenarios (crashes, vol spikes, regime changes)

### Strategy Features
- **Smart Filters**: Min premium, moneyness range, DTE limits, bid-ask spread filters
- **Earnings Avoidance**: Skip trades within 7 days of earnings
- **Dynamic Thresholds**: Ticker-specific edge thresholds (2% AAPL, 4% TSLA, etc.)
- **Portfolio Limits**: Max positions, daily loss limits, notional exposure caps
- **Automated Monitoring**: Real-time position tracking with auto-close on triggers

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/yourusername/options_rl_pricer.git
cd options_rl_pricer
pip install -r requirements.txt
```

### Find Trading Opportunities

```bash
# Scan for mispriced options
PYTHONPATH=. python scripts/edge_scanner.py \
    --ticker AAPL \
    --min-edge 5.0 \
    --min-volume 50

# Output: Top opportunities ranked by edge size
```

### Run Paper Trading

```bash
# 1. Setup IB Gateway (see docs/IB_SETUP_GUIDE.md)

# 2. Start automated trader
PYTHONPATH=. python scripts/run_trader.py \
    --mode paper \
    --tickers AAPL NVDA MSFT \
    --scan-interval 15 \
    --max-positions 5 \
    --client-id 100 \
    --use-market-orders \
    --min-premium 0.75 \
    --min-moneyness 0.94 \
    --max-moneyness 1.06 \
    --min-dte 10 \
    --max-dte 45 \
    --max-spread-pct 20 \
    --min-edge 6.0 \
    --max-position-size 5.0 \
    --max-notional 75.0
```

### Backtest Strategy

```bash
# Historical performance test
python scripts/run_backtest.py \
    --tickers AAPL NVDA MSFT \
    --start 2023-01-01 \
    --end 2023-12-31

# Stress test across market conditions
python scripts/stress_test.py --mode all
python scripts/analyze_stress_test.py
```

---

## 📊 How It Works

### 1. Edge Detection

The system identifies "edges" by comparing **market prices** to **LSM fair values**:

```
Edge % = (Market Price - LSM Fair Value) / LSM Fair Value × 100

Examples:
- Market: $2.50, LSM: $2.00 → Edge: +25% (SELL signal - overpriced)
- Market: $1.50, LSM: $2.00 → Edge: -25% (BUY signal - underpriced)
```

**Filters applied:**
- Minimum edge threshold (e.g., 6%)
- Monte Carlo standard error (reject if edge < 2σ noise)
- Bid-ask spread limits
- Volume/liquidity requirements

### 2. Position Sizing

**Volatility-Adjusted Sizing:**
```python
base_size = account_value × 5%  # Target position size
vol_adjustment = 30% / current_IV  # Scale down for high IV
notional_limit = min(position, 75% of account)  # Cap max exposure

# Example: $1.25M account, NVDA at 45% IV, $2.00 option
# → Base: 312 contracts, Vol-adjusted: 209 contracts
# → Premium: $41,800, Notional: $4.6M
```

### 3. Risk Management

**Automated Exit Rules:**
- **Profit Target**: Close at 25% gain (e.g., sold at $50 → buy back at $37.50)
- **Stop-Loss**: Close at 50% loss (e.g., sold at $50 → buy back at $75)
- **Max Daily Loss**: Circuit breaker at 2% account drawdown
- **Position Monitoring**: Every 30 seconds during market hours

---

## 📁 Project Structure

```
options_rl_pricer/
├── README.md                    # This file
├── requirements.txt             # Dependencies
├── STRATEGY_IMPROVEMENTS.md     # Future enhancements roadmap
│
├── scripts/                     # Executable scripts
│   ├── edge_scanner.py         # Find mispriced options
│   ├── run_trader.py           # Automated trading bot
│   ├── run_backtest.py         # Historical backtesting
│   ├── stress_test.py          # Multi-scenario testing
│   ├── start_trader.sh         # Convenience startup script
│   ├── test_ib_connection.py   # IB connectivity test
│   └── test_market_data_freshness.py  # Market data diagnostic
│
├── trading/                     # Trading engine
│   ├── automated_trader.py     # Main trading logic
│   └── ib_connector.py         # Interactive Brokers interface
│
├── pricing/                     # Pricing models
│   └── lsm.py                  # Longstaff-Schwartz MC
│
├── simulation/                  # Monte Carlo simulation
│   └── gbm.py                  # Geometric Brownian Motion
│
├── strategies/                  # Trading strategies
│   ├── earnings_filter.py      # Earnings date filtering
│   ├── ml_edge_filter.py       # Machine learning filters
│   └── trailing_stop.py        # Trailing stop-loss
│
├── backtesting/                 # Backtest engine
│   ├── engine.py               # Core backtesting logic
│   └── data_loader.py          # Historical data handling
│
├── data/                        # Data utilities
│   └── market_data.py          # Market data fetching
│
├── docs/                        # Documentation
│   ├── IB_SETUP_GUIDE.md       # Interactive Brokers setup
│   ├── TRADING_GUIDE.md        # How to trade
│   ├── BACKTEST_ANALYSIS.md    # Backtest results
│   └── STRESS_TEST_RESULTS.md  # Stress test findings
│
└── outputs/                     # Generated outputs (gitignored)
    ├── edge_opportunities_*.csv
    ├── trading_log_*.json
    └── stress_test/
```

---

## 🎮 Usage Examples

### Example 1: Scan for Edges

```bash
PYTHONPATH=. python scripts/edge_scanner.py --ticker AAPL
```

**Output:**
```
======================================================================
Edge Scanner (LSM fair value): AAPL
======================================================================
Spot: $321.73 | r=3.76% | q=0.32%
Min edge: 2.0% (dynamic threshold for AAPL)
Data source: live | As of: 2026-09-04

TOP TRADING OPPORTUNITIES (LSM fair value vs. market, ranked by edge)
======================================================================

#1 | SELL_PUT | Edge: +7.2%
    PUT $305 exp 2026-09-20 (16d)
    Market: $2.15 (bid $2.10 / ask $2.20)
    LSM fair value: $2.00 +/- 0.08
    Volume: 1,247 | OI: 5,890
```

### Example 2: Run Automated Trader

```bash
# Use the convenience script
cd scripts
./start_trader.sh

# Or run with custom parameters
PYTHONPATH=. python scripts/run_trader.py \
    --mode paper \
    --tickers AAPL NVDA \
    --max-positions 5 \
    --min-premium 1.00
```

**Live Output:**
```
======================================================================
Starting Automated Options Trader
======================================================================
Mode: PAPER
Tickers: AAPL, NVDA
Max positions: 5
Min edge: 6.0%
======================================================================

✓ Connected to IB on 127.0.0.1:7497
✓ Account value: $1,250,733.18
✓ Trader is now active

[14:30:13] Scanning for opportunities...
  Scanning AAPL...
    Found 33 opportunities (filtered from 89)
    Best: SELL_PUT $305 @ $2.15 (+7.2%)

  → Found opportunity: SELL_PUT
    Position sizing:
      Quantity: 290 contracts
      Premium: $2.15 × 290 × 100 = $62,350
      Portfolio %: 4.99%
      Notional risk (if assigned): $8.85M (70.8% of account)
      IV: 28.5%

✓ Order placed: SELL 290x AAPL 305.0P 20260920 @ MKT
✓ Order filled @ $2.14
    ✓ Trade executed successfully
```

### Example 3: Check Position Status

```bash
PYTHONPATH=. python scripts/utils/view_positions.py
```

**Output:**
```
Current Positions:
  AAPL_305.0_P: qty=-290, entry=$2.14, current=$2.10, P&L=+$1,160 (+1.9%)
  NVDA_220.0_P: qty=-150, entry=$3.50, current=$3.20, P&L=+$4,500 (+8.6%)

Total P&L: +$5,660
```

---

## ⚙️ Configuration

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--mode` | `paper` | Trading mode: `mock`, `paper`, or `live` |
| `--max-positions` | 10 | Max concurrent positions |
| `--max-position-size` | 5.0 | Max % of account per position (premium) |
| `--max-notional` | 75.0 | Max % of account notional exposure |
| `--min-premium` | 0.75 | Min option price ($) |
| `--min-edge` | 6.0 | Min edge threshold (%) |
| `--min-moneyness` | 0.94 | Min strike/spot ratio |
| `--max-moneyness` | 1.06 | Max strike/spot ratio |
| `--min-dte` | 10 | Min days to expiration |
| `--max-dte` | 45 | Max days to expiration |
| `--max-spread-pct` | 20.0 | Max bid-ask spread (%) |
| `--scan-interval` | 15 | Minutes between scans |
| `--stop-loss` | 30.0 | Stop-loss % (default 50% with 1.5x multiplier) |

### Risk Limits (Hardcoded in `RiskLimits`)

```python
max_daily_loss: 2%        # Circuit breaker
profit_target: 25%        # Auto-close at 25% gain
stop_loss_multiplier: 1.5x # Exit at 1.5x entry (50% loss)
```

---

## 📈 Performance

### Backtest Results (2023 Bull Market)

```
Period: Jan 1 - Dec 31, 2023
Tickers: AAPL, NVDA, MSFT
Strategy: Sell OTM puts (90-105% moneyness, 14-45 DTE)

Results:
  Total Return: +11.14%
  Win Rate: 74% (20 wins / 27 trades)
  Avg Win: $185 | Avg Loss: $320
  Profit Factor: 1.28
  Max Drawdown: -3.2%
  Sharpe Ratio: 1.47
```

**Note:** Backtests use simulated options data. Real options data (OptionMetrics) recommended for production.

### Stress Test Results

Tested across 35+ scenarios:
- ✅ Mild corrections (5-10%): +3% to +8% returns
- ⚠️ Moderate crashes (15-20%): -5% to -12% losses
- ❌ Black swans (30%+): -25% to -40% losses (stop-losses help)

See `docs/STRESS_TEST_RESULTS.md` for details.

---

## 🔧 Development

### Running Tests

```bash
# Test IB connection
PYTHONPATH=. python scripts/test_ib_connection.py

# Test market data
PYTHONPATH=. python scripts/test_market_data_freshness.py

# Backtest quick
python scripts/test_backtest.py
```

### Adding New Tickers

Edit dynamic thresholds in `scripts/edge_scanner.py`:

```python
EDGE_THRESHOLDS = {
    'AAPL': 2.0,   # High liquidity
    'TSLA': 4.0,   # Very volatile
    'YOUR_TICKER': 3.0,  # Add here
    'default': 3.0
}
```

---

## 📚 Documentation

- **[IB Setup Guide](docs/IB_SETUP_GUIDE.md)** - Interactive Brokers configuration
- **[Trading Guide](docs/TRADING_GUIDE.md)** - How to trade manually
- **[Strategy Improvements](STRATEGY_IMPROVEMENTS.md)** - Future enhancements roadmap
- **[Backtest Analysis](docs/BACKTEST_ANALYSIS.md)** - Historical performance details
- **[Stress Test Results](docs/STRESS_TEST_RESULTS.md)** - Multi-scenario analysis

---

## ⚠️ Risks & Limitations

### Known Limitations

1. **Model Risk**
   - LSM model can mispricedeep OTM/short-dated options
   - Monte Carlo noise creates false positives (~5% standard error)
   - Vol surface modeling is simplified (uses quoted IV directly)

2. **Market Risk**
   - Selling puts has unlimited downside (if held to assignment)
   - Overnight gaps can blow through stop-losses
   - Black swan events not fully captured in stress tests

3. **Data Limitations**
   - Backtests use **simulated** options data (real data recommended)
   - Historical vol may not predict future vol
   - Market regime changes invalidate historical patterns

4. **Execution Risk**
   - Slippage on large orders (100+ contracts)
   - Wide bid-ask spreads on illiquid options
   - Stop-losses only work during market hours

### Risk Management Best Practices

✅ **DO:**
- Start with paper trading
- Use position sizing (5% max per trade)
- Set stop-losses (25-50%)
- Diversify across tickers
- Monitor positions daily
- Keep detailed trade logs

❌ **DON'T:**
- Trade with money you can't afford to lose
- Ignore stop-losses
- Over-leverage (>50% notional exposure)
- Sell options on earnings dates
- Trade illiquid options (wide spreads)
- Hold short options through black swans

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:

1. **Better vol surface modeling** (SABR, SVI models)
2. **Greeks-based filters** (delta, gamma, vega checks)
3. **Portfolio-level risk** (correlation, stress testing)
4. **Machine learning** (better edge prediction)
5. **Real options data integration** (OptionMetrics, CBOE)

See `STRATEGY_IMPROVEMENTS.md` for detailed roadmap.

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **Longstaff-Schwartz (2001)** - American option pricing via LSM
- **Interactive Brokers** - Trading API and paper trading
- **yfinance** - Market data
- **ib_insync** - Python IB API wrapper

---

## 📧 Contact

Questions? Issues? Feel free to:
- Open an issue on GitHub
- Review `docs/` folder for detailed guides
- Check `STRATEGY_IMPROVEMENTS.md` for known issues

---

## ⚡ Quick Commands Cheat Sheet

```bash
# Scan for edges
PYTHONPATH=. python scripts/edge_scanner.py --ticker AAPL

# Start trader (easy mode)
cd scripts && ./start_trader.sh

# Start trader (custom)
PYTHONPATH=. python scripts/run_trader.py --mode paper --tickers AAPL NVDA

# Check positions
PYTHONPATH=. python scripts/utils/view_positions.py

# Close all positions
PYTHONPATH=. python scripts/close_all_positions.py

# Backtest
python scripts/run_backtest.py --tickers AAPL --start 2023-01-01

# Stress test
python scripts/stress_test.py --mode all
python scripts/analyze_stress_test.py

# Test IB connection
PYTHONPATH=. python scripts/test_ib_connection.py
```

---

**Happy Trading! 🚀**

*Remember: Past performance doesn't guarantee future results. Trade responsibly.*
