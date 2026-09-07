# The same kernel under three axis sets

Generated from the canonical experiment artifact. Do not edit manually.

One population of 22112 transactions, one pair sample (4000 per class, seed 0), one consistency (0.95). Only the axis set changes.

| family | axes | AUC | positive mean bits | negative mean bits |
|---|---:|---:|---:|---:|
| catalogued | 23 | 0.9244 | +15.47 | -16.58 |
| construction only | 18 | 0.9003 | +8.42 | -13.94 |
| decorrelated | 14 | 0.9432 | +8.72 | -10.24 |

Dropping the redundant axes costs **6.74 bits** of positive evidence and raises the AUC (0.9244 to 0.9432). The wide model scores several correlated axes as if they were separate facts; the additive rarity kernel has no conditional-independence correction, so the magnitude it reports is inflated while its ranking is not.

The construction-only family drops the axes the shared input address fixes outright, which is the part of the score that is the same-owner label restating itself rather than construction style.

The axis clusters and the address-determined set were measured on this same cache, so the families are not an out-of-sample test. A higher AUC on fewer axes does not show the dropped axes carry no signal, and none of these numbers is a privacy score.
