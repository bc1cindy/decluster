# Pair-level Bayesian and Fellegi–Sunter comparison

Canonical run: `catalog/runs/bayes-vs-fs-v1.json`.

This experiment compares three attacker-side pair-linkage scorers on 4,000
address-reuse pairs and 4,000 sampled non-reuse pairs from the preserved
22,112-transaction snapshot. The executable table is generated at
`results/generated/bayes-vs-fs-v1.md`; the full per-axis values and cluster
diagnostics are in `results/artifacts/bayes-vs-fs-v1.json`.

The preserved data do not reproduce the former handwritten numbers. The
canonical rerun reports AUC 0.9163 for fixed `m=0.95`, 0.9320 for EM, and
0.9324 for Bayesian integration. Its ECE values are 0.1455, 0.1750 and 0.1936
respectively. The AUCs are quoted to four places because a balanced sample of this
size resolves no further, which is also why the 0.0004 between EM and Bayesian
integration carries nothing; the ECE gap does. On this selected balanced sample,
Bayesian integration does not improve calibration over EM.

Address reuse is a weak, partly feature-dependent label. The model fits and
evaluates on the same selected pairs, assumes conditional independence between
correlated axes, and fixes `u` at the measured collision rate. The entity-count
bands independently sample pair edges; they are not a posterior over ownership
partitions. This is attack evidence, not CoinScore or a privacy certificate.
