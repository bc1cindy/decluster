# Clustering-overcount diagnostic (relative)

Reproduce: `python3 examples/metric_demo.py`. Diagnostic in `decluster/graph_metric.py`,
guarded by `tests/test_metric.py`.

This is a **relative** diagnostic — how much the naive co-spend clustering *overstates* the
attacker's residual uncertainty versus the fingerprint+amount clustering — **not** an absolute
"bits of anonymity" of any transaction. The intrinsic anonymity of a payment (interpretations
under no auxiliary information) is the separate path-counting / k-route estimate, not this
partition entropy.

## The diagnostic
For a clustering of N coins into groups, the Shannon entropy of the cluster-size distribution
is `H = −Σ (n_i/N)·log2(n_i/N)` bits (`log2(N)` = all singletons; `0` = one cluster). We read
`2^H` only as a *ratio* between the naive and fused clusterings, never as a standalone privacy
number. Supercluster signal = the largest cluster's fraction of N.

## Result — real depth-6 ancestry graph of the merged transaction `931d6627` (19 coins)

| clustering | clusters | entropy (bits) | eff. cluster count (2^H) | largest cluster |
|---|---|---|---|---|
| **union-find (BlockSci)** | 15 | 3.79 | **13.8** | 16% |
| **fingerprint-aware (amount+fingerprint)** | 6 | 1.89 | **3.7** | 53% |

**Interpretation.** The naive union-find view reports an effective cluster count of
~13.8; applying the amount + fingerprint evidence collapses the graph from 15 clusters
to 6 — a **~3.7× overestimate** by the naive view (the fused figure is ~3.7, read only as
this ratio, not as an absolute "3.7 bits of anonymity" for the transaction). The largest
cluster grows from 16% to 53% (a supercluster forming). This is the paper's thesis quantified
at the graph level: the naive common-input view *overstates* the attacker's residual
uncertainty once fingerprints and amount structure are accounted for.

## Honest caveats
- **Not chain-scale.** 19 coins, one merged transaction's depth-6 ancestry (capped at 60,
  fetched via mempool.space). A statistically meaningful chain-wide measurement needs an
  archival Bitcoin Core node (Floresta cannot provide it — its Utreexo model keeps no
  historical blocks). The metric is the contribution; the graph size is data-limited.
- The fingerprint-aware clustering inherits the round-number change-id and the
  per-axis measured bits (the library-measured bits, decluster/library.py).
