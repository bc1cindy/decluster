# Which counting method, and which L

> Historical record. The current canonical result is
> `catalog/runs/counting-methods-v1.json`, rendered as
> `results/generated/counting-methods-v1.md`. The historical timings, L comparison and router
> shares below are not current canonical measurements.

## Verdict

The whole-transaction cascade was picking the one method that adds nothing and handing the next one
an unbounded subset size, which is why it stopped returning past twenty inputs. Bounding the
convolution by the crate's own knee takes a 25-input call from 246.8s to 0.0032s. The
saddle-point estimator is not a missing tier here: it answers a pre-output question and this is a
post-output analyzer. And on the regime gate that decides when it applies, only one of the seven L
candidates recovers the truth — `max(A)`, at 18 of 18 against instances whose L is known.

## The order, and what each is for

| method | role | in this module |
|---|---|---|
| brute force | the convolution below its crossover | **absent** — same algorithm, only a way to be slow |
| radix | fast path for denominated shapes; reads the output side alone | first |
| sparse convolution | the general post-output path, bounded by the knee | second |
| saddle point | a magnitude estimate where the exact tiers return a truncated floor | reachable on purpose, never a tier |

## Why the cascade did not return

`w_count` tries brute first up to twenty inputs, and brute enumerates every distinct output subset
sum as a target and every input subset at every size. Past twenty it falls to the convolution — but
passes `max_size = inputs.len()`, so the graded sumset is built to full width. The crate has a knee
of 5 for coinjoin-shaped analysis and its per-coin path uses it; only the whole-transaction cascade
does not.

| inputs | `max_size = n_in` | `max_size = knee` |
|---:|---|---|
| 25 | 246.8 s | 0.0032 s |
| 60 | does not return | 0.0004 s |
| 67 | does not return | 81.4 s |

Five orders of magnitude, and the cause is the bound rather than the algorithm. It is not a complete
fix — one 67-input transaction still runs 81s — so a residual width guard stays.

## Routing the real slice

Over 1,428 multi-input transactions with complete amounts, 9.6s total, slowest single call 0.296s
(the cascade does not finish at all):

| resolved by | share |
|---|---:|
| radix, exact | 37.32% |
| sparse, exact | 2.10% |
| sparse, lower bound | 0.28% |
| nothing resolved | 60.29% |

A tier that completes with a count of zero has found no mapping, which is the absence of an answer
rather than an answer of no ambiguity. The radix path returns one on 63% of these transactions, so
accepting it would let the first tier short-circuit the rest on a non-result.

## Which L

The model draws each value uniformly from {1, …, L}, so L is a property of the value distribution
and `max(A)` is its natural estimator. Tested against instances generated with a known L, scoring
each candidate on whether it recovers the regime that L implies — 10 dense and 8 sparse, so a
candidate cannot win by always answering the same way:

| L | agreement |
|---|---:|
| **max(A)** | **18/18 (100%)** |
| sum(A) | 13/18 (72%) |
| max(A)², sum(aᵢ²), sum(A)² | 8/18 (44%) — never say dense |
| MAX_MONEY/N | 6/18 (33%) |
| MAX_MONEY | 5/18 (28%) |

κ rises with L while κ_c falls, so overestimating L pushes an instance toward sparse twice over. The
three quadratic candidates never return dense at all, and MAX_MONEY/N is undefined on three of the
sparse cases.

This matters because the regime gate reads dense only when κ < κ_c at the worst-case L
(MAX_MONEY/N) and calls everything between best and worst transitional. With a candidate that is
wrong two thirds of the time and biased toward sparse, dense becomes close to unreachable —
measured, the estimator declines on every transaction in the slice and on synthetic instances at
κ = 0.026 against κ_c = 0.121.

That is an observation about the upstream gate, not a change to it: those files are held as the
canonical statement of the model. It is recorded here because it explains what the estimator does
rather than leaving it looking broken.

## Why the estimator is separate rather than absent

Pre-output and post-output is the wrong axis to sort the methods by. It separates the two *sides* —
constructing a transaction versus reading one that exists — and on the construction side every
method is pre-output by definition. It does not say which method an analyst may use.

What the upstream correction actually rules out is narrower: the estimator does not fill the holes a
truncated lower bound leaves, so chaining it as an automatic upgrade merges a guarantee and an
estimate into one number. The pipeline that did that was withdrawn, and the prescribed shape is a
public function the caller invokes deliberately, checking convergence itself. The transcript is
explicit that the estimator "is more useful than just in the cost function", which is the analytic
side.

So it is not a tier in `count_w`, and it is available as `saddle_point_log_w` for a caller who wants
a magnitude rather than a floor. An earlier revision of this document removed it outright on the
pre/post-output reading; that was too strong.

## Scope

One slice, 137 blocks, 2023. The L comparison is on synthetic instances drawn from a known L, which
is the only way to know the answer being estimated; real transaction values are not drawn uniformly from any
range, so the estimator question there is a modelling choice rather than an estimation one.

## Reproducibility / provenance

Per `results/REPRODUCIBILITY.md`, state 2: **mechanism unit-tested, headline number is a data-run.**
The routing order, the zero-count rule and the estimator's absence from the post-output path are
pinned in `tests/test_counting.py`. The timings and the L comparison are regenerated over
`sample.ndjson` and synthetic draws, and are not asserted.


## Is any of this the model the writeup asks for?

Only partly, and the writeup says so itself. On the two combinatorial models it names:

> "In Maurer et al, the values of the inputs and the outputs must exactly cancel out, **which is not
> sufficiently general for real world analyses**. Boltzmann casts a wider net, by allowing these to
> vary somewhat, accounting for fees."

