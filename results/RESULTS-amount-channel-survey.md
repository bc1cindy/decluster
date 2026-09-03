# What the amount channel actually says on a real slice

> **Correction (2026-09-03) — "a deterministic link" is measured false.**
> Below, "369 rows admit exactly one output — a deterministic link, the amounts settling the
> assignment on their own" is the reading `counting.link_matrix`'s docstring handed consumers at the
> time. `results/RESULTS-exact-oracle-audit.md` has since measured that reading against an exact
> mapping oracle and found it wrong in one direction: `dss.pairwise_link_prob` is the uniform
> marginal over dss's own, strictly smaller mapping family, and asserting certainty from a
> single-non-zero row produces **1,197 spurious certainties across 395 of 507 transactions** (while
> missing no genuinely certain link). A one-entry row means *dss's family* admits one output, not
> that the amounts settle the assignment. The 369 count itself is unaffected — it is a count of rows
> — but the sentence attached to it is not a licence to read those 369 as settled. The docstrings in
> `decluster/counting.py` and `decluster/cost.py` have been amended accordingly.

## Verdict

Run against real transactions for the first time, the channel had three defects and one arm that
never speaks. The worst: `cost.amount_cuts` was cutting **every coin it could not measure**, because
the per-coin oracle spells "unreachable" as negative infinity while the guard tested for `None`.
That is 98.2% of input coins. With the sentinel handled, the channel cuts 1.35% of coins on 6.65% of
transactions, which is what a refuse-only channel should look like.

## Data

`sample.ndjson`: 5,491 transactions over blocks 812,695–812,831, all carrying prevout values and
script types, 1,428 of them multi-input. The graph-scale exports carry addresses only, which is why
none of this had been measured before.

## Each arm, and how often it speaks

| arm | fires on | of |
|---|---:|---|
| coinjoin shape detector | 28 (1.96%) | multi-input transactions |
| **de-mix into ≥2 participants** | **0 (0.00%)** | multi-input transactions |
| unnecessary-input heuristic | 485 (33.96%) | multi-input transactions |
| 2-in/2-out re-partition, top rank tied | 330 (68.32%) | the 483 it ranks |
| amount cuts (after the fix below) | 318 coins (1.35%) | 23,626 coins |

**The de-mix arm is silent.** Zero of 1,428. It looks for a fixed mix denomination appearing three
or more times with a uniquely matching change output, which is the JoinMarket shape; ordinary
traffic does not have it. The refusing clusterer's de-mix arm therefore contributes nothing on this
data, and the refusal reduces to the shape rule.

**The re-partition does not decide.** Of the 2-in/2-out transactions it ranks, more than two thirds
have their top two readings tied on roundness. The "decidable regime" is a minority of the shape the
engine treats as its primary case.

## Three defects, in order of severity

**1. Unreachable coins were being cut.** `amount_cuts` documents that a coin the truncated search
cannot reach is "skipped, not cut", and guards it with `log_w is not None`. The dss per-coin path
spells that state as `-inf`, so the guard never fired and `-inf <= cut_threshold` sent every such
coin into the cut list. Measured: 17,204 of 17,520 input coins (98.2%) are `-inf`, and 1,385 of
1,428 transactions (97.0%) have every input coin in that state. This is live code —
`report.report` calls `amount_cuts` — so the fused per-transaction view was refusing nearly every
coin it saw. Now: 318 cuts, 1.35% of coins.

**2. An exact count of zero was corroborating cuts as rigorous.** `amount_cuts` promotes a cut when
the transaction-level count comes back `exact`. The whole-transaction count is fee-blind — it asks
which input subsets hit an output subset sum *exactly*, and a fee-paying transaction has none — so
it completes at zero on 1,223 of the 1,303 exact counts. Zero is the counter finding nothing, the
weakest corroboration available. Rigour now requires the count to have found something.

