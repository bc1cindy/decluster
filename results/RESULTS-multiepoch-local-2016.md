# Local multi-epoch social-graph run — January 2016

## Verdict

The cross-view attack runs locally on an 8 GB M2 over complete weekly views. It does **not** ignite:
one correct rejoin out of 15,688 candidate pairs at a 10% seed, with every shuffled-seed control at
zero. But the precondition it needs is far closer than the first pass reported — 46.5% of rejoinable
pseudonyms now share at least one recurring cross-view neighbour, against 7.7% before. The barrier is
still the recurring neighbourhood, not the transaction count.

## Correction — this supersedes the first pass

The figures published here on 2 September were produced by a harness carrying two defects. Both are
fixed and pinned; every number below is from the corrected path.

**The view split leaked.** `split_clusters_by_view` tagged each address by which side it was first
seen on, so an address used in *both* windows was marked `#a` globally and reappeared as a vertex of
view B. Two consequences, pulling in opposite directions: the identity match `C#a → C#a` was
available in view B, structurally the better match and graded wrong; and a cluster whose shared
address dominated it never produced a `#b` vertex at all, so it was silently dropped from the
evaluation set. The rejoinable population was undercounted by a factor of 2.3. Each view is now
contracted under its own lookup (`views.view_lookup`), which is also the framework's own
construction — each epoch clustered separately.

**The active-vertex filter invented edges.** `views.contract` intersected the source set with `keep`
*before* testing it against `max_sources`, so a multi-source transaction the contraction had refused
to attribute emitted an edge as soon as the filter left it a single source — and the survivor is
systematically the hub. The `max_sources` bound is now evaluated on the transaction's own sources.
This inflated the straddler subgraph's mean degree.

Regression tests: `test_an_address_used_in_both_windows_does_not_carry_its_tag_into_the_other_view`
and `test_keep_drops_edges_and_never_invents_one`, both in `tests/test_views.py`.

## Data and reproducibility

Source: `epoch_2016_01.ndjson.gz`, split once into 1008-block chunks by `examples/split_epochs.py`.
The five chunks contain exactly 5,936,758 transactions and the local
`data/epochs_2016_weekly/manifest.json` records their height ranges and SHA-256 hashes.

```bash
.venv/bin/python examples/analyze_multiepoch.py 1 \
  data/epochs_2016_weekly/epoch_2016_01_391104-392111.ndjson.gz \
  data/epochs_2016_weekly/epoch_2016_01_392112-393119.ndjson.gz \
  --controls
```

The default runner uses directed matching and the high-confidence minimum of four mapped common
neighbours. `--controls` adds the undirected and shuffled-seed arms; `--auto-seeds` enables the
costly experimental seed heuristic, which must stay opt-in and must not feed the attack.

## Scale curve

| cap per view | total tx ceiling | pairs to rejoin | mean internal degree | recurring mean | support >=1 | support >=4 | peak RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 300,000 | 600,000 | 5,069 | 1.537 | 0.761 | 1,330 (26.2%) | 131 (2.58%) | 0.78 GB |
| 600,000 | 1,200,000 | 10,388 | 2.090 | 1.019 | 3,398 (32.7%) | 258 (2.48%) | 1.11 GB |
| complete | 2,098,584 | 17,431 | 2.866 | 1.516 | 8,105 (46.5%) | 466 (2.67%) | 1.38 GB |

The complete views contain 982,021 and 1,116,563 transactions. Against the first pass, the rejoinable
population is 2.3× larger and mean recurring support is 6.2× higher, while mean internal degree fell
from 3.46 to 2.87 once the invented edges were removed.

Everything grows with the prefix except the one quantity the attack gates on. The share reaching four
recurring neighbours — the high-confidence stage's own minimum — reads 2.58%, 2.48%, 2.67% across a
3.5× range of transactions: flat, and not even monotonic. Mean support and the ≥1 share both roughly
double over the same range, so the population is acquiring *a* recurring neighbour and not a
neighbourhood. Density inside a view is therefore not the missing quantity; the same economic
neighbourhood recurring in the other view is.

## Matching result

Complete views, ground-truth highest-degree seeds:

| seed share | matcher | new guesses | correct | precision |
|---:|---|---:|---:|---:|
| 5% | undirected | 0 | 0 | — |
| 5% | directed | 0 | 0 | — |
| 10% | undirected | 0 | 0 | — |
| 10% | directed | 1 | **1** | 1.000 |

All four shuffled-seed controls produced zero guesses. The first pass reported the directed matcher's
single inference as *incorrect*; on the corrected construction the same configuration produces one
correct rejoin and no false positive. One match out of 15,688 non-seed pairs is not ignition and
supports no claim on its own — recall rounds to zero. What it does establish is that the matcher's
high-confidence path is not inert, and that the shuffle arm separates from it.

## Temporal separation control — the first pass had this backwards

The first and last January chunks give a three-week gap (982,021 and 1,170,182 transactions):

