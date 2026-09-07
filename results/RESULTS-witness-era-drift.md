# Witness-axis bits drift by era

> **Historical: the sample below was not preserved and this result is not reproduced.** Every
> figure on this page was measured on a `.blkcache` described as balanced across three eras. The
> cache this checkout preserves is **22,112 transactions over 904 block-page files, heights
> 800,000-965,220 — entirely post-Taproot**: zero pre-SegWit transactions, zero SegWit-era ones,
> and therefore no SegWit column to compute. The per-era table cannot be regenerated here, and no
> claim on this page should be cited as a measured multi-era fact. It stands as a record of what
> was run. `RESULTS-fingerprint-validation.md`, `RESULTS-em-m.md`, `RESULTS-bayes-vs-fs.md` and
> `RESULTS-catalog-axes.md` carry the same limitation for the same reason.

The library's witness-axis bits (`low_r`, `sighash`, `pubkey_compression`, `nested_segwit`,
`multisig`) were calibrated on a single ~3.5k recent mempool snapshot. This re-measures them
per era on the multi-era `.blkcache` (`examples/witness_bits_by_era.py`), splitting at the
SegWit (481,824) and Taproot (709,632) activation heights. Bits = `−log2(share)` within each
era's tx population — the same method as the library, applied per era.

Witness exists only post-SegWit, so pre-segwit is degenerate (all `na`) by protocol and
omitted below.

**Sample, as recorded at the time.** Balanced multi-era `.blkcache` (`examples/era_crawler.py`):
~180k txs — pre-segwit ~36k, **segwit ~35k, taproot ~110k** witness-bearing (exact counts grow with
the local cache). The per-era bits were reported stable across cache sizes (≤ 0.07 variation), and
the drift read as real structure rather than a small-sample artifact. None of that is checkable
now: the surviving cache is 22,112 transactions of one era, so the stability claim has no second
era to be stable across and the ~180k population is gone.

| axis | value | segwit bits | taproot bits | library snapshot |
|---|---|---:|---:|---:|
| low_r | `low_r` | 2.33 | **1.01** | 2.30 |
| | `not_low_r` | 2.72 | 1.82 | 2.68 |
| pubkey_compression | `compressed` | 2.64 | **0.46** | 1.86 |
| nested_segwit | `nested_segwit` | 1.88 | **4.01** | 3.15 |
| sighash | `taproot_default` | — (n/a) | 3.44 | 3.96 |
| | `all` | 1.51 | 0.38 | 1.49 |
| multisig | `multisig` | 4.08 | 4.88 | 4.02 |

## Reading — fingerprint bits have a temporal dimension

- **Low-R grinding went mainstream.** `low_r` drops from 2.33 bits (segwit era) to **1.01**
  (taproot era): a once-distinctive wallet tell became a coin-flip as grinding libraries
  spread. The library snapshot (2.30) tracks the *segwit* era, not the current one.
- **Compressed pubkeys, same story.** `compressed` falls 2.64 → 0.46 as native SegWit
  displaced the older mix.
- **Nested SegWit inverted.** `nested_segwit` rises 1.88 → **4.01**: P2SH-P2WPKH was a common
  transition wrapper in 2017–2021 and is now rare (native bech32 won), so it *gained*
  distinctiveness.
- **`taproot_default` is protocol-gated** — zero bits before block 709,632; it cannot appear
  in the segwit column.
- **`multisig` is stable** (~4 bits both eras): a genuinely rare construction throughout.

## Implication

A single bits number per axis-value is an approximation: for the witness axes it is
effectively an *era-weighted* snapshot, and the library's happens to sit near the segwit
era. This does **not** invalidate the validation headline (the pair-AUC is computed on the
multi-era `.blkcache` directly, not from these per-value bits), but it means the library's
witness bits should be read as era-representative, and a whole-chain model would carry
per-era (or time-conditioned) bits for the drifting axes. Adopting new bits into
`library.py` is deliberately **not** done here — it would shift the locked scored headline
and is a separate decision.

Reproduce: `python3 -m examples.era_crawler` (balance the cache across eras), then
`python3 -m examples.witness_bits_by_era`. On this checkout's cache the second step has one era to
report and the SegWit column comes back empty; rebuilding a genuinely multi-era cache is a crawl,
not a rerun, and until it is done nothing here is re-measured.

## Reproducibility / provenance

Not yet filed against `results/REPRODUCIBILITY.md`. This document has not been assigned one of the
five evidence states, so read its numbers as unclassified rather than as any of them.
