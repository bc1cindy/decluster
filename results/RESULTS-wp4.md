# WP4 — merged transaction backward-channel demonstration (real bits)

Reproduce: `python3 examples/graph_demo.py` (bits from `fingerprints/library.py`, WP2).
Regression-guarded by `tests/test_wp4.py::test_merge_money_shot`.

## The graph
The ancestry graph of the real mainnet merged transaction **`931d6627`** — 7 coins: the merged transaction
itself, the Cake receiver coin (`0a568e3a`, `seq_0x01`), its lineage (`be2e3620`,
`seq_0x01`), the sender coin (`91106666`, `max_ffffffff`), and the sender's funding
chain (`5b97102c`, `89300d3b`, `b8c2bd60`, all `rbf_fffffffd`).

## The money-shot
**1) Union-find (common-input-ownership, BlockSci-style)** mis-merges the merged transaction:
it places **{Cake receiver `0a568e3a`, sender `91106666`}** in one cluster — exactly
the false link the merged transaction is designed to induce.

**2) Fingerprint-aware clustering (real measured bits)**:
- **REFUSES** the sender↔Cake merge at **−3.1 bits** (`max_ffffffff` vs `seq_0x01`,
  co-spent in `931d6627`) → the merged transaction is **re-partitioned**, sender isolated.
- **ADDS** the links the co-spend missed:
  - Cake lineage `0a568e3a ↔ be2e3620`: **+10.2 bits** (rare `seq_0x01` match).
  - sender funding chain (`5b97`, `89300d`, `b8c2bd`, `931d6627`): **+5.4 bits** each.

Net: the fingerprint-aware clusters are `{sender}`, `{Cake, Cake-lineage}`, and the
`{sender funding chain}` — the correct partition. Union-find gave the wrong one.

## Provenance of the bits
The scores are driven by **real measured mainnet bits** from WP2's `library.py`
(`Combiner.from_library()`), not a biased top-of-block sample. The biased-sample
version scored the refusal at −3.4 bits; with real unbiased bits it is **−3.1** —
recorded honestly. The +10.2 Cake-lineage link uses the unseen-value floor
(`seq_0x01` was not in the measured `nsequence` table), which only strengthens a rare
match.

## Honest caveats
- **Existence demonstration, not a statistical result.** One merged transaction, 7 coins. It
  shows the backward-channel breaks merged transaction privacy on a real tx; it does not measure
  a rate across the chain (that needs a mainnet dense index — WP1b, deferred).
- Thresholds (`refuse_below=-2.0`, `link_above=4.0`) are the prototype's; the sign of
  the refusal (−3.1) and the added links are what the regression test pins.
