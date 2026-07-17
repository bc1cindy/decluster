# Weight sensitivity: is the fingerprint verdict robust to the assumed disagreement weight?

**Claim tested.** The Fellegi-Sunter combiner (`decluster/combiner.py`) scores a mismatch with
`min(0, log2((1 - c) / (1 - collision)))`, where `c` (`consistency`, default 0.95) is the assumed
probability that the *same* wallet agrees on an axis. Unlike the agreement weight `-log2(p)`, whose `p`
is measured from the population, `c` is **assumed, not fitted** — it is not directly measurable without
same-owner labels (the same labels used to validate), so its exact value is an open, per-axis question.
Does the separation the model achieves depend on getting `c` right?

**Data.** 165,832 witness-bearing transactions from the local block-tx cache (`.blkcache`) — the same
corpus as `RESULTS-fingerprint-validation.md`.

**Method.** Sweep `c ∈ {0.60, 0.70, 0.80, 0.90, 0.95, 0.99}`. For each, re-score the **same** seeded
pairs (`seed=0`, 4,000 same-wallet + 4,000 random, address-reuse label) with
`LibraryScorer(consistency=c)` over all 23 library axes, and re-measure AUC with a shuffle control. Only
the weight changes between rows.

## Result

| c | same-wallet mean (bits) | random mean (bits) | AUC | shuffle |
|---|---:|---:|---:|---:|
| 0.60 | +20.25 | +5.86 | 0.8970 | 0.4941 |
| 0.70 | +19.46 | +2.28 | 0.9089 | 0.4937 |
| 0.80 | +18.25 | −3.07 | 0.9198 | 0.4938 |
| 0.90 | +16.12 | −12.52 | 0.9281 | 0.4947 |
| **0.95** | **+13.90** | **−22.39** | **0.9333** | 0.4955 |
| 0.99 | +8.77 | −45.31 | 0.9365 | 0.4958 |

**The scores are very sensitive to `c`; the verdict is not.** The raw weight of evidence swings
enormously — the random-pair mean travels ~50 bits (from +5.86 to −45.31, changing sign), the
same-wallet mean halves. Yet the AUC — the actual same-wallet-vs-random ranking quality — moves only
from 0.897 to 0.937 across the *entire* range, and by **< 0.01** across the realistic band
(0.90–0.99). Near the operating point it is flat: 0.928 → 0.933 → 0.937. The shuffle control stays
pinned at ~0.49 for every `c`, so the signal is real at any weight, not an artifact of the calibration.

The mechanism: the *magnitude* of the verdict depends on the weight, but the *ranking* depends on the
aggregate of 23 axes, which concentrates and dilutes per-axis weight uncertainty. The `≤0` clamp on the
mismatch weight bounds it further — a wrong `c` can only soften an axis toward neutral, never manufacture
a false match. The curve is monotone with no pathological value, and the default `c = 0.95` is mildly
conservative: it under-reports AUC by ~0.003 relative to `c = 0.99`.

Reproduce: `python3 examples/weight_sensitivity.py`. (The pair sampler is now
`PYTHONHASHSEED`-independent, so these figures are reproducible for a given `.blkcache`; the third
decimal shifts only as the cache grows — the flatness, not the exact figures, is the result. The
`c = 0.95` row's 0.9333 is the headline AUC.)

## Honest limits

- **This moves `c` uniformly across all axes.** It tests robustness to the *global* assumption — the
  value actually hard-coded — not to `c` varying *per axis*, which is the finer epistemic concern. Fitting
  `m` per axis (an EM pass over the pair mixture, Splink-style) would test that; this establishes only
  that the aggregate has wide margin against the global knob.
- **Same labels and sampling caveats as the base validation.** Address-reuse labels share script type by
  construction; positives are sampled with replacement; a small fraction of random pairs may be truly
  same-wallet. See `RESULTS-fingerprint-validation.md`.
