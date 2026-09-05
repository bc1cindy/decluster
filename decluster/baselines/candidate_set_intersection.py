"""Candidate-set intersection: narrowing a coin's origin across co-held observations.

Goldfeder, Kalodner, Reisman and Narayanan describe a cross-transaction intersection attack: a
coin's plausible origins form a *set*, and coins later shown to be held by the same party must have
come from a common origin, so what survives is the intersection of their sets.  Repeated over
successive observations the surviving set shrinks, and it can shrink to one.

The paper's Algorithm 2 is implemented below over injected graph and clustering callbacks.  Its
2015--2017 JoinMarket dataset and empirical rates are NOT reproduced, so no measured rate in this
repository is attributed to Goldfeder et al.  In particular this module states no shrink law.  The
reading that each observation cuts the candidate set by a constant factor is not Goldfeder's: the
intersection paper demonstrates the attack and states no such law.  It is not sourced elsewhere
here either -- the statistical-disclosure line of work bounds the observations an adversary needs
by a signal-to-noise condition and a confidence interval, not by a constant factor per observation.
``decluster/intersect.py`` carries the same distinction and this module does not weaken it.

The scope is deliberately narrow.  This module takes candidate sets; it does not compute them.
Where a set comes from -- a backward provenance walk, an address clustering, a wallet's own history
-- is outside it, and so is deciding that the coins were really co-held.  Both are
``decluster/intersect.py``'s business: that module wires the same mechanism to this repository's
ancestry walk and subordinates the result to ``cluster_refined``, which can refuse the co-spend the
whole narrowing is conditional on.

An empty intersection is a refusal, never an identification.  Observations that share no candidate
are inconsistent -- one of them is wrong, or the coins were not co-held -- and the attack has no
answer.  Reporting that as a maximal narrowing would turn the strongest evidence of a broken
assumption into the strongest claim.
"""

from dataclasses import dataclass
from math import log2
from typing import Hashable


@dataclass(frozen=True)
class IntersectionStep:
    """What one observation did to the surviving set."""

    index: int
    observed: int
    before: int
    after: int
    narrowing_bits: float | None


@dataclass(frozen=True)
class IntersectionResult:
    """The surviving candidates and the narrowing that produced them.

    ``identified`` is the lone survivor of a consistent run and ``None`` otherwise -- including
    when the run refused, so a refusal can never be read as an identification.  ``inconsistent_at``
    is the index of the observation that emptied the set, or ``None``.  A run with no observations
    at all has empty ``steps``: it did not refuse, it was never asked.
    """

    surviving: frozenset
    steps: tuple[IntersectionStep, ...]
    universe_size: int | None
    narrowing_bits: float | None
    identified: Hashable | None
    inconsistent_at: int | None


@dataclass(frozen=True)
class GoldfederIntersectionResult:
    """Algorithm 2's candidate clusters and unique-or-refuse verdict."""

    candidate_sets: tuple[frozenset, ...]
    surviving: frozenset
    identified: Hashable | None
    incorrect_assumptions: bool


def join_ancestors(coin, rounds, predecessors_of):
    """Return coins reachable backwards through at most ``rounds`` joins.

    ``predecessors_of(c)`` must return the inputs of the join transaction that
    created ``c``, or an empty iterable when that transaction is not a join.
    The start coin is included by the paper's length-zero-path case.
    """

    if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 0:
        raise ValueError("rounds must be a non-negative integer")
    seen = {coin}
    frontier = {coin}
    for _ in range(rounds):
        following = set()
        for current in frontier:
            following.update(predecessors_of(current))
        following -= seen
        if not following:
            break
        seen.update(following)
        frontier = following
    return frozenset(seen)


def goldfeder_cluster_intersection(coins, rounds, predecessors_of, cluster_of):
    """Goldfeder et al. Algorithm 2 over an already identified join graph.

    For every mixed coin, collect all coins on join-only backward paths of
    length at most ``rounds``, lift them to wallet clusters, and intersect the
    resulting sets.  Exactly one survivor is returned as an identification;
    zero or multiple survivors produce the paper's ``incorrect assumptions``
    outcome.  Join detection and recursive address clustering are explicit
    injected prerequisites rather than silently replaced by this repository's
    probabilistic ancestry walk.
    """

    candidate_sets = tuple(
        frozenset(cluster_of(ancestor) for ancestor in join_ancestors(
            coin, rounds, predecessors_of
        ))
        for coin in coins
    )
    result = intersect_candidate_sets(candidate_sets)
    identified = result.identified
    return GoldfederIntersectionResult(
        candidate_sets=candidate_sets,
        surviving=result.surviving,
        identified=identified,
        incorrect_assumptions=identified is None,
    )


