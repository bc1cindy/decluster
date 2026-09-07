# Candidate-set intersection: the mechanism, and what is not claimed for it

`decluster/baselines/candidate_set_intersection.py` implements the cross-transaction intersection
attack described by Goldfeder, Kalodner, Reisman and Narayanan: a coin's plausible origins form a
*set*, coins later shown to be held by the same party must have come from a common origin, and what
survives is the intersection of their sets.

## What this document does not claim

The primary text is now available and Algorithm 2's graph-independent core is implemented. The
paper's JoinMarket dataset, figures and empirical rates are not reproduced, and no measured
rate on this page is attributed to Goldfeder et al. The kernel cell is closed; empirical parity is
not.

The baseline also states no shrink law. The reading that each observation cuts the candidate set
by a constant factor is not Goldfeder's — the intersection paper demonstrates the attack and states
no such law — and it is not sourced anywhere else here either. It was previously credited on this
page to "Danezis and Serjantov's statistical-disclosure result", which does not exist: statistical
disclosure is Danezis alone, and the one paper by both authors that could have carried it, *Statistical
Disclosure or Intersection Attacks on Anonymity Systems* (IH 2004), was obtained and read in full. It
is Bayesian throughout and states no constant-factor law; its §7 says in the authors' own words that
analytic representations "would allow us to calculate the number of rounds", which is to say they did
not have them. The statistical-disclosure line of work bounds the observations an adversary needs by a
signal-to-noise condition and a confidence interval, not by a constant factor per observation.
`decluster/intersect.py` and `decluster/baselines/candidate_set_intersection.py` carry the same
distinction, and the numbers below are properties of a constructed family, not of any observed shrink
rate.

## Scope

The generic primitive takes candidate sets. `goldfeder_cluster_intersection` additionally constructs
them at Algorithm 2's abstraction boundary: injected join-only predecessor edges, a bound `r`, and
an injected wallet-cluster function. Join detection, recursive address clustering, and the auxiliary
observation that the coins are co-held remain caller responsibilities. The baseline imports no
ancestry walk, fetcher, or engine from this repository.

Three answers are possible, and the third matters most:

| answer | shape | reported as |
|---|---|---|
| identified | exactly one candidate survives a consistent run | `identified` = that candidate |
| narrowed | more than one survives | a set; `identified` is `None` |
| refused | the intersection is empty | `inconsistent_at`, `identified` `None`, bits `None` |

An empty intersection means the observations contradict each other — a candidate set is wrong, or
the coins were not co-held. It is a refusal, never an identification, and it is never reported as an
unbounded narrowing: `narrowing_bits` comes back `None` rather than infinite, so the strongest
evidence that the premise broke cannot be read as the strongest claim. A run that hits a
contradiction also stops there, rather than absorbing later observations that cannot narrow an empty
set.

## The constructed family

`candidate_set_intersection.scenarios()` is a deterministic family of **3** longitudinal runs over
one universe of `universe_size` = **64** candidates, **13** observations supplied in total. It is a
fixture for this document, not a claim about chain data, and the sizes are chosen so a reader can
check every row by hand.

### converging — successive observations narrow to one

Six observations, each half the size of the last, all containing candidate `0`.

| observation | observed | before | after | bits |
|---:|---:|---:|---:|---:|
| 0 | 32 | 64 | 32 | 1.0 |
| 1 | 16 | 32 | 16 | 1.0 |
| 2 | 8 | 16 | 8 | 1.0 |
| 3 | 4 | 8 | 4 | 1.0 |
| 4 | 2 | 4 | 2 | 1.0 |
| 5 | 1 | 2 | 1 | 1.0 |

`converging_survivors` = **1**, `converging_identified` = **0**, `converging_bits` = **6.0**. This is
the attack's whole shape: no single observation names the origin, and together they do.

### stalled — observations that do not converge

Four observations of the same 8 candidates.

| observation | observed | before | after | bits |
|---:|---:|---:|---:|---:|
| 0 | 8 | 64 | 8 | 3.0 |
| 1 | 8 | 8 | 8 | 0.0 |
| 2 | 8 | 8 | 8 | 0.0 |
| 3 | 8 | 8 | 8 | 0.0 |

`stalled_survivors` = **8**, `stalled_bits` = **3.0** — all of it from knowing the universe, none of
it from repetition. `identified` is `None`: eight survivors identify nobody, and the result stays a
set rather than being rounded to a name.

The first row is the reason `universe_size` is an input at all. A first set of 8 out of 64 has
already said 3 bits; without the universe there is nothing to measure that against, and the run says
so by carrying no bits for its first step rather than inventing a baseline for it.

### contradictory — the refusal

| observation | observed | before | after | bits |
|---:|---:|---:|---:|---:|
| 0 | 8 | 64 | 8 | 3.0 |
| 1 | 8 | 8 | 0 | — |

`contradictory_survivors` = **0**, `contradictory_inconsistent_at` = **1**, and
`narrowing_bits` is `None`. A third observation was supplied and was never consumed: the run stops
at the contradiction.

Across the family: `identifications` = **1**, `refusals` = **1**.

## Relationship to `decluster/intersect.py`

`decluster/intersect.py` stays, unrenamed, and is not replaced by this baseline. The two are
different objects:

- This module is the published mechanism in outline, standalone, over abstract candidate sets.
- `intersect.py` is this repository's wiring of that mechanism: origin sets from the backward
  absorbing walk, rarity weighting, cluster-lift, truncation and blindness reporting, and
  subordination to `cluster_refined`. Those additions are this repository's, not the paper's.

The primary text has now been checked. `goldfeder_cluster_intersection` implements Algorithm 2's
join-only backward paths bounded by `r`, wallet-cluster lift, intersection, and unique-or-refuse
verdict over injected join-graph and clustering callbacks. The 2015–2017 JoinMarket simulation and
its empirical rates have not been reproduced. `decluster/intersect.py` is a different, adapted
pipeline: it uses a probabilistic ancestry walk that is not restricted to join paths and adds engine
gating, rarity weights and blindness accounting.

## Reproduce

```python
from decluster.baselines import candidate_set_intersection as csi

for name, observations in csi.scenarios():
    print(name, csi.intersect_candidate_sets(observations, universe_size=csi.UNIVERSE))
print(csi.manifest_invariants())
```

`tests/test_candidate_set_intersection.py` recomputes every invariant above and checks it against
`results/manifests/RESULTS-candidate-set-intersection.json`, so a drifting number fails loudly
instead of standing on this page.
