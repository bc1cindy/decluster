"""Match the vertices of two pseudonym-graph views, seeded and propagated.

The cited construction: two overlapping views of one social graph, a small seed of
confidently matched pairs, and an iterative propagation that identifies further vertices by
the identities of their already-matched neighbours. A "dimension" here is roughly *is this
vertex related to that specific vertex*, which is where the sparsity the attack needs comes
from — not from the vertex's own attributes, which measure out far too coarse
(`RESULTS-fingerprint-sparsity.md`).

Three guards, each answering something measured rather than assumed:

  hub cap        degree in a contracted view is heavy-tailed: mean 4.79 against a second
                 moment of 6289, which forces some vertex above 1300
                 (`results/generated/graph-rejoin-2016-v1.md`). A hub is adjacent to
                 thousands of candidates and would vote for all of them, so propagation
                 must not route through one.
  eccentricity   a match is accepted only when its score stands clear of the runner-up,
                 the same gap test the provenance propagator uses. A diffuse tie is a
                 refusal, not a coin flip.
  reversibility  the match must also win scoring from the other side. Two views need not
                 agree, and a vertex with no counterpart is meant to stay unmatched.

WHERE THIS DEPARTS FROM THE PAPER. This is the closest module in `decluster/` to the cited
algorithm, but it is not the faithful implementation of it; that is
`decluster/baselines/narayanan_shmatikov.py`. Five differences change verdicts:

  * A candidate set of size one is accepted with `eccentricity = float("inf")`
    (`ViewMatcher._best`), skipping the gate entirely rather than computing a large-but-finite
    eccentricity. The baseline's live gate (`propagate`'s `_sparse_winner`, not `_winner`) never
    skips it: given one materialised score it still normalises over the whole unclaimed candidate
    population and computes a finite eccentricity from that, which clears `theta` or not depending
    on the population size — not a blanket refusal of a lone candidate.
  * The imported `propagate.eccentricity` normalises by the standard deviation of the scores that
    were actually materialised, and `candidate_scores` materialises only vertices that received a
    vote. The baseline's gate (`_sparse_winner`) normalises over the whole unclaimed candidate
    population, implicit zeros included, which is a larger population and a different sigma. The
    two formulas agree given the same values; they are not given the same values.
  * `candidate_scores` damps by `1/sqrt(conn(image))` — the connectedness of the *matched
    neighbour's image*, one weight for every candidate that neighbour reaches. The paper divides
    each vote by the square root of the degree of the *candidate* being voted for, which is what
    makes it a cosine-like similarity; the baseline does that at
    `narayanan_shmatikov._sparse_match_scores`. Different quantity, different ranking: the two
    agree only where every candidate reached by a matched neighbour has that neighbour's degree.
  * `directional` is off by default, so a vote from a matched neighbour is scored over the
    undirected neighbourhood. The paper scores in- and out-edges separately and sums the two,
    which is a strictly finer constraint — a candidate must be on the *same side* of the matched
    neighbour. Turning it on changes both coverage and precision, and not by a little.
  * `hubcap` drops any matched neighbour whose connectedness exceeds it, and defaults to 100.
    The paper has no such filter. The guard answers a measured property of a contracted Bitcoin
    view rather than anything in the algorithm, so it is a local addition and not a parameter
    choice.
"""
from collections import Counter
from math import sqrt

