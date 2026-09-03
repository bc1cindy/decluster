# The approximations against the exact oracle — measured

Canonical run: `catalog/runs/exact-oracle-audit-v1.json`. Machine-readable
results live in `results/artifacts/exact-oracle-audit-v1.json`; the concise
generated view is `results/generated/exact-oracle-audit-v1.md`. The narrative
below interprets that run and is not the source of its numeric results.

`decluster/baselines/maurer.py` + `boltzmann.py` are an exact, exponential oracle: every balanced
input/output block mapping of a transaction, and the uniform marginal link matrix over them. The
production paths use the compiled `dss` extension and the wrappers in `decluster/counting.py`,
`decluster/subtransaction.py`. Nothing in this repo had measured whether those agree with the oracle.
`decluster/baselines/oracle_audit.py` now does; `examples/exact_oracle_audit.py` emits the report as
JSON and exits non-zero when it carries a flag.

**Headline.** `dss.pairwise_link_prob` is the uniform marginal over **dss's own mapping family**,
which is a strict restriction of the oracle's, and a marginal over a sub-family is a bound on the
marginal over the full family in **neither direction**. Measured: over 6,228 entries it sits
**above** the exact marginal on 1,714 and **below** it on 4,104, agreeing on 410. And because
`decluster/counting.py`'s own `link_matrix` docstring tells consumers that "a row with one non-zero
entry is a deterministic link — the amounts settle that assignment on their own", the production path
asserts **945 certainties in 328 of 507 transactions that the amounts do not settle**, while
missing no *certain* link. That count is measured against the **full** oracle family, which is the
most conservative reading available: any smaller family has more certain links and so fewer spurious
ones. Dropping the oracle's coarser readings (refinement-maximal selection) leaves it unchanged at
945 / 0; selecting the finest mappings by block count instead — a strictly more generous reading
for the approximation — gives 942 / 108. Both are measured every run.

## The family

Exhaustive, deterministic, zero-fee: every balanced `(inputs, outputs)` over the value alphabet
`{1, 2, 3, 4}` with at least 2 coins a side and at most 8 coins in total, each in canonical form
(the pair of sorted value multisets) exactly once — the enumeration emits each multiset once per
shape, so no deduplication pass is involved and a test asserts the result carries no duplicate.

| quantity | value |
|---|---|
| transactions in the family | **507** |
| distinct (inputs, outputs) shapes | 15, from 2×2 to 6×2 and 2×6 (largest cell: 4×4, 119 cases) |
| exact mappings enumerated over the family | 7,930 |
| link-matrix entries compared | 6,228 |
| fee | **0** — the oracle has no fee model |
| wall (full family, all probes) | ~4 s on one machine, 6.4 s on another; the test file ~7-9 s. Machine-dependent, so deliberately not a manifest invariant |

Scale is deliberately *not* folded into the canonical form: `|M|` is scale-invariant, but
`radix_mappings` and the density gate are not, and folding would have hidden that.

## Semantics first: what each entry point actually counts

Comparing two quantities that count different objects manufactures a defect that is really a
category error. So every entry point is identified before it is compared, and every identification
below is *re-derived in Python* rather than read off a docstring.

| entry point | object | relation to the oracle |
|---|---|---|
| `exact_subtransaction_mappings` | index-level balanced set partitions, coarser readings included | the oracle |
| `dss.mapping_analysis` `n_non_derived` | refinement-maximal mappings on this bounded audit, a strict sub-family of the full oracle | **restriction** |
| `dss.pairwise_link_prob` | the uniform marginal over *that same restricted family* | **restriction** |
| `dss.mapping_analysis` `deterministic_links` | the certain links of *that same restricted family* | **restriction** |
| `dss.w_count` / `w_brute` / `w_sparse` | non-empty **proper input subsets whose sum is a proper output-subset sum**: the subset-sum solution count `W(E)` | **different object** |
| `counting.count_w` (the production router) | radix, else sparse — and the sparse answer is `W(E)` | **different object** |
| `dss.radix_mappings` | permutations of repeated output denominations; a function of the outputs alone | **different object** |
| `dss.per_coin_density` | per-coin `log_w` (natural log), a subset-sum density | **different object** |
| `subtransaction.subtransactions` `ambiguity_bits` | log2 of the (receiver input, receiver output) pairs with a positive implied payment; nothing has to balance | **different object** |

### The matrix, the count and the certain links are one enumeration

