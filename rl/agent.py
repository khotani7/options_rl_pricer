"""
Deep Q-Network agent that learns the optimal exercise policy.

The Q-network maps a state (moneyness, time-remaining, intrinsic-value
fraction) to two Q-values: Q(hold) and Q(exercise). Training uses the
standard DQN machinery (replay buffer, target network, epsilon-greedy
exploration) with discount factor gamma = exp(-r * dt), so that a
converged Q-value for "exercise" exactly equals the risk-neutral
discounted expected payoff -- i.e. the agent is trained to approximate
the American option's value function directly.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class QNetwork(nn.Module):
    def __init__(self, state_dim: int = 3, n_actions: int = 2, hidden_dim: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, n_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


@dataclass
class Transition:
    state: np.ndarray
    action: np.ndarray
    reward: np.ndarray
    next_state: np.ndarray
    done: np.ndarray


class ReplayBuffer:
    def __init__(self, capacity: int):
        self.buffer = deque(maxlen=capacity)

    def push_batch(self, state, action, reward, next_state, done):
        for i in range(state.shape[0]):
            self.buffer.append((state[i], action[i], reward[i], next_state[i], done[i]))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        state, action, reward, next_state, done = zip(*batch)
        return (
            np.array(state, dtype=np.float32),
            np.array(action, dtype=np.int64),
            np.array(reward, dtype=np.float32),
            np.array(next_state, dtype=np.float32),
            np.array(done, dtype=np.float32),
        )

    def __len__(self):
        return len(self.buffer)


class DQNAgent:
    def __init__(self, state_dim=3, n_actions=2, hidden_dim=32, lr=1e-3,
                 gamma=0.999, device: str | None = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.gamma = gamma
        self.n_actions = n_actions

        self.q_net = QNetwork(state_dim, n_actions, hidden_dim).to(self.device)
        self.target_net = QNetwork(state_dim, n_actions, hidden_dim).to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())
        self.target_net.eval()

        self.optimizer = torch.optim.Adam(self.q_net.parameters(), lr=lr)

    def act(self, obs: np.ndarray, epsilon: float, active_mask: np.ndarray | None = None) -> np.ndarray:
        """Epsilon-greedy batched action selection. Forces action=0 (hold)
        wherever active_mask is False (episode already finished for that path)."""
        n = obs.shape[0]
        with torch.no_grad():
            q = self.q_net(torch.from_numpy(obs).to(self.device))
            greedy = q.argmax(dim=1).cpu().numpy()

        explore = np.random.rand(n) < epsilon
        random_actions = np.random.randint(0, self.n_actions, size=n)
        actions = np.where(explore, random_actions, greedy)

        if active_mask is not None:
            actions = np.where(active_mask, actions, 0)
        return actions.astype(np.int64)

    def greedy_action(self, obs: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            q = self.q_net(torch.from_numpy(obs).to(self.device))
            return q.argmax(dim=1).cpu().numpy()

    def q_values(self, obs: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            return self.q_net(torch.from_numpy(obs).to(self.device)).cpu().numpy()

    def update(self, buffer: ReplayBuffer, batch_size: int) -> float:
        if len(buffer) < batch_size:
            return float("nan")

        state, action, reward, next_state, done = buffer.sample(batch_size)
        state = torch.from_numpy(state).to(self.device)
        action = torch.from_numpy(action).to(self.device)
        reward = torch.from_numpy(reward).to(self.device)
        next_state = torch.from_numpy(next_state).to(self.device)
        done = torch.from_numpy(done).to(self.device)

        q_sa = self.q_net(state).gather(1, action.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            # Double DQN: select the next action with the online network,
            # evaluate it with the target network. Plain DQN's max-over-target
            # tends to overestimate Q-values here and made training visibly
            # unstable (price estimates oscillating instead of converging).
            next_action = self.q_net(next_state).argmax(dim=1)
            next_q = self.target_net(next_state).gather(1, next_action.unsqueeze(1)).squeeze(1)
            target = reward + self.gamma * (1.0 - done) * next_q

        loss = F.smooth_l1_loss(q_sa, target)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_net.parameters(), max_norm=5.0)
        self.optimizer.step()

        return float(loss.item())

    def sync_target(self):
        self.target_net.load_state_dict(self.q_net.state_dict())

    def save(self, path: str):
        torch.save(self.q_net.state_dict(), path)

    def load(self, path: str):
        state_dict = torch.load(path, map_location=self.device)
        self.q_net.load_state_dict(state_dict)
        self.target_net.load_state_dict(state_dict)
