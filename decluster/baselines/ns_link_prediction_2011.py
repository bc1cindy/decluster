"""Algorithm 3 combiner from Narayanan, Shi and Rubinstein (2011).

This is one paper-faithful component, not the complete published pipeline.
The caller supplies its deterministic mapping, candidate mappings and machine-
learning scores.  Seed discovery, propagation, candidate generation and the
25-feature random forest are deliberately outside this module until separately
implemented and validated.
"""

from dataclasses import dataclass
from math import exp, sqrt
import random
from typing import Callable, Hashable, Iterable, Mapping


Vertex = Hashable
Pair = tuple[Vertex, Vertex]


@dataclass(frozen=True)
class CombinedPrediction:
    pair: Pair
    score: float
    source: str
    votes: int | None = None


@dataclass(frozen=True)
class SimilarityEvidence:
    target: Vertex
    auxiliary: Vertex
    score: float
    common_mapped_neighbours: int


class UndefinedAlgorithm2Weight(ValueError):
    """Algorithm 2's published ratio is undefined for a zero weight."""


@dataclass(frozen=True)
class TwoStageMapping:
    deterministic: dict[Vertex, Vertex]
    candidates: dict[Vertex, tuple[Vertex, ...]]
    stage1_rounds: int


def algorithm2_pair_distance(left: float, right: float, *, alpha=0.5) -> float:
    """The paper's ``(max(x/y, y/x) - 1)^alpha`` pair distance.

    The publication specifies no zero convention. Refusing that domain keeps
    an implementation choice from being misattributed to the paper.
    """

    if left <= 0 or right <= 0:
        raise UndefinedAlgorithm2Weight(
            "Algorithm 2 does not define ratios involving zero weights"
        )
    ratio = max(left / right, right / left)
    return (ratio - 1) ** alpha


def algorithm2_node_distance(
    target_nodes,
    auxiliary_nodes,
    target_dummies,
    auxiliary_dummies,
    target_weight,
    auxiliary_weight,
    index,
    *,
    alpha=0.5,
    beta=0.5,
) -> float:
    """Algorithm 2's distance for one pair of mapped nodes."""

    target_nodes, auxiliary_nodes = tuple(target_nodes), tuple(auxiliary_nodes)
    if len(target_nodes) != len(auxiliary_nodes):
        raise ValueError("mapped node sequences must have equal length")
    if not 0 <= index < len(target_nodes):
        raise IndexError("mapped-node index out of range")
    target_dummies, auxiliary_dummies = set(target_dummies), set(auxiliary_dummies)
    target_vector = tuple(
        float(target_weight(target_nodes[index], node))
        for position, node in enumerate(target_nodes)
        if position != index and node not in target_dummies
    )
    auxiliary_vector = tuple(
        float(auxiliary_weight(auxiliary_nodes[index], node))
        for position, node in enumerate(auxiliary_nodes)
        if position != index and node not in auxiliary_dummies
    )
    if len(target_vector) != len(auxiliary_vector) or not target_vector:
        raise ValueError("Algorithm 2 requires paired non-dummy weight vectors")
    target_mean = sum(target_vector) / len(target_vector)
    auxiliary_mean = sum(auxiliary_vector) / len(auxiliary_vector)
    if target_mean <= 0 or auxiliary_mean <= 0:
        raise UndefinedAlgorithm2Weight("Algorithm 2 normalization has a zero mean")
    normalized = zip(
        (value / target_mean for value in target_vector),
        (value / auxiliary_mean for value in auxiliary_vector),
    )
    distance = sum(
        algorithm2_pair_distance(left, right, alpha=alpha)
        for left, right in normalized
    )
    return (target_mean * auxiliary_mean) ** (beta / 2) * distance


def algorithm2_potential(
    target_nodes,
    auxiliary_nodes,
    target_dummies,
    auxiliary_dummies,
    target_weight,
    auxiliary_weight,
    *,
    alpha=0.5,
    beta=0.5,
) -> float:
    """Sum Algorithm 2's node distance over the current bijection."""

    target_nodes, auxiliary_nodes = tuple(target_nodes), tuple(auxiliary_nodes)
    return sum(
        algorithm2_node_distance(
            target_nodes, auxiliary_nodes, target_dummies, auxiliary_dummies,
            target_weight, auxiliary_weight, index, alpha=alpha, beta=beta,
        )
        for index in range(len(target_nodes))
    )


