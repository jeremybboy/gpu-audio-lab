# 03-fair-sasrec-vs-classical

Local, fair benchmark of a small SASRec-style sequential recommender against
strong classical baselines on MovieLens-1M.

## Models

- `SASRecSmall`: causal self-attention sequence model.
- `BPRMF`: matrix factorization with BPR loss.
- `ItemKNN`: item-item cosine similarity collaborative filtering.
- `FMC`: first-order Markov factorization baseline.

## Fairness Protocol

- Same user-level train/validation/test split (`leave-last-two`).
- Same evaluation candidates for every model (1 positive + sampled negatives).
- Same metrics: `Hit@10` and `NDCG@10`.
- Same tuning budget per model (`max_trials`) and same early-stopping patience.
- Fixed seeds with mean/std reported across runs.

## Dataset

Download MovieLens-1M from:

- https://grouplens.org/datasets/movielens/1m/

Expected file:

- `ml-1m/ratings.dat` inside this experiment folder.

Final expected path:

- `experiments/03-fair-sasrec-vs-classical/ml-1m/ratings.dat`

## Run

From repository root:

```bash
python experiments/03-fair-sasrec-vs-classical/run_benchmark.py --data-dir experiments/03-fair-sasrec-vs-classical/ml-1m
```

Useful options:

```bash
python experiments/03-fair-sasrec-vs-classical/run_benchmark.py --help
```

## Outputs

Written under `experiments/03-fair-sasrec-vs-classical/results/`:

- `metrics_summary.csv`
- `best_configs.json`
- `runtime_summary.csv`
- `notes.md`

