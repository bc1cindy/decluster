"""Executable contract for Algorithm 3 of Narayanan–Shi–Rubinstein (2011)."""

from decluster.baselines.ns_link_prediction_2011 import (
    SimilarityEvidence,
    combine_predictions,
    similarity_evidence,
    stage1_match,
    stage2_candidates,
)
from examples.link_prediction_run import directed_graph


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
