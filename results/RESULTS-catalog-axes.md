# Two Möser–Narayanan tells, tested against the 23-axis model

> A reproducible ablation on the frozen 600-transaction snapshot is defined by
> `catalog/runs/fingerprint-catalog-axes-v1.json`. Its structured artifact is
> `results/artifacts/fingerprint-catalog-axes-v1.json`, with canonical rendering in
> `results/generated/fingerprint-catalog-axes-v1.md`. It uses one pair population for all four
> configurations. On this snapshot, output count decreases AUC by 0.000725, SegWit serialization
> increases it by 0.002600, and both together increase it by 0.002125, less than SegWit alone. This
> is consistent with the historical redundancy concern but does not prove conditional dependence.
> The two historical cache snapshots below were not preserved and are not reproduced.

The record-linkage corpus (`fingerprints.md`, Table 4) lists two construction fingerprints
the paper's axis catalog (§8) marks ◐ — **output count** ("more than two outputs is less
likely an ordinary wallet") and **SegWit-conform** ("a segwit-capable wallet is forced to
non-segwit serialization when no input is segwit"). This measures whether adding them to the
canonical 23-axis rarity scorer buys anything. It does not — and the *shape* of the
non-result is the point.

(The scorer is `fingerprint_validate.LibraryScorer`, called the Fellegi-Sunter scorer here until
now. It is not: agreement carries Newcombe's `-log2(p)` rarity weight and disagreement a clamped
penalty from an assumed consistency, with no fitted `m`/`u`. The fitted Fellegi-Sunter baseline is
`decluster/fellegi_sunter.py` and is a different object. Nothing measured below changes — only what
it is called.)

## Probes

Two throwaway single-tx extractors (not shipped — they earn no place in the library, see
below), added to `LibraryScorer` and scored on the same seeded reuse-pairs as
`RESULTS-fingerprint-validation.md`:

```python
def x_output_count(tx):
    m = len(tx["vout"]); return "1" if m == 1 else "2" if m == 2 else "3" if m == 3 else "4plus"
def x_segwit_serialization(tx):
    return "segwit" if any(v.get("witness") for v in tx["vin"]) else "non_segwit"
```

Bits = `−log2(share)` on the local `.blkcache` (~166k): output_count `{2: 0.51, 1: 2.33,
4plus: 4.17, 3: 4.45}`; segwit_serialization `{segwit: 0.60, non_segwit: 1.56}`.

## Result — measured on two cache snapshots

Absolute AUCs are `.blkcache`-specific (the cache is a local, growing artifact — see
`RESULTS-fingerprint-validation.md`); the **deltas** are the finding, and they are not even
stable across two cache sizes on the same seeded pairs:

| adding to the 23-axis scorer | Δ AUC @ 166k cache | Δ AUC @ 180k cache |
|---|---:|---:|
| + output_count | +0.0011 | **−0.0012** |
| + segwit_serialization | +0.0026 | +0.0020 |
| + both | +0.0025 | +0.0006 |

(The base AUC itself drifts 0.9328 → 0.9416 as the cache grows — that is the pair-sample
moving, not the axes.)

## Reading — this is a double-counting artifact, not new signal

- **The delta is not even sign-stable.** `output_count` moves from **+0.0011** (166k) to
  **−0.0012** (180k) — it *flips sign* between two samples of the same cache. A contribution
  whose sign depends on the sample is noise, not signal: the cleanest possible evidence the
  axis carries no independent information.
- **The bigger magnitude comes from the *more redundant* axis.** `segwit_serialization` is
  nearly determined by `input_script_type` (+ `nested_segwit`), yet it moves the AUC more
  (~±0.002) than `output_count`. In a naïve-Bayes product-of-axes scorer, adding an axis
  correlated with one already present **re-counts the same evidence**: same-wallet pairs share
  their input script type by construction (address-reuse label → same type), so counting
  "both are segwit" on top of "both are `v0_p2wpkh`" inflates the positive-pair scores. A
  redundant axis producing the larger swing is the signature of that double-count.
- **Not additive.** Both together ≤ segwit alone on *both* snapshots: `output_count` adds
  essentially nothing once `segwit_serialization` is in. Independent signals would add up.
- **Within noise, though by less than was claimed.** Every delta above is smaller than the EM
  per-axis-`m` refinement (+0.0035, `RESULTS-em-m.md`). The weight-sensitivity comparison used to
  read "AUC moves ~0.04 across the realistic `c` sweep", which overstates the floor by about 2.5x:
  `results/generated/weight-sensitivity-v1.md` puts the full 0.60-0.99 grid at **0.0161**
  (0.9084 to 0.9245) and the realistic 0.90-0.99 band at **0.00055**. Read against the band that
  actually brackets the shipped `c=0.95`, the +0.0026 and +0.0020 deltas are *larger* than the
  weight sensitivity, not deep inside it. What keeps them out of the model is the sign flip and the
  non-additivity above, not a noise floor wide enough to swallow them.

## Conclusion

The canonical 23-axis model **correctly excludes** both. `output_count` is subsumed by
`io_shape`; `segwit_serialization` by `input_script_type` + `nested_segwit`. Folding them in
would violate the scorer's conditional-independence assumption and buy only a
double-counting artifact whose contribution is not even sign-stable — so they stay out, and the library ships no
extractor that no result consumes. `fingerprints.md` does not cover the taproot
script-tree-depth-from-round-fee leak (a separate derived signal) or "change is always
bech32" (a cross-transaction consistency claim, not a single-tx bit); both remain out of
scope.
