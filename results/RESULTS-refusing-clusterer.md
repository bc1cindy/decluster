# Does declining to apply CIOH blindly change the 2026 picture?

> **The slice-scale numbers below are pending re-execution and must not be cited.** They were
> measured under a `monitor.is_coinjoin` that no longer exists: at the time it recognised only
> the many-in/many-out shape, and commit `24caeed` added a second arm that also refuses on a
> repeated output denomination. They were also measured over `slice_2026.ndjson`, which is
> **not in this checkout**, so they cannot be re-labelled as "the 20/20 rule" and left standing —
> the rule that produced them is gone and the data that would settle the difference is gone with
> it. The rule's effect on the only slice this checkout can still measure is in
> **[What the current rule actually does](#what-the-current-rule-actually-does)** below, which is
> re-runnable and is what a reader should use.

**Why ask.** `RESULTS-contraction-2026.md` flagged its own clustering as a deliberate
simplification: naive common-input union-find is precisely the adversary the framework calls
incompetent, and its largest cluster, 30 304 addresses, was suspected of being a merge
artifact rather than one owner. This measures what a refusing clusterer actually changes.

**What was implemented.** Two refusal channels, both decidable from the spending transaction
alone, so both survive at slice scale:

- **coinjoin shape** — where co-spending stops implying common ownership, no input merges with
  any other. This is the framework's own stated rule for the cautious adversary. It is now two
  rules rather than one (`decluster/monitor.py:44-81`): the original **many-in/many-out** test,
  twenty inputs *and* twenty outputs, and an **equal-output** test that fires on three or more
  inputs against three or more outputs sharing one value. The second is the defining structure
  of an equal-amount coinjoin — one interchangeable denomination per participant — and the size
  rule cannot see it: a five-participant Whirlpool round is 5-in/5-out, far under any
  participant threshold.
- **de-mix partition** — where `coinjoin_demix` resolves inputs to distinct participants,
  only same-participant inputs merge, and an input it cannot resolve merges with nobody.
  Returning the partition rather than per-pair verdicts is what keeps this linear.

## What the current rule actually does

Measured on `sample.ndjson` — 5,491 transactions over blocks 812,695–812,831, the only
contiguous slice in this checkout carrying prevout values, and so the only one on which the
equal-output arm can fire at all. The denominator is the **934 transactions with two or more
distinct input addresses**, which is the population that presents a CIOH merge decision; the
1,428 with two or more inputs is the wrong denominator, since a transaction spending two coins
of one address merges nothing.

| rule | fires on | share of 934 |
|---|---:|---:|
| many-in/many-out (≥ 20 in and ≥ 20 out) | 12 | 1.28 % |
| equal-output group (≥ 3 in and ≥ 3 equal outputs) | 22 | 2.36 % |
| **either — the rule as it now stands** | **26** | **2.78 %** |

The partition it produces, over the whole sample:

| clustering | addresses | clusters |
|---|---:|---:|
| naive CIOH | 9,960 | 889 |
| refuse, many-in/many-out only | 9,191 | 881 |
| **refuse, current rule** | **9,109** | **868** |

The equal-output arm newly refuses **16 transactions**, **14** of which have two or more
distinct input addresses and so actually move the partition: **82 further addresses withheld
across 13 further clusters**. The refusal is roughly 2.2× wider than the size rule alone on
this slice — which is the correction the superseded numbers above most need.

**Two things that qualify it.**

*Two of the fourteen are batch shapes, not mixes.* Their in/out/largest-equal-group triples are
`(3, 196, 3)` and `(11, 238, 7)`: three and seven repeated values among 196 and 238 outputs.
That is far more likely a batcher paying several recipients the same amount than a mix
denomination. The error direction is conservative — the rule refuses a merge it should have
made — so it costs recall, not correctness, but it means the 2.78 % is an upper reading of how
much genuine mixing is present.

*The arm is structurally inert on address-only exports.* `equal_output_group` reads output
values, and the graph-scale exports do not carry them. Over `_span6m.ndjson` — 960,717
transactions, none of them carrying a single output value — it fires **zero** times, while the
size rule fires 1,140 times. Any refusal figure measured on an `epoch_2016_*`-shaped export,
here or in a sibling document, is therefore still the many-in/many-out rule alone and should be
read as such.

## Superseded slice-scale result

Everything in this section is under the banner: measured under the size rule alone, over
`slice_2026.ndjson` (831 770 transactions, of which **141 452 (17.0 %) have two or more distinct
input addresses**), which is not in this checkout. Retained as a record of what was run, not as
a current figure.

| | fires on | share of multi-input txs |
|---|---:|---:|
| coinjoin shape (≥ 20 in and ≥ 20 out) | 409 | 0.29 % |
| de-mix partition | 58 | 0.04 % |
| **either** | **467** | **0.33 %** |

| clustering | addresses | clusters | five largest |
|---|---:|---:|---|
| naive | 633 933 | 55 850 | 30 304, 21 912, 15 216, 15 177, 11 556 |
| refusing | 605 463 | 55 515 | 30 304, 21 912, 15 216, 14 859, 11 556 |

Downstream, matcher margin over a degree-only guess at eccentricity ≥ 5, seed 400:

| clustering | edges | spanning | links | margin over degree |
|---|---:|---:|---:|---:|
| naive | 534 652 | 33 033 | 61 | +0.257 |
| refusing | 525 010 | 32 857 | 59 | +0.229 |

*(This row was re-measured after the edge-attribution fix in `RESULTS-graph-shape.md`. The
earlier version compared the naive graph against a refusing graph with four times too many
edges — 4.4M against 534k — so it was not a fair comparison even though it happened to give
similar precision. With both graphs corrected to comparable edge counts the two remain
indistinguishable, so the "inert" conclusion held for the right reason **at the rule strength
then in force**.)*

## Reading

**The refusal is narrow, and how narrow is now an open question at slice scale.** On the slice
this checkout can still measure it touches 2.78 % of merge decisions rather than the 0.33 %
recorded above, so the "inert" verdict and the matcher-margin comparison that supported it
(+0.257 → +0.229) both rest on a rule strength that no longer holds. Whether a 2.2×-wider
refusal moves the margin is exactly what the re-run has to answer; nothing here should be read
as having answered it.

**The mega-clusters were untouched by the size rule.** 30 304 and 21 912 came out identical
under both arms of the superseded run. They are not built from many-in/many-out or de-mixable
transactions; they are built from ordinary multi-input consolidations that neither rule could
see. Whether the equal-output arm reaches them is untested — it needs output values, and the
2026 slice would have to be re-exported with them.

**And the fingerprint channel is unavailable for a reason worth naming precisely.** The
fingerprint refusal compares the *funding* transactions of two co-spent coins, not the
transaction that spends them. For a two-day slice those funders lie almost entirely outside it.
The limitation is data, not algorithm, and the requirement it implies is bounded and specific:
one hop back from every in-slice input. That is the concrete change a future export needs
in order to test the cautious adversary properly.

**Neither arm is calibrated, and they fail in opposite directions.** Twenty-in-and-twenty-out
is strict: most collaborative transactions, payjoins above all, look nothing like that, and on
`sample.ndjson` it reaches 1.28 % of merge decisions. Three equal outputs is loose enough to
catch batch payments, as the two shapes above show. Both thresholds are defaults rather than
findings, and where between them the right rule sits is an empirical question this does not
answer. Neither arm sees a payjoin at all: two inputs against two outputs is the shape a
payjoin is built to wear, and detecting it needs the amount channel, not a shape rule.

## Scope

Two refusal channels of the engine's five. The roundness channel is deliberately excluded
rather than merely absent: it is gated on the fingerprint disagreeing, and used alone it
would refuse ordinary round payments. Provenance is out for the same reason as
fingerprints. Single slice, single month.

## Reproducibility / provenance

The refusal **mechanism** (net-bit-balance keep/reject, refuse-edges, coinjoin-shape and
de-mix rules) is unit-tested and pinned in `tests/test_cluster_refined.py` and
`tests/test_cluster.py`. The `sample.ndjson` table is a **data-run** over a local, unversioned
file that is present in this checkout, recomputable from `decluster.monitor.is_coinjoin` and
`decluster.views.cluster_addresses`, and not asserted as a pinned value. The slice-scale
figures under the banner are a data-run over `slice_2026.ndjson`, which is **absent**, under a
rule that has since changed; they are neither recomputable nor re-labellable and stand only as
a historical record.
