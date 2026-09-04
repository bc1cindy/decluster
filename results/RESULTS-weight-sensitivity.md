# Global fingerprint-weight sensitivity

Canonical run: `catalog/runs/weight-sensitivity-v1.json`.

The executable table is `results/generated/weight-sensitivity-v1.md`; exact
values and source identity are in `results/artifacts/weight-sensitivity-v1.json`.
Every row uses the same 4,000 positive and 4,000 negative weak-label draws from
the preserved 22,112-transaction snapshot.

The AUC is locally stable: its range from `c=0.90` through `c=0.99` is 0.000550.
The evidence magnitudes are not stable. The positive mean falls from +23.06 to
+9.43 bits, while the negative mean falls from +8.85 to -36.95 bits across the
full sweep.

The historical monotonicity claim is false on the preserved data. AUC peaks at
0.924450 for `c=0.95` and falls to 0.923900 for `c=0.99`. Therefore this result
supports local ranking stability, not monotonic improvement or calibrated
evidence. Address reuse remains a weak label. This attacker-side sensitivity
analysis is not CoinScore or a privacy certificate.
