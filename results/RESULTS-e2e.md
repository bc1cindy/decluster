# End-to-end pipeline validation — Tier-1 (offline, asserted) + Tier-2 (live)

`examples/e2e.py` composes the tested pieces of the pipeline into one run: `cluster.cluster_refined`
(Layer 4) → `anonymity_set.cluster_of_from_tx_groups` (the cluster source — bridges `cluster_refined`'s
txid groups to the address→owner map the §04 source needs) → `report.report` (the §04
fused readout, `cluster_of`-fed) → the M3 exact-Bayesian partition posterior (`partition_model` +
`split_merge`, sampler vs exact enumeration). No new science — every term is an existing, separately
tested function; this module only wires them together and asserts the plumbing invariants hold
end to end, on a real (not synthetic-only) slice.

Two tiers:

- **Tier-1 (`run_offline`)** — deterministic, offline/`.cache`-only. Asserted by `tests/test_e2e.py`,
  part of the regular suite.
- **Tier-2 (`run_live`)** — the same pipeline sourced from a live-fetched slice (mempool.space) with
  the real, rebuilt `dss` behind a hard-bounded subprocess oracle. Not part of the asserted suite
  (network, non-deterministic); run via
  `.venv/bin/python -m examples.e2e --live [max_targets] [cap_total] [wall_ms] [depth]`.

## Tier-1 — offline, asserted (all green)

`tests/test_e2e.py`:

| test | slice | result |
|---|---|---|
| `test_e2e_offline_pipeline_holds_invariants` | tiny hand-built fixture (t1/t2/t3, address reuse + a real cospend-merge edge) — fully deterministic, no network, no `.cache` | **PASS** |
| `test_e2e_real_cache_slice_holds_invariants_nontrivially` | a bounded real `.cache/` slice (`ns_propagation_cache_run.build_sample`, `cap_total=30`), still offline (cache-only fetch) | **PASS** (skipped only if `.cache/` has &lt; 50 cached txs; it does not here) |

```
$ .venv/bin/pytest tests/test_e2e.py -v
tests/test_e2e.py::test_e2e_offline_pipeline_holds_invariants PASSED
tests/test_e2e.py::test_e2e_real_cache_slice_holds_invariants_nontrivially PASSED
2 passed in 12.19s
```

Both assert the same three invariants, on a synthetic and on a real-cache slice respectively:

1. **Fusion is conservative** — `fused_min_entropy <= min_entropy + 1e-9` for every report target
   (subjective evidence only narrows the anonymity set, never widens it — by construction in
   `report.report`).
2. **M3 is non-trivial and exact-matched** — the co-spend super-node slice has `>= 2` super-nodes
   (not the degenerate single-partition case), and the split-merge sampler's stationary distribution
   matches exact enumeration to within `< 0.05` worst-partition-probability gap.
3. **cluster_refined ran for real** — `>= 2` clustered nodes, `>= 1` cluster, and at least one group
   merges more than one node (not every node its own singleton).

Full suite: `.venv/bin/pytest -q` → **454 passed** (Tier-2's live-only imports are deferred inside
`run_live`'s function body, so the offline import path and the rest of the suite never touch the
network — see the docstring in `examples/e2e.py`).

## Tier-2 — live pipeline (`run_live`)

`run_live(max_targets, cap_total, wall_ms, depth, seed)` in `examples/e2e.py` runs the
identical composition against a real slice:

