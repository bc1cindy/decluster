# Bayesian record linkage vs Fellegi-Sunter: what does the point estimate cost?

**Claim tested.** decluster's engine is Fellegi-Sunter — a per-pair verdict with a *point* estimate of
the per-axis same-wallet agreement rate `m`. F-S is the plug-in special case of Bayesian record linkage,
which puts a prior on `m` and integrates the uncertainty. We compare them on decluster's own evidence.
(The full Bayesian record-linkage program — a hierarchical model with a posterior over the *linkage
partition* itself, Larsen's "Hierarchical Bayesian Record Linkage," `fingerprints.md`— is MCMC over
partitions, "computationally prohibitive" at scale per the same corpus. This comparison uses a tractable
**pair-level** Gibbs, a deliberate retreat from that full-partition MCMC; the cluster-level band below is
the cheap propagation of the pair posterior, not the joint-partition posterior.)

**Method.** On 8000 reuse pairs (4000+4000, `cap=4000`), three scorers under the **same per-field
naive-Bayes likelihood** (`m_j`, `u_j = collision`; NOT the value-specific `combiner.fs_score`):
F-S(0.95) point, F-S(EM) point, and Bayesian (a light Gibbs over `(z, m)`, `Beta(8.5,1.5)` prior, `u`
fixed, `p_match` integrating the `m` posterior). Calibration (ECE) is evaluated against reuse labels;
the labels are not used to fit.

## Result

**Discrimination and calibration.**

| scorer | AUC | ECE |
|---|---:|---:|
| F-S(0.95) | 0.9324 | 0.1302 |
| F-S(EM) | 0.9438 | 0.0947 |
| Bayesian | 0.9443 | 0.0989 |

The AUC is a tie: F-S(EM) 0.9438 and Bayesian 0.9443 are indistinguishable (same evidence), so the
Bayesian's value is not discrimination — calibration is where it pays off: ECE drops sharply from the
assumed-`m` F-S(0.95) (0.1302) to both the fitted F-S(EM) (0.0947) and the Bayesian (0.0989), which are
essentially equally well calibrated, roughly 25–27% better than fixing every axis at 0.95. The AUC tie is
partly *structural*, not just empirical: all three scorers share the same per-field product likelihood,
so they cannot diverge on discrimination — holding the likelihood fixed is exactly what isolates the
point-vs-Bayesian question (the treatment of `m`), which is calibration and uncertainty, not ranking.

**Per-axis `m`: the Bayesian posterior vs the point estimates.**

| axis | Bayesian mean [95% CI] | EM | oracle | assumed |
|---|---|---:|---:|---:|
| nsequence | 0.945 [0.937, 0.953] | 0.946 | 0.979 | 0.95 |
| locktime | 0.987 [0.982, 0.991] | 0.987 | 0.996 | 0.95 |
| input_order | 0.819 [0.806, 0.830] | 0.819 | 0.811 | 0.95 |
| output_order | 0.605 [0.589, 0.622] | 0.604 | 0.622 | 0.95 |
| change_spk | 0.836 [0.824, 0.847] | 0.836 | 0.852 | 0.95 |
| version | 0.972 [0.966, 0.977] | 0.972 | 0.993 | 0.95 |
| io_shape | 0.616 [0.599, 0.635] | 0.615 | 0.605 | 0.95 |
| uih | 0.888 [0.879, 0.898] | 0.889 | 0.880 | 0.95 |
| fee_rate | 0.926 [0.919, 0.934] | 0.926 | 0.928 | 0.95 |
| input_script_type | 1.000 [0.999, 1.000] | 1.000 | 0.983 | 0.95 |
| output_encoding | 0.890 [0.881, 0.900] | 0.890 | 0.893 | 0.95 |
| input_types_present | 1.000 [0.999, 1.000] | 1.000 | 0.982 | 0.95 |
| change_index | 0.746 [0.733, 0.760] | 0.746 | 0.750 | 0.95 |
| change_type_match | 0.782 [0.770, 0.795] | 0.782 | 0.784 | 0.95 |
| change_matches_output | 0.767 [0.755, 0.779] | 0.767 | 0.768 | 0.95 |
| change_address_reuse | 0.845 [0.833, 0.855] | 0.845 | 0.872 | 0.95 |
| low_r | 0.862 [0.851, 0.872] | 0.862 | 0.865 | 0.95 |
| sighash | 0.996 [0.993, 0.997] | 0.996 | 0.984 | 0.95 |
| op_return | 0.945 [0.937, 0.953] | 0.945 | 0.986 | 0.95 |
| nested_segwit | 0.999 [0.998, 1.000] | 0.999 | 0.996 | 0.95 |
| pubkey_compression | 1.000 [0.999, 1.000] | 1.000 | 0.995 | 0.95 |
| multisig | 0.993 [0.990, 0.995] | 0.993 | 0.989 | 0.95 |
| locktime_vs_broadcast | 0.848 [0.596, 0.988] | 0.900 | n/a | 0.95 |

