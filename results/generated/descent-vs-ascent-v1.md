# Ascending and descending over the same slice

Generated from the canonical experiment artifact. Do not edit manually.

Two passes read the same 12000 transactions and 12341 addresses. The ascending pass starts from the discrete partition and declines a merge the spending transaction argues against. The descending pass is handed the common-input-ownership partition and may only cut it, from the same refusal channels with the co-spend prior removed.

| pass | blocks |
|---|---:|
| common-input ownership, inherited | 3182 |
| refusing merge pass, ascending | 3282 |
| descent at cut_below -1 | 3182 |
| descent at cut_below -2 | 3182 |
| descent at cut_below -4 | 3182 |

The ascent separates 3837 address pairs the inherited partition joins. The descent separates none of them, at any of the 3 thresholds, and cut no block at all.

| quantity | pairs |
|---|---:|
| joined by the inherited partition | 601536 |
| carrying evidence against the pairing | 1054 |
| joined inside a searchable block | 7669 |
| evidence inside a searchable block | 0 |
| evidence inside a block above the search bound | 1054 |
| separated by the ascent inside a searchable block | 0 |

The null is not the threshold's doing. Evidence against a pairing reaches 0.18% of the joined pairs, and all of it lies inside 5 of the 84 blocks that exceed the exact search bound of 9 addresses. Not one of the 3098 blocks the search could reach contains a pair these channels argue against, so within its reach the search had nothing to act on and correctly did nothing.

What the two passes do with identical evidence is therefore not symmetric. A refusal at merge time separates two addresses without holding any evidence about that pair: the merge is simply not made, and transitivity never carries through it. A cut has to argue about every pair crossing the boundary it names, against a partition whose blocks here reach 648 addresses. On this slice that asymmetry is the whole difference between the two results.

These counts describe one six-block slice under two channels, compare the passes as partitions rather than against same-owner labels, and do not establish how either pass behaves where the evidence is denser.