An earlier draft of this document called the count a "restriction" and the matrix "the same object".
That cannot both be true, and it is falsified in one line. Checked on all **507/507** transactions
(`verify_dss_marginal_family`):

- every entry of `dss.pairwise_link_prob` is an exact multiple of `1 / n_non_derived`;
- the entries equal to 1.0 are exactly the `deterministic_links` the same call reports.

So all three are outputs of one enumeration over one family, and that family is **strictly smaller
than the oracle's on 491 of 507** cases. They therefore carry one verdict — restriction — and the
consequence is not a caveat but the finding: a marginal over a sub-family bounds the marginal over
the full family in neither direction, which is exactly what the entrywise tallies below measure.

### What `n_non_derived` measures

The current DSS revision exposes refinement-maximal mappings. Its count agrees with the independent
oracle's refinement-maximal count on all 507 cases in this bounded family. This is a measured
agreement, not a proof for every transaction.

Equal-value permutations do **not** collapse in general: `[1,3,4,4] → [3,3,3,3]` answers 4, and
those four readings differ only in which equal-valued output stands alone. The refinement-maximal
family is strictly smaller than the full oracle family on 491 of 507 cases. The matrix and its
certain links therefore remain marginals over a restriction of the full family.

`W(E)` was identified, not assumed: `dss.w_count` reproduces an independent Python re-derivation of
that subset-sum count on **507/507** exact answers (0 mismatches). A set partition is a
simultaneous, disjoint, exhaustive choice of many such subsets, so `W(E)` and `|M|` count different
things — they coincide by accident on 34 of the 507 cases. Ordering one against the other would say
nothing about either, so this audit reports the object mismatch and **declines to score `w_count` as
an under- or overcount**. `w_total`'s own docstring already says as much ("a per-target subset count,
NOT Maurer's full matched-partition mapping count"); what is new here is the verification.

## The comparisons

Every row is the same quantity on both sides, computed over two different mapping families, so
"bound direction" is a measurement and never a licence. The first four rows score against the **full**
oracle family; the two `_finest_only` rows are the robustness reading described below, and there
"finest" means **refinement-maximal** — the choice matters and is measured, see
"None missed is a statement about that definition".

| probe | relation | cases | agree | approx < exact | approx > exact | max abs error | measured bound direction |
|---|---|---|---|---|---|---|---|
| `mapping_count` | restriction | 507 | 16 | **491** | 0 | 107 mappings | **lower** |
| `mapping_entropy_bits` | restriction | 507 | 16 | **491** | 0 | **3.64 bits** | **lower** |
| `link_matrix` (entrywise) | restriction | 507 tx / 6,228 entries | 410 entries | 4,104 entries | **1,714 entries** (in **440** transactions) | **0.833** | **neither** |
| `deterministic_links` | restriction | 507 | 179 | 0 | **328** | 945 spurious links | **upper** |
| `link_matrix_finest_only` | restriction | 507 tx / 6,228 entries | 2,314 entries | 2,103 entries | **1,811 entries** (in **439** transactions) | **0.800** | **neither** |
| `deterministic_links_finest_only` | restriction | 507 | 179 | 0 | **328** | 945 spurious links | **upper** |

Reading the two link rows: the **440** (and 439) are transactions carrying at least one entry above
the oracle's — the number the audit's `flags` reports, since a transaction is where a consumer reads
the matrix. The **179** agreements on `deterministic_links` are the transactions where the two
certain-link sets match exactly.

"Measured bound direction" is measured on *this* family only. `lower` here means no case in these 507
exceeded the oracle; it is not a proof for all transactions, and it says nothing at all about a
fee-paying one.

### The link matrix errs in both directions

Only **16 of 507** transactions agree on every entry.

| transaction | `\|M\|` (exact) | exact marginal | `dss.pairwise_link_prob` |
|---|---|---|---|
| `[1,1,1] → [1,1,1]` | 16 | 0.5 everywhere | identity: 1.0 on the diagonal, 0.0 off it |
| `[1,1,1,1] → [1,1,1,1]` | 131 | 0.405 everywhere | identity |
| `[1,3,4,4] → [3,3,3,3]` | 5 | 0.8 / 0.4 rows | 10 entries at 1.0, 6 at 0.0 |
| `[1,4] → [1,1,1,1,1]` | 6 | 0.333 / 0.833 rows | 5 entries at 1.0, 5 at 0.0 |

