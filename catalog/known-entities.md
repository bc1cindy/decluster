# Known entities and special-case fingerprints

The library (`decluster/library.py`, paper §3/§8) measures *generic*
transaction-construction fingerprints — signals every wallet emits. A whole-chain
de-anonymization also needs an *entity-specific* layer on top: known super-clusters that
must be treated specially, and construction/protocol signatures that identify a particular
service. These are strong priors and, crucially, the practical source of the independent
**entity labels** the co-spend labels cannot supply (paper §9/§10).

Status: this is a **backlog**, not built. Each entry notes the tell and how it maps to the
engine (an existing axis, a new axis, or an entity label).

## A. Super-clusters — tag them, don't merge blindly

A few services generate clusters so large they distort any monotone clustering (they
absorb unrelated activity). The entropy metric (§6, `graph_metric.py`) already flags them
via the largest-cluster fraction ("supercluster rejection"); the point here is to *tag* the
known ones rather than let them grow.

| Entity | Era | Why it superclusters |
|---|---|---|
| SatoshiDice | 2012–2013 | Gambling service; enormous volume of tiny bet/payout txs |
| Mt. Gox | –2014 | Dominant early exchange; huge consolidated cluster |
| Large exchanges | ongoing | Hot-wallet consolidation + batching across many users |
| Mining pools | ongoing | Coinbase fan-out to many miners |

## B. Entity-specific construction signatures

Concrete construction tells that identify a *specific* service — the same axes the library
measures, specialized to one entity.

| Entity | Era | Signature | Maps to |
|---|---|---|---|
| Coinbase (hot wallet) | ~2013–2017 | *Reported/anecdotal* (not independently verified here): uneconomic consolidations + anomalous fee estimation | `fee_rate` + `io_shape` (consolidation) |
| Binance | multi-year | Static per-user deposit addresses, reused → an entity's deposit flow (and per-user deposit clusters) is visible on chain for that era | address reuse (the validation label) |
| BitMEX | ~2015–2023 | `3BMEX…` / `bc1qmex` vanity-prefix deposit addresses on 3-of-4 P2SH multisig (the `3` prefix is P2SH); reissued to plain bech32 in Oct 2023 (legacy deprecated Mar 2025) | address vanity prefix + multisig type |

## C. Protocol structures and patterns

| Pattern | Signature | What it leaks |
|---|---|---|
| BIP-47 (PayNym; Samourai impl.) | Public per-recipient **notification transaction** (to a static per-recipient notification address) establishes each channel; **deterministic** coin selection | The payment-channel **social graph** (who notified whom) is permanently on chain; and because coin selection is deterministic, the coin used for the notification *rules out* the sender then holding smaller coins that would also have qualified — state leaked by what was **not** chosen |
| "Moby Dick" spam/dust campaign | Long fan-out chains (summer 2015) + later dust aggregation; analyzed by LaurentMT & A. Le Calvez (OXT) | A de-anon / stress vector; dust is also the main **confound** for address-reuse clustering (dust ≠ same owner) |

## How this plugs into the engine

- **Super-clusters (A):** a label plus a guard so they contract as a tagged unit and do not
  absorb neighbors.
- **Entity signatures (B):** high-weight priors on the weighted graph — "this tx was built
  by X" is strong evidence, on top of the generic per-axis bits.
- **Protocol structures (C):** dedicated detectors (a notification-tx recognizer, a
  dust-pattern recognizer) that emit both edges and labels.

Together these turn generic clustering ("these coins share an owner") into named-entity
attribution ("this owner is X") — the missing half of the whole-chain entity-reduction
measurement (§10).

## Sources

- BitMEX vanity/multisig deposit addresses and the Oct-2023 bech32 reissue —
  [BitMEX blog](https://blog.bitmex.com/reissuing-btc-wallet-addresses/)
- BIP-47 notification-transaction social-graph / coin-selection leak —
  [BIP-47](https://bips.dev/47/), [Samourai](https://blog.samourai.is/how-bip47-works/)
- "Moby Dick" spam/dust campaign (LaurentMT & A. Le Calvez, OXT) —
  [Bitcoin Magazine](https://bitcoinmagazine.com/technical/curious-case-bitcoins-moby-dick-spam-and-miners-confirmed-it)
