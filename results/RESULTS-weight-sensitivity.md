# Global fingerprint-weight sensitivity

Canonical run: `catalog/runs/weight-sensitivity-v1.json`.

The executable table is `results/generated/weight-sensitivity-v1.md`; exact
values and source identity are in `results/artifacts/weight-sensitivity-v1.json`.
Every row uses the same 4,000 positive and 4,000 negative weak-label draws from
the preserved 22,112-transaction snapshot.

The AUC is locally stable: its range from `c=0.90` through `c=0.99` is 0.00055,
which is under a fifth of one standard error.
The evidence magnitudes are not stable. The positive mean falls from +23.06 to
+9.43 bits, while the negative mean falls from +8.85 to -36.95 bits across the
full sweep.

The historical monotonicity claim is not supported on the preserved data, and it is
not falsified either. AUC peaks at 0.9245 for `c=0.95` and reads 0.9239 for
`c=0.99` — a dip of 0.00055 against a standard error of 0.0031 at 4,000 pairs per
class, which is **0.18 standard errors**. Over this band the AUC is flat within what
the sample resolves. Calling the dip a reversal would read noise as a finding, in the
direction that happens to suit the argument. So this result supports local ranking
stability and nothing about the ordering. Address reuse remains a weak label. This attacker-side sensitivity
analysis is not CoinScore or a privacy certificate.
