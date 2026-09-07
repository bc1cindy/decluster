# Per-axis Fellegi–Sunter EM diagnostic

Canonical run: `catalog/runs/em-m-v1.json`.

The executable report is `results/generated/em-m-v1.md`, and the per-axis
measurements are in `results/artifacts/em-m-v1.json`. EM is fitted without pair
labels; address reuse is used afterward as a weak comparison label.

On the preserved 22,112-transaction snapshot, the LibraryScorer AUC is 0.9244
with fixed `m=0.95`, 0.9254 with EM-fitted per-axis values, and 0.9546 with
address-reuse agreement values. The EM-minus-fixed difference is +0.0009 — below
what this sample resolves, which is the point of the sentence that follows.
It is descriptive, not an established improvement, because no pre-registered
separability test was run.

The former 165,832-transaction table cannot be reproduced from the preserved
snapshot. Address reuse is a weak and partly feature-dependent proxy; fitting
and evaluation use the same selected pair sample; correlated axes violate the
conditional-independence assumption. This diagnoses attacker-side linkage
parameters. It is not CoinScore or a privacy certificate.
