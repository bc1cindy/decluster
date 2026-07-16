# Fingerprint-Aware Probabilistic De-anonymization of Bitcoin Transaction Graphs

*Every empirical number below is reproducible from this repository:
`decluster/library.py` (measured bits), `results/RESULTS-bigquery.txt` (calibration on a
~105k uniform whole-chain sample), `results/RESULTS-fingerprint-validation.md` (attribution AUC 0.974 on 106k
real txs), `results/RESULTS-graph-deanon.md` (structural de-anon across four eras), and
`results/RESULTS-wp4.md` (the ground-truth case study). Scope: a fingerprint-aware
clustering **method**, validated at mainnet scale without an archival node; the one thing
left is a whole-chain **entity-reduction rate** (§9).*

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
We build a curated **library of fingerprints with evidence** (23 measured axes across the
chain-observable transaction-construction surface, calibrated on unbiased real-chain
samples — 17 structural axes on a whole-chain sample, and 6 on mempool samples (5 witness +
a block-feerate broadcast-time axis) — anchored to chain-proven examples) and, on a real mainnet
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
(§9). You cannot shape a transaction to avoid a tell you have not first measured.

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
the library carries **23 measured axes** in total (the base set plus the granular additions
in §7 — input-type presence, nested segwit, pubkey compression, multisig, OP_RETURN, output
encoding, the change relations, and a block-feerate broadcast-time axis): the 17 structural
axes calibrated on the whole-chain BigQuery sample, and 6 on mempool samples (5 witness +
broadcast-time; §5).

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

Ordering tells (input/output) are **n-conditional**: a sorted set arises by chance with
probability `1/n!` (½ at n=2, ⅙ at n=3), so the engine brands `bip69` only at **n≥4** and
abstains (`small_n`, no link) at n≤3 — the `3.00` above is the software-rarity link weight for
the reliable n≥4 case, not a per-tx claim at small n. (As a *change* predictor rather than a link,
this ordering axis validates as **real but low-coverage** — it resolves fewer cases than the
round-number baseline at comparable precision; §7.)

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
chain-scale measurement (which needs the whole connected chain, §9).

**Community-structure de-anonymization (`results/RESULTS-graph-deanon.md`).** Beyond pairwise
evidence, we test the Narayanan–Shmatikov premise directly: does the *structure* of the
transaction graph predict same-owner membership, independent of the co-spend heuristic? On
a **connected real slice** — blocks 400000–400004, 8 927 txs, 27 962 addresses, 2 463
entities (`bigquery/graph.sql`, no archival node) — with same-owner labels from transitive
co-spend clusters (itself a heuristic: it over-merges any collaborative transaction in the
slice, so these labels are a near-certain floor for ordinary txs; an independent entity label
would be stronger, §8) and held-out positives = same-owner pairs that are *not* directly co-spent
(267 578 pairs), a common-neighbors link-prediction score predicts same-owner membership.
Removing the co-spend edges that *define* those labels — scoring by payment structure
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
needs independent entity labels (§8).

## 7. Coverage of the chain-observable fingerprint surface

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
`change_address_reuse` is heuristic-free. §7 tests these axes against M&N same-owner change labels
(the ordering axis validates as a real but low-coverage change signal); a cluster-membership
`findNext` reaches higher raw accuracy but is circular against those labels (§7) and is not used.

**Honest tally: ~30 of ~35 covered (measured bits), ~2 partial, ~2 not built** — the
library carries **23 measured axes** (incl. a block-feerate broadcast-time axis, below),
the structural ones on a whole-chain BigQuery sample (§5). The primary structural signal — the amount / receiver-contribution
subtransaction re-partition — is covered (§2/§6). **The honest ceiling is
~32/35, not 35/35:** the two remaining items are not clean single-transaction chain
fingerprints — **Coin Control** is a UX behavior no single tx uniquely reveals, and
**spend-unconfirmed** requires the transaction's ancestry (parent block heights), not the
transaction alone. The two ◐ partials (change-always-bech32, more-than-2-outputs) are
refinements of axes already covered.

**Deliberately out of scope (separate tracks, not part of the chain-observable fingerprint checklist):**
relay / network-timing fingerprints, JSON/HTTP serialization. (The one timing signal we *do*
measure is the **block-feerate broadcast-time** estimate — a bound read from on-chain feerate
ordering, not network relay — as the `locktime_vs_broadcast` axis; `results/RESULTS-broadcast.md`.) The graph-level entropy / entropist
metric is **delivered** (§6, `decluster/graph_metric.py`), and the community-structure premise
(Narayanan–Shmatikov) is now **measured on a real slice** (§6, `decluster/graph_deanon.py`, AUC
0.95); the full seed-and-extend attack at chain scale still needs adjacency infra + labels.
These are named so absence is explicit, not hidden.

