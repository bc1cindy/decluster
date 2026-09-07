# Is the pseudonym graph a social network in any era?

**Why sweep eras.** `RESULTS-graph-shape.md` found the 2026 pseudonym graph is not a social
network — clustering far below chance, disassortative — which explains the social-graph
attack's failure. But that could be a property of the 2026 chain (segwit, taproot, privacy
tooling, little address reuse) rather than of Bitcoin graphs generally. The framework's claim
is about "today's transaction graph"; the test that decides it is whether the precondition ever held.
2016 is the sharp case: heavy address reuse, and the era where `RESULTS-graph-deanon.md`
measured structural same-owner prediction at AUC 0.95.

**Data.** One contiguous ~2-day window (288 blocks) per era, contracted with the refusing
clusterer, measured with `decluster/graph_shape.py` and the statistical (epsilon,
delta)-sparsity of `decluster/def1_sparsity.py`. 2022 and 2025 exports were still paginating
and are not needed for the conclusion.

## Result

| era | txs | clusters | mean deg | clustering / null | assortativity | tail | stat. sparsity δ(0.99) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2013 | 105 954 | 114 364 | 3.13 | **0.0033** | −0.159 | 3.17 | 0.911 |
| 2016 | 403 021 | 508 525 | 3.10 | **0.0101** | −0.076 | 2.99 | 0.882 |
| 2019 | 588 971 | 727 182 | 2.84 | **0.0166** | −0.071 | 3.27 | 0.905 |
| 2026 | 830 770 | ~404 000 | 2.57 | **0.007 / 0.001** | −0.073 | 3.90 | 0.889 |

(A social network would read clustering / null ≫ 1, positive assortativity, tail 2–3.)

## Reading

**The pseudonym graph is not a social network in any era measured.** Clustering runs 60× to
300× *below* what the degree sequence alone would produce, in every year from 2013 to 2026.
The disassortativity and the near-identical statistical feature space (δ(0.99) ≈ 0.9
throughout) hold across the whole span. The social-graph attack's precondition is absent not
just in 2026 but structurally, across the history of the chain.

**2016 is marginally the most social-network-like, and it is still nowhere close.** Its
ratio, 0.0101, is the highest of the four, consistent with heavy address reuse producing
denser clusters — but it is still two orders of magnitude below the threshold the attack
needs. The AUC-0.95 structural signal `RESULTS-graph-deanon.md` found in 2016 is real, but it
is same-owner *prediction from local neighbourhood overlap*, not the global community
structure the propagation attack rides; the two are different, and this measures the second.

**The trend is mildly upward through 2019, not downward.** 0.0033 → 0.0101 → 0.0166 across
2013–2019, then 2026 lower. So there is no clean "the graph became less matchable over time"
story; the ratio moves within a narrow band far below 1, and the qualitative verdict —
not a social network — is invariant. The framework's *strong* social-graph route — cascade to most of the graph — is held back
by a structural property of the transaction graph that has held for over a decade; the
modest route (high-confidence links feeding clustering) is what the graph does support.

## Where this leaves the two attacks

Combined with `RESULTS-ancestry-sparsity.md`, the picture is now consistent and complete for
this data:

- **social-graph matching (cit. 24):** the pseudonym graph lacks the social-network
  structure in every era, so the *strong* form of this route — cascading propagation that
  recovers most of the graph — does not ignite. Its *modest* form does: `view_match` still
  recovers a few high-confidence links above a degree baseline, which is exactly what the
  framework claims for it ("high confidence links... can feed into other clustering
  heuristics"). The measurement confirms the modest claim and finds the strong claim's
  precondition absent from the topology.
- **sparse-dataset / record linkage (cit. 19–20):** precondition (a sparse feature space)
  holds — in the *ancestry* features, not the statistical or topological ones. This route is
  the applicable one, and it is `propagate.py`'s.

## Scope

Four eras, one ~2-day window each, one clusterer. The clustering coefficient is a sampled
estimate (20 000 vertices). The window sizes differ in tx count across eras (chain grew), but
the configuration-model null normalises for density, which is why the ratio is the comparable
quantity. 2022 and 2025 would extend the curve; the four points already settle the
qualitative question.

## Reproducibility / provenance

Not yet filed against `results/REPRODUCIBILITY.md`. This document has not been assigned one of the
five evidence states, so read its numbers as unclassified rather than as any of them.
