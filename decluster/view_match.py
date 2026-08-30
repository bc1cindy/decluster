"""Match the vertices of two pseudonym-graph views, seeded and propagated.

The cited construction: two overlapping views of one social graph, a small seed of
confidently matched pairs, and an iterative propagation that identifies further vertices by
the identities of their already-matched neighbours. A "dimension" here is roughly *is this
vertex related to that specific vertex*, which is where the sparsity the attack needs comes
from — not from the vertex's own attributes, which measure out far too coarse
(`RESULTS-fingerprint-sparsity.md`).

Three guards, each answering something measured rather than assumed:

  hub cap        degree in a contracted 2026 view is heavy-tailed, median 2 against a
                 maximum above 15 000 (`RESULTS-contraction-2026.md`). A hub is adjacent to
                 thousands of candidates and would vote for all of them, so propagation
                 must not route through one.
  eccentricity   a match is accepted only when its score stands clear of the runner-up,
                 the same gap test the provenance propagator uses. A diffuse tie is a
                 refusal, not a coin flip.
  reversibility  the match must also win scoring from the other side. Two views need not
                 agree, and a vertex with no counterpart is meant to stay unmatched.
"""
from collections import Counter
from math import sqrt

from .propagate import eccentricity


def candidate_scores(u, src, dst, mapping, hubcap=100, damping=True, stat=None):
    """Score dst-vertices as candidates for src-vertex `u`, by the images of u's already
    matched neighbours. Only matched neighbours carry information, so an unmatched
    neighbourhood scores nothing and u simply waits for a later round.

    Both the hub cap and the damping read a vertex's connectedness, and a shared obscure
    neighbour says far more about identity than a shared popular one. `stat` supplies that
    connectedness measured on the *unfiltered* graph. It matters: dropping leaves to fit a
    wide view in memory lowers the degree of everything they hung off, which silently
    reweights every score. Measured on a real slice, filtering without `stat` moved
    precision from 0.574 to 0.484 — the pre-filter is only neutral if the matcher keeps
    seeing the degrees the full graph had."""
    conn = (lambda v: stat.get(v, 0)) if stat is not None else dst.degree
    scores = Counter()
    for n in src.neighbours(u):
        image = mapping.get(n)
        if image is None or conn(image) > hubcap:
            continue
        w = 1.0 / sqrt(conn(image) or 1) if damping else 1.0
        for v in dst.neighbours(image):
            scores[v] += w
    return scores


class ViewMatcher:
    """`match` returns {vertex in A: vertex in B} including the seed. Vertices it cannot
    resolve are absent from the result rather than guessed at."""

    def __init__(self, theta=0.5, hubcap=100, min_score=0.0, damping=True,
                 reversible=True, stat=None):
        self.theta = theta
        self.hubcap = hubcap
        self.min_score = min_score
        self.damping = damping
        self.reversible = reversible
        self.stat = stat or {}          # {view: {vertex: unfiltered connectedness}}
        self.confidence = {}

    def _best(self, u, src, dst, mapping, detail=False):
        """Returns the accepted candidate, or None. With `detail`, returns
        (candidate, eccentricity, score) so a caller can rank matches by how clearly they
        won — the framework's value lies in the *high confidence* links, not in coverage,
        so a match has to carry how confident it was."""
        miss = (None, 0.0, 0.0) if detail else None
        scores = candidate_scores(u, src, dst, mapping, self.hubcap, self.damping,
                                  self.stat.get(id(dst)))
        for taken in mapping.values():
            scores.pop(taken, None)              # a dst vertex is claimed at most once
        if not scores:
            return miss
        best = max(scores, key=scores.get)
        if scores[best] <= self.min_score:
            return miss
        ecc = eccentricity(scores) if len(scores) >= 2 else float("inf")
        if len(scores) >= 2 and ecc <= self.theta:
            return miss                          # a diffuse tie is a refusal
        return (best, ecc, scores[best]) if detail else best

    def match(self, ga, gb, seed, stat_a=None, stat_b=None):
        """Propagate along the frontier rather than rescanning every vertex each round: a
        vertex only becomes scorable once one of its neighbours is matched, so the work is
        proportional to the matched region, not to the graph."""
        if stat_a is not None:
            self.stat[id(ga)] = stat_a
        if stat_b is not None:
            self.stat[id(gb)] = stat_b
        self.confidence = {}                 # vertex -> (eccentricity, winning score)
        mapping = dict(seed)
        reverse = {b: a for a, b in mapping.items()}
        frontier = {n for u in mapping for n in ga.neighbours(u) if n not in mapping}
        while frontier:
            nxt, refused, matched = set(), set(), 0
            for u in frontier:
                if u in mapping:
                    continue
                v, ecc, sc = self._best(u, ga, gb, mapping, detail=True)
                if v is not None and self.reversible \
                        and self._best(v, gb, ga, reverse) != u:
                    v = None                     # must win from the other side too
                if v is None:
                    refused.add(u)
                    continue
                mapping[u] = v
                self.confidence[u] = (ecc, sc)
                reverse[v] = u
                matched += 1
                nxt.update(n for n in ga.neighbours(u) if n not in mapping)
            if not matched:
                break
            frontier = nxt | refused             # a refusal can turn into a match once a
        return mapping                           # rival candidate is claimed elsewhere
