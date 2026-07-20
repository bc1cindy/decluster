# Cluster-scale — the whole-corpus merge-only baseline, measured offline

The faithful merge-only baseline (`cluster.build_cospend_lookup` + `cluster_from_index`, wired into
`graph_metric.overcount_report` via `baseline_lookup`) computes multi-input clustering over the **whole
loaded corpus**, not just the evaluation sample. This measures its **scale** and checks the premise
that whole-corpus membership is a stronger, fairer baseline than the sample-local `cluster_naive`.
Offline — no network. Code: `decluster/cluster.py`, `decluster/graph_metric.py`.

**Corpus:** the value-carrying BigQuery downloads (`~/Downloads/bquxjob_*.json`), **133,672 unique
transactions** (a scattered multi-epoch sample, not a contiguous chain — this matters below).

## Whole-corpus multi-input baseline

| funders | entities | collapse | entropy (bits) | eff. anon. set | largest-cluster frac |
|---|---|---|---|---|---|
| 318,433 | 99,957 | **68.6%** | 13.21 | 9,501 | 0.072 |

The common-input-ownership heuristic collapses 318k coin-funders into ~100k entities in seconds,
entirely offline — the machinery scales. The largest cluster already holds **7.2% of all funders** (a
supercluster, the usual exchange/service signature).

## Scale curve — entities per funder as the corpus grows

| corpus fraction | txs | funders | entities | entities/funder |
|---|---|---|---|---|
| 0.10 | 13,367 | 63,870 | 12,754 | 0.200 |
| 0.25 | 33,418 | 110,565 | 22,818 | 0.206 |
| 0.50 | 66,836 | 165,052 | 51,978 | 0.315 |
| 0.75 | 100,254 | 264,201 | 83,943 | 0.318 |
| 1.00 | 133,672 | 318,433 | 99,957 | 0.314 |

**Honest reading:** the entities/funder ratio does **not** fall monotonically as the corpus grows — it
rises from ~0.20 to ~0.31. On a scattered value-sample, each added chunk introduces more *new,
not-yet-co-spent* funders than it does new merges, so per-funder collapse dilutes rather than
compounds. On a **contiguous** corpus (a block window, or the eventual whole-chain source) the curve
would behave differently, because co-spends accumulate on the same funder population. Do not read this
as "more data always collapses more" — that holds for contiguous chain coverage, not for a scattered
sample.

## Window-local vs whole-corpus — the branch's premise

The point of `build_cospend_lookup` is to drop `cluster_naive`'s `if vin["txid"] in nodes` sample gate,
so the baseline sees co-spends **outside** the evaluation window. On the **same 63,870 funders** that
appear in a 10%-window:

| baseline | entities |
|---|---|
| window-local (co-spends inside the window only) | 12,754 |
| whole-corpus (all co-spends) | **12,705** |

Whole-corpus merges **49 more** funder-groups — co-spends the window-local baseline structurally
misses. The premise holds **directionally**: the whole-corpus baseline is strictly stronger. But the
magnitude here is **small (0.4%)**, again because the downloads are scattered: cross-window co-spends
among this particular sample are rare. The faithful-baseline advantage this branch enables becomes
material only on a **contiguous / whole-chain** source, where a coin's true cluster genuinely extends
far beyond any window.

## Scope & caveats

- **Baseline only.** The `cluster_refined` (decluster signed) side of `overcount_report` is `O(n^2)`
  pairwise and calls `fetch_tx` (network), so the baseline-vs-fused comparison at scale is **not** run
  here — it awaits a local raw-tx source (esplora / Core txindex) to be cheap. This doc measures the
  merge-only baseline's scale and faithfulness, which is what `build_cospend_lookup` newly enables.
- **Whole-downloads, not whole-chain.** The lookup is faithful to the *loaded corpus*; a funder never
  co-spent within it stays a singleton, so the true whole-chain baseline (which would merge more) is a
  lower bound on collapse. The full effect awaits the whole-chain source.
- **Node = funder txid** (a coin-granularity simplification decluster already makes); pass evaluation
  nodes as a **set** (deduped) — `cluster_from_index` counts duplicates while the fused side's
  union-find dedups, so a duplicated node list would desync the two partitions.

## Conclusion

The whole-corpus merge-only baseline computes at scale offline (133k txs -> 100k entities in seconds)
and is measurably stronger than the sample-local baseline (49 extra merges on the shared funders),
confirming the branch's premise directionally. The magnitude of the whole-chain advantage — and the
baseline-vs-fused comparison — is bounded here by the scattered, network-free sample; both grow on a
contiguous / whole-chain source, which is the next data-layer step (local esplora), not a change to
this method.
