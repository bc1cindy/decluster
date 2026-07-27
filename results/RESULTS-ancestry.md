# Provenance-entropy channel on real data — the absorber-model rung

The `ancestry_entropy` engine (`decluster/ancestry.py`) measures the **provenance / deep-feature
channel** that the framework (`tx-graph-anonymity-sets`, the absorber / random-walk model) centres:
a backward walk over the transaction graph, edge-weighted by the exact subset-sum link matrix
(`dss.pairwise_link_prob`), solved as an absorbing Markov chain — the coin's absorption distribution
over its ancestral boundary is the harmonic measure of the walk. Its Shannon / min-entropy is a
**lower bound** on the intrinsic graph entropy of the payment's provenance under no auxiliary
information (never a privacy score; the conservative, defender-side read is min-entropy).

Run in `./.venv` (the native `dss` module is built there), `fetch_tx` resolving ancestry over
mempool.space.

## Result — provenance is a near-deterministic quasi-identifier

**Anchor (`931d6627`, the §6 merged Cake+sender tx), vout 0:**

| depth | Shannon | min-entropy | boundary coins |
|---|---:|---:|---:|
| 3 | 1.73 | 1.00 | 4 |
| 6 | 1.46 | 1.00 | 3 |

Its origin is essentially a coin-flip between ~2 ancestral coins — a low-provenance coin, consistent
with a small decidable-amount transaction. (Deeper reach *lowers* the bound: the walk resolves more
mass onto fewer boundary coins.)

**Spectrum on 8 ordinary sampled coins (1–3 in/out), depth 4:**

- Shannon **median ≈ 0.00 bits**, range **[0.00, 2.94]**; min-entropy median 0.00.
- Most coins (boundary = 1) resolve to a **single** ancestral origin — provenance fully determined,
  zero ambiguity.
- The high end (2.94 bits over a **30-coin** boundary) is a coin that passed through a fan-out — the
  only regime with meaningful provenance ambiguity.

## Reading

This is exactly the framework's thesis measured on-chain: "**every coin is sparsely represented**" in
the exponential quasi-identifier space of ancestry — for typical coins the provenance lower bound is
~0 bits, i.e. the origin is (near-)determined, so ancestry is a **strong** identifier. Only coins
routed through genuine fan-out/mixing accumulate provenance entropy. Because every figure is a
conservative lower bound (truncation on an oracle-`None`, and the depth cutoff, can only *understate*
ambiguity), the true identifiability is at least this strong.

## Deep-feature matching — provenance as a linking quasi-identifier

The entropy above is per-coin; the *matching* attack scores **pairs**. `ancestry_signature` exposes a
coin's provenance vector and `provenance_link` scores the Narayanan–Shmatikov overlap of two vectors —
shared ancestral mass, optionally rarity-weighted (`wt = 1/log2(support)`, so a shared *rare* ancestor
is strong same-origin evidence and a shared hub coinbase is weak). Mechanism validated in
`tests/test_provenance_link.py`.

On the **WP4 merged anchor** (`931d6627`, which fuses a Cake-receiver lineage and a distinct-sender
lineage), the pairwise link matrix (depth 4):

| | cake_in | sender_in |
|---|---:|---:|
| **cake_in** | 1.000 | **0.000** |
| **sender_in** | 0.000 | 1.000 |

The two merged parties have **disjoint provenance** (link 0.000) — a *third* independent channel, after
the fingerprints (§6, −3.1 bits) and the amounts (§6, round re-partition), that separates the owners
the common-input merge tried to combine. (Same-tx sibling outputs `merged_o0/o1` link at 1.0, as
expected — they share the full input ancestry. Cross-*generation* terms are not comparable here: two
coins at different depths reach different absorber boundaries, so signatures must be scored at aligned
depth or against a fixed ancestral cut — a limitation of this per-target-depth demo.)

## Graph-scale matching — a weak but directionally-correct first pass

Beyond the case study, we scored the matching across many coins: same-owner label = a reused receiving
address (86 coins signed at depth 3 over the witness cache, `ancestry_signature` via network fetch,
global rarity table). Same-owner coin pairs vs random:

| | value |
|---|---:|
| same-owner pair provenance overlap (mean) | **0.025** |
| random pair overlap (mean) | **0.000** |
| AUC | **0.52** |

The **sign is right** — random pairs share *zero* provenance, same-owner pairs share a little — but the
AUC is near chance because at depth 3 on a *fragmented* sample most same-owner pairs also reach no
shared ancestor.

We then tried the obvious fix — a **contiguous value-bearing slice** (2019, blocks 581000–581025,
64,744 txs; in-memory fetch with an out-of-slice boundary stub) at depth 5. It is *worse*, and the
reason is the load-bearing finding: every signature collapses to a **single** boundary atom
(mean support = 1.0), so pos and neg both ≈0 and AUC = 0.50. A tractable-width slice (~25 blocks ≈ 4
hours) **cannot contain multi-hop ancestry** — a coin's parents are almost always older than the
window, so the first backward hop already exits the slice and truncates. Keeping depth-5 ancestry
in-slice would need a slice spanning the ancestry timespan (weeks of blocks), i.e. essentially the
whole connected graph.

**Conclusion — this is a data-scale requirement, not a missing method.** Provenance matching is an
intrinsically whole-graph attack: unlike direct-counterparty structure (recoverable in a few contiguous
blocks, §6), shared *ancestry* lives arbitrarily far back, so a strong graph-scale AUC needs the full
connected chain over a long window — the same requirement as the whole-chain entity-reduction rate
(§9). The network approach reaches real ancestry (nonzero same-owner overlap) but is depth- and
sample-limited by rate-limited fetching. The method is validated (mechanism + WP4 case study); the
strong graph-scale number is gated on whole-graph provenance data (a Utreexo/Floresta stream, §9), not
on new method.

## Boundary — what this rung is and is not

Built and measured: the absorber-model provenance **entropy** (per-coin ambiguity lower bound), the
pairwise **matching** (`provenance_link`, mechanism-tested; WP4 lineage separation at 0.000), and a
first **graph-scale** pass (weak/directional, AUC 0.52 — depth+connectivity bound). The provisional
edge weighting is link-probability-only (satoshi-flow value-weighting deferred;
`ancestry.build_extended_graph`).

Reproduce: `./.venv/bin/python -c "from decluster.ancestry import ancestry_entropy; from decluster
import fetch_tx; print(ancestry_entropy(('931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4',0), depth=6, fetch=fetch_tx))"`.
