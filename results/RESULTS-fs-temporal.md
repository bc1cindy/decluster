# Fellegi-Sunter, fit early / scored late, on the real transaction cache

**Sample limit stated up front.** `.blkcache/` holds 904 cached block-page files covering 22,112
distinct, complete (non-coinbase, fully-cached-input) transactions across 458 block heights
(800,000-965,220) — a block-sampled, non-contiguous slice, not a chain-wide or time-representative
population. Every number below is measured on exactly that slice; none of it supports a claim about
Bitcoin transactions in general, and it is not padded with data from any other source.

**Claim tested.** `decluster/fellegi_sunter.py` (supervised m/u Fellegi-Sunter, thresholds set from
tolerated error rates) and `decluster/fs_temporal.py` (block-height train/test split, address-reuse
weak labels, held-out evaluation against the repo's legacy value-rarity scorer — `combiner.rarity_score`,
exposed here through `LibraryScorer`, and never a Fellegi-Sunter model itself) exist and were unit-tested
on a synthetic fixture, but had never been run end to end on real cached transactions. This document is
that run.

**Method.** `examples/fellegi_sunter_temporal.py .blkcache --cap 4000 --seed 0 --train-fraction 0.7`
(the canonical run is `results/artifacts/fs-temporal-v1.json`, and `results/fs-temporal.json` is the
frozen historical report a test holds it against; every number below comes from that run
except the uncapped pair-pool row in the Split table, marked with a footnote). Transactions are
split at a block-height cutoff, strictly — the model is
fit only on pairs drawn from the train side and scored only on pairs drawn from the test side. Labels are
weak: a positive pair is two distinct transactions that share an observed input address (the same
address-reuse signal `fingerprint_validate.py` already uses); a negative pair shares no observed input
address. These are not independently verified same-owner labels — collaborative spends, address
transfer, and unseen history can flip either class, which is exactly why `label_provenance` in the JSON
carries `"independently_verified": false` rather than the word this repo does not use.

## Split

| | value |
|---|---:|
| transactions loaded | 22,112 |
| height range | 800,000 - 965,220 (458 distinct heights) |
| split strategy | strict block-height cutoff, `train_fraction=0.7` |
| cutoff height | 961,653 |
| train transactions | 15,100 (heights 800,000-961,653) |
| test transactions | 7,012 (heights 961,654-965,220) |
| train pairs (capped) | 4,000 positive / 4,000 negative |
| test pairs (capped) | 4,000 positive / 4,000 negative |
| positive pairs available before capping* | 153,122 (train), 64,521 (test) |

\* Not in the artifact — `weak_label_pairs` only reports the capped counts it actually drew.
These are the uncapped population sizes, recomputed directly from `.blkcache` (same split, same
`weak_label_pairs`, `cap=10**7` so no positive-side sampling ever triggers) and pinned in
`results/manifests/RESULTS-fs-temporal.json`. `tests/test_fs_temporal.py`'s
`test_manifest_invariants_are_recomputed_and_match_results_fs_temporal` recomputes them on every
test run and asserts the manifest is `ok` against that live recomputation, not just `identity-only`
against an unchanged byte digest.

## Fitted m/u and weights (train side, `alpha=0.5` pseudo-count)

Tolerated error rates `false_match_rate=0.05`, `false_non_match_rate=0.05` give thresholds
`non_link_below = -4.2479`, `link_at_or_above = +4.2479` in log2 likelihood-ratio units
(`decluster.fellegi_sunter.thresholds_from_error_rates`).

