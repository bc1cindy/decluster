# Broadcast-time fingerprint — coverage and calibration

Reproduce: `python3 -m decluster.broadcast`. Estimator + axis in `decluster/broadcast.py`
(`broadcast_window`, `locktime_vs_broadcast`), extractor `x_locktime_vs_broadcast`.

## Method
Miners fill blocks by feerate, so if block N−1's cheapest tx is below T's feerate, T was not
in the mempool at N−1 → broadcast in (N−1, N] (a *tight* bound). Otherwise T may have waited
(*loose*). The axis compares nLocktime to the estimated broadcast height. This de-confounds
the plain `locktime` axis, which uses the *inclusion* height: a tx that waited in the mempool
looks heavily backdated there even if it set locktime at broadcast. Here a loose bound →
`na_loose` (abstain), refusing that misleading verdict; we judge only when broadcast is
tightly bounded (see the de-confounding demonstration below).

There is no on-chain ground truth for broadcast time: the feerate bound is correct **by
construction**; we report coverage and calibrate the axis bits, and claim nothing more.

## Result
- Sample: 712 recent mempool.space txs (40 blocks × ~20 txs, uniform chain heights, seed=0).
- Tight-bound coverage: 674/712 = 94.7%.
- Axis distribution + calibrated bits (output of `python3 -m decluster.broadcast`):

```
# 712 txs   tight coverage: 674/712 = 94.7%

== locktime_vs_broadcast  (n=712, entropia=0.62 bits) ==
  no_locktime        610  85.67%    0.22 bits/match
  matches             99  13.90%    2.85 bits/match
  na_loose             2   0.28%    8.48 bits/match
  backdated            1   0.14%    9.48 bits/match
```

| value | share | bits/match |
|---|---:|---:|
| no_locktime | 85.67% | 0.22 |
| matches | 13.90% | 2.85 |
| na_loose | 0.28% | **0 (abstain)** |
| backdated | 0.14% | 9.48 |

`na_loose` is an **abstention**, so its stored weight in `library.py` is **0**, not the raw
−log2(share)=8.48 the calibrator prints from rarity. Rarity is not owner-linkage: "both txs
waited during congestion" is a market-wide condition, so scoring co-abstention as 8.48 bits
would forge a false same-owner link if the axis were fed to the combiner.

Chain-proven example for `matches`: `0ab4abca70d71f4554baa708a75604c0f05ad43f21f23cb0b25bd3e0e308b129`
(locktime=346028, block_height=346039 — locktime within 100 blocks of inclusion, tight bound).
The reference height is inclusion N; a tight bound puts broadcast in (N−1, N], so the tip a
wallet would encode is ~N−1 — one block inside the ±100 `matches` tolerance.

## De-confounding demonstration

The value over the plain `locktime` axis (which compares locktime to the *inclusion* height)
is shown by `tests/test_broadcast.py::test_deconfounds_plain_locktime`. A tx with
`locktime=700` included 200 blocks later at height 900, on a **loose** bound (it waited):

| axis | verdict |
|---|---|
| plain `locktime` (vs inclusion 900) | `height_other` — looks heavily backdated |
| `locktime_vs_broadcast` (loose bound) | `na_loose` — **abstains** |

The broadcast axis refuses the misleading "backdated" reading because the tx may have waited;
it judges (`matches`/`backdated`/`future`) only when the broadcast time is tightly bounded. In
the same test, a quickly-included tx (`prev_min < feerate`, `locktime` near the tip) reads
`matches`. So the axis is *designed* to remove a false-backdated verdict rather than re-label
it. This is shown as a unit case; in the 712-tx live sample the de-confounding is rarely
exercised (2 `na_loose`, 1 `backdated`), so the effect is demonstrated, not yet measured at
population scale.

## Honest limits
- No ground-truth broadcast time; only the bound is guaranteed.
- Loose for low-feerate txs during congestion (they wait many blocks) → `na_loose`.
- The cluster temporal fingerprint built on this estimate (activity schedule / timezone) was
  tested separately and is a **null** under proper controls (`results/RESULTS-temporal.md`).
