# The partition schemes on a slice a reader has

Generated from the canonical experiment artifact. Do not edit manually.

12000 transactions, 3179 clusters. Each scheme cuts the slice into two views, a straddling entity gets a distinct pseudonym per view, and the matcher has to rejoin them from structure alone.

| scheme | views | boundary txs | straddling entities | edges among them | non-isolated |
|---|---|---:|---:|---:|---:|
| epoch | 5804 / 6196 | 0 | 77 | 27 | 25 |
| decore | 4473 / 4983 | 2544 | 50 | 10 | 14 |
| collapse | 5794 / 6165 | 41 | 78 | 28 | 26 |

The collapse cut costs 41 transactions more than the temporal one and leaves the straddler population and its internal connectivity where the temporal cut leaves them (78 against 77 entities, 28 against 27 edges). `decore` is the one that differs, and it differs by destroying the signal: 50 entities and 10 edges among them. That ordering is what the 300,000-transaction run found, at two orders of magnitude more data.

**The matcher does not ignite here, under any scheme.** Not zero correct out of some guesses — zero guesses. Propagation needs edges among the straddlers and this slice does not supply enough of them, so the precision and recall half of `RESULTS-partition-cuts.md` stays backed only by the export this repository does not ship. Reporting zeros as a comparison would read as a measured tie between the schemes, and it is not one.

Every scheme generalises to n views:

| scheme | 2 | 3 | 4 |
|---|---|---|---|
| epoch | 5804/6196 | 2956/4266/4778 | 1659/1297/2848/6196 |
| decore | 4473/4983 | 2256/3297/3903 | 1277/979/2217/4983 |
| collapse | 5794/6165 | 2946/4247/4766 | 1655/1291/2848/6165 |

Cluster membership here is a co-spend label rather than wallet ownership, the export carries no output values so the collapse detector sees only its shape rule, and the counts are two orders of magnitude below the published run — they support the ordering, not a comparison of magnitudes. None of this is a privacy score.
