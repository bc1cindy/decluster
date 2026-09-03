# Bounded walk + §07 path-count — real numbers

> **Correction (2026-09-03) — the default oracle behind the walk has moved.**
> The runs below pass `bounded_link_oracle(...)` explicitly, so their numbers remain reproducible as
> written. `path_count_anonymity()` and `analyze()` now default to `ancestry.value_flow_link_oracle`
> (nominal-value transitions, no dss) instead; the subset-sum walk measured here is opt-in.

`examples/path_count_live.py` exercises the two shipped capabilities on real data: the **bounded walk**
(`max_nodes`, makes deep coinjoin `analyze()` tractable) and the **§07 path-count** object (weighted by
link probability alone — see "Multiplicity has left the bound", below). Honest numbers below, with the
nuances the runs surfaced.

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

## Multiplicity has left the bound

Earlier revisions reported that the path count up-weights origins reached through
high-multiplicity transactions, and a test pinned that behaviour. Both are retired.

`cost.py` declares the amount channel refuse-only: it may cut a coin from the graph, never weight
one. Measured on a synthetic two-origin DAG, the multiplicity term moved min-entropy from 1.0 bit
to 0.137 — note the direction, which is downward; the objection is not that it inflated a number
but that an ambiguity signal entered the bound as a weight at all. The factor is gone, the origin
distribution is weighted by link probability alone, and the mass key went with it: after the change
it is identically zero, because the edge weights are row-stochastic and the absorbed mass is always
one.

The combinatorial sub-transaction literature does read a low mapping count as low privacy, which is
why the weighting looked principled. But in that literature the count enters as the *denominator* of
a link probability, never as a multiplier on one, and the column this code weights is already
renormalized (`ancestry.py:149`). The factor reintroduced as a weight exactly what the matrix had
just divided out. The refuse-only contract and the literature agree here: there was one defensible
reading, not two.

**What this costs.** `path_count_anonymity` is the default target of the construction-side cost
function, and multiplicity was the only thing distinguishing its output from the plain ancestry
entropy. After this change that instrument measures **no structural property** of the graph.
Measuring one would need disjoint paths — a minimum *vertex* cut, and a plausibility-weighted one,
since a traceable path is not the same as a plausible flow. Vertex rather than edge: what fractures
the graph is a coin ceasing to carry flow, and coins are the vertices here, so the edge reading
counts a larger cut and over-reports robustness. This repository does not compute that. Note
also that the construction-side cost function never combined its terms in the first place: it
returns them uncombined and raises on the attempt, so what changes here is what one of the three
terms means, not a working number.

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
  delegates to `dss.w_count`. So dense coinjoins — the case this dispatcher exists for — get their
  exact counts (asserted by `tests/test_counting.py::test_w_total_dense_coinjoin_is_exact_not_unknown`),
  independent of whether §07 currently spends that count on anything.

Radix (dense repeated-denomination recognition) is a **separate, independent** dss path and is not part
of this cascade.

## Honest limits

- Bounded walk = truncated **lower bound**, never exact; deep-coinjoin exactness is impossible.
- §07 path-count = weighted by link probability alone; identical in distribution to §04's set-size
  entropy, and adds no structural-property term (see "Multiplicity has left the bound", above). It
  does not extend the tractable envelope either (same graph fan-out as §04).
- Live non-determinism (real chain + timing-bounded oracle); a small real slice, not a population.
