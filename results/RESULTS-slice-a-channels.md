# Structural density and graph shape on a real slice

> The reproducible six-block observations are recalculated by
> `catalog/runs/slice-channels-v1.json`. Its structured artifact is
> `results/artifacts/slice-channels-v1.json`, with canonical rendering in
> `results/generated/slice-channels-v1.md`. Measurements below for the 150.000-transaction and
> 947.000-transaction slices are historical records, not evidence, because their exact inputs were
> not preserved. The canonical run measures structural density and graph shape on 12,000
> transactions. Its source has no construction attributes, so it does not measure attribute density,
> graph-matching success or a privacy score.

**What this measures.** The reid capstone (`RESULTS-reid.md`) established that the *ancestry* feature
space is (epsilon, delta)-sparse and de-anonymizes (~0.94 on sparse coins). This measures the other
two channels an adversary can read off the graph: each entity's *attribute* distributions, and the
*cross-view* structure of the pseudonym graph. The attribute space is dense, and the contracted graph
is transactional rather than social, so on this slice neither channel de-anonymizes by itself.

**Data.** A contiguous 2016 slice, blocks 400000-400600 (601 blocks, ~947k transactions, ~860k
addresses), exported at address level via `bigquery/graph.sql` and collected with
`examples/bq_chunk_download.py` (chunked, no billing). Numbers below are the 150k-transaction working
slice (blocks 400000-~400100) unless the full 947k slice is named. Addresses are clustered with the
engine's refuse-guarded common-input clustering (`views.cluster_addresses`) and each cluster
contracted into a pseudonym vertex (`contraction.contract`).

## 1. Entity attributes are dense

`def1_sparsity` measures each entity's nearest-neighbour cosine over its attribute distributions, the
survival curve `RESULTS-reid.md` uses on ancestry. A sparse space keeps that curve near zero until
epsilon is high. Here it sits near one throughout.

| epsilon | delta (150k slice) | delta (min_degree=10) |
|---|---:|---:|
| 0.5 | 1.000 | 1.000 |
| 0.9 | 0.994 | 0.993 |
| 0.95 | 0.982 | — |
| 0.99 | 0.956 | 0.575 |

Almost every entity has a near-twin at epsilon=0.9, and restricting to well-connected entities
(min_degree up to 10) leaves it there, so the density is not a singleton artefact: an entity's
attribute distribution does not single it out. The channel that does is ancestry, measured separately.

**Correction, 2 Sep 2026.** The table above was measured before `feature_vector` normalised its
neighbour-degree histogram: as a raw count that one component carried almost the whole vector norm at
high degree, so the cosine read degree similarity. Re-measured on the committed fixture with the
corrected vector, the density is *higher* than recorded, and it holds across the degree range:

**Superseded by the correction of 6 Sep 2026 below.**

| min_degree | eligible vertices | delta(0.5) | delta(0.9) | delta(0.99) | median top-sim |
|---:|---:|---:|---:|---:|---:|
| 2 | 8,398 | 1.000 | 1.000 | 0.990 | 1.000 |
| 3 | 4,423 | 1.000 | 0.997 | 0.984 | 1.000 |
| 5 | 641 | 1.000 | 0.986 | 0.949 | 1.000 |
| 10 | 231 | 1.000 | 0.965 | 0.922 | 0.999 |
| 20 | 89 | 1.000 | 0.921 | 0.854 | 0.999 |

**Correction, 6 Sep 2026.** This is not an attribute measurement, and the table above was inflated
by reading absent fields as values. The committed fixture is an address-only export: it carries no
version, locktime, sequence or fee. `locktime_policy` returned `zero` for a missing locktime and
`x_version` returned `vNone`, so all 12,000 transactions agreed on two axes for free and every
feature vector carried the same two components. With the extractors abstaining instead, all four
axes are skipped on all 12,000 transactions — the canonical artifact now reports those counts — and
what remains is the structural vector alone: degree, transaction count, self-transfers and the
neighbour-degree histogram.

