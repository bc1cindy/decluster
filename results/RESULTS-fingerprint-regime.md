# Fingerprint N-S regime test: conditioner or sparse quasi-identifier?

> The reproducible 600-transaction comparison is recalculated by
> `catalog/runs/fingerprint-regime-v1.json`. Its structured artifact is
> `results/artifacts/fingerprint-regime-v1.json`, with canonical rendering in
> `results/generated/fingerprint-regime-v1.md`. It falsifies the historical assertion below that
> the conditioner verdict is stable across weight sources: snapshot-measured weights produce
> higher N-S-form top-1 than F-S and a within-class mean gap above 0.5. Those weights are fitted and
> evaluated on the same selected snapshot, so this demonstrates sensitivity rather than universal
> fingerprint sparsity. The cache-scale and Lumen rows below remain historical.

**Claim tested.** Does the per-tx fingerprint (`decluster/fingerprint_ns.py`: sparse
`{(axis,value): bits}` signature, agreement-overlap link, `propagate.eccentricity` acceptance
gap) behave as a sparse quasi-identifier — like ancestry — that can pick one individual out
of a crowd, or as a low-cardinality equivalence-class conditioner: it groups same-construction
transactions together but cannot further resolve *within* a group? The tx-graph anonymity-set
theory (posts 02/03 of the anonymity-set series) predicts the latter for construction-style
fingerprints and reserves the sparse-quasi-identifier regime for the ancestry channel
(`propagate.py`, post 03).

**Data.** 8,864 transactions from the local block-tx cache (`.blkcache`; this cache grows over
time, see Limits). Same-owner labels = address reuse (two txs spending the same input
address). `build_labeled_nodes` turns every reuse group of size ≥2 into one `owner_id`, capped at
200 nodes, assigning each tx to exactly one owner even when its inputs reuse more than one address
(the first qualifying group in sorted-address order; every other group it also belongs to is
skipped) — 200 labeled nodes, each a distinct txid, over 57 distinct owners (average group size
≈3.5).

**Method.** Two channels scored on the same reuse-pairs:

