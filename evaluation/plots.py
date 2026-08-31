"""Plotting utilities: training convergence, exercise boundary, and a
final price-comparison summary chart."""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_convergence(history: dict, lsm_price: float, out_path: str):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))

    ax1.plot(history["epoch"], history["price_estimate"], label="RL price estimate (epsilon-greedy)")
    ax1.axhline(lsm_price, color="firebrick", linestyle="--", label=f"Longstaff-Schwartz benchmark = {lsm_price:.4f}")
    ax1.set_xlabel("self-training epoch")
    ax1.set_ylabel("price estimate")
    ax1.set_title("RL price convergence vs. LSM benchmark")
    ax1.legend(fontsize=8)

    ax2.plot(history["epoch"], history["loss"], color="darkorange")
    ax2.set_xlabel("self-training epoch")
    ax2.set_ylabel("mean TD loss (smooth L1)")
    ax2.set_title("DQN training loss")

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_exercise_boundary(rl_boundary: np.ndarray, lsm_boundary: np.ndarray, K: float,
                            n_steps: int, T: float, out_path: str):
    t_axis = np.linspace(0, T, n_steps + 1)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(t_axis, lsm_boundary, "o-", color="firebrick", ms=3, label="Longstaff-Schwartz")
    ax.plot(t_axis, rl_boundary, "o-", color="steelblue", ms=3, label="RL (DQN) policy")
    ax.axhline(K, color="gray", linestyle=":", label=f"Strike K = {K:.2f}")
    ax.set_xlabel("time (years)")
    ax.set_ylabel("underlying price at exercise")
    ax.set_title("Early-exercise boundary: RL policy vs. LSM benchmark")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_price_comparison(prices: dict, errors: dict, out_path: str):
    labels = list(prices.keys())
    values = [prices[k] for k in labels]
    errs = [errors.get(k, 0.0) for k in labels]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bars = ax.bar(labels, values, yerr=errs, capsize=4,
                   color=["steelblue", "firebrick", "seagreen", "goldenrod"][:len(labels)])
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("option price ($)")
    ax.set_title("Price comparison")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
