# N-S seed-and-propagate driver

`examples/ns_propagation.py` wires `decluster.propagate` (build_rarity, entity_signature,
NSPropagator, holdout_reid, partition_from_assignment) into a single `run_on_signatures(...)`
summary: seed-label re-identification rate, whole-partition bits (entropy) before vs. after
merge propagation, and the split channel's refined-group count.

This file now has two runs. The **real cache-bounded run** (below) replaces the previously-deferred
chain-data measurement, computed entirely offline against this checkout's `.cache/` (~7,000 cached
tx JSON files) — no network. The original **synthetic smoke run** is kept underneath it for the
wiring-level regression check it still serves.

## Real cache-bounded run

`examples/ns_propagation_cache_run.py` (offline, no `decluster/propagate.py` or `decluster/cluster.py`
changes) draws a bounded real sample from `.cache/`, computes real `ancestry_signature`s via a
**cache-only fetch** (`cache_fetch_tx`: reads `.cache/{txid}.json`; a MISS returns a coinbase-shaped
boundary marker, which `ancestry.build_extended_graph`'s existing `_is_coinbase` check already treats
as an absorber — no core-code change needed, and the walk never touches the network), and runs both
N-S channels plus the deferred union-find baseline.

**Sample construction** (deterministic, from the 4,318 valid cached txs found in `.cache/`): two
independent same-owner signals, transitively closed by union-find so overlapping edges merge
correctly —

- **co-spend clusters**: a cached child tx whose inputs reference ≥2 other cached txids (a real
  common-input-ownership edge entirely inside the cache). 40 clusters (31 pairs, 9 triples), 110
  member coins, plus the 40 linking child txs needed so `cluster_naive` can rediscover the same
  edges from scratch → feeds `cospend_clusters` (the split channel) and the union-find baseline.
- **address-reuse clusters**: cached txs sharing an input address (independent of co-spend).
  22 clusters (20 pairs, 2 triples), 46 member coins → feeds `seed_labels` for
  `propagate`/`holdout_reid`.

Total sample: **150 coins** (nodes), capped so the run finishes in under 20s.

### Ancestry: mostly boundary, not mostly resolved — but not a total collapse either

| quantity | value |
|---|---:|
| n_nodes | 150 |
| depth | 4 |
| resolved (>1 absorber — real branching inside the cache) | **64 / 150 (43%)** |
| collapsed to a single boundary atom (≤1 absorber) | **86 / 150 (57%)** |
| — of which: target's own tx is itself the absorber (0 interior hops) | 31 / 150 |
| total cache-miss truncations (oracle-`None` refusals) across all 150 walks | 63 |

