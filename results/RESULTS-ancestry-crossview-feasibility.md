# Can ancestry feed the cross-view matcher? Feasibility, and a correction

**Why this was proposed.** The cross-view social-graph matcher built this session scores on
pseudonym-graph neighbourhood topology, and `RESULTS-graph-shape.md` found that topology is
not a social network on this slice. The framework calls structural features "more
importantly" the source of uniqueness, meaning ancestry / deep features. The proposal was to
feed those into the matcher, on the theory that the negative result might be about the chosen
feature rather than the graph.

**Two findings kill the proposal as stated, before any build.**

## The slice is too shallow for ancestry

An ancestry signature walks backward through funding transactions; its power comes from
reaching depth 6 or so, where the set of origin coins becomes a sparse quasi-identifier. On
`slice_2026.ndjson`, of 2 190 883 non-coinbase inputs, **53.6 % have their funder inside the
slice**, which caps the average backward walk at **~2.2 hops** before it truncates on a
missing funder. At that depth the signature is mostly truncation absorbers, not the sparse
high-dimensional vector the attack needs. The ancestry channel is blocked on the same
one-hop-back-and-deeper export the fingerprint channel needs (`RESULTS-refusing-clusterer.md`),
only more so, since it wants many hops rather than one.

## Ancestry belongs to a different attack, already built

The proposal conflated two of the three cited N-S papers. **Cit. 24 (social graph
de-anonymization)** matches two graphs by neighbourhood — the cross-view matcher this session
built. **Cit. 19–20 (sparse dataset / Netflix)** matches records by sparse feature-vector
overlap — which is exactly what ancestry signatures are, and what `decluster/propagate.py`
already implements via `provenance_link`, measured in `RESULTS-ns-propagation.md`
(re-identification rate 0.154 on a bounded real cache sample, 1.0 on the synthetic fixture).

So there is no missing cross-view ancestry experiment to build. Ancestry is the sparse-dataset
attack, and that attack exists and is measured; it is a separate paradigm from the social-graph
cross-view matching, and grafting it onto the matcher as a vertex or edge attribute would hit
the same gate problem `RESULTS-attribute-conditioning.md` already measured — a weak per-vertex
signal that manufactures eccentricity and adds error — on top of being depth-starved here.

## Where this leaves the three N-S papers on this data

| paper | attack | status |
|---|---|---|
| cit. 19–20 sparse dataset | record linkage on provenance signatures | built (`propagate.py`), measured (`ns-propagation`); richer measurement blocked on chain depth |
| cit. 24 social graph | cross-view neighbourhood matching | built (`view_match.py`), measured; precondition fails on this slice (`graph-shape`) |
| cit. 25 link prediction | matching on incomplete graphs | built (`view_match.predict_link`, optional ML callback in the mixed-vote and no-candidate branches); unmeasured on this slice, where predicted edges would be absent rather than censored |

## Recommendation

Nothing cheap remains on this slice. Both open levers — a deeper contiguous export for the
ancestry channel, and a wider-view export for the social-graph channel — need new data, and
the persistence curve already bounds the second's expected gain. The one measurement that could
still overturn the social-graph verdict cheaply would be a *different era or a longer contiguous
window*, but that is a data-collection decision, not a code one. The correct state to stop in is:
the social-graph attack is answered negatively for this regime with a mechanism, the sparse-dataset
attack is a separate already-measured channel, and further progress on either is gated on an export,
not on missing implementation.
