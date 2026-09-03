# Ablation of correlated axes in the Fellegi-Sunter model

**What this document is.** `decluster/fellegi_sunter.py` assumes conditional independence of
comparison fields given match status, and sums their log2 likelihood-ratio weights. Several
fingerprint axes in `decluster/library.py` plainly violate that (fields derived from the same
script type, the same signature encoding, or the same wallet behaviour move together). This
document measures the damage on the same real transaction cache and split used in
`results/RESULTS-fs-temporal.md`, rather than assuming it. It does not change that document's
headline (+0.0482 AUC over the rarity baseline); it asks a different question about the same model.

**Sample.** Same `.blkcache/` slice as `RESULTS-fs-temporal.md`: 22,112 transactions, heights
800,000-965,220, strict block-height split at cutoff 961,653 (15,100 train / 7,012 test
transactions). Same caveats apply: a block-sampled, non-contiguous slice; weak address-reuse
labels, not independently verified same-owner labels.

**Method.** `examples/fs_ablation.py .blkcache --seed 0` (saved to `results/fs-ablation.json`).
Implemented in `decluster/fs_ablation.py`, stdlib only.

## 1. Within-class association, not unconditional correlation

Unconditional correlation between two comparison fields is expected even under a perfectly valid
FS model: matches and non-matches differ systematically on every predictive axis, so pooling the
two classes induces spurious association between any two fields that are each individually
predictive (a Simpson's-paradox-style confound by class). The FS assumption is about association
*within* each class, so that is what is measured: the **phi coefficient** (the Pearson correlation
of two binary agree/disagree indicators; `phi = (n11*n00 - n10*n01) / sqrt((n11+n10)(n01+n00)(n11+n01)(n10+n00))`,
`decluster.fs_ablation.phi_coefficient`), computed separately within the match class and within the
non-match class, over comparison vectors built by `fs_temporal.fingerprint_fields()` on 8,000
train-side weak-labelled pairs (`association_cap=8000`, restricted to field pairs with at least 30
jointly-active observations in that class).

**Most dependent pairs** (by the larger of |phi_match|, |phi_non_match|):

| field a | field b | phi (match) | phi (non-match) |
|---|---|---:|---:|
| input_script_type | input_types_present | 1.000 | 1.000 |
| change_index | change_type_match | 0.977 | 0.950 |
| change_type_match | change_matches_output | 0.951 | 0.949 |
| change_index | change_matches_output | 0.948 | 0.944 |
| input_order | io_shape | 0.924 | 0.348 |
| output_order | io_shape | 0.446 | 0.884 |
| input_types_present | pubkey_compression | n/a (<30 in match) | 0.871 |
| input_script_type | pubkey_compression | 0.122 | 0.857 |
| input_types_present | sighash | 0.632 | 0.780 |
| input_script_type | nested_segwit | 0.778 | 0.415 |
| input_script_type | sighash | 0.301 | 0.776 |
| sighash | pubkey_compression | 0.547 | 0.714 |
| change_spk | output_encoding | 0.690 | 0.711 |

`input_script_type`/`input_types_present` are perfectly dependent in both classes (phi = 1.000):
on this population one is exactly a function of the other, so the FS model is currently double-
counting a single fact as two independent log-likelihood terms. The `change_index` /
`change_type_match` / `change_matches_output` triple and the `input_script_type`-adjacent
script/signature-encoding group are both strongly (phi > 0.6-0.98) associated within class as well.

**Clusters** (connected components at |phi| >= 0.6 in either class, a fixed, stated threshold, not
fitted to the data; single-linkage chaining means membership is a claim about connectivity at this
threshold, not that every internal pair is individually that strong):

1. `input_script_type`, `input_types_present`, `nested_segwit`, `pubkey_compression`, `sighash`
2. `change_index`, `change_matches_output`, `change_type_match`
3. `input_order`, `io_shape`, `output_order`
4. `change_spk`, `output_encoding`

## 2. Leave-one-out ablation

Each usable field removed one at a time, model refit on train, scored on the identical held-out
test pairs `RESULTS-fs-temporal.md` uses (`--cap 4000 --seed 0`, baseline AUC 0.9827, matching that
document). `auc_delta` is baseline AUC minus the AUC with that one field removed: positive means
removing it hurt, negative means removing it *improved* held-out AUC.

| field | AUC without it | auc_delta | coverage | selective accuracy |
|---|---:|---:|---:|---:|
| nsequence | 0.9707 | **+0.01195** | 0.895 | 0.9620 |
| version | 0.9737 | +0.00898 | 0.898 | 0.9621 |
| change_address_reuse | 0.9775 | +0.00520 | 0.903 | 0.9637 |
| low_r | 0.9792 | +0.00352 | 0.930 | 0.9712 |
| locktime | 0.9799 | +0.00275 | 0.907 | 0.9682 |
| op_return | 0.9812 | +0.00146 | 0.922 | 0.9714 |
| output_order | 0.9820 | +0.00070 | 0.918 | 0.9709 |
| fee_rate | 0.9823 | +0.00037 | 0.926 | 0.9721 |
| input_order | 0.9824 | +0.00025 | 0.931 | 0.9714 |
| multisig | 0.9827 | +0.00002 | 0.925 | 0.9735 |
| pubkey_compression | 0.9827 | -0.00005 | 0.919 | 0.9750 |
| uih | 0.9827 | -0.00005 | 0.929 | 0.9727 |
| nested_segwit | 0.9827 | -0.00006 | 0.921 | 0.9738 |
| input_types_present | 0.9828 | -0.00008 | 0.916 | 0.9750 |
| change_matches_output | 0.9828 | -0.00011 | 0.927 | 0.9728 |
| change_index | 0.9828 | -0.00013 | 0.928 | 0.9726 |
| change_type_match | 0.9828 | -0.00014 | 0.927 | 0.9729 |
| sighash | 0.9829 | -0.00020 | 0.921 | 0.9745 |
| input_script_type | 0.9831 | -0.00044 | 0.916 | 0.9753 |
| output_encoding | 0.9836 | -0.00092 | 0.926 | 0.9726 |
| change_spk | 0.9837 | -0.00103 | 0.924 | 0.9730 |
| io_shape | 0.9840 | **-0.00129** | 0.924 | 0.9724 |

**Reading it.** 12 of 22 fields have `auc_delta` <= 0: removing them individually does not hurt
held-out AUC, and for four of them (`io_shape`, `change_spk`, `output_encoding`,
`input_script_type`) it measurably helps. This is a majority-not-universal pattern, not a clean
rule: 11 of those 12 are members of a cluster from step 1 (`change_index`, `change_matches_output`,
`change_spk`, `change_type_match`, `input_script_type`, `input_types_present`, `io_shape`,
`nested_segwit`, `output_encoding`, `pubkey_compression`, `sighash`) — exactly what a correlated,
redundant axis looks like: on its own it looks harmless or even actively noisy to keep, because a
correlated partner already carries the same signal (and the partner's own m/u estimate absorbs the
discriminative content, so the removed field's disagreement penalty was mostly adding calibration
noise). The twelfth, `uih`, is **not** in any cluster at the 0.6 threshold — its strongest
association is phi 0.49 (match) / 0.25 (non-match) with `io_shape`, and phi 0.40 (match) / 0.44
(non-match) with `input_order`, both real but sub-threshold. My best read is that `uih`'s -0.00005
is mostly measurement noise: it is tied for the smallest-magnitude change in the whole table
(alongside `multisig`'s +0.00002 and `pubkey_compression`'s -0.00005), an order of magnitude below
the smallest effect I'd call real (`locktime` at +0.0028). The sub-threshold correlation to the
`io_shape` cluster is a plausible partial explanation if the effect is not pure noise, but nothing
here distinguishes the two, and at this magnitude it does not matter which is true.

Correlation membership does not fully predict the sign either: two members of the
`input_order`/`io_shape`/`output_order` cluster — `input_order` (+0.00025) and `output_order`
(+0.00070) — have small *positive* deltas, i.e. removing them individually costs a little rather
than nothing. Counting the full 13-field union of the four clusters against this table: 11 of 13
clustered fields have `auc_delta` <= 0, and 2 do not. Section 3 below shows this same cluster is
the one place where group ablation does not tell the clean redundancy story either.

The fields whose removal hurts most (`nsequence` +0.0120, `version` +0.0090, `change_address_reuse`
+0.0052, `low_r` +0.0035, `locktime` +0.0028) are none of them in a cluster from step 1 — each is
carrying information no other field supplies. That direction of the claim (informative ⇒
uncorrelated) holds without exception on this population; the reverse (correlated ⇒
uninformative-alone) holds for most but not all of the clustered fields, as above.

## 3. Group ablation

For each cluster from step 1: remove every member, versus remove every member but one
representative (the group member with the largest `|agreement_weight|` in the train-fitted full
model — chosen from train-side parameters only, no test-side information enters the choice).

| cluster | representative | remove-group delta | keep-representative delta |
|---|---|---:|---:|
| input_script_type, input_types_present, nested_segwit, pubkey_compression, sighash | input_script_type | **+0.00338** | -0.00007 |
| change_index, change_matches_output, change_type_match | change_index | **+0.00044** | -0.00009 |
| input_order, io_shape, output_order | io_shape | +0.00155 | +0.00112 |
| change_spk, output_encoding | change_spk | -0.00115 | -0.00092 |

**Reading it.** For the two strongest clusters (the script/signature-encoding group and the
change-position group), removing the whole cluster costs roughly the discriminative content of
the group's best member; keeping just that one representative recovers essentially all of it
(delta near zero, in fact very slightly negative — the fifth field's disagreement penalty was
adding a hair of noise rather than signal). This is the direction
`tests/test_fs_ablation.py::test_removing_the_whole_correlated_cluster_hurts_more_than_keeping_one_representative`
pins on the 5-field cluster, across six seeds, through `reproducibility.separable`.

Not every cluster tells the same story. For `input_order`/`io_shape`/`output_order`, both actions
cost a small positive amount (remove-group > keep-rep, same direction, smaller margin). For
`change_spk`/`output_encoding`, *both* deltas are negative: this correlated pair is net noise on
this population, and dropping it entirely beats dropping all-but-one. A blanket rule ("always keep
one representative per cluster") would be wrong here; the honest summary is that correlated
clusters are redundant with each other, not that every correlated field is individually valuable.

## Honest limits

- **Does not change the fs-temporal headline.** `RESULTS-fs-temporal.md`'s +0.0482 AUC delta over
  the rarity baseline is measured with all 22 fields present, as published; nothing here
  contradicts it. This document is about which of those 22 fields are carrying independent
  information, not about whether FS beats the rarity baseline.
- **Same weak labels, same slice.** Everything inherited from `RESULTS-fs-temporal.md`'s limits
  section applies here unchanged: block-sampled non-contiguous population, weak address-reuse
  labels (not independently verified same-owner labels), one out-of-period split.
- **Cluster threshold is a stated choice, not derived from the data.** `threshold=0.6` on the phi
  coefficient is a fixed, conventional "strong association" cutoff. Connected components can chain
  transitively through single-linkage; the 5-field cluster is one connected component at this
  threshold, not a claim that every pair inside it individually exceeds 0.6 (`sighash`-`nested_segwit`,
  for instance, is not in the top-15 pairs table above).
- **Representative selection uses the full model's fitted weights, which include the very
  correlation being ablated.** Picking the group member with the largest train-side
  `|agreement_weight|` is a reasonable proxy for "carries the group's signal alone," but it is not
  an independent measurement — a field's own m/u estimate is itself shaped by the correlated
  behaviour of the other axes it was fit alongside.
- **Leave-one-out changes are small relative to the FS-vs-rarity delta.** The largest single-field
  effect (`nsequence`, +0.012) is a quarter of the fs-temporal headline delta (+0.048); this
  analysis is about internal redundancy among FS's own inputs, not a comparably large finding on
  its own.

## Reproducibility / provenance

Manifest: `results/manifests/RESULTS-fs-ablation.json`, written by
`decluster.reproducibility.write_manifest` over `.blkcache/*.json` (904 files, byte digest) with
the population invariants this claim depends on: transaction count, split cutoff and train/test
transaction counts, the cluster threshold and the four clusters it produces, the single most
dependent field pair with its phi in each class, and the 22-field baseline AUC.
`tests/test_fs_ablation.py::test_manifest_invariants_are_recomputed_and_match_results_fs_ablation`
recomputes every one of those from `.blkcache` on each test run and asserts `check_manifest`
returns `ok`, not just `identity-only`. It skips cleanly, naming what went unrecomputed, on a
checkout without `.blkcache`.

Reproduce: `.venv/bin/python examples/fs_ablation.py .blkcache --seed 0 > results/fs-ablation.json`.
