# Negative controls: does the matcher beat degree alone?

**Why ask.** Every result so far was defended with a shuffle control, which rules out
chance. It does not rule out the likelier alternative: that the matcher recovers nothing
but degree. A vertex of degree 47 in one view and one of degree 47 in the other are an
obvious pair with no propagation at all, so beating chance is a low bar when the graphs are
degree-labelled. Until this is excluded, "precision 0.68 at eccentricity 5" is not evidence
that structure carries identity.

**Method.** All controls are scored on the *same* A-vertices the matcher matched, so the
comparison is of scoring rules rather than of populations. The decisive one is the degree
class expectation: for each matched vertex, one over the number of B-vertices sharing its
true partner's degree. That is exactly what degree is worth, with no algorithm attached, and
it is deliberately generous — it is handed the true partner's degree, which a real
degree-only adversary would have to guess from the other view, so it upper-bounds that
adversary rather than approximating it.

**Data.** `slice_2026.ndjson`, refusing clusterer, epoch partition, seed 400. 138 graded
matches, 50 at eccentricity ≥ 5.

## Result

| control | all matched | at eccentricity ≥ 5 |
|---|---:|---:|
| **matcher** | **0.561** | **0.700** |
| shuffle | 0.000 | 0.000 |
| degree rank | 0.087 | 0.170 |
| nearest degree, greedy | 0.000 | 0.000 |
| **degree class, exact upper bound** | **0.440** | **0.553** |

B-vertices sharing the true partner's degree: median 8, minimum 1, maximum 82 185.
148 graded matches, 60 at eccentricity ≥ 5.

*(Re-run on the graph corrected in `RESULTS-graph-shape.md`. The earlier figures — 0.580 /
0.680 for the matcher, 0.428 / 0.499 for the baseline — ran on a graph with four times too
many edges, almost all of them on hubs the matcher already discards, so every conclusion
holds and the numbers move within the run-to-run band. The margin over degree is +0.12
overall and +0.15 in the high-confidence band.)*

## Reading

**The matcher wins, by less than the shuffle control implied.** Against an upper bound of
0.428 overall and 0.499 in the high-confidence band, it reaches 0.561 and 0.700. The
structural propagation is worth roughly twelve points overall and fifteen in the band
where the framework locates the value. That is a real margin against a generous baseline,
and it is a long way from the near-zero baseline a shuffle control suggests.

**Degree is already most of the way there, on this population.** The median matched vertex
has a true partner whose degree is shared by only eight vertices in a view of 390 000. The
matcher matches where degree is nearly a quasi-identifier in its own right, which is a
selection effect worth naming rather than a coincidence: the vertices propagation can act on
are the ones with distinctive neighbourhoods, and a distinctive neighbourhood implies a
distinctive degree.

**The two naive degree strategies are weak algorithms, not bounds.** Degree rank scores
0.095 and greedy nearest-degree scores 0.000, because both must break ties among as many as
82 247 equal-degree vertices arbitrarily. They are reported for completeness; the exact
class expectation is the baseline that matters, and it is far stronger than either.

**One earlier control was degenerate and should not have been reported as one.** The
"seed-only" row in previous runs scores zero by construction, because the seed is excluded
from grading. It measured nothing.

**Run-to-run variation is real and was not previously stated.** This run reports 0.680 at
eccentricity ≥ 5 where an earlier one, differing only in the random pseudonym labelling,
reported 0.727 on 55 links. Both sit inside the Wilson interval given there (0.60–0.83), so
they are consistent, but the point estimate moves by about five points from relabelling
alone. Single-run point estimates at these counts should be read as a band, not a number.

## Consequence

`RESULTS-match-confidence.md` reported precision rising with confidence and translated it
into an evidence weight for feeding a clustering channel. That translation has to be taken
against this baseline, not against zero: the *additional* evidence the matcher supplies over
reading degrees off is what a clustering channel could claim, and it is smaller than the raw
precision suggests. Whether the residual margin is worth a channel is now a quantitative
question with a measured answer rather than an assumed one.

## Scope

One slice, one partition scheme, one seed size. The degree-class baseline is computed on the
matched set, which is the fair comparison for "is the matcher adding anything" and is *not*
an estimate of what degree alone would achieve across the whole graph.
