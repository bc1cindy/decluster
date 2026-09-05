"""Executable contract for Algorithm 3 of Narayanan–Shi–Rubinstein (2011)."""

from decluster.baselines.ns_link_prediction_2011 import (
    ComponentStatus,
    IncompletePipelineError,
    PipelineComponent,
    SimilarityEvidence,
    UndefinedAlgorithm2Weight,
    algorithm2_pair_distance,
    algorithm2_potential,
    anneal_seed_mapping,
    combine_predictions,
    pipeline_coverage,
    require_components,
    similarity_evidence,
    stage1_match,
    stage2_candidates,
    two_stage_mapping,
)
import random
import pytest
from examples.link_prediction_run import directed_graph


def test_pipeline_coverage_separates_components_from_end_to_end_reproduction():
    coverage = {row.component: row for row in pipeline_coverage()}

    assert set(coverage) == set(PipelineComponent)
    assert coverage[PipelineComponent.ALGORITHM1_SIMILARITY].status is ComponentStatus.IMPLEMENTED
    assert coverage[PipelineComponent.ANNEALING].status is ComponentStatus.PARTIAL
    assert (
        coverage[PipelineComponent.ALGORITHM2_DUMMY_WEIGHTS].status
        is ComponentStatus.MATHEMATICALLY_UNDEFINED
    )
    assert (
        coverage[PipelineComponent.CONFIDENCE_PRUNING].status
        is ComponentStatus.NOT_REPRODUCED
    )
    assert (
        coverage[PipelineComponent.LEARNED_25_FEATURE_MODEL].status
        is ComponentStatus.NOT_REPRODUCED
    )


def test_component_gate_accepts_only_fully_implemented_parts():
    require_components(
        PipelineComponent.ALGORITHM1_SIMILARITY,
        PipelineComponent.ALGORITHM3_CASCADE,
    )
    with pytest.raises(IncompletePipelineError, match="dummy_weights=mathematically_undefined"):
        require_components(PipelineComponent.ALGORITHM2_DUMMY_WEIGHTS)
    with pytest.raises(IncompletePipelineError, match="annealing=partial"):
        require_components(PipelineComponent.ANNEALING)


def test_algorithm1_uses_in_neighbours_and_conditionally_uses_out_neighbours():
    target = directed_graph(["k", "ki", "ko"], [("ki", "k"), ("k", "ko")])
    auxiliary = directed_graph(["f", "fi", "fo"], [("fi", "f"), ("f", "fo")])
    mapping = {"ki": "fi", "ko": "fo"}

    uncrawled = similarity_evidence(
        target, auxiliary, "k", "f", mapping,
        crawled_target={"ki", "ko"}, crawled_auxiliary={"fi", "fo"},
    )
    assert (uncrawled.score, uncrawled.common_mapped_neighbours) == (1.0, 1)

    crawled = similarity_evidence(
        target, auxiliary, "k", "f", mapping,
        crawled_target={"k", "ki", "ko"}, crawled_auxiliary={"f", "fi", "fo"},
    )
    assert (crawled.score, crawled.common_mapped_neighbours) == (1.0, 2)


def test_published_stage1_thresholds_require_support_score_and_margin():
    rows = [
        SimilarityEvidence("k", "best", 0.7, 4),
        SimilarityEvidence("k", "second", 0.49, 4),
    ]
    assert stage1_match(rows) == "best"
    assert stage1_match([rows[0], SimilarityEvidence("k", "close", 0.51, 4)]) is None
    assert stage1_match([SimilarityEvidence("k", "weak", 0.9, 3)]) is None


def test_stage2_drops_margin_and_returns_at_most_three_eligible_candidates():
    rows = [SimilarityEvidence("k", f"f{i}", score, support) for i, (score, support) in enumerate([
        (0.9, 3), (0.8, 4), (0.7, 3), (0.6, 3), (0.99, 2), (0.49, 9)
    ])]
    assert stage2_candidates(rows) == ("f0", "f1", "f2")


def test_algorithm2_pair_distance_is_symmetric_and_refuses_unspecified_zero_case():
    assert algorithm2_pair_distance(1, 4) == algorithm2_pair_distance(4, 1) == 3 ** 0.5
    with pytest.raises(UndefinedAlgorithm2Weight, match="zero weights"):
        algorithm2_pair_distance(0, 1)


def test_algorithm2_potential_prefers_the_weight_preserving_bijection():
    nodes = ("a", "b", "c")
    images = ("A", "B", "C")
    target = {("a", "b"): 1, ("a", "c"): 4, ("b", "c"): 2}
    auxiliary = {("A", "B"): 1, ("A", "C"): 4, ("B", "C"): 2}

    def weight(table):
        return lambda left, right: table.get((left, right), table.get((right, left)))

    exact = algorithm2_potential(nodes, images, (), (), weight(target), weight(auxiliary))
    swapped = algorithm2_potential(nodes, ("B", "A", "C"), (), (),
                                   weight(target), weight(auxiliary))
    assert exact == 0.0
    assert swapped > exact


