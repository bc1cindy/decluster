# Bounded walk + §07 path-count — real numbers

`examples/path_count_live.py` exercises the two shipped capabilities on real data: the **bounded walk**
(`max_nodes`, makes deep coinjoin `analyze()` tractable) and the **§07 path-count** object (the
multiplicity/robustness lens). Honest numbers below, with the nuances the runs surfaced.

## (a) Bounded walk — deep coinjoin now returns, instead of hanging

`analyze(<9-in/17-out coinjoin>, depth=5, max_nodes=20, link_oracle=bounded_link_oracle(5000))`:

| quantity | value |
|---|---|
| wall | **292 s (~5 min)** |
| crashed | **no** |
| origins resolved (lower bound) | **67** |
| min-entropy | **3.0 bits** |
| truncated (unexpanded frontier + oracle refusals) | 70 |

Contrast: the **unbounded** depth-5 walk over the same coinjoin **did not finish in a 25-minute cap**
(`RESULTS-analyze.md` (b)) — the ancestral fan-out explodes. `max_nodes` caps the expanded coins, so
the walk returns a **truncated lower bound** (67 origins, 3.0 bits) in bounded time. Two independent
knobs govern this and BOTH matter: `max_nodes` bounds the graph fan-out (number of hops); `budget_ms`
bounds each hop's oracle cost. With `budget_ms=2000` the same call returns in 6 s but the first
coinjoin hop (~2.3 s of exact subset-sum) truncates → a point mass; `budget_ms=5000` resolves the hops
at the cost of wall time. Bounded, honest, never exact — exact deep-coinjoin resolution is impossible
(the explosion is the privacy).

## (b) §07 vs §04 — when they differ, and why usually they don't

On the narrow depth-sweep tx and on the `9-in/17-out` seed coinjoin, the §07 path-count distribution is
**identical** to the §04 distribution (min-entropy equal; `log_W_paths ≈ 0`). This is not a defect —
two honest reasons:

1. **Structural (depth 1):** a single transaction's `W(E)` is a global constant across all its edges,
   so it **cancels in the normalization** of the origin distribution. §07's *distribution* therefore
   equals §04's at depth 1 for any tx; only the *magnitude* `log_W_paths` (= `log W(E)`) can differ.
2. **`W(E)=1` on real "coinjoin-shaped" txs:** `12da3dd7…` (9-in/17-out) has `w_total → count=1` — a
   UNIQUE subset-sum mapping. Its specific values pin the assignment, so there is genuinely no
   path-multiplicity to weight. Many real coinjoin-shaped payments are like this.

§07 **diverges from §04 only** when *different ancestral origins are reached through
different-`W(E)` transactions* (depth ≥ 2) **and** those txs carry genuine subset-sum multiplicity
(`W(E) > 1`) — i.e. true equal-denomination dense coinjoins (Wasabi-style equal outputs). The mechanism
is proven in `tests/test_path_count.py::test_multiplicity_upweights_higher_w_e_origin` (a controlled
2-origin fixture where the higher-`W(E)` origin gets strictly more weight: 0.833 vs 0.5). On real data
the divergence is rare because it requires that specific structure — which is itself the §06/§07 point:
robustness lives in genuine path multiplicity, and most single payments don't have it.

## (c) The W(E) count gate — a real bug found and fixed (Sasamoto is NOT the bug)

Investigating why §07 collapsed to §04 on coinjoins surfaced a bug — in **our method selection**, not
in Sasamoto:

- **Sasamoto is correct.** Cross-referenced against the paper (`sasamoto.md`, cond-mat/0106125)
  equation-for-equation and, in its Dense regime, matched to the exact count to **~7e-5 relative**
  (verified in the dss crate's own tests). The `unknown` results are the regime gate correctly refusing
  to apply the asymptotic off-regime (16 inputs cannot enter the Dense bracket, which needs ~thousands
  of BTC/coin and N≳46).
- **The method selection was wrong — and now lives in the right place.** decluster originally gated by
  combined SIZE (`len(inputs)+len(outputs) > 40 → Sasamoto`), which sent dense coinjoins (large size,
  tiny sumset) into a path that correctly refused them, **discarding a cheap exact answer** (a 16-in/
  60-out dense mix is exactly countable: `count=65534`, but the size gate returned `unknown`). The fix
  is architectural: method selection is not decluster's job — it moved into the dss crate as the
  `dss.w_count` feasibility-cascade dispatcher (brute → dp → sparse → sasamoto, selecting by REGIME,
  beside the density logic, with cross-validated Rust tests). `decluster.counting.w_total` now simply
  delegates to `dss.w_count`. So dense coinjoins — exactly where §07's multiplicity lives — get their
  exact counts (asserted by `tests/test_counting.py::test_w_total_dense_coinjoin_is_exact_not_unknown`).

Radix (dense repeated-denomination recognition) is a **separate, independent** dss path and is not part
of this cascade.

## Honest limits

- Bounded walk = truncated **lower bound**, never exact; deep-coinjoin exactness is impossible.
- §07 path-count = weight-of-evidence robustness lens, not a privacy score; it does not extend the
  tractable envelope (same graph fan-out as §04), and it diverges from §04 only on genuine
  path-multiplicity (dense coinjoins at depth ≥ 2).
- Live non-determinism (real chain + timing-bounded oracle); a small real slice, not a population.
