# Graph-structure linkage and the degree-matched control

Generated from the canonical experiment artifact. Do not edit manually.

8927 transactions, 27962 addresses, 2463 clusters of two or more. Positives are same-cluster pairs that do not co-spend; the score is rarity-weighted shared-neighbour structure.

| view | published AUC | degree-matched AUC | fall | degree-only AUC under matching |
|---|---:|---:|---:|---:|
| full | 0.9912 | 0.9784 | 0.0128 | 0.5478 |
| payment | 0.9506 | 0.9154 | 0.0353 | 0.5000 |

The payment-graph headline falls 0.0353 under degree-matched negatives, from 0.9506 to 0.9154. Under that control a score made only of the pair's degree sum reads 0.5000 — chance, by construction — so the remaining separation is not the asymmetry the published sampling leaves in.

The shuffled-label control reads 0.4994, which is what says the score is measuring the labels at all.

Cluster membership here is a co-spend label rather than wallet ownership, the fixture is one selected 2016 slice, and a fall under matching bounds how much of the AUC was degree asymmetry without establishing what the remainder is. Neither number is a re-identification rate or a privacy score.
