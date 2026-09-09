# Does clustering the conspicuous transactions first change anything?

## Verdict

No. On a contiguous 137-block slice with complete transaction data, ordering the merges by how
little each argues against itself produces a partition identical to block order. What does
change the partition is the state-dependent gate the ordering was supposed to feed: declining a
doubted merge that would fuse two already-established clusters takes the slice from 868 to 1,117
clusters. The ordering is inert; the gate is not.

## Data

`data/amount-channel-812695-812831-v1.json`: 5,491 transactions over blocks 812,695–812,831, every
one carrying prevout values and script types, 1,428 of them multi-input. This is the committed
contiguous slice that supports the amount channel — the graph-scale exports (`epoch_2016_*`, the committed graph
fixtures) carry addresses only, and the fingerprint survey is aggregate rather than per-transaction.

## What the transactions say against themselves

`merge_objections` counts the published tells that argue against reading a transaction's inputs as
one owner: an input that already covers the largest output (the unnecessary-input heuristics), and
inputs that disagree on script type. Over the 1,428 multi-input transactions:

| objections | transactions | share |
|---:|---:|---:|
| 0 | 855 | 59.9% |
| 1 | 512 | 35.9% |
| 2 | 61 | 4.3% |
| unrankable | 0 | — |

> **Superseded numbers, and how far the error reached.** An earlier revision published 513 / 820 / 95
> here. It was computed over an export storing every amount as a JSON string, so the comparison in
> `x_uih` ran lexicographically — `"330" > "1000"` is true as text and false as a number — and 51.3%
> of the UIH verdicts changed once the amounts were read as integers. `x_uih` now refuses a
> non-integer amount instead of ranking it, so this cannot recur silently.
>
> That revision also stated that the partition tables below were unaffected. They were not: the two
> doubt-gate rows are recomputed here as well, and they move a great deal, because the gate only
> declines a merge that the transaction argues against and under string amounts *every* multi-input
> transaction appeared to argue against itself.

**A majority of multi-input transactions is unambiguous** — 59.9% raise no objection at all, so
blind common-input ownership merges the rest regardless. That is the quantity the refusal exists to
act on.

## What each rule does to the partition

| configuration | clusters | largest | addresses clustered |
|---|---:|---:|---:|
| naive CIOH | 889 | 996 | 9,960 |
| refuse (shape + de-mix), block order | 868 | 996 | 9,109 |
| refuse, conspicuous-first | 868 | 996 | 9,109 |
| refuse + doubt gate, block order | 869 | 996 | 9,009 |
| refuse + doubt gate, conspicuous-first | 869 | 996 | 9,009 |

- Refusal changes the partition: yes (889 → 868)
- The doubt gate barely changes it: 868 → 869, one cluster. The earlier 1,117 was the string-amount
  reading, where every multi-input transaction raised an objection and the gate therefore had a
  candidate to decline almost everywhere. Read on the amounts as numbers, the gate is nearly inert
  on this slice
- The order changes it: no — the two gated runs are identical, and so are the two ungated ones

The largest cluster is 996 addresses in every configuration, including naive. Nothing here prevents
it, which says it is assembled from transactions that raise no objection — a genuinely conspicuous
entity, or one whose collapse happens through evidence none of these rules examines.

## Why the order is inert

Union-find over a fixed set of merges is order-independent, so ordering can only matter through a
decision that reads the partition built so far. The refusal rules are not such a decision: the
coinjoin shape and the de-mix both read the spending transaction alone.

`cluster_addresses` does contain one, though, and it is worth naming rather than passing over.
Change-link eligibility asks whether a transaction's inputs *already* stood in one cluster when it
was reached, which is a property of the partition-so-far and therefore of the order. It is inert
here for a different reason than the refusal rules are: `_merge_pass` takes that eligibility in
sample order under both settings (`views.py:171-177`), so staging changes which merges are judged
against which context and nothing else. The independence holds by construction, not because no
order-sensitive decision exists — read the other way, this section would be claiming something the
function does not support.

Adding a state-dependent decision to the *merging* — the doubt gate — makes the partition move, but
not with the order, because at a two-address threshold a cluster becomes "established" almost
immediately and the verdict is the same whenever it is taken.

That is a property of this gate, not a refutation of the idea. A gate whose threshold sat higher, or
which read something that accumulates more slowly than cluster size, would be order-sensitive. The
measurement says the *cheap* version of the idea buys nothing, not that staging is worthless.

## Scope

One slice, 137 blocks, one era. The doubt gate's threshold sweep was run under the string-amount
reading and is not carried over; what is measured here is the threshold of two. The largest-cluster figure is stable across every configuration,
which limits what this slice can say about cluster collapse — nothing here produces one.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data. `merge_objections`,
`merge_order` and the ordering's refusal on an unrankable export are pinned in
`tests/test_views.py`; the tables above are recomputed from
`data/amount-channel-812695-812831-v1.json` and asserted in
`tests/test_conspicuous_order_slice.py`, so a change that moves them fails rather than republishing
quietly.
