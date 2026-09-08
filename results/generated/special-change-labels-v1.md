# Change labels that do not read co-spend

Generated from the canonical experiment artifact. Do not edit manually.

22112 committed transactions, 10850 of them two-output candidates. Each label picks the change output from values or script types alone, so none of them reads the address relation the fingerprints are meant to extend.

| label | transactions it labels |
|---|---:|
| address_reuse | 4980 |
| optimal_change | 1138 |
| round_number | 1345 |
| type_match | 4222 |

## Within-transaction predictors against each label

| label | predictor | TPR | FPR | coverage | precision |
|---|---|---:|---:|---:|---:|
| address_reuse | address_reuse | 1.000 | 0.000 | 1.000 | 1.000 |
| address_reuse | round_number | 0.374 | 0.068 | 0.442 | 0.846 |
| optimal_change | address_reuse | 0.323 | 0.037 | 0.360 | 0.898 |
| optimal_change | round_number | 0.434 | 0.099 | 0.533 | 0.814 |
| round_number | address_reuse | 0.395 | 0.005 | 0.400 | 0.987 |
| round_number | round_number | 0.998 | 0.000 | 0.998 | 1.000 |
| type_match | address_reuse | 0.547 | 0.000 | 0.547 | 1.000 |
| type_match | round_number | 0.394 | 0.072 | 0.466 | 0.845 |

Against the value label, the round-number heuristic is right 0.81 of the time it commits, on 53% of the labelled transactions, and address reuse 0.90 on 36%. Two universal heuristics agreeing with a label neither of them reads.

A predictor scored against its own label is self-agreement and not corroboration: the round-number rows under the `round_number` label, and the address-reuse rows under `address_reuse`, read the same fact twice and are reported only so the table is complete.

## Do the labels agree with each other

| label | label | both label | agree | disagree |
|---|---|---:|---:|---:|
| address_reuse | optimal_change | 410 | 368 | 42 |
| address_reuse | round_number | 538 | 531 | 7 |
| address_reuse | type_match | 2310 | 2310 | 0 |
| optimal_change | round_number | 246 | 239 | 7 |
| optimal_change | type_match | 513 | 470 | 43 |
| round_number | type_match | 642 | 623 | 19 |

`address_reuse` and `type_match` agree on all 2310 transactions both label, and that is arithmetic rather than evidence: an output reusing an input address carries an input's script type, so the type rule can only select the same output or abstain. They are one label counted twice, which is the number a corroboration between them would double-count.

## The onward-spend arm is not measured here

Voting for the output whose *spender* repeats the transaction's fingerprint needs that spender to be in the data. The cache is block-sampled, so it is usually not:

| label | labelled | one output spent inside | both spent inside |
|---|---:|---:|---:|
| optimal_change | 1138 | 193 | 12 |
| round_number | 1345 | 438 | 21 |
| type_match | 4222 | 1154 | 48 |
| address_reuse | 4980 | 1496 | 97 |

At 12 transactions with both outputs spent inside the cache, the per-axis rates that arm would report are not a measurement. Getting it needs a contiguous export deep enough to hold each change output's spender, which is a collection and not a method — state 4 in `results/REPRODUCIBILITY.md`.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is recomputed from `data/fs-blkcache-2026-09-04.tar.gz` and compared byte for byte.
