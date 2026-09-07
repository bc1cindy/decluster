# Wiring the attributes in, and why they come back out

**Why ask.** The framework has statistical feature distributions reducing to attributes on
the vertices, with *"both those and the structural features"* informing the edge attributes.
Until now the matcher used neither: it was purely structural, and the whole attribute
apparatus, including the per-epoch normalisation calibrated in `RESULTS-attribute-drift.md`,
had no consumer. This wires both in and measures them.

**What was built.** Each edge stores the axis values of the transfer that created it (93 %
of edges carry one transfer, so for nearly all of them that is the whole distribution; a
`Counter` per edge does not fit at slice scale). Two bounded multiplicative conditioners:
one comparing the A-edge (u, n) against the B-edge (v, image) when evidence arrives through
a matched neighbour, one comparing the two vertices' attribute lifts. Half agreement is
neutral, so neither can turn a zero score into a positive one.

**Data.** `slice_2026.ndjson`, refusing clusterer, seed 400, 3.9 / 4.0 million edge
signatures. Every configuration scored against the degree-class baseline recomputed on its
own matched set.

## Result

At alpha 0.5:

| configuration | matched | precision | at ecc ≥ 5 | precision | degree baseline | margin |
|---|---:|---:|---:|---:|---:|---:|
| structure only | 143 | 0.559 | 56 | 0.679 | 0.578 | **+0.101** |
| + edge attributes | 370 | 0.322 | 78 | 0.513 | 0.516 | −0.003 |
| + vertex attributes | 426 | 0.211 | 115 | 0.409 | 0.557 | −0.149 |
| + both | 765 | 0.184 | 176 | 0.352 | 0.484 | −0.132 |

*(Re-run on the graph corrected in `RESULTS-graph-shape.md`, with 525k edge signatures in
place of the earlier inflated 3.9M. The pattern is unchanged and slightly sharper: every
conditioner is negative, the loss grows monotonically, and the mechanism below is
independent of the edge-attribution bug.)*

Sweeping the edge conditioner's strength (separate run, see the note on variance):

| edge alpha | links at ecc ≥ 5 | precision | degree baseline | margin |
|---:|---:|---:|---:|---:|
| 0.00 | 52 | 0.654 | 0.356 | **+0.298** |
| 0.05 | 88 | 0.455 | 0.217 | +0.238 |
| 0.10 | 85 | 0.447 | 0.218 | +0.229 |
| 0.25 | 84 | 0.476 | 0.264 | +0.212 |

## Reading

**The attributes hurt, and there is no setting at which they do not.** The margin over a
degree-only guess is monotone decreasing in alpha from zero. The largest single loss is
between alpha 0 and alpha 0.05, so it is not the size of the perturbation that costs, it is
that there is a perturbation at all.

**The mechanism is manufactured eccentricity, and it invalidates the design argument.** The
conditioner was justified on the grounds that a bounded multiplicative factor cannot create
a match where structure found nothing, because zero times anything is zero. That holds for
the *score*. The gate does not read the score; it reads the separation between the leader
and the runner-up. Scaling tied candidates by different factors creates exactly that
separation. The signature is in the counts: matches rise from 143 to 765 while precision
falls from 0.559 to 0.184. The attributes are not pointing at the wrong vertex, they are
converting refusals into errors.

**This was predictable from measurements already in hand.** 0.4 % of transactions sit in a
fingerprint class below 100 over the whole window, 2.35 % at single-epoch scope. A signal
that weak cannot break ties without contributing more noise than information. The earlier
conclusion that attributes should condition rather than score was right; implementing the
conditioner at the point where the decision is taken was not.

**So the correct implementation is to build them and keep them out of the gate.** That is
different from not having them, and the difference matters for the framework's model: the
vertex and edge attributes it specifies do exist here, are computed, and are measured to be
too weak to participate in the matching decision on this data. Both conditioners default to
off and are retained as the instrument that established this.

## Untested alternative

Applying the attributes *after* the gate, to rank confidence rather than to decide
acceptance, cannot manufacture eccentricity because the accept-or-refuse verdict is already
fixed. It would not change which matches are made, only their order, and whether that
sharpens the high-confidence band is not answered here.

## Note on variance

The two tables come from separate runs and their degree baselines differ, 0.542 against
0.356, because the random pseudonym labelling differs. `RESULTS-match-controls.md` records
the same effect. Comparisons within a table are internally consistent, which is what each
table is for; the two tables should not be read against each other.

## Reproducibility / provenance

State 2 in `results/REPRODUCIBILITY.md`: the mechanism is pinned; the reported numbers come from a data-run over `slice_2026.ndjson`, which is not committed, and are not asserted.