from .single_view_propagation import eccentricity


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
    refusals into accepted matches on no new structural fact
    (`test_view_match.test_the_conditioner_cannot_manufacture_a_score_but_does_manufacture_eccentricity`).
    The gate normalises by the spread of the scores, so its verdict does not depend on how
    large alpha is, only on the ordering the conditioner imposes: the smallest nonzero
    setting costs what the largest does. Both conditioners therefore default to off, and they
    are kept as the instrument that established this rather than as a feature to enable."""
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
                     edge_alpha=0.0, directional=False, return_support=False):
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
    support = Counter()
    # Preserve the relation to the matched neighbour. If u -> n, a candidate v must satisfy
    # v -> image(n), so v is an in-neighbour of image(n); the converse holds for n -> u.
    if directional:
        sides = [(src._out[u], lambda img: dst._in[img]),
                 (src._in[u], lambda img: dst._out[img])]
    else:
        sides = [(src.neighbours(u), lambda img: dst.neighbours(img))]
    for src_nbrs, dst_nbrs in sides:
        for n in src_nbrs:
            image = mapping.get(n)
            if image is None or conn(image) > hubcap:
                continue
            w = 1.0 / sqrt(conn(image) or 1) if damping else 1.0
            sa = _sig(src, u, n) if edge_alpha else None
            for v in dst_nbrs(image):
                wv = w
                if edge_alpha:
                    wv = _condition(w, agreement(sa, _sig(dst, v, image)), edge_alpha)
                scores[v] += wv
                support[v] += 1
    return (scores, support) if return_support else scores


class ViewMatcher:
    """`match` returns {vertex in A: vertex in B} including the seed. Vertices it cannot
    resolve are absent from the result rather than guessed at."""

    def __init__(self, theta=0.5, hubcap=100, min_score=0.0, damping=True,
                 reversible=True, stat=None, edge_alpha=0.0, vertex_alpha=0.0,
                 vertex_top=10, revisit=False, revisit_rounds=5, directional=False,
                 min_common=1):
        self.theta = theta
        self.hubcap = hubcap
        self.min_score = min_score
        self.damping = damping
        self.reversible = reversible
        self.stat = stat or {}          # {view: {vertex: unfiltered connectedness}}
        self.edge_alpha = edge_alpha    # 0 disables the attribute conditioners entirely
        self.vertex_alpha = vertex_alpha
        self.vertex_top = vertex_top    # only the leaders can change the gate's verdict
        self.directional = directional  # NS'09 in/out separated scoring (default: undirected)
        self.min_common = min_common    # paper's high-confidence stage uses k=4
        self.revisit = revisit          # NS'09 self-reinforcing pass: re-score mapped nodes
        self.revisit_rounds = revisit_rounds
        self.confidence = {}

    def _best(self, u, src, dst, mapping, detail=False):
        """Returns the accepted candidate, or None. With `detail`, returns
        (candidate, eccentricity, score) so a caller can rank matches by how clearly they
        won — the framework's value lies in the *high confidence* links, not in coverage,
        so a match has to carry how confident it was."""
        miss = (None, 0.0, 0.0) if detail else None
        scores, support = candidate_scores(u, src, dst, mapping, self.hubcap, self.damping,
                                           self.stat.get(id(dst)), self.edge_alpha,
                                           self.directional, return_support=True)
        if self.min_common > 1:
            scores = Counter({v: score for v, score in scores.items()
                              if support[v] >= self.min_common})
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
            # Sorted, because the order decides the outcome and a set's order is not defined.
            # `_best` denies an image once it is claimed, so whoever is scored first takes it from
            # everyone contesting it; iterating the set directly makes that hinge on string hashing,
            # which Python randomises per process. The algorithm does not specify an order, but an
            # implementation whose result changes between two runs of the same input has not
            # measured anything. This was found by a canonical run failing to reproduce itself.
            for u in sorted(frontier, key=repr):
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
        if self.revisit:                         # rival candidate is claimed elsewhere
            self._revisit(ga, gb, mapping, reverse, set(seed))
        return mapping

    def _revisit(self, ga, gb, mapping, reverse, seeds):
        """NS'09's self-reinforcing pass: once propagation settles, re-score each mapped
        (non-seed) vertex against the now-larger mapping. A vertex whose neighbourhood
        became better resolved can upgrade to a candidate that only became supportable
        later. A vertex is freed while it is re-scored, so it may reclaim its own image;
        it never steals another's, so the pass only ever sharpens, never thrashes."""
        for _ in range(self.revisit_rounds):
            changed = 0
            for u in [k for k in mapping if k not in seeds]:
                old = mapping.pop(u)
                reverse.pop(old, None)
                v, ecc, sc = self._best(u, ga, gb, mapping, detail=True)
                if v is not None and self.reversible \
                        and self._best(v, gb, ga, reverse) != u:
                    v = None
                if v is None:
                    mapping[u], reverse[old] = old, u        # keep the prior match
                    continue
                mapping[u], reverse[v] = v, u
                self.confidence[u] = (ecc, sc)
                if v != old:
                    changed += 1
            if not changed:
                break

    def match_candidates(self, ga, gb, seed, top_k=3, stat_a=None, stat_b=None):
        """The cit-25 (link-prediction) relaxation for incomplete graphs: after the strict
        match settles, every still-unmatched vertex adjacent to the matched region keeps a
        *candidate set* of its top-`top_k` images instead of a single accepted match. Stage-2
        sets do not feed back into propagation; they exist so a link can still be predicted
        for a vertex the strict matcher refused. Returns (mapping, {vertex: [candidate, ...]})."""
        mapping = self.match(ga, gb, seed, stat_a, stat_b)
        candidates = {}
        frontier = {n for u in mapping for n in ga.neighbours(u) if n not in mapping}
        for u in sorted(frontier, key=repr):
            scores = candidate_scores(u, ga, gb, mapping, self.hubcap, self.damping,
                                      self.stat.get(id(gb)), self.edge_alpha, self.directional)
            for taken in mapping.values():
                scores.pop(taken, None)
            if scores:
                candidates[u] = [v for v, _ in scores.most_common(top_k)]
        return mapping, candidates


