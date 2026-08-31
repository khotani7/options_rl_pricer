"""
Global configuration and the mid/high-cap ticker universe for the
self-training American options pricer.

Market-cap buckets follow the common convention:
    mid cap  : $2B  - $10B
    high cap : $10B - $200B  (large cap)
    mega cap : > $200B (still tagged "high" for our purposes)
"""

from dataclasses import dataclass, field

MID_CAP_MIN = 2e9
MID_CAP_MAX = 10e9
HIGH_CAP_MAX = 200e9  # above this we just call it "mega" but bucket as "high"


def classify_cap(market_cap: float) -> str:
    if market_cap is None:
        return "unknown"
    if market_cap < MID_CAP_MIN:
        return "small_or_micro"
    if market_cap <= MID_CAP_MAX:
        return "mid"
    return "high"  # covers large + mega


# A default mid/high-cap universe with liquid listed options.
# These are just sensible starting points -- fetch_market_params() will
# pull live data (or fall back to the bundled calibration cache) for
# whichever ticker is actually requested.
DEFAULT_UNIVERSE = {
    "high": ["AAPL", "MSFT", "JPM", "V", "XOM"],
    "mid": ["DECK", "RPM", "TTC", "FUN", "WING"],
}


@dataclass
class RunConfig:
    ticker: str = "DECK"
    option_type: str = "put"          # "put" or "call"
    moneyness: float = 1.0            # strike = moneyness * spot (1.0 = ATM)
    maturity_years: float = 0.5       # time to expiry in years
    n_steps: int = 50                 # exercise opportunities (time discretization)

    # Monte Carlo / self-training sizes
    # (350 epochs / 2000 paths-per-epoch was empirically the sweet spot in
    # testing: enough self-play episodes for the DQN price estimate to
    # climb to within ~5-6% of the Longstaff-Schwartz benchmark in ~80s
    # on CPU. Fewer epochs (e.g. 150) leave it visibly under-converged.)
    train_paths_per_epoch: int = 2000
    n_epochs: int = 350
    eval_paths: int = 20000
    lsm_paths: int = 20000

    # DQN hyperparameters
    gamma: float = None               # set to exp(-r*dt) at runtime
    lr: float = 5e-4
    hidden_dim: int = 32
    batch_size: int = 512
    replay_capacity: int = 200_000
    updates_per_epoch: int = 25
    target_sync_every: int = 10       # epochs
    eps_start: float = 1.0
    eps_end: float = 0.05
    eps_decay_epochs: int = 100  # note: main.py's --quick flag overrides several of these

    seed: int = 42
    output_dir: str = "outputs"
