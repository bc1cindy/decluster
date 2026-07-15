# Fingerprint-Aware Probabilistic De-anonymization of Bitcoin Transaction Graphs

*Every empirical number below is reproducible from this repository:
`decluster/library.py` (measured bits), `results/RESULTS-bigquery.txt` (calibration on a
~105k uniform whole-chain sample), `results/RESULTS-fingerprint-validation.md` (attribution AUC 0.974 on 106k
real txs), `results/RESULTS-graph-deanon.md` (structural de-anon across four eras), and
`results/RESULTS-wp4.md` (the ground-truth case study). Scope: a fingerprint-aware
clustering **method**, validated at mainnet scale without an archival node; the one thing
left is a whole-chain **entity-reduction rate** (§10).*

## Abstract

On-chain Bitcoin privacy is an emergent property of the **transaction graph**, not of
any single transaction. The **primary** de-anonymization signal is not a wallet-software
fingerprint but the **amount structure** — the amounts in use are a fingerprint of their
own kind. A transaction that merges unrelated parties can be
re-partitioned into per-owner subtransactions by subtracting a contributed input from an
output and testing whether the implied payment "makes sense" (a round number, under the
unnecessary-input heuristic). Wallet fingerprints are a **corroborating** layer on top of
this. We present a probabilistic clustering framework that fuses the two — an
**amount-based subtransaction re-partition** and a **fingerprint** weight-of-evidence in
**bits** (Fellegi–Sunter) — into a single most-likely clustering over the labeled
transaction multigraph that avoids the cluster-collapse failure of a single union-find. 
We build a curated **library of fingerprints with evidence** (22 measured axes across the
chain-observable transaction-construction surface, calibrated on unbiased real-chain
samples — 17 structural axes on a whole-chain sample, 5 witness axes
on a mempool sample — anchored to chain-proven examples) and, on a real mainnet
merged transaction whose correct owner-partition is known, show the intended false merge
is **refused** by the amount structure alone and **again** by the fingerprints — the two
signals fuse and agree. We argue that a merge's ~1.6 bits of structural ambiguity cannot
survive against the 100+ bits carried by an established cluster, and that fingerprint
uniformity is necessary but far from sufficient for collaborative-transaction privacy.
This measurement is instrumental: the same per-axis bits, read as a penalty instead of a
same-owner link, define a construction-side cost function — so quantifying the attack is
the prerequisite for the defense, shaping transactions that no longer carry these tells.

## 1. Introduction & thesis

