"""
Fair local benchmark: SASRec-small vs strong classical recommenders on ML-1M.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch

from models.bpr_mf import BPRMF, BPRMFConfig
from models.data import SequenceData, build_eval_candidates, load_movielens_1m
from models.eval import evaluate_next_item
from models.fmc import FMC, FMCConfig
from models.item_knn import ItemKNN, ItemKNNConfig
from models.sasrec_small import SASRecConfig, SASRecSmall


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_eval_contexts(data: SequenceData) -> Tuple[Dict[int, List[int]], Dict[int, List[int]]]:
    val_contexts = {u: list(seq) for u, seq in data.user_train.items()}
    test_contexts = {u: list(seq) + [data.user_val[u]] for u, seq in data.user_train.items()}
    return val_contexts, test_contexts


def timed_eval(users: List[int], contexts: Dict[int, List[int]], candidates: Dict[int, np.ndarray], scorer_fn):
    t0 = time.perf_counter()
    metrics = evaluate_next_item(users, contexts, candidates, scorer_fn, k=10)
    elapsed = time.perf_counter() - t0
    return metrics, elapsed


def run_itemknn(
    data: SequenceData,
    val_users: List[int],
    test_users: List[int],
    val_contexts: Dict[int, List[int]],
    test_contexts: Dict[int, List[int]],
    val_candidates: Dict[int, np.ndarray],
    test_candidates: Dict[int, np.ndarray],
    trials: int,
    patience: int,
    seed: int,
):
    # Kept for API uniformity; ItemKNN does not use epoch-based early stopping.
    _ = patience
    rng = np.random.default_rng(seed)
    search_space = {
        "topk_neighbors": [50, 100, 200, 400],
        "context_window": [3, 5, 10, 20],
    }
    best = None
    best_cfg = None
    best_train_seconds = None

    for trial_idx in range(trials):
        cfg = ItemKNNConfig(
            topk_neighbors=int(rng.choice(search_space["topk_neighbors"])),
            context_window=int(rng.choice(search_space["context_window"])),
        )
        print(
            f"[ItemKNN] trial {trial_idx + 1}/{trials} "
            f"topk_neighbors={cfg.topk_neighbors} context_window={cfg.context_window}"
        )
        model = ItemKNN(num_items=data.num_items, config=cfg)
        t0 = time.perf_counter()
        model.fit(data.user_train)
        train_seconds = time.perf_counter() - t0
        val_metrics, _ = timed_eval(val_users, val_contexts, val_candidates, model.score)
        print(
            f"[ItemKNN] trial {trial_idx + 1}/{trials} "
            f"val_hit@10={val_metrics['hit@10']:.4f} val_ndcg@10={val_metrics['ndcg@10']:.4f} "
            f"train={train_seconds:.1f}s"
        )
        if best is None or val_metrics["ndcg@10"] > best["ndcg@10"]:
            best = val_metrics
            best_cfg = cfg
            best_model = model
            best_train_seconds = train_seconds

    test_metrics, infer_seconds = timed_eval(test_users, test_contexts, test_candidates, best_model.score)
    return best_cfg, best, test_metrics, best_train_seconds, infer_seconds


def run_bprmf(
    data: SequenceData,
    val_users: List[int],
    test_users: List[int],
    val_contexts: Dict[int, List[int]],
    test_contexts: Dict[int, List[int]],
    val_candidates: Dict[int, np.ndarray],
    test_candidates: Dict[int, np.ndarray],
    trials: int,
    patience: int,
    seed: int,
    device: torch.device,
):
    rng = np.random.default_rng(seed)
    search_space = {
        "dim": [32, 64, 96],
        "lr": [1e-3, 5e-4],
        "weight_decay": [1e-6, 1e-5, 1e-4],
    }

    best_cfg = None
    best_val = None
    best_state = None
    best_train_seconds = None

    for trial_idx in range(trials):
        cfg = BPRMFConfig(
            dim=int(rng.choice(search_space["dim"])),
            lr=float(rng.choice(search_space["lr"])),
            weight_decay=float(rng.choice(search_space["weight_decay"])),
            epochs=30,
            batch_size=2048,
            samples_per_epoch=200_000,
        )
        model = BPRMF(data.num_users, data.num_items, cfg, device)

        def val_eval():
            return evaluate_next_item(val_users, val_contexts, val_candidates, model.score, k=10)

        print(f"[BPRMF] trial {trial_idx + 1}/{trials} cfg={asdict(cfg)}")
        val_best, train_seconds = model.fit(
            data.user_train,
            val_eval,
            seed + trial_idx * 1000,
            patience,
            progress_label=f"BPRMF t{trial_idx + 1}/{trials}",
        )
        print(f"[BPRMF] trial {trial_idx + 1}/{trials} done best_val_ndcg@10={val_best:.4f} train={train_seconds:.1f}s")
        if best_val is None or val_best > best_val:
            best_val = val_best
            best_cfg = cfg
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_train_seconds = train_seconds

    best_model = BPRMF(data.num_users, data.num_items, best_cfg, device)
    best_model.load_state_dict(best_state)
    val_metrics = evaluate_next_item(val_users, val_contexts, val_candidates, best_model.score, k=10)
    test_metrics, infer_seconds = timed_eval(test_users, test_contexts, test_candidates, best_model.score)
    return best_cfg, val_metrics, test_metrics, best_train_seconds, infer_seconds


def run_fmc(
    data: SequenceData,
    val_users: List[int],
    test_users: List[int],
    val_contexts: Dict[int, List[int]],
    test_contexts: Dict[int, List[int]],
    val_candidates: Dict[int, np.ndarray],
    test_candidates: Dict[int, np.ndarray],
    trials: int,
    patience: int,
    seed: int,
    device: torch.device,
):
    rng = np.random.default_rng(seed)
    search_space = {
        "dim": [32, 64, 96],
        "lr": [1e-3, 5e-4],
        "weight_decay": [1e-6, 1e-5, 1e-4],
    }

    best_cfg = None
    best_val = None
    best_state = None
    best_train_seconds = None

    for trial_idx in range(trials):
        cfg = FMCConfig(
            dim=int(rng.choice(search_space["dim"])),
            lr=float(rng.choice(search_space["lr"])),
            weight_decay=float(rng.choice(search_space["weight_decay"])),
            epochs=30,
            batch_size=4096,
        )
        model = FMC(data.num_items, cfg, device)

        def val_eval():
            return evaluate_next_item(val_users, val_contexts, val_candidates, model.score, k=10)

        print(f"[FMC] trial {trial_idx + 1}/{trials} cfg={asdict(cfg)}")
        val_best, train_seconds = model.fit(
            data.user_train,
            val_eval,
            seed + trial_idx * 1000,
            patience,
            progress_label=f"FMC t{trial_idx + 1}/{trials}",
        )
        print(f"[FMC] trial {trial_idx + 1}/{trials} done best_val_ndcg@10={val_best:.4f} train={train_seconds:.1f}s")
        if best_val is None or val_best > best_val:
            best_val = val_best
            best_cfg = cfg
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_train_seconds = train_seconds

    best_model = FMC(data.num_items, best_cfg, device)
    best_model.load_state_dict(best_state)
    val_metrics = evaluate_next_item(val_users, val_contexts, val_candidates, best_model.score, k=10)
    test_metrics, infer_seconds = timed_eval(test_users, test_contexts, test_candidates, best_model.score)
    return best_cfg, val_metrics, test_metrics, best_train_seconds, infer_seconds


def run_sasrec(
    data: SequenceData,
    val_users: List[int],
    test_users: List[int],
    val_contexts: Dict[int, List[int]],
    test_contexts: Dict[int, List[int]],
    val_candidates: Dict[int, np.ndarray],
    test_candidates: Dict[int, np.ndarray],
    trials: int,
    patience: int,
    seed: int,
    device: torch.device,
):
    rng = np.random.default_rng(seed)
    search_space = {
        "dim": [32, 64],
        "num_heads": [1, 2],
        "num_layers": [1, 2],
        "dropout": [0.2, 0.5],
        "max_len": [50, 100],
        "lr": [1e-3, 5e-4],
    }

    best_cfg = None
    best_val = None
    best_state = None
    best_train_seconds = None

    for trial_idx in range(trials):
        dim = int(rng.choice(search_space["dim"]))
        head_candidates = [h for h in search_space["num_heads"] if dim % h == 0]
        cfg = SASRecConfig(
            dim=dim,
            num_heads=int(rng.choice(head_candidates)),
            num_layers=int(rng.choice(search_space["num_layers"])),
            dropout=float(rng.choice(search_space["dropout"])),
            max_len=int(rng.choice(search_space["max_len"])),
            lr=float(rng.choice(search_space["lr"])),
            weight_decay=1e-6,
            epochs=30,
            batch_size=512,
        )
        model = SASRecSmall(data.num_items, cfg, device)

        def val_eval():
            return evaluate_next_item(val_users, val_contexts, val_candidates, model.score, k=10)

        print(f"[SASRec] trial {trial_idx + 1}/{trials} cfg={asdict(cfg)}")
        val_best, train_seconds = model.fit(
            data.user_train,
            val_eval,
            seed + trial_idx * 1000,
            patience,
            progress_label=f"SASRec t{trial_idx + 1}/{trials}",
        )
        print(f"[SASRec] trial {trial_idx + 1}/{trials} done best_val_ndcg@10={val_best:.4f} train={train_seconds:.1f}s")
        if best_val is None or val_best > best_val:
            best_val = val_best
            best_cfg = cfg
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_train_seconds = train_seconds

    best_model = SASRecSmall(data.num_items, best_cfg, device)
    best_model.load_state_dict(best_state)
    val_metrics = evaluate_next_item(val_users, val_contexts, val_candidates, best_model.score, k=10)
    test_metrics, infer_seconds = timed_eval(test_users, test_contexts, test_candidates, best_model.score)
    return best_cfg, val_metrics, test_metrics, best_train_seconds, infer_seconds


def aggregate(metric_rows: List[Dict[str, float]], key: str) -> Tuple[float, float]:
    vals = np.array([row[key] for row in metric_rows], dtype=np.float64)
    return float(vals.mean()), float(vals.std(ddof=0))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fair SASRec vs classical benchmark on MovieLens-1M.")
    parser.add_argument("--data-dir", type=str, required=True, help="Path containing ratings.dat.")
    parser.add_argument("--results-dir", type=str, default="experiments/03-fair-sasrec-vs-classical/results")
    parser.add_argument("--num-negatives", type=int, default=100)
    parser.add_argument("--max-trials", type=int, default=4)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--seeds", type=int, nargs="+", default=[13, 37, 97])
    args = parser.parse_args()

    data = load_movielens_1m(Path(args.data_dir))
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded users={len(data.user_train)} items={data.num_items}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    val_contexts, test_contexts = make_eval_contexts(data)
    eval_users = sorted(data.user_train.keys())

    metrics_by_model: Dict[str, List[Dict[str, float]]] = {m: [] for m in ["itemknn", "bprmf", "fmc", "sasrec_small"]}
    runtime_by_model: Dict[str, List[Dict[str, float]]] = {m: [] for m in ["itemknn", "bprmf", "fmc", "sasrec_small"]}
    best_configs: Dict[str, Dict[str, object]] = {}

    for seed in args.seeds:
        print(f"\n=== Seed {seed} ===")
        set_seed(seed)

        val_candidates = build_eval_candidates(
            positives=data.user_val,
            user_seen=val_contexts,
            num_items=data.num_items,
            num_negatives=args.num_negatives,
            seed=seed + 100,
        )
        test_candidates = build_eval_candidates(
            positives=data.user_test,
            user_seen=test_contexts,
            num_items=data.num_items,
            num_negatives=args.num_negatives,
            seed=seed + 200,
        )

        item_cfg, item_val, item_test, item_train_sec, item_infer_sec = run_itemknn(
            data,
            eval_users,
            eval_users,
            val_contexts,
            test_contexts,
            val_candidates,
            test_candidates,
            args.max_trials,
            args.patience,
            seed,
        )
        print(f"ItemKNN test hit@10={item_test['hit@10']:.4f} ndcg@10={item_test['ndcg@10']:.4f}")
        metrics_by_model["itemknn"].append(item_test)
        runtime_by_model["itemknn"].append({"train_seconds": item_train_sec, "infer_seconds": item_infer_sec})
        best_configs.setdefault("itemknn", asdict(item_cfg))

        bpr_cfg, bpr_val, bpr_test, bpr_train_sec, bpr_infer_sec = run_bprmf(
            data,
            eval_users,
            eval_users,
            val_contexts,
            test_contexts,
            val_candidates,
            test_candidates,
            args.max_trials,
            args.patience,
            seed,
            device,
        )
        print(f"BPRMF   test hit@10={bpr_test['hit@10']:.4f} ndcg@10={bpr_test['ndcg@10']:.4f}")
        metrics_by_model["bprmf"].append(bpr_test)
        runtime_by_model["bprmf"].append({"train_seconds": bpr_train_sec, "infer_seconds": bpr_infer_sec})
        best_configs.setdefault("bprmf", asdict(bpr_cfg))

        fmc_cfg, fmc_val, fmc_test, fmc_train_sec, fmc_infer_sec = run_fmc(
            data,
            eval_users,
            eval_users,
            val_contexts,
            test_contexts,
            val_candidates,
            test_candidates,
            args.max_trials,
            args.patience,
            seed,
            device,
        )
        print(f"FMC     test hit@10={fmc_test['hit@10']:.4f} ndcg@10={fmc_test['ndcg@10']:.4f}")
        metrics_by_model["fmc"].append(fmc_test)
        runtime_by_model["fmc"].append({"train_seconds": fmc_train_sec, "infer_seconds": fmc_infer_sec})
        best_configs.setdefault("fmc", asdict(fmc_cfg))

        sas_cfg, sas_val, sas_test, sas_train_sec, sas_infer_sec = run_sasrec(
            data,
            eval_users,
            eval_users,
            val_contexts,
            test_contexts,
            val_candidates,
            test_candidates,
            args.max_trials,
            args.patience,
            seed,
            device,
        )
        print(f"SASRec  test hit@10={sas_test['hit@10']:.4f} ndcg@10={sas_test['ndcg@10']:.4f}")
        metrics_by_model["sasrec_small"].append(sas_test)
        runtime_by_model["sasrec_small"].append({"train_seconds": sas_train_sec, "infer_seconds": sas_infer_sec})
        best_configs.setdefault("sasrec_small", asdict(sas_cfg))

    metrics_csv = results_dir / "metrics_summary.csv"
    with metrics_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "hit@10_mean", "hit@10_std", "ndcg@10_mean", "ndcg@10_std"])
        for model_name, rows in metrics_by_model.items():
            hit_mean, hit_std = aggregate(rows, "hit@10")
            ndcg_mean, ndcg_std = aggregate(rows, "ndcg@10")
            writer.writerow([model_name, f"{hit_mean:.6f}", f"{hit_std:.6f}", f"{ndcg_mean:.6f}", f"{ndcg_std:.6f}"])

    runtime_csv = results_dir / "runtime_summary.csv"
    with runtime_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "train_seconds_mean", "train_seconds_std", "infer_seconds_mean", "infer_seconds_std"])
        for model_name, rows in runtime_by_model.items():
            train_mean, train_std = aggregate(rows, "train_seconds")
            infer_mean, infer_std = aggregate(rows, "infer_seconds")
            writer.writerow([model_name, f"{train_mean:.6f}", f"{train_std:.6f}", f"{infer_mean:.6f}", f"{infer_std:.6f}"])

    with (results_dir / "best_configs.json").open("w", encoding="utf-8") as f:
        json.dump(best_configs, f, indent=2)

    # Build concise notes from summary means.
    summary = {}
    for model_name, rows in metrics_by_model.items():
        summary[model_name] = {
            "hit@10_mean": aggregate(rows, "hit@10")[0],
            "ndcg@10_mean": aggregate(rows, "ndcg@10")[0],
        }
    ranked = sorted(summary.items(), key=lambda x: x[1]["ndcg@10_mean"], reverse=True)
    best_name = ranked[0][0] if ranked else "n/a"

    notes = [
        "# Benchmark Notes",
        "",
        f"- Dataset: MovieLens-1M (`ratings.dat`).",
        f"- Seeds: {args.seeds}.",
        f"- Candidate protocol: 1 positive + {args.num_negatives} sampled negatives per user.",
        f"- Best mean NDCG@10: `{best_name}`.",
        "- Caveat: candidate-sampled ranking is standard but not full-catalog ranking.",
        "- Caveat: best configs are selected from a fixed, equal trial budget, not exhaustive search.",
    ]
    (results_dir / "notes.md").write_text("\n".join(notes), encoding="utf-8")

    print(f"\nWrote artifacts to: {results_dir}")


if __name__ == "__main__":
    main()