def anneal_seed_mapping(
    target_nodes,
    auxiliary_nodes,
    target_dummies,
    auxiliary_dummies,
    target_weight,
    auxiliary_weight,
    *,
    iterations: int,
    rng: random.Random,
):
    """Paper-specified swap transitions and ``T=1/t, c=20n`` schedule.

    The fixed iteration budget and injected RNG are reproducibility controls,
    not parameters reported by the paper. The best visited bijection is
    returned rather than whichever state happens to be last.
    """

    target_nodes, auxiliary_nodes = tuple(target_nodes), list(auxiliary_nodes)
    if len(target_nodes) != len(auxiliary_nodes) or len(target_nodes) < 2:
        raise ValueError("annealing requires equally sized node sets of size at least two")
    if iterations < 0:
        raise ValueError("iterations must be non-negative")
    if tuple(target_dummies) or tuple(auxiliary_dummies):
        raise UndefinedAlgorithm2Weight(
            "the published distance assigns zero incident weights to dummies "
            "but does not define its resulting zero ratios"
        )
    rng.shuffle(auxiliary_nodes)

    def potential(order):
        return algorithm2_potential(
            target_nodes, order, target_dummies, auxiliary_dummies,
            target_weight, auxiliary_weight,
        )

    current = potential(auxiliary_nodes)
    best_order, best = tuple(auxiliary_nodes), current
    n = len(target_nodes)
    for iteration in range(1, iterations + 1):
        first, second = rng.sample(range(n), 2)
        auxiliary_nodes[first], auxiliary_nodes[second] = (
            auxiliary_nodes[second], auxiliary_nodes[first]
        )
        candidate = potential(auxiliary_nodes)
        delta = candidate - current
        if delta <= 0 or rng.random() < exp(-delta * iteration / (20 * n)):
            current = candidate
            if candidate < best:
                best_order, best = tuple(auxiliary_nodes), candidate
        else:
            auxiliary_nodes[first], auxiliary_nodes[second] = (
                auxiliary_nodes[second], auxiliary_nodes[first]
            )
    return dict(zip(target_nodes, best_order)), best


def similarity_evidence(
    target_graph,
    auxiliary_graph,
    target: Vertex,
    auxiliary: Vertex,
    mapping: Mapping[Vertex, Vertex],
    *,
    crawled_target: Iterable[Vertex],
    crawled_auxiliary: Iterable[Vertex],
) -> SimilarityEvidence:
    """Compute the directed, crawl-aware similarity in the paper's Algorithm 1."""

    crawled_target = set(crawled_target)
    crawled_auxiliary = set(crawled_auxiliary)
    mapped_domain = set(mapping)
    mapped_crawled = {mapping[v] for v in crawled_target if v in mapping}

    target_neighbours = {
        mapping[v] for v in target_graph._in.get(target, ())
        if v in mapped_domain and mapping[v] in crawled_auxiliary
    }
    auxiliary_neighbours = (
        set(auxiliary_graph._in.get(auxiliary, ())) & mapped_crawled
    )
    if target in crawled_target and auxiliary in crawled_auxiliary:
        target_neighbours.update(
            mapping[v] for v in target_graph._out.get(target, ()) if v in mapped_domain
        )
        auxiliary_neighbours.update(
            set(auxiliary_graph._out.get(auxiliary, ()))
            & {mapping[v] for v in mapped_domain}
        )

    common = len(target_neighbours & auxiliary_neighbours)
    denominator = sqrt(len(target_neighbours) * len(auxiliary_neighbours))
    return SimilarityEvidence(
        target, auxiliary, common / denominator if denominator else 0.0, common
    )


def stage1_match(evidence: Iterable[SimilarityEvidence], *, k=4, theta=0.5, delta=0.2):
    """Select the unique high-confidence stage-1 match, or refuse.

    Evidence must concern one target node. The best candidate needs at least
    ``k`` mapped-neighbour pairs, score ``theta``, and a ``delta`` lead over
    the runner-up, matching the paper's published parameters by default.
    """

    ranked = sorted(evidence, key=lambda row: (-row.score, repr(row.auxiliary)))
    if not ranked:
        return None
    if any(row.target != ranked[0].target for row in ranked):
        raise ValueError("stage1 evidence must describe one target vertex")
    best = ranked[0]
    second_score = ranked[1].score if len(ranked) > 1 else 0.0
    if (best.common_mapped_neighbours >= k and best.score >= theta
            and best.score - second_score >= delta):
        return best.auxiliary
    return None


def stage2_candidates(evidence: Iterable[SimilarityEvidence], *, k=3, theta=0.5, limit=3):
    """Return up to the three best relaxed-stage candidates.

    These candidates are intentionally not fed back into similarity scoring;
    the caller receives an immutable tuple and must keep it separate from the
    deterministic stage-1 mapping.
    """

    if limit < 1:
        raise ValueError("limit must be positive")
    evidence = tuple(evidence)
    if evidence and any(row.target != evidence[0].target for row in evidence):
        raise ValueError("stage2 evidence must describe one target vertex")
    eligible = [row for row in evidence
                if row.common_mapped_neighbours >= k and row.score >= theta]
    eligible.sort(key=lambda row: (-row.score, repr(row.auxiliary)))
    return tuple(row.auxiliary for row in eligible[:limit])


