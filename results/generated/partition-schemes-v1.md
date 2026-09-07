# Which cut makes two matchable views

Generated from the canonical experiment artifact. Do not edit manually.

300000 transactions, 71986 clusters. Each scheme cuts the slice into two views, a straddling entity gets a distinct pseudonym per view, and the matcher has to rejoin them from structure alone.

| scheme | boundary txs | pairs to rejoin | straddler edges | mean straddler degree | non-isolated | correct @ 10% seed |
|---|---:|---:|---:|---:|---:|---:|
| `epoch` | 0 (0.0%) | 2562 | 1910 | 1.45 | 44.7% | 1 |
| `decore` | 117371 (39.1%) | 1294 | 360 | 0.55 | 28.3% | 0 |
| `collapse` | 4989 (1.7%) | 2536 | 1941 | 1.49 | 44.5% | 1 |

**`decore` cuts the wrong thing.** Dropping the busiest 1% of addresses removes 39.1% of the transactions, takes the rejoinable population from 2562 to 1294 and the straddler subgraph's mean degree from 1.45 to 0.55. It cuts by degree, and degree is where the recurring relationships live.

**`collapse` is nearly free and does not change the regime.** It costs 1.7% of the transactions and leaves the population and the degree where the temporal baseline leaves them (2536 against 2562 pairs, 1.49 against 1.45). It is the cut the framework asks for and it is not the binding constraint.

| scheme | seed | seeds | guesses | correct | precision |
|---|---:|---:|---:|---:|---:|
| `epoch` | 5% | 128 | 0 | 0 | n/a |
| `epoch` | 10% | 256 | 1 | 1 | 1.000 |
| `decore` | 5% | 64 | 0 | 0 | n/a |
| `decore` | 10% | 129 | 0 | 0 | n/a |
| `collapse` | 5% | 126 | 0 | 0 | n/a |
| `collapse` | 10% | 253 | 1 | 1 | 1.000 |

The matcher recovers a handful of pairs at best, so what separates the schemes here is the straddler subgraph and not the precision. A cut that halves the mean straddler degree leaves nothing to propagate along, whatever its precision reads on the pairs it does return.

Every scheme generalises to n views:

| scheme | 2 | 3 | 4 |
|---|---|---|---|
| `epoch` | 137354/162646 | 91349/94577/114074 | 70469/66597/78032/84902 |
| `decore` | 82820/99809 | 55231/57214/70184 | 42474/40182/46904/53069 |
| `collapse` | 135045/159966 | 89861/93060/112090 | 69302/65459/76829/83421 |

Cluster membership here is a co-spend label rather than wallet ownership, the export carries no output values so the collapse detector sees only its shape rule, and this is one slice of one era. None of it is a privacy score.