| views | pairs | vertices A | assortativity | internal degree | recurring mean | support >=1 | support >=4 | peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| adjacent | 17,431 | 588,843 | -0.076 | 2.866 | 1.516 | 46.5% | 2.67% | 1.64 GB |
| three weeks apart | 11,612 | 589,194 | -0.085 | 2.723 | 1.302 | 41.4% | 2.44% | 2.31 GB |

The first pass measured recurring support rising from 0.244 to 0.340 with the wider gap and read that
as a positive trend in the precondition, nominating longer separation as the next experiment. On the
corrected path the ordering **reverses**: the adjacent pair is better on every precondition figure,
and the wider gap also loses a third of the rejoinable population. Both matched at zero, all arms.

Widening the temporal gap is therefore not the way forward. Economic relationships that recur within
one week recur less across three, which is the opposite of the stability the cited construction wants
and is consistent with the graph being transactional rather than social.

## Do these relationships repeat at all?

The cross-view attack needs a neighbourhood that recurs. Until now that was only measurable *across*
the boundary, which conflates two different failures: a relationship that never repeated, and one
that repeated but not into the other view. Contraction now labels each edge with the block-height
span of the transfers it folds — Reid and Harrigan put value *and* time on every user-network edge —
so the first can be measured inside one view.

| edges in view A | fold more than one transfer | mean span of those |
|---|---:|---:|
| all, 300k prefix | 20,798 / 267,449 — **7.78%** | 251 blocks (~1.7 days) |
| straddler subgraph, 300k prefix | 1,586 / 4,139 — **38.32%** | 425 blocks (~3 days) |
| all, complete view | 124,245 / 1,430,236 — **8.69%** | 266 blocks |
| straddler subgraph, complete view | 10,270 / 26,315 — **39.03%** | 436 blocks |

The ratio is stable across a 4.8× change in graph size: straddler relationships recur about
4.5 times as often as the graph's relationships in general, at both scales.

**92% of cluster-to-cluster relationships in this graph fire exactly once.** The pseudonym graph is
overwhelmingly transactional in the most literal sense: most edges are a single payment that never
recurs, which is what the disassortativity (−0.11) has been saying structurally all along.

That number is not new to the repository, and its independence is worth stating:
`RESULTS-contraction-2026.md` measured 7.2% and 7.0% on a 2026 slice and concluded "most cluster
relationships in a single day are one-shot". 7.78% here, on a different era, a different collection
and a different code path, reproduces it. The one-off character of the pseudonym graph appears to be
stable across a decade of chain history rather than an artefact of either sample.

But the straddlers are **five times more recurrent** than the graph they sit in. That is partly
selection — a cluster that straddles two windows was active in both — and it is the encouraging half
of the measurement: among the pseudonyms the attack actually targets, more than a third of the
relationships do repeat, over a mean span of three days.

So the negative is now located precisely. It is **not** that these entities have no repeating
relationships; they do, inside a view. It is that the *same neighbourhood* does not survive the
boundary: mean cross-view support 1.516, with only 2.67% reaching the four mapped common neighbours
the high-confidence stage requires. Recurrence exists and does not transfer.

That distinction matters for what to try next, because the two failures have different remedies. A
graph with no recurrence at all would be a dead end. A graph whose recurrence does not cross a
particular boundary is an argument about where the boundary is drawn and how wide the windows are —
and `RESULTS-partition-cuts.md` reports that moving the boundary does not help, while narrowing the
windows raises straddler density but shrinks the population faster.

## The `max_sources=1` bound costs almost nothing here, and the reason is structural

`views.contract` refuses to attribute a transaction funded by more than one source pseudonym, on
the grounds that asserting every source-destination pair invents relationships. A reasonable
objection is that this discards most of the graph — Reid and Harrigan's user-network edge is an
input-output pair of a single transaction, so a bound of one drops every multi-source transfer.

Measured on view A of the 300k prefix, it does not:

| sources per transaction | transactions | share |
|---:|---:|---:|
| 1 | 299,465 | **99.82%** |
| 2–12 | 534 | 0.18% |
| 72 | 1 | 0.00% |

Only 535 transactions in 300,000 have more than one source pseudonym, and the bound keeps 73.9% of
the potential source-destination pairs; raising it to 20 buys 6.9 points and removing it entirely
buys 26, almost all of that from a handful of very wide transactions.

The reason is that the clustering *is* common-input ownership: every input of a merged transaction
is in one cluster by construction, so a transaction can only present several sources when the
clusterer **declined** to merge them — which is to say, in exactly the coinjoins where which
participant paid which output is unobservable. The bound and the refusal are the same decision seen
twice, and the bound is nearly free because the refusal already did the work.

This is dataset-dependent and should not be generalised. The 4.4M-to-534k figure in the module
docstring comes from a 2026 slice with far more consolidation; there the bound is doing much more
work and the trade deserves its own measurement.

## The amount channel is absent from this data, and from every graph fixture

