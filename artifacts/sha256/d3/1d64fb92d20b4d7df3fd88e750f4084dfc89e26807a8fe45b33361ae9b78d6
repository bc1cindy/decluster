# What each channel adds when the engine fuses them

Generated from the canonical experiment artifact. Do not edit manually.

22112 committed transactions hold 335 co-spends over 753 funding transactions. The engine judges those co-spends; the merge-only baseline takes every one of them.

| arm | groups | refused co-spends | added links | largest group |
|---|---:|---:|---:|---:|
| co-spend union-find | 697 | 0 | 0 | 5 |
| fingerprint | 508 | 19 | 7560 | 87 |
| fingerprint+amount | 508 | 19 | 7560 | 87 |
| fingerprint+amount+topology | 511 | 11 | 7560 | 88 |
| fingerprint+amount+topology+provenance | 514 | 22 | 7560 | 87 |
| all five channels | 514 | 22 | 7560 | 87 |

The fingerprint channel is what moves the partition: it adds 7560 links the co-spend missed and takes the largest group from 5 to 87. Refusal is the smaller effect and the one the thesis is about — 19 co-spends declined that the baseline merges.

Topology and provenance pull in opposite directions, which is the point of fusing them. Adding the cluster-level topology takes refusals from 19 to 11: it corroborates merges the fingerprint alone objected to. Adding provenance-disjointness takes them to 22, cutting pairs whose ancestry does not overlap.

The amount channel and the subset-sum de-mix move nothing here, and the reason is structural rather than empirical: both are refuse-only and gated behind fingerprint disagreement, so they can only speak on the pairs the fingerprint already objects to. The slice holds 81 two-input two-output co-spends, the only shape the roundness re-partition judges.

The provenance signature here is depth-1 — a node's in-slice funders — because the slice is block-sampled rather than contiguous. A deeper walk needs a contiguous export.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is recomputed from `data/fs-blkcache-2026-09-04.tar.gz` and compared byte for byte.
