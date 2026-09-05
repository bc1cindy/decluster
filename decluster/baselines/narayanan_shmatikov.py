"""Narayanan--Shmatikov (2009) social-graph propagation kernel.

This module deliberately contains only the topology-only propagation algorithm.  In
particular, it does not use vertex attributes, edge attributes, hub filters, rarity
weights, or single-view labels.  ``left`` and ``right`` must be distinct directed graph
views and ``seeds`` is a partial one-to-one correspondence between them.

The graph interface is the small subset exposed by :class:`views.PseudonymGraph`:
``vertices``, ``_in`` and ``_out``.  Keeping that interface structural also makes the
baseline usable by controlled synthetic tests without coupling it to Bitcoin records.

The score, eccentricity gate, direction handling, degree normalization and reverse match follow
the paper's propagation pseudocode. This is not the complete published attack: seeds are supplied
instead of found with the paper's clique search. The paper does not specify enough detail to
reproduce its occasional correction policy. Results from this module therefore test the
propagation mechanism, not an end-to-end reproduction of the 2009 experiment. The optional
conservative revisit pass is a declared local policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, sqrt
from statistics import pstdev
from typing import Hashable, Mapping

Vertex = Hashable


def eccentricity(scores: Mapping[Vertex, float]) -> float:
    """Return ``(max - second_max) / population_stddev``.

    All candidate scores, including zeros, belong to the population in the published
    algorithm.  Fewer than two candidates or zero variance cannot establish a unique
    winner and therefore have eccentricity zero.
    """

    values = list(scores.values())
    if len(values) < 2:
        return 0.0
    ordered = sorted(values, reverse=True)
    sigma = pstdev(values)
    return (ordered[0] - ordered[1]) / sigma if sigma else 0.0


def match_scores(left, right, mapping: Mapping[Vertex, Vertex], node: Vertex):
    """Compute the paper's direction-aware, degree-normalized candidate scores.

    An incoming mapped neighbour votes through incoming edges in the right view and
    contributes ``1/sqrt(candidate.in_degree)``.  Outgoing neighbours analogously use
    outgoing degree.  Already claimed right-hand vertices are excluded.
    """

    claimed = set(mapping.values())
    scores = {candidate: 0.0 for candidate in right.vertices if candidate not in claimed}

    for neighbour in sorted(left._in[node], key=repr):
        image = mapping.get(neighbour)
        if image is None:
            continue
        for candidate in sorted(right._out[image], key=repr):
            if candidate in scores:
                degree = len(right._in[candidate])
                scores[candidate] += 1.0 / sqrt(degree)

    for neighbour in sorted(left._out[node], key=repr):
        image = mapping.get(neighbour)
        if image is None:
            continue
        for candidate in sorted(right._in[image], key=repr):
            if candidate in scores:
                degree = len(right._out[candidate])
                scores[candidate] += 1.0 / sqrt(degree)

    return scores


def _winner(scores: Mapping[Vertex, float], theta: float):
    if not scores or max(scores.values()) <= 0.0 or eccentricity(scores) < theta:
        return None
    best = max(scores.values())
    winners = [node for node, score in scores.items() if score == best]
    return winners[0] if len(winners) == 1 else None


def _sparse_winner(scores: Mapping[Vertex, float], population: int, theta: float):
    """Winner with the implicit zero scores included in the candidate population.

    The paper's score has sparse support: only vertices adjacent to an already mapped
    neighbour can receive a vote.  Materialising every zero made a real 17k-by-17k run
    quadratic without changing either the mean, variance, or eccentricity.
    """

    if not scores or population < 2:
        return None
    ordered = sorted(scores.values(), reverse=True)
    best = ordered[0]
    second = ordered[1] if len(ordered) > 1 else 0.0
    if best <= 0.0 or best == second:
        return None
    total = sum(ordered)
    mean = total / population
    variance = (sum(value * value for value in ordered) / population) - mean * mean
    sigma = sqrt(max(0.0, variance))
    if not sigma or (best - second) / sigma < theta:
        return None
    winners = [node for node, score in scores.items() if score == best]
    return winners[0] if len(winners) == 1 else None


def _sparse_match_scores(left, right, mapping, node):
    claimed = set(mapping.values())
    contributions = {}

    def vote(candidate, degree):
        if candidate not in claimed and degree:
            contributions.setdefault(candidate, []).append(1.0 / sqrt(degree))

    for neighbour in left._in[node]:
        image = mapping.get(neighbour)
        if image is not None:
            for candidate in right._out[image]:
                vote(candidate, len(right._in[candidate]))
    for neighbour in left._out[node]:
        image = mapping.get(neighbour)
        if image is not None:
            for candidate in right._in[image]:
                vote(candidate, len(right._out[candidate]))
    scores = {candidate: fsum(values) for candidate, values in contributions.items()}
    return scores, len(right.vertices) - len(claimed)


@dataclass(frozen=True)
class PropagationResult:
    mapping: dict[Vertex, Vertex]
    rounds: int
    accepted_per_round: tuple[int, ...]
    revisit_policy: str = "disabled"
    remapped_per_round: tuple[int, ...] = ()


@dataclass(frozen=True)
class RevisitResult:
    mapping: dict[Vertex, Vertex]
    remapped_per_round: tuple[int, ...]


def conservative_revisit(
    left,
    right,
    accepted: Mapping[Vertex, Vertex],
    seeds: Mapping[Vertex, Vertex],
    *,
    theta: float = 1.5,
    max_rounds: int = 5,
):
    """Re-score accepted nodes without changing seeds or stealing claimed images.

    The paper mentions occasional correction but does not define its schedule or conflict
    resolution. This bounded leave-one-out policy is therefore an explicit adaptation.
    """

    if max_rounds < 0:
        raise ValueError("max_rounds must be non-negative")
    mapping = dict(accepted)
    if any(mapping.get(node) != image for node, image in seeds.items()):
        raise ValueError("accepted mapping must contain every seed unchanged")
    if len(mapping) != len(set(mapping.values())):
        raise ValueError("accepted mapping must be one-to-one")
    if not set(mapping).issubset(left.vertices):
        raise ValueError("accepted mapping contains a vertex absent from the left view")
    if not set(mapping.values()).issubset(right.vertices):
        raise ValueError("accepted mapping contains a vertex absent from the right view")
    remapped_per_round = []
    for _ in range(max_rounds):
        remapped = 0
        for node in sorted((vertex for vertex in mapping if vertex not in seeds), key=repr):
            old = mapping.pop(node)
            scores, population = _sparse_match_scores(left, right, mapping, node)
            candidate = _sparse_winner(scores, population, theta)
            if candidate is not None:
                reverse = {image: vertex for vertex, image in mapping.items()}
                reverse_scores, reverse_population = _sparse_match_scores(
                    right, left, reverse, candidate
                )
                if _sparse_winner(reverse_scores, reverse_population, theta) != node:
                    candidate = None
            mapping[node] = old if candidate is None else candidate
            remapped += candidate is not None and candidate != old
        if not remapped:
            break
        remapped_per_round.append(remapped)
    return RevisitResult(mapping, tuple(remapped_per_round))


def propagate(
    left,
    right,
    seeds: Mapping[Vertex, Vertex],
    theta: float = 1.5,
    *,
    conservative_revisit_rounds: int = 0,
):
    """Propagate a seed mapping to convergence using the 2009 scoring kernel.

    Each proposed match must clear the eccentricity threshold in both directions and
    must map back to the proposing node.  The returned mapping includes the seeds.
    """

    if conservative_revisit_rounds < 0:
        raise ValueError("conservative_revisit_rounds must be non-negative")
    mapping = dict(seeds)
    if len(mapping) != len(set(mapping.values())):
        raise ValueError("seed mapping must be one-to-one")
    if not set(mapping).issubset(left.vertices):
        raise ValueError("seed contains a vertex absent from the left view")
    if not set(mapping.values()).issubset(right.vertices):
        raise ValueError("seed contains a vertex absent from the right view")

    accepted_per_round = []
    while True:
        accepted = 0
        for node in sorted((v for v in left.vertices if v not in mapping), key=repr):
            scores, population = _sparse_match_scores(left, right, mapping, node)
            candidate = _sparse_winner(scores, population, theta)
            if candidate is None:
                continue

            reverse = {right_node: left_node for left_node, right_node in mapping.items()}
            reverse_scores, reverse_population = _sparse_match_scores(
                right, left, reverse, candidate
            )
            reverse_candidate = _sparse_winner(
                reverse_scores, reverse_population, theta
            )
            if reverse_candidate != node:
                continue
            mapping[node] = candidate
            accepted += 1
        if not accepted:
            break
        accepted_per_round.append(accepted)

    revisit = conservative_revisit(
        left,
        right,
        mapping,
        seeds,
        theta=theta,
        max_rounds=conservative_revisit_rounds,
    )
    policy = (
        "conservative_leave_one_out" if conservative_revisit_rounds else "disabled"
    )
    return PropagationResult(
        revisit.mapping,
        len(accepted_per_round),
        tuple(accepted_per_round),
        policy,
        revisit.remapped_per_round,
    )


def evaluate(mapping: Mapping[Vertex, Vertex], truth: Mapping[Vertex, Vertex], seeds=()):
    """Precision and non-seed coverage against an independently supplied truth map."""

    seed_nodes = set(seeds)
    declared = {node: image for node, image in mapping.items() if node not in seed_nodes}
    eligible = {node: image for node, image in truth.items() if node not in seed_nodes}
    correct = sum(truth.get(node) == image for node, image in declared.items())
    return {
        "declared": len(declared),
        "correct": correct,
        "eligible": len(eligible),
        "precision": correct / len(declared) if declared else None,
        "coverage": correct / len(eligible) if eligible else 0.0,
    }