| field | m | u | agreement weight | disagreement weight |
|---|---:|---:|---:|---:|
| change_address_reuse | 0.9964 | 0.5547 | 0.845 | -6.941 |
| change_index | 0.7077 | 0.6205 | 0.190 | -0.377 |
| change_matches_output | 0.7039 | 0.6172 | 0.190 | -0.371 |
| change_spk | 0.6258 | 0.3817 | 0.714 | -0.725 |
| change_type_match | 0.7149 | 0.6320 | 0.178 | -0.369 |
| fee_rate | 0.9806 | 0.8899 | 0.140 | -2.507 |
| input_order | 0.9515 | 0.7295 | 0.383 | -2.479 |
| input_script_type | 0.9969 | 0.5028 | 0.988 | -7.308 |
| input_types_present | 0.9996 | 0.5147 | 0.958 | -10.327 |
| io_shape | 0.9208 | 0.4399 | 1.066 | -2.822 |
| locktime | 0.9999 | 0.7197 | 0.474 | -11.131 |
| low_r | 0.8384 | 0.3615 | 1.214 | -1.982 |
| multisig | 0.9991 | 0.8832 | 0.178 | -7.061 |
| nested_segwit | 0.9981 | 0.8537 | 0.226 | -6.287 |
| nsequence | 0.9919 | 0.4015 | 1.305 | -6.203 |
| op_return | 0.9999 | 0.9159 | 0.127 | -9.394 |
| output_encoding | 0.5930 | 0.4263 | 0.476 | -0.495 |
| output_order | 0.9744 | 0.4761 | 1.033 | -4.356 |
| pubkey_compression | 0.9989 | 0.5737 | 0.800 | -8.566 |
| sighash | 0.9994 | 0.6139 | 0.703 | -9.249 |
| uih | 0.9711 | 0.8712 | 0.157 | -2.158 |
| version | 0.9984 | 0.5015 | 0.993 | -8.261 |

All 22 comparison fields had both weak-label classes active in training and were used; none were
dropped for lacking observations on this slice.

## Held-out performance (test side, identical pairs for both scorers)

| metric | Fellegi-Sunter | rarity baseline (`LibraryScorer`) |
|---|---:|---:|
| AUC | 0.9827 | 0.9345 |
| **AUC delta (FS - rarity)** | **+0.0482** | |

Both AUCs above are the **exact** Mann--Whitney statistic with tie half-credit
(`graph_deanon.exact_auc`, called through `fs_temporal._score_metrics`), on the identical held-out
pairs. Note when comparing across documents: most other AUCs in `results/` — including the
`LibraryScorer` AUC in `RESULTS-fingerprint-validation.md` — come from `graph_deanon.auc`, which
*estimates* the same quantity from at most 20,000 sampled draws and carries sampling error in the
third decimal. The exact one is used here because the headline is a **difference** between two AUCs,
where two independent third-decimal errors are a large fraction of a +0.048 delta. The 0.9345 above
and any sampled-estimator figure for the same scorer are therefore not the same measurement to three
decimals, and neither is wrong.

FS decisions at the 0.05/0.05 thresholds: 3,989 link, 3,413 non-link, 598 review (coverage 92.5%).

| metric | value |
|---|---:|
| precision (of links) | 0.9551 |
| recall (of positives) | 0.9525 |
| coverage (decided / total) | 0.9253 |
| selective accuracy (of decided) | 0.9730 |

**Calibration** (case-control caveat: the test set is a balanced 50/50 weak-label sample, not the
population base rate, so Brier and ECE describe calibration *on this sample*, not population risk):
Brier 0.0425, ECE (10 bins) 0.0407, prior used for the posterior transform 0.50.

## Headline finding

**On this out-of-period test split, Fellegi-Sunter beats the rarity baseline: AUC 0.9827 vs 0.9345, a
delta of +0.0482, on the identical held-out pairs.** The rarity baseline is already strong (it was built
from the same axes), so the gap is a modest but real improvement from fitting per-axis m/u instead of
scoring value rarity alone — not a large-margin win.

## Seed sensitivity

Same command, `--cap 4000 --train-fraction 0.7`, five seeds (seed also reseeds the test-side weak
labels via `seed+1` inside `evaluate_temporal`):

| seed | FS AUC | rarity AUC | delta |
|---:|---:|---:|---:|
| 0 | 0.9827 | 0.9345 | 0.0482 |
| 1 | 0.9815 | 0.9351 | 0.0464 |
| 2 | 0.9818 | 0.9348 | 0.0471 |
| 3 | 0.9789 | 0.9327 | 0.0462 |
| 4 | 0.9812 | 0.9359 | 0.0453 |

Delta ranges 0.0453-0.0482 across five seeds (spread 0.003, about 6% of the mean delta): FS beats
rarity on every seed tried, by a consistent margin. The direction survives resampling on this slice;
it is not a lucky draw at seed 0.

## Cap and train-fraction sensitivity