- **Sourcing.** Candidate txids from `examples.anonymity_set_scale.seed_targets()` (real multi-input
  txids drawn from local tx history — reusing that module's seed/slice approach, not a new one); tx
  dicts and `cluster_refined`'s fetch dependency both bind to the real `decluster.fetch.fetch_tx`
  (mempool.space, on-disk cached to `.cache/`). The seed targets here turn out to be
  payment+partial-mix transactions (e.g. 9-in / 17-out with one denomination repeated ~9× beside
  a large payment output), not fully-dense equal-value coinjoins.
- **Bounded oracle.** The link oracle is `examples.anonymity_set.hard_bounded_link_oracle` — the dss
  subset-sum call run in a throwaway subprocess and killed on a wall-clock deadline (`wall_ms`), so a
  dense/coinjoin ancestor truncates the walk (`None`, the same oracle-refusal boundary `ancestry`
  already handles) instead of hanging the run. Two properties of this oracle matter for the numbers
  below and were both verified during this run:
  - **The exact subset-sum path needs adequate wall time.** A payment+partial-mix tx of the shape
    above resolves to a real (non-uniform) link matrix in **~2.3 s** of dss compute; the historical
    `wall_ms=1500` default killed it at ~1.8 s → `None` → the target collapsed to a point mass
    (`n_absorbers=1`). Raising `wall_ms` to 6000 lets these resolve. (The dss radix fast path is a
    separate, O(n) short-circuit that returns a *uniform* matrix in ~0 s — but only for
    *fully*-dense coinjoins with ≥2 denominations each repeated ≥3× over ≥half the outputs; the seed
    targets here do not meet that structural test, so they take the exact path, not radix.)
  - **The subprocess entry must be `__main__`-guarded.** `hard_bounded_link_oracle` spawns worker
    processes; under macOS `spawn`, an unguarded caller re-imports its entry module in each worker and
    every oracle call fails-closed to `None` (silent whole-run truncation). `examples/e2e.py`'s
    `--live` entry is guarded; any standalone driver of `run_live` must be too.
- **Bounds.** `cap_total` caps the slice used for both `cluster_refined` and the M3 super-nodes;
  `max_targets` caps how many of that slice's txs get a full `report()` walk (the wall-clock cost
  driver); `depth` caps the ancestry walk (with a ~9× coinjoin fan-out, `depth=2` keeps a full sweep
  to minutes under the bounded oracle).
- Collects, beyond `run_offline`'s keys: `n_targets_attempted` / `n_targets_resolved` (the
  strict resolution count — targets whose graph-only walk finished with zero oracle-refusal
  truncations), and `m3_coassignment_agreement` (fraction of M3 super-node pairs where the split-merge
  sampler's posterior P(same partition) `> 0.5` agrees with whether `cluster_refined` placed their
  representative addresses in the same cluster — a cross-check between the exact-Bayesian partition
  posterior and the production clustering engine, not an identity test: they use different evidence,
  so disagreement is informative, not necessarily a bug).

### Full live run — real numbers

`.venv/bin/python -m examples.e2e --live 6 120 6000 2` (`max_targets=6`, `cap_total=120`,
`wall_ms=6000`, `depth=2`) ran the whole composition end to end against the live API — candidate
discovery, live fetch + on-disk caching, `cluster_refined` over the 120-node live slice, the fused
`report()` walk per target, and the M3 sampler-vs-enumeration + co-assignment agreement — without
error. Real output (one run; live data + timing-bounded oracle → not bit-for-bit reproducible):

| quantity | value |
|---|---|
| targets attempted | 6 |
| targets resolved (strict: **zero** truncations) | 0 |
| targets resolved to a **non-trivial** anonymity set | **6 / 6** (24–45 absorbers each) |
| mean graph-only min-entropy | **3.13 bits** (range 2.585–3.585) |
| mean absorbers per target | **34.5** (range 24–45) |
| residual truncations per target | 1–8 (deep coinjoin ancestors still refused at `wall_ms=6000`) |
| mean fused min-entropy (subjective-covered targets) | — (0 covered; see below) |
| §04 fusion sharpening (mean reduction, covered) | 0.0 bits — **no** subjective link fired on these targets |
| `cluster_refined` | 27 clusters over 120 nodes |
| M3 worst-partition gap (sampler vs exact enumeration) | **8.5e-9** (5 super-nodes) |
| M3 co-assignment vs `cluster_refined` agreement | **1.0** (all 5-super-node pairs agree) |

Per-target (graph-only == fused for every one):

| target (txid prefix, vout 0) | absorbers | min-entropy (bits) | truncations |
|---|---|---|---|
| `12da3dd7…` | 27 | 3.000 | 3 |
| `cc8b2e50…` | 45 | 3.459 | 6 |
| `d7149022…` | 35 | 3.170 | 4 |
| `74b79e92…` | 37 | 2.585 | 1 |
| `372fd5cb…` | 24 | 3.000 | 5 |
| `50447deb…` | 39 | 3.585 | 8 |