def two_stage_mapping(
    target_graph,
    auxiliary_graph,
    seeds: Mapping[Vertex, Vertex],
    target_vertices: Iterable[Vertex],
    auxiliary_vertices: Iterable[Vertex],
    *,
    crawled_target: Iterable[Vertex],
    crawled_auxiliary: Iterable[Vertex],
    stage1_k=4,
    stage1_theta=0.5,
    stage1_delta=0.2,
    stage2_k=3,
    stage2_theta=0.5,
    stage2_limit=3,
) -> TwoStageMapping:
    """Run the specified self-feeding stage 1 and non-feeding stage 2.

    Vertex iteration is canonicalized by ``repr`` so "pick an arbitrary node"
    becomes reproducible. This driver does not claim the paper's unspecified
    confidence-pruning or occasional correction of accepted mappings.
    """

    target_vertices = tuple(sorted(set(target_vertices), key=repr))
    auxiliary_vertices = tuple(sorted(set(auxiliary_vertices), key=repr))
    crawled_target, crawled_auxiliary = set(crawled_target), set(crawled_auxiliary)
    mapping = dict(seeds)
    if not set(mapping) <= set(target_vertices):
        raise ValueError("seed domain must be part of target_vertices")
    if not set(mapping.values()) <= set(auxiliary_vertices):
        raise ValueError("seed images must be part of auxiliary_vertices")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("seed mapping must be one-to-one")

    rounds = 0
    while True:
        changed = False
        used_images = set(mapping.values())
        for target in target_vertices:
            if target in mapping:
                continue
            unused = [vertex for vertex in auxiliary_vertices
                      if vertex not in used_images]
            evidence = [
                similarity_evidence(
                    target_graph, auxiliary_graph, target, auxiliary, mapping,
                    crawled_target=crawled_target,
                    crawled_auxiliary=crawled_auxiliary,
                )
                for auxiliary in unused
            ]
            match = stage1_match(
                evidence, k=stage1_k, theta=stage1_theta, delta=stage1_delta
            )
            if match is not None:
                mapping[target] = match
                used_images.add(match)
                changed = True
        if not changed:
            break
        rounds += 1

    candidate_sets = {}
    used = set(mapping.values())
    for target in target_vertices:
        if target in mapping:
            continue
        evidence = [
            similarity_evidence(
                target_graph, auxiliary_graph, target, auxiliary, mapping,
                crawled_target=crawled_target,
                crawled_auxiliary=crawled_auxiliary,
            )
            for auxiliary in auxiliary_vertices if auxiliary not in used
        ]
        candidates = stage2_candidates(
            evidence, k=stage2_k, theta=stage2_theta, limit=stage2_limit
        )
        if candidates:
            candidate_sets[target] = candidates
    return TwoStageMapping(mapping, candidate_sets, rounds)


def combine_predictions(
    test_pairs: Iterable[Pair],
    auxiliary_edges: Iterable[Pair],
    deterministic_mapping: Mapping[Vertex, Vertex],
    candidate_mapping: Mapping[Vertex, Iterable[Vertex]],
    ml_score: Callable[[Pair], float],
) -> tuple[CombinedPrediction, ...]:
    """Apply the paper's deterministic / unanimous-vote / ML cascade.

    Auxiliary edges are directed, as in the paper's Flickr graph. Candidate
    iterables are canonicalized to sets. A unanimous vote examines the full
    Cartesian product, so duplicate candidates cannot change its outcome.
    """

    edges = set(auxiliary_edges)
    candidates = {vertex: frozenset(images)
                  for vertex, images in candidate_mapping.items()}
    predictions = []
    for pair in test_pairs:
        left, right = pair
        if left in deterministic_mapping and right in deterministic_mapping:
            edge = (deterministic_mapping[left], deterministic_mapping[right])
            predictions.append(CombinedPrediction(pair, float(edge in edges), "deanonymized", 1))
            continue

        left_candidates = candidates.get(left, frozenset())
        right_candidates = candidates.get(right, frozenset())
        if left_candidates and right_candidates:
            votes = tuple(
                (left_image, right_image) in edges
                for left_image in left_candidates
                for right_image in right_candidates
            )
            if all(votes):
                predictions.append(CombinedPrediction(pair, 1.0, "unanimous_vote", len(votes)))
                continue
            if not any(votes):
                predictions.append(CombinedPrediction(pair, 0.0, "unanimous_vote", len(votes)))
                continue

        predictions.append(CombinedPrediction(pair, float(ml_score(pair)), "machine_learning"))
    return tuple(predictions)
