# Tx-construction fingerprint matrix (issue #1597)

Companion to `research-docs/fingerprints/merged transaction.md` and to the network-level
harness seed (`docs/superpowers/specs/2026-05-27-fingerprint-verification-harness-design.md`,
#1586). This is the **chain-level** analog: it audits each integration's
*standard* transaction builder — the code that produces the **prior transactions**
feeding a merged transaction — across 10 observable fingerprint axes, and groups the seven
integrations per axis (the way the issue grouped nSequence into A/B/C).

## Why the standard builder, not the merged transaction code

The library already coerces **intra-tx** uniformity for nSequence: the receiver
copies the sender's first-input sequence (`merged transaction/src/core/receive/common/mod.rs:286-317`)
and the sender rejects mixed sequences (`merged transaction/src/core/send/mod.rs:389-392`,
`InternalProposalError::MixedSequence`). That coercion **cannot reach the prior
transactions** that created each input. Those were built by each wallet's normal
spend path, and a chain analyst reads their fingerprints (the backward channel)
to re-partition the merged merged transaction back into per-owner inputs. So the leak lives
in each wallet's standard tx builder — that is what this matrix audits.

## Method & honesty caveats

- **Source of truth:** each cell was read from the integration's actual code
  (`gh api` raw files / `gh pr diff` / this local repo), then a second
  adversarial pass re-fetched the cited code per axis to confirm or refute the
  grouping. 9/10 axis groupings held; **axis 4 was refuted and corrected below**.
- **Most cells are code-PREDICTED; Example 3 is now chain-PROVEN.** Full txids
  for the three catalog examples (the open item) are:
  - Ex.1 (Ashigaru, low-R): `8dba6657…` — a **testnet** tx in the source write-up (resolves on testnet, 404 on mainnet), decoded there but not on our mainnet sample. Re-anchored to a mainnet example below (WP2, 2026-07-14).
  - Ex.2 (PDK demo, sighash): `3c5436f1…` — a **Mutinynet/signet** tx in the source write-up (404 on mainnet). Re-anchored to a mainnet example below (WP2).
  - Ex.3 (Cake→BBM merged transaction): `8fb80573d8871efee060a34dcb97fd12d5229444b7262b26358cd84912a04a75`
    · prior in_0 `9ecd77ab2115f12fd6d5ff46271f0a5e04ed03b267d6431f7b0991e0f0e23ef9`
    · prior in_1 `3fbe17132477ae6e38709b5e8e12ff5054fc66b4dd03568fea92a7a5bac18a84`
  - **Ex.3 decoded (mempool.space) — CONFIRMS the predictions:** merged transaction both
    inputs `seq=0x01`, both low-R (71B sig), in 19,358/440,337, out 29,358/429,919,
    payment = 10,000 (round), `locktime=0`, all `v0_p2wpkh`. Prior `9ecd77ab`
    carries the **Cake group-C `[0x01, MAX]` nSequence bug on-chain** (in seq
    `1` and `4294967295`; out 440,337 → merged transaction in_0), and `locktime=0` — Cake's
    no-anti-fee-sniping. → the code-predicted Cake cells (axis 1 `[1,MAX]`, axis 4
    `locktime=0`) are now **chain-proven**.
  - **Nuance from decoding:** prior `3fbe1713` (funding the receiver's UTXO) is
    `version=1` with a `v1_p2tr` input — i.e. **not** itself a BBM/BDK tx
    (BDK = v2/p2wpkh). Its all-`MAX` seq is *consistent with* the receiver, not
    proof BBM built it. The writeup's "consistent with BBM" attribution is loose.
  - **Ex.1/Ex.2 RE-ANCHORED to mainnet chain-proven examples (WP2, 2026-07-14).** The
    source Ex.1/Ex.2 txids are testnet/signet transactions that 404 on mainnet. Instead, the
    `x_low_r` and `x_sighash` extractors were run over a real unbiased mainnet sample
    (300 txs) and real example txids surfaced and decoded:
    - **low-R (axis 2):** `dce69633124d7a3240cc76de5fcc947881f6a140d6d2d0b009f70938136c6bb9`
      → `x_low_r = low_r` (71-byte DER sig). Measured base rate: low_r 20%, not_low_r
      14%, na 66% (2.32 bits/match for a low_r hit).
    - **sighash (axis 3):** `0361ae989850134b483cbf04b04978f331b0e6095dcf91de9737f4bde516367a`
      → `x_sighash = taproot_default` (64-byte schnorr, 4.23 bits/match). ECDSA `all`
      is the common case (34%, 1.57 bits).
    These bits and example txids are recorded in `decluster/library.py`. Low-R is a
    per-cluster *consistency* signal (a non-grinding wallet emits a 71-byte sig ~50% of
    the time), so it is low-severity — the measured base rate reflects that.
- **Core values now fetched from source:** axis 1 (`0xFFFFFFFD`) and axis 4
  (nLockTime) were confirmed in `bitcoin/bitcoin` master `src/wallet/spend.cpp` —
  the fee-sniping assert at L1041-1049 only permits `nSequence ∈ {0xFFFFFFFE,
  0xFFFFFFFD}`, and `DiscourageFeeSniping` L1022-1037 sets the locktime. These two
  Core cells are code-confirmed; everything else remains code-predicted.
- **PRs audited (all OPEN, receiver-side BIP77):** ldk-node #746
  (`Camillarhi/ldk-node:merged transaction-receiver`), Boltz #892 (`merged transaction-submarine-swap`),
  Liana #2011 (`merged transaction-receiver`). The merged transaction code is secondary context; the
  prior-tx fingerprint comes from each wallet's standard builder / underlying lib
  (Core, bdk_wallet, rust-bitcoin, cake-tech/bitcoin_base).
- **Liana fee rate (axis 10) is manual-input only** — Liana calls no
  `estimatesmartfee` / backend estimator; the spend `feerate_vb` is caller-supplied and
  the GUI fills it from a user-typed field. So the cell is `caller (manual)`, **not**
  bitcoind-derived.
- **Liana taproot changes the input-script-type reading** — under a Simple Inheritance
  taproot wallet, ordinary spends are a plain taproot **key-path** spend
  (indistinguishable from any single-sig P2TR); only a *recovery* spend takes the taptree
  branch. So the "distinctive `wsh()`/`tr()` witness" reading holds for non-taproot
  (miniscript `wsh`) or recovery spends — a taproot wallet's normal sends carry no
  distinctive witness. `library.py` bits are wallet-agnostic, so this is a prose caveat,
  not a weight change.
- **Liana nLockTime** — most integrations emit exact-tip, so Liana's anti-fee-sniping
  backdate can itself fingerprint a Liana payjoin, reinforcing the axis-4 tension
  (fee-sniping resistance vs cross-wallet uniformity).

## Version anchoring & temporal validity

Cells are pinned to the versions this research read (Cake Wallet `@dc1b369`,
2026-06-10). Because the matrix is a **backward-channel** de-anonymization surface,
a fingerprint is exploitable for every prior tx built by the version that emitted
it — a fix does not erase the signal from already-confirmed chain history, it only
bounds it. Cake's cells therefore carry a **fix/open marker**: `(vX · #PR)` = the
divergence was fixed as of Cake release `vX` (merged `#PR`), so txs built by
`< vX` still leak it; `(open · #PR)` = still divergent, fix in flight. Example 3
(`8fb80573…`, 2026-06) predates **every** Cake fix and remains chain-proven.

## Master matrix

`✓` = converges with the canonical (Core-baseline) value · `✗` = diverges (leaks) ·
`rand` = **sampled per-tx from the recent on-chain distribution → carries ~no
per-tx signal** (BTCPay/NBitcoin deliberately blends into the crowd) ·
severity is for the divergence as a backward-channel partition signal.

| # | Axis | Core (sender) | ldk-node (BDK) | Liana | Boltz | BBM (BDK) | Cake | BTCPay/NBitcoin | Sev |
|---|------|----|----|----|----|----|----|----|----|
| 1 | nSequence | `FD` ✓ | `FD` ✓ | `FD` ✓ | `FD` ✓ | `FD` ✓ | **mixed `01`/`FF` ✗** (open · bitcoin_base#12) | `FD` ✓ | **high** |
| 2 | Low-R grind | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **rand** | low |
| 3 | Taproot sighash | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | low |
| 4 | nLockTime | tip exact ✓ | tip exact ✓ | **tip −Δ~10% ✗** | **swap/0 ✗** | tip exact ✓ | **0 always ✗** (open · #3385) | **rand** | **high** |
| 5 | tx version | `2` ✓ | `2` ✓ | `2` ✓ | `2` ✓ | `2` ✓ | `2` ✓ | **rand** (`1`/`2`) | low |
| 6 | Input order | shuffle ✓ | shuffle ✓ | **selection-order ✗** | **BIP-69 ✗** | shuffle ✓ | shuffle ✓ (v6.3.0 · #3379) | shuffle ✓ | med |
| 7 | Output order | shuffle ✓ | shuffle ✓ | **change-last ✗** | sweep (n/a) | shuffle ✓ | shuffle ✓ (v6.3.0/v6.4.0 · #3420/#3432) | shuffle ✓ | **high** |
| 8 | Change spk type | match ✓ | match ✓ | match ✓ | sweep (n/a) | match ✓ | **fixed p2wpkh ✗** | match ✓ | med |
| 9 | Coin select/UIH | Core BnB | BDK BnB | BnB+desc-fallback | sweep | **greedy ✗** | **greedy ✗** (open · #3408) | stochastic knapsack | med |
| 10 | Fee rate | CLI/Core est | fee_estimator | caller (manual) | caller/Core | rounded ext | **Electrum buckets** | manual + rec | low |

BTCPay/NBitcoin is the outlier: it is the only integration that **actively
randomizes** version, nLockTime, and low-R (sampled from a 5-block window of the
on-chain distribution) instead of emitting a fixed per-wallet value — so on those
axes it carries no partition signal. Its residual fixed tells are structural
(always-RBF `0xFFFFFFFD`, default-P2WPKH, change-matches-wallet, the NBitcoin
knapsack's `0.01 BTC` min-change) and none separate it from the Group-A cluster.
See the anti-fingerprinting subsection below.

## Per-axis detail (high & medium severity)

### Axis 1 — nSequence · HIGH · *grouping holds*
- **Group A (canonical):** `0xFFFFFFFD` uniform — the sender wallet/Core, ldk-node/BDK,
  Liana, Boltz, BBM (5/6).
- **Group C (Cake, bug):** `input[0]=0x00000001`, all others `0xFFFFFFFF`.
  Two compounding bugs in `cake-tech/bitcoin_base`:
  1. `transaction_builder.dart:398-400` mutates **only `inputs[0]`** when
     `enableRBF`, leaving the rest at the `0xFFFFFFFF` default — an intra-tx mix
     that *also* reveals which input is index 0.
  2. `op_code/constant.dart:153` `REPLACE_BY_FEE_SEQUENCE` = little-endian
     `0x00000001` — the **wrong** RBF sentinel (BIP-125/Core use `0xFFFFFFFD`).
- **Canonical:** `0xFFFFFFFD` (`ENABLE_RBF_NO_LOCKTIME`) on every input. Cake
  matches *neither* the literal byte *nor* uniformity.

### Axis 4 — nLockTime · HIGH · *grouping corrected (source-verified)*
An earlier pass grouped `the sender wallet` with Core's generic anti-fee-sniping
(`tip −Δ~10%`, alongside Liana). That is **wrong**: the sender wallet explicitly opts
out of the delta and is exact-tip, converging with the BDK cluster. Verified in
both sources:

- **the sender wallet** sets an explicit `locktime = get_block_count()` (current tip)
  and passes it to `walletcreatefundedpsbt` (`the sender wallet .../wallet.rs:54-59`,
  comment: *"opinionated default for external wallet integrations to follow"*).
  In Core, `FundTransaction` copies that into `coin_control.m_locktime`
  (`src/wallet/spend.cpp:1512`), and a set `m_locktime` sets
  `use_anti_fee_sniping = false` (`spend.cpp:1324-1327`), so `DiscourageFeeSniping`
  (the ~10% `randrange` backdate, `spend.cpp:1029-1030`) **never runs** → exact tip.
- **ldk-node / BBM** wrap `bdk_wallet`, whose no-locktime arm sets
  `fee_sniping_height = current_height` with **no random subtraction** → exact tip.
- **Consequence:** the sender wallet, ldk-node, BBM all converge on **exact tip** — the
  value the sender wallet proposes as the canonical default. The divergences are:
  - `tip −Δ~10%`: **Liana** — reimplements Core's anti-fee-sniping
    (`liana spend.rs:485-517`); ~10% of txs sit 1–100 blocks below tip (and `0` if
    the tip is >8h stale). Its below-tip tail is distinguishable over several txs.
  - `swap-specific`: **Boltz** — refund = timeout height, claim = 0 (boltz-core).
  - `0 always`: **Cake** — `bitcoin_base transaction.dart:33` +
    `constant.dart:361` `DEFAULT_TX_LOCKTIME=0`, no anti-fee-sniping at all.
- **Canonical (proposed):** exact current block height (the sender wallet's default,
  already shared by the BDK cluster). A `locktime==0` prior tx (Cake) excludes
  every anti-fee-sniping wallet; Liana's ~10% below-tip tail and Boltz's swap
  height are the other non-tip signals. Note the genuine tension: Liana's backdate
  is itself a *legitimate* fee-sniping mitigation, so this axis trades fee-sniping
  resistance against cross-wallet uniformity.

### Axis 6 — Input ordering · MEDIUM · *holds*
Three-way split: **shuffle** (Core/BDK → the sender wallet, ldk-node, BBM,
BTCPay/NBitcoin, and Cake **as of v6.3.0** · #3379 — `@dc1b369` sorted BIP-69, so
pre-v6.3.0 Cake txs still carry it) · **BIP-69 lexicographic** (Boltz) ·
**selection/insertion order** (Liana). A non-BIP-69 wallet
sorts by chance with probability `1/n!` (½ at n=2, ⅙ at n=3), so a small-`n` sorted set is
coincidental, not a brand. That `1/n!` sets the **gate**, not the emitted weight: `x_input_order`
labels a sorted set `bip69` only at **n≥4** (accidental sort <5%); at n≤3 it returns `small_n`
and the combiner **abstains** (`combiner.py`), so a coincidentally-sorted 2-input tx cannot forge
a same-owner link. At n≥4 the emitted weight is the flat **software-rarity link (~3 bits,
`−log₂(share)`)** — bounded, *not* a per-tx `log₂(n!)` (which would over-link different owners of
the same wallet). A randomized order excludes BIP-69 at any n.

### Axis 7 — Output ordering / change position · HIGH · *holds*
Directly defeats merged transaction's change-ambiguity goal.
- **shuffle** (Core/BDK, BTCPay/NBitcoin): the sender wallet, ldk-node, BBM; **and
  Cake as of v6.3.0/v6.4.0** — `outputOrdering: BitcoinOrdering.shuffle`, #3420
  (software + RBF) then #3432 (hardware-wallet + Bitcoin-Cash paths).
- **change always LAST** (Liana): `spend.rs:750-752`, explicit `TODO: shuffle
  once we have Taproot`.
- ~~**insertion order, change appended** (Cake): `BitcoinOrdering.none` at
  `electrum_wallet.dart:1360`~~ — the pinned `@dc1b369` value; **exploitable for
  pre-v6.3.0 Cake txs** (Ex.3 is one), fixed forward by #3420/#3432.
- **single-output sweep** (Boltz): no change axis, but the shape is its own brand.
- A wallet whose prior txs always put change last makes change-identification
  trivial, re-partitioning the merged merged transaction.

### Axis 8 — Change spk type · MEDIUM · *holds*
Most wallets emit change matching their input/descriptor type (indistinguishable
for single-type segwit wallets). **Cake hard-fixes change to p2wpkh** for
`WalletType.bitcoin` regardless of input type
(`electrum_wallet_addresses.dart:601-606`, explicit `For now fixed to p2wpkh, the
cheapest type` TODO). A non-p2wpkh Cake wallet emits change whose type mismatches
its inputs — a deterministic tell no other integration produces.

### Axis 9 — Coin selection / UIH · MEDIUM · *holds*
Six regimes: Core `SelectCoins` (BnB + Knapsack + CoinGrinder + SRD, least-waste) ·
BDK `BranchAndBound<SingleRandomDraw>` (ldk-node, BBM) · Liana `bdk_coin_select`
BnB + descending-value-per-wu fallback (dust=500, long-term feerate 5) · Boltz
no-selection sweep · BTCPay/NBitcoin `DefaultCoinSelector` (Core-style **stochastic
knapsack**, `0.01 BTC` min-change) · **Cake greedy accumulation with residual
change, no BnB** (open · #3408 would move it to `BranchAndBound<SingleRandomDraw>`).
Greedy/exotic fallbacks leave UIH1/UIH2 peel-chain residuals distinguishable from
BnB. Probabilistic — needs repeated observations.

Beyond the leak-*value*, this axis carries a second, stronger technique —
**coin-selection prediction** — treated as its own de-anon lens below: a
*deterministic* selector lets an adversary replay the suspected cluster's selection
and refute a mis-join (a strictly-better unselected coin argues the coin is
mis-assigned); a *randomized* selector turns the selected set into a random variable
and defeats the test.

### BTCPay/NBitcoin · anti-fingerprinting randomization
Unlike every other integration — each of which emits a fixed per-wallet value that
convergence could eliminate — BTCPay (via NBXplorer) **samples** several axes to
imitate the on-chain crowd. NBXplorer keeps a 5-block sliding window of the joint
fingerprint distribution over every tx, and at build time conditions on what it
knows (script type, non-mixed inputs/sequence, RBF) and samples **nVersion (1/2),
nLockTime/fee-sniping, and low-R enforcement** to fill any field the caller left
unset. So on those axes BTCPay is `rand` — a random draw from the real
distribution, carrying ~no per-tx partition signal, the opposite of Cake's
deterministic tells. Active on ordinary sends; disabled only on the RBF fee-bump
path (which must reuse the original tx). Residual **fixed** tells are structural
and shared with the Group-A cluster: always-RBF `0xFFFFFFFD`, default-P2WPKH
(one script type per wallet → no multi-type vin), change matching the wallet type,
and the NBitcoin knapsack's `0.01 BTC` min-change — none of which single it out.
It is the reference for *how a wallet should behave* on these axes.

### Coin-selection prediction (de-anon lens)
The heuristic works only if the selector is **reproducible**: given {UTXO set,
feerate, outputs}, is the selection deterministic (predictable) or randomized
(resistant)?
- **Predictable (deterministic):** **Cake** (greedy address-then-age accumulation,
  no RNG; open · #3408) · **Liana** (`bdk_coin_select` BnB + deterministic
  descending-value fallback) · **Boltz receiver** (smallest-UTXO-that-fits) ·
  **Electrum** (`CoinChooserPrivacy`, PRNG **seeded from the UTXO set**, not the
  outputs — enumerating the coins yields the whole seed). These let the adversary
  replay the selection over a suspected cluster and test whether a "better" coin was
  wrongly joined.
- **Resistant (randomized):** **Core / payjoin-cli** (BnB + Knapsack/SRD/CoinGrinder,
  least-waste, with shuffles + a randomized change target — deterministic only when
  a changeless BnB solution dominates) · **BTCPay/NBitcoin** (stochastic knapsack) ·
  **BDK** SingleRandomDraw fallback (ldk-node/BBM — predictable only in the
  changeless-BnB regime) · **Boltz** ordinary send (delegates to Core). A "better"
  unselected coin here is consistent with normal behaviour, so only the selector's
  *parameters* (min-change, cost-of-change, long-term feerate) fingerprint the
  algorithm, not the selection.

## New bugs / tells surfaced

1. **Cake group-C is two bugs, not one** — wrong RBF sentinel (`0x00000001`) *and*
   only-`inputs[0]` mutation. (axis 1)
2. **Cake `locktime=0` always** — no anti-fee-sniping; a standalone deterministic
   tell. (axis 4)
3. **nLockTime: exact-tip cluster** — the sender wallet explicitly disables Core's ~10%
   anti-fee-sniping delta (`m_locktime` set → `use_anti_fee_sniping = false`), so
   it converges with ldk-node and BBM on exact tip. The divergences are Liana's
   ~10% below-tip backdate, Boltz's swap height, and Cake's `0`. (axis 4)
4. **Cake fixed-p2wpkh change** — type mismatch for non-p2wpkh wallets. (axis 8)
5. **Liana `change-last` + `TODO: shuffle`** — change position is deterministic
   until Taproot support lands. (axis 7)

`the sender wallet` itself is the clean baseline: it inherits Core defaults and sets the
canonical exact-tip locktime in Rust (`the sender wallet .../wallet.rs:54-59`),
delegating selection/signing to Core. On axis 4 it does **not** leak against the
BDK wallets — its explicit `m_locktime` disables Core's ~10% delta, so it converges
with ldk-node/BBM on exact tip.

## Conformance-policy implication

The non-leaking axes today (2, 3, 5) are uniform only by **inheritance** from
shared libs — nothing pins them, so a future integration can regress. The library
should generalize its existing intra-tx nSequence coercion into a **sender-side
conformance pass** over both the original PSBT and the receiver's contributed
inputs, checking the deterministic axes (1, 3, 4, 5, 6, 7, 8) on every merged transaction and
surfacing divergent wallets before broadcast:

- **nSequence** = `0xFFFFFFFD` uniform on every input — reject mixed / wrong-sentinel
  (catches Cake group-C).
- **nLockTime** = exact current-height (the sender wallet's proposed default, already
  shared by the BDK cluster) — flag `0` (Cake) and protocol values (Boltz swap
  timeout) as divergences. Liana's ~10% anti-fee-sniping backdate is a *legitimate*
  fee-sniping mitigation, so this axis carries a real tension (fee-sniping
  resistance vs cross-wallet uniformity); converging needs one chosen shape.
- **tx.version** = 2; **low-R grind**; **taproot SIGHASH_DEFAULT (64B)** — pin to
  prevent regression.
- **Randomized input AND output order**; **forbid** BIP-69 sorting (Boltz),
  insertion/selection order (Liana inputs, Cake outputs), and deterministic
  change-last (Liana).
- **Change spk type matches input type** — forbid hard-fixed types (Cake).
- **Prefer BnB** coin selection (recommendation + UIH self-check, not a hard
  reject — probabilistic).
- **Fee rate**: mandate whole-sat/vB rounding and require integrations to document
  their estimation source; no single canonical rate is enforceable.

The end-state the issue asks for — one group per axis — requires both fixing the
wallet-side bugs (Cake group-C, Cake locktime/change, Liana change-last) **and**
the library converging the axes where even the "good" wallets disagree (e.g.
nLockTime: the exact-tip cluster {the sender wallet, ldk-node, BBM} converges, but
Liana's legitimate anti-fee-sniping backdate still needs one chosen shape).

## Reproduce / extend

Each cell was read with:

```sh
gh api -H "Accept: application/vnd.github.raw" \
  "repos/<owner>/<repo>/contents/<path>?ref=<ref>"
gh pr view <n> --repo <owner>/<repo> --json headRefName,headRepositoryOwner
gh pr diff <n> --repo <owner>/<repo>
```

To upgrade cells from *predicted* to *chain-proven*: supply a full 64-hex txid for
a wallet-attributed tx and decode via `curl -s https://mempool.space/api/tx/<txid>`.