### Change identification: validating the ordering against same-owner change labels

Following Möser–Narayanan's non-interactive labeling — a 2-output transaction's change is revealed
when its address is later co-spent with the inputs' cluster — we build a labeled set on a one-day
mainnet slice (2024-06-01, 739,889 txs → **578** change labels after the M&N §2.2 filters:
fresh-change / reused-change removal and the >10% two-change-cluster exclusion). We then test each
construction axis as a change predictor: change = the output whose onward-spending transaction
**agrees with T on that axis** — a fingerprint agreement between T and its output's spender,
*disjoint* from the address-graph label. `coverage` = share of labels where the axis fires;
`prec.` = precision when it fires. (`decluster/change_gt.py`, `change_slice.py`, `change_validate.py`;
`results/RESULTS-change-id.md`.)

| axis (bootstrap B=2000) | TPR | FPR | coverage | prec. |
|---|---|---|---|---|
| tx version | 0.779 | 0.000 | 0.779 | 1.00 |
| nSequence | 0.768 | 0.007 | 0.775 | 0.99 |
| round-number baseline (`change_index`) | 0.486 | 0.080 | 0.566 | 0.86 |
| output order | 0.436 | 0.048 | 0.484 | 0.90 |
| input order | 0.320 | 0.066 | 0.386 | 0.83 |

Reading *the ordering* honestly: it is a **real but low-coverage** change predictor. `input_order`
fires on only 39% of labels (vs 57% for the round-number baseline, 78% for version) and, when it
fires, its precision (0.83) is about the baseline's (0.86); `output_order` fires on 48% at
precision 0.90. So ordering resolves *fewer* cases, not less accurately — the low recall is
coverage, not error. On this slice the strong single tells are `nSequence`/`version` (near-perfect
precision at high coverage: same-owner onward-spends reuse the wallet's sequence/version ~77%). The
combined tx-level pre↔post score reaches AUC ≈ 0.76 against a shuffle-null ≈ 0.5. This confirms the §3
distinction: the 3.00-bit ordering *link* weight and ordering as a *change* signal are different
quantities — the former stands; the latter is real but weak-coverage.

**A label-robustness caveat.** This ranking does not survive an independent label
(`results/RESULTS-special-change.md`). Re-run against an *optimal-change* label (the smaller-than-any-input
output must be change — a value signal disjoint from co-spend) on a multi-epoch sample, all four
onward-spend axes fall to ~0.60–0.74 precision and `nSequence`/`version` no longer dominate ordering.
Part is a co-spend-label **selection bias** — that label selects changes whose onward-spender *is* the
same-wallet reveal transaction, which shares nSequence/version by construction (inflating the numbers
above); part is epoch / time-gap drift in the multi-epoch sample. Disentangling the two needs a
contiguous-value slice running both labels on the same transactions (future work). The single-day
figures above are slice- and label-specific, not a general claim.

**A circularity caveat.** We also implemented Kappos's cluster-level `findNext` (change = the output
whose onward-spend's construction features are in the input cluster's feature set). Against an M&N
co-spend label it is **circular** — the change's onward-spender *is* the co-spend reveal transaction,
hence a cluster member by construction (verified: change spender is a member 576/578; payment spender
0/226), so "features ∈ cluster set" reduces to the label itself, and nulling the entire construction
fingerprint still scores 0.66. M&N's co-spend label and Kappos's co-spend-cluster `findNext` share
the same signal, so the latter cannot be validated against the former; the label-disjoint validation
is the per-axis test above. (`change_cluster.py` implements `findNext` but its number is a
label-consistency upper bound, not a fingerprint result.)

This is a case study: one day, labels skewed to fast-spending wallets (only change spent inside the
window is revealed) over one-day clusters. A multi-epoch replication is future work (§9).

## 8. Limitations (honest)

