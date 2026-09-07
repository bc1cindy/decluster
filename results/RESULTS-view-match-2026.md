# Cross-view matching on one-day views of the 2026 graph

**Claim tested.** The cited framework argues that fingerprints need not be sparse on their
own, because *if the social network structure is recoverable from the transaction graph,
that will be enough*. That "if" is an untested empirical claim. This tests it: contract two
views of the pseudonym graph, seed a small correspondence, propagate, and measure what
comes back.

**Data.** `slice_2026.ndjson`, views A and B of 144 blocks each (≈1 day), one week apart,
830 770 transactions. Both contracted against one global clustering, then view B relabelled
with opaque ids and the true correspondence withheld for scoring. 33 033 vertices are
present and linked in both views; 5 132 hold degree in [3, 100] in both, the population a
seed can be drawn from and propagation can act on. `examples/view_match_run.py`.

**Seed.** Self-identifying and label-free: mining pools announce themselves in the coinbase
tag. Only 1 pool payout cluster lands in the seedable band, so the seed is topped up by
degree within that band.

## Result

| seed | matched | correct | precision | matched per seed |
|---:|---:|---:|---:|---:|
| 40 | 5 | 4 | 0.800 | 0.125 |
| 100 | 34 | 21 | 0.618 | 0.340 |
| 400 | 146 | 83 | 0.568 | 0.365 |
| 1 000 | 230 | 111 | 0.483 | 0.230 |
| 2 500 | 338 | 164 | 0.485 | 0.135 |

At seed 400: **148 matched, 85 correct, precision 0.574**; the shuffle control, scoring the
same matches against a random bijection, is **0 correct, precision 0.000**; seed-only
propagation contributes nothing by construction.

## Reading

**A framing correction, added after the fact.** The absence of a cascade is measured
correctly below, but it was judged against a stricter criterion than the source states.
The framework explicitly anticipates that "a proliferation of pseudonyms may limit the
effectiveness of this approach for any particular run of the propagation algorithm" and
locates the value in the *high confidence* links that feed other clustering heuristics.
Precision stratified by the matcher's own confidence is the criterion it actually states,
and it is measured in `RESULTS-match-confidence.md`: 0.727 at eccentricity 5, ten of ten
above eccentricity 10. Read what follows as a result about coverage, not about the attack.

**The signal is real.** Precision between 0.48 and 0.80 against a shuffle control of
exactly zero, over a candidate set of 33 033. Structure does carry identity across the
boundary, and the matcher finds it.

**The cascade does not ignite.** Matches per seed peak at 0.365 and then *fall*. A
propagation that was self-sustaining would show each seed unlocking more than itself and
the yield rising with the matched region; instead it saturates below 0.4 and decays.
Seeding 2 500 of the 5 132 seedable vertices, roughly half the usable population, returns
338 matches of which 164 are correct.

**Precision degrades as the seed grows**, 0.80 down to 0.485. The later matches are made on
thinner evidence, so pushing for coverage buys errors rather than reach.

**The mechanism is neighbourhood persistence, and it is the binding constraint.** The 400
seeds have 15 324 neighbours between them, of which only **2 135 (14 %) exist and are
linked in both views** and only 1 205 reach degree 3. The frontier collapses on its first
step: 86 % of a vertex's counterparties in one day are one-offs that never reappear a week
later. The framework's mechanism requires *recurring* relationships, and at a one-day view
width most relationships do not recur.

## What this does and does not establish

It establishes that on **one-day views** of the 2026 transaction graph, seeded propagation
recovers a real but small correspondence and never becomes self-sustaining, and it
identifies why.

It does not establish that the graph is unrecoverable. View width is the obvious untested
lever and the measurement points straight at it: the framework's own argument is that the
more consistent an entity's activity, the more stable its representation, and a one-day
window samples too little of that activity for a neighbourhood to be distinctive. Wider
views should raise both persistence and degree. Testing that needs a degree-filtered
contraction, since the graph structures for a 144-block epoch already run to ~4.3 GB and a
week-wide view would not fit.

Three further caveats, each removable. The clustering is naive common-input union-find, the
adversary the framework calls incompetent; `cluster_refined`, which can refuse a co-spend,
would change the vertex set. Only one partition scheme is exercised here (epoch); the
ambiguity cut the framework prefers is not. And this is a single pair of views in a single
month.

## Correction

The first run of this experiment returned one match and was invalid. The seed had been
topped up with the highest-degree vertices, which are exactly the hubs the matcher refuses
to route through, so 34 of 40 seeds were invisible to it. The seed selection now draws from
the non-hub band. The failure was in the experiment, not in the graph.

## Reproducibility / provenance

State 2 in `results/REPRODUCIBILITY.md`: the mechanism is pinned; the reported numbers come from a data-run over `slice_2026.ndjson`, which is not committed, and are not asserted.

The *direction* read off these numbers is not established: the policy flags "cross-view matcher
precision vs baseline" as owing a migration to state 1 or state 5.
