# Provenance overlap: what ranking by descended inputs does and does not isolate

`decluster/provenance.py`. The module's premise is that a round a participant joined shows a share of
its inputs descending from that participant's earlier transactions, while unrelated rounds show a
background rate — so ranking rounds by that share narrows a few hundred inputs to a few dozen
candidates. This measures the premise.

## Population

Every ordered pair of the 129 coinjoins in the local cache, scored with `overlap_share` — the
fraction of the child's inputs spending an output of the parent.

| | |
|---|---:|
| pairs with any overlap | **1828** of 16512 (11%) |
| median overlap, where nonzero | 0.0065 |
| 90th percentile | 0.0508 |
| maximum | 0.2019 |

The first row is the finding that matters for the premise: coinjoin-to-coinjoin overlap is **common**,
not exceptional. In a remixing population, rounds routinely consume each other's outputs, so a
nonzero share is not by itself evidence of anything.

## Where a known chain lands

Five consecutive hops of a six-round chain in which one participant re-registers the previous round's
change — each hop confirmed by walking the spend forward, so the relation is known independently of
this measure:

| hop | overlap | rank of 1828 |
|---|---:|---:|
| 1 → 2 | 0.0531 | 176 |
| 2 → 3 | 0.1123 | 47 |
| 3 → 4 | **0.1918** | **2** |
| 4 → 5 | 0.1622 | 8 |
| 5 → 6 | 0.0102 | 607 |

Three of five land in the top 3% of pairs that overlap at all, and one is second overall. Two do not:
the first hop sits at roughly the 90th percentile, and the last is near the median, indistinguishable
from ordinary remixing.

**So the ranking narrows but does not isolate.** It is a cut worth taking — the top of the list is
enriched — and it is not a test: a hop of a known chain can sit at the median, and the pair ranked
first is not one of them.

## Complementary to conservation, not redundant

The two channels peak at opposite ends of the same chain. Conservation forces outputs where a
participant is large by **value**: it bites on rounds 1–3, where they hold 69%, 75% and 52% of the
round's input, and forces nothing at 2.2%, 0.2% and 0.0% (`RESULTS-conservation.md`). Provenance
overlap ranks by how many **coins** flow forward, and peaks at hops 3→4 and 4→5 — exactly where the
participant's value share has collapsed but their coin count has not.

Neither is a substitute for the other, and the chain is only covered because they fail in different
places.

## What this population is not

The cache was assembled by walking one chain and its neighbourhood, so it over-represents
interconnection: 11% of pairs overlapping is a property of *this* set, not a background rate for
mainnet coinjoins. The ranks are positions within a remixing population — which is the hard case for
the premise, and the reason the negative half of the result is the more trustworthy half.

## Reproduce

```python
from decluster.provenance import overlap_share   # over cached coinjoins, offline
overlap_share(child_tx, {parent_txid})
```