- **N-S** (`decluster/fingerprint_ns.py`): `fingerprint_link` = rarity-weighted agreement overlap
  only (no mismatch penalty), over up to three independent rarity sources — `library` (the 23-axis
  library's measured shares), `measured` (re-measured on this run's txs), `lumen` (an external
  prior, path given via the `LUMEN_PRIOR` environment variable, falling back to `library` per
  feature; the source is omitted entirely, not silently duplicated, if `LUMEN_PRIOR` is unset or
  the file doesn't exist).
- **F-S** (`decluster.fingerprint_validate.LibraryScorer`): agreement bits and clamped mismatch
  penalties over the same 23 axes — fixed across all rows since it doesn't consume the N-S rarity
  source.

**What the two arms actually differ in, since the labels overstate it.** The `FS_` columns are not
fitted Fellegi-Sunter and the `NS_` columns are not the 2009 propagation algorithm; the key names
are kept because they are written verbatim into
`results/artifacts/fingerprint-regime-v1.json`. Both arms sum `-log2(p)` rarity weights over the
same axes from the same shares. The **only** structural difference is that `LibraryScorer` adds a
clamped penalty when two axis values disagree and `fingerprint_link` does not. So the comparison
below isolates the mismatch penalty, and nothing more: it supports no conclusion about the
Narayanan--Shmatikov method, and none about Fellegi-Sunter, whose fitted `m`/`u` baseline
(`decluster/fellegi_sunter.py`) is not in this experiment at all.

Two measurements per source:

1. **Pairwise AUC** (the control) — 2,000 sampled same-address pairs vs. 2,000 random pairs,
   N-S link vs. F-S score.
2. **Candidate-set re-id** (the real test) — for each of the 200 labeled nodes, rank the other
   199 as candidates; top-1 accuracy for N-S (`reid_gap`) and F-S, plus the **within-class mean
   gap**: `reid_gap`'s eccentricity restricted to candidates sharing the query's
   `equivalence_key` (the conditioning axes `input_script_type`, `nsequence`, `input_order`,
   `output_order`, `version`) — 181 of 200 queries have ≥2 same-class candidates.

Reproduce: `LUMEN_PRIOR=<path to a prior JSON> .venv/bin/python examples/fingerprint_ns.py`
(omit `LUMEN_PRIOR` to run library/measured only).

## Result

| source   | NS_AUC | FS_AUC | NS_top1 | FS_top1 | within_gap (n=181) |
|----------|-------:|-------:|--------:|--------:|--------------------:|
| library  | 0.8895 | 0.9186 |   0.435 |   0.525 |                0.242 |
| measured | 0.9345 | 0.9186 |   0.510 |   0.525 |                0.366 |
| lumen    | 0.9332 | 0.9186 |   0.480 |   0.525 |                0.225 |

## Reading

**Pairwise AUC is a tie, as expected — it is the control, not the finding.** NS_AUC (0.890–0.935
across sources) sits close to FS_AUC (flat 0.919, since F-S doesn't vary with the N-S rarity
source). Both channels sum agreement bits over the same axes; a near-tie confirms the harness is
wired correctly, it doesn't distinguish the two regimes.

**Candidate-set re-id is the real test, and it comes out the same way in all three sources.**
NS_top1 (0.435 / 0.510 / 0.480) is below FS_top1 (0.525, flat) in every source — N-S never beats
F-S at picking the one true owner out of 199 candidates. Combined with the within-class mean gap
(0.225–0.366): the mean within-class gap sits below the θ≈0.5 reference used by `propagate.py`'s
driver default (this is a comparison of the *mean* against that reference, not a measured
per-query acceptance/clearance rate — `run_regime` does not compute what fraction of within-class
queries individually exceed θ). A mean that low, on top of NS_top1 trailing FS_top1, is consistent
with candidates in the query's own equivalence class being hard for the fingerprint channel to
tell apart. That's the equivalence-class-conditioner signature, not a sparse quasi-identifier: the
fingerprint sorts transactions into a construction-style bucket, it doesn't single one out inside
the bucket.

**Verdict: conditioner, stable across all three rarity sources.** Library, measured, and lumen
weightings agree on both signs — NS_top1 < FS_top1, within-class gap under θ — so this isn't an
artifact of one weighting scheme. No source shows N-S materially beating F-S at re-id, so there is
no surprise to chase here. The sparse N-S regime — where a signature *does* pick one node out of a
crowd — lives on the ancestry channel (`propagate.py`, see `results/RESULTS-ns-propagation.md`),
not on construction-style fingerprints.

## Limits

- **The `.blkcache` is a growing local artifact, not a fixed dataset.** Absolute numbers here are
  specific to this checkout's cache at measurement time (8,864 txs; an earlier run against 8,129
  txs gave NS_AUC 0.885–0.922 and NS_top1 0.500–0.575 — same signs, different digits) — the same
  caveat other `RESULTS-*.md` files carry for cache-derived figures. The direction of the result
  (conditioner, not quasi-identifier) is what's load-bearing, not the third decimal.
- **200-node cap, 57 owners.** The candidate-set re-id numbers are drawn from a small, capped
  sample (`build_labeled_nodes(txs, cap=200)`); the within-class gap has 181 supporting queries,
  not independent — many share the same handful of reuse groups' equivalence classes.
- **Labels are address reuse**, same caveat as `results/RESULTS-fingerprint-validation.md`: reused
  addresses also share script type, so part of the equivalence-class collapse is by construction,
  not purely a property of the fingerprint model.
- **`measured` is fit and evaluated on the same txs it's scored against** — its NS_AUC (0.935) is
  optimistic relative to an out-of-sample rarity fit; `library` (0.890, fit elsewhere) is the more
  read of the conditioner effect's size.
- **θ≈0.5 is cited from `propagate.py`'s driver default for scale, not re-derived here** — the
  claim is the within-class gap sits at or under a threshold used elsewhere in this pipeline, not
  a formally re-fitted cutoff for this exact channel. The `measured` source's gap (0.366) is the
  closest of the three to that line.
