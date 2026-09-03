"""
Edge Scanner: Find mispriced American options for paper-trading opportunities.

Usage:
    python edge_scanner.py --ticker AAPL
    python edge_scanner.py --ticker AAPL --min-edge 5.0

--- Why this version differs from the original ---

The original edge_scanner.py compared each market price to a *European*
Black-Scholes price and called the gap the "American premium," flagging a
large gap on ITM puts as a SELL signal (implying overpriced). That's not a
mispricing signal -- an American put is *supposed* to trade above its
European value, because of the early-exercise right. That gap is routinely
well above a few percent for ITM puts, especially at current risk-free
rates, so the old logic would flag ordinary, correctly-priced options as
"edge" constantly.

This version instead prices each candidate contract as an American option
via Longstaff-Schwartz Monte Carlo (pricing/lsm.py) -- the same benchmark
this project treats as authoritative (see README's Known Limitations: the
RL/DQN model still has a documented, unvalidated bias against LSM, so it is
deliberately NOT used to drive trading decisions here; it's a slower,
research-stage secondary signal you can inspect separately, not the thing
deciding "edge"). Edge is then market price vs. that LSM fair value, which
is the correct like-for-like comparison (American vs. American).

The pre-filters from the original (min volume, spread width) are kept,
applied *before* running LSM, since LSM is much more expensive per contract
than the old closed-form Black-Scholes formula -- this keeps a full-chain
scan fast.
"""

import argparse
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

from data.market_data import fetch_market_params
from pricing.lsm import longstaff_schwartz_price
from simulation.gbm import simulate_gbm_paths

# LSM sizing for the scanner: enough for a stable price estimate on a single
# contract in well under a second, small enough to scan a whole chain.
# NOTE: For short-dated options, we need MORE time steps to capture dynamics
LSM_N_PATHS = 6000  # Fixed number of paths

# Minimum days to expiry - below this, LSM with reasonable computation time
# cannot accurately price the option due to time discretization issues
MIN_DAYS_TO_EXPIRY = 5


def _adaptive_n_steps(days_to_expiry: int) -> int:
    """
    Choose number of LSM time steps based on days to expiry.

    Short-dated options need MORE steps per day to capture rapid changes.
    Long-dated options can use fewer steps per day.

    Target: ~2 steps per trading day for reasonable accuracy
    """
    if days_to_expiry < 5:
        # Very short dated - not recommended, but if forced use many steps
        return max(50, days_to_expiry * 10)
    elif days_to_expiry < 15:
        # Short dated: ~3 steps per day
        return max(30, days_to_expiry * 3)
    elif days_to_expiry < 60:
        # Medium dated: ~2 steps per day
        return max(50, days_to_expiry * 2)
    else:
        # Long dated: ~1 step per day is enough
        return min(100, max(60, days_to_expiry))


def _lsm_fair_value(spot, K, T, r, q, iv, option_type, days_to_expiry, seed):
    """American fair value for one contract, using the option's OWN quoted
    implied vol (not a single flat ticker-level vol) so strike/expiry skew
    is respected -- this matters a lot across a chain."""
    n_steps = _adaptive_n_steps(days_to_expiry)
    rng = np.random.default_rng(seed)
    paths = simulate_gbm_paths(S0=spot, r=r, q=q, sigma=iv, T=T, n_steps=n_steps,
                                n_paths=LSM_N_PATHS, rng=rng)
    result = longstaff_schwartz_price(paths, K, r, T, option_type=option_type, degree=3)
    return result.price, result.std_error


