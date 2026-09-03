"""De-anonymization-driven link prediction against the same predictor without the mapping.

Every fixture here is synthetic and controlled.  The direction is asserted, never a recorded
number, so a change in the mechanism that moves the numbers without inverting the finding does
not fail; the published numbers are pinned by the manifest test at the bottom instead.
"""
import os
import random

import pytest

from decluster import reproducibility as rp
from decluster.baselines import link_prediction as lp
from decluster.graph_deanon import structural_score
from examples.link_prediction_run import (MANIFEST_DOC, MANIFEST_SOURCE, build_parser,
                                          build_report, directed_graph, manifest_invariants,
                                          planted_views, run_fixture, sampled_seeds)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def args(**overrides):
    parsed = build_parser().parse_args([])
    for key, value in overrides.items():
        setattr(parsed, key, value)
    return parsed


def fixture(seed=0, **overrides):
    return planted_views(args(**overrides), random.Random(seed))


def arm(report, name):
    return next(run for run in report["runs"] if run["arm"] == name)


def test_transfer_pulls_back_only_edges_whose_endpoints_are_both_mapped():
    target = directed_graph(["a0", "a1", "a2"], [("a0", "a1")])
    auxiliary = directed_graph(["b0", "b1", "b2", "b3"],
                               [("b1", "b2"), ("b2", "b3"), ("b0", "b3")])
    # b3 is not an image, so neither of its edges can say anything about the target view.
    neighbours, new_pairs = lp.transferred_neighbourhoods(
        target, auxiliary, {"a0": "b0", "a1": "b1", "a2": "b2"})
    assert new_pairs == 1
    assert neighbours["a1"] == {"a0", "a2"}
    assert neighbours["a2"] == {"a1"}


def test_score_is_common_neighbours_on_a_pair_the_graph_does_not_join():
    target = directed_graph(["a0", "a1", "a2", "a3"],
                            [("a0", "a2"), ("a1", "a2"), ("a0", "a3"), ("a1", "a3")])
    neighbours = lp.neighbourhoods(target)
    assert lp.score(neighbours, "a0", "a1") == structural_score("a0", "a1", neighbours) == 2


def test_a_directly_transferred_edge_scores_above_the_pairs_common_neighbours():
    """The auxiliary view's plainest statement is that the two transacted; the score has to
    carry it, and it is the closed neighbourhood that does."""
    target = directed_graph(["a0", "a1"], [])
    auxiliary = directed_graph(["b0", "b1"], [("b0", "b1")])
    neighbours, _ = lp.transferred_neighbourhoods(target, auxiliary, {"a0": "b0", "a1": "b1"})
    assert structural_score("a0", "a1", neighbours) == 0
    assert lp.score(neighbours, "a0", "a1") == 2


def test_candidate_pairs_are_the_pairs_the_view_does_not_join():
    target = directed_graph(["a0", "a1", "a2"], [("a0", "a1")])
    assert lp.candidate_pairs(target) == [("a0", "a2"), ("a1", "a2")]


def test_candidates_already_joined_by_the_target_view_are_refused():
    target = directed_graph(["a0", "a1"], [("a0", "a1")])
    auxiliary = directed_graph(["b0", "b1"], [("b0", "b1")])
    with pytest.raises(ValueError, match="already an edge"):
        lp.compare(target, auxiliary, {"a0": "b0"}, [("a0", "a1")], [],
                   seed_provenance="test")


def test_predictions_are_ranked_by_score():
    views = fixture()
    seeds = sampled_seeds(views["correspondence"], 0.25, random.Random(1))
    prediction = lp.predict(views["target"], views["auxiliary"], seeds,
                            views["held_out"] + views["negatives"], seed_provenance="test")
    ranked = prediction.ranked()
    assert [score for _, score in ranked] == sorted((s for s in prediction.scores), reverse=True)
    assert set(prediction.declared(cutoff=2)) == {pair for pair, s in ranked if s >= 2}


@pytest.mark.parametrize("fixture_seed", [0, 1, 2, 3, 4])
def test_deanonymization_beats_structure_only_on_planted_views(fixture_seed):
    """The published claim's direction, on views built so the structure-only arm has real
    signal to find: the communities are what a common-neighbour predictor lives on."""
    report = run_fixture(args(), fixture_seed)
    attack = arm(report, "attack")
    ceiling = arm(report, "perfect-mapping-ceiling")
    assert attack["separability"]["beats_structure_only"] == "a"
    assert attack["deanonymization"]["auc"] > attack["structure_only"]["auc"]
    # The recall comparison cannot invert (see the dominance test below), so it is a level and
    # not a finding; the AUC and the paired verdict are what carry the direction.
    assert attack["deanonymization"]["recall"] > attack["structure_only"]["recall"]
    # Propagation coverage, not the transfer, is what the attack arm is short of.
    assert ceiling["deanonymization"]["recall"] > attack["deanonymization"]["recall"]