| min_degree | eligible vertices | delta(0.5) | delta(0.9) | delta(0.99) | median top-sim |
|---:|---:|---:|---:|---:|---:|
| 2 | 8,398 | 1.000 | 0.998 | 0.983 | 1.000 |
| 3 | 4,423 | 1.000 | 0.995 | 0.977 | 1.000 |
| 5 | 641 | 1.000 | 0.977 | 0.894 | 1.000 |
| 10 | 231 | 1.000 | 0.952 | 0.874 | 0.999 |
| 20 | 89 | 1.000 | 0.876 | 0.798 | 0.999 |

Density still falls with degree and still never approaches sparsity, but the fall is steeper than
recorded: at min_degree 20 the epsilon-0.99 figure moves 0.854 to 0.798. The conclusion this section
draws is unchanged and its basis is narrower — structural similarity on a slice that carries no
attributes, not the entity-attribute channel the heading promises. Pinned as a band in
`tests/test_slice_a_channels.py`.

## 2. The pseudonym graph is transactional, not social

The cross-view attack (cit 24) re-links a user whose activity a partial clustering left as separate
pseudonyms across two time views. The form of the test that does not hand over the answer splits each cluster along the view
boundary (`split_clusters_by_view`): the cluster becomes one pseudonym in view A and another in view
B, and the matcher must rejoin the two from graph structure alone. Each view is contracted under its
own lookup — tagging an address by where it is first seen instead leaves an address used in *both*
windows marked `#a` everywhere, so view B holds `C#a` as well as `C#b` and the identity match, which
is graded wrong, is the structurally better one. The figures below predate that fix (2 Sep 2026) and
are superseded; see `results/generated/graph-rejoin-2016-v1.md` for the corrected construction on
committed data.
(Contracting a complete clustering against itself instead only lets the matcher recover the identity
map, which carries no new information.) On this slice, of 5077 split pseudonym pairs a 5-10% seed
rejoins none (precision 0.000). The graph is disassortative (-0.064, hubs attaching to leaves) with no
clustering beyond what its degree sequence forces, so there is no neighbourhood regularity to
propagate along. The limit is the window: 601 blocks is ~10 days, a pseudonym's view-A neighbours and
view-B neighbours are different one-off counterparties, and a neighbourhood that does not recur cannot
be rejoined. Stable neighbourhoods need relationships that repeat across many epochs, a multi-year
span (§10 of `PAPER.md`); this slice measures the short-window regime only.

## Reading

The three channels an adversary reads off the graph carry different amounts of identifying signal.
Ancestry is sparse and pins a coin to its origin (`RESULTS-reid.md`). Attribute distributions are
dense: an entity's fee, timing, and value habits do not single it out. Cross-view structure is
underpowered on a short window, because recurring relationships have not yet accumulated. An attacker
holding only this slice de-anonymizes through provenance, not through attributes or graph matching.

The full 947k slice holds the same density curve at scale (175293 clusters over 860164 addresses,
1011271 contracted vertices); the 150k slice is the primary because `graph_shape` transitivity is
superlinear on a million-vertex graph.

## Scope, stated plainly

- **The density curve is slice-stable and pinned.** It reproduces on the committed 6-block fixture
  (delta(0.9)=0.996), on the 150k slice, and at full scale. `tests/test_slice_a_channels.py` pins it
  (delta(0.9) >= 0.95) together with the sign of assortativity.
- **The cross-view precision and the transitivity ratio are scale-dependent and are not band-pinned.**
  The transitivity ratio measured 7.0 on 6 blocks, 1.0 on 15 blocks, and 0.0 on 150k, so only the
  direction (negative assortativity, a dense attribute space) is committed as a test. The precision
  figures above read one short window, not a chain-wide rate.
- This is one era (2016), and one time span. The long-run cross-view result is a separate measurement
  on the multi-year collection.
