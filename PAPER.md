# Fingerprint-Aware Probabilistic De-anonymization of Bitcoin Transaction Graphs

*Reproducibility is tracked per result rather than asserted for this manuscript as a whole.
Canonical runs declare code, data, parameters, environment, outputs and limitations in
`catalog/runs`; `results/generated` is derived from those artifacts. Historical `RESULTS-*`
documents without a run manifest remain evidence records, not independently reproducible results.
Public cold-start reproduction also remains pending until every required blob has an immutable
public location and an independent mirror.*

*Two scope conditions are load-bearing. The reproducible attribution levels are **0.9459** on the
committed 600-transaction fixture and **0.9244** on the preserved 22,112-transaction cache; each
use below identifies its population (§5). **The preserved cache is single-era** — heights
800,000–965,220, Taproot only — so no multi-era claim about it is supported by data on disk.
Figures without a run manifest are identified as non-canonical measurements.*

## Abstract

On-chain Bitcoin privacy is an emergent property of the transaction graph, not of any single
transaction. The **graph is primary**: on our reading the amount channel is the most defeatable
layer — net-settlement and deliberately underdetermined values silence it — and, following the cited
framework (`tx-graph-anonymity-sets`, §05), we treat the amount channel as *embedded within* the
graph model. Two regimes are exceptions to that defeatability, and both are our reading rather than
the framework's, which carves out neither. The first is decidability: where the amount structure is
decidable — a sparse subset-sum instance, or a plausible round partition — the amounts become the
*locally* decisive de-anonymization signal, ahead of any wallet-software fingerprint. The second is
dominance: where one participant's input exceeds what every other participant brought to a round,
conservation traces the funding of outputs to them by arithmetic, with no partition required to
survive and no client model invoked — value provenance, not ownership, since a participant settling
obligations inside the round sends their satoshi into a counterparty's output. The two do not
overlap: the first partitions and abstains under ambiguity, the second never partitions at all.

A transaction that merges unrelated parties can be re-partitioned into per-owner subtransactions by
subtracting a contributed input from an output and testing whether the implied payment "makes sense"
(a round number, under the unnecessary-input heuristic), or, for a general coinjoin, by de-mixing
each participant's input against the mix denomination and their change output
(`input = mix + change − fee`, `decluster/coinjoin_demix.py`). On a real JoinMarket coinjoin of 11
participants the de-mix recovers 8 of the makers uniquely, with fees matching the reference tool.
**Where the amounts are dense** — a well-mixed coinjoin, where many input→output mappings balance —
the de-mix is silent and the wallet fingerprints and cluster-level graph structure carry the weight:
the labelled real dense coinjoins recover 0 participants, so they are amount-private *to that
question* (§2, `results/RESULTS-subtx-demix.md`).

We present a partition-refinement clustering that fuses signed bits of evidence over the labeled
transaction multigraph — refusing false merges rather than only growing them, the cluster-collapse
failure of a single union-find. Its dominant, most robust term is the Narayanan–Shmatikov
cluster-level counterparty structure — the graph itself; onto it fuse the amount-based subtransaction
re-partition and a curated **library of fingerprints with evidence** (23 catalogued axes, 22 active
on stored data) calibrated on unbiased real-chain samples (§3/§5). On a real mainnet merged
transaction whose correct owner-partition is known, the intended false merge is re-partitioned by the
amount structure and again by the fingerprints — the two signals fuse and agree (§6). A merge's
~1.6 bits of structural ambiguity cannot survive the identifying structure an established cluster
carries — measured at a median ~33 bits per cluster on a real slice, a lower bound on the >100
whole-chain figure — so fingerprint uniformity is necessary but far from sufficient for
collaborative-transaction privacy.

This measurement is instrumental: the same per-axis bits, read as a penalty instead of a same-owner
link, define a construction-side cost function, so quantifying the attack is the prerequisite for the
defense (§10). Beyond clustering, the same graph yields a coin's provenance anonymity set — its
distribution over ancestral origins from an absorbing random walk, whose min-entropy is a lower bound
on the coin's provenance entropy (§04) — fused with the same-owner beliefs and node-bounded for deep
coinjoins, exposed as one callable pipeline (§8). Every reading is a lower bound / weight-of-evidence,
never a privacy score.

## 1. Introduction & thesis