Reading it:

- **Coinjoin ancestry resolves on live data.** Given adequate oracle wall time, all six
  payment+partial-mix targets resolve to real anonymity sets of 24–45 ancestral origins (2.6–3.6
  bits of min-entropy) — where an under-budgeted oracle collapses each to a single point
  (`n_absorbers=1`, 0 bits). This is the §04 anonymity set, live. `n_targets_resolved=0` is the
  strict metric (zero truncations anywhere in the walk); every target still hits 1–8 deep
  coinjoin ancestors the bounded oracle refuses, so each set is a lower bound — more oracle time
  would only add origins, never remove them.
- **Fusion did not sharpen here.** `fused == graph` for all six: no subjective
  same-owner link (address-reuse self-transfer or `cluster_pairs`) fell inside these particular
  coinjoin-ancestry walks, so the §04 fusion had nothing to narrow. The fusion mechanism is the
  thing under test, and it is demonstrated separately by the Tier-1 controlled fixture (a
  concentrating same-owner oracle lowers provenance min-entropy 1.0 → 0.304 bits) and asserted by the
  conservative-clamp invariant; the live slice simply lacks a subjective-covered target. Coverage of
  the subjective sources on real coinjoin-heavy data is a known gap (see
  `RESULTS-anonymity-set-scale.md`), not a fusion failure.
- **M3 is exact and agrees with the production clusterer, live.** The sampler-vs-exact-enumeration
  gap (~8.5e-9) reconfirms the Tier-1 exactness on live-derived Evidence, and
  `m3_coassignment_agreement = 1.0` says the exact-Bayesian partition posterior and `cluster_refined`
  place all five co-spend super-node pairs the same way — the "complement" direction (M3 as an
  exact-Bayesian *check* on the production clustering) holding on real data. (An earlier run reported
  `0.0` here; that was a defect in the txid→address bridge feeding `cluster_of` — `cluster_refined`
  clusters funding txids, but the cross-check and the `cluster_pairs` source both look up
  *addresses*. Fixed by `cluster_of_from_tx_groups`, which expands each same-owner txid group into its
  input prevout addresses; the offline e2e test now asserts the cluster source actually fires, as a
  regression guard.)

## Limits

- **Bounded slice.** Both tiers cap the slice size (`cap_total`, `M3_MAX_SUPERNODES=5`,
  `max_targets`) — this validates the pipeline's plumbing and mechanism on a real but small slice,
  not a population-level claim.
- **Subjective sources are heuristic, not proof.** Address-reuse self-transfer and cluster-derived
  same-owner links (`cluster_pairs`) are same-owner **labels**, not independently verified; they
  narrow the anonymity set as evidence, under the same conservative-lower-bound discipline as the
  rest of the codebase (fusion is clamped to never exceed the graph-only baseline).
- **M3 vs `cluster_refined` are different engines.** The exact-Bayesian partition posterior (M3) is
  a small-`n` (`<= 5` super-node) exactness check on its own generative model; `cluster_refined` is
  the production, refuse-channel-fused engine over the full slice. `m3_coassignment_agreement`
  cross-checks them; it is a diagnostic, not a claim that one is "the correct" clustering.
- **Live non-determinism.** `run_live` depends on real chain data, real network timing, and the
  wall-clock-bounded oracle's timing-dependent truncation — not bit-for-bit reproducible run to run,
  by design (same posture as `results/RESULTS-anonymity-set-scale.md`).
- **Conservative-lower-bound footing.** Every entropy number here (Tier-1 or Tier-2) is an attacker
  lower bound / weight-of-evidence under no auxiliary information, not a privacy score.

## Reproducibility / provenance

State 2 in `results/REPRODUCIBILITY.md`: the mechanism is pinned; the reported numbers come from a data-run over `.cache`, which is not committed, and are not asserted.
Tier-1 is asserted by `tests/test_e2e.py`; Tier-2 fetches live and is not.