def scan_option_chain(ticker: str, min_volume: int = 5, min_edge_pct: float = 3.0,
                       max_expiries: int = 3, seed: int = 0,
                       min_moneyness: float = 0.85, max_moneyness: float = 1.15):
    """
    Scan a real option chain for LSM-vs-market mispricing.

    Returns a DataFrame of candidate opportunities ranked by |edge_score|,
    or None if nothing clears the filters. This function only reads market
    data and computes prices -- it never places an order.
    """
    params = fetch_market_params(ticker)
    spot, r, q = params.spot, params.risk_free_rate, params.dividend_yield

    print(f"\n{'='*70}")
    print(f"Edge Scanner (LSM fair value): {ticker}")
    print(f"{'='*70}")
    print(f"Spot: ${spot:.2f} | r={r:.2%} | q={q:.2%}")
    print(f"Data source: {params.source} | As of: {params.as_of}\n")

    t = yf.Ticker(ticker)
    expiries = t.options
    if not expiries:
        print("No option data available")
        return None

    opportunities = []
    today = datetime.now().date()

    for expiry in expiries[:max_expiries]:
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            days_to_exp = (exp_date - today).days
            T = days_to_exp / 365.0
            if T <= 0:
                continue

            # Filter out very short-dated options - LSM cannot price them accurately
            # with reasonable computation time due to time discretization issues
            if days_to_exp < MIN_DAYS_TO_EXPIRY:
                print(f"  Skipping {expiry} ({days_to_exp}d) - too short-dated for accurate LSM pricing")
                continue

            chain = t.option_chain(expiry)

            for option_type, table in (("put", chain.puts), ("call", chain.calls)):
                for _, row in table.iterrows():
                    if row["volume"] < min_volume or not row["bid"] or not row["ask"]:
                        continue

                    K = row["strike"]
                    iv = row["impliedVolatility"]
                    bid = row["bid"]
                    ask = row["ask"]

                    # Filter by moneyness - avoid deep OTM options
                    moneyness = K / spot
                    if moneyness < min_moneyness or moneyness > max_moneyness:
                        continue

                    # Filter out NaN or invalid prices
                    import math
                    if math.isnan(bid) or math.isnan(ask) or bid <= 0 or ask <= 0:
                        continue

                    market_mid = (bid + ask) / 2
                    spread = ask - bid

                    if iv <= 0 or market_mid <= 0 or math.isnan(market_mid):
                        continue
                    if spread >= market_mid * 0.15:  # ignore wide spreads
                        continue

                    fair_value, std_err = _lsm_fair_value(spot, K, T, r, q, iv, option_type, days_to_exp, seed)
                    if fair_value <= 0:
                        continue

                    edge_pct = (market_mid - fair_value) / fair_value * 100.0
                    # require the edge to clear both the threshold AND the
                    # LSM estimator's own Monte Carlo noise, so we're not
                    # trading on simulation noise dressed up as edge.
                    noise_floor_pct = (2 * std_err / fair_value) * 100.0
                    if abs(edge_pct) < max(min_edge_pct, noise_floor_pct):
                        continue

                    signal = "SELL" if edge_pct > 0 else "BUY"
                    opportunities.append({
                        "ticker": ticker, "expiry": expiry, "days": days_to_exp,
                        "type": option_type.upper(), "strike": K,
                        "moneyness": K / spot, "market_mid": market_mid,
                        "bid": row["bid"], "ask": row["ask"],
                        "spread_pct": spread / market_mid * 100,
                        "iv": iv, "lsm_fair_value": fair_value, "lsm_std_error": std_err,
                        "edge_pct": edge_pct, "edge_score": abs(edge_pct),
                        "signal": f"{signal}_{option_type.upper()}",
                        "volume": row["volume"], "oi": row["openInterest"],
                    })
        except Exception as e:
            print(f"Error processing {expiry}: {e}")
            continue

    if not opportunities:
        print("No significant edge found above threshold (after accounting for LSM Monte Carlo noise).")
        return None

    df = pd.DataFrame(opportunities).sort_values("edge_score", ascending=False)
    return df


def print_opportunities(df: pd.DataFrame, max_rows: int = 10):
    if df is None or df.empty:
        return
    print(f"\n{'='*70}")
    print(f"TOP TRADING OPPORTUNITIES (LSM fair value vs. market, ranked by edge)")
    print(f"{'='*70}\n")
    for i, row in df.head(max_rows).iterrows():
        print(f"#{i+1} | {row['signal']} | Edge: {row['edge_pct']:+.1f}%")
        print(f"    {row['type']} ${row['strike']:.0f} exp {row['expiry']} ({row['days']}d)")
        print(f"    Moneyness: {row['moneyness']:.3f} | IV: {row['iv']*100:.1f}%")
        print(f"    Market: ${row['market_mid']:.2f} (bid ${row['bid']:.2f} / ask ${row['ask']:.2f})")
        print(f"    LSM fair value: ${row['lsm_fair_value']:.2f} +/- {row['lsm_std_error']:.2f}")
        print(f"    Volume: {row['volume']:.0f} | OI: {row['oi']:.0f}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Scan a real option chain for LSM-vs-market edge")
    parser.add_argument("--ticker", type=str, default="AAPL")
    parser.add_argument("--min-volume", type=int, default=5)
    parser.add_argument("--min-edge", type=float, default=3.0)
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--max-expiries", type=int, default=3)
    args = parser.parse_args()

    df = scan_option_chain(args.ticker, args.min_volume, args.min_edge, args.max_expiries)
    print_opportunities(df, args.max_results)

    if df is not None and not df.empty:
        output_file = f"outputs/edge_opportunities_{args.ticker}.csv"
        df.to_csv(output_file, index=False)
        print(f"Saved detailed results to {output_file}")


if __name__ == "__main__":
    main()
