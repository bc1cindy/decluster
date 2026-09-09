# Does the matcher beat degree alone

Generated from the canonical experiment artifact. Do not edit manually.

Two consecutive 2016 weekly windows of 982,021 and 1,116,563 transactions, contracted into 588,843 and 638,436 pseudonyms. View B's labels are hidden, so 90,145 vertices are known to be present in both views and the correspondence between them is not. Seeds are drawn from the 54,486 of those whose degree sits in [3, 100] on both sides — below that a neighbourhood identifies nobody, and above it propagation refuses to route through the vertex at all, so a seed outside the band is a seed the matcher cannot spend.

At the 10% seeding, precision against the eccentricity each match won by:

| eccentricity | matched | uncontested | correct | precision | degree class alone | margin |
|---:|---:|---:|---:|---:|---:|---:|
| ≥ 0 | 623 | 2 | 376 | 0.604 | 0.31078 | +0.293 |
| ≥ 1 | 577 | 2 | 362 | 0.627 | 0.32650 | +0.301 |
| ≥ 2 | 515 | 2 | 334 | 0.649 | 0.34301 | +0.306 |
| ≥ 3 | 426 | 2 | 281 | 0.660 | 0.37982 | +0.280 |
| ≥ 5 | 283 | 2 | 197 | 0.696 | 0.48597 | +0.210 |
| ≥ 10 | 129 | 2 | 95 | 0.736 | 0.66658 | +0.070 |

**The matcher beats degree, and least where it is most sure.** Overall it is +0.293 against what degree alone is worth. That margin does not widen as the matcher grows confident; it collapses, to +0.070 at eccentricity 10. Precision does rise with confidence (0.604 to 0.736), which is the property the framework's argument wants — but the degree baseline rises faster (0.311 to 0.667), because the matches the matcher is surest of are the ones whose partner has a rare degree. The high-confidence band is where the matcher is *hardest* to distinguish from reading the degrees off.

The uncontested column is the matches where only one candidate materialised at all. The matcher records those with infinite eccentricity and skips the gate rather than computing it, so they clear every floor: a high band is only evidence about *standing clear of rivals* to the extent it is not made of them.

The degree-class column is what degree is worth with no algorithm attached: one over the number of B-vertices sharing the true partner's degree. It is handed that degree, which a degree-only adversary would have to guess, so it bounds such an adversary from above rather than approximating one. Classes here run to 225,915 vertices with a median of 119542.

Every arm, with the shuffled-seed control beside each seeded one:

| seed share | arm | seeds | guesses | correct | precision |
|---:|---|---:|---:|---:|---:|
| 5% | seeded | 2724 | 571 | 309 | 0.541 |
| 5% | shuffled | 2724 | 15 | 0 | 0.000 |
| 10% | seeded | 5448 | 623 | 376 | 0.604 |
| 10% | shuffled | 5448 | 17 | 3 | 0.176 |

The seeded arm returns 623 graded matches. A shuffled seed is the same matcher on the same graphs with the correspondence destroyed, and what it returns is the share of this that survives without the seeds meaning anything.

This is the complete-clustering premise: the matcher is told which vertices appear in both views and asked only which is which. The split-cluster premise, where a straddling entity carries a separate pseudonym per view and the matcher must discover that they are one, is measured beside it (`results/generated/graph-rejoin-2016-v1.md`) and is the harder question.

Cluster membership is a co-spend relation rather than observed wallet ownership, the seeds are supplied, and this is two windows of one era. None of it is a privacy score.

## Reproducibility / provenance

State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is recomputed from the committed weekly epoch graphs and compared byte for byte.
