"""Components of Narayanan, Shi and Rubinstein (2011), one at a time.

These are paper-faithful components, not the complete published pipeline:
Algorithm 1's similarity, Algorithm 2's distance and its annealer, the two-stage
propagation, and the Algorithm 3 cascade, which takes its machine-learning score
from the caller.  Confidence pruning, the correction of accepted mappings and the
25-feature random forest are absent.  :func:`pipeline_coverage` is the machine-
readable version of that boundary and :func:`require_components` enforces it.

Source: `ns-linkpred` in `catalog/ctp-sources.json` — Narayanan, Shi & Rubinstein,
*Link Prediction by De-anonymization* (2011).
"""

from dataclasses import dataclass
from enum import Enum
from math import exp, sqrt
import random
from typing import Callable, Hashable, Iterable, Mapping


Vertex = Hashable
Pair = tuple[Vertex, Vertex]


class ComponentStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    MATHEMATICALLY_UNDEFINED = "mathematically_undefined"
    NOT_REPRODUCED = "not_reproduced"


class PipelineComponent(str, Enum):
    ALGORITHM1_SIMILARITY = "algorithm1_similarity"
    ALGORITHM2_POSITIVE_WEIGHTS = "algorithm2_positive_weights"
    ALGORITHM2_DUMMY_WEIGHTS = "algorithm2_dummy_weights"
    ANNEALING = "annealing"
    TWO_STAGE_MAPPING = "two_stage_mapping"
    CONFIDENCE_PRUNING = "confidence_pruning"
    ACCEPTED_MAPPING_CORRECTION = "accepted_mapping_correction"
    ALGORITHM3_CASCADE = "algorithm3_cascade"
    LEARNED_25_FEATURE_MODEL = "learned_25_feature_model"


@dataclass(frozen=True)
class ComponentCoverage:
    component: PipelineComponent
    status: ComponentStatus
    limitation: str | None = None


class IncompletePipelineError(ValueError):
    """A caller requested components this baseline does not reproduce."""


def pipeline_coverage() -> tuple[ComponentCoverage, ...]:
    """Return the executable boundary of the 2011 baseline.

    ``implemented`` applies only to the named component, not the paper's end-to-end experiment.
    The annealer is partial because its fixed iteration budget, RNG injection and best-state return
    are reproducibility controls rather than parameters reported by the paper.
    """

    return (
        ComponentCoverage(PipelineComponent.ALGORITHM1_SIMILARITY, ComponentStatus.IMPLEMENTED),
        ComponentCoverage(
            PipelineComponent.ALGORITHM2_POSITIVE_WEIGHTS, ComponentStatus.IMPLEMENTED
        ),
        ComponentCoverage(
            PipelineComponent.ALGORITHM2_DUMMY_WEIGHTS,
            ComponentStatus.IMPLEMENTED,
            "a dummy-incident node term is fixed at zero; the paper states this in prose, "
            "not in the printed formula",
        ),
        ComponentCoverage(
            PipelineComponent.ANNEALING,
            ComponentStatus.PARTIAL,
            "iteration budget, RNG and best-state return are explicit local controls",
        ),
        ComponentCoverage(
            PipelineComponent.TWO_STAGE_MAPPING,
            ComponentStatus.IMPLEMENTED,
            "the paper picks an arbitrary unmapped node and stage 1 feeds back, so the "
            "``repr`` order this driver imposes is a result-bearing local choice; injectivity "
            "comes from Algorithm 3's 1-1 mapping, not from the propagation section",
        ),
        ComponentCoverage(
            PipelineComponent.CONFIDENCE_PRUNING,
            ComponentStatus.NOT_REPRODUCED,
            "an implementation-complete pruning policy is not available",
        ),
        ComponentCoverage(
            PipelineComponent.ACCEPTED_MAPPING_CORRECTION,
            ComponentStatus.NOT_REPRODUCED,
            "schedule and conflict resolution are not specified sufficiently",
        ),
        ComponentCoverage(PipelineComponent.ALGORITHM3_CASCADE, ComponentStatus.IMPLEMENTED),
        ComponentCoverage(
            PipelineComponent.LEARNED_25_FEATURE_MODEL,
            ComponentStatus.NOT_REPRODUCED,
            "the caller supplies an ML score; the published feature producer is absent",
        ),
    )


