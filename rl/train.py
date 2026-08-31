"""
Self-training loop.

Each epoch draws a brand-new batch of Monte Carlo paths (never reused
from a fixed dataset), rolls the current policy out against them with
epsilon-greedy exploration, pushes the resulting (state, action,
reward, next_state, done) transitions into a replay buffer, and runs
several DQN gradient updates. The agent's only "supervision" is the
Bellman consistency of its own predictions against rewards generated
by its own simulated interactions -- i.e. it trains itself, the same
way Longstaff-Schwartz fits a fresh regression from simulated paths at
every exercise date, except here one neural policy is learned jointly
across all time steps via temporal-difference learning.
"""

from __future__ import annotations

import time

import numpy as np

from config import RunConfig
from data.market_data import MarketParams
from rl.agent import DQNAgent, ReplayBuffer
from rl.env import BatchedAmericanOptionEnv
from simulation.gbm import simulate_gbm_paths


def rollout_epoch(env: BatchedAmericanOptionEnv, agent: DQNAgent, buffer: ReplayBuffer,
                   paths: np.ndarray, epsilon: float):
    obs = env.reset(paths)
    n_paths = paths.shape[0]
    active = np.ones(n_paths, dtype=bool)
    total_reward = np.zeros(n_paths, dtype=np.float32)
    exercise_time = np.zeros(n_paths, dtype=np.int64)

    for _ in range(env.n_steps + 1):
        prev_active = active.copy()
        action = agent.act(obs, epsilon, active_mask=prev_active)
        next_obs, reward, done, info = env.step(action)

        if prev_active.any():
            buffer.push_batch(
                obs[prev_active], action[prev_active], reward[prev_active],
                next_obs[prev_active], done[prev_active].astype(np.float32),
            )

        newly_done = prev_active & done
        total_reward[newly_done] = reward[newly_done]
        exercise_time[newly_done] = info["exercise_time"]

        active = ~done
        obs = next_obs
        if not active.any():
            break

    return total_reward, exercise_time


def self_train(cfg: RunConfig, market: MarketParams, log_every: int = 10, verbose: bool = True):
    rng = np.random.default_rng(cfg.seed)

    K = cfg.moneyness * market.spot
    r, q, sigma, T, n_steps = market.risk_free_rate, market.dividend_yield, market.vol, cfg.maturity_years, cfg.n_steps
    dt = T / n_steps
    gamma = np.exp(-r * dt)

    env = BatchedAmericanOptionEnv(K=K, r=r, q=q, sigma=sigma, T=T, n_steps=n_steps, option_type=cfg.option_type)
    agent = DQNAgent(state_dim=3, n_actions=2, hidden_dim=cfg.hidden_dim, lr=cfg.lr, gamma=gamma)
    buffer = ReplayBuffer(cfg.replay_capacity)

    history = {"epoch": [], "price_estimate": [], "loss": [], "epsilon": []}
    t0 = time.time()

    for epoch in range(cfg.n_epochs):
        epsilon = float(np.interp(epoch, [0, cfg.eps_decay_epochs], [cfg.eps_start, cfg.eps_end]))

        paths = simulate_gbm_paths(
            S0=market.spot, r=r, q=q, sigma=sigma, T=T, n_steps=n_steps,
            n_paths=cfg.train_paths_per_epoch, rng=rng,
        )
        rewards, ex_times = rollout_epoch(env, agent, buffer, paths, epsilon)

        losses = [agent.update(buffer, cfg.batch_size) for _ in range(cfg.updates_per_epoch)]
        losses = [l for l in losses if not np.isnan(l)]
        mean_loss = float(np.mean(losses)) if losses else float("nan")

        if epoch % cfg.target_sync_every == 0:
            agent.sync_target()

        # rewards from rollout_epoch are normalized by K (see env.step); rescale to $ here
        price_estimate = float(np.mean(rewards * gamma ** ex_times)) * K

        history["epoch"].append(epoch)
        history["price_estimate"].append(price_estimate)
        history["loss"].append(mean_loss)
        history["epsilon"].append(epsilon)

        if verbose and (epoch % log_every == 0 or epoch == cfg.n_epochs - 1):
            elapsed = time.time() - t0
            print(
                f"epoch {epoch:4d}/{cfg.n_epochs} | eps={epsilon:.3f} | "
                f"loss={mean_loss:.5f} | price~={price_estimate:.4f} | {elapsed:.1f}s"
            )

    return agent, history, {"K": K, "r": r, "q": q, "sigma": sigma, "T": T, "n_steps": n_steps, "gamma": gamma}
