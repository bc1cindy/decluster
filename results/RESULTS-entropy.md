# Graph-level anonymity metric

Reproduce: `python3 examples/metric_demo.py`. Metric in `decluster/graph_metric.py`,
guarded by `tests/test_metric.py`.

Closes the entropy / entropist anonymity-metric gap:
anonymity-set size assumes uniform, entropy generalizes; cluster size for rejecting
superclusters.

## The metric
For a clustering of N coins into groups, retained anonymity is the Shannon entropy of
the cluster-size distribution: `H = −Σ (n_i/N)·log2(n_i/N)` bits (`log2(N)` = all
singletons / max anonymity; `0` = one cluster / full collapse). Effective anonymity set
= `2^H`. Supercluster signal = the largest cluster's fraction of N.

## Result — real depth-6 ancestry graph of the merged transaction `931d6627` (19 coins)

| clustering | clusters | entropy (bits) | effective anon set | largest cluster |
|---|---|---|---|---|
| **union-find (BlockSci)** | 15 | 3.79 | **13.8** | 16% |
| **fingerprint-aware (amount+fingerprint)** | 5 | 1.78 | **3.4** | 53% |

**Interpretation.** The naive union-find view reports an effective anonymity set of
~13.8; applying the amount + fingerprint evidence collapses the graph from 15 clusters
to 5, revealing the *real* anonymity of ~**3.4** — a **~4× overestimate** by the naive
view. The largest cluster grows from 16% to 53% (a supercluster forming). This is the
paper's thesis quantified at the graph level: the on-chain anonymity is far smaller than
the common-input view suggests, once fingerprints and amount structure are accounted for.

## Honest caveats
- **Not chain-scale.** 19 coins, one merged transaction's depth-6 ancestry (capped at 60,
  fetched via mempool.space). A statistically meaningful chain-wide measurement needs an
  archival Bitcoin Core node (Floresta cannot provide it — its Utreexo model keeps no
  historical blocks). The metric is the contribution; the graph size is data-limited.
- The fingerprint-aware clustering inherits the round-number change-id and the
  per-axis measured bits (the library-measured bits, decluster/library.py).
