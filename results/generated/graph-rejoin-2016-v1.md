# Rejoining a cluster split across two weekly views

Generated from the canonical experiment artifact. Do not edit manually.

Two consecutive 2016 weekly windows of 982,021 and 1,116,563 transactions. 17,431 clusters straddle the boundary and survive contraction in both views, at a mean internal degree of 2.866.

| statistic | view A | view B |
|---|---:|---:|
| vertices | 588,843 | 638,436 |
| edges | 1,430,236 | 1,561,102 |
| mean degree | 4.7874 | 4.8199 |
| degree 1 share | 0.0464 | 0.0600 |
| transitivity | 0.0062 | 0.0001 |
| configuration transitivity | 0.6113 | 0.3976 |
| assortativity | -0.0764 | -0.0782 |
| tail exponent | 2.8613 | 2.8337 |

| seed share | matcher | arm | guesses | correct | precision |
|---:|---|---|---:|---:|---:|
| 5% | undirected | seeded | 0 | 0 | — |
| 5% | undirected | shuffled | 0 | 0 | — |
| 5% | directed | seeded | 0 | 0 | — |
| 5% | directed | shuffled | 0 | 0 | — |
| 10% | undirected | seeded | 0 | 0 | — |
| 10% | undirected | shuffled | 0 | 0 | — |
| 10% | directed | seeded | 1 | 1 | 1.000 |
| 10% | directed | shuffled | 0 | 0 | — |

At the widest seeding the matcher is offered 15,688 non-seed pairs. Across every seeded arm it guesses 1 and gets 1 right; the shuffled-seed arms guess 0. A cascade that carried itself would show each seed unlocking more than itself, and it does not at these view widths. One match is not ignition, and it is a different statement from none.

Cluster membership here is a co-spend relation rather than observed wallet ownership, and the seeds are supplied. The result is what propagation does once a foothold exists, not whether one can be found.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is recomputed from the committed weekly epoch graphs and compared byte for byte.
