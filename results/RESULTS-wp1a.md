# WP1a — recalibrated evidence bits (real mainnet, unbiased)

Reproduce: `python3 -m decluster.measure recalibrate 40` (seeded, cached to `.cache`/`.blkcache`).
Sample: 861 non-coinbase txs, heights uniform in [200000, tip], **within-block
offsets fee-spread** (offset 0 = high-fee top; spread corrects the fee bias).

## De-biasing finding (the headline)
The nLockTime `zero` share moved with sampling method:
- top-of-block only (offset 0): **81.2%** ≈ the biased ~83% baseline
- **within-block fee-spread: 85.25%** (locktime entropy 0.90 → 0.74 bits)

Direction confirmed; the full ~95% (#1676) is **not reachable via the mempool.space
API** at low request cost — it needs uniform-over-ALL-txs sampling, which is exactly
what the **WP1b dense emitter** provides (every tx, no per-block API cap). Also
`floor=200000` excludes pre-anti-fee-sniping blocks (almost all `locktime=0`), which
holds the number below 95%. This is a documented limitation, not a silent gap.

## Per-axis bits (n=861)
| Axis | entropy | top value (share, bits/match) |
|---|---|---|
| nsequence | 1.39 | max_ffffffff (67.7%, 0.56) · rbf_fffffffd (15.7%, 2.67) |
| locktime | 0.74 | zero (85.3%, 0.23) · height_tip (10.1%, 3.31) |
| input_order | 1.11 | single (72.5%) · shuffle (17.5%, 2.51) · bip69 (10.0%, 3.32) |
| output_order | 1.51 | sorted_value (43.1%) · unsorted (37.8%) |
| change_spk | 1.92 | mixed (41.7%) · uniform_p2pkh (35.0%) · uniform_v0_p2wpkh (9.8%, 3.36) |
| version | 0.92 | v1 (66.1%) · v2 (33.9%, 1.56) |
| io_shape | 3.04 | 1in-2out (49.8%) · 1in-1out (13.9%) · 2in-2out (9.9%) |

**Rare-value tells (high bits/match = strong linkage):** `uniform_v1_p2tr` change
(4.54 bits), `bip69` input order (3.32), `rbf_fffffffd` nSequence (2.67) — these are
the specific, low-frequency fingerprints the combiner should weight most.

Feeds WP2 (per-axis measured bits for the fingerprint library) and is superseded for
the locktime distribution by WP1b once a mainnet dense index exists.
