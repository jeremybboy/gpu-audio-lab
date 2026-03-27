from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import torch


@dataclass
class FMCConfig:
    dim: int = 64
    lr: float = 1e-3
    weight_decay: float = 1e-6
    epochs: int = 30
    batch_size: int = 4096


class FMC(torch.nn.Module):
    def __init__(self, num_items: int, config: FMCConfig, device: torch.device) -> None:
        super().__init__()
        self.num_items = num_items
        self.config = config
        self.device = device
        self.item_in = torch.nn.Embedding(num_items + 1, config.dim, padding_idx=0)
        self.item_out = torch.nn.Embedding(num_items + 1, config.dim, padding_idx=0)
        torch.nn.init.normal_(self.item_in.weight, std=0.02)
        torch.nn.init.normal_(self.item_out.weight, std=0.02)
        self.to(device)

    def _build_pairs(self, user_train: Dict[int, List[int]]) -> List[Tuple[int, int]]:
        pairs: List[Tuple[int, int]] = []
        for seq in user_train.values():
            for i in range(len(seq) - 1):
                pairs.append((seq[i], seq[i + 1]))
        return pairs

    def fit(
        self,
        user_train: Dict[int, List[int]],
        val_eval_fn,
        seed: int,
        patience: int,
        progress_label: str = "FMC",
    ) -> Tuple[float, float]:
        optimizer = torch.optim.Adam(self.parameters(), lr=self.config.lr, weight_decay=self.config.weight_decay)
        pairs = self._build_pairs(user_train)
        rng = np.random.default_rng(seed)
        best_score = -1.0
        best_state = None
        bad_epochs = 0
        t0 = time.perf_counter()

        if not pairs:
            return 0.0, 0.0

        for epoch_idx in range(self.config.epochs):
            epoch_t0 = time.perf_counter()
            rng.shuffle(pairs)
            self.train()
            for start in range(0, len(pairs), self.config.batch_size):
                chunk = pairs[start : start + self.config.batch_size]
                prev = np.array([x[0] for x in chunk], dtype=np.int64)
                pos = np.array([x[1] for x in chunk], dtype=np.int64)
                neg = rng.integers(1, self.num_items + 1, size=len(chunk), dtype=np.int64)
                prev_t = torch.from_numpy(prev).to(self.device)
                pos_t = torch.from_numpy(pos).to(self.device)
                neg_t = torch.from_numpy(neg).to(self.device)
                h = self.item_in(prev_t)
                pos_v = self.item_out(pos_t)
                neg_v = self.item_out(neg_t)
                x = torch.sum(h * (pos_v - neg_v), dim=-1)
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
    def score(self, _user_id: int, context: List[int], candidates: np.ndarray) -> np.ndarray:
        if not context:
            return np.zeros(len(candidates), dtype=np.float64)
        prev_item = context[-1]
        prev_t = torch.tensor([prev_item], dtype=torch.long, device=self.device)
        cand_t = torch.from_numpy(candidates.astype(np.int64)).to(self.device)
        h = self.item_in(prev_t).squeeze(0)
        out = self.item_out(cand_t)
        scores = torch.matmul(out, h)
        return scores.detach().cpu().numpy()

