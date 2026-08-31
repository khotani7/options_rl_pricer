"""
Diagnose why LSM is showing 100%+ edges

This will help us understand if it's a bug or real mispricing
"""

import yfinance as yf
import numpy as np
from datetime import datetime
from scipy.stats import norm

from data.market_data import fetch_market_params
from pricing.lsm import longstaff_schwartz_price
from simulation.gbm import simulate_gbm_paths


def bs_call(S, K, T, r, q, sigma):
    """European Black-Scholes call"""
    if T <= 0:
        return max(S - K, 0)
    d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    return S*np.exp(-q*T)*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)


def bs_put(S, K, T, r, q, sigma):
    """European Black-Scholes put"""
    if T <= 0:
        return max(K - S, 0)
    d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    return K*np.exp(-r*T)*norm.cdf(-d2) - S*np.exp(-q*T)*norm.cdf(-d1)


def diagnose_option(ticker, strike, expiry_str, option_type='call'):
    """Diagnose one specific option"""

    # Get market data
    params = fetch_market_params(ticker)
    spot = params.spot
    r = params.risk_free_rate
    q = params.dividend_yield

    # Get option quote
    t = yf.Ticker(ticker)
    chain = t.option_chain(expiry_str)

    table = chain.calls if option_type == 'call' else chain.puts
    option = table[table['strike'] == strike]

    if option.empty:
        print(f"Option not found: {ticker} {strike} {option_type}")
        return

    row = option.iloc[0]
    iv = row['impliedVolatility']
    market_mid = (row['bid'] + row['ask']) / 2

    # Calculate time to expiry
    exp_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
    today = datetime.now().date()
    days = (exp_date - today).days
    T = days / 365.0

    print(f"\n{'='*70}")
    print(f"DIAGNOSING: {ticker} {option_type.upper()} ${strike:.0f} exp {expiry_str}")
    print(f"{'='*70}\n")

    print(f"Market Data:")
    print(f"  Spot: ${spot:.2f}")
    print(f"  Strike: ${strike:.0f}")
    print(f"  Days to expiry: {days}")
    print(f"  Time (years): {T:.4f}")
    print(f"  Implied vol: {iv*100:.1f}%")
    print(f"  Risk-free rate: {r*100:.2f}%")
    print(f"  Dividend yield: {q*100:.2f}%")
    print()

    print(f"Market Quotes:")
    print(f"  Bid: ${row['bid']:.2f}")
    print(f"  Ask: ${row['ask']:.2f}")
    print(f"  Mid: ${market_mid:.2f}")
    print(f"  Volume: {row['volume']:.0f}")
    print()

    # Calculate intrinsic value
    if option_type == 'call':
        intrinsic = max(spot - strike, 0)
    else:
        intrinsic = max(strike - spot, 0)

    time_value = market_mid - intrinsic

    print(f"Value Breakdown:")
    print(f"  Intrinsic: ${intrinsic:.2f}")
    print(f"  Time value: ${time_value:.2f}")
    print(f"  Moneyness: {strike/spot:.3f} ({'ITM' if intrinsic > 0 else 'OTM'})")
    print()

    # Black-Scholes (European)
    if option_type == 'call':
        bs_price = bs_call(spot, strike, T, r, q, iv)
    else:
        bs_price = bs_put(spot, strike, T, r, q, iv)

    print(f"Black-Scholes (European):")
    print(f"  Price: ${bs_price:.2f}")
    print(f"  vs Market: {(market_mid - bs_price):.2f} ({(market_mid/bs_price - 1)*100:+.1f}%)")
    print()

    # LSM (American) with adaptive time steps
    # For short-dated options, we need MORE steps to capture dynamics
    if days < 5:
        n_steps = max(50, days * 10)  # ~10 steps per day
        print(f"  ⚠️  Using {n_steps} time steps (short-dated option)")
    elif days < 15:
        n_steps = max(30, days * 3)  # ~3 steps per day
    elif days < 60:
        n_steps = max(50, days * 2)  # ~2 steps per day
    else:
        n_steps = min(100, max(60, days))  # ~1 step per day

    print(f"Running LSM (American) with {n_steps} time steps...")
    rng = np.random.default_rng(42)
    paths = simulate_gbm_paths(
        S0=spot, r=r, q=q, sigma=iv, T=T,
        n_steps=n_steps, n_paths=6000, rng=rng
    )

    result = longstaff_schwartz_price(
        paths, strike, r, T,
        option_type=option_type, degree=3
    )

    print(f"  LSM Price: ${result.price:.2f} +/- ${result.std_error:.2f}")
    print(f"  vs Market: ${(market_mid - result.price):.2f} ({(market_mid/result.price - 1)*100:+.1f}%)")
    print(f"  vs BS European: ${(result.price - bs_price):.2f} (American premium)")
    print()

    # Edge calculation
    lsm_edge = (market_mid - result.price) / result.price * 100
    bs_edge = (market_mid - bs_price) / bs_price * 100

    print(f"EDGE ANALYSIS:")
    print(f"  Market vs LSM: {lsm_edge:+.1f}%")
    print(f"  Market vs BS:  {bs_edge:+.1f}%")
    print()

    # Diagnose
    print(f"DIAGNOSIS:")

    if abs(lsm_edge) > 50:
        print(f"  ⚠️  EXTREME EDGE ({lsm_edge:+.1f}%) - Likely a problem!")

        if days <= 3:
            print(f"  → Very short dated ({days} days)")
            print(f"     LSM with only 30 time steps may not capture value well")
            print(f"     Recommend: Increase n_steps or avoid <3 day options")

        if result.price < bs_price * 0.8:
            print(f"  → LSM < BS European (should be ≥)")
            print(f"     This suggests LSM is underpricing")
            print(f"     Possible causes:")
            print(f"       - Too few paths (6000 may not be enough)")
            print(f"       - Regression fitting issues")
            print(f"       - Need more basis functions")

        if intrinsic > 0 and result.price < intrinsic * 1.01:
            print(f"  → LSM barely above intrinsic for ITM option")
            print(f"     Missing time value - LSM issue")

        if (market_mid / bs_price) < 1.2 and abs(lsm_edge) > 50:
            print(f"  → Market close to BS, but LSM shows huge edge")
            print(f"     Problem is likely with LSM, not market mispricing")

    elif abs(lsm_edge) > 20:
        print(f"  ⚠️  LARGE EDGE ({lsm_edge:+.1f}%) - Investigate")

        if abs(bs_edge) < 10:
            print(f"  → BS shows small edge, LSM shows large edge")
            print(f"     Difference is in American premium estimation")

            if option_type == 'call' and q < 0.02:
                print(f"     For calls with low dividend, American ≈ European")
                print(f"     LSM may be overestimating early exercise value")

    else:
        print(f"  ✓ Edge is reasonable ({lsm_edge:+.1f}%)")

        if lsm_edge > 0:
            print(f"     Market > LSM → Option appears overpriced")
            print(f"     Strategy: SELL")
        else:
            print(f"     Market < LSM → Option appears underpriced")
            print(f"     Strategy: BUY")

    print()

    # Path statistics
    final_prices = paths[-1, :]
    if option_type == 'call':
        itm_mask = final_prices > strike
    else:
        itm_mask = final_prices < strike

    pct_itm = itm_mask.mean() * 100

    print(f"LSM Simulation Stats:")
    print(f"  Paths ending ITM: {pct_itm:.1f}%")
    print(f"  Avg final price: ${final_prices.mean():.2f}")
    print(f"  Std final price: ${final_prices.std():.2f}")

    if itm_mask.any():
        if option_type == 'call':
            avg_itm_payoff = (final_prices[itm_mask] - strike).mean()
        else:
            avg_itm_payoff = (strike - final_prices[itm_mask]).mean()
        print(f"  Avg ITM payoff: ${avg_itm_payoff:.2f}")

    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', default='AAPL')
    parser.add_argument('--strike', type=float, default=328)
    parser.add_argument('--expiry', default='2026-09-02')
    parser.add_argument('--type', choices=['call', 'put'], default='call')

    args = parser.parse_args()

    diagnose_option(args.ticker, args.strike, args.expiry, args.type)
