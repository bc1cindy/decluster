# Graph-topology weight — counterparty overlap as a Fellegi–Sunter quasi-identifier

Reproduce: `python3 tests/test_topology.py`. Term in `decluster/cluster.py`
(`counterparty_bits`, `topology_weight`), fused in `cluster_refined(..., neigh=...)`.

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

## Partial-overlap control (global rarity threshold)

The disjoint signal (`DISJOINT_BITS = −8.1`) fires only on *fully* disjoint neighbourhoods. A
subtler false positive arises when two clusters share counterparties — but only non-distinctive
ones (common exchange hubs that many clusters touch). A single shared hub would otherwise flip the
`−8` refusal into positive merge-evidence, rescuing a spurious payjoin collapse.

**Mechanism (rarity, not a candidate window).** Distinctiveness is already available globally: a
counterparty's rarity bits are `−log2(share of nodes touching it)` (`counterparty_bits`), so a
common hub is ~0 bits and a private address is many. `cluster_topology_weight` sums the rarity
bits of the shared counterparties and compares to a threshold `topo_tau` (bits): an overlap
**below `topo_tau`** — disjoint, or sharing only non-distinctive hubs — is treated as disjoint
(`−8.1`) and the merge is refused; **≥ `topo_tau`** corroborates same owner. Because rarity is
computed over the *whole graph*, this is **field-independent**: a universal hub (0 bits) is always
below threshold and refused, with no dependence on which clusters sit in any sample. (An earlier
design judged distinctiveness by a windowed N-S *eccentricity* `(max−max2)/σ` over a small
candidate set; that was field-dependent — a genuinely common hub could be missed if the window
held no co-occurring cluster — so it was replaced by this global rarity test, which is N-S's own
quasi-identifier weighting `wt = 1/log|supp|`.)

**Discriminative calibration on a real slice** (`sample.ndjson`, `calibrate_topo_tau`). Unlike a
same-owner-only pass-rate, this measures the actual discrimination: rarity-weighted overlap bits
for **same-owner** cluster pairs (split-half) vs **different-owner** pairs.

| overlap bits | value |
|---|---:|
| same-owner clusters | **889** |
| same-owner mean overlap bits | **11.7** |
| different-owner mean overlap bits | **0.004** (99.97% share nothing) |
| separation | **AUC ≈1.00 (0.9997)** |

The two populations are cleanly separated: same-owner clusters share distinctive counterparties
(11.7 bits), different owners essentially never do. Any `topo_tau` in `[0.5, 3.0]` keeps 100% of
same-owner and refuses 100% of different-owner on this slice; the default is **`topo_tau = 1.0`**
(the shared counterparty must be worth ≥ 1 bit, i.e. touched by ≤ half the nodes), with margin.
End-to-end proof in `test_engine_refuses_hub_only_partial_overlap` (hub-only Alice/Bob
overlap refused; their own distinctive coins kept).

**Honest limit.** This is the inherent counterparty-quasi-identifier limit, not removed by the
threshold: two *different* owners who genuinely both transact with the same **rare** counterparty
score above `topo_tau` and would merge — a shared rare quasi-identifier is treated as same-owner
evidence by the FS model itself. The threshold only removes the *hub* false positive; it cannot
tell a shared rare merchant from shared ownership. The AUC ≈1.00 (0.9997) is on one connected slice
where different owners are almost always fully disjoint; a denser graph with more incidental
rare-sharing would lower it. The threshold is also a hard cliff at `topo_tau`: on this slice nothing
lands near it (overlap is bimodal, 11.7 vs 0.004 bits), but on a denser graph counterparties in the
~0.5–1.5 bit range would make merge decisions sensitive to small rarity perturbations.

## Summary

- ✅ MATCH (shared, rarity-weighted) — calibrated and validated (AUC 0.84, +3.57 bits).
- ◐ Per-pair MISMATCH — weak (`−1.65` bits); cannot refuse alone.
- ✅ Cluster-level accumulation — calibrated (`~−8` bits, `P(disjoint|same)=0.00`) and proven
  to refuse a same-software payjoin end-to-end.
- ✅ Partial-overlap FP control (global rarity threshold `topo_tau = 1.0`) — non-distinctive/hub
  overlap treated as disjoint; **discriminatively** validated (same-owner 11.7 vs different-owner
  0.004 overlap bits, AUC ≈1.00 on 889 real clusters); field-independent; the residual limit is a
  shared *rare* counterparty (inherent FS-QI limit). Validated in `tests/test_topology.py`.
