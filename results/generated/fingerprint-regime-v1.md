# Fingerprint ranking regime

Generated from the canonical experiment artifact. Do not edit manually.

Transactions: 600.

| weights | N-S-form AUC | F-S AUC | N-S-form top-1 | F-S top-1 | within-class mean gap |
|---|---:|---:|---:|---:|---:|
| library | 0.920700 | 0.939150 | 0.680000 | 0.730000 | 0.392591 |
| snapshot_measured | 0.953150 | 0.939150 | 0.785000 | 0.730000 | 0.675116 |

The historical claim that the conditioner interpretation is stable across weight sources does not reproduce on this fixture. Snapshot-measured weights outperform the F-S top-1 baseline and have a larger within-class mean gap, but they are fitted and evaluated on the same selected data. This is evidence of sensitivity, not evidence that fingerprints are universal sparse identifiers.
