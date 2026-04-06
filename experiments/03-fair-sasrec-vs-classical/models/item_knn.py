from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class ItemKNNConfig:
    topk_neighbors: int = 200
    context_window: int = 10
    cooc_window: int = 10


class ItemKNN:
    def __init__(self, num_items: int, config: ItemKNNConfig) -> None:
        self.num_items = num_items
        self.config = config
        self.neighbors: Dict[int, Dict[int, float]] = {}

    def fit(self, user_train: Dict[int, List[int]]) -> None:
        cooc: Dict[int, Dict[int, float]] = {}
        pop = np.zeros(self.num_items + 1, dtype=np.float64)

        for seq in user_train.values():
            unique_items = set(seq)
            for i in unique_items:
                pop[i] += 1.0
            # Windowed co-occurrence is much cheaper than full pairwise over a
            # user's entire set and better reflects short-range sequential signal.
            for idx, center in enumerate(seq):
                row = cooc.setdefault(center, {})
                left = max(0, idx - self.config.cooc_window)
                right = min(len(seq), idx + self.config.cooc_window + 1)
                for j in range(left, right):
                    if j == idx:
                        continue
                    nbr = seq[j]
                    if nbr == center:
                        continue
                    row[nbr] = row.get(nbr, 0.0) + 1.0

        for i, row in cooc.items():
            sims: List[tuple[int, float]] = []
            denom_i = np.sqrt(pop[i]) if pop[i] > 0 else 1.0
            for j, cij in row.items():
                denom_j = np.sqrt(pop[j]) if pop[j] > 0 else 1.0
                sims.append((j, float(cij / (denom_i * denom_j + 1e-8))))
            sims.sort(key=lambda x: -x[1])
            self.neighbors[i] = dict(sims[: self.config.topk_neighbors])

    def score(self, _user_id: int, context: List[int], candidates: np.ndarray) -> np.ndarray:
        hist = context[-self.config.context_window :]
        weights = np.linspace(1.0, 2.0, num=max(1, len(hist)))
        scores = np.zeros(len(candidates), dtype=np.float64)

        for idx, item in enumerate(candidates):
            s = 0.0
            for w, h in zip(weights, hist):
                s += w * self.neighbors.get(h, {}).get(int(item), 0.0)
            scores[idx] = s
        return scores

