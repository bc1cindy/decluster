# (epsilon, delta)-sparsity of cluster features: the attack's own precondition, measured

**Why this is load-bearing.** The sparse-dataset de-anonymization the framework builds on
defines its precondition precisely: a record space is (epsilon, delta)-sparse if a random
record has probability at most delta of having any other record more than epsilon-similar
to it. The authors measure it as a survival curve of each record's nearest-neighbour
similarity (their Figure 1), and state that where the space is *not* sparse, the matching
set fills with false matches and the attack cannot single anyone out. A failed attack is
"expected" unless the data is shown to be sparse this way. Until now this session measured
proxies; this is the operational test.

**Method.** A record is a cluster; its feature vector is the statistical fingerprint
distributions plus coarse structural descriptors (degree, tx count, log-binned
neighbour-degree histogram). Nearest-neighbour similarity is estimated per the quadratic
cost: 3 000 query clusters against a 30 000 background sample, cosine similarity, top per
query. `slice_2026.ndjson`, refusing clusterer, one view. `decluster/def1_sparsity.py`.

## Result

| epsilon | delta (min_degree 1) | delta (min_degree 3) |
|---:|---:|---:|
| 0.5 | 1.000 | 1.000 |
| 0.7 | 1.000 | 1.000 |
| 0.9 | 0.981 | 0.981 |
| 0.95 | 0.929 | 0.896 |
| 0.99 | 0.889 | 0.731 |

Median nearest-neighbour similarity: **1.000**.

The Netflix Figure-1 baseline the method comes from: the vast majority of records had no
peer above similarity 0.5. Here every cluster has a peer above 0.5, and ~89 % have a near
identical twin above 0.99. The space is maximally **non-sparse**.

## Reading

**The statistical + coarse-structural feature space is not sparse, by the authors' own
definition.** This is the operational confirmation of `RESULTS-fingerprint-sparsity.md` and
of the concession the framework itself makes — "wallet fingerprints and other statistical
features of clusters might not be sparse on their own." It is the precondition of the
sparse-dataset attack, and on this feature set it fails.

**But this tests the space the framework concedes, not the one it relies on.** The feature
vector here is low-dimensional: four fingerprint axes and a handful of coarse structural
bins. The paper's sparsity comes from *high* dimensionality — hundreds to thousands of
observations per record. The framework locates the sparse, unique signal in the
**structural / deep features** (ancestry), which are the high-dimensional ones. Those are
absent from this vector, because ancestry walks reach only ~2.2 hops on a two-day slice
(`RESULTS-ancestry-crossview-feasibility.md`). So this result confirms the conceded half
and leaves the load-bearing half — is the *ancestry* feature space (epsilon, delta)-sparse?
— unmeasured.

## Consequence for the plan

This reorders the priorities stated earlier. The deep contiguous export, previously ranked
last as "engineering, not collection," is what unblocks the single measurement the authors
define as decisive: the (epsilon, delta)-sparsity survival curve over ancestry signatures.
If that space is non-sparse too, the attack's precondition fails on the feature the
framework calls most important, and the negative is complete and clean. If it is sparse,
then the attack's failure on this graph is the surprising result, and the reason lies in
the graph's topology (`RESULTS-graph-shape.md`), not its feature sparsity — a genuinely
interesting split. Either outcome is a real finding; neither can be had without the export.

## Scope

One slice, one era, one feature construction. The survival curve is a sampled estimate
(3 000 queries, 30 000 background), reported as such. The structural descriptors are a weak
proxy for the ancestry features the framework means; the result bounds the low-dimensional
space and does not speak to the high-dimensional one.
