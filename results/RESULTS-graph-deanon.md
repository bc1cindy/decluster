# Community-structure de-anonymization (Narayanan–Shmatikov, on real chain data)

**Claim tested.** Does the *structure* of the Bitcoin transaction graph predict
same-owner membership — beyond the co-spend heuristic that defines the clusters? This
is the Narayanan–Shmatikov premise (structure alone re-identifies) applied to Bitcoin.

**Data.** A *connected* chain slice — blocks 400000–400004 (Feb 2016), 8 927 non-coinbase
txs, **27 962 addresses**, **2 463 entities** (co-spend clusters with ≥2 addresses).
A contiguous block range (not a random sample) so the graph is actually connected; the
2016 era has heavy address reuse, giving rich clusters. Extracted via `bigquery/graph.sql`
(no archival node). Reproduce: `python3 decluster/graph_deanon.py <slice.json>`.

**Method.** Same-owner labels = transitive co-spend clusters — a *heuristic*: near-certain for
ordinary txs but **broken by the collaborative transactions this work studies** (a
coinjoin/payjoin in the slice is a false merge; 2016 has few — see the caveat below).
Held-out positives = same-owner pairs that are **not**
directly co-spent (267 578 pairs) — the link must come from structure, not the pair's own
tx. Structural score = common neighbors in the address graph (classic link prediction).
Negatives = cross-entity pairs. Metric = AUC (P[positive scores higher than negative]).

## Result

Blocks 400000–400004 (2016), full slice:

| Graph used for structure | AUC | Reading |
|---|---:|---|
| **FULL** (co-spend + payment edges) | **0.992** | structure aligns with entity boundaries |
| **PAYMENT-ONLY** (co-spend edges removed) | **0.950** | ← the honest test: structure de-anonymizes *independently* of the clustering heuristic |
| **SHUFFLE** (entity labels randomized) | **0.500** | control: the signal is not a sampling artifact |

The confound: the FULL graph shares its co-spend edges with the heuristic that *defines*
those labels, so its 0.990 is partly circular. Removing those edges — scoring pairs by
**payment** relationships only — still yields **AUC 0.950**. The shuffle control lands at
0.500, confirming the effect is real structure, not the pair-sampling.

### Across five eras: the mechanism, not a clean curve

Payment-only AUC on five connected slices, swept over graph reach *k* (k-hop common
neighbors, hub intermediates excluded — `decluster/graph_deanon.py --depth`).
**share%** = fraction of same-owner pairs sharing a *direct* counterparty. Each slice is a
contiguous block range (partition-pruned by `block_timestamp_month`, `bigquery/graph.sql`):

| Year | blocks | entities | held-out pairs | share% | k=1 | k=2 | k=3 | k=4 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2012 | 200000–200019 | 189 | 9 635 | 96% | **0.97** | 0.99 | 0.98 | 0.97 |
| 2013 | 250000–250014 | 558 | 25 944 | **6%** | **0.53** | 0.78 | 0.92 | **0.98** |
| 2016 | 400000–400004 | 2 463 | 267 578 | 91% | **0.95** | 0.97 | 0.99 | 0.99 |
| 2023 | 800000–800002 | 363 | 111 | 65% | **0.83** | 1.00 | 1.00 | 1.00 |
| 2024 | 845982–846001 | 2 704 | 897 247 | 48% | **0.74** | 0.88 | 0.95 | 0.97 |

(2024 is the robust modern anchor — 2 704 entities, 897 k held-out pairs, largest cluster
only 5% of clustered addresses, so no supercluster inflates it — unlike a small 2025 slice,
which is dominated by a single ~40%-supercluster consolidation and saturates to a
non-informative 1.00; a meaningful 2025 point needs that supercluster excluded first.)

Two findings. **(1) At k=1 the effect is not a clean era/reuse curve**: the 2013 slice
drops to chance (0.53) on a *substantial* 25 944 pairs — not a small-sample fluke. The
diagnostic explains it: 1-hop AUC tracks **share%** monotonically (96%→0.97, 91%→0.95,
65%→0.83, 48%→0.74, 6%→0.53). 2013 is the SatoshiDice / service-churn era — an owner's addresses each
touch a *different* service address, so only 6% share a direct counterparty and the 1-hop
feature is starved.

**(2) The structure is still there, deeper in the graph.** Sweeping reach recovers the
churny slice — 2013 climbs 0.53 → 0.78 → 0.92 → 0.98 — while the others stay saturated;
**by k=4 all five eras sit at 0.97–1.00**. So the 2013 null is a limitation of *shallow
reach under counterparty churn*, not absence of structural de-anonymizability. The depth
you need scales with how much counterparties are shared. This *strengthens* the
Narayanan–Shmatikov claim: structure de-anonymizes across every era tested.

Why deeper reach does not collapse to chance (the usual small-world objection): hub
counterparties (degree > 100, i.e. services/exchanges that connect everyone) are excluded
as intermediates, so k-hop follows only *personal* edges and the graph stays fragmented
into per-owner regions. **Honest caveat:** as k grows, that hub-excluded reachability
approaches "same non-hub-connected region," a coarser statement than fine link
prediction — legitimate entity recovery without co-spend, but at k=4 it is closer to
component membership than to a pairwise structural tell. (2023's 1.00 also rests on only
111 pairs.)

## Honest limits

- **One slice, one era.** 5 blocks of 2016. A multi-era / larger connected graph would
  strengthen (and possibly weaken, for modern low-reuse txs) the number. This is a
  demonstration on real data, not a whole-chain claim.
- **Labels are co-spend**, near-certain but not perfect (a collaborative transaction in the slice would
  be a false merge; 2016 has few). An *independent* entity label (exchange tags) would let
  us test the stronger claim — structure links entities co-spend leaves **separate** — which
  this self-contained design cannot (no external labels; the standing data wall).
- **Link-prediction feature is common-neighbors**, deliberately simple/stdlib. Community
  detection (Louvain) or embeddings would be a richer follow-on, not needed for the premise.
