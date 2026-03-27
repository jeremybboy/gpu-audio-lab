from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import torch


@dataclass
class SASRecConfig:
    dim: int = 64
    num_heads: int = 2
    num_layers: int = 2
    dropout: float = 0.2
    max_len: int = 50
    lr: float = 1e-3
    weight_decay: float = 1e-6
    epochs: int = 30
    batch_size: int = 512


class SASRecSmall(torch.nn.Module):
    def __init__(self, num_items: int, config: SASRecConfig, device: torch.device) -> None:
        super().__init__()
        self.num_items = num_items
        self.config = config
        self.device = device
        self.item_emb = torch.nn.Embedding(num_items + 1, config.dim, padding_idx=0)
        self.pos_emb = torch.nn.Embedding(config.max_len, config.dim)
        encoder_layer = torch.nn.TransformerEncoderLayer(
            d_model=config.dim,
            nhead=config.num_heads,
            dim_feedforward=config.dim * 4,
            dropout=config.dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = torch.nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)
        self.norm = torch.nn.LayerNorm(config.dim)
        self.to(device)

    def _build_training_samples(self, user_train: Dict[int, List[int]]) -> List[Tuple[List[int], int]]:
        samples: List[Tuple[List[int], int]] = []
        for seq in user_train.values():
            for t in range(1, len(seq)):
                context = seq[max(0, t - self.config.max_len) : t]
                target = seq[t]
                samples.append((context, target))
        return samples

    def _batch_tensors(self, batch: List[Tuple[List[int], int]], rng: np.random.Generator) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        bs = len(batch)
        seqs = np.zeros((bs, self.config.max_len), dtype=np.int64)
        pos = np.zeros(bs, dtype=np.int64)
        neg = rng.integers(1, self.num_items + 1, size=bs, dtype=np.int64)
        for i, (ctx, target) in enumerate(batch):
            tail = ctx[-self.config.max_len :]
            seqs[i, -len(tail) :] = np.array(tail, dtype=np.int64)
            pos[i] = target
        return (
            torch.from_numpy(seqs).to(self.device),
            torch.from_numpy(pos).to(self.device),
            torch.from_numpy(neg).to(self.device),
        )

    def _encode(self, seq: torch.Tensor) -> torch.Tensor:
        bsz, slen = seq.shape
        pos_idx = torch.arange(slen, device=self.device).unsqueeze(0).expand(bsz, slen)
        x = self.item_emb(seq) + self.pos_emb(pos_idx)

        # True means masked in PyTorch transformer masks.
        causal = torch.triu(torch.ones((slen, slen), device=self.device, dtype=torch.bool), diagonal=1)
        padding = seq.eq(0)
        h = self.encoder(x, mask=causal, src_key_padding_mask=padding)
        h = self.norm(h)

        lengths = torch.clamp((~padding).sum(dim=1), min=1)
        last_idx = lengths - 1
        out = h[torch.arange(bsz, device=self.device), last_idx]
        return out

    def fit(
        self,
        user_train: Dict[int, List[int]],
        val_eval_fn,
        seed: int,
        patience: int,
        progress_label: str = "SASRec",
    ) -> Tuple[float, float]:
        optimizer = torch.optim.Adam(self.parameters(), lr=self.config.lr, weight_decay=self.config.weight_decay)
        rng = np.random.default_rng(seed)
        samples = self._build_training_samples(user_train)
        best_score = -1.0
        best_state = None
        bad_epochs = 0
        t0 = time.perf_counter()

        if not samples:
            return 0.0, 0.0

        for epoch_idx in range(self.config.epochs):
            epoch_t0 = time.perf_counter()
            rng.shuffle(samples)
            self.train()
            for start in range(0, len(samples), self.config.batch_size):
                batch = samples[start : start + self.config.batch_size]
                seq, pos, neg = self._batch_tensors(batch, rng)
                h = self._encode(seq)
                pos_emb = self.item_emb(pos)
                neg_emb = self.item_emb(neg)
                pos_logits = torch.sum(h * pos_emb, dim=-1)
                neg_logits = torch.sum(h * neg_emb, dim=-1)
                loss = -torch.log(torch.sigmoid(pos_logits) + 1e-8).mean()
                loss += -torch.log(1.0 - torch.sigmoid(neg_logits) + 1e-8).mean()
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
        seq = np.zeros((1, self.config.max_len), dtype=np.int64)
        tail = context[-self.config.max_len :]
        seq[0, -len(tail) :] = np.array(tail, dtype=np.int64)
        seq_t = torch.from_numpy(seq).to(self.device)
        h = self._encode(seq_t).squeeze(0)
        cand_t = torch.from_numpy(candidates.astype(np.int64)).to(self.device)
        emb = self.item_emb(cand_t)
        scores = torch.matmul(emb, h)
        return scores.detach().cpu().numpy()

