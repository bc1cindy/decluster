# Canonical fingerprint model: validation on real witness-bearing transactions

**Claim tested.** Does the 23-axis fingerprint library (`decluster/library.py`) tell same-wallet
transactions apart from random ones — on real witness-bearing data? Scored on the **canonical** path
(`LibraryScorer` over all library axes, using the same extractors the rest of the pipeline uses), not
the former `rust_bridge` mirror.

**Data.** 164,705 witness-bearing transactions from the local block-tx cache (`.blkcache`), each with
full witness and prevout data (coinbase and inputs with missing prevout are dropped, so all axes —
including the witness ones: low-R, uncompressed pubkey, taproot sighash — are populated).

**Method.** Same-owner labels = address reuse: two transactions that spend the same input address are
the same wallet (near-certain). Positives = tx pairs sharing an input address (4,000 sampled);
negatives = random tx pairs (4,000). Score = the Fellegi-Sunter weight of evidence in bits
(`fingerprint_validate.LibraryScorer`, summing agreement bits / clamped mismatch weights over the 23
library axes). Metric = AUC, with a shuffle control.

## Result

| | bits |
|---|---:|
| same-wallet pair score (mean) | **+14.22** |
| random pair score (mean) | **−22.59** |

| AUC | |
|---|---:|
| 23-axis fingerprint separates same-wallet from random | **0.935** |
| shuffle control (per-pair label permutation) | **0.494** |

The library model ranks same-wallet transaction pairs far above random pairs (AUC 0.935); the shuffle
control at ~0.50 confirms the signal is real, not an artifact of the pair sampling. On real
witness-bearing data, the 23-axis model attributes wallet identity from transaction-construction style.
Reproduce: `python3 examples/fingerprint_validation.py`. (These figures are a snapshot on the current
`.blkcache`; the exact AUC wobbles by ~±0.001 as the local cache grows, since the tx population and the
seeded pair sample shift with it — the signal, not the third decimal, is the result.)

**Note on the number.** An earlier version of this measurement reported AUC 0.974, produced by a
now-removed `rust_bridge` mirror whose low-R and BIP-69 extractors were defective (a high-R signature
was misclassified as low-R; a coincidental small-n input sort was branded BIP-69) — both of which could
inflate the separation. Recomputed on the canonical path — with the correct length-based `x_low_r`, the
`n>=4`-gated `x_input_order`, and `x_uih` reading `prevout.value` — the honest figure is **0.935**. The
signal holds; the model is no longer measured through a buggy, unmaintained parallel implementation.

## Honest limits

- **Labels are address reuse.** Two txs spending the same address are the same wallet, but they also
  share that address's script type — so the `input_script_type` / `low_r` / type axes match partly by
  construction. The signal is spread across all 23 axes (score ≫ any single axis) and the shuffle
  control is clean, but the AUC is not attributable to construction style alone.
- **Positives are sampled with replacement.** The reported `n_pos = 4000` counts pair *draws*, not
  distinct pairs — where reuse groups are small, the effective number of independent same-wallet
  observations is smaller, so the AUC's support is narrower than 4,000.
- **Negatives may coincidentally share an address.** Random pairs are filtered only for tx distinctness;
  a small fraction are truly same-wallet, mildly contaminating the null and depressing the AUC.
- **Abstain axes are scored as mismatches when one-sided.** Under the library-faithful policy, the three
  0-bit abstains (`input_order.small_n`, `output_order.small_n`, `locktime_vs_broadcast.na_loose`)
  are dropped from the model, so a small-n tx paired with a large-n tx is penalized on ordering rather
  than treated as non-evidential — symmetric noise across positives/negatives that modestly lowers the
  AUC.
- **Sampled blocks, not a connected slice.** This validates *fingerprint attribution*, not graph-structure
  de-anonymization (that is `decluster/graph_deanon.py`).
- **`consistency = 0.95`** is the assumed same-wallet self-agreement rate, not fitted.
