# Known entities and special-case fingerprints

The library (`decluster/library.py`, paper §3/§8) measures *generic*
transaction-construction fingerprints — signals every wallet emits. A whole-chain
de-anonymization also needs an *entity-specific* layer on top: known super-clusters that
must be treated specially, and construction/protocol signatures that identify a particular
service. These are strong priors and, crucially, the practical source of the independent
**entity labels** the co-spend labels cannot supply (paper §9/§10).

Status. The label **machinery is built**; what remains for the named exchanges is data. Three kinds:

- **Named detectors** (`decluster/entities.py`, `tests/test_entities.py`) — an on-chain marker
  identifies the entity by name, no external data: **BitMEX** vanity (§B, 437 hits), **SatoshiDice**
  `1dice` vanity (§A, 42 house addrs, the strong-N-S positive), **mining pools** by coinbase tag (§A,
  588 hits / 18 pools), **BIP-47** notification txs (§C, 605), **dust fan-out** / Moby Dick (§C, 28).
- **Behaviour proxies** (◐) — the on-chain *pattern* is detected but not the *brand*:
  `detect_consolidation` / `detect_batching` (§A large exchanges, §B Coinbase-wallet) flag the sweep /
  batch behaviour; which company did it still needs a curated seed.
- **Curated lists** (`entities.load_curated`, schema `catalog/entities.example.ndjson`) — for the named
  entities that carry **no** on-chain signature at all (Mt. Gox, a *specific* exchange, Binance-the-brand):
  an address is that entity only because a tagged source says so, so the loader is the only path;
  `catalog/entities.ndjson` is populated externally (not shipped). This boundary is fundamental, not a
  gap — it is why the framework boxes KYC/exchange labelling out of the entropic model.

Both feed one **independent** same-owner label path — disjoint from the co-spend heuristic — through
`graph_deanon.entity_label_uf` / `evaluate_entity`, the label source the strong Narayanan–Shmatikov
claim needs (§8/§9). Remaining backlog: the Coinbase-wallet signature (§B, needs verification) and,
above all, populating the curated list. Each entry notes the tell and how it maps to the engine.

## A. Super-clusters — tag them, don't merge blindly

A few services generate clusters so large they distort any monotone clustering (they
absorb unrelated activity). The entropy metric (§6, `graph_metric.py`) already flags them
via the largest-cluster fraction ("supercluster rejection"); the point here is to *tag* the
known ones rather than let them grow.

These carry **no self-contained on-chain signature** — an address is Mt. Gox only because a tagged
dataset says so — so they are **not** detectable by code; they come from a curated NDJSON list instead.
The **loader is built** (`entities.load_curated` / `entity_of` / `curated_labeler`, schema in
`catalog/entities.example.ndjson`), feeding the same independent-label path as the detectors
(`graph_deanon.entity_label_uf`); what remains is **populating** `catalog/entities.ndjson` from tagged
sources (no third-party address data is shipped in-repo).

| Entity | Era | Why it superclusters | Source |
|---|---|---|---|
| SatoshiDice ✅ | 2012–2013 | Gambling service; enormous volume of tiny bet/payout txs; `1dice…` vanity house addresses | **built**: `entities.detect_satoshidice` — the strong-N-S **positive** demonstrator (AUC ≈0.72, `results/RESULTS-entity-deanon.md`) |
| Mt. Gox | –2014 | Dominant early exchange; huge consolidated cluster | curated list |
| Large exchanges ◐ | ongoing | Hot-wallet consolidation + batching across many users | **behaviour built** (`entities.detect_consolidation` / `detect_batching`, 2.7k / 3.9k cache hits) — flags the pattern; the *brand* (which exchange) still needs the curated list |
| Mining pools ✅ | ongoing | Coinbase fan-out to many miners; **coinbase-tag** self-ID (`/F2Pool/`, `/AntPool/`, …) | **built**: `entities.detect_mining_pool` (coinbase-tag → pool + payout addr; 588 hits / 18 named pools on the cache) |

## B. Entity-specific construction signatures

Concrete construction tells that identify a *specific* service — the same axes the library
measures, specialized to one entity.

| Entity | Era | Signature | Maps to |
|---|---|---|---|
| Coinbase (hot wallet) ◐ | ~2013–2017 | *Reported/anecdotal* (not independently verified here): uneconomic consolidations + anomalous fee estimation | **behaviour built**: `entities.detect_consolidation` (`io_shape` proxy) — flags the consolidation *pattern*; attributing it to Coinbase specifically needs a curated seed |
| Binance | multi-year | Static per-user deposit addresses, reused → an entity's deposit flow (and per-user deposit clusters) is visible on chain for that era | curated list (address reuse identifies the *pattern*, not that it is Binance) |
| BitMEX ✅ | ~2015–2023 | `3BMEX…` / `bc1qmex` vanity-prefix deposit addresses on 3-of-4 P2SH multisig (the `3` prefix is P2SH); reissued to plain bech32 in Oct 2023 (legacy deprecated Mar 2025) | **built**: `entities.detect_bitmex` (address vanity prefix + multisig type) |

## C. Protocol structures and patterns

| Pattern | Signature | What it leaks |
|---|---|---|
| BIP-47 (PayNym; Samourai impl.) ✅ | Public per-recipient **notification transaction** (to a static per-recipient notification address) establishes each channel — an 80-byte OP_RETURN blinded payment code plus the notification payment; **deterministic** coin selection. **Built**: `entities.detect_bip47_notification`. | The payment-channel **social graph** (who notified whom) is permanently on chain; and because coin selection is deterministic, the coin used for the notification *rules out* the sender then holding smaller coins that would also have qualified — state leaked by what was **not** chosen |
| "Moby Dick" spam/dust campaign ✅ | Long fan-out chains (summer 2015) + later dust aggregation; analyzed by LaurentMT & A. Le Calvez (OXT). **Built**: `entities.detect_dust_fanout` (many dust-value outputs sprayed at once; 28 hits on the witness cache). | A de-anon / stress vector; dust is also the main **confound** for address-reuse clustering (dust ≠ same owner) — the detector is a **guard** (don't cluster dusted addresses), not a same-owner label |

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
