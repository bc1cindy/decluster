> **SUPERSEDED (kept as the motivating analysis).** This document asks whether dss's W(E) counts were
> integrated when the question was first posed — at the time, they were not. Since then the §07
> path-counting object HAS been built and shipped: `decluster.path_count.path_count_anonymity` (via
> `analyze(path_count=True)`), backed by the `dss.w_count` dispatcher, with `counting.w_total` wiring
> the counts into decluster. So statements below like "called nowhere in decluster" and "not a wiring
> task" describe the *starting* state, not the shipped one — see `results/RESULTS-path-count.md` for
> the delivered object and its real numbers.
>
> The current executable contract is `catalog/runs/path-count-contract-v1.json`, rendered as
> `results/generated/path-count-contract-v1.md`. It identifies the delivered object as provenance
> route accumulation, not edge-disjoint plausible-flow path counting.

# Is dss what's needed for §07 path counting, and is it exposed/integrated in decluster?

Analysis against `tx-graph-anonymity-sets` §07 (*path-like anonymity set*) and the dss count-paths.
Short answer: **dss provides the necessary *local* counting primitive (per-transaction `W(E)`, plus a
tractable polynomial approximation) — but it is not *sufficient* for §07, which needs a graph-level
path aggregation that neither dss nor decluster implements. Of the count-paths, only
`per_coin_density` is wired into decluster today; the four `W(E)` count-paths are exposed in dss but
not integrated.**

## What §07 asks for (from the refs)

§07 is a sparse, mostly-TODO sketch. It defines the anonymity set's constituents as *paths*: for a coin
there are *"two apparent paths … one of them is noise"* — Alice's genuine transaction history and
**counterfactual paths** through unrelated coins. The object to build is *"a sufficiently robust
anonymity set whose constituent objects are these paths."* It marks the formalization TODO
(*"the intersections of the walks create symmetries…"*). It does **not** itself specify subset-sum
counting — that connection is inferred below, and it is the same combinatorial enumeration §03
attributes to the Boltzmann/Maurer frameworks (*"combinatorial enumeration of possible transaction
partitions with entropy quantification"*).

## What the dss count-paths actually compute (verified)

Each operates on a **single transaction's** input/output values:

| call | output | meaning |
|---|---|---|
| `w_brute(ins, outs, max_size)` | `{kind:"exact", count:6, log_w:1.79}` | exact `W(E)` — the NUMBER of valid subset-sum input↔output mappings, and log of it |
| `w_sparse(ins, outs, max_size)` | `{kind:"exact", count:6, log_w}` | same count via the sparse method |
| `w_sasamoto(ins, outs)` | `{kind:"unknown", count:None, log_w:None}` here | polynomial **saddle-point approximation** of `log W(E)` (applies in a regime; `unknown` off-regime) |
| `radix_mappings(ins, outs, max_size)` | radix-structured mapping enumeration | the dense-coinjoin structural count |
| `per_coin_density(ins, outs)` | `{kappa, coins:[{role,index,value,log_w,kappa_c}]}` | per-coin `log_w` magnitude + the κ vs κ_c phase (the privacy-magnitude engine) |

So the count-paths are exactly a **per-transaction mapping-multiplicity `W(E)`** engine — the local
factor a path count is built from — including a *polynomial* approximation (`w_sasamoto`) that is the
tractable alternative to explicit enumeration.

## Is dss "what's needed"?

**Necessary, not sufficient.**
- A §07 *path* is a consistent chain of per-transaction input↔output assignments through the ancestry.
  The multiplicity of assignments at each transaction is precisely `W(E)`; the count of counterfactual
  paths is the graph-level combination of these per-tx multiplicities. dss delivers the **per-tx
  `W(E)`** exactly (`w_brute`/`w_sparse`), structurally (`radix_mappings`), and — crucially for
  tractability — **approximately in polynomial time** (`w_sasamoto`). This is the right and necessary
  counting engine, and its approximation is exactly what could make a deep count tractable where the
  §04 walk explodes (see `RESULTS-analyze.md` (b)).
- **What dss does NOT provide:** the graph-level aggregation — walking the ancestry and combining the
  per-tx `W(E)` into a path count / path-like anonymity set (and the §07 "path-intersection symmetry"
  the refs leave TODO). That layer is per-graph, not per-tx, so it is outside dss by construction.

## Is the needed API exposed AND integrated with decluster?

- **Exposed in dss (Python):** YES — `w_brute`, `w_sparse`, `w_sasamoto`, `radix_mappings`,
  `per_coin_density` are all callable and return the shapes above.
- **Integrated into decluster:** only the **density** path. `decluster/cost.py::dss_oracle` wraps
  `dss.per_coin_density` and feeds `amount_cuts` (refuse-only amount-channel cut candidates, using each
  coin's `log_w` as a knee-truncated lower bound). The four `W(E)` **count**-paths
  (`w_brute`/`w_sparse`/`w_sasamoto`/`radix_mappings`) are **called nowhere** in decluster or examples
  (`grep` clean). No decluster object aggregates per-tx `W(E)` across the graph.
- **The code already names this gap, twice:**
  - `cost.py::amount_cuts`: *"A rigorous cut needs an exact count and is deferred."* (it uses the
    density `log_w` bound, not the exact `W(E)` count).
  - `cost.py::construction_cost`: raises `NotImplementedError` because *"it depends on the
    path-counting `target` (still a stub)"* — i.e. the §07 path-count object is the acknowledged
    missing input to the cost function.

## What integrating §07 with the 4 counts would take

1. **Expose the counts through decluster (trivial):** a thin wrapper in `cost.py`/a new
   `decluster/counting.py` mirroring `dss_oracle`, surfacing `w_brute`/`w_sparse`/`w_sasamoto`
   (exact when small, Sasamoto approximation when large) as a per-tx `W(E)` provider — analogous to how
   `dss_link_oracle` wraps `pairwise_link_prob`.
2. **The real work (research, = the §07 stub):** a graph-level aggregator that reuses the ancestry
   traversal (`ancestry.build_extended_graph`) but, instead of the random-walk absorbing solve,
   combines per-tx `W(E)` along paths into a path-count / path-like anonymity set — and formalizes the
   §07 path-intersection symmetry the refs leave open. This is the `target` stub `construction_cost`
   waits on.

**Bottom line:** dss is the correct counting engine for the *local* magnitude and even offers the
polynomial approximation a tractable deep count needs, so it is necessary — but §07 path counting is a
graph-level object requiring an aggregation layer that is neither in dss nor in decluster today (only
`per_coin_density` is integrated; the `W(E)` counts are exposed-but-unused). Building step 2 is
squarely the refs' open §07 research, not a wiring task.
