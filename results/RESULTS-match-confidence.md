# Precision against the matcher's own confidence

**Why ask.** `RESULTS-view-match-2026.md` reported that the propagation never becomes
self-sustaining and treated that as the headline. The framework anticipates exactly this
and does not rest its case on coverage: *"a proliferation of pseudonyms may limit the
effectiveness of this approach for any particular run of the propagation algorithm, **high
confidence links obtained by this method can feed into other clustering heuristics**."*
The criterion it actually states is whether the matcher produces high-confidence links, and
that had never been measured: precision was only ever reported in aggregate.

**Method.** Every accepted match now records the eccentricity it won by, `(best − second) /
stdev` over the candidate scores, the same gap the gate tests. Matches are then stratified
by it. Same slice, refusing clusterer, seed 400, 141 graded matches. Wilson 95 % intervals,
because the interesting bins are small.

## Result

| | correct / matched | precision | 95 % interval |
|---|---:|---:|---|
| all matches | 81 / 141 | 0.574 | 0.49 – 0.65 |
| eccentricity ≥ 1 | 76 / 131 | 0.580 | 0.49 – 0.66 |
| eccentricity ≥ 2 | 65 / 110 | 0.591 | 0.50 – 0.68 |
| eccentricity ≥ 3 | 61 / 91 | 0.670 | 0.57 – 0.76 |
| eccentricity ≥ 5 | 40 / 55 | 0.727 | 0.60 – 0.83 |
| eccentricity ≥ 10 | 10 / 10 | 1.000 | 0.72 – 1.00 |
| top 10 by eccentricity | 9 / 10 | 0.900 | 0.60 – 0.98 |
| top 20 by eccentricity | 17 / 20 | 0.850 | 0.64 – 0.95 |

## Reading

**Precision is monotone in the matcher's own confidence, across the whole range.** It rises
from 0.574 over all matches to 0.727 at eccentricity 5 and 10 of 10 above eccentricity 10.
The matcher knows which of its answers are good, which is the property the framework's
argument needs and the aggregate figure hides.

**A high-confidence subset exists, and it is small.** 55 links at eccentricity ≥ 5 out of
33 033 spanning vertices. Read as coverage that is negligible; read as evidence it is not,
because the framework's use for these links is to feed other clustering heuristics, where
a small number of reliable links is worth more than many unreliable ones.

**Translated into the weight such a channel would carry**, a link at precision 0.727 is
worth about 1.4 bits of evidence for common ownership, and one at 0.9 about 3.2 bits. Those
are the same order as the fingerprint channel's per-axis contributions, so the output is
usable as a channel rather than merely suggestive. That is the concrete case for wiring the
matcher back into the clusterer.

**The top bin is too small to pin down.** Ten of ten is consistent with anything above 0.72.
The claim this supports is that precision keeps rising with confidence, not that the top
band is error-free. Distinguishing those needs more matches, which means either a wider
slice or a partition scheme that yields more.

## Consequence for the earlier reading

`RESULTS-view-match-2026.md` framed the absent cascade as the result. That was measured
correctly but judged against a stricter criterion than the source states, and this
supersedes that emphasis: coverage does not ignite, and the links that *are* produced carry
graded, usable confidence. Both are true and the second was missing.