Both directions of error are present in a single case, which is why no monotone description survives.
Of the two, the one that matters is the **overclaim**: an entry the approximation calls 1.0 where the
oracle says 0.4 asserts a link the amounts do not settle, and `counting.link_matrix`'s docstring
hands exactly that reading to consumers. 945 such assertions of certainty stand across 328
transactions, and there is no case in the family where the approximation *misses* a link the oracle
calls certain — on certainty the error is one-directional, in exactly the direction that costs a
holder privacy they were told they had. (The 4,104 entries *below* the oracle are the same matrix
being under-confident about merely probable links; both are true, of different quantities.)

**First, note what the 945 is measured against.** The `deterministic_links` probe runs against the
**full** oracle family — every balanced set partition, coarser readings included. That is the largest
family available and therefore the most conservative reading of the overclaim: any sub-family has
*more* certain links, so restricting the oracle can only reduce the spurious count. The primary
finding never calls `finest_mappings` and nothing below changes it.

**The cross-check, and the definition it depends on.** As a robustness reading, the audit also scores
against the oracle's *finest-only* family — here **refinement-maximal**: the mappings no other
mapping strictly refines. Under it the entry tallies move (1,811 above, 2,103 below, 2,314 agreeing)
and the verdict does not: still **neither** bound, still **945** spurious certain links, still none
missed.

**"None missed" is a statement about that definition, and only that one.** Selecting the finest
mappings by *maximum block count* instead keeps a strict subset of the refinement-maximal ones — a
strict refinement always has more blocks, so an argmax-by-block-count mapping is always
refinement-maximal but not conversely. That is a smaller oracle family, hence more oracle
certainties, hence a reading strictly *more generous* to the approximation, and under it the tally
becomes **942 spurious and 108 missed**. The two selections differ on
**106 of 507** cases. Refinement-maximal is kept because it is what "finest" means on a poset of
partitions — not because it is the strongest reading; it is the weaker of the two for the
approximation. Both tallies are measured on every run
(`restriction_evidence.finest_selection_sensitivity`) and both are manifest invariants, so the
sensitivity cannot quietly stop being true.

The mechanism is visible in the equal-value cases. Three coins of equal value in and three out admit
16 balanced mappings and 4.000 bits of mapping entropy; the refinement-maximal family has six
mappings and the resulting matrix still breaks the value symmetry by index. Coin
order carries no information, so an index-diagonal answer to a value-symmetric transaction is the
symmetry being broken by the enumeration order rather than by the amounts.

### The mapping count is a restriction, and a severe one

`n_non_derived` agrees with `|M|` on 16 of 507 cases, and every one of those 16 is a transaction with
exactly one mapping. Where the transaction is ambiguous at all, the two numbers part company: the
largest understatement in this family is 3.64 bits. That is the
undercounting direction, which is the safe one for a refuse-only channel, and `counting.py` already
argues for preferring it. The finding is its size under the declared bounded family.

## Identifications, not comparisons

**`radix_mappings` is input-blind and scale-dependent.** The call takes the outputs and a knee; the
inputs are not a parameter. `counting.radix_applies` is true for 25 of the family's output multisets,
and on all 25 the crate returns a count of **0** at these magnitudes — so on this family the guarded
route never produces a usable bound. Multiply every coin by 1,000 and the count becomes non-zero on
**all 25** while the exact mapping count is unchanged, e.g.

| outputs | radix count | ×1000 outputs | radix count | `\|M\|` (either scale) |
|---|---|---|---|---|
| `[1,1,2,2,2]` | 0 | `[1000,1000,2000,2000,2000]` | 22 | 7 / 21 / 27 / 29, by inputs |
| `[1,2,2,2]` | 0 | `[1000,2000,2000,2000]` | 19 | 4 / 8 / 11 / 16 / 25 / 30 / 53, by inputs |

`|M|` cannot move under a common rescaling — the balance conditions scale with it — and it does
differ across the inputs that fund one output multiset. A quantity blind to a parameter the target
depends on, and sensitive to one it does not, is not a bound on the target.

**`per_coin_density` is coin-invariant where the exact marginals are not.** Its per-coin `log_w` is
identical for every coin of the transaction in **497 of 507** cases, while the exact per-coin maximum
link probability varies across the input coins in **339 of 507**. It is also a natural log, not bits.
No entrywise comparison is offered, because it is not the same object; the reportable fact is
structural — where it is flat it cannot express variation the oracle does show.

