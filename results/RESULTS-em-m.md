# EM per-axis `m`: does the data-driven self-agreement rate match the assumed 0.95?

**Claim tested.** The Fellegi-Sunter combiner assumes a single same-wallet self-agreement rate
`c = 0.95` for every axis's disagreement weight (`decluster/combiner.py`), because `m` is not directly
measurable without same-owner labels — the epistemic challenge. This fits `m` per axis by **unsupervised
EM** (Winkler's EM for the F-S model), with `u` fixed at the measured `collision`, over the `reuse_pairs`
mixture with the labels **withheld**. The address-reuse label is held out as an oracle.

**Data.** 165832 witness-bearing transactions (`.blkcache`); 4000 reuse-positive + 4000 random pairs
(`seed=0`, PYTHONHASHSEED-independent). EM never sees the labels; `λ ≈ 0.571` reflects the ~50%
enrichment of the pair sample, not the corpus match rate.

## Result

**Per-axis m: EM vs oracle vs assumed.**

| axis | u (collision) | m_EM | oracle (reuse) | assumed |
|---|---:|---:|---:|---:|
| nsequence | 0.397 | 0.946 | 0.979 | 0.95 |
| locktime | 0.618 | 0.987 | 0.996 | 0.95 |
| input_order | 0.528 | 0.819 | 0.811 | 0.95 |
| output_order | 0.337 | 0.604 | 0.622 | 0.95 |
| change_spk | 0.378 | 0.836 | 0.852 | 0.95 |
| version | 0.535 | 0.972 | 0.993 | 0.95 |
| io_shape | 0.204 | 0.615 | 0.605 | 0.95 |
| uih | 0.854 | 0.889 | 0.880 | 0.95 |
| fee_rate | 0.708 | 0.926 | 0.928 | 0.95 |
| input_script_type | 0.378 | 1.000 | 0.983 | 0.95 |
| output_encoding | 0.614 | 0.890 | 0.893 | 0.95 |
| input_types_present | 0.377 | 1.000 | 0.982 | 0.95 |
| change_index | 0.555 | 0.746 | 0.750 | 0.95 |
| change_type_match | 0.584 | 0.782 | 0.784 | 0.95 |
| change_matches_output | 0.560 | 0.767 | 0.768 | 0.95 |
| change_address_reuse | 0.650 | 0.845 | 0.872 | 0.95 |
| low_r | 0.477 | 0.862 | 0.865 | 0.95 |
| sighash | 0.456 | 0.996 | 0.984 | 0.95 |
| op_return | 0.887 | 0.945 | 0.986 | 0.95 |
| nested_segwit | 0.803 | 0.999 | 0.996 | 0.95 |
| pubkey_compression | 0.604 | 1.000 | 0.995 | 0.95 |
| multisig | 0.887 | 0.993 | 0.989 | 0.95 |
| locktime_vs_broadcast | 0.756 | 0.900 | n/a | 0.95 |

**Does EM alone recover the label?** Posterior `r` separates reuse-positives from random pairs with
AUC **0.9438** — unsupervised EM recovers the reuse-label structure without ever being shown which pairs
share an input address. (This 0.9438 is the per-pair naive-Bayes posterior `r`; the pair-AUC table just
below, 0.9333–0.9462, is a *different* scorer — the 23-axis `LibraryScorer` with each `m` source plugged
into `consistency` — so the two AUCs are not the same measurement.)

**Pair-AUC by per-axis m source.**

| m source | AUC |
|---|---:|
| assumed 0.95 | 0.9333 |
| EM-fitted (per axis) | 0.9368 |
| oracle (per axis) | 0.9462 |

The per-axis fitted m values spread widely — from 0.604 (output_order) to 1.000 (input_script_type,
input_types_present, pubkey_compression) — confirming that the flat 0.95 assumption is inaccurate for
most axes. The pair-AUC improvement from EM-fitted m (0.9368) over the assumed scalar (0.9333) is modest
but consistent with the weight-sensitivity plateau documented in `RESULTS-weight-sensitivity.md`: the
combiner is relatively robust to m shifts in the middle of the score distribution, so even a substantially
different per-axis m yields only a small AUC gain. The oracle m achieves 0.9462, under a point above
EM (0.9368), indicating there is headroom that unsupervised EM does not fully capture. For correlated axes —
input_script_type and input_types_present both clamp to 1.000 in m_EM while the oracle sits at 0.983 and
0.982 — the upward bias is the expected conditional-independence artifact: EM treats them as independent
evidence and inflates their joint m to compensate. The divergence between m_EM and oracle for those axes
is the independence-violation signal, not noise. Axes with low self-agreement (output_order 0.604,
io_shape 0.615, change_spk 0.836) are structurally noisier across wallets regardless of reuse labels;
EM correctly identifies them as weak discriminators.

Reproduce: `python3 examples/em_m_fit.py`.

## Honest limits

- **Conditional independence is assumed and partly violated.** EM's E-step multiplies per-axis
  likelihoods as if axes were independent given match. Correlated axes (input script type, low-R,
  encoding) bias their `m_EM`; the gap from the oracle is exactly how that shows up — read the divergent
  rows as the independence-violation signal, not as noise.
- **`λ ≈ 0.571` is an artifact of the enriched population**, not the corpus match rate.
- **Same label/sampling caveats as the base validation** (address-reuse labels share script type by
  construction; positives sampled with replacement) — see `RESULTS-fingerprint-validation.md`.
- **Snapshot.** Figures wobble as `.blkcache` grows; the pattern (does EM recover the oracle; does the
  AUC stay flat) is the result.
