# Provenance anonymity set (M1) — graph-only entropy, subjective decay, and the F-S collapse

`decluster/anonymity_set.py` (`anonymity_bits`, `reweight`, `provenance_anonymity`, `decay`,
`provenance_overlap_hypothesis`) is Object A of the tx-graph anonymity-set theory: the per-coin
entropic anonymity set, dual to the M3 partition posterior's same-owner-clustering Object B. The
graph-derived provenance distribution (`ancestry.absorber_distribution`, the §04 anonymity set) is
multiplicatively narrowed by subjective hypotheses (§06); min-entropy is the conservative,
defender-side read — a lower bound / weight-of-evidence, never a privacy score.

`examples/anonymity_set.py` runs this offline over `.cache/`, reusing
`examples.ns_propagation_cache_run`'s cache-bounded slice and its real address-reuse same-owner
labels (no network, no fabricated same-owner facts). Reproduce:
`./.venv/bin/python -m examples.anonymity_set` (prints the full per-target JSON; ~32s).

## Tractability: the exact oracle needed a harder bound than its own `budget_ms`

`dss.pairwise_link_prob` takes a cooperative `budget_ms`, but probing this cache found it does not
reliably return within it: a 27-input/2-output tx with near-equal input values hung **>40s** despite
`budget_ms=1500`, and a 3-input/37-output tx hung **>30s** — not only the obvious CoinJoin-scale
mixes (up to 331 inputs / 420 outputs are present in this cache). A `signal.alarm`-based Python
timeout also failed to preempt it (the native call never yields back to the interpreter mid-search).
One case (a 27-input tx) hard-panicked the native code (`assertion failed: set.len() <= 64`,
`pyo3_runtime.PanicException`) rather than hanging or returning `None`.

So `examples/anonymity_set.py`'s `hard_bounded_link_oracle` runs each link computation in a
throwaway subprocess and kills it (`terminate`, then `kill`) on a 1.2s wall-clock deadline —
an OS-level bound that works regardless of what the native code does internally, and also absorbs
the panic case cleanly. A kill or a panic both return `None`, exactly `ancestry`'s own
oracle-refusal boundary — `build_extended_graph` already truncates cleanly on `None`, so no
core-code change was needed, only the harness-level wrapper.

## (a) Graph-only min-entropy — the post-04 anonymity set, on 34 real same-owner pairs

34 (target, reference) pairs, drawn from this cache's real address-reuse same-owner clusters (the
independent, non-circular label `ns_propagation_cache_run` already validates against co-spend —
see `RESULTS-ns-propagation.md`). Depth 2, hard-bounded oracle, no network.

| outcome | count |
|---|---:|
| **resolved** (≥2 absorbers — real branching within the bounded walk) | **2 / 34** |
| **collapsed to a single boundary atom** (0 bits) | **32 / 34** |
| — of which: oracle-timeout truncation (dense/CoinJoin-scale parent) | 18 / 34 |
| — of which: genuine single-parent chain (no truncation, just 1 input all the way) | 14 / 34 |

**94% of these real targets carry zero graph-only ambiguity at depth 2** in this bounded slice —
either because the coin's own backward chain is genuinely a sequence of 1-input spends (no
branching to resolve), or because depth 2 immediately hits a dense CoinJoin-scale parent that the
hard-bounded oracle correctly refuses rather than fabricates a link for. This is the same
mechanism `RESULTS-ancestry.md` and `RESULTS-ns-propagation.md` already found: bounded-depth,
bounded-cache ancestry is dominated by collapse, with real ambiguity showing up only where the
graph actually branches.

The 2 targets that *do* resolve real branching (both small, un-truncated, exact walks):

| target | n_absorbers | graph min-entropy (Shannon = min, uniform split) |
|---|---:|---:|
| `796c742b14…` (4-in tx) | 4 | **2.000 bits** |
| `4817b7a896…` (3-in tx) | 3 | **1.585 bits** |

Both are a real 4-way / 3-way tie: the backward walk resolves the coin's provenance to several
boundary coins with exactly equal mass (`0.25` each / `0.333` each) — this is the §04
anonymity set for these two coins under no auxiliary information: an attacker constrained to the
graph alone cannot do better than guessing uniformly among 4 (resp. 3) candidate origins.

## (b) + (c) Subjective decay — narrowing hypotheses and the confidence-1 collapse

For each of the 2 resolved targets, three hypotheses are folded in via `decay`, in order:

1. **`provenance_overlap(same-owner ref)`** — `provenance_overlap_hypothesis` scored against the
   *real* address-reuse-labelled reference coin's own ancestry signature (same construction as
   `ancestry.provenance_link`, not synthetic).
