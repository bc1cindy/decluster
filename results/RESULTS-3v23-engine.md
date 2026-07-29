# 3-axis engine vs. 23-axis LibraryScorer on the merged-transaction anchor (real number for the §4 claim)

Reproduce: `./.venv/bin/python examples/three_vs_23_axes.py`. Offline — both coins are cached under
`.cache/`, no network required.

**Claim tested.** §4 argues that the engine's 3-axis `Combiner.from_library()` correctly refuses the
false Cake↔sender merge on the real merged transaction `931d6627` (§6, `RESULTS-wp4.md`), while the
full 23-axis `fingerprint_validate.LibraryScorer` would *resurrect* that false link if plugged into the
same pairwise scoring path. This measures both scores directly on the same edge.

## Result

| scorer | score (bits) | verdict |
|---|---:|---|
| 3-axis `Combiner.from_library()` | **−3.16** | REFUSE (correct — sender and Cake are different owners) |
| 23-axis `LibraryScorer` | **+11.67** | LINK (false — re-merges sender into the Cake cluster) |

The 3-axis figure matches `RESULTS-wp4.md`'s −3.1 (small drift is expected — `library.py`'s measured
bits are recalibrated over time, per WP4's own note; the test `test_wp4.py::test_merge_money_shot` pins
the *sign*, not the exact value). The 23-axis figure **is the real, reproducible number behind the
paper's "+11.7 bits" claim** — no invented figure.

## Per-axis breakdown (23-axis LibraryScorer, sender ↔ Cake)

| axis | sender value | Cake value | weight (bits) |
|---|---|---|---:|
| nsequence | max_ffffffff | seq_0x01_other | −3.59 |
| locktime | zero | zero | +0.43 |
| input_order | shuffle | single | −3.24 |
| output_order | single | single | +1.72 |
| change_spk | uniform_v0_p2wpkh | uniform_v0_p2wpkh | +3.42 |
| version | v2 | v2 | +1.42 |
| io_shape | 3in-1out | 1in-1out | −3.99 |
| uih | none | none | +0.12 |
| fee_rate | precise | precise | +0.28 |
| input_script_type | uniform_v0_p2wpkh | uniform_v0_p2wpkh | +2.18 |
| output_encoding | bech32 | bech32 | +2.93 |
| input_types_present | v0_p2wpkh | v0_p2wpkh | +2.18 |
| change_index | na | na | +0.48 |
| change_type_match | na | na | +0.48 |
| change_matches_output | na | na | +0.48 |
| change_address_reuse | none | none | +0.37 |
| low_r | low_r | low_r | +2.30 |
| sighash | all | all | +1.49 |
| op_return | none | none | +0.09 |
| nested_segwit | none | none | +0.17 |
| pubkey_compression | compressed | compressed | +1.86 |
| multisig | none | none | +0.09 |
| locktime_vs_broadcast | na | na | abstain |

**The mechanism is exactly the one §4 names.** The three genuinely discriminating, least-correlated
axes (`nsequence`, `input_order`, `io_shape`) all correctly refuse (−3.59, −3.24, −3.99 — these three
alone already sum to −10.8 bits). But the other 19 axes are dominated by *shared software/wallet-type
defaults* (`change_spk`, `input_script_type`, `output_encoding`, `low_r`, `pubkey_compression`,
`sighash`, `version`, ...) — both coins are ordinary v2 SegWit bech32 wallets, so they agree on nearly
every low-entropy policy axis. Those agreements are individually small (+0.09 to +3.42 bits each) but
numerous and positively correlated, and summing them under the (false) Fellegi-Sunter conditional-
independence assumption overwhelms the three real discriminators, flipping the total from −3.16 to
+11.67 bits — a **false LINK** that would re-merge the sender into the Cake cluster.

## Honest limits

- **One anchor, not a distribution.** Existence demonstration on the same real merged transaction as
  §6/WP4, not a swept statistic — consistent with `RESULTS-weight-sensitivity.md`'s broader finding that
  the 23-axis model's *ranking* (AUC) is robust even though its *raw magnitude* is not.
- **Direct-score comparison, not a full `cluster_refined` re-run.** This scores the same edge
  `LibraryScorer` and `Combiner.from_library()` would each feed into `cluster_refined`; both share the
  identical `fs_score` kernel, so the sign of this single-edge score is exactly what `cluster_refined`
  would act on for this pair (a positive score here clears the engine's default `link_above` threshold
  used in `RESULTS-wp4.md`).