def test_seed_annealing_is_reproducible_and_returns_best_visited_mapping():
    nodes = ("a", "b", "c")
    images = ("A", "B", "C")
    target = {("a", "b"): 1, ("a", "c"): 4, ("b", "c"): 2}
    auxiliary = {("A", "B"): 1, ("A", "C"): 4, ("B", "C"): 2}

    def weight(table):
        return lambda left, right: table.get((left, right), table.get((right, left)))

    first = anneal_seed_mapping(nodes, images, (), (), weight(target), weight(auxiliary),
                                iterations=200, rng=random.Random(3))
    second = anneal_seed_mapping(nodes, images, (), (), weight(target), weight(auxiliary),
                                 iterations=200, rng=random.Random(3))
    assert first == second == ({"a": "A", "b": "B", "c": "C"}, 0.0)


def test_annealing_refuses_to_invent_the_papers_missing_dummy_zero_policy():
    with pytest.raises(UndefinedAlgorithm2Weight, match="dummies"):
        anneal_seed_mapping(
            ("a", "dummy-k"), ("A", "dummy-f"), {"dummy-k"}, {"dummy-f"},
            lambda left, right: 1.0, lambda left, right: 1.0,
            iterations=1, rng=random.Random(0),
        )


def test_two_stage_driver_feeds_stage1_back_but_not_stage2_candidates():
    # Seeds s/t expose x; accepting x immediately supplies the second mapped
    # neighbour needed to accept y later in the same deterministic pass.
    target = directed_graph(
        ["s", "t", "x", "y"],
        [("s", "x"), ("t", "x"), ("s", "y"), ("x", "y")],
    )
    auxiliary = directed_graph(
        ["S", "T", "X", "Y", "noise"],
        [("S", "X"), ("T", "X"), ("S", "Y"), ("X", "Y"), ("S", "noise")],
    )
    result = two_stage_mapping(
        target, auxiliary, {"s": "S", "t": "T"}, ["s", "t", "x", "y"],
        ["S", "T", "X", "Y", "noise"],
        crawled_target=target.vertices, crawled_auxiliary=auxiliary.vertices,
        stage1_k=2, stage1_theta=0.5, stage1_delta=0.2,
        stage2_k=1, stage2_theta=0.5,
    )
    assert result.deterministic == {"s": "S", "t": "T", "x": "X", "y": "Y"}
    assert result.candidates == {}
    assert result.stage1_rounds == 1


def test_two_stage_driver_keeps_relaxed_candidates_out_of_deterministic_mapping():
    target = directed_graph(["s", "a"], [("s", "a")])
    auxiliary = directed_graph(["S", "A", "B"], [("S", "A"), ("S", "B")])
    result = two_stage_mapping(
        target, auxiliary, {"s": "S"}, ["s", "a"], ["S", "A", "B"],
        crawled_target=target.vertices, crawled_auxiliary=auxiliary.vertices,
        stage1_k=1, stage1_theta=0.5, stage1_delta=0.2,
        stage2_k=1, stage2_theta=0.5,
    )
    assert result.deterministic == {"s": "S"}
    assert result.candidates == {"a": ("A", "B")}


def test_deterministic_mapping_has_first_precedence():
    result = combine_predictions(
        [("a", "b")], {("A", "B")}, {"a": "A", "b": "B"},
        {"a": {"wrong"}, "b": {"wrong"}}, lambda pair: 0.25,
    )
    assert (result[0].score, result[0].source) == (1.0, "deanonymized")


def test_candidate_cartesian_product_can_vote_unanimously_for_edge_or_non_edge():
    results = combine_predictions(
        [("yes-a", "yes-b"), ("no-a", "no-b")],
        {("A1", "B1"), ("A1", "B2"), ("A2", "B1"), ("A2", "B2")},
        {},
        {
            "yes-a": {"A1", "A2"}, "yes-b": {"B1", "B2"},
            "no-a": {"X1", "X2"}, "no-b": {"Y1", "Y2"},
        },
        lambda pair: 0.25,
    )
    assert [(row.score, row.source, row.votes) for row in results] == [
        (1.0, "unanimous_vote", 4),
        (0.0, "unanimous_vote", 4),
    ]


def test_split_vote_and_missing_candidates_fall_back_to_ml():
    scores = {("split-a", "split-b"): 0.75, ("missing", "split-b"): 0.2}
    results = combine_predictions(
        scores, {("A1", "B1")}, {},
        {"split-a": {"A1", "A2"}, "split-b": {"B1"}}, scores.__getitem__,
    )
    assert [(row.score, row.source, row.votes) for row in results] == [
        (0.75, "machine_learning", None),
        (0.2, "machine_learning", None),
    ]


def test_auxiliary_edges_are_directional_and_duplicate_candidates_have_no_weight():
    result = combine_predictions(
        [("a", "b")], {("B", "A")}, {},
        {"a": ["A", "A"], "b": ["B", "B"]}, lambda pair: 0.4,
    )
    assert (result[0].score, result[0].source, result[0].votes) == (
        0.0, "unanimous_vote", 1
    )
