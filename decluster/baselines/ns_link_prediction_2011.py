"""Algorithm 3 combiner from Narayanan, Shi and Rubinstein (2011).

This is one paper-faithful component, not the complete published pipeline.
The caller supplies its deterministic mapping, candidate mappings and machine-
learning scores.  Seed discovery, propagation, candidate generation and the
25-feature random forest are deliberately outside this module until separately
implemented and validated.
"""

from dataclasses import dataclass
from math import sqrt
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