Unlike the prior contiguous-slice attempt in `results/RESULTS-ancestry.md` (§7 of `PAPER.md`: "every
signature collapses to a **single** boundary atom... a tractable-width slice cannot contain
multi-hop ancestry"), this sample does **not** collapse universally — 43% of coins resolve real
branching within the cache, because the sample was deliberately built from co-spend/address-reuse
*linked* subgraphs rather than a random contiguous block range, so a meaningful fraction of nodes'
immediate parents (or grandparents) happen to already be cached too. But the majority (57%) still
hit the cache boundary within 0–1 hops, exactly the mechanism `PAPER.md` §7 describes: a bounded
cache is a bounded graph window, and most coins' ancestry reaches outside it almost immediately.
**Honest reading: the cache-bounded ancestry signal is real but weak and partial, not the
near-deterministic quasi-identifier `RESULTS-ancestry.md` found with live network access at small
scale — a bounded, offline slice recovers some of the effect, not most of it.**

### N-S propagation and holdout re-identification

| quantity | value |
|---|---:|
| reid_rate (holdout, hide_frac≈0.3) | **0.154** (2 / 13 recovered) |
| partition_bits_before (22 seed groups, 46 labeled coins) | 4.447 |
| partition_bits_after (merge propagation; 57 coins labeled) | 4.368 |
| n_refined_groups (split channel, over 40 cospend clusters) | 46 |

- **reid_rate = 0.154**, versus **1.0** on the synthetic fixture below — the honest gap between a
  clean hand-built signal and a real, cache-truncated one. `holdout_reid` hid 13 of the 46
  address-reuse-labeled coins and re-derived their label from provenance overlap with the rest;
  only 2 recovered. Consistent with the ancestry finding above: 57% of signatures are
  boundary-collapsed, so most held-out coins have little or no real overlap left to match on.
- Merge propagation grew the labeled set from 46 to 57 coins (11 newly assigned beyond the seeds),
  a modest, plausible amount of real propagation — not zero, but far from the synthetic fixture's
  clean full recovery.
- **partition_bits_before → after: 4.447 → 4.368**, a small decrease (a few coins pulled into the
  larger seed groups), the same direction as the synthetic run but a much smaller move given the
  weaker signal.

**Caveat on the split channel (`n_refined_groups`, 40 → 46 groups, i.e. 6 splits):** `should_split`
requires provenance-disjointness **and** fingerprint divergence together, so a split is not provenance
alone. But of the 58 within-cluster co-spend pairs checked, **24 (41%) have both members' signatures
collapsed to a single (necessarily different) boundary atom** — meaning `provenance_link` reads them
as "disjoint" not because their true provenance is known to differ, but because the cache boundary
truncated both walks to an uninformative single atom. For those 24 pairs the provenance channel
contributes no real evidence either way; any split among them is being driven by the fingerprint
channel alone, with the provenance gate trivially satisfied by cache truncation rather than genuine
disjointness. This is the same §7 mechanism, restated for the split channel: a bounded cache cannot
tell "genuinely disjoint provenance" apart from "both walks hit the wall," so provenance-disjointness
evidence from this run should be read as weak/inflated, not trusted at face value.

### Union-find baseline (deferred baseline, now computed)

| partition | clusters | entropy (bits) |
|---|---:|---:|
| **union-find** (`cluster.cluster_naive`, common-input-ownership only) | 100 | 6.517 |
| **N-S refined** (split channel's 46 groups + 110 untouched coins as singletons, full 150-coin partition) | 107 | 6.620 |

Over this sample, the refined partition has **more** clusters and **higher** entropy than the raw
union-find baseline — i.e. it fragmented slightly further, not less. This is the opposite direction
from the engine's usual role (`cluster_refined` normally *reduces* overcount relative to
`cluster_naive`, see `RESULTS-cluster-scale.md`/`graph_metric.overcount_report`): here the split
channel (`NSPropagator.refine`, the provenance-aware analogue) removed a few co-spend edges
(6 of 40 clusters split), and — per the caveat above — a meaningful fraction of those removals rest
on a provenance-disjointness signal that the cache boundary made spuriously easy to satisfy. Read
honestly: on this small, cache-bounded, boundary-corrupted sample, the split channel is not shown to
improve on the union-find baseline; a live-network run (real multi-hop provenance, not a truncated
cache) is needed before drawing a directional conclusion either way.

Reproduce: `./.venv/bin/python -m examples.ns_propagation_cache_run` (prints the full JSON summary;
no network access, ~15–20s).

## Synthetic smoke run (prior, kept for the wiring-level regression check)

**Synthetic, not chain data.** All node signatures below are hand-built provenance vectors
(`{ancestor: mass}`), not `ancestry_signature` output over real transactions. This exercises the
driver's wiring end-to-end; it is not a measurement of real-chain re-identification performance —
see "Real cache-bounded run" above for that.

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

Not computed *on this synthetic fixture* — `cluster.cluster_naive(nodes)` clusters by
common-input-ownership and needs `fetch_tx` over real txids; it has no meaningful reading over
synthetic node labels like `A1`/`u1`. **Now computed for real** in the "Real cache-bounded run"
section above (100 clusters / 6.517 bits vs. the refined partition's 107 / 6.620).

## Chain-data reproduction — done (cache-bounded); network run still open

The "Real cache-bounded run" above supersedes the original plan here: it ran the full pipeline
(real `ancestry_signature`, `build_rarity`, `NSPropagator.propagate`/`.refine`, `holdout_reid`,
and the `cluster.cluster_naive` baseline) against this checkout's `.cache/`, entirely offline. The
one thing it does *not* give is a **network** run with unbounded ancestry depth — a real fetch
over `mempool.space` was previously abandoned mid-task as too slow (a single depth-2 walk from a
19-input coin took ~24s in that environment, rate-limited to ~5 req/s with backoff) and remains a
possible follow-up if a much larger multi-hop-connected cache (or a live, budgeted network session)
becomes available; `examples/ns_propagation.run(txs, seeds, depth=6)` is still the entry point for
that (`fetch=fetch_tx`, network-backed) once such a budget exists.