def require_components(*components: PipelineComponent) -> None:
    """Refuse unless every requested component is implemented in this baseline."""

    coverage = {row.component: row for row in pipeline_coverage()}
    unavailable = [coverage[component] for component in components
                   if coverage[component].status is not ComponentStatus.IMPLEMENTED]
    if unavailable:
        details = ", ".join(
            f"{row.component.value}={row.status.value}" for row in unavailable
        )
        raise IncompletePipelineError(f"N-S 2011 pipeline components unavailable: {details}")


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
    """Algorithm 2's published ratio has no value for the arguments it was given."""


@dataclass(frozen=True)
class TwoStageMapping:
    deterministic: dict[Vertex, Vertex]
    candidates: dict[Vertex, tuple[Vertex, ...]]
    stage1_rounds: int


def algorithm2_pair_distance(left: float, right: float, *, alpha=0.5) -> float:
    """The paper's ``(max(x/y, y/x) - 1)^alpha`` pair distance.

    Only zero against zero is undefined. A zero against a positive weight is an infinite
    ratio and so an infinite penalty, which is what the printed formula says rather than a
    convention added here; the weights are in-neighbourhood cosines, so zeros between real
    nodes are ordinary and a state can legitimately carry infinite potential.
    """

    if left < 0 or right < 0:
        raise ValueError("Algorithm 2 weights must be non-negative")
    if not left and not right:
        raise UndefinedAlgorithm2Weight(
            "Algorithm 2 does not define the ratio of two zero weights"
        )
    if not left or not right:
        return float("inf")
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
    """Algorithm 2's distance for one pair of mapped nodes.

    A node incident only on dummies has an all-zero weight vector and so a zero mean, and the
    paper fixes the resulting term at zero in prose: every edge incident on a dummy has weight
    zero, which is why "adding k dummy nodes ... has the effect of finding a mapping of size
    n - k" and why a dummy-to-dummy pair is "sub-optimal ... improvable in 1 step". Both
    statements are true only when a dummy-incident term costs nothing, so the convention is a
    reading of the paper rather than an invention. Refusing it instead pins the annealer at
    zero dummies, where the paper reports output no better than a random permutation.

    The paper's index conditions are per graph — a position is dropped from one vector when it
    holds a dummy in *that* graph — while ``PairDist(sigmaK[j], sigmaF[j])`` reads both vectors
    at one ``j``. When the two graphs put their dummies at different positions the vectors line
    up in length but not in index, and the paper does not say which pairing it means. This
    implementation pairs by position within each filtered vector, and refuses outright when the
    lengths do not even match.
    """

    target_nodes, auxiliary_nodes = tuple(target_nodes), tuple(auxiliary_nodes)
    if len(target_nodes) != len(auxiliary_nodes):
        raise ValueError("mapped node sequences must have equal length")
    if not 0 <= index < len(target_nodes):
        raise IndexError("mapped-node index out of range")
    target_dummies, auxiliary_dummies = set(target_dummies), set(auxiliary_dummies)
    if (target_nodes[index] in target_dummies
            or auxiliary_nodes[index] in auxiliary_dummies):
        return 0.0
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
    if not target_vector or not auxiliary_vector:
        raise ValueError("Algorithm 2 requires a non-empty non-dummy weight vector")
    if len(target_vector) != len(auxiliary_vector):
        raise ValueError(
            "unequal numbers of dummies leave the per-graph index conditions of Algorithm 2 "
            "with no common index to pair on"
        )
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

    Dummies are supported under the zero convention :func:`algorithm2_node_distance`
    documents, which is what lets the annealer return a partial mapping of size ``n - k``.
    """

    target_nodes, auxiliary_nodes = tuple(target_nodes), list(auxiliary_nodes)
    if len(target_nodes) != len(auxiliary_nodes) or len(target_nodes) < 2:
        raise ValueError("annealing requires equally sized node sets of size at least two")
    if iterations < 0:
        raise ValueError("iterations must be non-negative")
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
    """Compute the directed, crawl-aware similarity in the paper's Algorithm 1.

    Cosine similarity is undefined when either neighbourhood is empty, and the paper says
    nothing about that case either. Scoring it ``0.0`` is a declared convention of this
    module, matching the zero convention :func:`algorithm2_node_distance` takes for the same
    shape of degeneracy in Algorithm 2: an empty neighbourhood is no evidence, and no
    evidence must not become a match.
    """

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

    This is the stage 2 of the propagation section: ``k = 3``, the margin criterion dropped,
    and the best three candidates at or above ``theta``. The paper's voting coverage figures
    come from a *different* run of stage 2, preceded by a prune of the de-anonymization
    output by confidence score and with the "sufficiently similar" criterion eliminated
    altogether so that far more candidates survive. Neither the prune nor that variant is
    reproduced here, so no voting coverage number may be read off this function.
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