With 8000 pairs most axes are sharply identified — CIs a few thousandths wide — and on 20 of the 23
axes the assumed 0.95 falls *outside* the 95% CI, i.e. the point estimate is falsely precise at a value
the data reject. The reject runs both ways: `output_order` (0.605), `io_shape` (0.616), `change_index`
(0.746), `change_matches_output` (0.767) and `change_type_match` (0.782) agree far *less* often within a
wallet than 0.95 assumes, while `input_script_type`, `input_types_present`, `pubkey_compression`
(≈1.000), `nested_segwit` (0.999), `sighash` (0.996) agree *more*. Only `locktime_vs_broadcast` is
poorly identified — its CI [0.596, 0.988] is the sole *wide* one (`nsequence` and `op_return` contain
0.95 merely because their posterior means sit a hair above it) — because that
axis is rarely active, so few pairs constrain its `m`; there the honest posterior is "we don't know,"
exactly the state fixing `m` at 0.95 (or EM's 0.900 point) hides. This axis-by-axis gap is the epistemic
cost of a point estimate, made explicit. **One caveat on the clamped axes:** the tight `[0.999, 1.000]`
CIs on `input_script_type`/`input_types_present` are sharp around a value the oracle puts at 0.983/0.982
— i.e. tightly identified but *biased upward* by the conditional-independence inflation (same artifact as
the EM, `RESULTS-em-m.md`); "sharply identified" there means sharp, not necessarily correct. The Bayesian
means track EM to within a thousandth throughout, confirming F-S is the plug-in: same location, added
uncertainty.

**Cluster-level uncertainty (the Bayesian's unique output).** F-S gives a point entity count; the
Bayesian gives a *posterior band*. Two regimes make the difference concrete:

- **Clear structure** (50 address-reuse-linked coins): the band collapses to **[4, 4]**, coincident with
  the F-S point (4). When the same-owner structure is unambiguous, the point estimate loses nothing.
- **Ambiguous structure** (18 coins whose pairwise fingerprint links are borderline — intermediate
  P(match), chosen near the percolation threshold): the band is **[7, 10]** (mean 8.6) while the F-S
  point commits to a single **9**. The honest answer is "these 18 coins are 7–10 owners"; only the
  Bayesian carries that spread, and the point estimate hides it.

This is the calibrated cluster-level uncertainty the comment's Bayesian ask implies — *shown*, not just
asserted, once the node set is genuinely uncertain.

Reproduce: `python3 examples/bayes_vs_fs.py`.

## Honest limits

- **The AUC tie is the finding, not a null.** F-S and Bayesian share the evidence; the Bayesian adds
  calibrated uncertainty, not discrimination — F-S is its plug-in special case.
- **Axis-level, not the value-specific `fs_score`.** The comparison uses the per-field F-S both models
  share, to isolate point-vs-Bayesian; decluster's shipped scorer weights agreement by value rarity, an
  orthogonal enrichment.
- **Conditional independence** (per-axis terms multiplied) biases the `m` posterior on correlated axes
  the same way the EM is biased — cross-check against the oracle (`RESULTS-em-m.md`).
- **`u` fixed; `λ` from the enriched 50/50 pair mix; cluster sets are bounded**, not chain scale — an
  illustrative propagation of uncertainty, like the other case-study artifacts. The ambiguous-node band
  `[7, 10]` is on a purpose-selected borderline set (18 nodes near the percolation threshold); a
  strongly-structured set collapses it to a point (the clear-structure `[4, 4]`).
- **Prior sensitivity.** The `Beta(8.5,1.5)` prior (mean ≈ 0.85) is a modeling choice, anchored above
  chance to keep match the higher-agreement class; it is exposed as a parameter.