**Scope of the bits.** Every bit in this paper is an *attacker's* weight-of-evidence for linkage — a
lower bound on how identifiable a construction is under our best models, absent auxiliary information —
not a "bits of privacy" a transaction possesses. We never claim a transaction "has N bits of
anonymity": reading a single structure's entropy as its privacy is misleading (a distribution can be
assumed to yield almost any number), and the entropy of the sub-transaction model relates to privacy
only when it is *low* (Liebig's law of the minimum — the weakest channel governs). Accordingly the
sub-transaction / subset-sum channel enters this engine only as evidence that can *refuse* a link (cut
a coin from the graph), never as a positive term that adds anonymity. That constraint is
architectural, not stylistic, and it binds even where an amount argument is sound: a conservation
bound — a set of equal outputs worth more than every other participant brought to the round, so the
excess has no other source (`decluster/conservation.py`, §10) — is arithmetic rather than heuristic,
and still stays *outside* `cluster_refined`, because feeding it in would make this channel emit the
positive same-owner term the invariant forbids. It is reported beside the engine, never inside it. The measured `−log₂p` fingerprint
weights are that on-chain *leak* — evidence an analyst reads directly from the graph, which *reduces*
the auxiliary information an adversary must otherwise supply, not a bound the adversary must overcome.
The lower bound on that auxiliary information is set instead by the *residual ambiguity* — the
interpretations that survive the leak — and how far to trust that floor against a given threat model
(how much auxiliary information is really available) is an irreducibly subjective discount the user
must apply.

The common-input-ownership heuristic clusters all inputs of a transaction as one
entity. Collaborative transactions that deliberately merge unrelated parties violate it,
hoping a chain analyst will merge the parties into one entity. We show this hope is
quantitatively misplaced. A two-in/two-out merge adds at most **log₂3 ≈ 1.6 bits** of
ambiguity, while an established cluster in a social-transaction graph carries far more
identifying structure. We measure it: on a real connected slice, every co-spend cluster's
counterparty-rarity bits sum past the merge's 1.6 (median **~33 bits**, ~12% already exceed
100) — the Narayanan–Shmatikov accumulation computed directly (`results/generated/cluster-bits-v1.md`).
The **>100-bit** figure is the whole-chain order of magnitude; a slice undercounts each
cluster's counterparties, so the measured median is a lower bound (§10). An analyst needs only
~2 of those bits to override the merge, and every cluster supplies an order of magnitude more.
Enlarging the merge does not help: more inputs inflate the *count* of possible
owner-partitions — combinatorially, on the order of B(#ins)·B(#outs) (Bell numbers) — but
not the *entropy* of the distribution over them, which is what anonymity actually measures.
Fingerprints and amounts peak that distribution on the partition that splits the inputs
along their existing clusters, and those clusters can in turn be intersected *across
transactions* to a common origin (Goldfeder et al. — an intersection attack is inherently
multi-transaction, using the whole graph, not any single tx). That argument is carried in code:
`decluster/monitor.py` walks tracked coins forward to the occasion — a later transaction spending two
of them — `decluster/intersect.py` intersects their candidate origin sets, and the co-spend then enters
`cluster_refined` as a prior the fingerprint, amount, topology and provenance channels can still
refuse — a refutable prior, not a verdict, which is what separates
an intersection attack from the common-input heuristic it would otherwise be. The occasion is an
external event and is not guaranteed: branches that stay unspent, or that re-enter a mix, never supply
one. Where one exists the pipeline runs end to end on chain data, and what surfaces there — including
which channel ends up carrying the decision, and which is gated shut — is reported in §9.
More inputs buy possibilities, not privacy.

Our contribution is the *combination engine* plus the *evidence library* that make this
concrete: heuristics and fingerprints are fused as signed bits on a weighted graph, and
a partition-refinement pass over those bits (`cluster_refined`) admits *negative* edges, so it
can refuse a co-spent merge — the refinement lattice, not the merge-only union-find that can only
*grow*, never *refuse*. It is order-independent (a synchronous fixed-point) yet keeps the
Narayanan–Shmatikov cluster-level counterparty accumulation. It is the only fingerprint-aware
engine; `cluster_naive` is the merge-only BlockSci baseline it is compared against.

This offensive result is a means, not an end: the de-anonymization engine is the
measurement half of a construction-side cost function for collaborative transactions
(§10). You cannot shape a transaction to avoid a tell you have not first measured.

## 2. Straw-man: why merging unrelated parties does not deliver privacy

A merged transaction induces a false common-input link between a receiver and a sender.
Three facts defeat it, in order of importance:

0. **The amount structure (primary in the decidable regime).** The receiver contributes an input that is added to
   the payment output. An analyst subtracts a candidate contributed input from an output
   and reads off the implied payment; if that payment is a plausible (round) number under
   the unnecessary-input heuristic, the partition is likely. For a 2-in/2-out merge the
   per-owner balance is automatic, so the discriminator is the payment's round-ness, and
   the number of plausible partitions is small — often one clean answer. This
   re-partitions the merge before any fingerprint (§6). *Round-ness is a heuristic, not
   a proof:* it needs a value model (a round number in fiat at the time, not just in sats),
   and a market-priced payment may carry no round-number signal at all — so the amount
   channel is strong where a plausible round partition exists (as in §6) and silent where
   it does not. In the fused engine this round-ness re-partition corroborates a fingerprint
   disagreement rather than refusing a co-spend on its own (§4, §9): it identifies the likely
   split, but the standalone refuse is gated on the fingerprint also disagreeing.
1. **The backward channel (fingerprints).** A collaborative construction can coerce
   intra-transaction fingerprint uniformity (e.g. the receiver copies the sender's
   `nSequence`), but it cannot reach the *prior* transactions that created each input.
   Those carry wallet-specific fingerprints an analyst reads to corroborate the amount
   partition.
2. **The bit asymmetry.** Even with perfectly uniform fingerprints and ambiguous amounts,
   the merge's ~1.6 bits are dwarfed by the prior clustering evidence — a median of 29.0 bits per
   cluster on the committed cache, where every one of the 2538 clusters clears the merge's
   contribution (`results/generated/cluster-bits-v1.md`); the cache is block-sampled, so that median
   is a floor. The partition is decidable *without needing the merged transaction at all*.

**What the fusion measurably adds.** The engine is what makes those channels one decision rather
than a list of opinions, and `results/generated/fused-engine-v1.md` runs it over committed
transactions as a ladder. On 335 co-spends spanning 753 funding transactions, the merge-only
baseline leaves 697 clusters and refuses nothing; the fingerprint channel adds 7,560 links the
co-spend missed and declines 19 of the merges the baseline takes. The two remaining channels move in
opposite directions, which is what fusing them is for: cluster-level topology corroborates merges
the fingerprint alone objected to, taking refusals to 11, and provenance-disjointness cuts pairs
that survived it, taking them to 22. The amount channel moves nothing on that slice, and the reason
is the gating stated above rather than a failure of the channel — it is refuse-only and speaks only
where the fingerprint already disagrees.

## 3. The fingerprint library (evidence)

We catalog the chain-observable transaction-construction axes (nSequence, nLockTime,
input/output ordering, change script type, tx version, coin-selection/UIH, low-R grinding,
SIGHASH type, fee-rate, input script type), grouping seven reference
integrations per axis (`catalog/tx-construction-matrix.md`). Each axis carries an
extractor, measured bits, and a chain-proven example (`decluster/library.py`);
the library carries 23 catalogued axes / 22 active on stored data (the base set plus the granular
additions in §7 — input-type presence, nested segwit, pubkey compression, multisig, OP_RETURN, output
encoding, the change relations, and a block-feerate broadcast-time axis): the 16 structural
axes calibrated on the whole-chain BigQuery sample, and 7 on mempool samples (5 witness + OP_RETURN +
broadcast-time; §5).

**One catalogued axis is inert on any stored dataset.** `locktime_vs_broadcast` reads a
`_bc` annotation that only `broadcast.annotate_broadcast` writes, and only at fetch time, so on a
stored record it returns `na` for every transaction. Measured on the preserved 22,112-transaction
cache: `Counter({'na': 22112})`, zero transactions carrying the annotation. `na` is not among the
axis's `bits` values, so the abstention predicate skips it — the axis is *inert*, not merely
constant, and contributes exactly nothing to any published pair score. It is declared in code
(`library.ANNOTATION_ONLY_AXES`). Every number in this paper drawn from a stored dataset is therefore
a **22-axis** number; we keep the axis catalogued because it scores under live annotation
(§7, `results/RESULTS-broadcast.md`). Where this paper says "23-axis" for a scored figure, read
"23 catalogued, 22 scored".

Bits are estimated from an unbiased mainnet sample (§5). Representative
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

(The whole-chain sample surfaces high-bit tells like the
Cake-style `seq_0x01_other` nSequence at 8.9 bits and mixed input types at 6.0 bits.)

Ordering tells (input/output) are n-conditional: a sorted set arises by chance with
probability `1/n!` (½ at n=2, ⅙ at n=3), so the engine brands `bip69` only at n≥4 and
abstains (`small_n`, no link) at n≤3 — the `3.00` above is the software-rarity link weight for
the reliable n≥4 case, not a per-tx claim at small n. Ordering as a *change* predictor is a separate
evaluation interface for which this paper reports no large-slice result (§7).

**BIP-69 byte order.** BIP-69 orders inputs by the prevout txid in *internal* (reversed) byte order
and outputs by value then scriptPubKey; `x_input_order` and `x_output_order` implement that order.
The witness cache places the `bip69` tell near 7–8 bits. The engine retains the 3.00-bit calibration
from a separate BigQuery sample, so it under-weights this tell; recalibration on the structural
sample remains pending (§5).

**Example transactions.** The catalog uses mainnet transactions from the unbiased sample:
`dce69633…` for low-R and `0361ae98…` for Taproot SIGHASH. The Cake group-C nSequence example
`8fb80573…` is also independently chain-observed on mainnet.

## 4. The engine

**Clustering is the unifying framework.** Every ownership signal is a clustering heuristic on one
comparability scale, ordered by reliability: address reuse is the near-certain floor (two txs spending one
address are one wallet, barring a dust attack or key theft); the common-input-ownership heuristic is
already fallible; change identification (§7) relaxes it further; coinjoin *intersection attacks* are a
coinjoin-specific clustering heuristic (the cluster-collapse problem); and wallet fingerprints (§3) are
another. The engine does not treat these as separate ad-hoc rules — it scores them all as signed bits of
evidence and fuses them onto one weighted graph, so they *compose* and can be *compared*.
The degenerate limit makes the framework's dependence on graph *connectivity* concrete: an isolated
subgraph — an unspent coinbase, say — is a cluster of one, assignable only to the miner who found it,
until a collaborative transaction connects it to the rest of the graph.

**What the headline scorer is, precisely.** Evidence is a signed weight-of-evidence in bits. For a
value of frequency `p`, a match contributes `-log₂p` toward "same wallet"; a mismatch contributes a
clamped negative penalty. That is Newcombe's value-specific frequency weight (1959/1962), scaled
in the same bits as everything else on the graph — it is *not* a fitted Fellegi–Sunter model.
The two are not interchangeable in magnitude: on the
preserved cache the fitted F-S model's largest *agreement* weight is **+1.3047** bits (`nsequence`)
and its largest disagreement weight **−11.13** (`locktime`), whereas the rarity weight reaches
**13.88** bits on a single agreement (`cake_group_c`) — a ratio of ≈10.6× on the agreement side
(`results/artifacts/fs-temporal-v1.json`). A fitted Fellegi–Sunter model *is* built and used in this repository —
`decluster/fellegi_sunter.py`, driving the temporal split and the ablation
(`results/RESULTS-fs-temporal.md`, `results/RESULTS-fs-ablation.md`) — but it is a different object
from the headline scorer, whose implementation (`rarity_weight_baseline.rarity_score`,
`combiner.rarity_score`) says so in its own header and raises a `DeprecationWarning` on the legacy
`fs_score` alias. Per co-spent pair the fingerprint score, the amount-structure weights
(the 2-in/2-out roundness `amount_refuse_weight`, applied only when the fingerprint also disagrees —
round-ness is a heuristic (§2), so it corroborates a refusal rather than forcing one; and the coinjoin
de-mix refuse `amount_refuse_demix`, which carries its own uniqueness guard), and the Narayanan–Shmatikov cluster-level counterparty-overlap weight
(`cluster_topology_weight` — the rarity-weighted overlap of two clusters' neighbourhoods, scored in
the Newcombe/FS frequency weight `−log₂(share)` that operationalizes the N-S `wt = 1/log|supp|`
premise (§12), and *not* a per-pair term) are summed, and the partition is refined by
`cluster_refined`: a union-find that both merges *and* refuses (the refinement lattice, going down
as well as up). A synchronous fixed-point recomputes the cluster-level topology on the growing
entities each round and unions the net-positive pairs until stable — order-independent, and
transitive: a net-negative co-spent edge is refused (splitting a bare merge, §6), a chain A-B, B-C
stays one wallet, and an established cluster's bits dominate a lone refusal. `cluster_refined`
produces every partition figure; `amount=False` gives the fingerprint-only corroboration (§6). Of
those terms only the fingerprint and the roundness weight are on by default: the de-mix, the
cluster-level topology and the provenance-disjointness refusal each require their input to be handed
in (`subsetsum=`, `neigh=`, `signatures=`) and contribute exactly zero otherwise, so a channel the
caller did not supply is absent rather than assumed. Only
the partition results depend on the engine at all — the per-axis bits, attribution AUC, structural
de-anon, and cluster-bits figures never call a clustering engine.

**The engine's fingerprint score deliberately uses three axes, not all 23.** `cluster_refined`
scores co-spent pairs on the three highest-entropy, least-correlated construction axes (nSequence,
nLockTime policy, input ordering), *not* the full 23-axis library that drives the attribution AUC
(§5). This is a design choice, not an oversight, and the distinction matters: the 23-axis score is
an excellent *pairwise discriminator* but a poor *clustering driver* at the engine's thresholds,
because summing agreement bits across many correlated low-entropy axes inflates spurious same-owner
links between different-software wallets that happen to match on several policy values — exactly the
conditional-independence double-counting §9 flags. Concretely, on the merged anchor `931d6627` (§6) the 3-axis engine refuses the false Cake↔sender
merge (−3.16 bits) and recovers the correct partition, whereas scoring the same edge with the
23-axis `LibraryScorer` *resurrects* the false link (**+11.67 bits**, well past the engine's
`link_above=4.0` threshold) and would re-merge the sender into the Cake cluster
(`results/RESULTS-3v23-engine.md`; measured directly by `catalog/runs/anchor-axis-families-v1.json`,
which scores this edge under all four axis sets on a committed fixture.)
(One of the 23 axes, `locktime_vs_broadcast`, abstains here and everywhere on stored records; 22 are
scored. See §3.) The per-axis breakdown shows why: the three genuinely discriminating axes still
refuse (−10.8 bits combined), but 19 low-entropy policy axes that both coins' ordinary SegWit wallets
happen to share (script type, encoding, sighash, `low_r`, ...) each add a small positive weight, and
summing them under the additive kernel's conditional-independence assumption overwhelms the real
discriminators. The wide-axis model as published is therefore the right instrument for measuring *attribution* and
the wrong one for driving *refusal*; the engine uses the narrow, decorrelated set on purpose. The
next paragraph measures exactly how much of that failure is redundancy rather than width.

**How much of that resurrection is double-counting, measured.** Dropping one representative per
measured correlated cluster — 14 axes rather than 23, `fingerprint_validate.decorrelated_scorer()`,
clusters and representatives from `results/artifacts/fs-ablation-v1.json` — the same Cake↔sender edge
scores **+3.59 bits** instead of +11.67. So **8.07 of the 11.67 bits (69%) are redundant copies of
evidence already counted**, and the decorrelated wide model lands *below* `link_above=4.0`: it no
longer resurrects the false merge. Redundant evidence, not width, causes the threshold error.

That independence assumption is the standing objection to any additive per-field record-linkage form —
Fellegi–Sunter and this rarity kernel alike — and the reason the deep-feature line of work (§12) is
held to be the more robust of the two. The engine does not answer it by swapping the weight:
`−log₂(share)` *is* bits, commensurable with the co-spend prior and the amount terms it is summed
with, whereas the N-S `1/log|supp|` is not, so substituting it would put the score out of unit with
everything else on the graph. It answers by restricting to a decorrelated subset, which makes the
premise approximately true where it is relied on. The N-S form is used where *multiplication* rather
than summation is the operation: `rarity_weight` (`decluster/intersect.py`) and `provenance_link`
(`decluster/ancestry.py`) weight a shared origin's mass by `1/log₂(|supp|+1)` rather than
accumulating evidence in bits.

Three properties matter for the thesis:

- **Beyond union-find.** The graph can carry *negative* edges, so the clustering can
  **refuse** a merge — impossible for a monotone union-find.
- **Bit-accounting / priors.** A large established cluster contracts as a unit carrying
  its full weight; a merge-strength contrary signal (−3 bits) cannot override an established
  cluster's prior (measured at a median of 29.0 bits on the committed cache; §1,
  `results/generated/cluster-bits-v1.md`). We verify this as a property test (`high_weight_prior_survives_contrary_fingerprint`);
  the fixed-point union-find keeps a large wallet whole as one component, so large wallets are not
  silently dropped at scale.
