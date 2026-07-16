# Tx-construction fingerprint matrix (issue )

Companion to `research-docs/fingerprints/merged transaction.md` and to the network-level
harness seed (`docs/superpowers/specs/2026-05-27-fingerprint-verification-harness-design.md`,
#1586). This is the **chain-level** analog: it audits each integration's
*standard* transaction builder — the code that produces the **prior transactions**
feeding a merged transaction — across 10 observable fingerprint axes, and groups the six
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
  - Ex.1 (Ashigaru, low-R): `8dba6657…` — **UNVERIFIABLE: 404 on mainnet** (WP2, 2026-07-14). This txid was never actually decoded; it was a placeholder. See replacement below.
  - Ex.2 (PDK demo, sighash): `3c5436f1…` — **UNVERIFIABLE: 404 on mainnet** (WP2). Placeholder, not a real decoded tx.
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
  - **Ex.1/Ex.2 REPLACED with real chain-proven examples (WP2, 2026-07-14).** The
    catalog's original Ex.1/Ex.2 txids 404 on mainnet (placeholders). Instead, the
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

## Master matrix

`✓` = converges with the canonical (Core-baseline) value · `✗` = diverges (leaks) ·
severity is for the divergence as a backward-channel partition signal.

| # | Axis | the sender wallet (Core) | ldk-node (BDK) | Liana | Boltz | BBM (BDK) | Cake | Sev |
|---|------|----|----|----|----|----|----|----|
| 1 | nSequence | `FD` ✓ | `FD` ✓ | `FD` ✓ | `FD` ✓ | `FD` ✓ | **mixed `01`/`FF` ✗** | **high** |
| 2 | Low-R grind | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | low |
| 3 | Taproot sighash | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | low |
| 4 | nLockTime | tip exact ✓ | tip exact ✓ | **tip −Δ~10% ✗** | **swap/0 ✗** | tip exact ✓ | **0 always ✗** | **high** |
| 5 | tx version | `2` ✓ | `2` ✓ | `2` ✓ | `2` ✓ | `2` ✓ | `2` ✓ | low |
| 6 | Input order | shuffle ✓ | shuffle ✓ | **selection-order ✗** | **BIP-69 ✗** | shuffle ✓ | shuffle ✓ | med |
| 7 | Output order | shuffle ✓ | shuffle ✓ | **change-last ✗** | sweep (n/a) | shuffle ✓ | **insertion ✗** | **high** |
| 8 | Change spk type | match ✓ | match ✓ | match ✓ | sweep (n/a) | match ✓ | **fixed p2wpkh ✗** | med |
| 9 | Coin select/UIH | Core BnB | BDK BnB | BnB+desc-fallback | sweep | **greedy ✗** | **greedy ✗** | med |
| 10 | Fee rate | CLI/Core est | fee_estimator | caller/bitcoind | caller/Core | rounded ext | **Electrum buckets** | low |

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
Three-way split: **shuffle** (Core/BDK → the sender wallet, ldk-node, BBM, Cake) ·
**BIP-69 lexicographic** (Boltz) · **selection/insertion order** (Liana). A non-BIP-69 wallet
sorts by chance with probability `1/n!` (½ at n=2, ⅙ at n=3), so a small-`n` sorted set is
coincidental, not a brand. That `1/n!` sets the **gate**, not the emitted weight: `x_input_order`
labels a sorted set `bip69` only at **n≥4** (accidental sort <5%); at n≤3 it returns `small_n`
and the combiner **abstains** (`combiner.py`), so a coincidentally-sorted 2-input tx cannot forge
a same-owner link. At n≥4 the emitted weight is the flat **software-rarity link (~3 bits,
`−log₂(share)`)** — bounded, *not* a per-tx `log₂(n!)` (which would over-link different owners of
the same wallet). A randomized order excludes BIP-69 at any n.

### Axis 7 — Output ordering / change position · HIGH · *holds*
Directly defeats merged transaction's change-ambiguity goal.
- **shuffle** (Core/BDK): the sender wallet, ldk-node, BBM.
- **change always LAST** (Liana): `spend.rs:750-752`, explicit `TODO: shuffle
  once we have Taproot`.
- **insertion order, change appended** (Cake): `BitcoinOrdering.none` at
  `electrum_wallet.dart:1360`.
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
Five regimes: Core BnB · BDK `BranchAndBound<SingleRandomDraw>` (ldk-node, BBM) ·
Liana BnB + descending-value-per-wu fallback (dust=500, long-term feerate 5) ·
Boltz no-selection sweep · **Cake greedy accumulation with residual change, no
BnB**. Greedy/exotic fallbacks leave UIH1/UIH2 peel-chain residuals distinguishable
from BnB. Probabilistic — needs repeated observations.

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
