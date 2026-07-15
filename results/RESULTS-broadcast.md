# Broadcast-time fingerprint — coverage and calibration

Reproduce: `python3 -m decluster.broadcast`. Estimator + axis in `decluster/broadcast.py`
(`broadcast_window`, `locktime_vs_broadcast`), extractor `x_locktime_vs_broadcast`.

## Method
Miners fill blocks by feerate, so if block N−1's cheapest tx is below T's feerate, T was not
in the mempool at N−1 → broadcast in (N−1, N] (a *tight* bound). Otherwise T may have waited
(*loose*). The axis compares nLocktime to the estimated broadcast height, de-confounding the
plain locktime axis (a tx that set locktime at broadcast then waited reads `matches`, not
`backdated`).

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
| na_loose | 0.28% | 8.48 |
| backdated | 0.14% | 9.48 |

Chain-proven example for `matches`: `0ab4abca70d71f4554baa708a75604c0f05ad43f21f23cb0b25bd3e0e308b129`
(locktime=346028, block_height=346039 — locktime within 100 blocks of inclusion, tight bound).

## Honest limits
- No ground-truth broadcast time; only the bound is guaranteed.
- Loose for low-feerate txs during congestion (they wait many blocks) → `na_loose`.
- Cluster temporal fingerprint (activity schedule / timezone) is a separate follow-on.
