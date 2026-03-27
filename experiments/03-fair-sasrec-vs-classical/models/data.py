from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class SequenceData:
    user_train: Dict[int, List[int]]
    user_val: Dict[int, int]
    user_test: Dict[int, int]
    num_users: int
    num_items: int


def _parse_ratings(path: Path) -> List[Tuple[str, str, int]]:
    rows: List[Tuple[str, str, int]] = []
    with path.open("r", encoding="latin-1") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            user_raw, item_raw, _rating, ts = line.split("::")
            rows.append((user_raw, item_raw, int(ts)))
    return rows


def load_movielens_1m(data_dir: Path, min_user_interactions: int = 5, min_item_interactions: int = 5) -> SequenceData:
    ratings_path = data_dir / "ratings.dat"
    if not ratings_path.exists():
        raise FileNotFoundError(
            f"Could not find MovieLens-1M ratings file at {ratings_path}. "
            "Place ratings.dat inside the provided --data-dir."
        )

    rows = _parse_ratings(ratings_path)

    user_count: Dict[str, int] = {}
    item_count: Dict[str, int] = {}
    for user_raw, item_raw, _ts in rows:
        user_count[user_raw] = user_count.get(user_raw, 0) + 1
        item_count[item_raw] = item_count.get(item_raw, 0) + 1

    filtered = [
        (u, i, ts)
        for (u, i, ts) in rows
        if user_count.get(u, 0) >= min_user_interactions and item_count.get(i, 0) >= min_item_interactions
    ]

    user_map: Dict[str, int] = {}
    item_map: Dict[str, int] = {}
    user_events: Dict[int, List[Tuple[int, int]]] = {}

    for user_raw, item_raw, ts in filtered:
        if user_raw not in user_map:
            user_map[user_raw] = len(user_map) + 1
        if item_raw not in item_map:
            item_map[item_raw] = len(item_map) + 1
        user_id = user_map[user_raw]
        item_id = item_map[item_raw]
        user_events.setdefault(user_id, []).append((ts, item_id))

    user_train: Dict[int, List[int]] = {}
    user_val: Dict[int, int] = {}
    user_test: Dict[int, int] = {}

    for user_id, events in user_events.items():
        events.sort(key=lambda x: x[0])
        seq = [item for _ts, item in events]
        if len(seq) < 3:
            continue
        user_train[user_id] = seq[:-2]
        user_val[user_id] = seq[-2]
        user_test[user_id] = seq[-1]

    if not user_train:
        raise ValueError("No valid users after filtering and splitting.")

    return SequenceData(
        user_train=user_train,
        user_val=user_val,
        user_test=user_test,
        num_users=max(user_train.keys()),
        num_items=max(item_map.values()) if item_map else 0,
    )


def build_eval_candidates(
    positives: Dict[int, int],
    user_seen: Dict[int, List[int]],
    num_items: int,
    num_negatives: int,
    seed: int,
) -> Dict[int, np.ndarray]:
    rng = np.random.default_rng(seed)
    candidates: Dict[int, np.ndarray] = {}
    all_items = np.arange(1, num_items + 1)

    for user_id, pos_item in positives.items():
        seen = set(user_seen[user_id])
        seen.add(pos_item)
        pool = np.array([x for x in all_items if x not in seen], dtype=np.int64)
        if len(pool) < num_negatives:
            sampled = pool
        else:
            sampled = rng.choice(pool, size=num_negatives, replace=False)
        cand = np.concatenate(([pos_item], sampled))
        candidates[user_id] = cand

    return candidates