- **Real bits.** `Combiner.from_library` lets the engine score from the measured library bits
  (`library.py`) rather than a small in-sample fit.

## 5. Empirical calibration (unbiased real data)

Naive sampling of recent block tops is fee-biased. We first de-biased via mempool.space
(uniform across height + within-block fee-spread, `sample_chain_uniform`), then calibrated
definitively on a **uniform random sample of the whole chain via Google BigQuery's public
Bitcoin dataset** (`results/RESULTS-bigquery.txt`, `bigquery/sample.sql` — no archival node; the
query exports transactions in the pipeline's JSON schema so the same extractors run at
scale). **The 16 construction axes are estimated from a ~105,000-tx uniform sample across the whole chain**; the
witness axes (low-R, SIGHASH, pubkey compression, multisig, nested segwit) *and OP_RETURN* are measured on
a ~3,500-tx mempool sample, since BigQuery's schema carries no witness data (and OP_RETURN is degenerate
in the whole-chain export — all-`none`, 0 bits — so its 4.00 bits come from the mempool sample too).
That witness snapshot is effectively SegWit-era; re-measured across eras it drifts (below).

Whole-chain calibration notes:
- **nLockTime `zero` is ~74% chain-wide** (whole-chain BigQuery); a recent mempool sample
  runs higher (~85%). Chain-wide is the right prior.
- **UIH is a real signal.** The library's `uih` axis fires on ~8.3% of txs (3.6 bits), measured on
  the whole-chain sample with real top-level input values. **Which UIH matters here.** That axis is
  `extractors.x_uih`, a Gibson-style approximation: it brands `uih2` whenever
  `max(inputs) >= max(outputs)`, non-strict, with no restriction to two outputs and no fee term. It
  is **not** Ghesmati et al.'s Algorithm 2, which this repository also implements separately
  (`baselines/unnecessary_input.py`, with the paper's UIH1 / UIH2 / *uncategorized* three-way
  outcome) and which is deliberately a different observable. Every UIH-derived number in this paper
  and in `results/RESULTS-amount-channel-survey.md` is the approximation, retained so historical
  fingerprint artifacts do not shift silently; the paper-faithful categoriser is the one to cite
  when the claim is about Ghesmati's rates.
- Distributions are non-stationary: e.g. round fee-rates are ~17% chain-wide but ~9%
  in recent blocks — old wallets used round fees more. Chain-wide is the right prior.
This is a large representative sample (~105,000 txs), not literally every tx; exhaustive
per-tx measurement would still want the whole chain, but for calibrating fingerprint
frequencies this is publication-grade (rare values become estimable).

**Validation on real data (`results/RESULTS-fingerprint-validation.md`).** Do the calibrated
bits actually attribute wallets? On **4,000 same-wallet and 4,000 random tx pairs**, with same-owner
labels = address reuse (two txs spending the same input address are the same wallet), the rarity
score ranks same-wallet tx pairs far above random ones. The manifest-backed run is the committed
**600-transaction fixture**: positive mean
**+19.65 bits**, negative **−17.41**, **AUC 0.9459**, shuffle control 0.4908
(`catalog/runs/fingerprint-validation-v1.json`, `results/artifacts/fingerprint-validation-v1.json`).
The **preserved 22,112-transaction cache** gives **AUC 0.9244**, positive **+15.47** bits, negative
**−16.58**, shuffle 0.4984 (`results/generated/weight-sensitivity-v1.md`, row `c = 0.95`; the same
0.92445 appears as the `fixed_0_95` library-scorer AUC in `results/artifacts/em-m-v1.json`). Results
below identify whether they use the 0.9244 cache estimate or the 0.9459 fixture estimate.

Two scope limits on the preserved cache follow from its contents rather than from the method.
It spans heights 800,000–965,220 — the Taproot era only, so it cannot support a multi-era claim.
The pair draws are sampled with replacement, so the effective support is narrower than 4,000 (see
the results file). Subject to those limits the measured fingerprint model separates
same-wallet from random transactions on real data — a systematic, quantified result beyond the
prior anecdotal spot-checking.

**How much of that is the label restating itself, measured.** The labels are address reuse, and five
axes are fixed outright by the shared input address (`input_script_type`, `input_types_present`,
`nested_segwit`, `pubkey_compression`, `change_address_reuse`). Dropping them
(`fingerprint_validate.construction_only_scorer()`, 18 axes) on the preserved cache takes AUC
**0.9244 → 0.9003** and the positive mean **+15.47 → +8.42** bits. So **0.0241 of the AUC is label
leakage**, and the pure construction-style signal is **≈0.90**, still far above chance.

**The magnitude is inflated by redundant axes; the ranking is not.** Two of the catalogued axes,
`input_script_type` and `input_types_present`, are **perfectly correlated on the measured data —
φ = 1.000 in *both* the match and the non-match class** (`results/artifacts/fs-ablation-v1.json`,
whose own limitations line says they "are duplicates in this sample"). They are one fact scored
twice, and they are not alone: the same run clusters the axes at |φ| ≥ 0.6 into four groups. Keeping
one representative per group — 14 axes rather than 23,
`fingerprint_validate.decorrelated_scorer()` — on the preserved cache:

| axis set | AUC | positive mean bits | negative mean bits |
|---|---:|---:|---:|
| 23 catalogued (22 scored) | 0.9244 | +15.47 | −16.58 |
| 14 decorrelated | **0.9432** | **+8.72** | −10.24 |

The evidence **magnitude falls by 44%** (+15.47 → +8.72 bits) — the headline bits figure was
inflated ≈1.77× by double-counted axes — while the **AUC rises by 0.019**. The result is stronger,
not weaker: the redundant axes were adding bits without adding discrimination. Nor does this hinge on
which member of each group is kept. Sweeping **all 90** representative choices (5 × 3 × 3 × 2), AUC
lands in **[0.9299, 0.9439]** — *every* choice beats the 23-axis 0.9244. On the §4/§6 merged anchor,
the false edge stays positive at every axis set
we scored (+11.67 at 23, +4.91 at 18, +3.59 at 14). Its magnitude does not, and neither does its
position relative to a fixed threshold — at 14 axes that edge falls under the engine's
`link_above=4.0`. So every bits magnitude in this paper should be read at the decorrelated scale, and
any threshold calibrated against the 23-axis scale is calibrated against inflated numbers. These
decorrelated figures are reproducible from the committed cache and the shipped scorers but do **not
yet carry a run manifest**; what is canonical is the φ = 1.000 pair, the axis clusters and their
representatives (`fs-ablation-v1`).

**Robustness of the disagreement weights (`results/RESULTS-weight-sensitivity.md`,
`results/RESULTS-em-m.md`).** The mismatch weight depends on `c` — the assumed
probability that the *same* wallet agrees on an axis — which, unlike the agreement frequency `p`, is
not directly measurable without same-owner labels. Two experiments show the verdict does not hinge on
getting it right. Sweeping a global `c` from 0.60 to 0.99 swings the raw score by ~46 bits on the
random-pair mean (+8.85 → −36.95, so it changes sign) yet moves the **AUC by 0.00055** across the
realistic 0.90–0.99 band (0.0161 over the full 0.60–0.99 grid, and not monotone) — the
*magnitude* of the evidence tracks `c`, the *ranking* does not, because it is an aggregate over many
axes and the mismatch weight is clamped `≤ 0` (a wrong `c` can only soften an axis toward neutral,
never manufacture a match). Fitting `c` *per axis* by unsupervised EM (Winkler's EM for the FS model,
Splink-style; `u` fixed at the measured collision) recovers the address-reuse label with **AUC 0.932**
without being shown it, and yields per-axis `m` ranging from **0.51 to 1.00** — far from the flat 0.95
— yet the pair-AUC rises only from **0.92445 to 0.92535** (Δ **+0.0009**), a flat plateau under the
per-axis fit (`results/artifacts/em-m-v1.json`). The
divergence of the correlated axes' EM `m` from their label-implied value is the expected
conditional-independence artifact — and it is visible in the fit: the two φ = 1.000 axes above are
exactly the ones EM drives to `m = 1.000000`. This establishes the *fingerprint* leg of the
robustness claim; the **graph-topology leg is measured too** (`results/RESULTS-cluster-robustness.md`).
Fusing the counterparty-overlap term into the clustering (`cluster_refined(neigh=…)`, §9) and sweeping the
same `c`, the owner-partition is byte-identical across the whole range (Adjusted Rand Index **1.0**)
while a fingerprint-only clustering moves at both ends of the sweep — the >100 identifying bits of graph
structure (§1) swamp the per-axis weight uncertainty — fingerprint uniformity is necessary but
graph structure is what decides.

**Bayesian record linkage vs Fellegi-Sunter (`results/RESULTS-bayes-vs-fs.md`).** This comparison is
about a genuine Fellegi–Sunter model — the per-field `m`/`u` form of `decluster/fellegi_sunter.py`,
not the rarity kernel of §4 — and the F-S point estimate is the plug-in special case of Bayesian
record linkage. We build the Bayesian variant on the same per-field likelihood — a light Gibbs over the pair labels and per-axis `m` with a Beta prior,
`u` fixed — and compare. (These AUCs are on the classic per-field agree/disagree F-S — `m`/`u` per axis,
the form both models share — *not* the value-weighted rarity scorer of the plateau above; that scorer
draws most of its discrimination from the `−log2 p` agreement weights, so `m` barely moves it, whereas
the per-field form leans on `m` directly, which makes the same weight visibly affect calibration.)
On the preserved cache (`results/artifacts/bayes-vs-fs-v1.json`):

| scorer | AUC | ECE |
|---|---:|---:|
| F-S, `m` fixed at 0.95 | 0.91625 | **0.1455** |
| F-S, `m` fitted by EM | 0.93200 | 0.1750 |
| Bayesian, `m` integrated out | 0.93240 | 0.1936 |

Fixing `m` at `0.95` costs discrimination — 0.916 against 0.932 — and a fitted point `m` (EM) and
the full posterior are indistinguishable on the verdict (0.93200 vs 0.93240), the tie the theory
predicts (and partly structural: sharing the likelihood, the three scorers cannot diverge much on
discrimination). It does **not** cost calibration: the fixed-`0.95` scorer has the best ECE of the
three (0.1455), EM is worse (0.1750) and the Bayesian is worst (0.1936). Integrating `m` out buys a
falsifiable statement of uncertainty, not a better-calibrated score.

