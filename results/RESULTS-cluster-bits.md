# Anchoring the ">100 bits": a real cluster's identifying structure, measured

§1 argues a merge's ~1.6 bits of ambiguity cannot survive the **>100 bits** an established
cluster carries — an order-of-magnitude figure inherited from Narayanan–Shmatikov, previously
*not measured*. This measures it directly, instantiating the N-S accumulation that
`cluster.topology_weight`'s docstring names.

## Method

On a real connected slice, each cluster (co-spend-linked addresses) carries, as its structural
quasi-identifier, its set of distinct **external payment-graph counterparties** (co-spend
edges excluded — non-circular; and the cluster's own members excluded — an intra-cluster edge
is not a quasi-identifier to an outsider). Each counterparty contributes
`−log2(share of nodes touching it)` bits (`counterparty_bits`): a hub everyone touches ≈ 0
bits, a rare private address many. The cluster's **structural information content** is their
sum — the N-S accumulation ("dozens of sparse attributes, each a few bits") on real Bitcoin
(`examples/cluster_bits.py`).

## Result — 150k-tx connected subset of `slice.json`, 5,864 clusters (≥2 addresses)

| quantity | value |
|---|---:|
| median cluster bits | **32.7** |
| p90 cluster bits | 126.2 |
| max cluster bits (a hub/exchange) | ~29,200 |
| clusters ≥ 1.6 bits (the merge's ambiguity) | **100.0%** |
| clusters ≥ 10 bits | 98.4% |
| clusters ≥ 50 bits | 22.7% |
| clusters ≥ 100 bits | **11.5%** |

## Reading

- **Every cluster clears the merge.** All 5,864 clusters carry ≥ 1.6 bits — the exact quantity
  a 2-in/2-out merge adds. The median carries **~33 bits, ~20× the merge**; the asymmetry §1
  asserts is measured, not just argued. An analyst needs only ~2 bits to override the merge and
  every cluster supplies an order of magnitude more.
- **The ">100" is reached, even truncated.** 11.5% of clusters already exceed 100 bits on a
  *150k-tx subset*. A subset sees only a fraction of each cluster's true counterparties, so this
  **undercounts** the whole-chain figure — the real per-cluster bits are higher, and the
  order-of-magnitude ">100" is the whole-chain expectation (§9).
- **Not an independence artifact.** The median top-5-counterparty sum equals the median total
  (32.7), i.e. the median cluster has ≤ 5 counterparties: its bits come from a handful of *rare*
  counterparties, not from summing hundreds of weak-but-correlated ones. So the naïve-independence
  caveat (Σ overstates unique-ID bits when counterparties correlate) does not inflate the median.

## Honest limits

- **Structural content, not proof of unique ID.** `Σ −log2(share)` is the identifying
  information *content*; correlated counterparties mean the effective unique-identification bits
  are fewer than the raw sum for large clusters. The top-5 floor and the small median cluster
  size bound this for typical clusters; hub/exchange super-clusters (the ~29,200 tail) are where
  the raw sum most overstates.
- **Slice, not whole chain.** A connected subset truncates counterparty sets, so the figures are
  a **lower bound** on the whole-chain per-cluster bits (§9). Reproduce:
  `python3 -m examples.cluster_bits slice.json 150000`.
