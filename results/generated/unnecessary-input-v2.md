# Fee-aware unnecessary-input diagnostic

Generated from the canonical experiment artifact. Do not edit manually.

Definition: `blockstream_fee_aware` v2.
Its paper domain is transactions with at least two inputs and exactly two outputs.

| case | classification | fee | Gibson flags |
|---|---|---:|---|
| jointly funded uih2 | uih2 | 1 | `[False, False]` |
| fee aware uih1 | uih1 | 1 | `[True, False]` |
| equality boundary | uih2 | 1 | `[False, True]` |

The observational-equivalence fixture is classified `uih2`, yet remains `inconclusive` across 3 declared latent forms. It infers no ownership, PayJoin identity, payment output, or composition.

NS1R and NSNR controls are outside the two-output definition: `out_of_scope` and `out_of_scope`.

The cycle control preserves the nonzero net balances while changing gross obligations from 500 to 1400. Therefore the gross payment graph is not identified by the on-chain net amounts.

This is a deterministic diagnostic reproduction, not a PayJoin detector, ownership classifier, prevalence estimate, or privacy score.
