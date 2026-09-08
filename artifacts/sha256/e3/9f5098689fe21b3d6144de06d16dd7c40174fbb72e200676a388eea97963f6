# How small a cut separates a coin from its origins

Generated from the canonical experiment artifact. Do not edit manually.

335 coins in the committed cache have an ancestry the slice can walk. For each, the number of routes back to its candidate origins that share no coin — the size of the cut that would separate it.

| routes | coins |
|---:|---:|
| 1 | 32 |
| 2 | 121 |
| 3 | 33 |
| 4 | 37 |
| 5 | 30 |
| 6 | 12 |
| 7 | 6 |
| 8 | 8 |
| 9 | 3 |
| 10 | 4 |
| 11 | 4 |
| 12 | 2 |
| 14 | 1 |
| 16 | 1 |
| 17 | 3 |
| 18 | 2 |
| 19 | 1 |
| 20 | 1 |
| 21 | 1 |
| 22 | 1 |
| 24 | 1 |
| 26 | 1 |
| 27 | 1 |
| 30 | 1 |
| 32 | 1 |
| 33 | 1 |
| 36 | 1 |
| 41 | 1 |
| 45 | 1 |
| 52 | 1 |
| 53 | 1 |
| 55 | 3 |
| 56 | 1 |
| 58 | 1 |
| 59 | 1 |
| 60 | 5 |
| 61 | 1 |
| 77 | 1 |
| 84 | 1 |
| 85 | 1 |
| 89 | 1 |
| 119 | 1 |
| 129 | 1 |
| 182 | 1 |
| 193 | 1 |
| 198 | 1 |

**32 (10%) of these coins are separated from their entire ancestry by removing one coin**, and 186 (56%) by removing at most 3. The framework asks that no small cut do this. At the other end the distribution reaches 198 routes, so redundancy varies by orders of magnitude between coins in one slice.

**Counting origins overstates that redundancy for 201 (60%) of them.** A coin's origin set says how many places its value could have come from; the cut says how many of those a separation would have to defeat, and the two are not the same number because routes share coins. That difference is the reason this is measured rather than counted.

Both readings are lower bounds, and one boundary count says how loose. The walk stopped 5707 times because the slice holds no record of a parent, against 48 times at the depth limit: almost every origin here is the edge of the sample rather than a coinbase or a genuine end of provenance. A cut measured to that edge can only grow on a contiguous export, so these are the cuts the committed data can already show and not a ceiling on redundancy. Read the shape — that a tenth of coins are separated by one coin while others carry 198 routes — rather than the level.

A route is also counted, not weighted. The value it could carry is the plausible-flow half of the framework's property, and no module here computes it.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is recomputed from `data/fs-blkcache-2026-09-04.tar.gz` and compared byte for byte.