That statement is the Bayesian's exclusive addition, and the one thing a point estimate structurally
cannot give: a per-axis credible interval for `m`, outside which the flat `0.95` falls on **22 of 23
axes** — the lone exception, `locktime_vs_broadcast`, being inert on stored records (§3) and so
degenerate rather than agreeing. And a posterior band on cluster entity counts: on a clear-structure
50-node set the band is `[4, 4]` where the F-S point commits to **5**, and on an ambiguous 18-node
borderline set it is `[5, 6]` around an F-S point of 5 — the band excludes the point estimate on the
clear set and merely widens by one around it on the borderline one. So the Bayesian does not beat a
well-tuned F-S on the answer and does not calibrate better; it quantifies the confidence F-S leaves
implicit, and occasionally disagrees with it. The roles are fixed rather than interchangeable: F-S is
the production engine `cluster_refined` scores in — a cheap additive bit-weight the
partition-refinement fixed point and the graph cost function consume directly — and the Bayesian runs
beside it as a calibration audit. The inversion has no valid form, since F-S is the Bayesian's
degenerate-prior special case and a posterior is not a single additive bit.

## 6. Demonstration: a real merged transaction re-partitioned

Our anchor is a known merged transaction: `931d6627` is a confirmed mainnet
transaction that merges two wallets — a Cake Wallet receiver and a distinct sender
wallet — into one common-input group, so the correct owner-partition is known, not
inferred. On its ancestry graph (7 coins; inputs 2000 sats sender, 5750 sats Cake
receiver; outputs 791, 6750; fee 209):

