# Can the matcher join a user's separate pseudonyms?

**Why this is the question.** Every earlier run contracted both views from one clustering,
so a correct match linked a cluster to *itself*. That recovers the identity map, which the
adversary already holds; it is not new information and could feed nothing back into its
heuristics. Worse, precision defined as identity counted as an error the one outcome the
attack exists to produce. The framework's claim is specific: *"So long as the adversary
still hasn't collected enough evidence to conclude that several clusters belong to the same
user, that user still enjoys pseudonymity."* Breaking that means joining two pseudonyms of
one user, and nothing measured so far had tested it.

**Method.** Clusters are deliberately split before contraction, so the adversary's
clustering is incomplete in the way the framework assumes, and the answer is known. Three
outcomes: identity (a pseudonym matched to itself, correct but already known),
rejoin (matched to the other half of its own cluster — the discovery, and the only
outcome worth feeding back), and error. The seed is drawn only from *intact* pseudonyms:
seeding from a split cluster would hand the adversary the answer it is meant to find.

## Result

| split | clusters split | seed | matched | identity | **rejoin** | error | rejoins per split cluster |
|---|---:|---:|---:|---:|---:|---:|---:|
| random, half | 27 871 | 400 | 67 | 47 | **2** | 18 | 0.007 % |
| boundary, all | 2 986 | 361 | 53 | 29 | **4** | 20 | 0.13 % |
| boundary, half | 1 474 | 400 | 84 | 47 | **1** | 36 | 0.07 % |

At eccentricity ≥ 5 the rejoin counts are 1, 1 and 1 respectively.

## Reading

**The discovery almost never happens.** Across every configuration the matcher produces
between one and five genuine new links, from thousands of users whose pseudonyms were
separated. Under the sharpest test, 2 986 users split across the view boundary, it joined
four. Ninety-nine point nine percent kept their pseudonymity.

*(Re-run on the graph corrected in `RESULTS-graph-shape.md`; the pre-fix figure was five of
2 986. The correction does not touch the conclusion.)*

**Seed starvation does not explain it.** Splitting consumes exactly the spanning clusters
that make good seeds, so the boundary runs are seed-poor by construction and that is the
obvious alternative explanation. Halving the split doubles the intact pool, from 381 to 959,
and the rejoin rate *falls*. More seed did not buy discoveries.

**The first design was wrong and its number should not be used.** Splitting by drawing
addresses at random leaves both halves present in both views, so the identity match remains
available and is structurally easier than the rejoin while being equally correct. That
design puts the right answer in competition with an easier one. Splitting along the view
boundary removes the escape, one pseudonym on each side, and the rejoin rate triples, from
0.007 % to 0.17 % per split cluster. The low rate in the first run was measuring the design,
not the graph.

**Errors dominate the new information.** In the boundary runs, 34 % and 43 % of matches are
outright wrong against 9 % and 1 % rejoins. A channel fed from this output would carry far
more error than discovery unless restricted to the high-confidence band, where the counts
fall to a single rejoin per run.

## Consequence for feeding a clustering channel

This was the last step of the planned programme, and it is now answerable rather than
assumed. The channel is buildable and would be nearly empty: on the order of one
high-confidence new link per two-day slice, against thousands of opportunities. The
weighting question from `RESULTS-match-confidence.md` is therefore moot at this scale, not
because the links are unreliable but because there are almost none of them.

## Scope

Two-day views, which `RESULTS-persistence-curve.md` identifies as the weak regime: 31 % of a
vertex's neighbours recur, rising only to 38 % at a week and saturating there. A single
slice, a single month, one partition scheme, and a clustering whose refusal channels were
separately measured to be inert on this data. The result bounds what this method achieves in
this regime; it does not establish that no regime works, and the persistence curve says
which lever remains untested.

## Reproducibility / provenance

State 2 in `results/REPRODUCIBILITY.md`: the mechanism is pinned; the reported numbers come from a data-run over the two-day slice, which is not committed, and are not asserted.
