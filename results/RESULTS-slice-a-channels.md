# The entity-attribute and social-graph channels on a real slice

> The reproducible six-block observations are recalculated by
> `catalog/runs/slice-channels-v1.json`. Its structured artifact is
> `results/artifacts/slice-channels-v1.json`, with canonical rendering in
> `results/generated/slice-channels-v1.md`. Measurements below for the 150.000-transaction and
> 947.000-transaction slices are historical because their exact inputs were not preserved. The
> canonical run measures attribute density and graph shape; it does not measure graph-matching
> success or a privacy score.

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
contracted into a pseudonym vertex (`views.contract`).

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

| min_degree | eligible vertices | delta(0.5) | delta(0.9) | delta(0.99) | median top-sim |
|---:|---:|---:|---:|---:|---:|
| 2 | 8,398 | 1.000 | 1.000 | 0.990 | 1.000 |
| 3 | 4,423 | 1.000 | 0.997 | 0.984 | 1.000 |
| 5 | 641 | 1.000 | 0.986 | 0.949 | 1.000 |
| 10 | 231 | 1.000 | 0.965 | 0.922 | 0.999 |
| 20 | 89 | 1.000 | 0.921 | 0.854 | 0.999 |

Density falls with degree but never approaches sparsity: even the 89 best-connected entities almost
all have a near-twin at epsilon 0.9. Pinned as a band in `tests/test_slice_a_channels.py`.

## 2. The pseudonym graph is transactional, not social

The cross-view attack (cit 24) re-links a user whose activity a partial clustering left as separate
pseudonyms across two time views. The honest form of the test splits each cluster along the view
boundary (`split_clusters_by_view`): the cluster becomes one pseudonym in view A and another in view
B, and the matcher must rejoin the two from graph structure alone. Each view is contracted under its
own lookup — tagging an address by where it is first seen instead leaves an address used in *both*
windows marked `#a` everywhere, so view B holds `C#a` as well as `C#b` and the identity match, which
is graded wrong, is the structurally better one. The figures below predate that fix (2 Sep 2026) and
are superseded; see `RESULTS-multiepoch-local-2016.md` for the corrected construction.
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
