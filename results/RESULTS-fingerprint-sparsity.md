# Fingerprint anonymity sets at survey scale

> The 12-axis whole-window column is recalculated from the preserved aggregate by
> `catalog/runs/fingerprint-sparsity-v1.json`. Its structured artifact is
> `results/artifacts/fingerprint-sparsity-v1.json`, with canonical rendering in
> `results/generated/fingerprint-sparsity-v1.md`. All conditional partitions preserved in the
> aggregate reconstruct the same histogram. The 19-axis and single-epoch columns below remain
> historical because their source vectors or histograms were not preserved. The reproduced result
> measures exact-vector equivalence classes, not general nearest-neighbour sparsity, cluster
> distributions or successful attribution.

**Claim tested.** The Narayanan–Shmatikov results require a *sparse* feature space: most
records have no close neighbours. Wallet-construction fingerprints are the obvious
candidate feature space on Bitcoin. Are they sparse?

**Data.** A contiguous 2026 survey: blocks 939 969–962 720, 158 epochs of 144 blocks,
**98 179 414 transactions**. Per-epoch counts of every distinct fingerprint vector,
produced by the `lumen-fingerprints` scan (Floresta, no archival node). Two vector widths
are published by that survey: 12 axes (version, nSequence, nLockTime, input/output order,
output structure, input/output types, low-R, SIGHASH, uncompressed pubkey, OP_RETURN) and
19 axes (adding input subtype, low-S, ECDSA signature count, input age, feerate bucket,
round feerate, locktime offset).

**Method.** For each distinct vector, its occurrence count *is* the size of the anonymity
set of every transaction carrying it. Transactions are then bucketed by the size of their
own class, so each row reads as "what share of transactions sit in a crowd of this size".
Computed at two scopes, because class size depends on how much chain the observer
aggregates: the whole 158-day window, and a single 144-block epoch (median over the 158).

## Result

| Class size | 12 axes, whole window | 19 axes, whole window | 12 axes, single epoch |
|---|---:|---:|---:|
| exactly 1 | 0.009 % | 0.275 % | 0.465 % |
| 2–9 | 0.052 % | 0.952 % | 1.885 % |
| 10–99 | 0.351 % | 3.489 % | 7.366 % |
| 100–999 | 1.667 % | 8.777 % | 16.167 % |
| 1 000–9 999 | 6.249 % | 14.998 % | 19.413 % |
| 10 000–99 999 | 16.120 % | 14.054 % | 13.984 % |
| **≥ 100 000** | **75.552 %** | **57.455 %** | **40.122 %** |
| in a class < 10 | 0.061 % | 1.227 % | 2.350 % |
| in a class < 100 | 0.413 % | 4.716 % | 9.716 % |

The 12-axis whole-window column reproduces the conditional-anonymity distribution the
survey's own report emits, which cross-checks the computation against an independent
implementation.

## Reading

**Fingerprints are not sparse.** Three quarters of transactions share their 12-axis vector
with at least 100 000 others; 0.06 % sit in a crowd smaller than ten. The N-S premise
requires the opposite shape. This is the quantitative form of the qualifier the
collaborative-transaction-privacy writeup attaches to statistical features, and it agrees
with `RESULTS-fingerprint-regime.md` at roughly 11 000× the sample.

**More axes buy distinctiveness, but not sparseness.** Going from 12 to 19 axes multiplies
the sub-10 share by 20× (0.061 % → 1.227 %). The direction is real and large. It is also
not close to enough: 98.8 % of transactions still sit in a class of ten or more, and a
clear majority remain above 100 000. Dimensionality is not the binding constraint that a
handful of extra axes relieves.

**Aggregating more chain makes each fingerprint *less* identifying.** Narrowing from 158
days to one epoch raises the sub-10 share 40× (0.061 % → 2.350 %). Class size grows with
the observation window, so an adversary holding the whole chain sees *larger* crowds per
vector, not smaller. Fingerprint distinctiveness is a property of the window, not of the
transaction — which is precisely why the channel buckets rather than identifies.

## Scope

This measures the **per-transaction** vector. It says nothing about the distinctiveness of
a **cluster's feature distribution**: a cluster of fifty transactions carries a
distribution over vectors, which can be far more distinctive than any single vector, and
measuring it requires a clustering rather than a survey. That quantity is the one the
structural argument actually rests on, and it is measured separately.

Two further limits. The survey's axes are construction-level only: no amounts, no graph,
no timing-of-day. And the sub-10 shares are lower bounds on crowd size in the sense that
any *additional* axis can only split classes further, so the result bounds what this axis
set can do, not what all statistical features could.

## Reproduce

```sh
python3 examples/fingerprint_sparsity.py <epochs.jsonl>
```