The common-input-ownership heuristic clusters all inputs of a transaction as one
entity. Collaborative transactions that deliberately merge unrelated parties violate it,
hoping a chain analyst will merge the parties into one entity. We show this hope is
quantitatively misplaced. A two-in/two-out merge adds at most **log₂3 ≈ 1.6 bits** of
ambiguity, while an established cluster in a social-transaction graph carries **>100 bits**
of identifying structure. An analyst needs only ~2 of those bits to override the merge.
Enlarging the merge does not help: more inputs inflate the *count* of possible
owner-partitions — combinatorially, on the order of B(#ins)·B(#outs) (Bell numbers) — but
not the *entropy* of the distribution over them, which is what anonymity actually measures.
Fingerprints and amounts peak that distribution on the partition that splits the inputs
along their existing clusters, and those clusters can in turn be intersected to a common
origin (Goldfeder et al.). More inputs buy possibilities, not privacy.

Our contribution is the *combination engine* plus the *evidence library* that make this
concrete: heuristics and fingerprints are fused as signed bits on a weighted graph, and
a correlation-clustering pass (Pivot/KwikCluster) produces the most-likely partition —
strictly more expressive than the single union-find that clusters can only *grow*, never
*refuse*.

This offensive result is a means, not an end: the de-anonymization engine is the
measurement half of a construction-side cost function for collaborative transactions
(§10). You cannot shape a transaction to avoid a tell you have not first measured.

## 2. Straw-man: why merging unrelated parties does not deliver privacy

A merged transaction induces a false common-input link between a receiver and a sender.
Three facts defeat it, in order of importance:

0. **The amount structure (primary).** The receiver contributes an input that is added to
   the payment output. An analyst subtracts a candidate contributed input from an output
   and reads off the implied payment; if that payment is a plausible (round) number under
   the unnecessary-input heuristic, the partition is likely. For a 2-in/2-out merge the
   per-owner balance is automatic, so the discriminator is the payment's round-ness, and
   the number of plausible partitions is small — often one clean answer. This
   re-partitions the merge **before any fingerprint** (§6). *Round-ness is a heuristic, not
   a proof:* it needs a value model (a round number in fiat at the time, not just in sats),
   and a market-priced payment may carry no round-number signal at all — so the amount
   channel is strong where a plausible round partition exists (as in §6) and silent where
   it does not.
1. **The backward channel (fingerprints).** A collaborative construction can coerce
   intra-transaction fingerprint uniformity (e.g. the receiver copies the sender's
   `nSequence`), but it cannot reach the *prior* transactions that created each input.
   Those carry wallet-specific fingerprints an analyst reads to corroborate the amount
   partition.
2. **The bit asymmetry.** Even with perfectly uniform fingerprints and ambiguous amounts,
   the merge's ~1.6 bits are dwarfed by the 100+ bits of prior clustering evidence; the
   partition is decidable *without needing the merged transaction at all*.

## 3. The fingerprint library (evidence)

We catalog the chain-observable transaction-construction axes (nSequence, nLockTime,
input/output ordering, change script type, tx version, coin-selection/UIH, low-R grinding,
SIGHASH type, **fee-rate**, **input script type**), grouping six reference wallet
integrations per axis (`catalog/tx-construction-matrix.md`). Each axis carries an
**extractor**, **measured bits**, and a **chain-proven example** (`decluster/library.py`);
the library carries **22 measured axes** in total (the base set plus the granular additions
in §8 — input-type presence, nested segwit, pubkey compression, multisig, OP_RETURN, output
encoding, and the change relations): the 17 structural axes calibrated on the whole-chain
BigQuery sample, the 5 witness axes on a mempool sample (§5).

Bits are measured on an **unbiased** mainnet sample (§5). Representative
values (bits per matching value; higher = rarer = stronger link):

| Axis | value | bits/match |
|---|---|---|
| nSequence (Cake bug) | `cake_group_c` | 13.88 |
| nSequence | `seq_0x01_other` | 8.89 |
| nLockTime | `height_tip` | 3.01 |
| change spk | `uniform_v1_p2tr` | 5.92 |
| input order | `bip69` | 3.00 |
| input script type | `mixed` | 6.00 |
| change type | `mismatch_input` | 5.72 |
| fee-rate | `round` | 2.53 |
| low-R (mempool) | `low_r` | 2.30 |
| SIGHASH (mempool) | `taproot_default` | 3.96 |

(Rare values are now estimable: the whole-chain sample surfaces high-bit tells like the
Cake-style `seq_0x01` nSequence at 8.9 bits and mixed input types at 6.0 bits.)

**Honesty note.** Two catalog example transactions (Ex.1 low-R, Ex.2 SIGHASH) were
originally listed with txids that do not resolve on mainnet — placeholders, never
decoded. We replaced them with real example transactions surfaced and decoded from the
unbiased sample (`dce69633…` for low-R, `0361ae98…` for taproot SIGHASH). Only the Cake
group-C nSequence bug (`8fb80573…`) was independently chain-proven earlier.

## 4. The engine

Evidence is a signed weight-of-evidence in bits. For a value of frequency `p`, a match
contributes `-log₂p` toward "same wallet"; a mismatch contributes a negative penalty
(`EvidenceModel`, Fellegi–Sunter). Heuristic partitions and the fingerprint graph are
fused additively onto one weighted graph (`combine_evidence`), then correlation-
clustered.

Three properties matter for the thesis:

- **Beyond union-find.** The graph can carry *negative* edges, so the clustering can
  **refuse** a merge — impossible for a monotone union-find.
- **Bit-accounting / priors.** A large established cluster contracts as a unit carrying
  its full weight; a merge-strength contrary signal (−3 bits) cannot override a 100-bit
  prior. We verify this as a property test (`high_weight_prior_survives_contrary_fingerprint`)
  and replace the old hard "skip large groups" with O(n) star-contraction so large
  wallets are not silently dropped at scale.
- **Real bits.** `EvidenceModel::from_bits_table` (and the Python `Combiner.from_library`)
  let the engine score from the measured library bits rather than a small in-sample fit.

## 5. Empirical calibration (unbiased real data)

Naive sampling of recent block tops is fee-biased. We first de-biased via mempool.space
(uniform across height + within-block fee-spread, `sample_chain_uniform`), then calibrated
definitively on a **uniform random sample of the whole chain via Google BigQuery's public
Bitcoin dataset** (`results/RESULTS-bigquery.txt`, `bigquery/sample.sql` — no archival node; the
query exports transactions in the pipeline's JSON schema so the same extractors run at
scale). **The 17 structural axes are measured on a ~105,000-tx uniform sample across the whole chain**; the
witness axes (low-R, SIGHASH, pubkey compression, multisig, nested segwit) are measured on
a ~3,500-tx mempool sample, since BigQuery's schema carries no witness data.

Two honest corrections the whole-chain sample forced:
- **nLockTime `zero` is ~74% chain-wide, not ~95%.** The ~95% figure we had chased was a
  misconception; the whole-chain BigQuery sample puts zero at ~74% (the smaller recent
  mempool sample ran higher, ~85%).
- **UIH is real, not inert.** The unnecessary-input heuristic fires on ~8.3% of txs
  (3.6 bits) once real input values are available — the earlier "inert" result was an
  artifact of the mempool sample lacking top-level input values.
- Distributions are **non-stationary**: e.g. round fee-rates are ~17% chain-wide but ~9%
  in recent blocks — old wallets used round fees more. Chain-wide is the right prior.

This is a **large representative sample (~105,000 txs)**, not literally every tx; exhaustive
per-tx measurement would still want the whole chain, but for calibrating fingerprint
frequencies this is publication-grade (rare values become estimable).

**Validation on real data (`results/RESULTS-fingerprint-validation.md`).** Do the calibrated
bits actually attribute wallets? On **106,644 real witness-bearing mainnet txs**, with ground
truth = address reuse (two txs spending the same input address are the same wallet),
the Fellegi–Sunter score ranks same-wallet tx pairs (mean **+15.7 bits**) far above random
pairs (mean **−12.2 bits**): **AUC 0.974**, with a shuffle control at 0.51. So the measured
fingerprint model separates same-wallet from random transactions on real data — a systematic,
quantified result beyond the prior anecdotal spot-checking. (Ground truth is address reuse, so
the `input_types` axis matches partly by construction; the signal is spread across all axes and
the control is clean — see the honest caveats in the results file.)

## 6. Demonstration: a real merged transaction re-partitioned

Our anchor is a **ground-truth merged transaction**: `931d6627` is a confirmed mainnet
transaction that merges two wallets — a **Cake Wallet receiver** and a **distinct sender
wallet** — into one common-input group, so the correct owner-partition is known, not
inferred. On its ancestry graph (7 coins; inputs 2000 sats sender, 5750 sats Cake
receiver; outputs 791, 6750; fee 209):

- **Amount alone (primary, `results/RESULTS-gap1.md`)** re-partitions it: `6750 − 5750 = 1000`
  is a round payment, so the receiver is the Cake input and the sender is separate — at 1
  bit ambiguity, resolved by round-ness, **before any fingerprint**.
- **Union-find (BlockSci-style)** mis-merges {Cake `0a568e3a`, sender `91106666`} — the
  exact false link the merge intends.
- **Fused clustering (`cluster_fused`, `results/RESULTS-wp4.md`)** refuses that merge: the
  fingerprint evidence scores `−3.1 bits` (`max_ffffffff` vs `seq_0x01`), past the
  prototype's `−2.0` refuse threshold → the merge is re-partitioned, the sender isolated;
  and the fingerprint layer **adds** the links the co-spend missed (Cake lineage
  `+10.2 bits`, sender funding chain `+5.4 bits` each). The amount channel refuses the same
  merge independently (the round `1000`-sat re-partition above), so the two signals agree.
  Resulting clusters: `{sender}`, `{sender funding chain}`, `{Cake, lineage}` — the correct
  partition; union-find gave the wrong one.

This is an *existence* demonstration on one merged transaction, not a rate across the chain
— but it instantiates the thesis on real data: two independent signals fuse and agree to
re-partition the merge.

**Graph-level anonymity metric (`results/RESULTS-entropy.md`).** We quantify the effect with the
entropy of the clustering (`H = −Σ (n_i/N)·log2(n_i/N)` bits; effective anonymity set
`2^H`; largest-cluster fraction as a supercluster signal). On the real
**depth-6 ancestry graph of `931d6627` (19 coins)**:

| clustering | effective anon set | largest cluster |
|---|---|---|
| union-find (BlockSci) | 13.8 | 16% |
| fingerprint-aware | **3.4** | 53% |

The naive common-input view over-reports the anonymity set by **~4×**; the amount +
fingerprint evidence collapses 15 clusters to 5 and forms a supercluster (53%). This is
the thesis quantified at the graph level — still a modest real graph (19 coins), not a
chain-scale measurement (which needs the whole connected chain, §10).

**Community-structure de-anonymization (`results/RESULTS-graph-deanon.md`).** Beyond pairwise
evidence, we test the Narayanan–Shmatikov premise directly: does the *structure* of the
transaction graph predict same-owner membership, independent of the co-spend heuristic? On
a **connected real slice** — blocks 400000–400004, 8 927 txs, 27 962 addresses, 2 463
entities (`bigquery/graph.sql`, no archival node) — with ground truth = transitive co-spend
clusters and held-out positives = same-owner pairs that are *not* directly co-spent
(267 578 pairs), a common-neighbors link-prediction score predicts same-owner membership.
Removing the co-spend edges that *define* the ground truth — scoring by payment structure
alone (common neighbors) — still re-identifies same-owner addresses at **AUC 0.95** on the
2016 slice; the shuffle control lands at 0.50. Graph structure de-anonymizes *beyond* the
common-input heuristic, on real data. Across **four eras**, swept over graph reach *k*
(k-hop, hub intermediates excluded; `decluster/graph_deanon.py --depth`):

| era (slice) | held-out pairs | share% | k=1 | k=2 | k=3 | k=4 |
|---|---:|---:|---:|---:|---:|---:|
| 2012 (200 000) | 9 635 | 95% | 0.97 | 0.99 | 0.98 | 0.98 |
| 2013 (250 000) | 25 944 | **7%** | **0.53** | 0.77 | 0.93 | 0.98 |
| 2016 (400 000) | 267 578 | 91% | 0.95 | 0.97 | 1.00 | 0.99 |
| 2023 (800 000) | 111 | 65% | 0.82 | 1.00 | 1.00 | 1.00 |

At k=1 the effect is *not* a clean era curve: the 2013 slice falls to chance (0.53) on
25 944 pairs. The mechanism is exact — 1-hop AUC tracks **share%**, the fraction of
same-owner pairs sharing a direct counterparty (95→0.97 … 7→0.53); 2013 is the
service-churn (SatoshiDice) era, where an owner's addresses each touch a *different* service
address. But the structure is only deeper: sweeping reach recovers 2013 (0.53→0.98) and
**by k=4 all four eras sit at 0.98–1.00**. So structural de-anonymization holds across every
era; the graph *depth* needed scales with counterparty churn. (Deeper reach avoids the
small-world collapse only because hub counterparties are excluded — so high-k AUC approaches
non-hub component membership, a coarser tell than fine link prediction; and 2023 rests on
111 pairs.) The stronger claim — structure links entities co-spend leaves separate — still
needs independent entity labels (§9).

## 7. Related work

- **Narayanan & Shmatikov**, robust de-anonymization of large sparse datasets / social
  graphs: structure alone re-identifies nodes. §6 tests this premise on a real connected
  Bitcoin slice — payment-graph structure predicts same-owner at AUC 0.95, beyond the
  co-spend heuristic (`results/RESULTS-graph-deanon.md`). We measure the *premise* (structure is
  entity-separable); the full N-S seed-and-extend attack at chain scale, and richer
  features (community detection, embeddings), remain future work needing adjacency infra
  and independent labels.
- **Wang et al.**, *Exploring Unconfirmed Transactions for Effective Bitcoin Address
  Clustering*: the closest model — a clustering-effectiveness paper reporting **entity
  reduction** on the whole chain (co-spend +2.3%, novel heuristics +9.8%). We follow the
  same anonymity-collapse framing but at **case-study scale** (the entropy metric on the
  ground-truth merged transaction's graph, §6); a whole-chain entity-reduction measurement
  is a separate follow-on that needs the whole connected chain, not an archival node (§10).
- **Dingledine & Mathewson**, *Anonymity Loves Company*: uniformity is a network-effect
  property — a wallet that de-biases one axis but stands out on another gains nothing.
  This grounds our recommendation to randomize *between legitimate behaviors* (same
  distribution), not merely to fix single fingerprints.
- **Syverson**, *Why I'm Not an Entropist*: caution on the entropy framing; we report
  bits as weight-of-evidence for pairwise linkage, not as a single anonymity scalar.

## 8. Coverage of the chain-observable fingerprint surface

The chain-observable fingerprint surface enumerates **~35 granular fingerprints**. We do **not** cover
all of them; "coverage" here is an honest per-item claim (**✅** = extractor + measured
bits; **◐** = captured coarsely, not as the granular tell; **❌** = not built).

**Status against the fingerprint checklist:**

| Fingerprint | Status |
|---|---|
| Anti-Fee-Sniping (nLockTime) | ✅ |
| Default Opt-in RBF / Opt-in RBFing (nSequence) | ✅ |
| Tx nVersion 1 / 2 | ✅ |
| BIP-69 ordering (inputs) | ✅ |
| Low-R grinding | ✅ |
| Manual feerate / Feerate recommendations | ✅ |
| multi-type vin | ✅ |
| SIGHASH / taproot | ✅ |
| Spending from P2PK / P2PKH / P2SH / P2WPKH / P2WSH / P2TR | ✅ granular per-type + combos (`x_input_types_present`) |
| Spending from P2SH-P2WPKH (nested) | ✅ `nested_segwit` (3.15 bits) |
| Spending from P2SH-multisig / P2WSH-multisig | ✅ `x_multisig` (p2wsh witnessScript + legacy p2sh scriptSig OP_CHECKMULTISIG, 4.02 bits) |
| Compressed / Uncompressed ECDSA pubkeys | ✅ `pubkey_compression` (p2wpkh; uncompressed unseen in sample) |
| OP_RETURN outputs | ✅ `op_return` (4.00 bits) |
| Sending to base58 / bech32 / bech32m | ✅ `output_encoding` (bech32m 5.50 bits) |
| First / last change index | ✅ `change_index` (change-first 3.10 bits)† |
| Change type matches input(s) | ✅ `change_type_match` (mismatch 5.72 bits)† |
| Change type matches output(s) | ✅ `change_matches_output`† |
| Change address matches input | ✅ `change_address_reuse` (heuristic-free, 2.14 bits) |
| Change is always bech32 | ◐ via change-spk type |
| More than 2 outputs | ◐ count only (io-shape) |
| Spend unconfirmed outputs (zero-conf) | ❌ not a single-tx fingerprint — needs the tx's ancestry (parent-in-same-block), like the amount/time edges |
| Coin Control | ❌ not cleanly chain-observable — a UX behavior; UIH (its on-chain proxy) is now measured (8.8%, 3.5 bits) but does not *uniquely* identify manual coin control |

† conditional on a round-number change-identification heuristic (payment is the rounder
2-output; change is arbitrary) — the change-relation axes inherit that heuristic's error;
`change_address_reuse` is heuristic-free.

**Honest tally: ~30 of ~35 covered (measured bits), ~2 partial, ~2 not built** — the
library carries **22 measured axes**, the structural ones on a whole-chain BigQuery
sample (§5). The primary structural signal — the amount / receiver-contribution
subtransaction re-partition — is covered (§2/§6). **The honest ceiling is
~32/35, not 35/35:** the two remaining items are not clean single-transaction chain
fingerprints — **Coin Control** is a UX behavior no single tx uniquely reveals, and
**spend-unconfirmed** requires the transaction's ancestry (parent block heights), not the
transaction alone. The two ◐ partials (change-always-bech32, more-than-2-outputs) are
refinements of axes already covered.

**Deliberately out of scope (separate tracks, not part of the chain-observable fingerprint checklist):**
relay / timing fingerprints, JSON/HTTP serialization. The graph-level entropy / entropist
metric is **delivered** (§6, `decluster/graph_metric.py`), and the community-structure premise
(Narayanan–Shmatikov) is now **measured on a real slice** (§6, `decluster/graph_deanon.py`, AUC
0.95); the full seed-and-extend attack at chain scale still needs adjacency infra + labels.
These are named so absence is explicit, not hidden.

## 9. Limitations (honest)

- **Scope, not scale.** The fingerprint model *is* validated at mainnet scale — attribution
  AUC 0.974 on 106,644 real txs (§5) — and structural de-anonymization is measured across
  four eras (§6), both **without an archival node**. What we do not claim is a whole-chain
  **entity-reduction rate** (à la Wang et al.: "X% of all entities collapse") — that single
  number needs the full connected chain and is a separate follow-on (§10). The
  community-structure slices are also thin (a handful of blocks per era; the 2013 k=1 null
  shows one slice conflates slice-noise with era-trend), and the *stronger* N-S form
  (structure links what co-spend leaves separate) needs independent entity labels we lack —
  whose practical source is a catalog of known super-clusters (SatoshiDice, Mt. Gox,
  exchanges, pools) and entity-specific signatures (address-reuse eras, vanity prefixes,
  BIP-47 notification graphs; `catalog/known-entities.md`).
- **Low-R is a base-rate signal.** A non-grinding wallet emits a 71-byte signature ~50%
  of the time; low-R is a per-cluster *consistency* tell, low severity — the measured
  bits reflect this.
- **Policy-value over-clustering.** A match on a *policy* value (e.g. `locktime=height`)
  groups a *class* of wallets, not one; only rare values (`0x01`, `cake_group_c`) are
  strongly identifying. Per-axis specificity is modeled but not yet fully calibrated.
- **Independence assumption.** The engine sums per-axis bits assuming axis independence;
  real intra-wallet correlations (e.g. RBF ↔ locktime) may double-count.

## 10. Future work

The reason this measurement matters is constructive: every bit this paper reads as a link
is, inverted, a bit a wallet must avoid emitting. The offensive engine is the calibration
instrument for a defensive **cost function** — the bridge to collaborative multi-party
transactions where privacy can be *quantified and designed for* rather than hoped for.

What remains splits into one item that is only scale and two that are separate research.

**Only scale — the whole-chain rate.** The method is validated (§5/§6); it does not yet
report a whole-chain **entity-reduction rate** over the full connected graph. This needs no
archival node in principle: a small-disk Utreexo node (e.g. Floresta) already carries each
block's spent prevouts in order to validate them against its accumulator, so it is the
right architecture to stream `(block, prevouts)` at ~GB of disk rather than the ~600 GB of
an archival node. The remaining work is an integration spike — surfacing those prevouts
through the node's library API and running the scaled engine over the stream — not new
method. (That scaled engine, and its real-block / cached-tx runners, currently live in a
separate `tx-indexer` crate; the Python prototype here reproduces the method at
case-study scale.)

**Separate research tracks — not a scale run.** Two further directions are genuinely new
work: first, the full Narayanan–Shmatikov **seed-and-extend attack**, with richer features
(community detection, embeddings) and the independent entity labels the co-spend ground
truth cannot supply — bootstrapped from the known-entity catalog (`catalog/known-entities.md`);
second, the construction-side **cost function** — feeding the measured
bits back so a wallet shapes its own transactions to avoid these tells, the defensive
counterpart and a project in its own right.
