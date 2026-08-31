"""
Risk-neutral Geometric Brownian Motion path simulator.

Both the Longstaff-Schwartz benchmark pricer and the RL self-training
loop draw their training/evaluation data from here, so the RL agent
never sees "labels" -- only freshly simulated paths it must learn an
exercise policy against.
"""

from __future__ import annotations

import numpy as np


def simulate_gbm_paths(
    S0: float,
    r: float,
    q: float,
    sigma: float,
    T: float,
    n_steps: int,
    n_paths: int,
    antithetic: bool = True,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Simulate risk-neutral GBM price paths.

    Returns an array of shape (n_paths, n_steps + 1), column 0 = S0.
    """
    if rng is None:
        rng = np.random.default_rng()

    dt = T / n_steps
    drift = (r - q - 0.5 * sigma ** 2) * dt
    vol_step = sigma * np.sqrt(dt)

    if antithetic:
        half = (n_paths + 1) // 2
        z = rng.standard_normal((half, n_steps))
        z = np.concatenate([z, -z], axis=0)[:n_paths]
    else:
        z = rng.standard_normal((n_paths, n_steps))

    log_increments = drift + vol_step * z
    log_paths = np.cumsum(log_increments, axis=1)
    log_paths = np.concatenate([np.zeros((n_paths, 1)), log_paths], axis=1)
    paths = S0 * np.exp(log_paths)
    return paths
