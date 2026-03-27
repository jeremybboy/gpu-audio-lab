from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import torch


@dataclass
class BPRMFConfig:
    dim: int = 64
    lr: float = 1e-3
    weight_decay: float = 1e-6
    epochs: int = 30
    batch_size: int = 2048
    samples_per_epoch: int = 200_000


class BPRMF(torch.nn.Module):
    def __init__(self, num_users: int, num_items: int, config: BPRMFConfig, device: torch.device) -> None:
        super().__init__()
        self.num_users = num_users
        self.num_items = num_items
        self.config = config
        self.device = device

        self.user_emb = torch.nn.Embedding(num_users + 1, config.dim, padding_idx=0)
        self.item_emb = torch.nn.Embedding(num_items + 1, config.dim, padding_idx=0)
        torch.nn.init.normal_(self.user_emb.weight, std=0.02)
        torch.nn.init.normal_(self.item_emb.weight, std=0.02)
        self.to(device)

    def _sample_batch(self, user_pos: Dict[int, List[int]], user_pos_set: Dict[int, set[int]], rng: np.random.Generator) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        users = rng.integers(1, self.num_users + 1, size=self.config.batch_size)
        pos_items = np.zeros(self.config.batch_size, dtype=np.int64)
        neg_items = np.zeros(self.config.batch_size, dtype=np.int64)
        for i, u in enumerate(users):
            pos = int(rng.choice(user_pos[int(u)]))
            pos_items[i] = pos
            n = int(rng.integers(1, self.num_items + 1))
            while n in user_pos_set[int(u)]:
                n = int(rng.integers(1, self.num_items + 1))
            neg_items[i] = n
        return (
            torch.from_numpy(users.astype(np.int64)).to(self.device),
            torch.from_numpy(pos_items).to(self.device),
            torch.from_numpy(neg_items).to(self.device),
        )

    def fit(
        self,
        user_train: Dict[int, List[int]],
        val_eval_fn,
        seed: int,
        patience: int,
        progress_label: str = "BPRMF",
    ) -> Tuple[float, float]:
        optimizer = torch.optim.Adam(self.parameters(), lr=self.config.lr, weight_decay=self.config.weight_decay)
        user_pos = {u: list(set(seq)) for u, seq in user_train.items()}
        user_pos_set = {u: set(items) for u, items in user_pos.items()}
        rng = np.random.default_rng(seed)
        steps_per_epoch = max(1, self.config.samples_per_epoch // self.config.batch_size)

        best_score = -1.0
        best_state = None
        bad_epochs = 0
        t0 = time.perf_counter()

        for epoch_idx in range(self.config.epochs):
            epoch_t0 = time.perf_counter()
            self.train()
            for _ in range(steps_per_epoch):
                u, i_pos, i_neg = self._sample_batch(user_pos, user_pos_set, rng)
                pu = self.user_emb(u)
                qi = self.item_emb(i_pos)
                qj = self.item_emb(i_neg)
                x = torch.sum(pu * (qi - qj), dim=-1)
                loss = -torch.log(torch.sigmoid(x) + 1e-8).mean()
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            self.eval()
            val = val_eval_fn()
            score = val["ndcg@10"]
            elapsed = time.perf_counter() - t0
            epoch_seconds = time.perf_counter() - epoch_t0
            avg_epoch = elapsed / float(epoch_idx + 1)
            eta_seconds = max(0.0, avg_epoch * (self.config.epochs - epoch_idx - 1))
            print(
                f"[{progress_label}] epoch {epoch_idx + 1}/{self.config.epochs} "
                f"val_ndcg@10={score:.4f} best={max(best_score, score):.4f} "
                f"epoch={epoch_seconds:.1f}s elapsed={elapsed:.1f}s eta~{eta_seconds:.1f}s"
            )
            if score > best_score:
                best_score = score
                best_state = {k: v.detach().cpu().clone() for k, v in self.state_dict().items()}
                bad_epochs = 0
            else:
                bad_epochs += 1
                if bad_epochs >= patience:
                    print(f"[{progress_label}] early stop after {epoch_idx + 1} epochs (patience={patience}).")
                    break

        if best_state is not None:
            self.load_state_dict(best_state)
        train_seconds = time.perf_counter() - t0
        return best_score, train_seconds

    @torch.no_grad()
    def score(self, user_id: int, _context: List[int], candidates: np.ndarray) -> np.ndarray:
        u = torch.tensor([user_id], dtype=torch.long, device=self.device)
        cand = torch.from_numpy(candidates.astype(np.int64)).to(self.device)
        pu = self.user_emb(u)
        qi = self.item_emb(cand)
        scores = torch.matmul(qi, pu.squeeze(0))
        return scores.detach().cpu().numpy()

