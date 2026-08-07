# Intersection: exercising the channel on a real co-spend

`decluster/monitor.py` → `decluster/intersect.py` → `cluster_refined`, run end to end on mainnet
rather than on fixtures. The question is not whether an entity falls out — it does not — but whether
each stage does on real data what it does in the tests, and what the stages say to each other.

## Finding a co-spend

The channel needs two coins out of a mix, later spent together. Seeded from the JoinMarket round
`0cb4870cf2dfa387` already used by `RESULTS-subtx-demix.md` (12 in / 21 out): all 21 outputs are
spent, and two later transactions consume two outputs each.

| spender | shape | monitor |
|---|---|---|
| `66fcf6a888e26f66` | 29 in / 21 out | stopped as a mix |
| `5cce9a7fa309eabd` | 19 in / 20 out | candidate |

The first is refused by the stop rule, correctly: at ≥20 on both sides it has a mix's shape, and its
funders are themselves rounds of the same shape — it is another hop of remixing, not a consolidation.
The second is one input below the threshold. That the two differ by a single input is the stop rule's
`COINJOIN_MIN_PARTICIPANTS` boundary showing itself on real data.

## The run

Seeds are three coins the candidate spends, each from a distinct funder small enough for the link
oracle to resolve (≤24 combined coins; above that it refuses and the signature degenerates — see §9).

```
candidate 5cce9a7fa309eabd   shape (19, 20)   branches 3
  signature sizes      [2, 24, 5]
  shared origins       0
  narrowing            2 origins / None bits
  engine               believed=True, 0 refusals
```

**The walk and the engine step work.** The monitor produced a real candidate; `score_candidate`
handed the funders *and the co-spend itself* to `cluster_refined`, which scored it.

**The provenance channel resolves below the oracle guard.** Signature sizes of 2, 24 and 5 are real
ancestor sets, not the single-element degeneracy a coin out of a large mix returns. This is the
complement of the §9 limit measured from the other side: the backward walk is not broken, it is
bounded, and the bound is the oracle's ~24-coin cutoff.

**The intersection is empty, and it is not a refusal.** The three branches share no ancestor — but
the boundaries they were intersected over are largely the oracle declining to walk further, not
origins:

| branch | absorbers | truncated | |
|---|---:|---:|---|
| `346b246ffe7eb3:3` | 2 | **2** | boundary is *entirely* truncation |
| `64ef93f292ca52:1` | 24 | 4 | |
| `ed83ba69720950:2` | 5 | 3 | |

`shared_origins` is bounded by the smallest set, and the smallest set here contains no observed
origin at all. Two such sets fail to overlap whatever the provenance is, so the empty result says the
walk could not see, not that the coins came from different places. `evaluate` reports `truncated` and
`blind` for exactly this reason; this run is `blind`.

`collapsed_bits` is `None` rather than infinite, which is right for a different reason: an empty
intersection is never an unbounded narrowing. But the count `collapsed = 2` should be read as nothing
at all here — it is the smallest branch's size, and that branch saw nothing.

## Seeding on branches that can see

The candidate has seven funders under the oracle's cutoff. Measuring the boundary of each first —
absorbers, and how many of them are truncation — five of the seven contribute at least one observed
origin, and one resolves with no truncation at all. Re-run on the four that see:

```
candidate 5cce9a7fa309eabd   shape (19, 20)   branches 4
  signature sizes      [16, 24, 26, 9]
  truncated            [ 5,  4, 10, 0]      blind=False
  shared origins       0
  engine               believed=False, 3 refusals
```

Two things change. The empty intersection is now a **result**: every branch contributes observed
origins, so "no shared ancestor at depth 3" is what the walk found, not what it failed to see.

And **the engine refused**. The co-spend is a +2.0-bit prior toward one owner; three of the four
funders agree at +6.82 bits of fingerprint while the fourth disagrees at −4.06 against each of them,
and the fused score goes negative on exactly those three pairs. The partition comes out **4/1** — the
odd funder split out of a transaction that spent its coin alongside the others.

| pair | fingerprint | gate `fp < 0` |
|---|---:|---|
| the three alike, pairwise | **+6.82** | closed |
| each against `b3803654455a` | **−4.06** | open |

That is the step the channel exists for: co-spending is the common-input heuristic, and here the
engine declined it on the evidence. It is also the first case in this repository where the gate on
the provenance term is *open* — though the merge was already negative on the fingerprint alone, so
provenance could only corroborate. `refused` reports `(a, b, tx, fp, amt, fp+amt+topo)` and does not
surface the provenance contribution, so how much it added is not readable from the verdict.

`tests/test_intersection_real.py` pins all three findings — the stop-rule boundary, the non-blind
empty intersection, and the 4/1 refusal — as data, so they are checked without the network.

## What the origin sets are, and are not

Every number above that involves a signature rests on `ancestry.ancestry_signature`, whose edge
weighting is a **stated approximation** of the framework it implements. The theory's walk weights a
transition by coin value — each input satoshi equally likely to have become each output satoshi. This
walk weights by subset-sum link probability, row-normalized, which `decluster/ancestry.py` flags as
provisional and defers to the flow rung.

So "no shared origin" is a statement about the link-weighted walk at depth 3, not about satoshi flow.
A value-weighted walk could intersect where this one does not, or the reverse. The refusal the engine
issued is unaffected — it was carried by the fingerprint — but the narrowing, and the blindness
measurement that qualifies it, are only as good as that substitution.

## Why the engine did not use it

The signatures are handed to `cluster_refined`, but its provenance-disjointness term is gated on the
fingerprint also disagreeing, so that disjoint provenance alone never splits a benign single-owner
pair. Measured on this candidate:

| pair | fingerprint | provenance link |
|---|---:|---:|
| `346b246ffe7e` ~ `64ef93f292ca` | **+6.82 bits** | 0.0000 |
| `346b246ffe7e` ~ `ed83ba697209` | **+6.82 bits** | 0.0000 |
| `64ef93f292ca` ~ `ed83ba697209` | **+6.82 bits** | 0.0000 |

The gate is closed on every pair. The evidence is available and unused, by design.

The reading worth keeping is the interaction of two limitations §8 already lists separately. In a
population adjacent to one coordinator, fingerprint agreement is close to uninformative — every
participant runs the same client, so +6.82 bits of construction agreement is the same-software false
positive, not a same-owner signal. Gating provenance on fingerprint *disagreement* then leaves the one
channel that separates these coins dark exactly where it would have had something to say. Neither
behaviour is wrong on its own; the combination is worth knowing before either is trusted here.

## Reproduce

```python
from examples.intersection_pipeline import run, default_signature_of, default_cluster_fn
# seeds: one coin per distinct funder of 5cce9a7f… with ≤24 combined coins
run(seeds=seeds, signature_of=default_signature_of(),
    cluster_fn=default_cluster_fn(), max_depth=0)
```
