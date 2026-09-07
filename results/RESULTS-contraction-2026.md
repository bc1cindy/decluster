# Contracting a 2026 slice into two pseudonym-graph views

**What this builds.** The cited framework's construction: contract the cluster-annotated
coin graph so each cluster becomes one vertex, leaving transfers as the residual edges.
Under a partial clustering the result is a pseudonym graph, the object the matching
algorithm consumes. Contraction yields a multigraph; the parallel transfers between one
ordered pair are folded into a single attributed directed edge, per the model's own
footnote.

**Data.** `slice_2026.ndjson`: blocks 939 969–940 112 (view A) and 940 977–941 120
(view B), one week apart, 830 770 transactions. Two streaming passes, 44 s.
`examples/contract_slice.py`.

## Result

Global clustering over the whole slice: **633 933 addresses in 55 850 clusters** of two or
more, largest 30 304 addresses.

| | view A | view B |
|---|---:|---:|
| vertices | 395 547 | 389 908 |
| edges | 534 652 | 515 022 |
| mean degree | 2.68 | 2.62 |
| median / p90 / max degree | 1 / 3 / 15 638 | 1 / 3 / 13 408 |
| edges folding more than one transfer | 38 257 (7.2 %) | 36 251 (7.0 %) |

**Vertices present and linked in both views: 33 033.** Their mean degree in A is **8.68**
(median 2, p90 5), and **5 468** hold degree ≥ 3 in *both* views.

## Reading

**Contraction roughly doubles degree, on the population where that matters.**
`RESULTS-slice-gate-2026.md` measured mean out-degree 4.81 at address level among the
45 105 spanning addresses; the same population after contraction reads 8.68. The
whole-graph mean of 2.68 is *lower* than 4.81 and does not contradict it: it averages over
360 000-odd singleton pseudonyms, addresses the partial clustering never touched, which are
mostly degree-1 leaves. The two numbers describe different populations and only the
spanning one is the comparison the gate was making.

**The matchable population is 5 468 vertices, not 33 033.** Degree ≥ 3 in both views is the
condition under which a vertex has a neighbourhood distinctive enough for propagation to
work on. Everything above that is spanning material; this is the part with structure.

**Folding is doing real but minority work.** 7 % of ordered pairs carry more than one
transfer, so most cluster relationships in a single day are one-shot. The attributes that
folding preserves (how many transfers, how much value) therefore separate a small,
presumably more meaningful subset of edges rather than describing the typical one.

**Degree is heavy-tailed and the tail is dangerous.** Median 2 against a maximum of 15 638,
alongside a 30 304-address cluster, means a handful of hubs dominate. `graph_deanon` already
refuses to expand through nodes above degree 100 to avoid small-world collapse; the matcher
needs the same guard, or propagation will route through a hub and match everything to
everything.

## Scope, and one deliberate simplification to remove

The clustering here is naive common-input union-find, which is precisely the adversary
the framework calls incompetent. That simplification has since been measured rather than
left standing: `RESULTS-refusing-clusterer.md` measured a refusing clusterer against this slice
and found it left the 30 304-address cluster byte-identical, so the suspicion above is narrowed
rather than confirmed. **How narrow is now open.** That measurement put the refusal at 0.33 % of
merge decisions, but it ran before `monitor.is_coinjoin` gained its equal-output arm and over a
slice file no longer in the checkout, so the share is pending re-execution and should not be cited;
on the slice that can still be measured the current rule is about 2.2x wider. The refusal that
would bear on the mega-clusters is in any case the fingerprint channel, which compares *funding*
transactions lying outside a two-day slice.

Vertex attributes are stored as raw counts against each view's own base rates, never as
bare shares, because a median 54 % of an axis value's variance tracks epoch volume
(`RESULTS-attribute-drift.md`). No matching is performed here; this builds and measures the
object a matcher would run on.