- **Amount analysis (primary in the decidable regime, `results/RESULTS-gap1.md`)** re-partitions it:
  `6750 − 5750 = 1000` is a round payment, so the receiver is the Cake input and the sender is
  separate — at 1 bit ambiguity, resolved by round-ness, before any fingerprint. (This is the
  sub-transaction *analysis*; the engine's standalone refuse is corroboration-gated, below.)
- Union-find (BlockSci-style) mis-merges {Cake `0a568e3a`, sender `91106666`} — the
  exact false link the merge intends.
- **The engine (`cluster_refined`, `results/RESULTS-wp4.md`)** refuses that merge: the
  fingerprint evidence scores `−3.1 bits` (`max_ffffffff` vs `seq_0x01_other`), past the
  prototype's `−2.0` refuse threshold → the merge is re-partitioned, the sender isolated;
  and the fingerprint layer adds the links the co-spend missed (Cake lineage
  `+10.2 bits`, sender funding chain `+5.4 bits` each). The amount channel corroborates the same
  split (the round `1000`-sat re-partition above; the fingerprint disagreement is what licenses its
  refuse in the fused engine), so the two signals agree.
  Resulting clusters: `{sender}`, `{sender funding chain}`, `{Cake, lineage}` — the correct
  partition; union-find gave the wrong one.

This is an *existence* demonstration on one merged transaction, not a rate across the chain
— but it instantiates the thesis on real data: two independent signals fuse and agree to
re-partition the merge.

**Clustering-overcount diagnostic (`results/RESULTS-entropy.md`).** We quantify the effect as a
*relative* diagnostic — the entropy of the clustering *partition* (`H = −Σ (n_i/N)·log2(n_i/N)` bits;
`2^H`) read only as the ratio between the naive and fused clusterings. This is **not** an absolute
"bits of anonymity" of the transaction: partition entropy is a property of a clustering, whereas the
intrinsic anonymity of a payment — its interpretations under no auxiliary information — is the separate
path-counting anonymity object (§8), which this figure does not compute. The largest-cluster fraction
is used as a supercluster *rejection* signal (a supercluster argues *against* a clustering, never *for*
privacy). On the real
**depth-6 ancestry graph of `931d6627` (19 coins)**:

| clustering | eff. cluster count (2^H) | largest cluster |
|---|---|---|
| union-find (BlockSci) | 13.8 | 16% |
| fingerprint-aware | **3.7** | 53% |

The naive common-input view over-reports the anonymity-set size by ~3.7×; the amount +
fingerprint evidence collapses 15 clusters to 6 and forms a supercluster (53%). This is
the thesis quantified at the graph level — still a modest real graph (19 coins), not a
chain-scale measurement (which needs the whole connected chain, §10).

**Community-structure de-anonymization (`results/RESULTS-graph-deanon.md`).** Beyond pairwise
evidence, we test the Narayanan–Shmatikov premise directly: does the *structure* of the
transaction graph predict same-owner membership, independent of the co-spend heuristic? On
a connected real slice — blocks 400000–400004, 8 927 txs, 27 962 addresses, 2 463
entities (`bigquery/graph.sql`, no archival node) — with same-owner labels from transitive
co-spend clusters (itself a heuristic: it over-merges any collaborative transaction in the
slice, so these labels are a near-certain floor for ordinary txs; an independent entity label
would be stronger, §9) and held-out positives = same-owner pairs that are *not* directly co-spent
(267 578 pairs), a common-neighbors link-prediction score predicts same-owner membership.
Removing the co-spend edges that *define* those labels — scoring by payment structure
alone (common neighbors) — still re-identifies same-owner addresses at **AUC 0.95** on the
2016 slice; the shuffle control lands at 0.50. Graph structure de-anonymizes *beyond* the
common-input heuristic, on real data. Across five eras (2012–2024), swept over graph
reach *k* (k-hop, hub intermediates excluded; `decluster/graph_deanon.py --depth`). Each
slice is a contiguous block range (partition-pruned by `block_timestamp_month`,
`bigquery/graph.sql`); share% = fraction of same-owner pairs sharing a *direct*
counterparty:

| Year | blocks | entities | held-out pairs | share% | k=1 | k=2 | k=3 | k=4 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2012 | 200000–200019 | 189 | 9 635 | 96% | 0.97 | 0.99 | 0.98 | 0.97 |
| 2013 | 250000–250014 | 558 | 25 944 | **6%** | **0.53** | 0.78 | 0.92 | 0.98 |
| 2016 | 400000–400004 | 2 463 | 267 578 | 91% | 0.95 | 0.97 | 0.99 | 0.99 |
| 2023 | 800000–800002 | 363 | 111 | 65% | 0.83 | 1.00 | 1.00 | 1.00 |
| 2024 | 845982–846001 | 2 704 | 897 247 | 48% | **0.74** | 0.88 | 0.95 | 0.97 |

At k=1 the effect is *not* a clean era curve: the 2013 slice falls to chance (0.53) on
25 944 pairs. The mechanism is exact — 1-hop AUC tracks share%, the fraction of
same-owner pairs sharing a direct counterparty (96→0.97, 48→0.74, 6→0.53); 2013 is the
service-churn (SatoshiDice) era, where an owner's addresses each touch a *different* service
address. The 2024 slice anchors the modern end: heavy churn (48% share) starves k=1 to
0.74, yet depth recovers to 0.97 on 897 k held-out pairs — a robust modern point, not the
111 of 2023. But the structure is only deeper: sweeping reach recovers 2013 (0.53→0.98) and
**by k=4 all five eras sit at 0.97–1.00**. So structural de-anonymization holds across every
era; the graph *depth* needed scales with counterparty churn. (Deeper reach avoids the
small-world collapse only because hub counterparties are excluded — so high-k AUC approaches
non-hub component membership, a coarser tell than fine link prediction.) The stronger claim
— structure links entities co-spend leaves separate — still needs independent entity labels
(§9).

## 7. Coverage of the chain-observable fingerprint surface

The chain-observable fingerprint surface enumerates **~35 granular fingerprints**. We do **not** cover
all of them; "coverage" here is a per-item claim (✅ = extractor + measured
bits; ◐ = captured coarsely, not as the granular tell; ❌ = not built).

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
| More than 2 outputs | ◐ subsumed by `io_shape`; scoring it separately moves AUC by only a few thousandths — and the delta *flips sign* across cache samples (noise, not signal; `results/RESULTS-catalog-axes.md`) |
| Spend unconfirmed outputs (zero-conf) | ❌ not a single-tx fingerprint — needs the tx's ancestry (parent-in-same-block), like the amount/time edges |
| Coin Control | ❌ not cleanly chain-observable — a UX behavior; UIH, its on-chain proxy, measures 8.3% and 3.6 bits but does not *uniquely* identify manual coin control |
| Taproot script-tree depth from a round fee | ❌ not built — a niche *derived* leak: a round-number fee at the nominal rate can betray taproot script-tree depth. We model `fee_rate` (round/precise) and taproot script type, but not the depth inference |
| SegWit serialization / SegWit-conform | ◐ subsumed by `input_script_type` + `nested_segwit`; M&N's weakest tell (TPR ≈ 0.02). Scoring it separately adds only a ~±0.002 AUC double-counting artifact (within noise) — the redundant axis produces the *larger* swing — so it stays unscored (`results/RESULTS-catalog-axes.md`) |

† conditional on a round-number change-identification heuristic (payment is the rounder
2-output; change is arbitrary) — the change-relation axes inherit that heuristic's error;
`change_address_reuse` is heuristic-free. The implementation can test these axes against M&N
same-owner change labels, but the large-slice evaluation is not claimed because its dataset was not
preserved (§7). A cluster-membership `findNext` is not used as independent evidence because it shares
the co-spend-cluster signal with that label.

**Tally: ~30 of ~35 covered (measured bits), ~3 partial, ~3 not built.** The library carries
**23 catalogued axes** — including the block-feerate broadcast-time axis below, inert on stored
records, so 22 are active there (§3) — the structural ones on a whole-chain BigQuery sample (§5). The
primary structural signal, the amount / receiver-contribution subtransaction re-partition, is covered
(§2/§6). **The ceiling is ~32/35, not 35/35:** Coin Control is a UX behavior no single transaction
uniquely reveals, and spend-unconfirmed needs the transaction's ancestry rather than the transaction.
The ◐ partials are refinements of axes already covered, tested against the 23-axis scorer directly
and unstable within the noise floor — the output-count delta even flips sign across cache samples —
so the model leaves both unscored (`results/RESULTS-catalog-axes.md`).

**Separate tracks, not part of this checklist:** relay / network-timing fingerprints and JSON/HTTP
serialization. The consequential one — the provenance / "deep-feature" channel — is not out of scope
but developed as its own channel in §8: the 23 axes here are *low-dimensional* construction tells
that standardizing construction can drive toward zero, while where a coin came from is
high-dimensional, the origin of the sparse-high-dimension curse of dimensionality. That split is
measured rather than assumed, and the measurement is conditional. The construction fingerprint
behaves as an equivalence-class conditioner — it sorts a transaction into a construction-style bucket
without singling one owner out inside it — but the canonical run
(`results/artifacts/fingerprint-regime-v1.json`, `results/generated/fingerprint-regime-v1.md`) has
two weight sources, and they disagree:

| rarity weights | N-S-form top-1 | rarity-combiner top-1 | within-class mean gap |
|---|---:|---:|---:|
| `library` (fit elsewhere, out of sample) | 0.680 | 0.730 | 0.393 |
| `snapshot_measured` (fit on this snapshot) | **0.785** | 0.730 | **0.675** |

With out-of-sample library weights the N-S form trails the combiner at picking the true owner from
199 candidates (0.680 vs 0.730) and the within-class mean gap sits under `propagate.py`'s θ ≈ 0.5
reference — the conditioner signature. With weights measured on the snapshot itself the N-S form
beats the combiner (0.785 vs 0.730) and the gap rises above θ, but those weights are fitted and
evaluated on the same 600-transaction selection, which is evidence of sensitivity to the weighting
rather than evidence that construction fingerprints are universally sparse identifiers. The
supportable statement is the conditional one — **the conditioner verdict survives only under
out-of-sample weights** — and on that basis the sparse quasi-identifier regime that does pick one
coin out of the crowd is placed on the ancestry channel of §8 rather than on these low-dimensional
axes. `results/RESULTS-fingerprint-regime.md` records the falsification in its own header.

The one timing signal modelled here is the block-feerate broadcast-time estimate — a bound read from
on-chain feerate ordering, not network relay — as the `locktime_vs_broadcast` axis; it needs a
fetch-time annotation, so it scores nothing on any stored dataset and contributes to no figure here
(§3, `results/RESULTS-broadcast.md`). The relative clustering-overcount diagnostic is delivered (§6,
`decluster/graph_metric.py`), and a local common-neighbour structural-linkage adaptation is measured
on a selected real slice at AUC 0.95 (§6, `decluster/graph_deanon.py`) — not the seeded cross-view
Narayanan–Shmatikov attack, and its selected weak labels do not establish ownership accuracy. The
separate N-S baseline and Bitcoin snapshot experiment require supplied seeds; independent seed
discovery, social-corpus reproduction and chain-scale validation remain pending (§10). These are
named so absence is explicit, not hidden.

### Change identification

The implementation constructs Möser–Narayanan co-spend change labels and tests whether a
transaction agrees with an output's onward spender on each construction axis
(`decluster/change_gt.py`, `change_slice.py`, `change_validate.py`). The dataset used for the
large-slice evaluation is not preserved, so this paper makes no empirical claim from it. Such a
claim requires a versioned contiguous export with onward-spend links and an independent-label
robustness check. The committed value-based labels test two within-transaction heuristics without
co-spend clustering (`results/generated/special-change-labels-v1.md`); they do not carry the
onward-spender data needed to evaluate the construction axes.

### Wallet behavior after the pinned snapshot

The fingerprint cells use Cake Wallet `@dc1b369` (2026-06-10). Later releases bound the signal for
transactions they construct, while confirmed transactions retain their construction tells. The
demonstration transactions in §6, including Ex.3 `8fb80573…`, therefore remain repartitionable.
The relevant release behavior is:

- **Output ordering** — releases v6.3.0/v6.4.0 shuffle change instead of appending it last
  (`#3420` software+RBF / `#3432` hardware-wallet+Bitcoin-Cash).
- **Input ordering** — release v6.3.0 shuffles inputs instead of sorting them by BIP-69 (`#3379`).
- **Receiver input selection (UIH2)** — release v6.3.0 routes payjoin receiver candidates
  through `try_preserving_privacy` instead of contributing `unspent[0]` (`#3304`;
  v6.3.0), lowering but not eliminating unnecessary-input leakage from the
  receiver-contributed input.
- **Spending unconfirmed (receiver candidates)** — release v6.3.0 excludes 0-conf
  UTXOs (Cake `#3389`; ldk-node PR `#746` remains open), so a
  0-conf-ancestor contributed input rules the confirmed-only wallets out by
  elimination — a temporal/ancestry signal, not a single-tx one (§7).

Current divergences are nSequence group-C (`bitcoin_base#12`), nLockTime`=0`
(`#3385`) and greedy coin selection (`#3408`).

Two axes gained a qualitatively different case:

- **Anti-fingerprinting randomization (BTCPay/NBitcoin).** BTCPay is the first
  integration that *deliberately blends* rather than emitting a fixed value: NBXplorer
  keeps a 5-block window of the joint on-chain fingerprint distribution and, at build
  time, samples nVersion, nLockTime/fee-sniping, and low-R to fill any field the
  caller left unset — so on those axes it carries ~no per-tx partition signal (a
  random draw from the real distribution). Its residual fixed tells are structural
  and shared with the mainstream cluster (always-RBF `0xFFFFFFFD`, default-P2WPKH
  single-type vin, change-matches-wallet, the NBitcoin knapsack's `0.01 BTC`
  min-change). It is the reference for how a wallet defeats these axes without a
  library-side conformance pass.
- **Coin-selection prediction.** Coin selection carries a stronger technique than a
  static fingerprint value: an adversary who knows the algorithm can *replay* a
  suspected cluster's selection and, if a strictly-better coin was left unspent,
  argue the coin is mis-assigned to that cluster. This bites only against a
  deterministic selector — Cake (greedy, pre-`#3408`), Liana (BnB + deterministic
  fallback), a smallest-fit receiver, or Electrum (`CoinChooserPrivacy`, PRNG seeded
  from the candidate UTXO set) — and is defeated by a randomized one (Core's
  least-waste multi-solver with shuffles and a randomized change target; BTCPay's
  stochastic knapsack; BDK's SingleRandomDraw fallback), where a "better" unselected
  coin is consistent with normal behaviour. Against the randomized selectors only the
  *parameters* (min-change, cost-of-change, long-term feerate) fingerprint the
  algorithm, not the selection. The full per-integration split is in
  `catalog/tx-construction-matrix.md`.

## 8. Provenance channel & anonymity set

The high-dimensional provenance channel — where a coin came from, encoded as its ancestry signature —
is the deep-feature attack surface the low-dimensional construction axes of §7 deliberately set aside,
and the regime the conditioner-vs-quasi-identifier split there points to: the sparse signature that
*does* single a coin out. It is developed here as its own channel — first the attack primitives, then
the anonymity-set object they measure.

`ancestry_entropy` (`decluster/ancestry.py`) computes the
absorber-model provenance entropy — a backward walk weighted by the nominal-value transition rule
(`ancestry.value_flow_link_oracle`), solved as an absorbing Markov chain — a per-coin lower bound on
provenance ambiguity. The older **≈0-bit** mainnet observation was measured with the opt-in subset-sum
oracle and remains historical (`results/RESULTS-ancestry.md`); its input snapshot was not preserved,
so it is neither re-measurable under the new default nor carried over to it. What runs under the
default is the deterministic contract in `catalog/runs/ancestry-contract-v1.json`, which now names
the oracle in its own artifact rather than inheriting it. As a *bound*
that holds however it arose: truncation on an oracle refusal, like the depth cutoff, merges mass into
one atom and can only understate ambiguity. Reading it as confirmation of the framework's
"every coin is sparsely represented" premise asks more, because a boundary that is entirely the
oracle declining to walk is not an observed origin, and the run does not separate the two cases. The
distinction is reported by `intersect.evaluate` as `blind` (§9); applying it here is a
re-run, not a re-derivation. The deep-feature matching
attack — using that sparse ancestry signature as a Narayanan–Shmatikov distinguishing feature to *link*
coins — has a first demonstration too: `provenance_link` (`ancestry.py`) scores the rarity-weighted
overlap of two provenance signatures, and on the merged anchor `931d6627` it independently separates
the Cake and sender lineages (link **0.000** — disjoint provenance), a third channel agreeing with the
fingerprints and amounts of §6. At *graph scale* a first pass is only directional (same-owner pairs
share nonzero provenance, random pairs zero, but AUC ≈0.52 at depth 3), and a contiguous
value-bearing slice does *worse* — every signature collapses to a single boundary atom (AUC 0.50),
because a tractable-width slice cannot contain multi-hop ancestry (a coin's parents are older than the
window). This is the load-bearing point: provenance matching is intrinsically a whole-graph attack
— shared ancestry lives arbitrarily far back, unlike the few-block-local direct-counterparty structure
of §6 — so the strong graph-scale AUC is gated on whole-connected-graph data (the §10 prevout
stream), a data-scale requirement, not a missing method (`results/RESULTS-ancestry.md`).

`NSPropagator` (`decluster/propagate.py`) lifts that pairwise score to entities:
`entity_signature` aggregates a cluster's coins into one signature and `propagate_merge` grows a seed
labeling by rarity-weighted overlap, gated on an absolute match floor and — once a node has ≥3
competing labels — the N-S eccentricity gap, iterating to convergence. Its two-channel `should_split`
removes a co-spend edge only when provenance is disjoint *and* the fingerprint diverges; either
channel alone leaves the edge intact. Held-out seed re-identification is evaluated on a synthetic
fixture and a preliminary cache-bounded real run (`results/RESULTS-ns-propagation.md`), where most
signatures collapse to a single ancestral atom at the cache boundary — the whole-graph limit above —
so the run exercises the mechanism without establishing its strength; chain-scale evaluation remains
pending (§10). The live engine exposes the split channel as `cluster_refined`'s provenance-disjoint
refuse term (`decluster/cluster.py`, `provenance=`), gated on the fingerprint already disagreeing
(`fp < 0`) — the same discipline as the amount channel (§9).

Beyond clustering, the system measures a coin's provenance anonymity set: the distribution over
ancestral origins of the *same* absorbing walk, exposed by `analyze(txid)` per output beside a
subjective-fused reading. Its min-entropy is the same conservative lower bound on the coin's
provenance entropy (§04; a linear solve, not Monte Carlo); §06 reads such entropy as a lower bound on
the graph cuts to de-anonymize, but — per §12 — that transfer is not adopted here, so the number is
an entropy bound, not a cut count.

**Fusion.** Address-reuse self-transfer enters by default as a per-transaction subjective link matrix
that combines with the graph-derived one *before* the absorbing solve (our §04-faithful reading; §04
leaves the timing unspecified); the clustering engine's same-owner map is folded in when the caller
supplies it (`cluster_of` / `cluster_map`). The fused min-entropy is clamped never to exceed the
graph-only value: subjective evidence narrows the set, never widens it. On real transactions the fusion
sharpens where local same-owner structure falls inside the walk — 38% of address-reuse targets sharpen,
by up to 2.25 bits — while sharpening from a purely ancestral link is rare, which is what §06's
robustness argument predicts: intertwined deep structure resists de-anonymization.

**The node bound.** Deep coinjoin ancestry is exponential in depth (§03: intractable for larger
transactions; the explosion is, in effect, the privacy). A node cap bounds the walk to O(N) fetch/oracle
calls, returning a truncated lower bound in bounded time — ≈5 min on a real 9-in/17-out coinjoin
(`results/RESULTS-path-count.md`) — where the unbounded walk does not terminate. The bound is stated rather than assumed: it
can only omit origins, never invent them; exact deep resolution is not possible.

**Provenance route accumulation (§07 diagnostic).**
`provenance_route_accumulation.provenance_route_accumulation` weights each ancestral origin by link
probability alone, summed over every counterfactual input→output route reaching it. Subset-sum
multiplicity does not enter that bound, because `cost.py` declares the amount channel refuse-only
(§1): it may cut a coin from the graph, never weight one, and folding a mapping count in as a
per-hop multiplier would do exactly that. The count this walk does not use is read instead by the
amount channel's own refuse-only cut — `W(E)`, the `dense-subset-sum` crate's mapping count for a
transaction, routed by **`counting.count_w`** (`cost.py:63`) through the tiers guaranteed not to
overstate: sparse-exact, and the sparse lower bound where exact counting saturates. The radix tier is
an output-only structural diagnostic answering whether the amounts decompose into repeated
denominations; the crate tags it `Ambiguity::Diagnostic` and `counting.guaranteed_log_w` refuses it,
so a transaction whose count comes back refused yields no cut candidates at all rather than a guessed
one. Overstating `W(E)` would corroborate a cut the transaction's structure does not support, which
is the one error direction a refuse-only gate cannot afford.

That gate is strict, and the canonical measurement says how strict
(`results/artifacts/counting-router-v1.json`, `results/generated/counting-router-v1.md`). Over 1,428
real multi-input transactions the router resolves **82**: **0 radix-exact, 60 sparse-exact, 22 sparse
lower-bound, 13 radix-diagnostic (refused), 1,333 unknown**. Called *without* the precondition gate
the radix tier returns a positive reading **64** times, **51** of them on transactions carrying no
repeated denomination at all — which is the whole reason the gate exists. Downstream
(`results/artifacts/amount-per-coin-v1.json`): 318 ungated per-coin cut candidates across 95
transactions fall to **101 candidates in 62 transactions** after requiring a conservative nonzero
transaction-level `W(E)`, of which **61 (0 input, 61 output)** carry an exact transaction count
behind them. The construction-side path-count instrument has no structural-property term; the
separate route-capacity measurement and its limits are described in §9.

**The partition posterior as a check.** `cluster_posterior` is the exact-Bayesian same-owner clustering
posterior — a split-merge sampler verified against exact enumeration over the co-spend super-nodes
(≤5, the enumeration ceiling). The framework stops at clusters and
never forms `P(partition | data)`; this posterior is therefore a *check* on the production clustering, not
the headline anonymity set, and on a real slice it agrees with the clustering engine.

**One callable surface.** The measurement is exposed in the framework's pipeline order: same-owner
beliefs (`cluster_map`, bridging the clustering engine's transaction groups to an address→owner map)
→ the fused provenance anonymity set with optional path count and node bound (`analyze`) → the
partition-posterior check (`cluster_posterior`), over a panic-safe in-process or hang-proof
subprocess link oracle. Read as a penalty rather than a link, the min-entropy and the path count are
the quantities a constructed transaction must raise; measuring them is the prerequisite for designing
against them.

### The sparse-dataset attack these signatures enable: record linkage

The provenance signature is a sparse, high-dimensional record — the precondition for the
Narayanan–Shmatikov sparse-dataset attack (cit 19–20). Two measurements close that framing. First
the (ε,δ)-sparsity precondition — a distinct object from the amount channel's density gate
**κ = log₂(L)/N < κ_c** (Sasamoto eq 4.3, `dense-subset-sum/src/count/density_regime.rs`), which
governs when the dense-regime saddle-point `W(E)` estimate is valid and carries the opposite sign for
privacy, so the two are never composed into one "density". On real signatures the ancestry feature
space is sparse (a coin's
provenance signature typically has no near-twin), while the low-dimensional statistical fingerprint
space is *not* sparse on its own — so the distinguishing signal lives in the structural/ancestry
channel, which is exactly where record linkage bites (`results/RESULTS-def1-sparsity.md`,
`results/RESULTS-ancestry-sparsity.md`; a data-run over unversioned signatures under the conservative
uniform oracle). The canonical channel experiment measures structural vectors on 12,000
transactions from six 2016 blocks. Its export contains none of the four construction attributes,
so it establishes only that the sampled structural space is dense: δ(0.9) = 0.9975 at minimum
degree 2 and 0.8764 at minimum degree 20 (`results/artifacts/slice-channels-v1.json`,
`results/generated/slice-channels-v1.md`). It does not measure attribute density or graph-matching
performance. Second the
record-linkage attack itself: stratifying signatures by their own
sparsity and running Algorithm 1B (rarity-weighted overlap, eccentricity gate φ = 1.5) makes the gap
explicit. On the canonical run (`results/artifacts/reid-v1.json`,
`results/generated/reid-v1.md`; 200 records, 165 sparse / 35 dense), with `m` auxiliary origins drawn
from the target's own signature:

| stratum | m = 4 | m = 8 |
|---|---:|---:|
| sparse — pinned to the exact coin | 0.926 | 0.955 |
| dense — pinned to the exact coin | **0.057** | **0.086** |

Precision is 1.000 in every cell: where the eccentricity gate declares, it is right; the stratum
difference is entirely in *how often it declares at all*. That is a **~16× separation at m = 4 and
~11× at m = 8**. The separation is consistent with Theorem 2 rather than predicted by it: Theorem 2 states a
de-anonymization condition under sparsity, not a ratio between strata, and no ratio should be
attributed to it. (`results/RESULTS-reid.md`, band-pinned on committed
`tests/fixtures/reid_sigs.json.gz`.) The
scope: this is the demonstrated *link* between sparsity and de-anonymization on those signatures, not
a chain-wide rate — the fixture is a depth-bounded, non-representative sample; the representative rate
needs a uniform deep collection (§10).

### Social graph: cross-view matching

The contracted pseudonym graph is, per the framework, a social network (cit 24): two time-separated
views of it should be matchable from a small seed. Contracting two views, seeding a mining-pool /
high-degree correspondence and propagating (`view_match`) tests the framework's own "*if* the social
network structure is recoverable" premise. On one-day views a week apart the cascade does not ignite
and the ambiguity-cut partition does not decompose the graph, against both degree-baseline and
shuffle controls (`results/generated/graph-rejoin-2016-v1.md`,
`results/generated/partition-schemes-v1.md`). The framework's vertex and edge attributes are built
here and deliberately kept out of the acceptance gate: a bounded conditioner cannot turn a zero score
positive, but the gate reads the *separation* between leader and runner-up, and scaling tied
candidates by different factors is exactly how that separation is made (`decluster/view_match.py`,
`tests/test_view_match.py`).

A larger slice reads the same under a harness that does not hand the matcher its answer: each cluster
is split along the view boundary into two pseudonyms (`split_clusters_by_view`, the
incomplete-clustering premise) and the matcher is asked to rejoin them from structure. Over complete
weekly January-2016 views (982,021 and 1,116,563 transactions) holding 17,431 straddling clusters, at
a 10% high-degree seed the directed matcher makes **one guess, and it is correct — 1 of 15,688**
non-seed pairs; the undirected matcher and the 5% seeds guess nothing, and **all four shuffled-seed
controls produce zero guesses** (`results/generated/graph-rejoin-2016-v1.md`). One match is not
ignition and recall rounds to zero, but it is a different statement from "none": the high-confidence
path is not inert and it separates from the shuffle arm.

What gates it is the neighbourhood, not the transaction count. Per-vertex persistence rises from 31%
to 38% as the view widens from one day to seven and saturates by day three
(`results/RESULTS-persistence-curve.md`): a wider window adds relationships without adding recurring
ones. `graph_shape` says the same about the structure — the contracted graph is disassortative
(−0.044, `results/artifacts/slice-channels-v1.json`), hubs attaching to leaves rather than the
positive sign of a social graph, and the sharper statistic is clustering: transitivity reads 0.0062
and 0.0001 against a configuration-model null of 0.6113 and 0.3976, two orders of magnitude fewer
triangles than the degree sequence alone would produce. The degree tail does *not* carry the
argument: the exponent is 2.86, inside the social 2–3 range, and leaves are 4.6–6.0%. A pseudonym's
view-A and view-B neighbours are different one-off counterparties, and a neighbourhood that does not
recur cannot be rejoined. The result is therefore **underpowered, not a robust falsification**; the
strong test — wide multi-epoch views over a multi-year span, seeded on high-degree entities — is a
data-scale requirement (§10).


### The faithful N-S propagation kernel on real chain: ~1% precision

Everything above is either an adaptation (`view_match.py`, `graph_deanon.py`) or a premise test. The
paper-faithful 2009 kernel — `decluster/baselines/narayanan_shmatikov.py`, direction-aware
degree-normalised neighbour votes, eccentricity gate, mandatory reverse match, iterated to
convergence — has one real-chain run measuring what the attack does on this graph.

Two adjacent 120-block 2016 windows (heights 391,992–392,111 and 392,112–392,231; 133,576 and 157,724
transactions), clusters straddling the boundary contracted to a separate pseudonym per view
(`results/RESULTS-ns-bitcoin.md`, `results/artifacts/ns-bitcoin-v1.json`):

| seed share | θ | declared | correct | precision | coverage |
|---:|---:|---:|---:|---:|---:|
| 5% | 0.5 | 248 | 2 | 0.81% | 0.081% |
| 5% | 1.5 | 246 | 1 | 0.41% | 0.041% |
| 10% | 0.5 | 450 | 3 | 0.67% | 0.128% |
| 10% | 1.5 | 448 | 2 | 0.45% | 0.086% |
| 25% | 0.5 | 779 | 10 | **1.28%** | **0.513%** |
| 25% | 1.5 | 774 | 9 | 1.16% | 0.462% |

**Precision 0.41%–1.28%, coverage 0.041%–0.513%.** The shuffled-seed control declares comparably
often and gets **0 correct in all six rows**, so the signal is real and it is tiny. Two further limits
are structural, not incidental. The independent-label path was tried first and found zero gradeable
seeds across both views, so every row above is *seed-assisted*: the seeds are sampled from the
withheld correspondence the run is graded against. And the export carries addresses only — no prevout
values, no script types — so the amount and fingerprint channels are absent by construction.

Set this beside the AUC 0.95 of §6. Those are not two readings of one thing. The 0.95 is a
pairwise link-prediction score under weak co-spend labels — evidence that the graph carries
same-owner structure, which is the *premise* the attack needs; the ~1% is the attack, run to
completion, on real chain, and told to name a specific counterpart. A pairwise premise at AUC 0.95
and an end-to-end attack at approximately 1% precision delimit the current result.

## 9. Limitations

- **Scope, not scale.** The fingerprint model is validated on mainnet data and structural
  de-anonymization is measured across five eras (§5/§6), both without an archival node; a whole-chain
  entity-reduction rate needs the full connected chain (§10). **And validated pairwise scores are not
  attack rates:** the paper-faithful N-S kernel, run end to end on real chain, lands at the precision
  §8 reports, so every AUC here reads as evidence that a channel carries signal, never as the rate at
  which a named counterpart is recovered. The stronger N-S form — structure linking what co-spend
  leaves separate — needs independent entity labels; the detectors and a co-spend-disjoint same-owner
  probe are built (`decluster/entities.py`, `graph_deanon.evaluate_entity`) and draw a sharp boundary
  on real slices: an entity in an economic graph with recurring peers re-links (SatoshiDice,
  AUC ≈0.72), a custodial hub-and-spoke or a mining pool does not (BitMEX, a null)
  (`results/RESULTS-entity-deanon.md`).
- **The intersection channel runs, and recovers nothing yet.** `monitor.py`/`intersect.py` implement
  the multi-transaction argument §1 leans on, wired into `cluster_refined` and exercised on a real
  co-spend. There one branch's boundary is entirely oracle truncation, so the empty intersection
  means the walk could not see, not that the origins differ — `evaluate` reports `truncated` and
  `blind` to keep the two apart. Re-seeded on four non-blind branches the intersection is genuinely
  empty *and* the engine refuses: three funders agree at +6.82 bits, a fourth disagrees, and the
  partition comes out 4/1 (`results/RESULTS-intersection.md`). The mechanism and its subordination to
  the engine are claimed; no entity recovered by it is. The candidate rule is also asymmetric: a
  symmetric large mix halts the walk, while a many-in/few-out consolidation passes as a candidate —
  where the common-input heuristic pulls hardest and the amount channel is silent.
- **Low-R is a base-rate signal.** A non-grinding wallet emits a 71-byte signature ~50% of the time;
  low-R is a per-cluster *consistency* tell, low severity, and the measured bits reflect that.
- **Policy-value over-clustering.** A match on a *policy* value (e.g. `locktime=height`) groups a
  *class* of wallets, not one; only rare values (`0x01`, `cake_group_c`) are strongly identifying.
  Per-axis specificity is modeled but not yet fully calibrated.
- **Independence assumption — quantified, not just conceded.** The engine sums per-axis bits assuming
  axis independence, and real intra-wallet correlations double-count: two axes are perfectly
  correlated in both classes, and four correlated groups sit at |φ| ≥ 0.6
  (`results/artifacts/fs-ablation-v1.json`). §5 measures the cost — magnitudes inflated ≈1.77×,
  rankings unharmed, discrimination in fact slightly better without the redundancy — so what is
  damaged is bit magnitudes and the refusal thresholds calibrated against them. The default scorer
  stays fixed for reproducibility of the committed figures; `decorrelated_scorer()` supplies the
  scale for reading magnitudes.
- **Label leakage in the attribution figure.** The same-owner label is a shared input address, and
  five axes are determined by that address outright. Removing them (`construction_only_scorer()`)
  costs roughly a fortieth of the headline AUC (§5): the label restates itself that much, and pure
  construction style carries the rest.
- **Same-software false positives.** Fingerprints separate only *different* wallet software: two
  owners sharing a wallet, timezone and fee policy emit matching fingerprints, and the amount channel
  does not fill the gap, since its round-ness refuse is gated on a fingerprint disagreement (§4) that
  is absent here. The control rests on **graph topology, scored as a Newcombe/FS rarity
  quasi-identifier** — Alice's counterparties differ from Bob's, and few distinguishing relationships
  suffice (§6). Rarity-thresholded so common hubs count for nothing (`−log₂(share)`, N-S's own
  `1/log|supp|`), the cluster-level term separates same-owner from different-owner cluster pairs and
  refuses a same-software payjoin end-to-end where fingerprints alone would collapse it
  (`cluster_topology_weight`/`topo_tau`, `results/RESULTS-topology.md`). The residual limit is
  inherent to the quasi-identifier: two *different* owners who both use one *rare* counterparty score
  as same-owner, because a shared rare quasi-identifier is legitimate same-owner evidence in the FS
  model.
- **Topology at chain scale, and a negative result.** Chain-scale seed-and-extend over the whole
  graph is future work for this channel (§10; the provenance channel's own seed-and-propagate is
  built and cache-bounded-evaluated, §8). A cluster's temporal activity schedule (hour-of-day
  histogram) was tested as a candidate quasi-identifier and is reported as a negative result: a naive
  split-half gives AUC 0.92, but a persistence split with matched negatives collapses it to
  **0.49 (chance)** (`results/RESULTS-temporal.md`).
- **A bounded structural measurement, not robust connectivity.** `provenance_route_accumulation` (§8)
  weights ancestral origins by link probability alone — subset-sum multiplicity does not enter,
  because the amount channel is refuse-only (§1) — so it measures no structural property of the
  graph. `disjoint_routes`, evaluated separately by `route-capacity-v1`, measures coin-disjoint
  routes and their minimum cut over transactions as vertices and amount-labelled coins as directed
  edges, the cut after pruning routes unable to carry the target coin, and a value-capacitated
  maximum flow (`results/generated/route-capacity-v1.md`) — bounded readings on one committed slice,
  not a term composed into provenance accumulation and not a chain-scale proof.
  Counting how many coins belonging to *other* users already share a user's deep features needs no
  cut at all, and its primitives are built (`ancestry.absorber_distribution`,
  `ancestry.provenance_link`, `intersect.shared_origins`); each way of *qualifying* that reading
  needs its own primitive, and two are missing. Qualifying by proximity needs mass resolved by path
  length: `absorber_distribution` marginalizes length away by construction and
  `collapsed_expected_steps` returns only a mean, so neither answers "how much mass arrives within ℓ
  hops", and the finite-horizon `H_ℓ = Q·H_{ℓ−1}` is not implemented. Flow capacity is implemented
  separately from the stochastic weights: `flow_capacity` gives each known coin its recorded value
  and computes the maximum the admitted graph delivers simultaneously — on the committed slice 8 of
  335 measured targets cannot receive their own value from the observed origins — which identifies no
  satoshi's actual route and supplies no user antecedent set, the input own-origin robustness needs.
  Cost is real and omitted: the conservative reading is one backward walk per candidate input, at
  **292 s for a single coinjoin** with `depth=5, max_nodes=20`, the unbounded walk unfinished under a
  25-minute cap (`results/RESULTS-path-count.md`). A per-candidate sweep at population scale is a
  compute question, not a bookkeeping one.

## 10. Future work

Every bit this paper reads as a link is, inverted, a bit a wallet must avoid emitting. The engine is
the measurement half of a construction-side cost function: it reads the path-counting provenance
anonymity set (§8) rather than a taint score, which fights the fungibility a coordination protocol
needs, and subset-sum density enters strictly as a cut. Its leak, topology and path-count terms are
wired (`cost.construction_cost`); what remains is their combination into one scalar — Liebig minimum
against weighted sum.

**The whole-chain rate.** A node streaming each block's spent prevouts, and the entity-reduction
rate over the full connected graph. This is integration with that stream rather than a different
method (the scaled engine lives in a separate `tx-indexer` crate; the prototype here carries the
method at case-study scale). The one-day change-identification validation (§7) scales the same way.

**Collections the accreted cache cannot supply.** A uniform deep-ancestry sample turns the
demonstrated sparsity→de-anonymization link into a chain-wide rate. Entity labels independent of the
co-spend heuristic replace the seed-assisted rows of the N-S kernel. Wide multi-epoch views, seeded
on high-degree entities, decide the cross-view result in either direction. The same collection
carries a user's own antecedent coins, which is what own-origin robustness needs and the bounded
route-capacity run does not have.

**Deep coinjoin mappings by sampling.** Counting `W(E)` does not make the §04 walk tractable — the
exponential is the number of distinct ancestor transactions, and per-transaction `W` does not lift
it. A valid mapping is a balanced input/output partition, so local moves preserving balance give the
pairwise marginal from how often two coins share a block, validated below the enumeration guard
against the exact marginal (`pairwise_input_output_prob`); mixing time, not correctness, is the risk.
In a dense round that marginal comes out near-uniform, which puts amount privacy in the same bits as
every other channel here.

**Cluster-level topology at chain scale**, with community detection and embeddings beyond the
delivered rarity-threshold false-positive control (§9).

**The amount channel beyond the delivered de-mix** (§1/§6), inside the refuse-only boundary: the
conservation bound and the provenance-overlap ranking are cuts worth taking, and a channel that may
only refuse cannot be handed an attributing argument (§1).

**Partition-level Bayesian entity resolution** — MCMC over the linkage partition, of which the
delivered pair-level comparison (§5) is the tractable counterpart. Supervised record-linkage
classifiers stay out: they need the labelled same-owner pairs this design withholds for validation.

## 11. Conclusion

The graph is primary and the engine is what makes its channels one decision. Refusing a co-spend
before making it is enough to keep two owners apart when the clusterer owns every merge it made;
cutting a partition it inherited is the other direction, held to a stricter standard because a cut
made on absent evidence invents privacy rather than measuring it.

What the measurements establish, at the level they were taken. Construction fingerprints separate
same-owner coins and the engine declines co-spends the merge-only heuristic takes, on committed
transactions (§4, `results/generated/fused-engine-v1.md`). Cluster-level topology and
provenance-disjointness move those refusals in opposite directions, which is the case for fusing
them rather than reading them in turn. Graph structure predicts same-owner beyond co-spend and
survives a degree-matched control, so the signal is not an artefact of degree
(`results/RESULTS-graph-deanon.md`). Sparse feature vectors support record linkage where the vectors
are sparse, and the sparse-versus-dense gap is the result (`results/generated/reid-v1.md`).

What they do not establish, stated as plainly. Fingerprints are not a sparse quasi-identifier: on the
committed window, exact-vector classes of size one are a rounding error, so the fingerprint buckets
and does not single out (`results/generated/fingerprint-sparsity-v1.md`). Seeded propagation across
two pseudonym views does not ignite at the view widths measured, and neighbourhood persistence — not
the matcher — is the binding constraint (`results/generated/graph-rejoin-2016-v1.md`,
`results/RESULTS-persistence-curve.md`). The framework's own positive properties, robust connectivity
and own-origin robustness, are stated over counterfactual disjoint paths. The bounded route-capacity
experiment measures coin-disjoint cuts, value-pruned cuts and maximum flow on one committed
slice; it finds small cuts as well as high-redundancy cases
(`results/generated/route-capacity-v1.md`). That is evidence about the structural object, not proof
of either property: the sample ends mostly at missing parents, and own-origin still lacks a run with
a user's independently specified antecedent coins. The path-count result remains a different object
(§9, `results/RESULTS-path-count.md`).

Every measurement above resolves to a canonical artifact. The measurements that do not are listed in
`tests/test_paper_numbers.py` with the reason each is unavailable, and the list is checked in both
directions, so a number that gains an artifact has to leave it. `results/REPRODUCIBILITY.md` states
which evidence state every result document is filed under, and which are not yet filed.

## 12. Related work

- <sub>**Yuval Kogman (nothingmuch), [*Anonymity Sets on the Transaction Graph*](https://github.com/nothingmuch/tx-graph-anonymity-sets)** supplies the entropic anonymity-set, sub-transaction, absorber and graph-quasi-identifier framework used in §2/§6/§9. Its walk weights transitions by coin value, and `decluster/ancestry.py` now follows that nominal-value rule by default (`value_flow_link_oracle`); the row-normalized subset-sum oracle remains an explicit compatibility path for historical results, and `value_weighted` is a distinct hybrid rather than the framework's flow rule. This paper treats entropy as attacker weight-of-evidence rather than a privacy score, and `path_count.py` extends the framework's counterfactual-path notion using link probability alone. The framework's proposed relation between output entropy and excluded graph edges is not transferred to absorber entropy here, because the required equivalence is not established.</sub>
- <sub>**Yuval Kogman (nothingmuch), [*Collaborative Transaction Privacy*](https://gist.github.com/nothingmuch/d84ba390d89b5b08897af2d95009c2a1)**: the failure-mode taxonomy this paper calibrates against — CIOH violation by collaborative transactions, the NS1R / NSNR / net-settlement progression, and the robust-connectivity / own-origin / deep-feature program (§2/§9/§10). It shows how net-settlement with cycles and deliberately underdetermined values can *silence* amount analysis — on our reading the most defeatable layer — which is why our *primary* amount signal is scoped to the decidable regime (§2), and the provenance / deep-feature channel it develops is exactly the one §7 sets aside and §8 develops.</sub>
- <sub>**Armin Sabouri, [*How Fingerprints Damage PayJoin Privacy*](https://github.com/payjoin/research-docs/blob/main/fingerprints/payjoin.md)** (payjoin/research-docs): the applied payjoin case for this program — it walks real payjoin transactions through the same construction tells this paper measures (low-R, SIGHASH serialization, nSequence, value-conservation/round-number, input ordering/locktime, coin-selection residuals), across intra- and inter-transaction layers, and concludes that "PayJoin's privacy extends only as far as the uniformity of the participating wallets." That is precisely the collaborative-transaction failure our engine quantifies: the merge is refused by the amount structure and again by the fingerprints (§2/§6), and the same per-axis bits, inverted, define the construction-side uniformity a payjoin must reach (§10).</sub>
- <sub>**Cindy (bc1cindy)**, [*Tracking: chain-observable transaction-level fingerprinting*](https://github.com/payjoin/rust-payjoin/issues/1597) (payjoin/rust-payjoin #1597): the venue for this program and its review discussion — the tracking issue that scopes the fingerprint checklist (§7) this paper measures against.</sub>
- <sub>Maurer, Neudecker & Florian, *Anonymous CoinJoin Transactions with Arbitrary Values* (2017) define the sub-transaction model used by the amount-based repartition in §2/§6. Their §4.1 admissibility is binary: sub-transaction inputs and outputs cancel exactly, and admissible mappings are equiprobable. Graded plausibility is outside that model; Boltzmann accommodates fees, while §1 evaluates the entropy of a distribution over partitions.</sub>
- <sub>LaurentMT, *Boltzmann* (OXT, 2015): operationalized the sub-transaction model as transaction entropy `E = log₂N` over the N plausible input→output interpretations. §1 refines this: what bounds anonymity is the *entropy of the distribution* over partitions, not the count `log₂N`.</sub>
- <sub>Fellegi & Sunter, *A Theory for Record Linkage* (JASA 64(328):1183–1210, 1969; [doi:10.1080/01621459.1969.10501049](https://doi.org/10.1080/01621459.1969.10501049)) provide the fitted per-field `m`/`u` model implemented in `decluster/fellegi_sunter.py` and used by the temporal, ablation and Bayesian evaluations (§5). The headline pair scorer is different: its `−log₂p` value-specific frequency weight follows Newcombe (1959/1962). The topology term applies the same `−log₂(share)` scale to counterparty overlap (§9).</sub>
- <sub>Winkler, *Overview of Record Linkage and Current Research Directions* (2005), building on his EM weight-computation work (1988), and Splink (UK Ministry of Justice, [moj-analytical-services/splink](https://github.com/moj-analytical-services/splink)): the unsupervised EM that estimates the FS model's per-field agreement probability `m` without same-owner labels, and its open-source reference implementation. Our per-axis `m` fit (§5, `results/RESULTS-em-m.md`) is Splink-style — `u` fixed at the measured collision, the reuse label withheld for validation — and the Bayesian variant (`results/RESULTS-bayes-vs-fs.md`) is its posterior generalization.</sub>
- <sub>Narayanan & Shmatikov, *Robust De-anonymization of Large Sparse Datasets* (IEEE S&P 2008; [arXiv:cs/0610105](https://arxiv.org/abs/cs/0610105)) and *De-anonymizing Social Networks* (IEEE S&P 2009; [arXiv:0903.3276](https://arxiv.org/abs/0903.3276)): structure alone re-identifies nodes. Their high-dimensional sparsity result — rare structure re-identifies, distinctive attributes rarity-weighted `wt(i) = 1/log|supp(i)|` — is the *premise* our topology term operationalizes, scored in the Newcombe/FS frequency weight `−log₂(share)` (§4/§9). §6 tests that premise on a real connected Bitcoin slice, and §8 runs the 2009 propagation kernel itself (`decluster/baselines/narayanan_shmatikov.py`) on two real Bitcoin views. Independent seed discovery, chain-scale views and richer features remain future work (§10).</sub>
- <sub>**Goldfeder, Kalodner, Reisman & Narayanan**, *When the Cookie Meets the Blockchain: Privacy Risks of Web Payments via Cryptocurrencies* (PoPETs 2018(4):179–199; [arXiv:1708.04748](https://arxiv.org/abs/1708.04748)): the cross-transaction cluster intersection attack — for each co-held mixed coin, Algorithm 2 collects wallet clusters reachable by join-only backward paths of at most `r` rounds, intersects those sets, and identifies only a unique survivor. That kernel is implemented separately in `decluster/baselines/candidate_set_intersection.py`. §9's `decluster/intersect.py` is an adaptation: `monitor.py` supplies a co-spend occasion, but candidate origins come from a probabilistic walk not restricted to joins, and its narrowing is handed to `cluster_refined`; its real-chain result is not a reproduction of Goldfeder's 2015–2017 JoinMarket experiment.</sub>
- <sub>Kelen & Seres, *Towards Measuring the Traceability of Cryptocurrencies* ([arXiv:2211.04259](https://arxiv.org/abs/2211.04259); **v2, 2024-06-01**) provide the flow-based traceability and absorbing-chain formalism used by the provenance walk. `decluster/baselines/kelen_seres_graphs.py` implements their ledger transforms, and `ancestry.kelen_seres_expected_steps` converts the collapsed coin-to-parent transition to their uncollapsed UTXO-graph step count; it abstains on truncated or depth-capped walks. Their §2.2/§2.4 stationary transform needs no opening balances. Only the local temporal split transform needs them because its per-receipt snapshots hold a balance. The source catalogue records this implementation with `obligation: baseline`.</sub>
- <sub>Möser & Narayanan, *Resurrecting Address Clustering in Bitcoin* (FC 2023; [arXiv:2107.05749](https://arxiv.org/abs/2107.05749)): the non-interactive change-labeling method — the change of a 2-output transaction is revealed when its address is later co-spent with the inputs' cluster — and the "consistent fingerprint" change heuristics (their Table 1, incl. ordered ins/outs). We implement their labeling, §2.2 filters and per-axis validation (§7). This paper does not report the unpreserved large-slice evaluation.</sub>
- <sub>**Kappos et al.**, *How to Peel a Million: Validating and Expanding Bitcoin Clusters* (USENIX Security 2022; [paper](https://www.usenix.org/system/files/sec22-kappos.pdf)): change identification by whether an output's onward-spend belongs to the same peel chain — the cluster-feature `findNext` (TFC/AFC/changeC). We implement `findNext` (§7, `change_cluster.py`), but note it cannot be *validated against* an M&N co-spend label: the two share the co-spend-cluster signal, so `findNext` scores that label by construction (§7 circularity caveat). Our label-disjoint validation is the per-axis fingerprint test instead.</sub>
- <sub>**Wang et al.**, *Exploring Unconfirmed Transactions for Effective Bitcoin Address Clustering*: the closest model — a clustering-effectiveness paper reporting entity reduction by mining unconfirmed/mempool transactions (co-spend on unconfirmed txs +2.3%, three novel mempool heuristics +9.8%, against whole-chain entity counts). We follow the same anonymity-collapse framing but at case-study scale (the entropy metric on the merged-transaction graph, §6); a whole-chain measurement needs the whole connected chain, not an archival node (§10).</sub>
- <sub>Ron & Shamir, *Quantitative Analysis of the Full Bitcoin Transaction Graph* (FC 2013): the first quantitative graph analysis of Bitcoin and the tracking of specific large entities by their on-chain patterns — the lineage of the special-case de-anonymization this paper's known-entity catalog and optimal-change labels extend (`catalog/known-entities.md`, §7). The special cases are the next lever (§10).</sub>
- <sub>Dingledine & Mathewson, *Anonymity Loves Company*: uniformity is a network-effect property — a wallet that de-biases one axis but stands out on another gains nothing. This grounds our recommendation to randomize *between legitimate behaviors* (same distribution), not merely to fix single fingerprints.</sub>
- <sub>Syverson, *Why I'm Not an Entropist*: caution on the entropy framing; we report bits as weight-of-evidence for pairwise linkage, not as a single anonymity scalar.</sub>
