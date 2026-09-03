# Does clustering the conspicuous transactions first change anything?

## Verdict

No. On a contiguous 137-block slice with complete transaction data, ordering the merges by how
little each argues against itself produces a **partition identical** to block order. What does
change the partition is the state-dependent gate the ordering was supposed to feed: declining a
doubted merge that would fuse two already-established clusters takes the slice from 868 to 1,117
clusters. The ordering is inert; the gate is not.

## Data

`sample.ndjson`: 5,491 transactions over blocks 812,695–812,831, every one carrying prevout values
and script types, 1,428 of them multi-input. This is the only contiguous slice in the repository
that supports the amount channel — the graph-scale exports (`epoch_2016_*`, the committed graph
fixtures) carry addresses only, and the fingerprint survey is aggregate rather than per-transaction.

## What the transactions say against themselves

`merge_objections` counts the published tells that argue against reading a transaction's inputs as
one owner: an input that already covers the largest output (the unnecessary-input heuristics), and
inputs that disagree on script type. Over the 1,428 multi-input transactions:

| objections | transactions | share |
|---:|---:|---:|
| 0 | 513 | 35.9% |
| 1 | 820 | 57.4% |
| 2 | 95 | 6.6% |
| unrankable | 0 | — |

**Only 36% of multi-input transactions are unambiguous.** Blind common-input ownership merges the
other 64% regardless. That is a substantial amount of doubt for a clustering to be spending, and it
is the quantity the refusal exists to act on.

## What each rule does to the partition

| configuration | clusters | largest | addresses clustered |
|---|---:|---:|---:|
| naive CIOH | 889 | 996 | 9,960 |
| refuse (shape + de-mix), block order | 868 | 996 | 9,109 |
| refuse, conspicuous-first | 868 | 996 | 9,109 |
| refuse + doubt gate, block order | 1,117 | 996 | 9,257 |
| refuse + doubt gate, conspicuous-first | 1,117 | 996 | 9,257 |

- Refusal changes the partition: **yes**
- The doubt gate changes it: **yes** (868 → 1,117)
- The **order** changes it: **no** — the two gated runs are identical, and so are the two ungated ones

The largest cluster is 996 addresses in every configuration, including naive. Nothing here prevents
it, which says it is assembled from transactions that raise no objection — a genuinely conspicuous
entity, or one whose collapse happens through evidence none of these rules examines.

## Why the order is inert

Union-find over a fixed set of merges is order-independent, so ordering can only matter through a
decision that reads the partition built so far. The refusal rules do not: the coinjoin shape and the
de-mix both read the spending transaction alone. Adding a state-dependent decision — the doubt gate
— makes the partition move, but not with the order, because at a two-address threshold a cluster
becomes "established" almost immediately and the verdict is the same whenever it is taken.

That is a property of this gate, not a refutation of the idea. A gate whose threshold sat higher, or
which read something that accumulates more slowly than cluster size, would be order-sensitive. The
measurement says the *cheap* version of the idea buys nothing, not that staging is worthless.

## Scope

One slice, 137 blocks, one era. The doubt gate's threshold was swept over 2, 3, 5 and 10 and the
first three are indistinguishable. The largest-cluster figure is stable across every configuration,
which limits what this slice can say about cluster collapse — nothing here produces one.

## Reproducibility / provenance

Per `results/REPRODUCIBILITY.md`, state 2: **mechanism unit-tested, headline number is a data-run.**
`merge_objections`, `merge_order` and the ordering's refusal on an unrankable export are pinned in
`tests/test_views.py`. The tables here are regenerated over `sample.ndjson`, which is local and
unversioned, and are not asserted.
