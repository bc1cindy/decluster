# Partial-clustering pseudonym graph

Generated from the canonical experiment artifact. Do not edit manually.

Vertices: cluster-a, cluster-x, z.

| source | target | transfers | value | height span |
|---|---|---:|---:|---|
| cluster-a | cluster-x | 3 | 600 | 100–140 |
| cluster-x | cluster-a | 1 | 50 | 120–120 |
| z | cluster-a | 1 | 10 | 150–150 |

The unknown address `z` remains a singleton pseudonym. Parallel transfers from `cluster-a` to `cluster-x` are folded into one directed edge with count, total value and height span. The reverse direction remains a separate edge; change within `cluster-a` is recorded as a self-transfer rather than a relationship.

The supplied clustering is partial. These vertices are pseudonyms, not verified users.
