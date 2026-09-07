# Partition posterior by split-merge MCMC (M3) — calibration, ablation, coarsening hierarchy

**Claim:** `decluster.split_merge` (Jain-Neal restricted-Gibbs split-merge over co-spend
super-nodes) samples the joint posterior over partitions `P(z | E)` from
`decluster.partition_model`'s hybrid log-posterior (Dirichlet-multinomial categorical channel +
N-S provenance pseudo-likelihood + microclustering prior). This is the coarsest-to-finest
hierarchy's top object: `fs_bayes` gives the non-transitive pairwise marginal, this posterior
gives the joint object, and its own per-target marginal is what `anonymity_set.py` (M1) would
approximate by diffusion — see "M1 status" below for why that comparison is not available yet.

**Method:** a bounded, offline `.cache` slice built by `examples.partition_posterior.build_slice`,
which reuses `examples.ns_propagation_cache_run`'s two-independent-signal construction (co-spend
groups become the atomic must-link super-nodes; address-reuse groups give same-owner labels
*across* super-nodes, so the label is not circular with the sampler's evidence). The sampler runs
with the microclustering prior (default), categorical Dirichlet-multinomial axes from
`fingerprint_validate.LibraryScorer`, and an N-S provenance link factor scaled by `beta`. All
numbers below are from one real run of `examples.partition_posterior`'s harness functions
(`channel_ablation`, `beta_sweep`, `shuffle_null`, `fs_bayes_pair_marginal`) against this
checkout's real `.cache/` — no fabricated or hand-picked figures. Full run log:
`total_time_s = 490.1`, `n_iter`/`burn` as coded in `channel_ablation`/`beta_sweep`
(2000/600, two chains, and 1500/500, one chain, respectively).

## The slice

| quantity | value |
|---|---:|
| super-nodes | 15 |
| same-owner label pairs (address-reuse, cross-super-node) | 21 |
| — positive (same owner) | 2 |
| — negative (different owner) | 19 |
| slice build time | 67.6s |

Small and heavily class-imbalanced (2 positive pairs out of 21 labeled). **Illustrative, not
conclusive** — see the limits below. The label pairs come from address-reuse groups that
survived the `max_supernodes` truncation (which prioritizes labeled singles first, so this is
already the best label coverage obtainable at this slice size from the current cache).

## Convergence

`rhat_K` (Gelman-Rubin R-hat on the number-of-clusters series, 2 chains) for the full-evidence
run: **1.00015** — converged (≪ 1.05 target). Same for the `drop_provenance` ablation run
(identical evidence, see below). The `drop_categorical` run: **1.00033** — also converged.

## Per-channel marginal bits (`channel_ablation`, channels = categorical, provenance)

| run | posterior entropy (bits) | K posterior (mode) | rhat_K |
|---|---:|---|---:|
| full (`__all__`) | **0.8614** | K=5: 98.4% | 1.00015 |
| drop_categorical | **10.4512** | spread K=2..9, mode K=5: 39.6% | 1.00033 |
| drop_provenance | **0.8614** | K=5: 98.4% | 1.00015 |

**Marginal bits per channel** (entropy increase from dropping the channel — how much
uncertainty-reduction that channel is responsible for):

| channel | marginal bits (drop-entropy − full-entropy) |
|---|---:|
| categorical (fingerprint axes) | **9.590 bits** |
| provenance (N-S link factor, beta=1.0, depth=1, bounded slice) | **0.000 bits** |

**Reading:** on this slice, the categorical fingerprint channel carries essentially all of
the entropy-reducing evidence — dropping it collapses the posterior from near-certainty about the
partition (0.86 bits, effectively locked at K=5) to a nearly uninformative spread over K=2..9
(10.45 bits). The provenance channel contributed zero marginal bits here: `drop_provenance`
is bit-for-bit identical to the full run. This is a real, not a rounding-noise, null result for
this slice — see the limits for why (depth=1 + the bounded-dimension link oracle sharply limits
how much real provenance signal reaches the evidence at this scale).