**`counting.count_w` (the production router) inherits `w_count`'s object, and the saddle point never
answers.** The router's radix tier never wins on this family — it returns zero, `_resolved` reads
that as no answer, and the route falls through to sparse on 491 of 507 cases (16 resolve to nothing).
Every one of those 491 sparse answers equals the same `W(E)` re-derivation, so the router is a
different object from `|M|` for exactly the reason `w_count` is; 486 come back `exact` and 5
`lower_bound`. `counting.saddle_point_log_w` declines **all 507**, while `counting.is_dense` reads
**443** of them as Dense — the optimistic-gate discrepancy that function's own docstring predicts,
now measured rather than expected.

**`subtransaction.subtransactions` `ambiguity_bits`** covers the 16 two-in/two-out cases. It abstains
on 4 (no positive implied payment), and on the remaining 12 it lands **above** the exact mapping
entropy 6 times and **below** it 6 times, never equal. Its count admits partitions that do not
conserve value, so this is not a bound in either direction — its own docstring already calls it a
count diagnostic and not a privacy quantity, and that reading is confirmed here.

## Self-derived canonical cases

No number here is attributed to any paper: none of the source texts is in this checkout, so a
citation would be fabricated. The canonical cases below are derived from the oracle's own definition
and checked against its enumeration in `tests/test_oracle_audit.py`.

For an *n*-in/*n*-out join of one repeated value, a block of *a* inputs balances exactly the blocks of
*a* outputs, so a mapping is: a set partition of the inputs, a set partition of the outputs with the
same multiset of block sizes, and a size-preserving bijection between them. Writing a shape as sizes
with multiplicities `m_s`, the set partitions of that shape number `n! / (Π_s (s!)^{m_s} · Π_s m_s!)`
and the size-preserving bijections number `Π_s m_s!`, so

    |M|(n) = Σ over shapes of  P(shape)² · Π_s m_s!

| n | derivation | `\|M\|` | entropy |
|---|---|---|---|
| 2 | 1 (one block) + 2 (two singletons, 2 pairings) | **3** | log2 3 = **1.585 bits** |
| 3 | 1 + 9 + 6 | **16** | **4.000 bits** |
| 4 | 1 + 16 + 18 + 72 + 24 | **131** | **7.033 bits** |
| 5 | — | **1,496** | 10.547 bits |

So the canonical equal-value 2-in/2-out join has exactly three mappings — the identity pairing, the
swapped pairing, and the single all-coins block — and log2(3) bits of mapping entropy, with no
deterministic link at all. `dss.pairwise_link_prob` answers that case with an identity matrix.

## What this does and does not establish

- Zero-fee only. Every case here balances exactly; the oracle returns no mapping otherwise. The `dss`
  link paths balance a real fee in as a synthetic extra output, and nothing here measures that path.
- Small only: at most 8 coins, values in `{1,2,3,4}`. Nothing extrapolates to a 16-input mix, which is
  where these approximations are actually used and where the oracle cannot follow.
- No approximation in this repo may be described as a lower bound on the strength of this run. Two
  are measured as under-only *on this family* (`mapping_count`, `mapping_entropy_bits`); the link
  matrix is measured as **neither**, and that is a finding, not a caveat.
- The enumerator behind `n_non_derived` is **not** specified here. This audit sees the count, the
  marginal and the certain-link set — not the mappings — so it reports what that family demonstrably
  is not, and stops there.
- `decluster.oracle`'s subprocess link path and `counting.link_matrix`'s `budget_ms` / `wall_ms`
  refusal behaviour are unprobed: nothing in this family is large enough to trigger a refusal, so
  every call answered and the refusal branch went unmeasured.

## Reproducibility / provenance

The generated family, parameters, dependency identity and complete measurements are stored in the
canonical artifact. The run manifest records its content hash, source revision, environment,
limitations and exact verification command. `tests/test_oracle_audit.py` recomputes the artifact and
checks the generated Markdown, while `tests/test_data_manifest.py` verifies the recorded output
identities. Numeric claims therefore do not depend on parsing this narrative.

Reproduce with:

    .venv/bin/python -m decluster.experiments.exact_oracle_audit reproduce \
        --artifact results/artifacts/exact-oracle-audit-v1.json \
        --markdown results/generated/exact-oracle-audit-v1.md
    .venv/bin/python -m decluster.experiments.exact_oracle_audit verify \
        --artifact results/artifacts/exact-oracle-audit-v1.json \
        --markdown results/generated/exact-oracle-audit-v1.md

The verifier recomputes the full experiment from the artifact's recorded parameters and requires
byte-for-byte equality for both machine-readable and generated presentation artifacts.
