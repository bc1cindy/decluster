"""Algorithm 3 combiner from Narayanan, Shi and Rubinstein (2011).

This is one paper-faithful component, not the complete published pipeline.
The caller supplies its deterministic mapping, candidate mappings and machine-
learning scores.  Seed discovery, propagation, candidate generation and the
25-feature random forest are deliberately outside this module until separately
implemented and validated.
"""

from dataclasses import dataclass
from typing import Callable, Hashable, Iterable, Mapping


Vertex = Hashable
Pair = tuple[Vertex, Vertex]


@dataclass(frozen=True)
class CombinedPrediction:
    pair: Pair
    score: float
    source: str
    votes: int | None = None


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
