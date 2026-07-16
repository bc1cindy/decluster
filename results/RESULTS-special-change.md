# Special-case labels — an independent value-based cross-check of the ordering (Phase 1)

Change identification validated against a **value-based** special-case label (optimal-change / UIH,
à la Ron & Shamir) that is disjoint from co-spend clustering *and* from the construction fingerprints
it validates — so this cross-check is not circular. Complements `results/RESULTS-change-id.md`
(which used a co-spend label). Code: `decluster/change_special.py`, `examples/special_change_validation.py`.

**Optimal-change label:** in a ≥2-input 2-output tx, the output smaller than the smallest input value
must be the change (else an input was unnecessary). Reads only values. Disjointness is machine-checked
(`tests/test_change_special.py::test_optimal_change_reads_only_values`).

**Sample:** the value-carrying BigQuery downloads (`~/Downloads/bquxjob_*.json`), **105,546 txs,
multi-epoch (blocks 318,531–940,950 ≈ 2014–2025)** → **10,691 optimal-change labels**.

## Within-tx predictors vs the optimal-change label (offline)

| predictor | TPR | FPR | coverage | precision |
|---|---|---|---|---|
| round_number (`_change_index`) | 0.524 | 0.092 | 0.617 | 0.85 |
| address_reuse | 0.121 | 0.012 | 0.132 | 0.92 |

The round-number heuristic agrees with the value label at ~0.85 precision on 62% of labels; address
reuse is rare here (13%) but the reused output is the change 92% of the time. Two M&N universal
heuristics cross-confirming, non-circularly.

## Onward-spend fingerprints vs the optimal-change label (live fetch, n=1500)

| axis | TPR | FPR | coverage | precision |
|---|---|---|---|---|
| input_order | 0.314 | 0.133 | 0.447 | 0.70 |
| output_order | 0.286 | 0.191 | 0.477 | 0.60 |
| nSequence | 0.311 | 0.110 | 0.421 | 0.74 |
| version | 0.200 | 0.092 | 0.292 | 0.68 |

## The key finding: the co-spend-label numbers are not robust

Against the **co-spend** label (a single 2024-06-01 day; `RESULTS-change-id.md`), `nSequence` reached
0.99 precision and `version` 1.00, and the ordering axes looked distinctly weaker. Against the
**value** label, that collapses — **all four onward-spend axes fall to ~0.60–0.74 precision, and
nSequence/version no longer dominate the ordering axes.** So the "nSequence/version are the strong
tells, ordering is weak" ranking is **label- and population-dependent, not a robust result.**

The divergence is confounded — four plausible causes, none isolable here:

1. **Epoch.** The value sample spans 2014–2025; construction fingerprints drift heavily over time.
   The co-spend result was a single 2024 day.
2. **Onward-spend time gap.** Multi-epoch uniform txs can be spent years later (fingerprint drift);
   the one-day slice has short gaps (stable fingerprints).
3. **Co-spend label selection bias (likely inflates).** The co-spend label selects changes whose
   onward-spender *is* the reveal tx — a same-wallet transaction that shares nSequence/version almost
   always. The value label has no such bias.
4. **Optimal-change label error.** The "no unnecessary inputs" assumption fails for some txs.

Cause 3 is a real methodological inflation in the co-spend result; causes 1–2 also lower the value
result. So this does **not** retract the co-spend numbers — it shows they are not robust, and the
per-axis onward-spend signal is weaker and more label-dependent than the single-day co-spend table
suggested.

## What closes it (Phase 2)

The clean disentangling — label-inflation vs epoch/time-gap — needs a **contiguous slice with input
values** (a BigQuery re-query), so **both** labels (co-spend and optimal-change) run on the **same
transactions**. That, plus the cluster `findNext` against the value label, is Phase 2 (quota-gated).