## Beta sweep (`beta_sweep`, betas = 0.0, 0.5, 1.0, 2.0)

| beta | ECE |
|---:|---:|
| 0.0 | 0.23857 |
| 0.5 | 0.23857 |
| 1.0 | 0.23857 |
| 2.0 | 0.23857 |

**Selected beta = 0.0** (min-ECE; all four are numerically tied). This is a direct consequence of
the ablation result above: since the provenance channel contributes ~0 marginal bits on this
slice, scaling it by `beta` has no measurable effect on the posterior, so ECE does not move with
`beta`. Not evidence that beta calibration is unnecessary in general — it is evidence that this
particular bounded slice does not exercise the provenance channel enough to calibrate it.

Headline run (full evidence, selected beta=0.0, 2 chains, 2000/600): ECE = **0.23884**
(consistent with the sweep's single-chain 1500/500 estimate at beta=0.0, 0.23857 — small MC
difference from the different chain/iteration count, not a discrepancy).

## Coarsening hierarchy

| level | object | ECE (over the 21 labeled pairs) | notes |
|---|---|---:|---|
| pairwise (non-transitive) | `fs_bayes` Gibbs pair-marginal | **0.8844** | 105 pairs scored, mean P(match)=0.830, min=4.1e-05, max=0.999 — high-confidence pairwise scores that are **badly miscalibrated** against the same-owner labels |
| per-target marginal | M1 (`anonymity_set.py`) | **N/A** | M1 now exists in this repo (see "M1 status" below) but was not run as part of this ECE comparison — it reports a min-entropy lower bound, not a calibratable match probability, so it is not directly ECE-comparable to the rows above without its own methodology |
| joint partition posterior | this work (`split_merge` + `partition_posterior`) | **0.239** | transitivity + the microclustering prior sharply improve calibration over the raw pairwise marginal |

**This is the headline result of this task.** The joint partition posterior is **~3.7x better
calibrated** (ECE 0.239 vs 0.884) than the non-transitive pairwise `fs_bayes` marginal on the
identical slice and identical labels. `fs_bayes`'s pairwise scores are confident (mean P(match)
0.83 across 105 pairs) but that confidence does not track the same-owner labels well in isolation
— exactly the cluster-collapse failure mode the design spec's coarsening-hierarchy argument
predicts for a non-transitive pairwise object. Promoting the same evidence into a proper joint
posterior over partitions, with a microclustering prior, recovers most of the calibration.

### M1 status

