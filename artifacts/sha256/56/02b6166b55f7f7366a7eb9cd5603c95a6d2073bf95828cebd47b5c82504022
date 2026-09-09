# How small a cut separates a coin from its origins

Generated from the canonical experiment artifact. Do not edit manually.

335 coins in the committed cache have an ancestry the slice can walk. For each, the number of routes back to its candidate origins that share no coin — the size of the cut that would separate it.

| routes | coins | coins, routes able to carry the coin |
|---:|---:|---:|
| 0 | 0 | 128 |
| 1 | 32 | 70 |
| 2 | 121 | 57 |
| 3 | 33 | 18 |
| 4 | 37 | 18 |
| 5 | 30 | 10 |
| 6 | 12 | 10 |
| 7 | 6 | 2 |
| 8 | 8 | 6 |
| 9 | 3 | 1 |
| 10 | 4 | 0 |
| 11 | 4 | 1 |
| 12 | 2 | 0 |
| 13 | 0 | 1 |
| 14 | 1 | 0 |
| 16 | 1 | 2 |
| 17 | 3 | 0 |
| 18 | 2 | 0 |
| 19 | 1 | 0 |
| 20 | 1 | 0 |
| 21 | 1 | 1 |
| 22 | 1 | 0 |
| 23 | 0 | 1 |
| 24 | 1 | 1 |
| 26 | 1 | 0 |
| 27 | 1 | 0 |
| 29 | 0 | 1 |
| 30 | 1 | 0 |
| 32 | 1 | 1 |
| 33 | 1 | 1 |
| 34 | 0 | 1 |
| 36 | 1 | 1 |
| 41 | 1 | 0 |
| 45 | 1 | 0 |
| 52 | 1 | 0 |
| 53 | 1 | 0 |
| 55 | 3 | 0 |
| 56 | 1 | 0 |
| 58 | 1 | 0 |
| 59 | 1 | 0 |
| 60 | 5 | 0 |
| 61 | 1 | 0 |
| 69 | 0 | 1 |
| 77 | 1 | 1 |
| 84 | 1 | 0 |
| 85 | 1 | 0 |
| 89 | 1 | 0 |
| 119 | 1 | 0 |
| 129 | 1 | 0 |
| 182 | 1 | 0 |
| 193 | 1 | 0 |
| 198 | 1 | 1 |

**32 (10%) of these coins are separated from their entire ancestry by removing one coin**, and 186 (56%) by removing at most 3. The framework asks that no small cut do this. At the other end the distribution reaches 198 routes, so redundancy varies by orders of magnitude between coins in one slice.

That count treats every route alike, and the specification does not: a path worth less than the amount in question may have been removed before the question is asked. Pruning each coin's routes to those that could have carried its own value **takes the single-coin cut from 32 (10%) to 70 (21%)**, and leaves 128 (38%) with no route able to carry the coin at all. Counting routes without their value overstates redundancy, in the same direction and for the same reason as counting origins without their overlap.

**Counting origins overstates that redundancy for 201 (60%) of them.** A coin's origin set says how many places its value could have come from; the cut says how many of those a separation would have to defeat, and the two are not the same number because routes share coins. That difference is the reason this is measured rather than counted.

Both readings are lower bounds, and one boundary count says how loose. The walk stopped 5707 times because the slice holds no record of a parent, against 48 times at the depth limit: almost every origin here is the edge of the sample rather than a coinbase or a genuine end of provenance. A cut measured to that edge can only grow on a contiguous export, so these are the cuts the committed data can already show and not a ceiling on redundancy. Read the shape — that a tenth of coins are separated by one coin while others carry 198 routes — rather than the level.

**The framework states its property over the mass of a coin's candidate origins, not only over how many routes reach it**, so the same network is solved a second time with each coin's own value as its capacity. The maximum flow is what the origin set could deliver if every route ran at once, and its minimum cut is the value a separation would have to remove. For 8 (2%) of these coins the origins cannot deliver the coin's own value at all — a shortfall a route count cannot see, because those routes exist and simply are not worth enough together.

That is still one flow and still polynomial. Choosing which routes carry how much — the k-splittable formulation — is strongly NP-hard, is a decision about routing rather than a measurement of capacity, and is not this one.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is recomputed from `data/fs-blkcache-2026-09-04.tar.gz` and compared byte for byte.