- **Scope, not scale.** The fingerprint model *is* validated at mainnet scale — attribution
  AUC 0.974 on 106,644 real txs (§5) — and structural de-anonymization is measured across
  four eras (§6), both **without an archival node**. What we do not claim is a whole-chain
  **entity-reduction rate** (à la Wang et al.: "X% of all entities collapse") — that single
  number needs the full connected chain and is a separate follow-on (§9). The
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
- **Same-software false positives.** Fingerprints separate only *different* wallet software;
  two owners sharing a wallet, timezone, and fee policy emit matching fingerprints, so the
  fingerprint channel goes silent and cannot refuse merging their clusters in a shared
  payjoin. The control then rests on the amount structure alone (~1.6 bits for 2-in/2-out) —
  thin. The robust fix is to score graph topology as a quasi-identifier: even with identical
  fingerprints, Alice's counterparties differ from Bob's, and few such distinguishing
  relationships suffice (Narayanan–Shmatikov). We *measure* that structure separates owners
  (§6, AUC 0.95). The engine *scores* it as a Fellegi–Sunter quasi-identifier
  (`topology_weight`, `cluster_topology_weight`, `results/RESULTS-topology.md`): a shared
  rare counterparty carries mean `+3.57` bits for same-owner pairs (AUC 0.84 on a real
  slice). The *per-pair* disjoint mismatch is weak (`−1.65` bits, `P(disjoint|same)=0.32` vs
  `1.00`) and cannot refuse alone — the strength must come from *accumulation*, exactly the
  "enough distinguishing relationships" the N-S argument needs. Aggregated to the cluster
  level it does: same-owner clusters *never* have disjoint aggregate neighbourhoods
  (`P=0.00` of 272) while different owners almost always do (`0.997`) → `~−8` calibrated bits.
  Evaluating co-spent merges confident-first, this refuses a same-software payjoin end-to-end
  (`fp +2.78 − 8 = −5.2` → split; without topology the co-spend collapses them).

  A subtler false positive arises when two clusters share counterparties but only
  non-distinctive ones (common hubs). Without a check, hub-only overlap could rescue a
  spurious merge. This is handled by a **global rarity threshold** (`cluster_topology_weight`,
  `topo_tau`): the shared counterparties are rarity-weighted (`−log2(share)`, so a hub is ~0 bits)
  and summed; an overlap **below `topo_tau = 1.0` bit** — disjoint, or only non-distinctive hubs —
  is treated as disjoint (`−8`), refusing the merge, while a distinctive rare shared counterparty
  (≥ tau) corroborates same owner. Because rarity is global, this is field-independent (a universal
  hub is always refused). The threshold **discriminates cleanly** on a real slice: same-owner
  cluster pairs share **11.7** mean overlap bits vs different-owner **0.004** (99.97% share
  nothing) → **AUC ≈1.00 (0.9997)** (`calibrate_topo_tau`; see `results/RESULTS-topology.md`). The residual
  limit is inherent to the counterparty quasi-identifier, not the threshold: two *different* owners
  who both use the same **rare** counterparty score above tau and merge — a shared rare
  quasi-identifier is legitimate same-owner evidence in the FS model. (An earlier windowed N-S
  *eccentricity* was field-dependent and is replaced by this global rarity test — itself N-S's own
  quasi-identifier weighting `wt = 1/log|supp|`.)

  Chain-scale seed-and-extend over the whole graph remains future work (§9). We also *tested*
  a cluster's **temporal activity schedule** — the broadcast-time (§7) of its txs aggregated
  into an hour-of-day histogram (`active_hours`/`schedule_distance`, `results/RESULTS-temporal.md`) —
  as a candidate quasi-identifier, and report it as a **negative result**: on a 30-day sample
  of 20 000 reused-address clusters a naive split-half gives AUC 0.92, but that number is a
  concentration artifact — under a persistence (time-ordered) split with negatives matched on
  active-hours count the AUC collapses to **0.49 (chance)**. So the hour-of-day schedule does
  *not* identify owners in this data; disjoint active hours remain at most weak evidence of
  *different* owners. The mechanism is available, but unvalidated (§9).

## 9. Future work

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
case-study scale.) The same scale gap applies to the change-identification validation (§7): its
labels and clusters are one-day; a multi-epoch replication is only scale, not new method.

**Separate research tracks — not a scale run.** Two further directions are genuinely new
work: first, the full Narayanan–Shmatikov **seed-and-extend attack** at chain scale — the
rarity-threshold FP-control (§8) is delivered; what remains is running the cluster-level
topology over the whole connected graph with richer features (community detection,
embeddings) and the independent entity labels the co-spend heuristic cannot supply
(bootstrapped from the known-entity catalog, `catalog/known-entities.md`); second, the
construction-side **cost function** — feeding the measured bits back so a wallet shapes its
own transactions to avoid these tells, the defensive counterpart and a project in its own right.

## 10. Related work

