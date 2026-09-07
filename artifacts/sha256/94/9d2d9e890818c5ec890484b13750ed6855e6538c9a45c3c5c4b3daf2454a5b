# The fingerprint library against the population that is still here

Generated from the canonical experiment artifact. Do not edit manually.

The shipped bits were measured on a ~105k uniform whole-chain sample that no longer exists. This measures the same quantity on the 22112 transactions of the committed block cache. It is not a reproduction — the populations differ by construction — and the only thing it establishes is how far apart they land.

| axis | values | shown by the cache | mean divergence | max |
|---|---:|---:|---:|---:|
| nsequence | 6 | 6 | 2.21 | 4.66 |
| locktime | 5 | 2 | 0.68 | 1.17 |
| input_order | 4 | 4 | 2.80 | 6.85 |
| output_order | 4 | 4 | 1.55 | 4.30 |
| change_spk | 6 | 6 | 1.62 | 2.99 |
| version | 3 | 3 | 1.44 | 3.14 |
| io_shape | 4 | 4 | 0.53 | 1.62 |
| uih | 2 | 2 | 0.13 | 0.25 |
| fee_rate | 3 | 2 | 0.82 | 1.45 |
| input_script_type | 6 | 6 | 1.38 | 2.66 |
| output_encoding | 5 | 4 | 1.71 | 2.56 |
| input_types_present | 7 | 7 | 1.76 | 3.85 |
| change_index | 3 | 2 | 1.74 | 2.05 |
| change_type_match | 3 | 2 | 2.24 | 2.75 |
| change_matches_output | 3 | 2 | 1.93 | 2.38 |
| change_address_reuse | 2 | 2 | 0.36 | 0.52 |
| low_r | 3 | 2 | 1.44 | 1.62 |
| sighash | 5 | 4 | 0.83 | 1.59 |
| op_return | 2 | 2 | 0.23 | 0.44 |
| nested_segwit | 2 | 2 | 0.24 | 0.43 |
| pubkey_compression | 2 | 1 | 1.86 | 1.86 |
| multisig | 2 | 2 | 0.02 | 0.03 |
| locktime_vs_broadcast | 4 | 0 | n/a | n/a |

Across the 22 axes the cache can compare, the mean divergence is **1.25 bits** and the largest single one is **6.85 bits**, on `input_order`. For scale, the catalogued scorer's whole positive mean on this same cache is about 15 bits.

15 of 86 published values never appear in the cache, so they cannot be checked against it at all.

None of this says the shipped table is wrong. It says the part of it a reader can verify is the part measured here, and that the rest moves by bits rather than by decimals when the population changes. Whether to recalibrate on this cache is a separate decision, and `fingerprint-regime-v1` already reports what changes when the weights are fitted to a snapshot instead of read from the library.
