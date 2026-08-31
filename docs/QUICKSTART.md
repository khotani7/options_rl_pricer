# Quick Start Guide - Automated Options Trading System

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies

```bash
cd /Users/kabirhotani/Downloads/options_rl_pricer
pip install -r requirements.txt
```

### Step 2: Test Your Setup

```bash
# Test the backtesting system
python test_backtest.py
```

You should see:
```
✓ Loading data...
✓ Running backtest...
✓ Test Complete!
```

### Step 3: Run Your First Backtest

```bash
# Backtest LSM arbitrage strategy on AAPL
python run_backtest.py \
    --strategy lsm_arbitrage \
    --tickers AAPL \
    --start 2024-01-01 \
    --end 2024-08-31 \
    --capital 100000
```

Expected output:
```
Total Trades:       15
Win Rate:           60.0%
Total Return:       8.5%
Sharpe Ratio:       1.2
```

### Step 4: Scan for Live Opportunities

```bash
# Find mispriced options right now
python edge_scanner.py --ticker AAPL --min-edge 2.5
```

You'll see:
```
TOP TRADING OPPORTUNITIES
#1 | SELL_PUT | Edge: 4.0%
    PUT $322 exp 2026-09-02 (2d)
    Market: $7.42 (bid $7.25 / ask $7.60)
    American premium: $0.29 (4.0%)
```

### Step 5: Paper Trade (Simulated)

```bash
# Test the automated trader without IB
python run_trader.py --mode mock --tickers AAPL
```

This runs in "mock mode" - simulates trading without connecting to IB.

---

## 📊 Next Steps

### A. Serious Backtesting

```bash
# Test multiple strategies
python run_backtest.py --strategy lsm_arbitrage --start 2023-01-01 --end 2024-12-31
python run_backtest.py --strategy early_exercise --start 2023-01-01 --end 2024-12-31
python run_backtest.py --strategy vol_skew --start 2023-01-01 --end 2024-12-31

# Review results
ls outputs/backtest/
# equity_curve.csv, trades.csv, performance_metrics.csv
```

### B. Paper Trading with Interactive Brokers

1. **Download IB Gateway**
   - https://www.interactivebrokers.com/en/trading/tws.php
   - Create paper trading account

2. **Configure API Access**
   - Launch IB Gateway
   - Go to Configure → Settings → API
   - Enable Socket Clients
   - Port: 7497 (paper trading)
   - Trusted IPs: Add 127.0.0.1

3. **Connect & Trade**
   ```bash
   python run_trader.py --mode paper --tickers AAPL XOM JPM
   ```

### C. Live Trading (Only After Extensive Testing!)

```bash
# ⚠️ USE REAL MONEY - BE CAREFUL
python run_trader.py --mode live --port 7496 --max-positions 3
```

---

## 🎯 Common Use Cases

### Find Today's Best Opportunities

```bash
# Scan multiple stocks
for ticker in AAPL MSFT GOOGL XOM JPM; do
    python edge_scanner.py --ticker $ticker --min-edge 3.0
done
```

### Backtest Custom Parameters

```bash
python run_backtest.py \
    --strategy lsm_arbitrage \
    --tickers AAPL XOM JPM \
    --min-edge 4.0 \
    --max-positions 5 \
    --capital 50000 \
    --start 2024-01-01 \
    --end 2024-08-31
```

### Run Automated Trader with Custom Risk

```bash
python run_trader.py \
    --mode paper \
    --tickers AAPL \
    --max-positions 5 \
    --min-edge 3.5 \
    --max-daily-loss 1.5 \
    --stop-loss 25.0 \
    --scan-interval 10
```

---

## 📁 Project Structure

