# Coinjoin de-mix — amount channel

The amount channel de-mixes a coinjoin by matching each participant's input to the mix denomination
plus their change output, minus a bounded maker fee: `input = mix + change − fee`
(`decluster/coinjoin_demix.py`). Two co-spent inputs assigned to different participants are
conclusively different owners (`amount_refuse_demix` → refuse), fused with the fingerprint and
cluster-level topology channels in `cluster_refined`.

## Worked de-anonymisation (real JoinMarket coinjoin)

`0cb4870cf2dfa3877851088c673d163ae3c20ebcd6505c0be964d8fbcc856bbf` — 11 participants, mix denomination
6357366 sats. The de-mix recovers **8 of the makers** uniquely (`examples/coinjoin_demix_demo.py`),
with maker fees `[191, 413, 458, 559, 623, 636, 687, 973]` sats. The remaining inputs (the taker and a
multi-input maker) are left unmatched. This reproduces the reference de-mix (`joinmarket_analyzer`).

## Dense coinjoins are amount-private

On the labelled Wasabi 2 coinjoins the de-mix recovers **0** participants — Wasabi 2's dense
denomination tiers defeat the match, so the coinjoins are amount-private and the fingerprint +
cluster-level topology channels carry the decision. This is the correct, decidability-dependent outcome.

## Specificity

Ordinary and batch payments have no mix+change+maker-fee structure, so the de-mix recovers no
participants (`examples/subtx_demix_specificity.py`) — it does not false-fire on single-owner txs.

## Fused with fingerprints (one engine)

The de-mix refuse is summed with the fingerprint and topology bits in `cluster_refined`
(`base[k] = cospend_prior + fp + refuse + topology`) and decided by one fixed-point
(`tests/test_amount_fingerprint_fusion.py`).
