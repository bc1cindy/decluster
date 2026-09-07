# Comparing partition schemes

**Why ask.** The framework names the epoch partition as its trivial example and proposes a
better one: *"the adversary decomposes the cluster graph along a high ambiguity cut, such
that each component is relatively sparser, and then matching these components."* Epoch was
the only scheme ever run. `RESULTS-match-confidence.md` supplies the criterion to compare
on: not coverage, but how many links a scheme yields above an eccentricity threshold, since
those are the links the framework says feed other clustering heuristics.

**Schemes.** *epoch*, split by block height. *coinjoin seam*, the same split with
coinjoin-shaped transactions removed from both sides, since a coinjoin is where co-spending
stops implying common ownership. *ambiguity cut*, read literally as the opposite of expander
decomposition: remove the densest region, which is where every vertex looks like its
neighbours and identity is most ambiguous, and take the connected components it leaves.

**Data.** `slice_2026.ndjson`, refusing clusterer, seed 400, threshold eccentricity ≥ 5.

## Result

| scheme | views | spanning | seedable | matched | correct | links at ecc ≥ 5 | correct | precision |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| epoch | 403 963 / 394 989 | 32 857 | 5 124 | 147 | 83 | 57 | 40 | 0.702 |
| coinjoin seam | 389 263 / 383 115 | 32 843 | 5 118 | 147 | 83 | **58** | **41** | **0.707** |
| ambiguity cut | 195 197 / 352 | **1** | 0 | 0 | 0 | 0 | 0 | — |

*(Re-run on the graph corrected in `RESULTS-graph-shape.md`. The ambiguity cut's structural
failure is unchanged, as expected: whether multi-source transfers assert edges does not
affect whether the graph decomposes. Epoch and coinjoin-seam precision moved by under two
points and remain indistinguishable.)*

Sweeping the fraction of addresses treated as the dense core:

| core fraction | transactions cut | largest component | second | second / largest |
|---:|---:|---:|---:|---:|
| 0.1 % | 564 578 (68 %) | 266 490 | 411 | 0.0015 |
| 0.5 % | 677 985 (82 %) | 152 478 | 929 | 0.0061 |
| 1 % | 715 481 (86 %) | 115 961 | 209 | 0.0018 |
| 5 % | 788 214 (95 %) | 42 917 | 344 | 0.0080 |
| 10 % | 816 391 (98 %) | 13 982 | 1 107 | 0.079 |
| 25 % | 831 566 (99.98 %) | 113 | 53 | 0.469 |

## Reading

**The ambiguity cut fails, and not because the threshold was wrong.** No fraction produces
two comparable components. The ratio of second to largest stays near zero until the graph
has been destroyed: at 25 % the components are finally comparable, and the largest holds
113 transactions out of 831 770. This is the ordinary behaviour of a scale-free graph, which
keeps one giant component through hub removal and then crumbles to dust rather than
splitting in two.

**Removing even a tenth of a percent of addresses cuts 68 % of transactions.** The busiest
addresses touch most of the graph, so the cut is never a thin boundary; it swallows the data
before it separates anything.

**And there is a tension underneath the arithmetic.** A partition into *disconnected*
components cannot have entities spanning it, because a cluster with coins in two components
would join them. The correspondence the matcher recovers is exactly an entity appearing in
both views, so decomposing into components destroys the thing being looked for. One
spanning cluster out of 33 114 is that argument made concrete. The epoch partition works
precisely because it is *not* a graph decomposition: it is a time slice, and one entity is
in both slices with different neighbourhoods.

This does not settle what the source intends, and the sentence admits more than one reading.
What is measured here is that the literal reading, a decomposition into sparser components
matched against each other, is not available on this graph at any threshold, for a
structural reason rather than a tuning one.

**The coinjoin seam and epoch are indistinguishable**, 58 links against 57 and precision
0.707 against 0.702. At these counts the gap is noise and should not be read as a ranking. It is worth noting
only because it is the framework's own prescription for the cautious adversary, declining
CIOH inside a coinjoin while still matching the graphs on either side, and it costs nothing:
it does the same work on 5 % fewer vertices.

## Scope

One operationalisation of ambiguity, density, chosen because the framework's own analogy is
to expander decomposition. Other signals may behave differently, and the amount-side
ambiguity the source discusses at length is only defined for 2-in/2-out transactions, 5.6 %
of this slice, too thin to cut on. The structural objection above is not specific to the
signal: it applies to any reading that partitions into disconnected components.

## Reproducibility / provenance

State 2 in `results/REPRODUCIBILITY.md`: the mechanism is pinned; the reported numbers come from a data-run over `slice_2026.ndjson`, which is not committed, and are not asserted.
