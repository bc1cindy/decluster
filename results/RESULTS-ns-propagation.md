# N-S seed-and-propagate driver — offline smoke run

`examples/ns_propagation.py` wires `decluster.propagate` (build_rarity, entity_signature,
NSPropagator, holdout_reid, partition_from_assignment) into a single `run_on_signatures(...)`
summary: seed-label re-identification rate, whole-partition bits (entropy) before vs. after
merge propagation, and the split channel's refined-group count. `run(txs, seeds)` is the real-data
wiring (ancestry_signature + Combiner.from_library); it is untested against chain data here —
see "To reproduce on chain data" below.

## What this run is

**Synthetic smoke run, not chain data.** All node signatures below are hand-built provenance
vectors (`{ancestor: mass}`), not `ancestry_signature` output over real transactions. This
exercises the driver's wiring end-to-end; it is not a measurement of real-chain
re-identification performance.

Command:

```
./.venv/bin/python -c "
from examples.ns_propagation import run_on_signatures

class SplitCombiner:
    def score(self, a, b):
        return -5.0 if {a, b} == {'P', 'Q'} else 3.0

node_sigs = {
    'A1': {'r1': 1.0}, 'A2': {'r1': 0.9, 'hub': 0.1},
    'B1': {'r2': 1.0}, 'B2': {'r2': 0.9, 'hub': 0.1},
    'C1': {'r3': 1.0}, 'C2': {'r3': 0.9, 'hub': 0.1},
    'u1': {'r1': 0.85, 'hub': 0.15},
    'u2': {'hub': 1.0},
    'P': {'r9': 1.0}, 'Q': {'r8': 1.0},
}
seeds = {'A1': 'A', 'A2': 'A', 'B1': 'B', 'B2': 'B', 'C1': 'C', 'C2': 'C'}
txs = {k: k for k in node_sigs}
rarity = {'r1': 1, 'r2': 1, 'r3': 1, 'r9': 1, 'r8': 1, 'hub': 500}
print(run_on_signatures(node_sigs, seeds, txs, rarity,
                        combiner=SplitCombiner(),
                        cospend_clusters=[['P', 'Q']]))
"
```

Fixture: 3 seed entities (A, B, C), each with 2 labeled member nodes sharing a rare ancestor
(`r1`/`r2`/`r3`) plus a common weak hub ancestor; one unlabeled node `u1` overlapping A's rare
ancestor (a merge-propagation target); one unlabeled node `u2` sharing only the hub (should
stay unassigned — leaked hub overlap is below the match floor); and a co-spend pair `P`/`Q`
with disjoint provenance whose fingerprint combiner reports divergence (a split-channel
target). 10 nodes total, `theta=0.5`, `min_score=0.1`, `refuse_below=-2.0` (driver defaults).

## Result

| quantity | value |
|---|---:|
| n_nodes | 10 |
| reid_rate (holdout, hide_frac=0.3) | **1.0** |
| partition_bits_before | 1.585 |
| partition_bits_after | 1.557 |
| n_refined_groups | 2 |

- **reid_rate = 1.0**: `holdout_reid` hid one of the 6 seed-labeled nodes and re-derived its
  label purely from provenance overlap with the remaining seed — full recovery on this small,
  clean-signal fixture (each entity's rare ancestor is exclusive to it).
- **n_refined_groups = 2**: the split channel correctly separated the `[P, Q]` co-spend pair
  into `[P]` and `[Q]` (disjoint provenance AND divergent fingerprint — both channels agreed).
- **partition_bits_before = 1.585**: entropy of the whole seed-label partition before merge
  propagation — 3 labeled groups (`A`, `B`, `C`) of 2 nodes each, `log2(3) = 1.585` bits, the
  uncertainty about which of the 3 equal-size clusters a random labeled node falls in.
- **partition_bits_after = 1.557**: entropy of the whole partition after merge propagation
  assigns `u1` into `A` (its rare-ancestor overlap target) and leaves `u2` unassigned (hub-only
  overlap, below the match floor) — `A` grows to 3 members against `B`/`C`'s 2, a slightly less
  even partition, so bits drop slightly versus the perfectly-balanced seed labeling. This
  replaces the previous `_median_cluster_bits`, which took the median of
  `partition_entropy([g])` over each group in isolation — always 0.0 by construction, since a
  one-group partition has no uncertainty to measure. The fix computes
  `partition_entropy(partition_from_assignment(assigned))` over *all* groups together (see
  `_partition_bits` in `examples/ns_propagation.py`).

## Union-find baseline

Not computed. `cluster.cluster_naive(nodes)` clusters by common-input-ownership and needs
`fetch_tx` over real txids (co-spend edges from real transaction inputs) — it has no meaningful
reading over synthetic node labels like `A1`/`u1`. The union-find contrast against this metric
is deferred to the real-chain run (see below), where real co-spend edges make the comparison
meaningful.

## To reproduce on chain data

A real run needs, concretely:

1. **A prevout-resolved tx sample.** `decluster.fingerprint_validate.load_blkcache()` reads the
   local `.blkcache` offline (195,301 txs available in this repo checkout) and already filters
   to txs with resolved `prevout` values on every input.
2. **Real same-owner seed labels.** E.g. address-reuse groups, the same construction as
   `fingerprint_validate.reuse_pairs`: group txs by shared input address, entities = groups of
   size ≥ 2. On this checkout, filtering to small txs (≤3 vin/vout, to bound the ancestry walk
   below) gives 3,472 address-reuse pairs.
3. **`ancestry_signature(coin, depth=...)` per representative coin**, via the `dss` link oracle
   (`decluster.ancestry.dss_link_oracle`, the compiled subset-sum matrix) and `fetch_tx`
   (network — `mempool.space`, rate-limited to ~5 req/s with backoff). This is the expensive
   step: each hop of the backward walk fetches every input's parent transaction, so cost grows
   with both `depth` and each ancestor tx's input count. A single depth-2 walk from a
   19-input coin took ~24s in this environment; small-degree coins (1–2 in/out, the
   `reuse_pairs`-style sample above) are far cheaper but a batch of even 10 nodes at depth 3
   did not complete inside this task's time budget when attempted — abandoned per instruction
   rather than reported partially or estimated.
4. **The `cluster.cluster_naive(nodes)` baseline**, for contrast, over the same node set —
   also needs `fetch_tx` (real txids, real co-spend edges).

`examples/ns_propagation.run(txs, seeds, depth=6)` wires steps 1 and 3 together
(`node_sigs[node] = entity_signature([ancestry_signature((tx["txid"], 0), depth=depth)])`) and
calls `run_on_signatures` on the result; it is the entry point for a full chain-data run once a
sample and seed set (steps 1–2) and a time budget for step 3 are available.
