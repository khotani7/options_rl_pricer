"""
Vectorized American-option optimal-stopping environment.

Formulates American option pricing as an RL problem: at each time step
the agent observes the state of every path in a simulated batch and
chooses HOLD (0) or EXERCISE (1) for each one independently. Exercising
pays the intrinsic value and ends that path's episode; holding to
maturity forces settlement (exercise if ITM, else worthless expiry).

This is a batched/vectorized environment (all paths of a Monte Carlo
draw advance together), which is what makes training a DQN against
tens of thousands of freshly self-simulated paths per epoch tractable.
"""

from __future__ import annotations

import numpy as np


def payoff(S: np.ndarray, K: float, option_type: str) -> np.ndarray:
    if option_type == "put":
        return np.maximum(K - S, 0.0)
    return np.maximum(S - K, 0.0)


def state_features(S_t: np.ndarray, t: int, n_steps: int, K: float, option_type: str) -> np.ndarray:
    """
    3 hand-picked features per path, all scale-normalized so the
    network generalizes across tickers/strikes:
      1. moneyness      = S_t / K - 1
      2. time_remaining  = (n_steps - t) / n_steps   in [0, 1]
      3. intrinsic_frac = payoff(S_t, K) / K
    """
    moneyness = S_t / K - 1.0
    time_remaining = np.full_like(S_t, (n_steps - t) / n_steps)
    intrinsic_frac = payoff(S_t, K, option_type) / K
    return np.stack([moneyness, time_remaining, intrinsic_frac], axis=1).astype(np.float32)


class BatchedAmericanOptionEnv:
    """
    obs: (n_paths, 3) float32
    step(action): action is (n_paths,) int array {0=hold, 1=exercise}.
      Returns (next_obs, reward, done, info). Once a path is `done` it
      stays done and emits zero further reward regardless of the
      action supplied for it (the caller is expected to mask done
      paths out of training, but it's safe either way).
    """

    def __init__(self, K: float, r: float, q: float, sigma: float, T: float,
                 n_steps: int, option_type: str = "put"):
        self.K = K
        self.r = r
        self.q = q
        self.sigma = sigma
        self.T = T
        self.n_steps = n_steps
        self.dt = T / n_steps
        self.option_type = option_type

        self.paths: np.ndarray | None = None
        self.t = 0
        self.done: np.ndarray | None = None
        self.n_paths = 0

    def reset(self, paths: np.ndarray) -> np.ndarray:
        """
        `paths`: (n_paths, n_steps+1) array from simulation.gbm.simulate_gbm_paths,
        using this env's own r/q/sigma/T/n_steps. Each self-training epoch
        (see rl/train.py) draws a *fresh* batch of paths -- the agent never
        reuses episodes, which is what makes this "self-training" rather
        than fitting a fixed offline dataset.
        """
        self.paths = paths
        self.n_paths = paths.shape[0]
        self.t = 0
        self.done = np.zeros(self.n_paths, dtype=bool)
        return state_features(self.paths[:, 0], 0, self.n_steps, self.K, self.option_type)

    def step(self, action: np.ndarray):
        """
        Reward is the exercise payoff normalized by strike (payoff/K),
        not the raw dollar payoff. This keeps rewards O(1) regardless of
        whether the underlying trades at $20 or $2000, which matters a
        lot for DQN training stability -- and lets the same network
        hyperparameters work across the whole mid/high-cap universe.
        Callers that want dollar prices multiply back by K (train.py and
        evaluation/evaluate.py both do this).
        """
        assert self.paths is not None, "call reset() first"
        S_t = self.paths[:, self.t]
        reward = np.zeros(self.n_paths, dtype=np.float32)
        newly_done = np.zeros(self.n_paths, dtype=bool)

        exercise_now = (action.astype(bool)) & (~self.done)
        reward[exercise_now] = payoff(S_t[exercise_now], self.K, self.option_type) / self.K
        newly_done |= exercise_now

        is_last_step = self.t == self.n_steps
        if is_last_step:
            forced = (~self.done) & (~exercise_now)
            reward[forced] = payoff(S_t[forced], self.K, self.option_type) / self.K
            newly_done |= forced

        self.done = self.done | newly_done

        if not is_last_step:
            self.t += 1
        next_obs = state_features(self.paths[:, self.t], self.t, self.n_steps, self.K, self.option_type)

        info = {"exercise_time": self.t, "newly_done": newly_done}
        return next_obs, reward, self.done.copy(), info

    @property
    def finished(self) -> bool:
        return self.t >= self.n_steps and self.done.all()