**Stale-note correction:** an earlier version of this file reported that `decluster/anonymity_set.py`
"does not exist in this repository." That has since been superseded — M1 was added on a later
branch (`anonymity-set-s04-fusion`) and now exists: `anonymity_set.py` provides both the post-solve
`reweight`/`decay`/`provenance_anonymity` (the weaker baseline) and the §04-faithful, link-level
`provenance_anonymity_fused` (subjective matrix combined with the graph-derived one BEFORE the
absorbing solve — see `RESULTS-anonymity-set.md`'s "§04-faithful fusion" section for the real
graph-only-vs-fused min-entropy numbers on this cache's same-owner pairs).

The M1 row of the coarsening-hierarchy table above is still reported as **N/A** — not because the
module is missing, but because M1 reports a per-target min-entropy lower bound (a weight-of-evidence
floor), not the kind of per-pair match-probability this table's ECE metric calibrates against
same-owner labels. Computing an ECE-comparable number for M1 would need its own calibration
methodology (turning an entropy bound into a probability estimate) that neither this task nor
`RESULTS-anonymity-set.md` has done. This note corrects only the stale existence claim; no computed
number in this file has changed.

## Shuffle-null sanity check

Independent random permutation of the categorical axes and of the provenance link dict (two
separate permutations, so neither channel stays aligned to real super-node identity), rerun with
the same sampler settings (single chain, 1500/500):

| run | posterior entropy (bits) |
|---|---:|
| real evidence | 0.7362 |
| shuffled evidence (null) | 0.7622 |

**Reading: the separation is real but weak (0.736 vs 0.762, ~0.03 bits) on this tiny
15-super-node slice** — not the sharp "collapses to the prior" separation the design spec
anticipates for a slice with more signal. Two contributing factors, both consistent with the rest
of this run: (1) the categorical channel — which the ablation above shows carries essentially all
the real signal — still has *some* residual structure once permuted (a 15-item permutation can by
chance leave a few super-nodes closely matched, especially with only 15 elements to shuffle), and
(2) the provenance channel, already shown to contribute 0 marginal bits, contributes nothing to
sharpen this separation either. This shuffle-null is not strong evidence of a well-separated
signal at this scale; it is weak-but-directionally-correct evidence, reported as such.

## Limits

1. **The N-S provenance channel is a pseudo-likelihood, not a probability.** `beta * link(i,j)`
   scales a rarity-weighted overlap score into the log-posterior; it is weight-of-evidence, a
   conservative lower bound, never a calibrated probability on its own — consistent with the rest
   of the repo's disclaimer discipline (`ancestry.py`, `partition_model.py`).
2. **Results are on a bounded slice only.** 15 super-nodes, 21 same-owner label pairs (only 2
   positive), built from a single-hop (`depth=1`) ancestry walk over this checkout's `.cache/`. Not
   a chain-scale claim, and the extreme class imbalance (2 positive pairs) makes the ECE numbers
   noisy — a different slice could plausibly shift them.
3. **The bounded link oracle changes what provenance evidence is even available.** A real cached
   tx in this slice is CoinJoin-scale (vin=277, vout=325); the exact subset-sum solver's own
   documented range is 54ms-69s per call (see `ancestry.dss_link_oracle`'s docstring), and its
   `budget_ms` argument is advisory, not a hard preemptive cap. To keep this harness offline and
   tractable, `examples.partition_posterior._bounded_link_oracle` refuses (the same
   oracle-None truncation semantics `build_extended_graph` already uses) on any tx with more than
   24 inputs or outputs, and the walk depth is capped at 1 hop. This is very likely why the
   provenance channel measured **zero** marginal bits above: a depth-1, dimension-bounded walk
   sees far less of the real provenance graph than an unbounded one would. The zero-bits result
   should be read as "this channel measured no signal under this harness's tractability bound," not
   "this channel carries no signal in general."
4. **Provenance link weighting is provisional.** `build_extended_graph`'s edges are
   link-probability-only (row-stochastic on `L`), not satoshi-flow-weighted — satoshi-flow
   weighting of the walk is deferred to Task 9 per the design spec's phase 4. That change could
   materially alter the provenance channel's contribution measured here.
5. **The `fs_bayes` pairwise comparison uses the same 21 labeled pairs, but `mean_p_match=0.83`
   is over all 105 pairs** (the full pairwise set), not restricted to the labeled subset — reported
   separately in the coarsening-hierarchy table's notes column to avoid conflating the two.

Same-owner labels throughout — the address-reuse heuristic used for labels
here is a standard, near-certain but not infallible same-owner signal (a collaborative or shared
tx would produce a false merge), independent of the co-spend signal the sampler's super-nodes are
built from.

**Reproduce:** `.venv/bin/python -c "from examples.partition_posterior import *; ..."` calling
`build_slice(cap_total=50, depth=1, max_supernodes=15)` then `channel_ablation`, `beta_sweep`,
`shuffle_null`, and `fs_bayes_pair_marginal` as this run did (~8 minutes total, offline, no
network). Deterministic under `seed=0`.

## Reproducibility / provenance

State 2 in `results/REPRODUCIBILITY.md`: the mechanism is pinned; the reported numbers come from a data-run over the bounded `.cache` slice `examples.partition_posterior.build_slice` builds, which is not committed, and are not asserted.