**3. The whole-transaction count does not return above twenty inputs.** The cascade's brute branch
enumerates every distinct output subset sum as a target and, for each, every input subset at every
size; its own width limit is twenty, which is exactly where the call stops returning. Probed per
width in separate processes: under a second to ten inputs, 3.4s at sixteen, and past twenty two
thirds of the transactions never finished. A hang is not an exception, so the module's panic guard
could not catch it, and a Python alarm cannot either — the block is inside Rust. The call is now
declined above the largest width measured to complete.

The crate's fee-aware per-coin path has no such limit: it returns in 0.008s at sixty inputs and
0.136s at sixty-seven, the widths where the whole-transaction count hangs. That path was already
what `cost.py` used; only `counting.py` was on the other one.

## What this does not show

The per-coin path answers, but on this slice it mostly answers "unreachable" — 98.2%. So the
correction is about not *mistaking* that for a cut, and the channel remains quiet rather than
becoming informative. Of 316 coins with a finite measurement, the median is 4.20 and 60 sit at or
below the cut threshold.

## Scope

One slice, 137 blocks, one era, 2023. The de-mix's silence is a statement about ordinary traffic,
not about JoinMarket rounds, of which this slice contains none the detector recognises.

## Reproducibility / provenance

Per `results/REPRODUCIBILITY.md`, state 2: **mechanism unit-tested, headline number is a data-run.**
The sentinel handling, the zero-count corroboration and the width guard are pinned in
`tests/test_cost.py` and `tests/test_counting.py`. The tables here are regenerated by
`examples/amount_channel_survey.py` over `sample.ndjson`, which is local and unversioned, and are
not asserted.


## The fee-tolerant reading was already in the building

The counts ask for an exact subset hit and a fee-paying transaction has none. The link-probability
matrix does not: it reads the transaction's actual balance, and it is already exposed and already
used — as the transition measure of the provenance walk. Nothing in the amount channel was reaching
for it.

Wired as a per-coin oracle and measured over 300 transactions (3,384 input coins):

| per-coin oracle | coins measured | |
|---|---:|---:|
| density, exact-hit | 348 | 10.28% |
| **link matrix** | **947** | **27.98%** |

Of the 947, **369 rows admit exactly one output** — a deterministic link, the amounts settling the
assignment on their own, which is the refuse signal the channel exists to emit.

Two costs come with it. The matrix enumeration is exponential and its budget is cooperative: a
single call under the crate's own size guard was measured running past a minute, so bulk use has to
go through the throwaway-subprocess oracle the provenance walk already keeps for exactly this. And
the crate can hard-panic on pathological inputs, which the wrapper catches.

It is offered as `cost.boltzmann_oracle` beside the existing one rather than replacing it. The two
answer different questions — how many balancing subsets, against how many outputs an input could
have funded — and swapping them silently would move every number that rests on the old one.


## The entropy the writeup asks for, measured

"if the probabilities over the partitions are far from uniform this amounts to relatively little
privacy. This is typically quantified in terms of entropy." Everything above counts readings; this
is how concentrated they are, and it was implemented in the crate but reachable only from Rust. It
is now bound to Python and returned alongside the links every mapping agrees on, from the one
enumeration that produces both.

Over 250 transactions, each in its own process on a three-second deadline, 12 seconds total:

| | transactions | |
|---|---:|---:|
| answered | 223 | 89.2% |
| refused (size guard) | 26 | 10.4% |
| timed out | 1 | 0.4% |

| mapping entropy | transactions | |
|---|---:|---:|
| **0 bits — one reading, every coin pinned** | **222** | **99.6%** |
| 1–4 bits | 1 | 0.4% |

1,473 deterministic input-output links across the 223. Answering on 89% against the counts' 6% is
the fee handling: the fee is balanced in as an extra output before enumerating rather than being
required to vanish.

The reading is the writeup's own about unilateral transactions — "the amounts strongly suggest one
way of partitioning the transaction" — now measured rather than asserted. Ordinary traffic carries
no mapping ambiguity at all, which is what makes the 0.4% that does worth looking at.