Worth stating plainly because it bounds what the refusal in this pipeline can be. The multi-epoch
export carries only `height`, `txid` and the input/output **addresses** — no output values. So does
every committed graph fixture (`slice_a_channels_2016`, `graph_deanon_2016`,
`entity_satoshidice_2013`): 0 of 36,562 transactions across the three carry a value.

Three consequences, none of them visible from the numbers above:

- `coinjoin_demix` needs input and output values, so `views._demix_participants` returns `None` for
  every transaction here and the de-mix arm of the refusing clusterer never fires. Refusal on
  graph-scale data is the shape rule alone.
- The equal-amount detector added to `monitor.is_coinjoin` is structurally blind on this export. It
  refuses 0 additional transactions in 600,000 — a property of the collection, not of 2016.
- Nothing in this pipeline exercises the unnecessary-input heuristic or conservation either.

The amount channel and the graph channel are measured on disjoint datasets. Reading either result
as if the other channel were present would overstate both.

## Memory result

Unaffected by the two corrections — the union-find profile is upstream of both. The compact
union-find and the dictionary reference produce identical cluster counts at every scale:

| transactions | clusters | dict RSS / time | compact RSS / time |
|---:|---:|---:|---:|
| 300,000 | 96,991 | 91.7 MB / 2.02 s | 83.0 MB / 2.51 s |
| 1,000,000 | 287,931 | 160.1 MB / 6.38 s | 191.9 MB / 7.67 s |
| 3,000,000 | 757,606 | 492.7 MB / 18.35 s | 392.3 MB / 22.79 s |

Measured against `epoch_2016_01.ndjson.gz` (the unsplit monthly export; the weekly chunks give
different cluster counts at the same prefix). The earlier "~10x less memory" statement described only
the final parent-cell representation and was not true end to end: the saving at 3M transactions is
about 20–24%, for about 24–33% more runtime.

Whole-pipeline peak is dominated by contraction, not union-find. Two optimisations were taken:
`PseudonymGraph` no longer allocates the per-axis counters when `axes=False` (they were the vertex
record's bulk, 681 B against 191 B), and `views.contract_degrees` replaces the throwaway first
contraction whose only product was the unfiltered degrees. On the complete adjacent pair:

| stage | before | after |
|---|---:|---:|
| contract-a | 88.1 s / 1404.3 MB | 34.6 s / 1135.4 MB |
| contract-b | 116.8 s / **1636.1 MB** | 47.7 s / **1461.0 MB** |

The peak includes the height span later added to every edge — two integers across 1.43M edges, about
85 MB, which is what the temporal attribute costs at this scale. Timings and RSS above are from the
run that has it; the pre-span figure was 1376.6 MB.

Every reported figure is unchanged — pairs, vertices, assortativity, straddler edges, recurring
support and the single correct match all identical. That equivalence is not inferred from the run: on
the real 300k window `contract_degrees` was checked against the graph it replaces and returns an
identical degree map (590,344 entries) and an identical keep set (200,707), and the filtered graph
built with the slimmed vertex record has the same vertex set, the same *insertion order*, the same
edges with the same attributes, and the same unattributed count. Pinned in `tests/test_views.py`.

Insertion order matters here and is worth stating: the matcher breaks score ties on iteration order,
so a change that only reorders a set can move a marginal guess. It was preserved deliberately.

What is left is the vertex identity itself. Pseudonyms are strings like `"391182#a"` and adjacency is
a dict of sets; dense integer ids with CSR adjacency are the next tier, worth roughly an order of
magnitude on the contracted graph, and are what a month-per-view run would need.

## Interpretation and next experiment

This remains a qualified negative for week-scale views, not a falsification of graph
de-anonymization — but it is now a *clean* one, and the precondition is nearer than it looked. The
two experiments the first pass proposed are both retired: across a 3.5× range of transactions the ≥4
share stays flat at 2.5–2.7%, and widening the temporal gap makes every figure worse.

What the corrected numbers point at instead is the gate and the scorer, not the data volume. 2.67% of
pseudonyms clear four recurring neighbours; the matcher abstains on the rest by construction. The
informative next runs are therefore internal: sweep `min_common` from 4 down to 2 with the shuffle
arm carried alongside to price the precision lost, and compare the current rarity-weighted damping
against the cited candidate-degree normalisation on the same graph. Both are configuration, not
collection.

## Reproducibility / provenance

Per `results/REPRODUCIBILITY.md`, state 2: **mechanism unit-tested, headline number is a data-run.**
The matcher, the view split, the contraction bound and the compact clustering are pinned in
`tests/test_view_match.py`, `tests/test_views.py` and `tests/test_scale_cluster.py`. The tables here
are regenerated by `examples/analyze_multiepoch.py` and `examples/profile_scale.py` over
`data/epochs_2016_weekly/`, which is local and unversioned (gitignored), and are not asserted. The
manifest's SHA-256 hashes identify the exact chunks used.
