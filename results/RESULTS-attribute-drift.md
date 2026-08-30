# Attribute stability across epochs

**Claim tested.** Cross-view matching contracts two epochs of the coin graph into two
views of the pseudonym graph, then compares vertices between them. Statistical
fingerprint distributions are proposed as vertex attributes. Does an attribute mean the
same thing in both views?

**Data.** The same 2026 survey as `RESULTS-fingerprint-sparsity.md`: blocks
939 969–962 720, 158 epochs of 144 blocks (≈1 day), 98 179 414 transactions, 21 axes.

**Method.** Each epoch gives one distribution per axis. Drift is the total-variation
distance between two epochs' distributions, averaged over all pairs at a given gap.
Volume coupling is the Pearson correlation between an axis value's per-epoch share and
that epoch's transaction count, a covariate every vertex shares.

## Result

| axis | TV@1 | TV@7 | TV@30 | TV@120 | weekly gain |
|---|---:|---:|---:|---:|---:|
| nlocktime | 0.009 | 0.011 | 0.013 | 0.018 | 0.86 |
| locktime_offset | 0.009 | 0.011 | 0.013 | 0.018 | 0.86 |
| input_order | 0.019 | 0.020 | 0.027 | 0.035 | 0.84 |
| version | 0.029 | 0.026 | 0.042 | 0.071 | **0.75** |
| round_feerate | 0.025 | 0.027 | 0.037 | 0.060 | 0.84 |
| low_s | 0.024 | 0.034 | 0.064 | 0.088 | 1.07 |
| low_r | 0.038 | 0.052 | 0.090 | 0.155 | 1.04 |
| sighash | 0.027 | 0.036 | 0.068 | 0.152 | 1.05 |
| change_position | 0.076 | 0.081 | 0.125 | 0.241 | 0.85 |
| feerate_bucket | 0.094 | 0.097 | 0.135 | 0.156 | 0.85 |
| output_types | 0.089 | 0.102 | 0.153 | **0.278** | 0.89 |

*Weekly gain* = mean drift at gaps that are multiples of 7, over mean drift at every other
gap up to 21. Below 1.0 means same-weekday epochs are genuinely more comparable.

- **Secular trend, gap-120 / gap-1: median 3.12×, max 5.69×.** Drift keeps accumulating;
  it is not stationary noise.
- **Weekly cycle: median gain 0.88, best 0.75.** Drift dips at gaps 7, 14 and 21 and peaks
  at 4–5, 11–12 and 17–18, in every axis and in the transaction-count series itself.
- **Common mode: 70 of 85 axis values correlate with epoch volume above |r| 0.5, median
  r² 54.2 %**, reaching r² 88 % (`change_type=P2pkh`) and covering values with very large
  shares (`version=2` at 82 % share, r² 80.6 %; `input_age=SameBlock` at 59 %, r² 82.0 %).

## Reading

**Two epochs a week apart are more comparable than two epochs two days apart.** For
`change_position`, TV is 0.081 at a gap of 7 but 0.101–0.110 at gaps of 2 to 5. The
epoch is a day, so a gap that is a multiple of 7 compares like weekday with like. View
separation should be chosen on the cycle, not on mere proximity.

**Most of an attribute's apparent movement is one global covariate.** Half the variance of
a typical axis value tracks epoch transaction volume, which shifts every vertex in the
same direction at once. Comparing raw attribute values across two views therefore carries
a systematic bias, not merely added noise. Each vertex's attribute must be expressed
relative to its own epoch's base rate before it crosses the view boundary.

**The two failure modes are separable, and the axes sort by which one they suffer.**
Economic axes (change position, feerate, output types, input age) carry the weekly cycle
and the volume coupling. Signature-level axes (`low_r`, `low_s`, `sighash`,
`uncompressed_pubkey`) show weekly gain at or above 1.0, i.e. no cycle at all, because
they track wallet software rather than when people transact; what they suffer instead is
secular drift as the software population turns over (`low_r` 0.038 → 0.155, 4.1×).

**Stability and independence trade off.** The most stable axes are also strongly
volume-coupled (`nlocktime` TV@7 0.011 but worst r² 51.9 %), while the least coupled is
middling in stability (`low_s` worst r² 27.8 %, TV@7 0.034). No axis is good at both, so
a vertex attribute has to be built from several and normalised, not picked.

## Consequences for cross-view matching

1. Separate the two views by a multiple of 7 epochs, preferring 7 or 14.
2. Normalise every attribute against its own epoch's base rate. Unnormalised attributes
   are biased by a covariate explaining a median 54 % of their variance.
3. Draw attributes from the stable end (`nlocktime`, `locktime_offset`, `input_order`,
   `version`, `round_feerate`), and treat `output_types`, `feerate_bucket` and
   `change_position` as unusable across a boundary at 4–8× the drift.
4. Attributes condition, they do not score: at a single-epoch scope only 2.35 % of
   transactions sit in a fingerprint class smaller than ten
   (`RESULTS-fingerprint-sparsity.md`).

## Scope

Population base rates, not per-cluster attributes. This bounds the common-mode shift a
normalisation must remove and ranks the axes; it does not measure how distinctive one
cluster's attribute distribution is, which needs a clustering.

## Reproduce

```sh
python3 examples/attribute_drift.py <epochs.jsonl>
```