```
options_rl_pricer/
├── backtesting/          # Backtesting framework
│   ├── data_loader.py    # Historical data
│   ├── engine.py         # Backtest engine
│   └── strategies.py     # Trading strategies
│
├── trading/              # Live trading
│   ├── ib_connector.py   # IB API integration
│   └── automated_trader.py # Automated trader
│
├── data/                 # Market data
│   └── market_data.py    # Data fetching
│
├── pricing/              # Option pricing
│   └── lsm.py           # LSM pricer
│
├── rl/                   # RL agent
│   ├── agent.py         # DQN agent
│   └── env.py           # RL environment
│
├── edge_scanner.py       # Edge detection
├── run_backtest.py       # Run backtests
├── run_trader.py         # Run live trader
└── test_backtest.py      # Quick test
```

---

## ⚙️ Configuration Reference

### Backtest Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--strategy` | simple | Strategy to test |
| `--tickers` | AAPL | Stocks to trade |
| `--start` | 2024-01-01 | Start date |
| `--end` | 2024-03-31 | End date |
| `--capital` | 100000 | Initial capital |
| `--min-edge` | 3.0 | Min edge threshold % |
| `--max-positions` | 10 | Max positions |

### Trading Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--mode` | mock | mock/paper/live |
| `--host` | 127.0.0.1 | IB Gateway host |
| `--port` | 7497 | IB port (7497=paper) |
| `--tickers` | AAPL,XOM,JPM | Stocks to trade |
| `--scan-interval` | 15 | Scan every N minutes |
| `--max-positions` | 10 | Max open positions |
| `--min-edge` | 3.0 | Min edge % to trade |
| `--max-daily-loss` | 2.0 | Max daily loss % |
| `--stop-loss` | 30.0 | Stop loss % per position |

---

## 🆘 Troubleshooting

### "No module named ib_insync"
```bash
pip install ib_insync
```

### "Failed to connect to IB"
1. Check IB Gateway is running
2. Verify port 7497 (paper) or 7496 (live)
3. Enable API in IB settings
4. Add 127.0.0.1 to Trusted IPs

### "No significant edge found"
1. Lower `--min-edge` to 2.0
2. Add more tickers
3. Check market conditions (high vol = more edge)

### Backtest runs slowly
- Use shorter date range for testing
- Reduce number of tickers
- Use `--quick` flag if available

---

## 📚 Documentation

- **Full Trading Guide**: See `TRADING_GUIDE.md`
- **Original README**: See `README.md`
- **Code Documentation**: Inline comments in each file

---

## ✅ Pre-Live Checklist

Before trading real money:

- [ ] Backtest shows 6+ months of consistent profits
- [ ] Paper trade for 1+ month successfully
- [ ] Understand all code and risk controls
- [ ] Set appropriate position sizes (<5% per trade)
- [ ] Have stop-losses in place
- [ ] Monitor continuously during market hours
- [ ] Start with small capital (<10% of account)
- [ ] Test emergency shutdown (Ctrl+C)

---

## 🎓 Learning Path

1. **Week 1**: Backtesting
   - Run test_backtest.py
   - Understand different strategies
   - Analyze performance metrics

2. **Week 2**: Edge Detection
   - Run edge_scanner.py daily
   - Understand what creates edge
   - Track opportunities found

3. **Week 3**: Paper Trading Setup
   - Install IB Gateway
   - Configure API
   - Run mock trader

4. **Week 4**: Paper Trading
   - Run automated paper trader
   - Monitor performance
   - Refine parameters

5. **Month 2+**: Live Trading (if ready)
   - Start with 1-2 positions
   - Scale slowly
   - Monitor continuously

---

## 💡 Tips for Success

1. **Start Small**: Test with 1 ticker, low capital
2. **Be Patient**: Wait for high-edge opportunities (>4%)
3. **Monitor Closely**: Check trader output hourly
4. **Keep Learning**: Review every trade
5. **Respect Risk**: Never override stop-losses

---

## 🤝 Support

Questions? Check:
1. TRADING_GUIDE.md (comprehensive guide)
2. Code comments (detailed explanations)
3. Test files (working examples)

---

**Ready to start?**

```bash
python test_backtest.py
```

Good luck! 🚀