def predict_link(a, b, gb, mapping, candidates, ml=None):
    """Predict whether a->b is an edge in the target view, cit-25 Algorithm-3: de-anonymize
    (DA) when both endpoints are uniquely mapped, else a unanimous vote over their candidate
    sets, else the `ml` fallback. `ml` is an optional callable (a, b) -> score in [0, 1] (the
    paper's logistic classifier over neighbourhood features); when absent, the mixed-vote and
    no-candidate branches abstain (return None) — the high-precision default. Returns 1 (edge),
    0 (no edge), a float (ml score), or None (abstain). Unanimous voting overwhelmingly
    recovers *non-edges*: random pairs rarely share one."""
    def images(x):
        return [mapping[x]] if x in mapping else candidates.get(x)
    ia, ib = images(a), images(b)
    if not ia or not ib:
        return ml(a, b) if ml is not None else None
    votes = [(v in gb._out[u] or v in gb._in[u]) for u in ia for v in ib]
    if all(votes):
        return 1
    if not any(votes):
        return 0
    return ml(a, b) if ml is not None else None


def find_seeds(ga, gb, top=50):
    """Experimental seed bootstrap: match vertices whose
    local signature (own degree + sorted neighbour degrees) is unique and identical in both
    views, highest degree first. Returns a seed mapping {a-vertex: b-vertex}. This is a strict,
    local heuristic, not the cited papers' weighted global graph matching; callers must validate
    its precision before feeding it into propagation."""
    def sig(g, v):
        return (g.degree(v), tuple(sorted(g.degree(n) for n in g.neighbours(v))))
    sa, sb = {}, {}
    for v in ga.vertices:
        sa.setdefault(sig(ga, v), []).append(v)
    for v in gb.vertices:
        sb.setdefault(sig(gb, v), []).append(v)
    seeds = {}
    for key in sorted((k for k in sa if len(sa[k]) == 1 and len(sb.get(k, ())) == 1),
                      key=lambda k: -k[0]):
        seeds[sa[key][0]] = sb[key][0]
        if len(seeds) >= top:
            break
    return seeds
