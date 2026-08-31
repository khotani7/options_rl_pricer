"""
Longstaff-Schwartz (2001) least-squares Monte Carlo pricer for American
options. Serves as the industry-standard benchmark the RL agent is
checked against.

Note: LSM is itself a "self-training" method in spirit -- at every
exercise date it fits a fresh regression model (continuation value ~
basis functions of the simulated price) purely from the simulated
paths, with no external labels. The RL agent in rl/ generalizes this
idea by learning a single parametric (neural) policy across all time
steps jointly via temporal-difference learning, rather than one
regression per time step.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _payoff(S: np.ndarray, K: float, option_type: str) -> np.ndarray:
    if option_type == "put":
        return np.maximum(K - S, 0.0)
    return np.maximum(S - K, 0.0)


@dataclass
class LSMResult:
    price: float
    std_error: float
    exercise_boundary: np.ndarray  # length n_steps+1, NaN where no ITM paths


def longstaff_schwartz_price(
    paths: np.ndarray,
    K: float,
    r: float,
    T: float,
    option_type: str = "put",
    degree: int = 3,
) -> LSMResult:
    """
    paths: (n_paths, n_steps + 1) simulated underlying price paths,
    column 0 = t=0, column -1 = maturity.
    """
    n_paths, n_cols = paths.shape
    n_steps = n_cols - 1
    dt = T / n_steps
    disc = np.exp(-r * dt)

    payoff = _payoff(paths, K, option_type)  # (n_paths, n_steps+1)

    cashflow = payoff[:, -1].copy()          # cashflow realized at maturity
    exercise_time = np.full(n_paths, n_steps, dtype=int)

    exercise_boundary = np.full(n_cols, np.nan)
    # Boundary convention: a call's exercise region is unbounded ABOVE
    # (S > boundary), so the boundary is the infimum (min) of exercised
    # prices; a put's exercise region is unbounded BELOW (S < boundary,
    # down to 0), so the boundary is the supremum (max) of exercised prices.
    itm_at_T = payoff[:, -1] > 0
    if itm_at_T.any():
        exercise_boundary[-1] = (
            paths[itm_at_T, -1].min() if option_type == "call" else paths[itm_at_T, -1].max()
        )

    for t in range(n_steps - 1, 0, -1):
        itm = payoff[:, t] > 0
        if not itm.any():
            continue

        S_itm = paths[itm, t]
        # discount already-realized future cashflows back to time t
        periods_ahead = exercise_time[itm] - t
        Y = cashflow[itm] * disc ** periods_ahead

        X = np.column_stack([S_itm ** d for d in range(degree + 1)])
        coeffs, *_ = np.linalg.lstsq(X, Y, rcond=None)
        continuation = X @ coeffs

        immediate = payoff[itm, t]
        exercise_now = immediate > continuation

        idx_itm = np.where(itm)[0]
        idx_exercise = idx_itm[exercise_now]

        if idx_exercise.size:
            cashflow[idx_exercise] = immediate[exercise_now]
            exercise_time[idx_exercise] = t
            ex_prices = paths[idx_exercise, t]
            exercise_boundary[t] = (
                ex_prices.min() if option_type == "call" else ex_prices.max()
            )

    discounted = cashflow * disc ** exercise_time
    price = float(discounted.mean())
    std_error = float(discounted.std(ddof=1) / np.sqrt(n_paths))
    return LSMResult(price=price, std_error=std_error, exercise_boundary=exercise_boundary)
