# Graph-topology weight — counterparty overlap as a Fellegi–Sunter quasi-identifier

Reproduce: `python3 tests/test_topology.py`. Term in `decluster/cluster.py`
(`counterparty_bits`, `topology_weight`), fused in `cluster_fused(..., neigh=...)`.

## The gap this addresses

Fingerprints separate only *different* wallet software. If Alice and Bob use the **same**
wallet (identical fingerprints) and payjoin together, the co-spend heuristic plus the
matching fingerprints threaten to collapse their clusters — a false positive the fingerprint
channel cannot refuse (paper §9). The robust control is graph topology (Narayanan–Shmatikov):
Alice's counterparties differ from Bob's.

## What is calibrated and validated (the MATCH side)

Each counterparty is weighted by its rarity, `−log2(share of nodes touching it)`
(`counterparty_bits`): a hub (an exchange everyone touches) earns ~0 bits, a private address
many. On a connected real slice (`sample.ndjson`, 5 491 txs, 27 281 addresses, 889 co-spend
entities) counterparty bits range **4.1 (hub) to 14.7 (unique)**, and a shared-counterparty
score separates held-out same-owner pairs from cross-owner pairs:

| topology score | mean same-owner | mean cross-owner | AUC |
|---|---:|---:|---:|
| raw common-neighbour count | 0.68 | 0.00 | 0.839 |
| **rarity-calibrated bits** | **+3.57 bits** | 0.01 | 0.838 |

So a shared **rare** counterparty is real, calibrated same-owner evidence, summable with
the fingerprint bits. This is a delivered corroboration signal (it links same-owner coins
the co-spend missed).

## Per-pair mismatch is weak — the refusal needs accumulation

Calibrating the *disjoint* side **per pair** is the sobering part:

- **P(disjoint | same owner) = 0.32**, **P(disjoint | different owner) = 1.00** → FS mismatch
  weight `log2(0.32/1.00) ≈ −1.65 bits`.

`−1.65` does **not** overcome a same-wallet fingerprint match (`+2.78`): a *single* disjoint
pair is not refused. This is exactly the collaborator's *"if **enough** such distinguishing
relationships exist"* — the strength has to come from **accumulation**, not one pair.

## Cluster-level accumulation — this is what refuses (proven)

Aggregate the counterparty neighbourhoods of two candidate clusters (`cluster_topology_weight`)
and calibrate the *aggregate*-disjoint on the same slice:

- **P(aggregate-disjoint | same owner) = 0.000** (0 of 272 same-owner cluster halves)
- **P(aggregate-disjoint | different owner) = 0.997**
- FS weight = `log2(0.004 / 0.997) ≈ −8 bits` (Laplace-smoothed)

Same-owner clusters *never* have disjoint aggregate neighbourhoods (they reuse counterparties);
different owners almost always do. So an aggregate-disjoint is **~−8 calibrated bits** — strong
enough to refuse.

**End-to-end proof** (`tests/test_topology.py::test_cluster_topology_refuses_same_software_payjoin`):
Alice (`A1,A2`) and Bob (`B1,B2`) use the same wallet; each consolidates their own coins, then
a payjoin co-spends `A1,B1`. Merges are evaluated confident-first (Alice and Bob cluster
internally via their shared counterparties), so the payjoin edge is judged against the two
formed clusters: `fp +2.78 + aggregate-disjoint −8 = −5.2 < −2` → **refused**. Without topology
the co-spend collapses them. Alice's cluster is separated from Bob's — the transaction is
interpreted correctly as a payjoin.

## Summary

- ✅ MATCH (shared, rarity-weighted) — calibrated and validated (AUC 0.84, +3.57 bits).
- ◐ Per-pair MISMATCH — weak (`−1.65` bits); cannot refuse alone.
- ✅ Cluster-level accumulation — calibrated (`~−8` bits, `P(disjoint|same)=0.00`) and proven
  to refuse a same-software payjoin end-to-end. Chain-scale seed-and-extend over the whole
  graph remains future work (§10).