- <sub>**nothingmuch, [*Anonymity Sets on the Transaction Graph*](https://github.com/nothingmuch/tx-graph-anonymity-sets)**: the theoretical framework this paper calibrates empirically — entropic anonymity sets (§6), the sub-transaction and absorber models (§2/§6), and the graph-as-quasi-identifiers argument the topology term realizes (§8). We measure and implement what it models.</sub>
- <sub>**Maurer, Neudecker & Florian**, *Anonymous CoinJoin Transactions with Arbitrary Values* (2017): the **sub-transaction model** — a transaction with arbitrary amounts can be re-partitioned into the plausible original transactions, and their number and plausibility bound its anonymity. The origin of the amount-based re-partition we take as the *primary* signal (§2/§6).</sub>
- <sub>**LaurentMT**, *Boltzmann* (OXT, 2015): operationalized the sub-transaction model as transaction **entropy** `E = log₂N` over the N plausible input→output interpretations. §1 refines this: what bounds anonymity is the *entropy of the distribution* over partitions, not the count `log₂N`.</sub>
- <sub>**Fellegi & Sunter**, *A Theory for Record Linkage* (JASA 64(328):1183–1210, 1969; [doi:10.1080/01621459.1969.10501049](https://doi.org/10.1080/01621459.1969.10501049)): the record-linkage weight-of-evidence the engine scores in — an agreement on a value of frequency `p` contributes `−log₂p` bits (§4); the topology term internalizes counterparty overlap as an FS quasi-identifier, and the rarity threshold is its rarity-weighting of that match (§8).</sub>
- <sub>**Narayanan & Shmatikov**, *Robust De-anonymization of Large Sparse Datasets* (IEEE S&P 2008; [arXiv:cs/0610105](https://arxiv.org/abs/cs/0610105)) and *De-anonymizing Social Networks* (IEEE S&P 2009; [arXiv:0903.3276](https://arxiv.org/abs/0903.3276)): structure alone re-identifies nodes. Their rarity-weighted quasi-identifier score `wt(i) = 1/log|supp(i)|` is the basis of our topology distinctiveness threshold (`−log₂(share)`, §8). §6 tests the *premise* on a real connected Bitcoin slice — payment-graph structure predicts same-owner at AUC 0.95 beyond co-spend (`results/RESULTS-graph-deanon.md`); the full seed-and-extend attack at chain scale, and richer features (community detection, embeddings), remain future work (§9).</sub>
- <sub>**Möser & Narayanan**, *Resurrecting Address Clustering in Bitcoin* (FC 2023; [arXiv:2107.05749](https://arxiv.org/abs/2107.05749)): the non-interactive change-labeling method — the change of a 2-output transaction is revealed when its address is later co-spent with the inputs' cluster — and the "consistent fingerprint" change heuristics (their Table 4, incl. ordered ins/outs). We reproduce their labeling and §2.2 filters, and their per-axis validation, on a real slice (§7; `results/RESULTS-change-id.md`).</sub>
- <sub>**Kappos et al.**, *How to Peel a Million: Validating and Expanding Bitcoin Clusters* (USENIX Security 2022; [paper](https://www.usenix.org/system/files/sec22-kappos.pdf)): change identification by whether an output's onward-spend belongs to the same peel chain — the cluster-feature `findNext` (TFC/AFC/changeC). We implement `findNext` (§7, `change_cluster.py`), but note it cannot be *validated against* an M&N co-spend label: the two share the co-spend-cluster signal, so `findNext` scores that label by construction (§7 circularity caveat). Our label-disjoint validation is the per-axis fingerprint test instead.</sub>
- <sub>**Wang et al.**, *Exploring Unconfirmed Transactions for Effective Bitcoin Address Clustering*: the closest model — a clustering-effectiveness paper reporting **entity reduction** on the whole chain (co-spend +2.3%, novel heuristics +9.8%). We follow the same anonymity-collapse framing but at **case-study scale** (the entropy metric on the merged-transaction graph, §6); a whole-chain measurement needs the whole connected chain, not an archival node (§9).</sub>
- <sub>**Dingledine & Mathewson**, *Anonymity Loves Company*: uniformity is a network-effect property — a wallet that de-biases one axis but stands out on another gains nothing. This grounds our recommendation to randomize *between legitimate behaviors* (same distribution), not merely to fix single fingerprints.</sub>
- <sub>**Syverson**, *Why I'm Not an Entropist*: caution on the entropy framing; we report bits as weight-of-evidence for pairwise linkage, not as a single anonymity scalar.</sub>
- <sub>**Tracking issue** — [*chain-observable transaction-level fingerprinting*](https://github.com/payjoin/rust-payjoin/issues/1597) (payjoin/rust-payjoin #1597): the venue for this program and its review discussion.</sub>

