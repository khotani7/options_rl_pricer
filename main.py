"""
End-to-end pipeline: pull real market data for a mid/high-cap ticker,
self-train a DQN agent to learn the optimal early-exercise policy for
an American option on it, and evaluate the result against a
Longstaff-Schwartz Monte Carlo benchmark, a Black-Scholes European
reference, and (when reachable) a live market option quote.

Usage:
    python main.py --ticker DECK --option-type put --moneyness 1.0 \
        --maturity-years 0.5 --n-steps 50 --epochs 150

Run `python main.py --help` for the full list of options.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from config import RunConfig, classify_cap
from data.market_data import fetch_market_params, get_real_option_quote
from evaluation.evaluate import black_scholes_european, evaluate_policy
from evaluation.plots import plot_convergence, plot_exercise_boundary, plot_price_comparison
from pricing.lsm import longstaff_schwartz_price
from rl.train import self_train
from simulation.gbm import simulate_gbm_paths


def parse_args() -> RunConfig:
    d = RunConfig()  # single source of truth for defaults -- see config.py
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticker", default=d.ticker)
    p.add_argument("--option-type", choices=["put", "call"], default=d.option_type)
    p.add_argument("--moneyness", type=float, default=d.moneyness, help="strike = moneyness * spot")
    p.add_argument("--maturity-years", type=float, default=d.maturity_years)
    p.add_argument("--n-steps", type=int, default=d.n_steps)
    p.add_argument("--train-paths-per-epoch", type=int, default=d.train_paths_per_epoch)
    p.add_argument("--epochs", type=int, default=d.n_epochs)
    p.add_argument("--eval-paths", type=int, default=d.eval_paths)
    p.add_argument("--lsm-paths", type=int, default=d.lsm_paths)
    p.add_argument("--seed", type=int, default=d.seed)
    p.add_argument("--output-dir", default=d.output_dir)
    p.add_argument("--quick", action="store_true", help="fast smoke-test sizes")
    args = p.parse_args()

    cfg = RunConfig(
        ticker=args.ticker, option_type=args.option_type, moneyness=args.moneyness,
        maturity_years=args.maturity_years, n_steps=args.n_steps,
        train_paths_per_epoch=args.train_paths_per_epoch, n_epochs=args.epochs,
        eval_paths=args.eval_paths, lsm_paths=args.lsm_paths, seed=args.seed,
        output_dir=args.output_dir,
    )
    if args.quick:
        cfg.n_steps = 20
        cfg.train_paths_per_epoch = 500
        cfg.n_epochs = 30
        cfg.eval_paths = 4000
        cfg.lsm_paths = 4000
        cfg.eps_decay_epochs = 20
    return cfg


def run(cfg: RunConfig) -> dict:
    os.makedirs(cfg.output_dir, exist_ok=True)

    print(f"\n=== Fetching market data for {cfg.ticker} ===")
    market = fetch_market_params(cfg.ticker)
    print(
        f"  spot={market.spot:.2f}  vol={market.vol:.2%}  r={market.risk_free_rate:.2%}  "
        f"q={market.dividend_yield:.2%}  cap={market.cap_bucket} "
        f"(${(market.market_cap or 0)/1e9:.1f}B)  source={market.source} as_of={market.as_of}"
    )
    K = cfg.moneyness * market.spot

    print(f"\n=== Self-training DQN agent ({cfg.n_epochs} epochs, "
          f"{cfg.train_paths_per_epoch} fresh paths/epoch) ===")
    agent, history, env_params = self_train(cfg, market)

    print(f"\n=== Longstaff-Schwartz benchmark ({cfg.lsm_paths} paths) ===")
    rng = np.random.default_rng(cfg.seed + 1)
    lsm_paths = simulate_gbm_paths(
        S0=market.spot, r=market.risk_free_rate, q=market.dividend_yield, sigma=market.vol,
        T=cfg.maturity_years, n_steps=cfg.n_steps, n_paths=cfg.lsm_paths, rng=rng,
    )
    lsm_result = longstaff_schwartz_price(lsm_paths, K, market.risk_free_rate, cfg.maturity_years, cfg.option_type)
    print(f"  LSM price = {lsm_result.price:.4f} +/- {lsm_result.std_error:.4f}")

    print(f"\n=== Evaluating RL policy out-of-sample ({cfg.eval_paths} fresh paths) ===")
    rng_eval = np.random.default_rng(cfg.seed + 2)
    eval_paths = simulate_gbm_paths(
        S0=market.spot, r=market.risk_free_rate, q=market.dividend_yield, sigma=market.vol,
        T=cfg.maturity_years, n_steps=cfg.n_steps, n_paths=cfg.eval_paths, rng=rng_eval,
    )
    rl_result = evaluate_policy(agent, env_params, K, cfg.option_type, eval_paths)
    print(f"  RL price  = {rl_result.price:.4f} +/- {rl_result.std_error:.4f}")

    bs_price = black_scholes_european(
        market.spot, K, market.risk_free_rate, market.dividend_yield, market.vol, cfg.maturity_years, cfg.option_type
    )
    print(f"  European Black-Scholes reference = {bs_price:.4f} (American should be >= this)")

    print("\n=== Checking for a live market option quote (best effort) ===")
    market_quote = get_real_option_quote(cfg.ticker, cfg.option_type, cfg.moneyness)
    if market_quote:
        print(f"  Real market quote: {market_quote}")
    else:
        print("  No live option chain reachable in this environment -- skipping market-quote comparison.")

    print("\n=== Saving plots ===")
    tag = f"{cfg.ticker}_{cfg.option_type}"
    plot_convergence(history, lsm_result.price, os.path.join(cfg.output_dir, f"convergence_{tag}.png"))
    plot_exercise_boundary(
        rl_result.exercise_boundary, lsm_result.exercise_boundary, K, cfg.n_steps, cfg.maturity_years,
        os.path.join(cfg.output_dir, f"exercise_boundary_{tag}.png"),
    )
    prices = {"RL (DQN)": rl_result.price, "Longstaff-Schwartz": lsm_result.price, "BS European": bs_price}
    errors = {"RL (DQN)": rl_result.std_error, "Longstaff-Schwartz": lsm_result.std_error}
    if market_quote:
        prices["Market quote"] = market_quote["market_price"]
    plot_price_comparison(prices, errors, os.path.join(cfg.output_dir, f"price_comparison_{tag}.png"))

    report = {
        "ticker": cfg.ticker,
        "cap_bucket": market.cap_bucket,
        "market_cap": market.market_cap,
        "spot": market.spot,
        "strike": K,
        "option_type": cfg.option_type,
        "maturity_years": cfg.maturity_years,
        "vol": market.vol,
        "risk_free_rate": market.risk_free_rate,
        "dividend_yield": market.dividend_yield,
        "data_source": market.source,
        "data_as_of": market.as_of,
        "rl_price": rl_result.price,
        "rl_std_error": rl_result.std_error,
        "lsm_price": lsm_result.price,
        "lsm_std_error": lsm_result.std_error,
        "bs_european_price": bs_price,
        "market_quote": market_quote,
        "n_epochs": cfg.n_epochs,
        "train_paths_per_epoch": cfg.train_paths_per_epoch,
    }
    report_path = os.path.join(cfg.output_dir, f"report_{cfg.ticker}_{cfg.option_type}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=float)
    print(f"\nSaved report to {report_path}")
    print(f"Saved plots to {cfg.output_dir}/")

    return report


if __name__ == "__main__":
    cfg = parse_args()
    run(cfg)
