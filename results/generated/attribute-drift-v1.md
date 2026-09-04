# Projected attribute drift across epochs

Generated from the canonical experiment artifact. Do not edit manually.

Window: 158 epochs of 144 blocks, covering 98179414 transactions.

| axis projection | TV@1 | TV@7 | TV@30 | TV@120 | weekly gain |
|---|---:|---:|---:|---:|---:|
| input_order | 0.008 | 0.008 | 0.011 | 0.013 | 0.83 |
| input_types | 0.036 | 0.045 | 0.082 | 0.175 | 0.99 |
| low_r | 0.038 | 0.052 | 0.090 | 0.155 | 1.04 |
| nlocktime | 0.009 | 0.011 | 0.013 | 0.018 | 0.86 |
| nsequence | 0.040 | 0.044 | 0.074 | 0.077 | 0.88 |
| op_return | 0.071 | 0.072 | 0.103 | 0.147 | 0.82 |
| output_order | 0.031 | 0.035 | 0.057 | 0.127 | 0.90 |
| output_structure | 0.025 | 0.026 | 0.037 | 0.050 | 0.82 |
| sighash | 0.024 | 0.034 | 0.064 | 0.089 | 1.07 |
| uncompressed_pubkey | 0.025 | 0.035 | 0.066 | 0.093 | 1.06 |
| version | 0.029 | 0.026 | 0.042 | 0.070 | 0.75 |

Each row uses the explicitly preserved values plus one combined residual category. This reproduces every rounded historical cell for nlocktime and low_r. The version projection yields 0.070 rather than the historical 0.071 at gap 120. These projections are not replacements for unavailable full-distribution rows or the historical 70/85 volume-coupling summary.
