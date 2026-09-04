# Pair-level Bayesian and Fellegi–Sunter comparison

Canonical run: `catalog/runs/bayes-vs-fs-v1.json`.

This experiment compares three attacker-side pair-linkage scorers on 4,000
address-reuse pairs and 4,000 sampled non-reuse pairs from the preserved
22,112-transaction snapshot. The executable table is generated at
`results/generated/bayes-vs-fs-v1.md`; the full per-axis values and cluster
diagnostics are in `results/artifacts/bayes-vs-fs-v1.json`.

The preserved data do not reproduce the former handwritten numbers. The
canonical rerun reports AUC 0.916250 for fixed `m=0.95`, 0.932000 for EM, and
0.932400 for Bayesian integration. Its ECE values are 0.145541, 0.174952, and
0.193611 respectively. On this selected balanced sample, Bayesian integration
does not improve calibration over EM.

Address reuse is a weak, partly feature-dependent label. The model fits and
evaluates on the same selected pairs, assumes conditional independence between
correlated axes, and fixes `u` at the measured collision rate. The entity-count
bands independently sample pair edges; they are not a posterior over ownership
partitions. This is attack evidence, not CoinScore or a privacy certificate.