def narrowing_bits(before, after):
    """``log2(before / after)``, or ``None`` when there is nothing to measure.

    Bits, not a count of removed candidates, because a run's steps start from sets of different
    sizes.  ``None`` for an empty survivor set: an empty intersection is a refusal, not an
    unbounded narrowing.  (``intersect.collapse_bits`` is the same quantity wired to this
    repository's walk; the duplication keeps this baseline standalone.)
    """
    if before <= 0 or after <= 0:
        return None
    return log2(before / after)


def intersect_candidate_sets(observations, universe_size=None):
    """Narrow a coin's candidate origins across successive observations of co-held coins.

    ``observations`` is a sequence of candidate sets, one per coin shown to be held with the
    others; each is any iterable of hashable candidates.  ``universe_size``, when known, lets the
    first observation's own narrowing be counted, since a first set of 8 out of 4096 has already
    said something; without it the reported bits are explicitly relative to the first observed set
    and that first step carries no bits.

    Intersection stops at the observation that empties the set.  Later observations cannot narrow
    an empty set, and continuing would let an inconsistent run absorb them silently.
    """
    surviving = None
    steps = []
    total = 0.0
    inconsistent_at = None

    for index, observed in enumerate(observations):
        observed = frozenset(observed)
        if surviving is None:
            before = universe_size if universe_size is not None else len(observed)
            surviving = observed
        else:
            before = len(surviving)
            surviving = surviving & observed
        bits = narrowing_bits(before, len(surviving))
        steps.append(IntersectionStep(index, len(observed), before, len(surviving), bits))
        if bits is not None:
            total += bits
        if not surviving:
            inconsistent_at = index
            break

    surviving = surviving if surviving is not None else frozenset()
    identified = None
    if inconsistent_at is None and len(surviving) == 1:
        (identified,) = surviving
    return IntersectionResult(
        surviving=surviving,
        steps=tuple(steps),
        universe_size=universe_size,
        narrowing_bits=total if surviving else None,
        identified=identified,
        inconsistent_at=inconsistent_at,
    )


# --- The results document's fixture, not part of the attack. ---------------------------------
# A generated family, so `results/RESULTS-candidate-set-intersection.md` reports the mechanism's
# behaviour on cases a reader can recompute rather than on data that is not in this checkout.

UNIVERSE = 64


def scenarios():
    """Three deterministic longitudinal runs over the same universe: converging, stalled, refusing.

    Candidates are plain integers.  Nothing here is a claim about real chain data, and nothing here
    is taken from the paper -- the shapes are chosen so each of the three outcomes is exhibited
    once, at sizes a reader can check by hand.
    """
    halving = tuple(
        frozenset(range(UNIVERSE >> k)) for k in range(1, 7)
    )                                    # 32, 16, 8, 4, 2, 1 -- every set contains 0
    repeated = tuple(frozenset(range(8)) for _ in range(4))
    contradictory = (frozenset(range(8)), frozenset(range(8, 16)), frozenset(range(4)))
    return (
        ("converging", halving),
        ("stalled", repeated),
        ("contradictory", contradictory),
    )


def manifest_invariants():
    """Population facts behind the results document, for ``reproducibility.write_manifest``.

    The source digest covers this module's text; it cannot see what the mechanism does with it.
    The writer and the test both recompute these from ``scenarios()``, so a drifting number fails
    loudly rather than standing in the document.
    """
    runs = {name: intersect_candidate_sets(obs, universe_size=UNIVERSE)
            for name, obs in scenarios()}
    return {
        "universe_size": UNIVERSE,
        "scenarios": len(runs),
        "observations_supplied": sum(len(obs) for _, obs in scenarios()),
        "converging_survivors": len(runs["converging"].surviving),
        "converging_bits": runs["converging"].narrowing_bits,
        "converging_identified": runs["converging"].identified,
        "stalled_survivors": len(runs["stalled"].surviving),
        "stalled_bits": runs["stalled"].narrowing_bits,
        "contradictory_survivors": len(runs["contradictory"].surviving),
        "contradictory_inconsistent_at": runs["contradictory"].inconsistent_at,
        "identifications": sum(1 for r in runs.values() if r.identified is not None),
        "refusals": sum(1 for r in runs.values() if r.inconsistent_at is not None),
    }
