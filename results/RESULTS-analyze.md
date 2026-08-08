# `analyze()` live depth-5 validation — **PENDING** (harness built, live run not yet executed)

`examples/analyze_live.py` runs the PUBLIC `analyze()` facade (`decluster/analyze.py`, exported from
`decluster`) over real Wasabi-scale coinjoin round transactions, live-fetched, at `depth=5`, behind
the panic-safe `decluster.oracle.bounded_link_oracle`. It is the systematic-callability proof the
facade exists for: an external consumer calling `analyze(txid, ...)` on real chain data must never
crash, and should resolve deeper (more informative) origins than a shallow walk.

**This file's numeric table is PENDING.** The harness (`examples/analyze_live.py`) is built and
verified offline (see below); no live run has been executed yet. The numbers below are placeholders
— **do not treat any number in the table as real** until this section is replaced with an actual run.
The controller runs the live pass and fills this in next:

```
.venv/bin/python -m examples.analyze_live [max_targets] [cap_total] [budget_ms] [depth]
```

## (a) Systematic callability

| quantity | value |
|---|---|
| targets attempted (`n_targets`) | **PENDING** |
| crashes (`crashes`) | **PENDING** (must be 0 — the panic-safe `bounded_link_oracle` is designed so no exception ever surfaces through `analyze()`; an oracle refusal shows up as `truncated`, not an exception) |

## (b) Origins resolved (live, depth 5)

| quantity | value |
|---|---|
| resolved to a non-trivial anonymity set (`n_absorbers > 1`) | **PENDING** / PENDING |
| mean absorbers per resolved target (`mean_absorbers`) | **PENDING** |
| mean graph-only min-entropy, resolved (`mean_min_entropy`, bits) | **PENDING** |

Context for reading this once filled in: other live harnesses in this repo (`RESULTS-e2e.md`, at
`depth=2`) resolve payment+partial-mix targets to 24–45 absorbers / 2.6–3.6 bits. `depth=5` walks
further back through the ancestry graph than that; the panic-safe `bounded_link_oracle` (in-process,
`budget_ms`-cooperative) is expected to truncate more of the deepest coinjoin ancestors than the
subprocess, wall-clock-killed oracle those harnesses use, since dss's own cooperative budget check
is less reliable than an OS-level kill on pathological inputs — this is the tradeoff for staying
in-process (no `spawn`/`__main__`-guard requirement) at the default depth. If the live numbers show
fewer/shallower absorbers than the `depth=2` subprocess-oracle results, that is this tradeoff, not a
regression in `analyze()` itself.

## (c) Deep (ancestral) fusion emergence

| quantity | value |
|---|---|
| deep fusion count (`deep_fusion`) | **PENDING** / PENDING |

`deep_fusion` counts a target where the §04 fused min-entropy sharpens strictly below the graph-only
min-entropy (`fused.min_entropy < provenance.min_entropy - 1e-9`) **and** the target's own
transaction has no `address_reuse_pairs` firing — i.e. the sharpening came from a same-owner
`address_reuse_pairs` link found somewhere back in the ancestry walk (an ancestor transaction), not
from the target's own inputs/outputs. This isolates the deep-fusion mechanism from the much more
common case already demonstrated live in `RESULTS-anonymity-set-scale.md` and `RESULTS-e2e.md`
(same-owner evidence firing on the target's own tx).

## Honest limits

- **§06/robustness predicts deep fusion is rare — report as theory alignment, not failure.** The
  provenance walk's absorber distribution spreads probability mass across many ancestor origins as
  depth grows; a single ancestral same-owner link narrows only the mass routed through that one
  ancestor, and needs to be large relative to the rest of the distribution to move the *min*-entropy
  (a worst-case, not average-case, quantity) by more than `1e-9`. If `deep_fusion` comes back 0 or
  small on this slice, that is consistent with the theory, not evidence `analyze()`'s fusion is
  broken — the mechanism itself is separately demonstrated and asserted (see
  `results/RESULTS-anonymity-set-scale.md`'s own-tx-reuse coverage numbers, and `tests/test_analyze.py`
  / the offline fusion-conservative invariant in `RESULTS-e2e.md`).
- **Bounded, in-process oracle at depth 5.** `bounded_link_oracle` is the panic-safe default the
  public `analyze()` facade ships with — deliberately not the subprocess/`__main__`-guarded oracle
  other live harnesses use, so this harness can be a plain importable module with no spawn
  requirement. That means a pathological ancestor can still truncate a branch (counted in
  `truncated`, never an exception) at any depth; `budget_ms` (default 6000, matching
  `decluster.oracle.DEFAULT_ANALYZE_BUDGET_MS`) trades wall time against how much of the depth-5
  ancestry actually resolves.
- **Live non-determinism.** Real chain data, real network timing, and the `budget_ms`-bounded
  oracle's timing-dependent truncation — not bit-for-bit reproducible run to run (same posture as
  `RESULTS-e2e.md` and `RESULTS-anonymity-set-scale.md`).
- **Slice, not population.** `cap_total`/`max_targets` bound the run to a small real slice
  (`examples.anonymity_set_scale.seed_targets()`, multi-input non-coinjoin-scale txids drawn from
  local history) — this validates systematic callability and the deep-fusion mechanism's presence
  or (expected) rarity on a real but small sample, not a population-level claim.
- **Subjective source is heuristic, not proof.** `address_reuse_pairs` (self-transfer / address
  reuse) is a same-owner **label**, not independently verified; deep-fusion sharpening built on it
  inherits that same caveat, under the codebase's usual conservative-lower-bound discipline (fusion
  is clamped to never exceed the graph-only baseline — `analyze()`'s own `min(...)` clamp).
