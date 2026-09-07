# Does widening the view recover the neighbourhoods the matcher needs?

**Why ask.** `RESULTS-view-match-2026.md` finds the matcher's frontier collapses on its
first step: of the 400 seeds' 15 324 neighbours, only 14 % were present and linked in the
other view. The framework's mechanism requires *recurring* relationships, and at a one-day
view width most relationships do not recur. View width is the obvious untested lever, but
testing it properly means a much larger export and a run near the memory ceiling. This
measures the lever first, cheaply.

**Data.** 14 days from block 939 969 (2026-03), all 2 016 blocks present. Day 0 = 939 969.
View A = days [0, w), view B = days [7, 7 + w); at w = 7 they abut without overlapping.
Computed entirely in SQL with per-day bitmasks, so every width comes out of one
aggregation: 3.7 GB scanned, 23 s. `bigquery/persistence_curve.sql`.

**Metric.** For each address with degree ≥ 3 in view A and any activity in view B, the
share of its A-neighbours that are also active in B. This is address-level (union-find does
not fit in SQL) and uses the looser test *present in B* rather than *present and linked in
both*, so the absolute level is not comparable with the 14 % above. The trend across
widths is the quantity of interest and is measured consistently.

## Result

| view width | core vertices | mean degree in A | persistence, pooled | persistence, mean per vertex | vertices with ≥ 3 surviving neighbours |
|---:|---:|---:|---:|---:|---:|
| 1 day | 30 335 | 15.71 | 0.200 | 0.312 | 5 929 |
| 2 days | 68 896 | 14.83 | 0.233 | 0.347 | 16 312 |
| 3 days | 116 471 | 15.21 | 0.258 | 0.380 | 34 359 |
| 5 days | 212 460 | 17.23 | 0.248 | 0.383 | 70 372 |
| 7 days | 305 402 | 22.33 | 0.205 | 0.383 | 110 017 |

## Reading

**Widening helps, but it is not a phase change.** Per-vertex persistence rises from 31 % to
38 % and saturates by day three. Past that, a wider window adds relationships without
adding persistent ones. Whatever makes a counterparty a one-off is not fixed by watching
longer.

**The volume grows far more than the rate.** Vertices holding three or more surviving
neighbours go from 5 929 to 110 017, roughly eighteenfold. Combined with the rate, a core
vertex carries about 4.9 persistent neighbours at one day and about 8.5 at seven. Nearly
double, on eighteen times as many vertices.

**Pooled and per-vertex persistence diverge at width seven** (0.205 against 0.383), which
says the highest-degree vertices persist *worst*: a hub touches many counterparties once
and never again. The matcher refuses to route through hubs anyway, so the per-vertex figure
is the one that bears on it, and the divergence is a reason to keep the hub cap rather than
a problem.

## What this sets up

A week-wide run is worth doing and should not be expected to transform the result. The
expectation it sets: substantially more matches in absolute terms, from an eighteenfold
larger usable population, on a per-seed yield that improves by something closer to a factor
of two than to an order of magnitude. If the cascade fails to ignite there too, the
constraint is not view width and the negative result is a good deal stronger.

Width three is where the rate saturates; width seven is where the volume is. A run should
use seven and report both.

## Reproducibility / provenance

Not yet filed against `results/REPRODUCIBILITY.md`. This document has not been assigned one of the
five evidence states, so read its numbers as unclassified rather than as any of them.
