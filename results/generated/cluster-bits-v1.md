# What a cluster carries against what a merge hides

Generated from the canonical experiment artifact. Do not edit manually.

2538 co-spend clusters in 22112 committed transactions, each scored by the rarity of the external counterparties it pays or is paid by. Co-spend edges are excluded, so the identifier is not the thing that built the cluster.

| quantity | bits |
|---|---:|
| median cluster | 29.0 |
| p90 cluster | 68.7 |
| largest cluster | 21338.5 |
| median, five rarest counterparties only | 29.0 |

| threshold | share of clusters at or above |
|---:|---:|
| 1.6 bits | 100.0% |
| 10 bits | 97.9% |
| 50 bits | 16.5% |
| 100 bits | 5.2% |

The asymmetry the argument needs is the first row against 1.6: a merged transaction contributes about 1.6 bits of ambiguity, and 100.0% of these clusters already carry at least that much, at a median of 29.0.

The five-rarest floor does not test that on this cache: 92% of these clusters have at most 5 counterparties, so the restriction usually keeps the whole set and its median (29.0) repeats the one above it. A slice with richer neighbourhoods is what would make that floor say something about dependence between counterparties; here it says only that the clusters are small.

The cache is block-sampled rather than contiguous, so a cluster's counterparties are undercounted relative to a connected slice and every figure here is a floor. That is the direction the argument can use: a floor above the merge's contribution settles the comparison, and a larger slice can only raise it.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is recomputed from `data/fs-blkcache-2026-09-04.tar.gz` and compared byte for byte.
