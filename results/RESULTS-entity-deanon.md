# Entity-labelled strong-N-S probe on real data — a positive result and its boundary

The independent entity-label path (`decluster/entities.py` → `graph_deanon.entity_label_uf` /
`evaluate_entity`) tests the *strong* Narayanan–Shmatikov claim on **real BigQuery slices**: *does
payment-graph structure re-link same-entity addresses that co-spend leaves separate?*, using an
**independent** label (a vanity-prefix entity detector, disjoint from co-spend). The answer depends
entirely on the entity's *structure*, and the two cases below make the boundary precise.

## Positive — SatoshiDice (a service with recurring counterparties): AUC ≈ 0.72

**Slice.** 2013-08, blocks 250000–250150 (38,900 non-coinbase txs; SatoshiDice's peak era). Entity =
SatoshiDice, detected by the `1dice…` vanity prefix (`entities.detect_satoshidice`) — **42** distinct
house addresses (a small fixed set, one per bet ratio, heavily reused).

| structural score (payment-only, co-spend excluded) | AUC |
|---|---:|
| k=1 (common neighbours) | **0.73** |
| k=2 | 0.71 |
| k=3 | 0.73 |

Mean shared neighbours **7.95** between same-SatoshiDice pairs. Structure re-links the house addresses
**beyond co-spend**, robustly across depth — the strong N-S claim, demonstrated on real data with an
independent label. The mechanism is exactly the recurring-counterparty economics of a gambling
service: the same bettors play across several house addresses, so those addresses share a large
common-neighbour population that common-neighbours link prediction recovers.

## Null — BitMEX (a custodial hub): AUC ≈ 0.50

**Slice.** 2019-06, blocks 581000–581030 (74,130 txs; a high-volume BitMEX era). Entity = BitMEX,
`3BMEX…`/`bc1qmex` vanity (`entities.detect_bitmex`) — **2,642** distinct deposit addresses.

| structural score | AUC |
|---|---:|
| FULL (co-spend + payment), k=1 | 0.503 |
| PAYMENT-only (strong N-S), k=1 | 0.502 |
| PAYMENT-only, k=2 / k=3 | 0.500 / 0.514 |

Mean shared neighbours ~0.007; **zero** of ~3.5M pairs directly co-spent in-window. No signal at any
depth.

## What separates them — the boundary condition for the strong claim

Independent entity labels are *necessary* but not *sufficient*: the entity must sit in an
**economic graph with recurring peers**.
- **SatoshiDice** is such a graph — a fixed set of house addresses transacting with a *returning*
  bettor population → dense shared neighbourhoods → recoverable (0.72).
- **BitMEX** is a **hub-and-spoke star** — each deposit address links only to its own distinct
  depositor, and the shared hot wallet is reached only through consolidation that is a co-spend
  (excluded) or out of window → no shared structure (0.50).
- **Mining pools** (checked on the 2019 range) fail for a related reason: a pool's coinbase pays only
  2–4 outputs to a near-single reused payout address, and its recurring counterparties (miners) are a
  hop downstream in separate distribution txs — not a multi-address cluster with shared *direct*
  neighbours.

**Consequence for the program.** The strong N-S claim is now **empirically demonstrated** (SatoshiDice,
0.72) — and, importantly, *without external data*: it used a vanity-prefix detector on an entity
already named in `catalog/known-entities.md`. A curated address list (`catalog/entities.ndjson`) is
still what would unlock the *non-detectable* named entities (Mt. Gox, Binance, generic exchanges), but
it is no longer a prerequisite for the demonstration itself.

Reproduce: pull with `bigquery/graph.sql` (2013-08 / 250000–250150 for SatoshiDice; 2019-06 /
581000–581030 for BitMEX), then
`graph_deanon.evaluate_entity(sample, entities.detect_satoshidice)` (resp. `detect_bitmex`).
