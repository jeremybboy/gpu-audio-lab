# Benchmark Notes

- Dataset: MovieLens-1M (`ratings.dat`).
- Seeds: [13].
- Candidate protocol: 1 positive + 20 sampled negatives per user.
- Best mean NDCG@10: `itemknn`.
- Caveat: candidate-sampled ranking is standard but not full-catalog ranking.
- Caveat: best configs are selected from a fixed, equal trial budget, not exhaustive search.