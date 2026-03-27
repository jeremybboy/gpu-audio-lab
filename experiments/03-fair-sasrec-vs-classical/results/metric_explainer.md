# Metric Explainer and Interpretation Guardrails

## What the metrics mean

- `Hit@10`: fraction of test cases where the true next item appears anywhere in the top 10 recommendations.
  - Example: `Hit@10 = 0.8584` means about 85.84% of cases had the true item in top 10.
- `NDCG@10`: rank-sensitive quality in top 10.
  - Higher if the true item is near rank 1, lower if it is near rank 10.
  - Useful when two models have similar Hit@10 but different ranking sharpness.

## How to read this benchmark correctly

- This experiment uses sampled-candidate evaluation:
  - 1 positive + `num_negatives` sampled negatives (not full-catalog ranking).
- Therefore, absolute values are less important than relative comparisons inside the exact same protocol.
- Any conclusion should mention the run settings (seed count, trial budget, patience, negatives).

## What can be said from the current quick run

- In this run, classical methods outperformed the small SASRec variant:
  - `ItemKNN` > `FMC` > `BPRMF` > `SASRec` on test Hit@10 and NDCG@10.
- This supports a cautious statement:
  - "SASRec is not always best under all settings."

## What should NOT be generalized yet

- Do not claim "classical is always better than SASRec" from one quick run.
- Do not claim production superiority from sampled-candidate ranking alone.

## Why SASRec can underperform in this setup

- Small hyperparameter budget (`max-trials=1`) can miss strong SASRec configs.
- Aggressive early stop (`patience=1`) can stop before sequence models stabilize.
- Candidate set size affects apparent difficulty and metric scale.
- Data density and sequence structure can favor simpler neighborhood/Markov signals.

## Better generalization protocol

- Use at least 3 seeds (already supported).
- Increase tuning budget equally across models.
- Increase patience for sequence models while keeping fairness constraints.
- Report mean/std and discuss variance, not only single-run best.

## Suggested wording for conclusions

"In our current MovieLens-1M quick benchmark (sampled candidates, limited tuning budget), classical baselines outperformed the small SASRec configuration. This indicates SASRec is not universally superior and performance depends on dataset characteristics and evaluation/training settings. A stronger claim requires broader hyperparameter search and multi-seed stability analysis."

