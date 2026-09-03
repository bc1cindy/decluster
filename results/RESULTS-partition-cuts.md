# Which cut makes two matchable views — temporal, de-core, or cluster-collapse

## Verdict

The framework names the temporal cut as its own trivial example and asks for a cut along
cluster-collapse regions instead. Both are now implemented and measured on the same slice against
the same matcher. The result is a **clean negative for the cut criterion and a clear positive for
retiring `decore`**: cutting along collapse events costs 1.7% of the transactions and leaves every
figure within noise of the temporal baseline, while the previous "clever" scheme, `decore`, is
actively harmful. The one partition choice that does move the precondition is the number of views.

## The three cuts

All three produce two or more views of one slice; `split_clusters_by_view` then gives a straddling
cluster a distinct pseudonym per view and the matcher must rejoin them from structure alone.

| scheme | what it removes |
|---|---|
| `epoch` | nothing — splits by block height |
| `decore` | the busiest `core_frac` of addresses, then splits the survivors by height |
| `collapse` | the transactions whose common-input merge would fuse two clusters that are each already `min_side` or larger, then splits the survivors by height |

`collapse` detects and refuses in one pass, so the clusters that survive are the ones the declined
merges never joined: the boundary is a boundary of the clustering it produces. A merge that attaches
a fresh address to one cluster only grows it and is never a collapse.

## Result — 300,000 transactions, blocks 391182–392111

| scheme | boundary txs | pairs to rejoin | straddler edges | mean straddler degree | non-isolated | correct @ 10% seed |
|---|---:|---:|---:|---:|---:|---:|
| `epoch` | 0 | 2,562 | 1,910 | 1.45 | 44.7% | 1 |
| `decore` | **117,371 (39.1%)** | 1,294 | 360 | **0.55** | 28.3% | 0 |
| `collapse` | 4,989 (1.7%) | 2,536 | 1,941 | **1.49** | 44.5% | 1 |

**`decore` cuts the wrong thing.** Dropping the busiest 1% of addresses removes 39% of the
transactions, halves the rejoinable population and takes the straddler subgraph's mean degree from
1.45 to 0.55 — from marginal to hopeless. It cuts by degree, and degree is where the recurring
relationships live: the hubs it discards as ambiguous noise are carrying most of the structure the
matcher propagates along. It should not be used.

**`collapse` is nearly free and slightly better than doing nothing.** 4,989 collapse events in
300,000 transactions, and removing them leaves the population intact and the straddler degree
marginally higher than the temporal baseline (1.49 against 1.45) — consistent with collapse merges
being noise that dilutes genuine neighbourhoods. But it does not change the regime.

## Threshold sweep — the effect is flat

| `min_side` | boundary txs | pairs | mean straddler degree | correct @ 10% |
|---:|---:|---:|---:|---:|
| 2 | 4,989 | 2,536 | 1.49 | 1 |
| 3 | 4,264 | 2,536 | 1.37 | 1 |
| 5 | 3,220 | 2,542 | 1.38 | 1 |
| 10 | 1,948 | 2,546 | 1.40 | 1 |
| 25 | 488 | 2,562 | 1.44 | 1 |

Non-monotonic between 1.37 and 1.49 against a 1.45 baseline, converging on the baseline as the
threshold rises and fewer transactions are cut. That is noise in which transactions happen to be
removed, not a signal from the criterion. The matching result is identical at every setting,
including at no cut at all.

The reason is prevalence: on this data a collapse event is 0.16%–1.7% of transactions. The
framework's hypothesis — that cutting along collapse regions leaves sparser, more matchable
components — presupposes that collapse regions are a substantial structuring feature of the graph.
Here they are not, so the cut has almost nothing to act on. That is a property of the data, and it
would be worth re-testing on an era with heavy coinjoin activity, where collapse events are common.

## Number of views — the one choice that moves the precondition

`collapse`, `min_side=2`, splitting the survivors into narrower height bands:

| views | pairs to rejoin | straddler edges | mean straddler degree | non-isolated | correct @ 10% |
|---:|---:|---:|---:|---:|---:|
| 2 | 2,536 | 1,941 | 1.49 | 44.5% | 1 |
| 3 | 1,760 | 1,529 | **1.70** | 47.4% | 1 |
| 4 | 1,371 | 1,238 | **1.77** | 48.9% | 0 |

Narrowing the views raises mean straddler degree by 19% and the non-isolated share by four points.
The mechanism is selection: a cluster that straddles two *narrow* adjacent windows is one that was
active in both, and consistently active entities have denser neighbourhoods. It is the first
partition choice measured here that moves the precondition in the right direction.

It does not convert. The population falls faster than the density rises — 2,536 to 1,371 — and by
four views the single correct rejoin is gone. Density and population trade against each other along
this axis, and at this scale the trade is not favourable.

## Reading

The cut criterion is not the binding constraint. Three different cuts, a five-point threshold sweep
and a three-point view-count sweep all land on the same matching outcome, while the one scheme that
differs does so by destroying the signal. What separates a matchable pair of views from an
unmatchable one on this data is not where the boundary is drawn but whether the same economic
neighbourhood recurs across it, and that is a property of the underlying activity
(`RESULTS-multiepoch-local-2016.md`).

`decore` is retired as a recommendation. `collapse` replaces it as the non-trivial cut, on the
grounds that it costs almost nothing and is the construction the framework actually asks for — not
on the grounds that it was measured to help, because it was not.

## Scope

One slice, one era, one 300k-transaction prefix. The straddler-degree differences between `epoch`
and `collapse` are small enough that they should not be read as an ordering. The n>2 result is a
single sweep at one `min_side`. The export carries addresses but no output values, so the collapse
detector sees only the shape rule and never the de-mix arm.

## Reproducibility / provenance

Per `results/REPRODUCIBILITY.md`, state 2: **mechanism unit-tested, headline number is a data-run.**
`collapse_boundary` and `collapse_partition` are pinned in `tests/test_views.py` (the merge of two
substantial clusters is cut, a fresh address joining one cluster is not, the boundary lands in no
view, and n>2 partitions the sample without loss or duplication). The tables here are regenerated by
`examples/analyze_decore.py --scheme {epoch,decore,collapse}` over `data/epochs_2016_weekly/`, which
is local and unversioned, and are not asserted.
