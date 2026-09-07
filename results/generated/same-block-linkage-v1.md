# What the amounts settle about co-spent inputs

Generated from the canonical experiment artifact. Do not edit manually.

300 of 300 multi-input transactions in scope admit a value-conserving mapping under the transaction's own fee. Across their 864 input pairs, Maurer's `p_II` says how often the two coins share a block in every mapping the amounts admit.

| p_II | input pairs |
|---:|---:|
| 0.2 | 3 |
| 0.3 | 14 |
| 0.5 | 55 |
| 0.7 | 27 |
| 1.0 | 765 |

**765 of 864 pairs (88.5%) are forced together** — no admissible mapping separates them — and 0 are forced apart. The amounts corroborate the co-spend far more often than they contest it here, and on this snapshot they never contest it outright.

On the output side, 258 of 318 pairs are forced together.

**This is not an ownership result, and the gap is the point.** A block of a value-conserving mapping is an accounting unit; a collaborative transaction can put two owners in one block and satisfy every constraint measured here. What the number bounds is what the amounts alone can settle — the part common-input ownership borrows without checking.

Scope is capped at 12 coins, which excludes the wide consolidations and coinjoins where the question is hardest, and the fee-tolerant model admits mappings exact conservation would refuse — which can only widen the family and lower the forced share. The snapshot is 300 selected transactions and is not chain-wide.
