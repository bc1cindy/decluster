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


def agreement(sa, sb):
    """Share of axes on which two signatures agree, or None when either is missing."""
    if not sa or not sb or len(sa) != len(sb):
        return None
    return sum(1 for x, y in zip(sa, sb) if x == y) / len(sa)


def _sig(g, a, b):
    return g.edge_sig.get((a, b)) or g.edge_sig.get((b, a))


def _condition(weight, agree, alpha):
    """Bounded multiplicative conditioner. Half agreement is neutral, and zero score stays
    zero, so an attribute cannot manufacture a *score* where structure found none.

    It can, however, manufacture *eccentricity*, and that is what the gate reads. Scaling
    tied candidates by different factors creates the separation the gate tests for, turning
    refusals into accepted matches. `RESULTS-attribute-conditioning.md` measures the cost:
    the margin over a degree-only guess falls monotonically as alpha rises from zero, and
    even alpha 0.05 gives most of the loss away. Both conditioners therefore default to off,
    and they are kept as the instrument that measured this rather than as a feature to
    enable."""
    return weight if agree is None else weight * ((1 - alpha) + 2 * alpha * agree)


def vertex_agreement(src, u, dst, v, axes=None):
    """Cosine between two vertices' attribute lifts. Each lift is already normalised
    against its own view's base rates, which is what makes the two comparable at all: a
    median 54% of an axis value's variance tracks epoch volume, a covariate that moves
    every vertex in a view together (`RESULTS-attribute-drift.md`)."""
    axes = axes or list(src.base_rates)
    num = na = nb = 0.0
    for axis in axes:
        pa, pb = src.attribute(u, axis), dst.attribute(v, axis)
        for value, x in pa.items():
            if x == float("inf"):
                continue
            y = pb.get(value, 0.0)
            num += x * (0.0 if y == float("inf") else y)
            na += x * x
        for y in pb.values():
            if y != float("inf"):
                nb += y * y
    return num / ((na * nb) ** 0.5) if na and nb else None


def candidate_scores(u, src, dst, mapping, hubcap=100, damping=True, stat=None,
                     edge_alpha=0.0):
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
        sa = _sig(src, u, n) if edge_alpha else None
        for v in dst.neighbours(image):
            wv = w
            if edge_alpha:
                wv = _condition(w, agreement(sa, _sig(dst, v, image)), edge_alpha)
            scores[v] += wv
    return scores


class ViewMatcher:
    """`match` returns {vertex in A: vertex in B} including the seed. Vertices it cannot
    resolve are absent from the result rather than guessed at."""

    def __init__(self, theta=0.5, hubcap=100, min_score=0.0, damping=True,
                 reversible=True, stat=None, edge_alpha=0.0, vertex_alpha=0.0,
                 vertex_top=10):
        self.theta = theta
        self.hubcap = hubcap
        self.min_score = min_score
        self.damping = damping
        self.reversible = reversible
        self.stat = stat or {}          # {view: {vertex: unfiltered connectedness}}
        self.edge_alpha = edge_alpha    # 0 disables the attribute conditioners entirely
        self.vertex_alpha = vertex_alpha
        self.vertex_top = vertex_top    # only the leaders can change the gate's verdict
        self.confidence = {}

    def _best(self, u, src, dst, mapping, detail=False):
        """Returns the accepted candidate, or None. With `detail`, returns
        (candidate, eccentricity, score) so a caller can rank matches by how clearly they
        won — the framework's value lies in the *high confidence* links, not in coverage,
        so a match has to carry how confident it was."""
        miss = (None, 0.0, 0.0) if detail else None
        scores = candidate_scores(u, src, dst, mapping, self.hubcap, self.damping,
                                  self.stat.get(id(dst)), self.edge_alpha)
        if self.vertex_alpha and len(scores) >= 2:
            for v, _ in scores.most_common(self.vertex_top):
                scores[v] = _condition(scores[v],
                                       vertex_agreement(src, u, dst, v),
                                       self.vertex_alpha)
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
