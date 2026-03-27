from __future__ import annotations

from typing import Callable, Dict, List

import numpy as np


def ndcg_at_k(rank: int, k: int) -> float:
    if rank <= 0 or rank > k:
        return 0.0
    return 1.0 / np.log2(rank + 1.0)


def hit_at_k(rank: int, k: int) -> float:
    return 1.0 if 0 < rank <= k else 0.0


def evaluate_next_item(
    users: List[int],
    contexts: Dict[int, List[int]],
    candidates: Dict[int, np.ndarray],
    scorer: Callable[[int, List[int], np.ndarray], np.ndarray],
    k: int = 10,
) -> Dict[str, float]:
    hits: List[float] = []
    ndcgs: List[float] = []

    for user_id in users:
        cand = candidates[user_id]
        scores = scorer(user_id, contexts[user_id], cand)
        order = np.argsort(-scores)
        ranked_items = cand[order]
        pos_item = cand[0]
        rank = int(np.where(ranked_items == pos_item)[0][0]) + 1
        hits.append(hit_at_k(rank, k))
        ndcgs.append(ndcg_at_k(rank, k))

    return {
        "hit@10": float(np.mean(hits)) if hits else 0.0,
        "ndcg@10": float(np.mean(ndcgs)) if ndcgs else 0.0,
    }