2. **`entity_narrowing(reinforce top candidate)`** — a further narrowing step that reinforces
   whichever origin hypothesis 1 already left as most likely (factor `1.0` for that origin, `0.1`
   for the rest) — provably non-entropy-increasing by construction (renormalizing after uniformly
   discounting every non-favoured origin can only raise the favoured origin's relative share).
3. **`indicator_confidence1(illustrative F-S case)`** — a hypothetical confidence-1 indicator
   naming the (by-then) leading candidate as certain. This is **illustrative**, not a real
   de-anonymization claim on this coin — it demonstrates the *structure* of the Fung–Sui special
   case: a confidence-1 hypothesis collapses the distribution to a point mass, min-entropy exactly
   0.

| target | graph | provenance_overlap | entity_narrowing | indicator (confidence-1) | monotone? |
|---|---:|---:|---:|---:|:---:|
| `796c742b14…` | 2.000 | 2.000 | **0.379** | **0.000** | yes |
| `4817b7a896…` | 1.585 | 1.585 | **0.263** | **0.000** | yes |

Both traces are monotone non-increasing end to end, and both end in an exact 0-bit point mass
— (b) and (c) both hold on real data.

**Reading of step 1 (flat in both cases):** the `provenance_overlap` hypothesis contributed
*zero* narrowing for either target — not because the mechanism is broken, but because each
reference coin's own bounded-depth signature had already collapsed to a single boundary atom
(1 and 4 absorbers respectively — checked: `reference_n_absorbers` = 1 and 4), and that atom did
not coincide with any of the target's own absorbers within depth 2
(`h1_kept_graph_argmax=False` for both — the graph's own top candidate wasn't even in the
overlap-kept set, yet the *suppressed* set was suppressed uniformly, so the shape — and hence the
entropy — didn't move). `reweight`'s math makes this transparent: when every origin gets the same
suppression factor, the renormalized distribution is unchanged. This is the same finding
`RESULTS-ns-propagation.md` already reports at the pipeline level ("the cache-bounded ancestry
signal is real but weak and partial") — here it shows up directly in a subjective hypothesis
built from that signal. Steps 2–3 do not depend on the reference at all (they narrow around
whatever step 1 leaves as the leading candidate), so they demonstrate (b)/(c) cleanly regardless.

## Limits

- **Bounded slice.** All 34 pairs and both resolved walks are over this checkout's `.cache/`
  (~1,900 tx JSON files) at depth 2 — not a chain-scale claim. 94% collapse here; a live,
  higher-depth network run would very likely resolve more real branching, per
  `RESULTS-ancestry.md`'s finding that deeper reach *lowers* the graph-only entropy bound further
  (more mass resolves onto fewer boundary coins) — collapse is the expected direction as depth
  grows, not bounded-cache noise.
- **The hard-bounded oracle trades completeness for a wall-clock guarantee.** 18 of the 34
  "collapsed" targets collapsed because the walk hit a dense parent and the 1.2s subprocess-kill
  refused to compute a link, not because the graph is provably a single origin. Per
  `ancestry.build_extended_graph`'s own entropy-grouping argument, this can only ever *understate*
  ambiguity (truncation coarsens toward a boundary atom, which cannot raise the true entropy) — so
  every 0-bit reading here is a conservative floor, not evidence of true determinism.
  `WALL_MS=1200` is a harness-level tractability choice, not a validated cost model.
- **Reweighting is a conservative lower bound, not a privacy score.** `anonymity_bits`/`decay`
  report min-entropy under the hypotheses actually supplied; they say nothing about hypotheses not
  modelled, and a flat step (as in `provenance_overlap` above) means "no evidence found," not "no
  evidence exists."
- **Subjective factor confidences are provisional.** The `1.0`/`0.1` weights used for
  `entity_narrowing` and the `suppress=1e-6` default in `provenance_overlap_hypothesis` are
  illustrative constants, not calibrated confidence/false-positive rates — that calibration is
  future work (as already flagged in `task-2-report.md`).
- **`indicator_confidence1` is illustrative, not a finding about these specific coins.** It shows
  what a confidence-1 hypothesis structurally does to the distribution (the F-S special case), not
  a claim that either coin's origin is actually known with certainty.
- Same-owner labels throughout are the address-reuse heuristic already validated (independent of
  co-spend) in `RESULTS-ns-propagation.md` — same-owner labels, which are an address-reuse
  heuristic rather than ownership.

## §04-faithful fusion: link-level (pre-solve) vs the post-solve `reweight` baseline

`decluster/anonymity_set.py`'s `provenance_anonymity_fused` implements the §04 mechanism directly —
"a [subjective] matrix that combines with the ones derived from the graph": the subjective matrix is
multiplied into each per-tx link matrix BEFORE the absorbing solve
(`build_extended_graph(..., subjective_oracle=...)`, `decluster/ancestry.py`:
`matrix[i][j] *= sub[i][j]`), so subjective evidence can redirect probability mass through a
*specific interior edge* mid-walk. This is structurally different from, and strictly more
expressive than, the `reweight`/`decay` mechanism demonstrated in (a)-(c) above, which only rescales
the *already-solved* boundary distribution — it can favor or suppress whole absorbers, but it can
never route mass through one interior branch in preference to another the way link-level fusion
can. `reweight` is retained as the weaker (but simpler, cheaper) baseline, not removed.

### The mechanism, proven on a controlled fixture (task 2)

`test_fused_sharpens_provenance_vs_graph_only` (`tests/test_anonymity_set.py`) hand-derives a
branching walk where a concentrating subjective oracle (`boost=9.0` on a pinned `(input, output)`
pair at every interior tx) takes:

| | distribution | min-entropy | Shannon |
|---|---|---:|---:|
| graph-only | `{b:0.5, a0:0.25, a1:0.25}` | 1.000 bits | 1.500 bits |
| §04-fused | `{b:0.1, a0:0.81, a1:0.09}` | 0.304 bits | 0.891 bits |

confirming the link-level fusion sharpens entropy by construction (full derivation:
`task-2-report.md`).

### The concrete real-data signal: `_change_index`

`examples/anonymity_set_fused.py` builds a concrete `sameowner_link_oracle`
(`decluster/anonymity_set.py`) driven by `extractors._change_index(tx)` — a real decluster
detector, verified from source, not invented: on a genuine 2-output tx it flags the LESS-round
output as change (a round-number heuristic, independent of script type), which is same-owner as
every input by construction. `same_owner_pairs(tx) = {(i, change_idx) for i in range(n_inputs)}`
when `_change_index` resolves, else `set()` (abstain). This needs only the tx's own `vout` values —
no fetch/outspends — so it runs fully offline over `.cache/`.

Reused verbatim from `examples/anonymity_set.py`: the same 34-pair bounded slice (real same-owner
(target, reference) pairs from address-reuse clusters), depth 2, and `hard_bounded_link_oracle`
(subprocess-killed subset-sum — see this file's "Tractability" section above) — for the identical
reason: the exact link oracle hangs/panics on CoinJoin-scale and dense-value txs in this cache.
Reproduce: `.venv/bin/python -m examples.anonymity_set_fused` (prints the full per-target JSON;
~63s).

### Real graph-only vs §04-fused min-entropy, per target (34 real same-owner pairs, depth 2)

Same 34 targets as section (a). For each: graph-only min-entropy vs §04-fused min-entropy under
`sameowner_link_oracle` driven by `_change_index`.

| outcome | count |
|---|---:|
| sharpened (fused min-entropy < graph-only min-entropy, strictly) | **0 / 34** |
| unchanged | 34 / 34 |
| targets where the change signal actually fired (≥1 real `(i, change_idx)` pin) | **1 / 34** |
| total interior-tx oracle calls across all 34 fused walks | 16 |
| — of which fired a real pin | 1 / 16 |

The two targets that resolve real graph-only branching (section (a): `796c742b14…` at 2.000 bits,
`4817b7a896…` at 1.585 bits) are unchanged under fusion — the fused walk visits exactly one
interior tx for each (the target's own top-level tx) before hitting its boundary, and neither is a
clean 2-output tx, so `_change_index` abstains and no pin is ever available to route mass through.

The one target where the signal *did* fire (`0143df0bda79…`) was already collapsed to a single
boundary atom under the graph-only walk (0 bits) — a single-parent chain with nothing left to
sharpen: boosting the one live link column by 9x is a no-op when that column already has exactly
one nonzero entry.

### Reading

- **The result on this slice is null.** 0/34 targets show
  measurable §04 sharpening from this concrete signal, and the signal itself fires on only 1 of 34
  targets' own reachable interior txs. This is not a contradiction of the mechanism test above (which
  proves the sharpening happens whenever the oracle fires on a branching walk) — it is a coverage/
  overlap finding: on this bounded real slice, the two conditions needed for a visible effect (a
  resolvable `_change_index` pin AND live graph-only branching at that same interior tx) essentially
  never coincide. Each is independently rare here — 94% of these 34 targets already collapse to a
  single graph-only absorber before any branching is reached at all (section (a)), and
  `_change_index` requires an exact, non-tied 2-output tx — so their conjunction being 0/34 on a
  34-target, depth-2 sample is an expected small-sample outcome, not evidence the fusion mechanism
  is broken.
- **Bounded slice, same caveats as section (a):** ~1,900-tx `.cache/`, depth 2, hard-bounded (1.2s
  subprocess-killed) link oracle — every reading here is a conservative lower bound (truncation only
  ever coarsens toward a boundary atom; it cannot fabricate ambiguity, and it cannot manufacture
  resolution either).
- **Conservative lower bound, not a privacy score** — same as (a)-(c): both `graph_min_entropy` and
  `fused_min_entropy` report weight-of-evidence under exactly the modelled signal, nothing about
  signals not modelled. A deeper walk, a larger cache, or a richer subjective signal (e.g.
  `coinjoin_demix` pairs, when they cleanly yield input↔output links) would very likely surface real
  sharpening that this particular slice's `_change_index`-only signal did not.
- Same-owner labels throughout are the address-reuse heuristic already validated (independent of
  co-spend) in `RESULTS-ns-propagation.md` — same-owner labels, which are an address-reuse
  heuristic rather than ownership.

## Reproducibility / provenance

State 2 in `results/REPRODUCIBILITY.md`: the mechanism is pinned; the reported numbers come from a data-run over the `.cache/` slice `examples/anonymity_set.py` reads, which is not committed, and are not asserted.