def test_the_deanonymization_score_dominates_the_structure_only_score_on_every_pair():
    """A property of the construction, published so it is not read as a finding: the transfer
    only ever adds neighbours, so the de-anonymization arm's declaration set is a superset at
    any cutoff and its recall can never come out lower."""
    views = fixture()
    seeds = sampled_seeds(views["correspondence"], 0.25, random.Random(1))
    pairs = views["held_out"] + views["negatives"]
    prediction = lp.predict(views["target"], views["auxiliary"], seeds, pairs,
                            seed_provenance="test")
    structure = lp.neighbourhoods(views["target"])
    assert all(transferred >= lp.score(structure, *pair)
               for pair, transferred in zip(prediction.candidates, prediction.scores))


@pytest.mark.parametrize("fixture_seed", [0, 1, 2, 3, 4])
def test_controls_carrying_no_transferable_evidence_are_not_certified(fixture_seed):
    """An auxiliary view that corresponds to nothing, a deranged mapping of one that does, and
    a real one with the held-out links deleted from it.  None may reach a verdict: the last is
    the sharp one, since it keeps everything except the evidence the transfer carries."""
    controls = [run for run in run_fixture(args(), fixture_seed)["runs"]
                if run["arm"].endswith("-control")]
    assert len(controls) == 3
    for control in controls:
        assert control["separability"]["beats_structure_only"] != "a"


@pytest.mark.parametrize("cutoff", [1, 2, 3])
def test_ablating_the_closed_term_removes_the_result_rather_than_shrinking_it(cutoff):
    """The load-bearing design decision, measured instead of argued.  Scored with
    `open_score` — `graph_deanon.structural_score`, both arms — the de-anonymization arm keeps
    the transferred adjacency but may no longer read a transferred edge as evidence for the
    pair it joins, and nothing is left: no fixture seed is certified at any cutoff, and at
    cutoff 1 two of them are certified the other way."""
    for fixture_seed in range(5):
        attack = arm(run_fixture(args(cutoff=cutoff, scorer="open"), fixture_seed), "attack")
        assert attack["separability"]["beats_structure_only"] != "a"


@pytest.mark.parametrize("fixture_seed", [0, 1, 2, 3, 4])
def test_the_advantage_is_not_certified_at_the_looser_cutoff(fixture_seed):
    """The published nuance, asserted rather than left in prose: the ranking is better at every
    threshold, but declaring on any evidence at all buys the extra recall with enough false
    positives that the paired test reaches no verdict on a fixture this size."""
    attack = arm(run_fixture(args(cutoff=1), fixture_seed), "attack")
    assert attack["deanonymization"]["auc"] > attack["structure_only"]["auc"]
    assert attack["separability"]["beats_structure_only"] is None


def test_the_structure_only_arm_is_unchanged_by_the_auxiliary_view():
    """Both arms are scored on identical pairs and the control differs from the attack in the
    auxiliary view alone, so the structure-only column must be bit-identical across the rows.
    A control that quietly moved it would be comparing two different experiments."""
    runs = run_fixture(args(), 0)["runs"]
    assert len({tuple(sorted(run["structure_only"].items())) for run in runs}) == 1


def test_seed_provenance_is_required_and_recorded():
    views = fixture()
    seeds = sampled_seeds(views["correspondence"], 0.1, random.Random(2))
    with pytest.raises(TypeError):
        lp.predict(views["target"], views["auxiliary"], seeds, views["held_out"])
    result = lp.compare(views["target"], views["auxiliary"], seeds, views["held_out"],
                        views["negatives"], seed_provenance="withheld-correspondence-sample")
    assert result.seed_provenance == "withheld-correspondence-sample"


def test_results_document_disclaims_the_paper_reproduction_and_avoids_the_banned_phrase():
    text = open(os.path.join(ROOT, "results", MANIFEST_DOC)).read()
    assert "ground truth" not in text.lower()
    assert "not a reproduction" in text.lower()
    assert "open cell" in text.lower()


def test_the_documents_headline_table_is_the_one_the_run_produces():
    """The manifest pins the numbers; this pins the prose to them, which is the direction the
    drift actually goes."""
    text = open(os.path.join(ROOT, "results", MANIFEST_DOC)).read()
    for fixture in build_report(build_parser().parse_args([]))["fixtures"]:
        for column in ("deanonymization", "structure_only"):
            row = arm(fixture, "attack")[column]
            assert f"{row['auc']:.4f}" in text, (fixture["fixture_seed"], column, row["auc"])
            assert f"{row['recall']:.3f}" in text, (fixture["fixture_seed"], column, row["recall"])


def test_manifest_invariants_are_recomputed_and_match_results_link_prediction():
    """`check_manifest` compares invariants only when a caller recomputes and supplies them.
    The corpus is generated by the source the manifest names, so this recomputation is the
    whole check: a mechanism change that moves a published number lands here."""
    recorded = rp.read_manifest(MANIFEST_DOC, root=ROOT)
    assert recorded is not None and recorded["source"]["pattern"] == MANIFEST_SOURCE
    measured = manifest_invariants(build_report(build_parser().parse_args([])))
    status, message = rp.check_manifest(MANIFEST_DOC, measured, root=ROOT)
    assert status == "ok", message
