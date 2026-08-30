# Go/no-go gate for a 2026 cross-view slice

**Question.** Cross-view matching contracts two epochs into two views of the pseudonym
graph and matches vertices between them. Before paying to export such a slice: does 2026
supply the raw material? 2026 has far less address reuse than the 2016 era used in
`RESULTS-graph-deanon.md`, so the era cannot be assumed to work.

**Data.** `bigquery-public-data.crypto_bitcoin`, two epochs of 144 blocks separated by
seven epochs (the separation `RESULTS-attribute-drift.md` argues for): A = 939 969–940 112,
B = 940 977–941 120, both in the 2026-03 partition. Coinbase excluded. ~3 GB scanned per
query. `bigquery/slice_gate.sql`.

## Result

| | epoch A | epoch B |
|---|---:|---:|
| non-coinbase txs | 410 662 | 420 820 |
| txs with ≥2 distinct input addresses | 40 212 (9.8 %) | 39 276 (9.3 %) |
| distinct input addresses | 489 965 | 496 378 |
| input addresses reused within the epoch | 43 551 (8.9 %) | — |

**Addresses spending in both views: 45 105** (9.2 % of A's input addresses).

Of those 45 105, restricted to the addresses that actually span:

| | epoch A | epoch B |
|---|---:|---:|
| in a co-spend tx (so in a multi-address cluster) | 29 681 (65.8 %) | 29 634 (65.7 %) |
| mean out-degree | 4.81 | 4.88 |
| median / p90 out-degree | 2 / 4 | 2 / 5 |
| degree 1 (leaves) | 19 591 (43.4 %) | 19 950 (44.2 %) |
| degree ≥ 3 | 9 195 (20.4 %) | 10 614 (23.5 %) |

Seed supply, by degree rank:

| top-k by degree | in both views' top-k | precision |
|---:|---:|---:|
| 50 | 33 | 0.66 |
| 100 | 40 | 0.40 |
| 200 | 40 | 0.20 |
| 500 | 44 | 0.088 |
| 1 000 | 45 | 0.045 |
| 5 000 | 52 | 0.010 |

## Verdict: proceed

**Spanning material is ample.** 45 105 addresses spend in both views a week apart, and
two thirds of them sit in a co-spend transaction, so they carry a *cluster* correspondence
rather than a singleton. That is roughly 29 650 candidate vertex correspondences from two
single days of chain, an order of magnitude more than the 2 463 entities the 2016 probe
worked with.

**Degree is thin but present, and this is a lower bound.** Mean 4.81, median 2, and 20–23 %
of spanning addresses at degree ≥ 3. These are *address*-level degrees measured before
contraction; contraction fuses a cluster's member addresses into one vertex and their
neighbourhoods with them, so the pseudonym vertex degree is strictly higher than what is
tabulated here. The 43 % of spanning addresses at degree 1 have no neighbourhood to match
on and should remain unmatched, which is the intended behaviour rather than a failure.

**Seed supply is the weak leg.** Overlap of the top-k by degree saturates at roughly 40 to
52 addresses no matter how deep k goes: precision falls from 0.66 at k = 50 to 0.01 at
k = 5 000 while the absolute count barely moves. Only about 40 to 50 high-degree
*addresses* persist across a week; below that rank the population turns over completely.

The likely cause is also the likely fix: services rotate addresses, so an address-level
degree ranking churns even where the underlying entity does not. Contraction is exactly
what collapses a service's rotating addresses into one persistent vertex. This gate
therefore *understates* the seed supply, and the measurement has to be repeated on the
contracted graph before the seed strategy is settled.

## Consequences

1. Proceed to exporting the slice, in the 2026-03 partition, below height 959 194.
2. Re-measure seed supply after contraction. Do not commit to degree-rank seeding on the
   strength of the address-level numbers, in either direction.
3. Keep degree-rank seeding separate from the degree-only negative control, or the control
   is confounded by construction.
4. Expect ~43 % of spanning vertices to be unmatchable on structure. Report coverage and
   precision separately; a matcher that matches everything is wrong.

## Scope

Address-level proxies for cluster-level quantities, chosen because union-find does not fit
in SQL. Every number here is a bound on the contracted graph, not a measurement of it.
Two single days; seasonal variation across the 158-epoch window is not covered.