| run | cap | train_fraction | FS AUC | rarity AUC | delta |
|---|---:|---:|---:|---:|---:|
| `--cap 2000` | 2000 | 0.7 | 0.9837 | 0.9310 | 0.0527 |
| `--cap 4000` (canonical) | 4000 | 0.7 | 0.9827 | 0.9345 | 0.0482 |
| `--cap 8000` | 8000 | 0.7 | 0.9805 | 0.9318 | 0.0487 |
| `--train-fraction 0.5` | 4000 | 0.5 | 0.9795 | 0.9280 | 0.0515 |
| `--train-fraction 0.6` | 4000 | 0.6 | 0.9810 | 0.9354 | 0.0456 |
| `--train-fraction 0.8` | 4000 | 0.8 | 0.9778 | 0.9307 | 0.0471 |

The delta stays positive and in a narrow 0.046-0.053 band across every cap and split tried; nothing
here suggests it is an artifact of one particular sample size or cutoff choice.

## Honest limits

- **904 files, 22,112 transactions, one non-contiguous slice.** This is a small-sample measurement of
  one attack instance, not a population claim about Bitcoin traffic generally.
- **Weak labels, not independently verified ownership.** Address reuse is a real same-owner signal but
  not proof: two distinct owners can reuse an address handed to them (payment requests, exchange
  deposit addresses), and unseen history can hide a real link inside a "negative" pair. `label_provenance`
  in the JSON marks this explicitly (`"independently_verified": false`).
- **Correlated axes on both sides.** FS's per-field product likelihood and the rarity baseline's scorer
  are built from the same fingerprint axes (`LibraryScorer.axes`), so the two are not independent
  measurements of the same population statistic — the delta reflects what per-axis m/u fitting adds over
  fixed-rarity scoring on this same evidence, not an unrelated method beating a naive one. The 22
  comparison fields fitted above are not 22 independent pieces of evidence either — one pair,
  `input_script_type` and `input_types_present`, is functionally one field on this population
  (phi coefficient 1.000 within both the match and non-match class); see
  `results/RESULTS-fs-ablation.md` for the full within-class dependence measurement and the
  leave-one-out/group ablation this document does not attempt.
- **"Fit early / scored late" is asymmetric between the two arms.** It holds strictly for the FS
  arm: `fit_model_for_error_rates` sees only train-side pairs, drawn from below the height cutoff.
  It does not hold for the rarity baseline. `LibraryScorer`'s per-axis value shares are
  `decluster/library.py`'s fixed priors, whose own provenance note records a uniform ~105k
  whole-chain BigQuery sample plus ~3.5k recent mempool.space transactions — neither restricted to
  below the height cutoff, and both plausibly covering the test window. The baseline is therefore
  not held out from the test period in the way FS is. The asymmetry runs *against*
  the headline — the baseline is if anything advantaged — which makes the +0.0482 delta a
  conservative reading rather than an optimistic one. It is stated because "fit early / scored late"
  in this document's own title reads as a property of the comparison, and it is a property of one
  arm.
- **Calibration is case-control.** Brier/ECE are computed on a balanced 50/50 sample; they describe how
  well-calibrated the posterior transform is on that sample, not on Bitcoin's true match/non-match base
  rate.
- **No fix to `decluster/fs_temporal.py` was needed.** The module ran cleanly against the real cache on
  the first attempt across every cap/seed/train-fraction combination tried above; nothing in this run
  exposed a bug.

## Reproducibility / provenance

Manifest: `results/manifests/RESULTS-fs-temporal.json`, written by
`decluster.reproducibility.write_manifest` over `.blkcache/*.json` (904 files, recorded as a byte
digest) with the population invariants this claim depends on: transaction count (22,112), height range
(800,000-965,220, 458 distinct heights), the split cutoff and train/test transaction counts, and the
uncapped positive-pair pool sizes on each side of the split (153,122 train, 64,521 test) — the facts a
byte digest of `.blkcache/` cannot see. `tests/test_results_manifests.py`'s generic walker only
confirms the source is unchanged (`identity-only`, since it never recomputes any doc's invariants
itself); `tests/test_fs_temporal.py::test_manifest_invariants_are_recomputed_and_match_results_fs_temporal`
is the one that actually recomputes every invariant above from `.blkcache` and asserts `check_manifest`
returns `ok` against that live recomputation. It skips cleanly, naming what went unrecomputed, on a
checkout without `.blkcache`.

Reproduce the canonical run with the command in `catalog/runs/fs-temporal-v1.json`. The example
behind it is `.venv/bin/python examples/fellegi_sunter_temporal.py .blkcache --cap 4000 --seed 0
--train-fraction 0.7` (the other rows above substitute the named flag), which writes to stdout.
