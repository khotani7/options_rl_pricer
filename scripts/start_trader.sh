#!/bin/bash
cd /Users/kabirhotani/Downloads/options_rl_pricer
PYTHONPATH=. python scripts/run_trader.py \
    --mode paper \
    --tickers AAPL NVDA MU SNDK AMD PLTR NBIS TSLA SPCX META \
    --scan-interval 15 \
    --max-positions 10 \
    --client-id 100 \
    --use-market-orders \
    --min-premium 0.75 \
    --min-moneyness 0.94 \
    --max-moneyness 1.06 \
    --min-dte 10 \
    --max-dte 45 \
    --max-spread-pct 20 \
    --min-edge 6.0 \
    --max-position-size 7.5 \
    --max-notional 75.0
