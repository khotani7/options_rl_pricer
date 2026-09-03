#!/bin/bash
# Backtest: What would have traded today
# Shows what opportunities existed for each ticker

cd /Users/kabirhotani/Downloads/options_rl_pricer

echo "========================================================================"
echo "BACKTEST: What Would Have Traded Today"
echo "========================================================================"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Scanning tickers: AAPL NVDA MSFT META TSLA"
echo "Using new improvements:"
echo "  - Earnings filter (skip if earnings < 7 days)"
echo "  - Dynamic edge thresholds (2-5% based on ticker)"
echo "  - 1.5x stop-loss"
echo ""
echo "========================================================================"

for ticker in AAPL NVDA MSFT META TSLA; do
  echo ""
  echo ">>> Scanning $ticker..."
  PYTHONPATH=. python scripts/edge_scanner.py --ticker $ticker 2>&1 | head -60
  echo ""
  echo "Press Enter to continue to next ticker..."
  read
done

echo ""
echo "========================================================================"
echo "Backtest complete!"
echo "========================================================================"
