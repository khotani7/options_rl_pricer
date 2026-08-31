"""
Out-of-sample evaluation: freeze the trained policy, roll it out
greedily (no exploration) on freshly simulated paths never seen during
training, and compare against the Longstaff-Schwartz benchmark, a
Black-Scholes European reference, and (when reachable) a real market
option quote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.stats import norm

from rl.agent import DQNAgent
from rl.env import BatchedAmericanOptionEnv, state_features, payoff
from simulation.gbm import simulate_gbm_paths


def black_scholes_european(S0, K, r, q, sigma, T, option_type="put"):
    """Reference lower bound: a European option is never worth more than
    the corresponding American option, so RL/LSM prices should be >= this
    (equal for calls on non-dividend payers, where early exercise is never
    optimal)."""
    if T <= 0:
        return payoff(np.array([S0]), K, option_type)[0]
    d1 = (np.log(S0 / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "call":
        return S0 * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S0 * np.exp(-q * T) * norm.cdf(-d1)


@dataclass
class EvalResult:
    price: float
    std_error: float
    exercise_boundary: np.ndarray
    exercise_times: np.ndarray
    rewards: np.ndarray


def evaluate_policy(agent: DQNAgent, env_params: dict, K: float, option_type: str,
                     paths: np.ndarray) -> EvalResult:
    """
    Rolls the trained (frozen, greedy) policy out on `paths` -- pass a
    freshly simulated, out-of-sample batch (never used during training)
    for an unbiased price estimate.
    """
    r, q, sigma, T, n_steps = (
        env_params["r"], env_params["q"], env_params["sigma"],
        env_params["T"], env_params["n_steps"],
    )
    dt = T / n_steps
    disc = np.exp(-r * dt)

    env = BatchedAmericanOptionEnv(K=K, r=r, q=q, sigma=sigma, T=T, n_steps=n_steps, option_type=option_type)
    obs = env.reset(paths)
    n = paths.shape[0]
    active = np.ones(n, dtype=bool)
    rewards = np.zeros(n, dtype=np.float32)
    exercise_time = np.zeros(n, dtype=np.int64)
    boundary_hits = {t: [] for t in range(n_steps + 1)}

    for _ in range(n_steps + 1):
        prev_active = active.copy()
        action = agent.greedy_action(obs)
        action = np.where(prev_active, action, 0)

        # Only count *economically meaningful* exercises (positive intrinsic
        # value) toward the boundary -- an "exercise" action on an
        # out-of-the-money path pays 0 regardless and isn't a real early-
        # exercise decision, so including it would just add noise to the
        # boundary plot (this is a known weak spot of the current policy;
        # see the README's Known Limitations section).
        itm_now = payoff(paths[:, env.t], K, option_type) > 0
        exercised_this_step = prev_active & action.astype(bool) & itm_now
        if exercised_this_step.any():
            boundary_hits[env.t].extend(paths[exercised_this_step, env.t].tolist())

        next_obs, reward, done, info = env.step(action)
        newly_done = prev_active & done
        rewards[newly_done] = reward[newly_done]
        exercise_time[newly_done] = info["exercise_time"]

        active = ~done
        obs = next_obs
        if not active.any():
            break

    exercise_boundary = np.full(n_steps + 1, np.nan)
    for t, vals in boundary_hits.items():
        if vals:
            # put exercise region is unbounded below -> boundary = max exercised price;
            # call exercise region is unbounded above -> boundary = min exercised price.
            exercise_boundary[t] = (max(vals) if option_type == "put" else min(vals))

    # rewards emitted by env.step are normalized by K (see rl/env.py); rescale to $ here
    discounted = rewards * disc ** exercise_time * K
    price = float(discounted.mean())
    std_error = float(discounted.std(ddof=1) / np.sqrt(n))

    return EvalResult(price=price, std_error=std_error, exercise_boundary=exercise_boundary,
                       exercise_times=exercise_time, rewards=rewards)
