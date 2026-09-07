# Ascending and descending over the same slice

Generated from the canonical experiment artifact. Do not edit manually.

Two passes read the same 12000 transactions and 12341 addresses. The ascending pass starts from the discrete partition and declines a merge the spending transaction argues against. The descending pass is handed the common-input-ownership partition and may only cut it, from the same refusal channels with the co-spend prior removed.

| pass | blocks | blocks cut | separations the ascent makes and this does not |
|---|---:|---:|---:|
| common-input ownership, inherited | 3182 | n/a | 3837 |
| refusing merge pass, ascending | 3282 | n/a | 0 |
| descent at cut_below -1 | 3261 | 4 | 3014 |
| descent at cut_below -2 | 3182 | 0 | 3837 |
| descent at cut_below -4 | 3182 | 0 | 3837 |

At the loosest bar the descent recovers **823 of the 3837** separations the ascent makes, cutting 4 blocks and never separating a pair the ascent keeps together. Every signal on this slice is a single tell, so a bar of two or more clears nothing: the threshold is doing real work rather than sitting below the data.

| quantity | pairs |
|---|---:|
| joined by the inherited partition | 601536 |
| carrying evidence against the pairing | 1054 |
| joined inside an exactly searched block | 7669 |
| evidence inside an exactly searched block | 0 |
| evidence inside a block the conservative pass handled | 1054 |

Evidence against a pairing reaches 0.18% of the joined pairs, and all of it lies inside 5 of the 84 blocks that exceed the exact bound of 9 addresses. Not one of the 3098 blocks the exact search reaches contains a pair these channels argue against, so there it correctly did nothing. The heavy tail is where the evidence lives and where an exact search cannot go, which is why the conservative pass exists.

What the two directions do with identical evidence is still not symmetric, and the remaining 3014 pairs are the measure of it. A refusal at merge time separates two addresses without holding any evidence about that pair: the merge is simply not made, and transitivity never carries through it. A cut has to argue about the boundary it names, against blocks reaching 648 addresses. Descending is strictly more expensive than not ascending, and this slice says how much.

These counts describe one six-block slice under two channels, compare the passes as partitions rather than against same-owner labels, and do not establish how either pass behaves where the evidence is denser.