Every counting path reachable here applies the exact-cancellation criterion. Holding the shape fixed
and moving only the fee:

| | whole-tx count | per-coin path |
|---|---|---|
| fee = 0 | exact, 0 | 3 coins measured |
| fee = 1,000 sats | exact, 0 | **0 coins measured** |

Sweeping the fee locates the tolerance precisely: three coins measured at a fee of zero, one at a
fee of **1 satoshi**, none from **10** upward. So the machinery does carry a tolerance — it is
calibrated for exact arithmetic, three orders of magnitude below what a transaction actually pays.
Real fees on the slice run to a median of 4,956 sats. So the fee-blindness is not a wiring defect to
be fixed downstream; it is the criterion the writeup names as insufficient, and it accounts for the
exact-zero on 86% of transactions and the unreachable per-coin reading on 98.2% of input coins. The
tolerance needed by this old measurement was absent when it was produced.

> **Correction (2026-09-03).** `decluster.baselines.boltzmann` now exposes a separate
> `fee_tolerant` balance model. It allocates the observed non-negative transaction fee across
> participant blocks and requires an explicit total `fee_tolerance`; the original `exact` path and
> every number in this document remain unchanged. Roundness is neither an admissibility rule nor a
> prior in that baseline. This is a local mechanism, **not parity with the Boltzmann tool**, whose
> cases and implementation are not available in this checkout. This table has not been re-measured
> with the new model.

Two further gaps between the object and the writeup's framing, both of which the paper already
states: what it counts is subset-sum multiplicity, not Maurer's matched-partition count; and the
quantity the writeup says bounds anonymity is the *entropy of the distribution* over partitions,
not a count of them.

### The denominational bound, and the precondition nobody was checking

The denominational path is not a different quantity — it is a cheap lower bound on the same mapping
count, obtained by counting how a repeated denomination permutes among participants. But that bound
means nothing unless a denomination actually repeats, and the crate returns a number either way. The
upstream classifier work states the division explicitly: it delivers the per-series multiplicity
counts and leaves "the gap/density check ... to the lower-bound consumer that uses it". This module
is that consumer, and it was not checking.

Unguarded, the path answers on 64 of 1,428 real multi-input transactions — and **51 of those
(79.7%) carry no repeated output value at all**. It is now gated on the precondition, which is the
same three-fold floor the de-mix uses to call a value a mix denomination.

Those two figures were 533 and 514 (96.4%) before the mapping count itself was corrected
(`115b4e55:results/artifacts/counting-router-v1.json`). The
collapse from 533 to 64 is the same defect seen from the other side: almost every "answer" the
ungated path returned was a permutation of a denomination the transaction does not contain, so it
was counting a multiplicity that was not there rather than counting it without a licence. Current
values are `raw_positive` 64 and `raw_positive_without_precondition` 51 in
`results/artifacts/counting-router-v1.json`, rendered in `results/generated/counting-router-v1.md`.

| revision | multiplicity live | why |
|---|---:|---|
| the crate cascade | 5.60% | stalls past twenty inputs, exact-zero on the rest |
| router, denominational path ungated | 39.71% | 94% of it invalid — the precondition was unmet |
| router, denominational path removed | 6.37% | over-corrected: threw away the valid cases too |
| **router, precondition checked** | **6.86%** | sparse on 5.25%, denominational on the 1.61% that are denominated |

The middle two rows are both wrong, in opposite directions, and are recorded because the first is
the more tempting number and the second is the more comfortable one.

**Every share in that table predates the mapping-count correction and is superseded.** They were
measured when the radix path returned a positive reading 533 times; it now returns one 64 times, and
the exact tier it used to fill is empty. The current router resolves **82 of 1,428 transactions
(5.74%)** — 0 radix exact, 60 sparse exact, 22 sparse lower bound, 1,333 refused — per
`results/artifacts/counting-router-v1.json`. The rows above are kept as a record of the two failure
directions, not as current shares, and the generated report says the same: "Earlier router shares
are superseded by the current run."


## The sequence, and making each step depend on the one before

The guidance for this work states an order: classify the amounts, then evaluate the transaction as a
whole, and only then score per output — the last explicitly deferred, and to be reached with "a few
lookups in a precomputed table" rather than by a separate oracle call.

decluster had all three, wired in parallel rather than in sequence:

| step | where | was it grounded? |
|---|---|---|
| 1. classify radix-ness | `counting.radix_applies` | not checked at all — the bound was taken on 64 transactions, 51 of which had no denomination |
| 2. evaluate the tx as a whole | `counting.count_w` | routed through the crate cascade, which stalls past twenty inputs |
| 3. score per coin | `cost.amount_cuts` | ran independently of step 2 |

Step three running independently is measurable. Over the slice, the per-coin oracle produced cuts for
95 transactions and the transaction-level reading resolved for 82 — but they agree on only 62.
Thirty-three transactions were being cut on a per-coin reading that the transaction-level evaluation
had found nothing to support, and twenty that did resolve got no cut because the truncation could
not reach their coins.

Gating the third step on the second closes that:

| | transactions cut | cuts | share of coins |
|---|---:|---:|---:|
| ungated | 95 | 318 | 1.35% |
| **gated on step 2** | **62** | **101** | **0.43%** |

The remaining 62 are the transactions where the amounts classify, the transaction as a whole
resolves, and the coins are individually reachable — which is what a per-coin score was supposed to
mean. That the number is small is the finding, not a failure of the plumbing: it is the same 6%
ceiling the fee-blind criterion imposes, now reached through a chain where each link is earned.
