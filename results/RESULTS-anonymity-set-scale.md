# §04 provenance anonymity set at scale — live-fetch resolved subsample

`examples/anonymity_set_scale.py` walks real targets with **live ancestry fetch** (mempool.space,
not the shallow cache-only walk), keeps the ones whose graph-only walk actually branches, and on that
non-coinjoin subsample measures the §04 subjective-fusion sharpening and the `value_weighted` (Gap C)
ablation. Live network run; the walk uses the hard-bounded subset-sum oracle (a killed subprocess
returns `None` = the truncation boundary, not a fabricated link). Numbers below are from one run
(`results/scale_output.json`); the live network makes exact reproduction approximate.

## Headline

| quantity | value |
|---|---|
| targets tried | 30 |
| **resolved** (≥2 absorbers — real branching) | **15 (50%)** |
| graph-only mean entropy (resolved) | 2.48 bits (range 1.0–4.84; up to 162 absorbers) |
| subjective signal (address-reuse) coverage | **3 / 15 (20%)** |
| §04-fused mean entropy on covered | 2.38 bits |
| **§04 mean entropy reduction on covered** | **0.30 bits** (one clear case −0.83) |

## What this establishes

1. **Live-fetch deep walks work — data/connectivity is NOT the blocker.** Half the targets resolve
   with genuine provenance branching (2–162 absorbers, up to 4.84 bits). The earlier 2/34 collapse in
   the M1 run was the *cache-only* shallow walk; live fetch reaches real ancestry depth. So the
   BigQuery bulk export was never needed.

2. **§04 subjective fusion sharpens real provenance — when the signal fires.** On the 3 covered
   targets the link-level fusion reduced entropy by 0.30 bits on average; the clear case is
   `7787e8b6` (2 inputs, 15 absorbers): **graph 3.096 → fused 2.268 bits (−0.83)**. This confirms the
   §04 mechanism (Task-2 fixture, 1.0→0.304) on real branching walks, not just a synthetic fixture.

3. **Coverage is thin (3/15) — the honest limit.** The self-contained subjective signal
   (address-reuse self-transfer) fires on few non-coinjoin txs. The *strong* per-tx same-owner signal
   is coinjoin **demix** — which lives on exactly the coinjoin txs the oracle truncates. So full §04
   coverage is gated by the oracle, not by the signal design.

## The Gap-C result — `value_weighted` walk sharpens sharply (the strong finding)

The satoshi-flow-weighted walk (`value_weighted=True`, the deferred §04 flow rung) reduced entropy
**substantially on most resolved targets**, independent of the subjective signal's coverage:

| target | graph bits | value_weighted bits |
|---|---|---|
| 43892750 | 1.750 | **0.306** |
| 400984947 | 4.837 | **1.810** |
| c3c680d8 | 1.000 | **0.001** |
| 044ff8a8 | 1.000 | **0.037** |
| 400984… / 69a5… / f4cc… | 4.84 / 3.93 / 3.42 | 1.81 / 3.25 / 3.15 |

Across the 15 resolved targets, `value_weighted` is strictly lower than graph-only in 13 cases, tied
in one (`a467e531`), and higher in one (`a7fff057`: 3.944 → 4.039). This answers the Gap-C question —
**satoshi-weighting the provenance
walk concentrates the origin distribution markedly**, more than the subjective fusion did on this
sample. It was implemented opt-in (default off) precisely because it changes the numbers this much;
this run is the first real-data measurement of that effect.

## Honest limits

- **Non-coinjoin subsample bias.** The resolved set excludes coinjoin-heavy coins — their ancestry
  truncates because the exact subset-sum oracle can't evaluate dense mixes. A live probe found ~7/8
  arbitrary multi-input targets truncate on a coinjoin parent. So this validates §04 on non-coinjoin
  (peel-chain-ish) provenance, and the population is skewed toward simpler coins.
- **The ceiling is the oracle, not the data.** Full-population §04 validation (including coinjoins,
  where the subjective demix signal is strongest) is blocked until the subset-sum oracle handles dense
  coinjoins — the "Radics special case".
- **Conservative-lower-bound discipline.** Every entropy here is a lower bound / weight-of-evidence,
  not a privacy score. Same-owner labels drive the address-reuse signal.
- **Single live run.** Network variability means the exact target set and numbers are not bit-for-bit
  reproducible; the qualitative findings (deep walks resolve, §04 sharpens when covered, value_weighted
  sharpens strongly) are robust.

## Update — dss dense-coinjoin fast path (the Radix special case) lands

The numbers above predate the dss fix. The `dss` crate now recognizes dense coinjoins structurally
(≥2 output denominations each repeated ≥3×, covering ≥half the outputs — the transcript's "Radix"
case) and returns a **uniform link matrix** for them instead of timing out. Measured effect:

- **Mechanism (direct `dss.pairwise_link_prob`):** real 100- and 200-input coinjoins now return a
  uniform matrix in **0.00 s** (before: hung > 8 s → the harness's bounded oracle killed it → `None`
  → truncation).
- **Walk level (live proof, rebuilt dss):** targets whose **ancestry passes through real coinjoins**
  now resolve deeply — e.g. `d71490229941` (9 inputs) → **94 absorbers / 4.875 bits** (it fully
  collapsed to a point mass before the fix); `372fd5cb…` → 8 absorbers / 3.0 bits. This is the win:
  the coinjoin-ancestry truncation that dominated the earlier collapse is gone.
- **What still collapses is different and correct:** the remaining collapsed targets are
  **consolidations** (many inputs → few / distinct outputs, e.g. 203-in / few-out), not coinjoins. The
  recognizer correctly does **not** fire on them (no repeated denominations); their subset-sum is
  genuinely hard, so truncation there is the honest answer, not a bug.

**Caveat narrowed:** the "ceiling is the oracle" limit above no longer applies to coinjoins — those
now resolve. It narrows to **consolidation-style** (many-in / few-distinct-out) transactions, whose
exact subset-sum remains intractable and is out of scope for the Radix fast path. The dense matrix is
still the crude **uniform** approximation (max ambiguity); the exact radix-structured per-(i,o) matrix
is a deferred refinement.
