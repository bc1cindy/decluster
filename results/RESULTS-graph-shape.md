# Is the pseudonym graph a social network?

**Why this is the question under all the others.** The framework asserts that the
contracted cluster graph, under an incomplete clustering, "is a social network per
Shmatikov and Narayanan's definition." Everything the matching does rests on that: the N-S
algorithms were validated on social graphs, and a social graph is heavy-tailed, clustered
far above chance, and assortative — a vertex sits in a tight neighbourhood of well-connected
vertices, which is what lets its neighbours identify it. This is the one premise of the
whole programme that had been asserted rather than measured.

**Data.** `slice_2026.ndjson`, refusing clusterer, the two contracted views. Each statistic
is reported against a configuration-model null with the same degree sequence, because the
raw value alone conflates structure with mere density; the null answers "more than the
degrees alone would produce?". `decluster/graph_shape.py`.

## Result

| statistic | view A | view B | a social graph |
|---|---:|---:|---|
| vertices | 403 963 | 394 989 | |
| edges | 525 010 | 506 447 | |
| mean degree | 2.57 | 2.54 | higher |
| degree-1 share | 0.583 | 0.594 | low |
| transitivity (clustering) | 0.0030 | 0.0005 | high |
| configuration null | 0.428 | 0.355 | |
| **clustering / null** | **0.007** | **0.001** | **≫ 1** |
| assortativity | −0.072 | −0.074 | positive |
| degree tail exponent | 3.90 | 3.94 | 2 – 3 |

## Reading

**It is not a social network, on every axis at once.**

- **Clustering is ~140× and ~700× *below* chance.** A real social graph clusters far above
  what its degree sequence forces; this one clusters more than two orders of magnitude
  *under* it. Its friends-of-friends are systematically not friends. This is the community
  structure the framework's argument depends on, and it is absent — worse than absent, it is
  actively suppressed relative to a random graph with the same degrees.
- **The graph is mildly disassortative** (−0.07), the sign transactional and technological
  graphs carry, not the positive sign of a social graph. Its hubs attach to leaves.
- **The degree tail is too steep** (3.9 against the social 2–3), and **58 % of vertices are
  leaves.** The heavy tail of well-connected nodes that N-S propagation rides is thin here.

**This explains the whole series of negatives at once, at the level of a missing
precondition.** The frontier collapsed (`RESULTS-view-match-2026.md`), the ambiguity cut
would not decompose the graph (`RESULTS-partition-schemes.md`), attributes only added error
(`RESULTS-attribute-conditioning.md`), and the rejoin almost never fired
(`RESULTS-rejoin.md`). These are not four independent disappointments. They are what a
matching algorithm designed for social graphs does when handed a graph that is nearly a tree
of one-shot transfers: there is no community structure to propagate through, because at this
timescale the graph does not have any.

**And it says which of the remaining levers can and cannot help.** A wider view raises degree
but does not manufacture clustering where transfers are genuinely one-shot; the persistence
curve already showed the recurrence rate saturating at 38 %. Link prediction assumes a true
graph whose edges are censored, but these edges are not censored, they are absent, so
predicting them would invent economic activity that did not happen. Neither lever supplies
the missing precondition. The precondition is a property of the transaction graph itself, and
the only thing that changes it is the transaction graph becoming more interwoven — which is
exactly the defence the framework argues for in its closing section.

## What would change the verdict

The measurement is of two-day views in one month under one clusterer. The precondition could
hold at a longer timescale if recurring economic relationships accumulate faster than the
graph grows, but the persistence curve is evidence against that, and the clustering deficit
here is so large that closing it by a factor of a hundred-plus is a different regime, not a
tuning. A denser clusterer (the fingerprint channel, which needs a one-hop-back export) would
raise degree and could raise clustering; whether it moves the ratio above 1 is the one open
empirical question this leaves, and it is a sharper question than "try a wider view".

## Note on a bug this measurement caught

The first run of this reported 3.9 million edges and mean degree 19, four times the truth.
`contract` was asserting an edge from every source pseudonym to every output, which is a
no-op under the naive clusterer (one source per transaction) but explodes under the refusing
one: 211 coinjoins with six or more source pseudonyms generated 77 % of the edges, inventing
in a coinjoin the very relationship the construction is defined not to have. Fixed by treating
a multi-source transaction's transfers as unattributable. Every earlier result run on the
refusing clusterer stood on that inflated graph and is being re-checked; the results on the
naive clusterer, and the address-level and no-contraction measurements, are unaffected.
