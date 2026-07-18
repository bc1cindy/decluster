# Clustering weight-robustness: does graph topology stabilise the partition against weight changes?

**Claim tested.** The collaborator's part-3 conjecture is robustness "with enough fingerprints **and graph
structure**." The fingerprint leg is shown in `RESULTS-weight-sensitivity.md` / `RESULTS-em-m.md`. This
tests the graph leg at the clustering level: does fusing the topology term (`cluster_refined(neigh=…)`,
calibrated in `RESULTS-topology.md`) make the owner-*partition* stable under a fingerprint-weight (`c`)
sweep, where a fingerprint-only clustering moves?

**Setup.** A controlled ancestry-shaped scenario (`examples/cluster_robustness.py`): 4 wallets, each with
distinct construction fingerprints and a distinctive rare counterparty, consolidations giving within-wallet
co-spend edges, and 2 cross-wallet payjoin merges (the false links). For each `c ∈ {0.60…0.99}` we run
`cluster_refined` twice — `neigh=None` (fp-only) and `neigh=NEIGH` (fp+topo) — and measure the Adjusted Rand
Index of each partition against that arm's `c=0.95` partition. Offline, deterministic.

## Result

| c | ARI (fp-only) | ARI (fp+topo) | eff-anon (fp-only) | eff-anon (fp+topo) |
|---|---:|---:|---:|---:|
| 0.60 | 0.8445 | 1.0000 | 3.93 | 6.74 |
| 0.70 | 0.8445 | 1.0000 | 3.93 | 6.74 |
| 0.80 | 0.8445 | 1.0000 | 3.93 | 6.74 |
| 0.90 | 1.0000 | 1.0000 | 4.95 | 6.74 |
| 0.95 | 1.0000 | 1.0000 | 4.95 | 6.74 |
| 0.99 | 0.6364 | 1.0000 | 6.74 | 6.74 |

The fp+topo arm holds ARI = 1.0000 across every `c` in the grid: the disjoint rare-counterparty signal
(~−8 bits, calibrated in `RESULTS-topology.md`) dominates the merge decision, so the partition is
entirely stable regardless of how the fingerprint weight `c` is set. The fp-only arm moves at both
ends of the sweep: at `c ∈ {0.60, 0.70, 0.80}` the fingerprint mismatch score drops below the refuse
threshold and one or both cross-wallet payjoins collapse (ARI 0.8445 vs the c=0.95 baseline); at
`c = 0.99` the stronger mismatch weight refuses more co-spend merges, causing the baseline's combined
cluster to re-split into two (ARI 0.6364). The topology term carries the
merge/split decision independently of `c`, confirming that the graph leg of the robustness conjecture
holds in this controlled scenario.

Reproduce: `python3 examples/cluster_robustness.py`.

## Honest limits

- **Constructed scenario, not chain scale.** Like the paper's `931d6627` existence demos, this isolates
  the mechanism on a graph we build; it is not a whole-chain rate. Real-data confirmation on the
  `931d6627` ancestry is a noted follow-on.
- **3-axis clustering scorer.** The clustering path uses the 3-axis `Combiner`, not the 23-axis
  `LibraryScorer` of the pair-AUC validation.
- **`cluster_refined` is case-study scale** (`fetch_tx` per pair, O(n²) linking); the scenario is sized
  accordingly.
- **The topology signal here is counterparty-overlap, narrower than "graph connectivity."** The fused
  term is a rarity-weighted shared-counterparty overlap (`cluster_topology_weight`) — a graph-derived
  quasi-identifier (shared *edges* in the payment graph), the intersection-attack intuition. It is *not*
  the connectivity / average-distance / max-flow of the whole graph that the design conversation frames
  as the substance of robustness; those are a stronger, separate topological measure (future work). What
  this shows is "a rare shared counterparty dominates the fingerprint weight," which is one concrete way
  graph structure swamps the per-axis uncertainty, not the full connectivity argument.
